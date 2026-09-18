#!/usr/bin/env python3
"""Regression: residual lesson renderer blockers get an exact stem repair before refusal."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q

BAD="Ana nació en España. ¿Cuál es su nacionalidad?"
GOOD="España → ¿qué nacionalidad corresponde?"

topic={
    "id":"countries",
    "title":"Countries and Nationalities",
    "content":{
        "pages":[{
            "type":"mcq",
            "title":"Practice",
            "title_tr":"Alıştırma",
            "prompt":BAD,
            "answer":"española",
            "options":["española","mexicana","francesa","italiana"],
            "distractors":["mexicana","francesa","italiana"],
            "why":"Spain maps to española.",
            "why_tr":"İspanya için española kullanılır.",
        }]
    },
    "is_assessment":False,
}

orig_call=Q._call_review
orig_audit=Q._audit_topic
orig_render=Q._topic_render_blockers
orig_repair=Q.R.repair_lesson
calls=[]

def fake_audit(current_topic, *, language, track):
    return []

def fake_render(content):
    prompt=content["pages"][0]["prompt"]
    if prompt == BAD:
        return [{
            "page_index":0,
            "title":"Practice",
            "locale":"tr",
            "why":"answer depends on an identity fact inferred from a biographical one",
            "stem":prompt,
            "answer":"española",
        },{
            "page_index":0,
            "title":"Practice",
            "locale":"en",
            "why":"answer depends on an identity fact inferred from a biographical one",
            "stem":prompt,
            "answer":"española",
        }]
    return []

def fake_call(**kwargs):
    stage=kwargs["stage"]
    calls.append((stage,kwargs["payload"]))
    if stage.startswith("review_lesson:"):
        return {"topics":[{"topic_id":"countries","verdict":"ok","patches":[]}]}
    if stage == "review_render_exact:Countries and Nationalities:pages.0.prompt":
        payload=kwargs["payload"]
        assert payload["current_value"] == BAD
        assert payload["immutable_page_context"]["answer"] == "española"
        assert payload["immutable_page_context"]["options"] == [
            "española","mexicana","francesa","italiana"
        ]
        assert len(payload["renderer_contract_blockers"]) == 2
        return {"value":GOOD,"reason":"Use direct country-nationality mapping."}
    raise AssertionError(stage)

try:
    Q._call_review=fake_call
    Q._audit_topic=fake_audit
    Q._topic_render_blockers=fake_render
    Q.R.repair_lesson=lambda content, language: content
    applied=Q.review_unit_lessons(
        unit_title="Personal Identity and Origins",
        topics=[topic],
        language="Spanish",
        level="A1",
        track="tr",
        budget=Q.ReviewBudget(999),
    )
finally:
    Q._call_review=orig_call
    Q._audit_topic=orig_audit
    Q._topic_render_blockers=orig_render
    Q.R.repair_lesson=orig_repair

assert applied == 1, applied
assert topic["content"]["pages"][0]["prompt"] == GOOD
stages=[s for s,_ in calls]
assert stages == [
    "review_lesson:Personal Identity and Origins:Countries and Nationalities",
    "review_render_exact:Countries and Nationalities:pages.0.prompt",
], stages
print("[RENDER-EXACT-REPAIR] residual lesson renderer blocker repaired before refusal")
