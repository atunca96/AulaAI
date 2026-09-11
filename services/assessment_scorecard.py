"""Cheap deterministic scorecard for legacy/V2 shadow comparisons.

This is intentionally a proxy layer, not a pedagogical oracle. It uses no LLM or
embedding calls, so it adds no provider latency/cost. Objective validation is a
separate follow-up layer.
"""

import re
import unicodedata
from difflib import SequenceMatcher


def _norm(value):
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    chars = []
    for ch in text:
        if unicodedata.combining(ch):
            continue
        chars.append(ch if (ch.isalnum() or ch.isspace()) else " ")
    return " ".join("".join(chars).split())


def _tokens(value):
    return {t for t in _norm(value).split() if len(t) >= 2}


def _containment(a, b):
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def _question_near_repeat(a, b):
    p1, p2 = _norm(a.get("prompt")), _norm(b.get("prompt"))
    if not p1 or not p2:
        return False
    if p1 == p2 or SequenceMatcher(None, p1, p2).ratio() >= 0.86:
        return True
    a1, a2 = _norm(a.get("answer")), _norm(b.get("answer"))
    return bool(a1 and a1 == a2 and _containment(_tokens(p1), _tokens(p2)) >= 0.42)


def _objective_surface(value):
    text = _norm(value)
    text = re.sub(r"\b\d+\b", " n ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _objective_proxy_repeat(a, b):
    p1, p2 = _objective_surface(a.get("prompt")), _objective_surface(b.get("prompt"))
    if not p1 or not p2:
        return False
    if SequenceMatcher(None, p1, p2).ratio() >= 0.76:
        return True
    return _containment(_tokens(p1), _tokens(p2)) >= 0.72


def _valid_mcq(q):
    if not isinstance(q, dict):
        return False
    prompt = str(q.get("prompt", "")).strip()
    answer = str(q.get("answer", "")).strip()
    ds = [str(x).strip() for x in (q.get("distractors") or []) if str(x).strip()]
    if not prompt or not answer or len(ds) != 3:
        return False
    norms = [_norm(answer)] + [_norm(x) for x in ds]
    return bool(all(norms) and len(set(norms)) == 4)


def _source_grounded_proxy(q, source_text):
    source_n = _norm(source_text)
    if not source_n:
        return None
    answer_n = _norm(q.get("answer"))
    if answer_n and len(answer_n) >= 2 and answer_n in source_n:
        return True
    src = _tokens(source_n)
    ans = {x for x in _tokens(answer_n) if len(x) >= 3}
    if ans and _containment(ans, src) >= 0.5:
        return True
    prompt = {x for x in _tokens(q.get("prompt")) if len(x) >= 4}
    return bool(prompt and _containment(prompt, src) >= 0.18)


_META_STEM_GROUPS = {
    "etymology": ("etymol", "etimol", "etymolog", "etimolog"),
    "phonology_terminology": (
        "diphthong", "diptong", "ditong", "phonetic", "fonetic",
        "phonolog", "fonolog", "phonem", "fonem", "graphem", "grafem",
        "prosod", "syllab", "silab",
    ),
    "orthography_micro_trivia": (
        "orthographic accent", "acento ortograf", "accent mark", "accented letter",
        "accentuation", "acentuacion", "tilde", "diacritic", "diacrit",
        "aksan isaret", "aksan işaret", "imla isaret", "imla işaret",
    ),
    "morphology_terminology": (
        "morphem", "morfem", "morpholog", "morfolog", "prefix", "prefij",
        "suffix", "sufij", "affix", "afij", "linking element", "linking prefix",
        "elemento de enlace", "prefijo de enlace", "word stem", "raiz morf", "raíz morf",
    ),
    "cross_language_trivia": (
        "other romance language", "otras lenguas romances", "otra lengua romance",
        "other languages", "otras lenguas", "a diferencia de otras lenguas",
        "compared with other languages", "rispetto ad altre lingue", "anderen sprachen",
    ),
    "historical_root": (
        "latin root", "historical root", "raiz latina", "racine latine",
        "radice latina", "lateinische wurzel", "latin koken", "latin köken",
    ),
}

_META_EXACT_MARKERS = (
    "letter count", "how many letters", "which letter", "phonetic label",
    "acento grafico", "cuantas letras", "kaç harf", "hangi harf",
    "which spelling feature", "que rasgo ortografico", "qué rasgo ortográfico",
    "combination of letters", "combinacion de letras", "combinación de letras",
)

_MATH_STEMS = (
    "sumar", "suma", "multiplicar", "multiply", "subtract", "addition",
    "topla", "carp", "çarp",
)

_SOUND_TERMS = ("sound", "sonid", "ses", "laut", "suono", "son")
_SOUND_LABEL_STEMS = (
    "soft", "hard", "suave", "fuerte", "voiced", "voiceless", "sonoro", "sordo",
    "tap", "trill", "rhotic", "alveolar", "fricative", "fricativ", "occlusive",
    "oclusiv", "affricate", "africad", "plosive", "nasal", "approximant", "vibrant",
    "vibrante",
)


def _has_ipa_like_notation(raw):
    for match in re.findall(r"/([^/\n]{1,12})/", str(raw or "")):
        token = match.strip()
        if token and len(token.split()) == 1 and any(ch.isalpha() or ord(ch) > 127 for ch in token):
            return True
    return False


def _operation_allows_meta(reason, q):
    """Early guard escape hatch; final legacy gate still checks topic centrality."""
    op = str((q or {}).get("_objective_operation", "") or "").strip().lower()
    if reason in {"phonology_terminology", "phonetic_transcription_trivia", "sound_label_trivia"}:
        return op == "pronunciation"
    if reason in {"orthography_micro_trivia", "letter_or_spelling_trivia"}:
        return op == "orthography-form"
    if reason == "morphology_terminology":
        return op in {"grammar", "orthography-form"}
    if reason == "cross_language_trivia":
        return op == "contrast"
    return False


def _outside_meta_proxy_reason(q):
    raw = str(q.get("prompt", ""))
    p = _norm(raw)
    if not p:
        return None

    for reason, stems in _META_STEM_GROUPS.items():
        if any(_norm(stem) in p for stem in stems):
            if _operation_allows_meta(reason, q):
                continue
            return reason

    if any(_norm(marker) in p for marker in _META_EXACT_MARKERS):
        reason = "letter_or_spelling_trivia"
        if not _operation_allows_meta(reason, q):
            return reason

    if re.search(r"\b\d+\s*[+×*/]\s*\d+\b", raw):
        return "arithmetic"
    if any(_norm(stem) in p for stem in _MATH_STEMS):
        return "arithmetic"

    has_sound_term = any(_norm(x) in p for x in _SOUND_TERMS)
    sound_label_count = sum(1 for x in _SOUND_LABEL_STEMS if _norm(x) in p)

    if _has_ipa_like_notation(raw) and (has_sound_term or "letter" in p or "letra" in p):
        reason = "phonetic_transcription_trivia"
        if not _operation_allows_meta(reason, q):
            return reason

    if has_sound_term and sound_label_count >= 1:
        reason = "sound_label_trivia"
        if not _operation_allows_meta(reason, q):
            return reason

    return None


def _outside_meta_proxy(q):
    return _outside_meta_proxy_reason(q) is not None


def _pair_rate(questions, fn):
    n = len(questions)
    if n < 2:
        return 0.0
    duplicate_items = set()
    for i in range(n):
        for j in range(i + 1, n):
            if fn(questions[i], questions[j]):
                duplicate_items.add(i)
                duplicate_items.add(j)
    return round(len(duplicate_items) / n, 4)


def build_scorecard(questions, requested_count, source_text=""):
    qs = [q for q in (questions or []) if isinstance(q, dict)]
    requested = max(1, int(requested_count or 1))
    valid_rate = sum(1 for q in qs if _valid_mcq(q)) / requested

    grounding_checks = [_source_grounded_proxy(q, source_text) for q in qs]
    grounding_known = [x for x in grounding_checks if x is not None]
    grounding_rate = (
        round(sum(1 for x in grounding_known if x) / len(grounding_known), 4)
        if grounding_known else None
    )

    question_dup = _pair_rate(qs, _question_near_repeat)
    objective_dup_proxy = _pair_rate(qs, _objective_proxy_repeat)

    meta_reasons = {}
    flagged_meta = 0
    for q in qs:
        reason = _outside_meta_proxy_reason(q)
        if not reason:
            continue
        flagged_meta += 1
        meta_reasons[reason] = meta_reasons.get(reason, 0) + 1
    outside_meta = round(flagged_meta / requested, 4)
    count_match = len(qs) == requested

    grounding_component = 1.0 if grounding_rate is None else grounding_rate
    composite = (
        (0.35 if count_match else 0.0)
        + 0.20 * min(1.0, valid_rate)
        + 0.15 * grounding_component
        + 0.15 * (1.0 - min(1.0, question_dup))
        + 0.10 * (1.0 - min(1.0, objective_dup_proxy))
        + 0.05 * (1.0 - min(1.0, outside_meta))
    )

    return {
        "score_version": "shadow_proxy_v5",
        "composite_score": round(composite * 100.0, 2),
        "composite_score_provisional": True,
        "cutover_eligible": False,
        "requested_count_match": count_match,
        "returned_count": len(qs),
        "valid_mcq_rate": round(min(1.0, valid_rate), 4),
        "source_grounding_proxy_rate": grounding_rate,
        "question_duplicate_rate": question_dup,
        "objective_duplicate_proxy_rate": objective_dup_proxy,
        "outside_meta_proxy_rate": outside_meta,
        "outside_meta_proxy_reason_counts": meta_reasons,
        "hard_gates": {
            "count_match": count_match,
            "valid_structure": valid_rate >= 0.99,
        },
        "manual_calibration_required": True,
        "proxy_warning": "Grounding/objective/meta metrics are deterministic proxies, not final pedagogical validation or cutover gates.",
    }
