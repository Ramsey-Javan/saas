"""School-year and term-level analytics: whole-institution health rollups.

Level 4 (School Year) and Level 3 (Term) of the hierarchy, Lens A (School).
"""
import re
from collections import defaultdict

from django.core.cache import cache

from academics.models import ExamResult, ExamSetup, ExamConfig
from students.models import Classroom

from .cache_keys import CACHE_TTL_SUMMARY, school_overview, term_summary, school_classrooms
from ._helpers import d, safe_mean, grade_dist, bar_chart, line_chart, cbc_pie, TERM_ORDER, compute_level
from .exceptions import InsufficientDataError


def _natural_sort_key(s):
    """Sort strings with numbers naturally (Grade 1, Grade 2, ..., Grade 10)."""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', str(s))]


def get_school_overview(tenant, academic_year):
    """
    Whole-school health for one academic year: term-over-term trend,
    per-classroom comparison, overall grade distribution, and quick
    top/bottom-class callouts for the dashboard summary cards.
    Charts: line (term trend), bar (classroom comparison), pie (grade dist).
    2 DB queries: bulk ExamResult fetch, then a light exam count.
    """
    ck = school_overview(tenant.id, academic_year)
    cached = cache.get(ck)
    if cached:
        return cached

    rows = list(
        ExamResult.objects
        .filter(tenant=tenant, exam_subject__exam__academic_year=academic_year)
        .values(
            "student_id", "percentage", "cbc_level",
            "exam_subject__exam__term",
            "exam_subject__exam__classroom_id",
            "exam_subject__exam__classroom__name",
        )
    )

    if not rows:
        raise InsufficientDataError(
            filters={"academic_year": academic_year},
            suggestion="No exam results recorded for this academic year yet.",
        )

    by_term = defaultdict(list)
    by_classroom = defaultdict(list)
    classroom_names = {}
    all_levels = []

    for r in rows:
        pct = float(r["percentage"])
        term = r["exam_subject__exam__term"]
        cid = r["exam_subject__exam__classroom_id"]
        by_term[term].append(pct)
        by_classroom[cid].append(pct)
        classroom_names[cid] = r["exam_subject__exam__classroom__name"]
        all_levels.append(r["cbc_level"])

    terms_sorted = sorted(by_term.keys(), key=lambda t: TERM_ORDER.get(t, 99))
    term_means = [d(safe_mean(by_term[t])) for t in terms_sorted]

    classrooms_sorted = sorted(by_classroom.keys(), key=lambda cid: -safe_mean(by_classroom[cid]))
    classroom_rows = [
        {
            "id": cid,
            "name": classroom_names[cid],
            "mean": float(d(safe_mean(by_classroom[cid]))),
        }
        for cid in classrooms_sorted
    ]

    chart_term_trend = {
        **line_chart(
            labels=[t.upper() for t in terms_sorted],
            datasets=[{"label": "School Mean (%)", "data": [float(m) for m in term_means], "color": "#2563eb"}],
        ),
        "title": f"{academic_year} — Term-over-Term Trend",
    }

    chart_classroom_bar = {
        **bar_chart(
            labels=[c["name"] for c in classroom_rows],
            datasets=[{"label": "Mean Score (%)", "data": [c["mean"] for c in classroom_rows], "color": "#16a34a"}],
        ),
        "title": f"{academic_year} — Classroom Comparison",
    }

    chart_pie = cbc_pie(all_levels, title=f"{academic_year} — Overall Grade Distribution")

    total_exams = ExamSetup.objects.filter(tenant=tenant, academic_year=academic_year).count()

    data = {
        "academic_year": academic_year,
        "mean_percentage": d(safe_mean([float(r["percentage"]) for r in rows])),
        "total_results": len(rows),
        "total_students": len({r["student_id"] for r in rows}),
        "total_exams": total_exams,
        "top_performing_class": (
            {"id": classroom_rows[0]["id"], "name": classroom_rows[0]["name"], "mean": classroom_rows[0]["mean"]}
            if classroom_rows else None
        ),
        "lowest_performing_class": (
            {"id": classroom_rows[-1]["id"], "name": classroom_rows[-1]["name"], "mean": classroom_rows[-1]["mean"]}
            if classroom_rows else None
        ),
        "terms": [
            {"term": t, "mean": m, "result_count": len(by_term[t]), "exam_count": None}
            for t, m in zip(terms_sorted, term_means)
        ],
        "classrooms": classroom_rows,
        "grade_distribution": grade_dist(all_levels),
        "charts": {
            "term_trend": chart_term_trend,
            "classroom_bar": chart_classroom_bar,
            "grade_pie": chart_pie,
        },
    }

    cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
    return data


def get_term_summary(tenant, academic_year, term):
    """
    One term's health across all classrooms: per-classroom means, and
    progression across exam types within the term (opener -> midterm ->
    endterm). Charts: bar (classroom comparison), line (progression), pie.
    1 DB query.
    """
    ck = term_summary(tenant.id, academic_year, term)
    cached = cache.get(ck)
    if cached:
        return cached

    rows = list(
        ExamResult.objects
        .filter(
            tenant=tenant,
            exam_subject__exam__academic_year=academic_year,
            exam_subject__exam__term=term,
        )
        .values(
            "student_id", "percentage", "cbc_level",
            "exam_subject__exam__exam_type",
            "exam_subject__exam__classroom_id",
            "exam_subject__exam__classroom__name",
        )
    )

    if not rows:
        raise InsufficientDataError(
            filters={"academic_year": academic_year, "term": term},
            suggestion="No exam results recorded for this term yet.",
        )

    EXAM_TYPE_ORDER = {"opener": 1, "midterm": 2, "endterm": 3, "mock": 4, "other": 5}

    by_classroom = defaultdict(list)
    by_exam_type = defaultdict(list)
    classroom_names = {}
    all_levels = []

    for r in rows:
        pct = float(r["percentage"])
        cid = r["exam_subject__exam__classroom_id"]
        etype = r["exam_subject__exam__exam_type"]
        by_classroom[cid].append(pct)
        by_exam_type[etype].append(pct)
        classroom_names[cid] = r["exam_subject__exam__classroom__name"]
        all_levels.append(r["cbc_level"])

    classrooms_sorted = sorted(by_classroom.keys(), key=lambda cid: -safe_mean(by_classroom[cid]))
    classroom_rows = [
        {
            "classroom": {"id": cid, "name": classroom_names[cid]},
            "mean_percentage": d(safe_mean(by_classroom[cid])),
        }
        for cid in classrooms_sorted
    ]

    types_sorted = sorted(by_exam_type.keys(), key=lambda t: EXAM_TYPE_ORDER.get(t, 99))

    chart_classroom_bar = {
        **bar_chart(
            labels=[classroom_names[cid] for cid in classrooms_sorted],
            datasets=[{
                "label": "Mean Score (%)",
                "data": [float(row["mean_percentage"]) for row in classroom_rows],
                "color": "#16a34a",
            }],
        ),
        "title": f"{term.upper()} {academic_year} — Classroom Comparison",
    }

    chart_type_progression = {
        **line_chart(
            labels=[t.title() for t in types_sorted],
            datasets=[{
                "label": "Mean Score (%)",
                "data": [float(d(safe_mean(by_exam_type[t]))) for t in types_sorted],
                "color": "#7c3aed",
            }],
        ),
        "title": f"{term.upper()} {academic_year} — Exam Progression",
    }

    chart_pie = cbc_pie(all_levels, title=f"{term.upper()} {academic_year} — Grade Distribution")

    data = {
        "term": term,
        "academic_year": academic_year,
        "term_mean": d(safe_mean([float(r["percentage"]) for r in rows])),
        "total_results": len(rows),
        "classrooms": classroom_rows,
        "exam_progression": [
            {"exam_type": t, "mean_percentage": d(safe_mean(by_exam_type[t]))}
            for t in types_sorted
        ],
        "grade_distribution": grade_dist(all_levels),
        "charts": {
            "classroom_bar": chart_classroom_bar,
            "exam_progression": chart_type_progression,
            "grade_pie": chart_pie,
        },
    }

    cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
    return data


def get_school_classrooms(tenant, academic_year, term):
    """
    All classrooms for a tenant/year/term, with performance metrics.
    Groups by grade_level, with individual stream breakdown.

    Returns every active classroom (even those without exam data) so
    admins see the full picture of what is set up vs what has results.
    """
    ck = school_classrooms(tenant.id, academic_year, term)
    cached = cache.get(ck)
    if cached:
        return cached

    # ── 1. All active classrooms for this tenant/year ──────────────────
    classrooms = list(
        Classroom.objects.filter(
            tenant=tenant,
            academic_year=str(academic_year),
            is_active=True,
        ).order_by("grade_level", "stream")
    )

    # ── 2. Exam results for this term ──────────────────────────────────
    result_rows = list(
        ExamResult.objects
        .filter(
            tenant=tenant,
            exam_subject__exam__academic_year=academic_year,
            exam_subject__exam__term=term,
        )
        .values(
            "student_id", "percentage", "cbc_level",
            "exam_subject__exam__classroom_id",
        )
    )

    # ── 3. Per-classroom metrics ───────────────────────────────────────
    by_classroom = defaultdict(list)
    for r in result_rows:
        cid = r["exam_subject__exam__classroom_id"]
        by_classroom[cid].append(r)

    config = ExamConfig.get_for_tenant(tenant)
    metrics = {}
    for cid, rows in by_classroom.items():
        pcts = [float(r["percentage"]) for r in rows]
        levels = [r["cbc_level"] for r in rows]
        mean_pct = safe_mean(pcts)
        metrics[cid] = {
            "mean_percentage": d(mean_pct),
            "cbc_level": compute_level(config, mean_pct),
            "student_count": len({r["student_id"] for r in rows}),
            "result_count": len(rows),
            "grade_distribution": grade_dist(levels),
        }

    # ── 4. Rank classrooms by mean ─────────────────────────────────────
    ranked = sorted(
        [(cid, float(m["mean_percentage"])) for cid, m in metrics.items()],
        key=lambda x: x[1],
        reverse=True,
    )
    for rank, (cid, _) in enumerate(ranked, 1):
        metrics[cid]["rank"] = rank

    # ── 5. Build classroom objects ─────────────────────────────────────
    classroom_data = []
    for cls in classrooms:
        cid = cls.id
        m = metrics.get(cid, {})
        has_data = cid in metrics
        classroom_data.append({
            "id": cid,
            "name": str(cls),
            "grade_level": cls.grade_level,
            "stream": cls.stream or None,
            "student_count": m.get("student_count", cls.student_count),
            "mean_percentage": m.get("mean_percentage"),
            "cbc_level": m.get("cbc_level"),
            "rank": m.get("rank"),
            "has_data": has_data,
            "grade_distribution": m.get("grade_distribution") if has_data else None,
        })

    # ── 6. Group by grade_level ────────────────────────────────────────
    by_grade = defaultdict(list)
    for c in classroom_data:
        by_grade[c["grade_level"]].append(c)

    grade_levels = []
    for grade_level in sorted(by_grade.keys(), key=_natural_sort_key):
        streams = by_grade[grade_level]
        streams_with_data = [s for s in streams if s["has_data"]]

        if streams_with_data:
            grade_mean = safe_mean([float(s["mean_percentage"]) for s in streams_with_data])
            grade_students = sum(s["student_count"] for s in streams)
            grade_level_val = compute_level(config, grade_mean)
        else:
            grade_mean = None
            grade_students = sum(s["student_count"] for s in streams)
            grade_level_val = None

        grade_levels.append({
            "grade_level": grade_level,
            "classrooms": streams,
            "aggregate": {
                "mean_percentage": d(grade_mean) if grade_mean is not None else None,
                "student_count": grade_students,
                "cbc_level": grade_level_val,
                "classroom_count": len(streams),
                "with_data_count": len(streams_with_data),
            },
        })

    # ── 7. Flat ranked list (only classrooms with data) ────────────────
    all_classrooms = sorted(
        [c for c in classroom_data if c["has_data"]],
        key=lambda c: c["rank"] or 999,
    )

    # ── 8. School-wide mean ────────────────────────────────────────────
    school_mean = (
        safe_mean([
            float(c["mean_percentage"])
            for c in classroom_data
            if c["has_data"]
        ])
        if any(c["has_data"] for c in classroom_data)
        else None
    )

    data = {
        "academic_year": academic_year,
        "term": term,
        "grade_levels": grade_levels,
        "all_classrooms": all_classrooms,
        "total_classrooms": len(classrooms),
        "total_students": sum(c["student_count"] for c in classroom_data),
        "classrooms_with_data": len([c for c in classroom_data if c["has_data"]]),
        "school_mean": d(school_mean) if school_mean is not None else None,
    }

    cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
    return data