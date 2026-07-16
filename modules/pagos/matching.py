"""Fuzzy-match a bulk-imported Pago's concepto_original (raw Bizum text)
against known Alumno/Pagador names, to pre-fill suggestions on the batch
review screen. Pure functions — no DB writes, no external calls. The
academia's ConceptoAlias table (if any) is looked up by the caller and
passed in as a plain {alias_text: target_id} dict; this module never
queries the DB itself.
"""
import re
import unicodedata

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


def _score(concepto_tokens: set[str], candidate_tokens: list[str]) -> float:
    """Requires the candidate's given name — its first token, by Spanish
    naming convention (nombre(s) before apellidos) — to appear verbatim in
    the concepto text before awarding any score at all. A shared surname
    alone is never sufficient: e.g. "Ramirez Gonzalez Arturo" must not
    match "Alba Ramírez Martín" just because "Ramirez" overlaps, and
    "Troncoso Gonzalo" alone must not pick one of several relatives who
    share that surname.
    """
    if not candidate_tokens or not concepto_tokens:
        return 0.0
    given_name = candidate_tokens[0]
    if given_name not in concepto_tokens:
        return 0.0
    candidate_set = set(candidate_tokens)
    overlap = concepto_tokens & candidate_set
    return len(overlap) / len(candidate_set)


def _alias_match(concepto_tokens: set[str], candidates: list[tuple[int, str]], aliases: dict) -> dict | None:
    by_id = {cid: nombre for cid, nombre in candidates}
    for alias_text, target_id in aliases.items():
        if target_id not in by_id:
            continue
        alias_tokens = set(_tokenize(alias_text))
        if alias_tokens and alias_tokens <= concepto_tokens:
            return {"id": target_id, "nombre": by_id[target_id], "score": 1.0}
    return None


def best_match(
    concepto_original: str,
    candidates: list[tuple[int, str]],
    aliases: dict[str, int] | None = None,
) -> dict | None:
    """candidates: [(id, nombre), ...].
    aliases: {alias_text: target_id} — checked first, verbatim, before any
    token logic. Seed it with known nicknames or recurring Bizum-text
    variants (e.g. "Tete" -> the Alumno actually named "Tere").

    Returns {id, nombre, score} for the best match at or above
    MATCH_THRESHOLD, or None if nothing qualifies — including when the top
    score is tied between two or more candidates, since an ambiguous guess
    (e.g. two relatives sharing a surname, both scoring equally) is worse
    than surfacing no suggestion at all.
    """
    concepto_tokens = set(_tokenize(concepto_original))
    if not concepto_tokens or not candidates:
        return None

    if aliases:
        alias_hit = _alias_match(concepto_tokens, candidates, aliases)
        if alias_hit:
            return alias_hit

    scored = []
    for cid, nombre in candidates:
        candidate_tokens = _tokenize(nombre)
        score = _score(concepto_tokens, candidate_tokens)
        if score > 0:
            scored.append({"id": cid, "nombre": nombre, "score": round(score, 3)})

    if not scored:
        return None

    scored.sort(key=lambda s: s["score"], reverse=True)
    top_score = scored[0]["score"]
    if sum(1 for s in scored if s["score"] == top_score) > 1:
        return None  # ambiguous tie — don't guess

    best = scored[0]
    return best if best["score"] >= MATCH_THRESHOLD else None
