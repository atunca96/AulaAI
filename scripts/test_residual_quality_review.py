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
                 "phonetic":"[teˈlefono sejsˈθjentos ˈdoθe tɾejnˈtai̯ˈkwatɾo θiŋkwenˈtai̯ˈsejs setenˈtai̯ ˈotʃo]",
                 "translation":"Telefon"}
            ]},
        ]},
    }


    assessment={
        "id":"a1","title":"Unit Assessment","type":"unit_assessment",
        "is_assessment":True,
        "content":{"pages":[
            {"type":"mcq",
             "question":"Carlos dice: «están debajo del periódico, al lado del sofá». ¿Dónde están?",
             "answer":"Al lado del sofá.",
             "options":["Al lado del sofá.","En el pasillo.","Fuera.","Delante del armario."],
             "explanation_en":"The material says the keys are here.",
             "explanation_tr":"Ders materyalinde anahtarların burada olduğu belirtilir."}
        ]},
    }

    def fake_call(**kwargs):
        stage=kwargs["stage"]
        payload=kwargs["payload"]
        if stage.startswith("review_bilingual_exact:"):
            target = payload.get("target_locale")
            return {
                "value": (
                    "The visible clue «al lado del sofá» identifies the location."
                    if target == "en"
                    else "Görünür «al lado del sofá» ipucu konumu belirler."
                )
            }
        if stage.startswith("review_explanation_grounding:"):
            return {
                "explanation_en": (
                    "The stem says «debajo del periódico, al lado del sofá», which places the keys beside the sofa."
                ),
                "explanation_tr": (
                    "Soru kökündeki «debajo del periódico, al lado del sofá» ifadesi anahtarların konumunu açıkça gösterir."
                ),
            }
        if stage.startswith("review_rationale_exact:"):
            item=payload["items"][0]
            assert item["item_id"]=="q1"
            return {
                "checked_ids":["q1"],
                "quality_checks":[{
                    "item_id":"q1",
                    "grounded":True,
                    "rationale_specific":True,
                    "reason":"Final rationale cites the visible location clue."
                }],
                "patches":[{
                    "item_id":"q1","field":"explanation_en",
                    "old":"The material says the keys are here.",
                    "value":"The stem says «debajo del periódico, al lado del sofá», which places them beside the sofa.",
                    "reason":"Ground the rationale in the assessment stem."
                }],
            }
        if stage.startswith("review_rationale_grounding:"):
            items=payload["items"]
            return {
                "checked_ids":[row["item_id"] for row in items],
                "quality_checks":[
                    {
                        "item_id":row["item_id"],
                        "grounded":True,
                        "rationale_specific":True,
                        "reason":"Final rationale names the discriminating visible fact."
                    }
                    for row in items
                ],
                "patches":[
                    {"item_id":"q0","field":"explanation_en",
                     "old":"Ella is a female student, so the answer is mexicana.",
                     "value":"The feminine singular form of «mexicano» is «mexicana».",
                     "reason":"Remove evidence not present in the item."},
                    {"item_id":"q0","field":"explanation_tr",
                     "old":"Ella kadın bir öğrencidir, bu yüzden cevap mexicana'dır.",
                     "value":"«mexicano» sıfatının dişil tekil biçimi «mexicana»dır.",
                     "reason":"Soruda bulunmayan özne ve senaryoyu kaldır."},
                    {"item_id":"q1","field":"explanation_en",
                     "old":"Ella is a female student, so the answer is mexicana.",
                     "value":"The stem explicitly says the keys are «al lado del sofá».",
                     "reason":"Simulate a batch reviewer copying old from another item."},
                    {"item_id":"q1","field":"explanation_tr",
                     "old":"Ders materyalinde anahtarların burada olduğu belirtilir.",
                     "value":"Soru kökündeki «debajo del periódico, al lado del sofá» ifadesi konumu açıkça kanıtlar.",
                     "reason":"Gerekçeyi assessment kökündeki açık kanıta bağla."},
                ],
            }
        if stage.startswith("review_complex_digit_escalation:"):
            assert "612 34 56 78" in payload["term"]
            good="[teˈlefono ˈsejs ˈuno ˈðos ˈtɾes ˈkwatɾo ˈθiŋko ˈsejs ˈsjete ˈotʃo]"
            if payload["current"] == good:
                return {
                    "verdict":"ok",
                    "spoken_form":"teléfono seis uno dos tres cuatro cinco seis siete ocho",
                    "value":good,
                    "reason":"Digit order and IPA now agree."
                }
            return {
                "verdict":"fix",
                "spoken_form":"teléfono seis uno dos tres cuatro cinco seis siete ocho",
                "value":good,
                "reason":"The multi-digit transcription does not match the spoken sequence."
            }
        if stage.startswith("review_complex_digit_notation:"):
            assert "612 34 56 78" in payload["term"]
            current=payload["current"]
            good="[teˈlefono ˈsejs ˈuno ˈðos ˈtɾes ˈkwatɾo ˈθiŋko ˈsejs ˈsjete ˈotʃo]"
            if current != good:
                # Reproduce the production miss: Gemini says the malformed value is ok.
                return {
                    "verdict":"ok",
                    "spoken_form":"teléfono seis uno dos tres cuatro cinco seis siete ocho",
                    "value":current,
                    "reason":"Simulated Gemini false acceptance."
                }
            return {
                "verdict":"ok",
                "spoken_form":"teléfono seis uno dos tres cuatro cinco seis siete ocho",
                "value":good,
                "reason":"Digit order and IPA now agree."
            }
        if stage.startswith("review_complex_notation:"):
            items=payload["items"]
            return {"checked_ids":[row["item_id"] for row in items],"patches":[]}
        raise AssertionError(stage)

    Q._call_review=fake_call
    applied=Q.review_unit_mcq_rationales(
        unit_title="Identity",topics=[topic,assessment],language="Spanish",level="A1",
        track="tr",budget=Q.ReviewBudget(1.0),
    )
    assert applied > 0
    assert "female student" not in topic["content"]["pages"][0]["explanation_en"]
    assert "öğrencidir" not in topic["content"]["pages"][0]["explanation_tr"]
    assert "al lado del sofá" in assessment["content"]["pages"][0]["explanation_en"]
    assert "burada olduğu" not in assessment["content"]["pages"][0]["explanation_tr"]

    applied=Q.review_unit_complex_notation(
        unit_title="Identity",topics=[topic],language="Spanish",level="A1",
        budget=Q.ReviewBudget(1.0),
    )
    assert applied==1
    assert "sejis" not in topic["content"]["pages"][1]["items"][0]["phonetic"]
    assert Q._digit_notation_requires_escalation(
        "Teléfono: 612 34 56 78",
        "[teˈlefono sejsˈθjentos ˈdoθe tɾejnˈtai̯ ˈkwatɾo θiŋkwenˈtai̯ ˈsejs setenˈtai̯ ˈotʃo]",
    )
    assert not Q._digit_notation_requires_escalation(
        "Edad: 28", "[eˈðað bei̯nˈtjotʃo]"
    )
finally:
    Q._call_review=orig_call
    Q._audit_topic=orig_audit
    Q._topic_render_blockers=orig_render

print("[RESIDUAL-QUALITY] rationale grounding + complex notation review PASSED")
