"""Opt-in shadow capture for manual Assessment V2 calibration.

Disabled by default. When ASSESSMENT_SHADOW_CAPTURE=1, only the V2 shadow result is
logged to Railway-visible assessment telemetry. Source lesson/material content is never
logged by this module; only the generated MCQ prompt/answer/distractors are captured.
"""

import os

from services import assessment_telemetry


def _enabled():
    value = str(os.getenv("ASSESSMENT_SHADOW_CAPTURE", "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _clean_text(value, limit):
    return str(value or "").strip()[:limit]


def _question_view(question):
    if not isinstance(question, dict):
        return None
    prompt = _clean_text(question.get("prompt"), 500)
    answer = _clean_text(question.get("answer"), 220)
    distractors = [
        _clean_text(item, 220)
        for item in (question.get("distractors") or [])[:3]
        if _clean_text(item, 220)
    ]
    if not prompt:
        return None
    return {
        "prompt": prompt,
        "answer": answer,
        "distractors": distractors,
    }


def _emit(request_id, engine, questions):
    captured = []
    for question in list(questions or [])[:30]:
        view = _question_view(question)
        if view:
            captured.append(view)
    assessment_telemetry._write_metric(
        "ASSESSMENT-SHADOW-CAPTURE",
        {
            "schema": "assessment_shadow_capture_v1",
            "request_id": request_id,
            "engine": engine,
            "contains_generated_question_text": True,
            "source_material_logged": False,
            "question_count": len(captured),
            "questions": captured,
        },
    )


def install(router_module):
    """Wrap the router run function without changing routing or persistence behavior."""
    if getattr(router_module, "_assessment_shadow_capture_installed", False):
        return

    original = router_module._run_engine

    def captured_run_engine(engine, **kwargs):
        result, trace = original(engine, **kwargs)
        if _enabled() and kwargs.get("shadow") is True and engine == "v2":
            try:
                _emit(kwargs.get("request_id"), engine, result)
            except Exception:
                pass
        return result, trace

    router_module._run_engine = captured_run_engine
    router_module._assessment_shadow_capture_installed = True
