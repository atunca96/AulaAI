"""Course-level bilingual canonicalization for generated lesson material.

Runs after the existing bilingual finisher. It makes persisted EN/TR views
semantic pairs so the frontend does not need to repair visible lesson text after
first paint. Target-language examples/forms are preserved.
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
    r"doğru|seçenek|ilk|son|daima|kullanılır|göre|olarak|evde|evler)\b",
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
    return bool(text and _TURKISH_MARKERS.search(text))


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
    text = re.sub(r"\b(?:as|like|just like)\s+in\s+Turkish\b", "in standard pronunciation", text, flags=re.I)
    text = re.sub(r"\bin\s+Turkish\b", "in standard pronunciation", text, flags=re.I)
    text = re.sub(r"\bTurkish\s+(?:speakers|learners)\b", "learners", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _unwrap_mapping(result):
    if not isinstance(result, dict):
        return {}
    for key in ("translations", "data", "items"):
        if isinstance(result.get(key), dict):
            return result[key]
    return result


def _call_canonical_english(ai_engine, entries, course_language):
    """Create accurate, language-neutral English for phonetics/comparison notes.

    For alphabet entries the model is explicitly allowed to correct a generic or
    inaccurate old explanation using standard facts of the actual course language.
    This prevents a Russian letter from inheriting Spanish/Turkish comparison prose.
    """
    if not entries:
        return {}
    out = {}
    chunk_size = 20
    for start in range(0, len(entries), chunk_size):
        chunk = entries[start:start + chunk_size]
        payload = {}
        for idx, entry in enumerate(chunk):
            payload[str(idx)] = {
                "kind": entry[1],
                "term": entry[2],
                "existing_explanation": entry[3],
                "example": entry[4],
            }
        prompt = f"""You are the final linguistic editor for a {course_language} language course.
For every JSON item, return one concise, accurate ENGLISH pedagogical explanation.

Rules:
- For kind=alphabet: explain how that exact character functions/is pronounced in standard {course_language}. Correct a generic or inaccurate existing explanation when necessary using standard linguistic facts.
- For kind=comparison: preserve the exact spelling/reading contrast and meaning of the existing note; improve clarity only.
- Preserve target-language letters, words, stress marks and IPA exactly when they are relevant.
- English prose must be self-contained and language-neutral. NEVER refer to Turkish, Turkish speakers, a learner's native language, or use a Turkish word as the phonetic anchor.
- Do not introduce comparisons to an unrelated language. Prefer IPA or universally understandable articulatory/English anchors where useful.
- Do not add unrelated facts.
Return ONLY a JSON object mapping the exact input keys to explanation strings.

INPUT:
{json.dumps(payload, ensure_ascii=False)}"""
        result = ai_engine._call_ai(
            [{"role": "user", "content": prompt}],
            model=ai_engine.MODEL_TRANSLATOR,
            max_tokens=3200,
            temperature=0.05,
            json_mode=True,
        )
        mapping = _unwrap_mapping(result)
        for local_idx, entry in enumerate(chunk):
            token, _, _, original, _ = entry
            value = mapping.get(str(local_idx)) if isinstance(mapping, dict) else None
            out[token] = _scrub_cross_language_reference(value or original)
    return out


def _translate_to_english(ai_engine, strings, course_language):
    """Explicit-direction translator; intentionally does not consult mixed caches."""
    values = list(dict.fromkeys(str(x).strip() for x in strings if str(x).strip()))
    if not values:
        return {}
    output = {}
    chunk_size = 24
    for start in range(0, len(values), chunk_size):
        chunk = values[start:start + chunk_size]
        payload = {str(i): value for i, value in enumerate(chunk)}
        prompt = f"""Translate each educational UI string into natural, concise English for a {course_language} course.
Preserve {course_language} words, letters, stress marks, quoted target forms and IPA exactly. Translate only explanatory/instructional prose. Do not add facts or learner-language comparisons. Return ONLY a JSON object with the exact keys.
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


def _split_preserved_option(value):
    text = str(value or "").strip()
    if not text:
        return "", ""
    m = re.match(r"^(\[[^\]]+\]|«[^»]+»|“[^”]+”|'[^']+'|\"[^\"]+\")\s*\((.+)\)$", text)
    if m:
        return m.group(1), m.group(2).strip()
    return "", text


def _localize_options(raw_options, tr_map, en_map):
    en_values = []
    tr_values = []
    for raw in raw_options:
        text = str(raw or "").strip()
        prefix, note = _split_preserved_option(text)
        if prefix:
            en_note = en_map.get(note, note)
            tr_note = tr_map.get(en_note, tr_map.get(note, note))
            en_values.append(f"{prefix} ({en_note})")
            tr_values.append(f"{prefix} ({tr_note})")
            continue
        if _looks_english(text):
            en_values.append(text)
            tr_values.append(tr_map.get(text, text))
        elif _looks_turkish(text):
            tr_values.append(text)
            en_values.append(en_map.get(text, text))
        else:
            # Pure target-language answer/form remains identical in both UI languages.
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
    canonical_entries = []
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
                source = item.get("explanation_en") or item.get("explanation") or ""
                example = item.get("example") or ""
                if source and _letter_like(term):
                    token = f"{tid}:p{p_idx}:i{i_idx}:expl"
                    canonical_entries.append((token, "alphabet", str(term), str(source), str(example)))
                    token_targets[token] = (item, "explanation")

            for c_idx, comp in enumerate(page.get("comparisons", []) or []):
                if not isinstance(comp, dict):
                    continue
                note = comp.get("note") or comp.get("explanation") or ""
                target = comp.get("target") or comp.get("sentence") or comp.get("text") or ""
                if note:
                    token = f"{tid}:p{p_idx}:c{c_idx}:note"
                    canonical_entries.append((token, "comparison", str(target), str(note), ""))
                    token_targets[token] = (comp, "note")

        topics.append((tid, content))

    canonical_map = _call_canonical_english(ai_engine, canonical_entries, course_language)

    tr_sources = []
    for token, canonical in canonical_map.items():
        target, field = token_targets[token]
        if field == "explanation":
            target["explanation"] = canonical
            target["explanation_en"] = canonical
        else:
            target["note"] = canonical
        if canonical and canonical not in tr_sources:
            tr_sources.append(canonical)

    mcq_records = []
    en_sources = []
    option_tr_sources = []
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
                    en_sources.append(prompt)

            raw_options = page.get("options") if isinstance(page.get("options"), list) else []
            if not raw_options:
                raw_options = ([page.get("answer")] if page.get("answer") else []) + list(page.get("distractors") or [])
            for raw in raw_options:
                prefix, note = _split_preserved_option(raw)
                source = note if prefix else str(raw or "").strip()
                if _looks_english(source):
                    option_tr_sources.append(source)
                elif _looks_turkish(source):
                    en_sources.append(source)
            mcq_records.append((page, prompt, prompt_en, prompt_tr, raw_options))

    en_map = _translate_to_english(ai_engine, en_sources, course_language)

    for page, prompt, prompt_en, prompt_tr, _ in mcq_records:
        if not prompt_en:
            prompt_en = en_map.get(prompt, "")
        if prompt_en:
            page["prompt_en"] = prompt_en
            if not prompt_tr:
                tr_sources.append(prompt_en)

    tr_sources.extend(option_tr_sources)
    tr_sources = list(dict.fromkeys(x for x in tr_sources if x))
    tr_map = bilingual_finisher.batch_translate_strings(tr_sources, target_lang="tr") if tr_sources else {}

    for token, canonical in canonical_map.items():
        target, field = token_targets[token]
        tr_value = tr_map.get(canonical, "")
        if not tr_value:
            continue
        if field == "explanation":
            target["explanation_tr"] = tr_value
            target["turkish_explanation"] = tr_value
        else:
            target["note_tr"] = tr_value

    for page, prompt, prompt_en, prompt_tr, raw_options in mcq_records:
        prompt_en = str(page.get("prompt_en") or prompt_en or en_map.get(prompt, "") or "").strip()
        if prompt_en:
            page["prompt_en"] = prompt_en
            page["prompt_tr"] = tr_map.get(prompt_en, prompt_tr or page.get("prompt_tr") or "")

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
        f"[MATERIAL-CANONICAL] Course {course_id}: persisted canonical EN/TR lesson fields for {course_language}.",
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
