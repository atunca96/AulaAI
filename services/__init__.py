# Init module for services

# Keep the legacy assessment safeguards available for the legacy engine.
try:
    from . import ai_engine as _ai_engine
    # Temporary experiment: preserve the raw assessment generator before any guard/calibration wrappers.
    _raw_assessment_generate_questions = _ai_engine.ai_generate_questions
    from .assessment_prompt_policy import install as _install_assessment_prompt_policy
    from .assessment_output_budget import install as _install_assessment_output_budget
    from .assessment_guard import install as _install_assessment_guard
    from .assessment_evidence_balance import install as _install_assessment_evidence_balance
    from .assessment_legacy_calibration import install as _install_assessment_legacy_calibration
    from .assessment_small_supplement_pool import install as _install_assessment_small_supplement_pool
    from .assessment_pseudoform_precision import install as _install_assessment_pseudoform_precision
    from .assessment_batch_balance_prompt import install as _install_assessment_batch_balance_prompt
    from .assessment_direct_single_pass_experiment import install as _install_assessment_direct_single_pass_experiment
    # Install the 5k budget INSIDE the prompt-policy wrapper so the policy's legacy
    # 2500 clamp is overridden only for assessment calls at the final provider boundary.
    _install_assessment_output_budget(_ai_engine)
    _install_assessment_prompt_policy(_ai_engine)
    _install_assessment_guard(_ai_engine)
    _install_assessment_evidence_balance(_ai_engine)
    _install_assessment_legacy_calibration(_ai_engine)
    _install_assessment_small_supplement_pool()
    _install_assessment_pseudoform_precision()
    _install_assessment_batch_balance_prompt(_ai_engine)
    # TEMPORARY: bypass all assessment candidate filtering/repair and expose one raw model pass.
    _install_assessment_direct_single_pass_experiment(_ai_engine, _raw_assessment_generate_questions)
except Exception:
    # Never block application startup if legacy assessment safeguards cannot initialize.
    pass

# Curriculum-only reliability layer. It replaces only ai_generate_curriculum with
# an exact 6x5, one-retry bounded generator.
try:
    from .curriculum_direct_generator import install as _install_curriculum_direct_generator
    _install_curriculum_direct_generator(_ai_engine)
except Exception:
    pass

# Bilingual finishing integrity: never persist English text as a Turkish translation.
try:
    from . import bilingual_finisher as _bilingual_finisher
    from .bilingual_translation_guard import install as _install_bilingual_translation_guard
    _install_bilingual_translation_guard(_bilingual_finisher)
except Exception:
    pass

# Material bilingual canonicalization. After normal lesson generation/finalization,
# persist fact-aligned native EN/TR pedagogical views and localized embedded MCQ fields.
# A good Turkish explanation is preserved rather than flattened into literal English parity.
try:
    from .material_bilingual_canonicalizer import install as _install_material_bilingual_canonicalizer
    _install_material_bilingual_canonicalizer(_bilingual_finisher, _ai_engine)
except Exception:
    pass

# Frontend language/state integrity for already-generated material and deterministic
# rendering of the canonical fields created above.
try:
    from .runtime_content_integrity_guard import install as _install_runtime_content_integrity_guard
    _install_runtime_content_integrity_guard(_bilingual_finisher)
except Exception:
    pass

# Install one outer provider timer AFTER legacy wrappers but BEFORE V2 imports _call_ai.
# This gives legacy and V2 identical provider_ms/provider_calls instrumentation.
try:
    from .assessment_telemetry import install as _install_assessment_telemetry
    _install_assessment_telemetry(_ai_engine)
except Exception:
    pass

# Route unified assessment generation according to ASSESSMENT_ENGINE=legacy|v2|shadow.
try:
    from . import content_engine as _content_engine
    from . import assessment_router_v2 as _assessment_router_v2
    from .assessment_router_v2 import install as _install_assessment_router_v2
    _install_assessment_router_v2(_content_engine)

    # Legacy-only deterministic final quality gate. The candidate calibration above
    # preselects from a small one-call pool; this remains the final safety net.
    try:
        from .assessment_legacy_filter import install as _install_assessment_legacy_filter
        _install_assessment_legacy_filter(_assessment_router_v2)
    except Exception:
        pass

    # Objective validation is optional at startup: if it cannot initialize, routing still
    # continues to the safety layer below instead of silently losing fail-closed defaults.
    try:
        from .assessment_engine_v2_validated import install as _install_assessment_objective_validator
        _install_assessment_objective_validator(_assessment_router_v2)
    except Exception:
        pass

    # Manual calibration capture is explicitly opt-in via ASSESSMENT_SHADOW_CAPTURE=1.
    try:
        from .assessment_shadow_capture import install as _install_assessment_shadow_capture
        _install_assessment_shadow_capture(_assessment_router_v2)
    except Exception:
        pass

    # Safety is deliberately installed after the router.
    from .assessment_safety import install as _install_assessment_safety
    _install_assessment_safety(_assessment_router_v2, _content_engine)
except Exception:
    # Legacy generate_assessment_set remains available if the router/safety layer cannot load.
    pass
