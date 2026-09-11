"""Deterministic validation for Assessment Engine V2 written questions.

Runs after the writer and before a question is accepted. No LLM or embedding calls.
Lesson/material generation is never called or modified.
"""

import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher

from services.assessment_scorecard import _outside_meta_proxy_reason

VALIDATOR_VERSION = "question_validator_v1"


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


def _level_rank(level):
    return {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}.get(
        str(level or "").upper(), 1
    )


def _topic_central(topic_source, markers):
    context = _norm(f"{topic_source.get('title', '')} {topic_source.get('type', '')}")
    return any(_norm(marker) in context for marker in markers)


def _objective_text(objective):
    return _norm(
        f"{objective.get('skill', '')} {objective.get('target', '')} "
        f"{objective.get('evidence', '')} {objective.get('question_mode', '')}"
    )


def _form_or_rule_focused(objective):
    text = _objective_text(objective)
    return any(
        marker in text
        for marker in (
            "spell", "orthograph", "escrit", "form choice", "form-choice", "grammar",
            "agreement", "conjug", "suffix", "prefix", "morpholog", "rule",
            "apocop", "plural", "gender",
        )
    )


def _answer_grounded(answer, objective, source_text):
    answer_n = _norm(answer)
    if not answer_n:
        return False
    combined = _norm(
        f"{objective.get('target', '')} {objective.get('evidence', '')} {source_text or ''}"
    )
    if answer_n in combined:
        return True
    answer_tokens = _tokens(answer_n, 2)
    combined_tokens = _tokens(combined, 2)
    if not answer_tokens:
        return False
    return _containment(answer_tokens, combined_tokens) >= 0.70


def _aligned(question, objective):
    objective_tokens = _tokens(
        f"{objective.get('target', '')} {objective.get('evidence', '')}", 3
    )
    question_tokens = _tokens(
        f"{question.get('prompt', '')} {question.get('answer', '')}", 3
    )
    if not objective_tokens or not question_tokens:
        return True
    return _containment(objective_tokens, question_tokens) >= 0.18 or _containment(
        question_tokens, objective_tokens
    ) >= 0.18


def _meta_allowed(question, objective, topic_source, level):
    # Probe prompt + answer + distractors. The live V2 failure placed IPA notation in
    # the answer, which a prompt-only meta check could not see.
    probe = dict(question)
    probe["prompt"] = " ".join(
        [
            str(question.get("prompt", "")),
            str(question.get("answer", "")),
            " ".join(str(x) for x in (question.get("distractors") or [])),
        ]
    )
    reason = _outside_meta_proxy_reason(probe)
    if not reason:
        return True, None

    objective_text = _objective_text(objective)
    rank = _level_rank(level)

    pronunciation_markers = (
        "pronunciation", "pronunciacion", "pronunciación", "phonetic", "fonet",
        "phonology", "fonolog", "sound", "sonido", "ses", "laut", "suono",
    )
    etymology_markers = (
        "etymology", "etymol", "etimol", "word origin", "historical root",
        "latin root", "raiz latina", "kelime koken", "kelime köken",
    )

    if reason in {
        "phonology_terminology", "sound_label_trivia", "phonetic_transcription_trivia"
    }:
        objective_pronunciation = any(_norm(x) in objective_text for x in pronunciation_markers)
        central = _topic_central(topic_source, pronunciation_markers)
        if objective_pronunciation and central and rank >= 3:
            return True, None
        return False, f"meta_{reason}"

    if reason in {"etymology", "historical_root"}:
        objective_etymology = any(_norm(x) in objective_text for x in etymology_markers)
        central = _topic_central(topic_source, etymology_markers)
        if objective_etymology and central and rank >= 5:
            return True, None
        return False, f"meta_{reason}"

    return False, f"meta_{reason}"


def _numeric_answer_leak(question, objective):
    if _form_or_rule_focused(objective):
        return False
    prompt = str(question.get("prompt", ""))
    answer = _norm(question.get("answer"))
    if not answer or any(ch.isdigit() for ch in answer):
        return False
    prompt_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", prompt))
    if not prompt_numbers:
        return False
    objective_text = str(
        f"{objective.get('target', '')} {objective.get('evidence', '')}"
    )
    objective_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", objective_text))
    return bool(prompt_numbers & objective_numbers)


def _looks_like_pseudoform_distractors(question, objective, source_text):
    if _form_or_rule_focused(objective):
        return False

    answer = _norm(question.get("answer"))
    answer_words = answer.split()
    if len(answer_words) > 2 or len(answer) < 3:
        return False

    source_n = _norm(source_text)
    suspicious = 0
    for distractor in question.get("distractors") or []:
        d = _norm(distractor)
        if not d or len(d.split()) > 2 or d in source_n:
            continue
        ratio = SequenceMatcher(None, answer, d).ratio()
        if ratio >= 0.58 and abs(len(answer) - len(d)) <= 3:
            suspicious += 1
    return suspicious >= 2


def validate_question(question, objective, topic_source, level):
    """Return (accepted: bool, reason: str|None) for one written question."""
    if not isinstance(question, dict) or not isinstance(objective, dict):
        return False, "malformed"

    source_text = str((topic_source or {}).get("text", ""))
    if not source_text:
        return False, "topic_source_missing"

    allowed, reason = _meta_allowed(question, objective, topic_source or {}, level)
    if not allowed:
        return False, reason

    if _numeric_answer_leak(question, objective):
        return False, "answer_revealed_by_numeric_cue"

    aligned = _aligned(question, objective)
    if not aligned:
        return False, "objective_misaligned"

    # Literal grounding is required for vocabulary/context answers. Grammar/spelling
    # objectives may legitimately derive a new form from an explicitly taught rule.
    if not _answer_grounded(question.get("answer"), objective, source_text):
        if not (_form_or_rule_focused(objective) and aligned):
            return False, "answer_unsupported"

    if _looks_like_pseudoform_distractors(question, objective, source_text):
        return False, "pseudoform_distractors"

    return True, None


def validate_questions(questions, objectives_by_id, topic_sources, level):
    valid = []
    rejected = []
    reasons = Counter()
    for question in questions or []:
        objective_id = str(question.get("objective_id", "")) if isinstance(question, dict) else ""
        objective = (objectives_by_id or {}).get(objective_id)
        if not objective:
            reason = "objective_missing"
        else:
            topic_source = (topic_sources or {}).get(str(objective.get("topic_id", ""))) or {}
            ok, reason = validate_question(question, objective, topic_source, level)
            if ok:
                valid.append(question)
                continue
        reasons[reason] += 1
        rejected.append({"reason": reason, "question": question, "objective_id": objective_id})

    total = len(questions or [])
    return valid, rejected, {
        "validator_version": VALIDATOR_VERSION,
        "input_count": total,
        "accepted_count": len(valid),
        "rejected_count": len(rejected),
        "accept_rate": round(len(valid) / total, 4) if total else 0.0,
        "reason_counts": dict(sorted(reasons.items())),
    }
