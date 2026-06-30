from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out


# ───────────────────────────────────────────────────────────
# STUDENTS
# ───────────────────────────────────────────────────────────

@receiver(post_save, sender='students.Student')
def log_student_admitted(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if created and hasattr(instance, 'admission') and instance.admission:
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.STUDENT_ADMITTED,
            title=f"New student admitted: {instance.get_full_name()}",
            description=f"{instance.get_full_name()} was admitted to {instance.admission.class_admitted}",
            actor=None,
            target_model='students.Student',
            target_id=instance.id,
            target_name=instance.get_full_name(),
        )


@receiver(post_save, sender='students.Student')
def log_student_status_change(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if created:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old.status == instance.status:
        return

    if instance.status == 'transferred':
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.STUDENT_TRANSFERRED,
            title=f"Student transferred: {instance.get_full_name()}",
            description=f"{instance.get_full_name()} was transferred",
            actor=None,
            target_model='students.Student',
            target_id=instance.id,
            target_name=instance.get_full_name(),
        )
    elif instance.status == 'graduated':
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.STUDENT_GRADUATED,
            title=f"Student graduated: {instance.get_full_name()}",
            description=f"{instance.get_full_name()} has graduated",
            actor=None,
            target_model='students.Student',
            target_id=instance.id,
            target_name=instance.get_full_name(),
        )
    elif instance.status == 'dropped':
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.STUDENT_DROPPED,
            title=f"Student dropped: {instance.get_full_name()}",
            description=f"{instance.get_full_name()} has been marked as dropped",
            actor=None,
            target_model='students.Student',
            target_id=instance.id,
            target_name=instance.get_full_name(),
        )


# ───────────────────────────────────────────────────────────
# STAFF / ACCOUNTS
# ───────────────────────────────────────────────────────────

@receiver(post_save, sender='accounts.StaffProfile')
def log_staff_changes(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if created:
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.STAFF_JOINED,
            title=f"New staff member: {instance.get_full_name()}",
            description=f"{instance.get_full_name()} ({instance.get_job_title_display()}) joined the school",
            actor=instance.created_by,
            target_model='accounts.StaffProfile',
            target_id=instance.id,
            target_name=instance.get_full_name(),
        )
    else:
        try:
            old = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            return

        if old.employment_status != instance.employment_status:
            if instance.employment_status == 'terminated':
                log_activity(
                    tenant=instance.tenant,
                    activity_type=ActivityLog.ActivityType.STAFF_DEACTIVATED,
                    title=f"Staff deactivated: {instance.get_full_name()}",
                    description=f"{instance.get_full_name()} has been deactivated",
                    actor=None,
                    target_model='accounts.StaffProfile',
                    target_id=instance.id,
                    target_name=instance.get_full_name(),
                )
            elif old.employment_status == 'terminated' and instance.employment_status == 'active':
                log_activity(
                    tenant=instance.tenant,
                    activity_type=ActivityLog.ActivityType.STAFF_REACTIVATED,
                    title=f"Staff reactivated: {instance.get_full_name()}",
                    description=f"{instance.get_full_name()} has been reactivated",
                    actor=None,
                    target_model='accounts.StaffProfile',
                    target_id=instance.id,
                    target_name=instance.get_full_name(),
                )


@receiver(post_save, sender='accounts.StaffInvite')
def log_staff_invite(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if created:
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.STAFF_INVITED,
            title=f"Staff invited: {instance.email}",
            description=f"An invitation was sent to {instance.email} for the role of {instance.role}",
            actor=instance.invited_by,
            target_model='accounts.StaffInvite',
            target_id=instance.id,
            target_name=instance.email,
        )


# ───────────────────────────────────────────────────────────
# FINANCE
# ───────────────────────────────────────────────────────────

@receiver(post_save, sender='finance.Payment')
def log_payment(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if created and instance.status == 'completed':
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.FEE_PAID,
            title=f"Fee payment received: KES {instance.amount:,.2f}",
            description=f"Payment of KES {instance.amount:,.2f} received from {instance.student.get_full_name()}",
            actor=instance.recorded_by,
            target_model='finance.Payment',
            target_id=instance.id,
            target_name=instance.student.get_full_name(),
            metadata={
                'amount': str(instance.amount),
                'method': instance.payment_method,
            },
        )


@receiver(post_save, sender='finance.Receipt')
def log_receipt(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if created:
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.RECEIPT_ISSUED,
            title=f"Receipt issued: {instance.receipt_number}",
            description=f"Receipt {instance.receipt_number} issued to {instance.student.get_full_name()} for KES {instance.amount:,.2f}",
            actor=instance.issued_by,
            target_model='finance.Receipt',
            target_id=instance.id,
            target_name=instance.student.get_full_name(),
            metadata={
                'receipt_number': instance.receipt_number,
                'amount': str(instance.amount),
            },
        )


@receiver(post_save, sender='finance.StudentWaiver')
def log_waiver(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if created:
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.WAIVER_APPLIED,
            title=f"Waiver applied: {instance.student.get_full_name()}",
            description=f"{instance.policy.get_category_display()} waiver applied to {instance.student.get_full_name()}",
            actor=instance.approved_by,
            target_model='finance.StudentWaiver',
            target_id=instance.id,
            target_name=instance.student.get_full_name(),
            metadata={
                'policy': instance.policy.get_category_display(),
                'discount_type': instance.policy.discount_type,
                'discount_value': str(instance.policy.discount_value),
            },
        )


# ───────────────────────────────────────────────────────────
# COMMUNICATION
# ───────────────────────────────────────────────────────────

@receiver(post_save, sender='communication.Announcement')
def log_announcement(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if not created and instance.status == 'sent' and instance.sent_at:
        already_logged = ActivityLog.objects.filter(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.ANNOUNCEMENT_SENT,
            target_model='communication.Announcement',
            target_id=instance.id,
        ).exists()
        if not already_logged:
            log_activity(
                tenant=instance.tenant,
                activity_type=ActivityLog.ActivityType.ANNOUNCEMENT_SENT,
                title=f"Announcement sent: {instance.title}",
                description=f"Announcement '{instance.title}' was sent to {instance.recipient_type}",
                actor=instance.sent_by,
                target_model='communication.Announcement',
                target_id=instance.id,
                target_name=instance.title,
                metadata={
                    'recipient_type': instance.recipient_type,
                    'total_recipients': instance.total_recipients,
                    'delivered_count': instance.delivered_count,
                },
            )


# ───────────────────────────────────────────────────────────
# ACADEMICS
# ───────────────────────────────────────────────────────────

@receiver(post_save, sender='academics.ExamSetup')
def log_exam_created(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if created:
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.EXAM_CREATED,
            title=f"Exam created: {instance.name}",
            description=f"{instance.name} ({instance.get_exam_type_display()}) was created for {instance.classroom}",
            actor=instance.created_by,
            target_model='academics.ExamSetup',
            target_id=instance.id,
            target_name=instance.name,
        )


@receiver(post_save, sender='academics.ExamResult')
def log_exam_result(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if created:
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.GRADE_ENTERED,
            title=f"Grade entered: {instance.student.get_full_name()}",
            description=f"{instance.marks}/{instance.exam_subject.total_marks} entered for {instance.exam_subject.subject.name}",
            actor=instance.entered_by,
            target_model='academics.ExamResult',
            target_id=instance.id,
            target_name=instance.student.get_full_name(),
            metadata={
                'marks': str(instance.marks),
                'total_marks': instance.exam_subject.total_marks,
                'cbc_level': instance.cbc_level,
            },
        )


@receiver(post_save, sender='academics.AttendanceSession')
def log_attendance(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if created:
        teacher_name = instance.teacher.get_full_name() if instance.teacher else 'System'
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.ATTENDANCE_MARKED,
            title=f"Attendance marked: {instance.classroom} on {instance.date}",
            description=f"Attendance was marked for {instance.classroom} by {teacher_name}",
            actor=instance.teacher,
            target_model='academics.AttendanceSession',
            target_id=instance.id,
            target_name=str(instance.classroom),
            metadata={
                'date': str(instance.date),
                'session_type': instance.session_type,
            },
        )


@receiver(post_save, sender='academics.ClassTimetable')
def log_timetable(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if created:
        log_activity(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.TIMETABLE_UPLOADED,
            title=f"Timetable uploaded: {instance.classroom}",
            description=f"A new timetable was uploaded for {instance.classroom}",
            actor=instance.uploaded_by,
            target_model='academics.ClassTimetable',
            target_id=instance.id,
            target_name=str(instance.classroom),
        )


@receiver(post_save, sender='academics.ReportCard')
def log_report_card(sender, instance, created, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    if not created and instance.status == 'published' and instance.published_at:
        already_logged = ActivityLog.objects.filter(
            tenant=instance.tenant,
            activity_type=ActivityLog.ActivityType.REPORT_CARD_PUBLISHED,
            target_model='academics.ReportCard',
            target_id=instance.id,
        ).exists()
        if not already_logged:
            log_activity(
                tenant=instance.tenant,
                activity_type=ActivityLog.ActivityType.REPORT_CARD_PUBLISHED,
                title=f"Report card published: {instance.student.get_full_name()}",
                description=f"Report card for {instance.student.get_full_name()} has been published",
                actor=instance.generated_by,
                target_model='academics.ReportCard',
                target_id=instance.id,
                target_name=instance.student.get_full_name(),
            )


# ───────────────────────────────────────────────────────────
# AUTH / SYSTEM
# ───────────────────────────────────────────────────────────

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    tenant = getattr(user, 'tenant', None)
    if tenant:
        log_activity(
            tenant=tenant,
            activity_type=ActivityLog.ActivityType.LOGIN,
            title=f"User login: {user.get_full_name() or user.email}",
            description=f"{user.get_full_name() or user.email} logged in",
            actor=user,
            target_model='accounts.CustomUser',
            target_id=user.id,
            target_name=user.get_full_name() or user.email,
            is_system=True,
        )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    from activity.utils import log_activity
    from activity.models import ActivityLog

    tenant = getattr(user, 'tenant', None)
    if tenant:
        log_activity(
            tenant=tenant,
            activity_type=ActivityLog.ActivityType.LOGOUT,
            title=f"User logout: {user.get_full_name() or user.email}",
            description=f"{user.get_full_name() or user.email} logged out",
            actor=user,
            target_model='accounts.CustomUser',
            target_id=user.id,
            target_name=user.get_full_name() or user.email,
            is_system=True,
        )