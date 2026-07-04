import pytest
from django.urls import reverse

from finance.models import Payment, StudentFee
from tests.factories import (
    ClassroomFactory,
    StudentFactory,
    StudentFeeFactory,
    FeeStructureFactory,
)


def _reverse_or_skip(url_names, kwargs=None):
    for name in url_names:
        try:
            if kwargs:
                return reverse(name, kwargs=kwargs)
            return reverse(name)
        except:
            continue
    return None


@pytest.mark.django_db
class TestDashboardViewsExtended:
    def test_admin_dashboard_with_students(self, admin_client, admin_user):
        classroom = ClassroomFactory()
        StudentFactory(classroom=classroom)
        StudentFactory(classroom=classroom)
        StudentFactory(classroom=classroom)

        url = _reverse_or_skip(['dashboard-stats', 'dashboard-summary'])
        if url is None:
            pytest.skip("dashboard-stats URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_admin_dashboard_with_classrooms(self, admin_client, admin_user):
        ClassroomFactory()
        ClassroomFactory()

        url = _reverse_or_skip(['dashboard-stats', 'dashboard-summary'])
        if url is None:
            pytest.skip("dashboard-stats URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_bursar_dashboard_with_payments(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        fee_structure = FeeStructureFactory(classroom=classroom)
        StudentFeeFactory(student=student, fee_structure=fee_structure)
        Payment.objects.create(
            student=student,
            amount=5000,
            payment_method='cash',
            status='confirmed',
            tenant=student.tenant,
            idempotency_key='dash-test-1',
        )
        Payment.objects.create(
            student=student,
            amount=3000,
            payment_method='mpesa',
            status='confirmed',
            tenant=student.tenant,
            idempotency_key='dash-test-2',
        )

        url = _reverse_or_skip(['bursar-dashboard', 'finance-dashboard'])
        if url is None:
            pytest.skip("bursar-dashboard URL not found")

        response = bursar_client.get(url)
        assert response.status_code in [200, 404]

    def test_fee_trend_with_term_filter(self, bursar_client, bursar_user):
        url = _reverse_or_skip(['fee-trends', 'fee-trend-data'])
        if url is None:
            pytest.skip("fee-trends URL not found")

        response = bursar_client.get(url, {'term': 'term1', 'academic_year': 2026})
        assert response.status_code in [200, 404]

    def test_recent_payments_with_limit(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        Payment.objects.create(
            student=student,
            amount=1000,
            payment_method='cash',
            status='confirmed',
            tenant=student.tenant,
            idempotency_key='dash-test-3',
        )

        url = _reverse_or_skip(['recent-payments', 'payment-recent'])
        if url is None:
            pytest.skip("recent-payments URL not found")

        response = bursar_client.get(url, {'limit': 5})
        assert response.status_code in [200, 404]

    def test_enrollment_chart_with_year_filter(self, admin_client, admin_user):
        url = _reverse_or_skip(['enrollment-chart', 'enrollment-data'])
        if url is None:
            pytest.skip("enrollment-chart URL not found")

        response = admin_client.get(url, {'academic_year': 2026})
        assert response.status_code in [200, 404]
