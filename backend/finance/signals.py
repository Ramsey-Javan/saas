from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import StudentWaiver
from .utils import apply_waiver_to_invoices, remove_waiver_from_invoices


@receiver(post_save, sender=StudentWaiver)
def on_waiver_saved(sender, instance, **kwargs):
    if instance.is_active:
        apply_waiver_to_invoices(instance)
    else:
        remove_waiver_from_invoices(instance)


@receiver(post_delete, sender=StudentWaiver)
def on_waiver_deleted(sender, instance, **kwargs):
    remove_waiver_from_invoices(instance)
