"""Validated orchestration for Assessment Engine V2.

Planner objectives are validated before writing, and written questions are validated
again before acceptance. This module never calls or mutates lesson/material generation.
"""

import json
from collections import Counter

from services import assessment_engine_v2 as base
from services import assessment_telemetry
from services.assessment_evidence_balance import _build_balanced_evidence
from services.assessment_objective_validator import validate_objectives
from services.assessment_question_validator import validate_questions

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
    try:
        trace = assessment_telemetry._ACTIVE_TRACE.get()
        if trace is not None:
            trace["objective_validation"] = summary
            request_id = trace.get("request_id")
        else:
            request_id = None
        assessment_telemetry._write_metric(
            "ASSESSMENT-OBJECTIVE-VALIDATION", {"request_id": request_id, **summary}
        )
    except Exception:
        pass


def _annotate_question_validation(summary):
    try:
        trace = assessment_telemetry._ACTIVE_TRACE.get()
        if trace is not None:
            trace["question_validation"] = summary
            request_id = trace.get("request_id")
        else:
            request_id = None
        assessment_telemetry._write_metric(
            "ASSESSMENT-QUESTION-VALIDATION", {"request_id": request_id, **summary}
        )
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


def _aggregate_question_reports(reports, requested, accepted, unresolved_count):
    reasons = Counter()
    checked = 0
    rejected = 0
    for report in reports:
        checked += int(report.get("input_count", 0))
        rejected += int(report.get("rejected_count", 0))
        reasons.update(report.get("reason_counts") or {})
    if unresolved_count:
        reasons["writer_unresolved"] += int(unresolved_count)
    return {
        "validator_version": "question_validator_v1",
        "requested_count": int(requested),
        "checked_question_count": int(checked),
        "accepted_question_count": int(accepted),
        "rejected_question_count": int(rejected),
        "writer_unresolved_count": int(unresolved_count),
        "accepted_count_match": int(accepted) == int(requested),
        "reason_counts": dict(sorted(reasons.items())),
    }


def _validate_written(made, objectives, topic_sources, level):
    by_id = {obj["id"]: obj for obj in objectives}
    valid, rejected, report = validate_questions(made, by_id, topic_sources, level)
    rejected_ids = {
        str(item.get("objective_id", "")) for item in rejected if item.get("objective_id")
    }
    return valid, rejected_ids, report


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

    # Initial plan + at most two targeted objective refills.
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

    for index, obj in enumerate(objectives[:requested], start=1):
        obj["id"] = f"o{index}"
    objectives = objectives[:requested]

    objective_summary = _aggregate_reports(
        reports, requested=requested, accepted=len(objectives),
        planner_rounds=planner_rounds, raw_planned=raw_planned,
    )
    _annotate_validation(objective_summary)

    if not objectives:
        return []

    accepted_questions = []
    unresolved_by_id = {}
    question_reports = []

    for start in range(0, len(objectives), base._GEN_CHUNK_SIZE):
        chunk = objectives[start:start + base._GEN_CHUNK_SIZE]
        made, missing_objs = base._generate_for_objectives(
            language, level, chunk, evidence, previous_questions or [], history, accepted_questions
        )
        valid_made, rejected_ids, q_report = _validate_written(
            made, chunk, topic_sources, level
        )
        question_reports.append(q_report)
        accepted_questions.extend(valid_made)

        for obj in missing_objs:
            unresolved_by_id[obj["id"]] = obj
        for obj in chunk:
            if obj["id"] in rejected_ids:
                unresolved_by_id[obj["id"]] = obj

    # One bounded rewrite for objectives whose written question failed semantic/pedagogic
    # validation or could not be produced. If it still fails, router top-up will plan a
    # replacement objective rather than silently returning a bad question.
    first_unresolved = list(unresolved_by_id.values())
    unresolved_by_id = {}
    if first_unresolved:
        made, missing_objs = base._generate_for_objectives(
            language, level, first_unresolved, evidence, previous_questions or [], history, accepted_questions
        )
        valid_made, rejected_ids, q_report = _validate_written(
            made, first_unresolved, topic_sources, level
        )
        question_reports.append(q_report)
        accepted_questions.extend(valid_made)
        for obj in missing_objs:
            unresolved_by_id[obj["id"]] = obj
        for obj in first_unresolved:
            if obj["id"] in rejected_ids:
                unresolved_by_id[obj["id"]] = obj

    # Remember failed objective targets as soft history so the router's missing-count
    # top-up planner prefers a genuinely different objective instead of looping on the
    # same pedagogically bad target.
    failed_objectives = list(unresolved_by_id.values())
    if failed_objectives:
        base._remember(
            h_key,
            [
                {"objective_key": obj.get("key", ""), "prompt": obj.get("target", ""), "answer": ""}
                for obj in failed_objectives
            ],
        )

    order = {obj["id"]: i for i, obj in enumerate(objectives)}
    accepted_questions.sort(key=lambda q: order.get(q.get("objective_id"), 10**9))
    accepted_questions = accepted_questions[:requested]
    base._remember(h_key, accepted_questions)

    question_summary = _aggregate_question_reports(
        question_reports,
        requested=requested,
        accepted=len(accepted_questions),
        unresolved_count=len(failed_objectives),
    )
    _annotate_question_validation(question_summary)

    try:
        line = (
            f"[ASSESSMENT-V2-VALIDATED] requested={requested} objectives={len(objectives)} "
            f"generated={len(accepted_questions)} planner_rounds={planner_rounds} "
            f"objective_rejected={objective_summary['rejected_objective_count']} "
            f"question_rejected={question_summary['rejected_question_count']} "
            f"unresolved={len(failed_objectives)}\n"
        )
        with open("pipeline.log", "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
        print(line.rstrip(), flush=True)
    except Exception:
        pass

    for question in accepted_questions:
        question.pop("objective_id", None)
        question.pop("objective_key", None)
    return accepted_questions


def install(router_module):
    """Replace only the V2 generator reference used by the assessment router."""
    router_module.generate_assessment_questions = generate_assessment_questions
    router_module._assessment_objective_validator_installed = True
    router_module._assessment_question_validator_installed = True
