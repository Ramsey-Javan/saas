"""Django app configuration for analytics."""
from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analytics'
    verbose_name = 'Exam Analytics'

    def ready(self):
        """Import signal handlers when the app is ready."""
        import analytics.signals  # noqa: F401