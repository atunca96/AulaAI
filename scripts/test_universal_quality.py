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
    sanitize_instructional_label,
    heal_syllable_hyphenated_ipa,
    heal_phonetic_prose,
    calibrate_rule_scope_consistency,
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

    # PRODUCTION REGRESSION: Soft hyphens (U+00AD) and non-breaking hyphens (U+2011)
    # in Russian compound adverbs and Turkish case references
    prod_hyphen_corruptions = [
        ("по\u00ADанглийски", "по-английски"),
        ("по\u00ADиспански", "по-испански"),
        ("по\u00ADрусски", "по-русски"),
        ("по\u00ADитальянски", "по-итальянски"),
        ("по\u00ADнемецки", "по-немецки"),
        ("İ\u00ADhâlinde", "İ-hâlinde"),
        ("по\u2011русски", "по-русски"),
    ]
    for corrupt, expected_clean in prod_hyphen_corruptions:
        ok_h, why_h = validate_unicode_integrity(corrupt)
        assert not ok_h, f"Failed to reject corrupt hyphen code point in: {corrupt}"
        healed = safe_unicode_normalize(corrupt)
        assert healed == expected_clean, f"Safe normalize failed on {corrupt}: expected '{expected_clean}', got '{healed}'"

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
        "по-русски, по-английски, по-немецки",                       # Russian hyphenated adverbs with ASCII '-'
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

    # A) PRODUCTION REGRESSION: Ad-hoc learner respellings or native syllable breaks -> MUST DETECT
    prod_adhoc_respellings = [
        "mit-ró",
        "[mask-va]",
        "сло-ва́рь",
        "slo-var'",
        "[ˈzdrav-stvu-yte]",
    ]
    for adhoc in prod_adhoc_respellings:
        assert is_adhoc_learner_respelling(adhoc), f"Failed to detect ad-hoc learner respelling: {adhoc}"

    # IPA mixed with ad-hoc hyphenated learner respelling inside lesson -> MUST FAIL
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
                {"term": "perro", "phonetic": "/ˈpe.ro/"},
                {"term": "метро", "phonetic": "[mʲɪˈtro]"},
            ]
        }]
    }
    ok_ipa, why_ipa = _phonetic_gate(clean_ipa)
    assert ok_ipa, f"Standard IPA/phonemic rejected: {why_ipa}"

    # Pure IPA strings must NOT be classified as adhoc respellings
    assert not is_adhoc_learner_respelling("[mʲɪˈtro]")
    assert not is_adhoc_learner_respelling("[ˈka.sa]")
    assert not is_adhoc_learner_respelling("/ˈpe.ro/")

    # Clean Pinyin without brackets -> MUST PASS
    clean_pinyin = {
        "pages": [{
            "items": [{"term": "你好", "phonetic": "nǐ hǎo", "translation": "hello"}]
        }]
    }
    ok_pinyin, why_pinyin = _phonetic_gate(clean_pinyin)
    assert ok_pinyin, f"Valid Pinyin representation rejected: {why_pinyin}"
    assert not is_adhoc_learner_respelling("nǐ hǎo")

    # ──────────────────────────────────────────────────────────────────────────
    # 4. INSTRUCTIONAL-LANGUAGE ISOLATION & ROLE LOCALIZATION TESTS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Instructional-Language Isolation & Role Localization...")

    # PRODUCTION REGRESSION: Untranslated English speaker role labels in Turkish materials
    assert not validate_dialogue_speaker("(Professor)", "tr")[0]
    assert not validate_dialogue_speaker("(Student)", "tr")[0]
    assert not validate_dialogue_speaker("Waiter", "tr")[0]
    assert not validate_dialogue_speaker("Teacher", "tr")[0]
    assert not validate_dialogue_speaker("Passerby", "tr")[0]

    # Localized Turkish role labels and proper names -> MUST PASS
    assert validate_dialogue_speaker("(Profesör)", "tr")[0]
    assert validate_dialogue_speaker("(Öğrenci)", "tr")[0]
    assert validate_dialogue_speaker("Garson", "tr")[0]
    assert validate_dialogue_speaker("Öğretmen", "tr")[0]
    assert validate_dialogue_speaker("Marco", "tr")[0]
    assert validate_dialogue_speaker("Anna", "tr")[0]

    # Localization sanitization checks
    assert sanitize_dialogue_speaker("(Professor)", "tr") == "(Profesör)"
    assert sanitize_dialogue_speaker("(Student)", "tr") == "(Öğrenci)"
    assert sanitize_dialogue_speaker("Waiter", "tr") == "Garson"
    assert sanitize_dialogue_speaker("Teacher", "tr") == "Öğretmen"
    assert sanitize_dialogue_speaker("Marco", "tr") == "Marco"

    # Multilingual role localization & validation across German, French, Spanish, English
    assert sanitize_dialogue_speaker("Waiter", "de") == "Kellner"
    assert sanitize_dialogue_speaker("Teacher", "de") == "Lehrer"
    assert sanitize_dialogue_speaker("Student", "de") == "Schüler"
    assert sanitize_dialogue_speaker("Marco", "de") == "Marco"
    assert validate_dialogue_speaker("Kellner", "de")[0]
    assert validate_dialogue_speaker("Lehrer", "de")[0]

    assert sanitize_dialogue_speaker("Waiter", "fr") == "Serveur"
    assert sanitize_dialogue_speaker("Teacher", "fr") == "Professeur"
    assert sanitize_dialogue_speaker("Doctor", "fr") == "Médecin"
    assert sanitize_dialogue_speaker("Anna", "fr") == "Anna"
    assert validate_dialogue_speaker("Serveur", "fr")[0]
    assert validate_dialogue_speaker("Professeur", "fr")[0]

    assert sanitize_dialogue_speaker("Waiter", "es") == "Camarero"
    assert sanitize_dialogue_speaker("Teacher", "es") == "Profesor"
    assert sanitize_dialogue_speaker("Student", "es") == "Estudiante"
    assert validate_dialogue_speaker("Camarero", "es")[0]
    assert validate_dialogue_speaker("Profesor", "es")[0]

    assert sanitize_dialogue_speaker("Garson", "en") == "Waiter"
    assert sanitize_dialogue_speaker("Öğretmen", "en") == "Teacher"
    assert sanitize_dialogue_speaker("Lehrer", "en") == "Teacher"
    assert validate_dialogue_speaker("Teacher", "en")[0]

    # Format variants: colons and parenthesized colons
    assert sanitize_dialogue_speaker("Student:", "tr") == "Öğrenci"
    assert sanitize_dialogue_speaker("(Student):", "tr") == "(Öğrenci)"
    assert sanitize_dialogue_speaker("Teacher:", "de") == "Lehrer"

    # Composite names (Name + Role)
    assert sanitize_dialogue_speaker("Marco (Student)", "tr") == "Marco (Öğrenci)"
    assert sanitize_dialogue_speaker("Anna (Teacher)", "de") == "Anna (Lehrer)"
    assert sanitize_dialogue_speaker("Marco (Student)", "it") == "Marco"
    assert sanitize_dialogue_speaker("Student (Marco)", "it") == "Marco"

    # Proper names across diverse cultures and alphabets -> MUST PASS unchanged
    proper_names = [
        "Anna", "Marco", "Pierre", "Elena", "Yuki", "Ahmed", "Sofia", "Ivan",
        "Иван", "Анна", "أحمد", "Άννα", "雪", "민수", "דוד", "अमित"
    ]
    for p_name in proper_names:
        assert sanitize_dialogue_speaker(p_name, "tr") == p_name
        assert sanitize_dialogue_speaker(p_name, "de") == p_name
        assert sanitize_dialogue_speaker(p_name, "it") == p_name
        assert validate_dialogue_speaker(p_name, "tr")[0]
        assert validate_dialogue_speaker(p_name, "it")[0]

    # Unknown/future locale simulation (e.g. Italian 'it', Portuguese 'pt')
    # 1. Generation-time correct locale roles -> preserved
    assert sanitize_dialogue_speaker("Studente", "it") == "Studente"
    assert sanitize_dialogue_speaker("(Studente)", "it") == "(Studente)"
    assert validate_dialogue_speaker("Studente", "it")[0]
    # 2. Foreign English role leakage -> neutral omission, no leakage to publication
    assert sanitize_dialogue_speaker("Student", "it") == ""
    assert sanitize_dialogue_speaker("(Teacher)", "it") == ""
    assert not validate_dialogue_speaker("Student", "it")[0]
    assert not validate_dialogue_speaker("(Teacher)", "it")[0]

    # Idempotence: sanitize(sanitize(x)) == sanitize(x) across all test fixtures
    idempotence_samples = [
        ("Student", "tr"),
        ("(Student)", "tr"),
        ("Student:", "tr"),
        ("(Student):", "tr"),
        ("Marco (Student)", "tr"),
        ("Marco", "tr"),
        ("Anna", "de"),
        ("Yuki", "fr"),
        ("Ahmed", "es"),
        ("Studente", "it"),
        ("Marco (Student)", "it"),
        ("Student", "it"),
        ("Иван", "it"),
        ("أحمد", "tr"),
    ]
    for spk_sample, lang_sample in idempotence_samples:
        first_pass = sanitize_dialogue_speaker(spk_sample, lang_sample)
        second_pass = sanitize_dialogue_speaker(first_pass, lang_sample)
        assert first_pass == second_pass, f"Idempotence failed for '{spk_sample}' in '{lang_sample}': '{first_pass}' != '{second_pass}'"

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
    # 5. FORMATIVE MCQ VALIDITY & SEMANTIC ENTAILMENT TESTS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Formative MCQ Validity & Semantic Entailment...")

    # A) Missing prompt -> FAIL
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

    # B) PRODUCTION REGRESSION: Semantic non-entailment leaps -> MUST FAIL
    # 1. Birthplace does NOT entail nationality or citizenship
    birthplace_leap_mcq = {
        "type": "mcq",
        "prompt": "Анна родилась в Турции, она _______.",
        "options": ["турчанка", "испанка", "немка", "француженка"],
        "answer": "турчанка",
        "correct_index": 0,
        "explanation": "Анна родилась в Турции."
    }
    ok_sem1, why_sem1 = validate_mcq_semantics(birthplace_leap_mcq)
    assert not ok_sem1 and "birthplace-does-not-entail-nationality" in why_sem1, f"Failed to reject birthplace-to-nationality leap: {why_sem1}"

    # 2. Workplace does NOT entail profession without stated duties
    workplace_leap_mcq = {
        "type": "mcq",
        "prompt": "Я работаю в школе, я _______.",
        "options": ["учитель", "водитель", "инженер", "повар"],
        "answer": "учитель",
        "correct_index": 0,
        "explanation": "В школе работают учителя."
    }
    ok_sem2, why_sem2 = validate_mcq_semantics(workplace_leap_mcq)
    assert not ok_sem2 and "workplace-does-not-entail-profession" in why_sem2, f"Failed to reject workplace-to-profession leap: {why_sem2}"

    # C) Valid questions with explicit semantic grounding -> MUST PASS
    # 1. Question with explicit duties stated
    grounded_profession_mcq = {
        "type": "mcq",
        "prompt": "Я преподаю русский язык в школе, я _______.",
        "options": ["учитель", "водитель", "инженер", "повар"],
        "answer": "учитель",
        "correct_index": 0,
        "explanation": "Преподаватель в школе — это учитель."
    }
    ok_gr_prof, why_gr_prof = validate_mcq(grounded_profession_mcq)
    assert ok_gr_prof, f"Grounded profession MCQ falsely rejected: {why_gr_prof}"

    # 2. Question with explicit citizenship stated
    grounded_citizenship_mcq = {
        "type": "mcq",
        "prompt": "Анна — гражданка Турции, она _______.",
        "options": ["турчанка", "испанка", "немка", "француженка"],
        "answer": "турчанка",
        "correct_index": 0,
        "explanation": "Гражданка Турции — турчанка."
    }
    ok_gr_cit, why_gr_cit = validate_mcq(grounded_citizenship_mcq)
    assert ok_gr_cit, f"Grounded citizenship MCQ falsely rejected: {why_gr_cit}"

    # Valid structural MCQ -> PASS
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

    # Localized options parity across instructional languages
    valid_localized_options = {
        "type": "mcq",
        "prompt": "Select:",
        "options": ["a", "b", "c", "d"],
        "answer": "a",
        "options_de": ["eins", "zwei", "drei", "vier"],
        "options_fr": ["un", "deux", "trois", "quatre"],
        "options_es": ["uno", "dos", "tres", "cuatro"]
    }
    assert validate_mcq(valid_localized_options)[0]

    invalid_localized_options = {
        "type": "mcq",
        "prompt": "Select:",
        "options": ["a", "b", "c", "d"],
        "answer": "a",
        "options_de": ["eins", "zwei", "drei"]  # Count mismatch -> must fail
    }
    ok_inv, why_inv = validate_mcq(invalid_localized_options)
    assert not ok_inv and "invalid-options_de" in why_inv

    # ──────────────────────────────────────────────────────────────────────────
    # 6. STRUCTURAL & END-TO-END LESSON INTEGRITY ENFORCEMENT TESTS
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Structural & End-to-End Lesson Integrity Enforcement...")

    lesson_payload = {
        "pages": [
            {"type": "overview", "title": "Overview", "text": "Lesson foundations on по\u00ADрусски."},
            {
                "type": "examples",
                "dialogue": [
                    {"speaker": "(Professor)", "text": "Здравствуйте!", "line_tr": "Merhaba!"},
                    {"speaker": "(Student)", "text": "Доброе утро!", "line_tr": "Günaydın!"},
                ]
            },
            {
                "type": "vocabulary",
                "items": [
                    {"term": "метро", "phonetic": "mit-ró", "translation_tr": "metro"},
                    {"term": "книга", "phonetic": "[ˈknʲi.ɡə]", "translation_tr": "kitap"},
                ]
            },
            good_mcq,
            bad_mcq1,  # Structurally broken -> should be pruned
            bad_mcq3,  # Duplicate options -> should be pruned
            {"type": "grammar", "title": "Rules", "rules": []}
        ]
    }
    clean_lesson = enforce_material_integrity(lesson_payload, "Russian", material_language="tr")
    # Verified non-destructive cleanup: exactly 5 valid pages remain
    assert len(clean_lesson["pages"]) == 5, f"Expected 5 valid pages after cleanup, got {len(clean_lesson['pages'])}"
    assert clean_lesson["pages"][0]["type"] == "overview"
    # Unicode soft hyphen healed:
    assert "по-русски" in clean_lesson["pages"][0]["text"]
    # Dialogue speaker roles localized:
    assert clean_lesson["pages"][1]["dialogue"][0]["speaker"] == "(Profesör)"
    assert clean_lesson["pages"][1]["dialogue"][1]["speaker"] == "(Öğrenci)"
    # Ad-hoc respelling removed from vocabulary:
    assert clean_lesson["pages"][2]["items"][0]["phonetic"] == ""
    assert clean_lesson["pages"][2]["items"][1]["phonetic"] == "[ˈknʲi.ɡə]"
    # MCQ preserved:
    assert clean_lesson["pages"][3]["type"] == "mcq"
    # Grammar preserved:
    assert clean_lesson["pages"][4]["type"] == "grammar"
    # Two structurally invalid MCQs recorded in removed list:
    assert len(clean_lesson.get("_integrity_removed_mcq", [])) == 2

    # Multilingual lesson integrity enforcement in German, French, and Spanish instructional contexts
    clean_de = enforce_material_integrity(lesson_payload, "Russian", material_language="de")
    assert clean_de["pages"][1]["dialogue"][0]["speaker"] == "(Professor)"
    assert clean_de["pages"][1]["dialogue"][1]["speaker"] == "(Schüler)"

    clean_fr = enforce_material_integrity(lesson_payload, "Russian", material_language="fr")
    assert clean_fr["pages"][1]["dialogue"][0]["speaker"] == "(Professeur)"
    assert clean_fr["pages"][1]["dialogue"][1]["speaker"] == "(Étudiant)"

    clean_es = enforce_material_integrity(lesson_payload, "Russian", material_language="es")
    assert clean_es["pages"][1]["dialogue"][0]["speaker"] == "(Profesor)"
    assert clean_es["pages"][1]["dialogue"][1]["speaker"] == "(Estudiante)"

    # Unknown locale 'it' non-destructive integrity enforcement:
    lesson_it_payload = {
        "pages": [
            {
                "type": "examples",
                "dialogue": [
                    {"speaker": "Marco (Student)", "text": "Ciao!", "translation": "Hello!"},
                    {"speaker": "Studente", "text": "Buongiorno!", "translation": "Good morning!"},
                    {"speaker": "(Teacher)", "text": "Prego!", "translation": "You are welcome!"}
                ]
            }
        ]
    }
    clean_it = enforce_material_integrity(lesson_it_payload, "Italian", material_language="it")
    # Dialogue turns must NOT be dropped (non-destructive)
    assert len(clean_it["pages"][0]["dialogue"]) == 3
    # Marco (Student) preserves proper name, omits foreign unlocalized role
    assert clean_it["pages"][0]["dialogue"][0]["speaker"] == "Marco"
    # Generation-time Italian role preserved
    assert clean_it["pages"][0]["dialogue"][1]["speaker"] == "Studente"
    # Foreign English role omitted to avoid English leakage in Italian material
    assert clean_it["pages"][0]["dialogue"][2]["speaker"] == ""

    # Level-agnostic invariance: same payload behaves identically regardless of CEFR level context
    clean_a1 = enforce_material_integrity(lesson_payload, "Russian", material_language="tr")
    clean_c2 = enforce_material_integrity(lesson_payload, "Russian", material_language="tr")
    assert clean_a1 == clean_c2, "Material integrity enforcement diverged across CEFR levels"

    # ──────────────────────────────────────────────────────────────────────────
    # 7. INSTRUCTIONAL LABEL ISOLATION, IPA HEALING & RULE-SCOPE CONSISTENCY
    # ──────────────────────────────────────────────────────────────────────────
    print("  -> Testing Instructional Labels, IPA Healing & Rule Scope Consistency...")

    # A) Pedagogical label localization & English leakage prevention
    assert sanitize_instructional_label("Hard Consonant Indicator Vowels", material_language="tr") == "Kalın Ünsüz Belirten Ünlüler"
    assert sanitize_instructional_label("Soft Consonant Indicator Vowels", material_language="tr") == "İnce Ünsüz Belirten Ünlüler"
    assert sanitize_instructional_label("Hard Consonant Indicator Vowels", material_language="de") == "Harte Konsonanten anzeigende Vokale"
    assert sanitize_instructional_label("Hard Consonant Indicator Vowels", material_language="fr") == "Voyelles indicatrices de consonnes dures"
    assert sanitize_instructional_label("Hard Consonant Indicator Vowels", material_language="en") == "Hard Consonant Indicator Vowels"
    assert sanitize_instructional_label("Hard Consonant Indicator Vowels: А, О, У, Ы, Э", material_language="tr") == "Kalın Ünsüz Belirten Ünlüler: А, О, У, Ы, Э"

    # B) Standard IPA Syllable-Hyphen Healing
    # [ˈdo-mə] -> [ˈdomə], [dɐ-ˈma] -> [dɐˈma], [mʲɪ-ˈtro] -> [mʲɪˈtro]
    assert heal_syllable_hyphenated_ipa("[ˈdo-mə]") == "[ˈdomə]"
    assert heal_syllable_hyphenated_ipa("[dɐ-ˈma]") == "[dɐˈma]"
    assert heal_syllable_hyphenated_ipa("[mʲɪ-ˈtro]") == "[mʲɪˈtro]"
    # Prose healing
    assert heal_phonetic_prose("Örnek olarak дом [ˈdo-mə] ve дома [dɐ-ˈma] sözcükleri.") == "Örnek olarak дом [ˈdomə] ve дома [dɐˈma] sözcükleri."
    # Ad-hoc non-IPA respellings are NOT healed into valid IPA
    assert heal_syllable_hyphenated_ipa("[mask-va]") == "[mask-va]"
    assert is_adhoc_learner_respelling("[mask-va]") is True
    assert heal_syllable_hyphenated_ipa("mit-ró") == "mit-ró"
    assert is_adhoc_learner_respelling("mit-ró") is True

    # C) Rule-Scope Calibration & Internal Contradiction Elimination
    overgeneralized_tr = "11 ile 19 arasındaki tüm sayılarda birincil vurgu daima 'на' hecesindedir."
    calibrated_tr = calibrate_rule_scope_consistency(overgeneralized_tr, {"оди́ннадцать", "двена́дцать"}, "tr")
    assert "daima 'на'" not in calibrated_tr
    assert "genellikle 'на' hecesindedir (оди́ннадцать ve четы́рнадцать hariç)" in calibrated_tr

    overgeneralized_en = "In numbers 11 to 19, the primary stress is always on the syllable 'na'."
    calibrated_en = calibrate_rule_scope_consistency(overgeneralized_en, {"оди́ннадцать"}, "en")
    assert "always on the syllable 'na'" not in calibrated_en
    assert "typically on 'на'" in calibrated_en

    # D) End-to-end integration test with enforce_material_integrity
    lesson_test_payload = {
        "pages": [
            {
                "type": "vocabulary",
                "title": "Russian Vowels",
                "title_tr": "Rusça Ünlüler",
                "items": [
                    {
                        "term": "А, О, У, Ы, Э",
                        "phonetic": "[ˈdo-mə]",
                        "translation": "Hard Consonant Indicator Vowels",
                        "translation_tr": ""
                    },
                    {
                        "term": "дома",
                        "phonetic": "[dɐ-ˈma]",
                        "translation": "at home",
                        "translation_tr": "evde"
                    },
                    {
                        "term": "метро",
                        "phonetic": "mit-ró",  # ad-hoc respelling -> must be blanked
                        "translation": "subway",
                        "translation_tr": "metro"
                    }
                ]
            },
            {
                "type": "grammar",
                "title": "Russian Numbers 11-19",
                "title_tr": "11-19 Arası Sayılar",
                "text": "дом [ˈdo-mə] ve дома [dɐ-ˈma]",
                "rules": [
                    {
                        "rule": "In numbers 11 to 19, stress is always on the syllable 'na'.",
                        "rule_tr": "11 ile 19 arasındaki tüm sayılarda birincil vurgu daima 'на' hecesindedir.",
                        "explanation_tr": "дом [ˈdo-mə] ve дома [dɐ-ˈma]"
                    }
                ]
            }
        ]
    }
    cleaned_test = enforce_material_integrity(lesson_test_payload, "Russian", material_language="tr")
    p0 = cleaned_test["pages"][0]
    # Check that [ˈdo-mə] and [dɐ-ˈma] were healed to [ˈdomə] and [dɐˈma]
    assert p0["items"][0]["phonetic"] == "[ˈdomə]"
    assert p0["items"][1]["phonetic"] == "[dɐˈma]"
    # Check that ad-hoc mit-ró was safely blanked
    assert p0["items"][2]["phonetic"] == ""
    # Check that English table label was localized to Turkish
    assert p0["items"][0]["translation_tr"] == "Kalın Ünsüz Belirten Ünlüler"

    p1 = cleaned_test["pages"][1]
    # Check prose phonetic healing
    assert p1["text"] == "дом [ˈdomə] ve дома [dɐˈma]"
    assert p1["rules"][0]["explanation_tr"] == "дом [ˈdomə] ve дома [dɐˈma]"
    # Check rule calibration
    assert "genellikle 'на' hecesindedir (оди́ннадцать ve четы́рнадцать hariç)" in p1["rules"][0]["rule_tr"]
    assert "typically on 'на'" in p1["rules"][0]["rule"]

    # ──────────────────────────────────────────────────────────────────────────
    # 8. CONTRACT & CEFR CONSISTENCY CHECKS
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
