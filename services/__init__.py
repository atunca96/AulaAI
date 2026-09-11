# Init module for services

# Keep the legacy assessment safeguards available for the legacy engine.
try:
    from . import ai_engine as _ai_engine
    from .assessment_prompt_policy import install as _install_assessment_prompt_policy
    from .assessment_guard import install as _install_assessment_guard
    from .assessment_evidence_balance import install as _install_assessment_evidence_balance
    _install_assessment_prompt_policy(_ai_engine)
    _install_assessment_guard(_ai_engine)
    _install_assessment_evidence_balance(_ai_engine)
except Exception:
    # Never block application startup if legacy assessment safeguards cannot initialize.
    pass

# Install one outer provider timer AFTER legacy wrappers but BEFORE V2 imports _call_ai.
# This gives legacy and V2 identical provider_ms/provider_calls instrumentation.
try:
    from .assessment_telemetry import install as _install_assessment_telemetry
    _install_assessment_telemetry(_ai_engine)
except Exception:
    pass

# Route unified assessment generation according to ASSESSMENT_ENGINE=legacy|v2|shadow.
# Lesson/material generation is not changed.
try:
    from . import content_engine as _content_engine
    from .assessment_router_v2 import install as _install_assessment_router_v2
    _install_assessment_router_v2(_content_engine)
except Exception:
    # Legacy generate_assessment_set remains available if the router cannot load.
    pass
