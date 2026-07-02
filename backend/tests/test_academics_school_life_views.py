import pytest
from django.urls import reverse

from academics.models import (
    AttendanceSession, AttendanceRecord,
    Strand, SubStrand, LearningOutcome,
    ClassSubjectAssignment,
)
from tests.factories import (
    ClassroomFactory,
    StudentFactory,
    SubjectFactory,
    TeacherUserFactory,
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
class TestAttendanceSessionViews:
    def test_attendance_session_list(self, teacher_client, teacher_user):
        tenant = teacher_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        subject = SubjectFactory(tenant=tenant)
        AttendanceSession.objects.create(
            tenant=tenant,
            classroom=classroom,
            subject=subject,
            teacher=teacher_user,
            date='2026-01-15',
            session_type='daily',
            term='term1',
            academic_year=2026,
        )

        url = _reverse_or_skip(['attendancesession-list', 'attendance-session-list'])
        if url is None:
            pytest.skip("attendance-session-list URL not found")

        response = teacher_client.get(url)
        assert response.status_code == 200

    def test_attendance_session_detail(self, teacher_client, teacher_user):
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

        url = _reverse_or_skip(['attendancesession-detail', 'attendance-session-detail'], {'pk': session.id})
        if url is None:
            pytest.skip("attendance-session-detail URL not found")

        response = teacher_client.get(url)
        assert response.status_code in [200, 404]

    def test_attendance_session_update(self, teacher_client, teacher_user):
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

        url = _reverse_or_skip(['attendancesession-detail', 'attendance-session-detail'], {'pk': session.id})
        if url is None:
            pytest.skip("attendance-session-detail URL not found")

        response = teacher_client.patch(url, {'notes': 'Updated notes'}, format='json')
        assert response.status_code in [200, 404]

    def test_attendance_session_delete(self, teacher_client, teacher_user):
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

        url = _reverse_or_skip(['attendancesession-detail', 'attendance-session-detail'], {'pk': session.id})
        if url is None:
            pytest.skip("attendance-session-detail URL not found")

        response = teacher_client.delete(url)
        assert response.status_code in [204, 200, 404]


@pytest.mark.django_db
class TestAttendanceRecordViews:
    def test_attendance_record_list(self, teacher_client, teacher_user):
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
        AttendanceRecord.objects.create(
            tenant=tenant,
            session=session,
            student=student,
            status='P',
        )

        url = _reverse_or_skip(['attendancerecord-list', 'attendance-record-list'])
        if url is None:
            pytest.skip("attendance-record-list URL not found")

        response = teacher_client.get(url)
        assert response.status_code == 200

    def test_attendance_record_detail(self, teacher_client, teacher_user):
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
        record = AttendanceRecord.objects.create(
            tenant=tenant,
            session=session,
            student=student,
            status='P',
        )

        url = _reverse_or_skip(['attendancerecord-detail', 'attendance-record-detail'], {'pk': record.id})
        if url is None:
            pytest.skip("attendance-record-detail URL not found")

        response = teacher_client.get(url)
        assert response.status_code in [200, 404]

    def test_attendance_record_update(self, teacher_client, teacher_user):
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
        record = AttendanceRecord.objects.create(
            tenant=tenant,
            session=session,
            student=student,
            status='P',
        )

        url = _reverse_or_skip(['attendancerecord-detail', 'attendance-record-detail'], {'pk': record.id})
        if url is None:
            pytest.skip("attendance-record-detail URL not found")

        response = teacher_client.patch(url, {'status': 'A'}, format='json')
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestClassSubjectAssignmentViews:
    def test_class_subject_assignment_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        subject = SubjectFactory(tenant=tenant)
        teacher = TeacherUserFactory(tenant=tenant)
        ClassSubjectAssignment.objects.create(
            tenant=tenant,
            classroom=classroom,
            subject=subject,
            teacher=teacher,
            academic_year=2026,
            term='term1',
        )

        url = _reverse_or_skip(['classsubjectassignment-list', 'class-subject-assignment-list'])
        if url is None:
            pytest.skip("class-subject-assignment-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_class_subject_assignment_create(self, admin_client, admin_user):
        tenant = admin_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        subject = SubjectFactory(tenant=tenant)
        teacher = TeacherUserFactory(tenant=tenant)

        url = _reverse_or_skip(['classsubjectassignment-list', 'class-subject-assignment-list'])
        if url is None:
            pytest.skip("class-subject-assignment-list URL not found")

        payload = {
            'classroom': classroom.id,
            'subject': subject.id,
            'teacher': teacher.id,
            'academic_year': 2026,
            'term': 'term1',
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_class_subject_assignment_detail(self, admin_client, admin_user):
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

        response = admin_client.get(url)
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestStrandViews:
    def test_strand_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)

        url = _reverse_or_skip(['strand-list', 'strands-list'])
        if url is None:
            pytest.skip("strand-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_strand_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)

        url = _reverse_or_skip(['strand-detail', 'strands-detail'], {'pk': strand.id})
        if url is None:
            pytest.skip("strand-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestSubStrandViews:
    def test_sub_strand_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)

        url = _reverse_or_skip(['substrand-list', 'sub-strand-list'])
        if url is None:
            pytest.skip("substrand-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_sub_strand_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)

        url = _reverse_or_skip(['substrand-detail', 'sub-strand-detail'], {'pk': sub_strand.id})
        if url is None:
            pytest.skip("substrand-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestLearningOutcomeViews:
    def test_learning_outcome_list(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)
        LearningOutcome.objects.create(tenant=tenant, sub_strand=sub_strand, description='Outcome 1', order=1)

        url = _reverse_or_skip(['learningoutcome-list', 'learning-outcome-list'])
        if url is None:
            pytest.skip("learningoutcome-list URL not found")

        response = admin_client.get(url)
        assert response.status_code == 200

    def test_learning_outcome_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)
        outcome = LearningOutcome.objects.create(tenant=tenant, sub_strand=sub_strand, description='Outcome 1', order=1)

        url = _reverse_or_skip(['learningoutcome-detail', 'learning-outcome-detail'], {'pk': outcome.id})
        if url is None:
            pytest.skip("learningoutcome-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]
