from celery import shared_task
from django.db import transaction
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

@shared_task
def auto_mark_daily_attendance():
    """
    End-of-day task: for every classroom, if no daily attendance session
    exists for today, create one and mark all active students as Present.
    Skips if teacher already marked attendance.
    Runs at 4:00 PM daily via celerybeat.
    """
    from tenants.models import Tenant
    from students.models import Classroom, Student
    from academics.models import AttendanceSession, AttendanceRecord

    today = timezone.localdate()
    total_sessions_created = 0
    total_records_created = 0

    for tenant in Tenant.objects.filter(is_active=True):
        # Determine current term and academic year from tenant or defaults
        # Fall back to calendar year if tenant has no explicit academic_year field
        academic_year = getattr(tenant, 'academic_year', today.year)
        term = getattr(tenant, 'current_term', 'term1')

        classrooms = Classroom.objects.filter(tenant=tenant, is_active=True)

        for classroom in classrooms:
            # Check if a daily session already exists for this class today
            already_exists = AttendanceSession.objects.filter(
                tenant=tenant,
                classroom=classroom,
                date=today,
                session_type=AttendanceSession.SessionType.DAILY,
            ).exists()

            if already_exists:
                continue  # Teacher already marked — do nothing

            with transaction.atomic():
                session = AttendanceSession.objects.create(
                    tenant=tenant,
                    classroom=classroom,
                    date=today,
                    session_type=AttendanceSession.SessionType.DAILY,
                    term=term,
                    academic_year=academic_year,
                    teacher=None,  # No teacher — system-generated
                    notes='Auto-marked: teacher did not mark attendance.',
                    auto_marked=True,
                )

                students = Student.objects.filter(
                    tenant=tenant,
                    classroom=classroom,
                    is_active=True,
                )

                if students.exists():
                    AttendanceRecord.objects.bulk_create([
                        AttendanceRecord(
                            tenant=tenant,
                            session=session,
                            student=student,
                            status=AttendanceRecord.Status.PRESENT,
                        )
                        for student in students
                    ])
                    total_records_created += students.count()

                total_sessions_created += 1

    return {
        'sessions_created': total_sessions_created,
        'records_created': total_records_created,
    }