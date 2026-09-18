#!/usr/bin/env python3
"""Regression: sentence-level CamelCase corruption loses even if another token also differs."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q

topic={
    "id":"ef2ac973-4459-41c0-8876-66f819d4932e",
    "content":{"pages":[{}, {}, {"dialogue":[
        {"line_tr":"A"},{"line_tr":"B"},{"line_tr":"Ben İspanyolum, Madrid'denim."}
    ]}]}
}
path=["pages","2","dialogue","2","line_tr"]
old="Ben İspanyolum, Madrid'denim."
corrupt={
    "topic_id":topic["id"],"path":path,"old":old,
    "value":"Ben İspanyStandardım, Madridliyim.","reason":"provider corruption",
}
clean={
    "topic_id":topic["id"],"path":path,"old":old,
    "value":"Ben İspanyolum, Madrid'denim.","reason":"clean candidate",
}
applied=Q._apply_patches({topic["id"]:topic}, [corrupt, clean])
assert topic["content"]["pages"][2]["dialogue"][2]["line_tr"] == clean["value"]
assert applied in (0,1), applied
assert Q._sentence_camel_corruption_cleaner(
    corrupt["value"], clean["value"]
) == clean["value"]

# No CamelCase corruption => genuine semantic conflict must still fail closed.
topic["content"]["pages"][2]["dialogue"][2]["line_tr"] = old
a=dict(clean); a["value"]="Ben İspanyolum, Madridliyim."
b=dict(clean); b["value"]="Ben İspanyolum, Madrid'denim."
try:
    Q._apply_patches({topic["id"]:topic}, [a,b])
except Q.QualityGateError as exc:
    assert "conflicting semantic patches" in str(exc), exc
else:
    raise AssertionError("ordinary semantic alternatives must still fail closed")

print("[SENTENCE-CAMEL] corrupted candidate discarded despite another token difference")
