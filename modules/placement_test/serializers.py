
from rest_framework import serializers
from .models import Question, TestSession, TestResult

class QuestionSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ["id", "section", "level", "passage", "script", "question_text", "options"]

    def get_options(self, obj):
        return [obj.option_a, obj.option_b, obj.option_c, obj.option_d]


class TestResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="session.student_name", read_only=True)
    started_at = serializers.DateTimeField(source="session.started_at", read_only=True)

    class Meta:
        model = TestResult
        fields = "__all__"
