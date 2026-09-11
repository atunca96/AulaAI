# Init module for services

# Install assessment safeguards when the services package loads.
# Prompt policy runs first, semantic guard second, and the evidence balancer last so
# its read-only source pack is the outermost adapter for assessment calls.
try:
    from . import ai_engine as _ai_engine
    from .assessment_prompt_policy import install as _install_assessment_prompt_policy
    from .assessment_guard import install as _install_assessment_guard
    from .assessment_evidence_balance import install as _install_assessment_evidence_balance
    _install_assessment_prompt_policy(_ai_engine)
    _install_assessment_guard(_ai_engine)
    _install_assessment_evidence_balance(_ai_engine)
except Exception:
    # Never block application startup if an optional assessment safeguard cannot initialize.
    pass
