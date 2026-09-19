#!/usr/bin/env python3
"""Regression: a would-be publication refusal becomes the next repair prompt.

The production incident was:
Family Members and Possessive Adjectives / pages[4] /
"answer depends on gender inferred from a personal name".

The first repair changed the stem while leaving the Turkish rationale's
"'Abuela' ismi dişil..." trigger intact. This test proves the next repair call
receives the EXACT refusal text and may patch the actual coupled field, after
which the unchanged renderer contract passes.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")

from services.authoring import quality_gate as Q  # noqa: E402
from services.authoring import render_contract as RC  # noqa: E402


ERROR = (
    "Family Members and Possessive Adjectives: publication blockers are not "
    "converging; unresolved=[{'code': 'render_contract', 'where': 'pages[4]', "
    "'reason': 'answer depends on gender inferred from a personal name'}]"
)

topic = {
    "id": "family-pos",
    "title": "Family Members and Possessive Adjectives",
    "type": "grammar",
    "is_assessment": False,
    "content": {
        "pages": [
            {"type": "text", "text": "x", "text_tr": "x"},
            {"type": "text", "text": "x", "text_tr": "x"},
            {"type": "text", "text": "x", "text_tr": "x"},
            {"type": "text", "text": "x", "text_tr": "x"},
            {
                "type": "mcq",
                "title": "Practice: First-Person Plural Possessive",
                "title_tr": "Alıştırma",
                "prompt": (
                    'Completa la frase: "Esta mujer es ________ abuela '
                    'y vive con nosotros."'
                ),
                "text": (
                    "Choose the form of 'nuestro' that correctly agrees with "
                    "the feminine singular noun."
                ),
                "text_tr": (
                    "Dişil ve tekil isimle doğru şekilde uyum sağlayan "
                    "'nuestro' biçimini seçiniz."
                ),
                "answer": "nuestra",
                "options": ["nuestra", "nuestro", "nuestras", "nuestros"],
                "distractors": ["nuestro", "nuestras", "nuestros"],
                "explanation": (
                    "The noun 'abuela' is feminine and singular, so the matching "
                    "possessive adjective is 'nuestra'."
                ),
                "explanation_tr": (
                    "'Abuela' ismi dişil ve tekil olduğu için onunla uyumlu olan "
                    "iyelik sıfatı 'nuestra'dır."
                ),
            },
        ]
    },
}
units = [{"title": "Family", "topics": [topic]}]

assert RC.hidden_world_reason(topic["content"]["pages"][4]) == RC.NAME_GENDER_REASON

orig_call = Q._call_review
seen = []


def fake_call(**kwargs):
    payload = kwargs["payload"]
    seen.append((kwargs["stage"], payload["publication_error"]))

    assert payload["topic_title"] == topic["title"]
    assert payload["renderer_diagnostics"], payload

    if payload["retry_attempt"] == 2:
        assert payload["publication_error"] == ERROR
        assert any(
            row.get("reason") == RC.NAME_GENDER_REASON
            for row in payload["validator_blockers"]
        )
        current = topic["content"]["pages"][4]["explanation_tr"]
        return {
            "topic_id": topic["id"],
            "patches": [{
                "path": ["pages", "4", "explanation_tr"],
                "old": current,
                "value": (
                    "«abuela» sözcüğü dişil ve tekildir; bu nedenle onunla uyumlu "
                    "birinci çoğul şahıs iyelik sıfatı «nuestra»dır."
                ),
                "reason": (
                    "The rationale now names a lexical word/noun unambiguously "
                    "instead of wording that can mean a personal name."
                ),
            }],
        }

    assert payload["retry_attempt"] == 3
    assert (
        "answer depends on an identity fact inferred from a biographical one"
        in payload["publication_error"]
    )
    current_prompt = topic["content"]["pages"][4]["prompt"]
    return {
        "topic_id": topic["id"],
        "patches": [{
            "path": ["pages", "4", "prompt"],
            "old": current_prompt,
            "value": 'Completa la frase: "Esta mujer es ________ abuela."',
            "reason": (
                "Remove the unrelated biography marker while keeping the "
                "feminine singular grammatical controller explicit."
            ),
        }],
    }


try:
    Q._call_review = fake_call

    changed = Q.repair_publication_refusal_feedback(
        units=units,
        language="Spanish",
        level="A1",
        track="tr",
        publication_error=ERROR,
        retry_attempt=2,
        budget=Q.ReviewBudget(1.0),
    )
    assert changed == 1, changed

    page = topic["content"]["pages"][4]
    # The first would-be user error is gone. If another independent validator
    # predicate now fires, that becomes the next retry's exact input rather
    # than a terminal result.
    first_remaining = RC.hidden_world_reason(page)
    assert first_remaining != RC.NAME_GENDER_REASON, RC.explain_hidden_world(page)
    assert first_remaining == (
        "answer depends on an identity fact inferred from a biographical one"
    ), RC.explain_hidden_world(page)

    error2 = (
        "Family Members and Possessive Adjectives: publication blockers are "
        "not converging; unresolved=[{'code': 'render_contract', "
        "'where': 'pages[4]', 'reason': '"
        + first_remaining
        + "'}]"
    )
    changed2 = Q.repair_publication_refusal_feedback(
        units=units,
        language="Spanish",
        level="A1",
        track="tr",
        publication_error=error2,
        retry_attempt=3,
        budget=Q.ReviewBudget(1.0),
    )
    assert changed2 == 1, changed2
finally:
    Q._call_review = orig_call

page = topic["content"]["pages"][4]
assert RC.hidden_world_reason(page) == "", RC.explain_hidden_world(page)
assert RC.page_is_renderable(page, True)[0]
assert RC.page_is_renderable(page, False)[0]
assert seen[0][0].startswith(
    "publication_feedback_retry:2:Family Members and Possessive Adjectives"
)
assert seen[0][1] == ERROR
assert "identity fact inferred from a biographical one" in seen[1][1]
assert page["answer"] == "nuestra"
assert page["options"] == ["nuestra", "nuestro", "nuestras", "nuestros"]
print(
    "[PUBLICATION-FEEDBACK] refusal chain is fed back verbatim until the "
    "unchanged renderer contract is clean"
)


# The outer pipeline must keep content refusals in quality_review rather than
# writing the old terminal failed state before the retry prompt runs.
from services.legacy import pdf_pipeline as P  # noqa: E402
import inspect  # noqa: E402

source = inspect.getsource(P._run_publication_until_ready)
assert "publication_error = str(failure)" in source
assert "repair_publication_refusal_feedback" in source
assert "build_stage='quality_review'" in source
assert "UPDATE courses SET is_building=0, build_stage='failed'" not in source
assert "mark_failed(" not in source
assert "while True" in source
print("[PUBLICATION-FEEDBACK] outer publication loop has no content-retry ceiling")

# The lecturer's review-only retry endpoint must not bypass the self-healing
# loop. That legacy bypass was the production path that still surfaced
# "Publication refused: ..." after the loop itself had been fixed.
import server as S  # noqa: E402
server_source = inspect.getsource(S.APIHandler._retry_classroom_publication)
assert "_run_publication_until_ready" in server_source
assert "_run_publication_quality_gate" not in server_source
assert "PS.mark_failed(" not in server_source
print("[PUBLICATION-FEEDBACK] review-only endpoint cannot terminally refuse content")