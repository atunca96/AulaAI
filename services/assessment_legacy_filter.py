"""Deterministic final quality gate for the stable legacy assessment engine.

Legacy remains the generator. This wrapper rejects only clear quality failures and
asks legacy for at most one refill. Lesson/material generation is never called or
modified.
"""

import math
import re
from collections import Counter
from difflib import SequenceMatcher

from services import assessment_telemetry
from services.assessment_scorecard import (
    _norm,
    _objective_proxy_repeat,
    _outside_meta_proxy_reason,
    _question_near_repeat,
    _source_grounded_proxy,
    _valid_mcq,
)

FILTER_VERSION = "legacy_quality_gate_v3"
_MAX_REFILL_ROUNDS = 1

_PRONUNCIATION_CENTRAL = (
    "pronunciation", "pronunciacion", "pronunciación", "phonetic", "fonet",
    "phonology", "fonolog", "sound", "sounds", "ses", "laut", "suono",
)
_ORTHOGRAPHY_CENTRAL = (
    "orthography", "orthographic", "spelling", "accentuation", "diacritic",
    "ortografia", "ortografía", "acentuacion", "acentuación", "tilde",
    "imla", "yazim", "yazım",
)
_MORPHOLOGY_CENTRAL = (
    "morphology", "morphological", "word formation", "morfologia", "morfología",
    "morfoloji", "prefix", "suffix", "prefij", "sufij", "morphem", "morfem",
)
_ETYMOLOGY_CENTRAL = (
    "etymology", "etymologia", "etimologia", "etimología", "word origin",
    "kelime koken", "kelime köken",
)
_CONTRAST_CENTRAL = (
    "contrast", "comparative", "comparison", "false friend", "faux ami",
    "karşılaştır", "karsilastir", "contraste", "comparacion", "comparación",
)

_SPELLING_MARKERS = (
    "spelling", "spell", "orthograph", "ortograf", "se escribe", "como se escribe",
    "cómo se escribe", "grafia", "grafía", "written", "write the", "yazim", "yazım",
)
_GRAMMAR_MARKERS = (
    "grammar", "gramat", "agreement", "conjug", "singular", "plural", "masculin",
    "feminin", "article", "preposition", "before a noun", "delante de un sustantivo",
)
_MEANING_MARKERS = (
    "what does", "meaning", "means", "significa", "que significa", "qué significa",
    "corresponde a", "which word means", "hangi anlama",
)
_REPRESENTATION_MARKERS = (
    "what word", "which word", "que palabra", "qué palabra", "what numeral", "which numeral",
    "que numeral", "qué numeral", "how is", "como se escribe", "cómo se escribe",
    "write the", "written form", "forma escrita", "forma cardinal", "cardinal form",
    "corresponde", "represents", "representa", "indica", "cantidad", "quantity",
)


def _safe_int(value, default=10):
    try:
        return max(1, int(value))
    except Exception:
        return default


def _history_row(question):
    if not isinstance(question, dict):
        return None
    return {
        "prompt": str(question.get("prompt", "")),
        "answer": str(question.get("answer", "")),
    }


def _topic_headers(source_text):
    lines = []
    for line in str(source_text or "").splitlines():
        if line.strip().upper().startswith("TOPIC "):
            lines.append(line.strip())
    return _norm(" ".join(lines))


def _level_rank(question):
    return {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}.get(
        str((question or {}).get("difficulty", "A1") or "A1").upper(), 1
    )


def _central(headers, markers):
    h = _norm(headers)
    return bool(h and any(_norm(marker) in h for marker in markers))


def _meta_allowed(reason, question, headers):
    if reason in {"phonology_terminology", "phonetic_transcription_trivia", "sound_label_trivia"}:
        return _central(headers, _PRONUNCIATION_CENTRAL)
    if reason in {"orthography_micro_trivia", "letter_or_spelling_trivia"}:
        return _central(headers, _ORTHOGRAPHY_CENTRAL)
    if reason == "morphology_terminology":
        return _central(headers, _MORPHOLOGY_CENTRAL)
    if reason == "cross_language_trivia":
        return _central(headers, _CONTRAST_CENTRAL)
    if reason in {"etymology", "historical_root"}:
        return _level_rank(question) >= 5 and _central(headers, _ETYMOLOGY_CENTRAL)
    return False


def _edit_distance(a, b):
    a, b = str(a or ""), str(b or "")
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _compact(value):
    return "".join(_norm(value).split())


def _single_token(value):
    n = _norm(value)
    return n if n and " " not in n else ""


def _pseudoform_distractors(question, source_text):
    """Reject invented spelling-neighbors while preserving real paradigms."""
    headers = _topic_headers(source_text)
    if _central(headers, _ORTHOGRAPHY_CENTRAL):
        return False

    answer_raw = str(question.get("answer", "")).strip()
    answer = _single_token(answer_raw)
    answer_compact = _compact(answer_raw)
    source_words = set(_norm(source_text).split())
    source_compact = _compact(source_text)
    suspicious = 0

    for raw in question.get("distractors") or []:
        d_raw = str(raw).strip()
        d = _single_token(d_raw)
        d_compact = _compact(d_raw)
        if not d_compact or d_compact == answer_compact:
            suspicious += 1
            continue
        if d and d in source_words:
            continue
        if d_compact and d_compact in source_compact and len(d_compact) >= 4:
            continue

        if answer and d:
            ratio = SequenceMatcher(None, answer, d).ratio()
            distance = _edit_distance(answer, d)
        else:
            ratio = SequenceMatcher(None, answer_compact, d_compact).ratio()
            distance = _edit_distance(answer_compact, d_compact)

        if distance <= 1 or ratio >= 0.76:
            suspicious += 1

    # Short real paradigms such as un/una naturally cluster; require two suspicious forms.
    if answer and len(answer) <= 3:
        return suspicious >= 2

    # Multi-word written forms such as "thirty one" vs glued pseudoforms are especially
    # diagnostic outside a central orthography lesson.
    if " " in _norm(answer_raw):
        return suspicious >= 1
    return suspicious >= 1


def _answer_leak(question):
    prompt_raw = str(question.get("prompt", ""))
    answer = str(question.get("answer", "")).strip()
    if not prompt_raw or not answer:
        return False

    answer_n = _norm(answer)
    prompt_n = _norm(prompt_raw)

    # Strong parenthetical cue: (6), (4 €), etc. while asking for a non-numeric answer.
    if not re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", answer):
        if re.search(r"\(\s*[+-]?\d+(?:[.,]\d+)?\s*(?:€|\$|£|¥|%|º|°)?\s*\)", prompt_raw):
            return True

    # Direct representation cue: a digit is explicitly given while the question asks
    # which word/form/numeral represents or corresponds to it.
    if not re.search(r"\d", answer):
        has_digit = bool(re.search(r"(?<!\w)[+-]?\d+(?:[.,]\d+)?(?!\w)", prompt_raw))
        asks_representation = any(_norm(marker) in prompt_n for marker in _REPRESENTATION_MARKERS)
        if has_digit and asks_representation:
            return True

    # Literal answer already written in a non-blank prompt.
    if len(answer_n) >= 4 and " " not in answer_n and not re.search(r"_{2,}", prompt_raw):
        if re.search(rf"(?:^|\s){re.escape(answer_n)}(?:$|\s)", f" {prompt_n} "):
            return True
    return False


def _composite_option(question):
    values = [str(question.get("answer", ""))] + [str(x) for x in (question.get("distractors") or [])]
    blank_count = len(re.findall(r"_{2,}", str(question.get("prompt", ""))))
    return blank_count >= 2 and any("/" in value for value in values)


def _operation_signature(question):
    raw = str(question.get("prompt", ""))
    p = _norm(raw)
    if re.search(r"_{2,}", raw):
        return "blank_completion"
    if any(_norm(x) in p for x in _SPELLING_MARKERS):
        return "orthography"
    if any(_norm(x) in p for x in _GRAMMAR_MARKERS):
        return "grammar"
    if any(_norm(x) in p for x in _MEANING_MARKERS):
        return "meaning_lookup"
    if "—" in raw or (":" in raw and "?" in raw):
        return "dialogue_or_context"
    return "other"


def _operation_cap(signature, requested):
    if requested < 8:
        return requested
    if signature == "blank_completion":
        return max(3, int(math.ceil(requested * 0.30)))
    if signature == "meaning_lookup":
        return max(2, int(math.ceil(requested * 0.25)))
    if signature == "orthography":
        return max(3, int(math.ceil(requested * 0.30)))
    return requested


def _duplicate_reason(question, accepted, prior):
    for old in list(prior or []) + list(accepted or []):
        if not isinstance(old, dict):
            continue
        if _question_near_repeat(question, old):
            return "semantic_repeat"
        if _objective_proxy_repeat(question, old):
            p1, p2 = _norm(question.get("prompt")), _norm(old.get("prompt"))
            a1, a2 = _norm(question.get("answer")), _norm(old.get("answer"))
            if a1 == a2 or SequenceMatcher(None, p1, p2).ratio() >= 0.70:
                return "objective_repeat"
    return None


def _quality_reason(question, *, source_text, headers, accepted, prior, operation_counts, requested):
    if not _valid_mcq(question):
        return "invalid_mcq_structure"

    meta_reason = _outside_meta_proxy_reason(question)
    if meta_reason and not _meta_allowed(meta_reason, question, headers):
        return meta_reason

    if _composite_option(question):
        return "composite_multi_blank_option"

    if _answer_leak(question):
        return "answer_revealed"

    if _pseudoform_distractors(question, source_text):
        return "pseudoform_distractors"

    grounding = _source_grounded_proxy(question, source_text)
    answer_n = _norm(question.get("answer"))
    if grounding is False and len(answer_n) >= 3:
        return "source_unsupported"

    dup = _duplicate_reason(question, accepted, prior)
    if dup:
        return dup

    signature = _operation_signature(question)
    if operation_counts.get(signature, 0) >= _operation_cap(signature, requested):
        return "operation_overconcentration"

    return None


def _filter_batch(batch, *, source_text, accepted, prior, operation_counts, requested):
    clean = []
    rejected = []
    reasons = Counter()
    headers = _topic_headers(source_text)
    for question in batch or []:
        if not isinstance(question, dict):
            reasons["malformed"] += 1
            continue
        reason = _quality_reason(
            question,
            source_text=source_text,
            headers=headers,
            accepted=list(accepted) + clean,
            prior=prior,
            operation_counts=operation_counts,
            requested=requested,
        )
        if reason:
            reasons[reason] += 1
            rejected.append(question)
            continue
        signature = _operation_signature(question)
        operation_counts[signature] += 1
        clean.append(question)
    return clean, rejected, reasons


def _strip_internal(question):
    if not isinstance(question, dict):
        return question
    public = dict(question)
    for key in list(public):
        if str(key).startswith("_assessment_") or str(key).startswith("_objective_"):
            public.pop(key, None)
    return public


def _emit_summary(*, requested, initial_count, returned, rejected, refill_rounds, reasons, operation_counts):
    try:
        trace = assessment_telemetry._ACTIVE_TRACE.get()
        request_id = trace.get("request_id") if trace else None
        assessment_telemetry._write_metric(
            "ASSESSMENT-LEGACY-FILTER",
            {
                "schema": FILTER_VERSION,
                "request_id": request_id,
                "requested_count": int(requested),
                "initial_count": int(initial_count),
                "returned_count": int(returned),
                "count_match": int(returned) == int(requested),
                "rejected_count": int(rejected),
                "refill_rounds": int(refill_rounds),
                "reason_counts": dict(sorted((reasons or {}).items())),
                "operation_counts": dict(sorted((operation_counts or {}).items())),
            },
        )
    except Exception:
        pass


def install(router_module):
    original = getattr(router_module, "_LEGACY_GENERATOR", None)
    if not callable(original) or getattr(original, "__aula_legacy_meta_filter__", False):
        return

    def filtered_legacy_generate(
        topic_ids,
        count=10,
        is_quiz=False,
        ui_lang="en",
        existing_questions=None,
        progress_callback=None,
    ):
        requested = _safe_int(count)
        history = list(existing_questions or [])
        accepted = []
        rejected_total = 0
        reasons_total = Counter()
        operation_counts = Counter()
        refill_rounds = 0
        try:
            source_text = router_module._source_text(topic_ids)
        except Exception:
            source_text = ""

        first_batch = original(
            topic_ids=topic_ids,
            count=requested,
            is_quiz=False,
            ui_lang=ui_lang,
            existing_questions=history,
            progress_callback=progress_callback,
        ) or []
        initial_count = len(first_batch)

        clean, rejected, reasons = _filter_batch(
            first_batch,
            source_text=source_text,
            accepted=accepted,
            prior=history,
            operation_counts=operation_counts,
            requested=requested,
        )
        accepted.extend(clean[:requested])
        rejected_total += len(rejected)
        reasons_total.update(reasons)
        for question in first_batch:
            row = _history_row(question)
            if row:
                history.append(row)

        # One and only one outer refill. Prompt-first generation should make this rare.
        if len(accepted) < requested and _MAX_REFILL_ROUNDS:
            refill_rounds = 1
            missing = requested - len(accepted)
            refill_count = min(requested, max(4, missing + 3))
            refill = original(
                topic_ids=topic_ids,
                count=refill_count,
                is_quiz=False,
                ui_lang=ui_lang,
                existing_questions=history,
                progress_callback=None,
            ) or []
            clean, rejected, reasons = _filter_batch(
                refill,
                source_text=source_text,
                accepted=accepted,
                prior=history,
                operation_counts=operation_counts,
                requested=requested,
            )
            room = requested - len(accepted)
            accepted.extend(clean[:room])
            rejected_total += len(rejected)
            reasons_total.update(reasons)

        final = [_strip_internal(q) for q in accepted[:requested]]

        if is_quiz and final:
            persist = getattr(router_module, "_persist_primary_questions", None)
            if callable(persist):
                persist(final)

        _emit_summary(
            requested=requested,
            initial_count=initial_count,
            returned=len(final),
            rejected=rejected_total,
            refill_rounds=refill_rounds,
            reasons=reasons_total,
            operation_counts=operation_counts,
        )
        return final

    filtered_legacy_generate.__aula_legacy_meta_filter__ = True
    filtered_legacy_generate.__wrapped__ = original
    router_module._LEGACY_GENERATOR = filtered_legacy_generate
