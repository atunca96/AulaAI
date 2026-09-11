"""Domain-general calibration for the stable legacy assessment path.

Prompt-first generation stays authoritative. This layer adds only cheap deterministic
calibration: a small candidate headroom when output is naturally short, topic-aware
validation, and soft diversity selection. It never touches lesson/material generation.
"""

import json
import math
import re
from collections import Counter, OrderedDict


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


def _level_rank(value):
    return {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}.get(
        str(value or "A1").upper(), 1
    )


def _form_focused(gate, headers, question):
    op = str((question or {}).get("_objective_operation", "") or "").lower()
    h = gate._norm(headers)
    return (
        op in {"grammar", "orthography-form"}
        or " grammar" in f" {h}"
        or "grammatik" in h
        or "gramatica" in h
        or "grammaire" in h
        or "grammatica" in h
    )


def _extra_quality_reason(gate, question, headers):
    """High-precision, domain-general failures only."""
    p = gate._norm((question or {}).get("prompt", ""))
    if not p:
        return None

    # Letter-shape trivia is meta-linguistic unless spelling/orthography is central.
    letter_shape_markers = (
        "starts with", "begins with", "which letter", "what letter",
        "se escribe con", "empieza con", "comienza con", "que letra", "qué letra",
        "beginnt mit", "welcher buchstabe", "commence par", "quelle lettre",
        "inizia con", "quale lettera", "hangi harf", "ile baslar", "ile basliyor",
    )
    if any(marker in p for marker in letter_shape_markers):
        if not gate._central(headers, gate._ORTHOGRAPHY_CENTRAL):
            return "letter_or_spelling_trivia"

    # Morphological terminology is allowed only when morphology/form analysis is central.
    morphology_markers = (
        "word root", "lexical root", "irregular root", "morphological root",
        "raiz irregular", "raiz lexica", "racine lexicale", "radice lessicale",
        "wortstamm", "wortwurzel", "kelime koku", "sozcuk koku",
    )
    if any(marker in p for marker in morphology_markers):
        if not gate._central(headers, gate._MORPHOLOGY_CENTRAL):
            return "morphology_terminology"

    # Arithmetic is not language competence unless mathematics itself is the source topic.
    # This catches symbolic arithmetic and common arithmetic instructions across several
    # language families without depending on any particular vocabulary topic.
    if re.search(r"\b\d+(?:[.,]\d+)?\s*[+\-×*/÷]\s*\d+(?:[.,]\d+)?\b", p):
        return "arithmetic"
    arithmetic_markers = (
        "sum of", "difference of", "product of", "divided by", "subtract", "multiply",
        "suma de", "diferencia de", "producto de", "dividido por", "resta", "multiplica",
        "summe von", "differenz von", "produkt von", "geteilt durch", "subtrahiere", "multipliziere",
        "somme de", "difference de", "produit de", "divise par",
        "somma di", "differenza di", "prodotto di", "diviso per",
        "toplami", "farki", "carpimi", "bolumu",
    )
    if any(marker in p for marker in arithmetic_markers):
        return "arithmetic"

    return None


def _candidate_count(guard, args, kwargs, requested):
    topic_type = guard._norm(guard._arg(args, kwargs, "topic_type", 1, ""))
    level = _level_rank(guard._arg(args, kwargs, "level", 5, "A1"))

    # Grammar/mixed and B1+ items are naturally longer; oversampling them increases
    # truncation risk and latency. Shorter A1/A2 vocabulary/context sets can afford a
    # small headroom so the deterministic gate has choices without another LLM call.
    verbose = (
        "grammar" in topic_type
        or "mixed" in topic_type
        or level >= 3
    )
    if verbose or requested < 5:
        return requested
    headroom = max(2, int(math.ceil(requested * 0.20)))
    return min(24, requested + headroom)


def _diversity_key(gate, question):
    op = str((question or {}).get("_objective_operation", "") or "").strip().lower()
    if op:
        return op
    return gate._operation_signature(question)


def _round_robin_select(gate, candidates, requested):
    """Prefer breadth without rejecting otherwise valid questions."""
    buckets = OrderedDict()
    for question in candidates:
        buckets.setdefault(_diversity_key(gate, question), []).append(question)
    selected = []
    while len(selected) < requested and buckets:
        progressed = False
        for key in list(buckets):
            bucket = buckets[key]
            if bucket:
                selected.append(bucket.pop(0))
                progressed = True
                if len(selected) >= requested:
                    break
            if not bucket:
                buckets.pop(key, None)
        if not progressed:
            break
    return selected[:requested]


def install(ai_engine_module):
    if getattr(ai_engine_module, "_legacy_candidate_calibration_installed", False):
        return

    from services import assessment_guard as guard
    from services import assessment_legacy_filter as gate

    # There must be only one LLM refill owner. Content engine remains the bounded
    # supplementary pass; the semantic guard itself never starts another provider call.
    guard._MAX_REPAIR_ROUNDS = 0

    # Keep canonical objective metadata through the in-memory candidate stage. The final
    # legacy gate strips all _objective_* fields before anything is returned publicly.
    def _keep_internal_question(q):
        return dict(q) if isinstance(q, dict) else q
    guard._public_question = _keep_internal_question

    if not getattr(gate, "_legacy_domain_general_calibrated", False):
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

            # Format concentration is a ranking preference, never a correctness failure.
            if reason == "operation_overconcentration":
                reason = None

            # Near-form alternatives are often the whole point of a grammar/form question
            # (auxiliary choice, agreement, conjugation, case, etc.). Do not apply a
            # spelling-pseudoform heuristic when form discrimination is central.
            if reason == "pseudoform_distractors" and _form_focused(gate, headers, question):
                reason = None

            if reason:
                return reason
            return _extra_quality_reason(gate, question, headers)

        gate._quality_reason = calibrated_quality_reason
        gate._legacy_domain_general_calibrated = True

    original = ai_engine_module.ai_generate_questions

    def candidate_generate(*args, **kwargs):
        try:
            requested = max(1, int(guard._arg(args, kwargs, "count", 4, 10) or 10))
        except Exception:
            requested = 10

        candidate_count = _candidate_count(guard, args, kwargs, requested)
        call_args, call_kwargs = _set_count(args, kwargs, candidate_count)
        candidates = original(*call_args, **call_kwargs) or []

        source_text = _source_text(guard, args, kwargs)
        headers = gate._topic_headers(source_text)
        prior = list(guard._arg(args, kwargs, "existing_questions", 6, []) or [])
        clean = []
        operation_counts = Counter()
        reasons = Counter()

        for question in candidates:
            if not isinstance(question, dict):
                reasons["malformed"] += 1
                continue
            reason = gate._quality_reason(
                question,
                source_text=source_text,
                headers=headers,
                accepted=clean,
                prior=prior,
                operation_counts=operation_counts,
                requested=requested,
            )
            if reason:
                reasons[reason] += 1
                continue
            operation_counts[gate._operation_signature(question)] += 1
            clean.append(question)

        accepted = _round_robin_select(gate, clean, requested)

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
