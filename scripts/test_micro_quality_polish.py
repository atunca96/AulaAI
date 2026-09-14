#!/usr/bin/env python3
"""
Test Suite for Language-Agnostic Micro-Quality Polish.
Verifies:
1. Instructional grammar shorthand leakage detection and clean normalization.
2. Preservation of unrelated target-language content (quoted items, target vocabulary).
3. Formative MCQ with 4 plausible same-category options accepted across languages.
4. Rejection of nonexistent, placeholder, or obviously malformed distractors.
5. Language-agnostic parity across all supported languages.
"""

from pathlib import Path
import sys

import runpy

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(ROOT / "scripts" / "patch_micro_quality_polish.py"), run_name="__main__")

from services.material_quality_guard import (
    detect_grammar_shorthand_leakage,
    sanitize_instructional_shorthand,
    sanitize_instructional_metalanguage,
    deduplicate_morphological_parentheticals,
    validate_distractor_quality,
    validate_mcq,
    enforce_material_integrity,
    safe_unicode_normalize,
    _script_gate,
    align_lexical_fields,
    harmonize_mixed_scripts,
)
from services.pdf_renderer_v12 import _kind, _localized_title, TYPE_LABELS, _e


def test_grammar_shorthand_leakage_and_normalization():
    print("  -> Testing grammar shorthand leakage detection & normalization...")

    # 1. Turkish instructional text leaking English shorthand
    leaky_tr = "Bu tabloda он (masc.), она (fem.) ve оно (neut.) zamirleri (pl.) ile incelenir."
    leaks = detect_grammar_shorthand_leakage(leaky_tr, "tr")
    assert len(leaks) >= 4, f"Failed to detect all shorthand leaks in TR: {leaks}"
    assert any("masc" in l for l in leaks)
    assert any("fem" in l for l in leaks)
    assert any("neut" in l for l in leaks)
    assert any("pl" in l for l in leaks)

    cleaned_tr = sanitize_instructional_metalanguage(leaky_tr, "tr")
    assert "(eril)" in cleaned_tr, f"Expected (eril), got {cleaned_tr}"
    assert "(dişil)" in cleaned_tr, f"Expected (dişil), got {cleaned_tr}"
    assert "(nötr)" in cleaned_tr, f"Expected (nötr), got {cleaned_tr}"
    assert "(çoğul)" in cleaned_tr, f"Expected (çoğul), got {cleaned_tr}"
    assert "masc" not in cleaned_tr and "fem" not in cleaned_tr

    # Standalone shorthand with dot
    dot_tr = "masc. isimler her zaman tekil, fem. isimler ise dişil olur."
    cleaned_dot = sanitize_instructional_metalanguage(dot_tr, "tr")
    assert "eril isimler" in cleaned_dot
    assert "dişil isimler" in cleaned_dot

    # 2. English instructional text with native English shorthand -> NO LEAKAGE
    clean_en = "Notice that he (masc.) and she (fem.) take singular verbs."
    leaks_en = detect_grammar_shorthand_leakage(clean_en, "en")
    assert leaks_en == [], f"Expected no leaks detected for native English, got: {leaks_en}"
    assert sanitize_instructional_metalanguage(clean_en, "en") == clean_en


def test_unrelated_target_language_content_preserved():
    print("  -> Testing preservation of unrelated target-language content...")

    # Quoted target references must NOT be altered
    quoted_tr = 'Rusça sözlükte "masc." ve "fem." uluslararası sembol olarak yer alabilir.'
    assert detect_grammar_shorthand_leakage(quoted_tr, "tr") == []
    sanitized_quoted = sanitize_instructional_metalanguage(quoted_tr, "tr")
    assert '"masc."' in sanitized_quoted
    assert '"fem."' in sanitized_quoted

    # Target language words that resemble abbreviations must NOT be corrupted
    # e.g., Spanish "más", German "Plan", Polish "plan", Russian "он"
    mixed_content = "İspanyolca 'más' kelimesi daha fazla anlamına gelir ve bir plan gerektirir."
    sanitized_target = sanitize_instructional_metalanguage(mixed_content, "tr")
    assert "más" in sanitized_target
    assert "plan" in sanitized_target

    # ехать stem alternation rule must still be context-aware
    ekhat = "ехать fiili -д- gövdesi alır."
    assert "gövde 'ед-' biçimine dönüşür" in sanitize_instructional_metalanguage(ekhat, "tr")
    unrelated_d = "Bu fiil -д- gövdesi alır."
    assert "-д- gövdesi alır" in sanitize_instructional_metalanguage(unrelated_d, "tr")


def test_mcq_plausible_options_accepted():
    print("  -> Testing plausible same-category MCQ options across languages...")

    samples = [
        # German: definite articles (same morphological category)
        {
            "prompt": "Welcher Artikel steht im Nominativ maskulin?",
            "options": ["der", "die", "das", "den"],
            "answer": "der",
            "explanation": "'der' ist der bestimmte Artikel für maskuline Nomen im Nominativ."
        },
        # Russian: case inflections of the same noun
        {
            "prompt": "Выберите форму слова в родительном падеже:",
            "options": ["студент", "студента", "студенту", "студентом"],
            "answer": "студента",
            "explanation": "'студента' является формой родительного падежа."
        },
        # Spanish: conjugated verb forms of the same paradigm
        {
            "prompt": "Selecciona la forma correcta para 'nosotros':",
            "options": ["hablo", "hablas", "habla", "hablamos"],
            "answer": "hablamos",
            "explanation": "'hablamos' es la primera persona del plural en presente."
        },
        # Arabic: valid lexical forms
        {
            "prompt": "اختر الكلمة الصحيحة:",
            "options": ["كِتَاب", "كُتُب", "كَاتِب", "مَكْتَبَة"],
            "answer": "كِتَاب",
            "explanation": "كِتَاب هو المفرد الصحيح."
        },
        # Japanese: valid kanji options
        {
            "prompt": "正しい漢字を選んでください:",
            "options": ["本", "水", "山", "川"],
            "answer": "本",
            "explanation": "「本」が正しい選択肢です。"
        },
    ]

    for item in samples:
        item["type"] = "mcq"
        ok, why = validate_mcq(item)
        assert ok, f"Plausible MCQ rejected: {item['options']} -> {why}"


def test_malformed_and_nonexistent_distractors_rejected():
    print("  -> Testing rejection of nonexistent and malformed distractors...")

    # 1. Placeholder distractors
    bad_placeholders = [
        ["Option 1", "Option 2", "Option 3", "Option 4"],
        ["der", "die", "das", "Distractor 4"],
        ["casa", "perro", "gato", "Choice D"],
        ["haber", "tener", "estar", "N/A"],
    ]
    for opts in bad_placeholders:
        mcq = {"type": "mcq", "prompt": "Question", "options": opts, "answer": opts[0]}
        ok, why = validate_mcq(mcq)
        assert not ok and "malformed-distractor:placeholder" in why, f"Expected placeholder rejection for {opts}, got: {ok}, {why}"

    # 2. Punctuation-only noise
    mcq_punct = {"type": "mcq", "prompt": "Question", "options": ["der", "die", "das", "--"], "answer": "der"}
    ok, why = validate_mcq(mcq_punct)
    assert not ok and "malformed-distractor:punctuation-only" in why

    # 3. Repeated character / mashing artifacts
    mcq_mash = {"type": "mcq", "prompt": "Question", "options": ["книга", "книги", "книге", "книгааааа"], "answer": "книга"}
    ok, why = validate_mcq(mcq_mash)
    assert not ok and "malformed-distractor:char-repetition" in why

    # 4. Explanation admitting non-word / invented distractor
    mcq_admitted = {
        "type": "mcq",
        "prompt": "Almancada eril artikel hangisidir?",
        "options": ["der", "die", "das", "den"],
        "answer": "der",
        "explanation": "den burada uydurma form olarak eklenmiştir."
    }
    ok, why = validate_mcq(mcq_admitted)
    assert not ok and "malformed-distractor:admitted-non-word" in why

    # However, intentional error-hunt questions MUST NOT be rejected
    mcq_error_hunt = {
        "type": "mcq",
        "prompt": "Aşağıdaki seçeneklerden hangisi hatalı yazılmıştır?",
        "options": ["der", "die", "das", "denn"],
        "answer": "denn",
        "explanation": "'denn' bir bağlaçtır, artikel olarak hatalı bir form oluşturur."
    }
    ok, why = validate_mcq(mcq_error_hunt)
    assert ok, f"Error-hunt MCQ should be permitted: {why}"


def test_language_agnostic_behavior_across_all_languages():
    print("  -> Testing language-agnostic behavior across all languages...")

    languages = [
        ("Russian", "русский язык"),
        ("German", "deutsche Sprache"),
        ("Spanish", "idioma español"),
        ("French", "langue française"),
        ("Italian", "lingua italiana"),
        ("Portuguese", "língua portuguesa"),
        ("Turkish", "Türkçe"),
        ("Dutch", "Nederlandse taal"),
        ("Swedish", "svenska språket"),
        ("Greek", "ελληνική γλώσσα"),
        ("Arabic", "اللغة العربية"),
        ("Japanese", "日本語"),
        ("Korean", "한국어"),
        ("Chinese", "中文"),
    ]

    for lang_name, sample_text in languages:
        payload = {
            "pages": [{
                "type": "overview",
                "title": f"{lang_name} Lesson",
                "text": sample_text,
                "text_tr": f"{lang_name} dersine genel bakış.",
            }]
        }
        # Script integrity gate must pass
        ok, why = _script_gate(payload, lang_name)
        assert ok, f"Script gate failed for {lang_name}: {why}"

        # Enforce integrity must leave structure sound
        cleaned = enforce_material_integrity(payload, lang_name, material_language="tr")
        assert len(cleaned["pages"]) == 1


def test_section_label_and_title_localization():
    print("  -> Testing section label and title localization...")

    # 1. Page kind labels localized in Turkish
    assert _kind("theory", is_tr=True) == "Konu Anlatımı"
    assert _kind("theory", is_tr=False) == "Theory"
    assert _kind("practice", is_tr=True) == "Alıştırmalar"
    assert _kind("practice", is_tr=False) == "Practice"
    assert _kind("review", is_tr=True) == "Genel Tekrar"
    assert _kind("review", is_tr=False) == "Review"
    assert _kind("assessment", is_tr=True) == "Değerlendirme"
    assert _kind("assessment", is_tr=False) == "Assessment"
    assert _kind("overview", is_tr=True) == "Genel Bakış"
    assert _kind("overview", is_tr=False) == "Overview"
    assert _kind("vocabulary", is_tr=True) == "Kelime Bilgisi"
    assert _kind("grammar", is_tr=True) == "Dilbilgisi"

    # 2. Localized title resolution for standalone section names
    empty_maps = ({}, {}, {})
    assert _localized_title("Theory", is_tr=True, content=None, title_maps=empty_maps) == "Konu Anlatımı"
    assert _localized_title("Theory", is_tr=False, content=None, title_maps=empty_maps) == "Theory"
    assert _localized_title("Practice", is_tr=True, content=None, title_maps=empty_maps) == "Alıştırmalar"
    assert _localized_title("Review", is_tr=True, content=None, title_maps=empty_maps) == "Genel Tekrar"
    assert _localized_title("Assessment", is_tr=True, content=None, title_maps=empty_maps) == "Değerlendirme"

    # 3. Prefixed section titles: 'Theory: ...' -> 'Konu Anlatımı: ...'
    assert _localized_title("Theory: Fonetik Analiz", is_tr=True, content=None, title_maps=empty_maps) == "Konu Anlatımı: Fonetik Analiz"
    assert _localized_title("Theory: Fonetik Analiz", is_tr=False, content=None, title_maps=empty_maps) == "Theory: Fonetik Analiz"

    # 4. Target language content must remain untouched
    target_sentence = "The theory behind this concept is simple."
    assert sanitize_instructional_metalanguage(target_sentence, "en") == target_sentence


def test_morphology_aware_terminology_deduplication():
    print("  -> Testing morphology-aware terminology deduplication...")

    # 1. Redundant parentheticals with morphological endings simplified
    assert sanitize_instructional_metalanguage("Belirtme Hâlinde (Belirtme Hâli)", "tr") == "Belirtme Hâlinde"
    assert sanitize_instructional_metalanguage("Belirtme Hâli (Belirtme Hâli)", "tr") == "Belirtme Hâli"
    assert sanitize_instructional_metalanguage("Belirtme Hâli'nde (Belirtme Hâli)", "tr") == "Belirtme Hâli'nde"
    assert sanitize_instructional_metalanguage("İlgi/Tamlayan Hâlinde (İlgi/Tamlayan Hâli)", "tr") == "İlgi/Tamlayan Hâlinde"
    assert sanitize_instructional_metalanguage("Yönelme Hâlinde (Yönelme Hâli)", "tr") == "Yönelme Hâlinde"
    assert sanitize_instructional_metalanguage("Edat Durumunda (Edat Durumu)", "tr") == "Edat Durumunda"

    # 2. 'X biçimi (X)' / 'X biçiminde (X)'
    assert sanitize_instructional_metalanguage("çoğul biçimi (çoğul)", "tr") == "çoğul biçimi"
    assert sanitize_instructional_metalanguage("çoğul biçiminde (çoğul)", "tr") == "çoğul biçiminde"
    assert sanitize_instructional_metalanguage("geçmiş zaman biçimi (geçmiş zaman)", "tr") == "geçmiş zaman biçimi"

    # 3. Informative parentheticals MUST be strictly preserved
    assert sanitize_instructional_metalanguage("Belirtme Hâli (doğrudan nesne)", "tr") == "Belirtme Hâli (doğrudan nesne)"
    assert sanitize_instructional_metalanguage("Yalın Hâl (özne görevi)", "tr") == "Yalın Hâl (özne görevi)"
    assert sanitize_instructional_metalanguage("Genitive (possession)", "en") == "Genitive (possession)"
    assert sanitize_instructional_metalanguage("Accusative (direct object)", "en") == "Accusative (direct object)"

    # 4. Quoted target examples preserved
    quoted = "Bu cümle 'Belirtme Hâlinde (Belirtme Hâli)' kuralını açıklar."
    assert sanitize_instructional_metalanguage(quoted, "tr") == quoted


def test_rendered_example_shorthand_normalization():
    print("  -> Testing shorthand normalization in rendered examples & fields...")

    # Real user PDF case: До́брое у́тро (neut.) / До́брый день (masc.)
    sample = "До́брое у́тро (neut.) / До́брый день (masc.)"

    # Turkish instructional mode: must convert (neut.) -> (nötr), (masc.) -> (eril)
    rendered_tr = sanitize_instructional_shorthand(sample, "tr")
    assert "(nötr)" in rendered_tr, f"Expected (nötr), got: {rendered_tr}"
    assert "(eril)" in rendered_tr, f"Expected (eril), got: {rendered_tr}"
    assert "neut." not in rendered_tr and "masc." not in rendered_tr

    # English instructional mode: must preserve native English shorthand
    rendered_en = sanitize_instructional_shorthand(sample, "en")
    assert rendered_en == sample, f"Expected preserved EN shorthand, got: {rendered_en}"

    # Shorthand abbreviations with m., f., n.
    sample_mfn = "он (m.), она (f.), оно (n.)"
    rendered_mfn = sanitize_instructional_shorthand(sample_mfn, "tr")
    assert "(eril)" in rendered_mfn and "(dişil)" in rendered_mfn and "(nötr)" in rendered_mfn

    # Quoted example must NOT be modified
    quoted = "Belirtme: 'До́брое у́тро (neut.)' kalıbı"
    rendered_quoted = sanitize_instructional_shorthand(quoted, "tr")
    assert "'До́брое у́тро (neut.)'" in rendered_quoted

    # Material integrity recursive pass
    payload = {
        "pages": [
            {
                "type": "grammar",
                "rules": [{"example": sample, "target": "Привет (neut.)"}],
                "comparisons": [{"target": sample, "note": "Günün vakti (masc.)"}]
            }
        ]
    }
    cleaned_payload = enforce_material_integrity(payload, "Russian", material_language="tr")
    rule = cleaned_payload["pages"][0]["rules"][0]
    cmp = cleaned_payload["pages"][0]["comparisons"][0]
    assert "(nötr)" in rule["example"] and "(eril)" in rule["example"]
    assert "(nötr)" in rule["target"]
    assert "(nötr)" in cmp["target"]
    assert "(eril)" in cmp["note"]


def test_semantic_unicode_noncharacter_resolution():
    print("  -> Testing semantic Unicode noncharacter resolution & text-layer safety...")

    # Real user PDF cases:
    # 1. Russian prefix compounds: говори́т по\ufffeру́сски -> говори́т по-ру́сски
    assert safe_unicode_normalize("говори́т по\ufffeру́сски") == "говори́т по-ру́сски"
    assert safe_unicode_normalize("говоря́т по\ufffeру́сски") == "говоря́т по-ру́сски"
    assert safe_unicode_normalize("по\ufffeанглийски") == "по-английски"

    # 2. Suffix + conjunction cross-word boundary: -и\ufffeve -ат/-ят -> -и ve -ат/-ят
    assert safe_unicode_normalize("-и\ufffeve -ат/-ят") == "-и ve -ат/-ят"

    # 3. Turkish nominal compounds: sertlik\ufffeyumuşaklık -> sertlik-yumuşaklık
    assert safe_unicode_normalize("sertlik\ufffeyumuşaklık") == "sertlik-yumuşaklık"

    # 4. Adjacent duplicate noncharacters deduplicated cleanly
    assert safe_unicode_normalize("по\ufffe\ufffeру́сски") == "по-ру́сски"

    # 5. Plane-ends, surrogates, and reserved noncharacters stripped
    assert safe_unicode_normalize("A\U0001fffeB") == "A B"
    assert safe_unicode_normalize("X\U0002ffffY") == "X Y"
    assert safe_unicode_normalize("тест\ufdd0слово") == "тест слово"
    assert "\ufffe" not in safe_unicode_normalize("любой\ufffeтекст")
    assert "\uffff" not in safe_unicode_normalize("любой\uffffтекст")

    # 6. PDF renderer _e guarantees zero noncharacters in HTML/story layer
    raw_html = _e("по\ufffeру́сски & -и\ufffeve")
    assert "\ufffe" not in raw_html
    assert "по-ру́сски &amp; -и ve" == raw_html

    # 7. Linguistic combining marks & accents unharmed
    assert safe_unicode_normalize("дай ѝ книгата") == "дай ѝ книгата"
    assert safe_unicode_normalize("сѐ уште") == "сѐ уште"
    assert safe_unicode_normalize("très élève voilà où") == "très élève voilà où"
    assert safe_unicode_normalize("профѐссор") == "профессор"


def test_mixed_script_morphology_harmonization():
    print("  -> Testing language-agnostic mixed-script morphology harmonization...")

    # Cyrillic tokens with Latin homoglyphs
    assert safe_unicode_normalize("-иte") == "-ите"
    assert safe_unicode_normalize("-ИТE") == "-ИТЕ"
    assert safe_unicode_normalize("говориte") == "говорите"
    assert safe_unicode_normalize("рaбота") == "работа"
    assert safe_unicode_normalize("Вы говориte по-русски?") == "Вы говорите по-русски?"
    assert safe_unicode_normalize("Окончания: -иte ve -ат/-ят") == "Окончания: -ите ve -ат/-ят"

    # Latin tokens with Cyrillic homoglyphs
    assert safe_unicode_normalize("comеr") == "comer"
    assert safe_unicode_normalize("El verbo comеr es regular.") == "El verbo comer es regular."

    # Greek tokens with Latin homoglyphs
    assert safe_unicode_normalize("νεpό") == "νερό"

    # Bilingual compound words & legitimate Latin loan words PRESERVED
    assert safe_unicode_normalize("online-курс") == "online-курс"
    assert safe_unicode_normalize("Wi-Fi-сеть") == "Wi-Fi-сеть"
    assert safe_unicode_normalize("c-a-t") == "c-a-t"
    assert safe_unicode_normalize("по-русски") == "по-русски"
    assert safe_unicode_normalize("CEFR B1") == "CEFR B1"

    # HTML / story layer via _e preserves and harmonizes
    rendered = _e("-иte & comеr")
    assert "-ите &amp; comer" == rendered


def test_mcq_distractor_authenticity_and_admitted_non_words():
    print("  -> Testing MCQ distractor authenticity & non-word rejection...")

    # 1. Explanations admitting non-words or nonexistent forms (Turkish & English)
    opts = ["площадь", "площади", "площадью", "площаде"]
    expl_tr_admitted = "D seçeneğinde verilen 'площаде' böyle bir kelime yoktur; 3. çekim dişilleri -е eki almaz."
    ok, why = validate_distractor_quality(opts, prompt="Doğru formu seçiniz.", explanation=expl_tr_admitted)
    assert not ok and "admitted-non-word" in why

    expl_tr_varolmayan = "'площаде' var olmayan bir formdur."
    ok, why = validate_distractor_quality(opts, prompt="Doğru formu seçiniz.", explanation=expl_tr_varolmayan)
    assert not ok and "admitted-non-word" in why

    expl_tr_mevcut = "Böyle bir çekim Rusçada mevcut değildir."
    ok, why = validate_distractor_quality(opts, prompt="Doğru formu seçiniz.", explanation=expl_tr_mevcut)
    assert not ok and "admitted-non-word" in why

    expl_en_admitted = "Option D 'площаде' is an invented non-word that does not exist in Russian."
    ok, why = validate_distractor_quality(opts, prompt="Choose the correct form.", explanation=expl_en_admitted)
    assert not ok and "admitted-non-word" in why

    # Legitimate error-hunt items ALLOWED to identify errors
    error_hunt_prompt = "Aşağıdaki seçeneklerden hangisi yanlış yazılmıştır?"
    ok, why = validate_distractor_quality(opts, prompt=error_hunt_prompt, explanation=expl_tr_admitted)
    assert ok, f"Expected error hunt question to pass, got: {why}"

    # 2. Lazy / placeholder distractors REJECTED across languages
    lazy_samples = [
        ["der", "die", "das", "None of the above"],
        ["der", "die", "das", "All of the above"],
        ["der", "die", "das", "Hiçbiri"],
        ["der", "die", "das", "Yukarıdakilerin hepsi"],
        ["der", "die", "das", "Doğru cevap yok"],
        ["der", "die", "das", "uydurma"],
        ["der", "die", "das", "yanlış"],
        ["el", "la", "los", "ninguna de las anteriores"],
        ["le", "la", "les", "toutes des réponses"],
    ]
    for bad_opts in lazy_samples:
        ok, why = validate_distractor_quality(bad_opts, prompt="Select article")
        assert not ok and "placeholder" in why, f"Failed to reject lazy distractor {bad_opts}: {why}"

    # 3. Meta-annotated options (e.g. '(uydurma)', '(yanlış)') REJECTED
    annotated = ["der", "die", "das", "den (uydurma)"]
    ok, why = validate_distractor_quality(annotated, prompt="Select article")
    assert not ok and "meta-annotation" in why

    # 4. Formative MCQ validation rejecting admitted non-words
    bad_page = {
        "type": "mcq",
        "prompt": "Hangi form doğrudur?",
        "options": ["площадь", "площади", "площадью", "площаде"],
        "answer": "площадь",
        "explanation": expl_tr_admitted,
    }
    good_page = {
        "type": "mcq",
        "prompt": "Hangi form doğrudur?",
        "options": ["площадь", "площади", "площадью", "площадям"],
        "answer": "площадь",
        "explanation": "A seçeneği Yalın Hâl tekil formudur.",
    }
    ok_bad, why_bad = validate_mcq(bad_page)
    assert not ok_bad and "admitted-non-word" in why_bad
    ok_good, why_good = validate_mcq(good_page)
    assert ok_good, f"Expected valid MCQ to pass, got: {why_good}"


def test_pronunciation_ipa_field_alignment():
    print("  -> Testing pronunciation / IPA / field alignment & integrity...")

    # 1. Extract bracketed IPA embedded in term
    item_ipa = {"term": "здравствуйте [ˈzdrastvujtʲe]", "phonetic": "", "translation_tr": "merhaba"}
    aligned = align_lexical_fields(item_ipa, language="Russian", is_tr=True)
    assert aligned["term"] == "здравствуйте"
    assert aligned["phonetic"] == "[ˈzdrastvujtʲe]"
    assert aligned["translation_tr"] == "merhaba"

    # Slash IPA in term
    item_slash = {"term": "вода (/vɐˈda/)", "phonetic": "", "translation_tr": "su"}
    aligned_slash = align_lexical_fields(item_slash, language="Russian", is_tr=True)
    assert aligned_slash["term"] == "вода"
    assert aligned_slash["phonetic"] == "[vɐˈda]"

    # 2. Misplaced translation in phonetic recovered and cleaned
    item_phon_leak = {"term": "спасибо", "phonetic": "teşekkürler", "translation_tr": ""}
    aligned_leak = align_lexical_fields(item_phon_leak, language="Russian", is_tr=True)
    assert aligned_leak["phonetic"] == ""
    assert aligned_leak["translation_tr"] == "teşekkürler"

    # 3. Realigning swapped example and example_tr (Cyrillic target, Turkish instructional)
    item_swapped_ex = {
        "term": "книга",
        "example": "Bu bir kitaptır.",
        "example_tr": "Это книга."
    }
    aligned_ex = align_lexical_fields(item_swapped_ex, language="Russian", is_tr=True)
    assert aligned_ex["example"] == "Это книга."
    assert aligned_ex["example_tr"] == "Bu bir kitaptır."

    # 4. Realigning swapped term and translation_tr
    item_swapped_term = {
        "term": "günaydın",
        "translation_tr": "доброе утро"
    }
    aligned_term = align_lexical_fields(item_swapped_term, language="Russian", is_tr=True)
    assert aligned_term["term"] == "доброе утро"
    assert aligned_term["translation_tr"] == "günaydın"

    # 5. Normalizing IPA bracket formatting & stripping trailing punctuation
    item_punct = {"term": "кот", "phonetic": "kot,"}
    aligned_punct = align_lexical_fields(item_punct, language="Russian", is_tr=True)
    assert aligned_punct["phonetic"] == "[kot]"

    # 6. Integrated pass in enforce_material_integrity
    full_lesson = {
        "pages": [
            {
                "type": "vocabulary",
                "items": [
                    {
                        "term": "говорить [ɡəvɐˈrʲitʲ]",
                        "phonetic": "",
                        "translation_tr": "konuşmak",
                        "example": "Biz Rusça konuşuyoruz.",
                        "example_tr": "Мы говориte по-русски."
                    }
                ]
            }
        ]
    }
    cleaned_lesson = enforce_material_integrity(full_lesson, language="Russian", material_language="tr")
    cleaned_item = cleaned_lesson["pages"][0]["items"][0]
    assert cleaned_item["term"] == "говорить"
    assert cleaned_item["phonetic"] == "[ɡəvɐˈrʲitʲ]"
    # Note: example and example_tr swapped back, and '-иte' harmonized to '-ите'!
    assert cleaned_item["example"] == "Мы говорите по-русски."
    assert cleaned_item["example_tr"] == "Biz Rusça konuşuyoruz."


def run_all():
    print("[TEST-SUITE] Starting Language-Agnostic Micro-Quality Polish Tests...")
    test_grammar_shorthand_leakage_and_normalization()
    test_rendered_example_shorthand_normalization()
    test_semantic_unicode_noncharacter_resolution()
    test_mixed_script_morphology_harmonization()
    test_mcq_distractor_authenticity_and_admitted_non_words()
    test_pronunciation_ipa_field_alignment()
    test_unrelated_target_language_content_preserved()
    test_section_label_and_title_localization()
    test_morphology_aware_terminology_deduplication()
    test_mcq_plausible_options_accepted()
    test_malformed_and_nonexistent_distractors_rejected()
    test_language_agnostic_behavior_across_all_languages()
    print("[TEST-SUITE] All Micro-Quality Polish Tests PASSED successfully!\n")


if __name__ == "__main__":
    run_all()
