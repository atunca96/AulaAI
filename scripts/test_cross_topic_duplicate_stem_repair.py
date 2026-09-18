#!/usr/bin/env python3
"""Regression: cross-topic duplicate MCQ stems get exact repair before publication proof."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q

def topic(topic_id, title, stem):
    return {
        "id":topic_id,
        "title":title,
        "is_assessment":False,
        "content":{"pages":[{
            "type":"mcq",
            "prompt":stem,
            "answer":"eres",
            "options":["eres","soy","es","somos"],
            "distractors":["soy","es","somos"],
            "why":"Second-person singular uses eres.",
            "why_tr":"İkinci tekil kişi için eres kullanılır.",
        }]}
    }

t1=topic("t1","Unit 1 Review and Assessment","¿De dónde ___ tú?")
t2=topic("t2","The Verb 'Ser' and Origin","¿De dónde _____ tú?")
units=[
    {"title":"First Words and Greetings","topics":[t1]},
    {"title":"Personal Identity and Origins","topics":[t2]},
]

dups=Q._duplicate_mcq_occurrences(units)
assert len(dups)==1 and len(dups[0])==2, dups

orig_call=Q._call_review
orig_audit=Q._audit_topic
orig_render=Q._topic_render_blockers
orig_repair=Q.R.repair_lesson
calls=[]

def fake_call(**kwargs):
    calls.append(kwargs)
    payload=kwargs["payload"]
    assert payload["current_value"]=="¿De dónde _____ tú?"
    assert "¿De dónde ___ tú?" in payload["forbidden_duplicate_stems"]
    assert payload["immutable_page_context"]["answer"]=="eres"
    assert payload["immutable_page_context"]["options"]==["eres","soy","es","somos"]
    return {"value":"¿Tú de dónde eres?","reason":"Same skill, distinct natural stem."}

try:
    Q._call_review=fake_call
    Q._audit_topic=lambda topic, language, track: []
    Q._topic_render_blockers=lambda content: []
    Q.R.repair_lesson=lambda content, language: content
    applied=Q.repair_duplicate_mcq_stems(
        units=units,
        language="Spanish",
        level="A1",
        track="tr",
        budget=Q.ReviewBudget(1.0),
    )
finally:
    Q._call_review=orig_call
    Q._audit_topic=orig_audit
    Q._topic_render_blockers=orig_render
    Q.R.repair_lesson=orig_repair

assert applied==1, applied
assert t1["content"]["pages"][0]["prompt"]=="¿De dónde ___ tú?"
assert t2["content"]["pages"][0]["prompt"]=="¿Tú de dónde eres?"
assert Q._duplicate_mcq_occurrences(units)==[]
assert len(calls)==1
print("[DUPLICATE-STEM-REPAIR] cross-topic duplicate repaired before final publication proof")
# qa cross-topic duplicate stem repair
