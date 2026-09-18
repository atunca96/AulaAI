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
        row = payload["topics"][0]
        assert [r["path"] for r in row["records"]] == [
            ["pages", 0, "items", 0, "target"]
        ]
        return {
            "topics": [{
                "topic_id": "family",
                "verdict": "fix",
                "patches": [{
                    "path": ["pages", "0", "items", "0", "target"],
                    "old": BAD_TARGET,
                    "value": GOOD_TARGET,
                    "reason": "Use taught-language content.",
                }],
            }]
        }

    if stage.endswith("pages.1.prompt"):
        row = payload["topics"][0]
        assert [r["path"] for r in row["records"]] == [["pages", 1, "prompt"]]
        return {
            "topics": [{
                "topic_id": "family",
                "verdict": "fix",
                "patches": [{
                    "path": ["pages", "1", "prompt"],
                    "old": BAD_PROMPT,
                    "value": GOOD_PROMPT,
                    "reason": "Use a taught-language stem.",
                }],
            }]
        }

    raise AssertionError(f"unexpected stage {stage}")

try:
    Q._call_review = fake_call
    Q._audit_topic = fake_audit
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

assert applied >= 1, applied
assert topic["content"]["pages"][0]["items"][0]["target"] != BAD_TARGET
assert topic["content"]["pages"][1]["prompt"] == GOOD_PROMPT
stages = [s for s, _ in calls]
assert stages[0] == "review_preflight_repair:Family Members", stages
assert "review_preflight_exact:Family Members:pages.1.prompt" in stages, stages
# repair_lesson may mechanically normalize one blocker before semantic repair;
# the invariant under test is that every blocker still present after the bulk
# pass is repaired by an exact-path fallback rather than causing publication
# to fail immediately.
print("[PREFLIGHT-EXACT] residual blockers repaired one path at a time")
