import time
from collections import defaultdict

from django.conf import settings
from django.db import transaction

from students.models import Classroom

from ..models import (
    Period,
    RoomResource,
    SubjectRule,
    TeacherAvailability,
    TeacherSubjectAssignment,
    TeacherWorkloadLimit,
    TimetableEntry,
    TimetableJob,
)


class TimetableSolveError(Exception):
    pass


# --- Soft scheduling preference tuning ------------------------------------
MORNING_CUTOFF_HOUR = 14  # 2:00 PM

TIME_PREFERENCE_WEIGHTS = {
    SubjectRule.TimePreference.PREFER_MORNING: 2,
    SubjectRule.TimePreference.STRONG_MORNING: 6,
    SubjectRule.TimePreference.PREFER_AFTERNOON: 2,
}

SOFT_DAILY_TEACHER_THRESHOLD = 6
SOFT_DAILY_TEACHER_WEIGHT = 3

EMPTY_SLOT_PENALTY = 50  # Strongly prefer filling every period


def _minute_of_week(period):
    return ((period.day_of_week - 1) * 24 * 60) + period.start_time.hour * 60 + period.start_time.minute


def _duration_minutes(period):
    return (period.end_time.hour * 60 + period.end_time.minute) - (period.start_time.hour * 60 + period.start_time.minute)


def _is_morning(period):
    return period.start_time.hour < MORNING_CUTOFF_HOUR


def _build_rule_lookup(rules_queryset):
    exact = {}
    fallback = {}
    for rule in rules_queryset:
        if rule.stream:
            exact[(rule.grade_band, rule.stream, rule.subject_id)] = rule
        else:
            fallback[(rule.grade_band, rule.subject_id)] = rule

    def rule_for(classroom, subject_id):
        exact_match = exact.get((classroom.grade_level, classroom.stream, subject_id))
        if exact_match:
            return exact_match
        return fallback.get((classroom.grade_level, subject_id))

    return rule_for


def solve_timetable_job(
    job_id,
    tenant_id,
    class_stream_ids=None,
    diagnostic_relaxation=None,
    persist=True,
    max_seconds=None,
    skip_diagnostics=False,
):
    try:
        from ortools.sat.python import cp_model
    except ImportError as exc:
        raise TimetableSolveError('Google OR-Tools is not installed. Run pip install -r requirements.txt.') from exc

    started = time.monotonic()
    job = TimetableJob.objects.select_related('tenant').get(id=job_id, tenant_id=tenant_id)
    tenant = job.tenant
    affected_ids = set(class_stream_ids or [])

    classrooms = Classroom.objects.filter(tenant=tenant, is_active=True, schedule_template__isnull=False)
    if affected_ids:
        classrooms = classrooms.filter(id__in=affected_ids)
    classrooms = list(classrooms.select_related('schedule_template'))

    if not classrooms:
        raise TimetableSolveError(
            'No active classrooms have a bell schedule template assigned. '
            'Go to Timetable Setup and link a schedule template to your classes.'
        )

    rule_for = _build_rule_lookup(
        SubjectRule.objects.filter(tenant=tenant, is_active=True, periods_per_week__gt=0).prefetch_related('excluded_periods')
    )
    assignments = list(
        TeacherSubjectAssignment.objects.filter(
            tenant=tenant,
            classroom__in=classrooms,
            term=job.term,
            academic_year=job.academic_year,
        ).select_related('teacher', 'subject', 'classroom')
    )

    if not assignments:
        raise TimetableSolveError(
            f'No teacher-subject-classroom assignments found for {job.term} {job.academic_year}. '
            'Assign teachers to classes for this term in the Timetable Setup wizard.'
        )

    # ---- Pre-validation: teacher workload vs limits ----
    if diagnostic_relaxation != 'workload':
        workload_limits = {
            limit.teacher_id: limit
            for limit in TeacherWorkloadLimit.objects.filter(tenant=tenant)
        }
        teacher_required = defaultdict(int)
        for assignment in assignments:
            rule = rule_for(assignment.classroom, assignment.subject_id)
            if rule:
                teacher_required[assignment.teacher_id] += rule.periods_per_week

        for teacher_id, required in teacher_required.items():
            limit = workload_limits.get(teacher_id)
            if limit and limit.max_periods_per_week is not None and required > limit.max_periods_per_week:
                raise TimetableSolveError(
                    f'Teacher {teacher_id} requires {required} periods but weekly limit is {limit.max_periods_per_week}. '
                    'Adjust workload limits or assignment counts.'
                )
    else:
        workload_limits = {}

    periods_by_template = defaultdict(list)
    for period in Period.objects.filter(
        tenant=tenant,
        schedule_template_id__in={c.schedule_template_id for c in classrooms},
        is_break=False,
    ).order_by('day_of_week', 'order'):
        periods_by_template[period.schedule_template_id].append(period)

    for classroom in classrooms:
        supply = len(periods_by_template.get(classroom.schedule_template_id, []))
        demand = 0
        for assignment in assignments:
            if assignment.classroom_id != classroom.id:
                continue
            rule = rule_for(classroom, assignment.subject_id)
            if rule:
                demand += rule.periods_per_week
        if demand > supply:
            raise TimetableSolveError(
                f'Classroom "{classroom.name}" needs {demand} periods/week total but '
                f'its bell schedule only has {supply} non-break slots. '
                'Reduce the periods_per_week for some subjects or add more teaching periods.'
            )

    rooms_by_type = defaultdict(list)
    for room in RoomResource.objects.filter(tenant=tenant, is_active=True):
        rooms_by_type[room.room_type].append(room)

    blocked_availability = set()
    if diagnostic_relaxation != 'teacher_availability':
        blocked_availability = set(
            TeacherAvailability.objects.filter(
                tenant=tenant,
                is_available=False,
            ).values_list('teacher_id', 'period_id')
        )

    # workload_limits already defined above

    model = cp_model.CpModel()
    variables = {}
    teacher_intervals = defaultdict(list)
    room_intervals = defaultdict(list)
    class_period_vars = defaultdict(list)
    teacher_day_vars = defaultdict(list)
    teacher_week_vars = defaultdict(list)
    subject_day_vars = defaultdict(list)
    penalties = []
    fixed_class_periods = set()

    for assignment in assignments:
        rule = rule_for(assignment.classroom, assignment.subject_id)
        if not rule:
            continue
        periods = periods_by_template[assignment.classroom.schedule_template_id]
        excluded = set()
        if diagnostic_relaxation != 'excluded_periods' and rule.is_hard_excluded:
            excluded = set(rule.excluded_periods.values_list('id', flat=True))
        soft_excluded = set()
        if not rule.is_hard_excluded:
            soft_excluded = set(rule.excluded_periods.values_list('id', flat=True))
        room_options = [None]
        if rule.requires_room_type:
            room_options = rooms_by_type.get(rule.requires_room_type, [])
            if diagnostic_relaxation == 'room':
                room_options = room_options or [None]
        time_pref_weight = TIME_PREFERENCE_WEIGHTS.get(rule.time_preference)
        for period in periods:
            if period.id in excluded or (assignment.teacher_id, period.id) in blocked_availability:
                continue
            for room in room_options:
                name = f'a{assignment.id}_p{period.id}_r{getattr(room, "id", 0)}'
                var = model.NewBoolVar(name)
                variables[(assignment.id, period.id, getattr(room, 'id', None))] = (var, assignment, period, room, rule)
                class_period_vars[(assignment.classroom_id, period.id)].append(var)
                teacher_day_vars[(assignment.teacher_id, period.day_of_week)].append(var)
                teacher_week_vars[assignment.teacher_id].append(var)
                subject_day_vars[(assignment.classroom_id, assignment.subject_id, period.day_of_week)].append(var)
                teacher_intervals[assignment.teacher_id].append(
                    model.NewOptionalIntervalVar(
                        _minute_of_week(period),
                        _duration_minutes(period),
                        _minute_of_week(period) + _duration_minutes(period),
                        var,
                        f't{assignment.teacher_id}_{name}',
                    )
                )
                if room and diagnostic_relaxation != 'room':
                    room_intervals[room.id].append(
                        model.NewOptionalIntervalVar(
                            _minute_of_week(period),
                            _duration_minutes(period),
                            _minute_of_week(period) + _duration_minutes(period),
                            var,
                            f'room{room.id}_{name}',
                        )
                    )
                if period.id in soft_excluded:
                    penalties.append(var * 5)

                if time_pref_weight:
                    is_morning = _is_morning(period)
                    wants_morning = rule.time_preference in (
                        SubjectRule.TimePreference.PREFER_MORNING,
                        SubjectRule.TimePreference.STRONG_MORNING,
                    )
                    if wants_morning and not is_morning:
                        penalties.append(var * time_pref_weight)
                    elif rule.time_preference == SubjectRule.TimePreference.PREFER_AFTERNOON and is_morning:
                        penalties.append(var * time_pref_weight)

    fixed_entries = TimetableEntry.objects.filter(tenant=tenant, job=job).select_related('period', 'room')
    if affected_ids:
        fixed_entries = fixed_entries.exclude(classroom_id__in=affected_ids, locked=False)
    else:
        fixed_entries = fixed_entries.filter(locked=True)
    for entry in fixed_entries:
        teacher_intervals[entry.teacher_id].append(
            model.NewIntervalVar(
                _minute_of_week(entry.period),
                _duration_minutes(entry.period),
                _minute_of_week(entry.period) + _duration_minutes(entry.period),
                f'fixed_t{entry.teacher_id}_e{entry.id}',
            )
        )
        if entry.room_id and diagnostic_relaxation != 'room':
            room_intervals[entry.room_id].append(
                model.NewIntervalVar(
                    _minute_of_week(entry.period),
                    _duration_minutes(entry.period),
                    _minute_of_week(entry.period) + _duration_minutes(entry.period),
                    f'fixed_room{entry.room_id}_e{entry.id}',
                )
            )
        fixed_class_periods.add((entry.classroom_id, entry.period_id))

    fixed_teacher_week_counts = defaultdict(int)
    fixed_teacher_day_counts = defaultdict(lambda: defaultdict(int))
    for entry in fixed_entries:
        fixed_teacher_week_counts[entry.teacher_id] += 1
        fixed_teacher_day_counts[entry.teacher_id][entry.period.day_of_week] += 1

    for slot, vars_for_slot in class_period_vars.items():
        if slot in fixed_class_periods:
            for var in vars_for_slot:
                model.Add(var == 0)
        model.AddAtMostOne(vars_for_slot)
    for intervals in teacher_intervals.values():
        model.AddNoOverlap(intervals)
    for intervals in room_intervals.values():
        model.AddNoOverlap(intervals)

    # --- Strongly penalize empty slots to maximize timetable coverage ---
    for classroom in classrooms:
        for period in periods_by_template[classroom.schedule_template_id]:
            slot = (classroom.id, period.id)
            if slot in fixed_class_periods:
                continue
            vars_for_slot = class_period_vars.get(slot, [])
            if vars_for_slot:
                slot_filled = model.NewBoolVar(f'filled_{classroom.id}_{period.id}')
                model.Add(sum(vars_for_slot) >= 1).OnlyEnforceIf(slot_filled)
                model.Add(sum(vars_for_slot) == 0).OnlyEnforceIf(slot_filled.Not())
                penalties.append((1 - slot_filled) * EMPTY_SLOT_PENALTY)

    for assignment in assignments:
        rule = rule_for(assignment.classroom, assignment.subject_id)
        if not rule:
            continue
        assignment_vars = [data[0] for key, data in variables.items() if key[0] == assignment.id]
        if not assignment_vars:
            raise TimetableSolveError(f'No candidate periods for {assignment.classroom} {assignment.subject.name}.')
        model.Add(sum(assignment_vars) == rule.periods_per_week)

        if rule.requires_double:
            if rule.periods_per_week < 2:
                raise TimetableSolveError(
                    f'{assignment.classroom} {assignment.subject.name} requires double lessons '
                    f'but only has {rule.periods_per_week} period(s) per week.'
                )
            periods = periods_by_template[assignment.classroom.schedule_template_id]
            next_period = {
                (period.day_of_week, period.order): period
                for period in periods
            }
            pair_vars = []
            for key, data in variables.items():
                if key[0] != assignment.id:
                    continue
                var, _assignment, period, room, _rule = data
                following = next_period.get((period.day_of_week, period.order + 1))
                if not following:
                    continue
                other_key = (assignment.id, following.id, getattr(room, 'id', None))
                other = variables.get(other_key)
                if not other:
                    continue
                pair = model.NewBoolVar(f'double_a{assignment.id}_p{period.id}_{following.id}_r{getattr(room, "id", 0)}')
                model.Add(pair <= var)
                model.Add(pair <= other[0])
                model.Add(pair >= var + other[0] - 1)
                pair_vars.append(pair)
            if not pair_vars:
                raise TimetableSolveError(
                    f'No consecutive periods available for double lesson '
                    f'{assignment.classroom} {assignment.subject.name}.'
                )
            model.Add(sum(pair_vars) >= rule.periods_per_week // 2)

    for teacher_id, limit in workload_limits.items():
        if limit.max_periods_per_week is not None and teacher_id in teacher_week_vars:
            remaining = limit.max_periods_per_week - fixed_teacher_week_counts.get(teacher_id, 0)
            model.Add(sum(teacher_week_vars[teacher_id]) <= max(0, remaining))
        if limit.max_periods_per_day is not None:
            for day in range(1, 8):
                day_vars = teacher_day_vars.get((teacher_id, day), [])
                if day_vars:
                    remaining = limit.max_periods_per_day - fixed_teacher_day_counts[teacher_id].get(day, 0)
                    model.Add(sum(day_vars) <= max(0, remaining))

    for (teacher_id, day), day_vars in teacher_day_vars.items():
        fixed_count = fixed_teacher_day_counts[teacher_id].get(day, 0)
        if len(day_vars) + fixed_count <= SOFT_DAILY_TEACHER_THRESHOLD:
            continue
        overflow = model.NewIntVar(0, len(day_vars), f'dayload_t{teacher_id}_d{day}')
        model.Add(overflow >= sum(day_vars) + fixed_count - SOFT_DAILY_TEACHER_THRESHOLD)
        penalties.append(overflow * SOFT_DAILY_TEACHER_WEIGHT)

    for (classroom_id, subject_id, day), day_vars in subject_day_vars.items():
        used = model.NewBoolVar(f'used_{classroom_id}_{subject_id}_{day}')
        model.Add(sum(day_vars) >= 1).OnlyEnforceIf(used)
        model.Add(sum(day_vars) == 0).OnlyEnforceIf(used.Not())
        penalties.append(sum(day_vars) - used)

    if not variables:
        raise TimetableSolveError(
            'No timetable variables could be created. '
            'Check that subject rules, teacher assignments, classroom schedule templates, and periods are configured.'
        )

    model.Minimize(sum(penalties) if penalties else 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_seconds or getattr(settings, 'TIMETABLE_SOLVER_MAX_SECONDS', 300)
    solver.parameters.num_search_workers = getattr(settings, 'TIMETABLE_SOLVER_WORKERS', 8)
    if getattr(settings, 'DEBUG', False):
        solver.parameters.log_search_progress = True

    class TimetableProgressCallback(cp_model.CpSolverSolutionCallback):
        def __init__(self, tracked_job_id):
            cp_model.CpSolverSolutionCallback.__init__(self)
            self.tracked_job_id = tracked_job_id
            self.best = None

        def on_solution_callback(self):
            objective = self.ObjectiveValue()
            if self.best is None or objective < self.best:
                self.best = objective
                TimetableJob.objects.filter(id=self.tracked_job_id).update(
                    current_score=objective,
                    best_bound=self.BestObjectiveBound(),
                )

    callback = TimetableProgressCallback(job.id)
    status = solver.Solve(model, callback)

    if status == cp_model.INFEASIBLE:
        if skip_diagnostics:
            reason = 'Whole-school model is infeasible within the probing time limit.'
            if persist:
                job.failure_reason = reason
                job.status = TimetableJob.Status.FAILED
                job.solve_time_seconds = time.monotonic() - started
                job.save(update_fields=['failure_reason', 'status', 'solve_time_seconds', 'updated_at'])
            return {'status': 'failed', 'reason': reason}
        if persist:
            reason = diagnose_timetable_failure(job, tenant_id, class_stream_ids)
            job.failure_reason = reason
            job.status = TimetableJob.Status.FAILED
            job.solve_time_seconds = time.monotonic() - started
            job.save(update_fields=['failure_reason', 'status', 'solve_time_seconds', 'updated_at'])
        return {'status': 'failed', 'reason': job.failure_reason or 'No feasible timetable found.'}
    elif status == cp_model.UNKNOWN:
        timeout_reason = (
            'Solver timed out before finding a feasible timetable. '
            'The problem may be too large for a whole-school solve. '
            'Try regenerating for individual classrooms or streams instead, '
            'which is a dramatically smaller search space.'
        )
        if persist:
            job.failure_reason = timeout_reason
            job.status = TimetableJob.Status.FAILED
            job.solve_time_seconds = time.monotonic() - started
            job.save(update_fields=['failure_reason', 'status', 'solve_time_seconds', 'updated_at'])
        return {'status': 'failed', 'reason': job.failure_reason or timeout_reason}
    elif status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        invalid_reason = (
            'The timetable model is invalid — this usually indicates a bug '
            'in the solver setup (e.g., conflicting fixed entries).'
        )
        if persist:
            job.failure_reason = invalid_reason
            job.status = TimetableJob.Status.FAILED
            job.solve_time_seconds = time.monotonic() - started
            job.save(update_fields=['failure_reason', 'status', 'solve_time_seconds', 'updated_at'])
        return {'status': 'failed', 'reason': job.failure_reason or invalid_reason}

    solved_entries = []
    for var, assignment, period, room, _rule in variables.values():
        if solver.BooleanValue(var):
            solved_entries.append((assignment, period, room))

    if persist:
        with transaction.atomic():
            if affected_ids:
                TimetableEntry.objects.filter(tenant=tenant, job=job, classroom_id__in=affected_ids, locked=False).delete()
            else:
                TimetableEntry.objects.filter(tenant=tenant, job=job, locked=False).delete()
            TimetableEntry.objects.bulk_create([
                TimetableEntry(
                    tenant=tenant,
                    job=job,
                    classroom=assignment.classroom,
                    subject=assignment.subject,
                    teacher=assignment.teacher,
                    period=period,
                    room=room,
                )
                for assignment, period, room in solved_entries
            ])
            job.status = TimetableJob.Status.DONE
            job.current_score = solver.ObjectiveValue()
            job.best_bound = solver.BestObjectiveBound()
            job.solve_time_seconds = time.monotonic() - started
            job.failure_reason = ''
            job.save(update_fields=['status', 'current_score', 'best_bound', 'solve_time_seconds', 'failure_reason', 'updated_at'])

    return {'status': 'done', 'entries': len(solved_entries), 'score': solver.ObjectiveValue()}


def diagnose_timetable_failure(job, tenant_id, class_stream_ids=None):
    checks = [
        ('workload', 'Relaxing teacher workload limits made the timetable feasible. Review teacher max periods per day/week.'),
        ('room', 'Relaxing room availability made the timetable feasible. Add more matching rooms or reduce room-required lessons.'),
        ('teacher_availability', 'Relaxing teacher availability blocks made the timetable feasible. Review blocked slots for assigned teachers.'),
        ('excluded_periods', 'Relaxing subject excluded periods made the timetable feasible. Review hard excluded period rules.'),
    ]
    for key, message in checks:
        try:
            result = solve_timetable_job(
                job.id,
                tenant_id,
                class_stream_ids=class_stream_ids,
                diagnostic_relaxation=key,
                persist=False,
                skip_diagnostics=True,  # Prevent recursive diagnosis loops
            )
        except Exception:
            continue
        if result.get('status') == 'done':
            return message
    return 'No feasible timetable found with the current rules, teacher assignments, availability, and room setup.'