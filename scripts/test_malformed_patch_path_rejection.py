#!/usr/bin/env python3
"""Regression: a malformed reviewer patch path is rejected, not fatal.

Production course afcca9f1-7e89-42f2-b148-e779b76763c7 failed because the broad
lesson reviewer proposed the path ['pages', ',', 'items', '5', 'example'] for
"Numbers 0 to 30 and Contact Information". _coerce_patch_path correctly refused
the invalid list component ',', the whole unit was retried, the second model
response repeated the same malformed path, and publication aborted.

The malformed proposal must now be rejected on its own: no index guessing, no
silent remap to a nearby path, nothing written, the already-reviewed lessons
never re-sent, and the real renderer blocker on "Talking About My Family" still
reaching the existing targeted exact-repair layer.
"""

from __future__ import annotations
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q

MALFORMED_PATH = ["pages", ",", "items", "5", "example"]

# ---------------------------------------------------------------------------
# 1. _apply_patches rejects the exact malformed proposal, twice, without losing
#    the valid patches that shared the same response.
# ---------------------------------------------------------------------------

numbers_content = {
    "pages": [{
        "type": "vocab",
        "items": [
            {"term": "veinte", "example": "Tengo veinte años."},
            {"term": "treinta", "example": "Hay treinta sillas."},
        ],
        "prompt": "¿Cuál es tu número de teléfono?",
    }]
}
numbers_topic = {"id": "numbers", "title": "Numbers 0 to 30 and Contact Information",
                 "content": numbers_content, "is_assessment": False}

applied = Q._apply_patches(
    {"numbers": numbers_topic},
    [
        {"topic_id": "numbers", "path": list(MALFORMED_PATH),
         "old": "Tengo veinte años.", "value": "Tengo veinte años exactos.",
         "reason": "provider emitted an invalid list component"},
        # The identical malformed proposal a second time is still just noise.
        {"topic_id": "numbers", "path": list(MALFORMED_PATH),
         "old": "Tengo veinte años.", "value": "Tengo veinte años exactos.",
         "reason": "same malformed response shape again"},
        # A well-formed patch in the same batch must still be applied.
        {"topic_id": "numbers", "path": ["pages", "0", "items", "1", "example"],
         "old": "Hay treinta sillas.", "value": "Hay treinta sillas en el aula.",
         "reason": "valid exact patch"},
    ],
)

assert applied == 1, applied
assert numbers_content["pages"][0]["items"][0]["example"] == "Tengo veinte años."
assert numbers_content["pages"][0]["items"][1]["example"] == "Hay treinta sillas en el aula."
# Nothing may be invented at, or remapped from, the malformed path.
assert list(numbers_content["pages"][0].keys()) == ["type", "items", "prompt"]
assert len(numbers_content["pages"]) == 1
assert len(numbers_content["pages"][0]["items"]) == 2

# A non-list / empty path is malformed in the same way.
assert Q._apply_patches(
    {"numbers": numbers_topic},
    [{"topic_id": "numbers", "path": "pages.0.prompt", "old": "x", "value": "y"},
     {"topic_id": "numbers", "path": [], "old": "x", "value": "y"}],
) == 0

# Cross-topic safety is untouched: an unknown topic still fails closed.
try:
    Q._apply_patches({"numbers": numbers_topic},
                     [{"topic_id": "ghost", "path": ["pages", "0", "prompt"],
                       "old": "x", "value": "y"}])
except Q.QualityGateError:
    pass
else:
    raise AssertionError("unknown patch topic must still fail closed")

# ---------------------------------------------------------------------------
# 2. review_unit_lessons survives the same malformed path in both the broad
#    review and the blocker retry, and still drives the family lesson's
#    renderer blocker into the exact stem repair.
# ---------------------------------------------------------------------------

FAMILY_BAD = "Alex tiene una hermana. ¿Es hijo o hija de María?"
FAMILY_GOOD = "María es la madre de Ana. ¿Qué es Ana para María?"
NUMBERS_BAD = "Pablo nació en 1994. ¿Cuántos años tiene?"
NUMBERS_GOOD = "Veinte más diez, ¿cuánto es?"

numbers_lesson = {
    "id": "numbers",
    "title": "Numbers 0 to 30 and Contact Information",
    "content": {
        "pages": [{
            "type": "vocab",
            "items": [{"term": "veinte", "example": "Tengo veinte años."}],
            "prompt": NUMBERS_BAD,
        }]
    },
    "is_assessment": False,
}
family_lesson = {
    "id": "family",
    "title": "Talking About My Family",
    "content": {
        "pages": [
            {"type": "text", "text": "La familia.", "text_tr": "Aile."},
            {"type": "text", "text": "Los padres.", "text_tr": "Anne baba."},
            {"type": "text", "text": "Los hermanos.", "text_tr": "Kardeşler."},
            {"type": "text", "text": "Los abuelos.", "text_tr": "Büyükanne ve büyükbaba."},
            {
                "type": "mcq",
                "title": "Practice",
                "title_tr": "Alıştırma",
                "prompt": FAMILY_BAD,
                "answer": "hija",
                "options": ["hija", "hijo", "madre", "padre"],
                "distractors": ["hijo", "madre", "padre"],
            },
        ]
    },
    "is_assessment": False,
}

orig_call = Q._call_review
orig_audit = Q._audit_topic
orig_render = Q._topic_render_blockers
orig_repair = Q.R.repair_lesson
calls = []


def fake_audit(topic, *, language, track):
    return []


def fake_render(content):
    pages = (content or {}).get("pages") or []
    for index, page in enumerate(pages):
        if page.get("prompt") == FAMILY_BAD:
            return [{
                "page_index": index,
                "title": "Practice",
                "locale": "en",
                "why": "answer depends on gender inferred from a personal name",
                "stem": FAMILY_BAD,
                "answer": "hija",
            }]
        if page.get("prompt") == NUMBERS_BAD:
            return [{
                "page_index": index,
                "title": "Numbers",
                "locale": "en",
                "why": "answer depends on the current year, which is not stated",
                "stem": NUMBERS_BAD,
                "answer": "",
            }]
    return []


def fake_call(**kwargs):
    stage = kwargs["stage"]
    calls.append(stage)
    if stage.endswith("Numbers 0 to 30 and Contact Information"):
        # Both the broad review and any retry return the same malformed path.
        return {"topics": [{
            "topic_id": "numbers", "verdict": "fix",
            "patches": [{"topic_id": "numbers", "path": list(MALFORMED_PATH),
                         "old": "Tengo veinte años.", "value": "Tengo veinte años exactos.",
                         "reason": "malformed"}],
        }]}
    if stage.endswith("Talking About My Family"):
        return {"topics": [{"topic_id": "family", "verdict": "ok", "patches": []}]}
    if stage == "review_render_exact:Talking About My Family:pages.4.prompt":
        return {"value": FAMILY_GOOD, "reason": "Ask from an explicit stated relation."}
    if stage == ("review_render_exact:Numbers 0 to 30 and Contact Information"
                 ":pages.0.prompt"):
        return {"value": NUMBERS_GOOD, "reason": "Ask a self-contained arithmetic stem."}
    raise AssertionError(stage)


try:
    Q._call_review = fake_call
    Q._audit_topic = fake_audit
    Q._topic_render_blockers = fake_render
    Q.R.repair_lesson = lambda content, language: content
    applied = Q.review_unit_lessons(
        unit_title="Everyday Basics",
        topics=[numbers_lesson, family_lesson],
        language="Spanish",
        level="A1",
        track="tr",
        budget=Q.ReviewBudget(999),
    )

    # 3. A unit-level retry must not re-send lessons that already passed.
    before = len(calls)
    Q.review_unit_lessons(
        unit_title="Everyday Basics",
        topics=[numbers_lesson, family_lesson],
        language="Spanish",
        level="A1",
        track="tr",
        budget=Q.ReviewBudget(999),
    )
    resumed = calls[before:]
finally:
    Q._call_review = orig_call
    Q._audit_topic = orig_audit
    Q._topic_render_blockers = orig_render
    Q.R.repair_lesson = orig_repair

assert applied == 2, applied
# Neither malformed proposal changed anything.
assert numbers_lesson["content"]["pages"][0]["items"][0]["example"] == "Tengo veinte años."
# Both real renderer blockers still reached the exact stem repair.
assert numbers_lesson["content"]["pages"][0]["prompt"] == NUMBERS_GOOD
assert family_lesson["content"]["pages"][4]["prompt"] == FAMILY_GOOD
assert calls == [
    # Broad review proposes the malformed path; it is rejected on its own and
    # the lesson continues into its deterministic/render re-audit.
    "review_lesson:Everyday Basics:Numbers 0 to 30 and Contact Information",
    # The blocker retry repeats the identical malformed path — the shape that
    # aborted publication before — and is rejected the same way.
    "review_blocker_retry:Numbers 0 to 30 and Contact Information",
    "review_render_exact:Numbers 0 to 30 and Contact Information:pages.0.prompt",
    "review_lesson:Everyday Basics:Talking About My Family",
    "review_blocker_retry:Talking About My Family",
    "review_render_exact:Talking About My Family:pages.4.prompt",
], calls
assert resumed == [], resumed

print("[MALFORMED-PATCH] invalid reviewer patch path rejected in isolation; "
      "reviewed lessons not re-sent; renderer blocker still exact-repaired")
