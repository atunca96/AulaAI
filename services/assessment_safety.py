"""Safety defaults and hard-gate fallback for assessment engine routing.

This module is assessment-only. It does not modify lesson/material generation.
"""

import os
import uuid

from services.assessment_scorecard import build_scorecard


def engine_mode():
    """Fail closed to legacy when the env flag is missing or invalid."""
    value = str(os.getenv("ASSESSMENT_ENGINE", "legacy") or "legacy").strip().lower()
    return value if value in {"legacy", "v2", "shadow"} else "legacy"


def shadow_primary():
    """Calibration defaults to legacy primary; V2 stays shadow-only until cutover."""
    value = str(os.getenv("ASSESSMENT_SHADOW_PRIMARY", "legacy") or "legacy").strip().lower()
    return value if value in {"legacy", "v2"} else "legacy"


def _safe_count(value, default=10):
    try:
        return max(1, int(value))
    except Exception:
        return default


def _hard_gate_pass(questions, requested_count):
    scorecard = build_scorecard(questions or [], requested_count, "")
    gates = scorecard.get("hard_gates") or {}
    return bool(gates.get("count_match") and gates.get("valid_structure"))


def _log_fallback(request_id, requested_count, returned_count):
    try:
        with open("pipeline.log", "a", encoding="utf-8") as handle:
            handle.write(
                f"[ASSESSMENT-SAFETY] request_id={request_id} v2_hard_gate_failed "
                f"requested={requested_count} returned={returned_count} fallback=legacy\n"
            )
    except Exception:
        pass


def install(router_module, content_engine_module):
    """Install safe defaults and an explicit-V2 fallback without touching legacy/material code."""
    if getattr(content_engine_module, "_assessment_safety_installed", False):
        return

    # The router resolves these globals at call time, so replacing them here changes
    # both missing/invalid env behavior and shadow-mode primary selection safely.
    router_module._engine_mode = engine_mode
    router_module._shadow_primary = shadow_primary

    routed_generate = content_engine_module.generate_assessment_set

    def safe_generate_assessment_set(
        topic_ids,
        count=10,
        is_quiz=False,
        ui_lang="en",
        existing_questions=None,
        progress_callback=None,
    ):
        mode = engine_mode()

        # Legacy and shadow already have the desired safety behavior once the router's
        # mode functions above are replaced. Only explicit V2 needs hard-gate fallback.
        if mode != "v2":
            return routed_generate(
                topic_ids=topic_ids,
                count=count,
                is_quiz=is_quiz,
                ui_lang=ui_lang,
                existing_questions=existing_questions,
                progress_callback=progress_callback,
            )

        requested = _safe_count(count)
        request_id = uuid.uuid4().hex
        source_text = router_module._source_text(topic_ids)
        common = {
            "topic_ids": list(topic_ids or []),
            "count": requested,
            "ui_lang": ui_lang,
            "existing_questions": existing_questions,
        }

        # Run V2 side-effect-free until it passes the non-negotiable structural gates.
        result, _ = router_module._run_engine(
            "v2",
            is_quiz=False,
            progress_callback=progress_callback,
            source_text=source_text,
            request_id=request_id,
            shadow=False,
            **common,
        )

        if _hard_gate_pass(result, requested):
            if is_quiz:
                router_module._persist_primary_questions(result)
            return result

        _log_fallback(request_id, requested, len(result or []))
        fallback, _ = router_module._run_engine(
            "legacy",
            is_quiz=False,
            progress_callback=None,
            source_text=source_text,
            request_id=request_id,
            shadow=False,
            **common,
        )
        if is_quiz:
            router_module._persist_primary_questions(fallback)
        return fallback

    content_engine_module.generate_assessment_set = safe_generate_assessment_set
    content_engine_module._assessment_safety_installed = True
