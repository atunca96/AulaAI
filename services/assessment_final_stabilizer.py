"""Final stabilization for the legacy assessment path only.

This module does not touch lesson/material generation. It sits outside the existing
candidate calibration and adds two assessment-only guarantees:
1) if the calibrated candidate pass is still short, one guided rescue call gets the
   actual rejection classes so it can replace the failed patterns instead of repeating them;
2) final candidate selection prevents non-central pronunciation/orthography objectives
   and canonical objective repeats from taking over a batch.
"""

import json
import re
from collections import Counter
from difflib import SequenceMatcher

_OP_RE = re.compile(r"^\s*\[\[AULAOBJ:([a-z-]+)\]\]\s*", re.I)
_TGT_RE = re.compile(r"^\s*\[\[AULATGT:([^\]]+)\]\]\s*", re.I)
_META_OPS = {"pronunciation", "orthography-form"}


def _arg(guard, args, kwargs, name, index, default=None):
    try:
        return guard._arg(args, kwargs, name, index, default)
    except Exception:
        if name in kwargs:
            return kwargs[name]
        return args[index] if len(args) > index else default


def _set_count(args, kwargs, value):
    call_args = list(args)
    call_kwargs = dict(kwargs)
    if len(call_args) >= 5:
        call_args[4] = value
        call_kwargs.pop("count", None)
    else:
        call_kwargs["count"] = value
    return call_args, call_kwargs


def _source_text(guard, args, kwargs):
    title = str(_arg(guard, args, kwargs, "topic_title", 0, "") or "")
    topic_type = str(_arg(guard, args, kwargs, "topic_type", 1, "") or "")
    content = _arg(guard, args, kwargs, "topic_content", 2, {})
    try:
        body = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        body = str(content or "")
    return f"TOPIC {title} ({topic_type})\n{body}"[:120000]


def _objective_parts(question, guard):
    why = str((question or {}).get("why", "") or "")
    op_match = _OP_RE.match(why)
    op = op_match.group(1).lower() if op_match else str((question or {}).get("_objective_operation", "") or "").lower()
    rest = why[op_match.end():] if op_match else why
    tgt_match = _TGT_RE.match(rest)
    target = tgt_match.group(1) if tgt_match else str((question or {}).get("_objective_target", "") or "")
    return op, guard._norm(target)


def _same_target(guard, left, right):
    if not left or not right:
        return False
    if left == right or SequenceMatcher(None, left, right).ratio() >= 0.90:
        return True
    try:
        return guard._semantic_overlap(left, right) >= 0.62
    except Exception:
        return False


def _meta_central(guard, args, kwargs):
    title = guard._norm(_arg(guard, args, kwargs, "topic_title", 0, ""))
    topic_type = guard._norm(_arg(guard, args, kwargs, "topic_type", 1, ""))
    text = f"{title} {topic_type}"
    markers = (
        "pronunciation", "pronunciacion", "pronunciación", "phonetic", "phonology",
        "orthography", "orthographic", "spelling", "accentuation", "ortografia",
        "ortografía", "acentuacion", "acentuación", "telaffuz", "fonetik", "imla", "yazim", "yazım",
    )
    return any(guard._norm(marker) in text for marker in markers)


def _batch_select(guard, gate, questions, requested, args, kwargs):
    """Prefer distinct canonical targets and cap non-central meta/form objectives."""
    meta_cap = requested if _meta_central(guard, args, kwargs) else (2 if requested >= 8 else 1)
    meta_used = 0
    targets = []
    primary = []

    for q in questions or []:
        if not isinstance(q, dict) or not gate._valid_mcq(q):
            continue
        op, target = _objective_parts(q, guard)
        if target and any(_same_target(guard, target, old) for old in targets):
            continue
        if op in _META_OPS and meta_used >= meta_cap:
            continue
        primary.append(q)
        if target:
            targets.append(target)
        if op in _META_OPS:
            meta_used += 1
        if len(primary) >= requested:
            return primary[:requested]

    # Do not re-open the meta cap just to reach count; a guided rescue is safer.
    return primary[:requested]


def _quality_filter(guard, gate, candidates, source_text, prior, accepted, requested):
    headers = gate._topic_headers(source_text)
    clean = list(accepted or [])
    reasons = Counter()
    operation_counts = Counter(gate._operation_signature(q) for q in clean if isinstance(q, dict))
    for q in candidates or []:
        if not isinstance(q, dict):
            reasons["malformed"] += 1
            continue
        reason = gate._quality_reason(
            q,
            source_text=source_text,
            headers=headers,
            accepted=clean,
            prior=prior,
            operation_counts=operation_counts,
            requested=requested,
        )
        if reason:
            reasons[reason] += 1
            continue
        operation_counts[gate._operation_signature(q)] += 1
        clean.append(q)
    return clean, reasons


def install(ai_engine_module):
    if getattr(ai_engine_module, "_assessment_final_stabilizer_installed", False):
        return

    from services import assessment_guard as guard
    from services import assessment_legacy_filter as gate

    # Preserve the canonical target as well as the operation through the assessment-only
    # content transformation. The final gate strips both markers before public output.
    def keep_objective_metadata(q):
        if not isinstance(q, dict):
            return q
        public = dict(q)
        op = str(q.get("_objective_operation", "") or "").strip().lower()
        target = guard._norm(q.get("_objective_target", ""))
        why = str(public.get("why", "") or "")
        prefix = ""
        if op:
            prefix += f"[[AULAOBJ:{op}]] "
        if target:
            prefix += f"[[AULATGT:{target}]] "
        public["why"] = (prefix + why).strip()
        return public

    guard._public_question = keep_objective_metadata

    previous_strip = gate._strip_internal
    if not getattr(gate, "_assessment_target_marker_strip_installed", False):
        def strip_target_marker(question):
            public = previous_strip(question)
            if isinstance(public, dict):
                public["why"] = _TGT_RE.sub("", str(public.get("why", "") or "")).lstrip()
            return public
        gate._strip_internal = strip_target_marker
        gate._assessment_target_marker_strip_installed = True

    # Record the real deterministic rejection classes while candidate calibration runs.
    # The recorder is inert outside a stabilizer-owned assessment call.
    quality_reason = gate._quality_reason
    if not getattr(gate, "_assessment_rejection_recorder_installed", False):
        def recording_quality_reason(*args, **kwargs):
            reason = quality_reason(*args, **kwargs)
            bucket = getattr(ai_engine_module, "_assessment_rejection_counter", None)
            if reason and isinstance(bucket, Counter):
                bucket[reason] += 1
            return reason
        gate._quality_reason = recording_quality_reason
        gate._assessment_rejection_recorder_installed = True

    # Repair guidance is injected only while the stabilizer owns an assessment rescue.
    governed_call = ai_engine_module._call_ai
    def guided_call(messages, *args, **kwargs):
        guidance = getattr(ai_engine_module, "_assessment_repair_guidance", None)
        if guidance and isinstance(messages, list):
            rewritten = [dict(m) if isinstance(m, dict) else m for m in messages]
            is_assessment = any(
                isinstance(m, dict)
                and m.get("role") == "system"
                and "Pedagogic Assessment Engine" in str(m.get("content", ""))
                for m in rewritten
            )
            if is_assessment:
                for i, m in enumerate(rewritten):
                    if isinstance(m, dict) and m.get("role") == "user" and "TASK: Generate EXACTLY" in str(m.get("content", "")):
                        reason_text = ", ".join(f"{k}={v}" for k, v in sorted((guidance.get("reasons") or {}).items())) or "quality_replacement"
                        targets = "; ".join(guidance.get("targets") or [])[:700]
                        repair_note = (
                            "\n\nREPAIR PASS — REPLACE FAILED PATTERNS, DO NOT PARAPHRASE THEM. "
                            f"Need {guidance.get('missing', 1)} additional distinct high-quality items. "
                            f"Previous rejection classes: {reason_text}. "
                            f"Already accepted canonical targets: {targets or 'see previous questions'}. "
                            "Generate only genuinely different source-backed objectives. Avoid all rejection classes above, "
                            "avoid pronunciation/orthography meta-items unless the topic explicitly teaches them, and do not repeat an accepted objective."
                        )
                        rewritten[i]["content"] = str(m.get("content", "")) + repair_note
                        break
                messages = rewritten
        return governed_call(messages, *args, **kwargs)

    guided_call.__wrapped__ = governed_call
    ai_engine_module._call_ai = guided_call

    calibrated_generate = ai_engine_module.ai_generate_questions
    direct_generate = getattr(calibrated_generate, "__wrapped__", None)
    if not callable(direct_generate):
        direct_generate = calibrated_generate

    def _guided_direct(args, kwargs, requested, prior, selected, reasons, source_text):
        missing = max(1, requested - len(selected))
        rescue_n = min(12, max(6, missing * 3 + 3))
        rescue_args, rescue_kwargs = _set_count(args, kwargs, rescue_n)
        rescue_context = prior + list(selected)
        try:
            rescue_args, rescue_kwargs = guard._with_existing(rescue_args, rescue_kwargs, rescue_context)
        except Exception:
            rescue_kwargs["existing_questions"] = rescue_context

        accepted_targets = []
        for q in selected:
            _, target = _objective_parts(q, guard)
            if target:
                accepted_targets.append(target)

        ai_engine_module._assessment_repair_guidance = {
            "missing": missing,
            "reasons": dict(reasons or {}),
            "targets": accepted_targets,
        }
        try:
            rescue_raw = direct_generate(*rescue_args, **rescue_kwargs) or []
        finally:
            ai_engine_module._assessment_repair_guidance = None

        combined, rescue_reasons = _quality_filter(
            guard, gate, rescue_raw, source_text, rescue_context, selected, requested
        )
        final = _batch_select(guard, gate, combined, requested, args, kwargs)
        return final, rescue_n, len(rescue_raw), rescue_reasons

    def stabilized_generate(*args, **kwargs):
        try:
            requested = max(1, int(_arg(guard, args, kwargs, "count", 4, 10) or 10))
        except Exception:
            requested = 10

        prior = list(_arg(guard, args, kwargs, "existing_questions", 6, []) or [])
        source_text = _source_text(guard, args, kwargs)

        # A small supplementary call from content_engine already has a large prior set.
        # Bypass the calibrated wrapper's own repair so this completion costs one provider
        # call, not another nested two-call chain.
        if requested <= 4 and len(prior) >= 8:
            final, rescue_n, rescue_received, rescue_reasons = _guided_direct(
                args, kwargs, requested, prior, [], {"supplementary_completion": requested}, source_text
            )
            try:
                print(
                    "[ASSESSMENT-FINAL-STABILIZER] supplementary=1 "
                    f"requested={requested} rescue_asked={rescue_n} rescue_received={rescue_received} "
                    f"final={len(final)} rescue_reasons={dict(sorted(rescue_reasons.items()))}",
                    flush=True,
                )
            except Exception:
                pass
            return final[:requested]

        # Normal calibrated path: one writer call plus its single bounded repair at most.
        rejection_counter = Counter()
        ai_engine_module._assessment_rejection_counter = rejection_counter
        try:
            initial = calibrated_generate(*args, **kwargs) or []
        finally:
            ai_engine_module._assessment_rejection_counter = None

        selected = _batch_select(guard, gate, initial, requested, args, kwargs)
        if len(selected) >= requested:
            return selected[:requested]

        # Add batch-level reasons that deterministic per-item filters cannot see.
        if len(selected) < len(initial):
            rejection_counter["batch_objective_or_meta_concentration"] += len(initial) - len(selected)

        final, rescue_n, rescue_received, rescue_reasons = _guided_direct(
            args, kwargs, requested, prior + [q for q in initial if isinstance(q, dict)],
            selected, rejection_counter, source_text
        )

        try:
            print(
                "[ASSESSMENT-FINAL-STABILIZER] "
                f"requested={requested} before={len(selected)} rescue_asked={rescue_n} "
                f"rescue_received={rescue_received} final={len(final)} "
                f"initial_reasons={dict(sorted(rejection_counter.items()))} "
                f"rescue_reasons={dict(sorted(rescue_reasons.items()))}",
                flush=True,
            )
        except Exception:
            pass

        return final[:requested]

    stabilized_generate.__wrapped__ = calibrated_generate
    ai_engine_module.ai_generate_questions = stabilized_generate
    ai_engine_module._assessment_final_stabilizer_installed = True
