from decimal import Decimal

import factory
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker()


class TenantFactory(DjangoModelFactory):
    class Meta:
        model = 'tenants.Tenant'

    name = factory.Sequence(lambda n: f'Test School {n}')
    domain = factory.LazyAttribute(
        lambda o: f'http://{o.name.lower().replace(" ", "-")}.localhost'
    )
    email = factory.LazyAttribute(
        lambda o: f'admin@{o.name.lower().replace(" ", "")}.co.ke'
    )
    phone = '0700000000'
    primary_color = '#1e40af'
    secondary_color = '#ffffff'
    accent_color = '#fbbc04'
    is_active = True


class UserFactory(DjangoModelFactory):
    class Meta:
        model = 'accounts.CustomUser'

    email = factory.Sequence(lambda n: f'user{n}@test.co.ke')
    username = factory.LazyAttribute(lambda o: o.email)
    first_name = factory.LazyFunction(fake.first_name)
    last_name = factory.LazyFunction(fake.last_name)
    role = 'teacher'
    tenant = factory.SubFactory(TenantFactory)
    is_staff = False

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        obj.set_password(extracted or 'testpass123')
        if create:
            obj.save()


class AdminUserFactory(UserFactory):
    class Meta:
        skip_postgeneration_save = True

    role = 'admin'
    is_staff = True


class TeacherUserFactory(UserFactory):
    class Meta:
        skip_postgeneration_save = True

    role = 'teacher'


class BursarUserFactory(UserFactory):
    role = 'bursar'


class SuperAdminUserFactory(UserFactory):
    role = 'superadmin'
    tenant = None
    is_staff = True
    is_superuser = True


class ClassroomFactory(DjangoModelFactory):
    class Meta:
        model = 'students.Classroom'

    tenant = factory.SubFactory(TenantFactory)
    name = factory.Sequence(lambda n: f'Grade {n % 8 + 1}')
    grade_level = factory.LazyAttribute(lambda o: o.name)
    stream = factory.Sequence(lambda n: f'Stream {n % 3}')
    academic_year = '2026'
    capacity = 40
    is_active = True


class GuardianFactory(DjangoModelFactory):
    class Meta:
        model = 'students.Guardian'

    first_name = factory.LazyFunction(fake.first_name)
    last_name = factory.LazyFunction(fake.last_name)
    phone = factory.Sequence(lambda n: f'07{n:08d}'[:10])
    relationship = 'father'
    is_primary = True


class StudentFactory(DjangoModelFactory):
    class Meta:
        model = 'students.Student'

    tenant = factory.SubFactory(TenantFactory)
    admission_number = factory.Sequence(lambda n: f'ADM/TEST/{n:04d}')
    first_name = factory.LazyFunction(fake.first_name)
    last_name = factory.LazyFunction(fake.last_name)
    gender = 'M'
    date_of_birth = '2015-01-01'
    classroom = factory.SubFactory(ClassroomFactory, tenant=factory.SelfAttribute('..tenant'))
    primary_guardian = factory.SubFactory(GuardianFactory)
    is_active = True


class StaffProfileFactory(DjangoModelFactory):
    class Meta:
        model = 'accounts.StaffProfile'

    tenant = factory.SubFactory(TenantFactory)
    user = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))
    employee_number = factory.Sequence(lambda n: f'EMP/TEST/{n:04d}')
    first_name = factory.LazyFunction(fake.first_name)
    last_name = factory.LazyFunction(fake.last_name)
    phone = factory.Sequence(lambda n: f'07{n:08d}'[:10])
    email = factory.LazyAttribute(lambda o: f'{o.first_name.lower()}.{o.last_name.lower()}@test.co.ke')
    job_title = 'teacher'
    department = 'teaching'
    id_number = factory.Sequence(lambda n: f'ID{n:06d}')
    qualifications = 'BEd'
    start_date = '2026-01-01'
    employment_status = 'active'
    is_active = True
    created_by = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))


class SubjectFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.Subject'

    tenant = factory.SubFactory(TenantFactory)
    name = factory.Sequence(lambda n: f'Subject {n}')
    code = factory.Sequence(lambda n: f'S{n:03d}')
    description = 'Test subject'
    grade_levels = factory.LazyFunction(lambda: ['Grade 4'])
    is_preloaded = False
    is_active = True
    order = 0


class StrandFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.Strand'

    tenant = factory.SubFactory(TenantFactory)
    subject = factory.SubFactory(SubjectFactory, tenant=factory.SelfAttribute('..tenant'))
    name = factory.Sequence(lambda n: f'Strand {n}')
    order = 0


class SubStrandFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.SubStrand'

    tenant = factory.SubFactory(TenantFactory)
    strand = factory.SubFactory(StrandFactory, tenant=factory.SelfAttribute('..tenant'))
    name = factory.Sequence(lambda n: f'SubStrand {n}')
    order = 0


class LearningOutcomeFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.LearningOutcome'

    tenant = factory.SubFactory(TenantFactory)
    sub_strand = factory.SubFactory(SubStrandFactory, tenant=factory.SelfAttribute('..tenant'))
    description = factory.LazyFunction(fake.sentence)
    order = 0


class ExamConfigFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.ExamConfig'

    tenant = factory.SubFactory(TenantFactory)
    be_min = 0
    be_max = 29
    ae_min = 30
    ae_max = 49
    me_min = 50
    me_max = 74
    ee_min = 75
    ee_max = 100
    updated_by = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))


class ExamSetupFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.ExamSetup'

    tenant = factory.SubFactory(TenantFactory)
    name = factory.Sequence(lambda n: f'Exam {n}')
    exam_type = 'opener'
    classroom = factory.SubFactory(ClassroomFactory, tenant=factory.SelfAttribute('..tenant'))
    term = 'term1'
    academic_year = 2026
    start_date = '2026-01-10'
    end_date = '2026-01-20'
    instructions = 'Answer all questions.'
    is_active = True
    created_by = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))


class ExamSubjectFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.ExamSubject'

    tenant = factory.SubFactory(TenantFactory)
    exam = factory.SubFactory(ExamSetupFactory, tenant=factory.SelfAttribute('..tenant'))
    subject = factory.SubFactory(SubjectFactory, tenant=factory.SelfAttribute('..tenant'))
    total_marks = 100
    teacher = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))


class ExamResultFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.ExamResult'

    tenant = factory.SubFactory(TenantFactory)
    exam_subject = factory.SubFactory(ExamSubjectFactory, tenant=factory.SelfAttribute('..tenant'))
    student = factory.SubFactory(StudentFactory, tenant=factory.SelfAttribute('..tenant'))
    marks = Decimal('65.00')
    percentage = Decimal('65.00')
    cbc_level = 'ME'
    is_overridden = False
    override_reason = ''
    entered_by = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))


class ExamCBCSyncFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.ExamCBCSync'

    tenant = factory.SubFactory(TenantFactory)
    exam = factory.SubFactory(ExamSetupFactory, tenant=factory.SelfAttribute('..tenant'))
    synced_by = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))
    records_synced = 0
    records_skipped = 0


class AttendanceSessionFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.AttendanceSession'

    tenant = factory.SubFactory(TenantFactory)
    classroom = factory.SubFactory(ClassroomFactory, tenant=factory.SelfAttribute('..tenant'))
    subject = factory.SubFactory(SubjectFactory, tenant=factory.SelfAttribute('..tenant'))
    teacher = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))
    date = '2026-01-12'
    session_type = 'daily'
    term = 'term1'
    academic_year = 2026
    notes = ''
    is_locked = False


class AttendanceRecordFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.AttendanceRecord'

    tenant = factory.SubFactory(TenantFactory)
    session = factory.SubFactory(AttendanceSessionFactory, tenant=factory.SelfAttribute('..tenant'))
    student = factory.SubFactory(StudentFactory, tenant=factory.SelfAttribute('..tenant'))
    status = 'P'
    remarks = ''


class FeeStructureFactory(DjangoModelFactory):
    class Meta:
        model = 'finance.FeeStructure'

    tenant = factory.SubFactory(TenantFactory)
    classroom = factory.SubFactory(ClassroomFactory, tenant=factory.SelfAttribute('..tenant'))
    term = 'term1'
    academic_year = 2026
    base_amount = Decimal('15000.00')
    due_date = '2026-02-01'
    late_penalty_amount = Decimal('0.00')
    late_penalty_days = 0
    is_active = True


class StudentFeeFactory(DjangoModelFactory):
    class Meta:
        model = 'finance.StudentFee'

    tenant = factory.SubFactory(TenantFactory)
    student = factory.SubFactory(StudentFactory, tenant=factory.SelfAttribute('..tenant'))
    fee_structure = factory.LazyAttribute(lambda o: FeeStructureFactory(tenant=o.tenant, classroom=o.student.classroom))
    expected_amount = Decimal('15000.00')
    waived_amount = Decimal('0.00')
    carried_forward = Decimal('0.00')
    penalty_amount = Decimal('0.00')
    credit = Decimal('0.00')
    status = 'unpaid'
    due_date = '2026-02-01'
    paid_amount = Decimal('0.00')
    waiver_reason = ''


class PaymentFactory(DjangoModelFactory):
    class Meta:
        model = 'finance.Payment'

    tenant = factory.SubFactory(TenantFactory)
    student = factory.SubFactory(StudentFactory, tenant=factory.SelfAttribute('..tenant'))
    student_fee = factory.LazyAttribute(lambda o: StudentFeeFactory(tenant=o.tenant, student=o.student))
    amount = Decimal('1000.00')
    payment_method = 'cash'
    status = 'confirmed'
    mpesa_receipt_number = ''
    mpesa_checkout_request_id = ''
    idempotency_key = factory.Sequence(lambda n: f'idem-{n}')
    recorded_by = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))
    notes = ''


class ReceiptFactory(DjangoModelFactory):
    class Meta:
        model = 'finance.Receipt'

    tenant = factory.SubFactory(TenantFactory)
    student = factory.SubFactory(StudentFactory, tenant=factory.SelfAttribute('..tenant'))
    payment = factory.LazyAttribute(lambda o: PaymentFactory(tenant=o.tenant, student=o.student))
    amount = Decimal('1000.00')
    payment_method = 'cash'
    term = 'term1'
    academic_year = '2026'
    issued_by = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))


class WaiverPolicyFactory(DjangoModelFactory):
    class Meta:
        model = 'finance.WaiverPolicy'

    tenant = factory.SubFactory(TenantFactory)
    category = 'partial'
    discount_type = 'percentage'
    discount_value = Decimal('50.00')
    is_active = True
    description = 'Test waiver'
    created_by = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))


class StudentWaiverFactory(DjangoModelFactory):
    class Meta:
        model = 'finance.StudentWaiver'

    tenant = factory.SubFactory(TenantFactory)
    student = factory.SubFactory(StudentFactory, tenant=factory.SelfAttribute('..tenant'))
    policy = factory.LazyAttribute(lambda o: WaiverPolicyFactory(tenant=o.tenant))
    approved_by = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))
    valid_from_term = 'term1'
    valid_from_year = 2026
    valid_until_term = ''
    valid_until_year = None
    notes = ''
    is_active = True


class MessageTemplateFactory(DjangoModelFactory):
    class Meta:
        model = 'communication.MessageTemplate'

    tenant = factory.SubFactory(TenantFactory)
    name = factory.Sequence(lambda n: f'Template {n}')
    category = 'general'
    channel = 'sms'
    subject = factory.Sequence(lambda n: f'Subject {n}')
    body = 'Hello {{student_name}}'
    is_active = True
    created_by = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))


class AnnouncementFactory(DjangoModelFactory):
    class Meta:
        model = 'communication.Announcement'

    tenant = factory.SubFactory(TenantFactory)
    title = factory.Sequence(lambda n: f'Announcement {n}')
    body = 'Hello class'
    template = factory.SubFactory(MessageTemplateFactory, tenant=factory.SelfAttribute('..tenant'))
    template_vars = factory.LazyFunction(dict)
    channels = factory.LazyFunction(lambda: ['sms'])
    recipient_type = 'school'
    recipient_class = None
    recipient_grade = ''
    recipient_user = None
    send_immediately = True
    is_recurring = False
    recurrence_rule = factory.LazyFunction(dict)
    status = 'draft'
    sent_by = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))


class MessageLogFactory(DjangoModelFactory):
    class Meta:
        model = 'communication.MessageLog'

    tenant = factory.SubFactory(TenantFactory)
    announcement = factory.SubFactory(AnnouncementFactory, tenant=factory.SelfAttribute('..tenant'))
    channel = 'sms'
    recipient_phone = '0700000000'
    recipient_email = ''
    recipient_name = factory.LazyFunction(fake.name)
    message_body = 'Hello'
    status = 'sent'
    provider_message_id = 'msg-1'
    provider_cost = 'KES 0.80'
    failure_reason = ''


class SMSLogFactory(DjangoModelFactory):
    class Meta:
        model = 'communication.SMSLog'

    tenant = factory.SubFactory(TenantFactory)
    recipient_phone = '0700000000'
    message = 'Hello'
    status = 'sent'
    provider = 'africas_talking'
    reference_id = factory.Sequence(lambda n: f'ref-{n}')
    error_message = ''


class NationalExamSessionFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.NationalExamSession'

    tenant = factory.SubFactory(TenantFactory)
    name = 'KPSEA'
    academic_year = 2026
    classroom = factory.SubFactory(ClassroomFactory, tenant=factory.SelfAttribute('..tenant'))
    centre_number = '12345'
    centre_name = 'Test Centre'
    exam_date = '2026-10-01'
    is_results_entered = False
    notes = ''
    created_by = factory.SubFactory(UserFactory, tenant=factory.SelfAttribute('..tenant'))


class NationalExamCandidateFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.NationalExamCandidate'

    tenant = factory.SubFactory(TenantFactory)
    session = factory.SubFactory(NationalExamSessionFactory, tenant=factory.SelfAttribute('..tenant'))
    student = factory.SubFactory(StudentFactory, tenant=factory.SelfAttribute('..tenant'))
    index_number = factory.Sequence(lambda n: f'IDX{n:05d}')
    is_registered = True
    registration_confirmed = True
    special_needs = ''


class NationalExamResultFactory(DjangoModelFactory):
    class Meta:
        model = 'academics.NationalExamResult'

    tenant = factory.SubFactory(TenantFactory)
    candidate = factory.SubFactory(NationalExamCandidateFactory, tenant=factory.SelfAttribute('..tenant'))
    subject = factory.SubFactory(SubjectFactory, tenant=factory.SelfAttribute('..tenant'))
    marks = Decimal('70.00')
    total_marks = 100
    grade = 'ME'
    remarks = ''
