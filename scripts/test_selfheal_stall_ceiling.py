#!/usr/bin/env python3
"""The self-heal loop must stop when the repair stops moving the refusal.

The inner convergence controller learned this already. A repair that rewrites
content without clearing the same validator makes the defect look new, the same
strategies become eligible again, and the loop spins; `_blocker_fingerprint`
fixed it by keying on the invariant rather than on the bytes.

The OUTER publication self-heal loop never got the same treatment. It was
written with no content-retry ceiling on purpose — a repairable defect should
never reach the learner as a failure — but "no ceiling on attempts" was
implemented as "no ceiling on IDENTICAL attempts". A French A1 build was
observed live at "automatic repair retry 31", each attempt opening a fresh
QUALITY_SELF_HEAL_ATTEMPT_BUDGET against a refusal the repair could not move.

Progress, not attempts, is what bounds the loop. A refusal whose exact text
recurs is one the repair did not move; a few recurrences are legitimate,
because one attempt may write a patch the next completes.
"""

from __future__ import annotations
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FAILURES = []


def check(condition, label):
    if not condition:
        FAILURES.append(label)
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")


SOURCE = os.path.join(ROOT, "services", "legacy", "pdf_pipeline.py")
text = open(SOURCE, encoding="utf-8").read()

print("[1] the loop tracks refusals by identity, not by attempt number")
check("seen_refusals" in text, "refusals are remembered across attempts")
check(re.search(r'signature = " "\.join\(publication_error\.split\(\)\)', text),
      "identity is the refusal text, whitespace-normalised")
# An ordinal or a timestamp in the key would make every recurrence look new,
# which is precisely the mistake that produced the 24-round inner loop.
signature_line = re.search(r"signature = .*", text).group(0)
for forbidden in ("retry_attempt", "time.", "uuid", "random"):
    check(forbidden not in signature_line,
          f"the identity does not include {forbidden!r}")

print("\n[2] a stalled refusal stops the loop")
check("stall_ceiling" in text, "a stall ceiling exists")
check(re.search(r"seen_refusals\[signature\] > stall_ceiling", text),
      "the ceiling is compared against repeats of the SAME refusal")
check("raise" in text.split("stall_ceiling")[2][:600],
      "exceeding it re-raises rather than looping again")

print("\n[3] the ceiling is configurable and cannot be set to zero")
match = re.search(
    r'stall_ceiling = max\((\d+), int\(os\.getenv\(\s*"QUALITY_SELF_HEAL_STALL_CEILING",\s*"(\d+)"\s*\)\)\)',
    text,
)
check(bool(match), "the ceiling is read from one clamped expression")
floor, default = (int(v) for v in match.groups())
check(floor >= 1, f"the floor is at least one attempt ({floor})")
check(default >= 2, f"the default allows a repair to take effect ({default})")


def ceiling(env=None):
    return max(floor, int(default if env is None else env))


check(ceiling() == default, "an unset environment uses the default")
check(ceiling("0") == floor, "0 clamps to the floor, never to no attempts")
check(ceiling("10") == 10, "it can be raised for a stubborn build")

print("\n[4] progress is still unbounded — a MOVING refusal never stops")
# This is the property the loop exists for and the one a ceiling could break.
# Distinct refusals must each get their own budget of attempts.
seen: dict = {}
stopped_on = None
for step, refusal in enumerate(
    ["blocker A", "blocker A", "blocker B", "blocker C", "blocker B", "blocker D"], 1
):
    seen[refusal] = seen.get(refusal, 0) + 1
    if seen[refusal] > default:
        stopped_on = step
        break
check(stopped_on is None,
      f"six attempts on four distinct refusals do not trip the ceiling "
      f"(stopped at {stopped_on})")

seen = {}
stopped_on = None
for step in range(1, 12):
    seen["same"] = seen.get("same", 0) + 1
    if seen["same"] > default:
        stopped_on = step
        break
check(stopped_on == default + 1,
      f"but an unmoving refusal stops at attempt {default + 1} "
      f"(stopped at {stopped_on})")
check(stopped_on is not None and stopped_on < 31,
      "well before the 31 attempts observed in production")

print()
if FAILURES:
    print(f"FAILED ({len(FAILURES)}):")
    for label in FAILURES:
        print(f"  - {label}")
    sys.exit(1)
print("all self-heal stall ceiling checks passed")
