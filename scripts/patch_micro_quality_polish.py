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
    _v58_previous_meta = sanitize_instructional_metalanguage
except NameError:
    _v58_previous_meta = lambda v, m="tr": str(v or "")


def sanitize_instructional_metalanguage(value, material_language="tr"):
    text = _v58_previous_meta(value, material_language)
    return sanitize_instructional_shorthand(text, instructional_language=material_language)


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
'''
    guard_path.write_text(guard, encoding="utf-8")
    print("Applied micro-quality polish to material_quality_guard.py")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    renderer += r'''

# AULAAI_MICRO_QUALITY_POLISH
from services.material_quality_guard import sanitize_instructional_shorthand as _v58_shorthand

_v58_previous_pick = _pick

def _pick(obj, en_key, tr_key, is_tr):
    value = _v58_previous_pick(obj, en_key, tr_key, is_tr)
    if is_tr and isinstance(value, str):
        return _v58_shorthand(value, "tr")
    return value
'''
    renderer_path.write_text(renderer, encoding="utf-8")
    print("Applied micro-quality polish to pdf_renderer_v12.py")
