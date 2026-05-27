
import uuid, random
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .models import Question, TestSession, TestResult
from .serializers import QuestionSerializer, TestResultSerializer

LEVELS = ["A1", "A2", "B1", "B2", "C1"]
LEVEL_SCORES = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5}
SCORE_LEVELS = {1: "A1", 2: "A2", 3: "B1", 4: "B2", 5: "C1"}

LEVEL_DESCRIPTIONS = {
    "A1": "Principiante — Puedes presentarte, usar frases simples y entender expresiones básicas.",
    "A2": "Elemental — Puedes comunicarte en situaciones cotidianas sencillas.",
    "B1": "Intermedio — Puedes entender los puntos principales de textos claros y expresar opiniones.",
    "B2": "Intermedio alto — Puedes interactuar con fluidez con hablantes nativos sobre temas variados.",
    "C1": "Avanzado — Puedes expresarte de forma clara y detallada sobre temas complejos.",
}

STRENGTHS = {
    "A1": ["Te comunicas con valentía en inglés", "Reconoces vocabulario cotidiano"],
    "A2": ["Manejas situaciones del día a día", "Tu vocabulario básico es sólido"],
    "B1": ["Expresas ideas con claridad", "Entiendes textos auténticos"],
    "B2": ["Te comunicas con naturalidad", "Tu gramática es muy precisa"],
    "C1": ["Dominas estructuras complejas", "Tu nivel es casi nativo"],
}

IMPROVEMENTS = {
    "A1": ["Ampliar vocabulario básico", "Practicar verbos irregulares"],
    "A2": ["Trabajar tiempos pasados", "Mejorar la comprensión oral"],
    "B1": ["Perfeccionar el condicional", "Ampliar vocabulario académico"],
    "B2": ["Dominar estructuras avanzadas", "Mejorar matices de vocabulario"],
    "C1": ["Perfeccionar expresiones idiomáticas", "Alcanzar precisión nativa"],
}


def calculate_level(correct, total):
    if total == 0:
        return "A1", 0
    pct = correct / total
    if pct >= 0.85: return "C1", pct
    elif pct >= 0.70: return "B2", pct
    elif pct >= 0.55: return "B1", pct
    elif pct >= 0.40: return "A2", pct
    else: return "A1", pct


@api_view(["POST"])
@permission_classes([AllowAny])
def start_session(request):
    session_id = str(uuid.uuid4())
    session = TestSession.objects.create(
        session_id=session_id,
        student_name=request.data.get("student_name", "Estudiante"),
        has_accessibility_needs=request.data.get("has_accessibility_needs", False),
        accessibility_notes=request.data.get("accessibility_notes", ""),
        academia_slug=request.data.get("academia_slug", ""),
    )
    questions = []
    for section in ["grammar", "vocabulary", "reading", "listening"]:
        qs = list(Question.objects.filter(section=section, level="A2", active=True))
        if qs:
            n = 2 if section in ["reading", "listening"] else 3
            questions.extend(random.sample(qs, min(n, len(qs))))
    return Response({
        "session_id": session_id,
        "questions": QuestionSerializer(questions, many=True).data,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def submit_answers(request, session_id):
    try:
        session = TestSession.objects.get(session_id=session_id)
    except TestSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)

    answers = request.data.get("answers", {})
    session.answers = answers
    session.completed_at = timezone.now()
    session.save()

    section_scores = {}
    for section in ["grammar", "vocabulary", "reading", "listening"]:
        answered_ids = [int(k) for k in answers.keys()]
        section_qs = Question.objects.filter(id__in=answered_ids, section=section)
        correct = sum(1 for q in section_qs if str(q.id) in answers and answers[str(q.id)] == q.correct_answer)
        total = section_qs.count()
        level, score = calculate_level(correct, total)
        section_scores[section] = {"level": level, "score": score}

    avg = sum(LEVEL_SCORES[v["level"]] for v in section_scores.values()) / 4
    overall_idx = max(1, min(5, round(avg)))
    overall_level = SCORE_LEVELS[overall_idx]

    result = TestResult.objects.create(
        session=session,
        grammar_level=section_scores["grammar"]["level"],
        vocabulary_level=section_scores["vocabulary"]["level"],
        reading_level=section_scores["reading"]["level"],
        listening_level=section_scores["listening"]["level"],
        overall_level=overall_level,
        grammar_score=section_scores["grammar"]["score"],
        vocabulary_score=section_scores["vocabulary"]["score"],
        reading_score=section_scores["reading"]["score"],
        listening_score=section_scores["listening"]["score"],
        strengths=", ".join(STRENGTHS.get(overall_level, [])),
        areas_to_improve=", ".join(IMPROVEMENTS.get(overall_level, [])),
    )

    return Response({
        "overall_level": overall_level,
        "description": LEVEL_DESCRIPTIONS[overall_level],
        "sections": {k: {"level": v["level"], "score": round(v["score"] * 100)} for k, v in section_scores.items()},
        "strengths": STRENGTHS.get(overall_level, []),
        "areas_to_improve": IMPROVEMENTS.get(overall_level, []),
        "result_id": result.id,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def save_contact(request, result_id):
    try:
        result = TestResult.objects.get(id=result_id)
    except TestResult.DoesNotExist:
        return Response({"error": "Not found"}, status=404)
    result.contact_name = request.data.get("contact_name", "")
    result.contact_email = request.data.get("contact_email", "")
    result.contact_phone = request.data.get("contact_phone", "")
    result.writing_sample = request.data.get("writing_sample", "")
    result.save()
    return Response({"success": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_results(request):
    results = TestResult.objects.select_related("session").all().order_by("-created_at")
    return Response(TestResultSerializer(results, many=True).data)
