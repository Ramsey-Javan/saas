from celery import shared_task


@shared_task
def check_trial_expiry_task():
    from .models import Tenant

    locked = 0
    for school in Tenant.objects.filter(plan=Tenant.Plan.TRIAL, is_active=True):
        if school.is_trial_hard_expired():
            school.is_active = False
            school.save(update_fields=['is_active'])
            locked += 1
    return {'schools_locked': locked}
