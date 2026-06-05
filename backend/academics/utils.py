import json
from collections import Counter
from pathlib import Path

from django.db import transaction

from .models import LearningOutcome, Strand, Subject, SubStrand

LEVEL_TO_INT = {'BE': 1, 'AE': 2, 'ME': 3, 'EE': 4}
INT_TO_LEVEL = {1: 'BE', 2: 'AE', 3: 'ME', 4: 'EE'}


def load_knec_curriculum(tenant):
    fixture_path = Path(__file__).resolve().parent / 'fixtures' / 'knec_cbc_curriculum.json'
    with fixture_path.open(encoding='utf-8') as fixture:
        records = json.load(fixture)

    subject_map = {}
    strand_map = {}
    sub_strand_map = {}
    counts = Counter()

    with transaction.atomic():
        for record in records:
            model = record.get('model')
            fields = record.get('fields', {})
            key = record.get('pk')

            if model == 'academics.subject':
                subject, created = Subject.objects.get_or_create(
                    tenant=tenant,
                    code=fields['code'],
                    defaults={
                        'name': fields['name'],
                        'description': fields.get('description', ''),
                        'grade_levels': fields.get('grade_levels', []),
                        'is_preloaded': True,
                        'is_active': fields.get('is_active', True),
                        'order': fields.get('order', 0),
                    },
                )
                if not created:
                    updates = {}
                    if subject.name != fields['name']:
                        updates['name'] = fields['name']
                    if subject.description != fields.get('description', ''):
                        updates['description'] = fields.get('description', '')
                    if subject.grade_levels != fields.get('grade_levels', []):
                        updates['grade_levels'] = fields.get('grade_levels', [])
                    if not subject.is_preloaded:
                        updates['is_preloaded'] = True
                    if subject.is_active != fields.get('is_active', True):
                        updates['is_active'] = fields.get('is_active', True)
                    if subject.order != fields.get('order', 0):
                        updates['order'] = fields.get('order', 0)
                    if updates:
                        Subject.objects.filter(id=subject.id).update(**updates)
                        subject.refresh_from_db()
                subject_map[key] = subject
                if created:
                    counts['subjects'] += 1
            elif model == 'academics.strand':
                strand, created = Strand.objects.get_or_create(
                    tenant=tenant,
                    subject=subject_map[fields['subject']],
                    name=fields['name'],
                    defaults={'order': fields.get('order', 0)},
                )
                if not created and strand.order != fields.get('order', 0):
                    Strand.objects.filter(id=strand.id).update(order=fields.get('order', 0))
                    strand.refresh_from_db()
                strand_map[key] = strand
                if created:
                    counts['strands'] += 1
            elif model == 'academics.substrand':
                sub_strand, created = SubStrand.objects.get_or_create(
                    tenant=tenant,
                    strand=strand_map[fields['strand']],
                    name=fields['name'],
                    defaults={'order': fields.get('order', 0)},
                )
                if not created and sub_strand.order != fields.get('order', 0):
                    SubStrand.objects.filter(id=sub_strand.id).update(order=fields.get('order', 0))
                    sub_strand.refresh_from_db()
                sub_strand_map[key] = sub_strand
                if created:
                    counts['sub_strands'] += 1
            elif model == 'academics.learningoutcome':
                outcome, created = LearningOutcome.objects.get_or_create(
                    tenant=tenant,
                    sub_strand=sub_strand_map[fields['sub_strand']],
                    description=fields['description'],
                    defaults={'order': fields.get('order', 0)},
                )
                if not created and outcome.order != fields.get('order', 0):
                    LearningOutcome.objects.filter(id=outcome.id).update(order=fields.get('order', 0))
                if created:
                    counts['learning_outcomes'] += 1

    return {
        'subjects': counts['subjects'],
        'strands': counts['strands'],
        'sub_strands': counts['sub_strands'],
        'learning_outcomes': counts['learning_outcomes'],
    }


def assign_strand_levels(exam_level: str, strands: list) -> dict:
    """
    Given an overall exam CBC level and a list of strands (ordered by strand.order ascending),
    returns a dict mapping strand_id to CBC level.
    """
    import random

    target = LEVEL_TO_INT[exam_level]
    result = {}
    strand_list = list(strands)

    if not strand_list:
        return result

    core_strands = strand_list[:2]
    minor_strands = strand_list[2:]

    def clamp(val):
        return max(1, min(4, val))

    def assign_core(target_int):
        if random.random() < 0.70:
            return target_int
        delta = random.choice([-1, 1])
        return clamp(target_int + delta)

    def assign_minor(target_int):
        if random.random() < 0.40:
            return target_int
        delta = random.choice([-1, 1])
        return clamp(target_int + delta)

    assigned = {}
    for strand in core_strands:
        assigned[strand.id] = assign_core(target)
    for strand in minor_strands:
        assigned[strand.id] = assign_minor(target)

    if len(assigned) > 1:
        total = sum(assigned.values())
        count = len(assigned)
        current_avg = total / count
        attempts = 0

        while abs(current_avg - target) > 0.5 and attempts < 20:
            attempts += 1

            if current_avg < target:
                candidates = [
                    s for s in minor_strands
                    if assigned[s.id] < target and assigned[s.id] < 4
                ]
                if not candidates:
                    candidates = [
                        s for s in core_strands
                        if assigned[s.id] < 4
                    ]
                if candidates:
                    chosen = random.choice(candidates)
                    assigned[chosen.id] = clamp(assigned[chosen.id] + 1)
            else:
                candidates = [
                    s for s in minor_strands
                    if assigned[s.id] > target and assigned[s.id] > 1
                ]
                if not candidates:
                    candidates = [
                        s for s in core_strands
                        if assigned[s.id] > 1
                    ]
                if candidates:
                    chosen = random.choice(candidates)
                    assigned[chosen.id] = clamp(assigned[chosen.id] - 1)

            total = sum(assigned.values())
            current_avg = total / count

    for strand_id, level_int in assigned.items():
        result[strand_id] = INT_TO_LEVEL[level_int]

    return result


def assign_outcome_levels(strand_level: str, outcomes: list) -> dict:
    """
    Given a strand's CBC level, assign individual learning outcome levels with minor variation.
    """
    import random

    strand_int = LEVEL_TO_INT[strand_level]
    result = {}

    for outcome in outcomes:
        if random.random() < 0.60:
            result[outcome.id] = strand_level
        else:
            delta = random.choice([-1, 1])
            level_int = max(1, min(4, strand_int + delta))
            result[outcome.id] = INT_TO_LEVEL[level_int]

    return result
