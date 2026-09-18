#!/usr/bin/env python3
"""Regression: obvious embedded-token duplicate patch corruption resolves safely."""

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
    "value":"Ben İspanyStandardolum, Madridliyim.",
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

assert Q._embedded_meta_insertion_cleaner(
    corrupt["value"], clean["value"]
) == clean["value"]

# Legitimate different rewrites remain conflicts.
topic["content"]["pages"][2]["dialogue"][2]["line_tr"] = old
other=dict(clean)
other["value"]="Madrid'de yaşıyorum."
try:
    Q._apply_patches({topic["id"]:topic}, [clean, other])
except Q.QualityGateError as exc:
    assert "conflicting semantic patches" in str(exc), exc
else:
    raise AssertionError("genuine conflicting proposals must fail closed")

print("[EMBEDDED-CORRUPTION] exact mid-word insertion resolves to clean candidate")
