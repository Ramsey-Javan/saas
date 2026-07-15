"""Cache key builders for analytics endpoints.

Centralized here so cache invalidation (e.g. when a new ExamResult is
saved, or marks are corrected) can find every key pattern in one place,
and so key format never drifts between service modules.
"""

CACHE_TTL_SUMMARY = 60 * 15  # 15 minutes -- used for school/term-level rollups


def _key(*parts):
    return 'analytics:' + ':'.join(str(p) for p in parts)


def school_overview(tenant_id, academic_year):
    return _key('school-overview', tenant_id, academic_year)


def term_summary(tenant_id, academic_year, term):
    return _key('term-summary', tenant_id, academic_year, term)


def exam_breakdown(tenant_id, exam_id):
    return _key('exam-breakdown', tenant_id, exam_id)


def exam_rankings(tenant_id, exam_id):
    return _key('exam-rankings', tenant_id, exam_id)


def subject_analysis(tenant_id, exam_id, subject_id=None):
    return _key('subject-analysis', tenant_id, exam_id, subject_id or 'all')


def student_profile(tenant_id, student_id, academic_year):
    return _key('student-profile', tenant_id, student_id, academic_year)


def student_report_card(tenant_id, student_id, term, academic_year):
    return _key('student-report-card', tenant_id, student_id, term, academic_year)


def student_performance(tenant_id, student_id, term, academic_year):
    return _key('student-performance', tenant_id, student_id, term, academic_year)


def student_longitudinal(tenant_id, student_id, academic_year):
    return _key('student-longitudinal', tenant_id, student_id, academic_year)


def class_performance(tenant_id, classroom_id, term, academic_year):
    return _key('class-performance', tenant_id, classroom_id, term, academic_year)


def class_ranking(tenant_id, classroom_id, term, academic_year):
    return _key('class-ranking', tenant_id, classroom_id, term, academic_year)


def grade_distribution(tenant_id, classroom_id, exam_type, term, academic_year):
    return _key('grade-distribution', tenant_id, classroom_id, exam_type, term, academic_year)


def subject_comparison(tenant_id, classroom_id, term, academic_year):
    return _key('subject-comparison', tenant_id, classroom_id, term, academic_year)


def subject_school_analysis(tenant_id, subject_id, term, academic_year):
    return _key('subject-school-analysis', tenant_id, subject_id, term, academic_year)


def cohort_reference(tenant_id, classroom_id, subject_id, term, academic_year):
    return _key('cohort-reference', tenant_id, classroom_id, subject_id, term, academic_year)


def improvement_tracker(tenant_id, classroom_id, academic_year):
    return _key('improvement-tracker', tenant_id, classroom_id, academic_year)


def early_warning(tenant_id, term, academic_year):
    return _key('early-warning', tenant_id, term, academic_year)


def school_classrooms(tenant_id, academic_year, term):
    return f"analytics:school_classrooms:{tenant_id}:{academic_year}:{term}"

def invalidate_tenant(tenant_id):
    """
    Glob pattern matching every analytics cache key for one tenant --
    for manual/admin use only (e.g. a future "clear analytics cache for
    this school" management command). django-redis's cache.delete_pattern()
    understands this. NOT used by the automatic signal handlers in
    signals.py, which delete precise keys instead -- that's safer and
    doesn't depend on any particular cache backend supporting patterns.
    """
    return f'analytics:*:{tenant_id}:*'