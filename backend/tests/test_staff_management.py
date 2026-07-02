from accounts.models import StaffProfile
from accounts.utils import deactivate_and_reassign, get_active_assignments
from academics.models import ClassSubjectAssignment, ExamSetup, ExamSubject, Subject
from students.models import Classroom
from tests.factories import (
    ClassroomFactory,
    ExamSetupFactory,
    ExamSubjectFactory,
    StaffProfileFactory,
    SubjectFactory,
    TeacherUserFactory,
    TenantFactory,
)


def test_get_active_assignments_counts_teacher_roles(db):
    tenant = TenantFactory()
    teacher = TeacherUserFactory(tenant=tenant)
    classroom = ClassroomFactory(tenant=tenant, class_teacher=teacher)
    subject = SubjectFactory(tenant=tenant)
    exam = ExamSetupFactory(tenant=tenant, classroom=classroom, created_by=teacher)

    ClassSubjectAssignment.objects.create(
        tenant=tenant,
        classroom=classroom,
        subject=subject,
        teacher=teacher,
        academic_year=2026,
        term='term1',
    )
    ExamSubject.objects.create(
        tenant=tenant,
        exam=exam,
        subject=subject,
        total_marks=100,
        teacher=teacher,
    )

    assignments = get_active_assignments(teacher, tenant)

    assert assignments['class_subject_assignments'].count() == 1
    assert assignments['class_teacher_roles'].count() == 1
    assert assignments['exam_subjects'].count() == 1
    assert assignments['total_count'] == 3


def test_deactivate_and_reassign_moves_all_assignments(db):
    tenant = TenantFactory()
    teacher = TeacherUserFactory(tenant=tenant)
    reassign_to = TeacherUserFactory(tenant=tenant)
    classroom = ClassroomFactory(tenant=tenant, class_teacher=teacher)
    subject = SubjectFactory(tenant=tenant)
    exam = ExamSetupFactory(tenant=tenant, classroom=classroom, created_by=teacher)
    StaffProfileFactory(tenant=tenant, user=teacher, created_by=reassign_to)

    ClassSubjectAssignment.objects.create(
        tenant=tenant,
        classroom=classroom,
        subject=subject,
        teacher=teacher,
        academic_year=2026,
        term='term1',
    )
    ExamSubject.objects.create(
        tenant=tenant,
        exam=exam,
        subject=subject,
        total_marks=100,
        teacher=teacher,
    )

    reassigned = deactivate_and_reassign(teacher, tenant, reassign_to_user=reassign_to)

    teacher.refresh_from_db()
    profile = teacher.staff_profile
    classroom.refresh_from_db()
    exam_subject = ExamSubject.objects.get(tenant=tenant, exam=exam)

    assert not teacher.is_active
    assert profile.employment_status == StaffProfile.EmploymentStatus.TERMINATED
    assert profile.is_active is False
    assert classroom.class_teacher == reassign_to
    assert exam_subject.teacher == reassign_to
    assert reassigned == {
        'class_subject_assignments': 1,
        'class_teacher_roles': 1,
        'exam_subjects': 1,
    }
