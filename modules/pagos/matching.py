"""Fuzzy-match a bulk-imported Pago's concepto_original (raw Bizum text)
against known Alumno/Pagador names, to pre-fill suggestions on the batch
review screen. Pure functions — no DB writes, no external calls.
"""
import re
import unicodedata
from difflib import SequenceMatcher

NOISE_WORDS = {
    "ingreso", "bizum", "clases", "clase", "english", "classes", "ingles",
    "de", "y", "sin", "nombre", "medio", "mes", "transferencia", "pago", "pagos",
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre",
}

MATCH_THRESHOLD = 0.4


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _tokenize(text: str) -> list[str]:
    text = _strip_accents(text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [
        t for t in text.split()
        if len(t) >= 2 and not t.isdigit() and t not in NOISE_WORDS
    ]


def _score(concepto_tokens: set[str], candidate_tokens: set[str]) -> float:
    if not candidate_tokens or not concepto_tokens:
        return 0.0
    overlap = concepto_tokens & candidate_tokens
    if overlap:
        return len(overlap) / len(candidate_tokens)
    # No exact token overlap — fall back to fuzzy spelling similarity, discounted
    # so it never outranks a real token match.
    best = 0.0
    for ct in concepto_tokens:
        for cand in candidate_tokens:
            best = max(best, SequenceMatcher(None, ct, cand).ratio())
    return best * 0.5


def best_match(concepto_original: str, candidates: list[tuple[int, str]]) -> dict | None:
    """candidates: [(id, nombre), ...]. Returns {id, nombre, score} for the
    best match at or above MATCH_THRESHOLD, or None if nothing qualifies.
    """
    concepto_tokens = set(_tokenize(concepto_original))
    if not concepto_tokens or not candidates:
        return None

    best = None
    for cid, nombre in candidates:
        candidate_tokens = set(_tokenize(nombre))
        score = _score(concepto_tokens, candidate_tokens)
        if best is None or score > best["score"]:
            best = {"id": cid, "nombre": nombre, "score": round(score, 3)}

    return best if best and best["score"] >= MATCH_THRESHOLD else None
