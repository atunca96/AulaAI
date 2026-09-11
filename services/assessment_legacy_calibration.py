"""Domain-general calibration for the stable legacy assessment path.

Prompt-first generation stays authoritative. This layer owns the single bounded LLM
repair for legacy assessments, keeps internal objective metadata alive across the
assessment-only transformation path, and applies cheap deterministic selection.
Lesson/material generation is never touched.
"""

import json
import math
import re
from collections import Counter, OrderedDict
from difflib import SequenceMatcher

_INTERNAL_OP_RE = re.compile(r"^\s*\[\[AULAOBJ:([a-z-]+)\]\]\s*", re.I)


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


def _objective_operation(question):
    op = str((question or {}).get("_objective_operation", "") or "").strip().lower()
    if op:
        return op
    match = _INTERNAL_OP_RE.match(str((question or {}).get("why", "") or ""))
    return match.group(1).lower() if match else ""


def _form_focused(gate, headers, question):
    op = _objective_operation(question)
    h = gate._norm(headers)
    return (
        op in {"grammar", "orthography-form"}
        or " grammar" in f" {h}"
        or "grammatik" in h
        or "gramatica" in h
        or "grammaire" in h
        or "grammatica" in h
    )


def _pseudoform_suspicious_count(gate, question, source_text):
    """Count strong spelling-neighbour signals without treating one neighbour as proof."""
    answer_raw = str((question or {}).get("answer", "") or "").strip()
    answer = gate._single_token(answer_raw)
    answer_compact = gate._compact(answer_raw)
    source_words = set(gate._norm(source_text).split())
    source_compact = gate._compact(source_text)
    suspicious = 0

    for raw in (question or {}).get("distractors") or []:
        d_raw = str(raw or "").strip()
        d = gate._single_token(d_raw)
        d_compact = gate._compact(d_raw)
        if not d_compact or d_compact == answer_compact:
            suspicious += 1
            continue
        if d and d in source_words:
            continue
        if d_compact and d_compact in source_compact and len(d_compact) >= 4:
            continue

        if answer and d:
            ratio = SequenceMatcher(None, answer, d).ratio()
            distance = gate._edit_distance(answer, d)
        else:
            ratio = SequenceMatcher(None, answer_compact, d_compact).ratio()
            distance = gate._edit_distance(answer_compact, d_compact)
        if distance <= 1 or ratio >= 0.76:
            suspicious += 1
    return suspicious


def _extra_quality_reason(gate, question, headers):
    """High-precision, domain-general failures only."""
    p = gate._norm((question or {}).get("prompt", ""))
    if not p:
        return None

    letter_shape_markers = (
        "starts with", "begins with", "which letter", "what letter",
        "se escribe con", "empieza con", "comienza con", "que letra", "qué letra",
        "beginnt mit", "welcher buchstabe", "commence par", "quelle lettre",
        "inizia con", "quale lettera", "hangi harf", "ile baslar", "ile basliyor",
    )
    if any(marker in p for marker in letter_shape_markers):
        if not gate._central(headers, gate._ORTHOGRAPHY_CENTRAL):
            return "letter_or_spelling_trivia"

    morphology_markers = (
        "word root", "lexical root", "irregular root", "morphological root",
        "raiz irregular", "raiz lexica", "racine lexicale", "radice lessicale",
        "wortstamm", "wortwurzel", "kelime koku", "sozcuk koku",
    )
    if any(marker in p for marker in morphology_markers):
        if not gate._central(headers, gate._MORPHOLOGY_CENTRAL):
            return "morphology_terminology"

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
    verbose = "grammar" in topic_type or "mixed" in topic_type or level >= 3
    if verbose or requested < 5:
        return requested
    headroom = max(2, int(math.ceil(requested * 0.20)))
    return min(24, requested + headroom)


def _repair_count(requested, missing):
    if missing <= 0:
        return 0
    # This is the only LLM repair. Give narrow/high-rejection topics enough candidates
    # to finish the requested set in this same bounded provider call, so content_engine
    # does not need to open a third supplementary call for a leftover 1–2 items.
    return min(max(6, missing * 3 + 4), max(6, min(12, requested + 2)))


def _diversity_key(gate, question):
    op = _objective_operation(question)
    return op or gate._operation_signature(question)


def _round_robin_select(gate, candidates, requested):
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

    # Candidate calibration is the single LLM repair owner. Neither the semantic guard
    # nor the final legacy gate may launch another provider refill.
    guard._MAX_REPAIR_ROUNDS = 0
    gate._MAX_REFILL_ROUNDS = 0

    # Preserve only the objective operation through content_engine by encoding it inside
    # `why`, a field content_engine already carries. The final gate strips this marker
    # before persistence/public return, so internal metadata never reaches users.
    def _keep_internal_question(q):
        if not isinstance(q, dict):
            return q
        public = dict(q)
        op = str(q.get("_objective_operation", "") or "").strip().lower()
        why = str(public.get("why", "") or "")
        if op and not _INTERNAL_OP_RE.match(why):
            public["why"] = f"[[AULAOBJ:{op}]] {why}".strip()
        return public

    guard._public_question = _keep_internal_question

    original_strip_internal = gate._strip_internal
    if not getattr(gate, "_legacy_internal_marker_calibrated", False):
        def calibrated_strip_internal(question):
            public = original_strip_internal(question)
            if isinstance(public, dict):
                public["why"] = _INTERNAL_OP_RE.sub("", str(public.get("why", "") or "")).lstrip()
            return public
        gate._strip_internal = calibrated_strip_internal
        gate._legacy_internal_marker_calibrated = True

    if not getattr(gate, "_legacy_domain_general_calibrated", False):
        original_quality_reason = gate._quality_reason
        original_pseudoform = gate._pseudoform_distractors

        def calibrated_pseudoform_distractors(question, source_text):
            # Preserve explicit orthography/form exemptions first.
            headers = gate._topic_headers(source_text)
            if _form_focused(gate, headers, question):
                return False
            if not original_pseudoform(question, source_text):
                return False
            # One close-looking distractor is weak evidence and causes false positives
            # across inflection-rich languages. Require a cluster of at least two
            # unsupported near-forms before hard-rejecting the whole MCQ.
            return _pseudoform_suspicious_count(gate, question, source_text) >= 2

        gate._pseudoform_distractors = calibrated_pseudoform_distractors

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
        gate._legacy_domain_general_calibrated = True

    # Candidate calibration already performed the semantic/pedagogical quality pass.
    # The final legacy gate must not re-classify accepted items under a slightly different
    # source/header view and shrink a complete set. Keep the final pass structural only.
    if not getattr(gate, "_legacy_finalizer_structural_only", False):
        def structural_final_filter(batch, *, source_text, accepted, prior, operation_counts, requested):
            clean = []
            rejected = []
            reasons = Counter()
            for question in batch or []:
                if not isinstance(question, dict) or not gate._valid_mcq(question):
                    reasons["invalid_mcq_structure"] += 1
                    rejected.append(question)
                    continue
                operation_counts[gate._operation_signature(question)] += 1
                clean.append(question)
            return clean, rejected, reasons

        gate._filter_batch = structural_final_filter
        gate._legacy_finalizer_structural_only = True

    original = ai_engine_module.ai_generate_questions

    def _filter_candidates(candidates, *, source_text, headers, prior, requested, accepted_seed=None):
        clean = list(accepted_seed or [])
        operation_counts = Counter(gate._operation_signature(q) for q in clean if isinstance(q, dict))
        reasons = Counter()
        for question in candidates or []:
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
        return clean, reasons

    def candidate_generate(*args, **kwargs):
        try:
            requested = max(1, int(guard._arg(args, kwargs, "count", 4, 10) or 10))
        except Exception:
            requested = 10

        source_text = _source_text(guard, args, kwargs)
        headers = gate._topic_headers(source_text)
        prior = list(guard._arg(args, kwargs, "existing_questions", 6, []) or [])

        candidate_count = _candidate_count(guard, args, kwargs, requested)
        call_args, call_kwargs = _set_count(args, kwargs, candidate_count)
        first = original(*call_args, **call_kwargs) or []
        clean, reasons = _filter_candidates(
            first,
            source_text=source_text,
            headers=headers,
            prior=prior,
            requested=requested,
        )

        repair_calls = 0
        if len(clean) < requested:
            missing = requested - len(clean)
            repair_n = _repair_count(requested, missing)
            if repair_n:
                repair_calls = 1
                repair_args, repair_kwargs = _set_count(args, kwargs, repair_n)
                repair_context = prior + [q for q in first if isinstance(q, dict)] + clean
                repair_args, repair_kwargs = guard._with_existing(repair_args, repair_kwargs, repair_context)
                extra = original(*repair_args, **repair_kwargs) or []
                clean, repair_reasons = _filter_candidates(
                    extra,
                    source_text=source_text,
                    headers=headers,
                    prior=repair_context,
                    requested=requested,
                    accepted_seed=clean,
                )
                reasons.update(repair_reasons)

        accepted = _round_robin_select(gate, clean, requested)

        try:
            print(
                "[ASSESSMENT-CANDIDATE-POOL] "
                f"requested={requested} asked={candidate_count} received={len(first)} "
                f"accepted={len(accepted)} rejected={sum(reasons.values())} repairs={repair_calls} "
                f"reasons={dict(sorted(reasons.items()))}",
                flush=True,
            )
        except Exception:
            pass

        return accepted

    candidate_generate.__wrapped__ = original
    ai_engine_module.ai_generate_questions = candidate_generate
    ai_engine_module._legacy_candidate_calibration_installed = True
