def install(ai_engine_module):
    if getattr(ai_engine_module, "_assessment_output_budget_installed", False):
        return
    original_call = ai_engine_module._call_ai
    def budgeted_call(messages, *args, **kwargs):
        if isinstance(messages, list) and any(
            isinstance(m, dict)
            and m.get("role") == "system"
            and "Pedagogic Assessment Engine" in str(m.get("content", ""))
            for m in messages
        ):
            kwargs = dict(kwargs)
            kwargs["max_tokens"] = 5000
        return original_call(messages, *args, **kwargs)
    ai_engine_module._call_ai = budgeted_call
    ai_engine_module._assessment_output_budget_installed = True
