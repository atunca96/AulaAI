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


def test_transport_strict_schema_and_content_blocks():
    print("\n[Q0] reviewer transport uses strict schema and parses content blocks")
    original = T.urllib.request.urlopen
    captured = {}

    class FakeHTTP:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def read(self):
            body = {
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": [{"type": "text", "text": '{"ok":true}'}]},
                }],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "prompt_tokens_details": {"cached_tokens": 0},
                    "cost": 0.0001,
                },
            }
            return json.dumps(body).encode("utf-8")

    def fake_urlopen(request, timeout=None):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTP()

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
    }
    try:
        T.urllib.request.urlopen = fake_urlopen
        response = T.call_model(
            [{"role": "user", "content": "return ok"}],
            max_tokens=100, model="google/gemini-3.7-flash",
            reasoning_effort="high", response_schema=schema,
            response_name="quality_smoke", attempts=1,
        )
    finally:
        T.urllib.request.urlopen = original

    rf = captured.get("payload", {}).get("response_format", {})
    provider = captured.get("payload", {}).get("provider", {})
    check(response.ok and response.data == {"ok": True},
          "content-block responses are normalized before JSON parsing")
    check(rf.get("type") == "json_schema" and
          rf.get("json_schema", {}).get("strict") is True,
          "reviewer requests strict JSON-schema output")
    check(provider.get("require_parameters") is True,
          "routing refuses providers that cannot honor structured output")
    check(Q.REVIEW_MODEL == "google/gemini-3.7-flash",
          "semantic editor is pinned to Luna Pro")


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


def test_gemini_lesson_review_repairs_pdf_defects():
    print("\n[Q2] Gemini unit editor fixes the two real PDF defect classes")
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
                    "path": ["pages", 0, "items", 0, "phonetic"],
                    "old": "[ˈονθε]",
                    "value": "[ˈonθe]",
                    "reason": "Castilian once is [ˈonθe]; Greek look-alikes are not IPA.",
                },
                {
                    "path": ["pages", 1, "rules", 0, "rule"],
                    "old": "Adjectives ending in -e or a consonant never change for gender.",
                    "value": "Many -e adjectives are gender-invariable; consonant-final adjectives vary by lexical class, and nationality adjectives such as español/española can change.",
                    "reason": "The original absolute rule has common counterexamples.",
                },
                {
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


def test_gemini_assessment_review_removes_multi_correct_item():
    print("\n[Q3] assessment editor catches the real all-four-options-correct failure")
    lesson_topic = {"id": "t1", "title": "Sounds", "content": lesson_fixture()}
    # Start from the already-corrected IPA so evidence itself has no mechanical blocker.
    lesson_topic["content"]["pages"][0]["items"][0]["phonetic"] = "[ˈonθe]"
    assessment = {"id": "a1", "title": "Unit Assessment",
                  "content": assessment_fixture(), "is_assessment": True}
    original = Q.T.call_model

    def provider(messages, **kwargs):
        data = {
            "checked_questions": [str(i) for i in reversed(range(1, 11))],
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


def test_single_semantic_review_model():
    print("\n[Q4] publication review uses Gemini 3.7 Flash only; deterministic integrity is final")
    check(Q.REVIEW_MODEL == "google/gemini-3.7-flash",
          "Gemini 3.7 Flash is the single semantic review model")
    check(not hasattr(Q, "TERRA_VERIFY_MODEL"),
          "Terra is not part of the publication review runtime")



def clean_integrity_fixture():
    lesson = {"id": "t1", "title": "Reviewed lesson",
              "content": lesson_fixture(), "is_assessment": False}
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
    return [{"title": "Unit 1", "topics": [lesson, assessment]}]


def test_publication_integrity_keeps_ten_questions():
    print("\n[Q5] post-review integrity proves the renderer keeps all ten questions")
    units = clean_integrity_fixture()
    result = Q.validate_publication_integrity(
        units=units, language="Spanish", track="tr")
    check(result["unit_assessment_questions"] == 10,
          "a clean unit reaches publication with exactly ten assessment questions")

    broken = copy.deepcopy(units)
    broken[0]["topics"][1]["content"]["pages"].pop()
    try:
        Q.validate_publication_integrity(
            units=broken, language="Spanish", track="tr")
    except Q.QualityGateError as exc:
        check("9/10" in str(exc),
              "a nine-question assessment fails closed instead of shipping short")
    else:
        check(False, "a nine-question assessment must never pass publication integrity")


def test_publication_integrity_catches_renderer_silent_drop():
    print("\n[Q6] a legacy renderer rejection fails the build instead of hiding a question")
    units = clean_integrity_fixture()
    page = units[0]["topics"][1]["content"]["pages"][2]
    page["prompt"] = "Marco vive en Madrid. ¿Cuál es su nacionalidad?"
    page["answer"] = "española"
    page["options"] = ["española", "italiana", "francesa", "turca"]
    page["distractors"] = ["italiana", "francesa", "turca"]
    page["explanation"] = "The nationality is Spanish."
    page["explanation_tr"] = "Doğru milliyet İspanyoldur."
    try:
        Q.validate_publication_integrity(
            units=units, language="Spanish", track="tr")
    except Q.QualityGateError as exc:
        # The gate now asks the renderer's own admission contract instead of a
        # second copy of it, so the refusal names the question and the export
        # that would lose it rather than citing a legacy predicate by name.
        message = str(exc)
        check("identity fact" in message and "10" in message,
              f"the hidden-world renderer filter fails the build: {message[:80]}")
    else:
        check(False, "a question the renderer would silently drop must fail the build")


def test_publication_integrity_rejects_duplicates_and_missing_english():
    print("\n[Q7] duplicate questions and incomplete bilingual material cannot publish")
    duplicated = clean_integrity_fixture()
    pages = duplicated[0]["topics"][1]["content"]["pages"]
    pages[3]["prompt"] = pages[2]["prompt"]
    try:
        Q.validate_publication_integrity(
            units=duplicated, language="Spanish", track="tr")
    except Q.QualityGateError as exc:
        check("duplicate MCQ stems" in str(exc),
              "verbatim repeated MCQs are blocked after semantic review")
    else:
        check(False, "duplicate MCQ stems must not publish")

    monolingual = clean_integrity_fixture()
    del monolingual[0]["topics"][0]["content"]["pages"][0]["title_tr"]
    try:
        Q.validate_publication_integrity(
            units=monolingual, language="Spanish", track="tr")
    except Q.QualityGateError as exc:
        check("incomplete EN/TR field pairs" in str(exc),
              "a missing English/Turkish counterpart fails closed")
    else:
        check(False, "one-language-only lesson fields must not publish")



def test_gemini_can_fill_a_missing_bilingual_counterpart():
    print("\n[Q8] missing bilingual fields are made patchable before semantic review")
    units = clean_integrity_fixture()
    topic = units[0]["topics"][0]
    del topic["content"]["pages"][0]["title_tr"]
    original = Q.T.call_model
    saw_empty_slot = {"value": False}

    def provider(messages, **kwargs):
        payload = json.loads(messages[-1]["content"])
        records = payload["topics"][0]["records"]
        saw_empty_slot["value"] = any(
            rec.get("path") == ["pages", 0, "title_tr"] and rec.get("value") == ""
            for rec in records
        )
        return T.Response(
            data={"topics": [{
                "topic_id": "t1", "verdict": "fix",
                "patches": [{
                    "path": ["pages", 0, "title_tr"],
                    "old": "", "value": "Sayılar",
                    "reason": "Restore the missing Turkish counterpart.",
                }],
            }]},
            input_tokens=2500, output_tokens=200, cost=0.001,
            model=kwargs.get("model", ""),
        )

    try:
        Q.T.call_model = provider
        budget = Q.ReviewBudget(0.05)
        applied = Q.review_unit_lessons(
            unit_title="Unit 1", topics=[topic], language="Spanish",
            level="A1", track="tr", budget=budget)
    finally:
        Q.T.call_model = original

    check(saw_empty_slot["value"],
          "the missing counterpart is exposed as an exact empty patch path")
    check(applied == 1 and topic["content"]["pages"][0]["title_tr"] == "Sayılar",
          "Gemini can repair the missing bilingual field without inventing structure")


def main():
    test_transport_strict_schema_and_content_blocks()
    test_non_ipa_fails_closed()
    test_gemini_lesson_review_repairs_pdf_defects()
    test_gemini_assessment_review_removes_multi_correct_item()
    test_single_semantic_review_model()
    test_publication_integrity_keeps_ten_questions()
    test_publication_integrity_catches_renderer_silent_drop()
    test_publication_integrity_rejects_duplicates_and_missing_english()
    test_gemini_can_fill_a_missing_bilingual_counterpart()
    print(f"\n=== {len(FAILS)} quality-gate failing checks ===")
    for failure in FAILS:
        print("  -", failure)
    if FAILS:
        sys.exit(1)
    print("publication quality gate: all regression checks passed")


if __name__ == "__main__":
    main()
