
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Question",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("section", models.CharField(max_length=20)),
                ("level", models.CharField(max_length=5)),
                ("passage", models.TextField(blank=True)),
                ("script", models.TextField(blank=True)),
                ("question_text", models.TextField()),
                ("option_a", models.CharField(max_length=300)),
                ("option_b", models.CharField(max_length=300)),
                ("option_c", models.CharField(max_length=300)),
                ("option_d", models.CharField(max_length=300)),
                ("correct_answer", models.IntegerField()),
                ("active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["section", "level"]},
        ),
        migrations.CreateModel(
            name="TestSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("session_id", models.CharField(max_length=64, unique=True)),
                ("student_name", models.CharField(max_length=200)),
                ("has_accessibility_needs", models.BooleanField(default=False)),
                ("accessibility_notes", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(null=True, blank=True)),
                ("academia_slug", models.CharField(max_length=100, blank=True)),
                ("answers", models.JSONField(default=dict)),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="TestResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                ("session", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="result", to="placement_test.testsession")),
                ("grammar_level", models.CharField(max_length=5)),
                ("vocabulary_level", models.CharField(max_length=5)),
                ("reading_level", models.CharField(max_length=5)),
                ("listening_level", models.CharField(max_length=5)),
                ("overall_level", models.CharField(max_length=5)),
                ("grammar_score", models.FloatField(default=0)),
                ("vocabulary_score", models.FloatField(default=0)),
                ("reading_score", models.FloatField(default=0)),
                ("listening_score", models.FloatField(default=0)),
                ("strengths", models.TextField(blank=True)),
                ("areas_to_improve", models.TextField(blank=True)),
                ("writing_sample", models.TextField(blank=True)),
                ("contact_name", models.CharField(max_length=200, blank=True)),
                ("contact_email", models.EmailField(blank=True)),
                ("contact_phone", models.CharField(max_length=20, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
