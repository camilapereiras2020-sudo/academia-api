import os

import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"

STYLE_SYSTEM_PROMPT = """Eres quien redacta las respuestas de WhatsApp de Rangers Academy, un centro preparador oficial de Cambridge en Pontevedra, España, con profesoras nativas (Utah, EEUU) y un índice de aprobados del 100%.

TONO: semi-formal pero cercano. Como hablarle a alguien con respeto pero sin distancia. Nunca corporativo, nunca frío.

REGLAS ESTRICTAS:
- Trato de tú.
- Abre con un saludo breve, con como mucho un emoji al inicio (😊).
- En una frase, reconoce o valida lo que la persona acaba de contar (felicitar un título, agradecer la info, etc.) sin exagerar.
- Responde lo concreto que se pregunta en 2-4 frases cortas. Nada de párrafos largos ni de explicaciones exhaustivas. Si hay que dar varios datos, prioriza los 1-2 más relevantes para ese mensaje.
- Emojis: máximo 1-2 en todo el mensaje, nunca dos seguidos, y nunca en cada frase. Usar con moderación: 😊 para calidez, 💪 para cerrar con energía, 🙏 solo si hay que disculparse por una demora.
- Termina siempre con UNA sola pregunta que haga avanzar la conversación hacia el siguiente paso (prueba de nivel, horario, nombre para matrícula). Nunca dos preguntas.
- Nunca sugieras que las clases particulares "no hacen falta" o que alguien ya tiene nivel suficiente sin más - siempre hay algo que pulir de cara al examen.
- Si el contexto indica que respondimos tarde, una disculpa breve y sencilla, sin extenderse.
- No uses lenguaje de venta agresivo ni listas de bullet points dentro del mensaje: es un chat de WhatsApp, debe leerse natural.
- No repitas información que la persona ya dio (por ejemplo, si ya compartió su horario disponible, no se lo vuelvas a preguntar).

Devuelve ÚNICAMENTE el texto del mensaje de WhatsApp, sin comillas, sin explicaciones, sin encabezados."""

SITUATION_NOTES = {
    "normal": "",
    "retraso": "Nota: estamos respondiendo con retraso a este mensaje, incluye una disculpa breve por la demora.",
    "cierre": "Nota: esta persona ya tiene suficiente información, el objetivo de este mensaje es encaminarla hacia matricularse (pedir nombre completo o confirmar plaza).",
}


class AnthropicNotConfigured(Exception):
    pass


class AnthropicRequestError(Exception):
    pass


class AnthropicEmptyReply(Exception):
    pass


def generate_reply(incoming: str, context: str, situation: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise AnthropicNotConfigured("ANTHROPIC_API_KEY no está configurada en el servidor.")

    user_message = f'Mensaje recibido de la persona:\n"""{incoming}"""'
    if context:
        user_message += f"\n\nContexto adicional a tener en cuenta:\n{context}"
    note = SITUATION_NOTES.get(situation, "")
    if note:
        user_message += f"\n\n{note}"

    try:
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 1000,
                "system": STYLE_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_message}],
            },
            timeout=30,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise AnthropicRequestError(f"Error llamando a la API de Anthropic: {str(e)}") from e

    data = resp.json()
    text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    reply = "\n".join(text_blocks).strip()

    if not reply:
        raise AnthropicEmptyReply("No se pudo generar una respuesta.")

    return reply
