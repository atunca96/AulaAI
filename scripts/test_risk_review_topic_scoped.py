#!/usr/bin/env python3
"""Regression: the pedagogical-risk pass reviews one topic per call.

Production run on 9fa9bc2 finished all six units' lesson review, then died on:

    [QUALITY-CALL] END review_risk:Introductions and Basic Greetings ok=True
                   seconds=8.94 cost=$0.0110
    Introductions and Basic Greetings: risk reviewer returned incomplete topic
    coverage

The call succeeded and was paid for. review_unit_risk_claims() batched every
topic carrying risk records into one payload and then required the response to
contain exactly one row per supplied topic_id — but _LESSON_REVIEW_SCHEMA can
express neither array cardinality nor topic-id coverage, so the provider is free
to return valid JSON covering only some of them. Transport ok, application
fatal, nothing salvaged.

The boundary is now one topic per call, so partial coverage of a batch is not a
shape the code can be handed at all.

Nothing here is language- or level-specific. The fixture carries example content
the way a real course does, but every assertion is about field, schema and
topic-id semantics — not about any particular language or CEFR band.
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

ORIG_CALL = Q._call_review
FAILURES = []


def check(condition, label):
    print(("  PASS  " if condition else "  FAIL  ") + label)
    if not condition:
        FAILURES.append(label)


BROAD_RULE = "Adjectives always end in -o."
NARROW_RULE = "Many two-ending adjectives use -o in the masculine singular."


def risky_topic(topic_id, title, rule):
    """A topic whose rule text the risk selector picks up."""
    return {
        "id": topic_id,
        "title": title,
        "content": {"pages": [
            {"type": "grammar", "title": "Rule", "title_tr": "Kural",
             "rules": [{"rule": rule,
                        "rule_tr": "Sıfatlar her zaman -o ile biter."}]},
        ]},
        "is_assessment": False,
    }


def quiet_topic(topic_id, title):
    """A topic the risk selector does not pick up at all."""
    return {
        "id": topic_id,
        "title": title,
        "content": {"pages": [
            {"type": "vocabulary", "title": "Words", "title_tr": "Kelimeler",
             "items": [{"term": "hola", "translation": "hello",
                        "translation_tr": "merhaba"}]},
        ]},
        "is_assessment": False,
    }


def unit_topics():
    return [
        risky_topic("t1", "Greetings", BROAD_RULE),
        risky_topic("t2", "Introductions", BROAD_RULE),
        risky_topic("t3", "Farewells", BROAD_RULE),
    ]


class Provider:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs["stage"])
        return self.handler(kwargs)


def run(topics, handler, **kw):
    provider = Provider(handler)
    try:
        Q._call_review = provider
        applied = Q.review_unit_risk_claims(
            unit_title="Introductions and Basic Greetings", topics=topics,
            language="Spanish", level="A1", track="tr",
            budget=Q.ReviewBudget(0.22), **kw,
        )
    finally:
        Q._call_review = ORIG_CALL
    return applied, provider.calls


def supplied_ids(kwargs):
    return [str(row.get("topic_id")) for row in kwargs["payload"]["topics"]]


print("\n[1] the selector still decides which topics are reviewed at all")
topics = unit_topics()
check(all(Q._risk_review_records(t["content"]) for t in topics),
      "all three fixture topics carry risk records")
check(not Q._risk_review_records(quiet_topic("q", "Quiet")["content"]),
      "a topic with no pedagogical claim carries none")


print("\n[2] the old batch response shape is what killed the build")
# Exactly the production failure, reproduced against the old all-or-nothing
# check: three topics supplied, two returned.
selected = [{"topic_id": t["id"]} for t in unit_topics()]
rows = [{"topic_id": "t1", "verdict": "ok", "patches": []},
        {"topic_id": "t2", "verdict": "ok", "patches": []}]
expected = {row["topic_id"] for row in selected}
actual = {str(r.get("topic_id") or "") for r in rows}
check(actual != expected or len(rows) != len(selected),
      "a two-of-three batch response fails the old coverage check")
# And the schema genuinely cannot prevent it.
props = Q._LESSON_REVIEW_SCHEMA["properties"]["topics"]
check("minItems" not in props and "maxItems" not in props,
      "the response schema cannot express topic cardinality")


print("\n[3] each selected topic gets its own call, and all three complete")
topics = unit_topics()


CALL_KWARGS = []


def one_each(kwargs):
    CALL_KWARGS.append(kwargs)
    ids = supplied_ids(kwargs)
    assert len(ids) == 1, ids
    assert kwargs["payload"]["language"] == "Spanish"
    assert kwargs["payload"]["level"] == "A1"
    assert kwargs["payload"]["instruction_track"] == "tr"
    assert kwargs["payload"]["topics"][0]["records"], "records must travel"
    return {"topics": [{"topic_id": ids[0], "verdict": "ok", "patches": []}]}


applied, calls = run(topics, one_each)
check(len(calls) == 3, f"one call per selected topic ({calls})")
check(calls == [
    "review_risk:Introductions and Basic Greetings:Greetings",
    "review_risk:Introductions and Basic Greetings:Introductions",
    "review_risk:Introductions and Basic Greetings:Farewells",
], f"each call is scoped to its own topic ({calls})")
check(all(t.get(Q._RISK_REVIEW_DONE_KEY) for t in topics),
      "every topic is marked complete")

# Hidden reasoning shares the completion budget with the structured JSON. A
# production risk call died at finish_reason=length after 86 visible characters
# on a 1302-char payload with max_tokens=1600 — the budget went to reasoning,
# not to the schema. Every other structured review call in this module already
# asks for low effort for exactly that reason.
check(CALL_KWARGS and all(kw["effort"] == "low" for kw in CALL_KWARGS),
      f"risk review asks for low reasoning effort "
      f"({sorted({kw['effort'] for kw in CALL_KWARGS})})")
check(all(kw["max_tokens"] == 1600 for kw in CALL_KWARGS),
      "and the completion budget is unchanged")
check(all(kw["response_schema"] is Q._LESSON_REVIEW_SCHEMA for kw in CALL_KWARGS),
      "and the response schema is unchanged")
check(all(len(kw["payload"]["topics"]) == 1 for kw in CALL_KWARGS),
      "and each call still carries exactly one topic")


print("\n[4] a wrong or missing topic_id still fails closed")
for label, response in (
    ("another topic's id", {"topics": [{"topic_id": "t9", "verdict": "ok",
                                        "patches": []}]}),
    ("two rows for one topic", {"topics": [
        {"topic_id": "t1", "verdict": "ok", "patches": []},
        {"topic_id": "t1", "verdict": "ok", "patches": []}]}),
    ("no rows at all", {"topics": []}),
    ("missing topics key", {}),
):
    raised = None
    try:
        run(unit_topics(), lambda kw, r=response: r)
    except Q.QualityGateError as exc:
        raised = exc
    check(raised is not None and "incomplete topic coverage" in str(raised),
          f"refused: {label}")


print("\n[5] a failure on one topic never re-spends the completed calls")
topics = unit_topics()
attempts = {"t2": 0}


def fail_second_once(kwargs):
    ids = supplied_ids(kwargs)
    topic_id = ids[0]
    if topic_id == "t2":
        attempts["t2"] += 1
        if attempts["t2"] == 1:
            # The production shape: a response that does not cover its topic.
            return {"topics": [{"topic_id": "t7", "verdict": "ok", "patches": []}]}
    if topic_id == "t3":
        return {"topics": [{"topic_id": "t3", "verdict": "fix", "patches": [{
            "path": ["pages", "0", "rules", "0", "rule"],
            "old": BROAD_RULE, "value": NARROW_RULE,
            "reason": "The claim is true only for a subclass.",
        }]}]}
    return {"topics": [{"topic_id": topic_id, "verdict": "ok", "patches": []}]}


raised = None
provider = Provider(fail_second_once)
try:
    Q._call_review = provider
    Q.review_unit_risk_claims(
        unit_title="Introductions and Basic Greetings", topics=topics,
        language="Spanish", level="A1", track="tr", budget=Q.ReviewBudget(0.22),
    )
except Q.QualityGateError as exc:
    raised = exc
finally:
    Q._call_review = ORIG_CALL

check(raised is not None, f"the unresolved topic fails closed ({str(raised)[:50]})")
check(provider.calls == [
    "review_risk:Introductions and Basic Greetings:Greetings",
    "review_risk:Introductions and Basic Greetings:Introductions",
], f"it stops at the bad topic, having spent two calls ({provider.calls})")
check(topics[0].get(Q._RISK_REVIEW_DONE_KEY) is True
      and not topics[1].get(Q._RISK_REVIEW_DONE_KEY)
      and not topics[2].get(Q._RISK_REVIEW_DONE_KEY),
      "only the completed topic is marked")

# Resume: the same unit, same in-memory topics. The completed topic is not
# reviewed again; only the unresolved ones are.
applied, resumed = run(topics, fail_second_once)
check(resumed == [
    "review_risk:Introductions and Basic Greetings:Introductions",
    "review_risk:Introductions and Basic Greetings:Farewells",
], f"the resume re-calls only the unresolved topics ({resumed})")
check(topics[2]["content"]["pages"][0]["rules"][0]["rule"] == NARROW_RULE,
      "the patched topic carries the narrowed rule")
check(applied >= 1, f"the patch is counted ({applied})")


print("\n[6] a patched topic is re-proved through converge_topic")
topics = unit_topics()
converged = []
orig_converge = Q.converge_topic


def spy_converge(**kwargs):
    converged.append(kwargs["topic"]["id"])
    return orig_converge(**kwargs)


def patch_first(kwargs):
    topic_id = supplied_ids(kwargs)[0]
    if topic_id == "t1":
        return {"topics": [{"topic_id": "t1", "verdict": "fix", "patches": [{
            "path": ["pages", "0", "rules", "0", "rule"],
            "old": BROAD_RULE, "value": NARROW_RULE,
            "reason": "Narrow the overgeneralized claim.",
        }]}]}
    return {"topics": [{"topic_id": topic_id, "verdict": "ok", "patches": []}]}


try:
    Q.converge_topic = spy_converge
    applied, calls = run(topics, patch_first)
finally:
    Q.converge_topic = orig_converge

check(converged == ["t1", "t2", "t3"],
      f"every reviewed topic is re-proved by the controller ({converged})")
check(topics[0]["content"]["pages"][0]["rules"][0]["rule"] == NARROW_RULE,
      "the risk patch is applied through the exact-path guard")
for topic in topics:
    clean = (not A.blocking(Q._audit_topic(topic, language="Spanish", track="tr"))
             and Q._topic_render_blockers(topic["content"]) == []
             and Q.missing_bilingual_pairs(topic["content"]) == [])
    check(clean, f"{topic['title']}: audit, renderer and bilingual all clean after")


print("\n[7] a unit with no risk records costs nothing")
quiet = [quiet_topic("q1", "Alphabet"), quiet_topic("q2", "Numbers")]
snapshot = copy.deepcopy([t["content"] for t in quiet])


def never(kwargs):
    raise AssertionError(f"unexpected model call: {kwargs['stage']}")


applied, calls = run(quiet, never)
check(applied == 0 and calls == [], "no model calls and no patches")
check([t["content"] for t in quiet] == snapshot, "content untouched")
check(all(t.get(Q._RISK_REVIEW_DONE_KEY) for t in quiet),
      "and the topics are marked so a resume skips them too")


print("\n[8] the completion marker alone prevents a second review")
topics = unit_topics()
applied, calls = run(topics, one_each)
check(len(calls) == 3, "first pass reviews all three")
applied2, calls2 = run(topics, never)
check(applied2 == 0 and calls2 == [],
      f"a second pass over the same topics calls nothing ({calls2})")
check(Q._RISK_REVIEW_DONE_KEY != Q._LESSON_REVIEW_DONE_KEY,
      "risk completion is tracked separately from lesson completion")


print(f"\n=== {len(FAILURES)} failing checks ===")
for row in FAILURES:
    print("  -", row)
if FAILURES:
    sys.exit(1)
print("[RISK-REVIEW] one topic per call; partial batch coverage is not a "
      "reachable state; completed topics are never re-spent")
