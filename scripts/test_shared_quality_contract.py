#!/usr/bin/env python3
"""Regression: authoring and review share one quality contract and agreement proof."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import prompts as P
from services.authoring import quality_gate as Q
from services.authoring.quality_contract import (
    QUALITY_CONTRACT_VERSION,
    SHARED_QUALITY_CONTRACT,
    REPAIR_QUALITY_GUARDRAILS,
)


lesson = P.build_lesson_system(language="Spanish", level="A1", track="tr")
assessment = P.build_assessment_system(language="Spanish", level="A1", track="tr")

for label, system in (
    ("lesson generation", lesson),
    ("assessment generation", assessment),
    ("lesson review", Q._LESSON_REVIEW_SYSTEM),
    ("risk review", Q._RISK_REVIEW_SYSTEM),
    ("assessment review", Q._ASSESSMENT_REVIEW_SYSTEM),
):
    assert SHARED_QUALITY_CONTRACT in system, f"{label} drifted from shared quality contract"
    assert QUALITY_CONTRACT_VERSION in system, f"{label} omitted contract version"

for label, system in (
    ("exact target repair", Q._EXACT_TARGET_REPAIR_SYSTEM),
    ("duplicate stem repair", Q._EXACT_DUPLICATE_STEM_REPAIR_SYSTEM),
    ("missing transcription repair", Q._MISSING_TRANSCRIPTION_REPAIR_SYSTEM),
):
    assert REPAIR_QUALITY_GUARDRAILS in system, f"{label} drifted from repair guardrails"

# The exact Spanish A1 failure class that motivated the contract must be named
# generically, not patched as a Spanish/persona special case.
assert "grammatical controller/trigger" in SHARED_QUALITY_CONTRACT
assert "Grammatical gender is not real-world sex" in SHARED_QUALITY_CONTRACT
assert "context-sensitive allophony/assimilation" in SHARED_QUALITY_CONTRACT
assert "Translate meaning" in SHARED_QUALITY_CONTRACT
assert "learner-visible grammatical controller/trigger" in assessment

row_schema = Q._ASSESSMENT_REVIEW_SCHEMA["properties"]["quality_checks"]["items"]
required = set(row_schema["required"])
assert "form_and_agreement_correct" in required
assert row_schema["properties"]["form_and_agreement_correct"]["type"] == "boolean"

good = {
    "quality_checks": [
        {
            "question": i,
            "single_answer": True,
            "form_and_agreement_correct": True,
            "distractors_plausible": True,
            "rationale_specific": True,
            "cefr_fit": True,
            "reason": "proved",
        }
        for i in range(1, 11)
    ]
}
Q._require_assessment_quality_proof(
    good, unit_title="Fixture", stage="shared-contract regression"
)

bad = {"quality_checks": [dict(row) for row in good["quality_checks"]]}
bad["quality_checks"][6]["form_and_agreement_correct"] = False
try:
    Q._require_assessment_quality_proof(
        bad, unit_title="Fixture", stage="shared-contract regression"
    )
except Q.QualityGateError as exc:
    assert "form_and_agreement_correct" in str(exc)
else:
    raise AssertionError("assessment proof accepted a known agreement failure")

print("[SHARED-QUALITY-CONTRACT] generation/review/repair synchronized; agreement proof enforced")
