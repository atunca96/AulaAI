from pathlib import Path

# 1) Switch authoring model to Terra and price it correctly.
p = Path("services/authoring/budget.py")
s = p.read_text(encoding="utf-8")
s = s.replace('MODEL = "google/gemini-3.8-flash"', 'MODEL = "openai/gpt-5.6-terra"', 1)
anchor = 'RATES: Dict[str, Dict[str, float]] = {\n'
assert anchor in s
s = s.replace(anchor, anchor + '    "openai/gpt-5.6-terra": {"input": 2.00, "output": 12.00, "cache_read": 0.20},\n', 1)
p.write_text(s, encoding="utf-8")

# 2) English-track schema: never collide target-language example with its English gloss.
p = Path("services/authoring/prompts.py")
s = p.read_text(encoding="utf-8")
old = '''    s = _suffix(track)
    inst = _track_name(track)
    return f"""{{'''
new = '''    s = _suffix(track)
    inst_s = "_tr" if str(track or "tr").casefold().startswith("tr") else "_en"
    inst = _track_name(track)
    return f"""{{'''
assert old in s
s = s.replace(old, new, 1)
s = s.replace('"example{s}": "That sentence rendered in {inst}",', '"example{inst_s}": "That sentence rendered in {inst}",', 1)
s = s.replace('"example{s}": "That sentence in {inst}",', '"example{inst_s}": "That sentence in {inst}",', 1)
s = s.replace('"line{s}": "That utterance in {inst}"', '"line{inst_s}": "That utterance in {inst}"', 1)
p.write_text(s, encoding="utf-8")

# 3) Unit assessments keep surviving questions and top up only the shortfall.
p = Path("services/ai_engine.py")
s = p.read_text(encoding="utf-8")
old = '''def generate_unit_assessment(unit_title, unit_topics, language, level="A1",
                             material_language="tr", unit_index=None, unit_total=None,
                             model_override=None, timing_ctx=None, count=10, ledger=None):
    """The assessment that closes a unit, drawn from that unit's lessons only."""
    parts: List[str] = []
    for topic in (unit_topics or []):
        if not isinstance(topic, dict):
            continue
        content = topic.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except Exception:
                content = {}
        block = _material_for_assessment(content)
        if block.strip():
            parts.append(f"=== {topic.get('title', '')} ===\\n{block}")
    if not parts:
        return []
    return ai_generate_questions(
        unit_title, "review", {"_preassembled_content_str": "\n\n".join(parts)[:9000]},
        language, count=count, level=level, material_language=material_language,
        model_override=model_override, timing_ctx=timing_ctx, ledger=ledger)
'''
new = '''def generate_unit_assessment(unit_title, unit_topics, language, level="A1",
                             material_language="tr", unit_index=None, unit_total=None,
                             model_override=None, timing_ctx=None, count=10, ledger=None):
    """Close a unit with exactly count questions, topping up only a shortfall.

    The generic quiz wrapper deliberately returns [] for a short batch. That is
    right for an interactive quiz, but wrong here: it discarded clean surviving
    questions when one harder item was rejected, which is why a whole unit could
    end with no assessment.
    """
    started = time.perf_counter()
    parts: List[str] = []
    for topic in (unit_topics or []):
        if not isinstance(topic, dict):
            continue
        content = topic.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except Exception:
                content = {}
        block = _material_for_assessment(content)
        if block.strip():
            parts.append(f"=== {topic.get('title', '')} ===\n{block}")
    if not parts:
        return []

    source = "\\n\\n".join(parts)[:9000]
    own_ledger = ledger or _budget.BuildLedger(label=f"unit assessment {unit_title}")
    model = model_override or MODEL
    result = _engine.generate_assessment(
        title=str(unit_title), content=source, count=int(count), language=str(language),
        level=str(level or "A1"), track=str(material_language or "tr"),
        ledger=own_ledger, model=model)

    items = list(result.items)
    if len(items) < int(count) and own_ledger.remaining > 0:
        missing = int(count) - len(items)
        topup = _engine.generate_assessment(
            title=str(unit_title), content=source, count=missing, language=str(language),
            level=str(level or "A1"), track=str(material_language or "tr"),
            ledger=own_ledger, model=model,
            already_asked=[str(q.get("prompt") or "") for q in items],
            emphasis="Cover different taught targets from this unit; do not repeat an existing item.",
            temperature=0.65)
        seen = {str(q.get("prompt") or "").strip().casefold() for q in items}
        for item in topup.items:
            key = str(item.get("prompt") or "").strip().casefold()
            if key and key not in seen:
                items.append(item)
                seen.add(key)
            if len(items) >= int(count):
                break

    if isinstance(timing_ctx, dict):
        timing_ctx["total_elapsed"] = time.perf_counter() - started
        timing_ctx["total_cost"] = own_ledger.spent

    if len(items) < int(count):
        _log(f"[UNIT-ASSESS] '{unit_title}' still short: {len(items)}/{count}; not publishing partial assessment")
        return []
    return items[:int(count)]
'''
start = s.index("def generate_unit_assessment(")
end = s.index("\ndef ai_generate_activity_batch", start)
s = s[:start] + new + s[end:]
p.write_text(s, encoding="utf-8")

# 4) Teach the bilingual finisher how to fill either missing instructional track.
p = Path("services/bilingual_finisher.py")
s = p.read_text(encoding="utf-8")
anchor = '\ndef finalize_course_bilingual_data(course_id: str):\n'
assert anchor in s
helpers = r'''
# These are instructional-language mirrors. Target-language strings such as
# term/example/dialogue text/question prompt/options are deliberately absent.
_PAGE_MIRRORS = (
    ("title", "title_tr"), ("text", "text_tr"), ("explanation", "explanation_tr"),
    ("intro", "intro_tr"), ("description", "description_tr"),
    ("instructions", "instructions_tr"), ("analysis", "analysis_tr"),
    ("note", "note_tr"), ("label", "label_tr"), ("hint", "hint_tr"),
)
_NESTED_MIRRORS = {
    "items": (("translation_en", "translation_tr"), ("example_en", "example_tr"),
              ("explanation_en", "explanation_tr")),
    "vocabulary": (("translation_en", "translation_tr"), ("example_en", "example_tr"),
                   ("explanation_en", "explanation_tr")),
    "words": (("translation_en", "translation_tr"), ("example_en", "example_tr"),
              ("explanation_en", "explanation_tr")),
    "rules": (("rule", "rule_tr"), ("explanation", "explanation_tr"),
              ("example_en", "example_tr"), ("analysis", "analysis_tr"),
              ("note", "note_tr")),
    "comparisons": (("context", "context_tr"), ("note", "note_tr"),
                    ("translation_en", "translation_tr")),
    "dialogue": (("line_en", "line_tr"),),
    "conversations": (("line_en", "line_tr"),),
}


def _instructional_pairs(content):
    if not isinstance(content, dict):
        return
    pages = content.get("pages") or []
    if isinstance(pages, dict):
        pages = [pages]
    for page in pages if isinstance(pages, list) else []:
        if not isinstance(page, dict):
            continue
        for pair in _PAGE_MIRRORS:
            yield page, pair[0], pair[1]
        for container_key, pairs in _NESTED_MIRRORS.items():
            nodes = page.get(container_key) or []
            if isinstance(nodes, dict):
                nodes = [nodes]
            if not isinstance(nodes, list):
                continue
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                for en_key, tr_key in pairs:
                    yield node, en_key, tr_key


def _collect_missing_instructional_mirrors(content, to_tr, to_en):
    for node, en_key, tr_key in _instructional_pairs(content):
        en = str(node.get(en_key) or "").strip()
        tr = str(node.get(tr_key) or "").strip()
        if en and (not tr or tr == en):
            to_tr.append(en)
        if tr and (not en or en == tr):
            to_en.append(tr)


def _apply_instructional_mirrors(content, tr_map, en_map):
    for node, en_key, tr_key in _instructional_pairs(content):
        en = str(node.get(en_key) or "").strip()
        tr = str(node.get(tr_key) or "").strip()
        if tr and (not en or en == tr):
            translated = str(en_map.get(tr) or "").strip()
            if translated and translated != tr:
                node[en_key] = translated
                en = translated
        if en and (not tr or tr == en):
            translated = str(tr_map.get(en) or "").strip()
            if translated and translated != en:
                node[tr_key] = translated

        if en_key == "translation_en" and node.get("translation_en") and not node.get("translation"):
            node["translation"] = node["translation_en"]
        if en_key == "explanation_en" and node.get("explanation_en") and not node.get("explanation"):
            node["explanation"] = node["explanation_en"]
'''
s = s.replace(anchor, helpers + anchor, 1)

old = '''        topic_data_list.append((t["id"], t["title"], content))

    UI_LOCALIZABLE_KEYS_V12 = {'''
new = '''        _collect_missing_instructional_mirrors(content, to_translate_to_tr, to_translate_to_en)
        topic_data_list.append((t["id"], t["title"], content))

    UI_LOCALIZABLE_KEYS_V12 = {'''
assert old in s
s = s.replace(old, new, 1)

old = '''            pages = content.get("pages", [])
            for p in pages:
'''
new = '''            _apply_instructional_mirrors(content, trans_map, trans_map_en)
            pages = content.get("pages", [])
            for p in pages:
'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

# 5) Run one bilingual finishing pass after lessons and unit assessments exist.
p = Path("services/legacy/pdf_pipeline.py")
s = p.read_text(encoding="utf-8")
old = '''        _log(f"Phase 2 Complete for {course_id}.")
        if generation_cost is not None:
            try:
                generation_cost.emit_summary()
            except Exception as cost_err:
                _log(f"Cost summary unavailable: {cost_err}")
        _log("Bilingual post-processor disabled: using persisted bilingual lesson fields from the AI engine.")
        with db_connection() as db:
'''
new = '''        try:
            from services.bilingual_finisher import finalize_course_bilingual_data
            finalize_course_bilingual_data(course_id)
            _log("[BILINGUAL] both instructional tracks finalized.")
        except Exception as bilingual_err:
            _log(f"[BILINGUAL] finalizer failed: {bilingual_err}")

        _log(f"Phase 2 Complete for {course_id}.")
        if generation_cost is not None:
            try:
                generation_cost.emit_summary()
            except Exception as cost_err:
                _log(f"Cost summary unavailable: {cost_err}")
        with db_connection() as db:
'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

# 6) Focused regression checks.
test = Path("scripts/test_terra_bilingual_regressions.py")
test.write_text(r'''from services.authoring import budget, prompts

assert budget.MODEL == "openai/gpt-5.6-terra"
assert "openai/gpt-5.6-terra" in budget.RATES

schema_en = prompts.lesson_schema_block("Spanish", "en")
assert '"example": "A natural sentence in Spanish using the term"' in schema_en
assert '"example_en": "That sentence rendered in English"' in schema_en
assert '"line_en": "That utterance in English"' in schema_en

schema_tr = prompts.lesson_schema_block("Spanish", "tr")
assert '"example_tr": "That sentence rendered in Turkish"' in schema_tr
assert '"line_tr": "That utterance in Turkish"' in schema_tr

print("terra/bilingual regression checks passed")
''', encoding="utf-8")
