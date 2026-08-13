from django.db import migrations, models


def backfill_term_and_year(apps, schema_editor):
    """
    Existing TeacherSubjectAssignment rows predate term-scoping — they're the
    single 'current' assignment for that (teacher, subject, classroom). Stamp
    them with the term/year you're about to generate the first timetable for,
    so nothing silently disappears from the wizard after this migration runs.
    """
    TeacherSubjectAssignment = apps.get_model('timetabling', 'TeacherSubjectAssignment')
    # TODO: confirm these match the term/year you're setting up right now.
    CURRENT_TERM = 'term_1'
    CURRENT_YEAR = 2026
    TeacherSubjectAssignment.objects.filter(term='').update(
        term=CURRENT_TERM, academic_year=CURRENT_YEAR
    )


class Migration(migrations.Migration):

    dependencies = [
        ('timetabling', '004_subjectrule_time_preference'),
    ]

    operations = [
        # Step 1: add as blank/nullable so existing rows don't fail NOT NULL on write
        migrations.AddField(
            model_name='teachersubjectassignment',
            name='term',
            field=models.CharField(
                max_length=10,
                choices=[('term_1', 'Term 1'), ('term_2', 'Term 2'), ('term_3', 'Term 3')],
                blank=True,
                default='',
            ),
        ),
        migrations.AddField(
            model_name='teachersubjectassignment',
            name='academic_year',
            field=models.PositiveSmallIntegerField(null=True, blank=True),
        ),
        # Step 2: backfill existing rows
        migrations.RunPython(backfill_term_and_year, migrations.RunPython.noop),
        # Step 3: tighten to required + update the unique constraint
        migrations.AlterField(
            model_name='teachersubjectassignment',
            name='term',
            field=models.CharField(
                max_length=10,
                choices=[('term_1', 'Term 1'), ('term_2', 'Term 2'), ('term_3', 'Term 3')],
            ),
        ),
        migrations.AlterField(
            model_name='teachersubjectassignment',
            name='academic_year',
            field=models.PositiveSmallIntegerField(),
        ),
        migrations.AlterUniqueTogether(
            name='teachersubjectassignment',
            unique_together={('tenant', 'teacher', 'subject', 'classroom', 'term', 'academic_year')},
        ),
        migrations.AlterModelOptions(
            name='teachersubjectassignment',
            options={'ordering': ['-academic_year', 'term', 'classroom__name', 'subject__name']},
        ),
    ]
