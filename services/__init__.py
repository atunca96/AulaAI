# Init module for services

# Install the assessment semantic-diversity guard when the services package loads.
# The guard wraps ai_generate_questions without changing existing call sites.
try:
    from . import ai_engine as _ai_engine
    from .assessment_guard import install as _install_assessment_guard
    _install_assessment_guard(_ai_engine)
except Exception:
    # Never block application startup if the optional guard cannot initialize.
    pass
