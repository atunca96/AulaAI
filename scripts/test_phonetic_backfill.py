"""The pronunciation column has no holes in it, and no prose in it either.

A lesson may omit a transcription it is genuinely unsure of — an absent
transcription is honest, an invented one is a factual error a learner cannot
detect. What the reader must never see is a column where most rows carry IPA and
a few are blank, which is indistinguishable from a rendering bug. A shipped A1
book had 25 such holes in 474 rows, including phrase rows the repair pass could
not see because it read a narrower set of headword keys than the renderer.

No paid call is made here: the provider is replaced by a fixture.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")

FAILS = []


def check(cond, label):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILS.append(label)


def test_validator():
    print("\n[1] a returned value is notation, or it is not published")
    from services.publication_evidence import is_usable_transcription as ok
    for value, term, expected, why in [
        ("[ˈθine]", "cine", True, "IPA with a stress mark is accepted"),
        ("[ˈnweβe]", "nueve", True, "so is one with a non-orthographic symbol"),
        ("[ˈzdrastvujtʲe]", "здравствуйте", True, "across scripts"),
        ("[kæt]", "cat", True, "and in English"),
        ("[sinema anlamında]", "cine", False, "an instructional-language gloss is refused"),
        ("peynir", "queso", False, "bare prose is refused"),
        ("cine", "cine", False, "an echo of the headword is refused"),
        ("la hache", "h", False, "a letter name is refused"),
        ("[Cine]", "cine", False, "capitals are prose, not notation"),
        ("[ˈkasa, evi]", "casa", False, "so is sentence punctuation"),
        ("[]", "x", False, "empty brackets publish nothing"),
        # An alphabet table transcribes its vowels as [a], [e], [i]. These carry
        # no exotic symbol and are also echoes of their own headword. A first
        # version of this check refused all five and reported 130 false findings
        # against 341 rows of one real course.
        ("[a]", "a", True, "an alphabet row's own vowel is a real transcription"),
        ("[e]", "e", True, "and so are the rest of them"),
        ("[kasa]", "casa", True, "plain ASCII is notation when it fits the headword"),
        ("[cine]", "cine", False, "but a whole word echoed back is not"),
    ]:
        check(ok(value, term) is expected, why)


def test_repair_on_the_real_path():
    print("\n[2] the repair that actually runs during a build")
    import json
    import tempfile
    os.environ["AULAAI_DATA_DIR"] = tempfile.mkdtemp(prefix="aulaai-phon-")
    import database
    database.DB_PATH = os.path.join(os.environ["AULAAI_DATA_DIR"], "aula.db")
    database.init_db()
    from database import db_connection
    from services.legacy import pdf_pipeline as pp

    content = {"pages": [{"type": "vocabulary", "items": [
        {"term": "cine", "phonetic": ""},
        {"term": "casa", "phonetic": "[ˈkasa]"},
        {"phrase": "¿Puede repetir, por favor?"},
        {"sentence": "Más despacio, por favor"},
        {"term": "el zumo de naranja"},
    ]}]}
    with db_connection() as db:
        db.execute("INSERT INTO courses (id,name,language,level) VALUES ('c1','C','Spanish','A1')")
        db.execute("INSERT INTO chapters (id,course_id,number,title) VALUES ('ch1','c1',1,'U1')")
        db.execute("INSERT INTO topics (id,chapter_id,type,title,content,sort_order) VALUES (?,?,?,?,?,?)",
                   ("t1", "ch1", "vocabulary", "V", json.dumps(content, ensure_ascii=False), 0))
        db.commit()

    captured = {}

    def fixture(messages, **kw):
        captured["prompt"] = messages[0]["content"]
        return {"items": [
            {"term": "cine", "phonetic": "[ˈθine]"},
            {"term": "¿Puede repetir, por favor?", "phonetic": "[ˈpweðe repeˈtiɾ poɾ faˈβoɾ]"},
            {"term": "Más despacio, por favor", "phonetic": "[mas desˈpaθjo poɾ faˈβoɾ]"},
            {"term": "el zumo de naranja", "phonetic": "portakal suyu"},
        ]}

    real, pp._call_ai = pp._call_ai, fixture
    try:
        filled = pp._repair_missing_phonetics("c1", "Spanish")
    finally:
        pp._call_ai = real

    asked = captured.get("prompt", "")
    check("¿Puede repetir, por favor?" in asked, "a phrase row is now requested (was invisible before)")
    check("Más despacio, por favor" in asked, "so is a sentence row")
    check("casa" not in asked.split("Terms missing phonetics:")[-1],
          "a row that already has a transcription is not re-requested")
    check("NOT a reason to return nothing" in asked,
          "variation between standards is not offered as grounds to return nothing")

    with db_connection() as db:
        stored = json.loads(db.execute("SELECT content FROM topics WHERE id='t1'").fetchone()[0])
    items = stored["pages"][0]["items"]
    check(items[0]["phonetic"] == "[ˈθine]", "a hole is filled")
    check(items[1]["phonetic"] == "[ˈkasa]", "an existing transcription is left alone")
    check(items[2].get("phonetic", "").startswith("[ˈpweðe"), "the phrase row is filled")
    check(items[3].get("phonetic", "").startswith("[mas"), "and the sentence row")
    check(not items[4].get("phonetic"), "a returned translation is refused, leaving the cell blank")
    check(filled == 3, "the count reports only what was actually published")


def test_no_call_without_gaps():
    print("\n[3] a complete course costs nothing")
    import json
    from database import db_connection
    from services.legacy import pdf_pipeline as pp
    complete = {"pages": [{"type": "vocabulary", "items": [{"term": "a", "phonetic": "[a]"}]}]}
    with db_connection() as db:
        db.execute("INSERT INTO courses (id,name,language,level) VALUES ('c2','C','Spanish','A1')")
        db.execute("INSERT INTO chapters (id,course_id,number,title) VALUES ('ch2','c2',1,'U1')")
        db.execute("INSERT INTO topics (id,chapter_id,type,title,content,sort_order) VALUES (?,?,?,?,?,?)",
                   ("t2", "ch2", "vocabulary", "V", json.dumps(complete, ensure_ascii=False), 0))
        db.commit()
    calls = []

    def fixture(messages, **kw):
        calls.append(1)
        return {}

    real, pp._call_ai = pp._call_ai, fixture
    try:
        filled = pp._repair_missing_phonetics("c2", "Spanish")
    finally:
        pp._call_ai = real
    check(filled == 0 and not calls, "no gaps means no provider call at all")


def test_contract_is_consistent():
    print("\n[4] the generation contract no longer contradicts itself")
    from services.material_generation_prompt import build_material_prompts
    sys_p, _ = build_material_prompts(language="Spanish", level="A1", topic="T",
                                      topic_type="phonetics", official_institution="X")
    check("omit `phonetic`" in sys_p, "omission is still allowed where the transcription is uncertain")
    check("accepted standard varieties" in sys_p,
          "but variation between standards is explicitly not a reason to omit")
    check("has a non-empty `phonetic` value" not in sys_p,
          "the final check no longer demands what the integrity rule forbids")


if __name__ == "__main__":
    test_validator()
    test_repair_on_the_real_path()
    test_no_call_without_gaps()
    test_contract_is_consistent()
    print(f"\n=== {len(FAILS)} failing checks ===")
    if FAILS:
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    print("phonetic repair: all checks passed")
