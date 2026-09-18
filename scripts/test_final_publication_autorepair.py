#!/usr/bin/env python3
"""Regression: a final renderer blocker is repaired, not merely reported."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

from services.authoring import quality_gate as Q

bad="Lucía nació en Lima. ¿Cuál es su nacionalidad?"
good="Lucía es peruana. ¿Cuál es su nacionalidad?"
topic={
    "id":"lesson-1",
    "title":"Countries and Nationalities",
    "content":{"pages":[{
        "type":"mcq",
        "title":"Assessment: Country of Origin",
        "title_tr":"Değerlendirme: Menşe Ülkesi",
        "prompt":bad,
        "answer":"peruana",
        "options":["peruana","española","francesa","alemana"],
        "distractors":["española","francesa","alemana"],
        "explanation":"Her nationality is inferred from the biographical information.",
        "explanation_tr":"Milliyeti biyografik bilgiden çıkarılır."
    }]},
    "is_assessment":False,
}
units=[{"title":"Personal Identity and Origins","topics":[topic]}]

assert Q._topic_render_blockers(topic["content"]), "fixture must be rejected before repair"

orig_call=Q._call_review
orig_audit=Q.A.audit_lesson
orig_repair=Q.R.repair_lesson
calls=[]

def fake_call(**kwargs):
    calls.append(kwargs["stage"])
    assert kwargs["stage"]=="luna_final_repair:Countries and Nationalities"
    payload=kwargs["payload"]
    assert payload["topics"][0]["render_contract_blockers"]
    return {"topics":[{
        "topic_id":"lesson-1",
        "verdict":"fix",
        "patches":[{
            "path":["pages","0","prompt"],
            "old":bad,
            "value":good,
            "reason":"Make the identity fact explicit in the learner-visible stem."
        }]
    }]}

try:
    Q._call_review=fake_call
    Q.A.audit_lesson=lambda *args, **kwargs: []
    Q.R.repair_lesson=lambda *args, **kwargs: None
    applied=Q.repair_final_publication_blockers(
        units=units,
        language="Spanish",
        level="A1",
        track="tr",
        budget=Q.ReviewBudget(999),
    )
finally:
    Q._call_review=orig_call
    Q.A.audit_lesson=orig_audit
    Q.R.repair_lesson=orig_repair

assert applied==1, applied
assert topic["content"]["pages"][0]["prompt"]==good
assert not Q._topic_render_blockers(topic["content"])
assert calls==["luna_final_repair:Countries and Nationalities"], calls

# Parallel review accounting must reserve worst-case spend before provider calls
# start, so concurrency cannot spend beyond the ceiling.
budget=Q.ReviewBudget(0.01)
r1=budget.reserve(model=Q.LUNA_REVIEW_MODEL,input_chars=1000,output_tokens=1000,stage="a")
try:
    try:
        budget.reserve(model=Q.LUNA_REVIEW_MODEL,input_chars=1000,output_tokens=7000,stage="b")
    except Q.QualityGateError:
        pass
    else:
        raise AssertionError("second reservation should be refused when worst-case spend exceeds ceiling")
finally:
    budget.release(r1)

print("[FINAL-AUTOREPAIR] final blocker repair + parallel budget reservation PASSED")
