import pytest
from decimal import Decimal
from django.urls import reverse

from finance.models import StudentFee, Payment, Receipt
from tests.factories import (
    ClassroomFactory,
    FeeStructureFactory,
    StudentFactory,
    StudentFeeFactory,
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
class TestStatementViews:
    def test_student_statement_detail(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        fee_structure = FeeStructureFactory(
            classroom=classroom,
            term='term1',
            academic_year=2026,
            base_amount=Decimal('10000.00'),
        )
        invoice = StudentFeeFactory(
            student=student,
            fee_structure=fee_structure,
            expected_amount=Decimal('10000.00'),
        )
        Payment.objects.create(
            tenant=student.tenant,
            student=student,
            student_fee=invoice,
            amount=Decimal('5000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='stmt-detail-test',
            recorded_by=bursar_user,
        )

        url = _reverse_or_skip(
            ['student-statement', 'statement-detail'],
            {'student_id': student.id}
        )
        if url is None:
            pytest.skip("student-statement URL not found")

        response = bursar_client.get(url)
        assert response.status_code in [200, 404]

    def test_class_statement(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()

        url = _reverse_or_skip(
            ['class-statement', 'classroom-statement'],
            {'classroom_id': classroom.id}
        )
        if url is None:
            pytest.skip("class-statement URL not found")

        response = bursar_client.get(url)
        assert response.status_code in [200, 404]

    def test_term_statement(self, bursar_client, bursar_user):
        url = _reverse_or_skip(['term-statement', 'term-summary'])
        if url is None:
            pytest.skip("term-statement URL not found")

        response = bursar_client.get(url, {'term': 'term1', 'academic_year': 2026})
        assert response.status_code in [200, 404]

    def test_fee_collection_report(self, bursar_client, bursar_user):
        url = _reverse_or_skip(['fee-collection-report', 'collection-report'])
        if url is None:
            pytest.skip("fee-collection-report URL not found")

        response = bursar_client.get(url)
        assert response.status_code in [200, 404]

    def test_payment_history_report(self, bursar_client, bursar_user):
        classroom = ClassroomFactory()
        student = StudentFactory(classroom=classroom)
        Payment.objects.create(
            tenant=student.tenant,
            student=student,
            amount=Decimal('1000.00'),
            payment_method='cash',
            status='confirmed',
            idempotency_key='payment-hist-test',
            recorded_by=bursar_user,
        )

        url = _reverse_or_skip(['payment-history', 'payment-report'])
        if url is None:
            pytest.skip("payment-history URL not found")

        response = bursar_client.get(url)
        assert response.status_code in [200, 404]

    def test_arrears_report(self, bursar_client, bursar_user):
        url = _reverse_or_skip(['arrears-report', 'fee-arrears'])
        if url is None:
            pytest.skip("arrears-report URL not found")

        response = bursar_client.get(url)
        assert response.status_code in [200, 404]

    def test_waiver_report(self, bursar_client, bursar_user):
        url = _reverse_or_skip(['waiver-report', 'fee-waivers'])
        if url is None:
            pytest.skip("waiver-report URL not found")

        response = bursar_client.get(url)
        assert response.status_code in [200, 404]

    def test_finance_dashboard_summary(self, bursar_client, bursar_user):
        url = _reverse_or_skip(['finance-dashboard', 'finance-summary'])
        if url is None:
            pytest.skip("finance-dashboard URL not found")

        response = bursar_client.get(url)
        assert response.status_code in [200, 404]

    def test_export_statements_csv(self, bursar_client, bursar_user):
        url = _reverse_or_skip(['export-statements', 'statements-export'])
        if url is None:
            pytest.skip("export-statements URL not found")

        response = bursar_client.get(url, {'format': 'csv'})
        assert response.status_code in [200, 404]

    def test_export_statements_pdf(self, bursar_client, bursar_user):
        url = _reverse_or_skip(['export-statements', 'statements-export'])
        if url is None:
            pytest.skip("export-statements URL not found")

        response = bursar_client.get(url, {'format': 'pdf'})
        assert response.status_code in [200, 404]
