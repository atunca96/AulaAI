#!/usr/bin/env python3
"""The diagnostic decomposition must agree with the predicate it explains.

`pages[4]` of "Relative Clauses with Nominative, Accusative, and Dative"
survived `render_name_gender`, `render_stem` and `render_rescue` in production
while every fixture here stayed green. A reason string cannot explain that: it
is one bit of output from a predicate with six inputs and two independent
firing routes, and no log carried the inputs.

`RC.explain_hidden_world` carries them. It is only worth trusting if it is
(a) pure — consulting it never changes a verdict — and (b) faithful — its
per-statement trace fires exactly when `_name_gender_rationale` does. Both are
asserted below, because a diagnostic that disagrees with the predicate sends
the next investigation to the wrong layer.

The third block is the reason this file exists. It pins the 2x2 of
`decisive` x `name-word present`, and records that the shipped fixtures cover
only one column: a Turkish rationale saying "dişil bir isim" (ordinary
grammatical prose — `isim` is Turkish for NOUN) is refused, while the same
sentence with the agglutinated `isimdir` is not, because `\\bisim\\b` cannot
match through the suffix. That one character class is the whole difference
between the green fixture and the red production page.
"""

from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import render_contract as RC  # noqa: E402

FAILURES = []


def check(condition, label):
    if not condition:
        FAILURES.append(label)
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")


def mcq(stem, options, answer, **fields):
    page = {"type": "mcq", "title": "Question 1", "prompt": stem,
            "options": list(options), "answer": answer}
    page.update(fields)
    return page


PARADIGM = ["alta", "alto", "altos", "altas"]        # forms of one word
DISTINCT = ["grande", "pequeña", "nueva", "vieja"]   # four different words
ARTICLES = ["die", "der", "dem", "den"]              # three letters, no paradigm

print("explain_hidden_world is faithful to the predicate")
CORPUS = [
    mcq("Das ist die Wohnung, ___ wir gemietet haben.", ARTICLES, "die",
        explanation_tr="«Wohnung» dişil bir isim olduğu için «die» kullanılır.",
        explanation_en="«Wohnung» is feminine, so the relative pronoun is «die»."),
    mcq("Ana es ___.", PARADIGM, "alta",
        explanation="Ana is a feminine name, so «alta».",
        explanation_tr="Ana kadın ismidir; bu yüzden «alta»."),
    mcq("Casa es ___.", DISTINCT, "grande",
        explanation="Casa is feminine; the keyed answer is «grande».",
        explanation_tr="Casa dişil bir isimdir; doğru cevap «grande»."),
    mcq("La ___ es alta.", DISTINCT, "grande",
        analysis_tr="«mesa» dişil bir isim."),
    mcq("Это ___ квартира.", ARTICLES, "die"),
]
for index, page in enumerate(CORPUS):
    report = RC.explain_hidden_world(page)
    check(all(field["trace_agrees"] for field in report["rationale_fields"]),
          f"case {index}: per-statement trace matches _name_gender_rationale")
    check(report["hidden_world_reason"] == RC.hidden_world_reason(page),
          f"case {index}: reported reason is the live reason")
    for is_tr, key in ((True, "page_is_renderable_tr"),
                       (False, "page_is_renderable_en")):
        ok, why = RC.page_is_renderable(page, is_tr)
        check(report[key] == [ok, why],
              f"case {index}: reported {key} is the live verdict")
    fired = bool(report["firing_statements"])
    check(fired == (report["hidden_world_reason"] == RC.NAME_GENDER_REASON),
          f"case {index}: a refusal is always attributed to a statement")

print()
print("explain_hidden_world is pure")
for index, page in enumerate(CORPUS):
    before = dict(page)
    RC.explain_hidden_world(page)
    check(page == before, f"case {index}: the page is not mutated")

print()
print("production false positives are gone without disabling real name inference")

# Exact production shape 1: a capitalised common noun is quoted as linguistic
# material, while the option set is form-like. The noun must not become a person.
prod_relative = mcq(
    "Welches Relativpronomen passt in die Lücke?\n"
    "„Der Mietvertrag, _____ ich gestern unterschrieben habe, liegt auf dem Tisch.“",
    ["den", "der", "dem", "denen"], "den",
    explanation="'Der Mietvertrag' is masculine singular. In the relative clause, "
                "'ich' is the subject and the pronoun is the direct object.",
    explanation_tr="'Der Mietvertrag' eril ve tekildir. İlgi cümlesinde 'ich' özne, "
                   "zamir ise doğrudan nesnedir.",
)
check(all(RC.page_is_renderable(prod_relative, is_tr)[0]
          for is_tr in RC.EXPORT_LOCALES),
      "quoted capitalised common noun does not become a person in a decisive option set")

# Exact production shape 2: Turkish 'isim' is ordinary grammatical metalanguage
# meaning noun/name. With no candidate-person token in that statement it must not
# create a personal-name inference by itself.
prod_time = mcq(
    "Der Zug zum Hauptbahnhof fährt pünktlich ______ ab.",
    ["in einer halben Stunde", "in eine halbe Stunde",
     "in einer halbe Stunde", "in eines halben Stunde"],
    "in einer halben Stunde",
    explanation="The temporal preposition 'in' requires the dative case. "
                "The feminine noun 'Stunde' takes 'einer halben Stunde'.",
    explanation_tr="Zaman bildiren 'in' edatı Dativ ister. Dişil isim olan "
                   "'Stunde' 'einer halben Stunde' biçimini alır.",
)
check(all(RC.page_is_renderable(prod_time, is_tr)[0]
          for is_tr in RC.EXPORT_LOCALES),
      "bare grammatical 'isim' without a person token does not trigger name inference")

# Real unsafe case: unquoted personal-name candidate + decisive gendered form set.
unsafe_unquoted = mcq(
    "Ana es ___.", PARADIGM, "alta",
    explanation="Ana is feminine, so «alta».",
    explanation_tr="Ana dişildir; bu yüzden «alta».",
)
check(not any(RC.page_is_renderable(unsafe_unquoted, is_tr)[0]
              for is_tr in RC.EXPORT_LOCALES),
      "unquoted person candidate plus decisive gendered forms is still refused")

# Real unsafe case even when the name itself is quoted: explicit NAME wording
# keeps the protection active.
unsafe_quoted = mcq(
    "Ana es ___.", PARADIGM, "alta",
    explanation="'Ana' is a feminine name, so «alta».",
    explanation_tr="'Ana' kadın adıdır; bu yüzden «alta».",
)
check(not any(RC.page_is_renderable(unsafe_quoted, is_tr)[0]
              for is_tr in RC.EXPORT_LOCALES),
      "quoted token explicitly identified as a personal name is still refused")

# The diagnostic must agree with each of the new boundary cases.
for label, page in [
    ("prod_relative", prod_relative),
    ("prod_time", prod_time),
    ("unsafe_unquoted", unsafe_unquoted),
    ("unsafe_quoted", unsafe_quoted),
]:
    report = RC.explain_hidden_world(page)
    check(all(field["trace_agrees"] for field in report["rationale_fields"]),
          f"{label}: diagnostic trace remains faithful")

print()
print("the two layers can disagree, and the diagnostic reports both")
# `unsafe_reason` reads `_GENDER_WORDS`, which has no `feminine|masculine`, and
# derives `explicit_gender` without the gender-noun list. `hidden_world_reason`
# reads `_V57_GENDER_WORDS`, which has both. Same page, two answers.
german = CORPUS[0]
report = RC.explain_hidden_world(german)
check(report["unsafe_reason_tr"] != report["unsafe_reason_en"],
      "one page, two locale verdicts from unsafe_reason")
check("explicit_gender_v57" in report
      and "explicit_gender_unsafe_reason" in report,
      "both layers' explicit_gender escapes are reported separately")

print()
if FAILURES:
    print(f"FAILED ({len(FAILURES)}):")
    for label in FAILURES:
        print(f"  - {label}")
    sys.exit(1)
print("all hidden-world diagnostic checks passed")
