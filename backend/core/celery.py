import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# --- Reliability settings for long-running tasks (timetable solves) ---
#
# Default Celery behavior acknowledges (removes from the queue) a task the
# moment a worker RECEIVES it, not when it finishes. If the celery_timetable
# worker crashes or is OOM-killed mid-solve, the task is simply gone —
# nothing ever runs the code that flips the TimetableJob back out of
# RUNNING, and that job stays stuck that way forever. Combined with the
# concurrency guard in TimetableJobViewSet.create() (which deliberately
# refuses to start a new generation while one is already RUNNING for that
# tenant/term/year), an unacknowledged crash would permanently lock that
# tenant out of ever generating again without manual DB intervention.
# acks_late + reject_on_worker_lost together mean a task is only considered
# "done" once it actually completes, and gets redelivered to another worker
# if the one holding it dies.
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True

# Default prefetch (4) lets one worker process grab 4 heavy solve jobs ahead
# of time while only actively working one — starving any other idle worker
# of its fair share of the queue. 1 is the right value for long, CPU-bound
# tasks like these; short/light tasks on celery_default don't have this
# problem and are left at the default.
app.conf.worker_prefetch_multiplier = 1

# Hard backstop independent of the solver's own internal budgeting
# (PER_CLASSROOM_BUDGET / the sequential loop's own overall time check in
# tasks.py) — this only exists to catch a genuinely wedged OR-Tools process
# that isn't respecting its own timeout, not to bound normal-case runtime.
# Set generously above what a large school's worst-case sequential solve
# should ever need; tasks.py's own internal ceiling is what actually keeps
# normal runs well-behaved.
app.conf.task_time_limit = 1800       # hard kill after 30 minutes
app.conf.task_soft_time_limit = 1740  # SoftTimeLimitExceeded raised first, catchable for cleanup