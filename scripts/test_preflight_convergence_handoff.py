#!/usr/bin/env python3
"""Regression: recoverable preflight failures hand off to bounded convergence.

Proves both production failure classes from 2026-09-19:
1) an audit-clean renderer-only personal-name→gender blocker is repaired during
   preflight rather than surviving until final publication;
2) a deterministic target-field blocker whose local preflight candidates both
   fail is delegated to the generic convergence controller instead of aborting
   the whole classroom.
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
ORIG_AUDIT = Q._audit_topic


class Provider:
    def __init__(self, fn):
        self.fn = fn
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs["stage"])
        return self.fn(kwargs)


# ---------------------------------------------------------------------------
# 1) Renderer-only blocker: the exact class that reached production final gate.
# ---------------------------------------------------------------------------
meeting = {
    "id": "meeting",
    "title": "Meeting Someone New",
    "is_assessment": False,
    "content": {
        "pages": [{
            "type": "mcq",
            "title": "Check: Responding to an Introduction",
            "title_tr": "Kontrol: Tanışmaya Yanıt",
            "prompt": "Ana: Mucho gusto. — Yo: ___.",
            "answer": "Encantada.",
            "options": ["Encantada.", "Encantado.", "Buenos días.", "Hasta luego."],
            "distractors": ["Encantado.", "Buenos días.", "Hasta luego."],
            "explanation": "Ana is a feminine name, so the feminine response is used.",
            "explanation_tr": "Ana kadın ismidir; bu yüzden dişil yanıt kullanılır.",
            "why": "The response agrees with the speaker.",
            "why_tr": "Yanıt konuşana göre uyum sağlar.",
        }]
    },
}
assert not A.blocking(Q._audit_topic(meeting, language="Spanish", track="tr"))
assert Q._topic_render_blockers(meeting["content"]), "fixture must be renderer-only blocked"

def meeting_provider(kwargs):
    stage = kwargs["stage"]
    if stage.startswith("review_render_name_gender:Meeting Someone New:"):
        return {
            "stem": "Una mujer responde a una presentación: — Mucho gusto. — ___.",
            "explanation_en": "The stem explicitly identifies a woman speaker, so «Encantada.» is the matching response.",
            "explanation_tr": "Soru kadın bir konuşmacıyı açıkça belirtir; bu yüzden uygun yanıt «Encantada.»dır.",
            "reason": "Make the agreement evidence learner-visible instead of inferring it from a name.",
        }
    raise AssertionError(f"unexpected model stage: {stage}")

p1 = Provider(meeting_provider)
try:
    Q._call_review = p1
    applied = Q.repair_deterministic_preflight(
        units=[{"title": "First Meetings", "topics": [meeting]}],
        language="Spanish", level="A1", track="tr",
        budget=Q.ReviewBudget(0.22),
    )
finally:
    Q._call_review = ORIG_CALL

assert applied == 1, applied
assert len(p1.calls) == 1 and p1.calls[0].startswith("review_render_name_gender:")
assert Q._topic_render_blockers(meeting["content"]) == []
assert all(RC.page_is_renderable(meeting["content"]["pages"][0], locale)[0]
           for locale in RC.EXPORT_LOCALES)
assert meeting["content"]["pages"][0]["answer"] == "Encantada."
assert meeting["content"]["pages"][0]["options"] == [
    "Encantada.", "Encantado.", "Buenos días.", "Hasta luego."
]
print("[PREFLIGHT-HANDOFF] renderer-only name/gender blocker converged before broad review")


# ---------------------------------------------------------------------------
# 2) Local exact preflight repair fails twice; convergence must take ownership.
# ---------------------------------------------------------------------------
bad = "Daily routine explanation in English"
good = "Me levanto a las siete."
daily = {
    "id": "daily",
    "title": "Daily Schedule Conversation",
    "is_assessment": False,
    "content": {
        "pages": [{
            "type": "dialogue",
            "title": "Morning",
            "title_tr": "Sabah",
            "dialogue": [{
                "speaker": "A",
                "text": bad,
                "line_en": "I get up at seven.",
                "line_tr": "Saat yedide kalkarım.",
            }],
        }]
    },
}

def fake_audit(topic, *, language, track):
    value = topic["content"]["pages"][0]["dialogue"][0]["text"]
    if value != good:
        return [A.Finding(
            "instructional_prose_in_target_field", A.BLOCK,
            path="pages[0].dialogue[0]", field="text", role="target",
            detail="reads as instructional language", value=value,
        )]
    return []

def daily_provider(kwargs):
    stage = kwargs["stage"]
    if stage.startswith("review_preflight_repair:Daily Schedule Conversation"):
        return {"topics": [{"topic_id": "daily", "verdict": "ok", "patches": []}]}
    if stage.startswith("review_preflight_exact:Daily Schedule Conversation:"):
        # Both local candidates remain instructional prose and must be rejected
        # by the authoritative audit. This recreates the production dead end.
        return {"value": "Another English explanation", "reason": "bad fixture candidate"}
    if stage.startswith("converge_exact_field:Daily Schedule Conversation:"):
        row = kwargs["payload"]["topics"][0]
        blocker = row["deterministic_blockers"][0]
        assert blocker["repair_paths"] == [["pages", 0, "dialogue", 0, "text"]]
        current = row["records"][0]["value"]
        return {
            "topics": [{
                "topic_id": "daily",
                "verdict": "fix",
                "patches": [{
                    "path": ["pages", "0", "dialogue", "0", "text"],
                    "old": current,
                    "value": good,
                    "reason": "Target dialogue must be in the taught language.",
                }],
            }]
        }
    raise AssertionError(f"unexpected model stage: {stage}")

p2 = Provider(daily_provider)
try:
    Q._call_review = p2
    Q._audit_topic = fake_audit
    applied2 = Q.repair_deterministic_preflight(
        units=[{"title": "Daily Life", "topics": [daily]}],
        language="Spanish", level="A1", track="tr",
        budget=Q.ReviewBudget(0.22),
    )
finally:
    Q._call_review = ORIG_CALL
    Q._audit_topic = ORIG_AUDIT

assert daily["content"]["pages"][0]["dialogue"][0]["text"] == good
assert applied2 >= 1
assert any(stage.startswith("review_preflight_exact:") for stage in p2.calls)
assert any(stage.startswith("converge_exact_field:") for stage in p2.calls), p2.calls
print("[PREFLIGHT-HANDOFF] failed local exact repair delegated to convergence instead of aborting")
