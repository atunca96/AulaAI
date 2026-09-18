#!/usr/bin/env python3
"""Regression: an assessment does not print its own heading three times.

The published PDF opened each unit assessment with

    Ünite Değerlendirmesi …      <- the topic title
    Unit Assessment              <- the generic kind label
    Ünite Değerlendirmesi …      <- the first page's section title

Presentation only: nothing stored changes, question numbering and assessment
pages are untouched, and an ordinary topic keeps every heading it had. Matching
is normalized against the titles the topic actually carries in either stored
locale, never against a literal label.
"""

from __future__ import annotations
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")
DATA_DIR = tempfile.mkdtemp(prefix="aulaai-headings-")
os.environ["AULAAI_DATA_DIR"] = DATA_DIR

from services import state as _state  # noqa: E402
_state.VERSION_FILE = os.path.join(DATA_DIR, "version.txt")

import database  # noqa: E402
database.DB_PATH = os.path.join(DATA_DIR, "aula.db")
database.init_db()
from database import db_connection  # noqa: E402

import services.pdf_renderer_v12 as renderer  # noqa: E402

FAILURES = []


def check(condition, label):
    print(("  PASS  " if condition else "  FAIL  ") + label)
    if not condition:
        FAILURES.append(label)


def mcq(n):
    return {"type": "mcq", "title": f"Question {n}", "title_tr": f"Soru {n}",
            "prompt": f"La mujer es ___. ({n})", "answer": "alta",
            "options": ["alta", "alto", "altos", "altas"],
            "distractors": ["alto", "altos", "altas"],
            "explanation": "The stated noun is feminine, so «alta».",
            "explanation_tr": "Belirtilen sözcük dişildir; «alta»."}


def seed(course_id):
    # The assessment's first page repeats the topic heading; the lesson's first
    # page carries an ordinary section title that must survive.
    assessment = {"pages": [
        {"type": "overview", "title": "Unit Assessment",
         "title_tr": "Ünite Değerlendirmesi",
         "text": "Answer all questions.", "text_tr": "Tüm soruları yanıtlayın."},
    ] + [mcq(n) for n in range(1, 4)]}
    lesson = {"pages": [
        {"type": "overview", "title": "Adjective Agreement",
         "title_tr": "Sıfat Uyumu",
         "text": "Adjectives agree.", "text_tr": "Sıfatlar uyum sağlar."},
        mcq(9),
    ]}
    with db_connection() as db:
        db.execute("INSERT INTO courses (id,name,language,level,material_language) "
                   "VALUES (?,?,?,?,?)",
                   (course_id, "Spanish A1", "Spanish", "A1", "tr"))
        chapter = f"{course_id}-ch1"
        db.execute("INSERT INTO chapters (id,course_id,number,title,title_tr) "
                   "VALUES (?,?,?,?,?)",
                   (chapter, course_id, 1, "Unit 1: Agreement", "Ünite 1: Uyum"))
        db.execute("INSERT INTO topics (id,chapter_id,type,title,title_tr,content,sort_order) "
                   "VALUES (?,?,?,?,?,?,?)",
                   (f"{chapter}-lesson", chapter, "lesson", "Adjective Agreement",
                    "Sıfat Uyumu", json.dumps(lesson, ensure_ascii=False), 1))
        db.execute("INSERT INTO topics (id,chapter_id,type,title,title_tr,content,sort_order) "
                   "VALUES (?,?,?,?,?,?,?)",
                   (f"{chapter}-assess", chapter, "unit_assessment", "Unit Assessment",
                    "Ünite Değerlendirmesi", json.dumps(assessment, ensure_ascii=False), 2))
        db.commit()


def page_text(course_id, track):
    import fitz
    data, _dropped = renderer.render_course_pdf(course_id, track)
    doc = fitz.open(stream=data, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def norm_lines(text):
    return [re.sub(r"\s+", " ", line).strip().casefold()
            for line in text.splitlines() if line.strip()]


seed("headings")

for track, topic_heading in (("tr", "ünite değerlendirmesi"),
                             ("en", "unit assessment")):
    print(f"\n[{track}] the assessment heading appears once")
    lines = norm_lines(page_text("headings", track))
    hits = [l for l in lines if l.startswith(topic_heading)]
    check(len(hits) == 1,
          f"{topic_heading!r} printed once, not stacked ({hits})")
    # The other locale's label for the same topic must not appear beside it.
    other = "unit assessment" if track == "tr" else "ünite değerlendirmesi"
    check(not any(l == other for l in lines),
          f"the other locale's duplicate label is gone ({other!r})")

    print(f"[{track}] an ordinary topic keeps its headings")
    lesson_title = "sıfat uyumu" if track == "tr" else "adjective agreement"
    check(any(l.startswith(lesson_title) for l in lines),
          f"the lesson topic title is printed ({lesson_title!r})")
    kind = renderer._norm_key(renderer._kind("lesson", track == "tr"))
    check(any(l == kind for l in lines),
          f"and its kind label survives ({kind!r})")

    print(f"[{track}] the assessment itself is untouched")
    for n in range(1, 4):
        q = f"question {n}" if track == "en" else f"soru {n}"
        check(any(q in l for l in lines), f"{q} still renders")
    check(any("answer all questions" in l or "tüm soruları" in l for l in lines),
          "the first page's body text still renders")


print("\n[both] the suppression is normalized, not a literal match")
check(renderer._norm_key("  Ünite   Değerlendirmesi ")
      == renderer._norm_key("Ünite Değerlendirmesi"),
      "whitespace and case are normalized away")
source = open(os.path.join(ROOT, "services/pdf_renderer_v12.py"),
              encoding="utf-8").read()
block = source.split("_assessment_topic = ", 1)[1].split("topic_html = ", 1)[0]
for token in ("Ünite", "Unit Assessment", "Değerlendirmesi"):
    check(token not in block, f"no literal {token!r} in the suppression logic")


print(f"\n=== {len(FAILURES)} failing checks ===")
for row in FAILURES:
    print("  -", row)
if FAILURES:
    sys.exit(1)
print("[HEADINGS] an assessment prints its heading once; ordinary topics are "
      "unchanged")
