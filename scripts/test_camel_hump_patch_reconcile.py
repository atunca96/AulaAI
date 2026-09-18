#!/usr/bin/env python3
"""Regression: one-token mid-word CamelCase corruption resolves to clean duplicate."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q

topic={
    "id":"ef2ac973-4459-41c0-8876-66f819d4932e",
    "content":{
        "pages":[{}, {}, {
            "dialogue":[
                {"line_tr":"A"},
                {"line_tr":"B"},
                {"line_tr":"Ben İspanyolum, Madridliyim."},
            ]
        }]
    },
}
path=["pages","2","dialogue","2","line_tr"]
old="Ben İspanyolum, Madridliyim."
corrupt={
    "topic_id":topic["id"],
    "path":path,
    "old":old,
    "value":"Ben İspanyStandardım, Madridliyim.",
    "reason":"provider corruption",
}
clean={
    "topic_id":topic["id"],
    "path":path,
    "old":old,
    "value":"Ben İspanyolum, Madridliyim.",
    "reason":"clean resolved value",
}
applied=Q._apply_patches({topic["id"]:topic}, [corrupt, clean])
assert topic["content"]["pages"][2]["dialogue"][2]["line_tr"] == clean["value"]
assert applied in (0,1), applied
assert Q._camel_hump_token_cleaner(corrupt["value"], clean["value"]) == clean["value"]

# Two ordinary alternatives remain a real conflict.
topic["content"]["pages"][2]["dialogue"][2]["line_tr"] = old
other=dict(clean)
other["value"]="Ben Madridliyim, İspanyolum."
try:
    Q._apply_patches({topic["id"]:topic}, [clean, other])
except Q.QualityGateError as exc:
    assert "conflicting semantic patches" in str(exc), exc
else:
    raise AssertionError("ordinary semantic alternatives must fail closed")

print("[CAMEL-HUMP-DUPLICATE] exact one-token corruption resolves to clean candidate")
