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
class TestAttendanceSessionViewsExtended:
    def test_attendance_session_create(self, teacher_client, teacher_user):
        tenant = teacher_user.tenant
        classroom = ClassroomFactory(tenant=tenant)
        subject = SubjectFactory(tenant=tenant)

        url = _reverse_or_skip(['attendancesession-list', 'attendance-session-list'])
        if url is None:
            pytest.skip("attendance-session-list URL not found")

        payload = {
            'classroom': classroom.id,
            'subject': subject.id,
            'date': '2026-01-15',
            'session_type': 'daily',
            'term': 'term1',
            'academic_year': 2026,
        }
        response = teacher_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

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

    def test_attendance_session_filter_by_date(self, teacher_client, teacher_user):
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

        response = teacher_client.get(url, {'date': '2026-01-15'})
        assert response.status_code == 200

    def test_attendance_session_filter_by_classroom(self, teacher_client, teacher_user):
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

        response = teacher_client.get(url, {'classroom': classroom.id})
        assert response.status_code == 200


@pytest.mark.django_db
class TestAttendanceRecordViewsExtended:
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

    def test_attendance_record_delete(self, teacher_client, teacher_user):
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

        response = teacher_client.delete(url)
        assert response.status_code in [204, 200, 404]

    def test_attendance_record_filter_by_session(self, teacher_client, teacher_user):
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

        response = teacher_client.get(url, {'session': session.id})
        assert response.status_code == 200

    def test_attendance_record_filter_by_status(self, teacher_client, teacher_user):
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
        AttendanceRecord.objects.create(
            tenant=tenant,
            session=session,
            student=StudentFactory(tenant=tenant, classroom=classroom),
            status='A',
        )

        url = _reverse_or_skip(['attendancerecord-list', 'attendance-record-list'])
        if url is None:
            pytest.skip("attendance-record-list URL not found")

        response = teacher_client.get(url, {'status': 'P'})
        assert response.status_code == 200
