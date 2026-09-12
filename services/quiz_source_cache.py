import hashlib
import json
import threading
from typing import Dict, Any, Optional, Tuple, List

# Thread-safe in-memory cache keyed by (topic_id, content_hash, material_language)
_CACHE_LOCK = threading.Lock()
_QUIZ_SOURCE_CACHE: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

def get_content_hash(content_raw: Any) -> str:
    """Computes a deterministic MD5 hash for the given topic content."""
    if isinstance(content_raw, str):
        return hashlib.md5(content_raw.encode("utf-8")).hexdigest()
    elif isinstance(content_raw, (dict, list)):
        try:
            serialized = json.dumps(content_raw, sort_keys=True, ensure_ascii=False)
            return hashlib.md5(serialized.encode("utf-8")).hexdigest()
        except Exception:
            return hashlib.md5(str(content_raw).encode("utf-8")).hexdigest()
    return "empty_content_hash"

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

def get_or_assemble_quiz_source(topic_id: str, title: str, topic_type: str, content_raw: Any, material_language: str = "en") -> Dict[str, Any]:
    """
    Retrieves the preassembled, validated quiz-source context from cache if available.
    Otherwise, parses and preassembles the structured lesson representation once, caches it, and returns it.
    """
    tid_str = str(topic_id or "")
    c_hash = get_content_hash(content_raw)
    cache_key = (tid_str, c_hash, material_language)

    with _CACHE_LOCK:
        if cache_key in _QUIZ_SOURCE_CACHE:
            return _QUIZ_SOURCE_CACHE[cache_key]

    # Cache miss: assemble once
    if isinstance(content_raw, str) and content_raw.strip().startswith("{"):
        try:
            content_dict = json.loads(content_raw)
        except Exception:
            content_dict = {}
    elif isinstance(content_raw, dict):
        content_dict = content_raw
    else:
        content_dict = {}

    pages = content_dict.get("pages", []) if isinstance(content_dict, dict) else []

    # 1. Check has_explicit_grammar
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

    # 2. Assemble single-topic content_str
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
                    if term:
                        item_display = f"  * {term}" + (f" ({tr})" if tr else "")
                        if ex: item_display += f" — Example: '{ex}'"
                        if expl: item_display += f" — Note: {expl[:120]}"
                        item_lines.append(item_display)

                        # For multi-topic summary
                        disp_it = f"{term} ({tr})" if tr else term
                        if ex: disp_it += f" [ex: {ex}]"
                        if expl: disp_it += f" [note: {expl[:100]}]"
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
    else:
        single_topic_content_str = json.dumps(content_dict, ensure_ascii=False)[:3500]

    multi_topic_summary = {
        "id": tid_str,
        "title": title,
        "type": topic_type,
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
        _QUIZ_SOURCE_CACHE[cache_key] = assembled

    return assembled
