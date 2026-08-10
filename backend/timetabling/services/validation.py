from dataclasses import dataclass

from rest_framework.exceptions import ValidationError

from ..models import SubjectRule, TeacherAvailability, TimetableEntry


@dataclass
class TimetableMove:
    tenant: object
    job: object
    classroom: object
    subject: object
    teacher: object
    period: object
    room: object = None
    entry_id: int | None = None


def periods_overlap(left, right):
    if left.day_of_week != right.day_of_week:
        return False
    return left.start_time < right.end_time and right.start_time < left.end_time


def validate_timetable_move(move):
    if move.classroom.tenant_id != move.tenant.id:
        raise ValidationError({'classroom': 'Classroom must belong to your school.'})
    if move.subject.tenant_id != move.tenant.id:
        raise ValidationError({'subject': 'Subject must belong to your school.'})
    if move.teacher.tenant_id != move.tenant.id:
        raise ValidationError({'teacher': 'Teacher must belong to your school.'})
    if move.period.tenant_id != move.tenant.id:
        raise ValidationError({'period': 'Period must belong to your school.'})
    if move.classroom.schedule_template_id != move.period.schedule_template_id:
        raise ValidationError({'period': 'Period must belong to this classroom bell schedule.'})
    if move.room and move.room.tenant_id != move.tenant.id:
        raise ValidationError({'room': 'Room must belong to your school.'})

    rule = SubjectRule.objects.filter(
        tenant=move.tenant,
        subject=move.subject,
        grade_band=move.classroom.grade_level,
        is_active=True,
    ).first()
    if not rule:
        raise ValidationError({'subject': 'No timetable rule is configured for this subject and class grade.'})
    if rule.requires_room_type:
        if not move.room:
            raise ValidationError({'room': f'{move.subject.name} requires a {rule.requires_room_type} room.'})
        if move.room.room_type != rule.requires_room_type:
            raise ValidationError({'room': f'{move.subject.name} requires a {rule.requires_room_type} room.'})
    if rule.is_hard_excluded and rule.excluded_periods.filter(id=move.period.id).exists():
        raise ValidationError({'period': f'{move.subject.name} cannot be scheduled in this period.'})

    if TeacherAvailability.objects.filter(
        tenant=move.tenant,
        teacher=move.teacher,
        period=move.period,
        is_available=False,
    ).exists():
        raise ValidationError({'teacher': 'Teacher is not available in this period.'})

    entries = TimetableEntry.objects.filter(tenant=move.tenant, job=move.job).select_related('period')
    if move.entry_id:
        entries = entries.exclude(id=move.entry_id)

    if entries.filter(classroom=move.classroom, period=move.period).exists():
        raise ValidationError({'classroom': 'This class already has a lesson in that period.'})

    for entry in entries.filter(teacher=move.teacher):
        if periods_overlap(entry.period, move.period):
            raise ValidationError({'teacher': 'Teacher is already booked during that time.'})

    if move.room:
        for entry in entries.filter(room=move.room):
            if periods_overlap(entry.period, move.period):
                raise ValidationError({'room': 'Room is already booked during that time.'})

    return True

