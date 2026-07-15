"""Early Warning System (rule-based, explainable -- not a black-box model).

Every flag lists its own concrete reasons via `risk_factors`, so a
teacher can see exactly why a student appears here. Three risk tiers,
built from combinations of the same signals:
  - below_expectation: this term's overall mean is under "Meeting
    Expectation" (config.me_min).
  - declining: SAME trajectory classification as the Improvement Tracker
    (tracker.py's _classify_trajectory) -- "declining" means one thing
    everywhere in this app.
  - multiple_be: 2+ individual subjects sitting at Below Expectation
    this term, even if the overall mean hasn't dropped that far yet.
  - slight_decline: a milder single-term dip vs the immediately
    preceding term, not yet a sustained "declining" trajectory.

risk_level:
  high    = below_expectation AND declining together
  medium  = any ONE of below_expectation / declining / multiple_be alone
  low     = only a slight single-term dip, nothing more serious yet
"""
from collections import defaultdict

from django.core.cache import cache

from academics.models import ExamResult, ExamConfig

from .cache_keys import CACHE_TTL_SUMMARY, early_warning
from ._helpers import d, safe_mean, TERM_ORDER
from .tracker import _classify_trajectory
from .exceptions import InsufficientDataError

MULTIPLE_BE_THRESHOLD = 2
SLIGHT_DECLINE_THRESHOLD = 5.0  # percentage points dropped vs previous term


def _previous_term(current_term):
    """Only handles same-academic-year lookback (term2->term1, term3->term2)
    -- deliberately simple. term1 has no previous_term_mean computed; the
    frontend already handles that as optional/absent."""
    return {"term2": "term1", "term3": "term2"}.get(current_term)


def get_early_warning(tenant, term, academic_year):
    """
    Rule-based at-risk list for one term, computed school-wide (views.py
    scopes the result down to a single classroom for teachers).
    3 DB queries: this term's results, the previous term's results (for
    comparison), and the full year's results (for trajectory).
    """
    ck = early_warning(tenant.id, term, academic_year)
    cached = cache.get(ck)
    if cached:
        return cached

    config = ExamConfig.get_for_tenant(tenant)

    term_rows = list(
        ExamResult.objects
        .filter(tenant=tenant, exam_subject__exam__term=term, exam_subject__exam__academic_year=academic_year)
        .values(
            "student_id", "percentage", "cbc_level",
            "student__classroom_id", "student__classroom__name",
            "exam_subject__subject__id", "exam_subject__subject__name",
        )
    )
    if not term_rows:
        raise InsufficientDataError(
            filters={"term": term, "academic_year": academic_year},
            suggestion="No exam results recorded for this term yet.",
        )

    prev_term = _previous_term(term)
    prev_term_means = {}
    if prev_term:
        prev_rows = list(
            ExamResult.objects
            .filter(tenant=tenant, exam_subject__exam__term=prev_term, exam_subject__exam__academic_year=academic_year)
            .values("student_id", "percentage")
        )
        prev_by_student = defaultdict(list)
        for r in prev_rows:
            prev_by_student[r["student_id"]].append(float(r["percentage"]))
        prev_term_means = {sid: safe_mean(pcts) for sid, pcts in prev_by_student.items()}

    year_rows = list(
        ExamResult.objects
        .filter(tenant=tenant, exam_subject__exam__academic_year=academic_year)
        .values(
            "student_id", "percentage",
            "exam_subject__exam__id", "exam_subject__exam__term",
            "exam_subject__exam__start_date",
        )
    )

    student_term_pcts = defaultdict(list)
    student_classroom = {}
    student_subject_pcts = defaultdict(lambda: defaultdict(list))
    subject_names = {}
    for r in term_rows:
        sid = r["student_id"]
        student_term_pcts[sid].append(float(r["percentage"]))
        student_classroom[sid] = {"id": r["student__classroom_id"], "name": r["student__classroom__name"]}
        subj_id = r["exam_subject__subject__id"]
        student_subject_pcts[sid][subj_id].append(float(r["percentage"]))
        subject_names[subj_id] = r["exam_subject__subject__name"]

    student_exam_pcts = defaultdict(lambda: defaultdict(list))
    exam_meta = {}
    for r in year_rows:
        eid = r["exam_subject__exam__id"]
        student_exam_pcts[r["student_id"]][eid].append(float(r["percentage"]))
        if eid not in exam_meta:
            exam_meta[eid] = {"term": r["exam_subject__exam__term"], "start_date": str(r["exam_subject__exam__start_date"])}
    exam_order = sorted(exam_meta.items(), key=lambda kv: (TERM_ORDER.get(kv[1]["term"], 99), kv[1]["start_date"]))

    from students.models import Student
    students = Student.objects.filter(id__in=student_term_pcts.keys(), tenant=tenant).only(
        "id", "first_name", "middle_name", "last_name", "admission_number"
    )
    student_names = {s.id: (s.get_full_name(), s.admission_number) for s in students}

    flagged = []

    for sid, term_pcts in student_term_pcts.items():
        term_mean = safe_mean(term_pcts)
        below_expectation = term_mean < config.me_min

        exam_series = [
            safe_mean(student_exam_pcts[sid][eid])
            for eid, _ in exam_order
            if eid in student_exam_pcts[sid]
        ]
        trajectory, slope = _classify_trajectory(exam_series)
        declining = trajectory == "declining"

        be_subjects = [
            subject_names[subj_id]
            for subj_id, pcts in student_subject_pcts[sid].items()
            if len(pcts) and safe_mean(pcts) < config.ae_min  # BE band specifically
        ]
        at_risk_subjects = [
            subject_names[subj_id]
            for subj_id, pcts in student_subject_pcts[sid].items()
            if len(pcts) and safe_mean(pcts) < config.me_min  # AE or BE band -- the broader "at risk" set
        ]
        multiple_be = len(be_subjects) >= MULTIPLE_BE_THRESHOLD

        prev_mean = prev_term_means.get(sid)
        slight_decline = (
            prev_mean is not None
            and (prev_mean - term_mean) >= SLIGHT_DECLINE_THRESHOLD
            and not declining
        )

        if not (below_expectation or declining or multiple_be or slight_decline):
            continue

        risk_factors = []
        if below_expectation:
            risk_factors.append({
                "type": "overall_be",
                "message": f"Overall performance is Below Expectation ({d(term_mean)}%)",
                "severity": "high",
            })
        if declining:
            risk_factors.append({
                "type": "declining",
                "message": "Declining trend across recent exams",
                "severity": "high",
            })
        if multiple_be:
            risk_factors.append({
                "type": "multiple_be",
                "message": f"{len(be_subjects)} subjects Below Expectation",
                "severity": "medium",
            })
        if slight_decline:
            risk_factors.append({
                "type": "slight_decline",
                "message": f"Dropped {d(prev_mean - term_mean)} points from last term",
                "severity": "low",
            })

        if below_expectation and declining:
            risk_level = "high"
            recommended_action = "Schedule a parent-teacher meeting as soon as possible."
        elif below_expectation or declining or multiple_be:
            risk_level = "medium"
            recommended_action = "Monitor closely and consider targeted subject support."
        else:
            risk_level = "low"
            recommended_action = "Keep an eye on next term's results."

        name, adm = student_names.get(sid, (f"Student {sid}", ""))
        flagged.append({
            "student": {
                "id": sid, "name": name, "admission_number": adm,
                "classroom": student_classroom.get(sid),
            },
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "current_term_mean": float(d(term_mean)),
            "previous_term_mean": float(d(prev_mean)) if prev_mean is not None else None,
            "subjects_at_risk": at_risk_subjects,
            "recommended_action": recommended_action,
            "trend_slope": slope,
        })

    risk_order = {"high": 0, "medium": 1, "low": 2}
    flagged.sort(key=lambda e: (risk_order[e["risk_level"]], e["current_term_mean"]))

    data = {
        "term": term,
        "academic_year": academic_year,
        "at_risk_count": len(flagged),
        "total_students_evaluated": len(student_term_pcts),
        "students": flagged,
    }

    cache.set(ck, data, timeout=CACHE_TTL_SUMMARY)
    return data
