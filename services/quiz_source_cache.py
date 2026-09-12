import hashlib
import json
import threading
from typing import Dict, Any, Optional, Tuple, List

# Thread-safe in-memory cache keyed by (topic_id, content_hash, material_language)
_CACHE_LOCK = threading.Lock()
_QUIZ_SOURCE_CACHE: Dict[Tuple[str, str, str], Dict[str, Any]] = {}


def _resolve_quiz_structured_payload(
    content_raw: Any,
    topic_id: Optional[str] = None,
    title: str = "",
    topic_type: str = "",
    material_language: str = "en"
) -> Tuple[Dict[str, Any], Dict[str, Any], str, str]:
    """
    Extracts the complete, normalized quiz-relevant structured payload and parsed content_dict.
    Deterministically captures every field consumed by quiz generation:
      - refreshed pages[].items (term, translations, meaning, examples, notes, provenance)
      - refreshed pages[].rules (rule, translations, explanations, examples, source_evidence, provenance)
      - refreshed pages[].comparisons (target, contrasts, notes, source_evidence, provenance)
      - pre-authored MCQs (prompt, answer, distractors, options)
      - reading passages and lexical context (text, text_tr, explanation_tr)
      - page types and titles (type, title, title_tr)
      - topic metadata (topic_id, title, topic_type, material_language)

    If content_raw is raw text or lacks structured pages and topic_id is provided,
    checks SQLite for the persisted structured record so that any database re-enrichment
    or metadata refresh invalidates the cache even if the original raw source text is unchanged.
    """
    content_dict: Dict[str, Any] = {}
    is_raw_text = False
    resolved_title = str(title or "").strip()
    resolved_type = str(topic_type or "").strip()

    if isinstance(content_raw, str):
        s_strip = content_raw.strip()
        if s_strip.startswith("{") and s_strip.endswith("}"):
            try:
                parsed = json.loads(content_raw)
                if isinstance(parsed, dict):
                    content_dict = parsed
                else:
                    is_raw_text = True
            except Exception:
                is_raw_text = True
        else:
            is_raw_text = True
    elif isinstance(content_raw, dict):
        content_dict = content_raw
    else:
        is_raw_text = True

    # If content_dict lacks 'pages' and topic_id is provided, inspect SQLite for persisted structured content
    pages = content_dict.get("pages")
    if (not isinstance(pages, list) or len(pages) == 0) and topic_id:
        try:
            from database import db_connection
            with db_connection() as db:
                row = db.execute("SELECT title, type, content FROM topics WHERE id = ?", (str(topic_id),)).fetchone()
                if row:
                    if not resolved_title and row["title"]:
                        resolved_title = str(row["title"]).strip()
                    if not resolved_type and row["type"]:
                        resolved_type = str(row["type"]).strip()
                    if row["content"]:
                        raw_db = row["content"]
                        if isinstance(raw_db, str) and raw_db.strip().startswith("{"):
                            try:
                                db_dict = json.loads(raw_db)
                                if isinstance(db_dict, dict) and isinstance(db_dict.get("pages"), list):
                                    content_dict = db_dict
                            except Exception:
                                pass
                        elif isinstance(raw_db, dict) and isinstance(raw_db.get("pages"), list):
                            content_dict = raw_db
        except Exception:
            pass

    # Extract canonical structured pages
    raw_pages = content_dict.get("pages", []) if isinstance(content_dict, dict) else []
    structured_pages: List[Dict[str, Any]] = []

    for idx, p in enumerate(raw_pages, 1):
        if not isinstance(p, dict):
            continue

        p_entry: Dict[str, Any] = {
            "type": str(p.get("type") or "content").lower().strip(),
            "title": str(p.get("title") or "").strip(),
            "title_tr": str(p.get("title_tr") or "").strip(),
            "text": str(p.get("text") or "").strip(),
            "text_tr": str(p.get("text_tr") or "").strip(),
            "explanation_tr": str(p.get("explanation_tr") or "").strip(),
        }

        # Pre-authored MCQ
        if p.get("type") == "mcq" or (p.get("prompt") and p.get("answer")):
            p_entry["mcq"] = {
                "prompt": str(p.get("prompt") or "").strip(),
                "answer": str(p.get("answer") or "").strip(),
                "distractors": sorted([str(d).strip() for d in p.get("distractors", []) if str(d).strip()]),
                "options": sorted([str(o).strip() for o in p.get("options", []) if str(o).strip()]),
            }

        # Rules
        rules = p.get("rules", [])
        if isinstance(rules, list):
            rule_entries = []
            for r in rules:
                if isinstance(r, dict):
                    rule_entries.append({
                        "rule": str(r.get("rule") or "").strip(),
                        "rule_tr": str(r.get("rule_tr") or "").strip(),
                        "explanation": str(r.get("explanation") or "").strip(),
                        "explanation_tr": str(r.get("explanation_tr") or "").strip(),
                        "example": str(r.get("example") or "").strip(),
                        "source_evidence": str(r.get("source_evidence") or "").strip(),
                        "source_taught": str(r.get("source_taught") or "").strip(),
                        "provenance": str(r.get("provenance") or "").strip(),
                    })
            p_entry["rules"] = rule_entries

        # Comparisons
        comparisons = p.get("comparisons", [])
        if isinstance(comparisons, list):
            comp_entries = []
            for comp in comparisons:
                if isinstance(comp, dict):
                    comp_entries.append({
                        "target": str(comp.get("target") or "").strip(),
                        "context": str(comp.get("context") or "").strip(),
                        "context_tr": str(comp.get("context_tr") or "").strip(),
                        "note": str(comp.get("note") or "").strip(),
                        "note_tr": str(comp.get("note_tr") or "").strip(),
                        "source_evidence": str(comp.get("source_evidence") or "").strip(),
                        "source_taught": str(comp.get("source_taught") or "").strip(),
                        "provenance": str(comp.get("provenance") or "").strip(),
                    })
            p_entry["comparisons"] = comp_entries

        # Items
        items = p.get("items", [])
        if isinstance(items, list):
            item_entries = []
            for it in items:
                if isinstance(it, dict):
                    item_entries.append({
                        "term": str(it.get("term") or it.get("word") or it.get("rule") or "").strip(),
                        "translation": str(it.get("translation") or "").strip(),
                        "translation_en": str(it.get("translation_en") or "").strip(),
                        "translation_tr": str(it.get("translation_tr") or "").strip(),
                        "meaning": str(it.get("meaning") or "").strip(),
                        "example": str(it.get("example") or it.get("sample") or "").strip(),
                        "explanation": str(it.get("explanation") or "").strip(),
                        "explanation_en": str(it.get("explanation_en") or "").strip(),
                        "explanation_tr": str(it.get("explanation_tr") or "").strip(),
                        "source_evidence": str(it.get("source_evidence") or "").strip(),
                        "provenance": str(it.get("provenance") or "").strip(),
                    })
            p_entry["items"] = item_entries

        structured_pages.append(p_entry)

    # Any other persisted top-level keys
    extra_fields: Dict[str, Any] = {}
    if isinstance(content_dict, dict):
        for k, v in content_dict.items():
            if k != "pages":
                extra_fields[k] = v

    payload: Dict[str, Any] = {
        "topic_id": str(topic_id or "").strip(),
        "title": resolved_title,
        "topic_type": resolved_type,
        "material_language": str(material_language or "en").strip().lower(),
        "structured_pages": structured_pages,
        "extra_fields": extra_fields,
    }
    if is_raw_text and isinstance(content_raw, str):
        payload["raw_source_text"] = content_raw.strip()

    return payload, content_dict, resolved_title, resolved_type


def _hash_payload(payload: Dict[str, Any]) -> str:
    """Computes a deterministic 32-character SHA-256 hash of the complete structured payload."""
    try:
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]
    except Exception:
        return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()[:32]


def get_content_hash(
    content_raw: Any,
    topic_id: Optional[str] = None,
    title: str = "",
    topic_type: str = "",
    material_language: str = "en"
) -> str:
    """
    Computes a deterministic content version hash encompassing every quiz-relevant persisted structured field:
    pages[].items, pages[].rules, pages[].comparisons, source_evidence, provenance, and pre-authored MCQs.
    """
    payload, _, _, _ = _resolve_quiz_structured_payload(
        content_raw=content_raw,
        topic_id=topic_id,
        title=title,
        topic_type=topic_type,
        material_language=material_language
    )
    return _hash_payload(payload)


def invalidate_quiz_source_cache(topic_id: Optional[str] = None):
    """Invalidate cache entries for a specific topic, or clear entire cache if topic_id is None."""
    global _QUIZ_SOURCE_CACHE
    with _CACHE_LOCK:
        if topic_id is None:
            _QUIZ_SOURCE_CACHE.clear()
        else:
            keys_to_delete = [k for k in _QUIZ_SOURCE_CACHE.keys() if k[0] == str(topic_id)]
            for k in keys_to_delete:
                del _QUIZ_SOURCE_CACHE[k]


def get_or_assemble_quiz_source(
    topic_id: str,
    title: str,
    topic_type: str,
    content_raw: Any,
    material_language: str = "en"
) -> Dict[str, Any]:
    """
    Retrieves the preassembled, validated quiz-source context from cache if available.
    Otherwise, parses and preassembles the structured lesson representation once, caches it, and returns it.

    The cache key is bound to a deterministic hash of the complete quiz-relevant structured payload
    (including refreshed pages[].items, pages[].rules, pages[].comparisons, provenance, and pre-authored MCQs).
    A re-enrichment or metadata refresh automatically yields a new hash and invalidates the cached entry
    even when the original raw source text is unchanged.
    """
    tid_str = str(topic_id or "")

    # 1. Resolve structured payload and compute deterministic version hash
    payload, content_dict, res_title, res_type = _resolve_quiz_structured_payload(
        content_raw=content_raw,
        topic_id=topic_id,
        title=title,
        topic_type=topic_type,
        material_language=material_language
    )
    c_hash = _hash_payload(payload)
    cache_key = (tid_str, c_hash, material_language)

    with _CACHE_LOCK:
        if cache_key in _QUIZ_SOURCE_CACHE:
            return _QUIZ_SOURCE_CACHE[cache_key]

    # 2. Cache miss: assemble from resolved structured content
    eff_title = res_title or title
    eff_type = res_type or topic_type or "concept"
    pages = content_dict.get("pages", []) if isinstance(content_dict, dict) else []

    # Check has_explicit_grammar
    has_explicit_grammar = False
    for p in pages:
        if not isinstance(p, dict):
            continue
        if any(isinstance(r, dict) and r.get("source_evidence") for r in p.get("rules", [])):
            has_explicit_grammar = True
            break
        if any(isinstance(c, dict) and c.get("source_evidence") for c in p.get("comparisons", [])):
            has_explicit_grammar = True
            break

    # Assemble single-topic content_str and multi-topic summary
    page_sections = []
    key_terms = []
    key_grammar = []
    key_texts = []
    pre_authored_mcqs = []

    for idx, p in enumerate(pages, 1):
        if not isinstance(p, dict):
            continue

        if p.get("type") == "mcq" and p.get("prompt") and p.get("answer"):
            pre_authored_mcqs.append(p)

        p_title = p.get("title", f"Part {idx}")
        p_type = p.get("type", "content")
        p_lines = [f"[PART {idx}: '{p_title}' (Focus: {p_type})]"]
        
        has_explicit_rules = bool(p.get("rules") or p.get("comparisons"))
        has_items = bool(p.get("items"))

        # Rules
        if p.get("rules") and isinstance(p["rules"], list):
            rule_lines = []
            for r in p["rules"][:5]:
                if isinstance(r, dict):
                    r_name = (r.get("rule_tr") if material_language == "tr" and r.get("rule_tr") else (r.get("rule") or "")).strip()
                    r_expl = (r.get("explanation_tr") if material_language == "tr" and r.get("explanation_tr") else (r.get("explanation") or "")).strip()
                    r_ex = (r.get("example") or "").strip()
                    r_ev = (r.get("source_evidence") or "").strip()
                    if r_name and r_ev:
                        r_disp = f"  * [RULE] {r_name}"
                        if r_expl: r_disp += f": {r_expl[:180]}"
                        if r_ex: r_disp += f" — Example: '{r_ex}'"
                        r_disp += f" [Source: '{r_ev[:100]}']"
                        rule_lines.append(r_disp)

                        # For multi-topic summary
                        disp_multi = f"[RULE] {r_name}"
                        if r_expl: disp_multi += f": {r_expl[:150]}"
                        if r_ex: disp_multi += f" (ex: '{r_ex}')"
                        disp_multi += f" [Source: '{r_ev[:80]}']"
                        if len(key_grammar) < 6: key_grammar.append(disp_multi)
            if rule_lines:
                p_lines.append("Explicit Taught Grammar Rules (Primary Grammar Source):\n" + "\n".join(rule_lines))

        # Comparisons
        if p.get("comparisons") and isinstance(p["comparisons"], list):
            comp_lines = []
            for comp in p["comparisons"][:3]:
                if isinstance(comp, dict):
                    c_tgt = (comp.get("target") or "").strip()
                    c_ctx = (comp.get("context_tr") if material_language == "tr" and comp.get("context_tr") else (comp.get("context") or "")).strip()
                    c_note = (comp.get("note_tr") if material_language == "tr" and comp.get("note_tr") else (comp.get("note") or "")).strip()
                    c_ev = (comp.get("source_evidence") or "").strip()
                    if c_tgt and c_ev:
                        c_disp = f"  * [CONTRAST] '{c_tgt}'" + (f" ({c_ctx})" if c_ctx else "") + (f": {c_note[:140]}" if c_note else "")
                        c_disp += f" [Source: '{c_ev[:100]}']"
                        comp_lines.append(c_disp)

                        # For multi-topic summary
                        disp_multi_c = f"[CONTRAST] {c_tgt}" + (f": {c_note[:120]}" if c_note else "")
                        disp_multi_c += f" [Source: '{c_ev[:80]}']"
                        if len(key_grammar) < 6: key_grammar.append(disp_multi_c)
            if comp_lines:
                p_lines.append("Structural Contrasts & Nuances:\n" + "\n".join(comp_lines))

        # Narrative text (budget-conscious)
        ptext = (p.get("text") or "").strip()
        if ptext:
            txt_limit = 250 if (has_explicit_rules or has_items) else 500
            p_lines.append(f"Passage / Context (Lexical Evidence):\n{ptext[:txt_limit]}")
            if len(key_texts) < 1:
                key_texts.append(ptext[:250])

        # Items
        if p.get("items") and isinstance(p["items"], list):
            item_lines = []
            for it in p["items"][:12]:
                if isinstance(it, dict):
                    term = (it.get("term") or it.get("word") or it.get("rule") or "").strip()
                    tr = (it.get("translation_tr") if material_language == "tr" and it.get("translation_tr") else (it.get("translation_en") or it.get("translation") or it.get("meaning") or "")).strip()
                    ex = (it.get("example") or it.get("sample") or "").strip()
                    expl = (it.get("explanation_tr") if material_language == "tr" and it.get("explanation_tr") else (it.get("explanation_en") or it.get("explanation") or "")).strip()
                    # Source-evidence boundary: only serialize explanation if backed by identifiable original source evidence
                    it_ev = str(it.get("source_evidence") or "").strip()
                    it_prov = str(it.get("provenance") or "").strip().lower()
                    is_source_backed_expl = bool(it_ev or it_prov == "source_explicit")

                    if term:
                        item_display = f"  * {term}" + (f" ({tr})" if tr else "")
                        if ex: item_display += f" — Example: '{ex}'"
                        if is_source_backed_expl and expl: item_display += f" — Note: {expl[:120]}"
                        item_lines.append(item_display)

                        # For multi-topic summary
                        disp_it = f"{term} ({tr})" if tr else term
                        if ex: disp_it += f" [ex: {ex}]"
                        if is_source_backed_expl and expl: disp_it += f" [note: {expl[:100]}]"
                        if len(key_terms) < 8: key_terms.append(disp_it)
            if item_lines:
                p_lines.append("Target Lexicon & Examples (Lexical Evidence):\n" + "\n".join(item_lines))

        if len(p_lines) > 1:
            page_sections.append("\n".join(p_lines))

    parts = [
        "================================================================================",
        "AUTHORITATIVE LESSON SOURCE MATERIAL (PRIMARY EVIDENCE SOURCE OF TRUTH):",
        "================================================================================",
        "The learner has studied the following lesson material. Your questions MUST be strictly",
        "material-dependent: test target vocabulary, grammar patterns, rules, relationships,",
        "and core concepts taught in THIS MATERIAL itself.",
        "Do NOT ask questions that can be answered by generic common sense or world knowledge.",
        "--------------------------------------------------------------------------------"
    ]
    if page_sections:
        parts.extend(page_sections)
        parts.append("================================================================================")
        single_topic_content_str = "\n\n".join(parts)
    elif content_dict:
        single_topic_content_str = json.dumps(content_dict, ensure_ascii=False)[:3500]
    elif isinstance(content_raw, str):
        single_topic_content_str = content_raw[:3500]
    else:
        single_topic_content_str = ""

    multi_topic_summary = {
        "id": tid_str,
        "title": eff_title,
        "type": eff_type,
        "key_vocab": key_terms[:8],
        "key_grammar": key_grammar[:6],
        "key_texts": key_texts[:1]
    }

    assembled = {
        "topic_id": tid_str,
        "content_hash": c_hash,
        "material_language": material_language,
        "has_explicit_grammar": has_explicit_grammar,
        "single_topic_content_str": single_topic_content_str,
        "multi_topic_summary": multi_topic_summary,
        "pre_authored_mcqs": pre_authored_mcqs,
        "parsed_content": content_dict
    }

    with _CACHE_LOCK:
        # Evict any stale versions for this topic_id and material_language
        stale_keys = [k for k in _QUIZ_SOURCE_CACHE.keys() if k[0] == tid_str and k[2] == material_language and k[1] != c_hash]
        for k in stale_keys:
            del _QUIZ_SOURCE_CACHE[k]
        _QUIZ_SOURCE_CACHE[cache_key] = assembled

    return assembled

