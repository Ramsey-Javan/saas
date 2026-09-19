import logging
import time
import os

from celery import shared_task
from django.db.models import Count
from django.utils import timezone

from .models import TimetableJob
from .services.solver import solve_timetable_job, TimetableSolveError

logger = logging.getLogger(__name__)

# Hard ceiling per classroom (seconds). Single-classroom CP-SAT models are tiny;
# 30 s is usually enough, but can be increased via environment variable.
PER_CLASSROOM_BUDGET = int(os.environ.get('PER_CLASSROOM_BUDGET', 30))

# If more than this many classrooms fail in sequential mode, fall back to whole-school solve
FALLBACK_FAILURE_THRESHOLD = 3

# Overall wall-clock ceiling for the ENTIRE sequential loop across every
# classroom, not any single classroom's budget. A large school with many
# genuinely-infeasible classrooms could otherwise run far longer than any
# single Celery task_time_limit could safely bound without either killing
# legitimate large-school runs or being set uselessly high — each failing
# classroom can cost up to PER_CLASSROOM_BUDGET * 5 (the initial attempt
# plus 4 relaxation attempts) before giving up on it. Once this is
# exceeded, the loop stops attempting further classrooms and reports them
# as skipped rather than continuing indefinitely.
OVERALL_SOLVE_BUDGET = int(os.environ.get('OVERALL_SOLVE_BUDGET', 1200))  # 20 minutes


@shared_task(name='timetabling.tasks.generate_timetable')
def generate_timetable_task(job_id, tenant_id):
    TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
        status=TimetableJob.Status.RUNNING,
        updated_at=timezone.now(),
    )
    try:
        # Monolithic whole-school solves are exponential in classroom count.
        # Go straight to greedy sequential — each sub-problem is trivial.
        return _solve_classrooms_sequential(job_id, tenant_id)
    except Exception as exc:
        logger.exception('Timetable generation failed for job %s', job_id)
        TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
            status=TimetableJob.Status.FAILED,
            failure_reason=str(exc),
            updated_at=timezone.now(),
        )
        return {'status': 'failed', 'reason': str(exc)}


def _solve_classrooms_sequential(job_id, tenant_id):
    """
    Greedy sequential solve: one classroom at a time, treating previously
    solved classrooms as fixed constraints. Per-classroom timeout is configurable.
    If a classroom fails, try relaxing constraints one by one.
    If too many fail, fall back to a whole-school solve.
    """
    from students.models import Classroom

    # Order classrooms by number of teacher-subject assignments (most constrained first)
    classroom_ids = list(
        Classroom.objects.filter(
            tenant_id=tenant_id, is_active=True, schedule_template__isnull=False
        )
        .annotate(assignment_count=Count('subject_assignments'))  # <-- fixed field name
        .order_by('-assignment_count', '-grade_level', 'stream', 'name')
        .values_list('id', flat=True)
    )

    if not classroom_ids:
        msg = 'No active classrooms with schedule templates found.'
        TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
            status=TimetableJob.Status.FAILED,
            failure_reason=msg,
            updated_at=timezone.now(),
        )
        return {'status': 'failed', 'reason': msg}

    started = time.monotonic()
    total_entries = 0
    failed = []
    ran_out_of_time = False

    for idx, classroom_id in enumerate(classroom_ids, start=1):
        elapsed_so_far = time.monotonic() - started
        if elapsed_so_far > OVERALL_SOLVE_BUDGET:
            logger.warning(
                '[Job %s] Overall solve budget (%ss) exceeded after %d/%d classrooms — '
                'stopping here rather than continuing indefinitely.',
                job_id, OVERALL_SOLVE_BUDGET, idx - 1, len(classroom_ids),
            )
            ran_out_of_time = True
            for remaining_id in classroom_ids[idx - 1:]:
                failed.append((remaining_id, 'Skipped — generation ran out of overall time budget before reaching this classroom.'))
            break

        logger.info(
            '[Job %s] Solving classroom %s (%d/%d) — budget %ss',
            job_id, classroom_id, idx, len(classroom_ids), PER_CLASSROOM_BUDGET,
        )

        # skip_diagnostics=True: avoid running solver.py's own 4-attempt
        # diagnose_timetable_failure on every single failure — this loop's
        # own _try_relaxed_solve immediately does real relaxation attempts
        # right below, so running both was 8 solves per failing classroom
        # where 4 sufficed, eating directly into OVERALL_SOLVE_BUDGET.
        # mark_job_status=False: this is one step of a larger sequential
        # run, not a standalone solve — without this, job.status would
        # flip to DONE after the first classroom succeeds (or FAILED after
        # any single one fails, even ones this loop is about to fix via
        # relaxation), long before the overall job is actually finished.
        # See solver.py's mark_job_status docstring for the full picture.
        try:
            result = solve_timetable_job(
                job_id,
                tenant_id,
                class_stream_ids=[classroom_id],
                persist=True,
                max_seconds=PER_CLASSROOM_BUDGET,
                skip_diagnostics=True,
                mark_job_status=False,
            )
        except TimetableSolveError as exc:
            logger.error(
                '[Job %s] Classroom %s exception: %s',
                job_id, classroom_id, exc,
            )
            # Try with relaxation
            result = _try_relaxed_solve(job_id, tenant_id, classroom_id, exc)
            if result is None:
                failed.append((classroom_id, str(exc)))
                continue

        if result.get('status') == 'failed':
            logger.error(
                '[Job %s] Classroom %s solver failed: %s',
                job_id, classroom_id, result.get('reason', 'unknown'),
            )
            # Attempt relaxed solve
            relaxed = _try_relaxed_solve(job_id, tenant_id, classroom_id, result.get('reason'))
            if relaxed is None:
                failed.append((classroom_id, result.get('reason', 'Solver failed')))
                continue
            else:
                result = relaxed

        total_entries += result.get('entries', 0)
        logger.info(
            '[Job %s] Classroom %s done — %s entries (elapsed %.1fs)',
            job_id, classroom_id, result.get('entries', 0),
            time.monotonic() - started,
        )

        # Keep updated_at fresh throughout a long-running solve so the
        # concurrency guard's staleness check (views/timetable.py) can tell
        # a genuinely still-working job apart from an abandoned one without
        # waiting for the whole task to finish.
        TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(updated_at=timezone.now())

    elapsed = time.monotonic() - started

    # If too many failures, try whole-school fallback — but not if we
    # stopped early due to the overall time budget, since a whole-school
    # solve would only make total runtime worse, not better.
    if not ran_out_of_time and len(failed) >= FALLBACK_FAILURE_THRESHOLD:
        logger.warning(
            '[Job %s] %d classrooms failed, falling back to whole-school solve',
            job_id, len(failed)
        )
        try:
            result = solve_timetable_job(
                job_id,
                tenant_id,
                max_seconds=600,  # longer timeout for whole school
            )
            if result.get('status') == 'done':
                logger.info('[Job %s] Whole-school fallback succeeded', job_id)
                TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
                    status=TimetableJob.Status.DONE,
                    failure_reason='',
                    solve_time_seconds=time.monotonic() - started,
                    updated_at=timezone.now(),
                )
                return {'status': 'done', 'entries': result.get('entries', 0)}
        except Exception as e:
            logger.exception('Whole-school fallback failed: %s', e)

        # If fallback also fails, mark job as failed with details
        reasons = '; '.join(f'Classroom {cid}: {r}' for cid, r in failed)
        msg = f'Sequential solve failed for {len(failed)} classrooms. {reasons}'
        logger.error('[Job %s] %s', job_id, msg)
        TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
            status=TimetableJob.Status.FAILED,
            failure_reason=msg,
            solve_time_seconds=elapsed,
            updated_at=timezone.now(),
        )
        return {'status': 'failed', 'reason': msg}

    # If we have failures but below threshold (or we ran out of overall
    # time budget), still mark as failed but include details.
    if failed:
        prefix = 'Ran out of time before finishing. ' if ran_out_of_time else ''
        reasons = '; '.join(f'Classroom {cid}: {r}' for cid, r in failed)
        msg = f'{prefix}Sequential solve failed for {len(failed)} classrooms. {reasons}'
        logger.error('[Job %s] %s', job_id, msg)
        TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
            status=TimetableJob.Status.FAILED,
            failure_reason=msg,
            solve_time_seconds=elapsed,
            updated_at=timezone.now(),
        )
        return {'status': 'failed', 'reason': msg}

    logger.info(
        '[Job %s] All classrooms solved — %s entries in %.1fs',
        job_id, total_entries, elapsed,
    )
    TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
        status=TimetableJob.Status.DONE,
        failure_reason='',
        solve_time_seconds=elapsed,
        updated_at=timezone.now(),
    )
    return {'status': 'done', 'entries': total_entries}


def _try_relaxed_solve(job_id, tenant_id, classroom_id, original_error=None):
    """
    Attempt to solve a classroom with progressive relaxation of constraints.
    Returns the result dict if successful, else None.
    """
    # Order of relaxation: workload, room, teacher_availability, excluded_periods
    relaxations = ['workload', 'room', 'teacher_availability', 'excluded_periods']
    for relax in relaxations:
        logger.info(
            '[Job %s] Classroom %s trying relaxation: %s',
            job_id, classroom_id, relax
        )
        try:
            result = solve_timetable_job(
                job_id,
                tenant_id,
                class_stream_ids=[classroom_id],
                diagnostic_relaxation=relax,
                persist=True,
                max_seconds=PER_CLASSROOM_BUDGET,
                skip_diagnostics=True,  # avoid recursion in diagnosis
                mark_job_status=False,  # see solve_timetable_job's docstring
            )
            if result and result.get('status') == 'done':
                logger.warning(
                    '[Job %s] Classroom %s solved with relaxation: %s',
                    job_id, classroom_id, relax
                )
                # Optionally store a note about relaxation (you could add a field)
                return result
        except Exception as e:
            logger.warning(
                '[Job %s] Relaxation %s failed for classroom %s: %s',
                job_id, relax, classroom_id, e
            )
            continue
    logger.error('[Job %s] All relaxations failed for classroom %s', job_id, classroom_id)
    return None


@shared_task(name='timetabling.tasks.regenerate_partial')
def regenerate_partial_task(job_id, tenant_id, class_stream_ids):
    TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
        status=TimetableJob.Status.RUNNING,
        updated_at=timezone.now(),
    )
    try:
        result = solve_timetable_job(job_id, tenant_id, class_stream_ids=class_stream_ids)
        if result.get('status') == 'failed':
            TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
                status=TimetableJob.Status.FAILED,
                failure_reason=result.get('reason', 'Partial re-solve failed.'),
                updated_at=timezone.now(),
            )
        return result
    except Exception as exc:
        logger.exception('Partial timetable regeneration failed for job %s', job_id)
        TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
            status=TimetableJob.Status.FAILED,
            failure_reason=str(exc),
            updated_at=timezone.now(),
        )
        return {'status': 'failed', 'reason': str(exc)}