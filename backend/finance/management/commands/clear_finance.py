from django.core.management.base import BaseCommand
from django.db import connection
from finance.models import StudentFee, Payment, FeeStructure, StudentWaiver


class Command(BaseCommand):
    help = 'Clear all finance data (StudentFee, Payment, FeeStructure, StudentWaiver)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion without prompt',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            confirm = input(
                'This will DELETE all StudentFee, Payment, FeeStructure, and StudentWaiver records. '
                'Are you sure? (yes/no): '
            )
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled.'))
                return

        # Delete in order of dependencies
        student_fee_count = StudentFee.objects.count()
        payment_count = Payment.objects.count()
        fee_structure_count = FeeStructure.objects.count()
        waiver_count = StudentWaiver.objects.count()

        self.stdout.write(f'Deleting {payment_count} Payment records...')
        Payment.objects.all().delete()

        self.stdout.write(f'Deleting {student_fee_count} StudentFee records...')
        StudentFee.objects.all().delete()

        self.stdout.write(f'Deleting {waiver_count} StudentWaiver records...')
        StudentWaiver.objects.all().delete()

        self.stdout.write(f'Deleting {fee_structure_count} FeeStructure records...')
        FeeStructure.objects.all().delete()

        # Reset sequences
        with connection.cursor() as cursor:
            tables = ['finance_payment', 'finance_studentfee', 'finance_feestructure', 'finance_studentwaiver']
            for table in tables:
                cursor.execute(f'ALTER SEQUENCE {table}_id_seq RESTART WITH 1;')

        self.stdout.write(self.style.SUCCESS('✓ All finance data cleared successfully!'))
