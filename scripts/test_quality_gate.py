#!/usr/bin/env python3
"""Regression tests for the publication-grade semantic quality gate."""

import copy
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")
os.environ.setdefault("AULAAI_DATA_DIR", tempfile.mkdtemp(prefix="aulaai-quality-"))

from services.authoring import audit as A
from services.authoring import quality_gate as Q
from services.authoring import repair as R
from services.authoring import transport as T

FAILS = []


def check(cond, label):
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILS.append(label)


def lesson_fixture():
    return {
        "variety": "European (Castilian) Spanish",
        "pages": [
            {
                "type": "vocabulary",
                "title": "Numbers",
                "title_tr": "Sayılar",
                "text": "This page teaches common numbers used in daily life.",
                "text_tr": "Bu sayfa günlük hayatta kullanılan temel sayıları öğretir.",
                "items": [{
                    "term": "once",
                    "phonetic": "[ˈονθε]",
                    "translation": "eleven",
                    "translation_tr": "on bir",
                    "example": "Tengo once libros.",
                    "example_en": "I have eleven books.",
                    "example_tr": "On bir kitabım var.",
                }],
            },
            {
                "type": "grammar",
                "title": "Adjective agreement",
                "title_tr": "Sıfat uyumu",
                "text": "Adjectives agree with the nouns they describe.",
                "text_tr": "Sıfatlar niteledikleri isimlerle uyum sağlar.",
                "rules": [{
                    "rule": "Adjectives ending in -e or a consonant never change for gender.",
                    "rule_tr": "-e veya ünsüzle biten sıfatlar cinsiyete göre asla değişmez.",
                    "explanation": "This is presented as a general gender rule.",
                    "explanation_tr": "Bu, genel bir cinsiyet kuralı olarak sunulur.",
                    "example": "El libro verde y la mesa verde son grandes.",
                    "example_en": "The green book and the green table are large.",
                    "example_tr": "Yeşil kitap ve yeşil masa büyüktür.",
                    "scope": "absolute",
                    "domain": "morphology",
                }],
            },
        ],
    }


def assessment_fixture():
    pages = [{
        "type": "overview",
        "title": "Unit Assessment",
        "title_tr": "Ünite Değerlendirmesi",
        "text": "Check what you have learned in this unit.",
        "text_tr": "Bu ünitede öğrendiklerinizi değerlendirin.",
    }]
    for i in range(1, 11):
        if i == 1:
            prompt = "¿Qué palabra contiene una letra h que no se pronuncia?"
            answer = "hotel"
            options = ["hotel", "huevo", "hielo", "hacer"]
        else:
            prompt = f"¿Qué opción corresponde al ejemplo número {i}?"
            answer = f"respuesta {i}"
            options = [answer, f"alternativa {i}a", f"alternativa {i}b", f"alternativa {i}c"]
        pages.append({
            "type": "mcq",
            "title": f"Question {i}",
            "title_tr": f"Soru {i}",
            "prompt": prompt,
            "answer": answer,
            "options": options,
            "distractors": [o for o in options if o != answer],
            "explanation": "The taught form is correct in this context.",
            "explanation_tr": "Öğretilen biçim bu bağlamda doğrudur.",
        })
    return {"pages": pages}


def test_non_ipa_fails_closed():
    print("\n[Q1] look-alike Greek in IPA is never silently guessed")
    lesson = lesson_fixture()
    before = lesson["pages"][0]["items"][0]["phonetic"]
    R.repair_lesson(lesson, language="Spanish")
    after = lesson["pages"][0]["items"][0]["phonetic"]
    findings = A.audit_lesson(lesson, language="Spanish", track="tr")
    codes = [f.code for f in A.blocking(findings)]
    check(before == after, "mechanical repair does not guess the intended phoneme")
    check("non_ipa_in_transcription" in codes, "Greek look-alikes block publication")


def test_luna_lesson_review_repairs_pdf_defects():
    print("\n[Q2] Luna unit editor fixes the two real PDF defect classes")
    topic = {"id": "t1", "title": "Numbers and adjectives", "content": lesson_fixture()}
    original = Q.T.call_model

    def provider(messages, **kwargs):
        payload = json.loads(messages[-1]["content"])
        tid = payload["topics"][0]["topic_id"]
        data = {"topics": [{
            "topic_id": tid,
            "verdict": "fix",
            "patches": [
                {
                    "topic_id": tid,
                    "path": ["pages", 0, "items", 0, "phonetic"],
                    "old": "[ˈονθε]",
                    "value": "[ˈonθe]",
                    "reason": "Castilian once is [ˈonθe]; Greek look-alikes are not IPA.",
                },
                {
                    "topic_id": tid,
                    "path": ["pages", 1, "rules", 0, "rule"],
                    "old": "Adjectives ending in -e or a consonant never change for gender.",
                    "value": "Many -e adjectives are gender-invariable; consonant-final adjectives vary by lexical class, and nationality adjectives such as español/española can change.",
                    "reason": "The original absolute rule has common counterexamples.",
                },
                {
                    "topic_id": tid,
                    "path": ["pages", 1, "rules", 0, "rule_tr"],
                    "old": "-e veya ünsüzle biten sıfatlar cinsiyete göre asla değişmez.",
                    "value": "-e ile biten birçok sıfat cinsiyete göre değişmez; ünsüzle biten sıfatlarda ise sözcük türüne göre farklılık vardır ve español/española gibi milliyet sıfatları değişebilir.",
                    "reason": "Türkçe kural da aynı doğru kapsamı vermelidir.",
                },
            ],
        }]}
        return T.Response(data=data, input_tokens=4200, output_tokens=700,
                          cost=0.002, model=kwargs.get("model", ""))

    try:
        Q.T.call_model = provider
        budget = Q.ReviewBudget(0.05)
        applied = Q.review_unit_lessons(
            unit_title="Unit 1", topics=[topic], language="Spanish",
            level="A1", track="tr", budget=budget)
    finally:
        Q.T.call_model = original

    check(applied == 3, "three targeted corrections were applied")
    check(topic["content"]["pages"][0]["items"][0]["phonetic"] == "[ˈonθe]",
          "bad IPA was corrected from the word, not by Unicode shape")
    check("never change" not in topic["content"]["pages"][1]["rules"][0]["rule"],
          "the overgeneralised adjective rule was narrowed")
    check(not A.blocking(A.audit_lesson(topic["content"], language="Spanish", track="tr")),
          "the reviewed lesson is mechanically publishable")


def test_luna_assessment_review_removes_multi_correct_item():
    print("\n[Q3] assessment editor catches the real all-four-options-correct failure")
    lesson_topic = {"id": "t1", "title": "Sounds", "content": lesson_fixture()}
    # Start from the already-corrected IPA so evidence itself has no mechanical blocker.
    lesson_topic["content"]["pages"][0]["items"][0]["phonetic"] = "[ˈonθe]"
    assessment = {"id": "a1", "title": "Unit Assessment",
                  "content": assessment_fixture(), "is_assessment": True}
    original = Q.T.call_model

    def provider(messages, **kwargs):
        data = {
            "checked_questions": list(range(1, 11)),
            "patches": [
                {
                    "topic_id": "a1",
                    "path": ["pages", 1, "options"],
                    "old": ["hotel", "huevo", "hielo", "hacer"],
                    "value": ["hotel", "gato", "mesa", "casa"],
                    "reason": "All four original h words have silent h.",
                },
                {
                    "topic_id": "a1",
                    "path": ["pages", 1, "distractors"],
                    "old": ["huevo", "hielo", "hacer"],
                    "value": ["gato", "mesa", "casa"],
                    "reason": "Only hotel should satisfy the stem.",
                },
            ],
        }
        return T.Response(data=data, input_tokens=5000, output_tokens=500,
                          cost=0.002, model=kwargs.get("model", ""))

    try:
        Q.T.call_model = provider
        budget = Q.ReviewBudget(0.05)
        applied = Q.review_unit_assessment(
            unit_title="Unit 1", assessment_topic=assessment,
            lesson_topics=[lesson_topic], language="Spanish", level="A1",
            track="tr", budget=budget)
    finally:
        Q.T.call_model = original

    check(applied == 2, "the ambiguous item was surgically repaired")
    check(assessment["content"]["pages"][1]["options"] ==
          ["hotel", "gato", "mesa", "casa"],
          "only one option now has a silent h")
    check(not A.blocking(A.audit_lesson(assessment["content"], language="Spanish", track="tr")),
          "the corrected assessment passes deterministic validation")


def test_terra_final_coverage_is_mandatory():
    print("\n[Q4] final Terra pass proves it checked every high-risk record")
    lesson = {"id": "t1", "title": "Reviewed lesson", "content": lesson_fixture(),
              "is_assessment": False}
    lesson["content"]["pages"][0]["items"][0]["phonetic"] = "[ˈonθe]"
    lesson["content"]["pages"][1]["rules"][0]["rule"] = (
        "Many -e adjectives are gender-invariable; consonant-final adjectives vary by lexical class."
    )
    lesson["content"]["pages"][1]["rules"][0]["rule_tr"] = (
        "-e ile biten birçok sıfat değişmez; ünsüzle biten sıfatlar sözcüğe göre değişebilir."
    )
    assessment = {"id": "a1", "title": "Assessment",
                  "content": assessment_fixture(), "is_assessment": True}
    assessment["content"]["pages"][1]["options"] = ["hotel", "gato", "mesa", "casa"]
    assessment["content"]["pages"][1]["distractors"] = ["gato", "mesa", "casa"]
    units = [{"title": "Unit 1", "topics": [lesson, assessment]}]

    original = Q.T.call_model
    captured = {}

    def provider(messages, **kwargs):
        payload = json.loads(messages[-1]["content"])
        captured["model"] = kwargs.get("model")
        captured["effort"] = kwargs.get("reasoning_effort")
        return T.Response(
            data={"coverage": payload["expected_coverage"], "patches": []},
            input_tokens=6000, output_tokens=300, cost=0.005,
            model=kwargs.get("model", ""),
        )

    try:
        Q.T.call_model = provider
        budget = Q.ReviewBudget(0.05)
        applied = Q.final_terra_verify(
            units=units, language="Spanish", level="A1", track="tr", budget=budget)
    finally:
        Q.T.call_model = original

    check(applied == 0, "a clean course needs no final patch")
    check(captured.get("model") == "openai/gpt-5.6-terra",
          "final verifier is independent Terra, not the Gemini author")
    check(captured.get("effort") == "medium", "Terra uses explicit reasoning effort")


def main():
    test_non_ipa_fails_closed()
    test_luna_lesson_review_repairs_pdf_defects()
    test_luna_assessment_review_removes_multi_correct_item()
    test_terra_final_coverage_is_mandatory()
    print(f"\n=== {len(FAILS)} quality-gate failing checks ===")
    for failure in FAILS:
        print("  -", failure)
    if FAILS:
        sys.exit(1)
    print("publication quality gate: all regression checks passed")


if __name__ == "__main__":
    main()
