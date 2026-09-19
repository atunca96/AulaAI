"""READY and the exported PDF must describe the same classroom.

Every case here comes from one shipped Spanish A1 classroom that reached READY
and then exported a PDF containing defects the publication contract declares
impossible. The classroom was not broken — it was *validated*, and then the
renderer published something else.

The failure classes, all of them reproduced below:

  1. Unit 3 held ten assessment questions in the database and printed eight.
     The gate proved the stored count; the renderer dropped two on its own
     authority, using a predicate the gate did not model.
  2. A stem present in only one locale's field renders in that export and
     vanishes from the other.
  3. Greek look-alike characters — ο ν ε κ ι α μ υ — inside strings that read
     as Latin/IPA: `once [ˈονθε]`, `quince [ˈκινθε]`, `cocinero [κοθiˈneɾo]`.
  4. `veintinueve` glossed "twenty-nine" in a Turkish course.
  5. Unit headings printed as "Ünite 1: Ünite 1: İlk Kelimeler ve Selamlaşma".
  6. A topic whose stored JSON cannot be parsed auditing clean as `{}`.
  7. A deterministic blocker surviving semantic review and still reaching READY,
     because the finding was never re-checked against the object persisted.
  8. The renderer's SECOND drop point — a page filter running before the render
     loop, with a third predicate that neither the loop nor the gate consulted.

No network and no API key: the gate's deterministic half runs entirely offline.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")
os.environ.setdefault("AULAAI_DATA_DIR", tempfile.mkdtemp(prefix="aulaai-divergence-"))

from services.authoring import audit as A  # noqa: E402
from services.authoring import quality_gate as Q  # noqa: E402
from services.authoring import render_contract as RC  # noqa: E402
from services.authoring import schema as S  # noqa: E402

FAILS = []


def check(cond, label):
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILS.append(label)


def codes(lesson, language="Spanish", track="tr"):
    return [f.code for f in A.blocking(A.audit_lesson(lesson, language=language, track=track))]


# ── Fixtures shaped exactly like stored content ──────────────────────────────

def mcq(index, prompt, options, answer=None, explanation=None,
        explanation_tr=None, **extra):
    # A "clean" fixture must satisfy the same final-artifact rationale invariant
    # as production: cite learner-visible evidence beyond merely naming the key.
    # Tests that intentionally need a bad rationale pass one explicitly.
    if explanation is None:
        explanation = (
            f"The visible question «{prompt}» supplies the evidence used to "
            "select the keyed option."
        )
    if explanation_tr is None:
        explanation_tr = (
            f"Görünür soru «{prompt}» işaretli seçeneği belirleyen kanıtı verir."
        )
    # The two explanation fields are DIFFERENT strings, as production stores
    # them: `explanation` comes from the item's `why` and `explanation_tr` from
    # its `why_tr`. An identical pair is itself a defect this suite checks for,
    # so a fixture that shared one string would be testing the wrong thing.
    page = {
        "type": "mcq", "stem_scope": "target_complete", "assessment_scope": "unit",
        "title": f"Question {index}", "title_tr": f"Soru {index}",
        "prompt": prompt, "options": list(options),
        "answer": answer or options[0], "distractors": list(options[1:]),
        "explanation": explanation, "explanation_tr": explanation_tr,
    }
    page.update(extra)
    return page


GOOD_STEMS = [
    "¿Cómo se saluda por la mañana?", "Completa: Yo _____ estudiante.",
    "¿Qué dices para pedir la cuenta?", "Completa: Nosotros _____ en casa.",
    "¿Cómo te despides por la noche?", "Completa: Ella _____ café.",
    "¿Qué respondes a '¿Cómo estás?'", "Completa: Tú _____ la puerta.",
    "¿Cómo pides ayuda con cortesía?", "Completa: Ellos _____ al mercado.",
]


def assessment_topic(stems=None, title="Ünite Değerlendirmesi: Unidad 3"):
    stems = stems or GOOD_STEMS
    pages = [mcq(i, s, ["opción a", "opción b", "opción c", "opción d"])
             for i, s in enumerate(stems, 1)]
    return {"id": "a3", "title": title, "type": "unit_assessment",
            "is_assessment": True, "content": {"pages": pages}}


def lesson_topic(items=None, tid="t1", title="Los números"):
    items = items or [{
        "term": "once", "phonetic": "ˈonθe", "translation": "eleven",
        "translation_tr": "on bir", "example": "Tengo once libros.",
        "example_en": "I have eleven books.", "example_tr": "On bir kitabım var."}]
    return {"id": tid, "title": title, "type": "vocabulary", "is_assessment": False,
            "content": {"pages": [{
                "type": "vocabulary", "title": "Numbers", "title_tr": "Sayılar",
                "text": "Numbers from one to twenty.",
                "text_tr": "Birden yirmiye kadar sayılar.", "items": items}]}}


def unit(topics):
    return {"title": "Unidad 3", "topics": topics}


# ── 1. The exact Unit 3 failure ──────────────────────────────────────────────

def test_unit_three_cannot_reach_ready():
    print("\n[1] ten stored questions that print as eight")

    # The two items that a Spanish jobs unit produces naturally, and that the
    # renderer refuses while the old gate predicate allowed them.
    stems = list(GOOD_STEMS)
    poisoned = [
        mcq(1, "María trabaja en una oficina. ¿Cuál es su profesión?",
            ["Es secretaria", "Es cocinera", "Es médica", "Es profesora"],
            explanation="Her profession follows from where she works.", explanation_tr="Mesleği çalıştığı yerden çıkarılıyor."),
        mcq(2, "Pablo es muy puntual. ¿Cuándo llega a clase?",
            ["Siempre a tiempo", "Nunca", "A veces", "Tarde"]),
    ]
    pages = poisoned + [mcq(i, s, ["a", "b", "c", "d"])
                        for i, s in enumerate(stems[2:], 3)]
    topic = {"id": "a3", "title": "Ünite Değerlendirmesi", "type": "unit_assessment",
             "is_assessment": True, "content": {"pages": pages}}
    check(len(pages) == 10, "the fixture stores ten questions, as production did")

    lost = RC.unrenderable_pages(topic["content"])
    check(len(lost) >= 2, f"the render contract sees both losses ({len(lost)} report(s))")

    try:
        Q.validate_publication_integrity(units=[unit([lesson_topic(), topic])],
                                         language="Spanish", track="tr")
        check(False, "the gate REFUSES a unit that would print 8/10")
    except Q.QualityGateError as exc:
        check("10" in str(exc), f"the gate refuses it: {str(exc)[:96]}")

    clean = unit([lesson_topic(), assessment_topic()])
    try:
        result = Q.validate_publication_integrity(units=[clean], language="Spanish",
                                                  track="tr")
        check(result["unit_assessment_questions"] == 10,
              "and a genuinely complete unit still passes")
    except Q.QualityGateError as exc:
        check(False, f"a clean unit must pass: {exc}")


def test_renderer_and_gate_share_one_predicate():
    print("\n[2] the renderer and the gate cannot disagree")
    import services.pdf_renderer_v12 as R12

    samples = [
        mcq(1, "María trabaja en una oficina. ¿Cuál es su profesión?",
            ["Es secretaria", "Es cocinera", "Es médica", "Es profesora"],
            explanation="Her profession follows from her workplace.", explanation_tr="Mesleği iş yerinden çıkarılıyor."),
        mcq(2, "Pablo es puntual. ¿Cuándo llega?", ["Siempre", "Nunca", "A veces", "Tarde"]),
        mcq(3, "Pedro nació en Madrid. ¿Cuál es su nacionalidad?",
            ["Español", "Francés", "Italiano", "Alemán"],
            explanation="His nationality follows from his birthplace.", explanation_tr="Uyruğu doğum yerinden çıkarılıyor."),
        mcq(4, "¿Cómo se saluda por la mañana?", ["Buenos días", "Adiós", "Gracias", "Hola"]),
        mcq(5, "Completa: Yo _____ estudiante.", ["soy", "eres", "es", "son"]),
    ]
    # The renderer had TWO drop points, and the equivalence is owed to both: the
    # page filter that ran before the render loop (`_v57_unsafe_mcq`) and the
    # loop's own per-locale check (`_v54_pdf_unsafe_mcq` plus stem resolution).
    from services.authoring.legacy_text import _v57_unsafe_mcq

    mismatches = 0
    for is_tr in RC.EXPORT_LOCALES:
        for page in samples:
            stem = R12._mcq_prompt(page, is_tr)
            renderer_drops = (bool(_v57_unsafe_mcq(page)) or (not stem)
                              or R12._v54_pdf_unsafe_mcq(page, stem, is_tr))
            contract_drops = not RC.page_is_renderable(page, is_tr)[0]
            if renderer_drops != contract_drops:
                mismatches += 1
    check(mismatches == 0,
          f"the contract reproduces the renderer's decision exactly ({mismatches} mismatch(es))")


def test_locale_dependent_stem_loss():
    print("\n[3] a stem that exists in only one locale")
    only_tr = {"type": "mcq", "title": "Question 1", "prompt_tr": "Hangisi doğru?",
               "options": ["a", "b", "c", "d"], "answer": "a"}
    check(RC.page_is_renderable(only_tr, True)[0], "it renders in the Turkish export")
    check(not RC.page_is_renderable(only_tr, False)[0],
          "and is lost from the English export")
    lost = RC.unrenderable_pages({"pages": [only_tr]})
    check(any(row["locale"] == "en" for row in lost),
          "the contract names the locale that loses it")

    topic = {"id": "x", "title": "T", "type": "unit_assessment", "is_assessment": True,
             "content": {"pages": [only_tr] + [mcq(i, s, ["a", "b", "c", "d"])
                                               for i, s in enumerate(GOOD_STEMS[1:], 2)]}}
    try:
        Q.validate_publication_integrity(units=[unit([lesson_topic(), topic])],
                                         language="Spanish", track="tr")
        check(False, "the gate refuses a course one export would degrade")
    except Q.QualityGateError:
        check(True, "the gate refuses a course one export would degrade")


# ── 4. The IPA / Unicode contamination, exactly as published ────────────────

PUBLISHED_GREEK = {
    "once": "ˈονθε", "trece": "ˈtɾεθε", "catorce": "kaˈtoɾθε", "quince": "ˈκινθε",
    "cocinero": "κοθiˈneɾo", "cocinera": "κοθiˈneɾa", "oficina": "la ofiˈθiνα",
    "manzana": "la manˈθανα", "zumo": "el ˈθυμο", "la reserva": "la reˈseɾβα",
}


def test_greek_contamination_in_every_field():
    print("\n[4] Greek look-alikes, in every field they could hide in")
    for term, ipa in PUBLISHED_GREEK.items():
        lesson = {"pages": [{"type": "vocabulary",
                             "items": [{"term": term, "phonetic": ipa}]}]}
        check(bool(codes(lesson)), f"caught in `phonetic`: {term} [{ipa}]")

    # The field that had no script check at all before this fix.
    for field in ("term", "example", "translation_tr", "explanation_tr", "text_tr"):
        lesson = {"pages": [{"type": "vocabulary",
                             "items": [{"term": "once", field: "ˈονθε"}]}]}
        check("alien_script_token" in codes(lesson), f"caught in `{field}`")

    check(not S.alien_script_tokens("the [θ] sound is Castilian",
                                    S.profile_for_language("Spanish")),
          "inline IPA quoted in prose is not mistaken for contamination")
    for language, text in (("Russian", "Где находится дом Марты?"),
                           ("Greek", "Πού είναι το σπίτι;"),
                           ("Japanese", "マルタさんのいえはどこですか。"),
                           ("Arabic", "أين بيت مارتا؟"), ("Korean", "마르타의 집은 어디예요?")):
        check(not S.alien_script_tokens(text, S.profile_for_language(language)),
              f"{language}'s own script is not alien to it")


def test_locale_leak():
    print("\n[5] a Turkish gloss written in English")
    leak = {"pages": [{"type": "vocabulary", "items": [
        {"term": "veintinueve", "translation": "twenty-nine",
         "translation_tr": "twenty-nine", "phonetic": "bejntiˈnwebe"}]}]}
    check("locale_leak_in_gloss" in codes(leak), "an identical EN/TR pair is caught")

    only_tr = {"pages": [{"type": "vocabulary", "items": [
        {"term": "veintinueve", "translation_tr": "twenty-nine",
         "phonetic": "bejntiˈnwebe"}]}]}
    check("locale_leak_in_gloss" in codes(only_tr),
          "and so is an English number word standing alone in a Turkish gloss")

    fine = {"pages": [{"type": "vocabulary", "items": [
        {"term": "veintinueve", "translation": "twenty-nine",
         "translation_tr": "yirmi dokuz", "phonetic": "bejntiˈnwebe"},
        {"term": "la pizza", "translation": "pizza", "translation_tr": "pizza",
         "phonetic": "la ˈpiθa"}]}]}
    check(not codes(fine),
          "a correct gloss pair and a shared loanword both pass")


def test_unit_heading_is_not_duplicated():
    print("\n[6] duplicated unit headings")
    for stored, expected in (
            ("Ünite 1: İlk Kelimeler ve Selamlaşma", "İlk Kelimeler ve Selamlaşma"),
            ("Unit 2: Numbers and Time", "Numbers and Time"),
            ("Ünite 3 - Aile", "Aile"),
            ("Unidad 4: La casa", "La casa"),
            ("İlk Kelimeler", "İlk Kelimeler"),
            ("Numbers and Time", "Numbers and Time")):
        got = RC.strip_unit_prefix(stored)
        check(got == expected, f"{stored!r} -> {got!r}")


def test_unreadable_content_is_fatal():
    print("\n[7] a topic whose stored JSON cannot be read")
    broken = {"id": "b", "title": "Broken", "type": "vocabulary", "is_assessment": False,
              "content": "{not json"}
    try:
        Q.validate_publication_integrity(
            units=[unit([broken, assessment_topic()])], language="Spanish", track="tr")
        check(False, "non-object content is refused rather than audited as empty")
    except Q.QualityGateError as exc:
        check("not an object" in str(exc).lower() or "content" in str(exc).lower(),
              f"refused: {str(exc)[:80]}")

    empty = {"id": "e", "title": "Emptied", "type": "vocabulary", "is_assessment": False,
             "content": {}}
    try:
        Q.validate_publication_integrity(
            units=[unit([empty, assessment_topic()])], language="Spanish", track="tr")
        check(False, "an empty lesson does not silently pass as publishable")
    except Q.QualityGateError:
        check(True, "an empty lesson does not silently pass as publishable")


def test_semantic_blockers_reach_the_ready_decision():
    print("\n[8] a blocker in the final snapshot is binding on READY")

    # Everything structural is perfect here: ten questions, both locales
    # renderable, no duplicate stems, complete EN/TR pairs. The ONLY defect is a
    # deterministic finding of the kind the semantic reviewers are asked to
    # cure. If review findings were advisory — reported, patched optimistically,
    # and then not re-checked against the object that gets persisted — this
    # course would reach READY. It must not.
    contaminated = lesson_topic(items=[{
        "term": "once", "phonetic": "ˈονθε", "translation": "eleven",
        "translation_tr": "on bir", "example": "Tengo once libros.",
        "example_en": "I have eleven books.", "example_tr": "On bir kitabım var."}])
    try:
        Q.validate_publication_integrity(
            units=[unit([contaminated, assessment_topic()])],
            language="Spanish", track="tr")
        check(False, "a contaminated lesson cannot reach READY on structure alone")
    except Q.QualityGateError as exc:
        check("blocker" in str(exc).lower(),
              f"refused at the integrity boundary: {str(exc)[:88]}")

    # The same must hold inside the assessment, which the count checks pass
    # first and could otherwise be treated as already proven.
    stems = list(GOOD_STEMS)
    poisoned_assessment = assessment_topic()
    poisoned_assessment["content"]["pages"][4]["explanation_tr"] = "on bir = ˈονθε"
    try:
        Q.validate_publication_integrity(
            units=[unit([lesson_topic(), poisoned_assessment])],
            language="Spanish", track="tr")
        check(False, "a blocker inside an assessment is not excused by 10/10")
    except Q.QualityGateError as exc:
        check("blocker" in str(exc).lower(),
              f"the assessment is audited too: {str(exc)[:88]}")

    # And the control: with the contamination removed, the very same shapes
    # publish. A gate that refused everything would prove nothing.
    check(Q.validate_publication_integrity(
        units=[unit([lesson_topic(), assessment_topic(stems)])],
        language="Spanish", track="tr")["unit_assessment_questions"] == 10,
        "the same course without the blocker publishes 10/10")


def test_the_renderer_has_only_one_drop_point():
    print("\n[9] the renderer's page filter is part of the same contract")
    from services.authoring.legacy_text import _v57_unsafe_mcq
    from services import pdf_renderer_v12 as R

    # Items that the pre-loop page filter refused. Each one hides its trigger in
    # a field the per-locale MCQ check does not read — an `analysis_tr`, an
    # English-only explanation, a page that is MCQ-shaped without saying `mcq` —
    # which is exactly how the second drop point could disagree with the first.
    probes = [
        mcq(1, "Ali'nin arkadaşı geldi.", ["kadin", "erkek", "genc", "yasli"],
            explanation="Nothing revealing here.",
            explanation_tr="", analysis_tr="İsmi dişil olduğunu gösteriyor."),
        mcq(2, "Hans ist in Berlin geboren.", ["deutsch", "polnisch", "türkisch", "dänisch"],
            explanation="His nationality follows from his birthplace.",
            explanation_tr="Açıklama yok."),
        mcq(3, "Marta nació en Lima.", ["peruana", "chilena", "boliviana", "cubana"],
            explanation="", explanation_tr="",
            analysis_en="Her nationality comes from where she was born."),
        # MCQ-shaped, but typed as something else: the page filter judged it by
        # shape, so the contract has to as well.
        {"type": "exercise", "prompt": "Pierre travaille à l'hôpital.",
         "options": ["médecin", "boulanger", "avocat", "pilote"],
         "explanation": "His profession follows from where he works."},
    ]
    for page in probes:
        legacy = bool(_v57_unsafe_mcq(page))
        contract = [RC.page_is_renderable(page, is_tr)[0] for is_tr in RC.EXPORT_LOCALES]
        check(legacy, f"the legacy page filter refused it: {str(page.get('prompt'))[:44]}")
        check(not any(contract),
              f"and so does the contract, in both locales: "
              f"{RC.page_is_renderable(page, True)[1][:52]}")

    # A capitalised COMMON NOUN plus a grammatical-gender rationale is not
    # personal-name inference. Sentence-initial capitalisation alone must never
    # turn ordinary grammar explanation into a hidden-world identity claim.
    grammar_page = mcq(
        20,
        "Casa es ___.",
        ["grande", "pequeña", "nueva", "vieja"],
        answer="grande",
        explanation="Casa is feminine; the keyed answer is «grande».",
        explanation_tr="Casa dişil bir isimdir; doğru cevap «grande».",
    )
    check(all(RC.page_is_renderable(grammar_page, is_tr)[0]
              for is_tr in RC.EXPORT_LOCALES),
          "capitalised common noun + grammar rationale is not treated as a person")

    # But an actual rationale that explicitly claims a PERSONAL NAME supplies
    # gender remains blocked. This proves the fix narrows the predicate rather
    # than disabling it.
    unsafe_name = mcq(
        21,
        "Ana es ___.",
        ["alta", "alto", "altos", "altas"],
        answer="alta",
        explanation="Ana is a feminine name, so «alta».",
        explanation_tr="Ana kadın ismidir; bu yüzden «alta».",
    )
    check(not any(RC.page_is_renderable(unsafe_name, is_tr)[0]
                  for is_tr in RC.EXPORT_LOCALES),
          "explicit personal-name gender inference is still refused")

    # The filter itself is gone: `_normalize_pages` must now hand every stored
    # page to the render loop, which is the only place a drop may be decided.
    content = {"pages": [dict(probes[0]), mcq(9, "¿Cómo estás?", ["bien", "mal", "asi", "ya"])]}
    kept = R._normalize_pages(content)
    check(len(kept) == 2,
          f"`_normalize_pages` no longer removes pages on its own ({len(kept)}/2 kept)")

    # And the control: ordinary questions survive the widened predicate.
    for page in [mcq(i, s, ["opción a", "opción b", "opción c", "opción d"])
                 for i, s in enumerate(GOOD_STEMS, 1)]:
        check(all(RC.page_is_renderable(page, is_tr)[0] for is_tr in RC.EXPORT_LOCALES),
              f"a normal question still renders: {page['prompt'][:38]}")


def main():
    test_unit_three_cannot_reach_ready()
    test_renderer_and_gate_share_one_predicate()
    test_locale_dependent_stem_loss()
    test_greek_contamination_in_every_field()
    test_locale_leak()
    test_unit_heading_is_not_duplicated()
    test_unreadable_content_is_fatal()
    test_semantic_blockers_reach_the_ready_decision()
    test_the_renderer_has_only_one_drop_point()
    print(f"\n=== {len(FAILS)} failing checks ===")
    for f in FAILS:
        print("  -", f)
    if FAILS:
        sys.exit(1)
    print("publication divergence: READY and the exported PDF cannot disagree")


if __name__ == "__main__":
    main()
