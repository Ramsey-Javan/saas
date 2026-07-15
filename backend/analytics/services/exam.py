"""Exam-level analytics: breakdown, rankings, subject analysis."""
from collections import defaultdict
from decimal import Decimal

from django.core.cache import cache

from academics.models import ExamConfig, ExamResult, ExamSetup, ExamSubject
from students.models import Student

from .cache_keys import (
    CACHE_TTL_SUMMARY, exam_breakdown, exam_rankings, subject_analysis,
)
from ._helpers import (
    d, safe_mean, safe_median, safe_stdev,
    grade_dist, bar_chart, line_chart, pct_bar_chart, cbc_pie,
    CBC_COLORS, CBC_LABELS, PALETTE, ttl, compute_level,
)
from .exceptions import InsufficientDataError, InvalidFilterError


def _get_exam(tenant, exam_id):
    try:
        return ExamSetup.objects.select_related("classroom").get(
            tenant=tenant, id=exam_id
        )
    except ExamSetup.DoesNotExist:
        raise InsufficientDataError(
            filters={"exam_id": exam_id},
            suggestion="Exam not found.",
        )


def get_exam_breakdown(tenant, exam_id):
    """
    Per-subject performance for one exam.
    Charts: bar (subject means), bar (grade dist per subject), pie (overall dist).
    2 DB queries.
    """
    ck = exam_breakdown(tenant.id, exam_id)
    cached = cache.get(ck)
    if cached:
        return cached

    exam = _get_exam(tenant, exam_id)

    # Q1 — all results for this exam
    rows = list(
        ExamResult.objects
        .filter(tenant=tenant, exam_subject__exam=exam)
        .values(
            "student_id", "marks", "percentage", "cbc_level",
            "exam_subject_id",
            "exam_subject__subject__id",
            "exam_subject__subject__name",
            "exam_subject__total_marks",
            "exam_subject__teacher__first_name",
            "exam_subject__teacher__last_name",
        )
    )

    if not rows:
        raise InsufficientDataError(
            filters={"exam": exam.name},
            suggestion="No results entered for this exam.",
        )

    # Group by subject
    by_subj = defaultdict(list)
    subj_meta = {}
    for r in rows:
        esid = r["exam_subject_id"]
        by_subj[esid].append(r)
        if esid not in subj_meta:
            fn = r["exam_subject__teacher__first_name"] or ""
            ln = r["exam_subject__teacher__last_name"] or ""
            subj_meta[esid] = {
                "id": r["exam_subject__subject__id"],
                "name": r["exam_subject__subject__name"],
                "total_marks": r["exam_subject__total_marks"],
                "teacher": (fn + " " + ln).strip() or "Unassigned",
            }

    subjects = []
    for esid, es_rows in by_subj.items():
        pcts = [float(r["percentage"]) for r in es_rows]
        marks = [float(r["marks"]) for r in es_rows]
        levels = [r["cbc_level"] for r in es_rows]
        passing = sum(1 for lv in levels if lv in ("ME", "EE"))
        subjects.append({
            "subject": subj_meta[esid],
            "mean_marks": d(safe_mean(marks)),
            "mean_percentage": d(safe_mean(pcts)),
            "highest": d(max(marks)),
            "lowest": d(min(marks)),
            "std_deviation": d(safe_stdev(pcts)),
            "pass_rate": d((passing / len(levels)) * 100) if levels else Decimal("0.00"),
            "student_count": len(es_rows),
            "grade_distribution": grade_dist(levels),
        })

    subjects.sort(key=lambda x: x["mean_percentage"], reverse=True)

    all_pcts = [float(r["percentage"]) for r in rows]
    all_levels = [r["cbc_level"] for r in rows]
    total_students = len({r["student_id"] for r in rows})

    # Charts
    subj_names = [s["subject"]["name"] for s in subjects]
    subj_means = [float(s["mean_percentage"]) for s in subjects]

    chart_subj_bar = {
        **bar_chart(
            labels=subj_names,
            datasets=[{"label": "Mean Score (%)", "data": subj_means, "color": "#2563eb"}]
        ),
        "title": f"{exam.name} — Subject Performance",
    }

    # Stacked grade dist per subject
    chart_grade_stacked = {
        "type": "bar_stacked",
        "title": f"{exam.name} — Grade Distribution by Subject",
        "labels": subj_names,
        "datasets": [
            {
                "label": CBC_LABELS[lv],
                "data": [s["grade_distribution"]["counts"][lv] for s in subjects],
                "color": CBC_COLORS[lv],
            }
            for lv in ("EE", "ME", "AE", "BE")
        ],
    }

    chart_pie = cbc_pie(all_levels, title=f"{exam.name} — Overall Grade Distribution")

    data = {
        "exam": {
            "id": exam.id,
            "name": exam.name,
            "exam_type": exam.exam_type,
            "term": exam.term,
            "academic_year": exam.academic_year,
            "classroom": {"id": exam.classroom.id, "name": exam.classroom.name},
            "start_date": str(exam.start_date),
            "end_date": str(exam.end_date),
        },
        "total_students": total_students,
        "exam_mean": d(safe_mean(all_pcts)),
        "exam_median": d(safe_median(all_pcts)),
        "std_deviation": d(safe_stdev(all_pcts)),
        "grade_distribution": grade_dist(all_levels),
        "subjects": subjects,
        "charts": {
            "subject_bar": chart_subj_bar,
            "grade_stacked": chart_grade_stacked,
            "grade_pie": chart_pie,
        },
    }

    cache.set(ck, data, timeout=ttl(exam.term, exam.academic_year))
    return data


def get_class_rankings(tenant, exam_id):
    """
    Student rankings for one exam — top/bottom/biggest move.
    Charts: bar (top 10), bar (bottom 10).
    2 DB queries.
    """
    ck = exam_rankings(tenant.id, exam_id)
    cached = cache.get(ck)
    if cached:
        return cached

    exam = _get_exam(tenant, exam_id)
    config = ExamConfig.get_for_tenant(tenant)

    # Q1 — all results
    rows = list(
        ExamResult.objects
        .filter(tenant=tenant, exam_subject__exam=exam)
        .values(
            "student_id", "percentage", "cbc_level",
            "student__first_name", "student__last_name",
            "student__admission_number",
        )
    )

    if not rows:
        raise InsufficientDataError(filters={"exam_id": exam_id})

    # Per-student mean
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
        key=lambda x: x["mean_percentage"], reverse=True
    )

    for i, r in enumerate(rankings, 1):
        r["rank"] = i

    class_size = len(rankings)
    top10 = rankings[:10]
    bottom10 = list(reversed(rankings[-10:]))

    # Charts
    chart_top = {
        **bar_chart(
            labels=[r["student"]["name"] for r in top10],
            datasets=[{
                "label": "Score (%)",
                "data": [float(r["mean_percentage"]) for r in top10],
                "color": "#16a34a",
            }]
        ),
        "title": f"Top 10 — {exam.name}",
    }

    chart_bottom = {
        **bar_chart(
            labels=[r["student"]["name"] for r in bottom10],
            datasets=[{
                "label": "Score (%)",
                "data": [float(r["mean_percentage"]) for r in bottom10],
                "color": "#dc2626",
            }]
        ),
        "title": f"Bottom 10 — {exam.name}",
    }

    data = {
        "exam": {"id": exam.id, "name": exam.name,
                 "classroom": {"id": exam.classroom.id, "name": exam.classroom.name}},
        "class_size": class_size,
        "class_mean": d(safe_mean([float(r["mean_percentage"]) for r in rankings])),
        "rankings": rankings,
        "top_10": top10,
        "bottom_10": bottom10,
        "charts": {
            "top_bar": chart_top,
            "bottom_bar": chart_bottom,
        },
    }

    cache.set(ck, data, timeout=ttl(exam.term, exam.academic_year))
    return data


def get_subject_analysis(tenant, exam_id, subject_id=None):
    """
    Deep dive into one (or all) subjects for an exam.
    Charts: histogram of scores, bar comparing students to class avg.
    2 DB queries.
    """
    ck = subject_analysis(tenant.id, exam_id, subject_id)
    cached = cache.get(ck)
    if cached:
        return cached

    exam = _get_exam(tenant, exam_id)

    qs = ExamResult.objects.filter(tenant=tenant, exam_subject__exam=exam)
    if subject_id:
        qs = qs.filter(exam_subject__subject_id=subject_id)

    rows = list(
        qs.values(
            "student_id", "marks", "percentage", "cbc_level",
            "exam_subject__subject__id",
            "exam_subject__subject__name",
            "exam_subject__total_marks",
            "student__first_name", "student__last_name",
            "student__admission_number",
        )
    )

    if not rows:
        raise InsufficientDataError(filters={"exam_id": exam_id, "subject_id": subject_id})

    by_subj = defaultdict(list)
    subj_names = {}
    for r in rows:
        sid = r["exam_subject__subject__id"]
        by_subj[sid].append(r)
        subj_names[sid] = r["exam_subject__subject__name"]

    subjects_out = []
    for sid, subj_rows in by_subj.items():
        pcts = [float(r["percentage"]) for r in subj_rows]
        marks_list = [float(r["marks"]) for r in subj_rows]
        levels = [r["cbc_level"] for r in subj_rows]
        class_mean = safe_mean(pcts)
        total_marks = subj_rows[0]["exam_subject__total_marks"]

        # Per-student breakdown
        students_data = sorted(
            [
                {
                    "student": {
                        "id": r["student_id"],
                        "name": f"{r['student__first_name']} {r['student__last_name']}".strip(),
                        "admission_number": r["student__admission_number"] or "",
                    },
                    "marks": d(r["marks"]),
                    "percentage": d(r["percentage"]),
                    "cbc_level": r["cbc_level"],
                    "vs_class_avg": d(float(r["percentage"]) - class_mean),
                }
                for r in subj_rows
            ],
            key=lambda x: x["percentage"], reverse=True
        )

        # Score histogram (10 buckets)
        bucket_size = total_marks / 10 if total_marks else 10
        hist_labels = [f"{int(i*bucket_size)}-{int((i+1)*bucket_size)}" for i in range(10)]
        hist_counts = [0] * 10
        for m in marks_list:
            idx = min(int(m / bucket_size), 9) if bucket_size else 0
            hist_counts[idx] += 1

        chart_hist = {
            **bar_chart(
                labels=hist_labels,
                datasets=[{"label": "Students", "data": hist_counts, "color": "#7c3aed"}]
            ),
            "title": f"{subj_names[sid]} — Score Distribution",
        }

        # Students vs class average
        student_names = [s["student"]["name"] for s in students_data[:20]]
        student_pcts = [float(s["percentage"]) for s in students_data[:20]]
        chart_vs_avg = {
            "type": "mixed",
            "title": f"{subj_names[sid]} — Students vs Class Average",
            "labels": student_names,
            "datasets": [
                {"label": "Student Score", "data": student_pcts, "type": "bar", "color": "#2563eb"},
                {"label": "Class Average", "data": [float(d(class_mean))] * len(student_names),
                 "type": "line", "color": "#dc2626"},
            ],
        }

        subjects_out.append({
            "subject": {"id": sid, "name": subj_names[sid]},
            "total_marks": total_marks,
            "mean_marks": d(safe_mean(marks_list)),
            "mean_percentage": d(class_mean),
            "highest": d(max(marks_list)),
            "lowest": d(min(marks_list)),
            "std_deviation": d(safe_stdev(pcts)),
            "pass_rate": d((sum(1 for lv in levels if lv in ("ME","EE")) / len(levels)) * 100),
            "grade_distribution": grade_dist(levels),
            "students": students_data,
            "charts": {
                "histogram": chart_hist,
                "vs_average": chart_vs_avg,
                "grade_pie": {
                    **cbc_pie(levels),
                    "title": f"{subj_names[sid]} — Grade Distribution",
                },
            },
        })

    subjects_out.sort(key=lambda x: x["mean_percentage"], reverse=True)

    data = {
        "exam": {"id": exam.id, "name": exam.name,
                 "classroom": {"id": exam.classroom.id, "name": exam.classroom.name}},
        "subjects": subjects_out,
    }

    cache.set(ck, data, timeout=ttl(exam.term, exam.academic_year))
    return data
