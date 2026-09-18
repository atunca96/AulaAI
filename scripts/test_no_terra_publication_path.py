#!/usr/bin/env python3
"""Publication review/repair must stay Gemini-only; Luna/Terra/DeepSeek are not runtime dependencies."""

from __future__ import annotations
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
targets=[
    ROOT/"services"/"authoring"/"quality_gate.py",
    ROOT/"services"/"legacy"/"pdf_pipeline.py",
]
for path in targets:
    src=path.read_text(encoding="utf-8").casefold()
    assert "gpt-5.6-terra" not in src, f"Terra model re-entered publication path: {path}"
    assert "terra_verify_model" not in src, f"Terra runtime symbol re-entered publication path: {path}"
    assert "terra_" not in src, f"Terra stage/function re-entered publication path: {path}"
    assert "gpt-5.6-luna-pro" not in src, f"Luna Pro re-entered publication path: {path}"
    assert "deepseek/deepseek-v4.1-flash" not in src, f"DeepSeek re-entered publication path: {path}"
print("[REVIEW-MODEL] broad review=Gemini 3.7 Flash; targeted repair=Gemini 3.8 Flash")
