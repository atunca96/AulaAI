"""Where an assessment may draw from, and what language it may phrase itself in.

Three assessment scopes exist in this product and they are not interchangeable:

  TOPIC       formative items at the end of one topic. May assess ONLY that
              topic. A learner who has just read Topic 3 is not being examined
              on Topic 5.
  UNIT        the ten-question assessment that closes a unit. May assess the
              whole unit and nothing beyond it.
  STANDALONE  a quiz, in-class activity or assignment the lecturer generates
              over topics they chose. Its boundary is that selection.

The boundary is enforced STRUCTURALLY — by what evidence is assembled and handed
to the generator — not by asking the model to ignore material it was given. A
model handed Topic 5's vocabulary will eventually use Topic 5's vocabulary, and
no amount of instruction reliably prevents that. So the scope decides the
payload, and a deterministic check afterwards confirms what came back stayed
inside it.

The second thing this module owns is the PROGRESSION ENVELOPE. "Ask the question
in the target language" is not the same as "ask it in any target-language
sentence the model can write". An A1 learner five topics into a course can read
roughly what those five topics taught, and a stem phrased above that line is
unanswerable for reasons that have nothing to do with whether they know the
answer. The envelope is derived deterministically from the course position and
the material already generated — no model call — and states the ceiling as a
budget the generator writes inside.

Everything here produces COMPACT text. The previous prompt reached ~20k tokens by
appending a paragraph per requirement; scope and progression are expressed as
short structured clauses instead, and the invariants they imply live in
deterministic validation rather than in repeated prose.
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "SCOPE_TOPIC", "SCOPE_UNIT", "SCOPE_STANDALONE",
    "UNIT_ASSESSMENT_COUNT",
    "scope_clause", "progression_envelope", "build_envelope_from_topics",
    "plan_unit_coverage", "taught_inventory",
]

SCOPE_TOPIC = "topic"
SCOPE_UNIT = "unit"
SCOPE_STANDALONE = "standalone"

# A unit assessment is exactly ten questions. It is a product invariant, not a
# tuning knob, so it lives here and is asserted in tests rather than passed in.
UNIT_ASSESSMENT_COUNT = 10

# How much of the cumulative inventory is worth sending. Past roughly this much
# the list stops informing the generator and starts costing tokens; the tail is
# the least recently taught material, which is also the least likely to be the
# right target for the current assessment.
_MAX_INVENTORY_TERMS = 60
_MAX_INVENTORY_RULES = 12


# ── Scope ─────────────────────────────────────────────────────────────────────

_SCOPE_TEXT = {
    SCOPE_TOPIC: (
        "SCOPE — THIS TOPIC ONLY. Every item assesses a target introduced or practised in the "
        "topic above. Earlier material may appear where it is needed to make a sentence work, but "
        "it is never the thing being tested, and nothing from a later topic or another unit may "
        "appear at all. If the topic does not support {n} distinct targets, produce fewer."
    ),
    SCOPE_UNIT: (
        "SCOPE — THIS UNIT ONLY. This is the unit's closing assessment: exactly {n} questions "
        "covering the unit as a whole. Follow the coverage plan below — it allocates the {n} "
        "questions across the unit's topics by how much each actually teaches. Nothing from a "
        "later unit may appear."
    ),
    SCOPE_STANDALONE: (
        "SCOPE — THE SUPPLIED MATERIAL ONLY. Every item assesses a target taught in the source "
        "above. Nothing outside it."
    ),
}


def scope_clause(scope: str, item_count: int, coverage_plan: str = "") -> str:
    """One short paragraph naming the boundary. Not a restatement of the contract."""
    text = _SCOPE_TEXT.get(scope, _SCOPE_TEXT[SCOPE_STANDALONE]).format(n=item_count)
    if coverage_plan:
        text += "\n" + coverage_plan
    return text


# ── Progression envelope ──────────────────────────────────────────────────────

# The stem-complexity ceiling per CEFR band. This is about the language the
# QUESTION is written in, not the language it tests. Kept as short structured
# guidance because the generator needs a line it can hold, not an essay.
_STEM_BAND = {
    "A1": ("very short stems; present tense; the basic question words; one clause; "
           "no subordination; no passive; no conditional"),
    "A2": ("short stems; present and simple past; two clauses at most; common connectors; "
           "no subjunctive; no complex subordination"),
    "B1": ("ordinary everyday phrasing; common tenses including future and conditional; "
           "simple subordination; standard connectors"),
    "B2": ("fuller phrasing; a wider range of tenses and moods; subordination and "
           "discourse markers where natural"),
    "C1": ("flexible register and precise phrasing; complex structures where they serve the item"),
    "C2": ("unrestricted within natural, examiner-grade usage"),
}

# Very early in a course the band alone is still too generous: at A1 topic 2 the
# learner has met almost nothing, so the stem has to lean on the inventory.
_EARLY_COURSE_TOPICS = 4


def _band_for(level: Optional[str]) -> Tuple[str, str]:
    clean = str(level or "A1").upper().strip()
    for key in ("C2", "C1", "B2", "B1", "A2", "A1"):
        if key in clean:
            return key, _STEM_BAND[key]
    return "A1", _STEM_BAND["A1"]


def taught_inventory(contents: Sequence[Any]) -> Dict[str, List[str]]:
    """The terms and rules a sequence of already-generated lessons actually taught.

    Reads the material rather than guessing from titles: these are the exact
    fields the lesson schema publishes, so the inventory is what the learner was
    shown, not what the curriculum intended to show them.
    """
    terms: List[str] = []
    rules: List[str] = []
    seen_terms = set()
    seen_rules = set()
    for content in contents:
        if isinstance(content, str):
            try:
                import json as _json
                content = _json.loads(content or "{}")
            except Exception:
                continue
        if not isinstance(content, dict):
            continue
        for page in content.get("pages", []) or []:
            if not isinstance(page, dict):
                continue
            for item in page.get("items", []) or []:
                if not isinstance(item, dict):
                    continue
                term = str(item.get("term") or item.get("word") or "").strip()
                key = term.casefold()
                if term and key not in seen_terms:
                    seen_terms.add(key)
                    terms.append(term)
            for rule in page.get("rules", []) or []:
                if not isinstance(rule, dict):
                    continue
                name = str(rule.get("rule") or "").strip()
                key = name.casefold()
                if name and key not in seen_rules:
                    seen_rules.add(key)
                    rules.append(name)
    return {"terms": terms, "rules": rules}


def progression_envelope(
    *,
    level: str,
    language: str,
    unit_index: Optional[int] = None,
    unit_total: Optional[int] = None,
    topics_completed: int = 0,
    inventory: Optional[Dict[str, List[str]]] = None,
) -> str:
    """The language the question itself may be written in, at this point in the course.

    Deterministic: CEFR band, position in the course, and the inventory read out
    of the material already generated. No model call, and no per-item cost.
    """
    band_key, band_text = _band_for(level)
    inventory = inventory or {"terms": [], "rules": []}
    terms = [t for t in inventory.get("terms", []) if t][:_MAX_INVENTORY_TERMS]
    rules = [r for r in inventory.get("rules", []) if r][:_MAX_INVENTORY_RULES]

    where = ""
    if unit_index and unit_total:
        where = f" (unit {unit_index} of {unit_total}"
        if topics_completed:
            where += f", {topics_completed} topic(s) taught so far"
        where += ")"
    elif topics_completed:
        where = f" ({topics_completed} topic(s) taught so far)"

    lines = [
        f"ASSESSMENT LANGUAGE BUDGET — CEFR {band_key}{where}.",
        f"The learner reads {language} at this point in the course and no further. Phrase every "
        f"stem and option inside that: {band_text}.",
        "A question the learner cannot READ is not a hard question, it is a broken one. If a target "
        "cannot be tested inside this budget, test it more simply — never widen the budget.",
    ]
    if terms:
        lines.append("Vocabulary already taught (draw stem wording from here): " + ", ".join(terms))
    if rules:
        lines.append("Structures already taught: " + "; ".join(rules))
    if topics_completed and topics_completed <= _EARLY_COURSE_TOPICS and band_key in ("A1", "A2"):
        lines.append(
            "This is the very beginning of the course: keep stems to a few words, and prefer a "
            "gapped sentence or a short situational question over any instruction-heavy wording."
        )
    return "\n".join(lines)


def build_envelope_from_topics(
    *,
    level: str,
    language: str,
    prior_contents: Sequence[Any],
    unit_index: Optional[int] = None,
    unit_total: Optional[int] = None,
) -> str:
    """Convenience: read the inventory out of prior lessons and phrase the budget."""
    inventory = taught_inventory(prior_contents)
    return progression_envelope(
        level=level,
        language=language,
        unit_index=unit_index,
        unit_total=unit_total,
        topics_completed=len(list(prior_contents)),
        inventory=inventory,
    )


# ── Unit coverage planning ────────────────────────────────────────────────────

def _teaching_weight(content: Any) -> int:
    """How much a topic actually teaches, measured on its published material.

    Counting what the lesson contains beats sampling topics at random: a unit
    where one topic carries a 30-item alphabet and another carries three polite
    formulas should not split its assessment down the middle.
    """
    if isinstance(content, str):
        try:
            import json as _json
            content = _json.loads(content or "{}")
        except Exception:
            return 1
    if not isinstance(content, dict):
        return 1
    weight = 0
    for page in content.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        weight += len(page.get("items", []) or [])
        weight += 2 * len(page.get("rules", []) or [])
        weight += 2 * len(page.get("comparisons", []) or [])
    return max(1, weight)


def plan_unit_coverage(
    topics: Sequence[Dict[str, Any]],
    total: int = UNIT_ASSESSMENT_COUNT,
) -> List[Dict[str, Any]]:
    """Allocate `total` questions across a unit's topics by teaching weight.

    Deterministic and stable: every topic that teaches anything gets at least one
    question before any topic gets a second, and the remainder is distributed by
    weight with ties broken by position. That guarantees no substantial taught
    area is silently skipped, which random sampling could not.
    """
    usable = [t for t in topics if isinstance(t, dict)]
    if not usable or total <= 0:
        return []

    weights = [_teaching_weight(t.get("content")) for t in usable]

    # Floor of one each, capped by how many topics there are.
    n = len(usable)
    if n >= total:
        # More topics than questions: take the heaviest `total` topics, in order.
        ranked = sorted(range(n), key=lambda i: (-weights[i], i))[:total]
        chosen = sorted(ranked)
        return [{"topic_id": usable[i].get("id"), "title": usable[i].get("title"),
                 "questions": 1, "weight": weights[i]} for i in chosen]

    counts = [1] * n
    remaining = total - n
    if remaining:
        total_weight = sum(weights) or n
        # Largest-remainder apportionment, so the split is exact and reproducible.
        exact = [remaining * w / total_weight for w in weights]
        base = [int(e) for e in exact]
        leftover = remaining - sum(base)
        order = sorted(range(n), key=lambda i: (-(exact[i] - base[i]), i))
        for i in order[:leftover]:
            base[i] += 1
        counts = [counts[i] + base[i] for i in range(n)]

    return [{"topic_id": usable[i].get("id"), "title": usable[i].get("title"),
             "questions": counts[i], "weight": weights[i]} for i in range(n)]


def coverage_plan_clause(plan: Sequence[Dict[str, Any]]) -> str:
    """The plan as a compact instruction the generator can follow exactly."""
    if not plan:
        return ""
    rows = "; ".join(f"{p.get('title')} -> {p.get('questions')}" for p in plan)
    return f"COVERAGE PLAN (questions per topic, follow exactly): {rows}"
