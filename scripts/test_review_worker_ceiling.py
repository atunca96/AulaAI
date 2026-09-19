#!/usr/bin/env python3
"""The review concurrency knob must turn both ways, and default to today.

`QUALITY_REVIEW_WORKERS` was read through `min(3, ...)`, so it could only ever
lower concurrency. Six units therefore ran as two waves of three, and the
pedagogical-risk stage — the longest of the four, at two provider round-trips
per topic — paid that serialization twice. A build watching "pedagogical risks
0/6" is watching exactly that.

The ceiling is raised so the knob can be turned UP. What must not change is the
default: a deploy that sets nothing has to behave precisely as it does today,
because it currently produces a classroom end to end and that is not a thing to
risk for a speed-up nobody asked to be automatic.
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

print("[1] the knob is read exactly once, and clamped")
matches = re.findall(
    r"review_workers\s*=\s*max\(\s*(\d+)\s*,\s*min\(\s*(\d+)\s*,\s*"
    r"int\(\s*os\.getenv\(\s*\"QUALITY_REVIEW_WORKERS\"\s*,\s*\"(\d+)\"\s*\)\s*\)\s*\)\s*\)",
    text,
)
check(len(matches) == 1,
      f"one clamped read of QUALITY_REVIEW_WORKERS ({len(matches)} found)")

floor, ceiling, default = (int(v) for v in matches[0])


def workers(env=None):
    return max(floor, min(ceiling, int(default if env is None else env)))


print("\n[2] an unset environment is today's behaviour")
check(default == 3, f"the default is still 3 (found {default})")
check(workers() == 3, f"an unset knob yields 3 (yields {workers()})")

print("\n[3] and the knob now moves in both directions")
check(floor == 1 and workers("1") == 1, "it can still be turned down to 1")
check(ceiling > 3, f"the ceiling is above the old cap ({ceiling})")
check(workers("6") == 6, f"6 is honoured (got {workers('6')})")
check(workers("99") == ceiling,
      f"an absurd value clamps to the ceiling (got {workers('99')})")
check(workers("0") == floor, f"0 clamps to the floor (got {workers('0')})")

print()
if FAILURES:
    print(f"FAILED ({len(FAILURES)}):")
    for label in FAILURES:
        print(f"  - {label}")
    sys.exit(1)
print("all review worker ceiling checks passed")
