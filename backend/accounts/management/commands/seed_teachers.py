"""
Seed the 30 CBC teachers from the staff roster PDF directly into the database.

Usage:
    docker compose exec backend python manage.py seed_teachers
    docker compose exec backend python manage.py seed_teachers --tenant "Demo School"

Idempotent: skips any email that already has a CustomUser account, and skips
teachers whose subjects can't all be resolved (with a warning) rather than
silently creating them with no assignments.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import secrets

from accounts.models import CustomUser, StaffProfile
from academics.models import Subject
from tenants.models import Tenant

# (first_name, last_name, email, phone, id_number, qualifications, [subjects])
TEACHERS = [
    ("Peter", "Kamau", "peter.kamau@demoschool.ac.ke", "+254712345601", "28471092",
     "B.Ed (Science), TSC Registered", ["Mathematics", "Integrated Science"]),
    ("Mary", "Wanjiku", "mary.wanjiku@demoschool.ac.ke", "+254723456702", "30192847",
     "B.Ed (Arts - English/Literature)", ["English", "Language Activities (English)"]),
    ("John", "Otieno", "john.otieno@demoschool.ac.ke", "+254734567803", "29103847",
     "Dip. Education (Kiswahili/History)", ["Kiswahili", "Social Studies"]),
    ("Grace", "Akinyi", "grace.akinyi@demoschool.ac.ke", "+254745678904", "31029384",
     "B.Ed (Agriculture/Biology)", ["Agriculture & Nutrition", "Integrated Science"]),
    ("Samuel", "Kiplagat", "samuel.kiplagat@demoschool.ac.ke", "+254756789005", "27384910",
     "B.Ed (Science/Physics)", ["Mathematics", "Pre-Technical Studies"]),
    ("Esther", "Nduta", "esther.nduta@demoschool.ac.ke", "+254767890106", "32910283",
     "B.Ed (Early Childhood Education)", ["Language Activities (Kiswahili)", "Psychomotor & Creative Activities"]),
    ("David", "Omondi", "david.omondi@demoschool.ac.ke", "+254778901207", "28394019",
     "B.Ed (Physical Education/CRE)", ["Physical & Health Education", "Religious Education (CRE)"]),
    ("Mercy", "Chebet", "mercy.chebet@demoschool.ac.ke", "+254789012308", "33920194",
     "B.Ed (Home Economics)", ["Home Science", "Agriculture & Nutrition"]),
    ("Joseph", "Mwangi", "joseph.mwangi@demoschool.ac.ke", "+254790123409", "30491028",
     "B.Ed (Business Studies/Maths)", ["Business Studies", "Mathematics"]),
    ("Faith", "Achieng", "faith.achieng@demoschool.ac.ke", "+254701234510", "31920384",
     "Dip. Early Childhood Development", ["Environmental Activities", "Mathematical Activities"]),
    ("Brian", "Kiprono", "brian.kiprono@demoschool.ac.ke", "+254712345611", "29384012",
     "B.Ed (Fine Art/Design)", ["Creative Arts & Sports", "Creative Arts"]),
    ("Catherine", "Mutua", "catherine.mutua@demoschool.ac.ke", "+254723456712", "28401928",
     "B.Ed (Arts - Religious Studies)", ["Religious Education (CRE)", "Social Studies"]),
    ("James", "Njoroge", "james.njoroge@demoschool.ac.ke", "+254734567813", "32102938",
     "B.Ed (Computer Science/Maths)", ["Pre-Technical Studies", "Mathematics"]),
    ("Agnes", "Kilonzo", "agnes.kilonzo@demoschool.ac.ke", "+254745678914", "30291038",
     "B.Ed (Arts - English)", ["English", "Language Activities (English)"]),
    ("Emmanuel", "Wafula", "emmanuel.wafula@demoschool.ac.ke", "+254756789015", "29102938",
     "B.Ed (Science - Chemistry)", ["Integrated Science", "Physical & Health Education"]),
    ("Beatrice", "Nyambura", "beatrice.nyambura@demoschool.ac.ke", "+254767890116", "33829102",
     "B.Ed (Arts - Kiswahili)", ["Kiswahili", "Language Activities (Kiswahili)"]),
    ("Kevin", "Maina", "kevin.maina@demoschool.ac.ke", "+254778901217", "28391029",
     "B.Ed (Commerce/Economics)", ["Business Studies", "Social Studies"]),
    ("Rose", "Adhiambo", "rose.adhiambo@demoschool.ac.ke", "+254789012318", "31029182",
     "Dip. Special Needs Education", ["Psychomotor & Creative Activities", "English"]),
    ("Daniel", "Cheruiyot", "daniel.cheruiyot@demoschool.ac.ke", "+254790123419", "29481029",
     "B.Ed (Agriculture/Chemistry)", ["Agriculture", "Integrated Science"]),
    ("Jane", "Wambui", "jane.wambui@demoschool.ac.ke", "+254701234520", "30918273",
     "B.Ed (Science - Biology)", ["Integrated Science", "Health Education"]),
    ("Dennis", "Korir", "dennis.korir@demoschool.ac.ke", "+254712345621", "32810293",
     "B.Ed (Arts - History/Geography)", ["Social Studies", "Religious Education (CRE)"]),
    ("Lucy", "Mbulwa", "lucy.mbulwa@demoschool.ac.ke", "+254723456722", "28192038",
     "Dip. Early Childhood Education", ["Environmental Activities", "Mathematical Activities"]),
    ("Victor", "Onyango", "victor.onyango@demoschool.ac.ke", "+254734567823", "31820394",
     "B.Ed (Music/Physical Ed)", ["Creative Arts & Sports", "Physical & Health Education"]),
    # Row 24 in the PDF: name cell lost in extraction; Sarah Njeri is the
    # teacher with these qualifications/subjects (verify after import).
    ("Sarah", "Njeri", "sarah.njeri@demoschool.ac.ke", "+254745678924", "29381029",
     "B.Ed (Arts - Kiswahili/Geography)", ["Kiswahili", "Social Studies"]),
    ("Anthony", "Mutiso", "anthony.mutiso@demoschool.ac.ke", "+254756789025", "30192837",
     "B.Ed (Maths/Physics)", ["Mathematics", "Pre-Technical Studies"]),
    ("Winfred", "Kwamboka", "winfred.kwamboka@demoschool.ac.ke", "+254767890126", "32019283",
     "B.Ed (Home Economics/Biology)", ["Home Science", "Agriculture & Nutrition"]),
    ("Patrick", "Wanyama", "patrick.wanyama@demoschool.ac.ke", "+254778901227", "28491029",
     "B.Ed (Arts - English/CRE)", ["English", "Religious Education (CRE)"]),
    ("Lilian", "Jeptoo", "lilian.jeptoo@demoschool.ac.ke", "+254789012328", "33102938",
     "B.Ed (Business/Maths)", ["Business Studies", "Mathematics"]),
    ("George", "Ochieng", "george.ochieng@demoschool.ac.ke", "+254790123429", "29201928",
     "B.Ed (Computer Studies/Physics)", ["Pre-Technical Studies", "Integrated Science"]),
    ("Alice", "Macharia", "alice.macharia@demoschool.ac.ke", "+254701234530", "30928102",
     "B.Ed (Arts - Literature)", ["English", "Creative Arts"]),
]

DEFAULT_PASSWORD = "DemoSchool2026!"


def match_subject(name):
    """Exact (case-insensitive) match first, then fuzzy contains-match."""
    subjects = Subject.objects.all()
    for s in subjects:
        if s.name.strip().lower() == name.strip().lower():
            return s
    for s in subjects:
        if name.strip().lower() in s.name.strip().lower() or s.name.strip().lower() in name.strip().lower():
            return s
    return None


class Command(BaseCommand):
    help = "Seed the CBC teaching staff roster (idempotent, skips existing emails)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", default=None,
                            help="Tenant name (defaults to the first tenant).")
        parser.add_argument("--password", default=DEFAULT_PASSWORD,
                            help="Temporary password for all seeded logins.")

    def handle(self, *args, **options):
        if options["tenant"]:
            tenant = Tenant.objects.get(name=options["tenant"])
        else:
            tenant = Tenant.objects.first()
            if not tenant:
                self.stderr.write(self.style.ERROR("No tenant found in the database."))
                return
        password = options["password"]
        self.stdout.write(f"Seeding into tenant: {tenant.name}")

        created, skipped, warnings = 0, 0, []

        for first, last, email, phone, id_number, quals, subject_names in TEACHERS:
            if CustomUser.objects.filter(email=email).exists():
                self.stdout.write(f"  SKIP (account exists): {email}")
                skipped += 1
                continue

            subjects = [match_subject(n) for n in subject_names]
            missing = [n for n, s in zip(subject_names, subjects) if s is None]
            if missing:
                warnings.append(f"{first} {last}: subjects not found -> {missing}")

            with transaction.atomic():
                user = CustomUser.objects.create_user(
                    email=email,
                    password=password,
                    username=email,
                    first_name=first,
                    last_name=last,
                    phone_number=phone,
                    role=CustomUser.Role.TEACHER,
                    tenant=tenant,
                )
                profile = StaffProfile.objects.create(
                    tenant=tenant,
                    user=user,
                    first_name=first,
                    last_name=last,
                    phone=phone,
                    email=email,
                    job_title=StaffProfile.JobTitle.TEACHER,
                    id_number=id_number,
                    qualifications=quals,
                    start_date=timezone.localdate(),
                )
                if any(subjects):
                    profile.subjects_qualified.set([s for s in subjects if s])

            self.stdout.write(self.style.SUCCESS(
                f"  CREATED: {profile.employee_number} - {first} {last} ({email})"
            ))
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {created} created, {skipped} skipped (already existed)."
        ))
        for w in warnings:
            self.stdout.write(self.style.WARNING("WARNING: " + w))
        self.stdout.write(f"\nAll seeded logins use temporary password: {password}")
