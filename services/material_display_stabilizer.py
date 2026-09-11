"""Final display-state stabilization for generated lessons.

Runs after the normal bilingual finisher. It does not invent new lesson structure;
it normalizes only visible bilingual display fields so first render and language
toggles use the same persisted data.
"""

import json
import re


_NON_LATIN = re.compile(r"[\u0400-\u052F\u0600-\u06FF\u3040-\u30FF\u3400-\u9FFF]")
_ENGLISH_WORDS = re.compile(
    r"\b(the|a|an|is|are|and|or|in|on|for|with|of|to|from|word|letter|sound|"
    r"vowel|consonant|stress|stressed|pronounced|first|final|always|used|means|"
    r"home|house|build|homeless|plural|singular|correct|option|read|soft|hard)\b",
    re.I,
)
_TURKISH_WORDS = re.compile(
    r"[çğıöşüÇĞİÖŞÜ]|\b(bir|bu|şu|ve|ile|için|nasıl|nedir|hangisi|kelime|harf|"
    r"ses|ünlü|ünsüz|vurgu|vurgulu|okunur|telaffuz|doğru|seçenek|ilk|son|"
    r"yumuşak|sert|çoğul|tekil|evde|evler)\b",
    re.I,
)
_FORBIDDEN_ENGLISH_ANCHORS = re.compile(
    r"\b(Turkish|Scottish|German|French|Spanish|Italian|Portuguese|Arabic|Japanese|"
    r"Chinese|Korean|Greek|Polish|Dutch|Swedish|Norwegian|Danish|Finnish|Czech|"
    r"Hungarian|Romanian)\b",
    re.I,
)


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _looks_english(value):
    text = str(value or "").strip()
    if not text:
        return False
    latin = _NON_LATIN.sub(" ", text)
    return bool(_ENGLISH_WORDS.search(latin))


def _looks_turkish(value):
    text = str(value or "").strip()
    return bool(text and _TURKISH_WORDS.search(text) and not _looks_english(text))


def _is_letter_like(value):
    text = str(value or "").strip()
    if not text:
        return False
    clean = re.sub(r"[\s,;/|()\-–—]+", "", text)
    return 1 <= len(clean) <= 4 and any(ch.isalpha() for ch in clean)


def _unwrap(result):
    if not isinstance(result, dict):
        return {}
    for key in ("items", "data", "translations"):
        if isinstance(result.get(key), dict):
            return result[key]
    return result


def _split_option(value):
    text = str(value or "").strip()
    if not text:
        return "", ""
    match = re.match(r"^(\[[^\]]+\]|«[^»]+»|“[^”]+”|'[^']+'|\"[^\"]+\")\s*\((.+)\)$", text)
    if match:
        return match.group(1), match.group(2).strip()
    return "", text


def _call_letter_editor(ai_engine, records, course_language):
    if not records:
        return {}
    output = {}
    for start in range(0, len(records), 20):
        chunk = records[start:start + 20]
        payload = {
            str(i): {
                "term": record[1],
                "existing_en": record[2],
                "existing_tr": record[3],
                "example": record[4],
            }
            for i, record in enumerate(chunk)
        }
        prompt = f"""You are the final pronunciation editor for an adult beginner {course_language} course.
For each alphabet/letter item, return concise bilingual teaching notes.

Return exactly:
{{"0":{{"en":"...","tr":"...","keep_tr":true}}, ...}}

STRICT ENGLISH STYLE:
- Explain the pronunciation directly and simply, usually in ONE short sentence, maximum about 18 words.
- Prefer plain learner-friendly wording such as hard/soft, tongue, lips, throat, stress, voiced/unvoiced.
- Avoid specialist jargon such as velarized, alveolo-palatal, postalveolar, approximant, affricate unless absolutely necessary.
- NEVER use another language as a pronunciation comparison or anchor. No Turkish, Scottish, German, French, Spanish, etc. comparisons.
- Do not say "like German Bach", "like Scottish loch", "like the Turkish s", etc.
- IPA may be kept when it genuinely clarifies the sound, but the prose must still be simple.

TURKISH STYLE:
- Teach the same pronunciation fact in concise, natural Turkish.
- Turkish-specific sound comparisons ARE allowed when genuinely helpful.
- If existing_tr is already accurate and useful, preserve it as closely as possible and set keep_tr=true.
- Correct it only if it is missing, English, or factually wrong.

GENERAL:
- The EN and TR notes must agree on the linguistic fact but do not need to be literal translations.
- Preserve the exact target-language letter and relevant IPA.
- Do not add unrelated facts.

INPUT ({course_language}):
{json.dumps(payload, ensure_ascii=False)}"""
        result = ai_engine._call_ai(
            [{"role": "user", "content": prompt}],
            model=ai_engine.MODEL_TRANSLATOR,
            max_tokens=3600,
            temperature=0.05,
            json_mode=True,
        )
        mapping = _unwrap(result)
        for i, record in enumerate(chunk):
            token, _, old_en, old_tr, _ = record
            raw = mapping.get(str(i)) if isinstance(mapping, dict) else None
            if not isinstance(raw, dict):
                output[token] = {"en": old_en, "tr": old_tr}
                continue
            en = str(raw.get("en") or old_en or "").strip()
            tr = str(raw.get("tr") or old_tr or "").strip()
            keep_tr = raw.get("keep_tr") is True
            if old_tr and _looks_turkish(old_tr) and keep_tr:
                tr = str(old_tr).strip()
            # Fail safe: never accept an unrelated-language anchor in EN.
            if _FORBIDDEN_ENGLISH_ANCHORS.search(en):
                en = str(old_en or "").strip()
            output[token] = {"en": en, "tr": tr}
    return output


def _call_mcq_localizer(ai_engine, records, course_language):
    if not records:
        return {}
    output = {}
    for start in range(0, len(records), 14):
        chunk = records[start:start + 14]
        payload = {
            str(i): {
                "prompt": record[1],
                "options": record[2],
            }
            for i, record in enumerate(chunk)
        }
        prompt = f"""Localize embedded lesson-end multiple-choice questions for a {course_language} course into BOTH English and Turkish UI views.

Return exactly:
{{"0":{{"prompt_en":"...","prompt_tr":"...","options_en":[...],"options_tr":[...]}}, ...}}

Rules:
- prompt_en must be natural English instructional prose. prompt_tr must be natural Turkish instructional prose.
- Translate the full instructional sentence even when it contains {course_language} words.
- Preserve only the actual tested {course_language} forms, quoted words, letters, stress marks and IPA exactly.
- If an option is purely a {course_language} answer/form, keep that option identical in EN and TR.
- If an option contains an English/Turkish explanatory gloss, localize only the gloss and preserve the tested form/IPA.
- Keep the same option count and exact option order.
- Do not change which option is correct and do not add facts.
- Never leave an entire Russian/{course_language} question sentence in prompt_en merely because it contains target-language text.

INPUT:
{json.dumps(payload, ensure_ascii=False)}"""
        result = ai_engine._call_ai(
            [{"role": "user", "content": prompt}],
            model=ai_engine.MODEL_TRANSLATOR,
            max_tokens=4200,
            temperature=0.05,
            json_mode=True,
        )
        mapping = _unwrap(result)
        for i, record in enumerate(chunk):
            token, source_prompt, source_options = record
            raw = mapping.get(str(i)) if isinstance(mapping, dict) else None
            if not isinstance(raw, dict):
                continue
            en_opts = raw.get("options_en")
            tr_opts = raw.get("options_tr")
            if not isinstance(en_opts, list) or not isinstance(tr_opts, list):
                continue
            if len(en_opts) != len(source_options) or len(tr_opts) != len(source_options):
                continue
            output[token] = {
                "prompt_en": str(raw.get("prompt_en") or "").strip(),
                "prompt_tr": str(raw.get("prompt_tr") or "").strip(),
                "options_en": [str(x).strip() for x in en_opts],
                "options_tr": [str(x).strip() for x in tr_opts],
            }
    return output


def stabilize_course(course_id, ai_engine):
    from database import db_connection

    with db_connection() as db:
        course = db.execute("SELECT language FROM courses WHERE id = ?", (course_id,)).fetchone()
        course_language = (course["language"] if course else None) or "target language"
        rows = db.execute(
            """
            SELECT t.id, t.content
            FROM topics t
            JOIN chapters ch ON t.chapter_id = ch.id
            WHERE ch.course_id = ?
            ORDER BY ch.number, t.sort_order
            """,
            (course_id,),
        ).fetchall()

    topics = []
    letter_records = []
    letter_targets = {}
    mcq_records = []
    mcq_targets = {}

    for row in rows:
        try:
            topic_id, raw_content = row["id"], row["content"]
        except Exception:
            topic_id, raw_content = row[0], row[1]
        try:
            content = json.loads(raw_content or "{}") if isinstance(raw_content, str) else (raw_content or {})
        except Exception:
            continue
        if not isinstance(content, dict):
            continue

        for page_index, page in enumerate(content.get("pages", []) or []):
            if not isinstance(page, dict):
                continue

            for item_index, item in enumerate(page.get("items", []) or []):
                if not isinstance(item, dict):
                    continue
                term = item.get("term") or item.get("word") or item.get("letter") or item.get("character") or ""
                if not _is_letter_like(term):
                    continue
                old_en = item.get("explanation_en") or item.get("english_explanation") or item.get("explanation") or ""
                old_tr = item.get("explanation_tr") or item.get("turkish_explanation") or ""
                example = item.get("example") or ""
                token = f"{topic_id}:p{page_index}:i{item_index}"
                letter_records.append((token, str(term), str(old_en), str(old_tr), str(example)))
                letter_targets[token] = item

            if page.get("type") == "mcq" or page.get("prompt") or page.get("question"):
                source_prompt = str(page.get("prompt") or page.get("question") or "").strip()
                source_options = page.get("options") if isinstance(page.get("options"), list) else []
                if not source_options:
                    source_options = ([page.get("answer")] if page.get("answer") else []) + list(page.get("distractors") or [])
                source_options = [str(x).strip() for x in source_options if str(x).strip()]
                if source_prompt and source_options:
                    token = f"{topic_id}:p{page_index}:mcq"
                    mcq_records.append((token, source_prompt, source_options))
                    mcq_targets[token] = page

        topics.append((topic_id, content))

    letter_map = _call_letter_editor(ai_engine, letter_records, course_language)
    for token, pair in letter_map.items():
        item = letter_targets.get(token)
        if not item:
            continue
        en = str(pair.get("en") or "").strip()
        tr = str(pair.get("tr") or "").strip()
        if en:
            # One persisted EN source of truth. The generic field is intentionally kept
            # identical so first paint and later language toggles cannot diverge.
            item["explanation"] = en
            item["explanation_en"] = en
            item["english_explanation"] = en
        if tr:
            item["explanation_tr"] = tr
            item["turkish_explanation"] = tr

    mcq_map = _call_mcq_localizer(ai_engine, mcq_records, course_language)
    for token, localized in mcq_map.items():
        page = mcq_targets.get(token)
        if not page:
            continue
        original_options = page.get("options") if isinstance(page.get("options"), list) else []
        if not original_options:
            original_options = ([page.get("answer")] if page.get("answer") else []) + list(page.get("distractors") or [])
        original_options = [str(x).strip() for x in original_options if str(x).strip()]

        en_opts = localized["options_en"]
        tr_opts = localized["options_tr"]
        page["prompt_en"] = localized["prompt_en"]
        page["prompt_tr"] = localized["prompt_tr"]
        page["options_en"] = en_opts
        page["options_tr"] = tr_opts

        raw_answer = str(page.get("answer") or "").strip()
        try:
            answer_index = original_options.index(raw_answer)
        except ValueError:
            answer_index = -1
        if 0 <= answer_index < len(en_opts):
            page["answer_en"] = en_opts[answer_index]
            page["answer_tr"] = tr_opts[answer_index]
            page["distractors_en"] = [value for i, value in enumerate(en_opts) if i != answer_index]
            page["distractors_tr"] = [value for i, value in enumerate(tr_opts) if i != answer_index]

    with db_connection() as db:
        for topic_id, content in topics:
            db.execute("UPDATE topics SET content = ? WHERE id = ?", (json.dumps(content, ensure_ascii=False), topic_id))
        db.commit()

    print(
        f"[MATERIAL-STABLE] Course {course_id}: stabilized {len(letter_records)} pronunciation cards and {len(mcq_records)} embedded MCQs.",
        flush=True,
    )


def install(bilingual_finisher, ai_engine):
    if getattr(bilingual_finisher, "_aula_material_display_stabilizer_installed", False):
        return
    raw_finalize = bilingual_finisher.finalize_course_bilingual_data

    def wrapped_finalize(course_id):
        result = raw_finalize(course_id)
        stabilize_course(course_id, ai_engine)
        return result

    bilingual_finisher.finalize_course_bilingual_data = wrapped_finalize
    bilingual_finisher._aula_material_display_stabilizer_installed = True
