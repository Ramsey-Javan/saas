"""Classroom-level analytics for one term: the "Term x Class" view that
was missing from the original 4-level/3-lens design. Answers "how did
Grade 8 do this term, subject by subject" and "who's top/bottom in this
class this term" -- aggregating across EVERY exam the class sat that
term, not a single exam_id.
"""
from collections import defaultdict
from decimal import Decimal

from django.core.cache import cache

from academics.models import ExamConfig, ExamResult, ExamSetup

from .cache_keys import (
    CACHE_TTL_SUMMARY, class_performance, class_ranking, grade_distribution,
)
from ._helpers import (
    d, safe_mean, safe_median, safe_stdev, grade_dist, bar_chart, cbc_pie,
    CBC_COLORS, CBC_LABELS, compute_level,
)
from .exceptions import InsufficientDataError


def get_class_performance(tenant, classroom, term, academic_year):
    """
    Per-subject performance for one classroom across an ENTIRE term
    (every exam sat that term, combined) -- the entry point for "best/
    worst subject in this class", and the list of exams to drill into
    individually via exam-breakdown.
    Charts: bar (subject means), pie (grade dist).
    1 DB query.
    """
    ck = class_performance(tenant.id, classroom.id, term, academic_year)
    cached = cache.get(ck)
    if cached:
        return cached

    rows = list(
        ExamResult.objects
        .filter(
            tenant=tenant,
            student__classroom=classroom,
            exam_subject__exam__term=term,
            exam_subject__exam__academic_year=academic_year,
        )
        .values(
            "student_id", "marks", "percentage", "cbc_level",
            "exam_subject__subject__id", "exam_subject__subject__name", "exam_subject__subject__code",
            "exam_subject__total_marks",
            "exam_subject__teacher__first_name", "exam_subject__teacher__last_name",
            "exam_subject__exam__id", "exam_subject__exam__name",
        )
    )

    if not rows:
        raise InsufficientDataError(
            filters={"classroom_id": classroom.id, "term": term, "academic_year": academic_year},
            suggestion="No exam results recorded for this class this term yet.",
        )

    by_subj = defaultdict(list)
    subj_meta = {}
    exams_seen = {}
    for r in rows:
        sid = r["exam_subject__subject__id"]
        by_subj[sid].append(r)
        if sid not in subj_meta:
            fn = r["exam_subject__teacher__first_name"] or ""
            ln = r["exam_subject__teacher__last_name"] or ""
            subj_meta[sid] = {
                "id": sid,
                "name": r["exam_subject__subject__name"],
                "code": r["exam_subject__subject__code"],
                "teacher": (fn + " " + ln).strip() or "Unassigned",
            }
        eid = r["exam_subject__exam__id"]
        if eid not in exams_seen:
            exams_seen[eid] = r["exam_subject__exam__name"]

    subjects = []
    for sid, subj_rows in by_subj.items():
        pcts = [float(r["percentage"]) for r in subj_rows]
        marks = [float(r["marks"]) for r in subj_rows]
        levels = [r["cbc_level"] for r in subj_rows]
        passing = sum(1 for lv in levels if lv in ("ME", "EE"))
        subjects.append({
            "subject": subj_meta[sid],
            "mean_percentage": d(safe_mean(pcts)),
            "mean_marks": d(safe_mean(marks)),
            "highest": d(max(marks)),
            "lowest": d(min(marks)),
            "std_deviation": d(safe_stdev(pcts)),
            "pass_rate": d((passing / len(levels)) * 100) if levels else Decimal("0.00"),
            "student_count": len({r["student_id"] for r in subj_rows}),
            "grade_distribution": grade_dist(levels),
        })

    subjects.sort(key=lambda x: x["mean_percentage"], reverse=True)

    all_levels = [r["cbc_level"] for r in rows]
    all_pcts = [float(r["percentage"]) for r in rows]

    subj_names = [s["subject"]["name"] for s in subjects]
    subj_means = [float(s["mean_percentage"]) for s in subjects]

    chart_subject_bar = {
        **bar_chart(
            labels=subj_names,
            datasets=[{"label": "Mean Score (%)", "data": subj_means, "color": "#2563eb"}],
        ),
        "title": f"{classroom.name} — {term.upper()} {academic_year} Subject Performance",
    }

    chart_pie = cbc_pie(all_levels, title=f"{classroom.name} — {term.upper()} {academic_year} Grade Distribution")

    data = {
        "classroom": {"id": classroom.id, "name": classroom.name, "grade_level": classroom.grade_level},
        "term": term,
        "academic_year": academic_year,
        "student_count": len({r["student_id"] for r in rows}),
        "exams_this_term": [{"id": eid, "name": name} for eid, name in exams_seen.items()],
        "subjects": subjects,
        "grade_distribution": grade_dist(all_levels),
        "mean_percentage": d(safe_mean(all_pcts)),
        "charts": {
            "subject_bar": chart_subject_bar,
            "grade_pie": chart_pie,
        },
    }

    cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
    return data


def get_class_ranking(tenant, classroom, term, academic_year):
    """
    Student rankings within one class for the whole term (every exam
    combined, unlike get_class_rankings in exam.py which is one exam only).
    1 DB query.
    """
    ck = class_ranking(tenant.id, classroom.id, term, academic_year)
    cached = cache.get(ck)
    if cached:
        return cached

    config = ExamConfig.get_for_tenant(tenant)

    rows = list(
        ExamResult.objects
        .filter(
            tenant=tenant,
            student__classroom=classroom,
            exam_subject__exam__term=term,
            exam_subject__exam__academic_year=academic_year,
        )
        .values(
            "student_id", "percentage",
            "student__first_name", "student__last_name", "student__admission_number",
        )
    )

    if not rows:
        raise InsufficientDataError(
            filters={"classroom_id": classroom.id, "term": term, "academic_year": academic_year},
        )

    stu_pcts = defaultdict(list)
    stu_meta = {}
    for r in rows:
        sid = r["student_id"]
        stu_pcts[sid].append(float(r["percentage"]))
        if sid not in stu_meta:
            stu_meta[sid] = {
                "id": sid,
                "name": f"{r['student__first_name']} {r['student__last_name']}".strip(),
                "admission_number": r["student__admission_number"] or "",
            }

    rankings = sorted(
        [
            {
                "student": stu_meta[sid],
                "mean_percentage": d(safe_mean(pcts)),
                "cbc_level": compute_level(config, safe_mean(pcts)),
            }
            for sid, pcts in stu_pcts.items()
        ],
        key=lambda x: x["mean_percentage"], reverse=True,
    )
    for i, r in enumerate(rankings, 1):
        r["rank"] = i

    data = {
        "classroom": {"id": classroom.id, "name": classroom.name},
        "term": term,
        "academic_year": academic_year,
        "class_size": len(rankings),
        "class_mean": d(safe_mean([float(r["mean_percentage"]) for r in rankings])),
        "rankings": rankings,
    }

    cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
    return data


def get_grade_distribution(tenant, classroom, exam_type, term, academic_year):
    """
    EE/ME/AE/BE spread for one classroom, filtered to a specific exam
    type (e.g. only "midterm" exams), within one term.
    1 DB query.
    """
    ck = grade_distribution(tenant.id, classroom.id, exam_type, term, academic_year)
    cached = cache.get(ck)
    if cached:
        return cached

    rows = list(
        ExamResult.objects
        .filter(
            tenant=tenant,
            student__classroom=classroom,
            exam_subject__exam__term=term,
            exam_subject__exam__academic_year=academic_year,
            exam_subject__exam__exam_type=exam_type,
        )
        .values("student_id", "cbc_level")
    )

    if not rows:
        raise InsufficientDataError(
            filters={
                "classroom_id": classroom.id, "exam_type": exam_type,
                "term": term, "academic_year": academic_year,
            },
            suggestion=f"No {exam_type} exam results recorded for this class this term.",
        )

    levels = [r["cbc_level"] for r in rows]
    dist = grade_dist(levels)

    # Bins shaped exactly for ClassDistributionChart's `data` prop:
    # [{ level, label, count, percentage, color }]
    bins = [
        {
            "level": lv,
            "label": CBC_LABELS[lv],
            "count": dist["counts"][lv],
            "percentage": float(dist["percentages"][lv]),
            "color": CBC_COLORS[lv],
        }
        for lv in ("EE", "ME", "AE", "BE")
    ]

    data = {
        "classroom": {"id": classroom.id, "name": classroom.name},
        "exam_type": exam_type,
        "term": term,
        "academic_year": academic_year,
        "total_students": len({r["student_id"] for r in rows}),
        "bins": bins,
    }

    cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
    return data