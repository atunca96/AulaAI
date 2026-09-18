"""Publication-grade semantic quality gate for AI-authored classrooms.

Bulk generation stays on Gemini 3.8 Flash. This gate does the expensive thing
only where it has leverage: it reads finished material as an editor, patches
specific fields, then refuses publication unless the deterministic auditor is
clean. Two independent review layers are used:

* GPT-5.6 Luna (high reasoning) reviews every unit's five lessons and its ten
  assessment questions. It is cheap enough to inspect the whole course.
* GPT-5.6 Terra performs one final, compact verification over only the highest
  risk claims: grammar rules, IPA pairs, and MCQs.

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
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from services.authoring import audit as A
from services.authoring import budget as B
from services.authoring import repair as R
from services.authoring import schema as S
from services.authoring import transport as T


LUNA_REVIEW_MODEL = "openai/gpt-5.6-luna-pro"
TERRA_VERIFY_MODEL = "openai/gpt-5.6-terra"
QUALITY_REVIEW_CEILING_USD = 0.13

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
    "items": {"oneOf": [{"type": "string"}, {"type": "integer"}]},
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
_TERRA_VERIFY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "coverage": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "rules": {"type": "integer"},
                "phonetics": {"type": "integer"},
                "assessments": {"type": "integer"},
            },
            "required": ["rules", "phonetics", "assessments"],
        },
        "patches": {"type": "array", "items": _TOP_LEVEL_PATCH_SCHEMA},
    },
    "required": ["coverage", "patches"],
}


class QualityGateError(RuntimeError):
    pass


class ReviewBudget:
    def __init__(self, ceiling: float = QUALITY_REVIEW_CEILING_USD):
        self.ceiling = float(ceiling)
        self.spent = 0.0
        self.calls: List[Dict[str, Any]] = []

    def _estimate(self, model: str, input_chars: int, output_tokens: int) -> float:
        return B.price(
            model,
            input_tokens=max(1, math.ceil(int(input_chars) / 4)),
            output_tokens=max(1, int(output_tokens)),
        )

    def require(self, *, model: str, input_chars: int, output_tokens: int, stage: str) -> None:
        worst = self._estimate(model, input_chars, output_tokens)
        if self.spent + worst > self.ceiling:
            raise QualityGateError(
                f"quality review budget: {stage} could require ${worst:.4f}; "
                f"${self.ceiling - self.spent:.4f} remains of ${self.ceiling:.2f}"
            )

    def record(self, response: T.Response, *, model: str, stage: str) -> float:
        if response.cost is not None:
            cost = float(response.cost)
        else:
            cost = B.price(
                model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cached_tokens=response.cached_tokens,
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


def _get_path(root: Any, path: Sequence[Any]) -> Any:
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


def _apply_patches(topics_by_id: Dict[str, Dict[str, Any]], patches: Sequence[Any]) -> int:
    seen = set()
    applied = 0
    for raw in patches or []:
        if not isinstance(raw, dict):
            raise QualityGateError("semantic patch is not an object")
        topic_id = str(raw.get("topic_id") or "").strip()
        path = raw.get("path")
        if topic_id not in topics_by_id or not isinstance(path, list):
            raise QualityGateError("semantic patch has an unknown topic or missing path")
        marker = (topic_id, json.dumps(path, ensure_ascii=False))
        if marker in seen:
            raise QualityGateError(f"duplicate semantic patch for {topic_id} {path!r}")
        seen.add(marker)
        content = topics_by_id[topic_id]["content"]
        _set_path(content, path, raw.get("value"), old=raw.get("old"))
        applied += 1
    return applied


def _audit_topic(topic: Dict[str, Any], *, language: str, track: str) -> List[A.Finding]:
    content = topic.get("content")
    if not isinstance(content, dict):
        return [A.Finding("not_a_lesson", A.BLOCK)]
    R.repair_lesson(content, language=language)
    return A.audit_lesson(content, language=language, track=track)


def _findings_payload(findings: Iterable[A.Finding]) -> List[Dict[str, str]]:
    return [f.as_dict() for f in findings if f.severity == A.BLOCK]


_LESSON_REVIEW_SYSTEM = """You are AulaAI's independent publication editor.
The course was authored by another model. Your job is to find and correct
learner-visible errors, not to praise or rewrite stylistically.

Review EVERY supplied topic. Be adversarial and conservative. Check:
- factual grammar/lexis/usage claims and overgeneralizations; narrow absolute
  rules when standard counterexamples exist;
- naturalness and correctness of target-language examples/dialogue;
- English and Turkish instructional fields for semantic equivalence and natural
  phrasing;
- every IPA transcription against the exact written term AND the declared
  regional variety; IPA-looking Unicode is not enough;
- internal contradictions, invented forms, impossible examples and CEFR-level
  leakage;
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
- Use only paths that appear in the supplied records.
- Copy old exactly, byte for byte.
- Patch only genuine correctness/naturalness problems. No cosmetic rewrites.
- When one correction has paired EN/TR fields, patch both so they remain
  semantically equivalent.
- Never change structure, add pages, delete content, or change the lesson scope.
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
pages[10]. Use only supplied paths, copy old exactly, and make the smallest
correction that yields one unambiguously correct answer. Keep answer/options/
distractors mutually consistent. No cosmetic rewrites.
"""


_TERRA_VERIFY_SYSTEM = """You are the final fact-checker before a language
textbook is published. Another independent reviewer has already edited it.
Inspect the compact high-risk ledger and look only for defects that still make
publication professionally unacceptable.

You MUST independently verify:
1) every grammar/usage rule for truth, scope, exceptions and regional variety;
2) every IPA pair against the written form and declared variety;
3) every MCQ in BOTH lessons and unit assessments for exactly one correct
   answer, correct key, natural stem and defensible distractors;
4) cross-item consistency: repeated/paraphrased questions about the same taught
   fact must never carry incompatible answers, and answer explanations must agree
   with the evidence;
5) Turkish/English paired rule fields must remain semantically equivalent after
   any repair.

Return JSON only:
{"coverage":{"rules":N,"phonetics":N,"assessments":N},
 "patches":[
   {"topic_id":"EXACT ID","path":[...],"old":"EXACT OLD VALUE",
    "value":"CORRECT REPLACEMENT","reason":"brief factual reason"}
 ]}

Coverage numbers must exactly equal the counts stated in the user message.
Patch only certain errors; do not stylistically rewrite correct material. Use
only paths present in the ledger and copy old exactly. If a rule is too broad,
replace it with an accurate scoped rule. If an MCQ has multiple correct options,
repair the item so exactly one remains correct. If you change an assessment
answer/options/distractors, patch every affected field so the stored key,
options and distractors remain exactly consistent. If you change an English or
Turkish rule/explanation, patch its paired field too so both instructional
tracks continue to teach the same claim.
"""


def _call_review(*, model: str, system: str, payload: Dict[str, Any],
                 max_tokens: int, effort: str, budget: ReviewBudget,
                 stage: str, response_schema: Dict[str, Any],
                 response_name: str) -> Dict[str, Any]:
    user = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    budget.require(model=model, input_chars=len(system) + len(user),
                   output_tokens=max_tokens, stage=stage)
    response = T.call_model(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=max_tokens, temperature=0.0, model=model, cache_system=True,
        timeout=180, attempts=2, reasoning_effort=effort,
        response_schema=response_schema, response_name=response_name,
    )
    budget.record(response, model=model, stage=stage)
    if not response.ok or not isinstance(response.data, dict):
        raise QualityGateError(f"{stage} failed on {model}: {response.error or 'invalid JSON'}")
    return response.data


def review_unit_lessons(*, unit_title: str, topics: List[Dict[str, Any]],
                        language: str, level: str, track: str,
                        budget: ReviewBudget) -> int:
    if not topics:
        return 0
    by_id = {str(t["id"]): t for t in topics}
    payload_topics = []
    for topic in topics:
        findings = _audit_topic(topic, language=language, track=track)
        payload_topics.append({
            "topic_id": str(topic["id"]),
            "title": str(topic.get("title") or ""),
            "records": _review_records(topic["content"]),
            "deterministic_blockers": _findings_payload(findings),
        })
    profile = S.profile_for_language(language)
    payload = {
        "language": language, "level": level, "unit": unit_title,
        "regional_variety": profile.variety if profile else "",
        "instruction_track": track,
        "topics": payload_topics,
    }
    data = _call_review(
        model=LUNA_REVIEW_MODEL, system=_LESSON_REVIEW_SYSTEM, payload=payload,
        max_tokens=4800, effort="high", budget=budget,
        stage=f"luna_lessons:{unit_title}",
        response_schema=_LESSON_REVIEW_SCHEMA, response_name="lesson_review",
    )
    rows = data.get("topics")
    if not isinstance(rows, list):
        raise QualityGateError(f"lesson reviewer returned no topic coverage for {unit_title}")
    returned = [str(r.get("topic_id") or "") for r in rows if isinstance(r, dict)]
    if len(returned) != len(by_id) or set(returned) != set(by_id):
        raise QualityGateError(
            f"lesson reviewer coverage mismatch for {unit_title}: "
            f"got {returned}, expected {list(by_id)}"
        )
    patches: List[Any] = []
    for row in rows:
        if not isinstance(row, dict):
            raise QualityGateError("lesson review row is not an object")
        row_topic_id = str(row.get("topic_id") or "")
        for patch in (row.get("patches") or []):
            if not isinstance(patch, dict):
                raise QualityGateError("lesson semantic patch is not an object")
            patch = dict(patch)
            # The enclosing row already identifies the topic. Accept reviewers
            # that omit the redundant id inside each nested patch, but never
            # accept a contradictory id.
            if patch.get("topic_id") not in (None, "", row_topic_id):
                raise QualityGateError(
                    f"lesson patch topic mismatch: row={row_topic_id}, "
                    f"patch={patch.get('topic_id')}"
                )
            patch["topic_id"] = row_topic_id
            patches.append(patch)
    applied = _apply_patches(by_id, patches)

    # Any deterministic defect the semantic editor did not cure gets one very
    # small targeted pass. This is bounded and fail-closed.
    for topic in topics:
        blockers = A.blocking(_audit_topic(topic, language=language, track=track))
        if not blockers:
            continue
        targeted = {
            "language": language, "level": level, "unit": unit_title,
            "regional_variety": profile.variety if profile else "",
            "instruction_track": track,
            "topics": [{
                "topic_id": str(topic["id"]),
                "title": str(topic.get("title") or ""),
                "records": _review_records(topic["content"]),
                "deterministic_blockers": _findings_payload(blockers),
            }],
            "instruction": "Fix every deterministic blocker. Return this one topic only.",
        }
        retry = _call_review(
            model=LUNA_REVIEW_MODEL, system=_LESSON_REVIEW_SYSTEM, payload=targeted,
            max_tokens=2600, effort="high", budget=budget,
            stage=f"luna_blocker_retry:{topic.get('title')}",
            response_schema=_LESSON_REVIEW_SCHEMA, response_name="lesson_blocker_repair",
        )
        rows2 = retry.get("topics")
        if not isinstance(rows2, list) or len(rows2) != 1 or                 str(rows2[0].get("topic_id") or "") != str(topic["id"]):
            raise QualityGateError(f"blocker retry coverage failed for {topic.get('title')}")
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
            raise QualityGateError(
                f"{topic.get('title')}: deterministic blockers remain after semantic repair: "
                f"{A.summarise(still)}"
            )
    return applied


def review_unit_assessment(*, unit_title: str, assessment_topic: Dict[str, Any],
                           lesson_topics: List[Dict[str, Any]], language: str,
                           level: str, track: str, budget: ReviewBudget) -> int:
    content = assessment_topic.get("content")
    if not isinstance(content, dict):
        raise QualityGateError(f"{unit_title}: assessment has no content")
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
    }
    data = _call_review(
        model=LUNA_REVIEW_MODEL, system=_ASSESSMENT_REVIEW_SYSTEM, payload=payload,
        max_tokens=3400, effort="high", budget=budget,
        stage=f"luna_assessment:{unit_title}",
        response_schema=_ASSESSMENT_REVIEW_SCHEMA, response_name="assessment_review",
    )
    checked = data.get("checked_questions")
    try:
        checked_normalized = sorted({int(v) for v in (checked or [])})
    except (TypeError, ValueError):
        checked_normalized = []
    if checked_normalized != list(range(1, 11)):
        raise QualityGateError(
            f"{unit_title}: assessment reviewer did not explicitly verify all 10 questions"
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
    return applied


def _risk_ledger(units: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    ledger: List[Dict[str, Any]] = []
    counts = {"rules": 0, "phonetics": 0, "assessments": 0}
    for unit in units:
        for topic in unit.get("topics") or []:
            tid = str(topic["id"])
            is_assessment = bool(topic.get("is_assessment"))
            for rec in _review_records(topic["content"]):
                field = str(rec.get("field") or "")
                path = rec.get("path") or []
                include = False
                kind = ""
                if field in _NOTATION_FIELDS:
                    include, kind = True, "phonetic"
                    counts["phonetics"] += 1
                elif field in _RISK_RULE_FIELDS and any(str(p) == "rules" for p in path):
                    include, kind = True, "rule"
                    counts["rules"] += 1
                elif field in _ASSESSMENT_FIELDS:
                    # Final verification covers lesson checks as well as the
                    # synthetic unit assessment. The shipped PDF contained two
                    # paraphrases of the same restaurant question with different
                    # answers; limiting Terra to synthetic assessments made that
                    # contradiction invisible.
                    rec_path = rec.get("path") or []
                    is_mcq = False
                    if len(rec_path) >= 2 and rec_path[0] == "pages" and isinstance(rec_path[1], int):
                        pages = topic.get("content", {}).get("pages") or []
                        page_index = rec_path[1]
                        if 0 <= page_index < len(pages) and isinstance(pages[page_index], dict):
                            is_mcq = str(pages[page_index].get("type") or "").casefold() == "mcq"
                    if is_mcq:
                        include, kind = True, "assessment"
                        # Count once per question, not once per answer/option field.
                        if field in ("prompt", "question", "stem"):
                            counts["assessments"] += 1
                if include:
                    ledger.append({
                        "topic_id": tid, "unit": unit.get("title"), "title": topic.get("title"),
                        "kind": kind, **rec,
                    })
    return ledger, counts


def final_terra_verify(*, units: List[Dict[str, Any]], language: str, level: str,
                       track: str, budget: ReviewBudget) -> int:
    risk, counts = _risk_ledger(units)
    profile = S.profile_for_language(language)
    payload = {
        "language": language, "level": level,
        "regional_variety": profile.variety if profile else "",
        "instruction_track": track,
        "expected_coverage": counts,
        "ledger": risk,
    }
    data = _call_review(
        model=TERRA_VERIFY_MODEL, system=_TERRA_VERIFY_SYSTEM, payload=payload,
        max_tokens=3200, effort="high", budget=budget,
        stage="terra_final_verify",
        response_schema=_TERRA_VERIFY_SCHEMA, response_name="final_verification",
    )
    coverage = data.get("coverage")
    try:
        coverage_normalized = {
            key: int((coverage or {}).get(key)) for key in ("rules", "phonetics", "assessments")
        }
    except (TypeError, ValueError):
        coverage_normalized = {}
    if coverage_normalized != counts:
        raise QualityGateError(
            f"Terra verification coverage mismatch: got {coverage!r}, expected {counts!r}"
        )
    by_id = {
        str(topic["id"]): topic
        for unit in units for topic in (unit.get("topics") or [])
    }
    applied = _apply_patches(by_id, data.get("patches") or [])

    # Nothing reaches the renderer with a known mechanical defect.
    remaining: List[str] = []
    for unit in units:
        for topic in unit.get("topics") or []:
            findings = _audit_topic(topic, language=language, track=track)
            blockers = A.blocking(findings)
            if blockers:
                remaining.append(
                    f"{topic.get('title')}: {A.summarise(blockers)}"
                )
    if remaining:
        raise QualityGateError(
            "final publication audit failed: " + "; ".join(remaining[:8])
        )
    return applied


def provider_preflight() -> List[Dict[str, Any]]:
    """Tiny live contract check for the two publication-review providers.

    This is opt-in at deploy time. It spends only a few hundred output-token
    ceiling per model but exercises the exact structured-output transport that
    a classroom will later use, so a routing/schema incompatibility is found
    before a user pays to regenerate thirty lessons.
    """
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
    }
    rows = []
    for model, effort, name in (
        (LUNA_REVIEW_MODEL, "high", "luna_pro_preflight"),
        (TERRA_VERIFY_MODEL, "low", "terra_preflight"),
    ):
        response = T.call_model(
            [
                {"role": "system", "content": "Return the requested structured health result only."},
                {"role": "user", "content": "Set ok to true."},
            ],
            max_tokens=500, temperature=0.0, model=model, cache_system=False,
            timeout=90, attempts=2, reasoning_effort=effort,
            response_schema=schema, response_name=name,
        )
        if not response.ok or response.data != {"ok": True}:
            raise QualityGateError(
                f"provider preflight failed on {model}: "
                f"{response.error or repr(response.data)}"
            )
        rows.append({
            "model": model, "seconds": response.seconds,
            "cost": float(response.cost or 0.0),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        })
    return rows


def gate_summary(budget: ReviewBudget) -> str:
    calls = ", ".join(
        f"{row['stage']}=${row['cost']:.4f}" for row in budget.calls
    )
    return f"quality_review=${budget.spent:.4f}/{budget.ceiling:.2f}; {calls}"
