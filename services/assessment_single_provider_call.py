"""Guarantee at most one AI question-generation call per legacy assessment request.

The legacy content engine still contains a historical top-up branch. Rather than
allowing that branch to trigger a second provider request, this guard scopes the
question generator with ContextVars so concurrent requests remain isolated.
"""

from contextvars import ContextVar


_ACTIVE = ContextVar("aula_assessment_single_call_active", default=False)
_CALLS = ContextVar("aula_assessment_single_call_count", default=0)


def install(content_engine_module, ai_engine_module):
    if getattr(content_engine_module, "_assessment_single_provider_call_installed", False):
        return

    raw_generate = ai_engine_module.ai_generate_questions
    raw_assessment = content_engine_module.generate_assessment_set

    def guarded_generate(*args, **kwargs):
        if not _ACTIVE.get():
            return raw_generate(*args, **kwargs)

        calls = _CALLS.get()
        if calls >= 1:
            try:
                requested = kwargs.get("count", args[4] if len(args) > 4 else None)
                print(
                    f"[ASSESSMENT-SINGLE-CALL] blocked_legacy_refill=1 requested={requested}",
                    flush=True,
                )
            except Exception:
                pass
            return []

        _CALLS.set(calls + 1)
        return raw_generate(*args, **kwargs)

    def wrapped_assessment(*args, **kwargs):
        active_token = _ACTIVE.set(True)
        calls_token = _CALLS.set(0)
        try:
            return raw_assessment(*args, **kwargs)
        finally:
            _CALLS.reset(calls_token)
            _ACTIVE.reset(active_token)

    ai_engine_module.ai_generate_questions = guarded_generate
    content_engine_module.generate_assessment_set = wrapped_assessment
    content_engine_module._assessment_single_provider_call_installed = True
