"""
Universal Regression Test Suite for AulaAI Quality Assurance.
Language-Agnostic Verification across all 15+ supported languages & CEFR A1-C2.
"""

from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_quality_guard import (
    validate_mcq,
    validate_unicode_integrity,
    safe_unicode_normalize,
    _script_gate,
    _phonetic_gate,
    enforce_material_integrity,
    enforce_release_hard_gate,
    is_metadata_or_proper_token,
    MaterialReleaseRejected,
)


def run_tests():
    print("[TEST-SUITE] Starting Universal Regression Tests...")

    # ──────────────────────────────────────────────────────────────────────────
    # 1. SCRIPT INTEGRITY TESTS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Script Integrity...")

    # A) Single-script language token corruption (homoglyph corruption) -> MUST FAIL
    # "рaбота" has Cyrillic 'р', Latin 'a' (U+0061), Cyrillic 'бота'
    corrupted_russian = {
        "pages": [{
            "type": "vocabulary",
            "items": [{"term": "р\u0061бота", "translation": "work"}]
        }]
    }
    ok, why = _script_gate(corrupted_russian, "Russian")
    assert not ok and "mixed-script-corruption" in why, f"Expected mixed-script failure for corrupted Russian token, got {ok}, {why}"

    # Corrupted Greek token: "νεpό" with Latin 'p' (U+0070) instead of Greek 'ρ' (U+03C1)
    corrupted_greek = {
        "pages": [{
            "type": "vocabulary",
            "items": [{"term": "νε\u0070ό", "translation": "water"}]
        }]
    }
    ok_gr, why_gr = _script_gate(corrupted_greek, "Greek")
    assert not ok_gr and "mixed-script-corruption" in why_gr, f"Expected mixed-script failure for corrupted Greek token, got {ok_gr}, {why_gr}"

    # B) Natural multiscript language tokens -> MUST PASS
    # Japanese mixes Kanji (Han) + Hiragana naturally in a single word
    japanese_natural = {
        "pages": [{
            "type": "vocabulary",
            "items": [
                {"term": "食べる", "phonetic": "[ta.be.ɾɯ]", "translation": "to eat"},
                {"term": "コーヒー", "phonetic": "[koːçiː]", "translation": "coffee"},
                {"term": "本", "phonetic": "[hoɴ]", "translation": "book"},
            ]
        }]
    }
    ok_jp, why_jp = _script_gate(japanese_natural, "Japanese")
    assert ok_jp, f"Natural Japanese multiscript token failed: {why_jp}"

    # Korean mixes Hangul + Hanja
    korean_natural = {
        "pages": [{
            "type": "vocabulary",
            "items": [
                {"term": "한국어", "phonetic": "[han.ɡu.ɡʌ]", "translation": "Korean language"},
                {"term": "學校", "phonetic": "[hak.kjo]", "translation": "school (hanja)"},
            ]
        }]
    }
    ok_kr, why_kr = _script_gate(korean_natural, "Korean")
    assert ok_kr, f"Natural Korean multiscript token failed: {why_kr}"

    # Serbian naturally allows both Cyrillic and Latin scripts
    serbian_cyrillic = {
        "pages": [{"type": "vocabulary", "items": [{"term": "хвала", "translation": "thanks"}]}]
    }
    ok_sr1, _ = _script_gate(serbian_cyrillic, "Serbian")
    assert ok_sr1, "Serbian Cyrillic failed"

    serbian_latin = {
        "pages": [{"type": "vocabulary", "items": [{"term": "hvala", "translation": "thanks"}]}]
    }
    ok_sr2, _ = _script_gate(serbian_latin, "Serbian")
    assert ok_sr2, "Serbian Latin failed"

    # C) Technical metadata tokens (CEFR, IPA, URLs, abbreviations) -> MUST PASS
    metadata_in_russian = {
        "pages": [{
            "type": "vocabulary",
            "items": [
                {"term": "книга", "translation": "book"},
            ],
            "rules": [{
                "rule": "CEFR A1 core noun paradigm (UNESCO)",
                "example": "Это книга.",
                "analysis": "Standard CEFR A1 structure via http://aulaai.edu"
            }]
        }]
    }
    ok_meta, why_meta = _script_gate(metadata_in_russian, "Russian")
    assert ok_meta, f"Metadata tokens (CEFR, A1, URL) falsely rejected in Russian lesson: {why_meta}"

    assert is_metadata_or_proper_token("A1")
    assert is_metadata_or_proper_token("B2+")
    assert is_metadata_or_proper_token("CEFR")
    assert is_metadata_or_proper_token("IPA")
    assert is_metadata_or_proper_token("UNESCO")
    assert is_metadata_or_proper_token("HTTP")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. UNICODE & GLYPHIC INTEGRITY TESTS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Unicode & Glyphic Integrity...")

    # A) Malformed replacement character (U+FFFD) -> MUST FAIL
    ok_rep, why_rep = validate_unicode_integrity("broken \uFFFD encoding")
    assert not ok_rep and "replacement-character" in why_rep, "Failed to catch replacement char"

    # Noncharacter code point U+FFFF -> MUST FAIL
    ok_nonch, why_nonch = validate_unicode_integrity("invalid \uFFFF char")
    assert not ok_nonch and "unicode-noncharacter" in why_nonch, "Failed to catch noncharacter"

    # Orphaned combining mark at string start -> MUST FAIL
    ok_orph, why_orph = validate_unicode_integrity("\u0301accent")
    assert not ok_orph and "orphaned-combining-mark" in why_orph, "Failed to catch orphaned combining mark"

    # B) Legitimate combining diacritics across languages -> MUST PASS
    # Turkish, Spanish, German, French, Swedish, Russian, Arabic, Indic
    valid_unicode_samples = [
        "İstanbul, çay, yağmur, göl, şair, üzüm",                     # Turkish
        "canción, mañana, lingüística, él, cómo",                     # Spanish
        "schön, größtmöglich, Weißbier, Äpfel",                       # German
        "français, fête, château, naïve, cœur",                       # French
        "smörgåsbord, räksmörgås, ångbåt",                            # Swedish
        "йогурт, подъезд, кофе́ (accented stress)",                     # Russian with combining acute
        "كِتَابٌ جَمِيلٌ (with harakat/tashkeel)",                   # Arabic with full vocalization
        "नमस्ते, विद्या (with virama and matras)",                    # Hindi Devanagari
    ]
    for sample in valid_unicode_samples:
        ok_u, why_u = validate_unicode_integrity(sample)
        assert ok_u, f"Valid Unicode sample rejected: {sample} -> {why_u}"
        norm = safe_unicode_normalize(sample)
        assert len(norm) > 0, "Safe normalize emptied string"

    # ──────────────────────────────────────────────────────────────────────────
    # 3. PRONUNCIATION-SYSTEM CONSISTENCY TESTS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Pronunciation-System Consistency...")

    # A) IPA mixed with ad-hoc hyphenated learner respelling -> MUST FAIL
    mixed_respelling = {
        "pages": [{
            "items": [{"term": "cat", "phonetic": "[kæt] KAT-uh-lee-nuh"}]
        }]
    }
    ok_phon_bad, why_phon_bad = _phonetic_gate(mixed_respelling)
    assert not ok_phon_bad and "learner-respelling" in why_phon_bad, "Failed to reject mixed learner respelling"

    # B) Standard IPA or phonemic notation -> MUST PASS
    clean_ipa = {
        "pages": [{
            "items": [
                {"term": "casa", "phonetic": "[ˈka.sa]"},
                {"term": "perro", "phonetic": "/ˈpe.ro/"}
            ]
        }]
    }
    ok_ipa, why_ipa = _phonetic_gate(clean_ipa)
    assert ok_ipa, f"Standard IPA/phonemic rejected: {why_ipa}"

    # Clean Pinyin without brackets -> MUST PASS
    clean_pinyin = {
        "pages": [{
            "items": [{"term": "你好", "phonetic": "nǐ hǎo", "translation": "hello"}]
        }]
    }
    ok_pinyin, why_pinyin = _phonetic_gate(clean_pinyin)
    assert ok_pinyin, f"Valid Pinyin representation rejected: {why_pinyin}"

    # ──────────────────────────────────────────────────────────────────────────
    # 4. INSTRUCTIONAL-LANGUAGE ISOLATION TESTS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Instructional-Language Isolation...")

    # Target lexical string iterator correctly extracts only target language keys
    test_node = {
        "title": "Family Members",
        "title_tr": "Aile Üyeleri",
        "items": [{
            "term": "der Vater",
            "translation": "the father",
            "translation_tr": "baba",
            "explanation": "German masculine noun",
            "explanation_tr": "Almanca eril isim"
        }],
        "prompt": "Choose the correct article for 'Vater':",
        "prompt_tr": "'Vater' için doğru artikeli seçin:",
        "options": ["der", "die", "das", "den"],
        "answer": "der"
    }
    from services.material_quality_guard import _iter_target_lexical_strings
    lexical_extracted = list(_iter_target_lexical_strings(test_node))
    assert "der Vater" in lexical_extracted
    assert "der" in lexical_extracted
    # Explanations and translations must NOT be extracted as target lexical tokens
    assert "the father" not in lexical_extracted
    assert "baba" not in lexical_extracted
    assert "German masculine noun" not in lexical_extracted
    assert "Almanca eril isim" not in lexical_extracted

    # ──────────────────────────────────────────────────────────────────────────
    # 5. FORMATIVE MCQ VALIDITY TESTS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Formative MCQ Validity...")

    # Missing prompt -> FAIL
    bad_mcq1 = {"type": "mcq", "options": ["a", "b", "c", "d"], "answer": "a"}
    ok, why = validate_mcq(bad_mcq1)
    assert not ok and why == "missing-prompt", "Did not catch missing prompt"

    # Fewer than 4 options -> FAIL
    bad_mcq2 = {"type": "mcq", "prompt": "Q", "options": ["a", "b", "c"], "answer": "a"}
    ok, why = validate_mcq(bad_mcq2)
    assert not ok and why == "option-count", "Did not catch option count"

    # Duplicate options -> FAIL
    bad_mcq3 = {"type": "mcq", "prompt": "Q", "options": ["a", "a", "c", "d"], "answer": "a"}
    ok, why = validate_mcq(bad_mcq3)
    assert not ok and why == "duplicate-options", "Did not catch duplicate options"

    # Key not in options -> FAIL
    bad_mcq4 = {"type": "mcq", "prompt": "Q", "options": ["a", "b", "c", "d"], "answer": "e"}
    ok, why = validate_mcq(bad_mcq4)
    assert not ok and why == "answer-not-in-options", "Did not catch answer not in options"

    # Correct index mismatch -> FAIL
    bad_mcq5 = {"type": "mcq", "prompt": "Q", "options": ["a", "b", "c", "d"], "answer": "b", "correct_index": 0}
    ok, why = validate_mcq(bad_mcq5)
    assert not ok and why == "correct-index-mismatch", "Did not catch correct index mismatch"

    # Valid MCQ -> PASS
    good_mcq = {
        "type": "mcq",
        "prompt": "Which definite article is used with masculine singular nouns in German in the nominative case?",
        "options": ["der", "die", "das", "den"],
        "answer": "der",
        "correct_index": 0,
        "explanation": "'der' is the nominative masculine singular definite article."
    }
    ok, why = validate_mcq(good_mcq)
    assert ok, f"Valid MCQ rejected: {why}"

    # Multilingual MCQ options validation
    multilingual_samples = [
        (["книга", "книги", "книге", "книгу"], "книга"),                 # Russian
        (["كِتَاب", "كُتُب", "كَاتِب", "مَكْتَبَة"], "كِتَاب"),           # Arabic
        (["本", "水", "山", "川"], "本"),                                # Japanese
        (["집", "물", "불", "책"], "집"),                                # Korean
        (["βιβλίο", "σπίτι", "νερό", "δέντρο"], "βιβλίο"),               # Greek
    ]
    for opts, ans in multilingual_samples:
        item = {"type": "mcq", "prompt": "Select the correct word:", "options": opts, "answer": ans}
        ok, why = validate_mcq(item)
        assert ok, f"Multilingual MCQ rejected: {opts} -> {why}"

    # ──────────────────────────────────────────────────────────────────────────
    # 6. STRUCTURAL INTEGRITY ENFORCEMENT TESTS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Structural Integrity Enforcement...")

    lesson_payload = {
        "pages": [
            {"type": "overview", "title": "Overview", "text": "Lesson foundations."},
            good_mcq,
            bad_mcq1,  # Should be pruned
            bad_mcq3,  # Should be pruned
            {"type": "grammar", "title": "Rules", "rules": []}
        ]
    }
    clean_lesson = enforce_material_integrity(lesson_payload, "German")
    assert len(clean_lesson["pages"]) == 3, f"Expected 3 valid pages after cleanup, got {len(clean_lesson['pages'])}"
    assert clean_lesson["pages"][0]["type"] == "overview"
    assert clean_lesson["pages"][1]["type"] == "mcq"
    assert clean_lesson["pages"][2]["type"] == "grammar"
    assert len(clean_lesson.get("_integrity_removed_mcq", [])) == 2

    # ──────────────────────────────────────────────────────────────────────────
    # 7. CONTRACT & CEFR CONSISTENCY CHECKS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Quality Contract Consistency...")

    patch_v49_file = ROOT / "scripts" / "patch_consolidate_prompt_contract_v49.py"
    contract_text = patch_v49_file.read_text(encoding="utf-8")

    # Contract must contain all critical universal quality directives
    required_contract_markers = [
        "UNIVERSAL TARGET-LANGUAGE & WRITING-SYSTEM INTEGRITY",
        "UNIVERSAL UNICODE & GLYPHIC INTEGRITY",
        "UNIVERSAL PRONUNCIATION-SYSTEM CONSISTENCY",
        "UNIVERSAL INSTRUCTIONAL-LANGUAGE ISOLATION & TWO-TRACK FIDELITY",
        "UNIVERSAL GRAMMATICAL, TYPOLOGICAL & SEMANTIC CORRECTNESS",
        "UNIVERSAL RULE-SCOPE CALIBRATION",
        "UNIVERSAL TEACH-BEFORE-USE & COVERAGE CLOSURE",
        "UNIVERSAL CEFR CALIBRATION (A1–C2)",
        "UNIVERSAL DIALOGUE & LEXICAL NATURALNESS",
        "UNIVERSAL FORMATIVE MCQ STRICT GROUNDING & SELF-CONSISTENCY",
        "FINAL SAME-PASS RELEASE PASS",
        "MCQ SELF-CONSISTENCY:",
        "INTERNAL CONSISTENCY:",
        "RULE-SCOPE CALIBRATION:",
        "WRITING-SYSTEM INTEGRITY:",
        "PHONETIC/NOTATION TRUTH:",
        "AULAAI_INLINE_PUBLICATION_QA_V46",
    ]
    for m in required_contract_markers:
        assert m in contract_text, f"Missing required quality contract marker: {m}"

    # CEFR levels A1-C2 must each have explicit distinct pedagogical scope guidance
    for lvl in ("A1:", "A2:", "B1:", "B2:", "C1:", "C2:"):
        assert lvl in contract_text, f"Missing explicit guidance for CEFR level {lvl}"

    print("[TEST-SUITE] All Universal Regression Tests PASSED successfully!")


if __name__ == "__main__":
    run_tests()
