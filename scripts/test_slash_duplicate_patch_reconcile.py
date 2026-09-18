#!/usr/bin/env python3
"""Regression: slash-alternative duplicate patches reconcile to concrete branch."""

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
                {"line_tr":"Ben İspanyolum, Madrid'denim."},
            ]
        }]
    },
}
path=["pages","2","dialogue","2","line_tr"]
old="Ben İspanyolum, Madrid'denim."
ambiguous={
    "topic_id":topic["id"],
    "path":path,
    "old":old,
    "value":"Ben İspanyoldur/İspanyolum, Madrid'denim.",
    "reason":"alternative wording",
}
concrete={
    "topic_id":topic["id"],
    "path":path,
    "old":old,
    "value":"Ben İspanyolum, Madrid'denim.",
    "reason":"resolved wording",
}
applied=Q._apply_patches({topic["id"]:topic}, [ambiguous, concrete])
assert topic["content"]["pages"][2]["dialogue"][2]["line_tr"] == concrete["value"]
assert applied in (0,1), applied

# Unrelated conflicting values must still fail closed.
topic["content"]["pages"][2]["dialogue"][2]["line_tr"] = old
bad=dict(concrete)
bad["value"]="Madrid'de yaşıyorum."
try:
    Q._apply_patches({topic["id"]:topic}, [concrete, bad])
except Q.QualityGateError as exc:
    assert "conflicting semantic patches" in str(exc), exc
else:
    raise AssertionError("unrelated conflicting duplicates must fail closed")

print("[SLASH-DUPLICATE] concrete branch wins exact slash alternative; real conflicts fail closed")
