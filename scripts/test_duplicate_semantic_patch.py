#!/usr/bin/env python3
"""Regression: identical duplicate semantic patches are idempotent; conflicts fail closed."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q

topic={
    "id":"t1",
    "content":{
        "pages":[{
            "type":"dialogue",
            "dialogue":[
                {"line_tr":"Merhaba."},
                {"line_tr":"Nasılsın?"},
                {"line_tr":"Ben iyiyim."},
            ],
        }]
    },
}
path=["pages","0","dialogue","2","line_tr"]
base={
    "topic_id":"t1",
    "path":path,
    "old":"Ben iyiyim.",
    "value":"İyiyim.",
    "reason":"Natural Turkish phrasing.",
}
applied=Q._apply_patches({"t1":topic}, [dict(base), dict(base)])
assert applied == 1, applied
assert topic["content"]["pages"][0]["dialogue"][2]["line_tr"] == "İyiyim."

topic["content"]["pages"][0]["dialogue"][2]["line_tr"] = "Ben iyiyim."
conflict=dict(base)
conflict["value"]="Gayet iyiyim."
try:
    Q._apply_patches({"t1":topic}, [dict(base), conflict])
except Q.QualityGateError as exc:
    assert "conflicting semantic patches" in str(exc), exc
else:
    raise AssertionError("conflicting duplicate patches must fail closed")

print("[DUPLICATE-PATCH] identical duplicates dedupe; conflicting duplicates fail closed")
