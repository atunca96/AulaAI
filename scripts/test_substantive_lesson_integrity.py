import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ai_engine import (
    _is_substantive_page,
    _is_substantive_lesson,
    _ensure_minimum_lesson_structure,
    synthesize_substantive_lesson,
    _normalize_lesson_pages,
)
from services.pdf_renderer_v12 import _normalize_pages


def test_substantive_page_checks():
    assert not _is_substantive_page({})
    assert not _is_substantive_page({"title": "Empty Page", "type": "overview"})
    assert not _is_substantive_page({"title": "Empty Vocab", "type": "vocabulary", "items": []})
    assert not _is_substantive_page({"title": "Empty Grammar", "type": "grammar", "rules": []})

    # Valid overview
    assert _is_substantive_page({"type": "overview", "text": "This is a detailed overview of Spanish greetings for A1 learners."})
    # Valid vocabulary
    assert _is_substantive_page({
        "type": "vocabulary",
        "items": [
            {"term": "hola", "translation": "hello"},
            {"term": "adiós", "translation": "goodbye"}
        ]
    })
    # Valid grammar
    assert _is_substantive_page({
        "type": "grammar",
        "rules": [{"rule": "Subject pronouns", "explanation": "In Spanish, subject pronouns are often dropped."}]
    })


def test_substantive_lesson_checks():
    assert not _is_substantive_lesson({})
    assert not _is_substantive_lesson({"pages": []})
    assert not _is_substantive_lesson({"pages": [{"title": "Title 1"}, {"title": "Title 2"}]})

    substantive_lesson = {
        "pages": [
            {"type": "overview", "text": "Detailed overview text exceeding twenty characters."},
            {"type": "vocabulary", "items": [{"term": "hola", "translation": "hello"}, {"term": "buenos días", "translation": "good morning"}]},
            {"type": "grammar", "rules": [{"rule": "Gender concord", "explanation": "Nouns agree in gender with determiners."}]}
        ]
    }
    assert _is_substantive_lesson(substantive_lesson)


def test_rules_without_source_evidence_survive():
    # Previous bug: rules without source_evidence were completely wiped out
    raw_data = {
        "pages": [
            {
                "type": "grammar",
                "title": "Grammar Rules",
                "rules": [
                    {
                        "rule": "Definite articles",
                        "explanation": "El is masculine singular, La is feminine singular.",
                        "example": "El libro, la casa.",
                        "source_evidence": ""  # empty source evidence
                    }
                ]
            }
        ]
    }
    normalized = _normalize_lesson_pages(raw_data, "Definite Articles", "Spanish", "A1")
    grammar_page = normalized["pages"][0]
    assert len(grammar_page["rules"]) == 1, f"Rule was dropped! {grammar_page['rules']}"
    assert grammar_page["rules"][0]["rule"] == "Definite articles"
    assert grammar_page["rules"][0]["provenance"] in ("source_inherent", "source_explicit")


def test_polymorphic_container_normalization():
    # LLM outputs vocabulary under "vocabulary" instead of "items", and rules under "grammar_rules"
    raw_data = {
        "pages": [
            {
                "type": "custom",
                "title": "Essential Vocabulary",
                "vocabulary": [
                    {"word": "agua", "meaning": "water"},
                    {"word": "pan", "meaning": "bread"}
                ]
            },
            {
                "type": "custom",
                "title": "Sentence Mechanics",
                "grammar_rules": [
                    {"rule": "Word order", "explanation": "SVO is standard."}
                ]
            }
        ]
    }
    normalized = _normalize_lesson_pages(raw_data, "Food Basics", "Spanish", "A1")
    p1 = normalized["pages"][0]
    p2 = normalized["pages"][1]
    assert p1["type"] == "vocabulary"
    assert len(p1["items"]) == 2
    assert p1["items"][0]["term"] == "agua"
    assert p2["type"] == "grammar"
    assert len(p2["rules"]) == 1


def test_synthesize_substantive_lesson():
    synth = synthesize_substantive_lesson("Travel and Transportation", "vocabulary", "Spanish", "A1", material_language="tr")
    assert _is_substantive_lesson(synth)
    assert len(synth["pages"]) >= 3
    # Check MCQ validity
    mcq_page = next((p for p in synth["pages"] if p.get("type") == "mcq"), None)
    assert mcq_page is not None
    assert len(mcq_page["options"]) == 4
    assert len(mcq_page.get("options_tr", [])) == 4
    assert len(mcq_page["distractors"]) == 3
    assert mcq_page["answer"] in mcq_page["options"]


def test_mcq_options_localization():
    import unittest.mock as mock
    import services.ai_engine as ai_engine

    # Case 1: English metalanguage options must be localized into options_tr
    lesson_with_metalang = {
        "pages": [
            {
                "type": "mcq",
                "prompt": "How is the vowel pronounced?",
                "explanation": "It is reduced in unstressed positions.",
                "options": [
                    "As a palatalized vowel in stressed position",
                    "As a reduced schwa sound"
                ]
            }
        ]
    }

    mock_translations = {
        "0": "Ünlü nasıl telaffuz edilir?",
        "1": "Vurgusuz konumlarda indirgenir.",
        "2": "Vurgulu konumda yumuşak ünlü olarak",
        "3": "İndirgenmiş schwa sesi olarak"
    }

    with mock.patch.object(ai_engine, "_call_ai", return_value=mock_translations):
        res = ai_engine.translate_lesson_to_turkish(lesson_with_metalang, language="Russian")
        p = res["pages"][0]
        assert "options_tr" in p, "options_tr should be generated for metalanguage options"
        assert len(p["options_tr"]) == 2
        assert "schwa" in p["options_tr"][1] or "İndirgenmiş" in p["options_tr"][1]

    # Case 2: Target-language single tokens must NOT be translated
    lesson_with_target_tokens = {
        "pages": [
            {
                "type": "mcq",
                "prompt": "Doğru zamiri seçiniz.",
                "prompt_tr": "Doğru zamiri seçiniz.",
                "explanation_tr": "Doğru açıklama.",
                "options": ["он", "она", "оно", "они"]
            }
        ]
    }
    res2 = ai_engine.translate_lesson_to_turkish(lesson_with_target_tokens, language="Russian")
    p2 = res2["pages"][0]
    assert p2.get("options_tr") is None, "Target tokens should not have options_tr created"


def test_ensure_minimum_lesson_structure():
    partial_lesson = {
        "pages": [
            {
                "type": "vocabulary",
                "items": [
                    {"term": "uno", "translation": "one", "translation_tr": "bir"},
                    {"term": "dos", "translation": "two", "translation_tr": "iki"}
                ]
            },
            {
                "type": "grammar",
                "rules": [{"rule": "Counting", "explanation": "Numerals precede nouns."}]
            }
        ]
    }
    expanded = _ensure_minimum_lesson_structure(partial_lesson, "Numbers", "Spanish", "A1")
    assert len(expanded["pages"]) >= 3
    assert _is_substantive_lesson(expanded)


def test_renderer_normalize_pages():
    # Hollow pages (only titles, no content) must be filtered
    content = {
        "pages": [
            {"type": "overview", "title": "Empty 1"},
            {"type": "vocabulary", "title": "Empty 2", "items": []},
            {"type": "grammar", "title": "Empty 3", "rules": []},
            {"type": "overview", "title": "Valid", "text": "This page actually has substantial content."}
        ]
    }
    valid_pages = _normalize_pages(content)
    assert len(valid_pages) == 1
    assert valid_pages[0]["title"] == "Valid"


def run():
    print("[TEST] Running Substantive Lesson Integrity Tests...")
    test_substantive_page_checks()
    print("  -> test_substantive_page_checks PASSED")
    test_substantive_lesson_checks()
    print("  -> test_substantive_lesson_checks PASSED")
    test_rules_without_source_evidence_survive()
    print("  -> test_rules_without_source_evidence_survive PASSED")
    test_polymorphic_container_normalization()
    print("  -> test_polymorphic_container_normalization PASSED")
    test_synthesize_substantive_lesson()
    print("  -> test_synthesize_substantive_lesson PASSED")
    test_mcq_options_localization()
    print("  -> test_mcq_options_localization PASSED")
    test_ensure_minimum_lesson_structure()
    print("  -> test_ensure_minimum_lesson_structure PASSED")
    test_renderer_normalize_pages()
    print("  -> test_renderer_normalize_pages PASSED")
    print("[TEST] ALL Substantive Lesson Integrity Tests PASSED!")


if __name__ == "__main__":
    run()
