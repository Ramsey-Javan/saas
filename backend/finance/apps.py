from django.apps import AppConfig


class FinanceConfig(AppConfig):
    name = 'finance'

    def ready(self):
        # Import signals to ensure waiver changes update invoices
        import finance.signals  # noqa: F401
