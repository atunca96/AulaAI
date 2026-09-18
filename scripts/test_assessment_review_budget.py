#!/usr/bin/env python3
"""Regression: assessment review stays compact and serializes budget reservations."""

from __future__ import annotations
import os, sys

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q

content={
    "pages":[{
        "type":"lesson",
        "title":"English title",
        "title_tr":"Türkçe başlık",
        "text":"English explanation",
        "text_tr":"Türkçe açıklama",
        "items":[{
            "term":"madre",
            "translation":"mother",
            "translation_tr":"anne",
            "example":"Mi madre se llama Ana.",
            "example_en":"My mother's name is Ana.",
            "example_tr":"Annemin adı Ana.",
            "explanation":"English note",
            "explanation_tr":"Türkçe not",
        }],
    }]
}

tr=Q._assessment_evidence_records(content, track="tr")
fields=[r["field"] for r in tr]
assert "term" in fields and "example" in fields
assert "translation_tr" in fields and "explanation_tr" in fields
assert "translation" not in fields and "explanation" not in fields
assert len(str(tr)) < len(str(Q._review_records(content)))

digest=Q._assessment_evidence_digest(content, track="tr")
assert any(row.startswith("term: madre") for row in digest), digest
assert any("translation_tr: anne" in row for row in digest), digest
assert all("pages" not in row and "role" not in row and "track" not in row for row in digest)
assert len(str(digest)) < len(str(tr)) * 0.60, (len(str(digest)), len(str(tr)))

pipeline=open(os.path.join(ROOT,"services","legacy","pdf_pipeline.py"),encoding="utf-8").read()
assert "assessment_workers = 1" in pipeline
assert "ThreadPoolExecutor(max_workers=assessment_workers)" in pipeline
print("[ASSESSMENT-BUDGET] compact one-track evidence + serialized reservations")
