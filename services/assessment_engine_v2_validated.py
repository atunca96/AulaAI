"""Validated orchestration for Assessment Engine V2.

This wrapper keeps the existing V2 planner/writer implementation intact, but validates
planner objectives deterministically before any writer call. It never calls or mutates
lesson/material generation.
"""

import json
from collections import Counter

from services import assessment_engine_v2 as base
from services import assessment_telemetry
from services.assessment_evidence_balance import _build_balanced_evidence
from services.assessment_objective_validator import validate_objectives

_MAX_OBJECTIVE_REFILLS = 2
_EVIDENCE_LIMIT = 14000


def _topic_evidence_bundle(topics):
    """Return exactly the evidence visible to planner/writer plus per-topic slices."""
    blocks = []
    topic_sources = {}
    remaining = _EVIDENCE_LIMIT

    for topic in topics:
        content = topic.get("content") or {}
        pack = _build_balanced_evidence(content)
        if not pack:
            try:
                pack = json.dumps(content, ensure_ascii=False)[:5000]
            except Exception:
                pack = str(content)[:5000]
        if not pack or remaining <= 0:
            topic_sources[str(topic.get("id"))] = {
                "title": str(topic.get("title", "")),
                "type": str(topic.get("type", "")),
                "text": "",
            }
            continue

        header = f"=== TOPIC id={topic.get('id')} | title={topic.get('title', '')} | type={topic.get('type', '')} ===\n"
        piece = (header + pack)[:remaining]
        blocks.append(piece)
        topic_sources[str(topic.get("id"))] = {
            "title": str(topic.get("title", "")),
            "type": str(topic.get("type", "")),
            "text": piece,
        }
        remaining -= len(piece)
        if remaining > 2:
            remaining -= 2

    return "\n\n".join(blocks)[:_EVIDENCE_LIMIT], topic_sources


def _history_rows(history, objectives, rejected):
    rows = list(history or [])
    for obj in objectives or []:
        rows.append({"objective_key": obj.get("key", ""), "prompt": obj.get("target", ""), "answer": ""})
    for item in rejected or []:
        obj = item.get("objective") if isinstance(item, dict) else None
        if isinstance(obj, dict):
            rows.append({"objective_key": obj.get("key", ""), "prompt": obj.get("target", ""), "answer": ""})
    return rows[-base._HISTORY_LIMIT:]


def _annotate_validation(summary):
    """Attach non-content validation metrics to the active assessment trace."""
    try:
        trace = assessment_telemetry._ACTIVE_TRACE.get()
        if trace is not None:
            trace["objective_validation"] = summary
            request_id = trace.get("request_id")
        else:
            request_id = None
        payload = {"request_id": request_id, **summary}
        assessment_telemetry._write_metric("ASSESSMENT-OBJECTIVE-VALIDATION", payload)
    except Exception:
        pass


def _aggregate_reports(reports, requested, accepted, planner_rounds, raw_planned):
    reasons = Counter()
    rejected = 0
    for report in reports:
        rejected += int(report.get("rejected_count", 0))
        reasons.update(report.get("reason_counts") or {})
    return {
        "validator_version": "objective_validator_v1",
        "requested_count": int(requested),
        "planner_rounds": int(planner_rounds),
        "raw_planned_count": int(raw_planned),
        "accepted_objective_count": int(accepted),
        "rejected_objective_count": int(rejected),
        "accepted_count_match": int(accepted) == int(requested),
        "reason_counts": dict(sorted(reasons.items())),
    }


def generate_assessment_questions(*, topics, language, level, count, previous_questions=None, material_language="en"):
    try:
        requested = max(1, int(count))
    except Exception:
        requested = 10

    topics = [t for t in (topics or []) if isinstance(t, dict) and t.get("id") is not None]
    if not topics:
        return []

    evidence, topic_sources = _topic_evidence_bundle(topics)
    if not evidence:
        return []

    h_key = base._history_key(language, level, topics)
    history = base._get_history(h_key)
    objectives = []
    rejected_all = []
    reports = []
    raw_planned = 0
    planner_rounds = 0

    # Initial plan + at most two targeted refill plans. Every refill asks only for the
    # missing objective count and is validated against all already accepted objectives.
    while len(objectives) < requested and planner_rounds <= _MAX_OBJECTIVE_REFILLS:
        missing = requested - len(objectives)
        planner_history = _history_rows(history, objectives, rejected_all)
        candidates = base._plan_objectives(
            topics, language, level, missing, evidence, previous_questions or [], planner_history
        )
        planner_rounds += 1
        raw_planned += len(candidates)
        if not candidates:
            break

        valid, rejected, report = validate_objectives(
            candidates, topic_sources, level, accepted=objectives
        )
        reports.append(report)
        rejected_all.extend(rejected)
        for obj in valid:
            if len(objectives) >= requested:
                break
            objectives.append(dict(obj))

    # Re-number only after validation/refills so writer IDs are contiguous and unique.
    for index, obj in enumerate(objectives[:requested], start=1):
        obj["id"] = f"o{index}"
    objectives = objectives[:requested]

    summary = _aggregate_reports(
        reports, requested=requested, accepted=len(objectives),
        planner_rounds=planner_rounds, raw_planned=raw_planned,
    )
    _annotate_validation(summary)

    if not objectives:
        return []

    accepted_questions = []
    unresolved = []
    for start in range(0, len(objectives), base._GEN_CHUNK_SIZE):
        chunk = objectives[start:start + base._GEN_CHUNK_SIZE]
        made, missing_objs = base._generate_for_objectives(
            language, level, chunk, evidence, previous_questions or [], history, accepted_questions
        )
        accepted_questions.extend(made)
        unresolved.extend(missing_objs)

    if unresolved:
        made, _ = base._generate_for_objectives(
            language, level, unresolved, evidence, previous_questions or [], history, accepted_questions
        )
        accepted_questions.extend(made)

    order = {obj["id"]: i for i, obj in enumerate(objectives)}
    accepted_questions.sort(key=lambda q: order.get(q.get("objective_id"), 10**9))
    accepted_questions = accepted_questions[:requested]
    base._remember(h_key, accepted_questions)

    try:
        line = (
            f"[ASSESSMENT-V2-VALIDATED] requested={requested} objectives={len(objectives)} "
            f"generated={len(accepted_questions)} planner_rounds={planner_rounds} "
            f"rejected={summary['rejected_objective_count']}\n"
        )
        with open("pipeline.log", "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
        print(line.rstrip(), flush=True)
    except Exception:
        pass

    # Objective metadata remains internal; topic_id stays for persistence/routing.
    for question in accepted_questions:
        question.pop("objective_id", None)
        question.pop("objective_key", None)
    return accepted_questions


def install(router_module):
    """Replace only the V2 generator reference used by the assessment router."""
    router_module.generate_assessment_questions = generate_assessment_questions
    router_module._assessment_objective_validator_installed = True
