#!/usr/bin/env python3
"""Regression: deterministic audit blockers are repaired at their exact paths."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import audit as A
from services.authoring import quality_gate as Q

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
                    "target": "at the start of a word",
                    "translation": "position note",
                    "translation_tr": "konum notu",
                }],
            },
            {
                "type": "mcq",
                "title": "Practice",
                "title_tr": "Alıştırma",
                "prompt": "Which family member is this?",
                "answer": "madre",
                "options": ["madre", "padre", "hermano", "abuela"],
                "distractors": ["padre", "hermano", "abuela"],
                "explanation": "The answer is madre.",
                "explanation_tr": "Doğru cevap madre.",
            },
        ]
    },
}

BAD_TARGET = "at the start of a word"
GOOD_TARGET = "madre"
BAD_PROMPT = "Which family member is this?"
GOOD_PROMPT = "¿Qué miembro de la familia es?"

orig_call = Q._call_review
orig_audit = Q._audit_topic
orig_render = Q._topic_render_blockers
calls = []


def fake_audit(current_topic, *, language, track):
    content = current_topic["content"]
    findings = []
    target = content["pages"][0]["items"][0]["target"]
    prompt = content["pages"][1]["prompt"]
    if target.strip() == BAD_TARGET:
        findings.append(A.Finding(
            "instructional_prose_in_target_field", A.BLOCK,
            path="", field="target", role="target",
            detail="reads as en", value=BAD_TARGET,
        ))
    # The controller runs deterministic text normalization each round, which
    # may add Spanish opening punctuation. Match the defect, not the byte string.
    if "Which family member" in prompt:
        findings.append(A.Finding(
            "stem_in_instructional_language", A.BLOCK,
            path="pages[1]", field="prompt", role="target",
            detail="stem reads as en", value=prompt,
        ))
    return findings


def fake_call(**kwargs):
    stage = kwargs["stage"]
    payload = kwargs["payload"]
    calls.append((stage, payload))

    if stage.startswith("review_lesson:"):
        return {"topics": [{"topic_id": "family", "verdict": "ok", "patches": []}]}

    # The controller dispatches one bounded exact-field repair per finding, so
    # each payload carries exactly one blocker and its exact repair path.
    if stage.startswith("converge_exact_field:Family Members:"):
        row = payload["topics"][0]
        blockers = row["deterministic_blockers"]
        assert len(blockers) == 1, blockers
        code = blockers[0]["code"]
        if code == "instructional_prose_in_target_field":
            assert blockers[0]["repair_paths"] == [["pages", 0, "items", 0, "target"]]
            assert [rec["path"] for rec in row["records"]] == [
                ["pages", 0, "items", 0, "target"]]
            return {"topics": [{"topic_id": "family", "verdict": "fix", "patches": [{
                "path": ["pages", "0", "items", "0", "target"],
                "old": BAD_TARGET, "value": GOOD_TARGET,
                "reason": "Target fields must contain taught-language material.",
            }]}]}
        assert code == "stem_in_instructional_language", code
        assert blockers[0]["repair_paths"] == [["pages", 1, "prompt"]]
        assert [rec["path"] for rec in row["records"]] == [["pages", 1, "prompt"]]
        return {"topics": [{"topic_id": "family", "verdict": "fix", "patches": [{
            "path": ["pages", "1", "prompt"],
            "old": row["records"][0]["value"], "value": GOOD_PROMPT,
            "reason": "The stem must be written in the taught language.",
        }]}]}

    raise AssertionError(f"unexpected stage {stage}")


try:
    Q._call_review = fake_call
    Q._audit_topic = fake_audit
    Q._topic_render_blockers = lambda content: []
    applied = Q.review_unit_lessons(
        unit_title="Family and Descriptions",
        topics=[topic],
        language="Spanish",
        level="A1",
        track="tr",
        budget=Q.ReviewBudget(999),
    )
finally:
    Q._call_review = orig_call
    Q._audit_topic = orig_audit
    Q._topic_render_blockers = orig_render

assert applied == 2, applied
assert topic["content"]["pages"][0]["items"][0]["target"] == GOOD_TARGET
assert topic["content"]["pages"][1]["prompt"] == GOOD_PROMPT
assert [stage for stage, _ in calls] == [
    "review_lesson:Family and Descriptions:Family Members",
    "converge_exact_field:Family Members:",
    "converge_exact_field:Family Members:pages[1]",
], [stage for stage, _ in calls]
print("[EXACT-BLOCKER-REPAIR] deterministic blocker paths are mandatory and rechecked")
