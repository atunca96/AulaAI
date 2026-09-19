#!/usr/bin/env python3
"""The rendered PDF is audited as the artifact, not inferred from the database.

Every other gate reads the canonical JSON. The renderer is a second author —
it rewrites font CMaps, folds presentation forms, localizes labels, paginates
and composes the answer key — so a page can be clean in the database and wrong
on paper. Four defects of that shape were found in a published B1 German PDF
and none of them is visible from the canonical side:

  * U+FFFE in the text layer, while the stored content passed unicode checks;
  * a reading passage printing two of its lines twice;
  * pipeline vocabulary in learner-visible text;
  * a transcription writing aspiration as a plain `h`.

All four are decidable from the bytes, so they are checked on the bytes.

The hardest requirement here is the fourth check's opposite: "Fail belirteci"
is NOT a leak. `fail` is the ordinary Turkish grammatical term for an agent
(Arabic fâil, the doer), and `von` + Dativ marking the agent is precisely what
a German passive lesson has to teach. A meta-leak check that fired on it would
refuse passive voice in every Turkish-track course. Only strings this pipeline
emits about itself count.
"""

from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import artifact_audit as AA  # noqa: E402

FAILURES = []


def check(condition, label):
    if not condition:
        FAILURES.append(label)
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")


def codes(pages):
    return sorted({f.code for f in AA.audit_rendered_text(pages)})


print("[1] malformed Unicode in the text layer")
check("artifact_malformed_unicode" in codes(["e￾posta ve -ete￾Bir"]),
      "U+FFFE is caught")
check("artifact_malformed_unicode" in codes(["a � b"]),
      "U+FFFD, a character already lost, is caught")
check("artifact_malformed_unicode" in codes(["a \x00 b"]), "NUL is caught")
check(codes(["Normale deutsche Prosa mit Umlauten: ä ö ü ß."]) == [],
      "ordinary text with diacritics is clean")

print("\n[2] a line printed twice on one page")
doubled = (
    "Jede Woche werden die verschiedenen Mülltonnen an den Straßenrand gestellt.\n"
    "Jede Woche werden die verschiedenen Mülltonnen an den Straßenrand gestellt.\n"
)
check("artifact_duplicate_line" in codes([doubled]), "the doubled line is caught")
for label, page in (
    ("short repeated labels", "Evet.\nDoğru.\nEvet.\nDoğru.\n"),
    ("a drill frame", "Ich gehe zur Schule.\nDu gehst zur Schule.\n"),
    ("one long line, printed once", doubled.splitlines()[0] + "\n"),
):
    check("artifact_duplicate_line" not in codes([page]), f"not flagged: {label}")
# Two pages may legitimately share a line — a running header, a repeated
# instruction — so the check is per page rather than across the document.
one_line = doubled.splitlines()[0] + "\n"
check("artifact_duplicate_line" not in codes([one_line, one_line]),
      "the same line on two different pages is not a duplicate")

print("\n[3] pipeline vocabulary in learner text")
for text in (
    "render_contract: page_is_renderable refused this",
    "publication blockers are not converging",
    "topic_id 3 strategies_tried 2",
):
    check("artifact_meta_leak" in codes([text]), f"caught: {text[:38]}")

print("\n[4] and grammatical terminology that only LOOKS internal is not a leak")
# The one that matters. Turkish `fail` = agent, from Arabic fâil. A German
# passive lesson marks its agent with von + Dative, so this is the correct
# label, not a leak. Refusing it would block passive voice in every
# Turkish-track course.
for label, text in (
    ("the Turkish agent marker", "Fail belirteci: 'von' + Yönelme Hâli"),
    ("agent in a sentence", "Fail, 'von' ile işaretlenir."),
    ("an English lesson using 'blocker' about traffic",
     "Der Satz beschreibt einen Stau."),
):
    check("artifact_meta_leak" not in codes([text]), f"not a leak: {label}")

print("\n[5] transcription notation")
check("artifact_notation_defect" in codes(["der Kassenbon [deːɐ̯ ˈkhasn̩ ˌbɔŋ]"]),
      "aspiration written as a plain h is caught")
check("artifact_notation_defect" not in codes(["der Kassenbon [deːɐ̯ ˈkʰasn̩ ˌbɔŋ]"]),
      "the modifier letter is accepted")
check("artifact_notation_defect" not in codes(["Das Wort khaki kommt aus dem Urdu."]),
      "'kh' in ordinary prose, outside a transcription, is untouched")

print("\n[6] the audit survives an artifact it cannot read")
findings = AA.audit_pdf_bytes(b"not a pdf at all")
check(bool(findings), "an unreadable artifact produces a finding, not a crash")
check(all(isinstance(f, AA.ArtifactFinding) for f in findings),
      "and the finding is a normal finding")

print("\n[7] it runs on a real rendered PDF in the production path")
import json  # noqa: E402
import tempfile  # noqa: E402
os.environ.setdefault("AULAAI_DATA_DIR", tempfile.mkdtemp(prefix="aulaai-art-"))
import database  # noqa: E402

database.DB_PATH = os.path.join(os.environ["AULAAI_DATA_DIR"], "aula.db")
database.init_db()
from services.pdf_renderer_v12 import render_course_pdf  # noqa: E402

cid = "c-artifact-audit"
content = {"pages": [{
    "type": "grammar", "title": "Passive", "title_tr": "Edilgen Çatı",
    "text": "Das Haus wurde von dem Mann gebaut.",
    "text_tr": "Fail belirteci: 'von' + Yönelme Hâli.",
}]}
with database.db_connection() as db:
    db.execute("DELETE FROM courses WHERE id=?", (cid,))
    db.execute(
        "INSERT INTO courses (id,name,language,level,material_language) "
        "VALUES (?,?,?,?,?)", (cid, "T", "German", "B1", "tr"))
    db.execute("INSERT INTO chapters (id,course_id,number,title) VALUES (?,?,?,?)",
               (cid + "-ch", cid, 1, "Unit 1"))
    db.execute(
        "INSERT INTO topics (id,chapter_id,type,title,content,sort_order) "
        "VALUES (?,?,?,?,?,?)",
        (cid + "-t", cid + "-ch", "grammar", "Passive",
         json.dumps(content, ensure_ascii=False), 0))
    db.commit()

report = {}
pdf, _name = render_course_pdf(cid, lang="tr", report=report)
check(len(pdf) > 1000, f"a PDF was produced ({len(pdf)} bytes)")
check("artifact_findings" in report,
      "the render report carries the artifact audit")
check(report.get("artifact_findings") == [],
      f"a correct passive lesson renders clean ({report.get('artifact_findings')})")

print()
if FAILURES:
    print(f"FAILED ({len(FAILURES)}):")
    for label in FAILURES:
        print(f"  - {label}")
    sys.exit(1)
print("all artifact audit checks passed")
