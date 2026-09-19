"""READY must be a proven fact about the persisted classroom, never a claim.

A fresh Spanish A1 build published Unit 2 with nine assessment questions, Unit 3
with eight, and Greek look-alike characters throughout its IPA — from a system
whose deterministic gate rejects every one of those defects. Nothing in the gate
was wrong. `worker.py` set `build_stage='completed'` and 'Classroom is ready!' in
a `finally` in one build mode and unconditionally after the `except` in the
other, so the gate's refusal was written to the database and overwritten one
statement later. The export route refuses a failed course correctly; it was
never shown one.

The IPA contamination had a second and entirely separate cause, and the content
was innocent of it. `harmonize_mixed_scripts` repairs a word that drifted
between scripts — `говориte` -> `говорите` — and it ran over every string on its
way to the page. A transcription looks exactly like such a word to it, because
the IPA borrows θ, β, χ and ɣ from the Greek block, so it "repaired" a correct
`ˈonθe` by rewriting the LATIN letters into Greek: `ˈονθε`. The database held the
right string, every audit passed on the right string, and the wrong one was
manufactured afterwards, inside the renderer.

Every check here is about the mechanism that turns a verdict into state, and
about the artifact the learner actually receives. Real SQLite, the real
publication gate, the real PDF renderer — no fixture stands in for a boundary.
"""

import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")
DATA_DIR = tempfile.mkdtemp(prefix="aulaai-pub-state-")
os.environ["AULAAI_DATA_DIR"] = DATA_DIR

from services import state as _state  # noqa: E402
_state.VERSION_FILE = os.path.join(DATA_DIR, "version.txt")

import database  # noqa: E402
database.DB_PATH = os.path.join(DATA_DIR, "aula.db")
database.init_db()
from database import db_connection  # noqa: E402

from services.authoring import publication_state as PS  # noqa: E402

FAILS = []
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(cond, label):
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILS.append(label)


STEMS = [
    "¿Cómo se saluda por la mañana?", "Completa: Yo _____ estudiante.",
    "¿Qué dices para pedir la cuenta?", "Completa: Nosotros _____ en casa.",
    "¿Cómo te despides por la noche?", "Completa: Ella _____ café.",
    "¿Qué respondes a '¿Cómo estás?'", "Completa: Tú _____ la puerta.",
    "¿Cómo pides ayuda con cortesía?", "Completa: Ellos _____ al mercado.",
]

# Verbatim from the production PDF. Greek ο ν ε κ ι α μ υ standing in for Latin
# and IPA letters; θ, β, ð and ɾ here are legitimate and must stay legal.
CONTAMINATED = {"once": "ˈονθε", "quince": "ˈκινθε", "zumo": "el ˈθυμο"}
CLEAN = {"once": "ˈonθe", "quince": "ˈkinθe", "zumo": "el ˈθumo"}


def mcq(index, prompt):
    return {"type": "mcq", "stem_scope": "target_complete", "assessment_scope": "unit",
            "title": f"Question {index}", "title_tr": f"Soru {index}",
            "prompt": prompt, "options": ["opción a", "opción b", "opción c", "opción d"],
            "answer": "opción a", "distractors": ["opción b", "opción c", "opción d"],
            "explanation": (
                f"The visible question «{prompt}» supplies the evidence used "
                "to select the keyed option."
            ),
            "explanation_tr": (
                f"Görünür soru «{prompt}» işaretli seçeneği belirleyen kanıtı verir."
            )}


def assessment(unit_no, count=10):
    """A unit assessment holding `count` questions, numbered as production does."""
    pages = [{"type": "overview", "title": "Unit Assessment",
              "title_tr": "Ünite Değerlendirmesi",
              "text": "Check what you have learned in this unit.",
              "text_tr": "Bu ünitede öğrendiklerinizi değerlendirin."}]
    for index, stem in enumerate(STEMS[:count], 1):
        pages.append(mcq(index, f"[U{unit_no}] {stem}"))
    return {"pages": pages}


def lesson(vocab):
    return {"pages": [{
        "type": "vocabulary", "title": "Vocabulary", "title_tr": "Kelimeler",
        "text": "Everyday words for this unit.",
        "text_tr": "Bu ünite için günlük kelimeler.",
        "items": [{"term": term, "phonetic": ipa, "translation": "a word",
                   "translation_tr": "bir kelime", "example": f"Quiero {term}.",
                   "example_en": f"I want {term}.", "example_tr": f"{term} istiyorum."}
                  for term, ipa in vocab.items()]}]}


def seed(course_id, *, units=6, vocab=None, short_units=None, stage="enriching"):
    """A whole classroom in the database, shaped exactly as production stores it."""
    short_units = short_units or {}
    with db_connection() as db:
        db.execute("DELETE FROM topics WHERE chapter_id IN "
                   "(SELECT id FROM chapters WHERE course_id=?)", (course_id,))
        db.execute("DELETE FROM chapters WHERE course_id=?", (course_id,))
        db.execute("DELETE FROM courses WHERE id=?", (course_id,))
        db.execute("INSERT INTO courses (id,name,language,level,material_language,"
                   "is_building,build_stage,progress,total_steps) "
                   "VALUES (?,?,?,?,?,?,?,?,?)",
                   (course_id, "Spanish A1", "Spanish", "A1", "tr", 0, stage, 0, 0))
        for unit_no in range(1, units + 1):
            chapter = f"{course_id}-ch{unit_no}"
            db.execute("INSERT INTO chapters (id,course_id,number,title,title_tr) "
                       "VALUES (?,?,?,?,?)",
                       (chapter, course_id, unit_no, f"Unit {unit_no}: First Words",
                        f"Ünite {unit_no}: İlk Kelimeler"))
            db.execute("INSERT INTO topics (id,chapter_id,type,title,title_tr,content,sort_order) "
                       "VALUES (?,?,?,?,?,?,?)",
                       (f"{chapter}-t1", chapter, "vocabulary", f"Lesson {unit_no}.1",
                        f"Ders {unit_no}.1",
                        json.dumps(lesson(vocab or CLEAN), ensure_ascii=False), 1))
            db.execute("INSERT INTO topics (id,chapter_id,type,title,title_tr,content,sort_order) "
                       "VALUES (?,?,?,?,?,?,?)",
                       (f"{chapter}-assess", chapter, "unit_assessment",
                        "Unit Assessment", "Ünite Değerlendirmesi",
                        json.dumps(assessment(unit_no, short_units.get(unit_no, 10)),
                                   ensure_ascii=False), 2))
        db.commit()


def stage_of(course_id):
    with db_connection() as db:
        row = db.execute("SELECT build_stage, build_message FROM courses WHERE id=?",
                         (course_id,)).fetchone()
    return (row[0] or ""), (row[1] or "")


def force_stage(course_id, stage):
    """Set the ready state directly, the way the old worker did."""
    with db_connection() as db:
        db.execute("UPDATE courses SET is_building=0, build_stage=?, "
                   "build_message='Classroom is ready!' WHERE id=?", (stage, course_id))
        db.commit()


# ── 1. The exact production failure: the verdict must survive ────────────────

def test_a_refused_classroom_cannot_be_declared_ready():
    print("\n[1] the build's own success claim cannot grant READY")

    # This is the fresh production build: Unit 2 at 9/10, Unit 3 at 8/10.
    seed("shortfall", short_units={2: 9, 3: 8})
    try:
        PS.mark_ready("shortfall", "LEGACY")
        check(False, "a classroom with 9/10 and 8/10 units is refused")
    except PS.NotPublishable as refusal:
        check("10" in str(refusal),
              f"refused, naming the shortfall: {str(refusal)[:78]}")

    stage, message = stage_of("shortfall")
    check(stage != PS.READY_STAGE,
          f"and the classroom is NOT ready (stage={stage!r})")
    check(stage == "failed" and "Publication refused" in message,
          "the refusal is what the database records, not a success message")

    # The old shape: a caller that ignores the refusal and carries on. It used
    # to overwrite 'failed' with 'completed' one statement later; now there is
    # no statement it can use, because mark_ready is the only writer.
    try:
        PS.mark_ready("shortfall", "LEGACY")
    except PS.NotPublishable:
        pass
    check(stage_of("shortfall")[0] != PS.READY_STAGE,
          "a second attempt by a caller that ignored the refusal changes nothing")


def test_only_one_module_may_write_the_ready_state():
    print("\n[2] there is exactly one writer of the ready state")
    # The root cause was a second and a third writer, each granting READY on its
    # own authority. A grep is the only check that stays true as callers change.
    pattern = re.compile(r"build_stage\s*=\s*'completed'|build_stage\s*=\s*\"completed\"")
    offenders = []
    for folder, _dirs, files in os.walk(ROOT):
        if any(part in folder for part in (".git", "__pycache__", "node_modules")):
            continue
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, ROOT)
            if rel.startswith("scripts" + os.sep):
                continue
            if "publication_state" in rel:
                continue
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                for number, line in enumerate(handle, 1):
                    # A comment may quote the old statement to explain it; only
                    # real code assigns the state.
                    if pattern.search(line.split("#", 1)[0]):
                        offenders.append(f"{rel}:{number}")
    check(not offenders,
          f"no module outside publication_state assigns READY ({offenders[:4]})")


# ── 2. The artifact, not the claim ───────────────────────────────────────────

def test_contamination_cannot_reach_the_learner():
    print("\n[3] Greek-script contamination is refused before a byte is rendered")
    seed("contaminated", vocab=CONTAMINATED)
    try:
        PS.mark_ready("contaminated", "LEGACY")
        check(False, "a contaminated classroom cannot become ready")
    except PS.NotPublishable as refusal:
        check("alien_script" in str(refusal) or "IPA" in str(refusal)
              or "transcription" in str(refusal),
              f"refused at the deterministic layer: {str(refusal)[:78]}")

    # The decisive one. A course whose row already SAYS ready — set by a caller
    # that asserted it, exactly as the old worker did, or carried over from a
    # build that predates this module — must still not export.
    force_stage("contaminated", PS.READY_STAGE)
    check(stage_of("contaminated")[0] == PS.READY_STAGE,
          "the course row now claims to be ready")
    try:
        PS.assert_exportable("contaminated")
        check(False, "a ready-looking contaminated classroom is refused at export")
    except PS.NotPublishable as refusal:
        check(True, f"export refused despite the ready state: {str(refusal)[:66]}")

    # And prove the refusal is load-bearing rather than theoretical. Exported,
    # this classroom does not print the contamination — the publication boundary
    # inside the renderer throws the whole page away on its way to the paper,
    # and says so only in a field nothing used to read. That is the mechanism
    # behind "Question 2, Question 4": the page goes, the surviving pages keep
    # their stored titles, and the PDF looks complete.
    from services.pdf_renderer_v12 import render_course_pdf
    report = {}
    render_course_pdf("contaminated", "tr", report)
    dropped = report.get("dropped") or []
    check(bool(dropped),
          f"the renderer really does discard the contaminated pages ({len(dropped)})")
    check(any("publication boundary" in str(row.get("why")) for row in dropped),
          f"and the discard is reported, not silent: "
          f"{dropped[0].get('why') if dropped else None}")


def test_the_exported_artifact_matches_what_was_certified():
    print("\n[4] the rendered artifact is compared against the certified count")
    from services.pdf_renderer_v12 import render_course_pdf

    seed("clean")
    certified = PS.mark_ready("clean", "LEGACY")
    check(stage_of("clean")[0] == PS.READY_STAGE, "a clean classroom becomes ready")
    check(certified["unit_assessment_questions"] == 60,
          f"and 60 assessment questions were certified "
          f"(got {certified['unit_assessment_questions']})")

    for lang in ("tr", "en"):
        report = {}
        pdf_bytes, _name = render_course_pdf("clean", lang, report)
        check(not report.get("dropped"),
              f"{lang}: the renderer discarded nothing ({report.get('dropped')})")
        check(report.get("questions") == 60,
              f"{lang}: the renderer printed all 60 certified questions "
              f"(printed {report.get('questions')})")
        check(len(pdf_bytes) > 20000, f"{lang}: a real PDF was produced "
                                      f"({len(pdf_bytes)} bytes)")

    # A page the render contract refuses is reported rather than silently
    # skipped, so an export can refuse instead of delivering a short assessment.
    with db_connection() as db:
        content = assessment(2)
        content["pages"][3]["prompt"] = ""
        content["pages"][3]["prompt_tr"] = "Sadece Türkçe kökü var"
        db.execute("UPDATE topics SET content=? WHERE id=?",
                   (json.dumps(content, ensure_ascii=False), "clean-ch2-assess"))
        db.commit()
    report = {}
    render_course_pdf("clean", "en", report)
    check(len(report.get("dropped") or []) == 1,
          f"a page the contract refuses is REPORTED, not skipped "
          f"({report.get('dropped')})")
    check(report.get("questions") == 59,
          f"and the artifact is measurably one question short "
          f"(printed {report.get('questions')})")
    try:
        PS.assert_exportable("clean")
        check(False, "and the classroom no longer passes the export check")
    except PS.NotPublishable:
        check(True, "and the classroom no longer passes the export check")


# ── 3. The regressions that were already fixed must stay fixed ───────────────

def test_previously_fixed_regressions_stay_fixed():
    print("\n[5] the headings and the locale leak stay fixed")
    from services.pdf_renderer_v12 import render_course_pdf
    from services.authoring import audit as A

    seed("stayfixed")
    PS.mark_ready("stayfixed", "LEGACY")
    for lang in ("tr", "en"):
        pdf_bytes, _name = render_course_pdf("stayfixed", lang)
        import pymupdf
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        text = "\n".join(document[i].get_text() for i in range(document.page_count))
        check(not re.findall(r"(Ünite|Unit)\s+\d+:\s*(Ünite|Unit)\s+\d+:", text),
              f"{lang}: no duplicated unit heading in the exported PDF")

    leak = {"pages": [{"type": "vocabulary", "items": [
        {"term": "veintinueve", "translation": "twenty-nine",
         "translation_tr": "twenty-nine", "phonetic": "bejntiˈnwebe"}]}]}
    codes = {f.code for f in A.blocking(A.audit_lesson(leak, language="Spanish", track="tr"))}
    check("locale_leak_in_gloss" in codes, "the Turkish locale leak is still caught")

    fine = {"pages": [{"type": "vocabulary", "items": [
        {"term": "veintinueve", "translation": "twenty-nine",
         "translation_tr": "yirmi dokuz", "phonetic": "bejntiˈnwebe"},
        {"term": "la pizza", "translation": "pizza", "translation_tr": "pizza",
         "phonetic": "la ˈpiθa"}]}]}
    check(not A.blocking(A.audit_lesson(fine, language="Spanish", track="tr")),
          "and a correct gloss pair and a shared loanword still pass")


def test_script_integrity_covers_every_rendered_field():
    print("\n[6] every field that reaches a page is script-checked")
    from services.authoring import audit as A

    # Each of these is read and printed by the renderer, and none of them was
    # reachable by the role-based checks, because the schema does not type them.
    for field in ("prompt_tr", "prompt_en", "question_tr", "stem_tr", "text_en",
                  "phrase", "sentence", "meaning_tr", "said", "intro"):
        page = {"type": "mcq", "prompt": "¿Cuál es correcto?",
                "options": ["a", "b", "c", "d"], "answer": "a", field: "ˈονθε"}
        codes = {f.code for f in A.blocking(
            A.audit_lesson({"pages": [page]}, language="Spanish", track="tr"))}
        check("alien_script_token" in codes, f"contamination is caught in `{field}`")

    # Correct IPA is written without brackets all over this product, and θ, β, ɣ
    # and ð are legitimate. Condemning them would fail every correct classroom.
    for good in ("ˈonθe", "la βeˈβi.ða", "a.βoˈɣa.ðo", "kaˈtoɾθe"):
        page = {"type": "vocabulary", "items": [{"term": "x", "phonetic": good}]}
        check(not A.blocking(A.audit_lesson({"pages": [page]},
                                            language="Spanish", track="tr")),
              f"correct unbracketed IPA still passes: {good}")

    for language, text in (("Russian", "Где находится дом Марты?"),
                           ("Greek", "Πού είναι το σπίτι;"),
                           ("Japanese", "マルタさんのいえはどこですか。"),
                           ("Arabic", "أين بيت مارتا؟"),
                           ("Korean", "마르타의 집은 어디예요?")):
        page = {"type": "vocabulary", "title": text,
                "items": [{"term": text, "translation": "x", "translation_tr": "y"}]}
        check(not A.blocking(A.audit_lesson({"pages": [page]},
                                            language=language, track="tr")),
              f"{language}'s own script is not alien to it")


def test_the_exact_production_signature():
    print("\n[7] \"Question 2, Question 4\": a unit that prints 9 of its 10")
    from services.pdf_renderer_v12 import render_course_pdf
    import pymupdf

    # Question 3 is unanswerable as written — its key is not among its options,
    # an ordinary generation defect. The publication boundary discards that page
    # during export; questions 4-10 keep their stored titles, so the PDF reads
    # 1, 2, 4, 5 ... and looks intact. This is the fresh production build's
    # Unit 2, reproduced from the same stored shape.
    seed("signature", units=1)
    content = assessment(1)
    content["pages"][3]["answer"] = "una opción que no está"
    with db_connection() as db:
        db.execute("UPDATE topics SET content=? WHERE id=?",
                   (json.dumps(content, ensure_ascii=False), "signature-ch1-assess"))
        db.commit()

    force_stage("signature", PS.READY_STAGE)
    report = {}
    pdf_bytes, _name = render_course_pdf("signature", "tr", report)
    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(document[i].get_text() for i in range(document.page_count))

    check(report.get("questions") == 9,
          f"the exported PDF really prints 9 of 10 (printed {report.get('questions')})")
    check("Soru 2" in text and "Soru 3" not in text and "Soru 4" in text,
          "and the stored numbering survives the gap, exactly as shipped: "
          "Soru 2 -> Soru 4")
    check(bool(report.get("dropped")),
          f"the loss is reported instead of silent ({report.get('dropped')})")
    try:
        PS.assert_exportable("signature")
        check(False, "and a 9-of-10 classroom cannot be exported")
    except PS.NotPublishable as refusal:
        check(True, f"and a 9-of-10 classroom cannot be exported: {str(refusal)[:60]}")

    try:
        PS.mark_ready("signature", "LEGACY")
        check(False, "nor can it be declared ready")
    except PS.NotPublishable:
        check(stage_of("signature")[0] == "failed", "nor can it be declared ready")

    # The other half of the production failure, measured in the artifact rather
    # than argued about. Contamination in an explanation is NOT something the
    # publication boundary drops, so it renders: these characters really do
    # reach the learner's page unless the classroom is refused.
    seed("inked", units=1)
    inked = assessment(1)
    inked["pages"][2]["explanation_tr"] = "on bir sayısı ˈονθε biçiminde okunur"
    with db_connection() as db:
        db.execute("UPDATE topics SET content=? WHERE id=?",
                   (json.dumps(inked, ensure_ascii=False), "inked-ch1-assess"))
        db.commit()
    force_stage("inked", PS.READY_STAGE)
    ink_report = {}
    pdf_bytes, _name = render_course_pdf("inked", "tr", ink_report)
    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(document[i].get_text() for i in range(document.page_count))
    greek = sorted({ch for ch in text
                    if "Ͱ" <= ch <= "Ͽ" and ch not in "θβχɣ"})
    check(bool(greek),
          f"contamination in an explanation really is printed ({''.join(greek)})")
    check(not ink_report.get("dropped"),
          "and nothing drops it, so only the publication decision stands in its way")
    try:
        PS.assert_exportable("inked")
        check(False, "so the export must refuse this classroom")
    except PS.NotPublishable as refusal:
        check("alien_script" in str(refusal) or "blocker" in str(refusal),
              f"so the export refuses this classroom: {str(refusal)[:66]}")


def test_the_page_says_what_the_database_says():
    print("\n[8] no render-time transformation may rewrite validated content")
    from services.authoring.legacy_text import safe_unicode_normalize
    from services.pdf_renderer_v12 import render_course_pdf
    import pymupdf

    # The renderer's escaper ran `harmonize_mixed_scripts` over every string on
    # its way to the page. That pass repairs a word that drifted between scripts
    # — `говориte` -> `говорите` — and a transcription looks exactly like one to
    # it, because the IPA borrows θ, β, χ and ɣ from the Greek block. So it
    # "repaired" a correct `ˈonθe` by rewriting the LATIN letters into Greek and
    # produced `ˈονθε`. Stored content was right, every audit passed on it, and
    # the contamination was created afterwards, in the renderer.
    for correct in ("ˈonθe", "ˈkinθe", "el ˈθumo", "kaˈtoɾθe", "a.βoˈɣa.ðo",
                    "la βeˈβi.ða", "ˈtɾeθe", "[ˈonθe]"):
        check(safe_unicode_normalize(correct) == correct,
              f"a transcription survives the renderer's escaper: {correct!r} -> "
              f"{safe_unicode_normalize(correct)!r}")

    # And the pass must still do the job it exists for.
    for wrong, right in (("говориte", "говорите"), ("comеr", "comer"),
                         ("рaбота", "работа"), ("νεpό", "νερό")):
        check(safe_unicode_normalize(wrong) == right,
              f"a genuinely mixed-script word is still harmonized: "
              f"{wrong!r} -> {safe_unicode_normalize(wrong)!r}")

    # The architectural check, and the one that would have caught this without
    # anybody guessing which transformation was to blame: what the database
    # holds must be what the PDF says. Any future pass that rewrites content on
    # its way to the page fails here, whatever it is and whatever it rewrites.
    seed("roundtrip", units=1)
    transcriptions = {"once": "ˈonθe", "quince": "ˈkinθe", "zumo": "el ˈθumo",
                      "abogado": "a.βoˈɣa.ðo", "la bebida": "la βeˈβi.ða",
                      "trece": "ˈtɾeθe", "catorce": "kaˈtoɾθe"}
    with db_connection() as db:
        db.execute("UPDATE topics SET content=? WHERE id=?",
                   (json.dumps(lesson(transcriptions), ensure_ascii=False),
                    "roundtrip-ch1-t1"))
        db.commit()
    PS.mark_ready("roundtrip", "LEGACY")

    for lang in ("tr", "en"):
        pdf_bytes, _name = render_course_pdf("roundtrip", lang)
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        text = "\n".join(document[i].get_text() for i in range(document.page_count))
        flat = re.sub(r"\s+", " ", text)
        missing = [ipa for ipa in transcriptions.values()
                   if re.sub(r"\s+", " ", ipa) not in flat]
        check(not missing,
              f"{lang}: every stored transcription reaches the page unchanged "
              f"(missing {missing})")
        # Greek look-alikes, as opposed to the four symbols the IPA really uses.
        strays = sorted({ch for ch in text
                         if "Ͱ" <= ch <= "Ͽ" and ch not in "θβχɣ"})
        check(not strays,
              f"{lang}: the exported artifact contains no Greek look-alikes "
              f"({''.join(strays)})")


def main():
    test_a_refused_classroom_cannot_be_declared_ready()
    test_only_one_module_may_write_the_ready_state()
    test_contamination_cannot_reach_the_learner()
    test_the_exported_artifact_matches_what_was_certified()
    test_previously_fixed_regressions_stay_fixed()
    test_script_integrity_covers_every_rendered_field()
    test_the_exact_production_signature()
    test_the_page_says_what_the_database_says()
    print(f"\n=== {len(FAILS)} failing checks ===")
    for f in FAILS:
        print("  -", f)
    if FAILS:
        sys.exit(1)
    print("publication state: READY is proven from the persisted classroom")


if __name__ == "__main__":
    main()
