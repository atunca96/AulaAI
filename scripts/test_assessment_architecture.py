"""The assessment architecture: scope, progression, target language, and the unit assessment.

Everything here is deterministic. The provider is replaced by a fixture that
returns realistic candidate questions, so the whole path — prompt assembly,
scope boundary, validation, filtering, top-up, attribution, publication
invariants, persistence — is exercised without a single paid call.

The regression this suite exists to prevent first is WS1: a Turkish-track quiz
that assembled two questions out of ten and returned nothing, because the
lesson-page instructional-track gate was being applied to assessment items whose
stems are target-language-complete by contract.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")
os.environ["AULAAI_DATA_DIR"] = tempfile.mkdtemp(prefix="aulaai-assess-")
import database  # noqa: E402
database.DB_PATH = os.path.join(os.environ["AULAAI_DATA_DIR"], "aula.db")
database.init_db()
from database import db_connection  # noqa: E402

import services.ai_engine as ae  # noqa: E402
import services.content_engine as ce  # noqa: E402
from services import assessment_scope as asc  # noqa: E402
from services import assessment_validation as av  # noqa: E402

FAILS = []


def check(cond, label):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        FAILS.append(label)


# ── Fixtures ──────────────────────────────────────────────────────────────────

SPANISH = [
    ("¿Qué dices al llegar por la mañana?", "Buenos días", ["Buenas noches", "Hasta luego", "De nada"]),
    ("Un compañero dice 'Mucho gusto'. ¿Qué respondes?", "Igualmente", ["Buen provecho", "Hasta pronto", "Por favor"]),
    ("¿Qué frase usas para pedir la cuenta?", "La cuenta, por favor", ["Otra vez", "Buenas tardes", "Hasta mañana"]),
    ("Completa: Nosotros _____ en el centro.", "comemos", ["comer", "comes", "comieron"]),
    ("¿Cómo te despides por la tarde?", "Hasta luego", ["Buenos días", "Mucho gusto", "Encantado"]),
    ("Alguien te da las gracias. ¿Qué dices?", "De nada", ["Con permiso", "Buenas noches", "Adiós"]),
    ("¿Cómo pides ayuda con cortesía?", "¿Podría ayudarme?", ["Oye, ven aquí", "Dame eso ya", "Qué pasa"]),
    ("Completa: Ella _____ café por la mañana.", "toma", ["tomar", "tomas", "tomaron"]),
    ("¿Qué dices antes de comer con otros?", "Buen provecho", ["Buenas noches", "Lo siento", "Hasta luego"]),
    ("¿Qué respondes a '¿Cómo estás?'", "Muy bien, gracias", ["Buen provecho", "La cuenta", "Encantado"]),
    ("¿Cómo saludas por la noche?", "Buenas noches", ["Buenos días", "Mucho gusto", "Igualmente"]),
    ("Completa: Yo _____ al mercado.", "voy", ["ir", "vas", "fueron"]),
    ("¿Qué dices al entrar en una sala?", "Con permiso", ["De nada", "Hasta luego", "Buen provecho"]),
]
TASKS = ["situational_decision", "dialogue_comprehension", "sentence_application",
         "grammatical_discrimination", "communicative_collocation"]

CAPTURED = {}


def fixture_provider(bank=SPANISH, count=13):
    def _call(messages, model=None, max_tokens=1000, temperature=0.7, json_mode=True,
              allow_fallback=True, usage_dict=None, cost_stage="other", cost_subject="",
              cache_system=False, **kw):
        CAPTURED["system"] = str(messages[0].get("content", ""))
        CAPTURED["user"] = str(messages[-1].get("content", ""))
        CAPTURED.setdefault("calls", []).append({"stage": cost_stage, "cache_system": cache_system,
                                                 "max_tokens": max_tokens})
        out = []
        for i in range(count):
            p, a, d = bank[i % len(bank)]
            out.append({
                "type": "mcq", "material_section": f"Part {i % 3 + 1}", "evidence": f"line {i}: {a}",
                "cognitive_task": TASKS[i % 5], "prompt": p,
                "translation_en": "EN " + p, "translation_tr": "TR " + p,
                "answer": a, "distractors": list(d),
                "why": f"'{a}' is the taught form here ({i}).",
                "why_tr": f"'{a}' burada ogretilen bicimdir ({i}).",
            })
        return {"data": out}
    return _call


def lesson(terms, rules=()):
    return {"pages": [
        {"title": "Vocab", "type": "vocabulary",
         "items": [{"term": t, "translation_en": t, "translation_tr": t} for t in terms]},
        {"title": "Rules", "type": "grammar",
         "rules": [{"rule": r, "example": "ejemplo", "source_evidence": "ev"} for r in rules]},
    ]}


def seed_course(cid, language, track, units):
    with db_connection() as db:
        db.execute("DELETE FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id=?)", (cid,))
        db.execute("DELETE FROM chapters WHERE course_id=?", (cid,))
        db.execute("DELETE FROM courses WHERE id=?", (cid,))
        db.execute("INSERT INTO courses (id,name,language,level,material_language) VALUES (?,?,?,?,?)",
                   (cid, f"{language} A1", language, "A1", track))
        for u_i, (u_title, topics) in enumerate(units, 1):
            ch = f"{cid}-ch{u_i}"
            db.execute("INSERT INTO chapters (id,course_id,number,title) VALUES (?,?,?,?)", (ch, cid, u_i, u_title))
            for t_i, (t_id, t_title, content) in enumerate(topics):
                db.execute("INSERT INTO topics (id,chapter_id,type,title,content,sort_order) VALUES (?,?,?,?,?,?)",
                           (t_id, ch, "vocabulary", t_title, json.dumps(content, ensure_ascii=False), t_i))
        db.commit()


# ── 1. WS1 regression: the quiz path actually returns questions ───────────────

def test_quiz_path_returns_questions():
    print("\n[1] quiz / activity / assignment path (WS1 regression)")
    ae._call_ai = fixture_provider()
    ae.is_ai_available = lambda: True
    ce.is_ai_available = lambda: True

    seed_course("q1", "Spanish", "tr", [("Unit 1", [
        ("qt1", "Saludos", lesson(["buenos días", "hasta luego", "de nada", "gracias", "por favor"], ["Use 'usted' formally."])),
    ])])

    for track in ("tr", "en"):
        CAPTURED["calls"] = []
        got = ce.generate_assessment_set(["qt1"], count=10, is_quiz=True, ui_lang=track)
        check(len(got) == 10, f"{track} track: quiz assembles 10 of 10 requested")
        check(len(CAPTURED["calls"]) == 1, f"{track} track: one provider call, no top-up storm")
        check(all(len(q.get("distractors") or []) == 3 for q in got),
              f"{track} track: every question carries three distractors")
        check(all(len(q.get("options") or []) == 4 for q in got),
              f"{track} track: every question carries four options")

    # A communicative (non-cloze) question is what the old gate silently dropped.
    got = ce.generate_assessment_set(["qt1"], count=10, is_quiz=True, ui_lang="tr")
    check(any("_____" not in q.get("prompt", "") for q in got),
          "tr track: non-cloze communicative questions survive publication")

    # Activities take the same path with is_quiz=False.
    acts = ce.generate_assessment_set(["qt1"], count=8, is_quiz=False, ui_lang="tr")
    check(len(acts) >= 8, "activity path returns a full set")


# ── 2. Scope: topic-local and unit-local ──────────────────────────────────────

def test_scope_boundaries():
    print("\n[2] scope boundaries are structural")
    ae._call_ai = fixture_provider()

    unit_a = [("ua1", "Saludos", lesson(["buenos días", "hasta luego"], ["Use 'usted' formally."])),
              ("ua2", "Cortesía", lesson(["por favor", "con permiso"], ["Requests use 'podría'."]))]
    unit_b = [("ub1", "Comida", lesson(["restaurante", "camarero"], ["Ordering uses 'quisiera'."]))]
    seed_course("s1", "Spanish", "tr", [("Unit 1", unit_a), ("Unit 2", unit_b)])

    # The unit assessment must be built from its own unit's payload only.
    topics = [{"id": t, "title": ti, "content": c} for t, ti, c in unit_a]
    ae.generate_unit_assessment("Unit 1", topics, "Spanish", "A1", "tr", 1, 2)
    payload = CAPTURED["user"]
    check("Saludos" in payload and "Cortesía" in payload, "unit payload contains its own topics")
    check("Comida" not in payload and "restaurante" not in payload,
          "unit payload contains nothing from a later unit")
    check("SCOPE — THIS UNIT ONLY" in payload, "unit scope clause is stated")

    # Leakage detection is provenance-based, not a guess about wording.
    leaked = {"prompt": "¿Dónde trabaja el camarero?", "answer": "En el restaurante",
              "distractors": ["a", "b", "c"], "why": "x"}
    check(av.out_of_scope_terms(leaked, ["restaurante", "camarero"]),
          "later-unit vocabulary in an item is detected as leakage")
    clean = {"prompt": "¿Qué dices por la mañana?", "answer": "Buenos días",
             "distractors": ["a", "b", "c"], "why": "x"}
    check(not av.out_of_scope_terms(clean, ["restaurante", "camarero"]),
          "an in-scope item is not flagged")

    # A topic lesson is generated from that topic's source alone, and says so.
    from services.material_generation_prompt import build_material_prompts
    _sys, usr = build_material_prompts(language="Spanish", level="A1", topic="Saludos",
                                       topic_type="vocabulary", official_institution="I",
                                       assessment_budget="BUDGET")
    check("not a later topic" in usr, "topic lesson is told its assessment is topic-local")
    check("BUDGET" in usr, "topic lesson carries its assessment language budget")


# ── 3. The ten-question unit assessment ───────────────────────────────────────

def test_unit_assessment():
    print("\n[3] every unit ends with a ten-question assessment")
    ae._call_ai = fixture_provider()
    check(asc.UNIT_ASSESSMENT_COUNT == 10, "the unit assessment is ten questions by definition")

    unit = [("u1", "Saludos", lesson(["buenos días", "buenas noches", "hasta luego", "de nada", "gracias"], ["Use 'usted'."])),
            ("u2", "Cortesía", lesson(["por favor", "con permiso"], ["Requests use 'podría'.", "Formal address."]))]
    seed_course("ua", "Spanish", "tr", [("Everyday Survival", unit)])

    from services.legacy.pdf_pipeline import _build_unit_assessments
    _build_unit_assessments("ua", "Spanish", "A1", "tr")

    with db_connection() as db:
        rows = db.execute(
            "SELECT id,type,title,content,sort_order FROM topics WHERE chapter_id='ua-ch1' ORDER BY sort_order"
        ).fetchall()
    assessments = [r for r in rows if r[1] == "unit_assessment"]
    check(len(assessments) == 1, "exactly one assessment topic is created for the unit")
    check(rows[-1][1] == "unit_assessment", "it sits at the END of the unit")

    content = json.loads(assessments[0][3])
    mcq = [p for p in content["pages"] if p.get("type") == "mcq"]
    check(len(mcq) == 10, "it publishes exactly ten questions")
    check(all(p.get("stem_scope") == "target_complete" for p in mcq),
          "every page declares a target-complete stem")
    check(all(len(p.get("options") or []) == 4 for p in mcq), "every page has four options")
    check(all(p.get("answer") in (p.get("options") or []) for p in mcq), "the key is among the options")
    check(all(p.get("topic_id") in ("u1", "u2") for p in mcq), "every question is attributed to a topic")
    covered = {p.get("topic_id") for p in mcq}
    check(covered == {"u1", "u2"}, "coverage reaches every topic in the unit")

    # Re-running must not stack a second assessment onto the unit.
    _build_unit_assessments("ua", "Spanish", "A1", "tr")
    with db_connection() as db:
        again = db.execute("SELECT COUNT(*) FROM topics WHERE chapter_id='ua-ch1' AND type='unit_assessment'").fetchone()
    check(again[0] == 1, "rebuilding replaces the assessment rather than duplicating it")

    # A unit that cannot produce ten publishable questions publishes none.
    ae._call_ai = fixture_provider(count=3)
    out = ae.generate_unit_assessment("Thin Unit", [{"id": "u1", "title": "T", "content": lesson(["a"])}],
                                      "Spanish", "A1", "tr", 1, 1)
    check(out == [], "a unit that cannot fill ten questions publishes none, not a partial set")
    ae._call_ai = fixture_provider()


def test_coverage_planner():
    print("\n[4] unit coverage is planned, not sampled")
    topics = [
        {"id": "a", "title": "Alphabet", "content": lesson([f"letter{i}" for i in range(30)])},
        {"id": "b", "title": "Greetings", "content": lesson(["hola", "adiós"])},
        {"id": "c", "title": "Numbers", "content": lesson([f"n{i}" for i in range(10)])},
    ]
    plan = asc.plan_unit_coverage(topics, total=10)
    check(sum(p["questions"] for p in plan) == 10, "the plan allocates exactly ten questions")
    check(all(p["questions"] >= 1 for p in plan), "no topic is silently skipped")
    by_id = {p["topic_id"]: p["questions"] for p in plan}
    check(by_id["a"] > by_id["b"], "a topic that teaches more carries more questions")
    check(asc.plan_unit_coverage(topics, total=10) == plan, "the plan is deterministic")

    many = [{"id": str(i), "title": f"T{i}", "content": lesson(["x"])} for i in range(14)]
    plan2 = asc.plan_unit_coverage(many, total=10)
    check(sum(p["questions"] for p in plan2) == 10, "more topics than questions still allocates ten")
    check(len(plan2) == 10, "and picks ten distinct topics")
    check(not asc.plan_unit_coverage([], total=10), "an empty unit plans nothing")


# ── 5. Target language vs instructional track ─────────────────────────────────

def test_language_architecture():
    print("\n[5] question in the taught language, answer key in the instructional track")
    from services.publication_invariants import (
        enforce_instructional_track, enforce_assessment_track, apply_assessment_invariants,
    )

    item = {"prompt": "¿Qué dices al llegar por la mañana?",
            "options": ["Buenos días", "Buenas noches", "Hasta luego", "De nada"],
            "answer": "Buenos días", "distractors": ["Buenas noches", "Hasta luego", "De nada"],
            "why": "Morning greeting.", "why_tr": "Sabah selamı."}
    check(enforce_assessment_track(dict(item), "tr"), "a target-language stem is publishable on the tr track")
    check(enforce_assessment_track(dict(item), "en"), "and on the en track")
    kept = apply_assessment_invariants([dict(item)], language="Spanish", material_language="tr")
    check(len(kept) == 1, "the assessment publication boundary keeps it")

    # The lesson-page gate is unchanged for pages that are genuinely page-shaped.
    page = {"prompt": "Completa: Yo _____ al mercado.", "options": ["voy", "ir", "vas", "fueron"]}
    check(enforce_instructional_track(dict(page), "tr"), "a bare cloze page still passes the page gate")
    prose_page = {"prompt": "Choose the correct word to complete the sentence: 大卫是_____。",
                  "options": ["中国人", "英国人", "法国人", "美国人"]}
    check(not enforce_instructional_track(dict(prose_page), "tr"),
          "an English instruction on the Turkish track is still refused on a page")
    marked = dict(prose_page)
    marked["stem_scope"] = "target_complete"
    check(enforce_instructional_track(marked, "tr"),
          "an item that DECLARES a target-complete stem is exempt, by metadata not by guess")

    # Rationale track.
    gaps = __import__("services.publication_invariants", fromlist=["x"]).assessment_track_gaps
    check(not gaps([item], "tr"), "an item with why_tr has no tr-track gap")
    check(gaps([{"prompt": "x", "why": "only english"}], "tr"), "a missing tr rationale is reported")
    promoted = {"prompt": "x", "why": "English rationale"}
    enforce_assessment_track(promoted, "tr")
    check(promoted.get("why_tr") == "English rationale",
          "a rationale is promoted into the published track rather than the item being dropped")


def test_special_pair_assessment():
    print("\n[6] English and Turkish taught: question in the target, key in the other")
    from services.language_profiles import resolve_track
    from services.material_generation_prompt import build_material_prompts

    check(resolve_track("English", "en", "en") == "tr", "English course publishes the Turkish track")
    check(resolve_track("Turkish", "tr", "tr") == "en", "Turkish course publishes the English track")

    en_sys, _ = build_material_prompts(language="English", level="A1", topic="Articles",
                                       topic_type="grammar", official_institution="I")
    check("stem_scope" in en_sys and "target_complete" in en_sys,
          "English course still asks its questions in English")
    check("NO TRANSLATION ITEMS" in en_sys, "and still forbids translation items")
    check("PUBLISHED INSTRUCTIONAL TRACK" in en_sys and "TURKISH TRACK" in en_sys,
          "while its answer keys stay on the Turkish track")

    tr_sys, _ = build_material_prompts(language="Turkish", level="A1", topic="Vowel Harmony",
                                       topic_type="grammar", official_institution="I")
    check("ENGLISH TRACK" in tr_sys and "PUBLISHED INSTRUCTIONAL TRACK" in tr_sys,
          "Turkish course explains its answer keys in English")

    # An ordinary language is untouched by any of this.
    es_sys, _ = build_material_prompts(language="Spanish", level="A1", topic="Saludos",
                                       topic_type="vocabulary", official_institution="I")
    check("<taught_pair>" not in es_sys, "Spanish gets no special-pair section")
    check("ENGLISH TRACK: title, text" in es_sys, "Spanish keeps the general two-track section")

    # And the quiz path honours the lock rather than the session language.
    ae._call_ai = fixture_provider()
    seed_course("en1", "English", "tr", [("Unit 1", [("ent1", "Articles", lesson(["a", "an", "the"], ["Use 'a' before a consonant sound."]))])])
    got = ce.generate_assessment_set(["ent1"], count=10, is_quiz=True, ui_lang="en")
    check(len(got) == 10, "an English course generates a full quiz with the UI in English")
    check("why_tr" in got[0] and got[0]["why_tr"], "its answer key carries the Turkish rationale")


# ── 7. No translation questions ───────────────────────────────────────────────

def test_no_translation_questions():
    print("\n[7] translation questions are refused")
    forbidden = [
        "What does 'casa' mean?",
        "How do you say 'house' in Spanish?",
        "Translate this sentence into Turkish.",
        "'Casa' ne demek?",
        "'Casa' kelimesinin Türkçe karşılığı nedir?",
        "Which option means 'house'?",
        "What is the English translation of 'libro'?",
        "'Libro' ne anlama gelir?",
    ]
    for stem in forbidden:
        check(av.looks_like_translation_question(stem), f"refused: {stem[:42]}")

    allowed = [
        "¿Qué dices al llegar por la mañana?",
        "Completa: Nosotros _____ en el centro.",
        "Bir arkadaşın 'Nasılsın?' diyor. Ne cevap verirsin?",
        "Wählen Sie die richtige Form: Ich _____ nach Hause.",
    ]
    for stem in allowed:
        check(not av.looks_like_translation_question(stem), f"allowed: {stem[:42]}")

    # The rule is stated to the generator, once, in both contracts.
    from services import question_contract as qc
    sysp = qc.build_system_prompt(language="Spanish", level="A1")
    check("NO TRANSLATION QUESTIONS" in sysp, "the standalone contract states it")
    check(sysp.count("NO TRANSLATION QUESTIONS") == 1, "and states it exactly once")

    # And a translation item is rejected by the engine's own filter.
    bank = [("What does 'casa' mean?", "house", ["car", "tree", "book"])] * 13
    ae._call_ai = fixture_provider(bank=bank)
    out = ae.ai_generate_questions("Saludos", "vocabulary", lesson(["casa"]), "Spanish",
                                   count=5, level="A1", material_language="tr")
    check(out == [] or all(not av.looks_like_translation_question(q["prompt"]) for q in out),
          "translation candidates never reach the learner")
    ae._call_ai = fixture_provider()


# ── 8. Progression envelope ───────────────────────────────────────────────────

def test_progression_envelope():
    print("\n[8] the question is phrased inside what the learner can read")
    early = asc.progression_envelope(level="A1", language="Spanish", unit_index=1, unit_total=6,
                                     topics_completed=1, inventory={"terms": ["hola", "adiós"], "rules": []})
    late = asc.progression_envelope(level="B2", language="Spanish", unit_index=5, unit_total=6,
                                    topics_completed=22, inventory={"terms": ["negociar"], "rules": []})
    check("CEFR A1" in early and "CEFR B2" in late, "the budget names the level it is written for")
    check(early != late, "the budget is progressive, not one fixed wording for A1-C2")
    check("no subordination" in early, "A1 forbids structures an A1 learner has not met")
    check("no subordination" not in late, "B2 does not carry the A1 restriction")
    check("hola" in early, "vocabulary already taught is offered as stem wording")
    check("unit 1 of 6" in early and "unit 5 of 6" in late, "course position reaches the budget")
    check("very beginning of the course" in early, "the very start of a course is called out")
    check("very beginning of the course" not in late, "and a later unit is not")

    # Read out of real material rather than assumed.
    inv = asc.taught_inventory([lesson(["casa", "libro"], ["Nouns agree in gender."]),
                                lesson(["mesa"], [])])
    check(inv["terms"] == ["casa", "libro", "mesa"], "the inventory is read from the lessons themselves")
    check(inv["rules"] == ["Nouns agree in gender."], "including the structures taught")
    check(asc.taught_inventory([json.dumps(lesson(["silla"]))])["terms"] == ["silla"],
          "and works on stored JSON as well as dicts")

    # An A1 assessment cannot be configured without a budget.
    from services import question_contract as qc
    user = qc.build_material_user_prompt(language="Spanish", level="A1", scope=asc.SCOPE_TOPIC,
                                         title="Saludos", item_count=5, content_str="SRC",
                                         progression=early, request_id="r")
    check("ASSESSMENT LANGUAGE BUDGET" in user, "the budget reaches the generation call")
    check("SCOPE — THIS TOPIC ONLY" in user, "so does the scope boundary")


# ── 9. Deterministic item validation ──────────────────────────────────────────

def test_item_validation():
    print("\n[9] deterministic item validation")
    good = {"prompt": "¿Qué dices al llegar por la mañana?", "answer": "Buenos días",
            "distractors": ["Buenas noches", "Hasta luego", "De nada"],
            "options": ["Buenos días", "Buenas noches", "Hasta luego", "De nada"],
            "why": "Morning greeting.", "why_tr": "Sabah selamı."}
    check(av.violations(good, instructional_track="tr") == [], "a well-formed item passes cleanly")

    cases = [
        ({**good, "distractors": ["a", "b"]}, "distractor_count_2", "two distractors is refused"),
        ({**good, "distractors": ["Buenos días", "x", "y"]}, "answer_among_distractors", "the key among the distractors is refused"),
        ({**good, "options": ["Buenos días", "Buenos días", "x", "y"]}, "duplicate_options", "duplicate options are refused"),
        ({**good, "prompt": "What does 'casa' mean?"}, "translation_question", "a translation item is refused"),
        ({**good, "why_tr": ""}, "missing_why_tr", "a missing published-track rationale is reported"),
    ]
    for item, expected, label in cases:
        found = av.violations(item, instructional_track="tr")
        check(any(f.startswith(expected) for f in found), label)

    stem_in_tr = {**good, "prompt": "Aşağıdakilerden hangisi doğru seçenek?"}
    check(any(f == "stem_in_instructional_language" for f in av.violations(stem_in_tr, instructional_track="tr")),
          "a stem written in the instructional language is refused")

    gap = {**good, "prompt": "Completa: Yo _____ al mercado.", "answer": "voy",
           "translation_en": "Complete: I go to the market."}
    check(any(f.startswith("answer_revealed_in_") or f.startswith("gap_lost_in_")
              for f in av.violations(gap, instructional_track="tr")),
          "a gloss that fills in the gap is refused")

    check(av.is_fatal("translation_question"), "a translation item is fatal")
    check(not av.is_fatal("missing_why_tr"), "a missing rationale is not fatal — it costs a sentence, not a question")

    batch = av.filter_publishable([good, {**good, "prompt": "What does 'casa' mean?"}], instructional_track="tr")
    check(len(batch["kept"]) == 1 and len(batch["rejected"]) == 1, "the batch filter separates the two")

    # A stem asked once already, anywhere in the course. Taken from a shipped
    # A1 book that carried three questions twice, stem for stem.
    sk = av.stem_key
    check(sk("¿Qué palabra tiene la letra hache muda?") == sk("¿Qué palabra tiene la letra hache muda?"),
          "a verbatim repeat is the same stem")
    check(sk("Son las 08:00. ¡Buenos ______!") == sk("Son las 08:00. ¡Buenos ___!"),
          "and stays the same when the gap is drawn a different length")
    check(sk("¿Cómo se escribe?") == sk("¿Como se escribe?"),
          "a dropped accent does not make it a new question")

    # The near-misses this must NOT collapse: both score above 0.85 on a
    # similarity ratio, and both are legitimate items.
    check(sk("Mi hermano ___ los ojos marrones.") != sk("Mi hermana ___ los ojos verdes."),
          "a masculine/feminine contrast pair survives")
    check(sk("¿Cómo se escribe el número 24?") != sk("¿Cómo se escribe el número 34?"),
          "so do two questions about different numbers")

    # Script-agnostic: the key is built from normalization, not from an alphabet.
    check(sk("「は」が入る言葉は?") == sk("「は」が入る言葉は?"), "stems compare in Japanese")
    check(sk("Как пишется 24?") != sk("Как пишется 34?"), "and stay distinct in Cyrillic")

    # The generator must accept the list and must not need it.
    import inspect
    from services import ai_engine as _ae
    check("prior_stems" in inspect.signature(_ae.ai_generate_questions).parameters,
          "the generator takes a course-wide stem list")
    check(inspect.signature(_ae.ai_generate_questions).parameters["prior_stems"].default is None,
          "and works without one")

    # A unit assessment is written from its unit's lessons, so it is the one
    # generator that can re-ask a lesson's own exercise. In a shipped A1 book
    # every repeated question was exactly that.
    _real = _ae.ai_generate_questions
    _cap = {}
    try:
        _ae.ai_generate_questions = lambda **kw: (
            _cap.update(kw)
            or [{"prompt": f"Q{i}", "answer": "a", "distractors": ["b", "c", "d"]} for i in range(10)]
        )
        _lesson = json.dumps({"pages": [
            {"type": "vocabulary", "items": [{"term": "hola"}, {"term": "casa"}, {"term": "mesa"}]},
            {"type": "grammar", "rules": [{"rule": "h is silent", "example": "hola"}]},
            {"type": "mcq", "prompt": "¿Dónde compras medicamentos?", "answer": "en la farmacia"},
        ]})
        _ae.generate_unit_assessment(
            unit_title="U1",
            unit_topics=[{"id": "t1", "title": "Alfabeto", "content": _lesson}],
            language="Spanish", level="A1", material_language="tr",
            unit_index=1, unit_total=3,
        )
    finally:
        _ae.ai_generate_questions = _real
    check(_cap.get("prior_stems") == ["¿Dónde compras medicamentos?"],
          "a unit assessment is told what its own lessons already asked")


# ── 10. Token discipline ──────────────────────────────────────────────────────

def test_token_discipline():
    print("\n[10] the contract did not re-bloat")
    from services import question_contract as qc
    from services.cefr_reference import get_cefr_conditioning
    from services.language_data import get_pedagogical_guidelines

    sysp = qc.build_system_prompt(
        language="Spanish", level="A1",
        cefr_guidance=get_cefr_conditioning("Spanish", "A1"),
        pedagogy_guidance=get_pedagogical_guidelines("Spanish", "A1"))
    approx = len(sysp) // 4
    check(approx < 6000, f"the shared system contract stays lean (~{approx} tokens)")

    # Still class-invariant: the new scope work must not have leaked per-request
    # material into the cached prefix.
    for token in ("SCOPE —", "COVERAGE PLAN", "ASSESSMENT LANGUAGE BUDGET", "UNIQUE_REQUEST_ID"):
        check(token not in sysp, f"{token!r} stays out of the cached system prompt")

    # One shared contract, three scopes — not three prompts.
    topic_u = qc.build_material_user_prompt(language="Spanish", level="A1", scope=asc.SCOPE_TOPIC,
                                            title="T", item_count=5, content_str="S",
                                            progression="P", request_id="r")
    unit_u = qc.build_material_user_prompt(language="Spanish", level="A1", scope=asc.SCOPE_UNIT,
                                           title="U", item_count=10, content_str="S",
                                           progression="P", coverage_plan="PLAN", request_id="r")
    check("THIS TOPIC ONLY" in topic_u and "THIS UNIT ONLY" in unit_u,
          "the scopes differ only in their boundary clause")
    check(len(topic_u) < 2500 and len(unit_u) < 2500, "scope prompts stay small")


def main():
    test_quiz_path_returns_questions()
    test_scope_boundaries()
    test_unit_assessment()
    test_coverage_planner()
    test_language_architecture()
    test_special_pair_assessment()
    test_no_translation_questions()
    test_progression_envelope()
    test_item_validation()
    test_token_discipline()
    print(f"\n=== {len(FAILS)} failing checks ===")
    if FAILS:
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("assessment architecture: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
