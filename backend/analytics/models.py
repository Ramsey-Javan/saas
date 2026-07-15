"""Analytics models.

This app primarily uses computed data (via services.py) rather than stored models.
However, we define pre-computed aggregate models for high-performance scenarios
and signal-based cache invalidation hooks.
"""
from django.db import models


class AnalyticsSnapshot(models.Model):
    """Pre-computed analytics snapshot for heavy computations.

    Can be used to store nightly-computed aggregates for very large schools
    (1000+ students) to avoid real-time computation.
    """
    class SnapshotType(models.TextChoices):
        SCHOOL_SUMMARY = 'school_summary', 'School Summary'
        CLASS_PERFORMANCE = 'class_performance', 'Class Performance'
        EARLY_WARNING = 'early_warning', 'Early Warning'
        SUBJECT_COMPARISON = 'subject_comparison', 'Subject Comparison'

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='analytics_snapshots',
    )
    snapshot_type = models.CharField(max_length=30, choices=SnapshotType.choices)
    classroom = models.ForeignKey(
        'students.Classroom',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='analytics_snapshots',
    )
    term = models.CharField(max_length=10, blank=True)
    academic_year = models.PositiveIntegerField()
    data = models.JSONField(default=dict)
    computed_at = models.DateTimeField(auto_now=True)
    is_stale = models.BooleanField(default=False)

    class Meta:
        unique_together = ['tenant', 'snapshot_type', 'classroom', 'term', 'academic_year']
        ordering = ['-computed_at']
        indexes = [
            models.Index(fields=['tenant', 'snapshot_type', 'academic_year']),
            models.Index(fields=['tenant', 'classroom', 'term', 'academic_year']),
        ]

    def __str__(self):
        return f"{self.snapshot_type} - {self.tenant} - {self.academic_year} {self.term}"