from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")

# Add residual failure modes to the existing final editor.
anchor = "- Phonetic/transcription claims must distinguish exact facts from learner approximations; do not overstate simplified pronunciation cues as exact phonetics.\n"
extra = """- If a question tests target-language knowledge, the decisive stem/options must contain target-language evidence; do not use material-language-only options as a substitute.
- Reject MCQs solvable mainly by common sense, object-function guessing, family relations, arithmetic, stereotypes, or trivia; knowing the taught target language must be necessary.
- Replace subjective claims that a language/culture is beautiful, logical, melodic, easy, hard, superior, etc. with neutral communicative examples.
- Verify the rule that CAUSES a form, not only the final answer; exceptions and indeclinables must not be justified by superficial spelling.
"""
if "object-function guessing" not in s and anchor in s:
    s = s.replace(anchor, anchor + extra, 1)

helper = r'''
def _material_page_release_audit(data, language, level):
    """Focused per-page audit so long lessons cannot hide residual defects."""
    data = _material_deterministic_guard(data)
    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, list):
        return data
    prior = []
    system = f"""You are AulaAI's final senior proofreader for {language} CEFR {level}. Review ONE page deeply. Return ONLY JSON {{"patches":[{{"path":"pages.0.prompt","value":"replacement"}}],"remove":false}}. Paths must use the ABSOLUTE page index supplied. Fix only real defects. Check: grammar/morphology/case/agreement/valency/collocation/naturalness; explanation cause as well as answer; CEFR fit; exact translation/entity fidelity; neutral non-stereotyped examples; phonetic accuracy vs learner approximation; MCQ grounding only in explicitly taught PRIOR content; no common-sense/object-function/family-tree/trivia solving; target-language evidence in stem/options when testing target-language knowledge; exactly one answer; plausible same-category distractors. If an MCQ cannot be repaired from PRIOR taught content, set remove=true."""
    remove = []
    for i in range(len(pages)):
        page = data["pages"][i]
        digest = "\n".join(prior)[-6500:]
        payload = json.dumps({"absolute_index": i, "prior_taught": digest, "page": page}, ensure_ascii=False, separators=(",", ":"))
        try:
            review = _call_ai([{"role":"system","content":system},{"role":"user","content":payload}], model=MODEL_STRUCTURAL, max_tokens=1400, temperature=0.0, json_mode=True, allow_fallback=False)
        except Exception as exc:
            print(f"[MATERIAL-QA-V30] page {i} skipped: {exc}")
            review = None
        if isinstance(review, dict):
            for patch in (review.get("patches") or [])[:40]:
                if isinstance(patch, dict):
                    path = str(patch.get("path") or "")
                    if path.startswith(f"pages.{i}."):
                        _apply_material_patch(data, path, patch.get("value"))
            if review.get("remove") is True and isinstance(page, dict) and page.get("type") == "mcq":
                remove.append(i)
        if isinstance(page, dict):
            title = str(page.get("title") or page.get("title_tr") or "")
            ptype = str(page.get("type") or "")
            taught = [f"P{i} {ptype} {title}"]
            if ptype == "vocabulary":
                for item in (page.get("items") or [])[:20]:
                    if isinstance(item, dict):
                        taught.append(str(item.get("term") or item.get("word") or "") + "=" + str(item.get("meaning") or item.get("translation") or item.get("translation_tr") or ""))
            for key in ("text","text_tr","rule","explanation"):
                if isinstance(page.get(key), str):
                    taught.append(page[key][:500])
            prior.append(" | ".join(taught))
    for i in reversed(remove):
        if len(data.get("pages", [])) > 3:
            data["pages"].pop(i)
    return _material_deterministic_guard(data)
'''

if "def _material_page_release_audit(" not in s:
    a = "\ndef generate_full_lesson(topic, topic_type, language, count=6, level='A1', source_text=None, material_language=\"tr\"):\n"
    if a not in s:
        raise RuntimeError("v30 lesson anchor missing")
    s = s.replace(a, "\n" + helper + a, 1)

whole = "    lesson_dict = _material_publication_audit(lesson_dict, language, level)\n"
page = "    lesson_dict = _material_page_release_audit(lesson_dict, language, level)\n"
if page not in s:
    if whole + whole in s:
        s = s.replace(whole + whole, whole + page + whole, 1)
    elif whole in s:
        s = s.replace(whole, whole + page, 1)
    else:
        raise RuntimeError("v30 audit call missing")

if "object-function guessing" not in s or page not in s:
    raise RuntimeError("v30 verification failed")

p.write_text(s, encoding="utf-8")
print("Applied v30: focused per-page final audit")
