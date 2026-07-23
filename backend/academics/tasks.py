from celery import shared_task
from django.utils import timezone
from datetime import timedelta


@shared_task
def auto_lock_old_sessions():
    """
    Daily task: lock all attendance sessions past the tenant's grace period.
    Runs at 2 AM via celerybeat.
    """
    from tenants.models import Tenant
    from academics.models import AttendanceSession

    today = timezone.localdate()
    total_locked = 0

    for tenant in Tenant.objects.filter(is_active=True):
        days = getattr(tenant, 'attendance_auto_lock_days', 2)
        if days == 0:
            continue

        cutoff = today - timedelta(days=days)
        locked = AttendanceSession.objects.filter(
            tenant=tenant,
            is_locked=False,
            date__lte=cutoff,
        ).update(is_locked=True)

        total_locked += locked

    return {'sessions_locked': total_locked}