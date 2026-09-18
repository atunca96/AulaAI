"""The cost ceiling, as something the code enforces rather than hopes for.

A classroom build must cost at most $0.60. That was previously a wish: the
pipeline made as many calls as it felt like, sized their output ceilings by
round numbers, and reported a total afterwards computed from a rate table that
was wrong by half. A build that ran away was visible only on the invoice.

Here the ceiling is a live object. `BuildLedger` is opened at the start of a
build, every call is priced into it as it completes, and a call that would
breach the ceiling is refused before it is made. The budget is therefore a
property of the system, not a description of its usual behaviour.

Three things make the ceiling reachable, and all three are design rather than
economising:

* **One target-language layer, two instructional views.** Target-language
  examples, terms and answers are generated once, while English and Turkish
  pedagogical fields are generated in parallel because the product exposes both
  views. This avoids duplicating the taught-language payload while keeping both
  reader modes real rather than synthesising one after the build.

* **A cacheable prefix that is actually cacheable.** The system half is
  class-invariant by construction (see `prompts.py`), so after the first lesson
  in a course every subsequent call pays a quarter of the input rate for it.

* **An output ceiling big enough to finish.** `max_tokens` is a ceiling, not a
  charge — you are billed for tokens produced, never for headroom. Sizing it
  too tightly is what caused truncation, and a truncated attempt is billed in
  full and then retried, so a tight ceiling is strictly more expensive than a
  generous one. The previous 8192 against a dual-track lesson is exactly how
  that bill was run up.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

__all__ = [
    "MODEL", "RATES", "price", "BuildLedger", "BudgetExceeded",
    "lesson_output_ceiling", "assessment_output_ceiling", "CLASSROOM_CEILING_USD",
]


# The one model this system runs on. Pinned here rather than read from the
# environment at each call site, so "which model produced this material" has a
# single answer that a reader can find.
MODEL = "openai/gpt-5.6-terra"

# USD per million tokens, as OpenRouter publishes them. `cache_read` is the
# discounted rate for input served from a cached prefix.
RATES: Dict[str, Dict[str, float]] = {
    # Pinned to OpenRouter OpenAI Flex in transport.py.
    "openai/gpt-5.6-terra": {"input": 1.00, "output": 6.00, "cache_read": 0.10},
    "google/gemini-3.8-flash": {"input": 0.75, "output": 3.75, "cache_read": 0.1875},
    "google/gemini-3.7-flash": {"input": 0.75, "output": 3.75, "cache_read": 0.1875},
    "google/gemini-3.5-flash": {"input": 1.50, "output": 9.00, "cache_read": 0.375},
    "google/gemini-2.5-flash": {"input": 0.30, "output": 2.50, "cache_read": 0.075},
    "anthropic/claude-haiku-4.5": {"input": 1.00, "output": 5.00, "cache_read": 0.10},
    "anthropic/claude-sonnet-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20},
}
_FALLBACK_RATE = {"input": 1.00, "output": 4.00, "cache_read": 0.25}

CLASSROOM_CEILING_USD = 0.60


def rates_for(model: str) -> Dict[str, float]:
    return RATES.get(str(model or MODEL), _FALLBACK_RATE)


def price(model: str, *, input_tokens: int = 0, output_tokens: int = 0,
          cached_tokens: int = 0) -> float:
    """What a call cost, in USD.

    `cached_tokens` is the part of the input served from a cached prefix and is
    assumed to be included in `input_tokens`, which is how OpenRouter reports
    it: the discount applies to that slice, the rest pays full rate.
    """
    rate = rates_for(model)
    cached = max(0, min(int(cached_tokens), int(input_tokens)))
    fresh = max(0, int(input_tokens) - cached)
    return (fresh * rate["input"] + cached * rate["cache_read"] + int(output_tokens) * rate["output"]) / 1_000_000


# ── Output ceilings ──────────────────────────────────────────────────────────
# Sized from what the answer must actually contain, with real headroom on top.
# A single-track lesson of five pages measures ~3,000 output tokens; the ceiling
# is more than double that, so a lesson that runs long finishes on its first
# attempt instead of being truncated, billed and retried.

def lesson_output_ceiling(page_target: int = 5, *, inventory: bool = False) -> int:
    """Room for one single-track lesson.

    `inventory` marks a topic that must print a closed set — an alphabet, a
    writing system — which is several times the length of an ordinary page and
    is precisely the case that used to truncate.
    """
    base = 1200 + max(1, int(page_target)) * 1100
    if inventory:
        base += 5000
    return max(3000, min(24000, base))


def assessment_output_ceiling(count: int) -> int:
    """Room for `count` items. A complete item measures ~150 tokens."""
    return max(900, min(12000, int(count) * 190 + 250))


def overproduce(count: int) -> int:
    """How many items to request so `count` survive deterministic validation."""
    c = max(1, int(count))
    return max(c + 2, -(-c * 12 // 10))


# ── The ledger ───────────────────────────────────────────────────────────────

class BudgetExceeded(RuntimeError):
    """Raised before a call that the remaining budget cannot pay for."""


class BuildLedger:
    """What one build has spent, and what it is still allowed to spend.

    Thread-safe because a build generates its lessons concurrently. Every entry
    records the stage that spent it, so "what does a classroom cost" and "which
    stage is expensive" have the same answer source — and so does "what did we
    pay for output we then threw away", which is the number that matters when
    something is going wrong.
    """

    def __init__(self, ceiling_usd: float = CLASSROOM_CEILING_USD, *, model: str = MODEL,
                 label: str = ""):
        self.ceiling = float(ceiling_usd)
        self.model = model
        self.label = label
        self._lock = threading.Lock()
        self.entries: List[Dict[str, object]] = []

    # -- recording ---------------------------------------------------------
    def record(self, *, stage: str, input_tokens: int = 0, output_tokens: int = 0,
               cached_tokens: int = 0, wasted: bool = False,
               reported_cost: Optional[float] = None, subject: str = "") -> float:
        """Price one completed call into the ledger and return what it cost.

        `reported_cost` is the provider's own figure when it gave one. It is
        preferred over the rate table without exception: the table is an
        estimate maintained by hand, and an estimate should never override a
        measurement.
        """
        cost = float(reported_cost) if reported_cost is not None else price(
            self.model, input_tokens=input_tokens, output_tokens=output_tokens,
            cached_tokens=cached_tokens)
        with self._lock:
            self.entries.append({
                "stage": stage, "subject": subject, "cost": cost, "wasted": bool(wasted),
                "input_tokens": int(input_tokens), "output_tokens": int(output_tokens),
                "cached_tokens": int(cached_tokens),
                "estimated": reported_cost is None,
            })
        return cost

    # -- querying ----------------------------------------------------------
    @property
    def spent(self) -> float:
        with self._lock:
            return sum(float(e["cost"]) for e in self.entries)

    @property
    def wasted(self) -> float:
        with self._lock:
            return sum(float(e["cost"]) for e in self.entries if e["wasted"])

    @property
    def remaining(self) -> float:
        return max(0.0, self.ceiling - self.spent)

    def by_stage(self) -> Dict[str, Dict[str, float]]:
        out: Dict[str, Dict[str, float]] = {}
        with self._lock:
            for entry in self.entries:
                row = out.setdefault(str(entry["stage"]),
                                     {"calls": 0, "cost": 0.0, "wasted": 0.0,
                                      "input_tokens": 0, "output_tokens": 0})
                row["calls"] += 1
                row["cost"] += float(entry["cost"])
                row["input_tokens"] += int(entry["input_tokens"])
                row["output_tokens"] += int(entry["output_tokens"])
                if entry["wasted"]:
                    row["wasted"] += float(entry["cost"])
        return out

    # -- enforcing ---------------------------------------------------------
    def estimate(self, *, input_tokens: int, output_tokens: int,
                 cached_tokens: int = 0) -> float:
        return price(self.model, input_tokens=input_tokens, output_tokens=output_tokens,
                     cached_tokens=cached_tokens)

    def can_afford(self, *, input_tokens: int, output_tokens: int,
                   cached_tokens: int = 0) -> bool:
        return self.estimate(input_tokens=input_tokens, output_tokens=output_tokens,
                             cached_tokens=cached_tokens) <= self.remaining

    def require(self, *, stage: str, input_tokens: int, output_tokens: int,
                cached_tokens: int = 0) -> None:
        """Refuse a call the remaining budget cannot pay for.

        Priced at the call's CEILING rather than its likely output, so the
        ledger cannot be walked past its limit by a series of calls that each
        looked affordable on an optimistic estimate.
        """
        want = self.estimate(input_tokens=input_tokens, output_tokens=output_tokens,
                             cached_tokens=cached_tokens)
        if want > self.remaining:
            raise BudgetExceeded(
                f"{stage}: needs ${want:.4f}, ${self.remaining:.4f} left of "
                f"${self.ceiling:.2f}{' for ' + self.label if self.label else ''}")

    # -- reporting ---------------------------------------------------------
    def report(self) -> str:
        lines = [f"[BUILD-COST] {self.label or 'build'} on {self.model}: "
                 f"${self.spent:.4f} of ${self.ceiling:.2f}"]
        for stage, row in sorted(self.by_stage().items(), key=lambda kv: -kv[1]["cost"]):
            lines.append(
                f"  {stage:<14} {int(row['calls']):>3} call(s)  ${row['cost']:.4f}"
                f"  in={int(row['input_tokens']):>7}  out={int(row['output_tokens']):>6}"
                + (f"  wasted=${row['wasted']:.4f}" if row["wasted"] else ""))
        if self.wasted:
            share = self.wasted / self.spent * 100.0 if self.spent else 0.0
            lines.append(f"  produced nothing: ${self.wasted:.4f} ({share:.1f}% of spend)")
        return "\n".join(lines)


def project_classroom_cost(*, lessons: int, units: int, items_per_unit: int = 10,
                           pages_per_lesson: int = 5, model: str = MODEL,
                           source_tokens: int = 0) -> Dict[str, float]:
    """What a classroom of this shape should cost, before it is built.

    Used by the tests to assert the ceiling holds at the sizes the product
    actually builds, and by the engine to refuse a build it cannot finish
    rather than stopping halfway through and charging for the half.
    """
    from services.authoring import prompts as P

    lesson_system = len(P.build_lesson_system(language="Spanish", level="A1")) // 4
    assess_system = len(P.build_assessment_system(language="Spanish", level="A1")) // 4
    lesson_user = 520 + int(source_tokens)
    lesson_out = int(lesson_output_ceiling(pages_per_lesson) * 0.42)
    assess_user = 1500
    assess_out = int(assessment_output_ceiling(items_per_unit) * 0.8)

    # The first call in a class writes the prefix; the rest read it.
    def cached_input(system: int, user: int, calls: int) -> float:
        if calls <= 0:
            return 0.0
        first = price(model, input_tokens=system + user)
        rest = (calls - 1) * price(model, input_tokens=system + user, cached_tokens=system)
        return first + rest

    lessons_cost = cached_input(lesson_system, lesson_user, lessons) + \
        price(model, output_tokens=lesson_out * lessons)
    assess_cost = cached_input(assess_system, assess_user, units) + \
        price(model, output_tokens=assess_out * units)
    curriculum = price(model, input_tokens=900, output_tokens=1400)

    total = lessons_cost + assess_cost + curriculum
    return {"lessons": lessons_cost, "assessments": assess_cost,
            "curriculum": curriculum, "total": total,
            "headroom": CLASSROOM_CEILING_USD - total}
