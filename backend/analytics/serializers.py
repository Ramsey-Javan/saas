"""Query-parameter validation for analytics endpoints.

Not model serializers -- every response is a hand-shaped dict built in
services/. These exist purely so a missing/malformed param comes back as
a clean 400 with a field-level message.

Canonical term values are 'term1'/'term2'/'term3', matching
ExamSetup.term's own choices exactly -- the frontend is responsible for
converting any human-readable label ("Term 2") into this canonical form
before calling the API.
"""
from rest_framework import serializers

TERM_CHOICES = ['term1', 'term2', 'term3']


class AcademicYearFilterSerializer(serializers.Serializer):
    academic_year = serializers.IntegerField()


class TermSummaryFilterSerializer(serializers.Serializer):
    academic_year = serializers.IntegerField()
    term = serializers.ChoiceField(choices=TERM_CHOICES)


class ExamFilterSerializer(serializers.Serializer):
    exam_id = serializers.IntegerField()


class SubjectAnalysisFilterSerializer(serializers.Serializer):
    exam_id = serializers.IntegerField()
    subject_id = serializers.IntegerField(required=False, allow_null=True)


class StudentProfileFilterSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    academic_year = serializers.IntegerField()


class StudentReportCardFilterSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    term = serializers.ChoiceField(choices=TERM_CHOICES)
    academic_year = serializers.IntegerField()


class ClassroomYearFilterSerializer(serializers.Serializer):
    classroom_id = serializers.IntegerField()
    academic_year = serializers.IntegerField()


class ClassroomTermFilterSerializer(serializers.Serializer):
    classroom_id = serializers.IntegerField()
    term = serializers.ChoiceField(choices=TERM_CHOICES)
    academic_year = serializers.IntegerField()


class GradeDistributionFilterSerializer(serializers.Serializer):
    classroom_id = serializers.IntegerField()
    exam_type = serializers.ChoiceField(choices=['opener', 'midterm', 'endterm', 'mock', 'other'])
    term = serializers.ChoiceField(choices=TERM_CHOICES)
    academic_year = serializers.IntegerField()


class CohortReferenceFilterSerializer(serializers.Serializer):
    classroom_id = serializers.IntegerField()
    subject_id = serializers.IntegerField()
    term = serializers.ChoiceField(choices=TERM_CHOICES)
    academic_year = serializers.IntegerField()


class SubjectSchoolAnalysisFilterSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    term = serializers.ChoiceField(choices=TERM_CHOICES)
    academic_year = serializers.IntegerField()


class EarlyWarningFilterSerializer(serializers.Serializer):
    term = serializers.ChoiceField(choices=TERM_CHOICES)
    academic_year = serializers.IntegerField()
    classroom_id = serializers.IntegerField(required=False, allow_null=True)


class SchoolClassroomsFilterSerializer(serializers.Serializer):
    academic_year = serializers.IntegerField(required=True, min_value=2000, max_value=2100)
    term = serializers.ChoiceField(
        choices=[('term1', 'Term 1'), ('term2', 'Term 2'), ('term3', 'Term 3')],
        required=True,
    )