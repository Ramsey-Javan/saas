"""Shared utilities for analytics services: safe number handling, chart
builders, CBC level constants, and cache TTL policy.

Kept dependency-free (no numpy/pandas) since every series here is short
(a handful of exams per student per year) -- plain statistics/Decimal is
plenty fast and keeps the Docker image lean.
"""
import statistics
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone


# ── Term ordering ──────────────────────────────────────────────────────
# Used everywhere a series needs to be sorted chronologically by term
# (school-year rollups, student trend charts, improvement tracker).
TERM_ORDER = {'term1': 1, 'term2': 2, 'term3': 3}


# ── Number safety ──────────────────────────────────────────────────────
def d(value):
    """Round a number to 2 decimal places as a Decimal. Safe for None."""
    if value is None:
        return Decimal('0.00')
    return Decimal(str(round(float(value), 2))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def safe_mean(values):
    """Mean of a list of numbers, ignoring None, defaulting to 0.0 when empty."""
    clean = [v for v in values if v is not None]
    return statistics.fmean(clean) if clean else 0.0


def safe_median(values):
    clean = [v for v in values if v is not None]
    return statistics.median(clean) if clean else 0.0


def safe_stdev(values):
    """Population stdev (pstdev) rather than sample stdev -- we always
    have the FULL set of results for a given exam/subject, not a sample."""
    clean = [v for v in values if v is not None]
    return statistics.pstdev(clean) if len(clean) > 1 else 0.0


# ── CBC level constants ────────────────────────────────────────────────
CBC_LEVELS = ('EE', 'ME', 'AE', 'BE')

CBC_LABELS = {
    'EE': 'Exceeding Expectation',
    'ME': 'Meeting Expectation',
    'AE': 'Approaching Expectation',
    'BE': 'Below Expectation',
}

CBC_COLORS = {
    'EE': '#16a34a',
    'ME': '#2563eb',
    'AE': '#f59e0b',
    'BE': '#dc2626',
}

PALETTE = ['#2563eb', '#16a34a', '#f59e0b', '#dc2626', '#7c3aed', '#0891b2', '#db2777', '#65a30d']


def grade_dist(levels):
    """Counts + percentages per CBC level for a flat list of level strings."""
    total = len(levels)
    counts = {lv: 0 for lv in CBC_LEVELS}
    for lv in levels:
        if lv in counts:
            counts[lv] += 1
    percentages = {
        lv: d((counts[lv] / total) * 100) if total else Decimal('0.00')
        for lv in CBC_LEVELS
    }
    return {'counts': counts, 'percentages': percentages, 'total': total}


def compute_level(config, percentage):
    """Compute a CBC level directly from a percentage (0-100), reusing an
    ExamConfig instance's thresholds. Distinct from ExamConfig.compute_level(),
    which takes raw marks/total_marks -- this is for already-averaged
    percentages (e.g. a student's mean % across several exams), where
    there's no single "total_marks" to divide by."""
    if percentage >= config.ee_min:
        return 'EE'
    if percentage >= config.me_min:
        return 'ME'
    if percentage >= config.ae_min:
        return 'AE'
    return 'BE'


# ── Chart builders ─────────────────────────────────────────────────────
# Plain, framework-agnostic shapes -- the frontend maps these directly
# onto Recharts (or Chart.js) components. Backend decides chart type and
# colors so every analytics view looks consistent without the frontend
# having to encode any domain knowledge about what "looks right" for a
# given metric.
def bar_chart(labels, datasets):
    return {'type': 'bar', 'labels': labels, 'datasets': datasets}


def line_chart(labels, datasets):
    return {'type': 'line', 'labels': labels, 'datasets': datasets}


def pct_bar_chart(labels, datasets):
    return {'type': 'bar_percentage', 'labels': labels, 'datasets': datasets}


def cbc_pie(levels, title=''):
    dist = grade_dist(levels)
    return {
        'type': 'pie',
        'title': title,
        'labels': [CBC_LABELS[lv] for lv in CBC_LEVELS],
        'datasets': [{
            'data': [dist['counts'][lv] for lv in CBC_LEVELS],
            'colors': [CBC_COLORS[lv] for lv in CBC_LEVELS],
        }],
    }


# ── Cache TTL policy ────────────────────────────────────────────────────
CACHE_TTL_CURRENT = 60 * 5        # 5 min -- this term/year's data is still changing
CACHE_TTL_PAST = 60 * 60 * 24     # 24 hr -- historical terms are effectively frozen


def ttl(term, academic_year):
    """
    Short cache for the current (still-changing) academic year; long
    cache for past years, since historical exam data never changes once
    the year is over. Worst case if this guess is ever wrong (e.g. a
    correction is made to a "past" year's marks) is a 24h-stale cache --
    acceptable, and avoidable by clearing the cache key manually if that
    ever happens.
    """
    now_year = timezone.localdate().year
    if int(academic_year) < now_year:
        return CACHE_TTL_PAST
    return CACHE_TTL_CURRENT