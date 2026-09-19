#!/usr/bin/env python3
"""Regression: language-ID proxy routes to semantic review, never preflight gate."""

from __future__ import annotations
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")
os.environ.setdefault("AULAAI_DATA_DIR", tempfile.mkdtemp(prefix="aulaai-preflight-"))

from services.authoring import quality_gate as Q
from services.authoring import transport as T

BAD = "This is a family member in the lesson."
GOOD = "madre"

topic = {
    "id": "family",
    "title": "Family Members",
    "content": {
        "pages": [{
            "type": "vocabulary",
            "title": "Family",
            "title_tr": "Aile",
            "items": [{
                "target": BAD,
                "translation": "mother",
                "translation_tr": "anne",
            }],
        }]
    },
    "is_assessment": False,
}
units = [{"title": "Family and Descriptions", "topics": [topic]}]

orig = Q.T.call_model
seen = {}

def provider(messages, **kwargs):
    seen["model"] = kwargs.get("model")
    seen["reasoning_effort"] = kwargs.get("reasoning_effort")
    payload = json.loads(messages[-1]["content"])
    row = payload["topics"][0]

    # This is no longer a deterministic blocker. It is a semantic suspicion
    # that the language-aware reviewer must adjudicate.
    assert row.get("deterministic_blockers") == [], row
    proxies = row.get("semantic_proxy_findings") or []
    assert any(
        p.get("code") == "instructional_prose_in_target_field"
        for p in proxies
    ), proxies
    assert any(
        r.get("path") == ["pages", 0, "items", 0, "target"]
        and r.get("value") == BAD
        for r in row["records"]
    ), row["records"]

    return T.Response(
        data={
            "topics": [{
                "topic_id": "family",
                "verdict": "fix",
                "patches": [{
                    "path": ["pages", 0, "items", 0, "target"],
                    "old": BAD,
                    "value": GOOD,
                    "reason": "This is genuinely English prose in a Spanish target field.",
                }],
            }]
        },
        input_tokens=300,
        output_tokens=80,
        cost=0.0005,
        model=kwargs.get("model", ""),
    )

try:
    Q.T.call_model = provider
    budget = Q.ReviewBudget(0.05)

    # Cheap lexical suspicion must never trigger a deterministic repair call.
    preflight_applied = Q.repair_deterministic_preflight(
        units=units,
        language="Spanish",
        level="A1",
        track="tr",
        budget=budget,
    )
    assert preflight_applied == 0, preflight_applied
    assert topic["content"]["pages"][0]["items"][0]["target"] == BAD
    assert budget.calls == [], budget.calls

    # The language-aware reviewer sees the advisory signal and repairs a real
    # leak semantically.
    applied = Q.review_unit_lessons(
        unit_title="Family and Descriptions",
        topics=[topic],
        language="Spanish",
        level="A1",
        track="tr",
        budget=budget,
        unit_topic_titles=["Family Members"],
    )
finally:
    Q.T.call_model = orig

assert applied == 1, applied
assert topic["content"]["pages"][0]["items"][0]["target"] == GOOD
assert seen["model"] == "google/gemini-3.7-flash", seen
assert seen["reasoning_effort"] == "low", seen
assert [c["stage"] for c in budget.calls] == [
    "review_lesson:Family and Descriptions:Family Members"
], budget.calls
print("[LANGUAGE-PROXY-REVIEW] advisory target-language suspicion fixed semantically")
