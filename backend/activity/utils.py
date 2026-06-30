from .models import ActivityLog


def log_activity(
    tenant,
    activity_type,
    title,
    description,
    actor=None,
    target_model='',
    target_id='',
    target_name='',
    metadata=None,
    is_system=False,
):
    """Helper to create an activity log entry."""
    return ActivityLog.objects.create(
        tenant=tenant,
        actor=actor,
        activity_type=activity_type,
        title=title,
        description=description,
        target_model=target_model,
        target_id=str(target_id) if target_id else '',
        target_name=target_name,
        metadata=metadata or {},
        is_system=is_system,
    )