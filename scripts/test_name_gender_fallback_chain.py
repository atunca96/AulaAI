#!/usr/bin/env python3
"""Regression: the name/gender fallback strategy is actually reachable.

Production `Professions and Gender of Nouns / pages[3]` hits a genuine
name/gender renderer blocker. `_detect_topic_blockers()` classifies it
correctly with two strategies — `["render_name_gender", "render_stem"]` — but
the second one was unreachable twice over:

  * `_repair_name_gender_page_exact()` raised QualityGateError the moment its
    candidate still failed `RC.page_is_renderable()`, so `converge_topic()`
    never got control back to try anything else; and
  * `_strategy_render_stem()` routed the same blocker straight back into
    `_repair_name_gender_page_exact()`, so even with control restored the
    "stem fallback" was a second atomic attempt at the same answer.

A rejected atomic candidate is now a non-progressing attempt that writes
nothing, and the fallback is genuinely stem-only.
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


BAD_STEM = "Ana es ___. (profesor)"
GOOD_STEM = "La mujer es ___. (profesor)"


def professions_topic():
    return {
        "id": "professions",
        "title": "Professions and Gender of Nouns",
        "is_assessment": False,
        "content": {"pages": [
            {"type": "text", "text": "Professions have gender.",
             "text_tr": "Meslek adlarının cinsiyeti vardır."},
            {"type": "text", "text": "Endings change.",
             "text_tr": "Ekler değişir."},
            {"type": "text", "text": "Some are invariable.",
             "text_tr": "Bazıları değişmez."},
            {"type": "mcq", "title": "Practice", "title_tr": "Alıştırma",
             "prompt": BAD_STEM, "answer": "profesora",
             "options": ["profesora", "profesor", "profesores", "profesoras"],
             "distractors": ["profesor", "profesores", "profesoras"],
             "explanation": "Ana is a feminine name, so «profesora».",
             "explanation_tr": "Ana kadın ismidir; bu yüzden «profesora».",
             "why": "Profession nouns agree.", "why_tr": "Meslek adları uyum sağlar."},
        ]},
    }


topic = professions_topic()
page_before = copy.deepcopy(topic["content"]["pages"][3])

print("\n[1] the blocker is genuine and carries both strategies")
check(RC.hidden_world_reason(page_before) == RC.NAME_GENDER_REASON,
      "the renderer refuses the page for the name/gender reason")
rows = [r for r in Q._detect_topic_blockers(topic, language="Spanish", track="tr",
                                            canonical="Spanish")
        if r["kind"] == "render"]
check(len(rows) == 1 and rows[0]["strategies"] == ["render_name_gender",
                                                   "render_stem"],
      f"classified with a fallback ({[r['strategies'] for r in rows]})")


print("\n[2] a rejected atomic candidate hands control back instead of aborting")
calls = []
seen = {}


def provider(**kwargs):
    stage = kwargs["stage"]
    calls.append(stage)
    if stage.startswith("review_render_name_gender:"):
        # A candidate that still carries the name-based rationale: the repair's
        # own probe refuses it for the same reason. This is the production
        # shape, and it used to end the run right here.
        return {
            "stem": BAD_STEM,
            "explanation_en": "Ana is a feminine name, so «profesora».",
            "explanation_tr": "Ana kadın ismidir; bu yüzden «profesora».",
            "reason": "unchanged",
        }
    if stage.startswith("review_render_exact:"):
        payload = kwargs["payload"]
        assert payload["path"] == ["pages", 3, "prompt"], payload["path"]
        seen["stem_payload"] = payload["current_value"]
        # Stem-only: the answer set is immutable context, not something to edit.
        assert payload["immutable_page_context"]["answer"] == "profesora"
        return {"value": GOOD_STEM,
                "reason": "Ask from the stated noun instead of the person."}
    raise AssertionError(f"unscripted stage: {stage}")


try:
    Q._call_review = provider
    applied = Q.converge_topic(
        topic=topic, language="Spanish", level="A1", track="tr",
        budget=Q.ReviewBudget(0.22), unit_title="Professions and Gender of Nouns",
    )
finally:
    Q._call_review = ORIG_CALL

page = topic["content"]["pages"][3]

check(calls == [
    "review_render_name_gender:Professions and Gender of Nouns:pages.3.prompt",
    "review_render_exact:Professions and Gender of Nouns:pages.3.prompt",
], f"atomic first, then the stem fallback, once each ({calls})")
check(sum(1 for c in calls if c.startswith("review_render_name_gender:")) == 1,
      "the atomic strategy is not called twice on the same fingerprint")
check(sum(1 for c in calls if c.startswith("review_render_exact:")) == 1,
      "the stem fallback is called exactly once")
check(seen.get("stem_payload") == BAD_STEM,
      f"the fallback edits the page's real, unmutated stem "
      f"({seen.get('stem_payload')!r})")

print("\n[3] the fallback removed the dependency and the topic converged")
check(page["prompt"] == GOOD_STEM, "the stem no longer introduces the person")
check("Ana" not in page["prompt"], "the personal name is gone from the stem")
for key in ("answer", "options", "distractors"):
    check(page[key] == page_before[key], f"{key} is unchanged")
check(RC.page_is_renderable(page, True)[0] and RC.page_is_renderable(page, False)[0],
      "the renderer contract admits the page in both export locales")
check(Q._topic_render_blockers(topic["content"]) == []
      and not A.blocking(Q._audit_topic(topic, language="Spanish", track="tr"))
      and Q.missing_bilingual_pairs(topic["content"]) == [],
      "audit, renderer and bilingual completeness are all clean")
check(applied >= 1, f"the repair is counted ({applied})")

print("\n[4] the rejected candidate wrote nothing on its way through")
# The atomic attempt returned a candidate the probe refused; the only edit on
# the page is the fallback's stem rewrite.
check(page["explanation"] == page_before["explanation"]
      and page["explanation_tr"] == page_before["explanation_tr"],
      "the refused atomic candidate did not mutate the rationales")

print("\n[5] strict callers still fail closed on an unusable candidate")
strict_topic = professions_topic()
strict_page = strict_topic["content"]["pages"][3]
raised = None
try:
    Q._call_review = lambda **kw: {
        "stem": BAD_STEM,
        "explanation_en": "Ana is a feminine name, so «profesora».",
        "explanation_tr": "Ana kadın ismidir; bu yüzden «profesora».",
        "reason": "unchanged",
    }
    Q._repair_name_gender_page_exact(
        topic=strict_topic, page=strict_page, page_index=3, language="Spanish",
        level="A1", budget=Q.ReviewBudget(0.22),
        blockers=Q._topic_render_blockers(strict_topic["content"]),
    )
except Q.QualityGateError as exc:
    raised = exc
finally:
    Q._call_review = ORIG_CALL
check(raised is not None and "still refused" in str(raised),
      f"the default call path still raises ({str(raised)[:52]})")
check(strict_page == page_before, "and writes nothing either")

print("\n[6] the atomic route is still preferred when it works")
working = professions_topic()
work_calls = []


def working_provider(**kwargs):
    work_calls.append(kwargs["stage"])
    return {"stem": GOOD_STEM,
            "explanation_en": "The stated noun is feminine, so «profesora».",
            "explanation_tr": "Belirtilen sözcük dişil olduğu için «profesora».",
            "reason": "Ask from the stated noun."}


try:
    Q._call_review = working_provider
    Q.converge_topic(topic=working, language="Spanish", level="A1", track="tr",
                     budget=Q.ReviewBudget(0.22), unit_title="U")
finally:
    Q._call_review = ORIG_CALL
check(len(work_calls) == 1
      and work_calls[0].startswith("review_render_name_gender:"),
      f"one atomic call, no fallback needed ({work_calls})")
fixed = working["content"]["pages"][3]
check("Ana" not in fixed["explanation_tr"],
      "and the atomic route still repairs the rationale, which stem-only cannot")

print(f"\n=== {len(FAILURES)} failing checks ===")
for row in FAILURES:
    print("  -", row)
if FAILURES:
    sys.exit(1)
print("[NAME-GENDER-FALLBACK] a rejected atomic candidate is non-progress, "
      "and the stem fallback is genuinely stem-only")
