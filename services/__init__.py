# Init module for services

# Legacy assessment safeguards remain installed for the legacy engine, but all normal
# unified quiz/activity generation is routed through Assessment Engine V2 below.
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

# Assessment Engine V2 owns generate_assessment_set. This is assessment-only and does
# not alter lesson/material generation.
try:
    from . import content_engine as _content_engine
    from .assessment_router_v2 import install as _install_assessment_router_v2
    _install_assessment_router_v2(_content_engine)
except Exception:
    # Keep startup safe; legacy generate_assessment_set remains available if V2 cannot load.
    pass
