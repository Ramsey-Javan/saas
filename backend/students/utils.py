import csv
import io
import re
from datetime import date
from django.db import transaction
from django.utils.dateparse import parse_date
from .models import Student, Guardian, Classroom

GRADE_SEQUENCE = [
    'PP1',
    'PP2',
    'Grade 1',
    'Grade 2',
    'Grade 3',
    'Grade 4',
    'Grade 5',
    'Grade 6',
    'Grade 7',
    'Grade 8',
    'Grade 9',
]


def _normalize_classroom_name(value):
    return ' '.join((value or '').split()).lower()


def _resolve_grade_level(classroom):
    values = [
        classroom.grade_level,
        classroom.name,
        str(classroom),
    ]
    for value in values:
        normalized = ' '.join((value or '').split())
        if normalized in GRADE_SEQUENCE:
            return normalized

        match = re.search(r'\bgrade\s+([1-9])\b', normalized, re.IGNORECASE)
        if match:
            return f'Grade {match.group(1)}'

        match = re.search(r'\bpp\s*([12])\b', normalized, re.IGNORECASE)
        if match:
            return f'PP{match.group(1)}'

    return None


def get_or_create_classroom(classroom_name, tenant):
    """
    Resolve classroom names from CSV values like "Grade 4 West".
    Existing classrooms store the grade in name/grade_level and stream separately.
    """
    raw_name = ' '.join(classroom_name.split())
    normalized_name = _normalize_classroom_name(raw_name)

    classrooms = Classroom.objects.filter(tenant=tenant)
    for classroom in classrooms:
        if _normalize_classroom_name(str(classroom)) == normalized_name:
            return classroom, False
        if _normalize_classroom_name(classroom.name) == normalized_name:
            return classroom, False

    parts = raw_name.split()
    if len(parts) < 2:
        return None, False

    stream = parts[-1]
    grade_name = ' '.join(parts[:-1])
    classroom = classrooms.filter(
        name__iexact=grade_name,
        stream__iexact=stream,
    ).first()

    if classroom:
        return classroom, False

    classroom = Classroom.objects.create(
        tenant=tenant,
        name=grade_name,
        grade_level=grade_name,
        stream=stream,
        academic_year=str(date.today().year),
    )
    return classroom, True


def _next_academic_year(value):
    try:
        return str(int(value) + 1)
    except (TypeError, ValueError):
        return str(date.today().year + 1)


def promote_all_students_to_next_grade(tenant):
    """
    Promote active students in one tenant to the next grade.
    Grade 9 students are archived as graduated.
    """
    promoted_count = 0
    graduated_count = 0
    skipped = []
    created_classrooms = {}

    students = Student.objects.filter(
        tenant=tenant,
        is_active=True,
        status=Student.Status.ACTIVE,
    ).select_related('classroom').order_by('id')

    with transaction.atomic():
        for student in students:
            classroom = student.classroom
            if not classroom:
                skipped.append({
                    'student_id': student.id,
                    'admission_number': student.admission_number,
                    'reason': 'Student has no classroom',
                })
                continue

            current_grade = _resolve_grade_level(classroom)
            if not current_grade:
                skipped.append({
                    'student_id': student.id,
                    'admission_number': student.admission_number,
                    'reason': f'Unsupported grade level: {classroom.grade_level or classroom.name}',
                })
                continue

            current_index = GRADE_SEQUENCE.index(current_grade)
            if current_index == len(GRADE_SEQUENCE) - 1:
                student.status = Student.Status.GRADUATED
                student.is_active = False
                student.save(update_fields=['status', 'is_active', 'updated_at'])
                graduated_count += 1
                continue

            next_grade = GRADE_SEQUENCE[current_index + 1]
            next_year = _next_academic_year(classroom.academic_year)
            key = (next_grade, classroom.stream, next_year)
            target_classroom = created_classrooms.get(key)

            if not target_classroom:
                target_classroom, created = Classroom.objects.get_or_create(
                    tenant=tenant,
                    name=next_grade,
                    stream=classroom.stream,
                    academic_year=next_year,
                    defaults={
                        'grade_level': next_grade,
                        'capacity': classroom.capacity,
                        'is_active': True,
                    },
                )
                created_classrooms[key] = target_classroom

            student.classroom = target_classroom
            student.save(update_fields=['classroom', 'updated_at'])
            promoted_count += 1

    pp1_remaining_count = Student.objects.filter(
        tenant=tenant,
        is_active=True,
        status=Student.Status.ACTIVE,
        classroom__grade_level='PP1',
    ).count()

    return {
        'promoted_count': promoted_count,
        'graduated_count': graduated_count,
        'skipped_count': len(skipped),
        'pp1_remaining_count': pp1_remaining_count,
        'skipped': skipped[:25],
    }


def parse_student_csv(csv_file, tenant):
    """
    Parse CSV file and return list of student/guardian data.
    
    Expected CSV columns:
    admission_number,first_name,middle_name,last_name,gender,date_of_birth,
    classroom_name,guardian_first_name,guardian_last_name,guardian_phone,
    guardian_relationship,guardian_national_id
    """
    errors = []
    success_count = 0
    
    try:
        decoded_file = csv_file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        for row_num, raw_row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            row = {
                key: (value.strip() if isinstance(value, str) else value)
                for key, value in raw_row.items()
            }

            try:
                required = ['admission_number', 'first_name', 'last_name',
                           'gender', 'date_of_birth', 'classroom_name',
                           'guardian_first_name', 'guardian_last_name',
                           'guardian_phone', 'guardian_relationship']

                missing = [field for field in required if not row.get(field)]
                if missing:
                    errors.append({
                        'row': row_num,
                        'error': f'Missing fields: {", ".join(missing)}'
                    })
                    continue

                birth_date = parse_date(row['date_of_birth'])
                if not birth_date:
                    errors.append({
                        'row': row_num,
                        'error': 'date_of_birth must be in YYYY-MM-DD format'
                    })
                    continue

                if row['gender'] not in ['M', 'F']:
                    errors.append({
                        'row': row_num,
                        'error': 'gender must be M or F'
                    })
                    continue

                if Student.objects.filter(admission_number=row['admission_number']).exists():
                    errors.append({
                        'row': row_num,
                        'error': f'Admission number "{row["admission_number"]}" already exists'
                    })
                    continue

                classroom, _created = get_or_create_classroom(row['classroom_name'], tenant)

                if not classroom:
                    errors.append({
                        'row': row_num,
                        'error': f'Classroom "{row["classroom_name"]}" not found'
                    })
                    continue

                with transaction.atomic():
                    guardian = Guardian.objects.create(
                        first_name=row['guardian_first_name'],
                        last_name=row['guardian_last_name'],
                        phone=row['guardian_phone'],
                        relationship=row['guardian_relationship'],
                        national_id=row.get('guardian_national_id', ''),
                        # tenant=tenant  # Uncomment if Guardian has tenant field
                    )

                    Student.objects.create(
                        admission_number=row['admission_number'],
                        first_name=row['first_name'],
                        middle_name=row.get('middle_name', ''),
                        last_name=row['last_name'],
                        gender=row['gender'],
                        date_of_birth=birth_date,
                        classroom=classroom,
                        primary_guardian=guardian,
                        nemis_no=row.get('nemis_no', ''),
                        birth_certificate_no=row.get('birth_certificate_no', ''),
                        blood_group=row.get('blood_group', ''),
                        medical_notes=row.get('medical_notes', ''),
                        tenant=tenant,
                        status='active',
                    )

                success_count += 1

            except Exception as e:
                errors.append({
                    'row': row_num,
                    'error': str(e)
                })
                    
    except Exception as e:
        errors.append({'row': 0, 'error': f'Failed to parse CSV: {str(e)}'})
    
    return {
        'success_count': success_count,
        'errors': errors,
    }
