"""Signal handlers for analytics cache invalidation.

Whenever exam data changes, precisely delete every cache key that could
contain stale data -- using the SAME key-builder functions the read-path
(services/) already calls, so invalidation can never drift out of sync
with what's actually cached.
"""
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from academics.models import ExamResult, ExamSetup

from .services.cache_keys import (
    class_performance,
    class_ranking,
    cohort_reference,
    early_warning,
    exam_breakdown,
    exam_rankings,
    grade_distribution,
    improvement_tracker,
    school_overview,
    student_longitudinal,
    student_performance,
    student_profile,
    student_report_card,
    subject_analysis,
    subject_comparison,
    subject_school_analysis,
    term_summary,
)


def _invalidate_for_exam(tenant, exam):
    """Delete every cache key that could contain data from this exam."""
    cache.delete(school_overview(tenant.id, exam.academic_year))
    cache.delete(term_summary(tenant.id, exam.academic_year, exam.term))
    cache.delete(exam_breakdown(tenant.id, exam.id))
    cache.delete(exam_rankings(tenant.id, exam.id))
    cache.delete(subject_analysis(tenant.id, exam.id, None))

    if exam.classroom_id:
        cache.delete(class_performance(tenant.id, exam.classroom_id, exam.term, exam.academic_year))
        cache.delete(class_ranking(tenant.id, exam.classroom_id, exam.term, exam.academic_year))
        cache.delete(subject_comparison(tenant.id, exam.classroom_id, exam.term, exam.academic_year))
        cache.delete(grade_distribution(tenant.id, exam.classroom_id, exam.exam_type, exam.term, exam.academic_year))
        cache.delete(improvement_tracker(tenant.id, exam.classroom_id, exam.academic_year))

    cache.delete(early_warning(tenant.id, exam.term, exam.academic_year))

    for exam_subject in exam.exam_subjects.all():
        cache.delete(subject_analysis(tenant.id, exam.id, exam_subject.subject_id))
        cache.delete(subject_school_analysis(tenant.id, exam_subject.subject_id, exam.term, exam.academic_year))
        if exam.classroom_id:
            cache.delete(cohort_reference(
                tenant.id, exam.classroom_id, exam_subject.subject_id, exam.term, exam.academic_year,
            ))


def _invalidate_for_student(tenant, student, exam):
    if not student:
        return
    cache.delete(student_profile(tenant.id, student.id, exam.academic_year))
    cache.delete(student_report_card(tenant.id, student.id, exam.term, exam.academic_year))
    cache.delete(student_performance(tenant.id, student.id, exam.term, exam.academic_year))
    cache.delete(student_longitudinal(tenant.id, student.id, exam.academic_year))


@receiver(post_save, sender=ExamResult)
@receiver(post_delete, sender=ExamResult)
def invalidate_exam_result_cache(sender, instance, **kwargs):
    """Invalidate every analytics cache entry that could be affected by
    this ExamResult being created, updated, or deleted."""
    tenant = instance.tenant
    exam = instance.exam_subject.exam
    _invalidate_for_exam(tenant, exam)
    _invalidate_for_student(tenant, instance.student, exam)


@receiver(post_save, sender=ExamSetup)
@receiver(post_delete, sender=ExamSetup)
def invalidate_exam_setup_cache(sender, instance, **kwargs):
    """Invalidate cache when an exam setup's own metadata changes (e.g.
    term/year corrected, classroom reassigned) -- results may be
    unchanged, but the exam metadata driving these cache keys has."""
    tenant = instance.tenant
    _invalidate_for_exam(tenant, instance)