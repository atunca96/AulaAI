#!/usr/bin/env python3
"""Regression: preflight falls back to one exact path per residual blocker."""

from __future__ import annotations
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import audit as A
from services.authoring import quality_gate as Q

BAD_TARGET = "at the start of a word"
GOOD_TARGET = "madre"
BAD_PROMPT = "Which family member is this?"
GOOD_PROMPT = "¿Qué miembro de la familia es?"

topic = {
    "id": "family",
    "title": "Family Members",
    "content": {
        "pages": [
            {
                "type": "vocabulary",
                "title": "Family",
                "title_tr": "Aile",
                "items": [{
                    "target": BAD_TARGET,
                    "translation": "position note",
                    "translation_tr": "konum notu",
                }],
            },
            {
                "type": "mcq",
                "title": "Practice",
                "title_tr": "Alıştırma",
                "prompt": BAD_PROMPT,
                "answer": "madre",
                "options": ["madre", "padre", "hermano", "abuela"],
                "distractors": ["padre", "hermano", "abuela"],
                "explanation": "The answer is madre.",
                "explanation_tr": "Doğru cevap madre.",
            },
        ]
    },
    "is_assessment": False,
}

orig_call = Q._call_review
orig_audit = Q._audit_topic
orig_repair = Q.R.repair_lesson
calls = []

def fake_audit(current_topic, *, language, track):
    content = current_topic["content"]
    findings = []
    if content["pages"][0]["items"][0]["target"] == BAD_TARGET:
        findings.append(A.Finding(
            "instructional_prose_in_target_field", A.BLOCK,
            path="", field="target", role="target",
            detail="reads as en", value=BAD_TARGET,
        ))
    if content["pages"][1]["prompt"] == BAD_PROMPT:
        findings.append(A.Finding(
            "stem_in_instructional_language", A.BLOCK,
            path="pages[1]", field="prompt", role="target",
            detail="stem reads as en", value=BAD_PROMPT,
        ))
    return findings

def fake_call(**kwargs):
    stage = kwargs["stage"]
    payload = kwargs["payload"]
    calls.append((stage, payload))

    if stage == "review_preflight_repair:Family Members":
        # Reproduce production behavior: valid structured response, but the
        # bulk repair leaves all deterministic blockers untouched.
        return {
            "topics": [{
                "topic_id": "family",
                "verdict": "fix",
                "patches": [],
            }]
        }

    if stage.endswith("pages.0.items.0.target"):
        assert payload["taught_language"] == "Spanish"
        assert payload["path"] == ["pages", 0, "items", 0, "target"]
        assert payload["current_value"] == BAD_TARGET
        return {
            "value": GOOD_TARGET,
            "reason": "Use taught-language content.",
        }

    if stage.endswith("pages.1.prompt"):
        assert payload["taught_language"] == "Spanish"
        assert payload["path"] == ["pages", 1, "prompt"]
        assert payload["current_value"] == BAD_PROMPT
        context = payload["immutable_page_context"]
        assert context["answer"] == "madre"
        assert context["options"] == ["madre", "padre", "hermano", "abuela"]
        return {
            "value": GOOD_PROMPT,
            "reason": "Use a taught-language stem.",
        }

    raise AssertionError(f"unexpected stage {stage}")

try:
    Q._call_review = fake_call
    Q._audit_topic = fake_audit
    Q.R.repair_lesson = lambda content, language: content
    applied = Q.repair_deterministic_preflight(
        units=[{"title": "Family and Descriptions", "topics": [topic]}],
        language="Spanish",
        level="A1",
        track="tr",
        budget=Q.ReviewBudget(999),
    )
finally:
    Q._call_review = orig_call
    Q._audit_topic = orig_audit
    Q.R.repair_lesson = orig_repair

assert applied == 2, applied
assert topic["content"]["pages"][0]["items"][0]["target"] == GOOD_TARGET
assert topic["content"]["pages"][1]["prompt"] == GOOD_PROMPT
stages = [s for s, _ in calls]
assert stages == [
    "review_preflight_repair:Family Members",
    "review_preflight_exact:Family Members:pages.0.items.0.target",
    "review_preflight_exact:Family Members:pages.1.prompt",
], stages
print("[PREFLIGHT-EXACT] residual blockers repaired one path at a time")
