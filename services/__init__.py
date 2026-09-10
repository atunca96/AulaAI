# Init module for services

# Install assessment safeguards when the services package loads.
# Prompt policy runs first so every assessment generation call receives the V6 rules;
# the semantic guard then filters any duplicates/quality misses that still escape.
try:
    from . import ai_engine as _ai_engine
    from .assessment_prompt_policy import install as _install_assessment_prompt_policy
    from .assessment_guard import install as _install_assessment_guard
    _install_assessment_prompt_policy(_ai_engine)
    _install_assessment_guard(_ai_engine)
except Exception:
    # Never block application startup if an optional assessment safeguard cannot initialize.
    pass
