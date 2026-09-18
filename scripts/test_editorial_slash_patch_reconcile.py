#!/usr/bin/env python3
"""Regression: unresolved inline lexical slash alternatives lose to clean duplicate."""

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
ambiguous={
    "topic_id":topic["id"],
    "path":path,
    "old":old,
    "value":"Ben İspanyoldur/İspanyolum, Madridliyim.",
    "reason":"unresolved editorial alternative",
}
clean={
    "topic_id":topic["id"],
    "path":path,
    "old":old,
    "value":"Ben İspanyolum, Madrid'denim.",
    "reason":"resolved learner-visible wording",
}
applied=Q._apply_patches({topic["id"]:topic}, [ambiguous, clean])
assert topic["content"]["pages"][2]["dialogue"][2]["line_tr"] == clean["value"]
assert applied in (0,1), applied
assert Q._editorial_slash_candidate(ambiguous["value"], clean["value"]) == clean["value"]

# Ordinary slash content (date/path style) must not become a resolver.
assert Q._editorial_slash_candidate("Tarih 18/09.", "Tarih 19/09.") is None

# Two normal semantic alternatives remain a conflict.
topic["content"]["pages"][2]["dialogue"][2]["line_tr"] = old
other=dict(clean)
other["value"]="Ben Madridliyim ve İspanyolum."
try:
    Q._apply_patches({topic["id"]:topic}, [clean, other])
except Q.QualityGateError as exc:
    assert "conflicting semantic patches" in str(exc), exc
else:
    raise AssertionError("ordinary semantic conflicts must fail closed")

print("[EDITORIAL-SLASH] clean exact-path proposal wins unresolved inline lexical alternative")
