"""
Auto-assigns teachers to (classroom, subject) slots for a given term/year, so
the timetable generator has something realistic to chew on without manually
clicking through every dropdown in the setup wizard.

--- Why this does real slot-level scheduling, not just period counting ---
An earlier version of this script only compared a teacher's TOTAL periods
assigned against their TOTAL bell-schedule periods available. That's a weak
proxy: two classrooms sharing a bell-schedule template can both want the
same teacher at the literal same clock slot even when their combined period
count is well under budget. The CP-SAT solver (timetabling/services/
solver.py) reasons at the level of actual periods via AddNoOverlap on
per-teacher intervals — this script now does the same thing, tracking
exactly which Period IDs each teacher is already committed to
(`teacher_booked_periods`) and only ever reserving genuinely free ones. This
mirrors a known project lesson: "No feasible timetable found" failures trace
to upstream data (teachers double-booked across classrooms sharing a time
slot), not solver bugs — so the fix belongs here, before the solver ever
runs.

Three sources feed teacher_booked_periods, checked in this order:
  1. TimetableEntry rows from any prior solve for this term/year — these are
     REAL, already-placed periods and are treated as unconditionally fixed.
  2. Existing TeacherSubjectAssignment rows that haven't been solved yet
     (no matching TimetableEntry) — these get a virtual/retroactive
     reservation pass so the picture stays consistent before new
     assignments are added on top. If an existing assignment can't find
     enough free periods for its teacher even on its own, that's reported
     as a pre-existing conflict — this is the same failure mode that
     produces a solver "No feasible timetable found" error, just caught
     here instead.
  3. New assignments this run creates, reserved as they're made.

What this does NOT model: exact placement of double lessons (requires_double
just needs enough distinct free periods, not necessarily adjacent ones —
the solver still owns final placement and pairing), room contention, and
soft time preferences. Those stay the solver's job; this script only
guarantees each teacher has enough truly free periods to make a feasible
placement possible.

Usage:
    docker compose exec backend python manage.py auto_assign_teachers \
        --school-name "Demo School" --term term1 --academic-year 2026

    # Wipe existing assignments for that term/year first, then reassign —
    # recommended for a clean, guaranteed-conflict-free run:
    docker compose exec backend python manage.py auto_assign_teachers \
        --school-name "Demo School" --term term1 --academic-year 2026 --clear

    # Preview only, writes nothing:
    docker compose exec backend python manage.py auto_assign_teachers \
        --school-name "Demo School" --term term1 --academic-year 2026 --dry-run
"""
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser, StaffProfile
from students.models import Classroom
from tenants.models import Tenant
from timetabling.models import (
    Period,
    SubjectRule,
    TeacherAvailability,
    TeacherSubjectAssignment,
    TimetableEntry,
)
# Reusing the canonical stream-aware matcher rather than re-implementing it
# here — this is the same function readiness.py (and, separately, solver.py
# has its own near-identical copy) uses, so "does this rule apply to this
# classroom" can never disagree between this script and Readiness.
from timetabling.services.readiness import _build_rule_lookup


class Command(BaseCommand):
    help = 'Auto-assign teachers to classroom+subject slots for testing the timetable generator.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--school-code', default=None,
            help='Tenant school_code, e.g. DEMO001. Use --school-name instead if codes aren\'t set up yet.',
        )
        parser.add_argument(
            '--school-name', default=None,
            help='Case-insensitive partial match on tenant name, e.g. "Demo School". Alternative to --school-code.',
        )
        parser.add_argument(
            '--term', choices=[c for c, _ in TeacherSubjectAssignment.Term.choices],
            default=TeacherSubjectAssignment.Term.TERM_1,
        )
        parser.add_argument('--academic-year', type=int, default=None, help='Defaults to the current year.')
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete existing assignments for this tenant/term/year before assigning. '
                 'Recommended for a clean, guaranteed-conflict-free run.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would happen without writing anything to the database.',
        )

    def _resolve_tenant(self, school_code, school_name):
        if not school_code and not school_name:
            raise CommandError('Pass either --school-code or --school-name to identify the tenant.')

        def describe(t):
            code = t.school_code or '(no code set)'
            return f'"{t.name}" [id={t.id}, code={code}]'

        if school_code:
            try:
                return Tenant.objects.get(school_code=school_code)
            except Tenant.DoesNotExist:
                available = '\n    '.join(describe(t) for t in Tenant.objects.all()) or '(no tenants exist)'
                raise CommandError(
                    f'No tenant with school_code="{school_code}". Available tenants:\n    {available}\n'
                    f'Try --school-name instead if school codes aren\'t set up for this tenant yet.'
                )

        matches = list(Tenant.objects.filter(name__icontains=school_name))
        if not matches:
            available = '\n    '.join(describe(t) for t in Tenant.objects.all()) or '(no tenants exist)'
            raise CommandError(f'No tenant name contains "{school_name}". Available tenants:\n    {available}')
        if len(matches) > 1:
            listed = '\n    '.join(describe(t) for t in matches)
            raise CommandError(f'"{school_name}" matches multiple tenants — be more specific:\n    {listed}')
        return matches[0]

    def handle(self, *args, **options):
        term = options['term']
        academic_year = options['academic_year'] or timezone.now().year
        clear = options['clear']
        dry_run = options['dry_run']

        tenant = self._resolve_tenant(options['school_code'], options['school_name'])
        school_code = tenant.school_code or tenant.name

        if clear:
            if dry_run:
                count = TeacherSubjectAssignment.objects.filter(
                    tenant=tenant, term=term, academic_year=academic_year,
                ).count()
                self.stdout.write(self.style.WARNING(f'[dry-run] Would delete {count} existing assignments.'))
            else:
                deleted, _ = TeacherSubjectAssignment.objects.filter(
                    tenant=tenant, term=term, academic_year=academic_year,
                ).delete()
                self.stdout.write(self.style.WARNING(f'Deleted {deleted} existing assignments.'))

        teachers = list(CustomUser.objects.filter(tenant=tenant, role='teacher').order_by('id'))
        if not teachers:
            raise CommandError(f'No teachers found for tenant {school_code}. Add teachers before running this.')

        classrooms = list(
            Classroom.objects.filter(tenant=tenant, is_active=True).select_related('schedule_template')
        )
        if not classrooms:
            raise CommandError(f'No active classrooms found for tenant {school_code}.')

        rules = list(
            SubjectRule.objects.filter(tenant=tenant, is_active=True, periods_per_week__gt=0)
            .select_related('subject').prefetch_related('excluded_periods')
        )
        if not rules:
            raise CommandError('No active subject rules with periods_per_week > 0. Set those up first (step 3).')

        rule_for = _build_rule_lookup(rules)
        subject_ids_with_rules = {rule.subject_id for rule in rules}
        subject_names = {rule.subject_id: rule.subject.name for rule in rules}
        hard_excluded_by_rule = {
            rule.id: {p.id for p in rule.excluded_periods.all()} if rule.is_hard_excluded else set()
            for rule in rules
        }

        # Qualification map: teacher_id -> set of subject_ids they're qualified
        # for, from StaffProfile.subjects_qualified.
        qualified_subjects_by_teacher = defaultdict(set)
        for profile in StaffProfile.objects.filter(tenant=tenant, user_id__isnull=False).prefetch_related('subjects_qualified'):
            qualified_subjects_by_teacher[profile.user_id] = {s.id for s in profile.subjects_qualified.all()}

        # Ordered, non-break periods per bell-schedule template — the same
        # candidate pool solver.py builds.
        periods_by_template = defaultdict(list)
        for period in Period.objects.filter(tenant=tenant, is_break=False).order_by('day_of_week', 'order'):
            periods_by_template[period.schedule_template_id].append(period)

        blocked_availability = set(
            TeacherAvailability.objects.filter(tenant=tenant, is_available=False)
            .values_list('teacher_id', 'period_id')
        )

        # --- Source 1: real, already-solved placements are unconditionally
        # fixed. Deliberately scoped to any job for this term/year, not just
        # the latest one — safer to over-avoid a stale job's periods than to
        # under-count and reproduce the exact bug this rewrite fixes.
        teacher_booked_periods = defaultdict(set)
        solved_keys = set()
        for entry in TimetableEntry.objects.filter(
            tenant=tenant, job__term=term, job__academic_year=academic_year,
        ).values_list('teacher_id', 'period_id', 'classroom_id', 'subject_id'):
            teacher_id, period_id, classroom_id, subject_id = entry
            teacher_booked_periods[teacher_id].add(period_id)
            solved_keys.add((teacher_id, classroom_id, subject_id))

        def reserve_periods(teacher_id, classroom, subject_id, periods_needed):
            """Try to reserve `periods_needed` genuinely free periods for this
            teacher within this classroom's bell schedule. Returns the list of
            reserved Period objects, or None if there aren't enough free."""
            rule = rule_for(classroom, subject_id)
            if not rule:
                return None
            candidates = periods_by_template.get(classroom.schedule_template_id, [])
            excluded = hard_excluded_by_rule.get(rule.id, set())
            free = [
                p for p in candidates
                if p.id not in excluded
                and p.id not in teacher_booked_periods[teacher_id]
                and (teacher_id, p.id) not in blocked_availability
            ]
            if len(free) < periods_needed:
                return None
            chosen = free[:periods_needed]
            for p in chosen:
                teacher_booked_periods[teacher_id].add(p.id)
            return chosen

        # --- Source 2: existing, not-yet-solved assignments get a
        # retroactive reservation pass, in a stable order, so new
        # assignments correctly see them as committed. Anything that fails
        # here is a pre-existing conflict — the same condition that produces
        # a solver "No feasible timetable found" failure.
        existing = list(
            TeacherSubjectAssignment.objects.filter(tenant=tenant, term=term, academic_year=academic_year)
            .select_related('classroom')
        )
        already_assigned_pairs = {(a.classroom_id, a.subject_id) for a in existing}

        preexisting_conflicts = []
        for a in sorted(existing, key=lambda a: (a.classroom.grade_level, a.classroom.stream or '', a.subject_id)):
            if (a.teacher_id, a.classroom_id, a.subject_id) in solved_keys:
                continue
            rule = rule_for(a.classroom, a.subject_id)
            if not rule:
                continue
            if reserve_periods(a.teacher_id, a.classroom, a.subject_id, rule.periods_per_week) is None:
                preexisting_conflicts.append((a.classroom, a.subject_id, a.teacher_id))

        # --- Source 3: new (classroom, subject) jobs without an assignment
        # yet.
        jobs = []
        for classroom in classrooms:
            for subject_id in subject_ids_with_rules:
                rule = rule_for(classroom, subject_id)
                if not rule:
                    continue
                if (classroom.id, subject_id) in already_assigned_pairs:
                    continue
                jobs.append((classroom, subject_id, rule.periods_per_week))

        to_create = []
        no_bell_schedule = []
        no_capacity = []
        cycle_pointer = 0

        for classroom, subject_id, periods_needed in jobs:
            if not classroom.schedule_template_id:
                no_bell_schedule.append((classroom, subject_id))
                continue

            qualified_pool = [t for t in teachers if subject_id in qualified_subjects_by_teacher.get(t.id, set())]

            assigned_teacher = None

            # Pass 1: prefer qualified teachers, if any exist.
            if qualified_pool:
                for offset in range(len(qualified_pool)):
                    candidate = qualified_pool[(cycle_pointer + offset) % len(qualified_pool)]
                    if reserve_periods(candidate.id, classroom, subject_id, periods_needed) is not None:
                        assigned_teacher = candidate
                        break

            # Pass 2: qualification either doesn't apply here or every
            # qualified candidate was already full — fall back to ANY
            # teacher with genuinely free periods, rather than giving up.
            # This is the actual bug fix: the previous version only fell
            # back to the full pool when qualified_pool was empty, not when
            # it existed but was exhausted — so a subject with one busy
            # "qualified" teacher and fifty wide-open unqualified ones was
            # incorrectly reported as full.
            if not assigned_teacher:
                for offset in range(len(teachers)):
                    candidate = teachers[(cycle_pointer + offset) % len(teachers)]
                    if reserve_periods(candidate.id, classroom, subject_id, periods_needed) is not None:
                        assigned_teacher = candidate
                        break

            cycle_pointer += 1

            if not assigned_teacher:
                no_capacity.append((classroom, subject_id, periods_needed))
                continue

            to_create.append(TeacherSubjectAssignment(
                tenant=tenant,
                teacher=assigned_teacher,
                subject_id=subject_id,
                classroom=classroom,
                term=term,
                academic_year=academic_year,
            ))

        # --- Report ---
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO(
            f'{school_code} — {dict(TeacherSubjectAssignment.Term.choices)[term]} {academic_year}'
        ))
        self.stdout.write(f'  Classrooms: {len(classrooms)}   Teachers: {len(teachers)}   Rules: {len(rules)}')
        self.stdout.write(f'  Already assigned (skipped): {len(already_assigned_pairs)}')
        self.stdout.write(self.style.SUCCESS(f'  To assign: {len(to_create)}'))

        if preexisting_conflicts:
            self.stdout.write(self.style.ERROR(
                f'  Pre-existing conflicts found: {len(preexisting_conflicts)} '
                f'(these were already in the database before this run and don\'t have enough free '
                f'periods for their teacher — this is very likely why generation failed for these classrooms)'
            ))
            for classroom, subject_id, teacher_id in preexisting_conflicts[:10]:
                self.stdout.write(f'    - {classroom} / {subject_names.get(subject_id, subject_id)} (teacher id {teacher_id})')
            if len(preexisting_conflicts) > 10:
                self.stdout.write(f'    ... and {len(preexisting_conflicts) - 10} more')
            self.stdout.write(
                '  Re-run with --clear for a clean, guaranteed-conflict-free reassignment '
                '(this will delete and rebuild all assignments for this term/year).'
            )

        if no_bell_schedule:
            self.stdout.write(self.style.WARNING(f'  Skipped — classroom has no bell schedule: {len(no_bell_schedule)}'))
            for classroom, subject_id in no_bell_schedule[:10]:
                self.stdout.write(f'    - {classroom} / {subject_names.get(subject_id, subject_id)}')
            if len(no_bell_schedule) > 10:
                self.stdout.write(f'    ... and {len(no_bell_schedule) - 10} more')

        if no_capacity:
            self.stdout.write(self.style.WARNING(f'  Left unassigned — no teacher had enough free periods: {len(no_capacity)}'))
            for classroom, subject_id, periods_needed in no_capacity[:10]:
                self.stdout.write(
                    f'    - {classroom} / {subject_names.get(subject_id, subject_id)} '
                    f'({periods_needed} periods/week needed)'
                )
            if len(no_capacity) > 10:
                self.stdout.write(f'    ... and {len(no_capacity) - 10} more')
            self.stdout.write(
                '  These are genuinely full — either add more teachers, raise bell-schedule '
                'period counts, or reduce periods_per_week on the affected subject rules.'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[dry-run] Nothing was written to the database.'))
            return

        with transaction.atomic():
            TeacherSubjectAssignment.objects.bulk_create(to_create, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(f'\nCreated {len(to_create)} teacher-subject assignments.'))
