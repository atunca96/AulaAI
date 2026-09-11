# Init module for services

# Keep the legacy assessment safeguards available for the legacy engine.
try:
    from . import ai_engine as _ai_engine
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
    _install_assessment_output_budget(_ai_engine)
    _install_assessment_prompt_policy(_ai_engine)
    _install_assessment_guard(_ai_engine)
    _install_assessment_evidence_balance(_ai_engine)
    _install_assessment_legacy_calibration(_ai_engine)
    _install_assessment_small_supplement_pool()
    _install_assessment_pseudoform_precision()
    _install_assessment_batch_balance_prompt(_ai_engine)
    _install_assessment_direct_single_pass_experiment(_ai_engine, _raw_assessment_generate_questions)
except Exception:
    pass

# Curriculum reliability layer.
try:
    from .curriculum_direct_generator import install as _install_curriculum_direct_generator
    _install_curriculum_direct_generator(_ai_engine)
except Exception:
    pass

# Bilingual finishing integrity.
try:
    from . import bilingual_finisher as _bilingual_finisher
    from .bilingual_translation_guard import install as _install_bilingual_translation_guard
    _install_bilingual_translation_guard(_bilingual_finisher)
except Exception:
    pass

# Final visible material state: one stable persisted source for EN letter notes, native
# Turkish notes, and pre-localized lesson-end MCQs. This supersedes the older
# material_bilingual_canonicalizer path, which could rewrite a correct English note
# into a different version after a language toggle.
try:
    from .material_display_stabilizer import install as _install_material_display_stabilizer
    _install_material_display_stabilizer(_bilingual_finisher, _ai_engine)
except Exception:
    pass

# Deterministic browser rendering/state. V4 deliberately does not perform async
# pronunciation-note rewrites; toggling language can no longer mutate the English note.
try:
    from .runtime_content_integrity_guard_v4 import install as _install_runtime_content_integrity_guard_v4
    _install_runtime_content_integrity_guard_v4(_bilingual_finisher)
except Exception:
    pass

# Provider telemetry.
try:
    from .assessment_telemetry import install as _install_assessment_telemetry
    _install_assessment_telemetry(_ai_engine)
except Exception:
    pass

# Unified assessment routing.
try:
    from . import content_engine as _content_engine

    # The historical content engine contains a top-up AI pass. Keep the old code for
    # rollback, but guarantee that one assessment request can make only one provider
    # question-generation call.
    from .assessment_single_provider_call import install as _install_assessment_single_provider_call
    _install_assessment_single_provider_call(_content_engine, _ai_engine)

    from . import assessment_router_v2 as _assessment_router_v2
    from .assessment_router_v2 import install as _install_assessment_router_v2
    _install_assessment_router_v2(_content_engine)

    try:
        from .assessment_legacy_filter import install as _install_assessment_legacy_filter
        _install_assessment_legacy_filter(_assessment_router_v2)
    except Exception:
        pass

    try:
        from .assessment_engine_v2_validated import install as _install_assessment_objective_validator
        _install_assessment_objective_validator(_assessment_router_v2)
    except Exception:
        pass

    try:
        from .assessment_shadow_capture import install as _install_assessment_shadow_capture
        _install_assessment_shadow_capture(_assessment_router_v2)
    except Exception:
        pass

    from .assessment_safety import install as _install_assessment_safety
    _install_assessment_safety(_assessment_router_v2, _content_engine)
except Exception:
    pass
