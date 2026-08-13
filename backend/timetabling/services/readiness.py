from collections import defaultdict

from students.models import Classroom

from ..models import Period, RoomResource, SubjectRule, TeacherSubjectAssignment, TeacherWorkloadLimit


def _build_rule_lookup(rules):
    """
    Splits rules into two lookups:
      - exact: keyed by (grade_band, stream, subject_id) for rules that target one specific stream
      - fallback: keyed by (grade_band, subject_id) for rules with a blank stream (applies to the
        whole grade, every stream)

    Returns a callable that, given a classroom and subject_id, returns the single most specific
    matching rule (exact stream match wins over the grade-wide fallback), or None. This mirrors
    the same matching semantics the solver uses, so readiness and generation never disagree about
    which rule applies to a given classroom.
    """
    exact = {}
    fallback = {}
    for rule in rules:
        if rule.stream:
            exact[(rule.grade_band, rule.stream, rule.subject_id)] = rule
        else:
            fallback[(rule.grade_band, rule.subject_id)] = rule

    def rule_for(classroom, subject_id):
        match = exact.get((classroom.grade_level, classroom.stream, subject_id))
        if match:
            return match
        return fallback.get((classroom.grade_level, subject_id))

    return rule_for


def check_timetable_readiness(tenant, term, academic_year):
    errors = []
    warnings = []

    room_counts = defaultdict(int)
    for room_type in RoomResource.objects.filter(tenant=tenant, is_active=True).values_list('room_type', flat=True):
        room_counts[room_type] += 1

    rules = list(
        SubjectRule.objects.filter(tenant=tenant, is_active=True, periods_per_week__gt=0).select_related('subject')
    )
    classrooms = list(Classroom.objects.filter(tenant=tenant, is_active=True).select_related('schedule_template'))
    subject_ids_with_rules = {rule.subject_id for rule in rules}

    rule_for = _build_rule_lookup(rules)

    assignments_qs = list(
        TeacherSubjectAssignment.objects.filter(
            tenant=tenant, term=term, academic_year=academic_year,
        ).select_related('teacher', 'subject', 'classroom')
    )
    assignment_pairs = {(a.classroom_id, a.subject_id) for a in assignments_qs}

    # --- every classroom must have a bell schedule ---
    for classroom in classrooms:
        if not classroom.schedule_template_id:
            errors.append({
                'code': 'missing_schedule_template',
                'classroom': classroom.id,
                'classroom_name': str(classroom),
                'message': f'{classroom} has no bell schedule template assigned.',
            })

    # --- every assignment must have a matching active rule with periods > 0,
    #     for THIS classroom's specific stream (or the grade-wide fallback rule) ---
    for assignment in assignments_qs:
        rule = rule_for(assignment.classroom, assignment.subject_id)
        if not rule:
            errors.append({
                'code': 'missing_subject_rule',
                'classroom': assignment.classroom.id,
                'classroom_name': str(assignment.classroom),
                'subject': assignment.subject_id,
                'subject_name': assignment.subject.name,
                'message': f'{assignment.classroom} {assignment.subject.name} has a teacher assigned but no subject rule with periods/week > 0.',
            })

    # --- room type availability check (not classroom/stream specific) ---
    for rule in rules:
        if rule.requires_room_type and room_counts[rule.requires_room_type] == 0:
            errors.append({
                'code': 'missing_room',
                'subject': rule.subject_id,
                'subject_name': rule.subject.name,
                'grade_band': rule.grade_band,
                'room_type': rule.requires_room_type,
                'message': f'{rule.subject.name} requires {rule.requires_room_type} but no matching room is configured.',
            })

    # --- every classroom must have a teacher assigned for every subject that
    #     actually applies to it (via the correct stream-aware rule) ---
    for classroom in classrooms:
        for subject_id in subject_ids_with_rules:
            rule = rule_for(classroom, subject_id)
            if not rule:
                continue
            if (classroom.id, subject_id) not in assignment_pairs:
                errors.append({
                    'code': 'missing_teacher_assignment',
                    'classroom': classroom.id,
                    'classroom_name': str(classroom),
                    'subject': subject_id,
                    'subject_name': rule.subject.name,
                    'message': f'{classroom} has no teacher assigned for {rule.subject.name}.',
                })

    # --- bell schedule supply, needed both for the per-classroom demand check
    #     below and the per-teacher oversubscription check ---
    template_supply = {}
    for period in Period.objects.filter(tenant=tenant, is_break=False):
        template_supply[period.schedule_template_id] = template_supply.get(period.schedule_template_id, 0) + 1

    # --- teacher workload: sum periods using the same stream-aware rule match,
    #     and track which bell-schedule templates each teacher's classrooms use ---
    teacher_load = defaultdict(int)
    teacher_templates = defaultdict(set)
    teacher_names = {}
    for assignment in assignments_qs:
        rule = rule_for(assignment.classroom, assignment.subject_id)
        if rule:
            teacher_load[assignment.teacher_id] += rule.periods_per_week
            teacher_templates[assignment.teacher_id].add(assignment.classroom.schedule_template_id)
            teacher_names[assignment.teacher_id] = assignment.teacher.get_full_name() or assignment.teacher.email

    # --- NEW: hard error when a teacher's total assigned periods exceed what's
    #     actually schedulable, independent of whether a TeacherWorkloadLimit is
    #     configured. A teacher can only ever occupy one period at a time, so
    #     their combined load can never exceed the smallest bell-schedule supply
    #     among the templates their classrooms use — this is a structural
    #     impossibility, not a preference, so it's an error rather than a warning.
    #     Previously nothing caught this: it silently made generation infeasible
    #     after several minutes of solver retries instead of being visible up front.
    for teacher_id, load in teacher_load.items():
        templates_used = teacher_templates.get(teacher_id) or set()
        min_supply = min((template_supply.get(t, 0) for t in templates_used), default=0)
        if load > min_supply:
            errors.append({
                'code': 'teacher_oversubscribed',
                'teacher': teacher_id,
                'teacher_name': teacher_names.get(teacher_id, f'Teacher {teacher_id}'),
                'assigned_periods': load,
                'available_periods': min_supply,
                'message': (
                    f'{teacher_names.get(teacher_id, "This teacher")} is assigned {load} periods/week '
                    f'across all their classes, but only {min_supply} periods/week exist in their bell '
                    f'schedule. Reassign some of their subjects to another teacher.'
                ),
            })

    limits = TeacherWorkloadLimit.objects.filter(tenant=tenant, max_periods_per_week__isnull=False).select_related('teacher')
    for limit in limits:
        load = teacher_load.get(limit.teacher_id, 0)
        if load > limit.max_periods_per_week:
            warnings.append({
                'code': 'teacher_overload',
                'teacher': limit.teacher_id,
                'teacher_name': limit.teacher.get_full_name() or limit.teacher.email,
                'assigned_periods': load,
                'max_periods_per_week': limit.max_periods_per_week,
                'message': f'{limit.teacher.get_full_name() or limit.teacher.email} is assigned {load} periods, above the weekly limit of {limit.max_periods_per_week}.',
            })

    # --- total demand vs bell schedule supply, computed per classroom using the
    #     same stream-aware rule match, so a Grade 8 East classroom is never
    #     charged for Grade 8 West's periods (and vice versa) ---
    for classroom in classrooms:
        supply = template_supply.get(classroom.schedule_template_id, 0)
        demand = 0
        for subject_id in subject_ids_with_rules:
            rule = rule_for(classroom, subject_id)
            if rule:
                demand += rule.periods_per_week
        if demand > supply:
            errors.append({
                'code': 'oversubscribed_schedule',
                'classroom': classroom.id,
                'classroom_name': str(classroom),
                'message': f'{classroom} needs {demand} periods/week total but its bell schedule only has {supply} non-break slots. Add more periods or reduce subject periods/week.',
            })

    return {
        'ready': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'has_subject_rules': SubjectRule.objects.filter(tenant=tenant, is_active=True).exists(),
    }