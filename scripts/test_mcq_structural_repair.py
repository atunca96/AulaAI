#!/usr/bin/env python3
"""Regression: MCQ option-set blockers are repaired atomically, not path-at-a-time.

Production course 6c2c5f8c-28ed-4400-a620-75b4e42fadd4 failed on topic "Simple
Negation and Question Formation", page pages[4], with
{'distractor_count': 1, 'duplicate_options': 1}. The answer was present but
duplicated inside `options`, so only two usable distractors remained.

_findings_with_repair_paths resolved duplicate_options to ['pages', 4, 'options']
and distractor_count to nothing at all (`distractors` is derived, not stored),
and the residual exact-repair loop only accepted str values from _get_path, so a
list[str] repair path could never reach exact repair. The broad preflight repair
call returned ok=True and the blockers survived it.

An MCQ's answer, options and distractors are one structure: they are repaired as
one tuple, deterministically when the page still carries the text to do it, and
otherwise by one small bounded call for that single item.
"""

from __future__ import annotations
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import audit as A, quality_gate as Q, repair as R

ANSWER = "No hablo francés."
KEPT = ["Hablo francés.", "Hablas francés."]
SUPPLIED = "Habláis francés."


def negation_lesson():
    """The exact production page shape: answer duplicated inside options."""
    return {
        "pages": [
            {"type": "text", "text": "La negación.", "text_tr": "Olumsuzluk."},
            {"type": "text", "text": "El orden.", "text_tr": "Sözdizimi."},
            {"type": "text", "text": "Las preguntas.", "text_tr": "Sorular."},
            {"type": "text", "text": "La entonación.", "text_tr": "Tonlama."},
            {
                "type": "mcq",
                "title": "Negation practice",
                "title_tr": "Olumsuzluk alıştırması",
                "prompt": "¿Cómo se niega «Hablo francés»?",
                "answer": ANSWER,
                # The duplicate: four slots, three distinct readings, and only
                # two of them are usable distractors.
                "options": [ANSWER, ANSWER, KEPT[0], KEPT[1]],
                "why_tr": "Olumsuzluk «no» ile kurulur.",
            },
        ]
    }


def blockers_of(content):
    return A.summarise(A.blocking(A.audit_lesson(content, language="Spanish", track="tr")))


# ---------------------------------------------------------------------------
# 1. The production shape reproduces exactly, including the missing repair path.
# ---------------------------------------------------------------------------

content = negation_lesson()
found = A.blocking(A.audit_lesson(content, language="Spanish", track="tr"))
summary = A.summarise(found)
assert summary.get("duplicate_options") == 1, summary
assert summary.get("distractor_count") == 1, summary

rows = {row["code"]: row for row in Q._findings_with_repair_paths(content, found)}
assert rows["duplicate_options"]["repair_paths"] == [["pages", 4, "options"]], rows
assert rows["distractor_count"]["repair_paths"] == [], rows
# The residual loop's own precondition: the one resolvable path is a list, which
# is why it was skipped before this fix.
assert isinstance(Q._get_path(content, ["pages", 4, "options"]), list)

# The page genuinely lost a choice, so nothing may be rebuilt from its own text.
assert R.rebuild_mcq_option_set(content["pages"][4]) is None

# ---------------------------------------------------------------------------
# 2. Bounded exact repair: the model returns the complete tuple, it is validated
#    against the auditor, and both blockers clear.
# ---------------------------------------------------------------------------

orig_call = Q._call_review
calls = []


def fake_call(**kwargs):
    calls.append(kwargs["stage"])
    payload = kwargs["payload"]
    assert kwargs["response_schema"] is Q._MCQ_OPTION_SET_REPAIR_SCHEMA
    assert payload["current_answer"] == ANSWER
    assert payload["path"] == ["pages", 4]
    assert sorted(f["code"] for f in payload["blockers"]) == [
        "distractor_count", "duplicate_options",
    ], payload["blockers"]
    return {
        "answer": ANSWER,
        "options": [ANSWER, KEPT[0], KEPT[1], SUPPLIED],
        "distractors": [KEPT[0], KEPT[1], SUPPLIED],
        "reason": "Replace the repeated key with a distinct wrong conjugation.",
    }


topic = {"id": "negation", "title": "Simple Negation and Question Formation",
         "content": content, "is_assessment": False}
try:
    Q._call_review = fake_call
    applied = Q._repair_mcq_structural_blockers(
        topic=topic, language="Spanish", level="A1", track="tr",
        budget=Q.ReviewBudget(999), blockers=found,
    )
finally:
    Q._call_review = orig_call

page = content["pages"][4]
assert applied == 1, applied
assert calls == [
    "review_mcq_option_set:Simple Negation and Question Formation:pages.4"
], calls

assert len(page["options"]) == 4, page["options"]
identities = [A.option_identity(o) for o in page["options"]]
assert len(set(identities)) == 4, page["options"]
assert A.option_identity(page["answer"]) in identities
assert page["answer"] == ANSWER
# `distractors` was derived, not stored: the repair must not invent the field.
assert "distractors" not in page, page
derived = [o for o in page["options"] if A.option_identity(o) != A.option_identity(ANSWER)]
assert len(derived) == 3 and len(set(map(A.option_identity, derived))) == 3, derived

after = blockers_of(content)
assert "duplicate_options" not in after, after
assert "distractor_count" not in after, after
assert not after, after

# ---------------------------------------------------------------------------
# 3. A healthy MCQ is a no-op, and repeating the repair is idempotent.
# ---------------------------------------------------------------------------

healthy = {
    "type": "mcq",
    "title": "Negation practice",
    "prompt": "¿Cómo se niega «Hablo francés»?",
    "answer": ANSWER,
    "options": [KEPT[0], ANSWER, KEPT[1], SUPPLIED],
    "distractors": [KEPT[0], KEPT[1], SUPPLIED],
    "why_tr": "Olumsuzluk «no» ile kurulur.",
}
assert not A.blocking(A.audit_item(healthy, language="Spanish", track="tr"))

rebuilt = R.rebuild_mcq_option_set(healthy)
assert rebuilt == {"answer": ANSWER, "options": healthy["options"],
                   "distractors": healthy["distractors"]}, rebuilt

snapshot = dict(healthy)
healthy_topic = {"id": "ok", "title": "Healthy", "content": {"pages": [healthy]},
                 "is_assessment": False}


def refuse_call(**kwargs):
    raise AssertionError(f"a healthy MCQ must not cost a model call: {kwargs['stage']}")


try:
    Q._call_review = refuse_call
    # Re-running the repair over the already-repaired production page is also a
    # no-op, and must not spend a second call.
    assert Q._repair_mcq_structural_blockers(
        topic=healthy_topic, language="Spanish", level="A1", track="tr",
        budget=Q.ReviewBudget(999),
        blockers=A.blocking(A.audit_lesson({"pages": [healthy]},
                                           language="Spanish", track="tr")),
    ) == 0
    assert Q._repair_mcq_structural_blockers(
        topic=topic, language="Spanish", level="A1", track="tr",
        budget=Q.ReviewBudget(999), blockers=found,
    ) == 0
finally:
    Q._call_review = orig_call

assert healthy == snapshot, healthy
assert not A.blocking(A.audit_item(healthy, language="Spanish", track="tr"))

# ---------------------------------------------------------------------------
# 4. Deterministic path: when the page still carries three usable wrong
#    choices, the tuple is rebuilt with no model call at all.
# ---------------------------------------------------------------------------

deterministic = {
    "type": "mcq",
    "title": "Negation practice",
    "prompt": "¿Cómo se niega «Hablo francés»?",
    "answer": ANSWER,
    # Five slots, one repeat: the text to rebuild a clean four-way choice is
    # already on the page.
    "options": [KEPT[0], ANSWER, ANSWER, KEPT[1], SUPPLIED],
    "why_tr": "Olumsuzluk «no» ile kurulur.",
}
det_content = {"pages": [deterministic]}
det_found = A.blocking(A.audit_lesson(det_content, language="Spanish", track="tr"))
assert A.summarise(det_found).get("duplicate_options") == 1

try:
    Q._call_review = refuse_call
    assert Q._repair_mcq_structural_blockers(
        topic={"id": "det", "title": "Deterministic", "content": det_content,
               "is_assessment": False},
        language="Spanish", level="A1", track="tr",
        budget=Q.ReviewBudget(999), blockers=det_found,
    ) == 1
finally:
    Q._call_review = orig_call

assert deterministic["options"] == [KEPT[0], ANSWER, KEPT[1], SUPPLIED], deterministic["options"]
assert not A.blocking(A.audit_lesson(det_content, language="Spanish", track="tr"))

# ---------------------------------------------------------------------------
# 5. Fail-closed: an inconsistent tuple from the model is refused, never written.
# ---------------------------------------------------------------------------

broken = negation_lesson()
broken_topic = {"id": "negation", "title": "Simple Negation and Question Formation",
                "content": broken, "is_assessment": False}
broken_found = A.blocking(A.audit_lesson(broken, language="Spanish", track="tr"))
before = dict(broken["pages"][4])

for bad in (
    {"answer": ANSWER, "options": [ANSWER, KEPT[0], KEPT[1], KEPT[1]],
     "distractors": [KEPT[0], KEPT[1], KEPT[1]], "reason": "still duplicated"},
    {"answer": ANSWER, "options": [ANSWER, KEPT[0], KEPT[1], SUPPLIED],
     "distractors": [KEPT[0], KEPT[1], ANSWER], "reason": "distractors disagree"},
    {"answer": "Nunca hablo francés.", "options": ["Nunca hablo francés.", KEPT[0],
                                                   KEPT[1], SUPPLIED],
     "distractors": [KEPT[0], KEPT[1], SUPPLIED], "reason": "silently rekeyed"},
):
    try:
        Q._call_review = lambda _bad=bad, **kwargs: _bad
        Q._repair_mcq_structural_blockers(
            topic=broken_topic, language="Spanish", level="A1", track="tr",
            budget=Q.ReviewBudget(999), blockers=broken_found,
        )
    except Q.QualityGateError:
        pass
    else:
        raise AssertionError(f"inconsistent tuple was accepted: {bad['reason']}")
    finally:
        Q._call_review = orig_call
    assert broken["pages"][4] == before, broken["pages"][4]

# ---------------------------------------------------------------------------
# 6. End to end through the production entry point: repair_deterministic_preflight
#    used to raise "deterministic blocker has no exact repair path" / "blockers
#    remain after preflight exact repair" on this page. It now clears it with one
#    scoped call and never reaches the broad repair.
# ---------------------------------------------------------------------------

e2e = negation_lesson()
e2e_topic = {"id": "negation", "title": "Simple Negation and Question Formation",
             "content": e2e, "is_assessment": False}
e2e_calls = []


def preflight_call(**kwargs):
    e2e_calls.append(kwargs["stage"])
    if kwargs["stage"].startswith("review_mcq_option_set:"):
        return {
            "answer": ANSWER,
            "options": [ANSWER, KEPT[0], KEPT[1], SUPPLIED],
            "distractors": [KEPT[0], KEPT[1], SUPPLIED],
            "reason": "Replace the repeated key with a distinct wrong conjugation.",
        }
    raise AssertionError(f"unexpected preflight call: {kwargs['stage']}")


try:
    Q._call_review = preflight_call
    e2e_applied = Q.repair_deterministic_preflight(
        units=[{"title": "Everyday Basics", "topics": [e2e_topic]}],
        language="Spanish", level="A1", track="tr", budget=Q.ReviewBudget(999),
    )
finally:
    Q._call_review = orig_call

assert e2e_applied == 1, e2e_applied
assert e2e_calls == [
    "review_mcq_option_set:Simple Negation and Question Formation:pages.4"
], e2e_calls
assert not blockers_of(e2e), blockers_of(e2e)
assert len(set(map(A.option_identity, e2e["pages"][4]["options"]))) == 4

print("[MCQ-STRUCTURAL] duplicate_options + distractor_count repaired as one "
      "atomic tuple; healthy items no-op; inconsistent tuples refused; "
      "preflight clears the production page without the broad repair call")
