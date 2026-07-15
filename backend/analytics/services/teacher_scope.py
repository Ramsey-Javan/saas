"""Teacher scope resolver — returns what a teacher can see in analytics.

Admins get full scope. Class teachers get their classroom + any subjects
they teach. Subject teachers get only their assigned subjects.
"""
from collections import defaultdict
from django.utils import timezone
from academics.models import ClassSubjectAssignment, ExamSubject 
from students.models import Classroom
from ._helpers import d, safe_mean, grade_dist 


def get_teacher_scope(tenant, user):
    """
    Returns enriched teacher scope for the analytics frontend to know
    what to render.
    """
    is_admin = user.role == 'admin'
    is_teacher = user.role == 'teacher'

    scope = {
        "role": user.role,
        "is_admin": is_admin,
        "is_teacher": is_teacher,
        "is_class_teacher": False,
        "is_subject_teacher": False,
        "classrooms": [],
        "subjects": [],
    }

    if is_admin:
        # Admin sees everything — return empty arrays as signal to frontend
        # that no filtering should be applied
        return scope

    if not is_teacher:
        return scope

    # ── Class teacher check ──────────────────────────────────────────
    owned_classrooms = list(
        Classroom.objects.filter(tenant=tenant, class_teacher=user)
        .values("id", "name", "grade_level", "stream")
    )

    if owned_classrooms:
        scope["is_class_teacher"] = True
        scope["classrooms"] = [
            {
                "id": c["id"],
                "name": c["name"],
                "display_name": f"{c['grade_level']}{' ' + c['stream'] if c['stream'] else ''}",
                "grade_level": c["grade_level"],
                "stream": c["stream"],
            }
            for c in owned_classrooms
        ]

    # ── Subject teacher check ─────────────────────────────────────────
    # Current academic year assignments
    from django.utils import timezone
    current_year = timezone.now().year

    direct_subjects = set(
        ExamSubject.objects.filter(
            teacher=user,
            exam__academic_year__gte=current_year - 1,
        ).values_list("subject_id", flat=True)
    )

    assignment_subjects = set(
        ClassSubjectAssignment.objects.filter(
            tenant=tenant,
            teacher=user,
            academic_year__gte=current_year - 1,
        ).values_list("subject_id", flat=True)
    )

    all_subject_ids = direct_subjects | assignment_subjects

    if all_subject_ids:
        from academics.models import Subject
        subject_rows = list(
            Subject.objects.filter(id__in=all_subject_ids, tenant=tenant)
            .values("id", "name", "code")
        )
        scope["is_subject_teacher"] = True
        scope["subjects"] = [
            {"id": s["id"], "name": s["name"], "code": s["code"]}
            for s in subject_rows
        ]

    # ── Cross-reference: which subjects in which classrooms ──────────
    # For the combo teacher (class teacher + subject teacher)
    if scope["is_class_teacher"] and scope["is_subject_teacher"]:
        scope["classroom_subject_map"] = {}
        for cid in [c["id"] for c in owned_classrooms]:
            assigned = set(
                ClassSubjectAssignment.objects.filter(
                    tenant=tenant,
                    classroom_id=cid,
                    teacher=user,
                ).values_list("subject_id", flat=True)
            )
            scope["classroom_subject_map"][cid] = list(assigned)

    return scope


def get_teacher_overview(tenant, user, academic_year):
    from .subject_teacher import _get_teacher_subject_classrooms

    """
    Scoped school overview for a teacher.
    - Class teachers see their classroom(s) data
    - Subject teachers see their subject-classroom data
    - Combo teachers see BOTH
    """
    from academics.models import ExamResult, ExamSetup, Subject

    # ── Class teacher data ───────────────────────────────────────────
    owned_classrooms = list(
        Classroom.objects.filter(tenant=tenant, class_teacher=user)
        .values("id", "name", "grade_level", "stream")
    )

    # Build display_name for each classroom (e.g., "Grade 3 East")
    for c in owned_classrooms:
        c["display_name"] = f"{c['grade_level']}{' ' + c['stream'] if c['stream'] else ''}"

    # ── Subject teacher data (subjects in OTHER classrooms) ──────────
    subject_pairs = _get_teacher_subject_classrooms(tenant, user, academic_year)
    # Filter out classrooms they already own (those are in owned_classrooms)
    owned_ids = {c["id"] for c in owned_classrooms}
    extra_subject_pairs = [p for p in subject_pairs if p['classroom_id'] not in owned_ids]

    # Empty response if teacher has nothing
    if not owned_classrooms and not extra_subject_pairs:
        return {
            "academic_year": academic_year,
            "mean_percentage": None,
            "total_results": 0,
            "total_students": 0,
            "total_exams": 0,
            "top_performing_class": None,
            "lowest_performing_class": None,
            "terms": [],
            "classrooms": [],
            "subject_classrooms": [],
            "grade_distribution": {"counts": {"EE": 0, "ME": 0, "AE": 0, "BE": 0}, "percentages": {"EE": "0.00", "ME": "0.00", "AE": "0.00", "BE": "0.00"}},
            "charts": {},
            "is_teacher_view": True,
        }

    # Collect all classroom IDs we need results for
    all_classroom_ids = list({c["id"] for c in owned_classrooms} | {p['classroom_id'] for p in extra_subject_pairs})

    rows = list(
        ExamResult.objects
        .filter(tenant=tenant, exam_subject__exam__academic_year=academic_year, student__classroom_id__in=all_classroom_ids)
        .values("student_id", "percentage", "cbc_level", "exam_subject__exam__term",
                "exam_subject__exam__classroom_id", "exam_subject__exam__classroom__name",
                "exam_subject__subject_id", "exam_subject__subject__name")
    )

    if not rows:
        return {
            "academic_year": academic_year,
            "mean_percentage": None,
            "total_results": 0,
            "total_students": 0,
            "total_exams": 0,
            "top_performing_class": None,
            "lowest_performing_class": None,
            "terms": [],
            "classrooms": [{"id": c["id"], "name": c["display_name"], "stream": c.get("stream"), "mean": None} for c in owned_classrooms],
            "subject_classrooms": [],
            "grade_distribution": {"counts": {"EE": 0, "ME": 0, "AE": 0, "BE": 0}, "percentages": {"EE": "0.00", "ME": "0.00", "AE": "0.00", "BE": "0.00"}},
            "charts": {},
            "is_teacher_view": True,
        }

    # ── Aggregate owned classrooms ──────────────────────────────────
    by_classroom = defaultdict(list)
    by_term = defaultdict(list)
    all_levels = []

    # Subject-classroom aggregation for extra pairs
    extra_subject_data = defaultdict(list)

    for r in rows:
        cid = r["exam_subject__exam__classroom_id"]
        pct = float(r["percentage"])
        by_classroom[cid].append(pct)
        by_term[r["exam_subject__exam__term"]].append(pct)
        all_levels.append(r["cbc_level"])

        # If this classroom is in extra_subject_pairs, bucket by subject too
        if cid in {p['classroom_id'] for p in extra_subject_pairs}:
            extra_subject_data[(cid, r['exam_subject__subject_id'])].append({
                'percentage': pct,
                'subject_name': r['exam_subject__subject__name'],
                'subject_id': r['exam_subject__subject_id'],
            })

    # Build classroom rows for owned classrooms
    classroom_rows = []
    for c in owned_classrooms:
        cid = c["id"]
        pcts = by_classroom.get(cid, [])
        mean = safe_mean(pcts) if pcts else None
        classroom_rows.append({
            "id": cid,
            "name": c["display_name"],  # <-- FIX: use display_name ("Grade 3 East")
            "stream": c.get("stream"),
            "mean": float(d(mean)) if mean is not None else None,
        })

    classroom_rows.sort(key=lambda x: x["mean"] or 0, reverse=True)

    # Build subject_classrooms for extra assignments
    subject_classroom_rows = []
    for p in extra_subject_pairs:
        cid = p['classroom_id']
        sid = p['subject_id']
        key = (cid, sid)
        pcts = [d['percentage'] for d in extra_subject_data.get(key, [])]
        if pcts:
            mean = safe_mean(pcts)
            subject_classroom_rows.append({
                'classroom_id': cid,
                'classroom_name': p['classroom_name'],
                'classroom_display_name': f"{p['classroom_name']}{' ' + p['stream'] if p.get('stream') else ''}",
                'stream': p.get('stream'),
                'subject_id': sid,
                'subject_name': p['subject_name'],
                'mean_percentage': d(mean),
                'student_count': len(set(d['student_id'] for d in extra_subject_data.get(key, []) if 'student_id' in d)) or len(pcts),
                'result_count': len(pcts),
            })

    total_exams = ExamSetup.objects.filter(tenant=tenant, academic_year=academic_year, classroom_id__in=all_classroom_ids).count()
    all_pcts = [float(r["percentage"]) for r in rows]

    data = {
        "academic_year": academic_year,
        "mean_percentage": d(safe_mean(all_pcts)) if all_pcts else None,
        "total_results": len(rows),
        "total_students": len({r["student_id"] for r in rows}),
        "total_exams": total_exams,
        "top_performing_class": classroom_rows[0] if classroom_rows else None,
        "lowest_performing_class": classroom_rows[-1] if classroom_rows else None,
        "terms": [
            {"term": t, "mean": d(safe_mean(pcts)), "result_count": len(pcts), "exam_count": None}
            for t, pcts in by_term.items()
        ],
        "classrooms": classroom_rows,
        "subject_classrooms": subject_classroom_rows,
        "grade_distribution": grade_dist(all_levels),
        "charts": {},
        "is_teacher_view": True,
    }

    return data