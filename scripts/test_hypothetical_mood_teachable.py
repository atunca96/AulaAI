#!/usr/bin/env python3
"""A lesson must be able to teach the mood whose name is "hypothetical".

`invented_form_taught` exists because a published Spanish lesson printed `gueso`
in a table of real words and labelled it "(varsayımsal: sert-g peynir)". An A1
learner cannot tell which rows of a vocabulary table are real, so a lesson that
invents a form to demonstrate a rule has chosen the wrong rule.

The marker list that enforced it held two different kinds of thing. "not a real
word", "invented", "does not exist" are CLAIMS that a form is not real, and they
are evidence wherever they appear. "varsayımsal", "hypothetical", "hipotetik",
"hipotético" are the NAME OF A GRAMMATICAL CATEGORY, and most of the taught
languages require a lesson to teach it by that name: Konjunktiv II, subjuntivo,
subjonctif, congiuntivo, υποθετικός, dilek-şart.

So a B1 German unit titled "Polite Requests and Hypotheticals: Konjunktiv II"
was refused publication for writing the only sentence that explains its own
subject. What separates the two cases is not a longer word list but where the
word sits: a gloss labels a term the lesson is teaching, instruction prose
explains a rule. Both directions are pinned here.
"""

from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import audit as A  # noqa: E402
from services.authoring import schema as S  # noqa: E402

FAILURES = []


def check(condition, label):
    if not condition:
        FAILURES.append(label)
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")


print("[1] the original defect is still refused — a gloss calling a term imagined")
# This is the exact published label, and it was caught by the category word
# alone. Losing it would be a regression of the rule's reason to exist.
for label, text in (
    ("the published Spanish gloss", "(varsayımsal: sert-g peynir)"),
    ("its English equivalent", "hypothetical: hard-g cheese"),
):
    check(bool(A.hypothetical_markers(text, S.GLOSS)),
          f"refused in a gloss: {label}")

print("\n[1b] including the published one, which lived in instruction prose")
# The lesson that created this rule put its label in `analysis_tr`, an
# INSTRUCTION field, not a gloss. What makes it a defect is the second half:
# it states the construction does not exist. That claim is the marker.
published = "(varsayımsal: sert-g peynir) — standart İspanyolcada bu yapı yoktur."
check(bool(A.hypothetical_markers(published, S.INSTRUCTION)),
      "refused in instruction prose: the published gueso analysis")

print("\n[1c] but bare 'there isn't' is ordinary Turkish, not a claim about a form")
for text in (
    "Bu derste zamir yoktur, sadece isimler vardır.",
    "Almancada bu sesin karşılığı yoktur.",
    "Odada kimse yoktur.",
):
    check(not A.hypothetical_markers(text, S.INSTRUCTION),
          f"not refused: {text[:44]}")

print("\n[2] and a non-existence claim is refused wherever it appears")
for role_label, role in (("gloss", S.GLOSS), ("instruction", S.INSTRUCTION)):
    for text in (
        "The word 'blorf' is invented and does not exist in German.",
        "«glumpf» uydurma bir örnektir.",
        "This is a made-up form, not a real word.",
        "'xyzzy' is a non-word used only here.",
        "«flurbo» no es una palabra real.",
        "'zork' is fictitious.",
    ):
        check(bool(A.hypothetical_markers(text, role)),
              f"refused in {role_label}: {text[:44]}")

print("\n[3] the mood may be taught by its name in instruction prose")
# One sentence per taught language that names the category. None of these says
# any form is unreal; each is the lesson describing its own subject.
for label, text in (
    ("German B1 — the unit that was refused",
     "Konjunktiv II expresses a hypothetical situation or a polite request."),
    ("its Turkish counterpart",
     "Konjunktiv II varsayımsal bir durumu ya da kibar bir ricayı ifade eder."),
    ("Turkish, the other common term",
     "Bu yapı hipotetik koşullarda kullanılır."),
    ("Spanish subjunctive",
     "El subjuntivo expresa una situación hipotética."),
    ("French subjunctive",
     "Le subjonctif exprime une situation hypothétique."),
    ("English, contrasting with fact",
     "Use this form for hypothetical conditions, not for facts."),
):
    check(not A.hypothetical_markers(text, S.INSTRUCTION),
          f"teachable: {label}")

print("\n[4] a lesson that teaches the mood reaches publication")
lesson = {
    "pages": [{
        "type": "grammar",
        "title": "Polite Requests and Hypotheticals",
        "title_tr": "Kibar Ricalar ve Varsayımlar",
        "text": "Konjunktiv II expresses a hypothetical situation or a polite request.",
        "text_tr": "Konjunktiv II varsayımsal bir durumu ya da kibar bir ricayı ifade eder.",
        "rules": [{
            "rule": "Use hätte and wäre for hypothetical statements about the present.",
            "rule_tr": "Şimdiki zamana dair varsayımsal ifadelerde hätte ve wäre kullanılır.",
            "explanation": "The form signals a hypothetical rather than a fact.",
            "explanation_tr": "Bu biçim bir olguyu değil, varsayımsal bir durumu gösterir.",
            "example": "Ich hätte gern einen Kaffee.",
            "example_en": "I would like a coffee.",
            "example_tr": "Bir kahve istiyorum.",
        }],
    }],
}
codes = {f.code for f in A.audit_lesson(lesson, language="German", track="tr")}
check("invented_form_taught" not in codes,
      f"the Konjunktiv II lesson carries no invented-form blocker ({sorted(codes)})")

print("\n[5] and a lesson that really does teach an invented form does not")
bad = {
    "pages": [{
        "type": "vocabulary",
        "title": "Sounds", "title_tr": "Sesler",
        "text": "Some spellings are rare.", "text_tr": "Bazı yazımlar nadirdir.",
        "items": [{
            "term": "gueso", "phonetic": "[ˈɡeso]",
            "translation": "hypothetical: hard-g cheese",
            "translation_tr": "varsayımsal: sert-g peynir",
            "example": "No existe.", "example_en": "It does not exist.",
            "example_tr": "Mevcut değil.",
        }],
    }],
}
bad_codes = {f.code for f in A.audit_lesson(bad, language="Spanish", track="tr")}
check("invented_form_taught" in bad_codes,
      f"the invented-form lesson is still refused ({sorted(bad_codes)})")

print()
if FAILURES:
    print(f"FAILED ({len(FAILURES)}):")
    for label in FAILURES:
        print(f"  - {label}")
    sys.exit(1)
print("all hypothetical-mood teachability checks passed")
