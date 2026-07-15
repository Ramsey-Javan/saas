"""Subject-teacher scoped analytics.

A subject teacher sees analytics ONLY for the subjects they teach,
organized by classroom. Each subject-classroom combination shows:
- Performance metrics (mean, grade distribution)
- Top/bottom students in that subject
- Early warning students for that subject
- Term-over-term trend
"""
from collections import defaultdict

from django.core.cache import cache
from django.utils import timezone

from academics.models import ExamResult, ExamSetup, ExamConfig, ClassSubjectAssignment, ExamSubject
from students.models import Classroom
from ._helpers import d, safe_mean, grade_dist, line_chart, cbc_pie, TERM_ORDER, compute_level
from .cache_keys import CACHE_TTL_SUMMARY
from .exceptions import InsufficientDataError


def _get_teacher_subject_classrooms(tenant, user, academic_year):
    """
    Resolve which (subject, classroom) pairs this teacher is assigned to.
    Returns list of dicts: [{subject_id, subject_name, subject_code, classroom_id, classroom_name, stream, grade_level}]
    """
    # Direct assignments via ExamSubject (exam-specific)
    direct_assignments = list(
        ExamSubject.objects.filter(
            teacher=user,
            exam__tenant=tenant,
            exam__academic_year=academic_year,
        ).select_related('exam__classroom', 'subject').values(
            'subject_id', 'subject__name', 'subject__code',
            'exam__classroom_id', 'exam__classroom__name',
            'exam__classroom__stream', 'exam__classroom__grade_level',
        ).distinct()
    )

    # Assignment-based via ClassSubjectAssignment (term-based)
    assignment_subjects = list(
        ClassSubjectAssignment.objects.filter(
            tenant=tenant,
            teacher=user,
            academic_year=academic_year,
        ).select_related('classroom', 'subject').values(
            'subject_id', 'subject__name', 'subject__code',
            'classroom_id', 'classroom__name',
            'classroom__stream', 'classroom__grade_level',
        ).distinct()
    )

    # Merge and deduplicate by (subject_id, classroom_id)
    seen = set()
    pairs = []

    for a in direct_assignments:
        key = (a['subject_id'], a['exam__classroom_id'])
        if key not in seen:
            seen.add(key)
            pairs.append({
                'subject_id': a['subject_id'],
                'subject_name': a['subject__name'],
                'subject_code': a['subject__code'],
                'classroom_id': a['exam__classroom_id'],
                'classroom_name': a['exam__classroom__name'],
                'stream': a['exam__classroom__stream'],
                'grade_level': a['exam__classroom__grade_level'],
            })

    for a in assignment_subjects:
        key = (a['subject_id'], a['classroom_id'])
        if key not in seen:
            seen.add(key)
            pairs.append({
                'subject_id': a['subject_id'],
                'subject_name': a['subject__name'],
                'subject_code': a['subject__code'],
                'classroom_id': a['classroom_id'],
                'classroom_name': a['classroom__name'],
                'stream': a['classroom__stream'],
                'grade_level': a['classroom__grade_level'],
            })

    return pairs


def get_subject_teacher_overview(tenant, user, academic_year, term=None):
    """
    Subject teacher dashboard overview.

    Returns:
    - subjects: list of subjects the teacher teaches
    - subject_classrooms: per (subject, classroom) performance data
    - term_trend: performance trend across terms for each subject
    - top_students: top performers per subject-classroom
    - bottom_students: struggling students per subject-classroom
    """
    pairs = _get_teacher_subject_classrooms(tenant, user, academic_year)

    if not pairs:
        return {
            "academic_year": academic_year,
            "term": term,
            "is_subject_teacher_view": True,
            "subjects": [],
            "subject_classrooms": [],
            "term_trend": [],
            "grade_distribution": {"counts": {"EE": 0, "ME": 0, "AE": 0, "BE": 0}, "percentages": {"EE": "0.00", "ME": "0.00", "AE": "0.00", "BE": "0.00"}},
            "top_students": [],
            "bottom_students": [],
            "early_warning_count": 0,
        }

    subject_ids = list({p['subject_id'] for p in pairs})
    classroom_ids = list({p['classroom_id'] for p in pairs})

    # Fetch all results for this teacher's subject-classroom combinations
    results_filter = {
        'tenant': tenant,
        'exam_subject__exam__academic_year': academic_year,
        'student__classroom_id__in': classroom_ids,
        'exam_subject__subject_id__in': subject_ids,
    }
    if term:
        results_filter['exam_subject__exam__term'] = term

    rows = list(
        ExamResult.objects
        .filter(**results_filter)
        .values(
            "student_id", "percentage", "cbc_level", "marks",
            "exam_subject__exam__term",
            "exam_subject__subject__id", "exam_subject__subject__name",
            "student__classroom_id", "student__classroom__name",
            "student__first_name", "student__last_name", "student__admission_number",
        )
    )

    if not rows:
        # Return structure with subjects but no data
        subjects_grouped = defaultdict(list)
        for p in pairs:
            subjects_grouped[p['subject_id']].append(p)

        subject_list = []
        for sid, ps in subjects_grouped.items():
            subject_list.append({
                "id": sid,
                "name": ps[0]['subject_name'],
                "code": ps[0]['subject_code'],
                "classrooms": [
                    {
                        "id": p['classroom_id'],
                        "name": p['classroom_name'],
                        "stream": p['stream'],
                        "grade_level": p['grade_level'],
                        "mean": None,
                        "student_count": 0,
                    }
                    for p in ps
                ],
            })

        return {
            "academic_year": academic_year,
            "term": term,
            "is_subject_teacher_view": True,
            "subjects": subject_list,
            "subject_classrooms": [],
            "term_trend": [],
            "grade_distribution": {"counts": {"EE": 0, "ME": 0, "AE": 0, "BE": 0}, "percentages": {"EE": "0.00", "ME": "0.00", "AE": "0.00", "BE": "0.00"}},
            "top_students": [],
            "bottom_students": [],
            "early_warning_count": 0,
        }

    config = ExamConfig.get_for_tenant(tenant)

    # Group by (subject_id, classroom_id)
    by_subject_classroom = defaultdict(list)
    by_subject_term = defaultdict(lambda: defaultdict(list))
    subject_names = {}
    classroom_names = {}

    for r in rows:
        sid = r['exam_subject__subject__id']
        cid = r['student__classroom_id']
        key = (sid, cid)
        by_subject_classroom[key].append(r)
        subject_names[sid] = r['exam_subject__subject__name']
        classroom_names[cid] = r['student__classroom__name']

        # For term trend (all terms)
        t = r['exam_subject__exam__term']
        by_subject_term[sid][t].append(float(r['percentage']))

    # Build subject-classroom cards
    subject_classrooms = []
    for (sid, cid), sc_rows in by_subject_classroom.items():
        pcts = [float(r['percentage']) for r in sc_rows]
        levels = [r['cbc_level'] for r in sc_rows]
        mean_pct = safe_mean(pcts)

        # Per-student aggregation for top/bottom
        by_student = defaultdict(list)
        student_meta = {}
        for r in sc_rows:
            stu_id = r['student_id']
            by_student[stu_id].append(float(r['percentage']))
            if stu_id not in student_meta:
                student_meta[stu_id] = {
                    'id': stu_id,
                    'name': f"{r['student__first_name']} {r['student__last_name']}".strip(),
                    'admission_number': r['student__admission_number'] or '',
                }

        student_means = [
            {**student_meta[stu_id], 'mean': safe_mean(pcts)}
            for stu_id, pcts in by_student.items()
        ]
        student_means.sort(key=lambda x: x['mean'], reverse=True)

        # Find stream from pairs
        stream = next((p['stream'] for p in pairs if p['subject_id'] == sid and p['classroom_id'] == cid), None)
        grade_level = next((p['grade_level'] for p in pairs if p['subject_id'] == sid and p['classroom_id'] == cid), None)

        subject_classrooms.append({
            'subject_id': sid,
            'subject_name': subject_names[sid],
            'classroom_id': cid,
            'classroom_name': classroom_names[cid],
            'stream': stream,
            'grade_level': grade_level,
            'mean_percentage': d(mean_pct),
            'cbc_level': compute_level(config, mean_pct),
            'student_count': len(by_student),
            'result_count': len(sc_rows),
            'grade_distribution': grade_dist(levels),
            'top_student': student_means[0] if student_means else None,
            'bottom_student': student_means[-1] if student_means else None,
            'top_students': student_means[:3],  # Top 3 for quick view
        })

    # Sort by subject name, then by grade level
    subject_classrooms.sort(key=lambda x: (x['subject_name'], x['grade_level'] or '', x['stream'] or ''))

    # Build subjects list (grouped by subject)
    subjects_grouped = defaultdict(list)
    for sc in subject_classrooms:
        subjects_grouped[sc['subject_id']].append(sc)

    subjects = []
    for sid, scs in subjects_grouped.items():
        subjects.append({
            'id': sid,
            'name': scs[0]['subject_name'],
            'code': next((p['subject_code'] for p in pairs if p['subject_id'] == sid), ''),
            'classrooms': [
                {
                    'id': sc['classroom_id'],
                    'name': sc['classroom_name'],
                    'stream': sc['stream'],
                    'grade_level': sc['grade_level'],
                    'mean': sc['mean_percentage'],
                    'student_count': sc['student_count'],
                }
                for sc in scs
            ],
        })

    # Term trend per subject
    term_trend = []
    for sid, term_data in by_subject_term.items():
        terms_sorted = sorted(term_data.keys(), key=lambda t: TERM_ORDER.get(t, 99))
        term_trend.append({
            'subject_id': sid,
            'subject_name': subject_names[sid],
            'terms': [
                {'term': t, 'mean': d(safe_mean(term_data[t]))}
                for t in terms_sorted
            ],
        })

    # Overall grade distribution across all subject-classroom combos
    all_levels = [r['cbc_level'] for r in rows]

    data = {
        'academic_year': academic_year,
        'term': term,
        'is_subject_teacher_view': True,
        'subjects': subjects,
        'subject_classrooms': subject_classrooms,
        'term_trend': term_trend,
        'grade_distribution': grade_dist(all_levels),
        'top_students': [sc['top_student'] for sc in subject_classrooms if sc['top_student']],
        'bottom_students': [sc['bottom_student'] for sc in subject_classrooms if sc['bottom_student']],
        'early_warning_count': 0,  # Will be populated by separate call
    }

    return data


def get_subject_teacher_early_warning(tenant, user, term, academic_year):
    """
    Early warning scoped to subjects the teacher teaches.
    Returns students at-risk specifically in the teacher's subjects.
    """
    pairs = _get_teacher_subject_classrooms(tenant, user, academic_year)

    if not pairs:
        return {
            'term': term,
            'academic_year': academic_year,
            'at_risk_count': 0,
            'total_students_evaluated': 0,
            'students': [],
        }

    subject_ids = list({p['subject_id'] for p in pairs})
    classroom_ids = list({p['classroom_id'] for p in pairs})

    rows = list(
        ExamResult.objects
        .filter(
            tenant=tenant,
            exam_subject__exam__term=term,
            exam_subject__exam__academic_year=academic_year,
            student__classroom_id__in=classroom_ids,
            exam_subject__subject_id__in=subject_ids,
        )
        .values(
            "student_id", "percentage", "cbc_level",
            "exam_subject__subject__id", "exam_subject__subject__name",
            "student__classroom_id", "student__classroom__name",
            "student__first_name", "student__last_name", "student__admission_number",
        )
    )

    if not rows:
        raise InsufficientDataError(
            filters={"term": term, "academic_year": academic_year},
            suggestion="No exam results for your subjects this term yet.",
        )

    config = ExamConfig.get_for_tenant(tenant)

    by_student_subject = defaultdict(lambda: defaultdict(list))
    student_meta = {}
    student_classroom = {}

    for r in rows:
        sid = r['student_id']
        subj_id = r['exam_subject__subject__id']
        by_student_subject[sid][subj_id].append(float(r['percentage']))
        if sid not in student_meta:
            student_meta[sid] = {
                'id': sid,
                'name': f"{r['student__first_name']} {r['student__last_name']}".strip(),
                'admission_number': r['student__admission_number'] or '',
            }
            student_classroom[sid] = {
                'id': r['student__classroom_id'],
                'name': r['student__classroom__name'],
            }

    flagged = []

    for sid, subjects in by_student_subject.items():
        subject_risks = []
        overall_pcts = []

        for subj_id, pcts in subjects.items():
            mean_pct = safe_mean(pcts)
            overall_pcts.extend(pcts)

            if mean_pct < config.me_min:
                subject_risks.append({
                    'subject_id': subj_id,
                    'subject_name': next(
                        (r['exam_subject__subject__name'] for r in rows
                         if r['exam_subject__subject__id'] == subj_id), 'Unknown'
                    ),
                    'mean': d(mean_pct),
                    'severity': 'high' if mean_pct < config.ae_min else 'medium',
                })

        if not subject_risks:
            continue

        overall_mean = safe_mean(overall_pcts)
        risk_level = 'high' if any(r['severity'] == 'high' for r in subject_risks) else 'medium'

        flagged.append({
            'student': {
                'id': sid,
                'name': student_meta[sid]['name'],
                'admission_number': student_meta[sid]['admission_number'],
                'classroom': student_classroom[sid],
            },
            'risk_level': risk_level,
            'subject_risks': subject_risks,
            'current_term_mean': float(d(overall_mean)),
            'recommended_action': (
                'Schedule a parent-teacher meeting as soon as possible.'
                if risk_level == 'high'
                else 'Monitor closely and consider targeted subject support.'
            ),
        })

    risk_order = {'high': 0, 'medium': 1, 'low': 2}
    flagged.sort(key=lambda e: (risk_order[e['risk_level']], -e['current_term_mean']))

    return {
        'term': term,
        'academic_year': academic_year,
        'at_risk_count': len(flagged),
        'total_students_evaluated': len(by_student_subject),
        'students': flagged,
    }

def get_subject_teacher_classrooms(tenant, user, subject_id, academic_year, term=None):
    """
    Return all classroom-level data for a specific subject that this teacher teaches.
    Used when a subject teacher clicks 'View Details' on a subject card.
    """
    from academics.models import Subject

    # Verify teacher actually teaches this subject
    assigned = set(
        ClassSubjectAssignment.objects.filter(
            tenant=tenant, teacher=user, subject_id=subject_id,
            academic_year=academic_year,
        ).values_list('classroom_id', flat=True)
    )
    direct = set(
        ExamSubject.objects.filter(
            teacher=user, subject_id=subject_id,
            exam__tenant=tenant, exam__academic_year=academic_year,
        ).values_list('exam__classroom_id', flat=True)
    )
    classroom_ids = list(assigned | direct)

    if not classroom_ids:
        return {
            "subject_id": subject_id,
            "subject_name": Subject.objects.filter(id=subject_id, tenant=tenant).values_list('name', flat=True).first() or "Unknown",
            "academic_year": academic_year,
            "term": term,
            "classrooms": [],
        }

    results_filter = {
        'tenant': tenant,
        'exam_subject__exam__academic_year': academic_year,
        'exam_subject__subject_id': subject_id,
        'student__classroom_id__in': classroom_ids,
    }
    if term:
        results_filter['exam_subject__exam__term'] = term

    rows = list(
        ExamResult.objects
        .filter(**results_filter)
        .values(
            "student_id", "percentage", "cbc_level", "marks",
            "student__first_name", "student__last_name", "student__admission_number",
            "student__classroom_id", "student__classroom__name", "student__classroom__stream",
            "exam_subject__exam__term",
        )
    )

    subject_name = Subject.objects.filter(id=subject_id, tenant=tenant).values_list('name', flat=True).first() or "Unknown"

    if not rows:
        return {
            "subject_id": subject_id,
            "subject_name": subject_name,
            "academic_year": academic_year,
            "term": term,
            "classrooms": [],
        }

    # Group by classroom
    by_classroom = defaultdict(list)
    for r in rows:
        cid = r['student__classroom_id']
        by_classroom[cid].append(r)

    classroom_list = []
    for cid, cr in by_classroom.items():
        pcts = [float(r['percentage']) for r in cr]
        levels = [r['cbc_level'] for r in cr]
        mean = safe_mean(pcts)

        by_student = defaultdict(list)
        student_meta = {}
        for r in cr:
            sid = r['student_id']
            by_student[sid].append(float(r['percentage']))
            if sid not in student_meta:
                student_meta[sid] = {
                    'id': sid,
                    'name': f"{r['student__first_name']} {r['student__last_name']}".strip(),
                    'admission_number': r['student__admission_number'] or '',
                }

        student_means = [
            {**student_meta[sid], 'mean': safe_mean(pcts)}
            for sid, pcts in by_student.items()
        ]
        student_means.sort(key=lambda x: x['mean'], reverse=True)

        classroom_list.append({
            'id': cid,
            'name': cr[0]['student__classroom__name'],
            'stream': cr[0]['student__classroom__stream'],
            'mean_percentage': d(mean),
            'cbc_level': 'EE' if mean >= 75 else 'ME' if mean >= 50 else 'AE' if mean >= 30 else 'BE',
            'student_count': len(by_student),
            'result_count': len(cr),
            'grade_distribution': grade_dist(levels),
            'top_students': student_means[:3],
            'bottom_students': student_means[-3:] if len(student_means) >= 3 else student_means[:],
            'all_students': student_means,
        })

    return {
        "subject_id": subject_id,
        "subject_name": subject_name,
        "academic_year": academic_year,
        "term": term,
        "classrooms": classroom_list,
    }