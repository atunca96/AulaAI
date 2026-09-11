"""Deterministic validation for Assessment Engine V2 planner objectives.

No LLM or embedding calls are made here. The validator checks source support,
pedagogical admissibility, and semantic/objective duplication before writer calls.
Lesson/material generation is never called or modified.
"""

import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher

VALIDATOR_VERSION = "objective_validator_v2"


def _norm(value):
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    chars = []
    for ch in text:
        if unicodedata.combining(ch):
            continue
        chars.append(ch if (ch.isalnum() or ch.isspace()) else " ")
    return " ".join("".join(chars).split())


def _tokens(value, min_len=2):
    return {t for t in _norm(value).split() if len(t) >= min_len}


def _containment(a, b):
    return len(a & b) / len(a) if a else 0.0


def _evidence_supported(claim, source_text):
    claim_n = _norm(claim)
    source_n = _norm(source_text)
    if not claim_n or not source_n:
        return False
    if claim_n in source_n:
        return True
    claim_tokens = _tokens(claim_n, 2)
    source_tokens = _tokens(source_n, 2)
    if not claim_tokens:
        return False
    if _containment(claim_tokens, source_tokens) >= 0.68:
        return True
    for segment in re.split(r"[\n.!?;]+", source_n):
        segment = segment.strip()
        if not segment:
            continue
        seg_tokens = _tokens(segment, 2)
        if _containment(claim_tokens, seg_tokens) < 0.50:
            continue
        if SequenceMatcher(None, claim_n, segment[: max(len(claim_n) * 3, 120)]).ratio() >= 0.62:
            return True
    return False


_HARD_META_STEMS = {
    "etymology": ("etymol", "etimol"),
    "historical_root": ("historical root", "latin root", "raiz latina", "latin koken", "latin köken"),
    "letter_trivia": ("letter count", "how many letters", "which letter", "cuantas letras", "kaç harf", "hangi harf"),
}

_PHONOLOGY_STEMS = (
    "diphthong", "diptong", "ditong", "phoneme", "fonem", "grapheme", "grafem",
    "phonology", "fonolog", "phonetic label", "fonetik terim",
)

_ORTHOGRAPHY_MICRO_STEMS = (
    "orthographic accent", "acento ortograf", "accent mark", "accented letter",
    "accentuation", "acentuacion", "tilde", "diacritic", "diacrit",
    "aksan isaret", "aksan işaret", "imla isaret", "imla işaret",
)

_ARITHMETIC_STEMS = (
    "sumar", "suma", "multiplicar", "multiply", "subtract", "addition", "topla", "carp", "çarp",
)

_PRONUNCIATION_CENTRAL = (
    "pronunciation", "pronunciacion", "pronunciación", "fonet", "phonetic", "phonology", "fonologia", "fonología",
    "sound", "sounds", "ses", "laut", "suono",
)

_ETYMOLOGY_CENTRAL = (
    "etymology", "etymologia", "etimologia", "etimología", "word origin", "kelime koken", "kelime köken",
)

_ORTHOGRAPHY_CENTRAL = (
    "orthography", "orthographic", "spelling", "accentuation", "diacritic",
    "ortografia", "ortografía", "acentuacion", "acentuación", "tilde",
    "imla", "yazim", "yazım",
)


def _level_rank(level):
    order = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
    return order.get(str(level or "").upper(), 1)


def _topic_is_central(topic_source, markers):
    context = _norm(f"{topic_source.get('title', '')} {topic_source.get('type', '')}")
    return any(_norm(marker) in context for marker in markers)


def _pedagogical_reject_reason(obj, topic_source, level):
    target = _norm(obj.get("target"))
    skill = _norm(obj.get("skill"))
    mode = _norm(obj.get("question_mode"))
    joined = f"{target} {skill} {mode}"

    if re.search(r"\b\d+\s*[+×*/]\s*\d+\b", str(obj.get("target", ""))):
        return "arithmetic"
    if any(_norm(stem) in joined for stem in _ARITHMETIC_STEMS):
        return "arithmetic"

    for reason, stems in _HARD_META_STEMS.items():
        if not any(_norm(stem) in joined for stem in stems):
            continue
        if reason == "etymology" and _level_rank(level) >= 5 and _topic_is_central(topic_source, _ETYMOLOGY_CENTRAL):
            continue
        return reason

    if any(_norm(stem) in joined for stem in _ORTHOGRAPHY_MICRO_STEMS):
        if not _topic_is_central(topic_source, _ORTHOGRAPHY_CENTRAL):
            return "orthography_micro_trivia"

    if any(_norm(stem) in joined for stem in _PHONOLOGY_STEMS):
        practical = any(x in target for x in ("pronounc", "produce", "distinguish sound", "hear", "stress", "intonation"))
        if _level_rank(level) <= 2 and not practical:
            return "abstract_phonology_terminology"
        if _level_rank(level) >= 3 and not practical and not _topic_is_central(topic_source, _PRONUNCIATION_CENTRAL):
            return "abstract_phonology_terminology"

    return None


def _operation_class(obj):
    text = _norm(f"{obj.get('skill', '')} {obj.get('question_mode', '')} {obj.get('target', '')}")
    if any(x in text for x in ("dialogue", "conversation", "comprehension")):
        return "dialogue"
    if any(x in text for x in ("register", "pragmatic", "formal", "informal")):
        return "pragmatics"
    if any(x in text for x in ("pronounc", "sound", "stress", "intonation", "phon")):
        return "pronunciation"
    if any(x in text for x in ("grammar", "agreement", "conjug", "gender", "plural", "article", "preposition", "form function")):
        return "grammar"
    if any(x in text for x in ("context", "situational", "completion", "use in")):
        return "contextual_use"
    if any(x in text for x in ("meaning", "translation", "vocabulary", "lexical", "recognize", "identify the word", "identify the number")):
        return "lexical_lookup"
    if "contrast" in text:
        return "contrast"
    return "other"


def _abstract_target(value):
    text = _norm(value)
    text = re.sub(r"\b\d+\b", " n ", text)
    text = re.sub(r"\b[a-z]{1,2}\b", " ", text)
    return " ".join(text.split())


def _duplicate_reason(obj, prior):
    target = _norm(obj.get("target"))
    evidence = _norm(obj.get("evidence"))
    operation = _operation_class(obj)
    abstract = _abstract_target(target)

    for old in prior or []:
        old_target = _norm(old.get("target"))
        old_evidence = _norm(old.get("evidence"))
        old_operation = _operation_class(old)
        if target and target == old_target:
            return "same_target"
        if target and old_target and SequenceMatcher(None, target, old_target).ratio() >= 0.91:
            return "near_same_target"
        if operation == old_operation == "lexical_lookup":
            old_abstract = _abstract_target(old_target)
            if abstract and old_abstract and SequenceMatcher(None, abstract, old_abstract).ratio() >= 0.84:
                return "same_lookup_operation"

        target_tokens = _tokens(target, 3)
        old_target_tokens = _tokens(old_target, 3)
        evidence_tokens = _tokens(evidence, 3)
        old_evidence_tokens = _tokens(old_evidence, 3)
        target_overlap = min(_containment(target_tokens, old_target_tokens), _containment(old_target_tokens, target_tokens)) if target_tokens and old_target_tokens else 0.0
        evidence_overlap = min(_containment(evidence_tokens, old_evidence_tokens), _containment(old_evidence_tokens, evidence_tokens)) if evidence_tokens and old_evidence_tokens else 0.0
        if operation == old_operation and target_overlap >= 0.72 and evidence_overlap >= 0.72:
            return "same_subtarget"
    return None


def validate_objectives(candidates, topic_sources, level, accepted=None):
    valid = []
    rejected = []
    reasons = Counter()
    prior = list(accepted or [])

    for raw in candidates or []:
        if not isinstance(raw, dict):
            reasons["malformed"] += 1
            rejected.append({"reason": "malformed"})
            continue
        obj = dict(raw)
        topic_id = str(obj.get("topic_id", ""))
        topic_source = (topic_sources or {}).get(topic_id)
        if not topic_source or not str(topic_source.get("text", "")).strip():
            reason = "topic_source_missing"
        elif not str(obj.get("evidence", "")).strip():
            reason = "evidence_missing"
        elif not _evidence_supported(obj.get("evidence"), topic_source.get("text")):
            reason = "evidence_unsupported"
        else:
            reason = _pedagogical_reject_reason(obj, topic_source, level)
            if reason is None:
                dup = _duplicate_reason(obj, prior + valid)
                reason = f"duplicate_{dup}" if dup else None

        if reason:
            reasons[reason] += 1
            rejected.append({"reason": reason, "objective": obj})
            continue
        valid.append(obj)

    total = len(candidates or [])
    report = {
        "validator_version": VALIDATOR_VERSION,
        "input_count": total,
        "accepted_count": len(valid),
        "rejected_count": total - len(valid),
        "accept_rate": round(len(valid) / total, 4) if total else 0.0,
        "reason_counts": dict(sorted(reasons.items())),
    }
    return valid, rejected, report
