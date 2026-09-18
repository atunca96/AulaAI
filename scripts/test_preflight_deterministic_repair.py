#!/usr/bin/env python3
"""Regression: deterministic blockers are repaired before broad review spend."""

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
    blockers = row["deterministic_blockers"]
    repair_paths = {
        tuple(p)
        for blocker in blockers
        for p in blocker.get("repair_paths", [])
    }
    assert ("pages", 0, "items", 0, "target") in repair_paths
    assert [r["path"] for r in row["records"]] == [
        ["pages", 0, "items", 0, "target"]
    ]
    return T.Response(
        data={
            "topics": [{
                "topic_id": "family",
                "verdict": "fix",
                "patches": [{
                    "path": ["pages", "0", "items", "0", "target"],
                    "old": BAD,
                    "value": GOOD,
                    "reason": "Target field must contain Spanish, not English prose.",
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
    applied = Q.repair_deterministic_preflight(
        units=units,
        language="Spanish",
        level="A1",
        track="tr",
        budget=budget,
    )
finally:
    Q.T.call_model = orig

assert applied == 1, applied
assert topic["content"]["pages"][0]["items"][0]["target"] == GOOD
assert seen["model"] == "google/gemini-3.7-flash", seen
assert seen["reasoning_effort"] == "low", seen
assert [c["stage"] for c in budget.calls] == ["review_preflight_repair:Family Members"]
print("[PREFLIGHT-REPAIR] exact blocker repaired before broad review spend")
