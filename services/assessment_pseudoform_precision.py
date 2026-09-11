"""Assessment-only precision tuning for pseudoform rejection.

The stable calibration already ignores single near-form distractors. This final precision
step rejects an MCQ only when all three distractors form a strong unsupported near-form
cluster. It reduces false positives in narrow vocabulary topics without weakening answer
leak, source grounding, semantic repeat, or structure checks. Lesson/material generation
is not involved.
"""


def install():
    from services import assessment_legacy_calibration as calibration
    from services import assessment_legacy_filter as gate

    if getattr(gate, "_assessment_pseudoform_precision_installed", False):
        return

    previous = gate._pseudoform_distractors

    def precise_pseudoform_distractors(question, source_text):
        # Preserve every existing exemption and only tighten an existing rejection.
        if not previous(question, source_text):
            return False
        # Two near-looking distractors are common among legitimate learner-error options
        # in inflectional/form-choice questions. Require a full three-item unsupported
        # cluster before treating the MCQ as synthetic pseudoform noise.
        return calibration._pseudoform_suspicious_count(gate, question, source_text) >= 3

    gate._pseudoform_distractors = precise_pseudoform_distractors
    gate._assessment_pseudoform_precision_installed = True
