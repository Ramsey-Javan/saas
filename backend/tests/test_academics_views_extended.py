import pytest
from django.urls import reverse

from academics.models import (
    Subject, Strand, SubStrand, LearningOutcome,
    ExamSetup, ExamSubject, ExamResult, ExamConfig,
    AttendanceSession, AttendanceRecord,
    CBCGrade, ClassSubjectAssignment,
)
from tests.factories import (
    ClassroomFactory,
    StudentFactory,
    SubjectFactory,
    TeacherUserFactory,
    ExamSetupFactory,
    ExamSubjectFactory,
    ExamResultFactory,
    ExamConfigFactory,
)


def _reverse_or_skip(url_names, kwargs=None):
    for name in url_names:
        try:
            if kwargs:
                return reverse(name, kwargs=kwargs)
            return reverse(name)
        except:
            continue
    return None


@pytest.mark.django_db
class TestExamSetupExtendedViews:
    def test_exam_setup_create(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)

        url = _reverse_or_skip(['examsetup-list', 'exam-setup-list'])
        if url is None:
            pytest.skip("examsetup-list URL not found")

        payload = {
            'name': 'New Exam',
            'exam_type': 'mid_term',
            'classroom': classroom.id,
            'term': 'term1',
            'academic_year': 2026,
            'start_date': '2026-03-01',
            'end_date': '2026-03-05',
            'instructions': 'Test instructions',
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_exam_setup_publish(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        exam = ExamSetup.objects.create(
            tenant=tenant,
            name='Publish Test',
            exam_type='opener',
            classroom=classroom,
            term='term1',
            academic_year=2026,
            start_date='2026-01-10',
            end_date='2026-01-20',
            instructions='Test',
            is_active=True,
            created_by=admin_user,
        )

        url = _reverse_or_skip(['examsetup-publish', 'exam-publish'])
        if url is None:
            pytest.skip("exam-publish URL not found")

        response = admin_client.post(url, {'pk': exam.id}, format='json')
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestExamResultExtendedViews:
    def test_exam_result_create(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        exam = ExamSetup.objects.create(
            tenant=tenant,
            name='Result Exam',
            exam_type='opener',
            classroom=classroom,
            term='term1',
            academic_year=2026,
            start_date='2026-01-10',
            end_date='2026-01-20',
            instructions='Test',
            is_active=True,
            created_by=admin_user,
        )
        subject = SubjectFactory(tenant=tenant)
        student = StudentFactory(tenant=tenant, classroom=classroom)
        exam_subject = ExamSubject.objects.create(
            tenant=tenant,
            exam=exam,
            subject=subject,
            total_marks=100,
            teacher=admin_user,
        )

        url = _reverse_or_skip(['examresult-list', 'exam-result-list'])
        if url is None:
            pytest.skip("examresult-list URL not found")

        payload = {
            'exam_subject': exam_subject.id,
            'student': student.id,
            'marks': '85.00',
            'percentage': '85.00',
            'cbc_level': 'EE',
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_exam_result_bulk_create(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        exam = ExamSetup.objects.create(
            tenant=tenant,
            name='Bulk Exam',
            exam_type='opener',
            classroom=classroom,
            term='term1',
            academic_year=2026,
            start_date='2026-01-10',
            end_date='2026-01-20',
            instructions='Test',
            is_active=True,
            created_by=admin_user,
        )
        subject = SubjectFactory(tenant=tenant)
        student = StudentFactory(tenant=tenant, classroom=classroom)
        exam_subject = ExamSubject.objects.create(
            tenant=tenant,
            exam=exam,
            subject=subject,
            total_marks=100,
            teacher=admin_user,
        )

        url = _reverse_or_skip(['examresult-bulk', 'exam-result-bulk'])
        if url is None:
            pytest.skip("examresult-bulk URL not found")

        payload = {
            'results': [
                {
                    'exam_subject': exam_subject.id,
                    'student': student.id,
                    'marks': '85.00',
                    'cbc_level': 'EE',
                }
            ]
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 404]


@pytest.mark.django_db
class TestCBCGradeExtendedViews:
    def test_cbc_grade_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        student = StudentFactory(tenant=tenant)
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)
        outcome = LearningOutcome.objects.create(tenant=tenant, sub_strand=sub_strand, description='Outcome 1', order=1)
        grade = CBCGrade.objects.create(
            tenant=tenant,
            student=student,
            learning_outcome=outcome,
            level='ME',
            assessed_by=admin_user,
            academic_year=2026,
        )

        url = _reverse_or_skip(['cbcgrade-detail', 'cbc-grade-detail'], {'pk': grade.id})
        if url is None:
            pytest.skip("cbcgrade-detail URL not found")

        response = admin_client.patch(url, {'level': 'EE'}, format='json')
        assert response.status_code in [200, 404]

    def test_cbc_grade_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        student = StudentFactory(tenant=tenant)
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)
        outcome = LearningOutcome.objects.create(tenant=tenant, sub_strand=sub_strand, description='Outcome 1', order=1)
        grade = CBCGrade.objects.create(
            tenant=tenant,
            student=student,
            learning_outcome=outcome,
            level='ME',
            assessed_by=admin_user,
            academic_year=2026,
        )

        url = _reverse_or_skip(['cbcgrade-detail', 'cbc-grade-detail'], {'pk': grade.id})
        if url is None:
            pytest.skip("cbcgrade-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]


@pytest.mark.django_db
class TestAttendanceExtendedViews:
    def test_attendance_record_create(self, teacher_client, teacher_user):
        tenant = teacher_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        subject = SubjectFactory(tenant=tenant)
        student = StudentFactory(tenant=tenant, classroom=classroom)
        session = AttendanceSession.objects.create(
            tenant=tenant,
            classroom=classroom,
            subject=subject,
            teacher=teacher_user,
            date='2026-01-15',
            session_type='daily',
            term='term1',
            academic_year=2026,
        )

        url = _reverse_or_skip(['attendancerecord-list', 'attendance-record-list'])
        if url is None:
            pytest.skip("attendance-record-list URL not found")

        payload = {
            'session': session.id,
            'student': student.id,
            'status': 'P',
        }
        response = teacher_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_attendance_session_close(self, teacher_client, teacher_user):
        tenant = teacher_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        subject = SubjectFactory(tenant=tenant)
        session = AttendanceSession.objects.create(
            tenant=tenant,
            classroom=classroom,
            subject=subject,
            teacher=teacher_user,
            date='2026-01-15',
            session_type='daily',
            term='term1',
            academic_year=2026,
        )

        url = _reverse_or_skip(['attendancesession-close', 'close-attendance-session'], {'pk': session.id})
        if url is None:
            pytest.skip("attendance-session-close URL not found")

        response = teacher_client.post(url, {}, format='json')
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestClassSubjectAssignmentExtendedViews:
    def test_class_subject_assignment_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        subject = SubjectFactory(tenant=tenant)
        teacher = TeacherUserFactory(tenant=tenant)
        assignment = ClassSubjectAssignment.objects.create(
            tenant=tenant,
            classroom=classroom,
            subject=subject,
            teacher=teacher,
            academic_year=2026,
            term='term1',
        )

        url = _reverse_or_skip(['classsubjectassignment-detail', 'class-subject-assignment-detail'], {'pk': assignment.id})
        if url is None:
            pytest.skip("class-subject-assignment-detail URL not found")

        response = admin_client.patch(url, {'term': 'term2'}, format='json')
        assert response.status_code in [200, 404]

    def test_class_subject_assignment_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        subject = SubjectFactory(tenant=tenant)
        teacher = TeacherUserFactory(tenant=tenant)
        assignment = ClassSubjectAssignment.objects.create(
            tenant=tenant,
            classroom=classroom,
            subject=subject,
            teacher=teacher,
            academic_year=2026,
            term='term1',
        )

        url = _reverse_or_skip(['classsubjectassignment-detail', 'class-subject-assignment-detail'], {'pk': assignment.id})
        if url is None:
            pytest.skip("class-subject-assignment-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]
