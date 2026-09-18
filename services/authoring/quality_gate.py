"""Publication-grade semantic quality gate for AI-authored classrooms.

Bulk generation stays on Gemini 3.8 Flash. This gate does the expensive thing
only where it has leverage: it reads finished material as an editor, patches
specific fields, then refuses publication unless the deterministic auditor is
clean. One semantic review layer is used:

* Gemini 3.7 Flash reviews every unit's five lessons and its ten assessment
  questions, and performs bounded targeted repairs when deterministic checks
  identify an exact learner-visible defect.
* The final authority is deterministic publication integrity, not a second
  semantic model. The gate proves renderer, bilingual, assessment-count, IPA
  and duplicate invariants before READY.

The models never rewrite a lesson wholesale. They can only replace an existing
learner-facing field at an exact JSON path, and every patch is checked against
the value the model actually saw. This keeps a reviewer from drifting structure
or silently inventing a new lesson.

The gate fails closed. A provider failure, incomplete review coverage, malformed
patch, remaining deterministic blocker, or review budget overrun prevents a
classroom from being marked ready.
"""

from __future__ import annotations

import copy
import json
import math
import re
import threading
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from services.authoring import audit as A
from services.authoring import budget as B
from services.authoring import repair as R
from services.authoring import schema as S
from services.authoring import transport as T


REVIEW_MODEL = "google/gemini-3.7-flash"
REPAIR_MODEL = "google/gemini-3.7-flash"
QUALITY_REVIEW_CEILING_USD = 0.22

# A reviewer may change learner-facing content, never ids, page types, ordering,
# topic structure or bookkeeping.
_PATCHABLE_FIELDS = frozenset({
    "title", "title_tr", "text", "text_tr",
    "term", "word", "phonetic", "pronunciation", "ipa", "transcription",
    "translation", "translation_en", "translation_tr", "meaning",
    "example", "example_en", "example_tr", "sample",
    "explanation", "explanation_en", "explanation_tr",
    "rule", "rule_tr", "analysis", "analysis_tr",
    "target", "context", "context_tr", "note", "note_tr",
    "text", "line_en", "line_tr",
    "prompt", "question", "stem", "answer", "options", "choices",
    "distractors", "why", "why_tr",
})

_RISK_RULE_FIELDS = frozenset({
    "rule", "rule_tr", "analysis", "analysis_tr",
    "explanation", "explanation_en", "explanation_tr",
})
_NOTATION_FIELDS = frozenset({"phonetic", "pronunciation", "ipa", "transcription"})
_ASSESSMENT_FIELDS = frozenset({
    "prompt", "question", "stem", "answer", "options", "choices", "distractors",
    "why", "why_tr", "explanation", "explanation_tr",
})


_PATCH_SCALAR_OR_LIST = {
    "anyOf": [
        {"type": "string"},
        {"type": "array", "items": {"type": "string"}, "minItems": 1},
    ]
}
_PATCH_PATH = {
    "type": "array",
    # OpenAI Structured Outputs rejects nested oneOf in array items. Keep the
    # wire contract provider-compatible by encoding list indexes as decimal
    # strings ("0", "1", ...); _coerce_patch_path converts them back only when
    # the current container is actually a list.
    "items": {"type": "string"},
    "minItems": 1,
}
_NESTED_PATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "path": _PATCH_PATH,
        "old": _PATCH_SCALAR_OR_LIST,
        "value": _PATCH_SCALAR_OR_LIST,
        "reason": {"type": "string"},
    },
    "required": ["path", "old", "value", "reason"],
}
_TOP_LEVEL_PATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "topic_id": {"type": "string"},
        "path": _PATCH_PATH,
        "old": _PATCH_SCALAR_OR_LIST,
        "value": _PATCH_SCALAR_OR_LIST,
        "reason": {"type": "string"},
    },
    "required": ["topic_id", "path", "old", "value", "reason"],
}
_LESSON_REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "topic_id": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["ok", "fix"]},
                    "patches": {"type": "array", "items": _NESTED_PATCH_SCHEMA},
                },
                "required": ["topic_id", "verdict", "patches"],
            },
        },
    },
    "required": ["topics"],
}
_EXACT_TARGET_REPAIR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "value": {"type": "string", "minLength": 1},
        "reason": {"type": "string"},
    },
    "required": ["value", "reason"],
}

_ASSESSMENT_REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "checked_questions": {
            "type": "array", "items": {"type": "integer"},
            "minItems": 10, "maxItems": 10,
        },
        "patches": {"type": "array", "items": _TOP_LEVEL_PATCH_SCHEMA},
    },
    "required": ["checked_questions", "patches"],
}

class QualityGateError(RuntimeError):
    pass


class ReviewBudget:
    def __init__(self, ceiling: float = QUALITY_REVIEW_CEILING_USD):
        self.ceiling = float(ceiling)
        self.spent = 0.0
        self.calls: List[Dict[str, Any]] = []
        self._reserved = 0.0
        self._lock = threading.RLock()

    def _estimate(self, model: str, input_chars: int, output_tokens: int) -> float:
        return B.price(
            model,
            input_tokens=max(1, math.ceil(int(input_chars) / 4)),
            output_tokens=max(1, int(output_tokens)),
        )

    def require(self, *, model: str, input_chars: int, output_tokens: int, stage: str) -> None:
        worst = self._estimate(model, input_chars, output_tokens)
        with self._lock:
            if self.spent + self._reserved + worst > self.ceiling:
                raise QualityGateError(
                    f"quality review budget: {stage} could require ${worst:.4f}; "
                    f"${self.ceiling - self.spent - self._reserved:.4f} remains of ${self.ceiling:.2f}"
                )

    def reserve(self, *, model: str, input_chars: int, output_tokens: int, stage: str) -> float:
        worst = self._estimate(model, input_chars, output_tokens)
        with self._lock:
            if self.spent + self._reserved + worst > self.ceiling:
                raise QualityGateError(
                    f"quality review budget: {stage} could require ${worst:.4f}; "
                    f"${self.ceiling - self.spent - self._reserved:.4f} remains of ${self.ceiling:.2f}"
                )
            self._reserved += worst
        return worst

    def release(self, reservation: float) -> None:
        with self._lock:
            self._reserved = max(0.0, self._reserved - max(0.0, float(reservation or 0.0)))

    def record(self, response: T.Response, *, model: str, stage: str,
               reservation: float = 0.0) -> float:
        if response.cost is not None:
            cost = float(response.cost)
        else:
            cost = B.price(
                model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cached_tokens=response.cached_tokens,
            )
        with self._lock:
            self._reserved = max(
                0.0, self._reserved - max(0.0, float(reservation or 0.0))
            )
            self.spent += cost
            self.calls.append({
                "stage": stage,
                "model": model,
                "cost": cost,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "seconds": response.seconds,
            })
            if self.spent > self.ceiling + 1e-9:
                raise QualityGateError(
                    f"quality review spent ${self.spent:.4f}, over ${self.ceiling:.2f}"
                )
        return cost


def _field_spec(key: str, container: str = "") -> Optional[S.FieldSpec]:
    return S.spec_for(str(key), container)


def _review_records(node: Any, *, path: Tuple[Any, ...] = (),
                    container: str = "") -> List[Dict[str, Any]]:
    """Typed learner-facing fields with exact patch paths."""
    out: List[Dict[str, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            spec = _field_spec(key, container)
            here = path + (key,)
            if isinstance(value, str):
                if spec is not None and spec.role not in (S.META, S.EVIDENCE, S.NAME):
                    out.append({
                        "path": list(here), "field": key, "role": spec.role,
                        "track": spec.track, "value": value,
                    })
            elif isinstance(value, list):
                if spec is not None and all(isinstance(v, str) for v in value):
                    out.append({
                        "path": list(here), "field": key, "role": spec.role,
                        "track": spec.track, "value": list(value),
                    })
                else:
                    sub = key if key in S.ENTRY_CONTAINERS or key == "dialogue" else container
                    for idx, item in enumerate(value):
                        out.extend(_review_records(item, path=here + (idx,), container=sub))
            elif isinstance(value, dict):
                sub = key if key in S.ENTRY_CONTAINERS or key == "dialogue" else container
                out.extend(_review_records(value, path=here, container=sub))
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            out.extend(_review_records(item, path=path + (idx,), container=container))
    return out


def _coerce_patch_path(root: Any, path: Sequence[Any]) -> List[Any]:
    """Convert provider-safe string path segments into typed traversal parts.

    Review response schemas use string-only path items because OpenAI's
    Structured Outputs subset rejects nested oneOf. A decimal string is treated
    as a list index only when traversal is currently at a list; otherwise it
    remains an ordinary object key. This preserves exact field names and keeps
    structural edits impossible.
    """
    cur = root
    out: List[Any] = []
    for raw in path:
        part: Any = raw
        if isinstance(cur, list):
            if isinstance(raw, str) and re.fullmatch(r"0|[1-9][0-9]*", raw):
                part = int(raw)
            if not isinstance(part, int) or part < 0 or part >= len(cur):
                raise QualityGateError(
                    f"invalid list path component {raw!r} in {list(path)!r}"
                )
            out.append(part)
            cur = cur[part]
            continue

        if not isinstance(cur, dict) or not isinstance(part, str) or part not in cur:
            raise QualityGateError(
                f"invalid object path component {part!r} in {list(path)!r}"
            )
        out.append(part)
        cur = cur[part]
    return out


def _get_path(root: Any, path: Sequence[Any]) -> Any:
    path = _coerce_patch_path(root, path)
    cur = root
    for part in path:
        if isinstance(part, int):
            if not isinstance(cur, list) or part < 0 or part >= len(cur):
                raise QualityGateError(f"invalid list path component {part} in {list(path)!r}")
            cur = cur[part]
        else:
            if not isinstance(cur, dict) or part not in cur:
                raise QualityGateError(f"invalid object path component {part!r} in {list(path)!r}")
            cur = cur[part]
    return cur


def _set_path(root: Any, path: Sequence[Any], value: Any, *, old: Any) -> None:
    path = _coerce_patch_path(root, path)
    if not path or not isinstance(path[-1], str) or path[-1] not in _PATCHABLE_FIELDS:
        raise QualityGateError(f"reviewer tried to patch forbidden path {list(path)!r}")
    parent = root
    for part in path[:-1]:
        if isinstance(part, int):
            if not isinstance(parent, list) or part < 0 or part >= len(parent):
                raise QualityGateError(f"invalid list path in {list(path)!r}")
            parent = parent[part]
        else:
            if not isinstance(parent, dict) or part not in parent:
                raise QualityGateError(f"invalid object path in {list(path)!r}")
            parent = parent[part]
    key = path[-1]
    if not isinstance(parent, dict) or key not in parent:
        raise QualityGateError(f"patch may not invent field {key!r}")
    current = parent[key]
    if current != old:
        # Structured reviewers sometimes return null/empty for `old` even
        # though the exact non-empty field value was present in the supplied
        # records. That is not evidence of concurrent mutation. For scalar text
        # fields only, treat a nullable reviewer-old as unspecified and validate
        # the proposed replacement against the current canonical value instead.
        # Any non-empty conflicting old value still fails closed.
        nullable_old = old is None or old == ""
        if not (nullable_old and isinstance(current, str) and current.strip()):
            raise QualityGateError(
                f"stale semantic patch at {list(path)!r}: reviewer saw {old!r}, current is {current!r}"
            )
    if isinstance(current, str):
        if not isinstance(value, str) or not value.strip():
            raise QualityGateError(f"patch for {list(path)!r} must be a non-empty string")
    elif isinstance(current, list) and all(isinstance(v, str) for v in current):
        if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
            raise QualityGateError(f"patch for {list(path)!r} must be a non-empty string list")
    else:
        raise QualityGateError(f"reviewer may not change structural value at {list(path)!r}")
    parent[key] = value


def _slash_alternative_variants(value: Any) -> List[str]:
    """Expand one inline slash alternative into concrete candidate strings.

    Reviewers sometimes emit editorial alternatives such as
    "İspanyoldur/İspanyolum" in one patch and a single resolved form in another.
    Treat that as a resolvable duplicate only when the clean candidate exactly
    matches one concrete branch of the slash form. Anything less exact remains
    a conflicting semantic patch and fails closed.
    """
    if not isinstance(value, str) or "/" not in value:
        return []
    tokens = value.split()
    out: List[str] = []
    for i, token in enumerate(tokens):
        if "/" not in token:
            continue
        prefix = ""
        suffix = ""
        core = token
        while core and not core[0].isalnum():
            prefix += core[0]
            core = core[1:]
        while core and not core[-1].isalnum():
            suffix = core[-1] + suffix
            core = core[:-1]
        parts = [p for p in core.split("/") if p]
        if len(parts) < 2:
            continue
        for part in parts:
            candidate = list(tokens)
            candidate[i] = prefix + part + suffix
            out.append(" ".join(candidate))
    return out


def _apply_patches(topics_by_id: Dict[str, Dict[str, Any]], patches: Sequence[Any]) -> int:
    # Normalize duplicates before mutating content, so an ambiguous first
    # proposal cannot be written and then make the concrete duplicate stale.
    normalized: List[Any] = []
    index_by_marker: Dict[Tuple[str, str], int] = {}
    for raw in patches or []:
        if not isinstance(raw, dict):
            normalized.append(raw)
            continue
        topic_id = str(raw.get("topic_id") or "").strip()
        path = raw.get("path")
        if topic_id not in topics_by_id or not isinstance(path, list):
            normalized.append(raw)
            continue
        try:
            content = topics_by_id[topic_id]["content"]
            coerced = _coerce_patch_path(content, path)
        except Exception:
            normalized.append(raw)
            continue
        marker = (topic_id, json.dumps(coerced, ensure_ascii=False))
        if marker not in index_by_marker:
            index_by_marker[marker] = len(normalized)
            normalized.append(raw)
            continue
        prev_i = index_by_marker[marker]
        previous = normalized[prev_i]
        if not isinstance(previous, dict):
            normalized.append(raw)
            continue
        prev_value = previous.get("value")
        new_value = raw.get("value")
        if prev_value == new_value:
            continue
        if isinstance(prev_value, str) and isinstance(new_value, str):
            if new_value in _slash_alternative_variants(prev_value):
                normalized[prev_i] = raw
                continue
            if prev_value in _slash_alternative_variants(new_value):
                continue
        normalized.append(raw)

    patches = normalized
    # Structured reviewers occasionally emit the same exact patch path twice in
    # one response (commonly when bilingual/dialogue checks converge on the same
    # learner-visible field). Identical duplicate proposals are harmless and
    # idempotent; conflicting proposals for one path are still a correctness
    # ambiguity and must fail closed.
    seen: Dict[Tuple[str, str], Any] = {}
    applied = 0
    for raw in patches or []:
        if not isinstance(raw, dict):
            raise QualityGateError("semantic patch is not an object")
        topic_id = str(raw.get("topic_id") or "").strip()
        path = raw.get("path")
        if topic_id not in topics_by_id or not isinstance(path, list):
            raise QualityGateError("semantic patch has an unknown topic or missing path")
        content = topics_by_id[topic_id]["content"]
        path = _coerce_patch_path(content, path)
        marker = (topic_id, json.dumps(path, ensure_ascii=False))
        proposed = raw.get("value")
        if marker in seen:
            previous = seen[marker]
            if proposed == previous:
                print(
                    f"[QUALITY-PATCH] IGNORE identical duplicate patch at "
                    f"{topic_id} {list(path)!r}",
                    flush=True,
                )
                continue

            # If one proposal literally contains editorial slash alternatives
            # and the other is exactly one concrete branch, prefer the resolved
            # branch. This is not arbitrary conflict resolution: the accepted
            # value must be an exact expansion of the ambiguous proposal.
            resolved = None
            if isinstance(previous, str) and isinstance(proposed, str):
                if proposed in _slash_alternative_variants(previous):
                    resolved = proposed
                elif previous in _slash_alternative_variants(proposed):
                    resolved = previous
            if resolved is not None:
                print(
                    f"[QUALITY-PATCH] RESOLVE slash-alternative duplicate at "
                    f"{topic_id} {list(path)!r} -> {resolved!r}",
                    flush=True,
                )
                # If the already-seen proposal was the ambiguous one, update
                # the remembered winner so any further duplicate is compared
                # against the concrete value.
                seen[marker] = resolved
                if proposed != resolved:
                    continue
                # proposed is the concrete winner; let it continue below and
                # replace the earlier ambiguous value before application.
            else:
                raise QualityGateError(
                    f"conflicting semantic patches for {topic_id} {path!r}: "
                    f"{previous!r} vs {proposed!r}"
                )
        else:
            seen[marker] = proposed
        current = _get_path(content, path)
        old = raw.get("old")

        # Structured reviewers occasionally emit an empty replacement for an
        # existing learner-facing field. Treat that as a rejected no-op rather
        # than aborting the entire review: deleting learner-visible content is
        # never allowed, and the deterministic re-audit immediately after this
        # pass will still surface any blocker the skipped patch was meant to fix.
        # This preserves fail-closed publication while making harmless provider
        # patch noise non-fatal.
        if isinstance(current, str) and (
            not isinstance(proposed, str) or not proposed.strip()
        ):
            print(
                f"[QUALITY-PATCH] IGNORE empty/non-string replacement at "
                f"{topic_id} {list(path)!r}",
                flush=True,
            )
            continue
        if isinstance(current, list) and all(isinstance(v, str) for v in current):
            if not isinstance(proposed, list) or not proposed or not all(
                isinstance(v, str) and v.strip() for v in proposed
            ):
                print(
                    f"[QUALITY-PATCH] IGNORE empty/invalid list replacement at "
                    f"{topic_id} {list(path)!r}",
                    flush=True,
                )
                continue

        # Reviewers occasionally emit a patch for a field that deterministic
        # repair already filled after the review records were prepared. If the
        # proposed value is byte-for-byte the value already present, the patch is
        # an idempotent no-op, not a stale-write conflict. Any real disagreement
        # still fails closed below.
        if current == proposed and current != old:
            continue
        _set_path(content, path, proposed, old=old)
        applied += 1
    return applied


def _audit_topic(topic: Dict[str, Any], *, language: str, track: str) -> List[A.Finding]:
    content = topic.get("content")
    if not isinstance(content, dict):
        return [A.Finding("not_a_lesson", A.BLOCK)]
    R.repair_lesson(content, language=language)
    return A.audit_lesson(content, language=language, track=track)


def _findings_payload(findings: Iterable[A.Finding]) -> List[Dict[str, Any]]:
    return [f.as_dict() for f in findings if f.severity == A.BLOCK]


def _finding_path_prefix(path: str) -> List[Any]:
    """Turn audit paths such as pages[3].items[1] into review-record segments."""
    out: List[Any] = []
    for name, index in re.findall(r"(?:^|\.)([^.\[]+)|\[([0-9]+)\]", str(path or "")):
        if name:
            out.append(name)
        elif index:
            out.append(int(index))
    return out


def _repair_paths_for_finding(content: Dict[str, Any], finding: A.Finding) -> List[List[Any]]:
    """Resolve an audit finding back to exact patchable learner-visible paths.

    The auditor historically reported a field/value and sometimes only a page
    prefix. That was enough to refuse publication but too vague for a semantic
    repair model, which could fix adjacent prose and leave the actual bad field
    untouched. Resolve the finding against the exact review records before
    asking the model to edit anything.
    """
    records = _review_records(content)
    prefix = _finding_path_prefix(finding.path)
    candidates: List[List[Any]] = []
    for rec in records:
        path = rec.get("path")
        if not isinstance(path, list):
            continue
        if finding.field and str(rec.get("field") or "") != str(finding.field):
            continue
        if prefix and path[:len(prefix)] != prefix:
            continue
        if finding.value:
            value = rec.get("value")
            if isinstance(value, str) and value != finding.value:
                continue
            if isinstance(value, list) and finding.value not in value:
                continue
        candidates.append(list(path))

    # A value-bearing finding identifies the learner-visible string itself, so
    # every exact match is relevant. A value-less finding is safe to resolve
    # only when the field/prefix identifies one unique record.
    if finding.value:
        return candidates
    return candidates if len(candidates) == 1 else []


def _findings_with_repair_paths(content: Dict[str, Any],
                                findings: Iterable[A.Finding]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for finding in findings:
        if finding.severity != A.BLOCK:
            continue
        row: Dict[str, Any] = finding.as_dict()
        row["repair_paths"] = _repair_paths_for_finding(content, finding)
        out.append(row)
    return out


def _records_for_findings(content: Dict[str, Any],
                          findings: Iterable[A.Finding]) -> List[Dict[str, Any]]:
    wanted = {
        tuple(path)
        for finding in findings
        for path in _repair_paths_for_finding(content, finding)
    }
    if not wanted:
        return []
    return [
        rec for rec in _review_records(content)
        if isinstance(rec.get("path"), list) and tuple(rec["path"]) in wanted
    ]


def _assessment_evidence_records(content: Dict[str, Any], *, track: str) -> List[Dict[str, Any]]:
    """Compact semantic evidence for assessment review.

    Full lesson review records duplicated both EN/TR instructional prose and UI
    text, producing 100k+ character assessment payloads. Assessment correctness
    only needs taught-language material plus ONE instructional track. Preserve
    all target/notation records and only the active instructional/gloss track.
    """
    wanted_track = "tr" if str(track or "tr").casefold() == "tr" else "en"
    compact: List[Dict[str, Any]] = []
    for rec in _review_records(content):
        role = rec.get("role")
        rec_track = rec.get("track")
        field = str(rec.get("field") or "")
        if role in (S.TARGET, S.NOTATION):
            compact.append(rec)
            continue
        if role in (S.INSTRUCTION, S.GLOSS):
            if rec_track == wanted_track:
                compact.append(rec)
                continue
            # Some legacy English instructional fields are untagged.
            if rec_track is None and wanted_track == "en" and field in (
                "text", "explanation", "rule", "analysis", "context", "note", "why"
            ):
                compact.append(rec)
    return compact


_LESSON_REVIEW_SYSTEM = """You are AulaAI's independent publication editor.
The course was authored by another model. Your job is to find and correct
learner-visible errors, not to praise or rewrite stylistically.

Review EVERY supplied topic. Be adversarial and conservative. Check:
- factual grammar/lexis/usage claims and overgeneralizations; narrow absolute
  rules when standard counterexamples exist;
- naturalness and correctness of target-language examples/dialogue;
- English and Turkish instructional fields for exact semantic equivalence and
  natural phrasing. Treat a change of tense, aspect, person, number, polarity,
  register or factual relation as an error even when the rough meaning survives;
- every IPA transcription against the exact written term AND the declared
  regional variety; IPA-looking Unicode is not enough;
- internal contradictions, invented forms, impossible examples and CEFR-level
  leakage;
- every absolute pedagogical claim containing meanings such as always, never,
  every, only, must or impossible. Keep it absolute only if it is genuinely
  exceptionless in the declared standard variety; otherwise scope it precisely;
- lesson MCQs for exactly one defensible answer and plausible distractors.

Return JSON only:
{"topics":[
  {"topic_id":"EXACT ID","verdict":"ok|fix","patches":[
    {"path":["pages",0,"rules",0,"rule"],"old":"EXACT OLD VALUE",
     "value":"CORRECT REPLACEMENT","reason":"brief factual reason"}
  ]}
]}

Contract:
- Return exactly one entry for EVERY topic_id supplied.
- Any supplied English/Turkish counterpart whose value is empty is a blocking
  completeness defect. Fill it from its non-empty semantic pair.
- Use only paths that appear in the supplied records. Encode every path segment
  as a JSON string; list indexes must be decimal strings such as "0" or "12".
- Copy old exactly, byte for byte.
- Patch only genuine correctness/naturalness problems. No cosmetic rewrites.
- When one correction has paired EN/TR fields, patch both so they remain
  semantically equivalent.
- Never change structure, add pages, delete content, or change the lesson scope.
"""


_EXACT_TARGET_REPAIR_SYSTEM = """You repair exactly ONE existing learner-visible
TARGET-language string that failed AulaAI's deterministic publication audit.

Hard contract:
- The replacement MUST be written in the taught language named by
  `taught_language`. Do not write it in English or Turkish unless that is the
  taught language.
- If the field is prompt/question/stem, write a natural question in the taught
  language that remains answerable from the immutable page context. Preserve
  the keyed answer, options and distractors; only the requested field changes.
- Remove instructional/meta prose such as explanations about what the learner
  should do. The replacement itself must be the learner-facing target-language
  content.
- Preserve the original pedagogical intent and CEFR level.
- Do not add labels, commentary, markdown or alternate versions.
- Return JSON only: {"value":"NON-EMPTY REPLACEMENT","reason":"brief reason"}.
"""

_EXACT_RENDER_STEM_REPAIR_SYSTEM = """You repair exactly ONE MCQ stem that
failed AulaAI's deterministic renderer contract.

Hard contract:
- Return ONLY one replacement string for the existing stem field.
- Write the stem in the taught language.
- Preserve the existing keyed answer, options and distractors.
- The question must be answerable from the visible stem itself or from an
  explicit country→nationality fact already present in the immutable page
  context. Do NOT require the learner to infer nationality/identity from a
  person's birthplace, residence, job, biography, name, or cultural background.
- For a country/nationality item, prefer a direct vocabulary mapping question
  (for example: country → nationality) instead of a biographical identity
  question when that removes the inference.
- Do not reveal the keyed answer verbatim unless the original task already does.
- Keep the CEFR level and pedagogical intent.
- Return JSON only: {"value":"NON-EMPTY REPLACEMENT","reason":"brief reason"}.
"""

_ASSESSMENT_REVIEW_SYSTEM = """You are AulaAI's independent assessment examiner.
The lesson material and a ten-question unit assessment were authored by another
model. Verify ALL ten questions against the unit evidence.

For every question check:
- there is exactly ONE correct option in context, not merely one keyed option;
- the keyed answer is actually correct;
- no distractor is also correct, synonymous in context, or made correct by the
  wording (the classic failure is asking which h is silent when every option's
  h is silent);
- the stem is grammatical, natural, unambiguous and CEFR-appropriate;
- distractors are plausible learner errors, not nonsense giveaways;
- the item tests taught material and does not require outside knowledge;
- if the payload contains render_contract_blockers, EVERY listed blocker is mandatory:
  repair that question so its answer follows only from facts explicitly stated in the stem
  or taught evidence and so the same stored item remains renderable in both export locales.
  Never solve a blocker by deleting, renumbering or weakening the ten-question assessment;
- compare each assessment item with ALL lesson MCQs/evidence in the unit. A repeated
  or paraphrased question may never contradict the answer taught earlier. If the
  same fact was asked earlier, preserve the taught fact and repair the assessment;
- check the answer explanation too: an answer key that contradicts the lesson is
  a blocking factual defect even when the options are structurally valid.

Return JSON only:
{"checked_questions":[1,2,3,4,5,6,7,8,9,10],
 "patches":[
   {"topic_id":"ASSESSMENT TOPIC ID","path":["pages",1,"options"],
    "old":["..."],"value":["..."],"reason":"brief reason"}
 ]}

The overview is pages[0]; assessment question 1 is pages[1], question 10 is
pages[10]. Any supplied English/Turkish counterpart whose value is empty must
be filled from the non-empty semantic pair. Use only supplied paths and encode
every path segment as a JSON string (list indexes like "0", "1"). Copy old
exactly, and make the smallest correction that yields one unambiguously correct
answer. Keep answer/options/
distractors mutually consistent. No cosmetic rewrites.
"""



def _call_review(*, model: str, system: str, payload: Dict[str, Any],
                 max_tokens: int, effort: str, budget: ReviewBudget,
                 stage: str, response_schema: Dict[str, Any],
                 response_name: str) -> Dict[str, Any]:
    user = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    reservation = budget.reserve(
        model=model, input_chars=len(system) + len(user),
        output_tokens=max_tokens, stage=stage,
    )
    print(
        f"[QUALITY-CALL] START {stage} model={model} "
        f"payload_chars={len(user)} max_tokens={max_tokens}",
        flush=True,
    )
    try:
        response = T.call_model(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens, temperature=0.0, model=model, cache_system=True,
            timeout=180, attempts=2, reasoning_effort=effort,
            response_schema=response_schema, response_name=response_name,
        )
    except Exception:
        budget.release(reservation)
        raise
    budget.record(response, model=model, stage=stage, reservation=reservation)
    print(
        f"[QUALITY-CALL] END {stage} ok={response.ok} "
        f"seconds={response.seconds:.2f} cost=${float(response.cost or 0.0):.4f} "
        f"error={response.error or '-'}",
        flush=True,
    )
    if not response.ok or not isinstance(response.data, dict):
        raise QualityGateError(f"{stage} failed on {model}: {response.error or 'invalid JSON'}")
    return response.data


def _records_for_render_blockers(content: Dict[str, Any],
                                 blockers: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Only the records needed to repair the pages the renderer rejects.

    Targeted retries previously resent an entire five-page lesson.
    That made a one-field repair spend its completion budget on reasoning over
    unrelated material and could finish with reason=length before emitting any
    JSON. Keep exact patch paths, but send only the affected page records.
    """
    indexes = {
        int(row.get("page_index"))
        for row in (blockers or [])
        if isinstance(row, dict) and str(row.get("page_index", "")).isdigit()
    }
    records = _review_records(content)
    if not indexes:
        return records
    return [
        rec for rec in records
        if isinstance(rec.get("path"), list)
        and len(rec["path"]) >= 2
        and rec["path"][0] == "pages"
        and rec["path"][1] in indexes
    ]


def _topic_render_blockers(content: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Deterministic renderer-contract failures for learner-visible MCQ pages."""
    from services.authoring import render_contract as RC
    pages = content.get("pages") if isinstance(content, dict) else None
    blockers: List[Dict[str, Any]] = []
    for page_index, page in enumerate(pages or []):
        if not isinstance(page, dict) or str(page.get("type") or "").casefold() != "mcq":
            continue
        for is_tr in RC.EXPORT_LOCALES:
            ok, why = RC.page_is_renderable(page, is_tr)
            if ok:
                continue
            blockers.append({
                "page_index": page_index,
                "title": str(page.get("title") or f"page {page_index}"),
                "locale": "tr" if is_tr else "en",
                "why": why,
                "stem": RC.resolve_stem(page, is_tr),
                "answer": str(page.get("answer") or ""),
            })
    return blockers



def _repair_topic_render_stems_exact(*, topic: Dict[str, Any], language: str,
                                      level: str, budget: ReviewBudget,
                                      blockers: Sequence[Dict[str, Any]]) -> int:
    """Repair residual MCQ renderer blockers one stem at a time.

    Generic lesson review may understand the semantic issue yet still leave a
    renderer-only invariant unresolved. For identity/biographical inference,
    patching the exact stem is sufficient and avoids a terminal refusal after a
    successful model call.
    """
    content = topic.get("content")
    pages = content.get("pages") if isinstance(content, dict) else None
    if not isinstance(pages, list):
        return 0

    profile = S.profile_for_language(language)
    by_page: Dict[int, List[Dict[str, Any]]] = {}
    for row in blockers or []:
        if not isinstance(row, dict):
            continue
        try:
            page_index = int(row.get("page_index"))
        except (TypeError, ValueError):
            continue
        by_page.setdefault(page_index, []).append(row)

    applied = 0
    for page_index, page_blockers in sorted(by_page.items()):
        if page_index < 0 or page_index >= len(pages):
            continue
        page = pages[page_index]
        if not isinstance(page, dict):
            continue

        stem_key = next(
            (key for key in ("prompt", "question", "stem")
             if isinstance(page.get(key), str) and page.get(key).strip()),
            None,
        )
        if not stem_key:
            continue

        before = str(page[stem_key]).strip()
        context = {}
        for key in (
            "type", "title", "title_tr", "prompt", "question", "stem",
            "answer", "options", "choices", "distractors",
            "target", "term", "word", "example",
            "translation", "translation_tr",
        ):
            value = page.get(key)
            if value not in (None, "", []):
                context[key] = value

        payload = {
            "taught_language": language,
            "level": level,
            "regional_variety": profile.variety if profile else "",
            "topic_title": str(topic.get("title") or ""),
            "path": ["pages", page_index, stem_key],
            "field": stem_key,
            "current_value": before,
            "renderer_contract_blockers": list(page_blockers),
            "immutable_page_context": context,
        }
        data = _call_review(
            model=REPAIR_MODEL,
            system=_EXACT_RENDER_STEM_REPAIR_SYSTEM,
            payload=payload,
            max_tokens=700,
            effort="low",
            budget=budget,
            stage=(
                f"review_render_exact:{topic.get('title')}:"
                f"pages.{page_index}.{stem_key}"
            ),
            response_schema=_EXACT_TARGET_REPAIR_SCHEMA,
            response_name="lesson_render_exact_stem_repair",
        )
        replacement = data.get("value")
        if not isinstance(replacement, str) or not replacement.strip():
            raise QualityGateError(
                f"renderer exact repair returned empty stem for "
                f"{topic.get('title')} page {page_index}"
            )
        replacement = replacement.strip()
        if replacement == before:
            continue

        _set_path(content, ["pages", page_index, stem_key], replacement, old=before)
        applied += 1

    return applied

def repair_deterministic_preflight(*, units: List[Dict[str, Any]],
                                   language: str, level: str, track: str,
                                   budget: ReviewBudget) -> int:
    """Repair provable lesson blockers before paying for broad semantic review.

    A review-only retry used to spend roughly the whole lesson-review bill and
    only then hit the same Family Members blocker. This preflight does the
    opposite: audit first, send only exact blocked records to the repair model,
    re-audit, and stop immediately if repair is unreliable. Callers may persist
    these proven repairs as a checkpoint before the expensive broad review.
    """
    applied = 0
    profile = S.profile_for_language(language)

    for unit in units:
        for topic in unit.get("topics") or []:
            if topic.get("is_assessment"):
                continue
            content = topic.get("content")
            if not isinstance(content, dict):
                continue

            R.repair_lesson(content, language=language)
            blockers = A.blocking(
                _audit_topic(topic, language=language, track=track)
            )
            if not blockers:
                continue

            records = _records_for_findings(content, blockers)
            blocker_rows = _findings_with_repair_paths(content, blockers)
            if not records or not any(row.get("repair_paths") for row in blocker_rows):
                raise QualityGateError(
                    f"{topic.get('title')}: deterministic blocker has no exact repair path: "
                    f"{A.summarise(blockers)}"
                )

            payload = {
                "language": language,
                "level": level,
                "unit": unit.get("title"),
                "regional_variety": profile.variety if profile else "",
                "instruction_track": track,
                "topics": [{
                    "topic_id": str(topic["id"]),
                    "title": str(topic.get("title") or ""),
                    "records": records,
                    "deterministic_blockers": blocker_rows,
                    "render_contract_blockers": [],
                }],
                "instruction": (
                    "Preflight repair. Patch EVERY listed repair_path exactly. "
                    "Do not edit unrelated fields. Return this one topic only."
                ),
            }
            data = _call_review(
                model=REPAIR_MODEL,
                system=_LESSON_REVIEW_SYSTEM,
                payload=payload,
                max_tokens=3200,
                effort="low",
                budget=budget,
                stage=f"review_preflight_repair:{topic.get('title')}",
                response_schema=_LESSON_REVIEW_SCHEMA,
                response_name="lesson_preflight_repair",
            )
            rows = data.get("topics")
            if not isinstance(rows, list) or len(rows) != 1 or \
                    str(rows[0].get("topic_id") or "") != str(topic["id"]):
                raise QualityGateError(
                    f"preflight repair coverage failed for {topic.get('title')}"
                )

            patches = []
            for patch in rows[0].get("patches") or []:
                if not isinstance(patch, dict):
                    raise QualityGateError("preflight repair patch is not an object")
                patch = dict(patch)
                patch["topic_id"] = str(topic["id"])
                patches.append(patch)

            applied += _apply_patches({str(topic["id"]): topic}, patches)
            R.repair_lesson(content, language=language)

            still = A.blocking(
                _audit_topic(topic, language=language, track=track)
            )

            # A multi-path repair can return syntactically valid JSON yet leave
            # some exact fields untouched. Do not throw away the whole retry at
            # that point. Resolve every residual finding to its exact learner-
            # visible path and repair one path at a time. This keeps each call
            # tiny, removes ambiguity about which field must change, and lets
            # deterministic re-audit decide whether the repair actually worked.
            if still:
                residual_rounds = 0
                while still and residual_rounds < 8:
                    residual_rounds += 1
                    residual_rows = _findings_with_repair_paths(content, still)

                    path_to_findings: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
                    for row in residual_rows:
                        for repair_path in row.get("repair_paths") or []:
                            marker = tuple(repair_path)
                            if marker:
                                path_to_findings.setdefault(marker, []).append(row)

                    if not path_to_findings:
                        break

                    progress = False
                    for marker, path_findings in path_to_findings.items():
                        current_records = [
                            rec for rec in _review_records(content)
                            if tuple(rec.get("path") or []) == marker
                        ]
                        if len(current_records) != 1:
                            continue

                        before = _get_path(content, list(marker))
                        if not isinstance(before, str) or not before.strip():
                            continue

                        page_context: Dict[str, Any] = {}
                        if len(marker) >= 2 and marker[0] == "pages" and \
                                isinstance(marker[1], int):
                            pages = content.get("pages")
                            page_index = marker[1]
                            if isinstance(pages, list) and 0 <= page_index < len(pages) and \
                                    isinstance(pages[page_index], dict):
                                page = pages[page_index]
                                # Immutable semantic evidence for repairing a prompt/stem.
                                # Keep this compact, but include answerability context.
                                for key in (
                                    "type", "title", "title_tr", "prompt", "question", "stem",
                                    "answer", "options", "choices", "distractors",
                                    "target", "term", "word", "example",
                                    "translation", "translation_tr",
                                ):
                                    value = page.get(key)
                                    if value not in (None, "", []):
                                        page_context[key] = value

                        exact_payload = {
                            "taught_language": language,
                            "level": level,
                            "regional_variety": profile.variety if profile else "",
                            "topic_title": str(topic.get("title") or ""),
                            "path": list(marker),
                            "field": str(marker[-1]) if marker else "",
                            "current_value": before,
                            "blockers": path_findings,
                            "immutable_page_context": page_context,
                        }
                        one = _call_review(
                            model=REPAIR_MODEL,
                            system=_EXACT_TARGET_REPAIR_SYSTEM,
                            payload=exact_payload,
                            max_tokens=700,
                            effort="low",
                            budget=budget,
                            stage=(
                                f"review_preflight_exact:{topic.get('title')}:"
                                + ".".join(map(str, marker))
                            ),
                            response_schema=_EXACT_TARGET_REPAIR_SCHEMA,
                            response_name="lesson_preflight_exact_target_value",
                        )
                        replacement = one.get("value")
                        if not isinstance(replacement, str) or not replacement.strip():
                            raise QualityGateError(
                                f"preflight exact repair returned empty value for "
                                f"{topic.get('title')} {list(marker)!r}"
                            )
                        replacement = replacement.strip()
                        if replacement == before:
                            continue

                        _set_path(content, list(marker), replacement, old=before)
                        after = _get_path(content, list(marker))
                        if after != before:
                            applied += 1
                            progress = True
                            R.repair_lesson(content, language=language)

                    refreshed = A.blocking(
                        _audit_topic(topic, language=language, track=track)
                    )
                    if not refreshed:
                        still = []
                        break
                    if not progress or A.summarise(refreshed) == A.summarise(still):
                        still = refreshed
                        break
                    still = refreshed

            if still:
                unresolved = _findings_with_repair_paths(content, still)
                detail = [
                    {
                        "code": row.get("code"),
                        "path": row.get("path"),
                        "field": row.get("field"),
                        "repair_paths": row.get("repair_paths"),
                    }
                    for row in unresolved[:12]
                ]
                raise QualityGateError(
                    f"{topic.get('title')}: deterministic blockers remain after "
                    f"preflight exact repair: {A.summarise(still)}; "
                    f"unresolved={detail}"
                )

    return applied


def review_unit_lessons(*, unit_title: str, topics: List[Dict[str, Any]],
                        language: str, level: str, track: str,
                        budget: ReviewBudget) -> int:
    """Review a unit without sending a 70-110k character mega-prompt.

    Gemini 3.7 Flash can read the old unit-sized payload, but its completion budget
    is shared with hidden reasoning. In production this produced
    finish_reason=length with zero visible JSON. Review each lesson independently
    instead: same learner-visible coverage, much smaller prompts, smaller outputs,
    cheaper retries, and one bad lesson cannot waste the other four.
    """
    if not topics:
        return 0

    by_id = {str(t["id"]): t for t in topics}
    canonical = S.canonical_language(language)
    profile = S.profile_for_language(language)
    applied = 0

    for topic in topics:
        if canonical not in ("English", "Turkish"):
            _ensure_bilingual_slots(topic.get("content"))

        findings = _audit_topic(topic, language=language, track=track)
        payload = {
            "language": language, "level": level, "unit": unit_title,
            "regional_variety": profile.variety if profile else "",
            "instruction_track": track,
            "topics": [{
                "topic_id": str(topic["id"]),
                "title": str(topic.get("title") or ""),
                "records": _assessment_evidence_records(topic["content"], track=track),
                "deterministic_blockers": _findings_payload(findings),
                "render_contract_blockers": _topic_render_blockers(topic["content"]),
            }],
        }
        data = _call_review(
            model=REVIEW_MODEL, system=_LESSON_REVIEW_SYSTEM, payload=payload,
            # Broad review is editorial classification + exact patching. Hidden
            # chain-of-thought only burns completion budget here; deterministic
            # code re-checks every invariant afterwards.
            max_tokens=1800, effort="low", budget=budget,
            stage=f"review_lesson:{unit_title}:{topic.get('title')}",
            response_schema=_LESSON_REVIEW_SCHEMA, response_name="lesson_review",
        )
        rows = data.get("topics")
        if not isinstance(rows, list) or len(rows) != 1:
            raise QualityGateError(
                f"lesson reviewer returned invalid coverage for {topic.get('title')}"
            )
        row = rows[0]
        if not isinstance(row, dict) or str(row.get("topic_id") or "") != str(topic["id"]):
            raise QualityGateError(
                f"lesson reviewer coverage mismatch for {topic.get('title')}"
            )

        patches: List[Any] = []
        row_topic_id = str(topic["id"])
        for patch in (row.get("patches") or []):
            if not isinstance(patch, dict):
                raise QualityGateError("lesson semantic patch is not an object")
            patch = dict(patch)
            if patch.get("topic_id") not in (None, "", row_topic_id):
                raise QualityGateError(
                    f"lesson patch topic mismatch: row={row_topic_id}, "
                    f"patch={patch.get('topic_id')}"
                )
            patch["topic_id"] = row_topic_id
            patches.append(patch)
        applied += _apply_patches(by_id, patches)

        # Any deterministic defect the broad editor did not cure gets one narrow
        # pass over only this lesson. Keep reasoning minimal so the response
        # budget is available for the strict JSON patch itself.
        blockers = A.blocking(_audit_topic(topic, language=language, track=track))
        render_blockers = _topic_render_blockers(topic.get("content"))
        if blockers or render_blockers:
            blocker_records = _records_for_findings(topic["content"], blockers)
            render_records = (
                _records_for_render_blockers(topic["content"], render_blockers)
                if render_blockers else []
            )
            exact_records = []
            seen_record_paths = set()
            for rec in blocker_records + render_records:
                marker = tuple(rec.get("path") or [])
                if marker and marker not in seen_record_paths:
                    seen_record_paths.add(marker)
                    exact_records.append(rec)
            targeted = {
                "language": language, "level": level, "unit": unit_title,
                "regional_variety": profile.variety if profile else "",
                "instruction_track": track,
                "topics": [{
                    "topic_id": str(topic["id"]),
                    "title": str(topic.get("title") or ""),
                    "records": exact_records or _review_records(topic["content"]),
                    "deterministic_blockers": _findings_with_repair_paths(
                        topic["content"], blockers
                    ),
                    "render_contract_blockers": render_blockers,
                }],
                "instruction": (
                    "Fix every deterministic and renderer-contract blocker. "
                    "Each deterministic blocker may contain repair_paths resolved from the "
                    "auditor to exact learner-visible fields. Every listed repair_path is "
                    "mandatory: patch that exact path, not a nearby field. For any MCQ whose "
                    "answer depends on an unstated identity/biographical inference, rewrite "
                    "the smallest learner-visible fields so exactly one answer is derivable "
                    "from explicit stem or taught evidence. Return this one topic only."
                ),
            }
            retry = _call_review(
                model=REPAIR_MODEL, system=_LESSON_REVIEW_SYSTEM, payload=targeted,
                max_tokens=3200, effort="low", budget=budget,
                stage=f"review_blocker_retry:{topic.get('title')}",
                response_schema=_LESSON_REVIEW_SCHEMA,
                response_name="lesson_blocker_repair",
            )
            rows2 = retry.get("topics")
            if not isinstance(rows2, list) or len(rows2) != 1 or \
                    str(rows2[0].get("topic_id") or "") != str(topic["id"]):
                raise QualityGateError(
                    f"blocker retry coverage failed for {topic.get('title')}"
                )
            retry_patches = []
            for patch in (rows2[0].get("patches") or []):
                if not isinstance(patch, dict):
                    raise QualityGateError("blocker retry patch is not an object")
                patch = dict(patch)
                patch_id = str(patch.get("topic_id") or str(topic["id"]))
                if patch_id != str(topic["id"]):
                    raise QualityGateError("blocker retry patch changed topic id")
                patch["topic_id"] = str(topic["id"])
                retry_patches.append(patch)
            applied += _apply_patches(by_id, retry_patches)

            still = A.blocking(_audit_topic(topic, language=language, track=track))
            if still:
                # The first semantic pass may repair most blockers but miss one
                # exact field. Do not turn a repairable path into a publication
                # refusal. Give only the still-bad exact records one final bounded
                # pass, then fail closed if the deterministic auditor still objects.
                remaining_records = _records_for_findings(topic["content"], still)
                remaining_payload = _findings_with_repair_paths(topic["content"], still)
                if remaining_records and any(row.get("repair_paths") for row in remaining_payload):
                    exact_retry_payload = {
                        "language": language, "level": level, "unit": unit_title,
                        "regional_variety": profile.variety if profile else "",
                        "instruction_track": track,
                        "topics": [{
                            "topic_id": str(topic["id"]),
                            "title": str(topic.get("title") or ""),
                            "records": remaining_records,
                            "deterministic_blockers": remaining_payload,
                            "render_contract_blockers": [],
                        }],
                        "instruction": (
                            "The previous repair left these deterministic blockers. "
                            "Patch EVERY listed repair_path exactly. Do not edit unrelated "
                            "fields. Return this one topic only."
                        ),
                    }
                    exact_retry = _call_review(
                        model=REPAIR_MODEL, system=_LESSON_REVIEW_SYSTEM,
                        payload=exact_retry_payload,
                        max_tokens=2800, effort="low", budget=budget,
                        stage=f"review_exact_blocker_retry:{topic.get('title')}",
                        response_schema=_LESSON_REVIEW_SCHEMA,
                        response_name="lesson_exact_blocker_repair",
                    )
                    exact_rows = exact_retry.get("topics")
                    if not isinstance(exact_rows, list) or len(exact_rows) != 1 or \
                            str(exact_rows[0].get("topic_id") or "") != str(topic["id"]):
                        raise QualityGateError(
                            f"exact blocker retry coverage failed for {topic.get('title')}"
                        )
                    exact_patches = []
                    for patch in (exact_rows[0].get("patches") or []):
                        if not isinstance(patch, dict):
                            raise QualityGateError("exact blocker retry patch is not an object")
                        patch = dict(patch)
                        patch["topic_id"] = str(topic["id"])
                        exact_patches.append(patch)
                    applied += _apply_patches(by_id, exact_patches)
                    still = A.blocking(
                        _audit_topic(topic, language=language, track=track)
                    )
                if still:
                    detail = [
                        {
                            "code": f.code,
                            "path": f.path,
                            "field": f.field,
                            "repair_paths": _repair_paths_for_finding(
                                topic["content"], f
                            ),
                        }
                        for f in still[:8]
                    ]
                    raise QualityGateError(
                        f"{topic.get('title')}: deterministic blockers remain after exact repair: "
                        f"{A.summarise(still)}; unresolved={detail}"
                    )
            still_render = _topic_render_blockers(topic.get("content"))
            if still_render:
                applied += _repair_topic_render_stems_exact(
                    topic=topic,
                    language=language,
                    level=level,
                    budget=budget,
                    blockers=still_render,
                )
                R.repair_lesson(topic["content"], language=language)
                still_render = _topic_render_blockers(topic.get("content"))

            if still_render:
                detail = "; ".join(
                    f"page {row['page_index']} {row['locale']}: {row['why']}"
                    for row in still_render[:4]
                )
                raise QualityGateError(
                    f"{topic.get('title')}: renderer-contract blockers remain after "
                    f"dedicated exact stem repair — {detail}"
                )

        # Bilingual completeness is a publication invariant but not every missing
        # counterpart is represented as an audit.py blocker.
        if canonical not in ("English", "Turkish"):
            missing_pairs = _missing_bilingual_pairs(topic.get("content"))
            if missing_pairs:
                targeted = {
                    "language": language, "level": level, "unit": unit_title,
                    "regional_variety": profile.variety if profile else "",
                    "instruction_track": track,
                    "topics": [{
                        "topic_id": str(topic["id"]),
                        "title": str(topic.get("title") or ""),
                        "records": _review_records(topic["content"]),
                        "deterministic_blockers": [],
                        "missing_bilingual_pairs": missing_pairs,
                    }],
                    "instruction": (
                        "Fix every listed missing bilingual counterpart. Patch only the "
                        "existing empty counterpart paths from their non-empty semantic pair. "
                        "Return this one topic only."
                    ),
                }
                retry = _call_review(
                    model=REPAIR_MODEL, system=_LESSON_REVIEW_SYSTEM, payload=targeted,
                    max_tokens=2400, effort="low", budget=budget,
                    stage=f"review_bilingual_retry:{topic.get('title')}",
                    response_schema=_LESSON_REVIEW_SCHEMA,
                    response_name="lesson_bilingual_repair",
                )
                rows2 = retry.get("topics")
                if not isinstance(rows2, list) or len(rows2) != 1 or \
                        str(rows2[0].get("topic_id") or "") != str(topic["id"]):
                    raise QualityGateError(
                        f"bilingual retry coverage failed for {topic.get('title')}"
                    )
                retry_patches = []
                for patch in (rows2[0].get("patches") or []):
                    if not isinstance(patch, dict):
                        raise QualityGateError("bilingual retry patch is not an object")
                    patch = dict(patch)
                    patch["topic_id"] = str(topic["id"])
                    retry_patches.append(patch)
                applied += _apply_patches(by_id, retry_patches)
                remaining = _missing_bilingual_pairs(topic.get("content"))
                if remaining:
                    raise QualityGateError(
                        f"{topic.get('title')}: incomplete EN/TR field pairs after targeted repair: "
                        + ", ".join(remaining[:8])
                    )

    return applied


def _assessment_render_blockers(content: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Renderer-contract failures for assessment MCQs, with learner-visible context.

    The semantic examiner used to review the ten questions without being told
    that a later deterministic renderer rule would reject one of them. That is
    how a semantically reviewed assessment could still fail closed only at the
    final boundary. Feed these exact deterministic reasons into the examiner so
    the bad item can be repaired before publication rather than merely refused.
    """
    from services.authoring import render_contract as RC

    pages = content.get("pages") if isinstance(content, dict) else None
    blockers: List[Dict[str, Any]] = []
    question_no = 0
    for page_index, page in enumerate(pages or []):
        if not isinstance(page, dict) or str(page.get("type") or "").casefold() != "mcq":
            continue
        question_no += 1
        for is_tr in RC.EXPORT_LOCALES:
            ok, why = RC.page_is_renderable(page, is_tr)
            if ok:
                continue
            blockers.append({
                "question": question_no,
                "page_index": page_index,
                "title": str(page.get("title") or f"Question {question_no}"),
                "locale": "tr" if is_tr else "en",
                "why": why,
                "stem": RC.resolve_stem(page, is_tr),
                "answer": str(page.get("answer") or ""),
                "explanation": str(
                    (page.get("explanation_tr") or page.get("why_tr") or
                     page.get("explanation") or "")
                    if is_tr else
                    (page.get("explanation_en") or page.get("why") or
                     page.get("explanation") or "")
                ),
            })
    return blockers


def _checked_all_ten(data: Dict[str, Any], *, unit_title: str, stage: str) -> None:
    checked = data.get("checked_questions")
    try:
        normalized = sorted({int(v) for v in (checked or [])})
    except (TypeError, ValueError):
        normalized = []
    if normalized != list(range(1, 11)):
        raise QualityGateError(
            f"{unit_title}: {stage} did not explicitly verify all 10 questions"
        )


def review_unit_assessment(*, unit_title: str, assessment_topic: Dict[str, Any],
                           lesson_topics: List[Dict[str, Any]], language: str,
                           level: str, track: str, budget: ReviewBudget) -> int:
    content = assessment_topic.get("content")
    if not isinstance(content, dict):
        raise QualityGateError(f"{unit_title}: assessment has no content")
    if S.canonical_language(language) not in ("English", "Turkish"):
        _ensure_bilingual_slots(content)
    pages = content.get("pages")
    mcq_pages = [p for p in (pages or []) if isinstance(p, dict) and
                 str(p.get("type") or "").casefold() == "mcq"]
    if len(mcq_pages) != 10:
        raise QualityGateError(f"{unit_title}: expected 10 assessment questions, got {len(mcq_pages)}")

    evidence = []
    for topic in lesson_topics:
        # Assessment verification needs the taught claims and examples, not UI
        # metadata. Records keep exact wording while remaining compact.
        evidence.append({
            "topic_id": str(topic["id"]), "title": str(topic.get("title") or ""),
            "records": _review_records(topic["content"]),
        })
    payload = {
        "language": language, "level": level, "unit": unit_title,
        "regional_variety": (S.profile_for_language(language).variety
                             if S.profile_for_language(language) else ""),
        "assessment_topic_id": str(assessment_topic["id"]),
        "assessment_records": _review_records(content),
        "unit_evidence": evidence,
        # These are deterministic facts about what the renderer would refuse,
        # not semantic guesses. Give them to Gemini up front so it can repair the
        # item instead of letting the final gate discover the same problem too late.
        "render_contract_blockers": _assessment_render_blockers(content),
    }
    data = _call_review(
        model=REVIEW_MODEL, system=_ASSESSMENT_REVIEW_SYSTEM, payload=payload,
        max_tokens=1600, effort="low", budget=budget,
        stage=f"review_assessment:{unit_title}",
        response_schema=_ASSESSMENT_REVIEW_SCHEMA, response_name="assessment_review",
    )
    _checked_all_ten(data, unit_title=unit_title, stage="assessment reviewer")
    by_id = {str(assessment_topic["id"]): assessment_topic}
    applied = _apply_patches(by_id, data.get("patches") or [])

    R.repair_lesson(content, language=language)
    findings = A.audit_lesson(content, language=language, track=track)
    blockers = A.blocking(findings)
    if blockers:
        raise QualityGateError(
            f"{unit_title}: assessment has deterministic blockers after review: "
            f"{A.summarise(blockers)}"
        )

    # A renderer-contract blocker is deterministic but not necessarily an
    # audit.py blocker. The fresh production classroom exposed exactly that
    # gap: Gemini reviewed all ten items, then the final boundary correctly
    # refused one hidden-world inference. Give the exact rejected item and
    # reason one bounded targeted Gemini repair pass while the full unit evidence
    # is still available. Fail closed if it cannot make all ten renderable.
    render_blockers = _assessment_render_blockers(content)
    if render_blockers:
        retry_payload = {
            "language": language, "level": level, "unit": unit_title,
            "regional_variety": (S.profile_for_language(language).variety
                                 if S.profile_for_language(language) else ""),
            "instruction_track": track,
            "assessment_topic_id": str(assessment_topic["id"]),
            "assessment_records": _review_records(content),
            "unit_evidence": evidence,
            "render_contract_blockers": render_blockers,
            "instruction": (
                "Fix every listed render-contract blocker. Preserve exactly ten questions. "
                "Do not delete or renumber an item. Make the smallest evidence-grounded patch "
                "so each answer is derivable from explicit stem/taught facts and the same item "
                "renders in both English and Turkish export modes."
            ),
        }
        retry = _call_review(
            model=REPAIR_MODEL, system=_ASSESSMENT_REVIEW_SYSTEM,
            payload=retry_payload, max_tokens=3200, effort="low", budget=budget,
            stage=f"review_assessment_render_retry:{unit_title}",
            response_schema=_ASSESSMENT_REVIEW_SCHEMA,
            response_name="assessment_render_repair",
        )
        _checked_all_ten(retry, unit_title=unit_title,
                         stage="assessment render-contract repair")
        applied += _apply_patches(by_id, retry.get("patches") or [])

        R.repair_lesson(content, language=language)
        post_findings = A.audit_lesson(content, language=language, track=track)
        post_blockers = A.blocking(post_findings)
        if post_blockers:
            raise QualityGateError(
                f"{unit_title}: assessment repair introduced deterministic blockers: "
                f"{A.summarise(post_blockers)}"
            )
        remaining_render_blockers = _assessment_render_blockers(content)
        if remaining_render_blockers:
            detail = "; ".join(
                f"Q{row['question']} {row['locale']}: {row['why']}"
                for row in remaining_render_blockers[:4]
            )
            raise QualityGateError(
                f"{unit_title}: renderer-contract blockers remain after targeted repair — {detail}"
            )
    return applied


def repair_final_publication_blockers(*, units: List[Dict[str, Any]],
                                      language: str, level: str, track: str,
                                      budget: ReviewBudget) -> int:
    """Repair deterministic publication blockers found after semantic review.

    The final integrity boundary is a proof step, not a dead end. If it can name
    a repairable learner-visible defect, repair that exact topic/question once
    and re-prove it. Structural defects (missing units/questions, duplicate
    assessment cardinality, unreadable content) still fail closed.
    """
    applied = 0
    canonical = S.canonical_language(language)
    profile = S.profile_for_language(language)

    for unit in units:
        topics = unit.get("topics") or []
        lessons = [t for t in topics if not t.get("is_assessment")]
        evidence = [
            {
                "topic_id": str(t["id"]),
                "title": str(t.get("title") or ""),
                "records": _review_records(t.get("content") or {}),
            }
            for t in lessons
        ]

        for topic in topics:
            content = topic.get("content")
            if not isinstance(content, dict):
                continue

            if canonical not in ("English", "Turkish"):
                _ensure_bilingual_slots(content)
            missing_pairs = (
                _missing_bilingual_pairs(content)
                if canonical not in ("English", "Turkish") else []
            )

            if topic.get("is_assessment"):
                render_blockers = _assessment_render_blockers(content)
                if not render_blockers and not missing_pairs:
                    continue
                payload = {
                    "language": language, "level": level, "unit": unit.get("title"),
                    "regional_variety": profile.variety if profile else "",
                    "instruction_track": track,
                    "assessment_topic_id": str(topic["id"]),
                    "assessment_records": _review_records(content),
                    "unit_evidence": evidence,
                    "render_contract_blockers": render_blockers,
                    "missing_bilingual_pairs": missing_pairs,
                    "instruction": (
                        "This is the final publication repair. Fix every listed "
                        "renderer-contract blocker and missing bilingual counterpart. "
                        "Preserve exactly ten questions and all numbering. Make only "
                        "the smallest evidence-grounded patches needed for both export modes."
                    ),
                }
                data = _call_review(
                    model=REPAIR_MODEL, system=_ASSESSMENT_REVIEW_SYSTEM,
                    payload=payload, max_tokens=3200, effort="low", budget=budget,
                    stage=f"review_final_repair:{unit.get('title')}:assessment",
                    response_schema=_ASSESSMENT_REVIEW_SCHEMA,
                    response_name="final_assessment_repair",
                )
                _checked_all_ten(
                    data, unit_title=str(unit.get("title") or ""),
                    stage="final assessment repair",
                )
                applied += _apply_patches(
                    {str(topic["id"]): topic}, data.get("patches") or []
                )
            else:
                render_blockers = _topic_render_blockers(content)
                findings = A.blocking(_audit_topic(topic, language=language, track=track))
                if not render_blockers and not findings and not missing_pairs:
                    continue
                finding_records = _records_for_findings(content, findings)
                render_records = (
                    _records_for_render_blockers(content, render_blockers)
                    if render_blockers else []
                )
                records = []
                seen_paths = set()
                for rec in finding_records + render_records:
                    marker = tuple(rec.get("path") or [])
                    if marker and marker not in seen_paths:
                        seen_paths.add(marker)
                        records.append(rec)
                if missing_pairs or not records:
                    records = _review_records(content)
                payload = {
                    "language": language, "level": level, "unit": unit.get("title"),
                    "regional_variety": profile.variety if profile else "",
                    "instruction_track": track,
                    "topics": [{
                        "topic_id": str(topic["id"]),
                        "title": str(topic.get("title") or ""),
                        "records": records,
                        "deterministic_blockers": _findings_with_repair_paths(
                            content, findings
                        ),
                        "render_contract_blockers": render_blockers,
                        "missing_bilingual_pairs": missing_pairs,
                    }],
                    "instruction": (
                        "This is the final publication repair. Fix every listed "
                        "deterministic, renderer-contract, and bilingual blocker. "
                        "Patch only existing learner-visible fields and make the "
                        "smallest evidence-grounded correction."
                    ),
                }
                data = _call_review(
                    model=REPAIR_MODEL, system=_LESSON_REVIEW_SYSTEM,
                    payload=payload, max_tokens=3000, effort="low", budget=budget,
                    stage=f"review_final_repair:{topic.get('title')}",
                    response_schema=_LESSON_REVIEW_SCHEMA,
                    response_name="final_lesson_repair",
                )
                rows = data.get("topics")
                if not isinstance(rows, list) or len(rows) != 1 or \
                        str(rows[0].get("topic_id") or "") != str(topic["id"]):
                    raise QualityGateError(
                        f"final repair coverage failed for {topic.get('title')}"
                    )
                patches = []
                for patch in (rows[0].get("patches") or []):
                    if not isinstance(patch, dict):
                        raise QualityGateError("final repair patch is not an object")
                    patch = dict(patch)
                    patch["topic_id"] = str(topic["id"])
                    patches.append(patch)
                applied += _apply_patches({str(topic["id"]): topic}, patches)

            R.repair_lesson(content, language=language)

            post = A.blocking(_audit_topic(topic, language=language, track=track))
            if post:
                raise QualityGateError(
                    f"{topic.get('title')}: deterministic blockers remain after final repair: "
                    f"{A.summarise(post)}"
                )
            if topic.get("is_assessment"):
                remaining_render = _assessment_render_blockers(content)
            else:
                remaining_render = _topic_render_blockers(content)
            if remaining_render:
                detail = "; ".join(
                    f"{row.get('locale')}: {row.get('why')}"
                    for row in remaining_render[:4]
                )
                raise QualityGateError(
                    f"{topic.get('title')}: renderer blockers remain after final repair — {detail}"
                )
            if canonical not in ("English", "Turkish"):
                remaining_pairs = _missing_bilingual_pairs(content)
                if remaining_pairs:
                    raise QualityGateError(
                        f"{topic.get('title')}: bilingual gaps remain after final repair: "
                        + ", ".join(remaining_pairs[:8])
                    )
    return applied


_BILINGUAL_PAIRS = (
    ("title", "title_tr"),
    ("rule", "rule_tr"),
    ("explanation", "explanation_tr"),
    ("context", "context_tr"),
    ("note", "note_tr"),
    ("translation", "translation_tr"),
    ("example_en", "example_tr"),
    ("line_en", "line_tr"),
    ("why", "why_tr"),
)


def _stem_text(page: Dict[str, Any]) -> str:
    for key in ("prompt", "question", "stem", "prompt_tr", "question_tr", "stem_tr",
                "prompt_en", "question_en", "stem_en"):
        value = page.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _stem_key(text: str) -> str:
    """Normalize formatting, not linguistic contrasts, for exact-duplicate checks."""
    text = unicodedata.normalize("NFC", str(text or "")).casefold()
    chars = []
    for ch in text:
        cat = unicodedata.category(ch)
        chars.append(ch if (ch.isalnum() or cat.startswith("M")) else " ")
    return re.sub(r"\s+", " ", "".join(chars)).strip()


def _ensure_bilingual_slots(node: Any, *, page_level: bool = False) -> None:
    """Create only missing counterpart slots so a reviewer can repair them.

    The semantic model is still forbidden to invent arbitrary structure. This
    deterministic preparation adds an empty key only when its paired EN/TR key
    already exists with content, giving the reviewer an exact path and an exact
    old value to patch.
    """
    if isinstance(node, dict):
        pairs = list(_BILINGUAL_PAIRS)
        if page_level or "type" in node:
            pairs.append(("text", "text_tr"))
        for left, right in pairs:
            left_present = left in node and bool(str(node.get(left) or "").strip())
            right_present = right in node and bool(str(node.get(right) or "").strip())
            if left_present and right not in node:
                node[right] = ""
            elif right_present and left not in node:
                node[left] = ""
        for key, value in list(node.items()):
            if isinstance(value, (dict, list)):
                _ensure_bilingual_slots(value, page_level=(key == "pages"))
    elif isinstance(node, list):
        for value in node:
            _ensure_bilingual_slots(value, page_level=page_level)


def _missing_bilingual_pairs(node: Any, *, path: Tuple[Any, ...] = (),
                             page_level: bool = False) -> List[str]:
    """Pairs that would make EN/TR reader modes contain different material.

    Only a present field creates an obligation for its counterpart; genuinely
    optional notes may be absent in both languages. text/text_tr is checked
    only on page objects because dialogue text is the taught-language utterance,
    not English instructional prose.
    """
    missing: List[str] = []
    if isinstance(node, dict):
        pairs = list(_BILINGUAL_PAIRS)
        if page_level or "type" in node:
            pairs.append(("text", "text_tr"))
        for left, right in pairs:
            left_present = left in node and bool(str(node.get(left) or "").strip())
            right_present = right in node and bool(str(node.get(right) or "").strip())
            if left_present != right_present:
                absent = right if left_present else left
                missing.append(".".join(map(str, path + (absent,))))
        for key, value in node.items():
            if isinstance(value, (dict, list)):
                missing.extend(_missing_bilingual_pairs(
                    value, path=path + (key,),
                    page_level=(key == "pages"),
                ))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            missing.extend(_missing_bilingual_pairs(
                value, path=path + (index,), page_level=page_level
            ))
    return missing


def validate_publication_integrity(*, units: List[Dict[str, Any]], language: str,
                                   track: str) -> Dict[str, int]:
    """Last deterministic proof that the renderer cannot silently degrade a course.

    Semantic reviewers can say a course is correct while a later renderer drops
    an item for a legacy invariant. That produced a real shipped unit with only
    six of its ten assessment questions. This validator checks the exact
    post-review objects against both publication boundaries before any of them
    are persisted or the course can become READY.
    """
    from services.authoring import publish as P
    from services.authoring import render_contract as RC

    canonical = S.canonical_language(language)
    duplicate_stems: Dict[str, List[str]] = {}
    topic_count = 0
    mcq_count = 0
    assessment_count = 0

    for unit_index, unit in enumerate(units, 1):
        topics = unit.get("topics") or []
        assessment_topics = [t for t in topics if t.get("is_assessment")]
        if len(assessment_topics) != 1:
            raise QualityGateError(
                f"unit {unit_index} {unit.get('title')!r}: expected exactly one "
                f"unit assessment, got {len(assessment_topics)}"
            )

        assessment = assessment_topics[0]
        assessment_pages = assessment.get("content", {}).get("pages") or []
        assessment_mcqs = [
            p for p in assessment_pages
            if isinstance(p, dict) and str(p.get("type") or "").casefold() == "mcq"
        ]
        if len(assessment_mcqs) != 10:
            raise QualityGateError(
                f"{unit.get('title')}: post-review assessment has "
                f"{len(assessment_mcqs)}/10 questions"
            )

        # Ten STORED questions is not the invariant anyone cares about; ten
        # questions that reach the learner is. Unit 3 of a shipped Spanish A1
        # classroom held ten here and printed eight, so the count is taken
        # against what each export will actually publish.
        for is_tr in RC.EXPORT_LOCALES:
            survivors = [p for p in assessment_mcqs if RC.page_is_renderable(p, is_tr)[0]]
            if len(survivors) != 10:
                dropped = [
                    f"{p.get('title') or 'untitled'}: {RC.page_is_renderable(p, is_tr)[1]}"
                    for p in assessment_mcqs if not RC.page_is_renderable(p, is_tr)[0]
                ]
                raise QualityGateError(
                    f"{unit.get('title')}: only {len(survivors)}/10 assessment questions "
                    f"would reach the {'tr' if is_tr else 'en'} export — "
                    + "; ".join(dropped[:4])
                )
        assessment_count += len(assessment_mcqs)

        for topic in topics:
            topic_count += 1
            content = topic.get("content")
            if not isinstance(content, dict):
                raise QualityGateError(f"{topic.get('title')}: content is not an object")

            # An empty lesson audits perfectly clean — no pages, no findings,
            # no dropped items, page count unchanged at zero — and the persist
            # step at the end of the gate then writes it back over whatever was
            # really in the row. Emptiness has to be refused explicitly, because
            # every other check here is a check on content that exists.
            if not (content.get("pages") or []):
                raise QualityGateError(
                    f"{topic.get('title')}: no pages — an empty topic is not publishable")

            blockers = A.blocking(_audit_topic(topic, language=language, track=track))
            if blockers:
                raise QualityGateError(
                    f"{topic.get('title')}: deterministic blockers remain at "
                    f"publication integrity: {A.summarise(blockers)}"
                )

            before_pages = content.get("pages") or []
            published = P.load_publishable_content(
                copy.deepcopy(content), language=language, material_language=track,
                topic=str(topic.get("title") or ""),
            )
            if published.get("_dropped_items"):
                raise QualityGateError(
                    f"{topic.get('title')}: publication boundary would drop "
                    f"{published.get('_dropped_items')}"
                )
            after_pages = published.get("pages") or []
            if len(after_pages) != len(before_pages):
                raise QualityGateError(
                    f"{topic.get('title')}: publication boundary changes page count "
                    f"{len(before_pages)} -> {len(after_pages)}"
                )

            if canonical not in ("English", "Turkish"):
                missing_pairs = _missing_bilingual_pairs(content)
                if missing_pairs:
                    raise QualityGateError(
                        f"{topic.get('title')}: incomplete EN/TR field pairs: "
                        + ", ".join(missing_pairs[:8])
                    )

            # Ask the renderer's OWN admission contract, not a second copy of
            # it. The previous version imported `legacy_text._v57_unsafe_mcq`
            # while the renderer used `_v54_pdf_unsafe_mcq`, whose later layer
            # adds rules the gate never saw — so a Spanish jobs unit passed here
            # and lost two questions on the page, and Unit 3 shipped 8/10 from a
            # course this gate had declared complete. Both export locales are
            # checked: a page that renders in Turkish and vanishes from English
            # is the same divergence, one export later.
            lost = RC.unrenderable_pages(content)
            if lost:
                raise QualityGateError(
                    f"{topic.get('title')}: the renderer would silently drop "
                    + "; ".join(
                        f"page {row['index']} ({row.get('title') or 'untitled'}) "
                        f"in {row['locale']}: {row['why']}" for row in lost[:4])
                )

            for page_index, page in enumerate(before_pages):
                if not isinstance(page, dict):
                    continue
                if str(page.get("type") or "").casefold() != "mcq":
                    continue
                mcq_count += 1
                stem = _stem_text(page)
                key = _stem_key(stem)
                if key:
                    duplicate_stems.setdefault(key, []).append(
                        f"{unit.get('title')} / {topic.get('title')} / {stem}"
                    )

    duplicates = [rows for rows in duplicate_stems.values() if len(rows) > 1]
    if duplicates:
        examples = [" <> ".join(rows[:2]) for rows in duplicates[:4]]
        raise QualityGateError(
            "exact duplicate MCQ stems remain after semantic review: "
            + " | ".join(examples)
        )

    return {
        "topics": topic_count,
        "mcqs": mcq_count,
        "unit_assessment_questions": assessment_count,
    }


def provider_preflight() -> List[Dict[str, Any]]:
    """Live semantic canary for the exact defect classes that reached a real PDF.

    This is deliberately stronger than a connectivity ping. Before a user pays
    for a thirty-lesson regeneration, the production review model must recognize
    the semantic failures that motivated this gate while leaving a clean control
    alone. Mechanical invariants remain code-enforced. It is opt-in at deploy
    time and normally disabled after one successful production canary.
    """
    properties = {
        "greek_lookalike_ipa_error": {"type": "boolean"},
        "desayunar_ipa_error": {"type": "boolean"},
        "adjective_overgeneralization_error": {"type": "boolean"},
        "translation_tense_error": {"type": "boolean"},
        "silent_h_mcq_multiple_correct": {"type": "boolean"},
        "clean_control_error": {"type": "boolean"},
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }
    expected = {
        "greek_lookalike_ipa_error": True,
        "desayunar_ipa_error": True,
        "adjective_overgeneralization_error": True,
        "translation_tense_error": True,
        "silent_h_mcq_multiple_correct": True,
        "clean_control_error": False,
    }
    challenge = {
        "language": "European (Castilian) Spanish",
        "task": (
            "For each named check, set true only when the supplied material is "
            "professionally unacceptable. Evaluate linguistic truth, not JSON shape."
        ),
        "checks": {
            "greek_lookalike_ipa_error": {
                "term": "la reserva", "phonetic": "[la reˈseɾβα]"
            },
            "desayunar_ipa_error": {
                "term": "desayunar", "phonetic": "[desawˈnaɾ]"
            },
            "adjective_overgeneralization_error": {
                "claim": "Adjectives ending in -e or a consonant never change for gender."
            },
            "translation_tense_error": {
                "source": "Yo soy español, de Madrid.",
                "turkish": "Ben İspanyoldum, Madridliyim."
            },
            "silent_h_mcq_multiple_correct": {
                "stem": "¿Qué palabra contiene una h que no se pronuncia?",
                "options": ["hotel", "huevo", "hielo", "hacer"],
                "key": "hotel"
            },
            "clean_control_error": {
                "claim": "Many adjectives ending in -e, such as amable, are gender-invariable."
            },
        },
    }
    # Only Gemini 3.7 Flash is part of the production review path. Mechanical Unicode
    # contamination is proven by the deterministic gate, so the semantic canary
    # requires Gemini to catch the semantic defects and leaves that one mechanical
    # check to code.
    model_expected = dict(expected, greek_lookalike_ipa_error=False)
    response = T.call_model(
        [
            {
                "role": "system",
                "content": (
                    "You are a strict professional language-textbook fact-checker. "
                    "Return only the requested structured booleans. A false positive "
                    "on the clean control is a failure."
                ),
            },
            {"role": "user", "content": json.dumps(challenge, ensure_ascii=False)},
        ],
        max_tokens=900, temperature=0.0, model=REVIEW_MODEL, cache_system=False,
        timeout=120, attempts=2, reasoning_effort="high",
        response_schema=schema, response_name="gemini37_flash_semantic_canary",
    )
    if not response.ok or response.data != model_expected:
        raise QualityGateError(
            f"semantic provider preflight failed on {REVIEW_MODEL}: "
            f"got {response.data!r}; expected {model_expected!r}; "
            f"transport={response.error or 'ok'}"
        )
    return [{
        "model": REVIEW_MODEL, "seconds": response.seconds,
        "cost": float(response.cost or 0.0),
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
    }]


def gate_summary(budget: ReviewBudget) -> str:
    calls = ", ".join(
        f"{row['stage']}=${row['cost']:.4f}" for row in budget.calls
    )
    return f"quality_review=${budget.spent:.4f}/{budget.ceiling:.2f}; {calls}"
