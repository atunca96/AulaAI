#!/usr/bin/env python3
"""Regression: empty semantic replacements are ignored, then deterministic audit decides."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

from services.authoring import quality_gate as Q

topic={
    "content":{
        "pages":[
            {"type":"mcq","prompt":"¿Quién es tu madre?","answer":"madre",
             "options":["madre","padre","hermano","abuela"],
             "distractors":["padre","hermano","abuela"]}
        ]
    }
}

applied=Q._apply_patches(
    {"t1":topic},
    [{
        "topic_id":"t1",
        "path":["pages","0","prompt"],
        "old":"¿Quién es tu madre?",
        "value":"",
        "reason":"provider noise"
    }]
)

assert applied==0, applied
assert topic["content"]["pages"][0]["prompt"]=="¿Quién es tu madre?"
print("[EMPTY-PATCH] destructive empty semantic patch ignored; content preserved")
