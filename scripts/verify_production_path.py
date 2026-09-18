"""End-to-end proof that READY and the exported PDF describe the same classroom.

Runs the REAL publication gate and the REAL PDF renderer against a real SQLite
database, inside the production image. No fixtures stand in for either boundary:
the assessment questions counted at the end are extracted from the bytes of an
actual rendered PDF.

Two claims are proved, and they are the two halves of the regression:

  1. A classroom carrying the Unit 3 defect — ten stored questions, two of which
     the renderer refuses — is REFUSED by the publication gate. It can never
     reach READY, so it can never be exported eight-of-ten.

  2. A clean classroom passes the gate AND renders with every question intact,
     in BOTH export locales. Stored count, validated count and printed count are
     asserted equal rather than assumed.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")
DATA_DIR = tempfile.mkdtemp(prefix="aulaai-prod-path-")
os.environ["AULAAI_DATA_DIR"] = DATA_DIR

from services import state as _state  # noqa: E402
# The publication gate bumps the content version on success, and that counter
# lives in the app tree rather than the data directory. This script runs at
# image build time, where writing into the app tree is forbidden — the built
# image must be the source as checked in. Redirect the harness's own writes;
# the product's location is left exactly as it is.
_state.VERSION_FILE = os.path.join(DATA_DIR, "version.txt")

import database  # noqa: E402
database.DB_PATH = os.path.join(DATA_DIR, "aula.db")
database.init_db()
from database import db_connection  # noqa: E402

from services.authoring import quality_gate as Q  # noqa: E402

FAILS = []


def check(cond, label):
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILS.append(label)


LESSON_STEMS = [
    "¿Cómo se saluda por la mañana?", "Completa: Yo _____ estudiante.",
    "¿Qué dices para pedir la cuenta?", "Completa: Nosotros _____ en casa.",
    "¿Cómo te despides por la noche?", "Completa: Ella _____ café.",
    "¿Qué respondes a '¿Cómo estás?'", "Completa: Tú _____ la puerta.",
    "¿Cómo pides ayuda con cortesía?", "Completa: Ellos _____ al mercado.",
]

# The two items a Spanish jobs unit produces naturally and the renderer refuses.
POISON = [
    ("María trabaja en una oficina. ¿Cuál es su profesión?",
     ["Es secretaria", "Es cocinera", "Es médica", "Es profesora"],
     "Her profession follows from where she works.",
     "Mesleği çalıştığı yerden çıkarılıyor."),
    ("Pablo es muy puntual. ¿Cuándo llega a clase?",
     ["Siempre a tiempo", "Nunca", "A veces", "Tarde"],
     "He is always on time.", "Her zaman zamanında gelir."),
]


def mcq_page(index, prompt, options, expl_en, expl_tr):
    return {"type": "mcq", "stem_scope": "target_complete", "assessment_scope": "unit",
            "title": f"Question {index}", "title_tr": f"Soru {index}",
            "prompt": prompt, "options": list(options), "answer": options[0],
            "distractors": list(options[1:]),
            "explanation": expl_en, "explanation_tr": expl_tr}


def assessment_content(poisoned=False, unit_no=1):
    pages = [{"type": "overview", "title": "Unit Assessment",
              "title_tr": "Ünite Değerlendirmesi",
              "text": "Check what you have learned in this unit.",
              "text_tr": "Bu ünitede öğrendiklerinizi değerlendirin."}]
    if poisoned:
        for i, (prompt, options, en, tr) in enumerate(POISON, 1):
            pages.append(mcq_page(i, prompt, options, en, tr))
        rest = LESSON_STEMS[2:]
        start = 3
    else:
        rest, start = LESSON_STEMS, 1
    for offset, stem in enumerate(rest):
        # Distinct per unit: the gate refuses exact duplicate stems across a
        # course, and rightly so, so a fixture that reused ten stems six times
        # would be testing the duplicate rule rather than the render contract.
        pages.append(mcq_page(start + offset, f"[U{unit_no}] {stem}",
                              ["opción a", "opción b", "opción c", "opción d"],
                              "The taught form fits here.",
                              "Burada öğretilen biçim uygundur."))
    return {"pages": pages}


def lesson_content(n):
    return {"pages": [{
        "type": "vocabulary", "title": f"Vocabulary {n}", "title_tr": f"Kelimeler {n}",
        "text": "Everyday words for this unit.",
        "text_tr": "Bu ünite için günlük kelimeler.",
        "items": [{"term": "la casa", "phonetic": "la ˈkasa", "translation": "the house",
                   "translation_tr": "ev", "example": "¿Dónde está la casa?",
                   "example_en": "Where is the house?", "example_tr": "Ev nerede?"}]}]}


def seed_course(course_id, poisoned_unit=None, units=6, lessons=5):
    with db_connection() as db:
        db.execute("DELETE FROM topics WHERE chapter_id IN "
                   "(SELECT id FROM chapters WHERE course_id=?)", (course_id,))
        db.execute("DELETE FROM chapters WHERE course_id=?", (course_id,))
        db.execute("DELETE FROM courses WHERE id=?", (course_id,))
        db.execute("INSERT INTO courses (id,name,language,level,material_language) "
                   "VALUES (?,?,?,?,?)",
                   (course_id, "Spanish A1", "Spanish", "A1", "tr"))
        for unit_no in range(1, units + 1):
            chapter = f"{course_id}-ch{unit_no}"
            db.execute("INSERT INTO chapters (id,course_id,number,title,title_tr) "
                       "VALUES (?,?,?,?,?)",
                       (chapter, course_id, unit_no,
                        f"Unit {unit_no}: First Words",
                        f"Ünite {unit_no}: İlk Kelimeler"))
            for lesson_no in range(1, lessons + 1):
                db.execute(
                    "INSERT INTO topics (id,chapter_id,type,title,title_tr,content,sort_order) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (f"{chapter}-t{lesson_no}", chapter, "vocabulary",
                     f"Lesson {unit_no}.{lesson_no}", f"Ders {unit_no}.{lesson_no}",
                     json.dumps(lesson_content(lesson_no), ensure_ascii=False), lesson_no))
            db.execute(
                "INSERT INTO topics (id,chapter_id,type,title,title_tr,content,sort_order) "
                "VALUES (?,?,?,?,?,?,?)",
                (f"{chapter}-assess", chapter, "unit_assessment",
                 "Unit Assessment", "Ünite Değerlendirmesi",
                 json.dumps(assessment_content(unit_no == poisoned_unit, unit_no),
                            ensure_ascii=False), lessons + 1))
        db.commit()


def gate_units(course_id):
    """Exactly the shape `_run_publication_quality_gate` assembles from the DB."""
    units = []
    with db_connection() as db:
        chapters = db.execute(
            "SELECT id, title, number FROM chapters WHERE course_id=? ORDER BY number",
            (course_id,)).fetchall()
        for chapter in chapters:
            rows = db.execute(
                "SELECT id, title, type, content FROM topics WHERE chapter_id=? "
                "ORDER BY sort_order", (chapter[0],)).fetchall()
            topics = [{"id": r[0], "title": r[1], "type": r[2],
                       "content": json.loads(r[3]),
                       "is_assessment": r[2] == "unit_assessment"} for r in rows]
            units.append({"title": chapter[1], "topics": topics})
    return units


def count_pdf_questions(course_id, lang):
    from services.pdf_renderer_v12 import render_course_pdf
    import pymupdf
    pdf_bytes, _name = render_course_pdf(course_id, lang)
    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(document[i].get_text() for i in range(document.page_count))
    return pdf_bytes, text


def main():
    print("[1] a classroom with the Unit 3 defect cannot reach READY")
    seed_course("poisoned", poisoned_unit=3)
    try:
        Q.validate_publication_integrity(units=gate_units("poisoned"),
                                         language="Spanish", track="tr")
        check(False, "the gate REFUSES the classroom that shipped 8/10")
    except Q.QualityGateError as exc:
        check("10" in str(exc),
              f"the gate refuses it before READY: {str(exc)[:88]}")

    print("\n[2] a clean classroom passes the gate and renders complete")
    seed_course("clean")
    try:
        result = Q.validate_publication_integrity(units=gate_units("clean"),
                                                  language="Spanish", track="tr")
        check(result["unit_assessment_questions"] == 60,
              f"the gate validates 60 assessment questions across 6 units "
              f"(got {result['unit_assessment_questions']})")
    except Q.QualityGateError as exc:
        check(False, f"a clean classroom must pass: {exc}")
        sys.exit(1)

    import re
    # Count STEMS, not options: the renderer prints each option list once in the
    # question body and again in the answer key, so counting an option string
    # double-counts. A stem is printed exactly once per question, and every
    # fixture stem carries a unique "[Un] " marker.
    expected_stems = [f"[U{unit_no}] {stem}"
                      for unit_no in range(1, 7) for stem in LESSON_STEMS]
    assert len(set(expected_stems)) == 60

    def normalise(s):
        return re.sub(r"\s+", " ", s)

    for lang in ("tr", "en"):
        pdf_bytes, text = count_pdf_questions("clean", lang)
        check(len(pdf_bytes) > 20000, f"{lang}: a real PDF was produced "
                                      f"({len(pdf_bytes)} bytes)")
        # Every question the renderer printed, counted from the PDF's own text.
        flat = normalise(text)
        printed = sum(1 for stem in expected_stems if flat.count(normalise(stem)) == 1)
        check(printed == 60,
              f"{lang}: the exported PDF prints all 60 assessment questions "
              f"exactly once each (printed {printed})")
        # The renderer numbers questions continuously across the document, so a
        # silently dropped question shifts every number after it. Asserting the
        # printed number of each stem therefore catches a loss anywhere in the
        # book, not only at the end.
        misnumbered = [n for n, stem in enumerate(expected_stems, 1)
                       if f"{n}. {normalise(stem)}" not in flat]
        check(not misnumbered,
              f"{lang}: questions are numbered 1-60 with none dropped "
              f"(wrong at: {misnumbered[:5]})")
        duplicated = re.findall(r"(Ünite|Unit)\s+\d+:\s*(Ünite|Unit)\s+\d+:", text)
        check(not duplicated,
              f"{lang}: no duplicated unit heading in the exported PDF")

    print("\n[3] the gate's refusal describes a real export loss, not a hypothesis")
    # The negative control. If the poisoned classroom were let through, the
    # renderer really would drop the two refused items — the gate and the
    # renderer agree on the same snapshot, which is the whole point of the fix.
    pdf_bytes, text = count_pdf_questions("poisoned", "tr")
    flat = normalise(text)
    for prompt, _o, _e, _t in POISON:
        check(normalise(prompt) not in flat,
              f"the renderer really refuses it: {prompt[:52]}")
    unit3 = [f"[U3] {stem}" for stem in LESSON_STEMS[2:]]
    survived = sum(1 for stem in unit3 if normalise(stem) in flat)
    check(survived == 8,
          f"Unit 3 would have exported {survived}/10 questions — exactly the "
          f"shortfall the gate names")

    print("\n[4] the validated snapshot IS the persisted and exported one")
    # The whole regression was a gate that proved something about one object
    # while a different one reached the reader. Run the REAL
    # `_run_publication_quality_gate` with the semantic reviewers stubbed — the
    # only part that needs a provider — and hold it to two properties:
    # a passing gate persists exactly what it validated, and a failing gate
    # persists nothing at all.
    from services.legacy import pdf_pipeline as P

    def stub_reviews(mutate=None):
        def lessons(*, unit_title, topics, language, level, track, budget,
                    unit_topic_titles=()):
            return 0

        def risks(*, unit_title, topics, language, level, track, budget):
            return 0

        def phonetics(*, units, language, level, track, budget):
            return 0

        def assessment(*, unit_title, assessment_topic, lesson_topics,
                       language, level, track, budget):
            if mutate:
                mutate(unit_title, assessment_topic)
            return 0

        def terra(*, units, language, level, track, budget):
            return 0
        Q.review_unit_lessons = lessons
        Q.review_unit_risk_claims = risks
        Q.review_unit_assessment = assessment
        Q.repair_cross_topic_phonetic_conflicts = phonetics
        Q.final_terra_verify = terra

    def stored_assessment(course_id, unit_no):
        with db_connection() as db:
            row = db.execute("SELECT content FROM topics WHERE id=?",
                             (f"{course_id}-ch{unit_no}-assess",)).fetchone()
        return json.loads(row[0])

    REVIEWER_EDIT = "[U2] Revisado: ¿cómo se saluda por la tarde?"

    def edit_first_stem(unit_title, topic):
        if unit_title.startswith("Unit 2"):
            topic["content"]["pages"][1]["prompt"] = REVIEWER_EDIT

    seed_course("gatepass")
    stub_reviews(edit_first_stem)
    P._run_publication_quality_gate("gatepass", "Spanish", "A1", "tr")
    after = stored_assessment("gatepass", 2)
    check(after["pages"][1]["prompt"] == REVIEWER_EDIT,
          "a passing gate persists the reviewed object it validated")
    _bytes, gate_text = count_pdf_questions("gatepass", "tr")
    check(normalise(REVIEWER_EDIT) in normalise(gate_text),
          "and the exported PDF prints that same reviewed text")

    def contaminate(unit_title, topic):
        if unit_title.startswith("Unit 4"):
            # A reviewer-introduced defect after every count invariant holds.
            topic["content"]["pages"][3]["explanation_tr"] = "on bir = ˈονθε"

    seed_course("gatefail")
    before = stored_assessment("gatefail", 4)
    stub_reviews(contaminate)
    try:
        P._run_publication_quality_gate("gatefail", "Spanish", "A1", "tr")
        check(False, "a defect introduced during review blocks READY")
    except Q.QualityGateError as exc:
        check("blocker" in str(exc).lower(),
              f"a defect introduced during review blocks READY: {str(exc)[:70]}")
    check(stored_assessment("gatefail", 4) == before,
          "and a failing gate writes no partially reviewed content back")

    print(f"\n=== {len(FAILS)} failing checks ===")
    for f in FAILS:
        print("  -", f)
    if FAILS:
        sys.exit(1)
    print("production path: the gate refuses divergence and the PDF matches READY")


if __name__ == "__main__":
    main()
