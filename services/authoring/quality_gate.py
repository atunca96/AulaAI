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
import difflib
import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from services.authoring import audit as A
from services.authoring import budget as B
from services.authoring import repair as R
from services.authoring import schema as S
from services.authoring import transport as T


REVIEW_MODEL = "google/gemini-3.7-flash"
REPAIR_MODEL = "google/gemini-3.7-flash"
ESCALATION_MODEL = B.MODEL
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
_RISK_REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "topic_id": {"type": "string"},
        "checked_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "scope_checked_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "categorical_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "scope_checks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "record_id": {"type": "string"},
                    "counterexample_tested": {"type": "boolean"},
                    "final_scope_safe": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": [
                    "record_id", "counterexample_tested",
                    "final_scope_safe", "reason"
                ],
            },
        },
        "patches": {"type": "array", "items": _NESTED_PATCH_SCHEMA},
    },
    "required": [
        "topic_id", "checked_ids", "scope_checked_ids", "categorical_ids",
        "scope_checks", "patches"
    ],
}

_RATIONALE_PATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "item_id": {"type": "string"},
        "field": {"type": "string"},
        "old": {"type": "string"},
        "value": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["item_id", "field", "old", "value", "reason"],
}
_MCq_RATIONALE_REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "checked_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "quality_checks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "item_id": {"type": "string"},
                    "grounded": {"type": "boolean"},
                    "rationale_specific": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": [
                    "item_id", "grounded", "rationale_specific", "reason"
                ],
            },
        },
        "patches": {"type": "array", "items": _RATIONALE_PATCH_SCHEMA},
    },
    "required": ["checked_ids", "quality_checks", "patches"],
}

_COMPLEX_NOTATION_REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "checked_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "patches": {"type": "array", "items": _TOP_LEVEL_PATCH_SCHEMA},
    },
    "required": ["checked_ids", "patches"],
}

_EXACT_CATEGORICAL_REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {"type": "string", "enum": ["ok", "fix"]},
        "value": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "value", "reason"],
}

_BATCH_CATEGORICAL_REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "claim_id": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["ok", "fix"]},
                    "value": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["claim_id", "verdict", "value", "reason"],
            },
        },
    },
    "required": ["results"],
}

_MISSING_TRANSCRIPTION_REPAIR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "row_id": {"type": "string"},
                    "phonetic": {"type": "string", "minLength": 1},
                },
                "required": ["row_id", "phonetic"],
            },
        },
    },
    "required": ["rows"],
}

_MISSING_TRANSCRIPTION_REPAIR_SYSTEM = """You fill ONLY missing IPA cells in one
learner-visible pronunciation table.

For every supplied row, transcribe the exact written term in the declared
language and regional variety. Return one IPA value per row_id. Do not respell,
translate, omit, merge or add rows. Preserve the table's existing bracket style
when one is visible.

Return JSON only:
{"rows":[{"row_id":"m0","phonetic":"[...IPA...]"}]}

Contract:
- Return every supplied row_id exactly once and no others.
- phonetic must be a complete IPA transcription of that exact term.
- Do not return explanations or alternatives.
"""

_DIGIT_NOTATION_VERIFY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {"type": "string", "enum": ["ok", "fix"]},
        "spoken_form": {"type": "string"},
        "value": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "spoken_form", "value", "reason"],
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

_RENDER_RESCUE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "repairs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "field": {"type": "string"},
                    "value": {"type": "string", "minLength": 1},
                },
                "required": ["field", "value"],
            },
            "minItems": 1,
        },
    },
    "required": ["repairs"],
}

_ASSESSMENT_REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "checked_questions": {
            "type": "array", "items": {"type": "integer"},
            "minItems": 10, "maxItems": 10,
        },
        "quality_checks": {
            "type": "array",
            "minItems": 10,
            "maxItems": 10,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "question": {"type": "integer"},
                    "single_answer": {"type": "boolean"},
                    "distractors_plausible": {"type": "boolean"},
                    "rationale_specific": {"type": "boolean"},
                    "cefr_fit": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": [
                    "question", "single_answer", "distractors_plausible",
                    "rationale_specific", "cefr_fit", "reason"
                ],
            },
        },
        "patches": {"type": "array", "items": _TOP_LEVEL_PATCH_SCHEMA},
    },
    "required": ["checked_questions", "quality_checks", "patches"],
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


# In-memory marker on an in-flight topic record (never persisted, never part of
# lesson content) saying that review_unit_lessons already carried this lesson
# through semantic review, deterministic re-audit and the render contract.
_LESSON_REVIEW_DONE_KEY = "_quality_lesson_review_complete"

# Same idea for the pedagogical-risk pass: a topic that has been risk-reviewed
# and proven again is finished work, and a later failure elsewhere must not
# re-spend its call. In-memory only, never persisted, never part of content.
_RISK_REVIEW_DONE_KEY = "_quality_risk_review_complete"


# Persistent semantic-review attestations. We never cache model OUTPUT. We only
# remember that an exact semantic INPUT state has already completed the relevant
# review stage and then passed the authoritative deterministic proof that follows
# it. Any byte change in content/evidence/prompt/schema/model changes the digest
# and forces a fresh review. Cache failure is always a MISS, never a bypass.
_REVIEW_ATTEST_LOCK = threading.Lock()
_REVIEW_ATTEST_DB = (
    "/data/aula_quality_review_attest.sqlite3"
    if os.getenv("RAILWAY_ENVIRONMENT") else
    os.path.join(os.getcwd(), "data", "aula_quality_review_attest.sqlite3")
)


def _review_attestation_key(*, kind: str, model: str, system: str,
                            payload: Dict[str, Any], response_schema: Dict[str, Any],
                            response_name: str, contract_extra: Any = None) -> str:
    blob = {
        "v": 1,
        "kind": kind,
        "model": model,
        "system": system,
        "payload": payload,
        "response_schema": response_schema,
        "response_name": response_name,
        "contract_extra": contract_extra,
    }
    raw = json.dumps(blob, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _review_attestation_has(key: str) -> bool:
    try:
        with _REVIEW_ATTEST_LOCK:
            os.makedirs(os.path.dirname(_REVIEW_ATTEST_DB), exist_ok=True)
            conn = sqlite3.connect(_REVIEW_ATTEST_DB, timeout=2.0)
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS review_attestations ("
                    "digest TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
                row = conn.execute(
                    "SELECT 1 FROM review_attestations WHERE digest = ?", (key,)
                ).fetchone()
                return row is not None
            finally:
                conn.close()
    except Exception as exc:
        print(f"[QUALITY-CACHE] MISS cache_unavailable={type(exc).__name__}", flush=True)
        return False


def _review_attestation_store(key: str, *, stage: str) -> None:
    try:
        with _REVIEW_ATTEST_LOCK:
            os.makedirs(os.path.dirname(_REVIEW_ATTEST_DB), exist_ok=True)
            conn = sqlite3.connect(_REVIEW_ATTEST_DB, timeout=2.0)
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS review_attestations ("
                    "digest TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
                conn.execute(
                    "INSERT OR IGNORE INTO review_attestations(digest) VALUES (?)", (key,)
                )
                # Bound growth without making cache correctness depend on cleanup.
                conn.execute(
                    "DELETE FROM review_attestations WHERE digest IN ("
                    "SELECT digest FROM review_attestations ORDER BY created_at DESC LIMIT -1 OFFSET 12000)"
                )
                conn.commit()
            finally:
                conn.close()
        print(f"[QUALITY-CACHE] STORE {stage} {key[:12]}", flush=True)
    except Exception as exc:
        print(f"[QUALITY-CACHE] STORE-SKIP {stage} error={type(exc).__name__}", flush=True)


def _review_response_get(key: str) -> Optional[Dict[str, Any]]:
    """Return a previously VALIDATED reviewer response for this exact input.

    Responses enter this table only after their patches were applied and the
    stage completed all authoritative proof steps. A cache hit therefore replays
    a previously accepted semantic decision, then the normal validators run
    again. Any prompt/model/schema/input change changes the key.
    """
    try:
        with _REVIEW_ATTEST_LOCK:
            os.makedirs(os.path.dirname(_REVIEW_ATTEST_DB), exist_ok=True)
            conn = sqlite3.connect(_REVIEW_ATTEST_DB, timeout=2.0)
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS review_response_cache ("
                    "digest TEXT PRIMARY KEY, response_json TEXT NOT NULL, "
                    "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
                row = conn.execute(
                    "SELECT response_json FROM review_response_cache WHERE digest = ?",
                    (key,),
                ).fetchone()
            finally:
                conn.close()
        if not row:
            return None
        value = json.loads(row[0])
        return value if isinstance(value, dict) else None
    except Exception as exc:
        print(f"[QUALITY-CACHE] REPLAY-MISS error={type(exc).__name__}", flush=True)
        return None


def _review_response_store(key: str, data: Dict[str, Any], *, stage: str) -> None:
    """Persist only a response whose complete stage has already passed."""
    if not isinstance(data, dict):
        return
    try:
        raw = json.dumps(data, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"))
        with _REVIEW_ATTEST_LOCK:
            os.makedirs(os.path.dirname(_REVIEW_ATTEST_DB), exist_ok=True)
            conn = sqlite3.connect(_REVIEW_ATTEST_DB, timeout=2.0)
            try:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS review_response_cache ("
                    "digest TEXT PRIMARY KEY, response_json TEXT NOT NULL, "
                    "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
                conn.execute(
                    "INSERT OR REPLACE INTO review_response_cache"
                    "(digest,response_json,created_at) VALUES "
                    "(?,?,CURRENT_TIMESTAMP)",
                    (key, raw),
                )
                conn.execute(
                    "DELETE FROM review_response_cache WHERE digest IN ("
                    "SELECT digest FROM review_response_cache "
                    "ORDER BY created_at DESC LIMIT -1 OFFSET 4000)"
                )
                conn.commit()
            finally:
                conn.close()
        print(f"[QUALITY-CACHE] REPLAY-STORE {stage} {key[:12]}", flush=True)
    except Exception as exc:
        print(f"[QUALITY-CACHE] REPLAY-STORE-SKIP {stage} "
              f"error={type(exc).__name__}", flush=True)


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


def _editorial_slash_candidate(a: Any, b: Any) -> Optional[str]:
    """Prefer the clean candidate when only one duplicate proposal contains an
    inline alphabetic slash-alternative token such as oldur/olum.

    The proposals may differ elsewhere; the exact same field has two complete
    replacements, and learner-visible prose should not preserve an unresolved
    editor-style lexical alternative when the competing proposal has none.
    Ordinary slashes in dates, paths, fractions or spaced alternatives are not
    treated as editorial markers.
    """
    if not isinstance(a, str) or not isinstance(b, str) or a == b:
        return None

    def has_editorial_slash(text: str) -> bool:
        return bool(re.search(r"(?<=\w)[^\W\d_]+/[^\W\d_]+(?=\W|$)", text, re.UNICODE))

    ah = has_editorial_slash(a)
    bh = has_editorial_slash(b)
    if ah == bh:
        return None
    return b if ah else a


def _embedded_meta_insertion_cleaner(a: Any, b: Any) -> Optional[str]:
    """Return the clean candidate when one value is the other plus one
    suspicious CamelCase-style insertion inside an existing word.

    Example production corruption:
    "İspanyStandardolum" vs "İspanyolum".
    We only reconcile when removing exactly one alphabetic insertion of at
    least four characters from the longer candidate reproduces the shorter
    candidate byte-for-byte, and the insertion begins with an uppercase letter
    inside a surrounding alphabetic token. This is narrow enough to avoid
    choosing between genuinely different rewrites.
    """
    if not isinstance(a, str) or not isinstance(b, str) or a == b:
        return None

    long_value, short_value = (a, b) if len(a) > len(b) else (b, a)
    delta = len(long_value) - len(short_value)
    if delta < 4 or delta > 32:
        return None

    for start in range(1, len(long_value) - delta):
        chunk = long_value[start:start + delta]
        if not chunk.isalpha() or not chunk[0].isupper():
            continue
        before = long_value[start - 1]
        after = long_value[start + delta]
        if not (before.isalpha() and after.isalpha()):
            continue
        if long_value[:start] + long_value[start + delta:] == short_value:
            return short_value
    return None


def _camel_hump_token_cleaner(a: Any, b: Any) -> Optional[str]:
    """Prefer the clean candidate when two otherwise identical sentences differ
    in exactly one token and only one version contains a suspicious mid-word
    CamelCase hump.

    Production example:
    "Ben İspanyStandardım, Madridliyim." vs
    "Ben İspanyolum, Madridliyim."

    This is intentionally narrow and language-agnostic: same token count, every
    other token byte-identical, exactly one differing token, and exactly one of
    those tokens contains an internal uppercase letter after an alphabetic
    character. Genuine semantic rewrites still remain conflicts.
    """
    if not isinstance(a, str) or not isinstance(b, str) or a == b:
        return None
    ta = a.split()
    tb = b.split()
    if len(ta) != len(tb) or not ta:
        return None

    diffs = [i for i, (x, y) in enumerate(zip(ta, tb)) if x != y]
    if len(diffs) != 1:
        return None
    i = diffs[0]

    def has_midword_hump(token: str) -> bool:
        core = token.strip(".,;:!?()[]{}<>\"'“”‘’«»")
        if len(core) < 3:
            return False
        for j in range(1, len(core)):
            if core[j].isupper() and core[j - 1].isalpha():
                return True
        return False

    ah = has_midword_hump(ta[i])
    bh = has_midword_hump(tb[i])
    if ah == bh:
        return None
    return b if ah else a


def _sentence_camel_corruption_cleaner(a: Any, b: Any) -> Optional[str]:
    """Prefer the candidate without an obvious provider-injected CamelCase
    fragment anywhere in the sentence.

    This is broader than the one-token reconciler because production can emit
    a corrupted token AND independently rewrite another token in the same
    candidate pair. We still require exactly one side to contain a suspicious
    internal uppercase-start fragment of at least four alphabetic characters;
    if both or neither do, this resolver abstains and fail-closed behavior
    remains.
    """
    if not isinstance(a, str) or not isinstance(b, str) or a == b:
        return None

    def suspicious(text: str) -> bool:
        for token in text.split():
            core = token.strip(".,;:!?()[]{}<>\"'“”‘’«»")
            for i in range(1, len(core) - 3):
                if not (core[i].isupper() and core[i - 1].isalpha()):
                    continue
                j = i + 1
                while j < len(core) and core[j].isalpha():
                    j += 1
                if j - i >= 4:
                    return True
        return False

    ah = suspicious(a)
    bh = suspicious(b)
    if ah == bh:
        return None
    return b if ah else a


def _normalize_list_item_patch(content: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    """Lift a safe scalar option-item edit to its patchable parent string list.

    Review schemas allow arbitrary path depth, so a model can point at
    ["pages","3","options","0"]. Structural safety intentionally forbids
    mutating list elements directly. When — and only when — the parent is one of
    the learner-visible string-list fields, the index exists, old exactly
    matches the current element, and value is a non-empty string, lift the edit
    to an atomic whole-list replacement. No index is guessed and no structure is
    invented.
    """
    if not isinstance(raw, dict):
        return raw
    path = raw.get("path")
    if not isinstance(path, list) or len(path) < 2:
        return raw
    try:
        coerced = _coerce_patch_path(content, path)
    except Exception:
        return raw
    if not coerced or not isinstance(coerced[-1], int):
        return raw
    parent_path = coerced[:-1]
    if not parent_path or str(parent_path[-1]) not in {"options", "choices", "distractors"}:
        return raw
    try:
        parent = _get_path(content, parent_path)
    except Exception:
        return raw
    index = coerced[-1]
    if (
        not isinstance(parent, list)
        or not all(isinstance(v, str) for v in parent)
        or index < 0 or index >= len(parent)
    ):
        return raw
    old = raw.get("old")
    value = raw.get("value")
    if old != parent[index] or not isinstance(value, str) or not value.strip():
        return raw

    replacement = list(parent)
    replacement[index] = value
    lifted = dict(raw)
    lifted["path"] = list(parent_path)
    lifted["old"] = list(parent)
    lifted["value"] = replacement
    print(
        f"[QUALITY-PATCH] LIFT list-item patch {coerced!r} -> {parent_path!r}",
        flush=True,
    )
    return lifted


def _apply_patches(topics_by_id: Dict[str, Dict[str, Any]], patches: Sequence[Any],
                   notation_conflicts: Optional[List[Dict[str, Any]]] = None) -> int:
    # Normalize safe list-item edits before duplicate reconciliation. The
    # canonical mutator still only ever sees patchable scalar/list fields.
    lifted_patches: List[Any] = []
    for raw in patches or []:
        if isinstance(raw, dict):
            topic_id = str(raw.get("topic_id") or "").strip()
            topic = topics_by_id.get(topic_id)
            content = topic.get("content") if isinstance(topic, dict) else None
            if isinstance(content, dict):
                raw = _normalize_list_item_patch(content, raw)
        lifted_patches.append(raw)
    patches = lifted_patches

    # Normalize duplicates before mutating content, so an ambiguous first
    # proposal cannot be written and then make the concrete duplicate stale.
    normalized: List[Any] = []
    index_by_marker: Dict[Tuple[str, str], int] = {}
    deferred_notation: Dict[Tuple[str, str], Dict[str, Any]] = {}
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
        if marker in deferred_notation:
            value = raw.get("value")
            if isinstance(value, str) and value.strip() and                     value not in deferred_notation[marker]["candidates"]:
                deferred_notation[marker]["candidates"].append(value)
            continue
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
            editorial = _editorial_slash_candidate(prev_value, new_value)
            if editorial is not None:
                if editorial == new_value:
                    normalized[prev_i] = raw
                continue
            cleaned = _embedded_meta_insertion_cleaner(prev_value, new_value)
            if cleaned is None:
                cleaned = _camel_hump_token_cleaner(prev_value, new_value)
            if cleaned is None:
                cleaned = _sentence_camel_corruption_cleaner(prev_value, new_value)
            if cleaned is not None:
                if cleaned == new_value:
                    normalized[prev_i] = raw
                # else previous already is the clean concrete candidate.
                continue

        # Pronunciation fields are judged linguistically later. Two different
        # reviewer proposals for the same exact notation path are not a reason
        # to abandon the classroom: neither proposal is authoritative yet.
        # Defer the untouched path and all candidates to the narrow pronunciation
        # arbiter. Other semantic-field conflicts remain fail-closed.
        if coerced and str(coerced[-1]) in _NOTATION_FIELDS and                 notation_conflicts is not None:
            current = _get_path(content, coerced)
            entry = {
                "topic_id": topic_id,
                "path": list(coerced),
                "current": current,
                "candidates": [
                    value for value in (prev_value, new_value)
                    if isinstance(value, str) and value.strip()
                ],
            }
            entry["candidates"] = list(dict.fromkeys(entry["candidates"]))
            deferred_notation[marker] = entry
            notation_conflicts.append(entry)
            normalized[prev_i] = None
            print(
                f"[QUALITY-PATCH] DEFER notation conflict at {topic_id} "
                f"{list(coerced)!r} -> pronunciation arbiter",
                flush=True,
            )
            continue

        normalized.append(raw)

    patches = [raw for raw in normalized if raw is not None]
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
        if topic_id not in topics_by_id:
            raise QualityGateError("semantic patch has an unknown topic")
        content = topics_by_id[topic_id]["content"]

        # A patch whose path does not resolve against the current content is a
        # malformed proposal, not a content defect: the reviewer emitted a
        # segment like "," or an out-of-range index. Reject exactly that patch
        # instead of aborting the whole lesson/unit review. Nothing is written,
        # no index is guessed and no invalid path is remapped to a nearby field,
        # so exact-patch safety is unchanged; the deterministic and
        # renderer-contract re-audit that immediately follows still sees the
        # untouched content and routes any real blocker into the targeted
        # exact-repair layer, which fails closed if it cannot fix it.
        if not isinstance(path, list) or not path:
            print(
                f"[QUALITY-PATCH] REJECT malformed patch path {path!r} at {topic_id}",
                flush=True,
            )
            continue
        try:
            path = _coerce_patch_path(content, path)
        except QualityGateError as path_error:
            print(
                f"[QUALITY-PATCH] REJECT unresolvable patch path at {topic_id}: "
                f"{path_error}",
                flush=True,
            )
            continue
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
                else:
                    resolved = _editorial_slash_candidate(previous, proposed)
                    if resolved is None:
                        resolved = _embedded_meta_insertion_cleaner(previous, proposed)
                    if resolved is None:
                        resolved = _camel_hump_token_cleaner(previous, proposed)
                    if resolved is None:
                        resolved = _sentence_camel_corruption_cleaner(previous, proposed)
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


def _repair_notation_patch_conflicts(*, topics_by_id: Dict[str, Dict[str, Any]],
                                      conflicts: Sequence[Dict[str, Any]],
                                      language: str, level: str,
                                      budget: ReviewBudget) -> int:
    """Resolve reviewer disagreement on one exact pronunciation field.

    Broad semantic review is advisory for notation. When it proposes two
    different transcriptions for one path, keep the canonical content untouched
    and ask the existing pronunciation arbiter to choose one linguistically.
    """
    profile = S.profile_for_language(language)
    applied = 0
    for conflict in conflicts or []:
        topic_id = str(conflict.get("topic_id") or "")
        topic = topics_by_id.get(topic_id)
        path = conflict.get("path")
        if not topic or not isinstance(path, list) or not path:
            continue
        content = topic.get("content")
        if not isinstance(content, dict):
            continue
        path = _coerce_patch_path(content, path)
        current = _get_path(content, path)

        parent = content
        for part in path[:-1]:
            parent = parent[part]
        term = ""
        if isinstance(parent, dict):
            term = str(
                parent.get("term") or parent.get("word") or
                parent.get("target") or parent.get("example") or ""
            ).strip()
        if not term:
            term = str(topic.get("title") or "pronunciation item")

        candidates = []
        for value in [current] + list(conflict.get("candidates") or []):
            if isinstance(value, str) and value.strip() and value.strip() not in candidates:
                candidates.append(value.strip())
        if len(candidates) < 2:
            continue

        data = _call_review(
            model=REPAIR_MODEL,
            system=_EXACT_PHONETIC_CONFLICT_REPAIR_SYSTEM,
            payload={
                "language": language,
                "level": level,
                "regional_variety": profile.variety if profile else "",
                "term": term,
                "candidates": candidates,
                "occurrences": [{
                    "topic": str(topic.get("title") or ""),
                    "field": str(path[-1]),
                    "current_value": str(current or ""),
                }],
            },
            max_tokens=500,
            effort="low",
            budget=budget,
            stage=f"review_notation_conflict:{topic.get('title')}:{'.'.join(map(str, path))}",
            response_schema=_EXACT_TARGET_REPAIR_SCHEMA,
            response_name="notation_patch_conflict_repair",
        )
        replacement = data.get("value")
        if not isinstance(replacement, str) or not replacement.strip():
            raise QualityGateError(
                f"{topic.get('title')}: notation conflict repair returned empty value "
                f"for {path!r}"
            )
        replacement = replacement.strip()
        if replacement != current:
            _set_path(content, path, replacement, old=current)
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

    # Some deterministic findings represent a bilingual PAIR rather than one
    # scalar field, e.g. "title/title_tr" or "explanation/explanation_tr".
    # Treat those as two exact repair targets. Previously the router searched
    # for a literal field named "title/title_tr", so an identical bilingual
    # leak could be detected correctly but could never reach exact repair.
    finding_fields = {
        part.strip()
        for part in str(finding.field or "").split("/")
        if part.strip()
    }

    candidates: List[List[Any]] = []
    for rec in records:
        path = rec.get("path")
        if not isinstance(path, list):
            continue
        if finding_fields and str(rec.get("field") or "") not in finding_fields:
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
    # every exact match is relevant. Pair findings deliberately return BOTH
    # counterpart paths: repairing only one side is exactly how a bilingual leak
    # should be resolved. A value-less scalar finding remains safe only when its
    # field/prefix identifies one unique record.
    if finding.value:
        return candidates
    if len(finding_fields) > 1:
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


def _assessment_evidence_digest(content: Dict[str, Any], *, track: str) -> List[str]:
    """Compact read-only lesson evidence for assessment verification.

    Assessment reviewers never patch lesson evidence, so JSON patch paths, role
    labels and track metadata are prompt overhead. Preserve the complete
    learner-visible semantic values, but serialize them as deduplicated
    field/value strings. This keeps semantic coverage while cutting provider
    input cost substantially.
    """
    out: List[str] = []
    seen = set()
    for rec in _assessment_evidence_records(content, track=track):
        field = str(rec.get("field") or "").strip()
        value = rec.get("value")
        if isinstance(value, list):
            value_text = " | ".join(str(v).strip() for v in value if str(v).strip())
        else:
            value_text = str(value or "").strip()
        if not field or not value_text:
            continue
        row = f"{field}: {value_text}"
        if row in seen:
            continue
        seen.add(row)
        out.append(row)
    return out


_LESSON_REVIEW_SYSTEM = """You are AulaAI's independent publication editor.
The course was authored by another model. Your job is to find and correct
learner-visible errors, not to praise or rewrite stylistically.

Supported taught languages are exactly: English, Spanish, German, French,
Italian, Portuguese, Russian, Chinese, Japanese, Arabic, Turkish, Dutch,
Swedish, Korean and Greek.

Language-awareness contract:
- Judge target-language content by the grammar, writing system, morphology,
  syntax, punctuation and standard usage of the DECLARED taught language, not
  by English or Turkish expectations.
- Legitimate language-specific features are not defects. This includes
  grammatical gender, noun/adjective/article agreement, case systems,
  declension, conjugation, relative-pronoun selection, word order, clitics,
  articles, honorific/register systems, productive morphology, diacritics,
  language-specific punctuation and native scripts/alphabets.
- Native writing systems are valid learner content when they belong to the
  taught language: Latin-script languages may use their required diacritics;
  Russian uses Cyrillic; Greek uses Greek script; Arabic uses Arabic script;
  Chinese uses Han characters; Japanese may use kanji/hiragana/katakana; Korean
  uses Hangul. Do not "repair" a native script merely because it differs from
  Latin.
- Distinguish a real grammatical dependency from an unsupported identity
  inference. If an MCQ answer depends on gender, case, agreement or another
  grammatical feature, the learner-visible stem must contain the grammatical
  evidence that licenses it (for example an explicit noun/article/antecedent or
  other taught form). Never infer a person's gender, nationality, profession or
  other identity fact from a personal name alone.
- When a language-specific rule is correct for the declared standard/regional
  variety, allow it to pass unchanged. Patch only when the form, explanation or
  question is actually wrong, ambiguous, ungrounded or inconsistent in that
  language.

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
- lesson MCQs for exactly one defensible answer and high-quality distractors.
  Distractors must be plausible learner errors from the SAME tested semantic or
  grammatical space, similar enough in form/function to require knowledge rather
  than elimination by obvious category mismatch, absurdity or malformed language;
- every stored answer-key rationale must justify the keyed answer from evidence
  visible in that question or from the grammatical/lexical fact directly tested
  there. The rationale must state the specific discriminating rule, form or
  learner-visible evidence that makes the keyed answer correct; generic statements
  such as "it matches the rule", "the material says so", "this is correct" or
  equivalent low-information paraphrases are not publication quality. Never
  introduce a person, situation, grammatical subject or fact that is absent from
  the item merely to make the explanation sound concrete;
- translations and instructional prose must be idiomatic in their own language,
  not literal fragments or awkward calques. Correct genuine naturalness defects,
  but do not perform cosmetic rewrites;
- topical scope against the supplied unit title and unit topic list. A review,
  recap or milestone lesson must review THIS unit's material only. Content from
  another unit or from a generic textbook sequence is a blocking defect. When
  unit_scope_evidence is supplied, use it as the source of truth and patch every
  wrong-scope learner-visible field back to that unit.

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


_RISK_REVIEW_SYSTEM = """You are AulaAI's pedagogical-rule verifier.
Another editor already reviewed these lessons. This pass exists only for factual
grammar/usage claims that can harm a learner if they are overgeneralized.

Supported taught languages are exactly: English, Spanish, German, French,
Italian, Portuguese, Russian, Chinese, Japanese, Arabic, Turkish, Dutch,
Swedish, Korean and Greek.

Language-awareness contract:
- Judge target-language content by the grammar, writing system, morphology,
  syntax, punctuation and standard usage of the DECLARED taught language, not
  by English or Turkish expectations.
- A rule or formula must name a word by its CITATION FORM - the infinitive,
  lemma or dictionary entry - never by one of its inflected forms. A published
  German lesson listed the Prateritum of 'werden' correctly and then summarised
  the rule as "conjugated 'wurden' + Partizip II", naming a plural form as the
  thing to be conjugated, while its own example two lines below used 'wurde'.
  A formula that contradicts the paradigm printed beside it teaches the learner
  to conjugate an already-conjugated form. Patch the formula to the citation
  form and leave the paradigm list and the examples untouched.
- Legitimate language-specific features are not defects. This includes
  grammatical gender, noun/adjective/article agreement, case systems,
  declension, conjugation, relative-pronoun selection, word order, clitics,
  articles, honorific/register systems, productive morphology, diacritics,
  language-specific punctuation and native scripts/alphabets.
- Native writing systems are valid learner content when they belong to the
  taught language: Latin-script languages may use their required diacritics;
  Russian uses Cyrillic; Greek uses Greek script; Arabic uses Arabic script;
  Chinese uses Han characters; Japanese may use kanji/hiragana/katakana; Korean
  uses Hangul. Do not "repair" a native script merely because it differs from
  Latin.
- Distinguish a real grammatical dependency from an unsupported identity
  inference. If an MCQ answer depends on gender, case, agreement or another
  grammatical feature, the learner-visible stem must contain the grammatical
  evidence that licenses it (for example an explicit noun/article/antecedent or
  other taught form). Never infer a person's gender, nationality, profession or
  other identity fact from a personal name alone.
- When a language-specific rule is correct for the declared standard/regional
  variety, allow it to pass unchanged. Patch only when the form, explanation or
  question is actually wrong, ambiguous, ungrounded or inconsistent in that
  language.

Check EVERY supplied rule/explanation/text record against the declared language
and regional variety. In particular, actively search for standard
counterexamples before accepting words such as always, never, only, every,
must, cannot, asla, yalnızca, sadece, daima, değişmez or zorunlu. A broad rule
that is true only for a subclass must be narrowed to that subclass.

Scope is a claim even when no absolute word appears. Read every statement for the
set it quantifies over: a claim about a whole grammatical category asserts something
about every member of it, so if it holds only for some forms, name that subset. Where
exceptions materially exist, the claim must carry a qualifier (usually, often, most,
in general) rather than reading as categorical. A sentence of the form "X does not
depend on Y" is universal; if some members of X do depend on Y, it is wrong as
written even though it contains no absolute word.

The payload also names absolute_ids: records containing categorical language.
For EVERY absolute_id, actively try to falsify the claim with a standard
counterexample before accepting it. Scope consistency inside one lesson is
mandatory: if a nearby claim about the same form/category says "many", "most",
"usually", "often" or otherwise names exceptions/subclasses, a second statement
must not silently broaden that same category to ALL members. Narrow the broader
statement unless the broader claim is genuinely universal. This applies language-agnostically to morphology, spelling, pronunciation,
phonology, connected-speech claims, syntax and usage. For pronunciation claims,
distinguish pedagogical tendencies from exceptionless phonological rules: dialect,
speech rate, prosodic position, emphasis and careful-vs-casual speech can matter.
Do not allow "always/never/every" wording unless the declared standard variety
really licenses an exceptionless statement.

Preserve CEFR level and meaning. If one correction has paired English/Turkish fields,
patch both so they remain semantically equivalent.

Return JSON only:
{"topic_id":"EXACT ID",
 "checked_ids":["r0"],
 "scope_checked_ids":["r0"],
 "categorical_ids":["r0"],
 "scope_checks":[
   {"record_id":"r0","counterexample_tested":true,
    "final_scope_safe":true,"reason":"brief factual scope judgement"}
 ],
 "patches":[
   {"path":["pages","0","rules","0","rule_tr"],"old":"EXACT OLD VALUE",
    "value":"CORRECT REPLACEMENT","reason":"brief factual reason"}
 ]}

Contract:
- The request contains exactly one topic. Copy its topic_id exactly.
- checked_ids MUST contain every supplied record_id exactly once. This is a
  coverage proof, not a list of only suspicious records. Copy IDs exactly; do
  not reconstruct or normalize paths.
- categorical_ids MUST contain EVERY supplied record_id whose statement is
  categorical/universal in meaning, even when it contains no obvious absolute
  keyword. Never invent an ID. The supplied absolute_ids are only a server-side
  FLOOR: every absolute_id MUST also appear in categorical_ids.
- scope_checked_ids MUST contain every categorical_id. Never invent an ID.
- scope_checks MUST contain every categorical_id exactly once and no other IDs.
  counterexample_tested must be true only after actively trying to find a
  standard counterexample or exception class. final_scope_safe judges the FINAL
  value after applying your own patches. If the current wording is too broad,
  patch it first and then mark final_scope_safe=true. Never mark an unsafe
  unchanged absolute claim as safe merely because it is pedagogically convenient.
- Use only paths present in the supplied records.
- Copy old exactly, byte for byte.
- Patch only correctness/scope errors, never style.
"""

_EXACT_PHONETIC_CONFLICT_REPAIR_SYSTEM = """You are AulaAI's pronunciation
arbiter for exactly ONE written headword. The same headword was published with
multiple IPA transcriptions in one classroom.

Return the single correct IPA transcription for the declared language and
regional variety. Judge linguistic correctness; do not choose by majority.
Preserve the classroom's bracket style when the candidates are bracketed.
Do not return respelling, commentary, alternatives or multiple pronunciations.
Return JSON only: {"value":"IPA","reason":"brief factual reason"}.
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
- The keyed answer must follow from learner-visible evidence in the rewritten
  stem and from the grammatical/lexical fact the item is actually testing.
- If the answer depends on a grammatical feature such as gender, case,
  agreement, number, person, tense, aspect, register, script or word form, make
  the relevant grammatical evidence explicit in the stem itself using natural
  content for the declared taught language.
- Do not require identity or world-knowledge inference from a personal name,
  birthplace, residence, job, biography, culture or stereotype.
- Preserve valid language-specific grammar and writing-system behavior. Do not
  flatten a language-specific distinction merely to satisfy the renderer.
- Do not reveal the keyed answer verbatim unless the original task already does.
- Keep the CEFR level and pedagogical intent.
- Return JSON only: {"value":"NON-EMPTY REPLACEMENT","reason":"brief reason"}.
"""

_EXACT_DUPLICATE_STEM_REPAIR_SYSTEM = """You repair exactly ONE learner-visible
MCQ stem because AulaAI's deterministic publication proof found the same
normalized stem elsewhere in the classroom.

Hard contract:
- Return ONLY one replacement string for the existing stem field.
- Write the stem in the taught language.
- Preserve the keyed answer, options and distractors exactly.
- Keep the same CEFR level and the same skill/fact being tested, but phrase the
  question so it is genuinely distinct from every forbidden duplicate stem.
- The replacement must still have exactly one defensible answer using only the
  visible item context and taught material. Do not introduce outside knowledge.
- Do not change structure, numbering, answer key or choices.
- Do not use cosmetic blank-length changes, punctuation-only changes, or
  underscore-count changes to fake uniqueness.
- Return JSON only: {"value":"NON-EMPTY REPLACEMENT","reason":"brief reason"}.
"""

_ASSESSMENT_REVIEW_SYSTEM = """You are AulaAI's independent assessment examiner.
The lesson material and a ten-question unit assessment were authored by another
model. Verify ALL ten questions against the unit evidence.

Supported taught languages are exactly: English, Spanish, German, French,
Italian, Portuguese, Russian, Chinese, Japanese, Arabic, Turkish, Dutch,
Swedish, Korean and Greek.

Language-awareness contract:
- Judge target-language content by the grammar, writing system, morphology,
  syntax, punctuation and standard usage of the DECLARED taught language, not
  by English or Turkish expectations.
- Legitimate language-specific features are not defects. This includes
  grammatical gender, noun/adjective/article agreement, case systems,
  declension, conjugation, relative-pronoun selection, word order, clitics,
  articles, honorific/register systems, productive morphology, diacritics,
  language-specific punctuation and native scripts/alphabets.
- Native writing systems are valid learner content when they belong to the
  taught language: Latin-script languages may use their required diacritics;
  Russian uses Cyrillic; Greek uses Greek script; Arabic uses Arabic script;
  Chinese uses Han characters; Japanese may use kanji/hiragana/katakana; Korean
  uses Hangul. Do not "repair" a native script merely because it differs from
  Latin.
- Distinguish a real grammatical dependency from an unsupported identity
  inference. If an MCQ answer depends on gender, case, agreement or another
  grammatical feature, the learner-visible stem must contain the grammatical
  evidence that licenses it (for example an explicit noun/article/antecedent or
  other taught form). Never infer a person's gender, nationality, profession or
  other identity fact from a personal name alone.
- When a language-specific rule is correct for the declared standard/regional
  variety, allow it to pass unchanged. Patch only when the form, explanation or
  question is actually wrong, ambiguous, ungrounded or inconsistent in that
  language.

For every question check:
- there is exactly ONE correct option in context, not merely one keyed option;
- the keyed answer is actually correct;
- no distractor is also correct, synonymous in context, or made correct by the
  wording (the classic failure is asking which h is silent when every option's
  h is silent);
- the stem is grammatical, natural, unambiguous and CEFR-appropriate;
- distractors are plausible learner errors from the SAME tested semantic or
  grammatical space, not nonsense giveaways, unrelated categories, obviously
  malformed forms or choices removable without knowing the taught distinction;
- the item tests taught material and does not require outside knowledge;
- if the payload contains render_contract_blockers, EVERY listed blocker is mandatory:
  repair that question so its answer follows only from facts explicitly stated in the stem
  or taught evidence and so the same stored item remains renderable in both export locales.
  Never solve a blocker by deleting, renumbering or weakening the ten-question assessment;
- compare each assessment item with ALL lesson MCQs/evidence in the unit. A repeated
  or paraphrased question may never contradict the answer taught earlier. If the
  same fact was asked earlier, preserve the taught fact and repair the assessment;
- check the answer explanation too: it must state the specific discriminating
  evidence/rule/form that makes the keyed answer correct. Generic rationales such
  as "it matches the rule", "the material says so", "this is the correct answer"
  or equivalent low-information restatements are a quality defect and must be
  repaired. An answer key that contradicts the lesson is a blocking factual defect
  even when the options are structurally valid.

Return JSON only:
{"checked_questions":[1,2,3,4,5,6,7,8,9,10],
 "quality_checks":[
   {"question":1,"single_answer":true,"distractors_plausible":true,
    "rationale_specific":true,"cefr_fit":true,
    "reason":"brief final-state judgement"}
 ],
 "patches":[
   {"topic_id":"ASSESSMENT TOPIC ID","path":["pages",1,"options"],
    "old":["..."],"value":["..."],"reason":"brief reason"}
 ]}

quality_checks MUST contain question numbers 1..10 exactly once. Judge the
FINAL state after applying your own patches, not merely the original input.
Every boolean must be true in that final state. If any criterion is false in the
input, repair that exact question and only then mark the corresponding final
criterion true. Do not claim a distractor set is plausible when a learner can
eliminate choices by unrelated category, malformed language or absurdity; do
not claim a rationale is specific when it merely restates correctness.

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
    token_plan = [
        int(max_tokens),
        int(max_tokens) + 800,
        int(max_tokens) + 1600,
    ]
    original_user = user
    original_stage = stage
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
        response = None
        for admission_attempt in range(3):
            response = T.call_model(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=max_tokens, temperature=0.0, model=model, cache_system=True,
                timeout=180, attempts=2, reasoning_effort=effort,
                response_schema=response_schema, response_name=response_name,
            )
            error_text = str(getattr(response, "error", "") or "")
            zero_cost_failure = (
                not response.ok
                and float(getattr(response, "cost", 0.0) or 0.0) == 0.0
            )
            transient_429 = (
                zero_cost_failure
                and "429" in error_text
                and (
                    "openrouter_admission_control" in error_text
                    or "could not verify available credits" in error_text.casefold()
                )
            )
            transient_structured_json = (
                zero_cost_failure
                and "unparseable json body" in error_text.casefold()
                and "finish_reason=error" in error_text.casefold()
            )
            if not (transient_429 or transient_structured_json) or admission_attempt == 2:
                break
            if transient_429:
                delay = 2.0 * (admission_attempt + 1)
                print(
                    f"[QUALITY-CALL] RETRY {stage} transient OpenRouter admission 429; "
                    f"sleeping {delay:.0f}s",
                    flush=True,
                )
                time.sleep(delay)
            else:
                # Provider returned a partial structured body but charged $0 and
                # explicitly marked finish_reason=error. This is transport/provider
                # failure, not a semantic/schema judgement. Re-issue the exact strict
                # request once/twice; do not relax the schema or mutate the payload.
                print(
                    f"[QUALITY-CALL] RETRY {stage} transient zero-cost structured "
                    f"JSON transport failure ({admission_attempt + 1}/2)",
                    flush=True,
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
    if bool(getattr(response, "truncated", False)):
        last_error = response.error or "structured output truncated"
        for retry_no, retry_tokens in enumerate(token_plan[1:], start=1):
            retry_stage = f"{original_stage}:truncation_retry_{retry_no}"
            retry_user = original_user + (
                "\\n\\nSTRUCTURED OUTPUT RETRY: the previous response was truncated "
                "before the JSON object closed. Return the smallest valid JSON that "
                "exactly matches the response schema. Include every required field "
                "and required coverage, keep reason text brief, and emit no commentary."
            )
            retry_reservation = budget.reserve(
                model=model, input_chars=len(system) + len(retry_user),
                output_tokens=retry_tokens, stage=retry_stage,
            )
            print(
                f"[QUALITY-CALL] RETRY {original_stage} structured output truncated; "
                f"max_tokens={retry_tokens}", flush=True,
            )
            try:
                retry_response = T.call_model(
                    [{"role": "system", "content": system},
                     {"role": "user", "content": retry_user}],
                    max_tokens=retry_tokens, temperature=0.0, model=model,
                    cache_system=True, timeout=180, attempts=2,
                    reasoning_effort=effort, response_schema=response_schema,
                    response_name=response_name,
                )
            except Exception:
                budget.release(retry_reservation)
                raise
            budget.record(
                retry_response, model=model, stage=retry_stage,
                reservation=retry_reservation,
            )
            print(
                f"[QUALITY-CALL] END {retry_stage} ok={retry_response.ok} "
                f"truncated={bool(getattr(retry_response, 'truncated', False))} "
                f"seconds={retry_response.seconds:.2f} "
                f"cost=${float(retry_response.cost or 0.0):.4f} "
                f"error={retry_response.error or '-'}", flush=True,
            )
            if bool(getattr(retry_response, "truncated", False)):
                last_error = retry_response.error or "structured output truncated"
                continue
            if not retry_response.ok or not isinstance(retry_response.data, dict):
                raise QualityGateError(
                    f"{original_stage} failed on {model}: "
                    f"{retry_response.error or 'invalid JSON'}"
                )
            return retry_response.data
        raise QualityGateError(
            f"{original_stage} failed on {model}: structured JSON remained "
            f"truncated after {len(token_plan)} bounded attempts; last={last_error}"
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



# ── MCQ explanation grounding ────────────────────────────────────────────────
# The answer key prints each stored rationale verbatim, so a rationale that
# invents evidence teaches that evidence. Production shipped "Sara bir kadın
# olduğu için…" under a stem that says only "Una mujer…", and "Lucía" under a
# stem that names nobody at all.
#
# The deterministic half of that is small and needs no language knowledge: a
# proper noun is spelled the same in every locale's rationale, while ordinary
# words are not. A capitalised token that both rationales share, and that the
# learner never sees in the stem, the options or the taught fields, is a person
# the question does not show. The other half — a rationale that names someone
# the stem DOES show and then claims their gender — is already
# `render_contract`'s name/gender relation, and is left there rather than
# re-implemented here.
_EXPLANATION_GROUNDING_REASON = (
    "explanation introduces a person the question does not show"
)


_EXPLANATION_GROUNDING_REPAIR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "explanation_en": {"type": "string", "minLength": 1},
        "explanation_tr": {"type": "string", "minLength": 1},
        "reason": {"type": "string"},
    },
    "required": ["explanation_en", "explanation_tr", "reason"],
}

_EXPLANATION_GROUNDING_REPAIR_SYSTEM = """You repair exactly ONE MCQ answer-key
rationale pair. The question itself is already valid and MUST NOT change.

Hard contract:
- Keep the stem, keyed answer, options and distractors unchanged.
- Rewrite only explanation_en and explanation_tr.
- Both explanations must justify the keyed answer using only evidence visible
  in the supplied stem/options or the grammatical fact directly tested there.
- Each explanation must QUOTE at least one form it relies on from the stem,
  options or distractors, exactly as that form is spelled there, and must do so
  in addition to naming the keyed answer. A rationale that only restates the
  answer and says it matches the question cites nothing and is rejected.
- Do not introduce a person, place, biography or fact the question does not
  show. If a personal name is absent from the question, do not mention one.
- Do not infer gender, nationality, profession or identity from a personal name.
- The English and Turkish explanations must express the same rationale.
- Keep the explanation concise and CEFR-appropriate.
- Return JSON only:
  {"explanation_en":"...","explanation_tr":"...","reason":"brief reason"}.
"""

_GROUNDED_EVIDENCE_KEYS = (
    "answer", "options", "choices", "distractors", "term", "word", "target",
    "translation", "translation_tr", "translation_en", "title", "title_tr",
)


def _visible_evidence_tokens(page: Dict[str, Any]) -> set:
    """Every token a learner can actually read on this item."""
    from services.authoring import render_contract as RC

    out: set = set()
    for key in RC._V57_STEM_KEYS:
        out |= set(RC._WORD_TOKEN.findall(RC._fold(page.get(key))))
    for key in _GROUNDED_EVIDENCE_KEYS:
        value = page.get(key)
        if isinstance(value, dict):
            value = list(value.values())
        if not isinstance(value, (list, tuple)):
            value = [value]
        for item in value:
            out |= set(RC._WORD_TOKEN.findall(RC._fold(item)))
    return out


def _ungrounded_explanation_names(page: Any) -> List[str]:
    """Proper nouns a rationale introduces that the question never shows.

    Cross-locale agreement is the lexicon-free test for "this is a name": the
    same string appears in both rationales. "The"/"Soruda" do not survive it;
    "Sara"/"Sara" do. An item carrying only one rationale cannot be judged this
    way and is left alone.
    """
    from services.authoring import render_contract as RC

    if not isinstance(page, dict) or not RC.mcq_like(page):
        return []

    per_locale = []
    roman_label = re.compile(
        r"\b([^\W\d_]+)\s+(?:I|II|III|IV|V|VI|VII|VIII|IX|X)\b",
        re.UNICODE,
    )

    # A technical/grammar label may be shared verbatim across localized
    # rationales. Parenthetical labels are especially common in language
    # teaching: "final devoicing (Auslautverhärtung)" in English and the same
    # German term in Turkish. Cross-locale capitalization alone must not turn
    # such a label into an invented person. Build this exemption from the
    # rationale text itself rather than from a language-specific allowlist.
    technical_labels: set = set()
    for key in tuple(dict.fromkeys(_NAME_GENDER_EN_KEYS + _NAME_GENDER_TR_KEYS)):
        value = page.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        for parenthetical in re.findall(r"\(([^()]{1,80})\)", value):
            for raw in RC._WORD_TOKEN.findall(parenthetical):
                if len(raw) >= 3 and raw[:1].isupper() and not raw.isupper():
                    technical_labels.add(RC._fold(raw))
        technical_labels.update(
            RC._fold(match.group(1))
            for match in roman_label.finditer(value)
            if match.group(1)
        )

    for keys in (_NAME_GENDER_EN_KEYS, _NAME_GENDER_TR_KEYS):
        found: set = set()
        present = False
        for key in keys:
            text = page.get(key)
            if not isinstance(text, str) or not text.strip():
                continue
            present = True
            quoted = RC._quoted_common_tokens(text)
            # Grammar labels such as "Konjunktiv II" are deliberately shared
            # across locale rationales and capitalized, but they are not people.
            # Treat only the label token as grammatical evidence; this remains
            # lexicon-free and does not weaken ordinary personal-name detection.
            grammar_labels = {
                RC._fold(match.group(1))
                for match in roman_label.finditer(text)
                if match.group(1)
            }
            for raw in RC._WORD_TOKEN.findall(text):
                if len(raw) < 3 or not raw[:1].isupper() or raw.isupper():
                    continue
                folded = RC._fold(raw)
                if (
                    folded
                    and folded not in quoted
                    and folded not in grammar_labels
                    and folded not in technical_labels
                ):
                    found.add(folded)
        if present:
            per_locale.append(found)
    if len(per_locale) < 2:
        return []

    visible = _visible_evidence_tokens(page)
    candidates = set.intersection(*per_locale) - visible

    # Cross-locale capitalization is only a candidate generator, not sufficient
    # evidence that a token names a person. German pedagogical labels such as
    # Präteritum, Plusquamperfekt and Perfekt are routinely preserved verbatim
    # in both English and Turkish explanations. Treat a candidate as a
    # deterministic invented-person blocker only when the sentence containing
    # it also carries a high-confidence human/identity cue. Lower-confidence
    # scenario invention is still covered by the independent semantic rationale
    # reviewer, so this narrows a noisy duplicate detector without removing a
    # quality check.
    grounded_people: set = set()
    for key in tuple(dict.fromkeys(_NAME_GENDER_EN_KEYS + _NAME_GENDER_TR_KEYS)):
        value = page.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        for statement in RC._STATEMENT_SPLIT.split(value):
            folded_statement = RC._fold(statement)
            tokens = set(RC._WORD_TOKEN.findall(folded_statement))
            hits = candidates & tokens
            if not hits:
                continue
            human_cue = (
                bool(RC._V57_GENDER_WORDS.search(folded_statement))
                or any(noun in folded_statement for noun in RC._V57_GENDER_NOUNS)
                or bool(RC._V57_NAME_WORDS.search(folded_statement))
                or bool(RC._V57_IDENTITY.search(folded_statement))
                or RC._has_biography_marker(folded_statement, RC._V57_BIOGRAPHY)
            )
            if human_cue:
                grounded_people.update(hits)

    return sorted(grounded_people)


def _rationale_has_specific_evidence(page: Any) -> bool:
    """Bind rationale specificity to the final stored artifact.

    Strip an exact occurrence of the keyed answer from each rationale before
    testing overlap with learner-visible evidence. This rejects answer-plus-
    boilerplate templates while still allowing a real grammar explanation to
    discuss forms INSIDE a multiword/sentence answer (for example repeated
    particles or verbs) after quoting that answer once.
    """
    from services.authoring import render_contract as RC

    if not isinstance(page, dict) or not RC.mcq_like(page):
        return True

    answer = str(page.get("answer") or "").strip()
    folded_answer = RC._fold(answer)
    rationale_tokens: set = set()
    present = False
    for key in tuple(dict.fromkeys(_NAME_GENDER_EN_KEYS + _NAME_GENDER_TR_KEYS)):
        value = page.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        present = True
        folded = RC._fold(value)
        if folded_answer:
            # Remove only the verbatim keyed-answer occurrence. If the
            # explanation separately cites one of its internal forms as
            # evidence, that second occurrence remains and can prove specificity.
            folded = folded.replace(folded_answer, " ", 1)
        rationale_tokens |= set(RC._WORD_TOKEN.findall(folded))
    if not present:
        return True

    visible = _visible_evidence_tokens(page)
    return bool(rationale_tokens & visible)


_EXPLANATION_SPECIFICITY_REASON = (
    "answer rationale does not cite item-specific learner-visible evidence"
)


# ── Proof over proxy ─────────────────────────────────────────────────────────
#
# `_ungrounded_explanation_names` and `_rationale_has_specific_evidence` are
# DETERMINISTIC PROXIES for two semantic questions: does this rationale invent a
# person, and does it cite the item. Neither question is decidable from token
# shape, and both proxies are measurably wrong across the taught languages:
# capitalisation carries no name signal in Chinese, Japanese, Korean or Arabic
# and over-fires in German where every noun is capitalised, so the same guard is
# simultaneously dead in four languages and hyperactive in a fifth.
#
# Used as a hard publication gate, a proxy of that shape cannot converge. Each
# false positive is patched, the boundary moves, and a new class of ordinary
# prose starts failing: grammar labels, parenthetical teaching labels, technical
# labels, each its own emergency commit. The list does not terminate, because
# "capitalised but not a person" is unbounded in fifteen languages.
#
# So the proxy keeps its full detection power and loses only its FINALITY. When
# the language-aware reviewer has already judged these exact bytes and issued a
# grounding/specificity proof for them, that judgement stands and the proxy is
# recorded rather than enforced. The attestation is the exact semantic surface
# the proxies read, so any later edit to the stem, options, answer or either
# rationale invalidates it and the proxy binds again with full force.
#
# Nothing is weakened for unreviewed content: with no proof, the blocker is
# raised exactly as before and publication still fails closed.

_RATIONALE_PROOF_KIND = "rationale_page_semantic_proof"


def _rationale_semantic_digest(page: Any) -> str:
    """The exact surface the rationale proxies read, as one stable key.

    Defined in `render_contract` and only re-exported here. The renderer resolves
    proofs without importing this module, so two implementations of the digest
    would be two answers to the same question — the drift this whole layer was
    built to remove.
    """
    from services.authoring import render_contract as RC

    return RC.rationale_semantic_digest(page)


def _rationale_proof_covers(page: Any) -> bool:
    """Whether a reviewer already cleared this page's exact semantic surface."""
    digest = _rationale_semantic_digest(page)
    if not digest:
        return False
    try:
        return _review_attestation_has(digest)
    except Exception:
        # A proof that cannot be read is a proof that does not exist: the proxy
        # keeps its blocker and publication stays fail-closed.
        return False


def _install_rationale_proof_lookup() -> None:
    """Give the shared predicate the same proof the gate reads.

    `render_contract` owns the name/gender rule for BOTH the publication gate
    and the renderer, so the proof has to be visible from inside it rather than
    consulted by one caller. Installed at import: any process that has the
    review layer loaded resolves proofs, and any process without it keeps the
    strict predicate, which is the fail-closed direction.
    """
    from services.authoring import render_contract as RC

    RC.set_rationale_proof_lookup(_rationale_proof_covers)


def attest_rationale_pages(content: Any, *, stage: str) -> int:
    """Record that a reviewer judged these pages' exact rationale surface.

    Called only after a rationale proof has been accepted AND its patches and
    deterministic normalization have been applied, so the attested bytes are the
    ones that will be persisted and exported rather than the ones the model was
    shown.
    """
    pages = content.get("pages") if isinstance(content, dict) else None
    stored = 0
    for page in pages or []:
        if not isinstance(page, dict):
            continue
        from services.authoring import render_contract as RC
        if not RC.mcq_like(page):
            continue
        digest = _rationale_semantic_digest(page)
        if not digest:
            continue
        try:
            _review_attestation_store(digest, stage=stage)
            stored += 1
        except Exception:
            continue
    return stored


def _explanation_grounding_blockers(content: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Final-artifact rationale invariants, shaped like renderer blockers."""
    from services.authoring import render_contract as RC

    pages = content.get("pages") if isinstance(content, dict) else None
    out: List[Dict[str, Any]] = []
    for page_index, page in enumerate(pages or []):
        names = _ungrounded_explanation_names(page)
        proven = None
        if names or not _rationale_has_specific_evidence(page):
            # Only consult the store when a proxy actually fires, so a clean
            # page costs no lookup.
            proven = _rationale_proof_covers(page)
            if proven:
                print(
                    f"[QUALITY-PROOF] proxy overruled by reviewer proof on "
                    f"pages[{page_index}]: "
                    f"{'grounding ' if names else ''}"
                    f"{'specificity' if not _rationale_has_specific_evidence(page) else ''}"
                    .strip(),
                    flush=True,
                )
                continue
        if names:
            out.append({
                "page_index": page_index,
                "title": str(page.get("title") or f"page {page_index}"),
                "locale": "both",
                "why": _EXPLANATION_GROUNDING_REASON,
                "detail": ", ".join(names),
                "stem": RC.resolve_stem(page, True) or RC.resolve_stem(page, False),
                "answer": str(page.get("answer") or ""),
            })
        if not _rationale_has_specific_evidence(page):
            out.append({
                "page_index": page_index,
                "title": str(page.get("title") or f"page {page_index}"),
                "locale": "both",
                "why": _EXPLANATION_SPECIFICITY_REASON,
                "detail": "rationale overlaps the item only through the keyed answer",
                "stem": RC.resolve_stem(page, True) or RC.resolve_stem(page, False),
                "answer": str(page.get("answer") or ""),
            })
    return out


def _active_renderer_stem_keys(page: Dict[str, Any]) -> List[str]:
    """Existing fields the renderer will actually select in either export locale."""
    from services.authoring import render_contract as RC

    keys: List[str] = []
    for candidates in (RC._STEM_KEYS_TR, RC._STEM_KEYS_EN):
        key = next(
            (name for name in candidates
             if isinstance(page.get(name), str) and page.get(name).strip()),
            None,
        )
        if key and key not in keys:
            keys.append(key)
    return keys


def _repair_topic_render_stems_exact(*, topic: Dict[str, Any], language: str,
                                      level: str, budget: ReviewBudget,
                                      blockers: Sequence[Dict[str, Any]],
                                      atomic_name_gender: bool = True) -> int:
    """Repair residual MCQ renderer blockers one stem at a time.

    Generic lesson review may understand the semantic issue yet still leave a
    renderer-only invariant unresolved. For identity/biographical inference,
    patching the exact stem is sufficient and avoids a terminal refusal after a
    successful model call.
    """
    from services.authoring import render_contract as RC

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

        # The personal-name→gender refusal is read off the STEM AND the
        # explanation together, so rewriting the stem alone is not the first
        # thing to try: that page gets the atomic repair instead.
        #
        # `atomic_name_gender=False` is the convergence controller invoking this
        # as the FALLBACK after the atomic repair has already been attempted on
        # this fingerprint. Routing back here would make that fallback a second
        # atomic attempt and the chain would have no second route at all, so the
        # page falls through to the genuinely stem-only repair below. Removing
        # the person from the stem clears the blocker too; the next convergence
        # round re-proves it against the audit, bilingual completeness and the
        # renderer contract in both locales.
        if atomic_name_gender and any(
            str(row.get("why") or "") == RC.NAME_GENDER_REASON
            for row in page_blockers
        ):
            applied += _repair_name_gender_page_exact(
                topic=topic, page=page, page_index=page_index,
                language=language, level=level, budget=budget,
                blockers=page_blockers,
            )
            continue

        stem_keys = _active_renderer_stem_keys(page)
        if not stem_keys:
            continue
        stem_key = stem_keys[0]
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

        changed = 0
        for active_key in stem_keys:
            active_before = str(page.get(active_key) or "").strip()
            if active_before == replacement:
                continue
            _set_path(
                content, ["pages", page_index, active_key], replacement,
                old=page.get(active_key),
            )
            changed += 1
        applied += changed

    return applied


# The renderer reads the personal-name→gender refusal off the stem AND the
# rationale together, so the two must be repaired as one page-level edit. A
# stem-only rewrite left the rationale saying "this name is feminine" and the
# page was refused again on the next audit — in production this looped through
# review_lesson → review_blocker_retry → review_render_exact and a whole unit
# retry without ever being able to converge, on `Adjective Agreement and
# Physical Description` and on `A Family Photograph` before it.
#
# The item's answer, options and distractors are immutable here: this defect is
# about how the learner is asked and how the answer is justified, never about
# what the answer is.
_NAME_GENDER_PAGE_REPAIR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "stem": {"type": "string", "minLength": 1},
        "explanation_en": {"type": "string", "minLength": 1},
        "explanation_tr": {"type": "string", "minLength": 1},
        "reason": {"type": "string"},
    },
    "required": ["stem", "explanation_en", "explanation_tr", "reason"],
}

_NAME_GENDER_PAGE_REPAIR_SYSTEM = """You repair exactly ONE multiple-choice item
that AulaAI's renderer refuses because its answer can only be reached by
guessing a person's gender from their personal name.

You return three learner-visible strings and nothing else. The item's answer,
options and distractors are FIXED — they are given to you as immutable context
and your rewrite must keep exactly that answer correct.

Hard contract:
- `stem`: the question, in the taught language named by `taught_language`. It
  must carry the evidence the answer needs ON ITS FACE — a stated noun, a
  stated article, a stated relationship, a stated form. A learner who has never
  heard the personal name must be able to answer it. Prefer replacing the
  person with the grammatical evidence itself (for example a stated noun with
  its article) over keeping a name and adding a hint.
- Do not require the learner to infer gender, nationality, profession or any
  other identity fact from a name, a birthplace, a residence, a job or a
  biography.
- `explanation_en` (English) and `explanation_tr` (Turkish) are the same
  rationale in the two locales. Each MUST explain the answer ONLY from what the
  new stem states. NEVER write that a name is feminine, masculine, a woman's
  name or a man's name, and never reason from the name at all — if the name is
  gone from the stem, do not mention it.
- Naming the grammatical category is expected and correct: say which stated
  word the answer agrees with and why. The forbidden move is grounding that in
  a person's name, not using grammatical vocabulary.
- Justify the answer ONLY from what the question shows: its stem, its options,
  or vocabulary the lesson teaches. Never introduce a person, a place or any
  other fact the learner cannot see — if the stem names nobody, your rationale
  names nobody. This text is printed verbatim in the answer key.
- Keep the CEFR level, the pedagogical point and the register. Do not add
  labels, commentary, markdown or alternatives.
- Return JSON only: {"stem":"...","explanation_en":"...",
  "explanation_tr":"...","reason":"brief reason"}.
"""

# Which page field each returned locale is written into. Only a key the page
# ALREADY carries with content is written; nothing new is invented.
_NAME_GENDER_EN_KEYS = ("explanation_en", "explanation", "analysis_en", "analysis")
_NAME_GENDER_TR_KEYS = ("explanation_tr", "analysis_tr")


def _repair_name_gender_page_exact(*, topic: Dict[str, Any], page: Dict[str, Any],
                                   page_index: int, language: str, level: str,
                                   budget: ReviewBudget,
                                   blockers: Sequence[Dict[str, Any]],
                                   strict: bool = True) -> int:
    """Repair one page's stem and rationale together, or refuse the page.

    Bounded and page-scoped: one call, one page, and only the stem plus the
    explanation fields the page already carries. The result is accepted only
    when the renderer contract passes for BOTH export locales on the page as it
    would look after the write, and when the answer, options and distractors
    come through untouched.

    `strict=False` is how the convergence controller calls it. An unusable
    candidate then writes nothing and returns 0 — a non-progressing attempt the
    controller can move past — instead of aborting the run before the fallback
    strategy on the same fingerprint is ever reached. Every other caller keeps
    the fail-closed behaviour: a rejected candidate there has nowhere else to go.
    """
    from services.authoring import render_contract as RC

    def reject(message: str) -> int:
        if strict:
            raise QualityGateError(message)
        print(f"[QUALITY-REPAIR] REJECT {message}", flush=True)
        return 0

    stem_keys = _active_renderer_stem_keys(page)
    if not stem_keys:
        return 0
    stem_key = stem_keys[0]
    before_stem = str(page[stem_key]).strip()
    en_keys = [k for k in _NAME_GENDER_EN_KEYS
               if isinstance(page.get(k), str) and page.get(k).strip()]
    tr_keys = [k for k in _NAME_GENDER_TR_KEYS
               if isinstance(page.get(k), str) and page.get(k).strip()]

    profile = S.profile_for_language(language)
    immutable = {}
    for key in ("type", "title", "title_tr", "answer", "options", "choices",
                "distractors", "term", "word", "target", "translation",
                "translation_tr"):
        value = page.get(key)
        if value not in (None, "", []):
            immutable[key] = value

    data = _call_review(
        model=REPAIR_MODEL,
        system=_NAME_GENDER_PAGE_REPAIR_SYSTEM,
        payload={
            "taught_language": language,
            "level": level,
            "regional_variety": profile.variety if profile else "",
            "topic_title": str(topic.get("title") or ""),
            "path": ["pages", page_index],
            "stem_field": stem_key,
            "current_stem": before_stem,
            "current_explanation_en": page.get(en_keys[0]) if en_keys else "",
            "current_explanation_tr": page.get(tr_keys[0]) if tr_keys else "",
            "renderer_contract_blockers": list(blockers),
            "immutable_page_context": immutable,
        },
        max_tokens=900,
        effort="low",
        budget=budget,
        stage=(
            f"review_render_name_gender:{topic.get('title')}:"
            f"pages.{page_index}.{stem_key}"
        ),
        response_schema=_NAME_GENDER_PAGE_REPAIR_SCHEMA,
        response_name="lesson_name_gender_page_repair",
    )

    stem = data.get("stem") if isinstance(data, dict) else None
    explanation_en = data.get("explanation_en") if isinstance(data, dict) else None
    explanation_tr = data.get("explanation_tr") if isinstance(data, dict) else None
    if not all(isinstance(v, str) and v.strip()
               for v in (stem, explanation_en, explanation_tr)):
        return reject(
            f"{topic.get('title')}: name/gender page repair returned an empty "
            f"field for page {page_index}"
        )

    updates: Dict[str, Any] = {
        key: stem.strip() for key in stem_keys
    }
    for key in en_keys:
        updates[key] = explanation_en.strip()
    for key in tr_keys:
        updates[key] = explanation_tr.strip()

    # Prove it on the page as it would look after the write, in both export
    # locales, before anything is written.
    probe = dict(page)
    probe.update(updates)
    for is_tr in RC.EXPORT_LOCALES:
        ok, why = RC.page_is_renderable(probe, is_tr)
        if not ok:
            # The candidate is discarded here and never reaches the page, so
            # without this line a rejected model answer leaves no evidence of
            # WHAT it wrote — only that it failed.
            _log_hidden_world("candidate_render_name_gender_rejected",
                              topic, page_index, probe)
            return reject(
                f"{topic.get('title')}: name/gender page repair still refused in "
                f"the {'tr' if is_tr else 'en'} export for page {page_index}: {why}"
            )
    ungrounded = _ungrounded_explanation_names(probe)
    if ungrounded:
        return reject(
            f"{topic.get('title')}: name/gender page repair left {ungrounded} "
            f"in the rationale without showing it in the question on page "
            f"{page_index}"
        )
    for key in ("answer", "options", "choices", "distractors"):
        if probe.get(key) != page.get(key):
            return reject(
                f"{topic.get('title')}: name/gender page repair changed {key!r} "
                f"on page {page_index}; the keyed answer is immutable here"
            )

    # A person the new stem no longer introduces must not survive in the
    # rationale. The renderer rule reads names off the stem, so a stale
    # "Ana is feminine" next to a stem about «mujer» would pass the contract
    # while still teaching the inference this repair exists to remove.
    before_names = set()
    after_names = set()
    for key in stem_keys:
        before_names |= RC.personal_name_tokens(page, str(page.get(key) or ""))
        after_names |= RC.personal_name_tokens(probe, str(probe.get(key) or ""))
    dropped = before_names - after_names
    if dropped:
        leftover = sorted(
            name for name in dropped
            for key in list(en_keys) + list(tr_keys)
            if name in RC.personal_name_tokens(probe, str(probe.get(key) or ""))
        )
        if leftover:
            return reject(
                f"{topic.get('title')}: name/gender page repair left {leftover} "
                f"in the rationale after removing it from the stem on page "
                f"{page_index}"
            )

    if all(page.get(key) == value for key, value in updates.items()):
        return 0
    page.update(updates)
    return 1


# One MCQ's key, its option list and its stored distractors are a single
# structure. Every code below is that structure disagreeing with itself, so they
# are repaired together or not at all: patching `options` alone can clear
# duplicate_options while leaving distractor_count standing, which is exactly
# how course 6c2c5f8c-28ed-4400-a620-75b4e42fadd4 stalled. distractor_count also
# resolves to no exact repair path at all (`distractors` is usually derived, not
# stored), so the path-at-a-time residual loop can never reach it.
_MCQ_STRUCTURAL_CODES = frozenset({
    "duplicate_options", "distractor_count", "empty_option",
    "answer_not_in_options", "option_distractor_mismatch",
})

_MCQ_OPTION_SET_REPAIR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer": {"type": "string", "minLength": 1},
        # Cardinality is stated in the system prompt and enforced by
        # _mcq_option_set_updates. `maxItems` is deliberately not in the wire
        # schema: `minItems`/`minLength` are already proven against the provider
        # this gate calls, `maxItems` is not, and the validator is the authority
        # either way.
        "options": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 4,
        },
        "distractors": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 3,
        },
        "reason": {"type": "string"},
    },
    "required": ["answer", "options", "distractors", "reason"],
}

_MCQ_OPTION_SET_REPAIR_SYSTEM = """You repair the option set of exactly ONE
multiple-choice item that failed AulaAI's deterministic publication audit.

The item's answer, options and distractors no longer describe one coherent
four-way choice: options repeat, are empty, do not contain the key, or do not
match the stored distractors.

Hard contract:
- Return the COMPLETE tuple: one answer, exactly four options, exactly three
  distractors. Partial answers are rejected.
- `answer` MUST stay the same answer the item already keys, character for
  character where possible. You are repairing the choices, not the fact.
- The four options are the answer plus the three distractors, in the order a
  learner should read them. `distractors` MUST be exactly the three options
  that are not the answer.
- Every option must be distinct to a learner: not a repeat, not the same word
  with only a diacritic or punctuation changed.
- Reuse the item's existing usable options wherever they are still correct.
  Write a replacement only for a slot the item genuinely lost.
- Every distractor must be a plausible but clearly WRONG answer to this exact
  stem, written in the taught language at the same CEFR level, in the same
  form and register as the other options.
- Do not reveal the key, do not add labels, commentary or markdown.
- Return JSON only:
  {"answer":"...","options":["...","...","...","..."],
   "distractors":["...","...","..."],"reason":"brief reason"}.
"""


def _mcq_structural_codes(findings: Iterable[A.Finding]) -> List[str]:
    return sorted({f.code for f in findings if f.code in _MCQ_STRUCTURAL_CODES})


def _mcq_option_set_updates(page: Dict[str, Any], candidate: Any, *,
                            language: str, track: str) -> Optional[Dict[str, Any]]:
    """Validate one answer/options/distractors tuple against this exact page.

    Returns the field assignments to write, or None when the tuple is not
    provably a coherent four-way choice. The proof is the auditor itself, run
    over the page as it would look after the write, so nothing can be accepted
    here that the gate would refuse two lines later.
    """
    if not isinstance(candidate, dict):
        return None
    answer = candidate.get("answer")
    options = candidate.get("options")
    distractors = candidate.get("distractors")
    if not isinstance(answer, str) or not answer.strip():
        return None
    if not isinstance(options, list) or len(options) != 4:
        return None
    if not isinstance(distractors, list) or len(distractors) != 3:
        return None
    if not all(isinstance(v, str) and v.strip() for v in options + distractors):
        return None
    answer = answer.strip()
    options = [v.strip() for v in options]
    distractors = [v.strip() for v in distractors]

    keys = [A.option_identity(v) for v in options]
    if not all(keys) or len(set(keys)) != 4:
        return None
    answer_key = A.option_identity(answer)
    if not answer_key or answer_key not in keys:
        return None
    if sorted(k for k in keys if k != answer_key) != \
            sorted(A.option_identity(d) for d in distractors):
        return None

    # The key is the taught fact, not part of this defect class. A repair that
    # silently rekeys the item would change what the lesson teaches under cover
    # of fixing its shape, so an item that already has a usable key keeps it.
    existing_answer = str(page.get("answer") or "").strip()
    if existing_answer and A.option_identity(existing_answer) != answer_key:
        return None

    # Write into the key this page already publishes; never invent a `options`
    # field next to a `choices` one, or a `distractors` field the auditor is
    # happy to derive.
    option_key = "options"
    if not isinstance(page.get("options"), list) or not page.get("options"):
        if isinstance(page.get("choices"), list) and page.get("choices"):
            option_key = "choices"
    updates: Dict[str, Any] = {"answer": answer, option_key: options}
    if isinstance(page.get("distractors"), list):
        updates["distractors"] = distractors

    probe = dict(page)
    probe.update(updates)
    if _mcq_structural_codes(A.blocking(
        A.audit_item(probe, language=language, track=track)
    )):
        return None
    return updates


def _repair_mcq_structural_blockers(*, topic: Dict[str, Any], language: str,
                                    level: str, track: str, budget: ReviewBudget,
                                    blockers: Sequence[A.Finding]) -> int:
    """Repair MCQ option-set blockers atomically, one page at a time.

    Deterministic first: when the page's own surviving text still holds three
    usable wrong choices, the whole tuple is rebuilt with no model call and
    nothing invented. Only a page that genuinely lost a choice costs one small
    bounded call scoped to that single item, which must return the complete
    tuple. Either way the write is all three fields at once, after the auditor
    has been re-run over the result — a half-applied structural repair is how a
    consistent item becomes an inconsistent one.
    """
    from services.authoring import render_contract as RC

    content = topic.get("content")
    pages = content.get("pages") if isinstance(content, dict) else None
    if not isinstance(pages, list):
        return 0

    by_page: Dict[int, List[A.Finding]] = {}
    for finding in blockers or []:
        if finding.code not in _MCQ_STRUCTURAL_CODES:
            continue
        prefix = _finding_path_prefix(finding.path)
        if len(prefix) != 2 or prefix[0] != "pages" or not isinstance(prefix[1], int):
            continue
        by_page.setdefault(prefix[1], []).append(finding)

    profile = S.profile_for_language(language)
    applied = 0
    for page_index, page_findings in sorted(by_page.items()):
        if page_index < 0 or page_index >= len(pages):
            continue
        page = pages[page_index]
        if not isinstance(page, dict):
            continue

        updates = _mcq_option_set_updates(
            page, R.rebuild_mcq_option_set(page), language=language, track=track
        )
        if updates is None:
            payload = {
                "taught_language": language,
                "level": level,
                "regional_variety": profile.variety if profile else "",
                "topic_title": str(topic.get("title") or ""),
                "path": ["pages", page_index],
                "stem": RC.resolve_stem(page, str(track).casefold() == "tr"),
                "current_answer": str(page.get("answer") or ""),
                "current_options": page.get("options") or page.get("choices") or [],
                "current_distractors": page.get("distractors") or [],
                "blockers": [f.as_dict() for f in page_findings],
                "immutable_page_context": {
                    key: page[key]
                    for key in ("type", "title", "title_tr", "prompt", "question",
                                "stem", "why", "why_tr", "translation",
                                "translation_tr")
                    if page.get(key) not in (None, "", [])
                },
            }
            data = _call_review(
                model=REPAIR_MODEL,
                system=_MCQ_OPTION_SET_REPAIR_SYSTEM,
                payload=payload,
                max_tokens=900,
                effort="low",
                budget=budget,
                stage=f"review_mcq_option_set:{topic.get('title')}:pages.{page_index}",
                response_schema=_MCQ_OPTION_SET_REPAIR_SCHEMA,
                response_name="mcq_option_set_repair",
            )
            updates = _mcq_option_set_updates(
                page, data, language=language, track=track
            )
            if updates is None:
                raise QualityGateError(
                    f"{topic.get('title')}: MCQ option-set repair returned an "
                    f"inconsistent tuple for page {page_index} "
                    f"({', '.join(_mcq_structural_codes(page_findings))})"
                )

        if all(page.get(key) == value for key, value in updates.items()):
            continue
        page.update(updates)
        applied += 1

    return applied


def _repair_partial_transcription_columns(*, topic: Dict[str, Any],
                                          language: str, level: str,
                                          budget: ReviewBudget,
                                          blockers: Sequence[A.Finding]) -> int:
    """Fill missing IPA cells atomically; never delete a partially useful column."""
    content = topic.get("content")
    if not isinstance(content, dict):
        return 0
    profile = S.profile_for_language(language)
    applied = 0
    for finding in blockers:
        if getattr(finding, "code", "") != "partial_transcription_column":
            continue
        prefix = _finding_path_prefix(getattr(finding, "path", ""))
        try:
            rows = _get_path(content, prefix)
        except Exception:
            rows = None
        if not isinstance(rows, list):
            raise QualityGateError(
                f"{topic.get('title')}: partial transcription container is not addressable"
            )
        missing = []
        bracketed = False
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            term = str(row.get("term") or row.get("word") or row.get("target") or "").strip()
            if not term:
                continue
            current = str(row.get("phonetic") or "").strip()
            if current:
                bracketed = bracketed or (
                    (current.startswith("[") and current.endswith("]"))
                    or (current.startswith("/") and current.endswith("/"))
                )
                continue
            missing.append({"row_id": f"m{index}", "index": index, "term": term})
        if not missing:
            continue
        data = _call_review(
            model=REPAIR_MODEL,
            system=_MISSING_TRANSCRIPTION_REPAIR_SYSTEM,
            payload={
                "language": language,
                "level": level,
                "regional_variety": profile.variety if profile else "",
                "bracketed_style_present": bracketed,
                "rows": [{"row_id": r["row_id"], "term": r["term"]} for r in missing],
            },
            max_tokens=max(500, 180 * len(missing)),
            effort="low",
            budget=budget,
            stage=f"review_missing_transcriptions:{topic.get('title')}",
            response_schema=_MISSING_TRANSCRIPTION_REPAIR_SCHEMA,
            response_name="missing_transcription_repair",
        )
        returned = data.get("rows") or []
        expected = {r["row_id"] for r in missing}
        got = {
            str(r.get("row_id") or "") for r in returned if isinstance(r, dict)
        }
        if got != expected or len(returned) != len(missing):
            raise QualityGateError(
                f"{topic.get('title')}: missing-transcription coverage mismatch"
            )
        by_id = {r["row_id"]: r for r in missing}
        for row in returned:
            row_id = str(row.get("row_id") or "")
            phonetic = row.get("phonetic")
            if not isinstance(phonetic, str) or not phonetic.strip():
                raise QualityGateError(
                    f"{topic.get('title')}: empty IPA for {row_id}"
                )
            target = rows[by_id[row_id]["index"]]
            if str(target.get("phonetic") or "").strip():
                raise QualityGateError(
                    f"{topic.get('title')}: missing IPA row changed concurrently"
                )
            target["phonetic"] = phonetic.strip()
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

            # Missing IPA cells are structural: the generic patcher cannot
            # patch a field that does not yet exist. Fill only the missing cells,
            # then re-audit before any broad semantic review.
            if any(f.code == "partial_transcription_column" for f in blockers):
                applied += _repair_partial_transcription_columns(
                    topic=topic, language=language, level=level,
                    budget=budget, blockers=blockers,
                )
                R.repair_lesson(content, language=language)
                blockers = A.blocking(
                    _audit_topic(topic, language=language, track=track)
                )
                if not blockers:
                    continue

            # MCQ option-set defects are structural, not editorial: they live in
            # three fields that must agree, and distractor_count resolves to no
            # exact repair path at all. Settle them atomically before the broad
            # repair call — deterministically when the page still holds the text
            # to do it, and never by relaxing what the auditor accepts.
            if _mcq_structural_codes(blockers):
                applied += _repair_mcq_structural_blockers(
                    topic=topic, language=language, level=level, track=track,
                    budget=budget, blockers=blockers,
                )
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
                    "records": [
                        dict(rec, record_id=f"r{index}")
                        for index, rec in enumerate(records)
                    ],
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

            # The broad repair can also reintroduce an option-set inconsistency
            # while fixing something else — it patches fields independently.
            # Settle that class atomically again before the path-at-a-time loop,
            # which by construction cannot resolve it.
            if still and _mcq_structural_codes(still):
                applied += _repair_mcq_structural_blockers(
                    topic=topic, language=language, level=level, track=track,
                    budget=budget, blockers=still,
                )
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
                        def _exact_candidate(payload: Dict[str, Any], *,
                                             suffix: str = "") -> str:
                            result = _call_review(
                                model=REPAIR_MODEL,
                                system=_EXACT_TARGET_REPAIR_SYSTEM,
                                payload=payload,
                                max_tokens=700,
                                effort="low",
                                budget=budget,
                                stage=(
                                    f"review_preflight_exact:{topic.get('title')}:"
                                    + ".".join(map(str, marker)) + suffix
                                ),
                                response_schema=_EXACT_TARGET_REPAIR_SCHEMA,
                                response_name="lesson_preflight_exact_target_value",
                            )
                            value = result.get("value")
                            if not isinstance(value, str) or not value.strip():
                                raise QualityGateError(
                                    f"preflight exact repair returned empty value for "
                                    f"{topic.get('title')} {list(marker)!r}"
                                )
                            return value.strip()

                        before_signature = {
                            (
                                finding.code,
                                str(getattr(finding, "path", "") or ""),
                                str(getattr(finding, "field", "") or ""),
                                str(getattr(finding, "detail", "") or ""),
                            )
                            for finding in still
                        }

                        def _prove_exact_candidate(replacement: str):
                            if replacement == before:
                                return None, [], set()
                            probe = copy.deepcopy(content)
                            _set_path(probe, list(marker), replacement, old=before)
                            R.repair_lesson(probe, language=language)

                            probe_topic = dict(topic)
                            probe_topic["content"] = probe
                            probe_blockers = A.blocking(
                                _audit_topic(
                                    probe_topic, language=language, track=track
                                )
                            )

                            def _finding_hits_marker(finding: A.Finding) -> bool:
                                paths = _repair_paths_for_finding(probe, finding)
                                return any(tuple(p) == marker for p in paths)

                            unresolved_here = [
                                finding for finding in probe_blockers
                                if _finding_hits_marker(finding)
                            ]
                            after_signature = {
                                (
                                    finding.code,
                                    str(getattr(finding, "path", "") or ""),
                                    str(getattr(finding, "field", "") or ""),
                                    str(getattr(finding, "detail", "") or ""),
                                )
                                for finding in probe_blockers
                            }
                            introduced = after_signature - before_signature
                            if unresolved_here or introduced or \
                                    len(after_signature) >= len(before_signature):
                                return None, unresolved_here, introduced
                            return probe, [], set()

                        replacement = _exact_candidate(exact_payload)
                        probe, unresolved_here, introduced = _prove_exact_candidate(
                            replacement
                        )

                        if probe is None:
                            # One bounded corrective attempt gets the authoritative
                            # audit result, not another vague "try again". This
                            # prevents two findings on the same path from taking
                            # turns undoing each other across convergence rounds.
                            corrective_payload = dict(exact_payload)
                            corrective_payload["rejected_candidate"] = replacement
                            corrective_payload["authoritative_remaining_blockers"] = [
                                finding.as_dict() for finding in unresolved_here
                            ]
                            corrective_payload["instruction"] = (
                                "Your previous replacement was rejected by the "
                                "authoritative deterministic audit. Return ONE "
                                "replacement for this same path that clears ALL "
                                "original blockers simultaneously and does not "
                                "introduce any new blocker. Do not change any "
                                "other field."
                            )
                            print(
                                f"[QUALITY-PATCH] RETRY atomic exact candidate "
                                f"{list(marker)!r}: unresolved_here="
                                f"{A.summarise(unresolved_here) if unresolved_here else {}} "
                                f"introduced={len(introduced)}",
                                flush=True,
                            )
                            replacement = _exact_candidate(
                                corrective_payload, suffix=":corrective"
                            )
                            probe, unresolved_here, introduced = _prove_exact_candidate(
                                replacement
                            )

                        if probe is None:
                            print(
                                f"[QUALITY-PATCH] REJECT atomic exact candidate "
                                f"{list(marker)!r} after corrective attempt: "
                                f"unresolved_here="
                                f"{A.summarise(unresolved_here) if unresolved_here else {}} "
                                f"introduced={len(introduced)}",
                                flush=True,
                            )
                            continue

                        # Commit only the exact snapshot that cleared every
                        # blocker on this path and strictly reduced the complete
                        # deterministic blocker set.
                        content.clear()
                        content.update(probe)
                        applied += 1
                        progress = True

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


_EXACT_BILINGUAL_COUNTERPART_SYSTEM = """You write exactly ONE missing
counterpart field for a bilingual AulaAI lesson page.

`source_value` is the field that already exists, in `source_locale`. You return
the SAME content in `target_locale` — nothing added, nothing dropped, nothing
answered or explained further.

Hard contract:
- `en` means English and `tr` means Turkish. Write the value in `target_locale`
  and in no other language.
- It must be a faithful counterpart of `source_value`: same meaning, same
  register, same CEFR level, same length class. Do not summarise, expand,
  re-teach, or add examples the source does not have.
- NEVER return `source_value` itself, or a copy of it with only punctuation or
  casing changed. A field that still reads in the source language is a failure,
  not a fallback.
- Target-language words the lesson teaches stay in the taught language inside
  the sentence; only the instructional prose around them changes locale.
- Do not add labels, quotation marks, commentary, markdown or alternatives.
- Return JSON only: {"value":"NON-EMPTY COUNTERPART","reason":"brief reason"}.
"""


def repair_bilingual_preflight(*, units: List[Dict[str, Any]],
                               language: str, level: str, track: str,
                               budget: ReviewBudget,
                               on_topic_complete: Optional[Any] = None) -> int:
    """Prove EN/TR completeness for every lesson before broad review runs.

    Bilingual completeness used to be a tail check inside `review_unit_lessons`,
    which made it both late and invisible: a gap the broad reviewer happened to
    fill never produced a `review_bilingual_retry` call, and the filled content
    only reached the database if the ENTIRE gate passed. Course
    6c2c5f8c… ran exactly that way — `Countries and Nationalities` was reviewed
    clean in memory, an unrelated renderer blocker on another topic aborted the
    run before the final persist, and the database kept the preflight-level
    snapshot whose `pages.5.text_tr` was still empty. The outer publication
    validation then refused the course over a gap that had been repaired.

    So bilingual completeness is its own stage, ahead of any broad review:
    deterministic detection, one small exact repair per missing counterpart, and
    a re-proof per topic. It never trusts a generic reviewer to produce a
    translation as a side effect, never copies the source into the target, and
    never accepts an empty counterpart. Callers checkpoint the result before
    spending review budget, so a later unrelated failure cannot leave the
    database in an incomplete bilingual state.
    """
    if S.canonical_language(language) in ("English", "Turkish"):
        return 0

    profile = S.profile_for_language(language)
    applied = 0
    for unit in units:
        for topic in unit.get("topics") or []:
            if topic.get("is_assessment"):
                continue
            content = topic.get("content")
            if not isinstance(content, dict):
                continue

            # Create only the counterpart slots an existing field already
            # obliges, so every repair below has an exact path and an exact
            # empty old value. No slot is created where both sides are absent.
            _ensure_bilingual_slots(content)
            slots = _missing_bilingual_slots(content)
            if not slots:
                continue

            topic_applied = 0
            for slot in slots:
                changed = _repair_bilingual_counterpart(
                    topic=topic, content=content, slot=slot,
                    language=language, level=level, track=track, budget=budget,
                    unit_title=str(unit.get("title") or ""),
                    profile=profile,
                )
                topic_applied += changed
                applied += changed

            remaining = _missing_bilingual_pairs(content)
            if remaining:
                raise QualityGateError(
                    f"{topic.get('title')}: incomplete EN/TR field pairs after "
                    f"bilingual preflight repair: " + ", ".join(remaining[:8])
                )

            # Persist only a topic that has proved complete.  The callback keeps
            # database concerns out of this module while ensuring a later topic's
            # failure cannot resurrect an already-repaired stale snapshot.
            if topic_applied and on_topic_complete is not None:
                on_topic_complete(topic, topic_applied)

    return applied


def _repair_bilingual_counterpart(*, topic: Dict[str, Any], content: Dict[str, Any],
                                  slot: Dict[str, Any], language: str, level: str,
                                  track: str, budget: ReviewBudget,
                                  unit_title: str, profile: Any) -> int:
    """Fill exactly one empty counterpart from its own source field."""
    path = list(slot["path"])
    source_value = str(slot.get("source_value") or "").strip()
    if not source_value:
        # A slot exists only because its source is non-empty; if that stopped
        # being true between detection and repair the re-proof below the caller
        # will refuse the topic rather than this writing something arbitrary.
        return 0

    current = _get_path(content, path)
    if not isinstance(current, str) or current.strip():
        return 0

    page_context: Dict[str, Any] = {}
    if len(path) >= 2 and path[0] == "pages" and isinstance(path[1], int):
        pages = content.get("pages")
        if isinstance(pages, list) and 0 <= path[1] < len(pages) and \
                isinstance(pages[path[1]], dict):
            page = pages[path[1]]
            for key in ("type", "title", "title_tr", "prompt", "question",
                        "term", "word", "target", "translation", "translation_tr"):
                value = page.get(key)
                if value not in (None, "", []):
                    page_context[key] = value

    base_payload = {
        "taught_language": language,
        "level": level,
        "regional_variety": profile.variety if profile else "",
        "instruction_track": track,
        "unit": unit_title,
        "topic_title": str(topic.get("title") or ""),
        "path": path,
        "field": slot["field"],
        "target_locale": slot["target_locale"],
        # Immutable evidence. The source field is read, never written.
        "source_field": slot["source_field"],
        "source_locale": slot["source_locale"],
        "source_value": source_value,
        "immutable_page_context": page_context,
    }
    stage = (
        f"review_bilingual_exact:{topic.get('title')}:"
        + ".".join(map(str, path))
    )

    def _candidate(*, corrective: bool = False, rejected: str = "",
                   max_tokens: int = 500) -> str:
        payload = dict(base_payload)
        if corrective:
            payload["rejected_candidate"] = rejected
            payload["instruction"] = (
                "The previous candidate was invalid because it was empty or "
                "copied source_value. Return a faithful translation in "
                "target_locale only; do not copy the source."
            )
        data = _call_review(
            model=REPAIR_MODEL,
            system=_EXACT_BILINGUAL_COUNTERPART_SYSTEM,
            payload=payload,
            max_tokens=max_tokens,
            effort="low",
            budget=budget,
            stage=stage + (":corrective" if corrective else ""),
            response_schema=_EXACT_TARGET_REPAIR_SCHEMA,
            response_name="lesson_bilingual_counterpart",
        )
        value = data.get("value")
        return value.strip() if isinstance(value, str) else ""

    try:
        value = _candidate()
    except QualityGateError as exc:
        # Structured output can occasionally spend its small completion budget
        # before closing the JSON object. That is transport truncation, not an
        # unrepairable content defect: retry only this exact slot with headroom.
        if "finish_reason=length" not in str(exc):
            raise
        value = _candidate(max_tokens=900)

    invalid = not value or _stem_key(value) == _stem_key(source_value)
    if invalid:
        # A counterpart is a repairable defect, not a reason to abandon the
        # whole classroom after one bad candidate. Retry this exact slot once;
        # no topic/unit work is repeated.
        try:
            value = _candidate(corrective=True, rejected=value)
        except QualityGateError as exc:
            if "finish_reason=length" not in str(exc):
                raise
            value = _candidate(
                corrective=True, rejected=value, max_tokens=900
            )
        invalid = not value or _stem_key(value) == _stem_key(source_value)

    if invalid:
        if not value:
            raise QualityGateError(
                f"{topic.get('title')}: bilingual exact repair returned an "
                f"empty counterpart twice for {'.'.join(map(str, path))}"
            )
        raise QualityGateError(
            f"{topic.get('title')}: bilingual exact repair copied the "
            f"{slot['source_locale']} source twice into "
            f"{'.'.join(map(str, path))} instead of writing "
            f"{slot['target_locale']}"
        )

    # Exactly the target counterpart is written, at the exact path, through the
    # same guard every reviewer patch goes through.
    _set_path(content, path, value, old=current)
    return 1


# ── Bounded convergence controller ───────────────────────────────────────────
# Every production failure so far — malformed reviewer paths, MCQ option/
# distractor inconsistency, a missing EN/TR counterpart, renderer hidden-world
# inference, the name/gender page repair — was a different defect meeting the
# same orchestration bug: a hand-rolled chain of "call, re-audit, raise" in
# which one class had no strategy that could express its fix, and the only
# fallback was re-reviewing the whole unit and arriving at the identical answer.
#
# The safety logic per class stays exactly where it is. What is unified is the
# contract around it: detect the exact blocker, classify it into one of the
# strategies below, repair the smallest surface that class owns, re-run the
# authoritative validators, and continue. A repair is never "successful"
# because a rule was disabled or a blocker allowlisted — only because
# `_audit_topic`, `_missing_bilingual_pairs` and `_topic_render_blockers` say
# so on the next round.
#
# "Until clean" is bounded by a fingerprint, not a retry count: topic, path,
# blocker code/reason and a digest of the object that blocker lives on. Seeing
# the same fingerprint again means the last strategy changed nothing, so that
# strategy is not called again for it. Another bounded strategy may take over;
# when none is left the gate fails closed with the exact diagnostic.

_NON_REPAIRABLE_CODES = frozenset({"not_a_lesson", "not_an_object"})
_CONVERGENCE_MAX_ROUNDS = 96


def _content_digest(node: Any) -> str:
    try:
        payload = json.dumps(node, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        payload = repr(node)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _blocker_page_index(where: Any) -> Optional[int]:
    prefix = _finding_path_prefix(where)
    if len(prefix) >= 2 and prefix[0] == "pages" and isinstance(prefix[1], int):
        return prefix[1]
    return None


def _detect_topic_blockers(topic: Dict[str, Any], *, language: str, track: str,
                           canonical: str) -> List[Dict[str, Any]]:
    """Every blocker on one topic, ordered cheapest-and-most-structural first.

    Ordering is deterministic so two runs over the same content dispatch the
    same strategies in the same order: structural MCQ defects, then the rest of
    the deterministic audit, then bilingual completeness, then the renderer
    contract. A blocker with no strategy is reported with none, and the
    controller fails closed on it rather than inventing a repair.
    """
    content = topic.get("content")
    if not isinstance(content, dict):
        return [{"kind": "structural", "code": "unreadable_content", "where": "",
                 "reason": "topic content is not an object", "strategies": []}]
    if content.get("_review_required"):
        return [{
            "kind": "structural",
            "code": "review_required_lesson",
            "where": "",
            "reason": str(content.get("_reason") or "lesson generation did not complete"),
            "strategies": [],
        }]

    structural: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []
    for finding in A.blocking(_audit_topic(topic, language=language, track=track)):
        row = {
            "kind": "audit",
            "code": finding.code,
            "where": str(finding.path or ""),
            "reason": str(finding.detail or finding.field or ""),
            "finding": finding,
        }
        if finding.code in _NON_REPAIRABLE_CODES:
            row["strategies"] = []
            structural.append(row)
        elif finding.code in _MCQ_STRUCTURAL_CODES:
            row["strategies"] = ["mcq_structural", "exact_field"]
            structural.append(row)
        else:
            row["strategies"] = ["exact_field"]
            other.append(row)

    bilingual: List[Dict[str, Any]] = []
    if canonical not in ("English", "Turkish"):
        for slot in _missing_bilingual_slots(content):
            bilingual.append({
                "kind": "bilingual",
                "code": "missing_bilingual_counterpart",
                "where": ".".join(map(str, slot["path"])),
                "reason": str(slot["field"]),
                "slot": slot,
                "strategies": ["bilingual_counterpart"],
            })

    # One blocker per (page, reason), carrying every locale row for it: the
    # repair is page-level, and both locales' rows are the evidence it reads.
    render: List[Dict[str, Any]] = []
    grouped: Dict[Tuple[Any, str], List[Dict[str, Any]]] = {}
    for row in _topic_render_blockers(content):
        grouped.setdefault((row.get("page_index"), str(row.get("why") or "")),
                           []).append(row)
    for row in _explanation_grounding_blockers(content):
        grouped.setdefault((row.get("page_index"), str(row.get("why") or "")),
                           []).append(row)
    for (page_index, why), rows in grouped.items():
        render.append({
            "kind": "render",
            "code": "render_contract",
            "where": f"pages[{page_index}]",
            "reason": why,
            "render_rows": rows,
            # The name/gender class owns two surfaces: the stem that introduces
            # the person and the rationale that reasons from them. The atomic
            # page repair edits both, which is what this class needs. The
            # stem-only repair is a genuine second route — removing the person
            # from the stem clears the blocker too — so it is the fallback
            # rather than a dead end when the page repair cannot converge.
            "strategies": (
                ["render_name_gender", "render_stem", "render_rescue"]
                if why == _name_gender_reason()
                else ["explanation_grounding", "render_rescue"]
                if why in {
                    _EXPLANATION_GROUNDING_REASON,
                    _EXPLANATION_SPECIFICITY_REASON,
                }
                else ["render_stem", "render_rescue"]
            ),
        })

    return structural + other + bilingual + render


def _blocker_fingerprint(topic: Dict[str, Any], blocker: Dict[str, Any]) -> str:
    """Stable logical identity of one publication blocker.

    Mutable content bytes MUST NOT be part of this identity. A failed repair can
    rewrite learner-visible text without clearing the same validator. Hashing
    that rewritten page makes the same blocker look new and re-enables the same
    paid strategies, which previously caused 24-round loops and long retries.

    Identity is therefore the invariant itself: topic, location, blocker code
    and validator reason. If a repair truly transforms the defect, path/code/
    reason changes and that new blocker receives its own bounded strategy set.
    """
    return "|".join((
        str(topic.get("id")), str(blocker.get("where")), str(blocker.get("code")),
        str(blocker.get("reason")),
    ))


def _name_gender_reason() -> str:
    from services.authoring import render_contract as RC
    return RC.NAME_GENDER_REASON


# One structured line per predicate evaluation of a name/gender page, so a
# production non-convergence says WHICH statement and WHICH boolean refused the
# item rather than only that something did. `pages[4]` of "Relative Clauses with
# Nominative, Accusative, and Dative" survived all three strategies while every
# fixture stayed green, which can only mean the live page differs from the
# fixtures in an input no log carried.
#
# Emitted only for the name/gender blocker class, which bounds the volume to the
# pages actually under repair, and only ever read from the page — this cannot
# change which pages publish.
def _log_hidden_world(stage: str, topic: Dict[str, Any], page_index: Any,
                      page: Any) -> None:
    from services.authoring import render_contract as RC
    if not isinstance(page, dict):
        return
    try:
        payload = {
            "stage": stage,
            "topic": str(topic.get("title") or "")[:80],
            "topic_id": str(topic.get("id") or ""),
            "where": f"pages[{page_index}]",
            "explain": RC.explain_hidden_world(page),
        }
        print("[QUALITY-REPAIR] [HIDDEN-WORLD] "
              + json.dumps(payload, ensure_ascii=False, sort_keys=True),
              flush=True)
    except Exception as exc:                       # never break a repair to log
        print(f"[QUALITY-REPAIR] [HIDDEN-WORLD] emit failed at {stage}: {exc!r}",
              flush=True)


def _log_hidden_world_blocker(stage: str, topic: Dict[str, Any],
                              blocker: Dict[str, Any]) -> None:
    """Emit the decomposition for the page one render blocker points at."""
    if str(blocker.get("reason") or "") != _name_gender_reason():
        return
    index = _blocker_page_index(blocker.get("where"))
    pages = (topic.get("content") or {}).get("pages")
    if index is None or not isinstance(pages, list) or not 0 <= index < len(pages):
        return
    _log_hidden_world(stage, topic, index, pages[index])


def _strategy_mcq_structural(*, topic, blocker, language, level, track, budget,
                             unit_title):
    return _repair_mcq_structural_blockers(
        topic=topic, language=language, level=level, track=track,
        budget=budget, blockers=[blocker["finding"]],
    )


def _strategy_bilingual_counterpart(*, topic, blocker, language, level, track,
                                    budget, unit_title):
    content = topic["content"]
    _ensure_bilingual_slots(content)
    return _repair_bilingual_counterpart(
        topic=topic, content=content, slot=blocker["slot"], language=language,
        level=level, track=track, budget=budget, unit_title=unit_title,
        profile=S.profile_for_language(language),
    )


def _strategy_explanation_grounding(*, topic, blocker, language, level, track,
                                    budget, unit_title):
    """Rewrite only the answer-key rationale for an otherwise valid MCQ."""
    from services.authoring import render_contract as RC

    rows = blocker.get("render_rows") or []
    pages = (topic.get("content") or {}).get("pages")
    try:
        page_index = int(rows[0].get("page_index"))
    except (IndexError, TypeError, ValueError, AttributeError):
        return 0
    if not isinstance(pages, list) or not 0 <= page_index < len(pages):
        return 0
    page = pages[page_index]
    if not isinstance(page, dict):
        return 0

    en_key = next(
        (k for k in _NAME_GENDER_EN_KEYS
         if isinstance(page.get(k), str) and page.get(k).strip()),
        None,
    )
    tr_key = next(
        (k for k in _NAME_GENDER_TR_KEYS
         if isinstance(page.get(k), str) and page.get(k).strip()),
        None,
    )
    if not en_key or not tr_key:
        return 0

    blocker_reasons = sorted({
        str(row.get("why") or "") for row in rows if str(row.get("why") or "")
    }) or [_EXPLANATION_GROUNDING_REASON]

    immutable = {}
    for key in ("prompt", "question", "stem", "answer", "options", "choices",
                "distractors", "term", "word", "target"):
        value = page.get(key)
        if value not in (None, "", []):
            immutable[key] = value

    profile = S.profile_for_language(language)
    data = _call_review(
        model=REPAIR_MODEL,
        system=_EXPLANATION_GROUNDING_REPAIR_SYSTEM,
        payload={
            "taught_language": language,
            "level": level,
            "regional_variety": profile.variety if profile else "",
            "topic_title": str(topic.get("title") or ""),
            "immutable_page_context": immutable,
            "current_explanation_en": page[en_key],
            "current_explanation_tr": page[tr_key],
            # The ACTUAL reasons this page was refused. This strategy owns two
            # rationale invariants, and `_grounding_clear` below accepts a
            # candidate only when BOTH pass. Naming one of them unconditionally
            # asked the repairer to remove a person from an item that has none
            # while the real defect — a rationale citing no item-specific
            # evidence — went unstated, so the candidate failed the acceptance
            # predicate and the strategy could never converge.
            "blocker": "; ".join(blocker_reasons),
            "blockers": blocker_reasons,
        },
        max_tokens=700,
        effort="low",
        budget=budget,
        stage=f"review_explanation_grounding:{topic.get('title')}:pages.{page_index}",
        response_schema=_EXPLANATION_GROUNDING_REPAIR_SCHEMA,
        response_name="mcq_explanation_grounding_repair",
    )
    new_en = str(data.get("explanation_en") or "").strip()
    new_tr = str(data.get("explanation_tr") or "").strip()

    def _grounding_clear(en_text: str, tr_text: str) -> bool:
        if not en_text or not tr_text:
            return False
        probe = copy.deepcopy(page)
        probe[en_key] = en_text
        probe[tr_key] = tr_text
        return not _explanation_grounding_blockers({"pages": [probe]})

    # A failed semantic repair must not be replaced by generic server-authored
    # boilerplate. No proven candidate means no progress; convergence remains
    # fail-closed.
    if not _grounding_clear(new_en, new_tr):
        return 0

    # This strategy owns only explanation grounding. Commit that proven local
    # repair even if another independent renderer rule still rejects the page;
    # the convergence controller immediately re-detects from scratch and sends
    # the remaining blocker to its own strategy. Requiring this one repair to
    # make the entire page renderable made genuine progress look like failure.
    changed = 0
    if new_en != page[en_key]:
        page[en_key] = new_en
        changed += 1
    if new_tr != page[tr_key]:
        page[tr_key] = new_tr
        changed += 1
    return changed


def _strategy_render_name_gender(*, topic, blocker, language, level, track,
                                 budget, unit_title):
    rows = blocker["render_rows"]
    pages = (topic.get("content") or {}).get("pages")
    index = rows[0].get("page_index")
    if not isinstance(pages, list) or not isinstance(index, int) or \
            not 0 <= index < len(pages) or not isinstance(pages[index], dict):
        return 0
    return _repair_name_gender_page_exact(
        topic=topic, page=pages[index], page_index=index, language=language,
        level=level, budget=budget, blockers=rows, strict=False,
    )


def _strategy_render_stem(*, topic, blocker, language, level, track, budget,
                          unit_title):
    # Stem-only, always. When this runs as the name/gender fallback the atomic
    # repair has already been attempted on this fingerprint, so re-entering it
    # would spend a second call on the same answer.
    return _repair_topic_render_stems_exact(
        topic=topic, language=language, level=level, budget=budget,
        blockers=blocker["render_rows"], atomic_name_gender=False,
    )


def _strategy_render_rescue(*, topic, blocker, language, level, track, budget,
                            unit_title):
    """Generic page-scoped rescue accepted only after authoritative re-validation."""
    content = topic.get("content")
    pages = content.get("pages") if isinstance(content, dict) else None
    page_index = _blocker_page_index(blocker.get("where"))
    if not isinstance(pages, list) or page_index is None or not 0 <= page_index < len(pages):
        return 0
    page = pages[page_index]
    if not isinstance(page, dict):
        return 0

    immutable_fields = {
        "type", "title", "title_tr", "answer", "options", "choices",
        "distractors", "term", "word", "target",
    }
    editable_names = {
        "prompt", "prompt_tr", "prompt_en",
        "question", "question_tr", "question_en",
        "stem", "stem_tr", "stem_en",
        "text", "text_tr", "text_en",
        "explanation", "explanation_en", "explanation_tr",
        "analysis", "analysis_en", "analysis_tr",
        "why", "why_tr", "context", "context_tr",
    }
    editable = {
        key: value
        for key, value in page.items()
        if key in editable_names and isinstance(value, str) and value.strip()
    }
    if not editable:
        return 0

    profile = S.profile_for_language(language)
    data = _call_review(
        model=ESCALATION_MODEL,
        system=(
            "Repair exactly one learner-visible MCQ page that failed a "
            "deterministic renderer contract. Work language-agnostically using "
            "the declared taught language. Return only existing editable fields "
            "that must change. Preserve answer, options, distractors, structure "
            "and pedagogical target exactly. Make the keyed answer derivable "
            "from explicit learner-visible grammatical or lexical evidence. "
            "Never rely on an unstated identity fact, personal-name stereotype, "
            "biography, workplace, residence or cultural assumption. Preserve "
            "valid language-specific grammar, morphology, script and agreement. "
            "Any rationale must justify the answer only from the rewritten "
            "visible item. No commentary or markdown."
        ),
        payload={
            "taught_language": language,
            "level": level,
            "regional_variety": profile.variety if profile else "",
            "blocker_reason": blocker.get("reason"),
            "editable_fields": editable,
            "immutable_fields": {
                key: value for key, value in page.items()
                if key in immutable_fields and value not in (None, "", [])
            },
        },
        max_tokens=1800,
        effort="low",
        budget=budget,
        stage=f"converge_render_rescue:{topic.get('title')}:pages.{page_index}",
        response_schema=_RENDER_RESCUE_SCHEMA,
        response_name="render_convergence_rescue",
    )

    updates = {}
    for raw in data.get("repairs") or []:
        if not isinstance(raw, dict):
            return 0
        field = str(raw.get("field") or "").strip()
        value = str(raw.get("value") or "").strip()
        if field not in editable or not value:
            return 0
        if field in updates:
            return 0
        if value != editable[field]:
            updates[field] = value
    if not updates:
        return 0

    probe_topic = copy.deepcopy(topic)
    probe_page = probe_topic["content"]["pages"][page_index]
    probe_page.update(updates)
    R.repair_lesson(probe_topic["content"], language=language)

    if A.blocking(_audit_topic(probe_topic, language=language, track=track)):
        return 0
    remaining = [
        row for row in _topic_render_blockers(probe_topic["content"])
        if row.get("page_index") == page_index
    ]
    remaining += [
        row for row in _explanation_grounding_blockers(probe_topic["content"])
        if row.get("page_index") == page_index
    ]
    if remaining:
        # Probed AFTER R.repair_lesson, so this line is the one that tells a
        # normalization reintroduction apart from a bad candidate.
        _log_hidden_world("candidate_render_rescue_rejected",
                          topic, page_index, probe_page)
        return 0

    changed = 0
    for field, value in updates.items():
        if page.get(field) != value:
            page[field] = value
            changed += 1
    return changed


def _strategy_exact_field(*, topic, blocker, language, level, track, budget,
                          unit_title):
    """One bounded exact-path repair for a single deterministic finding."""
    finding = blocker.get("finding")
    content = topic["content"]
    if finding is None:
        return 0
    rows = _findings_with_repair_paths(content, [finding])
    records = _records_for_findings(content, [finding])
    if not records or not any(row.get("repair_paths") for row in rows):
        # No exact learner-visible path resolves, so there is nothing this
        # strategy can express. The controller records it as attempted and
        # fails closed unless another strategy owns the blocker.
        return 0
    profile = S.profile_for_language(language)
    data = _call_review(
        model=REPAIR_MODEL, system=_LESSON_REVIEW_SYSTEM,
        payload={
            "language": language, "level": level, "unit": unit_title,
            "regional_variety": profile.variety if profile else "",
            "instruction_track": track,
            "topics": [{
                "topic_id": str(topic["id"]),
                "title": str(topic.get("title") or ""),
                "records": records,
                "deterministic_blockers": rows,
                "render_contract_blockers": [],
            }],
            "instruction": (
                "Patch EVERY listed repair_path exactly. Do not edit unrelated "
                "fields. Return this one topic only."
            ),
        },
        max_tokens=1600, effort="low", budget=budget,
        stage=f"converge_exact_field:{topic.get('title')}:{blocker.get('where')}",
        response_schema=_LESSON_REVIEW_SCHEMA,
        response_name="converge_exact_field_repair",
    )
    out = data.get("topics")
    if not isinstance(out, list) or len(out) != 1 or \
            str(out[0].get("topic_id") or "") != str(topic["id"]):
        raise QualityGateError(
            f"exact-field repair coverage failed for {topic.get('title')}"
        )
    patches = []
    for patch in (out[0].get("patches") or []):
        if not isinstance(patch, dict):
            raise QualityGateError("exact-field repair patch is not an object")
        patch = dict(patch)
        patch["topic_id"] = str(topic["id"])
        patches.append(patch)
    return _apply_patches({str(topic["id"]): topic}, patches)


# Every strategy here is an existing, narrow repair. There is deliberately no
# general "fix this lesson" entry: a class without a strategy fails closed.
_REPAIR_STRATEGIES = {
    "mcq_structural": _strategy_mcq_structural,
    "bilingual_counterpart": _strategy_bilingual_counterpart,
    "explanation_grounding": _strategy_explanation_grounding,
    "render_name_gender": _strategy_render_name_gender,
    "render_stem": _strategy_render_stem,
    "render_rescue": _strategy_render_rescue,
    "exact_field": _strategy_exact_field,
}


def _convergence_diagnostic(topic: Dict[str, Any], blockers: Sequence[Dict[str, Any]],
                            attempted: Sequence[Any]) -> str:
    rows = [
        {
            "code": b.get("code"),
            "where": b.get("where"),
            "reason": b.get("reason"),
            "strategies": b.get("strategies"),
        }
        for b in blockers[:8]
    ]
    # Terminal: this is the last moment the refused page still exists in
    # memory, so the decomposition is emitted here or never.
    for blocker in blockers:
        _log_hidden_world_blocker("terminal_non_convergence", topic, blocker)
    return (
        f"{topic.get('title')}: publication blockers are not converging; "
        f"unresolved={rows}; strategies_tried={len(attempted)}"
    )


def converge_topic(*, topic: Dict[str, Any], language: str, level: str, track: str,
                   budget: ReviewBudget, unit_title: str = "") -> int:
    """Repair one topic until the authoritative validators pass, or fail closed.

    Bounded by fingerprints rather than by a retry count. Re-detection happens
    from scratch after every repair, so a defect that turns into a different
    repairable class is dispatched as that class instead of being reported as
    the old one. The unit is never re-reviewed as a fallback: nothing here
    re-sends a lesson that has already passed.
    """
    canonical = S.canonical_language(language)
    attempted: set = set()
    applied = 0

    for _round in range(_CONVERGENCE_MAX_ROUNDS):
        # Cheap deterministic normalization first, every round: it costs
        # nothing and can remove a blocker before any model call is considered.
        if isinstance(topic.get("content"), dict):
            R.repair_lesson(topic["content"], language=language)

        blockers = _detect_topic_blockers(
            topic, language=language, track=track, canonical=canonical
        )
        if not blockers:
            return applied

        # After R.repair_lesson above: a candidate that was clean before
        # normalization and dirty after is a different defect from a candidate
        # the model never got right, and only this pair of lines separates them.
        for blocker in blockers:
            _log_hidden_world_blocker("post_repair_lesson_normalization",
                                      topic, blocker)

        for blocker in blockers:
            if not blocker.get("strategies"):
                # Structural / non-repairable invariant: never repaired, never
                # allowlisted, reported exactly as the validators saw it.
                raise QualityGateError(
                    f"{topic.get('title')}: non-repairable publication blocker "
                    f"{blocker.get('code')!r} at {blocker.get('where')!r}"
                    + (f": {blocker['reason']}" if blocker.get("reason") else "")
                )

        dispatched = False
        for blocker in blockers:
            fingerprint = _blocker_fingerprint(topic, blocker)
            for name in blocker["strategies"]:
                if (fingerprint, name) in attempted:
                    continue
                attempted.add((fingerprint, name))
                _log_hidden_world_blocker(f"before_{name}", topic, blocker)
                applied += _REPAIR_STRATEGIES[name](
                    topic=topic, blocker=blocker, language=language, level=level,
                    track=track, budget=budget, unit_title=unit_title,
                )
                # The committed page, whatever the strategy decided to write.
                # A strategy that returned 0 leaves this identical to the
                # `before_` line, which is how "wrote nothing" is told apart
                # from "wrote the wrong field".
                _log_hidden_world_blocker(f"after_{name}", topic, blocker)
                dispatched = True
                break
            if dispatched:
                # Re-detect from scratch: this repair may have cleared other
                # blockers, or produced a different repairable class.
                break

        if not dispatched:
            raise QualityGateError(
                _convergence_diagnostic(topic, blockers, attempted)
            )

    raise QualityGateError(
        f"{topic.get('title')}: publication repair exceeded "
        f"{_CONVERGENCE_MAX_ROUNDS} bounded rounds without converging"
    )


def review_unit_lessons(*, unit_title: str, topics: List[Dict[str, Any]],
                        language: str, level: str, track: str,
                        budget: ReviewBudget,
                        unit_topic_titles: Sequence[str] = ()) -> int:
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
        # The unit is the retry boundary, but a lesson that already passed
        # review, deterministic re-audit and the render contract is finished
        # work. Re-sending it would spend review budget to re-derive the same
        # result and could only be undone by a second provider response.
        if topic.get(_LESSON_REVIEW_DONE_KEY):
            continue
        if canonical not in ("English", "Turkish"):
            _ensure_bilingual_slots(topic.get("content"))

        findings = _audit_topic(topic, language=language, track=track)
        payload = {
            "language": language, "level": level, "unit": unit_title,
            "regional_variety": profile.variety if profile else "",
            "instruction_track": track,
            "unit_topic_titles": [
                str(v) for v in unit_topic_titles if str(v).strip()
            ],
            "topics": [{
                "topic_id": str(topic["id"]),
                "title": str(topic.get("title") or ""),
                "records": _assessment_evidence_records(topic["content"], track=track),
                "deterministic_blockers": _findings_payload(findings),
                "render_contract_blockers": _topic_render_blockers(topic["content"]),
            }],
        }
        topic_type = str(topic.get("type") or "").casefold()
        if "review" in topic_type or "recap" in topic_type or "revision" in topic_type:
            payload["unit_scope_evidence"] = [
                {
                    "title": str(other.get("title") or ""),
                    "evidence": _assessment_evidence_digest(
                        other.get("content") or {}, track=track
                    ),
                }
                for other in topics
                if str(other.get("id")) != str(topic.get("id"))
            ]
        lesson_cache_key = _review_attestation_key(
            kind="lesson_broad",
            model=REVIEW_MODEL,
            system=_LESSON_REVIEW_SYSTEM,
            payload=payload,
            response_schema=_LESSON_REVIEW_SCHEMA,
            response_name="lesson_review",
        )
        replay_data = _review_response_get(lesson_cache_key)
        lesson_cache_hit = _review_attestation_has(lesson_cache_key)
        if replay_data is not None:
            print(
                f"[QUALITY-CACHE] REPLAY lesson {unit_title}:{topic.get('title')} "
                f"{lesson_cache_key[:12]}",
                flush=True,
            )
            data = replay_data
        elif lesson_cache_hit:
            print(
                f"[QUALITY-CACHE] HIT lesson {unit_title}:{topic.get('title')} "
                f"{lesson_cache_key[:12]}",
                flush=True,
            )
            data = {"topics": [{
                "topic_id": str(topic["id"]), "verdict": "ok", "patches": []
            }]}
        else:
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
        notation_conflicts: List[Dict[str, Any]] = []
        applied += _apply_patches(
            by_id, patches, notation_conflicts=notation_conflicts
        )
        if notation_conflicts:
            applied += _repair_notation_patch_conflicts(
                topics_by_id=by_id,
                conflicts=notation_conflicts,
                language=language,
                level=level,
                budget=budget,
            )

        # Everything the broad editor did not cure goes to the bounded
        # convergence controller: detect the exact blocker, dispatch it to the
        # one narrow strategy that owns its class, re-run the authoritative
        # validators, repeat until clean or provably non-progressing. This
        # replaces the old hand-rolled chain of blocker retry -> exact retry ->
        # render repair -> bilingual retry, each of which could only express
        # part of the problem and whose only fallback was re-reviewing the unit.
        applied += converge_topic(
            topic=topic, language=language, level=level, track=track,
            budget=budget, unit_title=unit_title,
        )

        # Attest the FINAL state, not the pre-review state. If the reviewer made
        # a patch, the next retry must match the patched bytes before it can hit.
        final_findings = _audit_topic(topic, language=language, track=track)
        final_payload = {
            "language": language, "level": level, "unit": unit_title,
            "regional_variety": profile.variety if profile else "",
            "instruction_track": track,
            "unit_topic_titles": [
                str(v) for v in unit_topic_titles if str(v).strip()
            ],
            "topics": [{
                "topic_id": str(topic["id"]),
                "title": str(topic.get("title") or ""),
                "records": _assessment_evidence_records(topic["content"], track=track),
                "deterministic_blockers": _findings_payload(final_findings),
                "render_contract_blockers": _topic_render_blockers(topic["content"]),
            }],
        }
        if "review" in topic_type or "recap" in topic_type or "revision" in topic_type:
            final_payload["unit_scope_evidence"] = [
                {
                    "title": str(other.get("title") or ""),
                    "evidence": _assessment_evidence_digest(
                        other.get("content") or {}, track=track
                    ),
                }
                for other in topics
                if str(other.get("id")) != str(topic.get("id"))
            ]
        final_lesson_key = _review_attestation_key(
            kind="lesson_broad", model=REVIEW_MODEL,
            system=_LESSON_REVIEW_SYSTEM, payload=final_payload,
            response_schema=_LESSON_REVIEW_SCHEMA, response_name="lesson_review",
        )
        _review_attestation_store(
            final_lesson_key,
            stage=f"lesson:{unit_title}:{topic.get('title')}",
        )
        _review_response_store(
            lesson_cache_key, data,
            stage=f"lesson:{unit_title}:{topic.get('title')}",
        )

        # Reached only when this lesson cleared every check above, so a retry of
        # the unit resumes at the first lesson that has not passed yet.
        topic[_LESSON_REVIEW_DONE_KEY] = True

    return applied



_ABSOLUTE_RISK_RE = re.compile(
    r"\b(?:always|never|every|only|must|cannot|can't|impossible)\b"
    r"|\b(?:her\s+zaman|asla|hiçbir|yalnızca|sadece|daima|değişmez|zorunlu|imkânsız)\b",
    re.IGNORECASE,
)


def _scope_overlap_evidence(current: str, siblings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return only strong same-rule sibling evidence, ordered by similarity.

    Broad risk review already checks every selected claim. This selector exists
    only for likely scope contradictions, so precision matters more than recall:
    unnecessary escalation calls are redundant, slow and expensive.
    """
    base = " ".join(unicodedata.normalize("NFKC", current).casefold().split())
    if not base:
        return []
    scored = []
    for sibling in siblings:
        other = sibling.get("value")
        if not isinstance(other, str) or not other.strip():
            continue
        normalized = " ".join(
            unicodedata.normalize("NFKC", other).casefold().split()
        )
        ratio = difflib.SequenceMatcher(None, base, normalized).ratio()
        if ratio >= 0.46:
            scored.append((ratio, sibling))
    scored.sort(key=lambda row: row[0], reverse=True)
    return [row[1] for row in scored[:2]]

def _digit_notation_requires_escalation(term: str, value: str) -> bool:
    """Select digit expressions that deserve an independent second judgement.

    A previous detector only noticed multiple stress marks inside one
    whitespace token. Real PDF layout split malformed Spanish number IPA across
    spaces, so a phone number escaped despite being exactly the high-risk case.
    Multi-group/long digit expressions (phones, codes, dates, account-like
    strings) are rare and semantically dense enough to justify one compact
    independent call. Short ordinary numbers such as an age do not.
    """
    if not isinstance(term, str) or not isinstance(value, str):
        return False
    body = value.strip().strip("[]/")
    if any(token.count("ˈ") >= 2 for token in body.split()):
        return True
    digit_groups = re.findall(r"\d+", term)
    digit_count = sum(len(group) for group in digit_groups)
    return digit_count >= 4 or len(digit_groups) >= 2


def _risk_review_records(content: Dict[str, Any], *,
                         topic_type: str = "") -> List[Dict[str, Any]]:
    """Compact learner-visible claims that deserve a dedicated factual pass.

    Grammar/theory AND pronunciation/phonology prose are pedagogical rule
    surfaces even when no obvious absolute keyword is present. Pronunciation
    topics are especially vulnerable to textbook-sounding universals about
    connected speech, allophony and register, so their explanatory prose must
    receive the same counterexample/scope review as grammar.
    """
    pages = content.get("pages") if isinstance(content, dict) else None
    risk_page_indexes = set()
    topic_kind = str(topic_type or "").strip().casefold()
    pronunciation_topic = topic_kind in {
        "phonetic", "phonetics", "phonology", "pronunciation"
    }
    if isinstance(pages, list):
        for index, page in enumerate(pages):
            if not isinstance(page, dict):
                continue
            ptype = str(page.get("type") or "").strip().casefold()
            pronunciation_page = ptype in {
                "phonetic", "phonetics", "phonology", "pronunciation"
            }
            has_notation_surface = any(
                str(rec.get("field") or "") in _NOTATION_FIELDS
                for rec in _review_records(page)
            )
            if (
                ptype in ("grammar", "theory")
                or pronunciation_topic
                or pronunciation_page
                or has_notation_surface
            ):
                risk_page_indexes.add(index)

    out: List[Dict[str, Any]] = []
    for rec in _review_records(content):
        field = str(rec.get("field") or "")
        value = rec.get("value")
        if field in ("rule", "rule_tr", "analysis", "analysis_tr"):
            out.append(rec)
            continue
        if field in (
            "text", "text_tr", "explanation", "explanation_en", "explanation_tr"
        ) and isinstance(value, str):
            path = rec.get("path") or []
            on_risk_page = (
                len(path) >= 2 and path[0] == "pages"
                and isinstance(path[1], int) and path[1] in risk_page_indexes
            )
            if on_risk_page or _ABSOLUTE_RISK_RE.search(value):
                out.append(rec)
    return out


def review_unit_risk_claims(*, unit_title: str, topics: List[Dict[str, Any]],
                            language: str, level: str, track: str,
                            budget: ReviewBudget) -> int:
    """Second, narrow semantic pass over pedagogical claims only.

    Broad lesson review has many jobs and can miss a subtle overgeneralization.
    This pass is intentionally small: rules, explanations and absolute-sounding
    prose only. It does not rewrite ordinary lesson content.

    The review boundary is one topic, not the unit. It used to send every topic
    carrying risk records in a single payload and then demand that the response
    contain exactly one row per supplied topic_id. The response schema cannot
    express array cardinality or topic-id coverage, so the provider could — and
    in production did — return valid JSON covering only some of them: the call
    was ok=True, cost real money, and the build died on
    "risk reviewer returned incomplete topic coverage" with nothing salvaged.

    One topic per call removes that state entirely. A response either covers
    the single id it was asked about or it fails closed, and partial coverage
    of a batch is no longer a shape the code can be handed. A topic that
    completes is marked done, so a failure on a later topic never re-spends the
    calls that already succeeded. The system prompt is the cached prefix of
    every one of these calls, and only the selected risk records travel, which
    is what keeps splitting the payload from costing more than the whole-unit
    call it replaces.
    """
    profile = S.profile_for_language(language)
    applied = 0

    for topic in topics:
        if topic.get(_RISK_REVIEW_DONE_KEY):
            continue

        records = _risk_review_records(
            topic.get("content") or {}, topic_type=str(topic.get("type") or "")
        )
        if not records:
            # Nothing in this topic makes a pedagogical claim worth verifying.
            # The selector stays the authority on that; no call is made.
            topic[_RISK_REVIEW_DONE_KEY] = True
            continue

        topic_id = str(topic["id"])
        risk_payload = {
            "language": language,
            "level": level,
            "unit": unit_title,
            "regional_variety": profile.variety if profile else "",
            "instruction_track": track,
            "topics": [{
                "topic_id": topic_id,
                "title": str(topic.get("title") or ""),
                "records": [
                    dict(rec, record_id=f"r{index}")
                    for index, rec in enumerate(records)
                ],
                "absolute_ids": [
                    f"r{index}" for index, rec in enumerate(records)
                    if isinstance(rec.get("value"), str)
                    and _ABSOLUTE_RISK_RE.search(rec["value"])
                ],
            }],
        }
        risk_cache_key = _review_attestation_key(
            kind="risk_full",
            model=REVIEW_MODEL,
            system=_RISK_REVIEW_SYSTEM,
            payload=risk_payload,
            response_schema=_RISK_REVIEW_SCHEMA,
            response_name="pedagogical_risk_review",
            contract_extra={
                "escalation_model": ESCALATION_MODEL,
                "escalation_system": _EXACT_CATEGORICAL_REVIEW_SYSTEM,
                "escalation_schema": _EXACT_CATEGORICAL_REVIEW_SCHEMA,
            },
        )
        risk_replay = _review_response_get(risk_cache_key)
        # Order matters, and it used to be the other way round. These are two
        # proofs of different strength: the attestation says the WHOLE risk
        # stage — broad review AND every categorical escalation — already passed
        # for this exact content, while the cached response only answers the
        # first call. Consulting the response first made the stronger proof
        # unreachable, so a retry replayed one cheap call and then paid for
        # every escalation again. Measured on a clean three-unit classroom that
        # was 15 avoidable escalation calls per retry, against 19 calls for the
        # entire generation. The attestation is checked first now; the response
        # replay remains for the case where the stage did not finish.
        if _review_attestation_has(risk_cache_key):
            print(
                f"[QUALITY-CACHE] HIT risk {unit_title}:{topic.get('title')} "
                f"{risk_cache_key[:12]}",
                flush=True,
            )
            # The exact final semantic state already passed the complete risk
            # stage. Re-run convergence/deterministic proof only.
            applied += converge_topic(
                topic=topic, language=language, level=level, track=track,
                budget=budget, unit_title=unit_title,
            )
            topic[_RISK_REVIEW_DONE_KEY] = True
            continue
        elif risk_replay is not None:
            print(
                f"[QUALITY-CACHE] REPLAY risk {unit_title}:{topic.get('title')} "
                f"{risk_cache_key[:12]}",
                flush=True,
            )
            data = risk_replay
        else:
            data = _call_review(
            model=REVIEW_MODEL,
            system=_RISK_REVIEW_SYSTEM,
            payload=risk_payload,
            # One topic's worth of rows and patches rather than a whole unit's.
            # Still ample for every selected record to be patched; the reduction
            # is in what a single response can ever need to carry.
            max_tokens=1600,
            # Low, for the same reason broad lesson review is low: hidden
            # reasoning shares this completion budget with the structured JSON.
            # In production a 1302-char payload with max_tokens=1600 came back
            # at finish_reason=length after 86 visible characters — the response
            # died inside `"patches` with the whole budget spent on reasoning
            # nobody reads. The factual work still happens; it just stops being
            # charged against the bytes the schema needs.
            effort="low",
            budget=budget,
            stage=f"review_risk:{unit_title}:{topic.get('title')}",
            response_schema=_RISK_REVIEW_SCHEMA,
            response_name="pedagogical_risk_review",
        )
        if str(data.get("topic_id") or "") != topic_id:
            raise QualityGateError(
                f"{topic.get('title')}: risk reviewer returned wrong topic id"
            )
        expected_ids = {f"r{index}" for index, _ in enumerate(records)}
        checked_ids = {
            str(value) for value in (data.get("checked_ids") or [])
            if isinstance(value, str)
        }
        if checked_ids != expected_ids:
            missing = sorted(expected_ids - checked_ids)
            extra = sorted(checked_ids - expected_ids)
            raise QualityGateError(
                f"{topic.get('title')}: risk reviewer coverage mismatch; "
                f"missing_ids={missing[:5]} extra_ids={extra[:5]}"
            )
        server_scope_floor = {
            f"r{index}" for index, rec in enumerate(records)
            if isinstance(rec.get("value"), str)
            and _ABSOLUTE_RISK_RE.search(rec["value"])
        }
        categorical_ids = {
            str(value) for value in (data.get("categorical_ids") or [])
            if isinstance(value, str)
        }
        scope_checked_ids = {
            str(value) for value in (data.get("scope_checked_ids") or [])
            if isinstance(value, str)
        }
        missing_floor = server_scope_floor - categorical_ids
        unknown_categorical = categorical_ids - expected_ids
        missing_scope_ids = categorical_ids - scope_checked_ids
        unknown_scope_ids = scope_checked_ids - expected_ids
        if missing_floor or unknown_categorical or missing_scope_ids or unknown_scope_ids:
            raise QualityGateError(
                f"{topic.get('title')}: categorical-scope coverage mismatch; "
                f"floor_missing={sorted(missing_floor)[:5]} "
                f"unknown_categorical={sorted(unknown_categorical)[:5]} "
                f"scope_missing={sorted(missing_scope_ids)[:5]} "
                f"scope_unknown={sorted(unknown_scope_ids)[:5]}"
            )
        _require_risk_scope_proof(
            data,
            topic_title=str(topic.get("title") or ""),
            expected_scope_ids=categorical_ids,
        )
        categorical_paths = {
            tuple(records[int(rid[1:])].get("path") or [])
            for rid in categorical_ids
            if rid.startswith("r") and rid[1:].isdigit()
            and int(rid[1:]) < len(records)
        }

        patches = []
        for patch in (data.get("patches") or []):
            if not isinstance(patch, dict):
                raise QualityGateError("risk-review patch is not an object")
            item = dict(patch)
            item["topic_id"] = topic_id
            patches.append(item)
        applied += _apply_patches({topic_id: topic}, patches)

        # Broad risk review cannot be its own final authority on categorical
        # truth. Every SERVER-FLAGGED/model-declared categorical claim still
        # receives an independent exact judgement, but transport is batched:
        # several claims share one provider round-trip while each keeps its own
        # opaque id, verdict, replacement and proof. This removes latency without
        # reducing coverage or changing the fail-closed contract.
        current_records = _risk_review_records(
            topic.get("content") or {}, topic_type=str(topic.get("type") or "")
        )
        exact_candidates = []
        for exact_index, rec in enumerate(current_records):
            value = rec.get("value")
            path = rec.get("path") or []
            server_flagged_now = (
                isinstance(value, str) and bool(_ABSOLUTE_RISK_RE.search(value))
            )
            model_declared = tuple(path) in categorical_paths
            if not (server_flagged_now or model_declared) or not isinstance(value, str):
                continue
            page_index = path[1] if (
                len(path) >= 2 and path[0] == "pages" and isinstance(path[1], int)
            ) else None
            siblings = []
            for sibling in current_records:
                spath = sibling.get("path") or []
                if sibling is rec:
                    continue
                if (
                    page_index is not None and len(spath) >= 2
                    and spath[0] == "pages" and spath[1] == page_index
                    and isinstance(sibling.get("value"), str)
                ):
                    siblings.append({
                        "field": sibling.get("field"),
                        "value": sibling.get("value"),
                    })
            exact_candidates.append({
                "claim_id": f"c{exact_index}",
                "path": path,
                "current": value,
                "same_page_siblings": _scope_overlap_evidence(value, siblings),
            })

        # Keep batches deliberately small. Six independent claims comfortably fit
        # the structured response while collapsing the dominant one-call-per-claim
        # latency seen in production.
        batch_size = 6
        for batch_start in range(0, len(exact_candidates), batch_size):
            batch = exact_candidates[batch_start:batch_start + batch_size]
            exact = _call_review(
                model=ESCALATION_MODEL,
                system=_BATCH_CATEGORICAL_REVIEW_SYSTEM,
                payload={
                    "language": language,
                    "level": level,
                    "regional_variety": profile.variety if profile else "",
                    "claims": [
                        {
                            "claim_id": row["claim_id"],
                            "current": row["current"],
                            "same_page_siblings": row["same_page_siblings"],
                        }
                        for row in batch
                    ],
                },
                max_tokens=1400,
                effort="low",
                budget=budget,
                stage=(
                    f"review_categorical_escalation_batch:{unit_title}:"
                    f"{topic.get('title')}:{batch_start // batch_size}"
                ),
                response_schema=_BATCH_CATEGORICAL_REVIEW_SCHEMA,
                response_name="categorical_scope_escalation_batch",
            )
            expected_claims = {row["claim_id"] for row in batch}
            results = exact.get("results") or []
            returned_claims = {
                str(row.get("claim_id") or "") for row in results
                if isinstance(row, dict)
            }
            if returned_claims != expected_claims or len(results) != len(batch):
                raise QualityGateError(
                    f"{topic.get('title')}: categorical batch coverage mismatch; "
                    f"missing={sorted(expected_claims-returned_claims)} "
                    f"extra={sorted(returned_claims-expected_claims)}"
                )
            by_claim = {row["claim_id"]: row for row in batch}
            for result in results:
                claim_id = str(result.get("claim_id") or "")
                source = by_claim[claim_id]
                value = source["current"]
                verdict = str(result.get("verdict") or "")
                replacement = result.get("value")
                if verdict == "ok":
                    if replacement != value:
                        raise QualityGateError(
                            f"{topic.get('title')}: categorical escalation "
                            f"marked ok but changed value for {claim_id}"
                        )
                    continue
                if (
                    verdict != "fix"
                    or not isinstance(replacement, str)
                    or not replacement.strip()
                ):
                    raise QualityGateError(
                        f"{topic.get('title')}: categorical escalation returned "
                        f"invalid fix for {claim_id}"
                    )
                applied += _apply_patches(
                    {topic_id: topic},
                    [{
                        "topic_id": topic_id,
                        "path": source["path"],
                        "old": value,
                        "value": replacement,
                        "reason": (
                            result.get("reason")
                            or "categorical scope correction"
                        ),
                    }],
                )

        # A risk patch is an ordinary content edit and can leave any of the
        # repairable classes behind it. Proving that is the convergence
        # controller's job, not a second hand-rolled audit/render check here:
        # it re-runs the deterministic audit, bilingual completeness and the
        # renderer contract, dispatches whatever it finds to the strategy that
        # owns it, and fails closed when nothing progresses.
        applied += converge_topic(
            topic=topic, language=language, level=level, track=track,
            budget=budget, unit_title=unit_title,
        )

        final_records = _risk_review_records(
            topic.get("content") or {}, topic_type=str(topic.get("type") or "")
        )
        if final_records:
            final_risk_payload = {
                "language": language,
                "level": level,
                "unit": unit_title,
                "regional_variety": profile.variety if profile else "",
                "instruction_track": track,
                "topics": [{
                    "topic_id": topic_id,
                    "title": str(topic.get("title") or ""),
                    "records": [
                        dict(rec, record_id=f"r{index}")
                        for index, rec in enumerate(final_records)
                    ],
                    "absolute_ids": [
                        f"r{index}" for index, rec in enumerate(final_records)
                        if isinstance(rec.get("value"), str)
                        and _ABSOLUTE_RISK_RE.search(rec["value"])
                    ],
                }],
            }
            final_risk_key = _review_attestation_key(
                kind="risk_full", model=REVIEW_MODEL,
                system=_RISK_REVIEW_SYSTEM, payload=final_risk_payload,
                response_schema=_RISK_REVIEW_SCHEMA,
                response_name="pedagogical_risk_review",
                contract_extra={
                    "escalation_model": ESCALATION_MODEL,
                    "escalation_system": _EXACT_CATEGORICAL_REVIEW_SYSTEM,
                    "escalation_schema": _EXACT_CATEGORICAL_REVIEW_SCHEMA,
                },
            )
            _review_attestation_store(
                final_risk_key,
                stage=f"risk:{unit_title}:{topic.get('title')}",
            )
        _review_response_store(
            risk_cache_key, data,
            stage=f"risk:{unit_title}:{topic.get('title')}",
        )
        topic[_RISK_REVIEW_DONE_KEY] = True

    return applied



_EXACT_CATEGORICAL_REVIEW_SYSTEM = """You are AulaAI's final semantic arbiter
for one categorical pedagogical claim. Judge ONLY the supplied current claim
against the declared language, level and regional variety. Same-page sibling
claims may be supplied as supporting evidence but can be empty.

A categorical claim is publication-safe only if it is true for the whole class
of forms it names. Actively search for standard counterexamples, contextual
conditioning and exception classes even when no sibling evidence is supplied.
If a sibling claim narrows the same category with wording equivalent to
many, most, usually, often, some, except, or a named subclass, the target claim
must not silently broaden that category to all members unless that broader claim
is genuinely universal.

Return JSON only:
{"verdict":"ok|fix","value":"FINAL CLAIM","reason":"brief factual reason"}

Rules:
- If verdict=ok, value MUST equal current exactly.
- If verdict=fix, preserve the teaching point but narrow or qualify it enough to
  be factually correct. Do not add unrelated material.
- Do not depend on the source language wording; judge the linguistic rule itself.
"""

_BATCH_CATEGORICAL_REVIEW_SYSTEM = """You are AulaAI's final semantic arbiter
for a SMALL BATCH of categorical pedagogical claims. Judge EACH claim
independently against the declared language, level and regional variety.
Same-page sibling claims are supporting context only.

For every supplied claim, actively search for standard counterexamples,
conditioning factors and exception classes. Do not let one claim's verdict
influence another merely because they are in the same batch.

Return JSON only:
{"results":[
  {"claim_id":"c0","verdict":"ok|fix","value":"FINAL CLAIM",
   "reason":"brief factual reason"}
]}

Contract:
- Return exactly one result for every supplied claim_id and no others.
- Copy claim_id exactly.
- If verdict=ok, value MUST equal that claim's current value exactly.
- If verdict=fix, preserve the teaching point but narrow or qualify it enough to
  be factually correct. Do not add unrelated material.
- Judge every claim independently; batching changes transport only, not rigor.
"""

_DIGIT_NOTATION_VERIFY_SYSTEM = """You are AulaAI's final verifier for one
digit-bearing pronunciation entry. Work from the exact written learner-visible
term and current transcription.

First derive a plain-language spoken_form for the complete written expression in
the declared target language and regional variety. Then verify the IPA against
that spoken_form token by token. Every written digit/group must be represented
in order; no digit/group may disappear, merge into a different number, or be
invented. Reject malformed pseudo-IPA even when it resembles the intended number
word. If a label such as telephone/address/room precedes the digits, verify that
label too.

Return JSON only:
{"verdict":"ok|fix","spoken_form":"HOW THE WHOLE TERM IS READ",
 "value":"FINAL IPA","reason":"brief reason"}

Rules:
- If verdict=ok, value MUST equal current exactly.
- If verdict=fix, value must be a complete replacement transcription for the
  whole written term, not a partial fragment.
- Preserve the classroom's bracket convention and declared regional variety.
"""

_RATIONALE_GROUNDING_REVIEW_SYSTEM = """You are AulaAI's answer-key grounding verifier.
Review ONLY the supplied lesson MCQ rationales. The questions, keyed answers and
options are already fixed.

For every item:
- verify that each explanation justifies the keyed answer from information
  visible in the stem/options or from the grammatical/lexical fact directly
  tested by those words;
- require a SPECIFIC discriminating rationale: it must name the actual visible
  clue, grammatical relation, lexical distinction, form, case, agreement,
  meaning contrast, or other concrete fact that selects the keyed answer.
  Generic statements equivalent to "the answer is correct", "it matches the
  question/rule/material", "it matches the information shown", or merely
  restating the keyed answer are NOT publication quality and MUST be patched;
- remove invented people, subjects, scenarios, biographical facts or contextual
  details that do not appear in the item;
- do not infer gender, identity, nationality, profession or other properties
  from a personal name;
- keep English and Turkish rationales semantically equivalent;
- keep useful grammatical explanation when it is genuinely required by the item;
- when the stem itself explicitly states the evidence that selects the answer,
  explain from that exact visible evidence. Do not replace it with a looser fact
  from another lesson or with vague phrases such as "the material says here";
- do not rewrite a correct explanation for style alone.

Return JSON only:
{"checked_ids":["q0"],
 "quality_checks":[
   {"item_id":"q0","grounded":true,"rationale_specific":true,
    "reason":"brief final-state judgement"}
 ],
 "patches":[
   {"item_id":"q0","field":"explanation_tr",
    "old":"EXACT OLD","value":"GROUNDED REPLACEMENT","reason":"brief reason"}
 ]}

Contract:
- checked_ids MUST contain every supplied item_id exactly once. Copy opaque IDs exactly.
- quality_checks MUST contain every supplied item_id exactly once and no others.
  Judge the FINAL state after your own patches. Both grounded and
  rationale_specific must be true. If either is false in the input, patch the
  explanation first; never certify a generic rationale as specific.
- Every patch MUST identify only item_id + field. Never reconstruct or return a topic_id, page index or path; the server owns those coordinates.
- Patch ONLY an existing field listed inside that item's explanations object.
- Never change stems, answers, options, distractors, titles or structure.
- Copy old exactly, byte for byte from that same item and field.
"""

_COMPLEX_NOTATION_REVIEW_SYSTEM = """You are AulaAI's pronunciation verifier for
complex written headwords. Verify every supplied transcription against the exact
written headword, declared language and regional variety.

Complex entries may contain numbers, symbols, punctuation or several words.
Check the whole expression, not merely whether the string looks IPA-like.
Correct malformed segments, omitted material, wrong sounds, impossible symbols
or transcription that belongs to a different written form. For any written
digit sequence, independently verify every spoken number segment and its IPA:
digits/groups must be represented in the same order, no digit may disappear or
be invented, and a valid number word written in malformed pseudo-IPA is still a
defect. If the term includes a label plus digits, verify both the label and the
digit reading. Preserve the classroom's bracket style. Do not respell, add
alternatives or rewrite a correct transcription for style.

Return JSON only:
{"checked_ids":["n0"],
 "patches":[
   {"topic_id":"EXACT ID","path":["pages","0","items","0","phonetic"],
    "old":"EXACT OLD","value":"CORRECT IPA","reason":"brief reason"}
 ]}

Contract:
- checked_ids MUST contain every supplied item_id exactly once. Copy opaque IDs
  exactly; do not reconstruct paths.
- Patch ONLY the supplied notation paths.
- Copy old exactly, byte for byte.
"""


def _lesson_mcq_rationale_items(topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compact lesson-MCQ evidence for semantic rationale grounding."""
    items: List[Dict[str, Any]] = []
    for topic in topics:
        content = topic.get("content")
        pages = content.get("pages") if isinstance(content, dict) else None
        for page_index, page in enumerate(pages or []):
            if not isinstance(page, dict) or str(page.get("type") or "").casefold() != "mcq":
                continue
            explanation_fields = {}
            for key in tuple(dict.fromkeys(_NAME_GENDER_EN_KEYS + _NAME_GENDER_TR_KEYS)):
                value = page.get(key)
                if isinstance(value, str) and value.strip():
                    explanation_fields[key] = value
            if not explanation_fields:
                continue
            stem = next(
                (str(page.get(key)).strip() for key in ("prompt", "question", "stem")
                 if isinstance(page.get(key), str) and page.get(key).strip()),
                "",
            )
            options = page.get("options") or page.get("choices") or []
            items.append({
                "item_id": f"q{len(items)}",
                "topic_id": str(topic["id"]),
                "page_index": page_index,
                "stem": stem,
                "answer": page.get("answer"),
                "options": options,
                "explanations": explanation_fields,
            })
    return items


def review_unit_mcq_rationales(*, unit_title: str, topics: List[Dict[str, Any]],
                               language: str, level: str, track: str,
                               budget: ReviewBudget) -> int:
    """Semantically ground every lesson-MCQ answer-key rationale in one unit."""
    items = _lesson_mcq_rationale_items(topics)
    if not items:
        return 0
    profile = S.profile_for_language(language)
    rationale_payload = {
        "language": language,
        "level": level,
        "regional_variety": profile.variety if profile else "",
        "unit": unit_title,
        "items": items,
    }
    # Lesson, risk and assessment review all replay a validated response when
    # their exact input recurs; this stage did not, so every retry of a build
    # paid for it again over content that had not changed. Measured on a clean
    # three-unit classroom, a retry re-reviewed nothing else and still spent
    # this call per unit. The key is the full payload, so any edit to an item's
    # stem, options, answer or rationale is a different review and is charged.
    rationale_cache_key = _review_attestation_key(
        kind="rationale_grounding",
        model=REVIEW_MODEL,
        system=_RATIONALE_GROUNDING_REVIEW_SYSTEM,
        payload=rationale_payload,
        response_schema=_MCq_RATIONALE_REVIEW_SCHEMA,
        response_name="lesson_mcq_rationale_grounding",
    )
    replay_data = _review_response_get(rationale_cache_key)
    if replay_data is not None:
        print(
            f"[QUALITY-CACHE] REPLAY rationale {unit_title} "
            f"{rationale_cache_key[:12]}",
            flush=True,
        )
        data = replay_data
    else:
        data = _call_review(
            model=REVIEW_MODEL,
            system=_RATIONALE_GROUNDING_REVIEW_SYSTEM,
            payload=rationale_payload,
            max_tokens=1800,
            effort="low",
            budget=budget,
            stage=f"review_rationale_grounding:{unit_title}",
            response_schema=_MCq_RATIONALE_REVIEW_SCHEMA,
            response_name="lesson_mcq_rationale_grounding",
        )

    expected_ids = {row["item_id"] for row in items}
    checked_ids = {
        str(value) for value in (data.get("checked_ids") or [])
        if isinstance(value, str)
    }
    if checked_ids != expected_ids:
        raise QualityGateError(
            f"{unit_title}: rationale grounding coverage mismatch; "
            f"missing_ids={sorted(expected_ids - checked_ids)[:5]} "
            f"extra_ids={sorted(checked_ids - expected_ids)[:5]}"
        )
    _require_rationale_quality_proof(
        data, expected_ids=expected_ids,
        unit_title=unit_title, stage="rationale grounding reviewer"
    )

    by_id = {str(topic["id"]): topic for topic in topics}
    item_by_id = {row["item_id"]: row for row in items}

    def _materialize_rationale_patch(raw: Dict[str, Any]) -> Dict[str, Any]:
        item_id = str(raw.get("item_id") or "")
        row = item_by_id.get(item_id)
        if row is None:
            raise QualityGateError(
                f"rationale grounding patch has unknown item_id {item_id!r}"
            )
        field = str(raw.get("field") or "")
        if field not in row["explanations"]:
            raise QualityGateError(
                f"rationale grounding may not patch {item_id} field {field!r}"
            )
        return {
            "topic_id": row["topic_id"],
            "path": ["pages", row["page_index"], field],
            "old": raw.get("old"),
            "value": raw.get("value"),
            "reason": raw.get("reason") or "",
        }

    patches = []
    for raw in (data.get("patches") or []):
        if not isinstance(raw, dict):
            raise QualityGateError("rationale grounding patch is not an object")
        patch = _materialize_rationale_patch(raw)
        topic = by_id[patch["topic_id"]]
        current = _get_path(topic["content"], patch["path"])
        if current != patch["old"]:
            row = item_by_id[str(raw.get("item_id") or "")]
            retry = _call_review(
                model=REVIEW_MODEL,
                system=_RATIONALE_GROUNDING_REVIEW_SYSTEM,
                payload={
                    "language": language,
                    "level": level,
                    "regional_variety": profile.variety if profile else "",
                    "unit": unit_title,
                    "items": [row],
                    "instruction": (
                        "EXACT ITEM RETRY: review only this one item. Copy item_id "
                        "and old field values exactly from the payload."
                    ),
                },
                max_tokens=700,
                effort="low",
                budget=budget,
                stage=f"review_rationale_exact:{unit_title}:{row['item_id']}",
                response_schema=_MCq_RATIONALE_REVIEW_SCHEMA,
                response_name="lesson_mcq_rationale_exact",
            )
            if set(retry.get("checked_ids") or []) != {row["item_id"]}:
                raise QualityGateError(
                    f"{unit_title}: exact rationale retry coverage mismatch for {row['item_id']}"
                )
            _require_rationale_quality_proof(
                retry, expected_ids={row["item_id"]},
                unit_title=unit_title, stage="exact rationale retry"
            )
            retry_patches = retry.get("patches") or []
            if not retry_patches:
                continue
            if len(retry_patches) != 1:
                raise QualityGateError(
                    f"{unit_title}: exact rationale retry returned "
                    f"{len(retry_patches)} patches for one item"
                )
            patch = _materialize_rationale_patch(retry_patches[0])
            topic = by_id[patch["topic_id"]]
            current = _get_path(topic["content"], patch["path"])
            if current != patch["old"]:
                raise QualityGateError(
                    f"{unit_title}: exact rationale retry remained stale for "
                    f"{row['item_id']} {patch['path']!r}"
                )
        patches.append(patch)

    applied = _apply_patches(by_id, patches)

    # The reviewer has now judged every item in `expected_ids` and its patches
    # are applied, so these exact bytes carry a language-aware grounding and
    # specificity verdict. Attest them: from here the token proxies may report
    # this page but may no longer be the thing that refuses a paid classroom at
    # the final gate. Attestation is per item and keyed to the page's semantic
    # surface, so anything edited afterwards drops back under the proxy.
    for row in items:
        topic = by_id.get(str(row.get("topic_id")))
        pages = (topic or {}).get("content", {}).get("pages")
        index = row.get("page_index")
        if not isinstance(pages, list) or not isinstance(index, int):
            continue
        if not 0 <= index < len(pages):
            continue
        attest_rationale_pages(
            {"pages": [pages[index]]},
            stage=f"rationale_proof:{unit_title}:{row.get('item_id')}",
        )

    # Only now: the response passed coverage, passed its per-item proof and its
    # patches applied cleanly. Caching earlier would replay an answer that never
    # finished being accepted.
    _review_response_store(
        rationale_cache_key, data, stage=f"rationale:{unit_title}",
    )

    # This verifier owns rationale grounding only. Do not invoke the whole
    # convergence machine after a clean local repair: that can make an
    # explanation edit pay for an unrelated bilingual/structural repair. If the
    # new rationale itself still trips grounding or renderer semantics, then
    # hand only that genuinely affected topic back to convergence.
    for topic in topics:
        content = topic.get("content") or {}
        if _explanation_grounding_blockers(content) or _topic_render_blockers(content):
            applied += converge_topic(
                topic=topic, language=language, level=level, track=track,
                budget=budget, unit_title=unit_title,
            )
    return applied


def _complex_notation_items(topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Notation rows whose written form makes silent corruption harder to spot."""
    items: List[Dict[str, Any]] = []

    def walk(node: Any, path: List[Any], topic: Dict[str, Any]) -> None:
        if isinstance(node, dict):
            term = node.get("term") or node.get("word") or node.get("target")
            if isinstance(term, str) and term.strip():
                normalized = term.strip()
                complex_headword = (
                    bool(re.search(r"\d|[@._/+:#-]", normalized))
                    or len(normalized.split()) >= 3
                )
                if complex_headword:
                    for field in _NOTATION_FIELDS:
                        value = node.get(field)
                        if isinstance(value, str) and value.strip():
                            items.append({
                                "topic_id": str(topic["id"]),
                                "path": path + [field],
                                "term": normalized,
                                "field": field,
                                "value": value.strip(),
                            })
            for key, value in node.items():
                walk(value, path + [key], topic)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path + [index], topic)

    for topic in topics:
        walk(topic.get("content") or {}, [], topic)
    return items


def review_unit_complex_notation(*, unit_title: str, topics: List[Dict[str, Any]],
                                 language: str, level: str,
                                 budget: ReviewBudget) -> int:
    """Verify complex pronunciation rows, with exact focus for digit-bearing terms."""
    items = _complex_notation_items(topics)
    if not items:
        return 0
    profile = S.profile_for_language(language)
    by_id = {str(topic["id"]): topic for topic in topics}
    applied = 0

    # Digit-bearing learner strings (phone numbers, addresses, codes, prices)
    # get bounded exact convergence. A candidate is not committed merely because
    # one reviewer produced plausible-looking IPA: the next independent call
    # must accept the complete digit reading and transcription unchanged.
    digit_items = [row for row in items if re.search(r"\d", row["term"])]
    for index, row in enumerate(digit_items):
        candidate = row["value"]
        accepted = False
        for round_index in range(3):
            data = _call_review(
                model=REVIEW_MODEL,
                system=_DIGIT_NOTATION_VERIFY_SYSTEM,
                payload={
                    "language": language,
                    "level": level,
                    "regional_variety": profile.variety if profile else "",
                    "unit": unit_title,
                    "term": row["term"],
                    "field": row["field"],
                    "current": candidate,
                    "phase": (
                        "initial exact judgement" if round_index == 0
                        else "independent verification of the previous candidate"
                    ),
                },
                max_tokens=800,
                effort="low",
                budget=budget,
                stage=f"review_complex_digit_notation:{unit_title}:{index}:{round_index}",
                response_schema=_DIGIT_NOTATION_VERIFY_SCHEMA,
                response_name="complex_digit_notation_verify",
            )
            verdict = str(data.get("verdict") or "")
            value = data.get("value")
            spoken_form = data.get("spoken_form")
            if not isinstance(spoken_form, str) or not spoken_form.strip():
                raise QualityGateError(
                    f"{unit_title}: digit notation verifier omitted spoken form"
                )
            if verdict == "ok":
                if value != candidate:
                    raise QualityGateError(
                        f"{unit_title}: digit notation verifier marked ok but changed value"
                    )
                if _digit_notation_requires_escalation(row["term"], candidate):
                    data = _call_review(
                        model=ESCALATION_MODEL,
                        system=_DIGIT_NOTATION_VERIFY_SYSTEM,
                        payload={
                            "language": language,
                            "level": level,
                            "regional_variety": profile.variety if profile else "",
                            "unit": unit_title,
                            "term": row["term"],
                            "field": row["field"],
                            "current": candidate,
                            "phase": (
                                "INDEPENDENT ESCALATION: Gemini marked this IPA ok, "
                                "but a whitespace-delimited IPA token contains "
                                "multiple primary-stress marks. Verify word "
                                "boundaries and the complete digit reading."
                            ),
                        },
                        max_tokens=650,
                        effort="low",
                        budget=budget,
                        stage=f"review_complex_digit_escalation:{unit_title}:{index}:{round_index}",
                        response_schema=_DIGIT_NOTATION_VERIFY_SCHEMA,
                        response_name="complex_digit_notation_escalation_verify",
                    )
                    verdict = str(data.get("verdict") or "")
                    value = data.get("value")
                    spoken_form = data.get("spoken_form")
                    if not isinstance(spoken_form, str) or not spoken_form.strip():
                        raise QualityGateError(
                            f"{unit_title}: independent digit verifier omitted spoken form"
                        )
                    if verdict == "ok":
                        if value != candidate:
                            raise QualityGateError(
                                f"{unit_title}: independent digit verifier marked ok but changed value"
                            )
                        accepted = True
                        break
                    if verdict != "fix" or not isinstance(value, str) or not value.strip():
                        raise QualityGateError(
                            f"{unit_title}: independent digit verifier returned invalid fix"
                        )
                    if value == candidate:
                        raise QualityGateError(
                            f"{unit_title}: independent digit verifier requested a no-op fix"
                        )
                    candidate = value
                    continue
                accepted = True
                break
            if verdict != "fix" or not isinstance(value, str) or not value.strip():
                raise QualityGateError(
                    f"{unit_title}: digit notation verifier returned invalid fix"
                )
            if value == candidate:
                raise QualityGateError(
                    f"{unit_title}: digit notation verifier requested a no-op fix"
                )
            candidate = value

        if not accepted:
            raise QualityGateError(
                f"{unit_title}: digit notation did not converge after 3 exact judgements"
            )
        if candidate != row["value"]:
            topic = by_id[row["topic_id"]]
            applied += _apply_patches(
                {row["topic_id"]: topic},
                [{
                    "topic_id": row["topic_id"],
                    "path": row["path"],
                    "old": row["value"],
                    "value": candidate,
                    "reason": "digit-bearing pronunciation exact convergence",
                }],
            )

    # The remaining non-digit complex forms are safe to verify in one compact batch.
    items = [row for row in items if not re.search(r"\d", row["term"])]
    if not items:
        return applied
    payload_items = [
        {
            "item_id": f"n{index}",
            "topic_id": row["topic_id"],
            "path": [str(part) for part in row["path"]],
            "term": row["term"],
            "field": row["field"],
            "value": row["value"],
        }
        for index, row in enumerate(items)
    ]
    data = _call_review(
        model=REVIEW_MODEL,
        system=_COMPLEX_NOTATION_REVIEW_SYSTEM,
        payload={
            "language": language,
            "level": level,
            "regional_variety": profile.variety if profile else "",
            "unit": unit_title,
            "items": payload_items,
        },
        # Production regularly exhausted 1200 and paid a second 2000-token
        # transport round-trip. Providers bill actual output, while the budget
        # still reserves the declared worst case, so give the first call the
        # headroom it already needed without changing any review contract.
        max_tokens=2000,
        effort="low",
        budget=budget,
        stage=f"review_complex_notation:{unit_title}",
        response_schema=_COMPLEX_NOTATION_REVIEW_SCHEMA,
        response_name="complex_notation_review",
    )
    expected_ids = {f"n{index}" for index, _ in enumerate(items)}
    checked_ids = {
        str(value) for value in (data.get("checked_ids") or [])
        if isinstance(value, str)
    }
    if checked_ids != expected_ids:
        raise QualityGateError(
            f"{unit_title}: complex notation coverage mismatch; "
            f"missing_ids={sorted(expected_ids - checked_ids)[:5]} "
            f"extra_ids={sorted(checked_ids - expected_ids)[:5]}"
        )

    allowed = {
        (
            row["topic_id"],
            json.dumps([str(p) for p in row["path"]], ensure_ascii=False,
                       separators=(",", ":")),
        )
        for row in items
    }
    patches = []
    for raw in (data.get("patches") or []):
        if not isinstance(raw, dict):
            raise QualityGateError("complex notation patch is not an object")
        patch = dict(raw)
        topic_id = str(patch.get("topic_id") or "")
        topic = by_id.get(topic_id)
        if topic is None or not isinstance(patch.get("path"), list):
            raise QualityGateError("complex notation patch targets unknown content")
        coerced = _coerce_patch_path(topic["content"], patch["path"])
        marker = (
            topic_id,
            json.dumps([str(p) for p in coerced], ensure_ascii=False,
                       separators=(",", ":")),
        )
        if marker not in allowed or str(coerced[-1]) not in _NOTATION_FIELDS:
            raise QualityGateError(
                f"complex notation review may not patch {topic_id} {coerced!r}"
            )
        patch["path"] = coerced
        patches.append(patch)
    return applied + _apply_patches(by_id, patches)


def _cross_topic_phonetic_occurrences(
        units: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Same lexical headword carrying multiple transcriptions across a class."""
    groups: Dict[str, List[Dict[str, Any]]] = {}

    def walk(node: Any, path: List[Any], unit: Dict[str, Any],
             topic: Dict[str, Any]) -> None:
        if isinstance(node, dict):
            term = node.get("term") or node.get("word") or node.get("target")
            if isinstance(term, str) and term.strip():
                key = " ".join(
                    unicodedata.normalize("NFC", term).strip().casefold().split()
                )
                for field in _NOTATION_FIELDS:
                    value = node.get(field)
                    if isinstance(value, str) and value.strip():
                        groups.setdefault(key, []).append({
                            "unit": str(unit.get("title") or ""),
                            "topic": topic,
                            "term": term.strip(),
                            "field": field,
                            "path": path + [field],
                            "value": value.strip(),
                        })
            for key, value in node.items():
                walk(value, path + [key], unit, topic)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, path + [index], unit, topic)

    for unit in units:
        for topic in unit.get("topics") or []:
            walk(topic.get("content") or {}, [], unit, topic)

    conflicts = []
    for rows in groups.values():
        variants = {
            unicodedata.normalize("NFC", row["value"]).strip()
            for row in rows
        }
        if len(variants) > 1:
            conflicts.append(rows)
    return conflicts


def repair_cross_topic_phonetic_conflicts(*, units: List[Dict[str, Any]],
                                          language: str, level: str,
                                          track: str,
                                          budget: ReviewBudget) -> int:
    """Resolve class-wide pronunciation disagreement by linguistic judgement."""
    profile = S.profile_for_language(language)
    applied = 0
    touched: Dict[str, Dict[str, Any]] = {}

    for rows in _cross_topic_phonetic_occurrences(units):
        term = rows[0]["term"]
        variants = []
        for row in rows:
            if row["value"] not in variants:
                variants.append(row["value"])
        payload = {
            "language": language,
            "level": level,
            "regional_variety": profile.variety if profile else "",
            "term": term,
            "candidates": variants,
            "occurrences": [
                {
                    "unit": row["unit"],
                    "topic": str(row["topic"].get("title") or ""),
                    "field": row["field"],
                    "current_value": row["value"],
                }
                for row in rows
            ],
        }
        data = _call_review(
            model=REPAIR_MODEL,
            system=_EXACT_PHONETIC_CONFLICT_REPAIR_SYSTEM,
            payload=payload,
            max_tokens=500,
            effort="low",
            budget=budget,
            stage=f"review_phonetic_conflict:{term}",
            response_schema=_EXACT_TARGET_REPAIR_SCHEMA,
            response_name="phonetic_conflict_repair",
        )
        replacement = data.get("value")
        if not isinstance(replacement, str) or not replacement.strip():
            raise QualityGateError(
                f"{term}: phonetic-conflict repair returned empty value"
            )
        replacement = replacement.strip()
        for row in rows:
            if unicodedata.normalize("NFC", row["value"]).strip() == replacement:
                continue
            _set_path(
                row["topic"]["content"],
                row["path"],
                replacement,
                old=row["value"],
            )
            touched[str(row["topic"]["id"])] = row["topic"]
            applied += 1

    remaining = _cross_topic_phonetic_occurrences(units)
    if remaining:
        examples = [
            f"{rows[0]['term']}: "
            + " <> ".join(dict.fromkeys(row["value"] for row in rows))
            for rows in remaining[:4]
        ]
        raise QualityGateError(
            "cross-topic phonetic conflicts remain after repair: "
            + " | ".join(examples)
        )

    for topic in touched.values():
        R.repair_lesson(topic["content"], language=language)
        blockers = A.blocking(_audit_topic(topic, language=language, track=track))
        if blockers:
            raise QualityGateError(
                f"{topic.get('title')}: phonetic conflict repair introduced blockers: "
                f"{A.summarise(blockers)}"
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
    # The answer key prints these rationales verbatim, so an ungrounded one is
    # a publication defect the examiner must be told about, in the same shape.
    for row in _explanation_grounding_blockers(content):
        blockers.append(dict(row, question=1 + sum(
            1 for i, p in enumerate(pages or [])
            if i < row["page_index"] and isinstance(p, dict)
            and str(p.get("type") or "").casefold() == "mcq"
        )))
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



def _require_rationale_quality_proof(data: Dict[str, Any], *,
                                    expected_ids: set,
                                    unit_title: str, stage: str) -> None:
    rows = data.get("quality_checks")
    if not isinstance(rows, list):
        raise QualityGateError(
            f"{unit_title}: {stage} omitted rationale quality_checks"
        )
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise QualityGateError(
                f"{unit_title}: {stage} rationale proof row is not an object"
            )
        item_id = str(row.get("item_id") or "")
        if not item_id or item_id in seen:
            raise QualityGateError(
                f"{unit_title}: {stage} invalid rationale proof id {item_id!r}"
            )
        seen.add(item_id)
        failed = [
            key for key in ("grounded", "rationale_specific")
            if row.get(key) is not True
        ]
        if failed:
            raise QualityGateError(
                f"{unit_title}: {stage} final rationale proof failed "
                f"{item_id}: {','.join(failed)} - "
                f"{str(row.get('reason') or '')[:180]}"
            )
    if seen != set(expected_ids):
        raise QualityGateError(
            f"{unit_title}: {stage} rationale proof coverage mismatch; "
            f"missing={sorted(set(expected_ids)-seen)[:5]} "
            f"extra={sorted(seen-set(expected_ids))[:5]}"
        )


def _require_assessment_quality_proof(data: Dict[str, Any], *,
                                      unit_title: str, stage: str) -> None:
    rows = data.get("quality_checks")
    if not isinstance(rows, list) or len(rows) != 10:
        raise QualityGateError(
            f"{unit_title}: {stage} returned invalid quality proof cardinality"
        )
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise QualityGateError(
                f"{unit_title}: {stage} quality proof row is not an object"
            )
        q = row.get("question")
        if not isinstance(q, int) or q < 1 or q > 10 or q in seen:
            raise QualityGateError(
                f"{unit_title}: {stage} quality proof has invalid question {q!r}"
            )
        seen.add(q)
        failed = [
            key for key in (
                "single_answer", "distractors_plausible",
                "rationale_specific", "cefr_fit"
            )
            if row.get(key) is not True
        ]
        if failed:
            raise QualityGateError(
                f"{unit_title}: {stage} final quality proof failed Q{q}: "
                f"{','.join(failed)} - {str(row.get('reason') or '')[:180]}"
            )
    if seen != set(range(1, 11)):
        raise QualityGateError(
            f"{unit_title}: {stage} quality proof coverage mismatch"
        )


def _require_risk_scope_proof(data: Dict[str, Any], *,
                              topic_title: str,
                              expected_scope_ids: set) -> None:
    rows = data.get("scope_checks")
    if not isinstance(rows, list):
        raise QualityGateError(
            f"{topic_title}: risk reviewer omitted scope_checks"
        )
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise QualityGateError(
                f"{topic_title}: risk scope proof row is not an object"
            )
        rid = str(row.get("record_id") or "")
        if rid in seen:
            raise QualityGateError(
                f"{topic_title}: duplicate risk scope proof id {rid}"
            )
        seen.add(rid)
        if row.get("counterexample_tested") is not True:
            raise QualityGateError(
                f"{topic_title}: no counterexample test for {rid}"
            )
        if row.get("final_scope_safe") is not True:
            raise QualityGateError(
                f"{topic_title}: unsafe categorical claim remains at {rid}: "
                f"{str(row.get('reason') or '')[:180]}"
            )
    if seen != set(expected_scope_ids):
        raise QualityGateError(
            f"{topic_title}: risk scope proof coverage mismatch; "
            f"missing={sorted(set(expected_scope_ids)-seen)[:5]} "
            f"extra={sorted(seen-set(expected_scope_ids))[:5]}"
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
            "title": str(topic.get("title") or ""),
            "evidence": _assessment_evidence_digest(topic["content"], track=track),
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
    assessment_cache_key = _review_attestation_key(
        kind="assessment_broad",
        model=REVIEW_MODEL,
        system=_ASSESSMENT_REVIEW_SYSTEM,
        payload=payload,
        response_schema=_ASSESSMENT_REVIEW_SCHEMA,
        response_name="assessment_review",
    )
    assessment_replay = _review_response_get(assessment_cache_key)
    assessment_cache_hit = _review_attestation_has(assessment_cache_key)
    if assessment_replay is not None:
        print(
            f"[QUALITY-CACHE] REPLAY assessment {unit_title} "
            f"{assessment_cache_key[:12]}",
            flush=True,
        )
        data = assessment_replay
    elif assessment_cache_hit:
        print(
            f"[QUALITY-CACHE] HIT assessment {unit_title} "
            f"{assessment_cache_key[:12]}",
            flush=True,
        )
        data = {
            "checked_questions": list(range(1, 11)),
            "quality_checks": [
                {
                    "question": q,
                    "single_answer": True,
                    "distractors_plausible": True,
                    "rationale_specific": True,
                    "cefr_fit": True,
                    "reason": "exact final semantic state previously proved",
                }
                for q in range(1, 11)
            ],
            "patches": [],
        }
    else:
        data = _call_review(
            model=REVIEW_MODEL, system=_ASSESSMENT_REVIEW_SYSTEM, payload=payload,
            # Production repeatedly exhausts 2400 while returning the required
            # ten-question proof, then succeeds at 3200. Start at the proven
            # ceiling: evidence/schema/quality requirements are identical, and
            # billing is based on actual output rather than unused headroom.
            max_tokens=3200, effort="low", budget=budget,
            stage=f"review_assessment:{unit_title}",
            response_schema=_ASSESSMENT_REVIEW_SCHEMA, response_name="assessment_review",
        )
    _checked_all_ten(data, unit_title=unit_title, stage="assessment reviewer")
    _require_assessment_quality_proof(
        data, unit_title=unit_title, stage="assessment reviewer"
    )
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

    # NOTE: deliberately NOT attesting the rationale surface here.
    # `_require_assessment_quality_proof` is a BLANKET ten-question quality
    # verdict, not a per-item adjudication of grounding. Attesting on it lets a
    # sweeping "all ten are fine" silently disable the invented-person detector,
    # which is the self-certification loophole this gate already closed once. A
    # proof may overrule a proxy only where the reviewer's whole job was that
    # exact question, item by item — which is the rationale grounding reviewer,
    # and only there.

    # Assessment rationales use the same deterministic grounding contract as
    # lesson MCQs. Repair EVERY grounding blocker in this unit with the proven
    # page-scoped strategy before falling back to the broad assessment editor.
    # This prevents one invented-person rationale from consuming the unit's only
    # generic retry and avoids surfacing the same repairable class one question
    # at a time across later retries.
    render_blockers = _assessment_render_blockers(content)
    grounding_pages = sorted({
        int(row["page_index"])
        for row in render_blockers
        if row.get("why") in {
            _EXPLANATION_GROUNDING_REASON, _EXPLANATION_SPECIFICITY_REASON
        }
        and isinstance(row.get("page_index"), int)
    })
    for page_index in grounding_pages:
        rows = [
            row for row in render_blockers
            if row.get("why") in {
                _EXPLANATION_GROUNDING_REASON, _EXPLANATION_SPECIFICITY_REASON
            }
            and row.get("page_index") == page_index
        ]
        if not rows:
            continue
        applied += _strategy_explanation_grounding(
            topic=assessment_topic,
            blocker={"render_rows": rows},
            language=language,
            level=level,
            track=track,
            budget=budget,
            unit_title=unit_title,
        )

    if grounding_pages:
        R.repair_lesson(content, language=language)
        post_findings = A.audit_lesson(content, language=language, track=track)
        post_blockers = A.blocking(post_findings)
        if post_blockers:
            raise QualityGateError(
                f"{unit_title}: assessment grounding repair introduced deterministic blockers: "
                f"{A.summarise(post_blockers)}"
            )
        render_blockers = _assessment_render_blockers(content)

    # Any OTHER renderer-contract blocker is deterministic but not necessarily
    # an audit.py blocker. Give the remaining set one bounded targeted assessment
    # repair pass while the full unit evidence is still available.
    if render_blockers:
        retry_payload = {
            "language": language, "level": level, "unit": unit_title,
            "regional_variety": (S.profile_for_language(language).variety
                                 if S.profile_for_language(language) else ""),
            "instruction_track": track,
            "assessment_topic_id": str(assessment_topic["id"]),
            # The ten-question semantic review already happened above. This
            # targeted retry may only repair pages the deterministic renderer
            # rejected, so resend only those exact assessment records while
            # retaining the FULL unit evidence needed to verify the taught fact.
            "assessment_records": _records_for_render_blockers(content, render_blockers),
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
        _require_assessment_quality_proof(
            retry, unit_title=unit_title, stage="assessment render-contract repair"
        )
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

    # Attest only the final clean assessment state. Lesson evidence is part of
    # the payload digest, so any lesson edit invalidates the assessment cache.
    final_assessment_payload = {
        "language": language, "level": level, "unit": unit_title,
        "regional_variety": (S.profile_for_language(language).variety
                             if S.profile_for_language(language) else ""),
        "assessment_topic_id": str(assessment_topic["id"]),
        "assessment_records": _review_records(content),
        "unit_evidence": [
            {
                "title": str(topic.get("title") or ""),
                "evidence": _assessment_evidence_digest(topic["content"], track=track),
            }
            for topic in lesson_topics
        ],
        "render_contract_blockers": _assessment_render_blockers(content),
    }
    final_assessment_key = _review_attestation_key(
        kind="assessment_broad", model=REVIEW_MODEL,
        system=_ASSESSMENT_REVIEW_SYSTEM, payload=final_assessment_payload,
        response_schema=_ASSESSMENT_REVIEW_SCHEMA, response_name="assessment_review",
    )
    _review_attestation_store(
        final_assessment_key, stage=f"assessment:{unit_title}"
    )
    _review_response_store(
        assessment_cache_key, data, stage=f"assessment:{unit_title}"
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
                _require_assessment_quality_proof(
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

            # The final proof may still name a repairable blocker. Hand exactly
            # that topic — not the course, not the unit — back to the bounded
            # dispatcher, then prove it again below. Assessments keep their own
            # cardinality-preserving path and are never sent here.
            if not topic.get("is_assessment"):
                applied += converge_topic(
                    topic=topic, language=language, level=level, track=track,
                    budget=budget, unit_title=str(unit.get("title") or ""),
                )

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


def _missing_bilingual_slots(node: Any, *, path: Tuple[Any, ...] = (),
                             page_level: bool = False) -> List[Dict[str, Any]]:
    """Every missing EN/TR counterpart, with the exact path and its source.

    Same traversal and same obligation rule as `_missing_bilingual_pairs`, which
    is derived from this function so the detector and the repairer can never
    disagree about which gaps exist. Each row names the empty counterpart to
    write and the non-empty field it must be the counterpart OF — the repair is
    only ever allowed to touch the former and only ever allowed to read the
    latter as evidence.
    """
    out: List[Dict[str, Any]] = []
    if isinstance(node, dict):
        pairs = list(_BILINGUAL_PAIRS)
        if page_level or "type" in node:
            pairs.append(("text", "text_tr"))
        for left, right in pairs:
            left_present = left in node and bool(str(node.get(left) or "").strip())
            right_present = right in node and bool(str(node.get(right) or "").strip())
            if left_present != right_present:
                absent, source = (right, left) if left_present else (left, right)
                out.append({
                    "path": list(path + (absent,)),
                    "field": absent,
                    "target_locale": "tr" if absent.endswith("_tr") else "en",
                    "source_path": list(path + (source,)),
                    "source_field": source,
                    "source_locale": "tr" if source.endswith("_tr") else "en",
                    "source_value": str(node.get(source) or "").strip(),
                })
        for key, value in node.items():
            if isinstance(value, (dict, list)):
                out.extend(_missing_bilingual_slots(
                    value, path=path + (key,),
                    page_level=(key == "pages"),
                ))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            out.extend(_missing_bilingual_slots(
                value, path=path + (index,), page_level=page_level
            ))
    return out


def _missing_bilingual_pairs(node: Any, *, path: Tuple[Any, ...] = (),
                             page_level: bool = False) -> List[str]:
    """Pairs that would make EN/TR reader modes contain different material.

    Only a present field creates an obligation for its counterpart; genuinely
    optional notes may be absent in both languages. text/text_tr is checked
    only on page objects because dialogue text is the taught-language utterance,
    not English instructional prose.
    """
    return [
        ".".join(map(str, row["path"]))
        for row in _missing_bilingual_slots(node, path=path, page_level=page_level)
    ]


def missing_bilingual_pairs(content: Any) -> List[str]:
    """Public name for the EN/TR completeness proof the publication gate uses.

    The pipeline checkpoints bilingual repairs to the database and must prove,
    at that boundary, that what it is about to write is complete — using this
    exact predicate rather than a second implementation of it.
    """
    return _missing_bilingual_pairs(content)


def _duplicate_mcq_occurrences(units: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Return exact cross-topic MCQ duplicate groups using publication stem normalization."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for unit in units:
        for topic in unit.get("topics") or []:
            content = topic.get("content")
            pages = content.get("pages") if isinstance(content, dict) else None
            for page_index, page in enumerate(pages or []):
                if not isinstance(page, dict) or str(page.get("type") or "").casefold() != "mcq":
                    continue
                stem_key = next(
                    (key for key in ("prompt", "question", "stem")
                     if isinstance(page.get(key), str) and page.get(key).strip()),
                    None,
                )
                if not stem_key:
                    continue
                stem = str(page[stem_key]).strip()
                key = _stem_key(stem)
                if not key:
                    continue
                groups.setdefault(key, []).append({
                    "unit": str(unit.get("title") or ""),
                    "topic": topic,
                    "page_index": page_index,
                    "page": page,
                    "stem_key": stem_key,
                    "stem": stem,
                })
    return [rows for rows in groups.values() if len(rows) > 1]


def repair_duplicate_mcq_stems(*, units: List[Dict[str, Any]], language: str,
                               level: str, track: str, budget: ReviewBudget) -> int:
    """Repair exact cross-topic duplicate stems before final publication proof.

    Broad review is local to one lesson/unit, so two individually valid MCQs can
    still collide globally. Keep the first occurrence stable and repair later
    occurrences one exact stem at a time, then re-run deterministic audit and
    renderer checks. Structural or unresolved duplicates still fail closed.
    """
    profile = S.profile_for_language(language)
    applied = 0

    for _round in range(4):
        duplicates = _duplicate_mcq_occurrences(units)
        if not duplicates:
            return applied

        changed = 0
        for group in duplicates:
            forbidden = [row["stem"] for row in group]
            for row in group[1:]:
                topic = row["topic"]
                page = row["page"]
                page_index = row["page_index"]
                stem_key = row["stem_key"]
                before = str(page[stem_key]).strip()

                context = {}
                for key in (
                    "type", "title", "title_tr", "prompt", "question", "stem",
                    "answer", "options", "choices", "distractors",
                    "why", "why_tr", "target", "term", "word", "example",
                    "translation", "translation_tr",
                ):
                    value = page.get(key)
                    if value not in (None, "", []):
                        context[key] = value

                payload = {
                    "taught_language": language,
                    "level": level,
                    "regional_variety": profile.variety if profile else "",
                    "unit": row["unit"],
                    "topic_title": str(topic.get("title") or ""),
                    "path": ["pages", page_index, stem_key],
                    "field": stem_key,
                    "current_value": before,
                    "forbidden_duplicate_stems": forbidden,
                    "immutable_page_context": context,
                }
                def _duplicate_candidate(call_payload: Dict[str, Any], *,
                                         suffix: str = "") -> str:
                    data = _call_review(
                        model=REPAIR_MODEL,
                        system=_EXACT_DUPLICATE_STEM_REPAIR_SYSTEM,
                        payload=call_payload,
                        max_tokens=700,
                        effort="low",
                        budget=budget,
                        stage=(
                            f"review_duplicate_stem:{topic.get('title')}:"
                            f"pages.{page_index}.{stem_key}{suffix}"
                        ),
                        response_schema=_EXACT_TARGET_REPAIR_SCHEMA,
                        response_name="duplicate_stem_repair",
                    )
                    value = data.get("value")
                    if not isinstance(value, str) or not value.strip():
                        raise QualityGateError(
                            f"{topic.get('title')}: duplicate-stem repair returned empty value"
                        )
                    return value.strip()

                def _prove_duplicate_candidate(replacement: str):
                    if _stem_key(replacement) == _stem_key(before):
                        return None, "no semantic stem change", [], []

                    probe = copy.deepcopy(topic["content"])
                    _set_path(
                        probe,
                        ["pages", page_index, stem_key],
                        replacement,
                        old=before,
                    )
                    R.repair_lesson(probe, language=language)

                    probe_topic = dict(topic)
                    probe_topic["content"] = probe
                    blockers = A.blocking(
                        _audit_topic(probe_topic, language=language, track=track)
                    )
                    if blockers:
                        return None, "deterministic blockers", blockers, []

                    render = _topic_render_blockers(probe)
                    if render:
                        return None, "renderer blockers", [], render

                    # The whole purpose of this repair is uniqueness. Prove the
                    # candidate against every forbidden normalized stem before
                    # canonical mutation; punctuation/cosmetic differences do
                    # not count.
                    replacement_key = _stem_key(replacement)
                    forbidden_keys = {_stem_key(value) for value in forbidden}
                    if replacement_key in forbidden_keys:
                        return None, "still duplicates a forbidden stem", [], []

                    return probe, "", [], []

                replacement = _duplicate_candidate(payload)
                probe, reject_reason, blockers, render = _prove_duplicate_candidate(
                    replacement
                )

                if probe is None:
                    corrective_payload = dict(payload)
                    corrective_payload["rejected_candidate"] = replacement
                    corrective_payload["rejection_reason"] = reject_reason
                    corrective_payload["authoritative_deterministic_blockers"] = [
                        finding.as_dict() for finding in blockers
                    ]
                    corrective_payload["authoritative_renderer_blockers"] = render
                    corrective_payload["instruction"] = (
                        "Your previous stem was rejected by AulaAI's authoritative "
                        "post-candidate proof. Return ONE replacement for the SAME "
                        "stem field that is in the declared taught language, remains "
                        "answerable from the immutable options/context, is genuinely "
                        "distinct from every forbidden duplicate, and introduces no "
                        "deterministic or renderer blocker."
                    )
                    print(
                        f"[QUALITY-PATCH] RETRY duplicate stem "
                        f"{topic.get('title')} pages.{page_index}.{stem_key}: "
                        f"{reject_reason}",
                        flush=True,
                    )
                    replacement = _duplicate_candidate(
                        corrective_payload, suffix=":corrective"
                    )
                    probe, reject_reason, blockers, render = _prove_duplicate_candidate(
                        replacement
                    )

                if probe is None:
                    detail = (
                        f" deterministic={A.summarise(blockers)}"
                        if blockers else ""
                    )
                    if render:
                        detail += (
                            " renderer=" + "; ".join(
                                f"page {x['page_index']} {x['locale']}: {x['why']}"
                                for x in render[:4]
                            )
                        )
                    raise QualityGateError(
                        f"{topic.get('title')}: duplicate-stem repair could not "
                        f"produce a proven candidate after corrective retry: "
                        f"{reject_reason}{detail}"
                    )

                # Commit exactly the snapshot that already passed language,
                # deterministic, renderer and duplicate-uniqueness proof.
                topic["content"].clear()
                topic["content"].update(probe)
                page = topic["content"]["pages"][page_index]

                applied += 1
                changed += 1

        if not changed:
            break

    remaining = _duplicate_mcq_occurrences(units)
    if remaining:
        examples = [
            " <> ".join(
                f"{r['unit']} / {r['topic'].get('title')} / {r['stem']}"
                for r in group[:2]
            )
            for group in remaining[:4]
        ]
        raise QualityGateError(
            "exact duplicate MCQ stems remain after targeted duplicate repair: "
            + " | ".join(examples)
        )
    return applied


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

            # Bind rationale grounding/specificity to the exact final bytes that
            # will be persisted and exported. Reviewer proof fields describe an
            # earlier model response; later deterministic repairs must not be
            # able to reintroduce an invented-person or answer+boilerplate
            # rationale after that proof was issued.
            # The specificity check is a token-overlap PROXY, not a semantic
            # publication invariant. It remains visible to the rationale repair
            # stage, where it is useful as a cheap candidate signal, but it must
            # not have the last word after the language-aware reviewer has
            # already judged the item. This matters especially cross-language:
            # a correct rationale can name the discriminating fact in the
            # instruction language while sharing no token with the taught-
            # language stem. Invented-person/grounding failures remain blocking.
            rationale_blockers = [
                row for row in _explanation_grounding_blockers(content)
                if row.get("why") != _EXPLANATION_SPECIFICITY_REASON
            ]
            if rationale_blockers:
                detail = "; ".join(
                    f"page {row.get('page_index')} {row.get('locale')}: "
                    f"{row.get('why')}"
                    for row in rationale_blockers[:4]
                )
                raise QualityGateError(
                    f"{topic.get('title')}: final rationale integrity failed — {detail}"
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

# The shared predicate must resolve proofs wherever the review layer is loaded,
# so this runs at import rather than from a caller that might not exist.
_install_rationale_proof_lookup()