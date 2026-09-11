"""Shared assessment telemetry for legacy and V2 engines.

Only records timing/count metadata; prompts, answers and lesson content are never logged.
"""

import contextvars
import json
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

_ACTIVE_TRACE = contextvars.ContextVar("assessment_trace", default=None)


def _ms(seconds):
    return round(max(0.0, seconds) * 1000.0, 2)


def _detect_phase(messages):
    try:
        text = "\n".join(
            str(m.get("content", "")) for m in (messages or []) if isinstance(m, dict)
        )
    except Exception:
        text = ""
    if "Assessment Planner V2" in text:
        return "planner"
    if "Assessment Writer V2" in text:
        return "writer"
    if "Pedagogic Assessment Engine" in text:
        return "legacy_writer"
    return "provider_other"


def install(ai_engine_module):
    """Wrap the final _call_ai path so both legacy and V2 use identical timing."""
    if getattr(ai_engine_module, "_assessment_telemetry_installed", False):
        return
    original = ai_engine_module._call_ai

    def timed_call(messages, *args, **kwargs):
        trace = _ACTIVE_TRACE.get()
        if trace is None:
            return original(messages, *args, **kwargs)

        phase = _detect_phase(messages)
        model = str(kwargs.get("model") or "default")
        start = time.perf_counter()
        ok = False
        try:
            result = original(messages, *args, **kwargs)
            ok = True
            return result
        finally:
            elapsed = _ms(time.perf_counter() - start)
            trace["provider_ms"] = round(trace.get("provider_ms", 0.0) + elapsed, 2)
            trace["provider_calls"] = int(trace.get("provider_calls", 0)) + 1
            trace.setdefault("provider_by_phase_ms", {})[phase] = round(
                trace.get("provider_by_phase_ms", {}).get(phase, 0.0) + elapsed, 2
            )
            trace.setdefault("provider_calls_by_phase", {})[phase] = (
                trace.get("provider_calls_by_phase", {}).get(phase, 0) + 1
            )
            trace.setdefault("models", {})[model] = trace.get("models", {}).get(model, 0) + 1
            if not ok:
                trace["provider_errors"] = int(trace.get("provider_errors", 0)) + 1

    ai_engine_module._call_ai = timed_call
    ai_engine_module._assessment_telemetry_installed = True


@contextmanager
def trace_assessment(engine, requested_count, topic_count, request_id=None, shadow=False):
    trace = {
        "schema": "assessment_metric_v1",
        "request_id": request_id or uuid.uuid4().hex,
        "engine": str(engine),
        "shadow": bool(shadow),
        "requested_count": int(requested_count),
        "topic_count": int(topic_count),
        "provider_ms": 0.0,
        "provider_calls": 0,
        "provider_errors": 0,
        "provider_by_phase_ms": {},
        "provider_calls_by_phase": {},
        "models": {},
    }
    token = _ACTIVE_TRACE.set(trace)
    started = time.perf_counter()
    try:
        yield trace
    except Exception as exc:
        trace["error"] = f"{type(exc).__name__}: {str(exc)[:220]}"
        raise
    finally:
        trace["total_ms"] = _ms(time.perf_counter() - started)
        _ACTIVE_TRACE.reset(token)


def complete_trace(trace, returned_count, scorecard=None, error=None):
    trace["returned_count"] = int(returned_count or 0)
    trace["count_match"] = trace["returned_count"] == trace.get("requested_count")
    if scorecard is not None:
        trace["scorecard"] = scorecard
    if error and not trace.get("error"):
        trace["error"] = str(error)[:240]
    trace["logged_at"] = datetime.now(timezone.utc).isoformat()
    _write_metric("ASSESSMENT-METRIC", trace)
    return trace


def log_shadow_comparison(request_id, primary_trace, shadow_trace):
    record = {
        "schema": "assessment_shadow_v1",
        "request_id": request_id,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "primary": primary_trace,
        "shadow": shadow_trace,
    }
    _write_metric("ASSESSMENT-SHADOW", record)
    return record


def _write_metric(prefix, payload):
    try:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with open("pipeline.log", "a", encoding="utf-8") as handle:
            handle.write(f"[{prefix}] {line}\n")
    except Exception:
        pass
