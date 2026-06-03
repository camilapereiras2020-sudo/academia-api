import os
import resend


def send_email(to: str, subject: str, body: str, academia_nombre: str = "") -> str:
    """Send a plain-text email via Resend. Returns the message id."""
    resend.api_key = os.environ.get("RESEND_API_KEY", "")

    footer = (
        f"<hr style='margin-top:32px'>"
        f"<p style='color:#aaa;font-size:12px'>{academia_nombre}</p>"
        if academia_nombre else ""
    )
    html = (
        f"<div style='font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px'>"
        f"<p style='white-space:pre-wrap'>{body}</p>"
        f"{footer}</div>"
    )

    result = resend.Emails.send({
        "from": os.environ.get("DEFAULT_FROM_EMAIL", "onboarding@resend.dev"),
        "to": [to],
        "subject": subject,
        "html": html,
    })
    return result.get("id", "")
