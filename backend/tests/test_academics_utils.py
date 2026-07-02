import json
import io
import random
from types import SimpleNamespace

from academics.utils import (
    INT_TO_LEVEL,
    LEVEL_TO_INT,
    assign_outcome_levels,
    assign_strand_levels,
    load_knec_curriculum,
)
from tests.factories import LearningOutcomeFactory, StrandFactory, TenantFactory


def test_load_knec_curriculum_is_idempotent(db, monkeypatch):
    tenant = TenantFactory()

    payload = json.dumps([
        {'model': 'academics.subject', 'pk': 1, 'fields': {'code': 'ENG', 'name': 'English', 'description': '', 'grade_levels': ['Grade 4'], 'is_preloaded': True, 'is_active': True, 'order': 1}},
        {'model': 'academics.strand', 'pk': 2, 'fields': {'subject': 1, 'name': 'Reading', 'order': 1}},
        {'model': 'academics.substrand', 'pk': 3, 'fields': {'strand': 2, 'name': 'Comprehension', 'order': 1}},
        {'model': 'academics.learningoutcome', 'pk': 4, 'fields': {'sub_strand': 3, 'description': 'Reads a short passage', 'order': 1}},
    ])
    class FakeFixture(io.StringIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()

    monkeypatch.setattr('academics.utils.Path.open', lambda self, encoding=None: FakeFixture(payload))

    first = load_knec_curriculum(tenant)
    second = load_knec_curriculum(tenant)


    assert first['subjects'] > 0
    assert first['strands'] > 0
    assert first['sub_strands'] > 0
    assert first['learning_outcomes'] > 0
    assert second == {'subjects': 0, 'strands': 0, 'sub_strands': 0, 'learning_outcomes': 0}


def test_assign_strand_levels_rebalances_average(db, monkeypatch):
    strands = [SimpleNamespace(id=1, order=0), SimpleNamespace(id=2, order=1), SimpleNamespace(id=3, order=2)]
    monkeypatch.setattr(random, 'random', lambda: 0.99)
    monkeypatch.setattr(random, 'choice', lambda options: options[0])

    levels = assign_strand_levels('ME', strands)
    numeric_levels = [LEVEL_TO_INT[level] for level in levels.values()]
    average = sum(numeric_levels) / len(numeric_levels)

    assert set(levels) == {strand.id for strand in strands}
    assert all(level in INT_TO_LEVEL.values() for level in levels.values())
    assert abs(average - LEVEL_TO_INT['ME']) <= 0.5


def test_assign_outcome_levels_preserves_strand_level_when_random_allows(db, monkeypatch):
    outcomes = [SimpleNamespace(id=10), SimpleNamespace(id=11)]
    monkeypatch.setattr(random, 'random', lambda: 0.0)

    levels = assign_outcome_levels('AE', outcomes)

    assert levels == {outcome.id: 'AE' for outcome in outcomes}
