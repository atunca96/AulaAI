#!/usr/bin/env python3
"""Regression: the personal-name→gender refusal is repaired at page level.

Production topic "Adjective Agreement and Physical Description", page pages[3],
failed twice with the same chain:

    review_lesson ... ok=True
    review_blocker_retry ... ok=True
    review_render_exact:...pages.3.prompt ... ok=True
    -> renderer still: page 3 tr/en: answer depends on gender inferred from a
       personal name
    (and the unit retry produced exactly the same result)

"A Family Photograph" had stalled in the same class the run before. The retry
count was never the problem. render_contract reads this refusal off the stem AND
the explanation together, and _repair_topic_render_stems_exact only ever patched
the stem — so the rationale kept saying "this name is feminine" and the page was
refused again, forever.

It was also unrepairable in a second way: the rule's only escape is an explicit
gender word in the STEM, matched against a short fixed lexicon. A Spanish stem
says `mujer`, which that lexicon does not contain and cannot contain without a
brittle per-language list. So a semantically correct Spanish rewrite still
failed deterministically.
"""

from __future__ import annotations
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q
from services.authoring import render_contract as RC

NAME_STEM = "Ana es una persona ___. (alto)"
NAME_EN = "Ana is a feminine name, so the adjective takes the feminine form 'alta'."
NAME_TR = "Ana bir kadın ismi olduğu için sıfat dişil biçimde «alta» olur."

FIXED_STEM = "La mujer es ___. (alto)"
FIXED_EN = "The stem states the noun «mujer», which is feminine, so «alta» agrees with it."
FIXED_TR = "Soruda «mujer» adı geçiyor; bu sözcük dişil olduğu için «alta» uyum sağlar."


def agreement_page():
    return {
        "type": "mcq",
        "title": "Adjective agreement",
        "title_tr": "Sıfat uyumu",
        "prompt": NAME_STEM,
        "answer": "alta",
        "options": ["alta", "alto", "altos", "altas"],
        "distractors": ["alto", "altos", "altas"],
        "explanation_en": NAME_EN,
        "explanation_tr": NAME_TR,
        "why_tr": "Sıfat, ismin cinsiyetine uyar.",
    }


def topic_with(page):
    return {
        "id": "agreement",
        "title": "Adjective Agreement and Physical Description",
        "content": {"pages": [
            {"type": "text", "text": "Adjectives agree.", "text_tr": "Sıfatlar uyum sağlar."},
            {"type": "text", "text": "Gender and number.", "text_tr": "Cinsiyet ve sayı."},
            {"type": "text", "text": "Physical description.", "text_tr": "Fiziksel betimleme."},
            page,
        ]},
        "is_assessment": False,
    }


# ---------------------------------------------------------------------------
# 1. The production state, and the proof that a stem-only rewrite cannot clear
#    it: the rationale still carries the name→gender reasoning.
# ---------------------------------------------------------------------------

page = agreement_page()
for is_tr in (True, False):
    ok, why = RC.page_is_renderable(page, is_tr)
    assert not ok and why == RC.NAME_GENDER_REASON, (is_tr, ok, why)

stem_only = agreement_page()
# What a stem-only repair actually produces: the question is rewritten and a
# Spanish gender cue is added, but the person stays and the rationale is
# untouched. The renderer reads both, so it refuses again — which is why this
# class needs the page-level repair.
stem_only["prompt"] = "Ana es una mujer. Ana es ___. (alto)"
for is_tr in (True, False):
    ok, why = RC.page_is_renderable(stem_only, is_tr)
    assert not ok and why == RC.NAME_GENDER_REASON, (
        "a stem-only repair must still be refused while the rationale stands",
        is_tr, ok, why,
    )

# And the rule no longer refuses a page whose rationale is corrected, even
# though its stem is Spanish and its explanation must still say "feminine".
fixed = agreement_page()
fixed.update({"prompt": FIXED_STEM, "explanation_en": FIXED_EN,
              "explanation_tr": FIXED_TR})
for is_tr in (True, False):
    ok, why = RC.page_is_renderable(fixed, is_tr)
    assert ok, (is_tr, why)

# ---------------------------------------------------------------------------
# 2. The atomic repair: one page-scoped call, stem and both rationales together.
# ---------------------------------------------------------------------------

orig_call = Q._call_review
calls = []


def fake_call(**kwargs):
    calls.append(kwargs["stage"])
    payload = kwargs["payload"]
    assert kwargs["response_schema"] is Q._NAME_GENDER_PAGE_REPAIR_SCHEMA
    assert payload["path"] == ["pages", 3], payload["path"]
    assert payload["stem_field"] == "prompt"
    assert payload["current_stem"] == NAME_STEM
    assert payload["current_explanation_en"] == NAME_EN
    assert payload["current_explanation_tr"] == NAME_TR
    # The answer set is handed over as immutable context, never as something
    # the repair may propose a new value for.
    assert payload["immutable_page_context"]["answer"] == "alta"
    assert payload["immutable_page_context"]["options"] == [
        "alta", "alto", "altos", "altas"]
    assert "answer" not in Q._NAME_GENDER_PAGE_REPAIR_SCHEMA["properties"]
    assert "options" not in Q._NAME_GENDER_PAGE_REPAIR_SCHEMA["properties"]
    assert [row["why"] for row in payload["renderer_contract_blockers"]] == [
        RC.NAME_GENDER_REASON, RC.NAME_GENDER_REASON]
    return {"stem": FIXED_STEM, "explanation_en": FIXED_EN,
            "explanation_tr": FIXED_TR,
            "reason": "Ask from the stated noun instead of the person's name."}


topic = topic_with(agreement_page())
before = copy.deepcopy(topic["content"]["pages"][3])
blockers = Q._topic_render_blockers(topic["content"])
assert [row["why"] for row in blockers] == [
    RC.NAME_GENDER_REASON, RC.NAME_GENDER_REASON], blockers

try:
    Q._call_review = fake_call
    applied = Q._repair_topic_render_stems_exact(
        topic=topic, language="Spanish", level="A1",
        budget=Q.ReviewBudget(0.22), blockers=blockers,
    )
finally:
    Q._call_review = orig_call

repaired = topic["content"]["pages"][3]
assert applied == 1, applied
assert calls == [
    "review_render_name_gender:Adjective Agreement and Physical Description"
    ":pages.3.prompt"
], calls

# The answer set is untouched.
for key in ("answer", "options", "distractors"):
    assert repaired[key] == before[key], (key, repaired[key], before[key])

# The stem now carries visible evidence and no longer leans on the name.
assert repaired["prompt"] == FIXED_STEM
assert "Ana" not in repaired["prompt"]

# Neither rationale reasons from the name any more.
assert repaired["explanation_en"] == FIXED_EN
assert repaired["explanation_tr"] == FIXED_TR
for text in (repaired["explanation_en"], repaired["explanation_tr"]):
    assert "Ana" not in text, text

# And the renderer contract passes for BOTH exports.
for is_tr in (True, False):
    ok, why = RC.page_is_renderable(repaired, is_tr)
    assert ok, (is_tr, why)
assert Q._topic_render_blockers(topic["content"]) == []

# ---------------------------------------------------------------------------
# 3. Safety intent held: an item that really does infer gender from the name
#    alone is still refused, and a repair that leaves it that way fails closed.
# ---------------------------------------------------------------------------

control = agreement_page()
control["prompt"] = "Ana es ___. (alto)"
for is_tr in (True, False):
    ok, why = RC.page_is_renderable(control, is_tr)
    assert not ok and why == RC.NAME_GENDER_REASON, (is_tr, ok, why)

# Same rationale split by a semicolon is still one statement's reasoning.
semicolon = agreement_page()
semicolon["explanation_en"] = "Ana is a feminine name; therefore «alta»."
semicolon["explanation_tr"] = "Ana dişil bir isimdir; bu yüzden «alta»."
assert RC.hidden_world_reason(semicolon) == RC.NAME_GENDER_REASON

# A single locale carrying the unsafe rationale still refuses both exports.
tr_only = agreement_page()
tr_only["explanation_en"] = FIXED_EN
assert RC.hidden_world_reason(tr_only) == RC.NAME_GENDER_REASON


def refusing_repairs():
    """Repairs that do not actually clear the blocker, or touch the answer."""
    yield ({"stem": FIXED_STEM, "explanation_en": NAME_EN,
            "explanation_tr": FIXED_TR, "reason": "rationale untouched"},
           "still refused")
    yield ({"stem": NAME_STEM, "explanation_en": NAME_EN,
            "explanation_tr": NAME_TR, "reason": "no change at all"},
           "still refused")
    yield ({"stem": FIXED_STEM, "explanation_en": "", "explanation_tr": FIXED_TR,
            "reason": "empty rationale"},
           "empty field")


for response, label in refusing_repairs():
    victim = topic_with(agreement_page())
    snapshot = copy.deepcopy(victim["content"]["pages"][3])
    victim_blockers = Q._topic_render_blockers(victim["content"])
    try:
        Q._call_review = lambda _r=response, **kwargs: _r
        Q._repair_topic_render_stems_exact(
            topic=victim, language="Spanish", level="A1",
            budget=Q.ReviewBudget(0.22), blockers=victim_blockers,
        )
    except Q.QualityGateError:
        pass
    else:
        raise AssertionError(f"{label} must fail closed")
    finally:
        Q._call_review = orig_call
    assert victim["content"]["pages"][3] == snapshot, "nothing may be written"

# The answer set is immutable by construction: the response schema has no field
# that can express it, and only the stem and the explanation keys the page
# already carries are ever written.
assert set(Q._NAME_GENDER_PAGE_REPAIR_SCHEMA["required"]) == {
    "stem", "explanation_en", "explanation_tr", "reason"}
# A page that carries no explanation field at all gets nothing invented on it.
bare = {"type": "mcq", "title": "Bare", "prompt": NAME_STEM, "answer": "alta",
        "options": ["alta", "alto", "altos", "altas"],
        "distractors": ["alto", "altos", "altas"]}
assert RC.page_is_renderable(bare, True)[0], "no rationale, nothing to infer from"

# ---------------------------------------------------------------------------
# 4. The other renderer-blocker classes still take the stem-only path.
# ---------------------------------------------------------------------------

bio_page = {
    "type": "mcq",
    "title": "Nationality",
    "prompt": "Ana nació en España. ¿Cuál es su nacionalidad?",
    "answer": "española",
    "options": ["española", "mexicana", "francesa", "italiana"],
    "distractors": ["mexicana", "francesa", "italiana"],
    "explanation_en": "Her nationality follows from her birthplace.",
    "explanation_tr": "Milliyeti doğum yerinden çıkar.",
}
bio_topic = {"id": "bio", "title": "Countries", "content": {"pages": [bio_page]},
             "is_assessment": False}
bio_blockers = Q._topic_render_blockers(bio_topic["content"])
assert bio_blockers and all(row["why"] != RC.NAME_GENDER_REASON for row in bio_blockers)

bio_calls = []


def bio_call(**kwargs):
    bio_calls.append(kwargs["stage"])
    assert kwargs["response_schema"] is Q._EXACT_TARGET_REPAIR_SCHEMA
    return {"value": "España → ¿qué nacionalidad corresponde?", "reason": "direct mapping"}


try:
    Q._call_review = bio_call
    assert Q._repair_topic_render_stems_exact(
        topic=bio_topic, language="Spanish", level="A1",
        budget=Q.ReviewBudget(0.22), blockers=bio_blockers,
    ) == 1
finally:
    Q._call_review = orig_call

assert bio_calls == ["review_render_exact:Countries:pages.0.prompt"], bio_calls
assert Q._topic_render_blockers(bio_topic["content"]) == []

print("[NAME-GENDER] stem and both rationales repaired atomically; answer set "
      "immutable; both exports renderable; name-only inference still refused")
