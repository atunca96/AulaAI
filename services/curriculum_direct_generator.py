"""Reliable, bounded curriculum generation for the architect.

This module is curriculum-only. It does not alter lesson/material generation.
"""

import json
import os
import re
import time
from datetime import datetime

_EXPECTED_CHAPTERS = 6
_EXPECTED_TOPICS = 5
_ALLOWED_TYPES = {"vocabulary", "grammar", "reading"}


def _log(message):
    try:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [CURRICULUM-DIRECT] {message}\n")
    except Exception:
        pass


def _normalize_type(value):
    value = str(value or "").strip().lower()
    aliases = {
        "vocab": "vocabulary",
        "lexical": "vocabulary",
        "lexis": "vocabulary",
        "grammar": "grammar",
        "grammatical": "grammar",
        "reading": "reading",
        "culture": "reading",
        "cultural": "reading",
        "functional": "reading",
        "communication": "reading",
    }
    return aliases.get(value, value)


def normalize_curriculum(chapters):
    if not isinstance(chapters, list):
        return []

    normalized = []
    for index, chapter in enumerate(chapters):
        if not isinstance(chapter, dict):
            continue
        title = str(chapter.get("title") or "").strip()
        title_tr = str(chapter.get("title_tr") or "").strip()
        title = re.sub(r"^(?:Unit|Chapter)\s*\d+\s*[:\-–—]*\s*", "", title, flags=re.I).strip()
        title_tr = re.sub(r"^(?:Ünite|Bölüm)\s*\d+\s*[:\-–—]*\s*", "", title_tr, flags=re.I).strip()

        topics = []
        raw_topics = chapter.get("topics")
        if isinstance(raw_topics, list):
            for topic in raw_topics:
                if not isinstance(topic, dict):
                    continue
                topics.append({
                    "title": str(topic.get("title") or "").strip(),
                    "title_tr": str(topic.get("title_tr") or "").strip(),
                    "type": _normalize_type(topic.get("type")),
                })

        normalized.append({
            "number": index + 1,
            "title": title,
            "title_tr": title_tr,
            "topics": topics,
        })
    return normalized


def curriculum_is_complete(chapters):
    if not isinstance(chapters, list) or len(chapters) != _EXPECTED_CHAPTERS:
        return False
    for chapter in chapters:
        if not isinstance(chapter, dict):
            return False
        if not str(chapter.get("title") or "").strip() or not str(chapter.get("title_tr") or "").strip():
            return False
        topics = chapter.get("topics")
        if not isinstance(topics, list) or len(topics) != _EXPECTED_TOPICS:
            return False
        for topic in topics:
            if not isinstance(topic, dict):
                return False
            if not str(topic.get("title") or "").strip() or not str(topic.get("title_tr") or "").strip():
                return False
            if _normalize_type(topic.get("type")) not in _ALLOWED_TYPES:
                return False
    return True


def _build_messages(language, level, prompt_extra="", retry=False):
    from services.cefr_reference import get_cefr_conditioning, LANGUAGE_CEFR_STANDARDS

    lang_std = LANGUAGE_CEFR_STANDARDS.get(language, {})
    institution = lang_std.get("institution", f"Council of Europe CEFR framework for {language}")
    guidance = get_cefr_conditioning(language, level, "Curriculum Architecture", "syllabus")

    level_focus = {
        "A1": "absolute basics, phonetics, greetings, numbers, core present-tense patterns, survival language and personal information",
        "A2": "routine tasks, introductory past reference, surroundings, social exchanges, shopping and work situations",
        "B1": "travel, opinions, plans, narrative past, future/conditional functions and reasons",
        "B2": "detailed interaction, abstract discussion, nuanced grammar and independent communication",
        "C1": "academic/professional flexibility, implicit meaning, nuance, idiomatic control and complex discourse",
        "C2": "near-native precision, synthesis, stylistic control and fine shades of meaning",
    }
    focus = next((text for key, text in level_focus.items() if key in str(level).upper()), "the official CEFR outcomes for this level")

    system = f"""You are an expert bilingual curriculum architect for {language} under {institution} and CEFR {level}.
Use the official pedagogical progression below as grounding, but output only the requested compact curriculum JSON.

{guidance}

Quality requirements: CEFR-accurate progression, authentic functional language, grammar and culture; descriptive lesson titles rather than generic labels; natural professional English titles and natural Turkish title_tr values with no English/Turkish hybrids. Keep titles concise and specific."""

    retry_note = "\nThe previous response was structurally incomplete. Regenerate the ENTIRE curriculum from chapter 1 through chapter 6; do not continue or abbreviate it." if retry else ""
    extra = f" Course context: {prompt_extra}." if prompt_extra else ""
    user = f"""Create the complete {level} {language} syllabus.{extra}
Primary focus: {focus}.{retry_note}

Return EXACTLY 6 chapters and EXACTLY 5 topics in every chapter: 30 topics total. No fewer, no more.
Each chapter must contain: number, title, title_tr, topics.
Each topic must contain: title, title_tr, type.
Topic type must be exactly one of: vocabulary, grammar, reading.
Every title must describe a real lesson objective; avoid generic titles such as only "Vocabulary", "Grammar" or "Exercises".
Return ONLY valid JSON in this schema:
{{"chapters":[{{"number":1,"title":"...","title_tr":"...","topics":[{{"title":"...","title_tr":"...","type":"vocabulary"}}]}}]}}"""

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _call_once(ai_engine, language, level, prompt_extra, retry=False):
    started = time.perf_counter()
    result = ai_engine._call_ai(
        _build_messages(language, level, prompt_extra, retry=retry),
        model=ai_engine.MODEL_CURRICULUM,
        max_tokens=2400,
        temperature=0.2,
        json_mode=True,
        allow_fallback=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    chapters = normalize_curriculum(result.get("chapters", []) if isinstance(result, dict) else [])
    valid = curriculum_is_complete(chapters)
    _log(f"attempt={2 if retry else 1} provider_ms={elapsed_ms:.0f} chapters={len(chapters)} valid={int(valid)}")
    return chapters if valid else []


def generate_curriculum(ai_engine, language, level, prompt_extra=""):
    total_started = time.perf_counter()

    chapters = _call_once(ai_engine, language, level, prompt_extra, retry=False)
    if not chapters:
        _log("primary response incomplete; performing one bounded full-regeneration retry")
        chapters = _call_once(ai_engine, language, level, prompt_extra, retry=True)

    if not chapters:
        # A verified local blueprint is preferable to ever returning a partial syllabus.
        try:
            cache_file = ai_engine._get_blueprint_path(language, level)
            if cache_file and os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                cached_chapters = normalize_curriculum(cached.get("chapters", [])) if isinstance(cached, dict) else []
                if curriculum_is_complete(cached_chapters):
                    chapters = cached_chapters
                    _log("using verified exact 6x5 blueprint fallback")
        except Exception as exc:
            _log(f"blueprint fallback error={exc}")

    if not chapters:
        _log("failed: no complete 6x5 curriculum available")
        return []

    bilingual_started = time.perf_counter()
    try:
        from services.curriculum_translator import ensure_bilingual_curriculum
        chapters = ensure_bilingual_curriculum(chapters)
    except Exception as exc:
        _log(f"bilingual repair warning={exc}")
    bilingual_ms = (time.perf_counter() - bilingual_started) * 1000

    # Bilingual repair must never change the required 6x5 structure.
    chapters = normalize_curriculum(chapters)
    if not curriculum_is_complete(chapters):
        _log("failed: bilingual repair broke required structure")
        return []

    total_ms = (time.perf_counter() - total_started) * 1000
    _log(f"complete chapters=6 topics=30 bilingual_ms={bilingual_ms:.0f} total_ms={total_ms:.0f}")
    return chapters


def install(ai_engine):
    """Replace only curriculum drafting; lesson/material generation remains untouched."""
    ai_engine.ai_generate_curriculum = lambda language, level, prompt_extra="": generate_curriculum(
        ai_engine, language, level, prompt_extra
    )
