#!/usr/bin/env python3
"""A missing artifact is not defective content, and must not get a content repair.

A French A1 build refused publication with

    publication gate refuses a course with missing unit assessment(s):
    Describing People and Daily Surroundings, Daily Routine, Time, and Days,
    Café, Shopping, and Numbers 70-100

and then spent thirty-two self-heal retries handing that sentence to
`repair_publication_refusal_feedback`, which patched lesson prose in
`Regular -er Verbs and Habiter / Parler`, `At the Language Exchange` and
`Reading Student Profiles` — three topics in units that were never named. No
edit to any of them can bring an assessment into existence, so the refusal came
back byte-identical every round and `remaining_blockers=1` never moved.

The defect is not the retry count. It is that one repair was applied to two
kinds of refusal. Everything the gate says about content goes to the content
repair; a refusal naming an absent artifact goes to the stage that authors it.

These checks pin the routing, the fact that the distinction travels as a type
rather than as a sentence, and the two bounds that keep either path from
spinning: a repair that ran and did not move the refusal is charged to the
stall ceiling, and one that never reached the provider is not — but is still
bounded, or a provider outage would restore the unbounded loop under a new name.
"""

from __future__ import annotations
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q  # noqa: E402
from services.legacy import pdf_pipeline as P  # noqa: E402

FAILURES = []


def check(condition, label):
    if not condition:
        FAILURES.append(label)
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")


UNITS = ["Daily Routine, Time, and Days", "Café, Shopping, and Numbers 70-100"]

print("[1] the refusal carries its own identity, not just prose")
err = Q.MissingUnitAssessments(UNITS)
check(isinstance(err, Q.QualityGateError),
      "it is still a QualityGateError, so every existing handler still catches it")
check(err.unit_titles == UNITS,
      f"the named units travel with it ({err.unit_titles})")

# The wording is unchanged on purpose: it is read by humans in logs and pasted
# into the repair prompt for every OTHER refusal class, and a build that has
# been diagnosed from these exact words should keep producing them.
check(str(err) == ("publication gate refuses a course with missing unit "
                   "assessment(s): " + ", ".join(UNITS)),
      f"the message is unchanged ({str(err)!r})")

print("\n[2] the gate raises the typed refusal, not a bare one")
gate_src = inspect.getsource(P._run_publication_quality_gate)
check("Q.MissingUnitAssessments(" in gate_src,
      "the missing-assessment branch raises the structural type")
check("missing unit assessment(s): " not in gate_src,
      "and no longer builds that sentence by hand, so there is one source of it")

print("\n[3] the router keys on the type")
loop_src = inspect.getsource(P._run_publication_until_ready)
check("isinstance(failure, Q.MissingUnitAssessments)" in loop_src,
      "the branch tests the exception's type")
# and nothing in the loop decides anything by reading the refusal's words.
# `publication_error` may still be logged and pasted into the repair prompt —
# that is what it is for — but it must never be searched to pick a branch.
prose_tests = [
    line.strip() for line in loop_src.splitlines()
    if "publication_error" in line
    and (" in publication_error" in line or ".startswith(" in line
         or ".casefold()" in line or ".lower()" in line)
]
check(not prose_tests,
      f"no branch is chosen by matching the refusal's wording ({prose_tests})")

print("\n[4] the structural branch calls the author, not the patcher")
structural = loop_src.split("isinstance(failure, Q.MissingUnitAssessments)", 1)[1]
structural = structural.split("# Identity is the refusal itself", 1)[0]
check("_build_unit_assessments(" in structural,
      "it re-authors the missing assessments")
check("only_unit_titles=failure.unit_titles" in structural,
      "for exactly the units the gate named, not the whole course")
check("repair_publication_refusal_feedback" not in structural,
      "and never reaches the content repair")

print("\n[5] re-authoring is scoped, and reports what it could not write")
sig = inspect.signature(P._build_unit_assessments)
check("only_unit_titles" in sig.parameters,
      f"the author accepts a narrowing ({list(sig.parameters)})")
check(sig.parameters["only_unit_titles"].default is None,
      "which defaults to the whole course, so the ordinary phase is unchanged")

author_src = inspect.getsource(P._build_unit_assessments)
check("unwritten.append(unit[\"title\"])" in author_src,
      "a unit it could not complete is recorded")
check("return unwritten" in author_src,
      "and returned, so a shortfall is not discovered three phases later")
# A partial assessment is a worse outcome than a missing one, and nothing here
# changes that: the unit still publishes none.
check("if len(questions) != UNIT_ASSESSMENT_COUNT:" in author_src,
      "a short set is still refused rather than published partial")
# A requested unit with no lesson material never reaches the author at all, and
# reporting it as written by omission would claim a rescue that did not happen.
check("unwritten = list(unreachable)" in author_src,
      "a unit it could not even reach is reported unwritten too")

print("\n[6] the structural path is bounded by the same stall ceiling")
check("stall_ceiling" in structural,
      "repeated failure to author the same units stops the loop")
check("seen_refusals[signature] -= 1" in structural,
      "but an authoring call that never completed is not charged to it")

print("\n[7] the uncharged attempts have their own bound")
check("_note_incomplete" in loop_src,
      "a repair that never reached the provider is counted separately")
check("QUALITY_SELF_HEAL_PROVIDER_CEILING" in loop_src,
      "and that count has a ceiling")
check(loop_src.count("_note_incomplete(") >= 4,
      f"every non-completing path reports it "
      f"({loop_src.count('_note_incomplete(') - 1} call sites)")
check("incomplete_streak = 0" in loop_src,
      "and a completed repair resets the streak, so it measures consecutive failures")

print("\n[8] the loop's two ceilings are configurable and default sanely")
stall = max(1, int(os.getenv("QUALITY_SELF_HEAL_STALL_CEILING", "3")))
provider = max(1, int(os.getenv("QUALITY_SELF_HEAL_PROVIDER_CEILING", "12")))
check(stall == 3, f"an unmoved refusal stops at the fourth attempt (ceiling {stall})")
check(provider > stall,
      f"a provider outage is tolerated longer than a stuck repair "
      f"({provider} > {stall})")

print("\n[9] OpenRouter's in-flight capacity limit is not a permanent 402")
from services.authoring import transport as T  # noqa: E402
transport_src = inspect.getsource(T)
check("in_flight" in transport_src,
      "the capacity variant of 402 is recognised")
# The distinction matters in both directions: an account that is genuinely out
# of credit must still fail fast rather than retry into the same wall.
check("exc.code == 402" in transport_src,
      "and only 402 is examined for it")
check("capacity_402" in transport_src and "elif exc.code not in" in transport_src,
      "a non-capacity 4xx still returns immediately")

print("\n[10] and the transport actually retries it")
# Driven for real rather than read, because the difference between the two 402s
# is the whole point and a comment cannot be trusted to be what the code does.
import io  # noqa: E402
import json as _json  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402


def _http_error(code, body):
    """A factory, not an instance — see the note in `drive`."""
    return lambda: urllib.error.HTTPError(
        "https://openrouter.ai/api/v1/chat/completions", code, "err", {},
        io.BytesIO(body.encode("utf-8")),
    )


class _Ok:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return _json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


GOOD = {"choices": [{"message": {"content": '{"ok": true}'},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


def drive(responses, attempts=3):
    """Return (result, number of requests the transport actually made)."""
    calls = {"n": 0}

    def fake_urlopen(request, timeout=None):
        index = calls["n"]
        calls["n"] += 1
        outcome = responses[min(index, len(responses) - 1)]
        if callable(outcome):
            # Built fresh per request: the transport reads the error body, and a
            # reused HTTPError hands the second read an exhausted stream.
            raise outcome()
        return _Ok(outcome)

    real_open, real_sleep = urllib.request.urlopen, T.time.sleep
    key = os.environ.get("OPENROUTER_API_KEY")
    try:
        urllib.request.urlopen = fake_urlopen
        T.time.sleep = lambda _s: None        # the backoff is real; the wait is not
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        result = T.call_model(
            [{"role": "user", "content": "hi"}], max_tokens=64,
            model="test/model", attempts=attempts,
        )
    finally:
        urllib.request.urlopen = real_open
        T.time.sleep = real_sleep
        if key is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = key
    return result, calls["n"]


IN_FLIGHT = _json.dumps(
    {"error": {"code": 402,
               "message": "in_flight_budget_exhausted: too many concurrent requests"}}
)
NO_CREDIT = _json.dumps(
    {"error": {"code": 402, "message": "Insufficient credits to run this request"}}
)

result, made = drive([_http_error(402, IN_FLIGHT), GOOD])
check(made == 2, f"a capacity 402 is retried ({made} request(s) made)")
check(result.data == {"ok": True},
      f"and the call succeeds once concurrency drains ({result.error!r})")

result, made = drive([_http_error(402, NO_CREDIT), GOOD])
check(made == 1, f"an out-of-credit 402 still fails fast ({made} request(s) made)")
check(result.data is None and "402" in (result.error or ""),
      f"and reports the real cause rather than retrying into it ({result.error!r})")

# The exemption is bounded by `attempts` like every other retryable status, so a
# provider stuck at capacity cannot hold a worker open indefinitely.
result, made = drive([_http_error(402, IN_FLIGHT)], attempts=3)
check(made == 3, f"a persistent capacity 402 stops at the attempt bound ({made})")
check(result.data is None, "and surfaces as an error rather than a silent success")

print()
if FAILURES:
    print(f"FAILED ({len(FAILURES)}):")
    for label in FAILURES:
        print(f"  - {label}")
    sys.exit(1)
print("all structural refusal routing checks passed")
