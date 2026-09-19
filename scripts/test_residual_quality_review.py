#!/usr/bin/env python3
"""Regression: residual rationale grounding and complex-notation review."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q

orig_call=Q._call_review
orig_audit=Q._audit_topic
orig_render=Q._topic_render_blockers

try:
    Q._audit_topic=lambda topic, language, track: []
    Q._topic_render_blockers=lambda content: []

    topic={
        "id":"t1","title":"Nationality Agreement","type":"grammar",
        "content":{"pages":[
            {"type":"mcq","question":"¿Cuál es la forma femenina de «mexicano»?",
             "answer":"mexicana","options":["mexicana","mexicano","mexicanas","mexicanos"],
             "explanation_en":"Ella is a female student, so the answer is mexicana.",
             "explanation_tr":"Ella kadın bir öğrencidir, bu yüzden cevap mexicana'dır."},
            {"type":"lesson","items":[
                {"term":"Teléfono: 612 34 56 78",
                 "phonetic":"[teˈlefono sejisˈθjentos ˈdoθe]",
                 "translation":"Telefon"}
            ]},
        ]},
    }

    def fake_call(**kwargs):
        stage=kwargs["stage"]
        payload=kwargs["payload"]
        if stage.startswith("review_rationale_grounding:"):
            items=payload["items"]
            return {
                "checked_ids":[row["item_id"] for row in items],
                "patches":[
                    {"topic_id":"t1","path":["pages","0","explanation_en"],
                     "old":"Ella is a female student, so the answer is mexicana.",
                     "value":"The feminine singular form of «mexicano» is «mexicana».",
                     "reason":"Remove evidence not present in the item."},
                    {"topic_id":"t1","path":["pages","0","explanation_tr"],
                     "old":"Ella kadın bir öğrencidir, bu yüzden cevap mexicana'dır.",
                     "value":"«mexicano» sıfatının dişil tekil biçimi «mexicana»dır.",
                     "reason":"Soruda bulunmayan özne ve senaryoyu kaldır."},
                ],
            }
        if stage.startswith("review_complex_digit_notation:") or stage.startswith("review_complex_notation:"):
            items=payload["items"]
            assert items and "612 34 56 78" in items[0]["term"]
            return {
                "checked_ids":[row["item_id"] for row in items],
                "patches":[
                    {"topic_id":"t1","path":items[0]["path"],
                     "old":"[teˈlefono sejisˈθjentos ˈdoθe]",
                     "value":"[teˈlefono ˈsejs ˈuno ˈðos ˈtɾes ˈkwatɾo ˈθiŋko ˈsejs ˈsjete ˈotʃo]",
                     "reason":"The stored transcription did not match the written digit sequence."},
                ],
            }
        raise AssertionError(stage)

    Q._call_review=fake_call
    applied=Q.review_unit_mcq_rationales(
        unit_title="Identity",topics=[topic],language="Spanish",level="A1",
        track="tr",budget=Q.ReviewBudget(1.0),
    )
    assert applied==2
    assert "female student" not in topic["content"]["pages"][0]["explanation_en"]
    assert "öğrencidir" not in topic["content"]["pages"][0]["explanation_tr"]

    applied=Q.review_unit_complex_notation(
        unit_title="Identity",topics=[topic],language="Spanish",level="A1",
        budget=Q.ReviewBudget(1.0),
    )
    assert applied==1
    assert "sejis" not in topic["content"]["pages"][1]["items"][0]["phonetic"]
finally:
    Q._call_review=orig_call
    Q._audit_topic=orig_audit
    Q._topic_render_blockers=orig_render

print("[RESIDUAL-QUALITY] rationale grounding + complex notation review PASSED")
