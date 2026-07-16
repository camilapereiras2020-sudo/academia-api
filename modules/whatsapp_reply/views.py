from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import service


class WhatsAppReplyView(APIView):
    """
    POST /api/v1/whatsapp-reply/generar/
    Body: {
        "incoming": "<mensaje recibido>",           # required
        "context": "<contexto adicional>",          # optional
        "situation": "normal" | "retraso" | "cierre" # optional, defaults to "normal"
    }
    Returns: { "reply": "<texto generado>" }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        incoming = (request.data.get("incoming") or "").strip()
        context = (request.data.get("context") or "").strip()
        situation = request.data.get("situation") or "normal"

        if not incoming:
            return Response(
                {"error": "Falta el mensaje entrante."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reply = service.generate_reply(incoming, context, situation)
        except service.AnthropicNotConfigured as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except (service.AnthropicRequestError, service.AnthropicEmptyReply) as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({"reply": reply})
