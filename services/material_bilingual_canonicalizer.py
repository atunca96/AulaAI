"""Course-level bilingual canonicalization for generated lesson material.

Runs after the existing bilingual finisher. EN and TR are treated as two native
pedagogical views of the same linguistic fact — never as forced word-for-word
translations. Existing good Turkish explanations are preserved whenever the
linguistic editor judges them accurate.
"""

import json
import re


_ENGLISH_MARKERS = re.compile(
    r"\b(the|a|an|is|are|was|were|and|or|in|on|at|for|with|of|to|from|"
    r"word|letter|sound|vowel|consonant|stress|stressed|pronounced|"
    r"pronunciation|first|final|always|used|means|correct|option|choose|"
    r"read|written|syllable|reduce|reduced|home|house|build|homeless)\b",
    re.I,
)
_TURKISH_MARKERS = re.compile(
    r"[çğıöşüÇĞİÖŞÜ]|\b(bir|bu|şu|ve|ile|için|nasıl|nedir|hangisi|"
    r"kelime|harf|ses|sesli|sessiz|vurgu|vurgulu|okunur|telaffuz|"
    r"doğru|seçenek|ilk|son|daima|kullanılır|göre|olarak|evde|evler|"
    r"hece|ünlü|ünsüz|yumuşak|sert|ince|kalın|söylenir|duyulur)\b",
    re.I,
)
_NON_LATIN = re.compile(r"[\u0400-\u052F\u0600-\u06FF\u3040-\u30FF\u3400-\u9FFF]")


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _looks_english(value):
    text = str(value or "").strip()
    if not text or _NON_LATIN.search(text):
        return False
    return len(_ENGLISH_MARKERS.findall(text)) >= 1


def _looks_turkish(value):
    text = str(value or "").strip()
    return bool(text and _TURKISH_MARKERS.search(text) and not _looks_english(text))


def _letter_like(value):
    text = str(value or "").strip()
    if not text:
        return False
    clean = re.sub(r"[\s,;/|()\-–—]+", "", text)
    return 1 <= len(clean) <= 4 and any(ch.isalpha() for ch in clean)


def _scrub_cross_language_reference(value):
    text = str(value or "").strip()
    if not text:
        return text
    text = re.sub(
        r"\b(?:the\s+)?Turkish\s+['\"“”‘’]([^'\"“”‘’]+)['\"“”‘’](?:\s+sound)?",
        r"the '\1' sound",
        text,
        flags=re.I,
    )
    text = re.sub(r"\bTurkish\s+([A-Za-z])\s+sound\b", r"the '\1' sound", text, flags=re.I)
    text = re.sub(r"\b(?:as|like|just like)\s+in\s+Turkish\b", "in standard pronunciation", text, flags=re.I)
    text = re.sub(r"\bin\s+Turkish\b", "in standard pronunciation", text, flags=re.I)
    text = re.sub(r"\bTurkish\s+(?:speakers|learners)\b", "learners", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _unwrap_mapping(result):
    if not isinstance(result, dict):
        return {}
    for key in ("items", "translations", "data"):
        if isinstance(result.get(key), dict):
            return result[key]
    return result


def _call_native_explanation_pairs(ai_engine, entries, course_language):
    """Return fact-aligned native EN/TR explanations.

    The model receives both existing language views as evidence. It may correct a
    factual mismatch, but it is instructed to preserve a good existing Turkish
    pedagogical explanation rather than flatten it into a literal English translation.
    """
    if not entries:
        return {}

    out = {}
    chunk_size = 18
    for start in range(0, len(entries), chunk_size):
        chunk = entries[start:start + chunk_size]
        payload = {}
        for idx, entry in enumerate(chunk):
            payload[str(idx)] = {
                "kind": entry[1],
                "term": entry[2],
                "existing_en": entry[3],
                "existing_tr": entry[4],
                "example": entry[5],
            }

        prompt = f"""You are the final bilingual linguistic editor for a {course_language} course.
For each JSON item, establish ONE correct linguistic fact and express it independently in natural English and natural Turkish.

Return each key as:
{{"en":"...","tr":"...","existing_tr_accurate":true}}

Rules:
- EN and TR must teach the SAME factual rule, but they MUST NOT be forced literal translations.
- English must be natural for an English-interface learner. NEVER refer to Turkish, Turkish speakers, the learner's native language, or use Turkish words as phonetic anchors.
- Turkish must be natural and pedagogically useful for a Turkish-speaking learner. It MAY use Turkish-specific sound comparisons when they genuinely help.
- If existing_tr is already accurate, natural Turkish, keep its useful pedagogical wording as much as possible and set existing_tr_accurate=true.
- If existing_tr is missing, English, misleading, or factually inconsistent, write a corrected native Turkish explanation and set existing_tr_accurate=false.
- For kind=alphabet, explain the exact character in standard {course_language}; correct generic/wrong legacy explanations using standard linguistic facts.
- For kind=comparison, preserve the actual spelling/reading contrast and meaning.
- Preserve relevant {course_language} letters, words, stress marks and IPA.
- Do not add unrelated facts.
Return ONLY the JSON object with the exact input keys.

INPUT:
{json.dumps(payload, ensure_ascii=False)}"""

        result = ai_engine._call_ai(
            [{"role": "user", "content": prompt}],
            model=ai_engine.MODEL_TRANSLATOR,
            max_tokens=4200,
            temperature=0.05,
            json_mode=True,
        )
        mapping = _unwrap_mapping(result)

        for local_idx, entry in enumerate(chunk):
            token, _, _, old_en, old_tr, _ = entry
            raw = mapping.get(str(local_idx)) if isinstance(mapping, dict) else None
            if isinstance(raw, dict):
                en_value = _scrub_cross_language_reference(raw.get("en") or old_en)
                proposed_tr = str(raw.get("tr") or old_tr or "").strip()
                tr_ok = raw.get("existing_tr_accurate") is True
            else:
                en_value = _scrub_cross_language_reference(old_en)
                proposed_tr = str(old_tr or "").strip()
                tr_ok = bool(old_tr and _looks_turkish(old_tr))

            # Preserve good native Turkish pedagogy. Replace only missing/contaminated
            # Turkish, or when the linguistic editor explicitly found it inaccurate.
            existing_good_tr = bool(old_tr and _looks_turkish(old_tr))
            tr_value = str(old_tr).strip() if (existing_good_tr and tr_ok) else proposed_tr
            out[token] = {"en": en_value, "tr": tr_value}

    return out


def _translate_to_english(ai_engine, strings, course_language):
    """Explicit-direction translation for UI prose; bypasses mixed legacy caches."""
    values = list(dict.fromkeys(str(x).strip() for x in strings if str(x).strip()))
    if not values:
        return {}
    output = {}
    for start in range(0, len(values), 24):
        chunk = values[start:start + 24]
        payload = {str(i): value for i, value in enumerate(chunk)}
        prompt = f"""Translate each educational UI string into natural, concise English for a {course_language} course.
Preserve {course_language} words, letters, stress marks, quoted target forms and IPA exactly. Translate only explanatory/instructional prose. Never refer to Turkish or another learner L1. Do not add facts. Return ONLY a JSON object with the exact keys.
{json.dumps(payload, ensure_ascii=False)}"""
        result = ai_engine._call_ai(
            [{"role": "user", "content": prompt}],
            model=ai_engine.MODEL_TRANSLATOR,
            max_tokens=3000,
            temperature=0.05,
            json_mode=True,
        )
        mapping = _unwrap_mapping(result)
        for i, source in enumerate(chunk):
            translated = mapping.get(str(i)) if isinstance(mapping, dict) else None
            if isinstance(translated, str) and translated.strip():
                output[source] = _scrub_cross_language_reference(translated.strip())
    return output


def _translate_ui_to_turkish(ai_engine, strings, course_language):
    """Generate natural Turkish UI prose, not literal sentence mirroring."""
    values = list(dict.fromkeys(str(x).strip() for x in strings if str(x).strip()))
    if not values:
        return {}
    output = {}
    for start in range(0, len(values), 24):
        chunk = values[start:start + 24]
        payload = {str(i): value for i, value in enumerate(chunk)}
        prompt = f"""Render each educational UI string as natural, concise Turkish for a Turkish-speaking learner studying {course_language}.
Preserve {course_language} words, letters, stress marks, quoted target forms and IPA exactly. Translate the instructional meaning faithfully, but use idiomatic Turkish rather than word-for-word calques. Do not add facts. Return ONLY a JSON object with the exact keys.
{json.dumps(payload, ensure_ascii=False)}"""
        result = ai_engine._call_ai(
            [{"role": "user", "content": prompt}],
            model=ai_engine.MODEL_TRANSLATOR,
            max_tokens=3000,
            temperature=0.05,
            json_mode=True,
        )
        mapping = _unwrap_mapping(result)
        for i, source in enumerate(chunk):
            translated = mapping.get(str(i)) if isinstance(mapping, dict) else None
            if isinstance(translated, str) and translated.strip():
                output[source] = translated.strip()
    return output


def _split_preserved_option(value):
    text = str(value or "").strip()
    if not text:
        return "", ""
    m = re.match(r"^(\[[^\]]+\]|«[^»]+»|“[^”]+”|'[^']+'|\"[^\"]+\")\s*\((.+)\)$", text)
    if m:
        return m.group(1), m.group(2).strip()
    return "", text


def _localize_options(raw_options, tr_map, en_map):
    en_values, tr_values = [], []
    for raw in raw_options:
        text = str(raw or "").strip()
        prefix, note = _split_preserved_option(text)
        if prefix:
            en_note = en_map.get(note, note)
            tr_note = tr_map.get(en_note, tr_map.get(note, note))
            en_values.append(f"{prefix} ({en_note})")
            tr_values.append(f"{prefix} ({tr_note})")
        elif _looks_english(text):
            en_values.append(text)
            tr_values.append(tr_map.get(text, text))
        elif _looks_turkish(text):
            tr_values.append(text)
            en_values.append(en_map.get(text, text))
        else:
            # Pure target-language form is tested content, not interface prose.
            en_values.append(text)
            tr_values.append(text)
    return en_values, tr_values


def canonicalize_course(course_id, bilingual_finisher, ai_engine):
    from database import db_connection

    with db_connection() as db:
        course_row = db.execute("SELECT language FROM courses WHERE id = ?", (course_id,)).fetchone()
        course_language = (course_row["language"] if course_row else None) or "target language"
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
    explanation_entries = []
    token_targets = {}

    for row in rows:
        try:
            tid, raw = row["id"], row["content"]
        except Exception:
            tid, raw = row[0], row[1]
        try:
            content = json.loads(raw or "{}") if isinstance(raw, str) else (raw or {})
        except Exception:
            continue
        if not isinstance(content, dict):
            continue

        for p_idx, page in enumerate(content.get("pages", []) or []):
            if not isinstance(page, dict):
                continue

            for i_idx, item in enumerate(page.get("items", []) or []):
                if not isinstance(item, dict):
                    continue
                term = item.get("term") or item.get("word") or item.get("letter") or item.get("character") or ""
                old_en = item.get("explanation_en") or item.get("explanation") or ""
                old_tr = item.get("explanation_tr") or item.get("turkish_explanation") or ""
                example = item.get("example") or ""
                if (old_en or old_tr) and _letter_like(term):
                    token = f"{tid}:p{p_idx}:i{i_idx}:expl"
                    explanation_entries.append((token, "alphabet", str(term), str(old_en), str(old_tr), str(example)))
                    token_targets[token] = (item, "explanation")

            for c_idx, comp in enumerate(page.get("comparisons", []) or []):
                if not isinstance(comp, dict):
                    continue
                old_en = comp.get("note_en") or comp.get("note") or comp.get("explanation") or ""
                old_tr = comp.get("note_tr") or comp.get("explanation_tr") or ""
                target_form = comp.get("target") or comp.get("sentence") or comp.get("text") or ""
                if old_en or old_tr:
                    token = f"{tid}:p{p_idx}:c{c_idx}:note"
                    explanation_entries.append((token, "comparison", str(target_form), str(old_en), str(old_tr), ""))
                    token_targets[token] = (comp, "note")

        topics.append((tid, content))

    pair_map = _call_native_explanation_pairs(ai_engine, explanation_entries, course_language)

    for token, pair in pair_map.items():
        target, field = token_targets[token]
        en_value = str(pair.get("en") or "").strip()
        tr_value = str(pair.get("tr") or "").strip()
        if field == "explanation":
            if en_value:
                target["explanation"] = en_value
                target["explanation_en"] = en_value
            if tr_value:
                target["explanation_tr"] = tr_value
                target["turkish_explanation"] = tr_value
        else:
            if en_value:
                target["note"] = en_value
                target["note_en"] = en_value
            if tr_value:
                target["note_tr"] = tr_value

    # Embedded lesson-end MCQs: persist both UI-language views before first paint.
    mcq_records = []
    to_en, to_tr = [], []
    for _, content in topics:
        for page in content.get("pages", []) or []:
            if not isinstance(page, dict) or not (page.get("type") == "mcq" or page.get("prompt")):
                continue

            prompt = str(page.get("prompt") or page.get("question") or "").strip()
            prompt_en = str(page.get("prompt_en") or "").strip()
            prompt_tr = str(page.get("prompt_tr") or "").strip()
            if not prompt_en:
                if _looks_english(prompt):
                    prompt_en = prompt
                elif prompt:
                    to_en.append(prompt)
            if prompt_en and not prompt_tr:
                to_tr.append(prompt_en)

            raw_options = page.get("options") if isinstance(page.get("options"), list) else []
            if not raw_options:
                raw_options = ([page.get("answer")] if page.get("answer") else []) + list(page.get("distractors") or [])

            for raw in raw_options:
                prefix, note = _split_preserved_option(raw)
                source = note if prefix else str(raw or "").strip()
                if _looks_english(source):
                    to_tr.append(source)
                elif _looks_turkish(source):
                    to_en.append(source)

            mcq_records.append((page, prompt, prompt_en, prompt_tr, raw_options))

    en_map = _translate_to_english(ai_engine, to_en, course_language)

    # Resolve canonical EN prompts, then generate native Turkish versions in one pass.
    for page, prompt, prompt_en, prompt_tr, _ in mcq_records:
        if not prompt_en:
            prompt_en = en_map.get(prompt, "")
        if prompt_en:
            page["prompt_en"] = prompt_en
            if not prompt_tr:
                to_tr.append(prompt_en)

    to_tr = list(dict.fromkeys(x for x in to_tr if x))
    tr_map = _translate_ui_to_turkish(ai_engine, to_tr, course_language)

    for page, prompt, prompt_en, prompt_tr, raw_options in mcq_records:
        prompt_en = str(page.get("prompt_en") or prompt_en or en_map.get(prompt, "") or "").strip()
        if prompt_en:
            page["prompt_en"] = prompt_en
            page["prompt_tr"] = str(prompt_tr or page.get("prompt_tr") or tr_map.get(prompt_en, "")).strip()

        en_opts, tr_opts = _localize_options(raw_options, tr_map, en_map)
        page["options_en"] = en_opts
        page["options_tr"] = tr_opts

        raw_answer = str(page.get("answer") or "").strip()
        try:
            answer_idx = [str(x or "").strip() for x in raw_options].index(raw_answer)
        except ValueError:
            answer_idx = -1
        if 0 <= answer_idx < len(en_opts):
            page["answer_en"] = en_opts[answer_idx]
            page["answer_tr"] = tr_opts[answer_idx]
            page["distractors_en"] = [x for i, x in enumerate(en_opts) if i != answer_idx]
            page["distractors_tr"] = [x for i, x in enumerate(tr_opts) if i != answer_idx]

    with db_connection() as db:
        for tid, content in topics:
            db.execute("UPDATE topics SET content = ? WHERE id = ?", (json.dumps(content, ensure_ascii=False), tid))
        db.commit()

    print(
        f"[MATERIAL-CANONICAL] Course {course_id}: persisted native EN/TR lesson views for {course_language}.",
        flush=True,
    )


def install(bilingual_finisher, ai_engine):
    if getattr(bilingual_finisher, "_aula_material_canonicalizer_installed", False):
        return
    raw_finalize = bilingual_finisher.finalize_course_bilingual_data

    def wrapped_finalize(course_id):
        result = raw_finalize(course_id)
        canonicalize_course(course_id, bilingual_finisher, ai_engine)
        return result

    bilingual_finisher.finalize_course_bilingual_data = wrapped_finalize
    bilingual_finisher._aula_material_canonicalizer_installed = True
