
from django.db import models

LEVEL_CHOICES = [("A1","A1"),("A2","A2"),("B1","B1"),("B2","B2"),("C1","C1")]
SECTION_CHOICES = [("grammar","Grammar"),("vocabulary","Vocabulary"),("reading","Reading"),("listening","Listening")]

class Question(models.Model):
    section = models.CharField(max_length=20, choices=SECTION_CHOICES)
    level = models.CharField(max_length=5, choices=LEVEL_CHOICES)
    passage = models.TextField(blank=True)
    script = models.TextField(blank=True)
    question_text = models.TextField()
    option_a = models.CharField(max_length=300)
    option_b = models.CharField(max_length=300)
    option_c = models.CharField(max_length=300)
    option_d = models.CharField(max_length=300)
    correct_answer = models.IntegerField()
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["section", "level"]

    def __str__(self):
        return f"[{self.level}] {self.section}: {self.question_text[:50]}"


class TestSession(models.Model):
    session_id = models.CharField(max_length=64, unique=True)
    student_name = models.CharField(max_length=200)
    has_accessibility_needs = models.BooleanField(default=False)
    accessibility_notes = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    academia_slug = models.CharField(max_length=100, blank=True)
    answers = models.JSONField(default=dict)

    class Meta:
        ordering = ["-started_at"]


class TestResult(models.Model):
    session = models.OneToOneField(TestSession, on_delete=models.CASCADE, related_name="result")
    grammar_level = models.CharField(max_length=5)
    vocabulary_level = models.CharField(max_length=5)
    reading_level = models.CharField(max_length=5)
    listening_level = models.CharField(max_length=5)
    overall_level = models.CharField(max_length=5)
    grammar_score = models.FloatField(default=0)
    vocabulary_score = models.FloatField(default=0)
    reading_score = models.FloatField(default=0)
    listening_score = models.FloatField(default=0)
    strengths = models.TextField(blank=True)
    areas_to_improve = models.TextField(blank=True)
    writing_sample = models.TextField(blank=True)
    contact_name = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.session.student_name} — {self.overall_level}"
