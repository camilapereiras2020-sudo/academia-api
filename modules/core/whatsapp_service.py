from urllib.parse import quote


def _normalise_phone(phone: str) -> str:
    """Strip spaces/dashes; prepend +34 if no country code present."""
    cleaned = phone.replace(" ", "").replace("-", "")
    if not cleaned.startswith("+"):
        cleaned = "+34" + cleaned
    return cleaned.lstrip("+")   # wa.me expects digits only, no leading +


def whatsapp_link(phone: str, text: str = "") -> str:
    """Return a wa.me URL that opens WhatsApp with an optional pre-filled message."""
    number = _normalise_phone(phone)
    if text:
        return f"https://wa.me/{number}?text={quote(text)}"
    return f"https://wa.me/{number}"
