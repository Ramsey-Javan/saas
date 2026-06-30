from django.utils import timezone


def get_active_assignments(teacher_user, tenant):
    from academics.models import ClassSubjectAssignment, ExamSubject
    from students.models import Classroom

    class_subjects = ClassSubjectAssignment.objects.filter(
        tenant=tenant,
        teacher=teacher_user,
    ).select_related('classroom', 'subject')
    class_teacher_of = Classroom.objects.filter(
        tenant=tenant,
        class_teacher=teacher_user,
    )
    exam_subjects = ExamSubject.objects.filter(
        tenant=tenant,
        teacher=teacher_user,
    ).select_related('subject', 'exam')

    return {
        'class_subject_assignments': class_subjects,
        'class_teacher_roles': class_teacher_of,
        'exam_subjects': exam_subjects,
        'total_count': class_subjects.count() + class_teacher_of.count() + exam_subjects.count(),
    }


def deactivate_and_reassign(teacher_user, tenant, reassign_to_user=None):
    from academics.models import ClassSubjectAssignment, ExamSubject
    from students.models import Classroom

    teacher_user.is_active = False
    teacher_user.save(update_fields=['is_active'])

    profile = getattr(teacher_user, 'staff_profile', None)
    if profile:
        profile.employment_status = 'terminated'
        profile.end_date = timezone.localdate()
        profile.is_active = False
        profile.save(update_fields=['employment_status', 'end_date', 'is_active'])

    reassigned = {
        'class_subject_assignments': 0,
        'class_teacher_roles': 0,
        'exam_subjects': 0,
    }

    if reassign_to_user:
        reassigned['class_subject_assignments'] = ClassSubjectAssignment.objects.filter(
            tenant=tenant,
            teacher=teacher_user,
        ).update(teacher=reassign_to_user)
        reassigned['class_teacher_roles'] = Classroom.objects.filter(
            tenant=tenant,
            class_teacher=teacher_user,
        ).update(class_teacher=reassign_to_user)
        reassigned['exam_subjects'] = ExamSubject.objects.filter(
            tenant=tenant,
            teacher=teacher_user,
        ).update(teacher=reassign_to_user)

    return reassigned
