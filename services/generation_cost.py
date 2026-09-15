"""Cost ledger for model spend during material generation.

Why this exists
---------------
Before this module the pipeline could not answer the only question that matters
when someone asks "what does a class cost?": which calls were made, what they
cost, and how much of that spend produced nothing. The information existed --
every provider response carries a usage block -- but it was read in exactly one
place (quiz generation) and discarded everywhere else, including the lesson
call, which is the dominant cost. Retries and truncated attempts were charged
by the provider and recorded nowhere at all, so wasted spend was structurally
invisible: the more a topic failed, the less the logs said about it.

The ledger is deliberately passive. It never changes what is generated, never
gates a call, never decides to skip work. It observes what was already going to
happen and writes it down, per call, per lesson, and per class, so a cost claim
can be checked against a measurement instead of an estimate.

Threading
---------
A class build fans topics out across a thread pool inside one worker process, so
the ledger is process-global and lock-guarded rather than thread-local: the
class total is the sum across workers. `stage` labels which part of the pipeline
a call belongs to, so the per-class total decomposes without any caller having
to thread an aggregate object through the call graph.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

# Stage labels. Kept as constants so a typo in one call site cannot silently
# create a second bucket that looks like a different kind of work.
STAGE_LESSON = "lesson"
STAGE_LESSON_PRIME = "lesson_prime"
STAGE_CLAIM_REVIEW = "claim_review"
STAGE_QUESTIONS = "questions"
STAGE_CURRICULUM = "curriculum"
STAGE_TRANSLATION = "translation"
STAGE_OTHER = "other"

# Outcome labels. `ok` means the response was usable; everything else is spend
# that produced no publishable output and is what "wasted" counts below.
OUTCOME_OK = "ok"
OUTCOME_PARSE_FAILED = "parse_failed"
OUTCOME_TRUNCATED = "truncated"
OUTCOME_REJECTED = "rejected"

_WASTED_OUTCOMES = (OUTCOME_PARSE_FAILED, OUTCOME_REJECTED)


def _log_path() -> str:
    return os.getenv("AULAAI_PIPELINE_LOG", "pipeline.log")


def _write_log(line: str) -> None:
    try:
        with open(_log_path(), "a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.now().strftime('%H:%M:%S')}] {line}\n")
    except Exception:
        # Cost accounting must never be able to fail a build.
        pass


class CostLedger:
    """Append-only record of model calls for the current process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: List[Dict[str, Any]] = []
        self._label = ""

    # -- lifecycle ---------------------------------------------------------

    def reset(self, label: str = "") -> None:
        with self._lock:
            self._calls = []
            self._label = str(label or "")

    @property
    def label(self) -> str:
        return self._label

    # -- recording ---------------------------------------------------------

    def record(
        self,
        *,
        stage: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_tokens: int = 0,
        cache_write_tokens: int = 0,
        cache_discount: float = 0.0,
        reasoning_tokens: int = 0,
        cost: float = 0.0,
        outcome: str = OUTCOME_OK,
        attempt: int = 1,
        subject: str = "",
    ) -> Dict[str, Any]:
        """Record one provider response and return the recorded entry.

        Called for every response that carried a usage block, including the ones
        whose content could not be used. A call that was charged and thrown away
        is exactly the call this ledger exists to make visible, so recording is
        never conditional on success.

        The entry is returned so a caller that only learns later that it will
        discard the result -- a lesson that parses but fails the release gate --
        can reclassify its own spend through `mark_outcome` instead of the ledger
        having to guess from the outside.
        """
        entry = {
            "stage": str(stage or STAGE_OTHER),
            "model": str(model or ""),
            "prompt_tokens": max(0, int(prompt_tokens or 0)),
            "completion_tokens": max(0, int(completion_tokens or 0)),
            "cached_tokens": max(0, int(cached_tokens or 0)),
            "cache_write_tokens": max(0, int(cache_write_tokens or 0)),
            "cache_discount": max(0.0, float(cache_discount or 0.0)),
            "reasoning_tokens": max(0, int(reasoning_tokens or 0)),
            "cost": max(0.0, float(cost or 0.0)),
            "outcome": str(outcome or OUTCOME_OK),
            "attempt": max(1, int(attempt or 1)),
            "subject": str(subject or ""),
        }
        with self._lock:
            self._calls.append(entry)
        return entry

    def mark_outcome(self, entry: Any, outcome: str) -> None:
        """Reclassify an entry this ledger already holds."""
        if not isinstance(entry, dict) or "outcome" not in entry:
            return
        with self._lock:
            entry["outcome"] = str(outcome or OUTCOME_OK)

    # -- reporting ---------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            calls = list(self._calls)

        def blank() -> Dict[str, Any]:
            return {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_tokens": 0,
                "cache_write_tokens": 0,
                "cache_discount": 0.0,
                "reasoning_tokens": 0,
                "cost": 0.0,
                "wasted_calls": 0,
                "wasted_cost": 0.0,
            }

        total = blank()
        stages: Dict[str, Dict[str, Any]] = {}
        for c in calls:
            bucket = stages.setdefault(c["stage"], blank())
            for target in (total, bucket):
                target["calls"] += 1
                target["prompt_tokens"] += c["prompt_tokens"]
                target["completion_tokens"] += c["completion_tokens"]
                target["cached_tokens"] += c["cached_tokens"]
                target["cache_write_tokens"] += c["cache_write_tokens"]
                target["cache_discount"] += c["cache_discount"]
                target["reasoning_tokens"] += c["reasoning_tokens"]
                target["cost"] += c["cost"]
                if c["outcome"] in _WASTED_OUTCOMES:
                    target["wasted_calls"] += 1
                    target["wasted_cost"] += c["cost"]

        billed_prompt = total["prompt_tokens"]
        total["cache_hit_ratio"] = (
            (total["cached_tokens"] / billed_prompt) if billed_prompt else 0.0
        )
        lessons = sum(
            1
            for c in calls
            if c["stage"] == STAGE_LESSON and c["outcome"] == OUTCOME_OK
        )
        total["published_lessons"] = lessons
        total["cost_per_lesson"] = (total["cost"] / lessons) if lessons else 0.0
        return {"label": self._label, "total": total, "stages": stages}

    def top_subjects(self, limit: int = 5) -> List[Any]:
        """Heaviest labelled subjects, most expensive first."""
        with self._lock:
            calls = list(self._calls)
        rollup: Dict[str, List[Any]] = {}
        for c in calls:
            subject = c["subject"]
            if not subject:
                continue
            row = rollup.setdefault(subject, [0.0, 0])
            row[0] += c["cost"]
            row[1] += 1
        ordered = sorted(rollup.items(), key=lambda kv: kv[1][0], reverse=True)
        return [(name, row[0], row[1]) for name, row in ordered[: max(0, int(limit))]]

    def format_summary(self) -> List[str]:
        s = self.summary()
        t = s["total"]
        lines = [
            f"[COST-SUMMARY] {s['label'] or 'run'}: "
            f"${t['cost']:.4f} over {t['calls']} call(s); "
            f"in={t['prompt_tokens']} (cached={t['cached_tokens']}, "
            f"hit={t['cache_hit_ratio'] * 100:.1f}%) out={t['completion_tokens']} "
            f"reasoning={t['reasoning_tokens']}"
        ]
        # Stated separately from the hit ratio because they answer different
        # questions: the ratio says how much of the input was served from cache,
        # the discount says what the provider actually took off the bill. A build
        # that writes caches it never reads shows writes with no discount, which
        # is the signature of a cache whose lifetime is shorter than the build.
        lines.append(
            f"[COST-CACHE] written={t['cache_write_tokens']} read={t['cached_tokens']} "
            f"provider-reported discount=${t['cache_discount']:.4f}"
        )
        if t["published_lessons"]:
            lines.append(
                f"[COST-SUMMARY] published lessons={t['published_lessons']}, "
                f"${t['cost_per_lesson']:.4f} per published lesson"
            )
        if t["wasted_calls"]:
            share = (t["wasted_cost"] / t["cost"] * 100.0) if t["cost"] else 0.0
            lines.append(
                f"[COST-SUMMARY] discarded output: {t['wasted_calls']} call(s), "
                f"${t['wasted_cost']:.4f} ({share:.1f}% of spend)"
            )
        # Per-subject rollup. A class total hides the shape of the spend: one
        # topic that retried three times costs what four ordinary topics cost, and
        # naming it is the difference between "the class is expensive" and "this
        # topic is expensive". Only the heaviest few are printed; the rest are the
        # flat body of the distribution and say nothing.
        for subject, spend, calls in self.top_subjects(5):
            lines.append(
                f"[COST-TOPIC] {subject}: ${spend:.4f} over {calls} call(s)"
            )
        for stage in sorted(s["stages"]):
            b = s["stages"][stage]
            lines.append(
                f"[COST-STAGE] {stage}: {b['calls']} call(s) ${b['cost']:.4f} "
                f"in={b['prompt_tokens']} cached={b['cached_tokens']} "
                f"out={b['completion_tokens']} wasted=${b['wasted_cost']:.4f}"
            )
        return lines

    def emit_summary(self) -> None:
        for line in self.format_summary():
            _write_log(line)


LEDGER = CostLedger()


def record_call(**kwargs: Any) -> Dict[str, Any]:
    """Module-level shorthand so callers do not import the singleton by name."""
    return LEDGER.record(**kwargs)


def mark_outcome(entry: Any, outcome: str) -> None:
    LEDGER.mark_outcome(entry, outcome)


def reset(label: str = "") -> None:
    LEDGER.reset(label)


def summary() -> Dict[str, Any]:
    return LEDGER.summary()


def emit_summary() -> None:
    LEDGER.emit_summary()


def extract_usage(response_json: Any) -> Optional[Dict[str, int]]:
    """Pull token counts out of a provider response.

    Providers disagree about where these live -- prompt token details may carry
    cached counts, completion token details may carry reasoning counts, and some
    responses flatten both to the top level. Reading all the known spellings here
    keeps that knowledge in one place instead of at each call site, and returning
    None (rather than zeros) lets a caller tell "no usage reported" apart from
    "a call that genuinely used nothing".
    """
    if not isinstance(response_json, dict):
        return None
    usage = response_json.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt_details = usage.get("prompt_tokens_details")
    if not isinstance(prompt_details, dict):
        prompt_details = {}
    completion_details = usage.get("completion_tokens_details")
    if not isinstance(completion_details, dict):
        completion_details = {}

    def _int(*values: Any) -> int:
        for v in values:
            if isinstance(v, (int, float)):
                return int(v)
        return 0

    return {
        "prompt_tokens": _int(usage.get("prompt_tokens"), usage.get("input_tokens")),
        "completion_tokens": _int(
            usage.get("completion_tokens"), usage.get("output_tokens")
        ),
        "cached_tokens": _int(
            prompt_details.get("cached_tokens"), usage.get("cached_tokens")
        ),
        # Written vs read matters: a write is charged at roughly the normal input
        # price, a read at a quarter of it. Recording only the reads would make a
        # build that wrote a cache thirty times and read it never look identical
        # to one that never tried to cache at all.
        "cache_write_tokens": _int(
            prompt_details.get("cache_write_tokens"), usage.get("cache_write_tokens")
        ),
        "reasoning_tokens": _int(
            completion_details.get("reasoning_tokens"), usage.get("reasoning_tokens")
        ),
    }


def extract_cache_discount(response_json: Any) -> float:
    """The provider's own statement of what caching saved on this call.

    Reported by OpenRouter alongside usage. It is the only number in the system
    that is neither estimated nor derived, so it is what a claim about cache
    savings should be made from.
    """
    if not isinstance(response_json, dict):
        return 0.0
    usage = response_json.get("usage")
    if not isinstance(usage, dict):
        return 0.0
    value = usage.get("cache_discount")
    return float(value) if isinstance(value, (int, float)) else 0.0
