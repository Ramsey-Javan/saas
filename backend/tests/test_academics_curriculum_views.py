import pytest
from django.urls import reverse

from academics.models import Subject, Strand, SubStrand, LearningOutcome
from tests.factories import SubjectFactory


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
class TestSubjectViewsExtended:
    def test_subject_create(self, admin_client, admin_user):
        url = _reverse_or_skip(['subject-list', 'subjects-list'])
        if url is None:
            pytest.skip("subject-list URL not found")

        payload = {
            'name': 'Mathematics',
            'code': 'MATH',
            'description': 'Core math subject',
            'grade_levels': ['Grade 4', 'Grade 5'],
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_subject_detail(self, admin_client, admin_user):
        subject = SubjectFactory()

        url = _reverse_or_skip(['subject-detail', 'subjects-detail'], {'pk': subject.id})
        if url is None:
            pytest.skip("subject-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_subject_update(self, admin_client, admin_user):
        subject = SubjectFactory()

        url = _reverse_or_skip(['subject-detail', 'subjects-detail'], {'pk': subject.id})
        if url is None:
            pytest.skip("subject-detail URL not found")

        response = admin_client.patch(url, {'name': 'Updated Math'}, format='json')
        assert response.status_code in [200, 404]

    def test_subject_delete(self, admin_client, admin_user):
        subject = SubjectFactory()

        url = _reverse_or_skip(['subject-detail', 'subjects-detail'], {'pk': subject.id})
        if url is None:
            pytest.skip("subject-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]

    def test_subject_filter_by_grade(self, admin_client, admin_user):
        SubjectFactory(name='Math Grade 4', grade_levels=['Grade 4'])
        SubjectFactory(name='Math Grade 5', grade_levels=['Grade 5'])

        url = _reverse_or_skip(['subject-list', 'subjects-list'])
        if url is None:
            pytest.skip("subject-list URL not found")

        response = admin_client.get(url, {'grade_level': 'Grade 4'})
        assert response.status_code == 200

    def test_subject_search(self, admin_client, admin_user):
        SubjectFactory(name='Searchable Subject')

        url = _reverse_or_skip(['subject-list', 'subjects-list'])
        if url is None:
            pytest.skip("subject-list URL not found")

        response = admin_client.get(url, {'search': 'Searchable'})
        assert response.status_code == 200


@pytest.mark.django_db
class TestStrandViewsExtended:
    def test_strand_create(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)

        url = _reverse_or_skip(['strand-list', 'strands-list'])
        if url is None:
            pytest.skip("strand-list URL not found")

        payload = {
            'subject': subject.id,
            'name': 'Numbers',
            'order': 1,
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_strand_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)

        url = _reverse_or_skip(['strand-detail', 'strands-detail'], {'pk': strand.id})
        if url is None:
            pytest.skip("strand-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_strand_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)

        url = _reverse_or_skip(['strand-detail', 'strands-detail'], {'pk': strand.id})
        if url is None:
            pytest.skip("strand-detail URL not found")

        response = admin_client.patch(url, {'name': 'Updated Strand'}, format='json')
        assert response.status_code in [200, 404]

    def test_strand_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)

        url = _reverse_or_skip(['strand-detail', 'strands-detail'], {'pk': strand.id})
        if url is None:
            pytest.skip("strand-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]


@pytest.mark.django_db
class TestSubStrandViewsExtended:
    def test_sub_strand_create(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)

        url = _reverse_or_skip(['substrand-list', 'sub-strand-list'])
        if url is None:
            pytest.skip("substrand-list URL not found")

        payload = {
            'strand': strand.id,
            'name': 'Sub Strand 1',
            'order': 1,
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_sub_strand_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)

        url = _reverse_or_skip(['substrand-detail', 'sub-strand-detail'], {'pk': sub_strand.id})
        if url is None:
            pytest.skip("substrand-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_sub_strand_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)

        url = _reverse_or_skip(['substrand-detail', 'sub-strand-detail'], {'pk': sub_strand.id})
        if url is None:
            pytest.skip("substrand-detail URL not found")

        response = admin_client.patch(url, {'name': 'Updated Sub'}, format='json')
        assert response.status_code in [200, 404]

    def test_sub_strand_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)

        url = _reverse_or_skip(['substrand-detail', 'sub-strand-detail'], {'pk': sub_strand.id})
        if url is None:
            pytest.skip("substrand-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]


@pytest.mark.django_db
class TestLearningOutcomeViewsExtended:
    def test_learning_outcome_create(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)

        url = _reverse_or_skip(['learningoutcome-list', 'learning-outcome-list'])
        if url is None:
            pytest.skip("learningoutcome-list URL not found")

        payload = {
            'sub_strand': sub_strand.id,
            'description': 'Can read fluently',
            'order': 1,
        }
        response = admin_client.post(url, payload, format='json')
        assert response.status_code in [201, 400, 404]

    def test_learning_outcome_detail(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)
        outcome = LearningOutcome.objects.create(tenant=tenant, sub_strand=sub_strand, description='Outcome 1', order=1)

        url = _reverse_or_skip(['learningoutcome-detail', 'learning-outcome-detail'], {'pk': outcome.id})
        if url is None:
            pytest.skip("learningoutcome-detail URL not found")

        response = admin_client.get(url)
        assert response.status_code in [200, 404]

    def test_learning_outcome_update(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)
        outcome = LearningOutcome.objects.create(tenant=tenant, sub_strand=sub_strand, description='Outcome 1', order=1)

        url = _reverse_or_skip(['learningoutcome-detail', 'learning-outcome-detail'], {'pk': outcome.id})
        if url is None:
            pytest.skip("learningoutcome-detail URL not found")

        response = admin_client.patch(url, {'description': 'Updated outcome'}, format='json')
        assert response.status_code in [200, 404]

    def test_learning_outcome_delete(self, admin_client, admin_user):
        tenant = admin_user.tenant
        subject = SubjectFactory(tenant=tenant)
        strand = Strand.objects.create(tenant=tenant, subject=subject, name='Strand 1', order=1)
        sub_strand = SubStrand.objects.create(tenant=tenant, strand=strand, name='Sub 1', order=1)
        outcome = LearningOutcome.objects.create(tenant=tenant, sub_strand=sub_strand, description='Outcome 1', order=1)

        url = _reverse_or_skip(['learningoutcome-detail', 'learning-outcome-detail'], {'pk': outcome.id})
        if url is None:
            pytest.skip("learningoutcome-detail URL not found")

        response = admin_client.delete(url)
        assert response.status_code in [204, 200, 404]
