import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from .models import Payment
from .mpesa import MpesaService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def query_mpesa_status_task(self, payment_id):
    """
    Query M-Pesa transaction status as a fallback when callback is missed.
    Called:
    - 30s after STK push timeout (early check)
    - 120s after successful STK push (fallback if callback missed)
    - By the periodic reconcile task for stale payments
    """
    try:
        payment = Payment.objects.select_related('tenant').get(id=payment_id)
    except Payment.DoesNotExist:
        logger.warning(f"Payment {payment_id} not found for status query")
        return {"status": "not_found"}

    if payment.status != 'pending':
        logger.info(f"Payment {payment_id} is already {payment.status}, skipping query")
        return {"status": "already_resolved", "payment_status": payment.status}

    if not payment.mpesa_checkout_request_id:
        logger.warning(f"Payment {payment_id} has no checkout_request_id")
        return {"status": "no_checkout_id"}

    try:
        service = MpesaService()
        query_result = service.query_transaction_status(payment.mpesa_checkout_request_id)

        # Check if we got a meaningful result
        result_code = query_result.get('ResultCode')
        response_code = query_result.get('ResponseCode')

        if result_code is not None:
            # We got a definitive answer
            result = service.process_status_query_result(payment, query_result)
            logger.info(f"Status query resolved payment {payment_id}: {result}")
            return result

        # ResponseCode '0' with no ResultCode might mean "in progress"
        if response_code == '0':
            logger.info(f"Payment {payment_id} still in progress according to status query")
            # Requeue for another check in 60s if payment is still fresh
            age = (timezone.now() - payment.created_at).total_seconds()
            if age < 300:  # 5 minutes
                raise self.retry(countdown=60)
            return {"status": "still_pending"}

        # Unknown response — maybe the checkout ID doesn't exist yet
        logger.warning(f"Unexpected status query response for {payment_id}: {query_result}")
        return {"status": "unknown_response", "response": query_result}

    except Exception as exc:
        logger.exception(f"Status query failed for payment {payment_id}")
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc)
        return {"status": "error", "reason": str(exc)}


@shared_task
def reconcile_pending_mpesa_task():
    """
    Periodic task (every 2 minutes) to find stale pending M-Pesa payments
    and query their status. This is the ULTIMATE fallback.
    """
    cutoff = timezone.now() - timedelta(seconds=45)
    # Payments that have been pending for 45+ seconds and haven't been queried recently
    stale_payments = Payment.objects.filter(
        status='pending',
        payment_method='mpesa',
        created_at__lte=cutoff,
    ).select_related('tenant')[:50]  # Batch limit

    processed = 0
    for payment in stale_payments:
        # Skip if it was created very recently (might still be in progress)
        age = (timezone.now() - payment.created_at).total_seconds()
        if age < 30:
            continue

        # Schedule individual status query
        query_mpesa_status_task.delay(payment.id)
        processed += 1

    if processed > 0:
        logger.info(f"Reconcile task scheduled status queries for {processed} pending payments")

    # Also auto-expire payments that are way too old (10+ minutes)
    ancient_cutoff = timezone.now() - timedelta(minutes=10)
    ancient = Payment.objects.filter(
        status='pending',
        payment_method='mpesa',
        created_at__lte=ancient_cutoff,
    )
    expired_count = 0
    for payment in ancient:
        payment.status = 'expired'
        payment.notes = 'Payment expired after 10 minutes with no confirmation.'
        payment.save(update_fields=['status', 'notes'])
        expired_count += 1

    if expired_count > 0:
        logger.info(f"Auto-expired {expired_count} ancient pending payments")

    return {
        "queried": processed,
        "expired": expired_count,
    }