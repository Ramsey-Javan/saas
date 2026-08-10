import pytest
from rest_framework.exceptions import ValidationError

from timetabling.services.readiness import check_timetable_readiness
from timetabling.services.validation import TimetableMove, validate_timetable_move

from .factories import (
    AdminUserFactory,
    ClassroomFactory,
    PeriodFactory,
    RoomResourceFactory,
    ScheduleTemplateFactory,
    SubjectFactory,
    SubjectRuleFactory,
    TeacherSubjectAssignmentFactory,
    TeacherUserFactory,
    TimetableEntryFactory,
    TimetableJobFactory,
)


@pytest.mark.django_db
class TestTimetableApiPermissions:
    def test_teacher_cannot_access_readiness(self, teacher_client):
        response = teacher_client.get('/api/timetabling/readiness/')
        assert response.status_code == 403

    def test_teacher_cannot_list_jobs(self, teacher_client):
        response = teacher_client.get('/api/timetabling/jobs/')
        assert response.status_code == 403

    def test_teacher_can_list_own_entries(self, teacher_client, teacher_user, tenant):
        other_teacher = TeacherUserFactory(tenant=tenant)
        job = TimetableJobFactory(tenant=tenant)
        schedule = ScheduleTemplateFactory(tenant=tenant)
        period = PeriodFactory(tenant=tenant, schedule_template=schedule)
        classroom = ClassroomFactory(tenant=tenant, schedule_template=schedule)
        subject = SubjectFactory(tenant=tenant)
        mine = TimetableEntryFactory(
            tenant=tenant, job=job, classroom=classroom, subject=subject,
            teacher=teacher_user, period=period,
        )
        TimetableEntryFactory(
            tenant=tenant, job=job, classroom=classroom, subject=subject,
            teacher=other_teacher, period=PeriodFactory(tenant=tenant, schedule_template=schedule, order=2),
        )

        response = teacher_client.get('/api/timetabling/entries/')
        assert response.status_code == 200
        ids = {row['id'] for row in response.data.get('results', response.data)}
        assert mine.id in ids
        assert len(ids) == 1

    def test_admin_can_access_readiness(self, admin_client):
        response = admin_client.get('/api/timetabling/readiness/')
        assert response.status_code == 200
        assert 'ready' in response.data


@pytest.mark.django_db
def test_readiness_reports_missing_room_and_assignment():
    tenant = AdminUserFactory().tenant
    schedule = ScheduleTemplateFactory(tenant=tenant)
    classroom = ClassroomFactory(tenant=tenant, grade_level='Grade 4', schedule_template=schedule)
    subject = SubjectFactory(tenant=tenant, name='Integrated Science')
    SubjectRuleFactory(
        tenant=tenant,
        subject=subject,
        grade_band=classroom.grade_level,
        periods_per_week=2,
        requires_room_type='lab',
    )

    result = check_timetable_readiness(tenant)

    assert result['ready'] is False
    assert {error['code'] for error in result['errors']} == {'missing_room', 'missing_teacher_assignment'}


@pytest.mark.django_db
def test_readiness_passes_with_room_assignment_and_schedule():
    tenant = AdminUserFactory().tenant
    schedule = ScheduleTemplateFactory(tenant=tenant)
    classroom = ClassroomFactory(tenant=tenant, grade_level='Grade 4', schedule_template=schedule)
    subject = SubjectFactory(tenant=tenant, name='Integrated Science')
    teacher = TeacherUserFactory(tenant=tenant)
    SubjectRuleFactory(
        tenant=tenant,
        subject=subject,
        grade_band=classroom.grade_level,
        periods_per_week=2,
        requires_room_type='lab',
    )
    RoomResourceFactory(tenant=tenant, room_type='lab')
    TeacherSubjectAssignmentFactory(tenant=tenant, classroom=classroom, subject=subject, teacher=teacher)

    result = check_timetable_readiness(tenant)

    assert result['ready'] is True
    assert result['errors'] == []


@pytest.mark.django_db
def test_manual_move_rejects_teacher_time_overlap():
    tenant = AdminUserFactory().tenant
    schedule = ScheduleTemplateFactory(tenant=tenant)
    classroom_one = ClassroomFactory(tenant=tenant, grade_level='Grade 4', schedule_template=schedule)
    classroom_two = ClassroomFactory(tenant=tenant, grade_level='Grade 4', schedule_template=schedule)
    subject = SubjectFactory(tenant=tenant)
    teacher = TeacherUserFactory(tenant=tenant)
    period = PeriodFactory(tenant=tenant, schedule_template=schedule, day_of_week=1, order=1)
    job = TimetableJobFactory(tenant=tenant)
    SubjectRuleFactory(tenant=tenant, subject=subject, grade_band='Grade 4')
    TimetableEntryFactory(
        tenant=tenant,
        job=job,
        classroom=classroom_one,
        subject=subject,
        teacher=teacher,
        period=period,
    )

    with pytest.raises(ValidationError):
        validate_timetable_move(TimetableMove(
            tenant=tenant,
            job=job,
            classroom=classroom_two,
            subject=subject,
            teacher=teacher,
            period=period,
        ))
