#!/usr/bin/env python3
"""Regression: idempotent reviewer patches and missing bilingual slots do not kill READY."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q

topic={
    "id":"t1",
    "title":"Greetings and Farewells",
    "content":{
        "pages":[
            {"type":"overview","title":"Greetings","title_tr":"Selamlaşmalar",
             "text":"Use these expressions in class."},
            {"type":"vocabulary","items":[
                {"term":"adiós","translation":"goodbye","translation_tr":"hoşça kal",
                 "explanation":"A general farewell expression.",
                 "explanation_tr":"Her ortamda kullanılabilen genel bir vedalaşma ifadesidir."}
            ]}
        ]
    }
}

calls=[]
orig_call=Q._call_review
orig_audit=Q.A.audit_lesson
orig_repair=Q.R.repair_lesson

def fake_call(**kwargs):
    calls.append(kwargs["stage"])
    if kwargs["stage"].startswith("review_lesson:"):
        return {"topics":[{
            "topic_id":"t1","verdict":"fix","patches":[{
                "path":["pages","1","items","0","explanation_tr"],
                "old":None,
                "value":"Her ortamda kullanılabilen genel bir vedalaşma ifadesidir.",
                "reason":"Already correct after deterministic repair."
            }]
        }]}
    if kwargs["stage"].startswith("review_bilingual_retry:"):
        return {"topics":[{
            "topic_id":"t1","verdict":"fix","patches":[{
                "path":["pages","0","text_tr"],
                "old":"",
                "value":"Bu ifadeleri derste kullanın.",
                "reason":"Fill the missing Turkish counterpart."
            }]
        }]}
    raise AssertionError(kwargs["stage"])

try:
    Q._call_review=fake_call
    Q.A.audit_lesson=lambda *args, **kwargs: []
    Q.R.repair_lesson=lambda *args, **kwargs: None
    applied=Q.review_unit_lessons(
        unit_title="Unit 1",
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

assert topic["content"]["pages"][1]["items"][0]["explanation_tr"] ==        "Her ortamda kullanılabilen genel bir vedalaşma ifadesidir."
assert topic["content"]["pages"][0]["text_tr"] == "Bu ifadeleri derste kullanın."
assert applied == 1, applied
assert calls == ["review_lesson:Unit 1:Greetings and Farewells", "review_bilingual_retry:Greetings and Farewells"], calls
print("[SEMANTIC-PATCH] idempotent stale patch + bilingual repair regression PASSED")
