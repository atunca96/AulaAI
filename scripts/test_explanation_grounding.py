#!/usr/bin/env python3
"""Regression: an MCQ rationale must justify the answer from what the learner sees.

The PDF answer key prints each stored explanation verbatim, so a rationale that
invents evidence teaches that evidence. The published course carried:

    Q8   stem: "Una mujer…"   key: "Sara bir kadın olduğu için…"
    Q21  stem names nobody    key: "Lucía…"
    Q24  stem: "Mateo es un ___ conocido"   key: "Mateo erildir"

Q24 is already the renderer's name/gender relation. Q8 and Q21 are the new
half: a proper noun the question never shows. The lexicon-free test is
cross-locale agreement — a name is spelled the same in both rationales, an
ordinary word is not — and the repair runs through the existing atomic page
strategy, which holds answer/options/distractors immutable.

Nothing here branches on a language or a CEFR band; the fixtures span several
of both and every assertion is about fields and tokens.
"""

from __future__ import annotations
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")

from services.authoring import audit as A  # noqa: E402
from services.authoring import quality_gate as Q  # noqa: E402
from services.authoring import render_contract as RC  # noqa: E402

ORIG_CALL = Q._call_review
FAILURES = []


def check(condition, label):
    print(("  PASS  " if condition else "  FAIL  ") + label)
    if not condition:
        FAILURES.append(label)


def mcq(**kw):
    page = {"type": "mcq", "title": "Question", "title_tr": "Soru",
            "prompt": "Una mujer de España es ___.", "answer": "española",
            "options": ["española", "español", "españoles", "españolas"],
            "distractors": ["español", "españoles", "españolas"],
            "why": "Agreement.", "why_tr": "Uyum."}
    page.update(kw)
    return page


def topic_of(page, title="Nationalities"):
    return {"id": "t1", "title": title, "is_assessment": False,
            "content": {"pages": [
                {"type": "text", "text": "Nationalities agree.",
                 "text_tr": "Milliyetler uyum sağlar."},
                page,
            ]}}


print("\n[1] a rationale that introduces a person the question never shows")
for label, page in (
    ("Q8: stem says «Una mujer», key says Sara",
     mcq(explanation="Sara is a woman, so the feminine form is used.",
         explanation_tr="Sara bir kadın olduğu için dişil biçim kullanılır.")),
    ("Q21: stem names nobody, key invents Lucía",
     mcq(prompt="¿Cuál es la nacionalidad femenina de una persona de España?",
         explanation="Lucía is from Spain, so she is española.",
         explanation_tr="Lucía İspanya'dan olduğu için española'dır.")),
    ("a German B1 item inventing a person",
     mcq(prompt="Eine Frau aus Spanien ist ___.", answer="Spanierin",
         options=["Spanierin", "Spanier", "Spanierinnen", "spanisch"],
         distractors=["Spanier", "Spanierinnen", "spanisch"],
         explanation="Katrin is a woman, so the feminine form applies.",
         explanation_tr="Katrin bir kadın olduğu için dişil biçim geçerlidir.")),
):
    check(Q._ungrounded_explanation_names(page), f"flagged: {label}")


print("\n[2] grounded rationales are a no-op")
for label, page in (
    ("cites the stem's own words",
     mcq(explanation="The stem states «una mujer», so the feminine form is used.",
         explanation_tr="Soruda «una mujer» geçtiği için dişil biçim kullanılır.")),
    ("names a person the stem itself shows",
     mcq(prompt="Sara es de España. Ella es ___.",
         explanation="The stem says Sara is from Spain.",
         explanation_tr="Soruda Sara'nın İspanya'dan olduğu belirtiliyor.")),
    ("ordinary capitalised sentence openers in both locales",
     mcq(explanation="The feminine form agrees with the stated noun.",
         explanation_tr="Dişil biçim, belirtilen sözcükle uyum sağlar.")),
    ("a place the stem shows",
     mcq(explanation="España is feminine here, so «española».",
         explanation_tr="España burada dişildir; «española».")),
    ("only one rationale exists, so it cannot be judged this way",
     mcq(explanation="Sara is a woman, so the feminine form is used.",
         explanation_tr="")),
    ("a quoted vocabulary item, not a person",
     mcq(explanation="«Mujer» is feminine, so «española».",
         explanation_tr="«Mujer» dişildir; «española».")),
):
    check(not Q._ungrounded_explanation_names(page), f"clean: {label}")


print("\n[3] it is a repairable blocker on the existing strategy")
topic = topic_of(mcq(explanation="Sara is a woman, so the feminine form is used.",
                     explanation_tr="Sara bir kadın olduğu için dişil biçim kullanılır."))
rows = [r for r in Q._detect_topic_blockers(topic, language="Spanish", track="tr",
                                            canonical="Spanish")
        if r["kind"] == "render"]
check(len(rows) == 1
      and rows[0]["reason"] == Q._EXPLANATION_GROUNDING_REASON
      and rows[0]["where"] == "pages[1]",
      f"detected as a page-scoped blocker ({[r['reason'] for r in rows]})")
check(rows[0]["strategies"] == ["render_name_gender"],
      f"routed to the rationale-editing strategy ({rows[0]['strategies']})")
# The renderer itself is unchanged: this page is still admitted for export.
check(all(RC.page_is_renderable(topic["content"]["pages"][1], t)[0]
          for t in RC.EXPORT_LOCALES),
      "renderer admission is untouched by the new blocker")


print("\n[4] the repair grounds the rationale and leaves the answer set alone")
before = copy.deepcopy(topic["content"]["pages"][1])
calls = []


def provider(**kwargs):
    calls.append(kwargs["stage"])
    payload = kwargs["payload"]
    assert payload["immutable_page_context"]["answer"] == "española"
    return {
        "stem": before["prompt"],
        "explanation_en": "The stem states «una mujer», so the feminine form is used.",
        "explanation_tr": "Soruda «una mujer» geçtiği için dişil biçim kullanılır.",
        "reason": "Cite the stem instead of a person it does not show.",
    }


try:
    Q._call_review = provider
    applied = Q.converge_topic(topic=topic, language="Spanish", level="A1",
                              track="tr", budget=Q.ReviewBudget(0.22),
                              unit_title="Unit 1")
finally:
    Q._call_review = ORIG_CALL

page = topic["content"]["pages"][1]
check(len(calls) == 1 and calls[0].startswith("review_render_name_gender:"),
      f"one bounded call through the existing strategy ({calls})")
check(applied == 1, f"the repair is counted ({applied})")
for key in ("answer", "options", "distractors"):
    check(page[key] == before[key], f"{key} unchanged")
check(page["prompt"] == before["prompt"], "the stem is unchanged too")
check("Sara" not in page["explanation"] and "Sara" not in page["explanation_tr"],
      "the invented person is gone from both rationales")
check(Q._ungrounded_explanation_names(page) == []
      and Q._topic_render_blockers(topic["content"]) == []
      and not A.blocking(Q._audit_topic(topic, language="Spanish", track="tr"))
      and Q.missing_bilingual_pairs(topic["content"]) == [],
      "grounding, renderer, audit and bilingual are all clean afterwards")


print("\n[5] a rationale inferring gender from a name the stem shows is repaired "
      "to cite the grammatical evidence")
# Q24's shape: the stem carries an explicit masculine article, and the rationale
# reasons from the person's name instead. That is the renderer's existing
# name/gender relation, and the repair must reach the stated evidence.
q24 = topic_of(mcq(prompt="Mateo es un ___ conocido.", answer="escritor",
                   options=["escritor", "escritora", "escritores", "escritoras"],
                   distractors=["escritora", "escritores", "escritoras"],
                   explanation="Mateo is masculine, so «escritor».",
                   explanation_tr="Mateo erildir; bu yüzden «escritor»."),
               title="Professions")
q24_before = copy.deepcopy(q24["content"]["pages"][1])
check(RC.hidden_world_reason(q24_before) == RC.NAME_GENDER_REASON,
      "the existing name/gender relation already owns this one")
q24_calls = []


def q24_provider(**kwargs):
    q24_calls.append(kwargs["stage"])
    return {
        "stem": "Es un ___ conocido.",
        "explanation_en": "The article «un» is masculine, so «escritor».",
        "explanation_tr": "«un» artikeli eril olduğu için «escritor».",
        "reason": "Cite the stated article, not the person's name.",
    }


try:
    Q._call_review = q24_provider
    Q.converge_topic(topic=q24, language="Spanish", level="A2", track="tr",
                     budget=Q.ReviewBudget(0.22), unit_title="Unit 2")
finally:
    Q._call_review = ORIG_CALL

q24_page = q24["content"]["pages"][1]
check(len(q24_calls) == 1, f"one call ({q24_calls})")
for key in ("answer", "options", "distractors"):
    check(q24_page[key] == q24_before[key], f"{key} unchanged")
check("Mateo" not in q24_page["explanation_tr"],
      "the rationale no longer reasons from the name")
check(Q._ungrounded_explanation_names(q24_page) == []
      and Q._topic_render_blockers(q24["content"]) == [],
      "and the page is clean under both predicates")


print("\n[6] a repair that invents a different person is refused, writing nothing")
victim = topic_of(mcq(explanation="Sara is a woman, so the feminine form is used.",
                      explanation_tr="Sara bir kadın olduğu için dişil biçim kullanılır."))
victim_before = copy.deepcopy(victim["content"]["pages"][1])
raised = None
try:
    Q._call_review = lambda **kw: {
        "stem": victim_before["prompt"],
        "explanation_en": "Elena is a woman, so the feminine form is used.",
        "explanation_tr": "Elena bir kadın olduğu için dişil biçim kullanılır.",
        "reason": "swapped one invented person for another",
    }
    Q.converge_topic(topic=victim, language="Spanish", level="A1", track="tr",
                     budget=Q.ReviewBudget(0.22), unit_title="Unit 1")
except Q.QualityGateError as exc:
    raised = exc
finally:
    Q._call_review = ORIG_CALL
check(raised is not None, f"it fails closed ({str(raised)[:56]})")
check(victim["content"]["pages"][1] == victim_before, "and writes nothing")


print("\n[7] assessments are judged by the same predicate, with no extra call")
assessment = {"pages": [
    mcq(title="Question 1",
        explanation="The stem states «una mujer».",
        explanation_tr="Soruda «una mujer» geçiyor."),
    mcq(title="Question 2",
        explanation="Lucía is from Spain, so she is española.",
        explanation_tr="Lucía İspanya'dan olduğu için española'dır."),
]}
rows = Q._assessment_render_blockers(assessment)
grounding = [r for r in rows if r["why"] == Q._EXPLANATION_GROUNDING_REASON]
check(len(grounding) == 1 and grounding[0]["page_index"] == 1,
      f"the ungrounded assessment item is reported ({grounding})")
check(grounding[0]["question"] == 2,
      f"numbered as the learner sees it ({grounding[0].get('question')})")


print("\n[8] no language or CEFR branch was introduced")
import inspect  # noqa: E402
source = "\n".join(
    inspect.getsource(fn) for fn in (
        Q._ungrounded_explanation_names, Q._visible_evidence_tokens,
        Q._explanation_grounding_blockers,
    )
)
for token in ("Spanish", "Turkish", "English", "German", "espa", "A1", "A2", "B1"):
    check(token not in source, f"no {token!r} in the grounding implementation")


print(f"\n=== {len(FAILURES)} failing checks ===")
for row in FAILURES:
    print("  -", row)
if FAILURES:
    sys.exit(1)
print("[GROUNDING] an MCQ rationale may only cite evidence the learner can see")
