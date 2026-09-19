#!/usr/bin/env python3
"""The name/gender rule may defer to a reviewer, but never to only one caller.

`personal_name_tokens` decides who is a person from capitalisation. Measured
across the taught languages that signal is absent in Chinese, Japanese, Korean
and Arabic — an explicit "X is a feminine name, so the answer is feminine" is
caught in none of them — and in German, where every noun is capitalised,
ordinary grammar prose is refused as personal-name inference. A proxy that wrong
in both directions must not be the last word on a paid classroom.

The answer-key grounding reviewer adjudicates this exact question: its contract
says "do not infer gender, identity, nationality, profession or other properties
from a personal name", and it certifies the final state per item. Where it has
cleared these exact bytes, its verdict stands.

The danger in that trade is NOT leniency, it is DIVERGENCE. `render_contract`
exists because the gate and the renderer once disagreed and a validated page was
silently dropped on its way to the page. So the proof is resolved inside the
shared predicate, and these checks pin that both callers always get the same
answer — including in a process that never imports the review layer, which is
exactly the renderer's situation.
"""

from __future__ import annotations
import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import render_contract as RC  # noqa: E402

FAILURES = []
RUN = uuid.uuid4().hex[:12]


def check(condition, label):
    if not condition:
        FAILURES.append(label)
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")


def named(**over):
    page = {
        "type": "mcq",
        "prompt": f"Ana {RUN} es ___.",
        "options": ["alta", "alto", "altos", "altas"],
        "answer": "alta",
        "distractors": ["alto", "altos", "altas"],
        "explanation": "Ana is a feminine name, so «alta».",
        "explanation_tr": "Ana kadın ismidir; bu yüzden «alta».",
    }
    page.update(over)
    return page


print("[1] unreviewed personal-name gender inference is still refused")
page = named()
check(RC.hidden_world_reason(page) == RC.NAME_GENDER_REASON,
      "the rule fires with no proof present")
for is_tr in RC.EXPORT_LOCALES:
    ok, why = RC.page_is_renderable(page, is_tr)
    check(not ok and why == RC.NAME_GENDER_REASON,
          f"{'tr' if is_tr else 'en'} export refuses it")

print("\n[2] a reviewer verdict on these exact bytes is honoured")
cleared = {RC.rationale_semantic_digest(page)}
RC.set_rationale_proof_lookup(
    lambda p: RC.rationale_semantic_digest(p) in cleared
)
try:
    check(RC.hidden_world_reason(page) == "",
          "the shared predicate defers to the reviewer")
    # The parity claim: BOTH callers read this one predicate, so neither can
    # admit a page the other refuses.
    for is_tr in RC.EXPORT_LOCALES:
        ok, why = RC.page_is_renderable(page, is_tr)
        check(ok, f"{'tr' if is_tr else 'en'} export admits it too ({why})")

    print("\n[3] the verdict is bound to the bytes")
    for label, mutation in (
        ("the rationale changes", {"explanation": "Ana is a man's name, so «alto»."}),
        ("the stem changes", {"prompt": f"Ana {RUN} y Luis son ___."}),
        ("the answer changes", {"answer": "alto"}),
        ("an option changes", {"options": ["alta", "alto", "altos", "altisimas"]}),
    ):
        mutated = dict(page)
        mutated.update(mutation)
        check(RC.hidden_world_reason(mutated) == RC.NAME_GENDER_REASON,
              f"the strict predicate returns when {label}")

    print("\n[4] an unrelated page is not covered by someone else's proof")
    other = named(prompt=f"Luis {RUN} es ___.",
                  explanation="Luis is a masculine name, so «alto».",
                  explanation_tr="Luis erkek ismidir; bu yüzden «alto».")
    check(RC.hidden_world_reason(other) == RC.NAME_GENDER_REASON,
          "a proof covers one page, not the class of pages")
finally:
    RC.set_rationale_proof_lookup(None)

print("\n[5] the default resolver cannot open the gate on its own")
# With no store, a missing table or an unreadable file, the answer is "no
# proof". This is the state the renderer runs in before any review has happened.
check(RC.hidden_world_reason(page) == RC.NAME_GENDER_REASON,
      "the restored default keeps the page refused")
RC.set_rationale_proof_lookup(lambda p: (_ for _ in ()).throw(RuntimeError("down")))
try:
    check(RC.hidden_world_reason(page) == RC.NAME_GENDER_REASON,
          "a resolver that raises is treated as no proof")
finally:
    RC.set_rationale_proof_lookup(None)

print("\n[6] the digest is defined once, and the review layer re-exports it")
from services.authoring import quality_gate as Q  # noqa: E402
check(Q._rationale_semantic_digest(page) == RC.rationale_semantic_digest(page),
      "gate and predicate compute the same digest for the same page")
check(Q._rationale_proof_covers(named(prompt=f"Nadie {RUN} es ___.")) is False,
      "an unattested page is not covered")

print("\n[7] the capitalisation signal is why this exists")
# Not an aspiration: these are the languages where the proxy cannot see a
# blatant inference at all, which is what makes it unfit to be the last word.
blind = []
for label, stem, expl in (
    ("Chinese", "小美是___。", "小美 is a feminine name, so the answer is feminine."),
    ("Japanese", "さくらは___です。", "さくら is a feminine name, so the answer is feminine."),
    ("Korean", "미나는 ___입니다.", "미나 is a feminine name, so the answer is feminine."),
    ("Arabic", "فاطمة ___.", "فاطمة is a feminine name, so the answer is feminine."),
):
    probe = named(prompt=stem, explanation=expl, explanation_tr=expl)
    if RC.hidden_world_reason(probe) != RC.NAME_GENDER_REASON:
        blind.append(label)
check(blind == ["Chinese", "Japanese", "Korean", "Arabic"],
      f"the proxy is blind in exactly the caseless scripts ({blind})")

print()
if FAILURES:
    print(f"FAILED ({len(FAILURES)}):")
    for label in FAILURES:
        print(f"  - {label}")
    sys.exit(1)
print("all name/gender proof parity checks passed")
