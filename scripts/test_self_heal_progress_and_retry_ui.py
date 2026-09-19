#!/usr/bin/env python3
"""Regression: self-heal progress is logical, and retry UI keeps course totals."""

from __future__ import annotations

import copy
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")

from services.authoring import quality_gate as Q  # noqa: E402
from services.legacy import pdf_pipeline as P  # noqa: E402


# ---------------------------------------------------------------------------
# 1) Moving the same logical blocker to a different path is NOT progress.
# ---------------------------------------------------------------------------
topic = {
    "id": "fixture",
    "title": "Fixture Topic",
    "type": "grammar",
    "is_assessment": False,
    "content": {
        "pages": [
            {"type": "text", "text": "BAD", "text_tr": "Kötü"},
            {"type": "text", "text": "SECOND", "text_tr": "İkinci"},
        ]
    },
}
units = [{"title": "Fixture Unit", "topics": [topic]}]
before = copy.deepcopy(topic["content"])

orig_detect = Q._detect_topic_blockers
orig_call = Q._call_review
orig_repair = Q.R.repair_lesson


def fake_detect(current_topic, *, language, track, canonical):
    first = current_topic["content"]["pages"][0]["text"]
    # Before patch: same logical class at page 0.
    if first == "BAD":
        return [{
            "kind": "render",
            "code": "render_contract",
            "where": "pages[0]",
            "reason": "same logical renderer predicate",
            "strategies": ["render_rescue"],
        }]
    # After patch: the model merely moved/preserved the SAME logical class at
    # another location. This must not be considered progress.
    return [{
        "kind": "render",
        "code": "render_contract",
        "where": "pages[1]",
        "reason": "same logical renderer predicate",
        "strategies": ["render_rescue"],
    }]


def fake_call(**kwargs):
    payload = kwargs["payload"]
    return {
        "topic_id": topic["id"],
        "patches": [{
            "path": ["pages", "0", "text"],
            "old": "BAD",
            "value": "CHANGED",
            "reason": "fixture candidate that only moves the same blocker class",
        }],
    }


try:
    Q._detect_topic_blockers = fake_detect
    Q._call_review = fake_call
    Q.R.repair_lesson = lambda content, language: content

    changed = Q.repair_publication_refusal_feedback(
        units=units,
        language="Spanish",
        level="A1",
        track="tr",
        publication_error=(
            "Fixture Topic: publication blockers are not converging; "
            "unresolved=[{'code':'render_contract','where':'pages[0]',"
            "'reason':'same logical renderer predicate'}]"
        ),
        retry_attempt=2,
        budget=Q.ReviewBudget(1.0),
    )
finally:
    Q._detect_topic_blockers = orig_detect
    Q._call_review = orig_call
    Q.R.repair_lesson = orig_repair

assert changed == 0, changed
assert topic["content"] == before, topic["content"]
print("[SELF-HEAL-PROGRESS] 1->1 same code+reason is rejected, even if path changes")


# ---------------------------------------------------------------------------
# 2) A one-unit semantic resume must keep the classroom denominator at six.
# ---------------------------------------------------------------------------
gate_source = inspect.getsource(P._run_publication_quality_gate)
assert "display_total_units = len(all_units)" in gate_source
assert "display_completed_base" in gate_source
assert "def _display_progress(done: int)" in gate_source
assert "pedagogical risks 0/{len(active_units)}" not in gate_source
assert "pronunciation 0/{len(active_units)}" not in gate_source
assert "assessments 0/{len(active_units)}" not in gate_source
assert "rationale grounding 0/{len(active_units)}" not in gate_source
assert "lessons {done}/{total}" not in gate_source
assert "pedagogical risks {done}/{total}" not in gate_source
assert "pronunciation {done}/{total}" not in gate_source
assert "assessments {done}/{total}" not in gate_source
assert "rationale grounding {done}/{total}" not in gate_source
print("[SELF-HEAL-PROGRESS] retry subset keeps global x/6 UI progress")


# ---------------------------------------------------------------------------
# 3) After one proven targeted repair, visible blockers are swept BEFORE
#    another semantic resume, preventing one-unit-per-retry discovery.
# ---------------------------------------------------------------------------
outer_source = inspect.getsource(P._run_publication_until_ready)
persist_pos = outer_source.index("if changed:")
sweep_pos = outer_source.index("repair_final_publication_blockers", persist_pos)
db_pos = outer_source.index("with db_connection() as db:", sweep_pos)
assert persist_pos < sweep_pos < db_pos
assert "repair_final_publication_blockers" in outer_source
assert "sweep_units = copy.deepcopy(units)" in outer_source
assert "before semantic resume" in outer_source
print("[SELF-HEAL-PROGRESS] course-wide visible blocker sweep runs before semantic resume")