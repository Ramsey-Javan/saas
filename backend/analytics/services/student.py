"""Student-level analytics.

Two generations of function live here:
- get_student_profile / get_student_report_card: the original exam-scoped
  versions from the first pass. Not used by the current frontend, kept
  in case a future "drill into one specific exam for this student" view
  wants them -- harmless to leave in place.
- get_student_performance / get_student_longitudinal: what the actual
  frontend (StudentProfilePage) needs -- term-scoped and year-scoped
  (bucketed by TERM, not by exam), with trend/velocity classification
  reusing tracker.py's trajectory logic so "improving" means the exact
  same thing here as it does in the Improvement Tracker.
"""
from collections import defaultdict

from django.core.cache import cache

from academics.models import ExamResult, ExamConfig

from .cache_keys import (
    CACHE_TTL_SUMMARY, student_profile, student_report_card,
    student_performance, student_longitudinal,
)
from ._helpers import d, safe_mean, grade_dist, line_chart, PALETTE, TERM_ORDER, compute_level
from .tracker import _classify_trajectory
from .exceptions import InsufficientDataError


def get_student_profile(tenant, student, academic_year):
    """
    One student's full-year journey, bucketed by EXAM (not term).
    Charts: line (overall trend across exams), line (per-subject trend).
    1 DB query. Not currently used by the frontend -- see module docstring.
    """
    ck = student_profile(tenant.id, student.id, academic_year)
    cached = cache.get(ck)
    if cached:
        return cached

    rows = list(
        ExamResult.objects
        .filter(tenant=tenant, student=student, exam_subject__exam__academic_year=academic_year)
        .values(
            "percentage", "cbc_level",
            "exam_subject__exam__id", "exam_subject__exam__name",
            "exam_subject__exam__term", "exam_subject__exam__start_date",
            "exam_subject__subject__id", "exam_subject__subject__name",
        )
    )

    if not rows:
        raise InsufficientDataError(
            filters={"student_id": student.id, "academic_year": academic_year},
            suggestion="No exam results recorded for this student this year.",
        )

    by_exam = defaultdict(list)
    exam_meta = {}
    by_subject = defaultdict(list)
    subject_names = {}
    all_levels = []

    for r in rows:
        eid = r["exam_subject__exam__id"]
        pct = float(r["percentage"])
        by_exam[eid].append(pct)
        if eid not in exam_meta:
            exam_meta[eid] = {
                "id": eid,
                "name": r["exam_subject__exam__name"],
                "term": r["exam_subject__exam__term"],
                "start_date": str(r["exam_subject__exam__start_date"]),
            }
        sid = r["exam_subject__subject__id"]
        by_subject[sid].append({"exam_id": eid, "percentage": pct})
        subject_names[sid] = r["exam_subject__subject__name"]
        all_levels.append(r["cbc_level"])

    exams_sorted = sorted(exam_meta.values(), key=lambda e: (TERM_ORDER.get(e["term"], 99), e["start_date"]))
    exam_trend = [
        {**e, "mean_percentage": d(safe_mean(by_exam[e["id"]]))}
        for e in exams_sorted
    ]

    chart_overall_trend = {
        **line_chart(
            labels=[e["name"] for e in exam_trend],
            datasets=[{
                "label": student.get_full_name(),
                "data": [float(e["mean_percentage"]) for e in exam_trend],
                "color": "#2563eb",
            }],
        ),
        "title": f"{student.get_full_name()} — Overall Trend {academic_year}",
    }

    subject_trends = []
    subject_trend_datasets = []
    for i, (sid, entries) in enumerate(by_subject.items()):
        by_exam_for_subject = defaultdict(list)
        for e in entries:
            by_exam_for_subject[e["exam_id"]].append(e["percentage"])
        series = [
            d(safe_mean(by_exam_for_subject[exam["id"]])) if exam["id"] in by_exam_for_subject else None
            for exam in exam_trend
        ]
        subject_trends.append({"subject": {"id": sid, "name": subject_names[sid]}, "series": series})
        subject_trend_datasets.append({
            "label": subject_names[sid],
            "data": [float(v) if v is not None else None for v in series],
            "color": PALETTE[i % len(PALETTE)],
        })

    chart_subject_trend = {
        **line_chart(labels=[e["name"] for e in exam_trend], datasets=subject_trend_datasets),
        "title": f"{student.get_full_name()} — Subject Trends {academic_year}",
    }

    data = {
        "student": {
            "id": student.id,
            "name": student.get_full_name(),
            "admission_number": student.admission_number,
            "classroom": str(student.classroom) if student.classroom else None,
        },
        "academic_year": academic_year,
        "overall_mean": d(safe_mean([float(r["percentage"]) for r in rows])),
        "exam_trend": exam_trend,
        "subject_trends": subject_trends,
        "grade_distribution": grade_dist(all_levels),
        "charts": {
            "overall_trend": chart_overall_trend,
            "subject_trend": chart_subject_trend,
        },
    }

    cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
    return data


def get_student_report_card(tenant, student, term, academic_year):
    """
    One term, all subjects, with class rank -- exam-grouped-under-subject
    shape. Not currently used by the frontend -- see module docstring.
    2 DB queries.
    """
    ck = student_report_card(tenant.id, student.id, term, academic_year)
    cached = cache.get(ck)
    if cached:
        return cached

    rows = list(
        ExamResult.objects
        .filter(
            tenant=tenant, student=student,
            exam_subject__exam__term=term,
            exam_subject__exam__academic_year=academic_year,
        )
        .values(
            "marks", "percentage", "cbc_level", "is_overridden",
            "exam_subject__exam__name", "exam_subject__exam__exam_type",
            "exam_subject__subject__id", "exam_subject__subject__name",
            "exam_subject__total_marks",
        )
    )

    if not rows:
        raise InsufficientDataError(
            filters={"student_id": student.id, "term": term, "academic_year": academic_year},
            suggestion="No exam results recorded for this student this term.",
        )

    by_subject = defaultdict(list)
    subject_names = {}
    for r in rows:
        sid = r["exam_subject__subject__id"]
        by_subject[sid].append(r)
        subject_names[sid] = r["exam_subject__subject__name"]

    subjects_out = []
    for sid, subj_rows in by_subject.items():
        pcts = [float(r["percentage"]) for r in subj_rows]
        subjects_out.append({
            "subject": {"id": sid, "name": subject_names[sid]},
            "term_mean_percentage": d(safe_mean(pcts)),
            "exams": [
                {
                    "exam_name": r["exam_subject__exam__name"],
                    "exam_type": r["exam_subject__exam__exam_type"],
                    "marks": d(r["marks"]),
                    "total_marks": r["exam_subject__total_marks"],
                    "percentage": d(r["percentage"]),
                    "cbc_level": r["cbc_level"],
                    "is_overridden": r["is_overridden"],
                }
                for r in subj_rows
            ],
        })
    subjects_out.sort(key=lambda x: x["term_mean_percentage"], reverse=True)

    classroom = student.classroom
    rank = None
    class_size = None
    if classroom:
        classmate_rows = list(
            ExamResult.objects
            .filter(
                tenant=tenant,
                student__classroom=classroom,
                exam_subject__exam__term=term,
                exam_subject__exam__academic_year=academic_year,
            )
            .values("student_id", "percentage")
        )
        by_student = defaultdict(list)
        for r in classmate_rows:
            by_student[r["student_id"]].append(float(r["percentage"]))
        student_means = sorted(
            [(sid, safe_mean(pcts)) for sid, pcts in by_student.items()],
            key=lambda x: x[1], reverse=True,
        )
        class_size = len(student_means)
        for i, (sid, _) in enumerate(student_means, 1):
            if sid == student.id:
                rank = i
                break

    all_pcts = [float(r["percentage"]) for r in rows]

    chart_subject_bar = {
        "type": "bar",
        "title": f"{student.get_full_name()} — {term.upper()} {academic_year}",
        "labels": [s["subject"]["name"] for s in subjects_out],
        "datasets": [{
            "label": "Score (%)",
            "data": [float(s["term_mean_percentage"]) for s in subjects_out],
            "color": "#2563eb",
        }],
    }

    data = {
        "student": {
            "id": student.id,
            "name": student.get_full_name(),
            "admission_number": student.admission_number,
        },
        "term": term,
        "academic_year": academic_year,
        "term_mean": d(safe_mean(all_pcts)),
        "rank": rank,
        "class_size": class_size,
        "subjects": subjects_out,
        "charts": {"subject_bar": chart_subject_bar},
    }

    cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
    return data


def get_student_performance(tenant, student, term, academic_year):
    """
    One student's ONE TERM, flattened to one row per SUBJECT (not per exam).
    Each row shows the mean percentage across all exams in that term for
    that subject, plus a breakdown of individual exam results.

    Class average and rank_in_subject are computed from the aggregated
    subject means so that a student with one exam and a student with five
    exams in the same term are compared fairly.

    2 DB queries: this student's own results, then every classmate's
    results this term.
    """
    ck = student_performance(tenant.id, student.id, term, academic_year)
    cached = cache.get(ck)
    if cached:
        return cached

    own_rows = list(
        ExamResult.objects
        .filter(
            tenant=tenant, student=student,
            exam_subject__exam__term=term,
            exam_subject__exam__academic_year=academic_year,
        )
        .values(
            "marks", "percentage", "cbc_level",
            "exam_subject__exam__id", "exam_subject__exam__name",
            "exam_subject__exam__exam_type",
            "exam_subject__subject__id", "exam_subject__subject__name",
            "exam_subject__subject__code", "exam_subject__total_marks",
        )
    )

    classroom = student.classroom

    # Graceful empty response instead of a 400 when no grades exist for this term.
    if not own_rows:
        data = {
            "student": {
                "id": student.id,
                "name": student.get_full_name(),
                "admission_number": student.admission_number,
            },
            "classroom": {"id": classroom.id, "name": classroom.name} if classroom else None,
            "term": term,
            "academic_year": academic_year,
            "overall_mean": None,
            "class_rank": None,
            "class_size": None,
            "percentile": None,
            "subjects": [],
        }
        cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
        return data

    # ── Aggregate own results by subject ─────────────────────────────────
    # Group raw ExamResults by subject, then compute mean percentage per subject.
    own_by_subject = defaultdict(list)
    own_exams_by_subject = defaultdict(list)
    subject_meta = {}

    for r in own_rows:
        sid = r["exam_subject__subject__id"]
        own_by_subject[sid].append(float(r["percentage"]))
        own_exams_by_subject[sid].append({
            "exam_id": r["exam_subject__exam__id"],
            "exam_name": r["exam_subject__exam__name"],
            "exam_type": r["exam_subject__exam__exam_type"],
            "marks": d(r["marks"]),
            "total_marks": r["exam_subject__total_marks"],
            "percentage": d(r["percentage"]),
            "cbc_level": r["cbc_level"],
        })
        if sid not in subject_meta:
            subject_meta[sid] = {
                "id": sid,
                "name": r["exam_subject__subject__name"],
                "code": r["exam_subject__subject__code"],
            }

    # Compute aggregated subject means for this student
    own_subject_means = {
        sid: safe_mean(pcts) for sid, pcts in own_by_subject.items()
    }

    # ── Fetch classmates for ranking ─────────────────────────────────────
    classmate_rows = []
    if classroom:
        classmate_rows = list(
            ExamResult.objects
            .filter(
                tenant=tenant, student__classroom=classroom,
                exam_subject__exam__term=term,
                exam_subject__exam__academic_year=academic_year,
            )
            .values("student_id", "percentage", "exam_subject__subject__id")
        )

    # ── Overall class rank/size/percentile ───────────────────────────────
    # Use the student's own aggregated mean (mean of subject means) for
    # overall ranking so that exam-count differences don't skew rank.
    overall_by_student = defaultdict(list)
    for r in classmate_rows:
        overall_by_student[r["student_id"]].append(float(r["percentage"]))
    overall_ranked = sorted(
        [(sid, safe_mean(pcts)) for sid, pcts in overall_by_student.items()],
        key=lambda x: x[1], reverse=True,
    )
    class_size = len(overall_ranked)
    class_rank = None
    for i, (sid, _) in enumerate(overall_ranked, 1):
        if sid == student.id:
            class_rank = i
            break
    percentile = (
        round(((class_size - class_rank) / class_size) * 100, 1)
        if class_rank and class_size else None
    )

    # ── Per-subject class average + rank_in_subject ──────────────────────
    # Aggregate classmates by subject (mean of their percentages per subject)
    by_subject_student = defaultdict(lambda: defaultdict(list))
    for r in classmate_rows:
        by_subject_student[r["exam_subject__subject__id"]][r["student_id"]].append(float(r["percentage"]))

    subject_rank_lookup = {}
    subject_class_avg = {}
    for sid, student_map in by_subject_student.items():
        # Mean per student for this subject, then overall class mean
        student_means = {stid: safe_mean(pcts) for stid, pcts in student_map.items()}
        ranked = sorted(student_means.items(), key=lambda x: x[1], reverse=True)
        subject_rank_lookup[sid] = {stid: (i, mean) for i, (stid, mean) in enumerate(ranked, 1)}
        subject_class_avg[sid] = safe_mean(student_means.values())

    # ── Build output: one row per subject ────────────────────────────────
    config = ExamConfig.get_for_tenant(tenant)
    subjects_out = []
    for sid in sorted(own_subject_means.keys(), key=lambda k: own_subject_means[k], reverse=True):
        mean_pct = own_subject_means[sid]
        rank_info = subject_rank_lookup.get(sid, {}).get(student.id)
        rank_in_subject, _ = rank_info if rank_info else (None, None)
        class_avg = subject_class_avg.get(sid)

        # Determine CBC level from the aggregated mean
        agg_level = compute_level(config, mean_pct)

        subjects_out.append({
            "subject": subject_meta[sid],
            "term_mean_percentage": d(mean_pct),
            "cbc_level": agg_level,
            "class_average": d(class_avg) if class_avg is not None else None,
            "rank_in_subject": rank_in_subject,
            "exams": sorted(
                own_exams_by_subject[sid],
                key=lambda e: e["percentage"],
                reverse=True,
            ),
        })

    data = {
        "student": {
            "id": student.id,
            "name": student.get_full_name(),
            "admission_number": student.admission_number,
        },
        "classroom": {"id": classroom.id, "name": classroom.name} if classroom else None,
        "term": term,
        "academic_year": academic_year,
        "overall_mean": d(safe_mean(own_subject_means.values())),
        "class_rank": class_rank,
        "class_size": class_size,
        "percentile": percentile,
        "subjects": subjects_out,
    }

    cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
    return data


def get_student_longitudinal(tenant, student, academic_year):
    """
    One student's full YEAR, bucketed by TERM (not exam): each term's
    mean, class rank, per-subject breakdown, plus an overall trend
    ("improving"/"declining"/"stable"/"mixed") and velocity -- reusing
    tracker.py's EXACT trajectory classification, so "improving" here
    means the same thing it means in the Improvement Tracker.
    2 DB queries: this student's own year of results, then every
    classmate's year of results (for per-term ranking).
    """
    ck = student_longitudinal(tenant.id, student.id, academic_year)
    cached = cache.get(ck)
    if cached:
        return cached

    own_rows = list(
        ExamResult.objects
        .filter(tenant=tenant, student=student, exam_subject__exam__academic_year=academic_year)
        .values(
            "percentage",
            "exam_subject__exam__term",
            "exam_subject__subject__id", "exam_subject__subject__name",
        )
    )

    if not own_rows:
        raise InsufficientDataError(
            filters={"student_id": student.id, "academic_year": academic_year},
            suggestion="No exam results recorded for this student this year.",
        )

    classroom = student.classroom
    classmate_rows = []
    if classroom:
        classmate_rows = list(
            ExamResult.objects
            .filter(tenant=tenant, student__classroom=classroom, exam_subject__exam__academic_year=academic_year)
            .values("student_id", "percentage", "exam_subject__exam__term")
        )

    own_by_term = defaultdict(list)
    own_subject_by_term = defaultdict(lambda: defaultdict(list))
    subject_names = {}
    for r in own_rows:
        term = r["exam_subject__exam__term"]
        pct = float(r["percentage"])
        own_by_term[term].append(pct)
        sid = r["exam_subject__subject__id"]
        own_subject_by_term[term][sid].append(pct)
        subject_names[sid] = r["exam_subject__subject__name"]

    classmates_by_term = defaultdict(lambda: defaultdict(list))
    for r in classmate_rows:
        term = r["exam_subject__exam__term"]
        classmates_by_term[term][r["student_id"]].append(float(r["percentage"]))

    config = ExamConfig.get_for_tenant(tenant)

    terms_out = []
    term_means_sequence = []
    for term_key in ("term1", "term2", "term3"):
        if term_key not in own_by_term:
            terms_out.append({"term": term_key, "has_data": False})
            continue

        mean_pct = safe_mean(own_by_term[term_key])
        term_means_sequence.append(mean_pct)

        overall_ranked = sorted(
            [(sid, safe_mean(pcts)) for sid, pcts in classmates_by_term.get(term_key, {}).items()],
            key=lambda x: x[1], reverse=True,
        )
        class_size = len(overall_ranked)
        class_rank = None
        for i, (sid, _) in enumerate(overall_ranked, 1):
            if sid == student.id:
                class_rank = i
                break

        subjects_this_term = sorted(
            [
                {"subject": {"id": sid, "name": subject_names[sid]}, "percentage": d(safe_mean(pcts))}
                for sid, pcts in own_subject_by_term[term_key].items()
            ],
            key=lambda x: float(x["percentage"]), reverse=True,
        )

        terms_out.append({
            "term": term_key,
            "has_data": True,
            "mean_percentage": d(mean_pct),
            "class_rank": class_rank,
            "class_size": class_size,
            "overall_cbc_level": compute_level(config, mean_pct),
            "subjects": subjects_this_term,
        })

    trajectory, slope = _classify_trajectory(term_means_sequence)
    trend_label = {
        "rising": "improving",
        "declining": "declining",
        "stable": "stable",
        "inconsistent": "mixed",
        "insufficient_data": "stable",
    }[trajectory]

    data = {
        "student": {"id": student.id, "name": student.get_full_name()},
        "academic_year": academic_year,
        "trend": trend_label,
        "velocity": slope,
        "terms": terms_out,
    }

    cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
    return data