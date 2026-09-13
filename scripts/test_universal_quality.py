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
    validate_mcq_semantics,
    validate_unicode_integrity,
    safe_unicode_normalize,
    sanitize_dialogue_speaker,
    validate_dialogue_speaker,
    is_adhoc_learner_respelling,
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

    # Soft Hyphen (U+00AD) from production regression -> MUST FAIL
    ok_shy1, why_shy1 = validate_unicode_integrity("по\u00ADанглийски")
    assert not ok_shy1 and "soft-hyphen" in why_shy1, f"Failed to catch soft-hyphen in Russian adverb: {why_shy1}"

    ok_shy2, why_shy2 = validate_unicode_integrity("İ\u00ADhâlinde")
    assert not ok_shy2 and "soft-hyphen" in why_shy2, f"Failed to catch soft-hyphen in Turkish case: {why_shy2}"

    # Noncharacter code point U+FFFF -> MUST FAIL
    ok_nonch, why_nonch = validate_unicode_integrity("invalid \uFFFF char")
    assert not ok_nonch and "unicode-noncharacter" in why_nonch, "Failed to catch noncharacter"

    # Private Use Area (Co) -> MUST FAIL
    ok_pua, why_pua = validate_unicode_integrity("pua \uE001 char")
    assert not ok_pua and "unicode-private-use" in why_pua, "Failed to catch PUA character"

    # Orphaned combining mark at string start -> MUST FAIL
    ok_orph, why_orph = validate_unicode_integrity("\u0301accent")
    assert not ok_orph and "orphaned-combining-mark" in why_orph, "Failed to catch orphaned combining mark"

    # B) Safe normalization of exotic hyphens -> MUST NORMALIZE TO STANDARD ASCII '-'
    # U+2011 Non-breaking hyphen in Russian adverbs and Turkish case markers
    norm_ru = safe_unicode_normalize("по\u2011русски")
    assert norm_ru == "по-русски", f"Expected 'по-русски', got {norm_ru}"

    norm_tr = safe_unicode_normalize("İ\u2011hâlinde")
    assert norm_tr == "İ-hâlinde", f"Expected 'İ-hâlinde', got {norm_tr}"

    norm_de = safe_unicode_normalize("deutsch\u2010englisch")
    assert norm_de == "deutsch-englisch", f"Expected standard hyphen, got {norm_de}"

    # Stripping discretionary soft-hyphens
    norm_shy = safe_unicode_normalize("по\u00ADанглийски")
    assert norm_shy == "поанглийски" and "\u00AD" not in norm_shy

    # C) Legitimate combining diacritics across languages -> MUST PASS
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

    # A) Real production failure classes of ad-hoc learner respelling -> MUST FAIL
    adhoc_samples = [
        ("mit-ró", True),
        ("[mask-va]", True),
        ("сло-ва́рь", True),
        ("slo-var'", True),
        ("[ˈzdrav-stvu-yte]", True),
        ("[mʲɪˈtro]", False),       # Authentic IPA with palatalization and near-close near-front vowel
        ("[mɐskˈva]", False),       # Authentic IPA with near-open central vowel
        ("nǐ hǎo", False),          # Standard Pinyin
        ("arigatou", False),        # Standard Romaji
    ]
    for phon_val, should_fail in adhoc_samples:
        is_bad = is_adhoc_learner_respelling(phon_val)
        if should_fail:
            assert is_bad, f"Expected ad-hoc respelling detection for '{phon_val}', but passed"
        else:
            assert not is_bad, f"Valid representation '{phon_val}' falsely classified as ad-hoc respelling"

    # Gate rejecting lesson mixing IPA with learner respellings
    production_regression_lesson = {
        "pages": [{
            "items": [
                {"term": "метро", "phonetic": "[mʲɪˈtro]"},
                {"term": "Москва", "phonetic": "[mask-va]"}
            ]
        }]
    }
    ok_mix, why_mix = _phonetic_gate(production_regression_lesson)
    assert not ok_mix and "ad-hoc-learner-respelling" in why_mix, f"Failed to catch ad-hoc [mask-va]: {why_mix}"

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
    # 4. INSTRUCTIONAL-LANGUAGE ISOLATION & DIALOGUE ROLE TESTS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Instructional-Language Isolation & Role Localization...")

    # Dialogue speaker leakage in Turkish material -> MUST FAIL validation
    assert not validate_dialogue_speaker("(Professor)", "tr")[0]
    assert not validate_dialogue_speaker("Student", "tr")[0]
    assert not validate_dialogue_speaker("Teacher", "tr")[0]
    assert not validate_dialogue_speaker("Passerby", "tr")[0]

    # Localized Turkish speaker roles -> MUST PASS
    assert validate_dialogue_speaker("Profesör", "tr")[0]
    assert validate_dialogue_speaker("Öğrenci", "tr")[0]
    assert validate_dialogue_speaker("Öğretmen", "tr")[0]

    # Automatic sanitization of English role labels to Turkish
    assert sanitize_dialogue_speaker("(Professor)", "tr") == "(Profesör)"
    assert sanitize_dialogue_speaker("Student", "tr") == "Öğrenci"
    assert sanitize_dialogue_speaker("Teacher", "tr") == "Öğretmen"
    assert sanitize_dialogue_speaker("Passerby", "tr") == "Yoldan Geçen"

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
    assert "the father" not in lexical_extracted
    assert "baba" not in lexical_extracted
    assert "German masculine noun" not in lexical_extracted
    assert "Almanca eril isim" not in lexical_extracted

    # ──────────────────────────────────────────────────────────────────────────
    # 5. FORMATIVE MCQ STRUCTURAL & SEMANTIC GROUNDING TESTS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Formative MCQ Validity & Semantic Grounding...")

    # Structural failures
    bad_mcq1 = {"type": "mcq", "options": ["a", "b", "c", "d"], "answer": "a"}
    assert not validate_mcq(bad_mcq1)[0]

    bad_mcq2 = {"type": "mcq", "prompt": "Q", "options": ["a", "b", "c"], "answer": "a"}
    assert not validate_mcq(bad_mcq2)[0]

    bad_mcq3 = {"type": "mcq", "prompt": "Q", "options": ["a", "a", "c", "d"], "answer": "a"}
    assert not validate_mcq(bad_mcq3)[0]

    bad_mcq4 = {"type": "mcq", "prompt": "Q", "options": ["a", "b", "c", "d"], "answer": "e"}
    assert not validate_mcq(bad_mcq4)[0]

    bad_mcq5 = {"type": "mcq", "prompt": "Q", "options": ["a", "b", "c", "d"], "answer": "b", "correct_index": 0}
    assert not validate_mcq(bad_mcq5)[0]

    # Real production semantic regression 1: Birthplace != Nationality -> MUST FAIL
    birthplace_mcq = {
        "type": "mcq",
        "prompt": "Анна родилась в Турции, она _______.",
        "options": ["турчанка", "испанка", "немка", "француженка"],
        "answer": "турчанка",
        "correct_index": 0
    }
    ok_bp, why_bp = validate_mcq(birthplace_mcq)
    assert not ok_bp and "birthplace-does-not-entail-nationality" in why_bp, f"Failed to catch birthplace leap: {why_bp}"

    # Explicit citizenship in stem -> MUST PASS
    citizenship_mcq = {
        "type": "mcq",
        "prompt": "Анна — гражданка Турции, она _______.",
        "options": ["турчанка", "испанка", "немка", "француженка"],
        "answer": "турчанка",
        "correct_index": 0
    }
    ok_cz, why_cz = validate_mcq(citizenship_mcq)
    assert ok_cz, f"Valid citizenship MCQ rejected: {why_cz}"

    # Real production semantic regression 2: Workplace != Profession -> MUST FAIL
    workplace_mcq = {
        "type": "mcq",
        "prompt": "Я работаю в школе. Кто я?",
        "options": ["учитель", "водитель", "инженер", "повар"],
        "answer": "учитель",
        "correct_index": 0
    }
    ok_wp, why_wp = validate_mcq(workplace_mcq)
    assert not ok_wp and "workplace-does-not-entail-profession" in why_wp, f"Failed to catch workplace leap: {why_wp}"

    # Explicit job duty in stem -> MUST PASS
    job_duty_mcq = {
        "type": "mcq",
        "prompt": "Я преподаю математику в школе. Кто я?",
        "options": ["учитель", "водитель", "инженер", "повар"],
        "answer": "учитель",
        "correct_index": 0
    }
    ok_jd, why_jd = validate_mcq(job_duty_mcq)
    assert ok_jd, f"Valid job duty MCQ rejected: {why_jd}"

    # ──────────────────────────────────────────────────────────────────────────
    # 6. STRUCTURAL INTEGRITY ENFORCEMENT & PIPELINE PURITY TESTS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Structural Integrity Enforcement & Pipeline Purity...")

    # Lesson containing dialogue role leak, exotic hyphen, ad-hoc phonetic, and semantic MCQ leap
    dirty_lesson = {
        "pages": [
            {
                "type": "overview",
                "title": "Giriş",
                "text": "Bu derste по\u2011русски konuşmayı öğreniyoruz."  # Exotic hyphen U+2011
            },
            {
                "type": "dialogue",
                "dialogue": [
                    {"speaker": "(Professor)", "text": "Здравствуйте!", "line_tr": "Merhaba!"},
                    {"speaker": "Student", "text": "Добрый день!", "line_tr": "İyi günler!"}
                ]
            },
            {
                "type": "vocabulary",
                "items": [
                    {"term": "словарь", "phonetic": "сло-ва́рь", "translation": "sözlük"},
                    {"term": "метро", "phonetic": "[mʲɪˈtro]", "translation": "metro"}
                ]
            },
            birthplace_mcq,  # Should be pruned due to non-entailed assumption
            citizenship_mcq  # Should be preserved
        ]
    }
    clean_lesson = enforce_material_integrity(dirty_lesson, language="Russian", material_language="tr")
    assert len(clean_lesson["pages"]) == 4, f"Expected 4 pages after pruning invalid MCQ, got {len(clean_lesson['pages'])}"

    # Check exotic hyphen normalized
    assert "по-русски" in clean_lesson["pages"][0]["text"]
    assert "\u2011" not in clean_lesson["pages"][0]["text"]

    # Check dialogue speakers localized to Turkish
    d_page = clean_lesson["pages"][1]["dialogue"]
    assert d_page[0]["speaker"] == "(Profesör)", f"Expected '(Profesör)', got {d_page[0]['speaker']}"
    assert d_page[1]["speaker"] == "Öğrenci", f"Expected 'Öğrenci', got {d_page[1]['speaker']}"

    # Check ad-hoc Cyrillic syllable phonetic cleared, legitimate IPA preserved
    v_items = clean_lesson["pages"][2]["items"]
    assert v_items[0]["phonetic"] == "", f"Expected cleared ad-hoc phonetic, got {v_items[0]['phonetic']}"
    assert v_items[1]["phonetic"] == "[mʲɪˈtro]", f"Expected intact IPA, got {v_items[1]['phonetic']}"

    # Check invalid MCQ pruned and valid MCQ kept
    assert clean_lesson["pages"][3]["prompt"] == "Анна — гражданка Турции, она _______."

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
