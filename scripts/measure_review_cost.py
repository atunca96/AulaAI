#!/usr/bin/env python3
"""What one unit actually costs to review, measured rather than estimated.

The product's complaint is that review rivals generation in money and beats it
in wall clock. `budget.project_classroom_cost` says what GENERATION should cost;
nothing said what REVIEW costs, so the ceiling ($0.58 hard, $0.22 nominal) was
set against a number nobody had. This runs the five real review stages over a
real unit with a recording stub in place of the provider, and reports the calls
each stage makes.

It is a measurement tool, not a check: it asserts nothing about content and is
not part of the build. Run it before and after a change that is supposed to
remove work, and compare.

    python3 scripts/measure_review_cost.py [--lessons N] [--units N]
"""

from __future__ import annotations
import argparse
import copy
import json
import os
import sys
import tempfile
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault("OPENROUTER_API_KEY", "measurement-key-never-used")
os.environ.setdefault("AULAAI_DATA_DIR", tempfile.mkdtemp(prefix="aulaai-measure-"))

from services.authoring import budget as B  # noqa: E402
from services.authoring import quality_gate as Q  # noqa: E402
from services.authoring import transport as T  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scripts"))
_QG_TESTS = os.path.join(ROOT, "scripts", "test_quality_gate.py")
_fixtures = {"__file__": _QG_TESTS, "__name__": "test_quality_gate_fixtures"}
exec(  # noqa: S102 - reuse the build's own fixtures rather than a second copy
    compile(
        open(_QG_TESTS, encoding="utf-8").read()
        .split("def test_transport_strict_schema")[0],
        "test_quality_gate_fixtures", "exec",
    ),
    _fixtures,
)
lesson_fixture = _fixtures["lesson_fixture"]
assessment_fixture = _fixtures["assessment_fixture"]
assessment_quality_checks = _fixtures["assessment_quality_checks"]


def build_unit(index: int, lessons: int):
    topics = []
    for n in range(lessons):
        content = copy.deepcopy(lesson_fixture())
        # The quality-gate fixture deliberately ships a corrupt transcription so
        # its own audit check has something to catch. This harness measures the
        # CLEAN floor, so repair it here rather than measuring one topic's
        # convergence over and over.
        for page in content["pages"]:
            for item in page.get("items") or []:
                if item.get("term") == "once":
                    item["phonetic"] = "[ˈonθe]"
        topics.append({
            "id": f"u{index}t{n}", "title": f"Topic {index}.{n}",
            "type": "lesson", "content": content,
        })
    assessment = {
        "id": f"u{index}a", "title": f"Unit {index} Assessment",
        "type": "assessment", "content": copy.deepcopy(assessment_fixture()),
    }
    return {"title": f"Unit {index}", "lessons": topics,
            "assessment": assessment, "topics": topics + [assessment]}


class Recorder:
    """Stands in for the provider and answers each schema minimally-validly."""

    def __init__(self):
        self.calls = Counter()
        self.stages = []

    def __call__(self, messages, **kwargs):
        payload = json.loads(messages[-1]["content"])
        name = str(kwargs.get("response_name") or "")
        self.calls[name] += 1
        self.stages.append(name)
        return T.Response(
            data=self._answer(name, payload),
            input_tokens=900, output_tokens=140, cost=0.0,
            model=kwargs.get("model", ""),
        )

    def _answer(self, name, payload):
        # Every reviewer is answered with "nothing to change", which is the
        # cheapest TRUE path: it measures the floor, the calls a clean unit
        # cannot avoid. A unit needing repairs costs strictly more.
        if "assessment" in name:
            return {"checked_questions": list(range(1, 11)),
                    "quality_checks": assessment_quality_checks(), "patches": []}
        if "rationale" in name:
            ids = [row["item_id"] for row in (payload.get("items") or [])]
            return {"checked_ids": ids,
                    "quality_checks": [
                        {"item_id": i, "grounded": True, "rationale_specific": True,
                         "reason": "measurement stub"} for i in ids],
                    "patches": []}
        if "risk" in name or "pedagogical" in name:
            topic = (payload.get("topics") or [{}])[0]
            records = topic.get("records") or []
            absolute = list(topic.get("absolute_ids") or [])
            return {"topic_id": topic.get("topic_id", ""),
                    "checked_ids": [f"r{i}" for i, _ in enumerate(records)],
                    "scope_checked_ids": absolute,
                    "categorical_ids": absolute,
                    "scope_checks": [
                        {"record_id": rid, "counterexample_tested": True,
                         "final_scope_safe": True, "reason": "measurement stub"}
                        for rid in absolute],
                    "patches": []}
        if "categorical" in name or "escalation" in name:
            # Answer every claim the payload carries, wherever it sits, so a
            # coverage mismatch here is the product's contract and never the
            # harness failing to reply.
            claims = []

            def collect(node):
                if isinstance(node, dict):
                    if "claim_id" in node:
                        claims.append(node)
                    for value in node.values():
                        collect(value)
                elif isinstance(node, list):
                    for value in node:
                        collect(value)

            collect(payload)
            # The contract reads `results`, and `value` must equal `current`
            # for an "ok" verdict.
            return {"results": [{"claim_id": c["claim_id"], "verdict": "ok",
                                 "value": c.get("current", ""),
                                 "reason": "stub"} for c in claims]}
        if "notation" in name:
            return {"checked_ids": [r.get("item_id") for r in (payload.get("items") or [])],
                    "patches": []}
        topics = payload.get("topics") or []
        return {"topics": [{"topic_id": t.get("topic_id", ""), "verdict": "ok",
                            "patches": []} for t in topics]}


def run(lessons: int, units: int):
    rec = Recorder()
    original = T.call_model
    T.call_model = rec
    budget = Q.ReviewBudget(10.0)
    started = time.perf_counter()
    stage_calls = {}
    try:
        for index in range(units):
            unit = build_unit(index, lessons)
            for label, fn in (
                ("lessons", lambda u: Q.review_unit_lessons(
                    unit_title=u["title"], topics=u["lessons"], language="Spanish",
                    level="A1", track="tr", budget=budget,
                    unit_topic_titles=[t["title"] for t in u["lessons"]])),
                ("risk", lambda u: Q.review_unit_risk_claims(
                    unit_title=u["title"], topics=u["lessons"], language="Spanish",
                    level="A1", track="tr", budget=budget)),
                ("assessment", lambda u: Q.review_unit_assessment(
                    unit_title=u["title"], assessment_topic=u["assessment"],
                    lesson_topics=u["lessons"], language="Spanish", level="A1",
                    track="tr", budget=budget)),
                ("rationales", lambda u: Q.review_unit_mcq_rationales(
                    unit_title=u["title"], topics=u["topics"], language="Spanish",
                    level="A1", track="tr", budget=budget)),
                ("notation", lambda u: Q.review_unit_complex_notation(
                    unit_title=u["title"], topics=u["lessons"], language="Spanish",
                    level="A1", budget=budget)),
            ):
                before = sum(rec.calls.values())
                try:
                    fn(unit)
                except Q.QualityGateError as exc:
                    print(f"  [{label}] QualityGateError: {str(exc)[:110]}")
                after = sum(rec.calls.values())
                stage_calls[label] = stage_calls.get(label, 0) + (after - before)
    finally:
        T.call_model = original
    return rec, stage_calls, time.perf_counter() - started


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lessons", type=int, default=5)
    ap.add_argument("--units", type=int, default=3)
    args = ap.parse_args()

    rec, stage_calls, elapsed = run(args.lessons, args.units)
    total_calls = sum(rec.calls.values())
    gen = B.project_classroom_cost(
        lessons=args.lessons * args.units, units=args.units,
        items_per_unit=10, pages_per_lesson=5,
    )
    gen_calls = args.lessons * args.units + args.units + 1  # lessons + assessments + curriculum

    print()
    print(f"UNIT SHAPE: {args.units} unit(s) x {args.lessons} lesson(s) + 1 assessment each")
    print()
    print("REVIEW CALLS BY STAGE (clean content — this is the FLOOR)")
    for label, count in stage_calls.items():
        print(f"  {label:12} {count:4d}")
    print(f"  {'TOTAL':12} {total_calls:4d}")
    print()
    print("BY RESPONSE CONTRACT")
    for name, count in rec.calls.most_common():
        print(f"  {count:4d}  {name}")
    print()
    print("AGAINST GENERATION")
    print(f"  generation calls (projected)  {gen_calls:4d}")
    print(f"  review calls     (measured)   {total_calls:4d}")
    if gen_calls:
        print(f"  ratio                         {total_calls / gen_calls:.2f}x")
    print(f"  generation cost  (projected)  ${gen['total']:.4f}")
    print(f"  measured wall clock (stubbed) {elapsed:.2f}s"
          "   <- provider latency excluded; call COUNT is the signal")


if __name__ == "__main__":
    main()
