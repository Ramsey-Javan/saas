import logging
import random
from datetime import timedelta

from celery import shared_task
from django.db.models import Count
from django.utils import timezone

from tenants.models import Tenant
from .models import Payment
from .mpesa import MpesaService, MpesaConfigurationError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def query_mpesa_status_task(self, payment_id):
    """
    Query M-Pesa transaction status as a fallback when callback is missed.
    Called:
    - 45s after STK push (early check)
    - 120s after STK push (fallback if callback missed)
    - By the periodic reconcile task for stale payments

    SECURITY FIX #7: Checks resolved_at before processing to avoid
    redundant work on already-completed payments.
    """
    try:
        payment = Payment.objects.select_related('tenant', 'student_fee').get(id=payment_id)
    except Payment.DoesNotExist:
        logger.warning(f"Payment {payment_id} not found for status query")
        return {"status": "not_found"}

    # Skip if already resolved (callback or previous query handled it)
    if payment.resolved_at or payment.status not in ['pending', 'PENDING']:
        logger.info(f"Payment {payment_id} is already {payment.status} (resolved_at={payment.resolved_at}), skipping query")
        return {"status": "already_resolved", "payment_status": payment.status}

    if not payment.mpesa_checkout_request_id:
        logger.warning(f"Payment {payment_id} has no checkout_request_id")
        return {"status": "no_checkout_id"}

    try:
        service = MpesaService(school_slug=payment.tenant.slug)
        query_result = service.query_transaction_status(payment.mpesa_checkout_request_id)

        result_code = query_result.get('ResultCode')
        response_code = query_result.get('ResponseCode')

        if result_code is not None:
            # Definitive answer
            result = service.process_status_query_result(payment, query_result)
            logger.info(f"Status query resolved payment {payment_id}: {result.status}")
            return {"status": "resolved", "payment_id": payment_id, "new_status": result.status}

        # ResponseCode '0' with no ResultCode might mean "in progress"
        if str(response_code) == '0':
            logger.info(f"Payment {payment_id} still in progress")
            age = (timezone.now() - payment.created_at).total_seconds()
            if age < 300:  # 5 minutes
                # Add jitter (0-15s) to prevent thundering herd
                jitter = random.randint(30, 90)
                raise self.retry(countdown=120 + jitter)
            return {"status": "still_pending", "age_seconds": age}

        # Unknown response
        logger.warning(f"Unexpected status query response for {payment_id}: {query_result}")
        return {"status": "unknown_response", "response": query_result}

    except MpesaConfigurationError as exc:
        logger.error(f"M-Pesa not configured for tenant {payment.tenant.slug}: {exc}")
        return {"status": "error", "reason": "mpesa_not_configured"}
    except Exception as exc:
        logger.exception(f"Status query failed for payment {payment_id}")
        if self.request.retries < self.max_retries:
            # Exponential backoff with jitter: 60s, 120s, 240s
            countdown = 60 * (self.request.retries + 1) + random.randint(0, 30)
            raise self.retry(countdown=countdown, exc=exc)
        return {"status": "error", "reason": str(exc)}


@shared_task(name="finance.tasks.reconcile_pending_mpesa_transactions")
def reconcile_pending_mpesa_task():
    """
    Periodic fallback task to find stale pending M-Pesa payments and query their status.
    Runs every 2-3 minutes via Celery beat.

    SECURITY FIX #17: Tenant-isolated batching to prevent one tenant
    from starving others.
    """
    # Find payments that are pending and older than 45 seconds
    cutoff = timezone.now() - timedelta(seconds=45)

    # Get tenant IDs with stale payments, limited to max 10 per tenant
    tenant_ids = (
        Payment.objects.filter(
            status__in=['pending', 'PENDING'],
            mpesa_checkout_request_id__isnull=False,
            created_at__lte=cutoff,
            resolved_at__isnull=True,
        )
        .values('tenant')
        .annotate(count=Count('id'))
        .filter(count__gt=0)
        .values_list('tenant', flat=True)
    )

    processed = 0
    for tenant_id in tenant_ids:
        # Process max 10 payments per tenant per run
        tenant_payments = Payment.objects.filter(
            tenant_id=tenant_id,
            status__in=['pending', 'PENDING'],
            mpesa_checkout_request_id__isnull=False,
            created_at__lte=cutoff,
            resolved_at__isnull=True,
        )[:10]

        for payment in tenant_payments:
            age = (timezone.now() - payment.created_at).total_seconds()
            if age < 30:
                continue

            # Schedule individual status query asynchronously
            query_mpesa_status_task.delay(payment.id)
            processed += 1

    if processed > 0:
        logger.info(f"Reconcile task scheduled status queries for {processed} pending payments across {len(tenant_ids)} tenants")

    # Auto-expire payments that are way too old (10+ minutes) with no response
    ancient_cutoff = timezone.now() - timedelta(minutes=10)
    ancient_payments = Payment.objects.filter(
        status__in=['pending', 'PENDING'],
        mpesa_checkout_request_id__isnull=False,
        created_at__lte=ancient_cutoff,
        resolved_at__isnull=True,
    ).select_related('tenant')

    expired_count = 0
    for payment in ancient_payments:
        try:
            service = MpesaService(school_slug=payment.tenant.slug)
            service.expire_stale_payment(payment)
            expired_count += 1
        except MpesaConfigurationError:
            logger.error(f"Cannot expire payment {payment.id}: M-Pesa not configured for tenant {payment.tenant.slug}")
        except Exception as e:
            logger.error(f"Failed to auto-expire payment {payment.id}: {str(e)}")

    if expired_count > 0:
        logger.info(f"Auto-expired {expired_count} ancient pending payments")

    return {
        "queried": processed,
        "expired": expired_count,
        "tenants_affected": len(tenant_ids),
    }
