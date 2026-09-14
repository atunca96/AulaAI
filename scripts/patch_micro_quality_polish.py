#!/usr/bin/env python3
"""
AulaAI Micro-Quality Polish Patch
Ensures language-agnostic instructional shorthand sanitization and MCQ distractor
quality enforcement are active in services/material_quality_guard.py and
services/pdf_renderer_v12.py across all supported languages.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"
TAG = "# AULAAI_MICRO_QUALITY_POLISH"

guard = guard_path.read_text(encoding="utf-8")
if TAG not in guard:
    guard += r'''

# AULAAI_MICRO_QUALITY_POLISH
try:
    _v58_previous_safe_unicode = safe_unicode_normalize
except NameError:
    _v58_previous_safe_unicode = lambda t, l=None: str(t or "")


def safe_unicode_normalize(text: str, language=None) -> str:
    res = _v58_previous_safe_unicode(text, language=language)
    return harmonize_mixed_scripts(res, language=language)


try:
    _v58_previous_meta = sanitize_instructional_metalanguage
except NameError:
    _v58_previous_meta = lambda v, m="tr": str(v or "")


def sanitize_instructional_metalanguage(value, material_language="tr"):
    text = _v58_previous_meta(value, material_language)
    text = sanitize_instructional_shorthand(text, instructional_language=material_language)
    try:
        return deduplicate_morphological_parentheticals(text)
    except NameError:
        return text


try:
    _v58_previous_validate_mcq = validate_mcq
except NameError:
    _v58_previous_validate_mcq = None


def validate_mcq(page):
    if _v58_previous_validate_mcq:
        ok, why = _v58_previous_validate_mcq(page)
        if not ok:
            return ok, why
    if not isinstance(page, dict):
        return False, "mcq-not-dict"
    opts = _as_list(page.get("options") or page.get("choices"))
    prompt = _norm(page.get("prompt") or page.get("question") or page.get("text"))
    expl = _norm(page.get("explanation") or page.get("explanation_tr") or page.get("explanation_en") or "")
    return validate_distractor_quality(opts, prompt=prompt, explanation=expl)


try:
    _v58_previous_integrity = enforce_material_integrity
except NameError:
    _v58_previous_integrity = lambda d, l=None, m="tr": d


def enforce_material_integrity(data, language=None, material_language="tr"):
    out = _v58_previous_integrity(data, language=language, material_language=material_language)
    if not isinstance(out, dict):
        return out
    pages = out.get("pages")
    if isinstance(pages, list):
        is_tr = bool(str(material_language or "").strip().casefold() in ("tr", "turkish", "türkçe"))
        for page in pages:
            if isinstance(page, dict):
                for container in ("items", "vocabulary", "words", "examples", "rules", "comparisons"):
                    sub = page.get(container)
                    if isinstance(sub, list):
                        for idx, item in enumerate(sub):
                            if isinstance(item, dict):
                                sub[idx] = align_lexical_fields(item, language=language, is_tr=is_tr)
    return out
'''
    guard_path.write_text(guard, encoding="utf-8")
    print("Applied micro-quality polish to material_quality_guard.py")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    renderer += r'''

# AULAAI_MICRO_QUALITY_POLISH
from services.material_quality_guard import (
    safe_unicode_normalize as _v58_safe_unicode,
    sanitize_instructional_shorthand as _v58_shorthand,
    deduplicate_morphological_parentheticals as _v58_dedup,
    align_lexical_fields as _v58_align_fields,
    harmonize_mixed_scripts as _v58_harmonize,
)

_v58_previous_pick = _pick

def _pick(obj, en_key, tr_key, is_tr):
    value = _v58_previous_pick(obj, en_key, tr_key, is_tr)
    if is_tr and isinstance(value, str):
        return _v58_dedup(_v58_shorthand(value, "tr"))
    return value

_v58_previous_e = _e

def _e(value):
    raw = _v58_safe_unicode(str(value or ""))
    return _v58_previous_e(raw)

_v58_previous_story = AcademicPaginator._story

def _v58_story(self, fragment: str, *args, **kwargs):
    if fragment and self.is_tr:
        fragment = _v58_shorthand(fragment, "tr")
    if fragment:
        fragment = _v58_safe_unicode(fragment)
    return _v58_previous_story(self, fragment, *args, **kwargs)

AcademicPaginator._story = _v58_story

_v58_previous_normalize_pages = _normalize_pages

def _normalize_pages(content):
    pages = _v58_previous_normalize_pages(content)
    for p in pages:
        if isinstance(p, dict):
            for k in ('items', 'vocabulary', 'words', 'rules', 'comparisons'):
                sub = p.get(k)
                if isinstance(sub, list):
                    for idx, item in enumerate(sub):
                        if isinstance(item, dict):
                            sub[idx] = _v58_align_fields(item)
    return pages
'''
    renderer_path.write_text(renderer, encoding="utf-8")
    print("Applied micro-quality polish to pdf_renderer_v12.py")

