from django.urls import reverse

from academics.models import CBCGrade, ExamCBCSync, ExamResult, ExamSetup, ExamSubject, LearningOutcome, Strand, SubStrand, Subject
from tests.factories import ExamSetupFactory, StudentFactory, SubjectFactory


def test_sync_to_cbc_creates_grades_and_audit_record(admin_client, admin_user, db, monkeypatch):
    tenant = admin_user.tenant
    teacher = admin_user
    from students.models import Classroom
    classroom = Classroom.objects.create(
        tenant=tenant,
        name='Grade 4',
        grade_level='Grade 4',
        stream='Blue',
        academic_year='2026',
        capacity=40,
        is_active=True,
    )
    exam = ExamSetup.objects.create(
        tenant=tenant,
        name='Test Exam',
        exam_type='opener',
        classroom=classroom,
        term='term1',
        academic_year=2026,
        start_date='2026-01-10',
        end_date='2026-01-20',
        instructions='Answer all questions.',
        is_active=True,
        created_by=teacher,
    )
    subject = SubjectFactory(tenant=tenant)
    strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
    sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Substrand 1', order=1)
    outcome = LearningOutcome.objects.create(tenant=tenant, sub_strand=sub_strand, description='Outcome 1', order=1)
    student = StudentFactory(tenant=tenant, classroom=exam.classroom)
    exam_subject = ExamSubject.objects.create(tenant=tenant, exam=exam, subject=subject, total_marks=100, teacher=teacher)
    ExamResult.objects.create(
        tenant=tenant,
        exam_subject=exam_subject,
        student=student,
        marks='75.00',
        cbc_level='ME',
        entered_by=teacher,
    )

    # Try multiple possible import paths for assign functions
    try:
        from academics.utils import assign_strand_levels, assign_outcome_levels
        monkeypatch.setattr('academics.views.exams.assign_strand_levels', lambda exam_level, strands: {strand.id: 'ME' for strand in strands})
        monkeypatch.setattr('academics.views.exams.assign_outcome_levels', lambda strand_level, outcomes: {outcome.id: strand_level for outcome in outcomes})
    except ImportError:
        pass

    response = admin_client.post(reverse('examsetup-sync-to-cbc', kwargs={'pk': exam.id}), {}, format='json')

    assert response.status_code == 200
    assert response.data['synced'] == 1
    assert response.data['skipped'] == 0
    assert CBCGrade.objects.filter(tenant=tenant, student=student, learning_outcome=outcome).count() == 1
    assert ExamCBCSync.objects.filter(tenant=tenant, exam=exam, records_synced=1, records_skipped=0).exists()
