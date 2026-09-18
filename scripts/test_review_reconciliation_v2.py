#!/usr/bin/env python3
"""Regression: nullable reviewer-old cannot crash review, and lesson MCQ render blockers get repaired."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0,ROOT)

from services.authoring import quality_gate as Q

# 1) A reviewer may incorrectly return old=null for a field that was present in
# its supplied records. Scalar text replacement must remain possible.
root={"pages":[{"type":"overview","text_tr":"Eski değer"}]}
Q._set_path(root, ["pages",0,"text_tr"], "Yeni değer", old=None)
assert root["pages"][0]["text_tr"]=="Yeni değer"

# Non-empty conflicting old remains stale and must fail closed.
try:
    Q._set_path(root, ["pages",0,"text_tr"], "Başka", old="Yanlış eski")
except Q.QualityGateError:
    pass
else:
    raise AssertionError("non-empty stale old must still be rejected")

# 2) Lesson MCQ hidden-world inference must be handed to targeted semantic repair.
bad_prompt="Lucía nació en Lima. ¿Cuál es su nacionalidad?"
good_prompt="Lucía es peruana. ¿Cuál es su nacionalidad?"
topic={
    "id":"lesson-1",
    "title":"Professions and Occupations",
    "content":{"pages":[
        {"type":"overview","title":"Occupations","title_tr":"Meslekler",
         "text":"Learn occupations.","text_tr":"Meslekleri öğrenin."},
        {"type":"mcq","title":"Check","title_tr":"Kontrol",
         "prompt":bad_prompt,
         "answer":"peruana",
         "options":["peruana","española","francesa","alemana"],
         "distractors":["española","francesa","alemana"],
         "explanation":"The explicit statement determines the answer.",
         "explanation_tr":"Açık ifade cevabı belirler."}
    ]}
}

assert Q._topic_render_blockers(topic["content"]), "fixture must hit renderer contract"

calls=[]
orig_call=Q._call_review
orig_audit=Q.A.audit_lesson
orig_repair=Q.R.repair_lesson

def fake_call(**kwargs):
    calls.append((kwargs["stage"], kwargs["payload"]))
    stage=kwargs["stage"]
    if stage.startswith("luna_lessons:"):
        payload=kwargs["payload"]
        assert payload["topics"][0]["render_contract_blockers"]
        return {"topics":[{"topic_id":"lesson-1","verdict":"ok","patches":[]}]}
    if stage.startswith("terra_blocker_retry:"):
        payload=kwargs["payload"]
        assert payload["topics"][0]["render_contract_blockers"]
        return {"topics":[{"topic_id":"lesson-1","verdict":"fix","patches":[{
            "path":["pages","1","prompt"],
            "old":None,
            "value":good_prompt,
            "reason":"Make nationality explicit rather than inferred from birthplace."
        }]}]}
    raise AssertionError(stage)

try:
    Q._call_review=fake_call
    Q.A.audit_lesson=lambda *args, **kwargs: []
    Q.R.repair_lesson=lambda *args, **kwargs: None
    applied=Q.review_unit_lessons(
        unit_title="Professions and Family",
        topics=[topic],
        language="Spanish",
        level="A1",
        track="tr",
        budget=Q.ReviewBudget(999),
    )
finally:
    Q._call_review=orig_call
    Q.A.audit_lesson=orig_audit
    Q.R.repair_lesson=orig_repair

assert applied==1
assert topic["content"]["pages"][1]["prompt"]==good_prompt
assert not Q._topic_render_blockers(topic["content"])
assert [stage for stage,_ in calls]==[
    "luna_lessons:Professions and Family",
    "terra_blocker_retry:Professions and Occupations",
]
print("[REVIEW-RECONCILE] nullable-old + lesson renderer repair regression PASSED")
