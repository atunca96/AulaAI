#!/usr/bin/env python3
"""Adversarial matrix for the hidden-world blockers in render_contract.

These blockers refuse an item because the learner cannot reach the keyed answer
from what is in front of them. That is a claim about the ANSWER, so each one
owes two things and not one:

    1. the risky inference is present, AND
    2. that inference could change WHICH OPTION IS CORRECT.

(2) is what the name/gender rule was missing. In production it refused
"The House and Locations / Prepositions of Place / pages[3]" — a preposition
item whose subject happened to be called Ana and whose rationale explained the
gender of a completely different noun. Nothing checked that the person, the
gender claim and the answer had anything to do with each other.

Every case below is a positive or negative control for one blocker. Nothing in
the implementation branches on a language or a CEFR level, so the fixtures
deliberately span several of both: the assertions are about the option set, the
fields, and what the rationale attributes its claim to.
"""

from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import render_contract as RC  # noqa: E402
from services.authoring.legacy_text import _v57_unsafe_mcq  # noqa: E402

FAILURES = []


def verdict(page):
    """Exactly what the gate and the renderer both ask, for both exports."""
    hidden = RC.hidden_world_reason(page)
    if hidden:
        return hidden
    for is_tr in RC.EXPORT_LOCALES:
        ok, why = RC.page_is_renderable(page, is_tr)
        if not ok:
            return why
    return ""


def case(must_refuse, label, page, expect=None):
    reason = verdict(page)
    refused = bool(reason)
    ok = refused == must_refuse and (not expect or reason == expect)
    print(("  PASS  " if ok else "  FAIL  ")
          + ("REFUSE " if refused else "admit  ") + label)
    if not ok:
        FAILURES.append(f"{label} -> {reason or 'admitted'}")


def mcq(**kw):
    page = {"type": "mcq", "title": "Q", "answer": "alta",
            "options": ["alta", "alto", "altos", "altas"],
            "distractors": ["alto", "altos", "altas"],
            "explanation": "", "explanation_tr": ""}
    page.update(kw)
    return page


NG = RC.NAME_GENDER_REASON
BIO = "answer depends on an identity fact inferred from a biographical one"

print("\n=== name/gender: positive controls (must refuse) ===")
case(True, "the rationale says the personal name is feminine",
     mcq(prompt="Ana es ___. (alto)",
         explanation="Ana is a feminine name, so «alta».",
         explanation_tr="Ana kadın ismidir; bu yüzden «alta»."), NG)
case(True, "same claim, Turkish, agglutinated (`ismidir`, not `ismi`)",
     mcq(prompt="Ayşe nasıl biri? ___",
         explanation="The stated noun is feminine.",
         explanation_tr="Ayşe kadın ismidir, bu yüzden sıfat dişil olur."), NG)
case(True, "'the name is feminine' without repeating the name",
     mcq(prompt="Ana es ___. (alto)",
         explanation="The name is feminine, so «alta».",
         explanation_tr="Belirtilen sözcük dişildir."), NG)
case(True, "options ARE the genders, rationale reads them off the name",
     mcq(prompt="Ali'nin arkadaşı geldi.", answer="kadın",
         options=["kadın", "erkek", "genç", "yaşlı"],
         distractors=["erkek", "genç", "yaşlı"],
         explanation="Nothing revealing here.", explanation_tr="",
         analysis_tr="İsmi dişil olduğunu gösteriyor."), NG)
case(True, "suppletive options, the claim names the keyed answer",
     mcq(prompt="Ana es una ___.", answer="mujer",
         options=["mujer", "hombre", "perro", "gato"],
         distractors=["hombre", "perro", "gato"],
         explanation="Ana is a woman's name, so the answer is mujer.",
         explanation_tr="Ana kadın ismidir; cevap mujer."), NG)

print("\n=== name/gender: negative controls (must admit) ===")
case(False, "PRODUCTION CASE: name in stem, answer is a preposition, "
            "gender claim is about another noun",
     mcq(prompt="Ana está ___ la mesa.", answer="debajo de",
         options=["debajo de", "encima de", "al lado de", "detrás de"],
         distractors=["encima de", "al lado de", "detrás de"],
         explanation="«mesa» is a feminine noun, so it takes «la».",
         explanation_tr="«mesa» dişil bir isim olduğu için «la» alır."))
case(False, "name in stem, paradigm options, gender claim about another noun",
     mcq(prompt="Ana lee el libro. ¿Qué artículo?", answer="el",
         options=["el", "la", "los", "las"], distractors=["la", "los", "las"],
         explanation="«libro» is a masculine noun, so «el».",
         explanation_tr="«libro» eril bir isimdir; «el» kullanılır."))
case(False, "capitalized place name, not a person",
     mcq(prompt="Madrid es ___. (grande)", answer="grande",
         options=["grande", "grandes", "gran", "grandote"],
         distractors=["grandes", "gran", "grandote"],
         explanation="«ciudad» is a feminine noun but «grande» is invariable.",
         explanation_tr="«ciudad» dişil bir isimdir ama «grande» değişmez."))
case(False, "sentence-initial capitalized common noun (Russian B1)",
     mcq(prompt="Книга большая. Какая форма?", answer="большая",
         options=["большая", "большой", "большие", "большое"],
         distractors=["большой", "большие", "большое"],
         explanation="«книга» is a feminine noun, so the adjective agrees.",
         explanation_tr="«книга» dişil bir isim olduğu için sıfat uyum sağlar."))
case(False, "quoted taught vocabulary only, no person anywhere",
     mcq(prompt="¿Qué forma corresponde? ___",
         explanation="«mujer» is feminine, so «alta».",
         explanation_tr="«mujer» dişil bir isimdir; «alta»."))
case(False, "sentence-initial capitalized TARGET word",
     mcq(prompt="Alta es la forma ___.", answer="femenina",
         options=["femenina", "femenino", "femeninos", "femeninas"],
         distractors=["femenino", "femeninos", "femeninas"],
         explanation="The feminine form is «alta».",
         explanation_tr="Dişil biçim «alta» dır."))
case(False, "name present but no gender vocabulary at all",
     mcq(prompt="Ana compra pan. ¿Qué compra?", answer="pan",
         options=["pan", "leche", "queso", "agua"],
         distractors=["leche", "queso", "agua"],
         explanation="The stem states she buys bread.",
         explanation_tr="Soruda ekmek aldığı belirtiliyor."))
case(False, "explicit gender evidence the track language states (German A2)",
     mcq(prompt="Anna ist ___. (groß) — the woman", answer="groß",
         options=["groß", "großer", "große", "großes"],
         distractors=["großer", "große", "großes"],
         explanation="Anna is a feminine name, so the ending changes.",
         explanation_tr="Anna kadın ismidir; ek değişir."))
case(False, "explicit taught-language evidence, rationale cites it not the name",
     mcq(prompt="Ana es una mujer. Ella es ___. (alto)",
         explanation="The stem states «mujer», which is feminine, so «alta».",
         explanation_tr="Soruda «mujer» belirtiliyor; dişil olduğu için «alta»."))

print("\n=== biography -> identity ===")
case(True, "nationality asked from a stated birthplace",
     mcq(prompt="Ana nació en España. ¿Cuál es su nacionalidad?", answer="española",
         options=["española", "mexicana", "francesa", "italiana"],
         distractors=["mexicana", "francesa", "italiana"],
         explanation="Her nationality follows from her birthplace.",
         explanation_tr="Milliyeti doğum yerinden çıkar."), BIO)
case(True, "still refused when the stem quotes only what it asks FOR",
     mcq(prompt="Ana nació en España. ¿Cuál es su «nacionalidad»?", answer="española",
         options=["española", "mexicana", "francesa", "italiana"],
         distractors=["mexicana", "francesa", "italiana"],
         explanation="Her nationality follows from her birthplace.",
         explanation_tr="Milliyeti doğum yerinden çıkar."), BIO)
case(False, "gloss item that quotes the very word it asks about",
     mcq(prompt="Ella trabaja en un hospital. ¿Qué significa «hospital»?",
         answer="hastane", options=["hastane", "okul", "market", "banka"],
         distractors=["okul", "market", "banka"],
         explanation="«hospital» means hastane; it is a building, not a job.",
         explanation_tr="«hospital» hastane demektir; bir meslek değil, bir binadır."))
case(False, "conjugation drill whose stem merely contains a biography verb",
     mcq(prompt="Ella ___ en Madrid. (vivir)", answer="vive",
         options=["vive", "vives", "vivimos", "viven"],
         distractors=["vives", "vivimos", "viven"],
         explanation="Third person singular takes -e.",
         explanation_tr="Üçüncü tekil şahıs -e alır."))

print("\n=== workplace -> profession, trait -> frequency ===")
wp = mcq(prompt="Ana works at a hospital. ¿Cuál es su profesión?", answer="enfermera",
         options=["enfermera", "profesora", "abogada", "cocinera"],
         distractors=["profesora", "abogada", "cocinera"],
         explanation="x", explanation_tr="y")
case(True, "profession asked from a stated workplace", wp,
     "profession asked from a workplace fact")
tf = mcq(prompt="Ana es muy puntual. ¿Cómo llega?", answer="siempre a tiempo",
         options=["siempre a tiempo", "nunca", "a veces", "raramente"],
         distractors=["nunca", "a veces", "raramente"],
         explanation="x", explanation_tr="y")
case(True, "character trait answered by an absolute-frequency option", tf,
     "character trait answered by an absolute-frequency option")
case(False, "a workplace is stated but the question is a translation",
     mcq(prompt="Ana works at a hospital. ¿Qué significa «hospital»?",
         answer="hastane", options=["hastane", "okul", "market", "banka"],
         distractors=["okul", "market", "banka"],
         explanation="A gloss question.", explanation_tr="Çeviri sorusu."))
case(False, "punctual is stated but no option is an absolute frequency",
     mcq(prompt="Ana es muy puntual. ¿Qué es?", answer="puntual",
         options=["puntual", "puntuales", "impuntual", "tardía"],
         distractors=["puntuales", "impuntual", "tardía"],
         explanation="The stem states it.", explanation_tr="Soruda belirtiliyor."))

print("\n=== the dependency helpers, directly ===")
case_checks = [
    (True, "alta/alto/altos/altas is a form paradigm",
     RC.answer_turns_on_form(mcq())),
    (False, "four prepositions are not",
     RC.answer_turns_on_form(mcq(options=["debajo de", "encima de",
                                          "al lado de", "detrás de"]))),
    (False, "four nationalities are not",
     RC.answer_turns_on_form(mcq(options=["española", "mexicana",
                                          "francesa", "italiana"]))),
    (True, "a gloss question quotes a word its own stem also uses",
     RC.question_is_about_a_quoted_word(
         "Ella trabaja en un hospital. ¿Qué significa «hospital»?")),
    (False, "quoting only what is being asked for is not a gloss question",
     RC.question_is_about_a_quoted_word("¿Cuál es su «nacionalidad»?")),
]
for expected, label, got in case_checks:
    ok = bool(got) == expected
    print(("  PASS  " if ok else "  FAIL  ") + label)
    if not ok:
        FAILURES.append(label)

print("\n=== the renderer and the gate still share one predicate ===")
# Anything the historical page filter refused must still be refused by the one
# predicate the render loop and the gate both call.
for page in (
    mcq(prompt="Hans ist in Berlin geboren.", answer="deutsch",
        options=["deutsch", "polnisch", "türkisch", "dänisch"],
        distractors=["polnisch", "türkisch", "dänisch"],
        explanation="His nationality follows from his birthplace.",
        explanation_tr="Açıklama yok."),
    mcq(prompt="Ali'nin arkadaşı geldi.", answer="kadın",
        options=["kadın", "erkek", "genç", "yaşlı"],
        distractors=["erkek", "genç", "yaşlı"],
        explanation="", explanation_tr="",
        analysis_tr="İsmi dişil olduğunu gösteriyor."),
):
    legacy = bool(_v57_unsafe_mcq(page))
    contract = bool(verdict(page))
    ok = (not legacy) or contract
    print(("  PASS  " if ok else "  FAIL  ")
          + f"legacy={legacy} contract={contract}: {str(page['prompt'])[:44]}")
    if not ok:
        FAILURES.append(f"contract admits what the legacy filter refused: {page['prompt']}")

print(f"\n=== {len(FAILURES)} failing controls ===")
for row in FAILURES:
    print("  -", row)
if FAILURES:
    sys.exit(1)
print("[HIDDEN-WORLD] every blocker requires a risky inference that could "
      "actually change which option is correct")
