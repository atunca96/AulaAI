#!/usr/bin/env python3
"""Regression: assessment generation cannot count renderer-refused MCQs toward 10/10."""

from __future__ import annotations
import os, sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import engine as E
from services.authoring import prompts as P

system=P.build_assessment_system(language="Spanish",level="A1",track="tr")
assert "NEVER infer a person's gender from their name" in system
assert "never infer nationality/identity from birthplace or residence" in system

unsafe={
    "prompt":"María es _____.",
    "answer":"española",
    "distractors":["español","españoles","españolas"],
    "options":["española","español","españoles","españolas"],
    "why":"The name María is feminine, so use the feminine form.",
    "why_tr":"María adı kadın ismidir, bu yüzden dişil biçim kullanılır.",
}
ok,why=E._assessment_item_renderable(unsafe)
assert not ok
assert "gender inferred from a personal name" in why

safe={
    "prompt":"Una mujer de España es _____.",
    "answer":"española",
    "distractors":["español","españoles","españolas"],
    "options":["española","español","españoles","españolas"],
    "why":"The stem explicitly states a woman from Spain.",
    "why_tr":"Soru kökü İspanya'dan bir kadın olduğunu açıkça belirtir.",
}
ok,why=E._assessment_item_renderable(safe)
assert ok, why

print("[ASSESSMENT-RENDER-FILTER] hidden-world MCQs rejected before kept[] PASSED")
