"""The auditor, tested against the defects that actually shipped.

Every case here is taken verbatim from the Spanish A1 PDF the previous guard
passed. If a case ever stops failing, that defect can ship again.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.authoring import audit as A  # noqa: E402
from services.authoring import schema as S  # noqa: E402

FAILS = []


def check(cond, label):
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILS.append(label)


def codes(findings):
    return {f.code for f in findings}


# ── 1. The defect that started the rebuild ───────────────────────────────────

def test_greek_inside_ipa():
    print("\n[1] Greek letters inside a phonetic field")
    lesson = {"pages": [{"type": "vocabulary", "items": [
        {"term": "cena", "phonetic": "ˈθενα", "translation_tr": "akşam yemeği"},
    ]}]}
    found = A.audit_lesson(lesson, language="Spanish", track="tr")
    check("non_ipa_in_transcription" in codes(found), "[ˈθενα] is caught")
    hit = [f for f in found if f.code == "non_ipa_in_transcription"][0]
    check("U+03B5" in hit.detail and "U+03B1" in hit.detail, "it names the offending codepoints")
    # Greek alpha is deliberately absent from GREEK_TO_IPA: it could be meant as
    # `a` or as `ɑ`, which are different vowels. A transcription is a factual
    # claim about sounds, and guessing at one is how wrong phonetics gets taught,
    # so a field containing an ambiguous stray blocks and is regenerated rather
    # than being quietly resolved in the learner's material.
    check(hit.severity == A.BLOCK, "an ambiguous stray blocks rather than being guessed at")
    epsilon_only = A.audit_lesson(
        {"pages": [{"type": "vocabulary", "items": [{"term": "gente", "phonetic": "ˈxεnte"}]}]},
        language="Spanish")
    hit2 = [f for f in epsilon_only if f.code == "non_ipa_in_transcription"][0]
    check(hit2.severity == A.BLOCK,
          "a look-alike stray blocks because Unicode shape cannot prove the intended phoneme")

    clean = {"pages": [{"type": "vocabulary", "items": [
        {"term": "cena", "phonetic": "ˈθena", "translation_tr": "akşam yemeği"},
        {"term": "gente", "phonetic": "ˈxente", "translation_tr": "insanlar"},
        {"term": "chocolate", "phonetic": "tʃokoˈlate", "translation_tr": "çikolata"},
    ]}]}
    check("non_ipa_in_transcription" not in codes(A.audit_lesson(clean, language="Spanish")),
          "correct IPA — including θ, β, χ — passes untouched")

    beta = {"pages": [{"type": "vocabulary", "items": [
        {"term": "w", "phonetic": "ˈdoβle ube"}, {"term": "haber", "phonetic": "aˈβer"},
        {"term": "jota", "phonetic": "ˈxota"},
    ]}]}
    check("non_ipa_in_transcription" not in codes(A.audit_lesson(beta, language="Spanish")),
          "beta is IPA, not a stray Greek letter")


# ── 2. Two pronunciation systems ─────────────────────────────────────────────

def test_second_pronunciation_system():
    print("\n[2] IPA and learner respelling in one document")
    for sample in ("'gato' 'gah-toh' gibi sesler, 'ge-a-te-o' değil.",
                   "'teléfono' sözcüğü te-LÉ-fo-no biçiminde okunur.",
                   "'gato' sözcüğünde vurgulanan hece 'ga'dır: GÁ-to."):
        found = A.audit_lesson(
            {"pages": [{"type": "grammar", "text_tr": sample}]}, language="Spanish", track="tr")
        check("second_pronunciation_system" in codes(found), f"caught: {sample[:38]}…")

    check(not A.respelling_tokens("Bu ders e-posta yazmayı öğretir."),
          "an ordinary hyphenated word is not a respelling")
    check(not A.respelling_tokens("Kelimenin anlamı 'ev' olarak verilir."),
          "an ordinary quoted word is not a respelling")


# ── 3. A lesson contradicting its own transcriptions ─────────────────────────

def test_self_contradiction():
    print("\n[3] the same grapheme transcribed two ways")
    lesson = {"pages": [
        {"type": "phonetics", "items": [
            {"term": "c", "phonetic": "θ", "translation_tr": "e/i önünde"},
            {"term": "g", "phonetic": "x", "translation_tr": "e/i önünde"},
        ]},
        {"type": "vocabulary", "items": [
            {"term": "c", "phonetic": "ˈse", "translation_tr": "c harfi (la ce)"},
            {"term": "g", "phonetic": "ˈhe", "translation_tr": "g harfi (la ge)"},
        ]},
    ]}
    found = A.audit_lesson(lesson, language="Spanish", track="tr")
    check("self_contradicting_transcription" in codes(found),
          "the [θ] / [ˈse] and [x] / [ˈhe] contradictions are caught")
    check(len([f for f in found if f.code == "self_contradicting_transcription"]) == 2,
          "both contradicting graphemes are reported, not just the first")

    consistent = {"pages": [
        {"type": "phonetics", "items": [{"term": "casa", "phonetic": "ˈkasa"}]},
        {"type": "vocabulary", "items": [{"term": "casa", "phonetic": "kasa"}]},
    ]}
    check("self_contradicting_transcription" not in codes(
        A.audit_lesson(consistent, language="Spanish")),
        "marking stress in one place and not the other is not a contradiction")


# ── 4. Invented words presented as vocabulary ────────────────────────────────

def test_invented_form():
    print("\n[4] a form the lesson itself says is not a word")
    lesson = {"pages": [{"type": "grammar", "rules": [{
        "rule_tr": "'gu' kombinasyonu sert 'g' sesini korur.",
        "example": "gueso",
        "analysis_tr": "(varsayımsal: sert-g peynir) — standart İspanyolcada bu yapı yoktur.",
        "source_evidence": "p.5"}]}]}
    check("invented_form_taught" in codes(A.audit_lesson(lesson, language="Spanish", track="tr")),
          "'varsayımsal' beside an example is caught")
    for phrasing in ("This is a hypothetical form.", "bu uydurma bir kelimedir",
                     "not a real word in Spanish"):
        check(bool(A.hypothetical_markers(phrasing)), f"caught: {phrasing!r}")


# ── 5. Instructional-language leakage ────────────────────────────────────────

def test_language_leakage():
    print("\n[5] the wrong language in a typed field")
    lesson = {"pages": [{"type": "vocabulary",
                         "text_tr": "To spell 'mesa' you say the name of each of the letters.",
                         "items": [{"term": "r (at the start of a word)", "phonetic": "r"}]}]}
    found = A.audit_lesson(lesson, language="Spanish", track="tr")
    check("wrong_instructional_language" in codes(found),
          "English prose in a Turkish-track field is caught")
    check("instructional_prose_in_target_field" in codes(found),
          "'r (at the start of a word)' as a Spanish term is caught")

    ok = {"pages": [{"type": "vocabulary", "title_tr": "Ünlüler",
                     "text_tr": "Bu derste İspanyolca ünlüleri ve temel ünsüzleri öğreneceksiniz.",
                     "items": [{"term": "casa", "phonetic": "ˈkasa", "translation_tr": "ev",
                                "example": "La casa es grande."}]}]}
    check("wrong_instructional_language" not in codes(A.audit_lesson(ok, language="Spanish", track="tr")),
          "correct Turkish prose beside Spanish material passes")
    check("instructional_prose_in_target_field" not in codes(
        A.audit_lesson(ok, language="Spanish", track="tr")),
        "a genuine Spanish example is not mistaken for prose")

    # An English course teaches English: English in a target field is correct.
    english = {"pages": [{"type": "vocabulary", "text_tr": "Bu derste İngilizce öğreneceksiniz.",
                          "items": [{"term": "Which of these is correct in the shop?",
                                     "translation_tr": "Dükkanda hangisi doğru?"}]}]}
    check("instructional_prose_in_target_field" not in codes(
        A.audit_lesson(english, language="English", track="tr")),
        "an English course may put English in its target fields")


# ── 6. Spanish opening punctuation ───────────────────────────────────────────

def test_opening_punctuation():
    print("\n[6] obligatory opening marks")
    lesson = {"pages": [{"type": "mcq", "prompt": "Cómo estás?", "answer": "Muy bien",
                         "distractors": ["Adiós", "Gracias", "Hasta luego"],
                         "options": ["Muy bien", "Adiós", "Gracias", "Hasta luego"],
                         "why_tr": "Selamlaşmaya verilen doğru yanıttır."}]}
    found = A.audit_lesson(lesson, language="Spanish", track="tr")
    check("missing_opening_question_mark" in codes(found), "'Cómo estás?' is caught")
    check([f for f in found if f.code == "missing_opening_question_mark"][0].severity == A.REPAIR,
          "and is marked repairable rather than fatal")

    good = dict(lesson["pages"][0], prompt="¿Cómo estás?")
    check("missing_opening_question_mark" not in codes(
        A.audit_lesson({"pages": [good]}, language="Spanish", track="tr")),
        "correct Spanish passes")
    check("missing_opening_question_mark" not in codes(A.audit_lesson(
        {"pages": [{"type": "vocabulary", "items": [{"term": "Nasılsın?"}]}]}, language="Turkish")),
        "Turkish takes no opening mark")


# ── 7. A half-filled transcription column ────────────────────────────────────

def test_partial_column():
    print("\n[7] some rows transcribed, others silently blank")
    page = {"type": "phonetics", "items": [
        {"term": "ch", "phonetic": "tʃ"}, {"term": "ll", "phonetic": "ʎ"},
        {"term": "rr", "phonetic": "r"}, {"term": "ñ"}, {"term": "z"}, {"term": "j"}]}
    found = A.audit_lesson({"pages": [page]}, language="Spanish", track="tr")
    check("partial_transcription_column" in codes(found), "the blank ñ / z / j cells are caught")

    whole = {"type": "phonetics", "items": [
        {"term": "ch", "phonetic": "tʃ"}, {"term": "ll", "phonetic": "ʎ"},
        {"term": "ñ", "phonetic": "ɲ"}]}
    check("partial_transcription_column" not in codes(
        A.audit_lesson({"pages": [whole]}, language="Spanish")), "a complete column passes")
    bare = {"type": "vocabulary", "items": [{"term": "casa"}, {"term": "mesa"}, {"term": "silla"}]}
    check("partial_transcription_column" not in codes(
        A.audit_lesson({"pages": [bare]}, language="Spanish")),
        "a table with no transcription column at all is not a partial one")


# ── 8. Assessment items ──────────────────────────────────────────────────────

def test_items():
    print("\n[8] multiple-choice validity")
    base = {"prompt": "Completa: Nosotros _____ en el centro.", "answer": "comemos",
            "distractors": ["comes", "comer", "comen"],
            "options": ["comemos", "comes", "comer", "comen"], "why_tr": "Biz için doğru çekim."}
    check(not A.blocking(A.audit_item(base, language="Spanish", track="tr")),
          "a sound item passes clean")

    dup = dict(base, distractors=["comes", "comer", "comemos"],
               options=["comemos", "comes", "comer", "comemos"])
    check("duplicate_options" in codes(A.audit_item(dup, language="Spanish")),
          "the key repeated as a distractor is caught")

    slip = dict(base, answer="francés", distractors=["francesa", "frances", "franceses"],
                options=["francés", "francesa", "frances", "franceses"])
    check("mixed_spelling_variants" in codes(A.audit_item(slip, language="Spanish")),
          "an accent-slip standing in for a distractor is caught")

    para = dict(base, answer="hablo", distractors=["hablas", "habla", "hablan"],
                options=["hablo", "hablas", "habla", "hablan"])
    check("mixed_spelling_variants" not in codes(A.audit_item(para, language="Spanish")),
          "a real four-form paradigm is not mistaken for one")

    giveaway = {"prompt": "¿Qué palabra lleva una 'h' muda?", "answer": "hotel",
                "distractors": ["gato", "mesa", "casa"],
                "options": ["hotel", "gato", "mesa", "casa"], "why_tr": "h yazılır, okunmaz."}
    check("feature_only_in_key" in codes(A.audit_item(giveaway, language="Spanish")),
          "a feature only the key carries is caught")

    longkey = dict(base, answer="Por favor, ¿podría usted traerme la cuenta enseguida?",
                   distractors=["La cuenta", "Un café", "Otra vez"],
                   options=["Por favor, ¿podría usted traerme la cuenta enseguida?",
                            "La cuenta", "Un café", "Otra vez"])
    check("key_length_outlier" in codes(A.audit_item(longkey, language="Spanish")),
          "a key twice the length of every option is caught")

    leak = dict(base, prompt="Which of the following completes the sentence correctly?")
    check("stem_in_instructional_language" in codes(A.audit_item(leak, language="Spanish")),
          "an English stem in a Spanish course is caught")


# ── 9. Unicode integrity ─────────────────────────────────────────────────────

def test_unicode():
    print("\n[9] characters that must never reach a text layer")
    for bad, label in ((u"ca�sa", "replacement character"),
                       (u"ca￾sa", "noncharacter"),
                       (u"casa", "control character")):
        check("unicode_corruption" in codes(A.audit_lesson(
            {"pages": [{"type": "vocabulary", "items": [{"term": bad}]}]}, language="Spanish")),
            f"caught: {label}")
    check(not A.unicode_defects("İspanyolca ñ é ü — “alıntı”"),
          "legitimate diacritics, dashes and quotes pass")


def main():
    test_greek_inside_ipa()
    test_second_pronunciation_system()
    test_self_contradiction()
    test_invented_form()
    test_language_leakage()
    test_opening_punctuation()
    test_partial_column()
    test_items()
    test_unicode()
    print(f"\n=== {len(FAILS)} failing checks ===")
    for f in FAILS:
        print("  -", f)
    if FAILS:
        sys.exit(1)
    print("authoring auditor: every shipped defect is now caught")


if __name__ == "__main__":
    main()
