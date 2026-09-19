#!/usr/bin/env python3
"""The rationale repair must be able to satisfy its own acceptance predicate.

`_explanation_grounding_blockers` owns TWO rationale invariants: a rationale may
not introduce a person the question does not show, and it must cite item-specific
learner-visible evidence. `_strategy_explanation_grounding` is the repair for
both, and `_grounding_clear` admits a candidate only when BOTH pass.

The specificity invariant was routed into that strategy without being named in
the repair contract: the payload announced the grounding reason unconditionally
and the system prompt asked only for grounded evidence. A page refused solely
for specificity therefore sent the repairer to fix a person that is not there,
and every candidate it produced was rejected by the half of the predicate nobody
had told it about. `return 0` on a blocker with no other strategy is a permanent
fail-closed stall, not a repair.

These checks are language-agnostic: the fixtures below are Spanish and German
only because the repair must work the same in both, and nothing in the
implementation reads either language.
"""

from __future__ import annotations
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q  # noqa: E402

FAILURES = []


def check(condition, label):
    if not condition:
        FAILURES.append(label)
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")


def page(**over):
    base = {
        "type": "mcq", "stem_scope": "target_complete", "assessment_scope": "unit",
        "title": "Question 1", "title_tr": "Soru 1",
        "prompt": "¿Dónde está la llave?",
        "options": ["encima de la mesa", "muy bien", "a las ocho", "con Ana"],
        "answer": "encima de la mesa",
        "distractors": ["muy bien", "a las ocho", "con Ana"],
        "explanation": "The correct answer is 'encima de la mesa' because it "
                       "matches the information explicitly given in the question.",
        "explanation_tr": "Doğru cevap 'encima de la mesa'; çünkü soruda açıkça "
                          "verilen bilgiyle eşleşir.",
    }
    base.update(over)
    return base


def topic_of(mcq_page, title="Locations"):
    return {"id": "t1", "title": title,
            "content": {"pages": [{"type": "overview", "title": "U", "title_tr": "U"},
                                  mcq_page]}}


print("[1] the repair is told the reason it must actually clear")
seen = {}
ORIG = Q._call_review


def provider(**kwargs):
    seen.update(kwargs["payload"])
    return {
        # Cites «llave» from the stem, so specificity is satisfied by evidence
        # rather than by scaffolding.
        "explanation_en": "The stem asks where «la llave» is, so a place phrase "
                          "answers it: «encima de la mesa».",
        "explanation_tr": "Soru «la llave» nerede diye sorar; yer bildiren "
                          "«encima de la mesa» yanıt verir.",
        "reason": "Cite the stem's own noun as the evidence.",
    }


topic = topic_of(page())
bare = {k: v for k, v in page().items() if k not in ("title", "title_tr")}
reasons = {row["why"]
           for row in Q._explanation_grounding_blockers({"pages": [bare]})}
check(Q._EXPLANATION_SPECIFICITY_REASON in reasons,
      f"the boilerplate rationale is refused for specificity ({sorted(reasons)})")

# KNOWN GAP, pinned rather than silently tolerated. `_GROUNDED_EVIDENCE_KEYS`
# counts `title`/`title_tr` as learner-visible evidence, and every persisted
# assessment page carries the scaffolding "Question N"/"Soru N"
# (services/legacy/pdf_pipeline.py). That donates the tokens `question`/`soru`
# to every item, so a rationale merely containing the word "question" clears the
# specificity invariant. The boilerplate does. Tightening this changes which
# stored courses publish, so it is recorded here as behaviour rather than
# changed as a side effect of the repair fix.
with_scaffolding = Q._explanation_grounding_blockers({"pages": [page()]})
check([row["why"] for row in with_scaffolding] == [],
      "PINNED GAP: page title scaffolding still admits the same boilerplate")

try:
    Q._call_review = provider
    applied = Q._strategy_explanation_grounding(
        topic=topic,
        blocker={"render_rows": [{"page_index": 1,
                                  "why": Q._EXPLANATION_SPECIFICITY_REASON}]},
        language="Spanish", level="A1", track="tr",
        budget=Q.ReviewBudget(0.22), unit_title="Unit 1",
    )
finally:
    Q._call_review = ORIG

check(Q._EXPLANATION_SPECIFICITY_REASON in str(seen.get("blocker") or ""),
      f"the payload names the specificity defect ({seen.get('blocker')!r})")
check(Q._EXPLANATION_SPECIFICITY_REASON in (seen.get("blockers") or []),
      "the payload carries the reasons as a list too")
check(applied > 0, f"a proven candidate is committed ({applied})")

print("\n[2] and the repaired page reaches publication")
repaired = topic["content"]["pages"][1]
check(Q._explanation_grounding_blockers({"pages": [repaired]}) == [],
      "no rationale blocker survives on the repaired page")
for key in ("answer", "options", "distractors", "prompt"):
    check(repaired[key] == page()[key], f"{key} is unchanged by the repair")

print("\n[3] invalid content is still blocked — fail-closed is preserved")
seen.clear()


def weak_provider(**kwargs):
    # Grounded, but still cites nothing from the item: the acceptance predicate
    # must reject it and the strategy must make no progress.
    return {"explanation_en": "The correct answer is the one that matches.",
            "explanation_tr": "Doğru cevap eşleşen seçenektir.",
            "reason": "no"}


stalled = topic_of(page())
try:
    Q._call_review = weak_provider
    applied_bad = Q._strategy_explanation_grounding(
        topic=stalled,
        blocker={"render_rows": [{"page_index": 1,
                                  "why": Q._EXPLANATION_SPECIFICITY_REASON}]},
        language="Spanish", level="A1", track="tr",
        budget=Q.ReviewBudget(0.22), unit_title="Unit 1",
    )
finally:
    Q._call_review = ORIG
check(applied_bad == 0, "an unspecific candidate is refused, not committed")
check(stalled["content"]["pages"][1]["explanation"] == page()["explanation"],
      "and nothing is written to the page")

print("\n[4] the same repair works on a different taught language")
german = topic_of(page(
    prompt="Wo ist der Schlüssel?",
    options=["auf dem Tisch", "sehr gut", "um acht Uhr", "mit Anna"],
    answer="auf dem Tisch",
    distractors=["sehr gut", "um acht Uhr", "mit Anna"],
    explanation="The correct answer is 'auf dem Tisch' because it matches the "
                "information explicitly given in the question.",
    explanation_tr="Doğru cevap 'auf dem Tisch'; çünkü soruda açıkça verilen "
                   "bilgiyle eşleşir.",
), title="Wohnen")


def de_provider(**kwargs):
    return {"explanation_en": "The stem asks where «der Schlüssel» is, so the "
                              "place phrase «auf dem Tisch» answers it.",
            "explanation_tr": "Soru «der Schlüssel» nerede diye sorar; «auf dem "
                              "Tisch» yer bildirir.",
            "reason": "Cite the stem's noun."}


try:
    Q._call_review = de_provider
    applied_de = Q._strategy_explanation_grounding(
        topic=german,
        blocker={"render_rows": [{"page_index": 1,
                                  "why": Q._EXPLANATION_SPECIFICITY_REASON}]},
        language="German", level="B1", track="tr",
        budget=Q.ReviewBudget(0.22), unit_title="Unit 1",
    )
finally:
    Q._call_review = ORIG
check(applied_de > 0, "the repair converges in German too")
check(Q._explanation_grounding_blockers(
    {"pages": [german["content"]["pages"][1]]}) == [],
    "and that page is clean as well")

print()
if FAILURES:
    print(f"FAILED ({len(FAILURES)}):")
    for label in FAILURES:
        print(f"  - {label}")
    sys.exit(1)
print("all rationale specificity repair checks passed")
