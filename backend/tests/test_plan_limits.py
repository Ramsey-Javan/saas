from django.urls import reverse

from students.models import Student
from tests.factories import ClassroomFactory, StudentFactory


def test_starter_plan_blocks_student_creation_after_limit(admin_client, admin_user, db):
    tenant = admin_user.tenant
    tenant.plan = 'starter'
    tenant.save(update_fields=['plan'])
    classroom = ClassroomFactory(tenant=tenant)

    for index in range(400):
        StudentFactory(tenant=tenant, classroom=classroom, admission_number=f'STARTER/{index:04d}')

    payload = {
        'first_name': 'New',
        'last_name': 'Student',
        'admission_number': 'STARTER/0400',
        'date_of_birth': '2015-01-01',
        'gender': 'M',
        'classroom': classroom.id,
    }

    response = admin_client.post(reverse('student-list'), payload, format='json')

    assert response.status_code == 400
    message = response.data['message']
    assert 'Starter' in message
    assert '400' in message
    assert 'plan' in message.lower()
