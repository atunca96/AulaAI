from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")

helper = r'''
def _material_clean_scalar(value):
    """Deterministic last-mile cleanup for generated lesson strings."""
    if not isinstance(value, str):
        return value
    text = value
    text = text.replace("\ufffe", "").replace("\uffff", "").replace("\u200b", "")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"(?i)\bO\s+PHYSIK\b", "", text)
    text = re.sub(r"(?i)\bPHYSIK\b", "", text)
    text = re.sub(r"(?i)\b(?:DEBUG_ARTIFACT|PLACEHOLDER_TEXT|LOREM_IPSUM)\b", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def _material_deterministic_guard(lesson_dict):
    """Apply zero-cost structural QA without inventing linguistic content."""
    if not isinstance(lesson_dict, dict) or not isinstance(lesson_dict.get("pages"), list):
        return lesson_dict

    def clean_deep(obj):
        if isinstance(obj, dict):
            return {k: clean_deep(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean_deep(v) for v in obj]
        if isinstance(obj, str):
            return _material_clean_scalar(obj)
        return obj

    data = clean_deep(lesson_dict)
    clean_pages = []
    seen_mcq_prompts = set()

    for page in data.get("pages", []):
        if not isinstance(page, dict):
            continue

        is_mcq = page.get("type") == "mcq" or bool(page.get("prompt"))
        if is_mcq:
            prompt = str(page.get("prompt") or "").strip()
            answer = str(page.get("answer") or "").strip()
            options = page.get("options") or []
            distractors = page.get("distractors") or []

            if not options and answer and isinstance(distractors, list):
                options = [answer] + list(distractors)

            uniq = []
            seen = set()
            for opt in options if isinstance(options, list) else []:
                txt = str(opt).strip()
                key = unicodedata.normalize("NFKC", txt).casefold()
                if txt and key not in seen:
                    seen.add(key)
                    uniq.append(txt)

            ans_key = unicodedata.normalize("NFKC", answer).casefold()
            if answer and ans_key not in seen:
                uniq.insert(0, answer)

            if not prompt or not answer or len(uniq) != 4:
                continue

            prompt_key = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", prompt).casefold()).strip()
            if prompt_key in seen_mcq_prompts:
                continue
            seen_mcq_prompts.add(prompt_key)

            page["options"] = uniq
            page["distractors"] = [o for o in uniq if unicodedata.normalize("NFKC", o).casefold() != ans_key]
            if len(page["distractors"]) != 3:
                continue

        clean_pages.append(page)

    data["pages"] = clean_pages
    return data


def _apply_material_patch(root, path, value):
    """Safely apply a reviewer patch only to an existing lesson field."""
    if not isinstance(path, str) or not path.startswith("pages."):
        return False
    parts = path.split(".")
    cur = root
    try:
        for part in parts[:-1]:
            if isinstance(cur, list):
                cur = cur[int(part)]
            elif isinstance(cur, dict):
                if part not in cur:
                    return False
                cur = cur[part]
            else:
                return False
        last = parts[-1]
        if isinstance(cur, list):
            idx = int(last)
            if idx < 0 or idx >= len(cur):
                return False
            cur[idx] = value
            return True
        if isinstance(cur, dict) and last in cur:
            if not isinstance(value, (str, int, float, bool, list, dict)) and value is not None:
                return False
            cur[last] = value
            return True
    except (ValueError, IndexError, KeyError, TypeError):
        return False
    return False


def _material_publication_audit(lesson_dict, language, level):
    """Independent, patch-only publication audit. One compact call; no full regeneration."""
    data = _material_deterministic_guard(lesson_dict)
    if not isinstance(data, dict) or not data.get("pages"):
        return data

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if len(payload) > 26000:
        payload = payload[:26000]

    audit_system = f"""You are AulaAI's independent final publication editor for {language} at CEFR {level}.
You are reviewing an ALREADY GENERATED lesson, not creating a new lesson.
Return ONLY a JSON object with this exact shape:
{{"patches":[{{"path":"pages.0.items.1.example","value":"replacement"}}],"remove_pages":[]}}

MISSION: make only high-confidence surgical repairs required for publication quality. Do not rewrite correct content for stylistic preference.

HARD AUDIT GATES:
1. TARGET-LANGUAGE ACCURACY: inspect every target-language example, dialogue, rule example, MCQ stem and option. Reject malformed morphology, wrong particles/cases/prepositions, invalid numeral/classifier/counter syntax, unnatural valency, impossible collocations, wrong agreement, bad conjugation, or invented forms. A vocabulary example must itself be a fully natural sentence or phrase in {language}; never copy English-style noun counting or word order into {language}.
2. NATIVE NATURALNESS: prefer the shortest ordinary native construction appropriate to CEFR {level}. Repair textbook-sounding but non-native combinations only when clearly defective.
3. CEFR SCOPE: at A1/A2 remove or simplify specialist theory, rare exceptions, historical linguistics, dialectology, advanced prosody/pitch-accent theory, and advanced register analysis unless the topic explicitly requires it.
4. BILINGUAL ENTAILMENT: target-language text, English, and Turkish must express the same proposition. Preserve person, number, tense, polarity, quantity, place, and referent. Do not add information absent from the target sentence.
5. ENTITY LOCK: keep each person's/place's identity consistent across script, romanization/localization, dialogue and translation. Normal transliteration differences are allowed (for example Japanese ミラー may correctly correspond to Miller); accidental identity mutation is not.
6. CONTAMINATION: remove editor/model debris, placeholder tokens, foreign garbage, control-character leakage, or unrelated words embedded in translations.
7. MCQ VALIDITY: exactly one answer must be defensible from content explicitly taught BEFORE the question. Required vocabulary and grammar must already be taught. No family-tree logic, arithmetic, outside knowledge, hidden future content, or merely-incidental grammar.
8. MCQ DIVERSITY: within this lesson, do not spend two MCQs on the same learning objective using the same cognitive operation. Keep the stronger item and either surgically retarget the weaker one to another explicitly taught objective or put its page index in remove_pages.
9. DISTRACTORS: all four options must be plausible, same-category, CEFR-appropriate, and pedagogically useful; no random fillers or malformed nonsense unless the lesson explicitly tests that exact learner error.
10. PEDAGOGICAL SEQUENCING: explanation precedes assessment; examples do not secretly require untaught structures; headings accurately describe their content.
11. CONSERVATIVE EDITING: if you cannot prove a change is necessary, do not patch it. Never introduce new facts, rules, vocabulary, or cultural claims.

PATCH RULES:
- Paths must point to EXISTING fields in the supplied JSON.
- Use remove_pages only for an irreparable/duplicate/unsupported page; indices are zero-based.
- Return no commentary, scores, or reasoning."""

    try:
        review = _call_ai(
            [{"role": "system", "content": audit_system},
             {"role": "user", "content": "Audit this lesson and return only necessary patches:\n" + payload}],
            model=MODEL_STRUCTURAL,
            max_tokens=1800,
            temperature=0.05,
            json_mode=True,
            allow_fallback=False,
        )
    except Exception as exc:
        print(f"[MATERIAL-QA] audit skipped after error: {exc}")
        return data

    if not isinstance(review, dict):
        return data

    patches = review.get("patches") or []
    if isinstance(patches, list):
        for patch in patches[:80]:
            if not isinstance(patch, dict):
                continue
            _apply_material_patch(data, patch.get("path", ""), patch.get("value"))

    remove_pages = review.get("remove_pages") or []
    if isinstance(remove_pages, list):
        valid = sorted(
            {i for i in remove_pages if isinstance(i, int) and 0 <= i < len(data.get("pages", []))},
            reverse=True,
        )
        for idx in valid:
            if len(data.get("pages", [])) <= 3:
                break
            data["pages"].pop(idx)

    data = _material_deterministic_guard(data)
    print(f"[MATERIAL-QA] publication audit applied: {len(patches) if isinstance(patches, list) else 0} patches")
    return data
'''

if "def _material_publication_audit(" not in s:
    anchor = "\ndef generate_full_lesson(topic, topic_type, language, count=6, level='A1', source_text=None, material_language=\"tr\"):\n"
    if anchor in s:
        s = s.replace(anchor, "\n" + helper + anchor, 1)
    else:
        print("v27: generate_full_lesson anchor unavailable; QA helper not inserted")

p.write_text(s, encoding="utf-8")
print("Applied v27: independent publication audit + deterministic material guard")
