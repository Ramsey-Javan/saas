from django.core.management.base import BaseCommand, CommandError

from tenants.models import Tenant
from timetabling.models import TimetableJob
from timetabling.services.solver import solve_timetable_job


class Command(BaseCommand):
    help = 'Run the timetable solver for a tenant/job from the command line.'

    def add_arguments(self, parser):
        parser.add_argument('tenant_id', type=int)
        parser.add_argument('--job-id', type=int)
        parser.add_argument('--term', default='term1')
        parser.add_argument('--academic-year', type=int, default=2026)

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(id=options['tenant_id']).first()
        if not tenant:
            raise CommandError('Tenant not found.')
        job = None
        if options['job_id']:
            job = TimetableJob.objects.filter(id=options['job_id'], tenant=tenant).first()
            if not job:
                raise CommandError('Timetable job not found for tenant.')
        else:
            job = TimetableJob.objects.create(
                tenant=tenant,
                term=options['term'],
                academic_year=options['academic_year'],
                status=TimetableJob.Status.RUNNING,
            )
        result = solve_timetable_job(job.id, tenant.id)
        self.stdout.write(self.style.SUCCESS(str(result)))
