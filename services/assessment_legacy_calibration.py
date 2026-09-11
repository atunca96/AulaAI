"""Congress calibration for the stable legacy assessment path.

Prompt-first generation stays authoritative. This layer only makes the existing
legacy path use a small one-call candidate pool before content_engine sees the
questions, so deterministic quality rejection does not cascade into repeated LLM
refills. Lesson/material generation is never touched.
"""

import json
import math
import re
from collections import Counter


def _set_count(args, kwargs, value):
    call_args = list(args)
    call_kwargs = dict(kwargs)
    if len(call_args) >= 5:
        call_args[4] = value
        call_kwargs.pop("count", None)
    else:
        call_kwargs["count"] = value
    return call_args, call_kwargs


def _source_text(guard, args, kwargs):
    title = str(guard._arg(args, kwargs, "topic_title", 0, "") or "")
    topic_type = str(guard._arg(args, kwargs, "topic_type", 1, "") or "")
    content = guard._arg(args, kwargs, "topic_content", 2, {})
    try:
        body = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        body = str(content or "")
    return f"TOPIC {title} ({topic_type})\n{body}"[:120000]


def _extra_quality_reason(gate, question, headers):
    p = gate._norm((question or {}).get("prompt", ""))
    if not p:
        return None

    # Orthographic micro-trivia that is not useful in an ordinary vocabulary/
    # grammar topic: "which word starts with...", "se escribe con ... inicial", etc.
    letter_shape = (
        "se escribe con" in p and "inicial" in p
        or "empieza con" in p
        or "comienza con" in p
        or "starts with" in p
        or "begins with" in p
        or "commence par" in p
        or "inizia con" in p
        or "beginnt mit" in p
        or "ile baslar" in p
        or "ile basliyor" in p
    )
    if letter_shape and not gate._central(headers, gate._ORTHOGRAPHY_CENTRAL):
        return "letter_or_spelling_trivia"

    # Morphology jargon variants that previously escaped the narrower stem list.
    morphology_terms = (
        "raiz irregular", "root irregular", "irregular root", "word root",
        "lexical root", "radice irregolare", "racine irreguliere",
        "unregelmassige wurzel", "kelime koku", "sozcuk koku",
    )
    if any(term in p for term in morphology_terms) and not gate._central(headers, gate._MORPHOLOGY_CENTRAL):
        return "morphology_terminology"

    # Arithmetic disguised in words is not language competence for ordinary language
    # lessons. Keep this deliberately high precision rather than banning every word
    # meaning "more" or "plus" in natural prose.
    arithmetic_phrases = (
        "formado por diez mas", "formed by ten plus", "sum of", "difference of",
        "product of", "toplami", "artinin", "plus seven", "plus eight", "plus nine",
    )
    if any(term in p for term in arithmetic_phrases):
        return "arithmetic"

    return None


def install(ai_engine_module):
    if getattr(ai_engine_module, "_legacy_candidate_calibration_installed", False):
        return

    from services import assessment_guard as guard
    from services import assessment_legacy_filter as gate

    # One provider call should normally be enough. The base generator already asks for
    # an over-complete raw JSON pool, and this wrapper adds a small accepted-candidate
    # headroom. Disable the guard's own second LLM call; content_engine remains the
    # single bounded fallback if the first pass truly comes back short.
    guard._MAX_REPAIR_ROUNDS = 0

    # Operation concentration is a ranking preference, not a correctness failure.
    # Rejecting it hard caused valid 10-question requests to collapse to 8/10.
    if not getattr(gate, "_legacy_operation_calibrated", False):
        original_quality_reason = gate._quality_reason

        def calibrated_quality_reason(question, *, source_text, headers, accepted, prior, operation_counts, requested):
            reason = original_quality_reason(
                question,
                source_text=source_text,
                headers=headers,
                accepted=accepted,
                prior=prior,
                operation_counts=operation_counts,
                requested=requested,
            )
            if reason == "operation_overconcentration":
                reason = None
            if reason:
                return reason
            return _extra_quality_reason(gate, question, headers)

        gate._quality_reason = calibrated_quality_reason
        gate._legacy_operation_calibrated = True

    original = ai_engine_module.ai_generate_questions

    def candidate_generate(*args, **kwargs):
        try:
            requested = max(1, int(guard._arg(args, kwargs, "count", 4, 10) or 10))
        except Exception:
            requested = 10

        # Small dynamic headroom: 10->12, 15->18, 20->24. Never inflate tiny one-off
        # requests excessively and never exceed the prompt policy's 24-candidate cap.
        headroom = max(2, int(math.ceil(requested * 0.20))) if requested >= 5 else 1
        candidate_count = min(24, requested + headroom)
        call_args, call_kwargs = _set_count(args, kwargs, candidate_count)
        candidates = original(*call_args, **call_kwargs) or []

        source_text = _source_text(guard, args, kwargs)
        headers = gate._topic_headers(source_text)
        prior = list(guard._arg(args, kwargs, "existing_questions", 6, []) or [])
        accepted = []
        operation_counts = Counter()
        reasons = Counter()

        for question in candidates:
            if len(accepted) >= requested:
                break
            if not isinstance(question, dict):
                reasons["malformed"] += 1
                continue
            reason = gate._quality_reason(
                question,
                source_text=source_text,
                headers=headers,
                accepted=accepted,
                prior=prior,
                operation_counts=operation_counts,
                requested=requested,
            )
            if reason:
                reasons[reason] += 1
                continue
            operation_counts[gate._operation_signature(question)] += 1
            accepted.append(question)

        try:
            print(
                "[ASSESSMENT-CANDIDATE-POOL] "
                f"requested={requested} asked={candidate_count} received={len(candidates)} "
                f"accepted={len(accepted)} rejected={sum(reasons.values())} "
                f"reasons={dict(sorted(reasons.items()))}",
                flush=True,
            )
        except Exception:
            pass

        return accepted

    candidate_generate.__wrapped__ = original
    ai_engine_module.ai_generate_questions = candidate_generate
    ai_engine_module._legacy_candidate_calibration_installed = True
