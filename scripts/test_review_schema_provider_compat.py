#!/usr/bin/env python3
"""Provider-compatibility regression for semantic review response schemas."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


for name, schema in (
    ("lesson_review", Q._LESSON_REVIEW_SCHEMA),
    ("assessment_review", Q._ASSESSMENT_REVIEW_SCHEMA),
    ("terra_verify", Q._TERRA_VERIFY_SCHEMA),
):
    assert not any("oneOf" in obj for obj in walk(schema)), (
        f"{name} contains oneOf, rejected by OpenAI Structured Outputs"
    )

assert Q._PATCH_PATH["items"] == {"type": "string"}

content = {
    "pages": [
        {"type": "overview", "text": "old"},
        {"type": "grammar", "rules": [{"rule": "old rule"}]},
    ]
}
assert Q._coerce_patch_path(content, ["pages", "1", "rules", "0", "rule"]) == [
    "pages", 1, "rules", 0, "rule"
]

topic = {"content": content}
applied = Q._apply_patches(
    {"t1": topic},
    [{
        "topic_id": "t1",
        "path": ["pages", "1", "rules", "0", "rule"],
        "old": "old rule",
        "value": "new rule",
        "reason": "regression",
    }],
)
assert applied == 1
assert content["pages"][1]["rules"][0]["rule"] == "new rule"

print("[REVIEW-SCHEMA] OpenAI-compatible path schema regression PASSED")
