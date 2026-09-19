#!/usr/bin/env python3
"""A repaired page must not re-buy the whole unit's semantic review.

The publication self-heal loop repairs content and then runs the FULL quality
gate again. That is the right thing to prove and the wrong thing to pay for:
the rationale payload was built for the UNIT, so one repaired page in one
lesson changed the payload and the unit's entire rationale review was bought a
second time — ten items re-judged to re-learn one. A Spanish A1 build that
healed twice reached about $0.40.

The verdict is already item-scoped: `_require_rationale_quality_proof` demands
`grounded` and `rationale_specific` per item_id, and `attest_rationale_pages`
records the exact semantic surface each verdict covered. So an item carrying
that proof has nothing to learn from being sent again, and the stage now sends
only unproven items.

Measured here end to end, six units of five lessons each, with a recording stub
in place of the provider.
"""

from __future__ import annotations
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (ROOT, os.path.join(ROOT, "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)
os.environ.setdefault("OPENROUTER_API_KEY", "regression-key-never-used")
os.environ.setdefault("AULAAI_DATA_DIR", tempfile.mkdtemp(prefix="aulaai-heal-"))
sys.argv = [sys.argv[0]]

import measure_review_cost as M  # noqa: E402
from services.authoring import quality_gate as Q  # noqa: E402
from services.authoring import transport as T  # noqa: E402

FAILURES = []


def check(condition, label):
    if not condition:
        FAILURES.append(label)
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")


def run(units):
    recorder = M.Recorder()
    original = T.call_model
    T.call_model = recorder
    budget = Q.ReviewBudget(10.0)
    try:
        for unit in units:
            for stage in (
                lambda u: Q.review_unit_lessons(
                    unit_title=u["title"], topics=u["lessons"], language="Spanish",
                    level="A1", track="tr", budget=budget,
                    unit_topic_titles=[t["title"] for t in u["lessons"]]),
                lambda u: Q.review_unit_risk_claims(
                    unit_title=u["title"], topics=u["lessons"], language="Spanish",
                    level="A1", track="tr", budget=budget),
                lambda u: Q.review_unit_assessment(
                    unit_title=u["title"], assessment_topic=u["assessment"],
                    lesson_topics=u["lessons"], language="Spanish", level="A1",
                    track="tr", budget=budget),
                lambda u: Q.review_unit_mcq_rationales(
                    unit_title=u["title"], topics=u["topics"], language="Spanish",
                    level="A1", track="tr", budget=budget),
            ):
                try:
                    stage(unit)
                except Q.QualityGateError:
                    pass
    finally:
        T.call_model = original
    return sum(recorder.calls.values())


def reopen(units):
    """What the self-heal loop does: run the whole gate again from scratch."""
    for unit in units:
        for topic in unit["lessons"]:
            topic.pop(Q._LESSON_REVIEW_DONE_KEY, None)
            topic.pop(Q._RISK_REVIEW_DONE_KEY, None)


units = [M.build_unit(i, 5) for i in range(6)]

print("[1] the first pass reviews everything")
first = run(units)
check(first > 50, f"a cold classroom is fully reviewed ({first} calls)")

print("\n[2] a self-heal rerun over unchanged content is free")
reopen(units)
unchanged = run(units)
check(unchanged == 0,
      f"nothing is re-bought when nothing changed ({unchanged} calls)")

print("\n[3] and a repaired page pays for itself, not for the classroom")
units[0]["lessons"][0]["content"]["pages"][1]["rules"][0]["rule"] = (
    "Adjectives usually agree in gender and number."
)
reopen(units)
repaired = run(units)
check(repaired > 0, f"the changed topic IS re-reviewed ({repaired} calls)")
check(repaired <= 6,
      f"but only the changed topic ({repaired} calls, was {first} before)")
check(repaired < first / 10,
      f"an order of magnitude below a full pass ({repaired} vs {first})")

print("\n[4] the proof that allows this is per item and content-bound")
page = units[0]["lessons"][0]["content"]["pages"][1]
check(hasattr(Q, "_rationale_proof_covers"), "per-item proof lookup exists")
before = Q._rationale_semantic_digest(page)
page["rules"][0]["rule"] = "Something else entirely."
check(Q._rationale_semantic_digest(page) == before
      or not Q._rationale_proof_covers(page),
      "an edited item does not keep a proof it no longer matches")

print()
if FAILURES:
    print(f"FAILED ({len(FAILURES)}):")
    for label in FAILURES:
        print(f"  - {label}")
    sys.exit(1)
print("all self-heal incremental cost checks passed")
