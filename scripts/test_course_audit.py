"""The build looks at the book it just produced.

Every check this project has earned runs per item or per batch. Nothing looked
at the finished artefact, which is why a question asked twice, a letter the stem
gave away and a pronunciation column with holes were each found by a person
reading a PDF rather than by the build. This seeds one of every known defect and
asserts the audit names it.

No model call is made: the audit is deterministic.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")
os.environ["AULAAI_DATA_DIR"] = tempfile.mkdtemp(prefix="aulaai-audit-")
import database  # noqa: E402
database.DB_PATH = os.path.join(os.environ["AULAAI_DATA_DIR"], "aula.db")
database.init_db()
from database import db_connection  # noqa: E402
from services.legacy import pdf_pipeline as pp  # noqa: E402

FAILS = []


def check(cond, label):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILS.append(label)


def mcq(prompt, answer, options):
    return {"type": "mcq", "prompt": prompt, "answer": answer, "options": options}


def seed(cid, topics):
    with db_connection() as db:
        db.execute("INSERT INTO courses (id,name,language,level) VALUES (?,?,?,?)",
                   (cid, "C", "Spanish", "A1"))
        db.execute("INSERT INTO chapters (id,course_id,number,title) VALUES (?,?,?,?)",
                   (f"{cid}-ch", cid, 1, "U1"))
        for i, (tid, title, content) in enumerate(topics):
            db.execute("INSERT INTO topics (id,chapter_id,type,title,content,sort_order)"
                       " VALUES (?,?,?,?,?,?)",
                       (tid, f"{cid}-ch", "vocabulary", title,
                        json.dumps(content, ensure_ascii=False), i))
        db.commit()


def test_dirty_course():
    print("\n[1] a book with one of every known defect")
    lesson = {"pages": [
        {"type": "vocabulary", "items": [
            {"term": "casa", "phonetic": "[ˈkasa]"},
            {"term": "cine"},                                  # hole
            {"term": "queso", "phonetic": "peynir"},           # prose, not notation
        ]},
        mcq("¿Dónde compras medicinas?", "en la farmacia",
            ["en la farmacia", "en el metro", "en el parque", "en el banco"]),
        mcq("¿Qué palabra tiene la letra 'h' muda?", "hola",
            ["hola", "mesa", "casa", "foto"]),                  # giveaway
        mcq("Ella es ____.", "francesa",
            ["francesa", "francés", "frances", "francesas"]),   # spelling variants
        mcq("What does 'casa' mean?", "house",
            ["house", "car", "tree", "book"]),                  # translation item
    ]}
    unit = {"pages": [
        mcq("¿Dónde compras medicinas?", "en la farmacia",     # verbatim repeat
            ["en el banco", "en la farmacia", "en el metro", "en el parque"]),
    ]}
    seed("dirty", [("d1", "Lesson", lesson), ("d2", "Unit test", unit)])
    f = pp._audit_course("dirty")

    check(len(f["repeated_stems"]) == 1, "the question asked twice is named")
    check("Lesson" in f["repeated_stems"][0] and "Unit test" in f["repeated_stems"][0],
          "and both places it appears are identified")
    check(len(f["giveaway"]) == 1, "the stem that gives its own answer away is named")
    check(len(f["spelling_variants"]) == 1, "the misspelling posing as a distractor is named")
    # The validator reports the giveaway and the spelling defect as fatal too, so
    # those items appear here as well as under their own heading. That overlap is
    # intended: this list is what the contract refuses, the others say why.
    check(any("translation_question" in x for x in f["invalid_items"]),
          "the translation drill is named")
    check(len(f["invalid_items"]) == 3,
          "and the two defects that are also contract violations appear here too")
    check(f["phonetic_gaps"] == ["cine"], "the hole in the pronunciation column is named")
    check(len(f["bad_transcriptions"]) == 1, "so is a cell holding prose instead of notation")


def test_clean_course():
    print("\n[2] a clean book reports nothing")
    clean = {"pages": [
        {"type": "vocabulary", "items": [{"term": "casa", "phonetic": "[ˈkasa]"}]},
        mcq("¿Dónde compras medicinas?", "en la farmacia",
            ["en la farmacia", "en el metro", "en el parque", "en el banco"]),
        mcq("Completa: Nosotros _____ en el centro.", "comemos",
            ["comemos", "comer", "comes", "comieron"]),
    ]}
    seed("clean", [("c1", "Lesson", clean)])
    f = pp._audit_course("clean")
    check(sum(len(v) for v in f.values()) == 0, "no findings on a well-formed course")


def test_isolation():
    print("\n[3] courses are audited separately")
    f = pp._audit_course("clean")
    check(not f["repeated_stems"],
          "a stem used in another course is not reported as a repeat here")


if __name__ == "__main__":
    test_dirty_course()
    test_clean_course()
    test_isolation()
    print(f"\n=== {len(FAILS)} failing checks ===")
    if FAILS:
        for x in FAILS:
            print("  -", x)
        sys.exit(1)
    print("course audit: all checks passed")
