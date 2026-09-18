#!/usr/bin/env python3
"""Regression: renderer-contract assessment blockers are repaired before publication.

Provider-free. The model call is stubbed so the test proves orchestration:
Luna may miss a deterministic render blocker; the exact blocker is then handed
to Terra, which patches the existing question in place. Ten questions remain.
"""

from __future__ import annotations

import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q


def page(prompt: str, n: int, explanation: str = "The taught fact determines the answer."):
    return {
        "type": "mcq",
        "title": f"Question {n}",
        "title_tr": f"Soru {n}",
        "prompt": prompt,
        "answer": "turca" if n == 1 else "opción a",
        "options": (["turca", "española", "francesa", "alemana"] if n == 1
                    else ["opción a", "opción b", "opción c", "opción d"]),
        "distractors": (["española", "francesa", "alemana"] if n == 1
                        else ["opción b", "opción c", "opción d"]),
        "explanation": explanation,
        "why": explanation,
        "why_tr": "Öğretilen bilgi doğru cevabı belirler.",
    }


bad_prompt = "María vive en Turquía. ¿Cuál es su nacionalidad?"
good_prompt = "María es turca. ¿Cuál es su nacionalidad?"

content = {
    "pages": [
        {"type": "overview", "title": "Unit Assessment", "title_tr": "Ünite Değerlendirmesi",
         "text": "Check your learning.", "text_tr": "Öğrendiklerinizi kontrol edin."},
        page(bad_prompt, 1, "Her nationality is Turkish."),
    ] + [page(f"Completa la frase {n}.", n) for n in range(2, 11)]
}

before = Q._assessment_render_blockers(copy.deepcopy(content))
assert before, "production-signature hidden-world inference must be detected"
assert any(row["question"] == 1 for row in before)
assert {row["locale"] for row in before} == {"tr", "en"}

calls = []
orig_call = Q._call_review
orig_audit = Q.A.audit_lesson
orig_repair = Q.R.repair_lesson

def fake_call_review(**kwargs):
    calls.append(kwargs)
    stage = kwargs["stage"]
    payload = kwargs["payload"]
    if stage.startswith("luna_assessment:"):
        assert payload["render_contract_blockers"],             "Luna must receive deterministic renderer blockers up front"
        return {"checked_questions": list(range(1, 11)), "patches": []}
    assert stage.startswith("terra_assessment_render_retry:"), stage
    blockers = payload["render_contract_blockers"]
    assert blockers and blockers[0]["question"] == 1
    return {
        "checked_questions": list(range(1, 11)),
        "patches": [{
            "topic_id": "assessment-1",
            "path": ["pages", 1, "prompt"],
            "old": bad_prompt,
            "value": good_prompt,
            "reason": "Nationality must be explicit rather than inferred from residence.",
        }],
    }

try:
    Q._call_review = fake_call_review
    Q.A.audit_lesson = lambda *args, **kwargs: []
    Q.R.repair_lesson = lambda *args, **kwargs: None

    assessment = {"id": "assessment-1", "content": copy.deepcopy(content)}
    lesson = {
        "id": "lesson-1",
        "title": "Countries and Nationalities",
        "content": {"pages": [{"type": "overview", "text": "Nationality vocabulary.",
                               "text_tr": "Uyruk kelimeleri."}]},
    }
    applied = Q.review_unit_assessment(
        unit_title="Origins, Languages, and Numbers",
        assessment_topic=assessment,
        lesson_topics=[lesson],
        language="Spanish",
        level="A1",
        track="tr",
        budget=Q.ReviewBudget(ceiling=999),
    )
finally:
    Q._call_review = orig_call
    Q.A.audit_lesson = orig_audit
    Q.R.repair_lesson = orig_repair

assert applied == 1
assert len(calls) == 2, f"expected Luna + one targeted Terra pass, got {len(calls)}"
assert assessment["content"]["pages"][1]["prompt"] == good_prompt
assert not Q._assessment_render_blockers(assessment["content"]),     "targeted repair must make all ten questions renderable"
assert len([p for p in assessment["content"]["pages"] if p.get("type") == "mcq"]) == 10

print("[ASSESSMENT-RENDER-REPAIR] targeted fail-closed repair regression PASSED")
