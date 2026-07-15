"""Improvement Tracker: classify each student's trajectory across the
exams and terms of an academic year, and surface highlights (biggest
improvers, most declined, consistent top/bottom performers, students
needing attention).

Lens B (Student) rolled up to Lens B-for-a-Class, Level 4 (Year).
"""
import statistics
from collections import defaultdict

from django.core.cache import cache

from academics.models import ExamResult
from students.models import Student

from .cache_keys import CACHE_TTL_SUMMARY, improvement_tracker
from ._helpers import d, safe_mean, TERM_ORDER
from .exceptions import InsufficientDataError

# Thresholds for trajectory classification -- tunable. A student needs at
# least 2 exams with results before any trajectory can be meaningfully
# assigned (a single data point has no slope).
RISING_SLOPE_THRESHOLD = 2.0          # mean % gained per exam, on average
DECLINING_SLOPE_THRESHOLD = -2.0
INCONSISTENT_STDEV_THRESHOLD = 10.0   # scatter around a near-flat trend


def _linear_trend_slope(values):
    """
    Simple linear regression slope over evenly-spaced points (x = 0,1,2...).
    No numpy dependency -- these series are always short.
    """
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    return numerator / denominator if denominator else 0.0


def _classify_trajectory(values):
    """
    Returns (trajectory, slope). Exposed (not underscored away entirely)
    so warning.py can reuse the exact same classification logic --
    Early Warning's "declining trend" signal must mean the same thing as
    the Improvement Tracker's "declining" bucket, not a second, subtly
    different definition.
    """
    if len(values) < 2:
        return "insufficient_data", 0.0
    slope = _linear_trend_slope(values)
    scatter = statistics.pstdev(values) if len(values) > 1 else 0.0
    # A near-flat slope with high scatter means the student is bouncing
    # around rather than steadily improving/declining/plateauing --
    # that's "inconsistent", distinct from a genuine stable plateau.
    if abs(slope) < RISING_SLOPE_THRESHOLD and scatter > INCONSISTENT_STDEV_THRESHOLD:
        return "inconsistent", round(slope, 2)
    if slope >= RISING_SLOPE_THRESHOLD:
        return "rising", round(slope, 2)
    if slope <= DECLINING_SLOPE_THRESHOLD:
        return "declining", round(slope, 2)
    return "stable", round(slope, 2)


def get_improvement_tracker(tenant, classroom, academic_year):
    """
    Per-student trajectory classification for one classroom across one
    academic year, plus highlight groups.
    Charts: none at the top level (this is a table/highlights view) --
    individual student trend charts are available via student-profile.
    2 DB queries: bulk ExamResult fetch, then a light Student name lookup.
    """
    ck = improvement_tracker(tenant.id, classroom.id, academic_year)
    cached = cache.get(ck)
    if cached:
        return cached

    rows = list(
        ExamResult.objects
        .filter(
            tenant=tenant,
            student__classroom=classroom,
            exam_subject__exam__academic_year=academic_year,
        )
        .values(
            "student_id", "percentage",
            "exam_subject__exam__id", "exam_subject__exam__name",
            "exam_subject__exam__term", "exam_subject__exam__start_date",
        )
    )

    if not rows:
        raise InsufficientDataError(
            filters={"classroom_id": classroom.id, "academic_year": academic_year},
            suggestion="No exam results recorded for this classroom this year.",
        )

    student_exam_pcts = defaultdict(lambda: defaultdict(list))
    exam_meta = {}

    for r in rows:
        sid = r["student_id"]
        eid = r["exam_subject__exam__id"]
        student_exam_pcts[sid][eid].append(float(r["percentage"]))
        if eid not in exam_meta:
            exam_meta[eid] = {
                "id": eid,
                "name": r["exam_subject__exam__name"],
                "term": r["exam_subject__exam__term"],
                "start_date": str(r["exam_subject__exam__start_date"]),
            }

    exam_order = sorted(exam_meta.values(), key=lambda e: (TERM_ORDER.get(e["term"], 99), e["start_date"]))

    students = Student.objects.filter(id__in=student_exam_pcts.keys(), tenant=tenant).only(
        "id", "first_name", "middle_name", "last_name"
    )
    student_names = {s.id: s.get_full_name() for s in students}

    students_out = []
    for sid, exam_pcts in student_exam_pcts.items():
        exam_series = []
        for exam in exam_order:
            if exam["id"] in exam_pcts:
                exam_series.append({
                    "exam": exam["name"],
                    "term": exam["term"],
                    "mean": d(safe_mean(exam_pcts[exam["id"]])),
                })

        means_only = [float(e["mean"]) for e in exam_series]
        trajectory, slope = _classify_trajectory(means_only)

        term_means_raw = defaultdict(list)
        for exam in exam_order:
            if exam["id"] in exam_pcts:
                term_means_raw[exam["term"]].extend(exam_pcts[exam["id"]])
        term_means_out = {
            term_key: d(safe_mean(pcts)) if pcts else None
            for term_key, pcts in term_means_raw.items()
        }

        students_out.append({
            "student": {"id": sid, "name": student_names.get(sid, f"Student {sid}")},
            "trajectory": trajectory,
            "exams": exam_series,
            "term_means": term_means_out,
            "trend_slope": slope,
            "overall_mean": d(safe_mean(means_only)) if means_only else d(0),
        })

    students_out.sort(key=lambda s: float(s["overall_mean"]), reverse=True)

    total = len(students_out)
    by_trajectory = defaultdict(int)
    for s in students_out:
        by_trajectory[s["trajectory"]] += 1

    with_slope = [s for s in students_out if s["trajectory"] != "insufficient_data"]
    biggest_improvers = sorted(with_slope, key=lambda s: s["trend_slope"], reverse=True)[:3]
    most_declined = sorted(with_slope, key=lambda s: s["trend_slope"])[:3]

    top_cutoff = max(1, round(total * 0.2))
    consistent_top = students_out[:top_cutoff]
    consistent_bottom = list(reversed(students_out[-top_cutoff:])) if total else []

    needs_attention_raw = [
        s for s in students_out
        if s["trajectory"] == "declining" or s in consistent_bottom
    ]
    seen_ids = set()
    needs_attention = []
    for s in needs_attention_raw:
        sid = s["student"]["id"]
        if sid not in seen_ids:
            seen_ids.add(sid)
            needs_attention.append(s)

    data = {
        "classroom": {"id": classroom.id, "name": classroom.name},
        "academic_year": academic_year,
        "summary": {
            "total_students": total,
            "rising": by_trajectory["rising"],
            "stable": by_trajectory["stable"],
            "declining": by_trajectory["declining"],
            "inconsistent": by_trajectory["inconsistent"],
            "insufficient_data": by_trajectory["insufficient_data"],
        },
        "highlights": {
            "biggest_improvers": biggest_improvers,
            "most_declined": most_declined,
            "consistent_top": consistent_top,
            "consistent_bottom": consistent_bottom,
            "needs_attention": needs_attention[:10],
        },
        "students": students_out,
    }

    cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
    return data
