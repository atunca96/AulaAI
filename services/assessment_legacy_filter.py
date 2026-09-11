"""Small deterministic post-filter for the stable legacy assessment engine.

Legacy generation remains the source of questions. This wrapper only removes
known meta/trivia failures and asks legacy to refill missing slots. Lesson/material
generation is never called or modified.
"""

from collections import Counter

from services import assessment_telemetry
from services.assessment_scorecard import _outside_meta_proxy_reason

FILTER_VERSION = "legacy_meta_filter_v1"
_MAX_REFILL_ROUNDS = 3


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


def _filter_batch(batch):
    accepted = []
    rejected = []
    reasons = Counter()
    for question in batch or []:
        if not isinstance(question, dict):
            continue
        reason = _outside_meta_proxy_reason(question)
        if reason:
            reasons[reason] += 1
            rejected.append(question)
        else:
            accepted.append(question)
    return accepted, rejected, reasons


def _emit_summary(*, requested, initial_count, returned, rejected, refill_rounds, reasons):
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
            },
        )
    except Exception:
        pass


def install(router_module):
    """Wrap router_module._LEGACY_GENERATOR once, preserving legacy behavior otherwise."""
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
        refill_rounds = 0

        # Always generate side-effect-free. Only the final filtered set may be persisted.
        first_batch = original(
            topic_ids=topic_ids,
            count=requested,
            is_quiz=False,
            ui_lang=ui_lang,
            existing_questions=history,
            progress_callback=progress_callback,
        ) or []
        initial_count = len(first_batch)

        clean, rejected, reasons = _filter_batch(first_batch)
        accepted.extend(clean[:requested])
        rejected_total += len(rejected)
        reasons_total.update(reasons)
        for question in first_batch:
            row = _history_row(question)
            if row:
                history.append(row)

        # Reuse legacy itself for top-ups. Oversample small gaps so one bad refill
        # does not immediately reduce the final requested count.
        while len(accepted) < requested and refill_rounds < _MAX_REFILL_ROUNDS:
            refill_rounds += 1
            missing = requested - len(accepted)
            refill_count = min(requested, max(4, missing * 2))
            refill = original(
                topic_ids=topic_ids,
                count=refill_count,
                is_quiz=False,
                ui_lang=ui_lang,
                existing_questions=history,
                progress_callback=None,
            ) or []
            if not refill:
                break

            clean, rejected, reasons = _filter_batch(refill)
            room = requested - len(accepted)
            accepted.extend(clean[:room])
            rejected_total += len(rejected)
            reasons_total.update(reasons)
            for question in refill:
                row = _history_row(question)
                if row:
                    history.append(row)

        final = accepted[:requested]

        # Direct legacy mode used to persist inside the generator. Because filtering
        # now happens before persistence, persist only the accepted final set once.
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
        )
        return final

    filtered_legacy_generate.__aula_legacy_meta_filter__ = True
    filtered_legacy_generate.__wrapped__ = original
    router_module._LEGACY_GENERATOR = filtered_legacy_generate
