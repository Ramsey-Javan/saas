import logging
import time
import os

from celery import shared_task
from django.db.models import Count

from .models import TimetableJob
from .services.solver import solve_timetable_job, TimetableSolveError

logger = logging.getLogger(__name__)

# Hard ceiling per classroom (seconds). Single-classroom CP-SAT models are tiny;
# 30 s is usually enough, but can be increased via environment variable.
PER_CLASSROOM_BUDGET = int(os.environ.get('PER_CLASSROOM_BUDGET', 30))

# If more than this many classrooms fail in sequential mode, fall back to whole-school solve
FALLBACK_FAILURE_THRESHOLD = 3


@shared_task(name='timetabling.tasks.generate_timetable')
def generate_timetable_task(job_id, tenant_id):
    TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
        status=TimetableJob.Status.RUNNING
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
        )
        return {'status': 'failed', 'reason': msg}

    started = time.monotonic()
    total_entries = 0
    failed = []

    for idx, classroom_id in enumerate(classroom_ids, start=1):
        logger.info(
            '[Job %s] Solving classroom %s (%d/%d) — budget %ss',
            job_id, classroom_id, idx, len(classroom_ids), PER_CLASSROOM_BUDGET,
        )

        # Try normal solve
        try:
            result = solve_timetable_job(
                job_id,
                tenant_id,
                class_stream_ids=[classroom_id],
                persist=True,
                max_seconds=PER_CLASSROOM_BUDGET,
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

    elapsed = time.monotonic() - started

    # If too many failures, try whole-school fallback
    if len(failed) >= FALLBACK_FAILURE_THRESHOLD:
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
        )
        return {'status': 'failed', 'reason': msg}

    # If we have failures but below threshold, still mark as failed but include details
    if failed:
        reasons = '; '.join(f'Classroom {cid}: {r}' for cid, r in failed)
        msg = f'Sequential solve failed for some classrooms. {reasons}'
        logger.error('[Job %s] %s', job_id, msg)
        TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
            status=TimetableJob.Status.FAILED,
            failure_reason=msg,
            solve_time_seconds=elapsed,
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
        status=TimetableJob.Status.RUNNING
    )
    try:
        result = solve_timetable_job(job_id, tenant_id, class_stream_ids=class_stream_ids)
        if result.get('status') == 'failed':
            TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
                status=TimetableJob.Status.FAILED,
                failure_reason=result.get('reason', 'Partial re-solve failed.'),
            )
        return result
    except Exception as exc:
        logger.exception('Partial timetable regeneration failed for job %s', job_id)
        TimetableJob.objects.filter(id=job_id, tenant_id=tenant_id).update(
            status=TimetableJob.Status.FAILED,
            failure_reason=str(exc),
        )
        return {'status': 'failed', 'reason': str(exc)}