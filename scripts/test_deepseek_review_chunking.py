#!/usr/bin/env python3
"""Regression: lesson review is split per lesson and cannot recreate 100k-char unit mega-prompts."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

from services.authoring import quality_gate as Q

topics=[
    {
        "id":"t1","title":"Lesson One",
        "content":{"pages":[{"type":"overview","title":"One","text":"A"*25000}]},
    },
    {
        "id":"t2","title":"Lesson Two",
        "content":{"pages":[{"type":"overview","title":"Two","text":"B"*25000}]},
    },
]

calls=[]
orig_call=Q._call_review
orig_audit=Q.A.audit_lesson
orig_repair=Q.R.repair_lesson

def fake_call(**kwargs):
    calls.append(kwargs)
    payload=kwargs["payload"]
    rows=payload["topics"]
    assert len(rows)==1, f"review payload must contain one lesson, got {len(rows)}"
    assert kwargs["max_tokens"]==2200
    assert kwargs["effort"]=="none"
    row=rows[0]
    return {"topics":[{"topic_id":row["topic_id"],"verdict":"ok","patches":[]}]}

try:
    Q._call_review=fake_call
    Q.A.audit_lesson=lambda *args, **kwargs: []
    Q.R.repair_lesson=lambda *args, **kwargs: None
    applied=Q.review_unit_lessons(
        unit_title="Unit",
        topics=topics,
        language="English",
        level="A1",
        track="en",
        budget=Q.ReviewBudget(999),
    )
finally:
    Q._call_review=orig_call
    Q.A.audit_lesson=orig_audit
    Q.R.repair_lesson=orig_repair

assert applied==0
assert len(calls)==2, f"expected one semantic call per lesson, got {len(calls)}"
assert calls[0]["stage"]=="review_lesson:Unit:Lesson One"
assert calls[1]["stage"]=="review_lesson:Unit:Lesson Two"
assert all(len(c["payload"]["topics"])==1 for c in calls)
print("[DEEPSEEK-CHUNKING] per-lesson review regression PASSED")
