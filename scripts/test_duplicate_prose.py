#!/usr/bin/env python3
"""A reading passage must not print the same sentence twice.

A published B1 German recycling text printed "Jede Woche werden die
verschiedenen Mülltonnen…" twice in a row, and "In modernen Sortieranlagen
werden die Wertstoffe…" twice as well. Nothing checked for it: `duplicate_options`
covers an MCQ's option list and nothing covered prose, so a generator that
stuttered produced a reading text no human would write and it published.

Repetition is a legitimate teaching device, so the rule is narrow. Short
sentences recur on purpose, drills repeat a frame with one slot changed, and a
summary may restate a point in different words. What no lesson intends is the
SAME long sentence, byte for byte after normalisation, printed twice inside one
field. Both halves are pinned here: the defect is caught, and every legitimate
shape of repetition is left alone.

The repair is deterministic — a second printing is deleted — so this class
never reaches a model call, and the auditor and the repair share one identity
so a "fix" cannot leave the blocker standing.
"""

from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import audit as A  # noqa: E402
from services.authoring import repair as R  # noqa: E402
from services.authoring import schema as S  # noqa: E402

FAILURES = []
SPEC = S.FieldSpec(S.TARGET, "")


def check(condition, label):
    if not condition:
        FAILURES.append(label)
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")


PUBLISHED = (
    "Jede Woche werden die verschiedenen Mülltonnen an den Straßenrand gestellt. "
    "Jede Woche werden die verschiedenen Mülltonnen an den Straßenrand gestellt. "
    "In modernen Sortieranlagen werden die Wertstoffe maschinell getrennt. "
    "In modernen Sortieranlagen werden die Wertstoffe maschinell getrennt."
)

print("[1] the published defect is caught, both of its repeats")
found = A.repeated_sentences(PUBLISHED)
check(len(found) == 2, f"both duplicated sentences are reported ({len(found)})")
check(any(s.startswith("Jede Woche") for s in found), "the first repeat is named")
check(any(s.startswith("In modernen") for s in found), "the last repeat is named")
# The last sentence of a field keeps its terminator because the split needs
# whitespace after it. Without stripping that, a repeat printed LAST is missed.
check(found[-1].startswith("In modernen"),
      "a repeat in final position is not missed")

print("\n[2] and it is a lesson-level blocker")
lesson = {"pages": [{
    "type": "reading", "title": "Recycling", "title_tr": "Geri Dönüşüm",
    "text": PUBLISHED, "text_tr": "Her hafta çöp kutuları yola konur.",
}]}
codes = {f.code for f in A.audit_lesson(lesson, language="German", track="tr")}
check("duplicate_prose_sentence" in codes, f"blocked ({sorted(codes)})")

print("\n[3] legitimate repetition is left alone")
for label, text in (
    ("short confirmations", "Evet. Doğru. Das stimmt. Genau. Evet. Doğru."),
    ("a drill frame with one slot changed",
     "Ich gehe zur Schule. Du gehst zur Schule. Er geht zur Schule."),
    ("a summary restating a point in other words",
     "Die Mülltrennung ist in Deutschland gesetzlich geregelt. "
     "Zusammengefasst: die Mülltrennung folgt klaren Regeln."),
    ("the same words in a different order",
     "Der Mann gibt dem Kind das Buch. Das Buch gibt der Mann dem Kind."),
    ("one long sentence, printed once",
     "In modernen Sortieranlagen werden die Wertstoffe maschinell getrennt."),
):
    check(A.repeated_sentences(text) == [], f"not flagged: {label}")

print("\n[4] the repair removes the second printing and nothing else")
fixed = R.repair_text(PUBLISHED, SPEC, None)
check(A.repeated_sentences(fixed) == [], "the repaired text carries no repeat")
check(fixed.count("Jede Woche") == 1, "the first sentence survives exactly once")
check(fixed.count("In modernen") == 1, "the second sentence survives exactly once")
check("Straßenrand gestellt" in fixed and "maschinell getrennt" in fixed,
      "both sentences are still present — this is a deletion, not a truncation")
check(R.repair_text(fixed, SPEC, None) == fixed, "the repair is idempotent")

print("\n[5] the repair does not touch text that was never duplicated")
for label, text in (
    ("short confirmations", "Evet. Doğru. Evet. Doğru."),
    ("a drill frame", "Ich gehe zur Schule. Du gehst zur Schule."),
    ("ordinary prose",
     "Die Mülltrennung ist gesetzlich geregelt. Sie gilt überall."),
    ("a single sentence", "In modernen Sortieranlagen wird getrennt."),
):
    check(R.repair_text(text, SPEC, None) == text, f"unchanged: {label}")

print("\n[6] auditor and repair share one identity")
# If the repair deduplicated by a different rule than the auditor blocks on,
# the blocker would survive its own fix and convergence would loop.
lesson_fixed = {"pages": [{
    "type": "reading", "title": "Recycling", "title_tr": "Geri Dönüşüm",
    "text": PUBLISHED, "text_tr": "Her hafta çöp kutuları yola konur.",
}]}
R.repair_lesson(lesson_fixed, language="German")
after = {f.code for f in A.audit_lesson(lesson_fixed, language="German", track="tr")}
check("duplicate_prose_sentence" not in after,
      f"repair_lesson clears the blocker it raised ({sorted(after)})")

print()
if FAILURES:
    print(f"FAILED ({len(FAILURES)}):")
    for label in FAILURES:
        print(f"  - {label}")
    sys.exit(1)
print("all duplicate-prose checks passed")
