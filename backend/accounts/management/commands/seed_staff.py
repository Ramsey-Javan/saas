"""
Dynamically seed teachers (and optionally support staff) for any school.

Usage:
    docker compose exec backend python manage.py seed_staff
    docker compose exec backend python manage.py seed_staff --tenant "Greenhill Academy" --teachers 45
    docker compose exec backend python manage.py seed_staff --tenant "Greenhill Academy" --teachers 40 --support 5

Interactive mode: if --tenant or --teachers are omitted, the command prompts
for them, so you can just run `python manage.py seed_staff` and answer.

- Creates the tenant automatically if the school doesn't exist yet.
- Idempotent within a run and safe across runs (skips emails that already
  exist; never creates a duplicate username).
- Teachers get 2 random subjects from the school's own Subject table
  ( warns if the school has no subjects yet ).
- All generated logins share one temporary password (override with --password).
"""
import random
import secrets

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import CustomUser, StaffProfile
from academics.models import Subject
from tenants.models import Tenant

FIRST_NAMES = [
    "Peter", "Mary", "John", "Grace", "Samuel", "Esther", "David", "Mercy", "Joseph", "Faith",
    "Brian", "Catherine", "James", "Agnes", "Emmanuel", "Beatrice", "Kevin", "Rose", "Daniel",
    "Jane", "Dennis", "Lucy", "Victor", "Sarah", "Anthony", "Winfred", "Patrick", "Lilian",
    "George", "Alice", "Michael", "Esther", "Collins", "Naomi", "Elijah", "Charity", "Moses",
    "Rebecca", "Isaac", "Dorcas", "Timothy", "Esther", "Nicholas", "Joyce", "Stephen", "Ruth",
    "Gabriel", "Hellen", "Francis", "Ann", "Bernard", "Caroline", "Felix", "Deborah", "Harrison",
    "Eunice", "Kennedy", "Faith", "Lawrence", "Margaret", "Nelson", "Phyllis", "Oscar", "Tabitha",
    "Raymond", "Vivian", "Stanley", "Zipporah", "Victor", "Irene", "Wycliffe", "Naomi", "Dennis",
    "Esther", "Brian", "Millicent", "Antony", "Sheila", "Erick", "Nancy", "Geoffrey", "Stella",
]

LAST_NAMES = [
    "Kamau", "Wanjiku", "Otieno", "Akinyi", "Kiplagat", "Nduta", "Omondi", "Chebet", "Mwangi",
    "Achieng", "Kiprono", "Mutua", "Njoroge", "Kilonzo", "Wafula", "Nyambura", "Maina",
    "Adhiambo", "Cheruiyot", "Wambui", "Korir", "Mbulwa", "Onyango", "Njeri", "Mutiso",
    "Kwamboka", "Wanyama", "Jeptoo", "Ochieng", "Macharia", "Kariuki", "Achieng", "Barasa",
    "Muthoni", "Ochieng", "Kosgei", "Wairimu", "Kiptoo", "Moraa", "Kimani", "Wekesa",
    "Atieno", "Rutto", "Makena", "Odhiambo", "Jepchirchir", "Mutua", "Wanjiru", "Too",
    "Mogaka", "Chepkoech", "Ouma", "Karanja", "Auma", "Mwangangi", "Kemunto", "Opondo",
    "Githinji", "Biwott", "Sifuna", "Langat", "Nyokabi", "Otieka", "Chepngeno", "Musyoka",
    "Wambua", "Kerubo", "Kipchoge", "Mbinda", "Odour", "Jelagat", "Kinyua", "Ogutu",
    "Nyongesa", "Mbai", "Koech", "Simiyu", "Kagwi", "Muthama", "Odera", "Chelangat", "Kabiru",
]

QUALIFICATIONS = [
    "B.Ed (Science)", "B.Ed (Arts - English)", "B.Ed (Arts - Kiswahili)",
    "B.Ed (Mathematics/Physics)", "B.Ed (Business Studies)", "B.Ed (Home Economics)",
    "B.Ed (Agriculture/Biology)", "B.Ed (Computer Studies)", "B.Ed (Physical Education)",
    "B.Ed (Early Childhood Education)", "B.Ed (Special Needs Education)",
    "B.Ed (Music)", "B.Ed (Fine Art)", "Dip. Education", "Dip. Early Childhood Development",
    "B.Ed (History/Geography)", "B.Ed (Chemistry)", "B.Ed (Religious Studies)",
    "B.Ed (Commerce/Economics)", "B.Sc (Statistics), PGDE",
]

SUPPORT_TITLES = [
    (StaffProfile.JobTitle.BURSAR, "Dip. Business Management / CPA I"),
    (StaffProfile.JobTitle.ACCOUNTANT, "B.Com (Accounting), CPA II"),
    (StaffProfile.JobTitle.COOK, "Certificate in Food Production"),
    (StaffProfile.JobTitle.CLEANER, "KCSE Certificate"),
    (StaffProfile.JobTitle.SECURITY, "Certificate in Security Management"),
    (StaffProfile.JobTitle.DRIVER, "Driving License Class BCE, Defensive Driving Cert"),
    (StaffProfile.JobTitle.LIBRARIAN, "Dip. Library & Information Science"),
    (StaffProfile.JobTitle.NURSE, "KRCHN (Registered Community Health Nurse)"),
]

DEFAULT_PASSWORD = "ChangeMe2026!"


def make_email(first, last, domain, used):
    base = f"{first.lower()}.{last.lower()}"
    candidate = f"{base}@{domain}"
    n = 2
    while candidate in used or CustomUser.objects.filter(email=candidate).exists():
        candidate = f"{base}{n}@{domain}"
        n += 1
    used.add(candidate)
    return candidate


class Command(BaseCommand):
    help = "Generate and seed teachers/support staff for any school (interactive or flagged)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", default=None, help="School (tenant) name.")
        parser.add_argument("--teachers", type=int, default=None, help="Number of teachers to generate.")
        parser.add_argument("--support", type=int, default=0, help="Number of support staff to generate.")
        parser.add_argument("--password", default=DEFAULT_PASSWORD,
                            help="Temporary password for all generated logins.")
        parser.add_argument("--no-login", action="store_true",
                            help="Create staff profiles WITHOUT user accounts.")

    def handle(self, *args, **options):
        # ── Interactive prompts for whatever wasn't passed as a flag ──
        tenant_name = options["tenant"] or input("School name: ").strip()
        if not tenant_name:
            self.stderr.write(self.style.ERROR("School name is required."))
            return
        teachers_count = options["teachers"]
        if teachers_count is None:
            raw = input("Number of teachers [45]: ").strip()
            teachers_count = int(raw) if raw else 45
        support_count = options["support"]

        password = options["password"]
        create_login = not options["no_login"]

        # ── Tenant: reuse or create ──
        tenant, created = Tenant.objects.get_or_create(
            name=tenant_name,
            defaults={
                "slug": slugify(tenant_name)[:50] or secrets.token_hex(4),
                "is_active": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"Tenant: {tenant.name}" + (" (created)" if created else " (existing)")
        ))

        school_subjects = list(Subject.objects.filter(tenant=tenant, is_active=True))
        if teachers_count and not school_subjects:
            self.stdout.write(self.style.WARNING(
                f"NOTE: {tenant.name} has no subjects yet - teachers will be created "
                f"without subject assignments. Add subjects first if you need them."
            ))

        domain = f"{slugify(tenant_name).replace('-', '')}.ac.ke"
        used_emails = set()
        stats = {"created": 0, "skipped": 0}
        rng = random.Random(f"{tenant_name}:{teachers_count}:{support_count}")  # reproducible per school

        def generate_person():
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            return first, last

        def seed_person(first, last, job_title, quals, subjects):
            email = make_email(first, last, domain, used_emails)
            phone = f"+2547{rng.randint(10000000, 99999999)}"
            id_number = str(rng.randint(10000000, 49999999))

            if create_login and CustomUser.objects.filter(email=email).exists():
                self.stdout.write(f"  SKIP (account exists): {email}")
                stats["skipped"] += 1
                return

            with transaction.atomic():
                user = None
                if create_login:
                    user = CustomUser.objects.create_user(
                        email=email,
                        password=password,
                        username=email,
                        first_name=first,
                        last_name=last,
                        phone_number=phone,
                        role=(CustomUser.Role.TEACHER
                              if job_title == StaffProfile.JobTitle.TEACHER
                              else CustomUser.Role.SUPPORT_STAFF),
                        tenant=tenant,
                    )
                profile = StaffProfile.objects.create(
                    tenant=tenant,
                    user=user,
                    first_name=first,
                    last_name=last,
                    phone=phone,
                    email=email,
                    job_title=job_title,
                    id_number=id_number,
                    qualifications=quals,
                    start_date=timezone.localdate(),
                )
                if subjects:
                    profile.subjects_qualified.set(subjects)

            stats["created"] += 1
            login_note = f" login={email}" if create_login else " (no login)"
            subj_note = f" subjects={[s.name for s in subjects]}" if subjects else ""
            self.stdout.write(self.style.SUCCESS(
                f"  {profile.employee_number}  {first} {last} [{profile.get_job_title_display()}]{subj_note}{login_note}"
            ))

        # ── Teachers ──
        for i in range(teachers_count):
            first, last = generate_person()
            quals = rng.choice(QUALIFICATIONS)
            subjects = rng.sample(school_subjects, k=min(2, len(school_subjects))) if school_subjects else []
            seed_person(first, last, StaffProfile.JobTitle.TEACHER, quals, subjects)

        # ── Support staff ──
        for i in range(support_count):
            first, last = generate_person()
            job_title, quals = rng.choice(SUPPORT_TITLES)
            seed_person(first, last, job_title, quals, [])

        self.stdout.write(self.style.SUCCESS(
            f"\nDone: {stats['created']} staff created, {stats['skipped']} skipped."
        ))
        if create_login:
            self.stdout.write(f"Temporary password for all logins: {password}")
        self.stdout.write(f"Email domain used: @{domain}")
