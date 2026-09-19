#!/usr/bin/env python3
"""Regression: publication retries resume only the implicated unit.

Covers the production failure where:
  refusal: People and Nationalities ... Q9
  repair:  Unit Assessment: Family, Home, and Description   (WRONG UNIT)

A unit-title refusal must route feedback and the next semantic pass to that
unit only. Final global integrity still sees the full classroom.
"""

from __future__ import annotations

import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")

from services.authoring import quality_gate as Q  # noqa: E402
from services.legacy import pdf_pipeline as P  # noqa: E402


def assessment(topic_id, unit_name):
    return {
        "id": topic_id,
        "title": f"Unit Assessment: {unit_name}",
        "type": "unit_assessment",
        "is_assessment": True,
        "content": {
            "pages": [{
                "type": "mcq",
                "title": "Question 9",
                "title_tr": "Soru 9",
                "prompt": "María es de España. ¿Cuál es la forma correcta?",
                "answer": "española",
                "options": ["española", "español", "españoles", "españolas"],
                "distractors": ["español", "españoles", "españolas"],
                "explanation": "María is a feminine name, so «española» is used.",
                "explanation_tr": "María kadın ismidir; bu yüzden «española» kullanılır.",
            }]
        },
    }


people_assessment = assessment("assess-people", "People and Nationalities")
family_assessment = assessment("assess-family", "Family, Home, and Description")

units = [
    {
        "title": "People and Nationalities",
        "topics": [people_assessment],
    },
    {
        "title": "Family, Home, and Description",
        "topics": [family_assessment],
    },
]

error = (
    "People and Nationalities: renderer-contract blockers remain after targeted "
    "repair — Q9 tr: answer depends on gender inferred from a personal name; "
    "Q9 en: answer depends on gender inferred from a personal name"
)

# Outer resume scope: a unit-title refusal resolves to exactly that unit.
assert P._publication_retry_unit_titles(units, error) == [
    "People and Nationalities"
]

orig_call = Q._call_review
seen = []


def fake_call(**kwargs):
    seen.append(kwargs["stage"])
    payload = kwargs["payload"]
    assert payload["topic_id"] == "assess-people", payload["topic_id"]
    assert payload["topic_title"] == "Unit Assessment: People and Nationalities"
    page = people_assessment["content"]["pages"][0]
    return {
        "topic_id": "assess-people",
        "patches": [
            {
                "path": ["pages", "0", "prompt"],
                "old": page["prompt"],
                "value": (
                    "Una mujer de España responde. ¿Cuál es la forma correcta?"
                ),
                "reason": "Make the grammatical controller explicit.",
            },
            {
                "path": ["pages", "0", "explanation"],
                "old": page["explanation"],
                "value": (
                    "The stem explicitly identifies a woman; «española» is "
                    "the matching feminine singular nationality form."
                ),
                "reason": "Remove name-based identity inference.",
            },
            {
                "path": ["pages", "0", "explanation_tr"],
                "old": page["explanation_tr"],
                "value": (
                    "Soru kadın bir konuşmacıyı açıkça belirtir; «española» "
                    "uygun dişil tekil milliyet biçimidir."
                ),
                "reason": "Remove name-based identity inference.",
            },
        ],
    }


try:
    Q._call_review = fake_call
    changed = Q.repair_publication_refusal_feedback(
        units=units,
        language="Spanish",
        level="A1",
        track="tr",
        publication_error=error,
        retry_attempt=3,
        budget=Q.ReviewBudget(1.0),
    )
finally:
    Q._call_review = orig_call

assert changed >= 1, changed
assert seen == [
    "publication_feedback_retry:3:Unit Assessment: People and Nationalities"
], seen

# The unrelated unit must remain byte-for-byte on the old bad fixture. If the
# router ever falls back to "dirtiest topic in course" again, this catches it.
family_page = family_assessment["content"]["pages"][0]
assert family_page["prompt"] == "María es de España. ¿Cuál es la forma correcta?"
assert "feminine name" in family_page["explanation"]

# Structural proof: semantic runners use active_units while final/global proof
# deliberately uses all_units.
gate_source = inspect.getsource(P._run_publication_quality_gate)
assert gate_source.count("units=active_units") >= 5
assert 'reviewed_units = [{"title": u["title"], "topics": u["topics"]} for u in all_units]' in gate_source
assert "unit_titles=None" in inspect.signature(P._run_publication_quality_gate).__str__()

outer_source = inspect.getsource(P._run_publication_until_ready)
assert "unit_titles=retry_unit_titles" in outer_source
assert "_publication_retry_unit_titles" in outer_source

print(
    "[PUBLICATION-RESUME-SCOPE] named-unit refusal repairs/reviews only that "
    "unit; global integrity remains course-wide"
)
