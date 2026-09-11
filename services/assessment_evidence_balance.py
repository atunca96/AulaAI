"""Balanced evidence adapter for assessment generation only.

Reads already-generated lesson/topic content and exposes a compact, balanced source
pack to the assessment engine. It never mutates lesson content and never participates
in material generation.
"""

import json

_EVIDENCE_BUDGET = 6800
_BUCKET_LIMITS = {
    "TARGETS": 14,
    "USAGE": 14,
    "RULES": 10,
    "CONTRASTS": 10,
    "DIALOGUE": 12,
    "PITFALLS": 8,
    "CONTEXT": 10,
}
_BUCKET_ORDER = ("RULES", "CONTRASTS", "DIALOGUE", "USAGE", "PITFALLS", "TARGETS", "CONTEXT")


def _clean(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            value = json.dumps(value, ensure_ascii=False)
        except Exception:
            value = str(value)
    return " ".join(str(value).split()).strip()


def _push(buckets, family, value):
    text = _clean(value)
    if not text:
        return
    bucket = buckets[family]
    if text not in bucket and len(bucket) < _BUCKET_LIMITS[family]:
        bucket.append(text)


def _build_balanced_evidence(topic_content):
    if not isinstance(topic_content, dict):
        return ""

    buckets = {name: [] for name in _BUCKET_ORDER}

    for page in topic_content.get("pages") or []:
        if not isinstance(page, dict):
            continue

        page_type = _clean(page.get("type"))
        page_title = _clean(page.get("title"))
        if page_title:
            _push(buckets, "CONTEXT", f"{page_type + ': ' if page_type else ''}{page_title}")
        _push(buckets, "CONTEXT", page.get("context"))
        _push(buckets, "CONTEXT", page.get("text"))
        _push(buckets, "PITFALLS", page.get("pitfall"))

        for item in page.get("items") or []:
            if not isinstance(item, dict):
                continue
            term = item.get("term") or item.get("target") or item.get("word")
            meaning = item.get("translation") or item.get("meaning") or item.get("english")
            explanation = item.get("explanation") or item.get("note")
            example_target = item.get("example") or item.get("sentence") or item.get("text")
            example_support = item.get("example_en") or item.get("sentence_en") or item.get("translation_tr")

            if term or meaning:
                pair = " | ".join(x for x in (_clean(term), _clean(meaning)) if x)
                _push(buckets, "TARGETS", pair)
            if explanation:
                _push(buckets, "USAGE", explanation)
            if example_target or example_support:
                example = " | ".join(x for x in (_clean(example_target), _clean(example_support)) if x)
                _push(buckets, "USAGE", example)

        for rule in page.get("rules") or []:
            if not isinstance(rule, dict):
                _push(buckets, "RULES", rule)
                continue
            parts = (
                rule.get("rule") or rule.get("title"),
                rule.get("explanation"),
                rule.get("example") or rule.get("example_en"),
                rule.get("analysis"),
            )
            _push(buckets, "RULES", " | ".join(_clean(x) for x in parts if _clean(x)))

        for comp in page.get("comparisons") or []:
            if isinstance(comp, dict):
                parts = (comp.get("context"), comp.get("target"), comp.get("translation"), comp.get("note"))
                _push(buckets, "CONTRASTS", " | ".join(_clean(x) for x in parts if _clean(x)))
            else:
                _push(buckets, "CONTRASTS", comp)

        for turn in page.get("dialogue") or []:
            if isinstance(turn, dict):
                speaker = _clean(turn.get("speaker"))
                utterance = _clean(turn.get("text") or turn.get("line"))
                support = _clean(turn.get("line_en") or turn.get("translation"))
                if utterance:
                    line = f"{speaker}: {utterance}" if speaker else utterance
                    if support:
                        line += f" | {support}"
                    _push(buckets, "DIALOGUE", line)
            else:
                _push(buckets, "DIALOGUE", turn)

    # Compatibility with older/non-page content shapes.
    words = topic_content.get("words") or topic_content.get("vocabulary")
    if isinstance(words, dict):
        for term, meaning in words.items():
            _push(buckets, "TARGETS", f"{_clean(term)} | {_clean(meaning)}")
    elif words:
        _push(buckets, "TARGETS", words)

    for value in topic_content.get("grammar_rules") or topic_content.get("rules") or []:
        _push(buckets, "RULES", value)
    for value in topic_content.get("examples") or []:
        _push(buckets, "USAGE", value)
    for value in topic_content.get("dialogue") or topic_content.get("conversations") or []:
        _push(buckets, "DIALOGUE", value)
    _push(buckets, "CONTEXT", topic_content.get("notes"))

    nonempty = [name for name in _BUCKET_ORDER if buckets[name]]
    if not nonempty:
        return ""

    if len(nonempty) >= 3:
        breadth_rule = "Use at least 3 evidence families in a 10-item batch; no single family should dominate the batch."
    elif len(nonempty) == 2:
        breadth_rule = "Use both evidence families across the batch; do not turn every item into the same lookup operation."
    else:
        breadth_rule = "Only one evidence family is available: stay source-faithful, but vary distinct uses/contrasts/forms without inventing outside facts."

    header = (
        "BALANCED ASSESSMENT EVIDENCE — READ ONLY. Every tested claim/answer must be supported here.\n"
        f"AVAILABLE FAMILIES: {', '.join(nonempty)}\n"
        f"COVERAGE RULE: {breadth_rule}\n"
        "IMPORTANT: Different vocabulary/forms inside the same repeated lookup task are not automatically different pedagogical objectives.\n"
    )

    lines = []
    indexes = {name: 0 for name in nonempty}
    while True:
        progressed = False
        for family in _BUCKET_ORDER:
            if family not in indexes:
                continue
            idx = indexes[family]
            if idx >= len(buckets[family]):
                continue
            candidate = f"[{family}] {buckets[family][idx]}"
            indexes[family] += 1
            progressed = True
            prospective = header + "\n".join(lines + [candidate])
            if len(prospective) <= _EVIDENCE_BUDGET:
                lines.append(candidate)
        if not progressed:
            break
        if len(header + "\n".join(lines)) >= _EVIDENCE_BUDGET - 250:
            break

    return header + "\n".join(lines)


def _arg(args, kwargs, name, index, default=None):
    if name in kwargs:
        return kwargs[name]
    if len(args) > index:
        return args[index]
    return default


def install(ai_engine_module):
    if getattr(ai_engine_module, "_assessment_evidence_balance_installed", False):
        return

    original = ai_engine_module.ai_generate_questions

    def evidence_balanced_ai_generate_questions(*args, **kwargs):
        # Never replace an explicit PDF/text source supplied by the caller.
        if _arg(args, kwargs, "source_text_override", 9, None):
            return original(*args, **kwargs)

        topic_content = _arg(args, kwargs, "topic_content", 2, None)
        evidence = _build_balanced_evidence(topic_content)
        if not evidence:
            return original(*args, **kwargs)

        call_args = list(args)
        call_kwargs = dict(kwargs)
        if len(call_args) >= 10:
            call_args[9] = evidence
            call_kwargs.pop("source_text_override", None)
        else:
            call_kwargs["source_text_override"] = evidence
        return original(*call_args, **call_kwargs)

    ai_engine_module.ai_generate_questions = evidence_balanced_ai_generate_questions
    ai_engine_module._assessment_evidence_balance_installed = True
