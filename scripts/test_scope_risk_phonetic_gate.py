#!/usr/bin/env python3
"""Regression: unit scope, pedagogical-risk, and cross-topic IPA gates."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import prompts as P
from services.authoring import quality_gate as Q

prompt=P.build_lesson_user(
    topic="Unit 3 Review and Assessment",
    topic_type="review",
    language="Spanish",
    unit_title="Family and Personal Descriptions",
    unit_topics=("Family Members","Adjective Agreement","Physical and Personality Adjectives","Unit 3 Review and Assessment"),
)
assert "CURRENT UNIT: Family and Personal Descriptions" in prompt
assert "Family Members; Adjective Agreement" in prompt
assert "must review THIS unit's topics only" in prompt
assert "never substitute material from another unit" in prompt

orig_call=Q._call_review
orig_audit=Q._audit_topic
orig_render=Q._topic_render_blockers
orig_repair=Q.R.repair_lesson

try:
    calls=[]
    def fake_scope_call(**kwargs):
        calls.append(kwargs)
        payload=kwargs["payload"]
        topic_id=payload["topics"][0]["topic_id"]
        return {"topics":[{"topic_id":topic_id,"verdict":"ok","patches":[]}]}

    Q._call_review=fake_scope_call
    Q._audit_topic=lambda topic, language, track: []
    Q._topic_render_blockers=lambda content: []
    Q.R.repair_lesson=lambda content, language: content

    review={
        "id":"r1","title":"Unit 3 Review and Assessment","type":"review",
        "content":{"pages":[{"type":"lesson","title":"Review","text":"Review text."}]},
    }
    sibling={
        "id":"s1","title":"Family Members","type":"vocabulary",
        "content":{"pages":[{"type":"lesson","title":"Family","text":"Family vocabulary."}]},
    }
    Q.review_unit_lessons(
        unit_title="Family and Personal Descriptions",
        topics=[review,sibling],
        language="English", level="A1", track="tr",
        budget=Q.ReviewBudget(1.0),
        unit_topic_titles=[review["title"],sibling["title"]],
    )
    scope_payload=calls[0]["payload"]
    assert scope_payload["unit_topic_titles"]==[review["title"],sibling["title"]]
    assert scope_payload["unit_scope_evidence"][0]["title"]=="Family Members"

    risk_topic={
        "id":"g1","title":"Adjective Agreement","type":"grammar",
        "content":{"pages":[{"type":"lesson","rules":[{
            "rule":"Adjectives ending in -e or a consonant only change for number.",
            "rule_tr":"-e veya ünsüzle biten sıfatlar yalnızca tekillik-çoğulluğa göre değişir.",
            "scope":"absolute",
            "analysis":"Different adjective classes can follow different agreement patterns.",
        }]}]},
    }
    risk_records=Q._risk_review_records(
        risk_topic["content"], topic_type=risk_topic["type"]
    )
    assert any(r["field"]=="rule_tr" for r in risk_records)

    # Pronunciation/phonology prose is a pedagogical rule surface too. It must
    # receive the same semantic scope/counterexample pass even when the page is
    # stored as a generic lesson and contains no notation field.
    pronunciation_topic={
        "id":"p0","title":"Connected Speech","type":"pronunciation",
        "content":{"pages":[{"type":"lesson",
            "text":"In connected speech, every word boundary is always marked by a glottal stop.",
            "text_tr":"Bağlantılı konuşmada her kelime sınırı daima gırtlak patlamasıyla işaretlenir."
        }]},
    }
    pronunciation_records=Q._risk_review_records(
        pronunciation_topic["content"], topic_type=pronunciation_topic["type"]
    )
    assert {r["field"] for r in pronunciation_records} >= {"text","text_tr"}

    # The semantic contracts explicitly reject low-information rationales and
    # distractors that can be eliminated without knowing the taught distinction.
    assert "specific discriminating rule, form or" in Q._LESSON_REVIEW_SYSTEM
    assert "low-information paraphrases are not publication quality" in Q._LESSON_REVIEW_SYSTEM
    assert "SAME tested semantic or" in Q._ASSESSMENT_REVIEW_SYSTEM
    assert "low-information restatements are a quality defect" in Q._ASSESSMENT_REVIEW_SYSTEM

    def fake_risk_call(**kwargs):
        stage=kwargs["stage"]
        payload=kwargs["payload"]
        if stage.startswith("review_categorical_exact:") or stage.startswith("review_categorical_escalation:"):
            current=payload["current"]
            if "only change for number" in current or "yalnızca tekillik-çoğulluğa" in current:
                return {
                    "verdict":"fix",
                    "value":(
                        "Many adjectives ending in -e are gender-invariable; consonant-ending adjectives vary by class."
                        if "only change for number" in current else
                        "-e ile biten birçok sıfat cinsiyete göre değişmez; ünsüzle biten sıfatlarda davranış sınıfa göre değişir."
                    ),
                    "reason":"The claim was too broad."
                }
            return {"verdict":"ok","value":current,"reason":"Scoped claim is correct."}
        assert payload["topics"][0]["topic_id"]=="g1"
        checked_ids=[
            rec["record_id"]
            for rec in payload["topics"][0]["records"]
        ]
        absolute_ids=payload["topics"][0].get("absolute_ids") or []
        return {
            "topic_id":"g1",
            "checked_ids":checked_ids,
            # A reviewer may conservatively scope-check additional valid records.
            # This is extra verification, not a publication defect.
            "scope_checked_ids":checked_ids,
            "patches":[
                {
                    "path":["pages","0","rules","0","rule"],
                    "old":"Adjectives ending in -e or a consonant only change for number.",
                    "value":"Many adjectives ending in -e are gender-invariable; consonant-ending adjectives vary by class.",
                    "reason":"The original rule overgeneralized consonant-ending adjectives.",
                },
                {
                    "path":["pages","0","rules","0","rule_tr"],
                    "old":"-e veya ünsüzle biten sıfatlar yalnızca tekillik-çoğulluğa göre değişir.",
                    "value":"-e ile biten birçok sıfat cinsiyete göre değişmez; ünsüzle biten sıfatlarda davranış sınıfa göre değişir.",
                    "reason":"Kural ünsüzle biten sıfatları aşırı genelliyordu.",
                },
            ],
        }
    Q._call_review=fake_risk_call
    applied=Q.review_unit_risk_claims(
        unit_title="Family and Personal Descriptions",
        topics=[risk_topic],language="Spanish",level="A1",track="tr",
        budget=Q.ReviewBudget(1.0),
    )
    assert applied==2
    assert "sınıfa göre" in risk_topic["content"]["pages"][0]["rules"][0]["rule_tr"]

    unknown_topic={
        "id":"g2","title":"Unknown Coverage Guard","type":"grammar",
        "content":{"pages":[{"type":"lesson","rules":[{
            "rule":"This form always changes.",
            "rule_tr":"Bu biçim her zaman değişir.",
        }]}]},
    }
    def fake_unknown_scope_call(**kwargs):
        payload=kwargs["payload"]
        records=payload["topics"][0]["records"]
        checked=[rec["record_id"] for rec in records]
        absolute=payload["topics"][0].get("absolute_ids") or []
        return {
            "topic_id":"g2",
            "checked_ids":checked,
            "scope_checked_ids":absolute+["r999"],
            "patches":[],
        }
    Q._call_review=fake_unknown_scope_call
    try:
        Q.review_unit_risk_claims(
            unit_title="Guard",topics=[unknown_topic],language="Spanish",
            level="A1",track="tr",budget=Q.ReviewBudget(1.0),
        )
        raise AssertionError("unknown scope id must fail closed")
    except Q.QualityGateError as exc:
        assert "unknown_ids=['r999']" in str(exc)

    p1={
        "id":"p1","title":"Daily Activities","type":"vocabulary",
        "content":{"pages":[{"type":"lesson","items":[
            {"term":"desayunar","phonetic":"[desajuˈnaɾ]","translation":"to have breakfast"}
        ]}]},
    }
    p2={
        "id":"p2","title":"Daily Routines","type":"vocabulary",
        "content":{"pages":[{"type":"lesson","items":[
            {"term":"desayunar","phonetic":"[desawˈnaɾ]","translation":"to have breakfast"}
        ]}]},
    }
    units=[{"title":"Daily Routine and Time","topics":[p1,p2]}]
    def fake_ipa_call(**kwargs):
        payload=kwargs["payload"]
        assert payload["term"]=="desayunar"
        assert set(payload["candidates"])=={"[desajuˈnaɾ]","[desawˈnaɾ]"}
        return {"value":"[desajuˈnaɾ]","reason":"Spanish y is not /w/ here."}
    Q._call_review=fake_ipa_call
    applied=Q.repair_cross_topic_phonetic_conflicts(
        units=units,language="Spanish",level="A1",track="tr",
        budget=Q.ReviewBudget(1.0),
    )
    assert applied==1
    assert p2["content"]["pages"][0]["items"][0]["phonetic"]=="[desajuˈnaɾ]"
    assert Q._cross_topic_phonetic_occurrences(units)==[]
finally:
    Q._call_review=orig_call
    Q._audit_topic=orig_audit
    Q._topic_render_blockers=orig_render
    Q.R.repair_lesson=orig_repair

print("[SCOPE-RISK-IPA] unit grounding + rule risk + class IPA regressions PASSED")
