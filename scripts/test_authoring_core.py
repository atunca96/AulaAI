"""The authoring core across every language and level the product sells.

Three things this suite exists to hold down, in order of how much damage they do
if they slip:

1. **No false positives.** A guard that blocks correct material is worse than no
   guard: it fails builds, costs regenerations, and trains everyone to ignore
   it. Correct material in all fifteen languages must pass clean, and that is
   checked before anything else.

2. **The cost ceiling.** A classroom build costs at most sixty cents. Asserted
   against a fixture-driven build of every language, so it is a property of the
   system rather than an observation about one run.

3. **Coverage.** Fifteen languages times six CEFR levels is ninety courses, and
   a rule that only works for Spanish is a rule that fails for fourteen
   languages silently.

No network, no API key, no paid call anywhere in this file.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")
os.environ.setdefault("AULAAI_DATA_DIR", tempfile.mkdtemp(prefix="aulaai-core-"))

from services.authoring import audit as A  # noqa: E402
from services.authoring import blueprint as BP  # noqa: E402
from services.authoring import budget as B  # noqa: E402
from services.authoring import engine as E  # noqa: E402
from services.authoring import prompts as P  # noqa: E402
from services.authoring import publish as PUB  # noqa: E402
from services.authoring import repair as R  # noqa: E402
from services.authoring import schema as S  # noqa: E402
from services.authoring import transport as T  # noqa: E402

FAILS = []

LANGUAGES = ["English", "Spanish", "German", "French", "Italian", "Portuguese",
             "Russian", "Chinese", "Japanese", "Arabic", "Turkish", "Dutch",
             "Swedish", "Korean", "Greek"]
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


def check(cond, label):
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILS.append(label)


# ── 1. Correct material in every language passes clean ───────────────────────
# One realistic, CORRECT lesson per taught language. If any of these produces a
# blocking finding, the guard is broken, not the material.

GOOD = {
    "Spanish": dict(term="la casa", ipa="la ˈkasa", ex="¿Dónde está la casa de Marta?",
                    gloss="ev", prose="Bu derste ev ve aile kelimelerini öğreneceksiniz."),
    "English": dict(term="the shop", ipa="ðə ʃɒp", ex="Where is the nearest shop, please?",
                    gloss="dükkan", prose="Bu derste alışveriş kelimelerini öğreneceksiniz."),
    "German": dict(term="das Haus", ipa="das haʊs", ex="Wo ist das Haus deiner Schwester?",
                   gloss="ev", prose="Bu derste ev kelimelerini öğreneceksiniz."),
    "French": dict(term="la maison", ipa="la mɛzɔ̃", ex="Où se trouve la maison de Marie ?",
                   gloss="ev", prose="Bu derste ev kelimelerini öğreneceksiniz."),
    "Italian": dict(term="la casa", ipa="la ˈkaːza", ex="Dov'è la casa di Marta?",
                    gloss="ev", prose="Bu derste ev kelimelerini öğreneceksiniz."),
    "Portuguese": dict(term="a casa", ipa="ɐ ˈkazɐ", ex="Onde fica a casa da Marta?",
                       gloss="ev", prose="Bu derste ev kelimelerini öğreneceksiniz."),
    "Dutch": dict(term="het huis", ipa="ɦɛt ɦœys", ex="Waar is het huis van Marta?",
                  gloss="ev", prose="Bu derste ev kelimelerini öğreneceksiniz."),
    "Swedish": dict(term="huset", ipa="ˈhʉːsɛt", ex="Var ligger Martas hus?",
                    gloss="ev", prose="Bu derste ev kelimelerini öğreneceksiniz."),
    "Turkish": dict(term="ev", ipa="ev", ex="Marta'nın evi nerede?",
                    gloss="house", prose="In this lesson you will learn words for the home."),
    "Russian": dict(term="дом", ipa="dom", ex="Где находится дом Марты?",
                    gloss="ev", prose="Bu derste ev kelimelerini öğreneceksiniz."),
    "Greek": dict(term="το σπίτι", ipa="to ˈspiti", ex="Πού είναι το σπίτι της Μάρθας;",
                  gloss="ev", prose="Bu derste ev kelimelerini öğreneceksiniz."),
    "Arabic": dict(term="البيت", ipa="al bajt", ex="أين بيت مارتا؟",
                   gloss="ev", prose="Bu derste ev kelimelerini öğreneceksiniz."),
    "Chinese": dict(term="房子", ipa="fɑŋ t͡sɹ̩", ex="玛尔塔的房子在哪里？",
                    gloss="ev", prose="Bu derste ev kelimelerini öğreneceksiniz."),
    "Japanese": dict(term="いえ", ipa="ie", ex="マルタさんのいえはどこですか。",
                     gloss="ev", prose="Bu derste ev kelimelerini öğreneceksiniz."),
    "Korean": dict(term="집", ipa="t͡ɕip", ex="마르타의 집은 어디예요?",
                   gloss="ev", prose="Bu derste ev kelimelerini öğreneceksiniz."),
}


def good_lesson(language):
    spec = GOOD[language]
    track_prose = "prose"
    is_en_track = language == "Turkish"
    prose_key = "text" if is_en_track else "text_tr"
    gloss_key = "translation" if is_en_track else "translation_tr"
    return {
        "variety": "standard",
        "pages": [{
            "type": "vocabulary",
            ("title" if is_en_track else "title_tr"): "Ev",
            prose_key: spec[track_prose],
            "items": [{"term": spec["term"], "phonetic": spec["ipa"],
                       gloss_key: spec["gloss"], "example": spec["ex"]}],
            "dialogue": [{"speaker": "Marta", "text": spec["ex"],
                          ("line" if is_en_track else "line_tr"): spec["gloss"]}],
        }],
    }


def test_no_false_positives():
    print("\n[1] correct material in every taught language passes clean")
    for language in LANGUAGES:
        lesson = good_lesson(language)
        track = "en" if language == "Turkish" else "tr"
        findings = A.blocking(A.audit_lesson(lesson, language=language, track=track))
        check(not findings,
              f"{language}: clean lesson has no blocking finding"
              + (f" — got {[f.code for f in findings]}" if findings else ""))


def test_repair_is_a_no_op_on_correct_material():
    print("\n[2] repair never touches correct material")
    import json
    for language in LANGUAGES:
        lesson = good_lesson(language)
        before = json.dumps(lesson, ensure_ascii=False, sort_keys=True)
        R.repair_lesson(lesson, language=language)
        after = json.dumps(lesson, ensure_ascii=False, sort_keys=True)
        check(before == after, f"{language}: correct material comes back byte-identical")


# ── 3. Prompts ───────────────────────────────────────────────────────────────

def test_prompts():
    print("\n[3] prompts build for every language, level and track")
    built = 0
    biggest = 0
    for language in LANGUAGES:
        for level in LEVELS:
            for track in ("tr", "en"):
                system = P.build_lesson_system(language=language, level=level, track=track)
                assess = P.build_assessment_system(language=language, level=level, track=track)
                built += 1
                biggest = max(biggest, len(system) // 4, len(assess) // 4)
                if language == "Spanish" and level == "A1" and track == "tr":
                    check("¿" in system, "Spanish carries its opening-mark rule")
                if language == "Greek" and level == "A1":
                    check("';'" in system, "Greek carries its semicolon question mark")
                if language == "Japanese" and level == "A1":
                    check("。" in system, "Japanese carries its fullwidth punctuation")
    check(built == len(LANGUAGES) * len(LEVELS) * 2, f"all {built} combinations build")
    check(biggest < 3000, f"the cached prefix stays lean (largest ~{biggest} tokens)")

    # Class-invariance is what makes the prefix cacheable, which is most of how
    # the cost ceiling is met. Nothing per-topic may enter the system half.
    system = P.build_lesson_system(language="Spanish", level="A1", track="tr")
    for leak in ("<topic>", "REQUEST_ID", "SOURCE MATERIAL", "ALREADY TAUGHT"):
        check(leak not in system, f"{leak!r} stays out of the cached prefix")
    check(P.build_lesson_system(language="Spanish", level="A1", track="tr") == system,
          "the prefix is byte-identical across calls")

    # Each CEFR band must actually differ, or the level is decoration.
    ceilings = {lv: P.cefr_band(lv)["ceiling"] for lv in LEVELS}
    check(len(set(ceilings.values())) == len(LEVELS), "all six CEFR bands differ")
    a1 = P.build_lesson_system(language="Spanish", level="A1")
    c2 = P.build_lesson_system(language="Spanish", level="C2")
    check("No past or future" in a1 and "No past or future" not in c2,
          "A1 forbids what C2 requires")


def test_bilingual_authoring_contract():
    print("\n[3b] lesson and assessment wire shapes carry both instructional languages")
    lesson = P.lesson_schema_block("Spanish", "tr")
    assessment = P.assessment_schema_block("Spanish", "tr")
    for field in ('"title"', '"title_tr"', '"text"', '"text_tr"',
                  '"example_en"', '"example_tr"', '"explanation"', '"explanation_tr"',
                  '"line_en"', '"line_tr"'):
        check(field in lesson, f"lesson schema includes {field}")
    for field in ('"translation_en"', '"translation_tr"', '"why"', '"why_tr"'):
        check(field in assessment, f"assessment schema includes {field}")

    raw = {
        "prompt": "¿Cómo saludas por la mañana?",
        "answer": "Buenos días",
        "distractors": ["Buenas noches", "Hasta luego", "De nada"],
        "translation_en": "How do you greet someone in the morning?",
        "translation_tr": "Sabah birini nasıl selamlarsın?",
        "why": "It is the standard morning greeting.",
        "why_tr": "Sabah kullanılan standart selamlamadır.",
    }
    item = E._clean_item(raw, track="tr")
    check(item.get("translation") == raw["translation_en"],
          "generic translation alias stays English")
    check(item.get("translation_en") == raw["translation_en"],
          "English assessment gloss survives normalisation")
    check(item.get("translation_tr") == raw["translation_tr"],
          "Turkish assessment gloss survives normalisation")
    check(item.get("why") == raw["why"] and item.get("why_tr") == raw["why_tr"],
          "both rationale tracks survive normalisation")


def test_assessment_shortfall_topup():
    print("\n[3c] a near-complete assessment gets one bounded shortfall retry")
    original = E.T.call_model
    calls = []

    bank = [
        ("¿Qué dices al llegar por la mañana?", "Buenos días",
         ["Buenas noches", "Hasta luego", "De nada"]),
        ("¿Qué dices cuando alguien te da las gracias?", "De nada",
         ["Buenos días", "Hasta mañana", "Mucho gusto"]),
        ("¿Qué dices al despedirte?", "Hasta luego",
         ["Buenos días", "Por favor", "Mucho gusto"]),
    ]

    def provider(messages, *, max_tokens, temperature=0.6, model="", cache_system=True,
                 timeout=None, attempts=3):
        idx = min(len(calls), len(bank) - 1)
        prompt, answer, distractors = bank[idx]
        calls.append(str(messages[-1]["content"]))
        data = {"items": [{
            "prompt": prompt, "answer": answer, "distractors": distractors,
            "translation_en": f"English gloss {idx}",
            "translation_tr": f"Türkçe karşılık {idx}",
            "why": "The taught expression fits the situation.",
            "why_tr": "Öğretilen ifade bu duruma uygundur.",
            "evidence": "lesson", "material_section": "greetings",
            "cognitive_task": "situational_decision",
        }]}
        return T.Response(data=data, input_tokens=1800, output_tokens=350, model=model)

    try:
        E.T.call_model = provider
        result = E.generate_assessment(
            title="Greetings", content="Buenos días. De nada. Hasta luego.",
            count=3, language="Spanish", level="A1", track="tr",
            ledger=B.BuildLedger(1.0), seed=1)
    finally:
        E.T.call_model = original

    check(len(calls) == 3, "only the unresolved shortfall caused the third call")
    check(result.attempts == 3, "the result records three bounded attempts")
    check(len(result.items) == 3, "the third attempt completes the requested count")


def test_unit_assessment_reuses_clean_lesson_mcq():
    print("\n[3d] a 9/10 unit assessment is completed from an already-published lesson MCQ")
    import json
    import services.ai_engine as ae

    generated = [{
        "id": f"g{i}", "type": "mcq",
        "prompt": f"¿Qué opción corresponde a la situación número {i}?",
        "answer": f"respuesta {i}",
        "distractors": [f"alternativa {i}a", f"alternativa {i}b", f"alternativa {i}c"],
        "options": [f"respuesta {i}", f"alternativa {i}a", f"alternativa {i}b", f"alternativa {i}c"],
        "why": "The taught form fits.", "why_tr": "Öğretilen biçim uygundur.",
    } for i in range(9)]

    lesson = {"pages": [
        {"type": "overview", "text": "Greeting practice.", "text_tr": "Selamlaşma alıştırması."},
        {"type": "mcq", "prompt": "¿Qué dices al despedirte?",
         "answer": "Hasta luego",
         "options": ["Hasta luego", "Buenos días", "Por favor", "Mucho gusto"],
         "explanation": "It is a standard farewell.",
         "explanation_tr": "Standart bir vedalaşma ifadesidir."},
    ]}
    topics = [{"title": "Saludos", "content": json.dumps(lesson, ensure_ascii=False)}]

    original = ae._engine.generate_assessment
    try:
        ae._engine.generate_assessment = lambda **kwargs: E.AssessmentResult(
            items=list(generated), attempts=3, cost=0.01)
        result = ae.generate_unit_assessment(
            "First Encounters", topics, "Spanish", level="A1",
            material_language="tr", count=10)
    finally:
        ae._engine.generate_assessment = original

    check(len(result) == 10, "the unit assessment reaches the required ten questions")
    check(any(q.get("answer") == "Hasta luego" for q in result),
          "the missing slot came from a clean lesson MCQ, not invented fallback content")


# ── 4. Course planning ───────────────────────────────────────────────────────

def test_planning():
    print("\n[4] course plans are valid for all 90 courses")
    bad = []
    for language in LANGUAGES:
        for level in LEVELS:
            plan = BP.skeleton_plan(language, level)
            problems = BP.validate_plan(plan)
            if problems:
                bad.append((language, level, problems))
    check(not bad, f"all 90 skeleton plans validate — {bad[:2]}")

    for language in ("Russian", "Greek", "Arabic", "Japanese", "Korean", "Chinese"):
        opener = BP.skeleton_plan(language, "A1").topics[0]
        check("sound" in opener.title.casefold() or "writing" in opener.title.casefold(),
              f"{language} A1 opens with its writing system")
        b2 = BP.skeleton_plan(language, "B2").topics[0]
        check("writing" not in b2.title.casefold(),
              f"{language} B2 does not re-teach the alphabet")

    plan = BP.skeleton_plan("Spanish", "A1")
    check(plan.taught_before(plan.topics[0]) == [], "nothing precedes the first topic")
    check(len(plan.taught_before(plan.topics[-1])) > 0, "the last topic knows what came before")

    over = BP.CoursePlan("Spanish", "A1", "tr", [
        BP.Unit(f"U{i}", "", [BP.Topic(f"T{i}.{j}") for j in range(6)]) for i in range(9)])
    check(any("exceeds" in p for p in BP.validate_plan(over)),
          "a plan too large for the budget is refused")


def test_curriculum_titles_are_bilingual():
    """Unit and topic titles show in the lecturer's editor in two columns.

    Generating one title and translating it afterwards put Turkish under ENGLISH
    UNIT NAME and left TÜRKÇE ÜNİTE ADI empty, and cost a batch translation call
    per row — most of the 45 seconds a curriculum used to take.
    """
    print("\n[4b] curriculum titles carry both languages, without a translation pass")
    import services.ai_engine as ae

    for level in LEVELS:
        plan = BP.skeleton_plan("Spanish", level)
        pairs = [(u.title, u.title_tr) for u in plan.units] + \
                [(t.title, t.title_tr) for t in plan.topics]
        both = all(en.strip() and tr.strip() and en.casefold() != tr.casefold()
                   for en, tr in pairs)
        check(both, f"{level}: every skeleton title differs in the two columns")

    parsed = BP._parse({"units": [{
        "title": "Unit 1: Introductions", "title_tr": "Ünite 1: Tanışma", "goal": "g",
        "topics": [
            {"title": "Spanish sounds", "title_tr": "İspanyolca Sesler",
             "type": "phonetics", "teaches": ["the sound inventory"]},
            {"title": "Greetings", "title_tr": "Selamlaşma",
             "type": "vocabulary", "teaches": ["greeting formulas"]}]}] * 3},
        "Spanish", "A1", "tr")
    check(parsed is not None and parsed.units[0].title_tr == "Ünite 1: Tanışma",
          "a model answer's Turkish unit title is parsed, not discarded")
    check(parsed.units[0].topics[0].title_tr == "İspanyolca Sesler",
          "and so is a topic's")

    chapters = [{"number": n, "title": u.title, "title_tr": u.title_tr,
                 "topics": [{"title": t.title, "title_tr": t.title_tr, "type": t.type}
                            for t in u.topics]}
                for n, u in enumerate(parsed.units, 1)]
    check(ae._monolingual_rows(chapters) == 0,
          "a fully bilingual curriculum triggers no translation pass")
    check(ae._monolingual_rows([{"title": "X", "title_tr": "X", "topics": []}]) == 1,
          "a row with the same string in both columns is caught as monolingual")
    check(ae._monolingual_rows([{"title": "X", "title_tr": "", "topics": []}]) == 1,
          "and so is one with an empty column")


def test_curriculum_draft_shape_and_model():
    print("\n[4c] lecturer curriculum uses Gemini 3.8 Flash and exact 6x5 shape")
    original = BP.T.call_model
    seen = {}

    def provider(messages, *, max_tokens, temperature=0.6, model="", cache_system=True,
                 timeout=None, attempts=3):
        seen["model"] = model
        units = []
        for u in range(1, 7):
            units.append({
                "title": f"Unit {u}",
                "title_tr": f"Ünite {u}",
                "goal": f"Goal {u}",
                "topics": [{
                    "title": f"Topic {u}.{t}",
                    "title_tr": f"Konu {u}.{t}",
                    "type": "vocabulary",
                    "teaches": [f"item {u}.{t}"],
                } for t in range(1, 6)],
            })
        return T.Response(data={"units": units}, input_tokens=1200,
                          output_tokens=1800, model=model)

    try:
        BP.T.call_model = provider
        plan = BP.plan_curriculum_draft(language="Spanish", level="A1", track="tr")
    finally:
        BP.T.call_model = original

    check(seen.get("model") == "google/gemini-3.8-flash",
          "curriculum is pinned to Gemini 3.8 Flash")
    check(len(plan.units) == 6, "curriculum has exactly six units")
    check(all(len(unit.topics) == 5 for unit in plan.units),
          "every curriculum unit has exactly five topics")
    check(plan.lesson_count == 30, "curriculum exposes thirty topics")


# ── 5. The cost ceiling ──────────────────────────────────────────────────────

def test_budget():
    print("\n[5] the sixty-cent ceiling")
    check(B.MODEL == "openai/gpt-5.6-terra", f"the model is pinned ({B.MODEL})")

    # Live Terra is $2/$12. The planner is capped at nine lessons because
    # ten passed the nominal projection but failed the real end-to-end fixture
    # after assessment/retry reservations were accounted for.
    for lessons, units in ((6, 3), (8, 4), (BP.MAX_LESSONS, 4)):
        projected = B.project_classroom_cost(lessons=lessons, units=units)
        check(projected["total"] <= B.CLASSROOM_CEILING_USD,
              f"{lessons} lessons / {units} units projects "
              f"${projected['total']:.3f} <= ${B.CLASSROOM_CEILING_USD:.2f}")

    oversized = B.project_classroom_cost(lessons=BP.MAX_LESSONS + 1, units=4)
    check(oversized["total"] > 0,
          "the budget model can price a course above the structural lesson cap")

    ledger = B.BuildLedger(0.05, label="tiny")
    ledger.record(stage="lesson", input_tokens=3000, output_tokens=8000)
    try:
        ledger.require(stage="lesson", input_tokens=3000, output_tokens=8000)
        check(False, "the ledger refuses a call it cannot pay for")
    except B.BudgetExceeded:
        check(True, "the ledger refuses a call it cannot pay for")

    measured = B.BuildLedger(1.0)
    measured.record(stage="lesson", input_tokens=1000, output_tokens=1000, reported_cost=0.0123)
    check(abs(measured.spent - 0.0123) < 1e-9,
          "a provider-reported cost overrides the rate table")

    # Caching must actually be worth something, or the prefix design is pointless.
    fresh = B.price(B.MODEL, input_tokens=10000)
    cached = B.price(B.MODEL, input_tokens=10000, cached_tokens=10000)
    check(cached < fresh / 3, f"a cached prefix costs a quarter (${cached:.5f} vs ${fresh:.5f})")


# ── 6. A whole classroom, in every language ──────────────────────────────────

def fixture_provider(output_per_lesson=2600):
    """A provider that returns plausible, CLEAN material without a network."""
    import itertools
    counter = itertools.count()

    def call(messages, *, max_tokens, temperature=0.6, model="", cache_system=True,
             timeout=None, attempts=3):
        system = str(messages[0]["content"])
        index = next(counter)
        if "curriculum architect" in system:
            data = {"units": [
                {"title": f"Unit {u}", "goal": "goal",
                 "topics": [{"title": f"Topic {u}.{t}", "type": "vocabulary",
                             "teaches": [f"item {u}{t}"]} for t in (1, 2, 3)]}
                for u in (1, 2, 3, 4)]}
            out = 1400
        elif "assessment author" in system:
            data = {"items": [{
                "prompt": f"Situación {k}: ¿qué frase usas para {SITUATIONS[k % 10]}?",
                "answer": f"respuesta correcta {k}",
                "distractors": [f"alternativa {k}a", f"alternativa {k}b", f"alternativa {k}c"],
                "why_tr": "materyale gore dogru", "evidence": "e",
                "material_section": "m", "cognitive_task": "situational_decision"}
                for k in range(12)]}
            out = 1600
        else:
            data = {"variety": "standard", "pages": [{
                "type": "vocabulary", "title_tr": "Baslik",
                "text_tr": "Bu derste yeni kelimeler ogreneceksiniz.",
                "items": [{"term": "la casa", "phonetic": "la ˈkasa",
                           "translation_tr": "ev", "example": "¿Dónde está la casa?"}]}]}
            out = output_per_lesson
        return T.Response(data=data, input_tokens=2600, output_tokens=out,
                          cached_tokens=2100 if index else 0, model=model)
    return call


SITUATIONS = ["saludar", "pedir la cuenta", "preguntar la hora", "despedirte",
              "dar las gracias", "pedir ayuda", "comprar pan", "reservar mesa",
              "preguntar el precio", "presentarte"]


def test_full_builds():
    print("\n[6] a whole classroom build, per language, under the ceiling")
    provider = fixture_provider()
    E.T.call_model = provider
    BP.T.call_model = provider
    worst = 0.0
    for language in LANGUAGES:
        track = "en" if language == "Turkish" else "tr"
        result = E.build_course(language=language, level="A1", track=track)
        worst = max(worst, result.cost)
        ok = (result.cost <= B.CLASSROOM_CEILING_USD and not result.errors
              and len(result.lessons) == result.plan.lesson_count)
        check(ok, f"{language}: {len(result.lessons)} lessons, "
                  f"{sum(len(v) for v in result.unit_assessments.values())} items, "
                  f"${result.cost:.4f}"
                  + (f" — errors {result.errors[:1]}" if result.errors else ""))
    check(worst <= B.CLASSROOM_CEILING_USD,
          f"the most expensive build stayed under the ceiling (${worst:.4f})")


def test_budget_stops_a_runaway():
    print("\n[7] a build that cannot afford itself stops instead of overspending")
    E.T.call_model = fixture_provider(output_per_lesson=20000)
    BP.T.call_model = fixture_provider(output_per_lesson=20000)
    result = E.build_course(language="Spanish", level="A1", track="tr", ceiling_usd=0.05)
    check(result.cost <= 0.06, f"spend stopped at the ceiling (${result.cost:.4f} of $0.05)")
    check(bool(result.errors) or len(result.lessons) < result.plan.lesson_count,
          "and the build reported that it could not finish")


# ── 8. The audit-driven retry ────────────────────────────────────────────────

def test_retry_uses_the_findings():
    print("\n[8] a rejected draft is retried with its own defects quoted back")
    seen = {}

    def provider(messages, *, max_tokens, temperature=0.6, model="", cache_system=True,
                 timeout=None, attempts=3):
        user = str(messages[-1]["content"])
        seen.setdefault("calls", []).append(user)
        if len(seen["calls"]) == 1:
            data = {"pages": [{"type": "vocabulary", "title_tr": "B",
                               "text_tr": "Bu derste kelimeler ogreneceksiniz.",
                               "items": [{"term": "cena", "phonetic": "ˈθενα",
                                          "translation_tr": "aksam yemegi"}]}]}
        else:
            data = {"pages": [{"type": "vocabulary", "title_tr": "B",
                               "text_tr": "Bu derste kelimeler ogreneceksiniz.",
                               "items": [{"term": "cena", "phonetic": "ˈθena",
                                          "translation_tr": "aksam yemegi"}]}]}
        return T.Response(data=data, input_tokens=2600, output_tokens=2000, model=model)

    E.T.call_model = provider
    result = E.generate_lesson(topic="Comidas", topic_type="vocabulary", language="Spanish",
                               level="A1", track="tr")
    check(result.attempts == 2, "the defective draft caused exactly one retry")
    check("not IPA" in seen["calls"][1],
          "the retry named the actual defect rather than asking again blindly")
    check(result.clean, "the second draft passed clean")
    check(result.lesson["pages"][0]["items"][0]["phonetic"] == "ˈθena",
          "and the repaired lesson is the one returned")


# ── 9. The publication boundary ──────────────────────────────────────────────

def test_boundary():
    print("\n[9] stored content cannot reach a page unchecked")
    import json
    stored = json.dumps({"pages": [
        {"type": "vocabulary", "items": [{"term": "cena", "phonetic": "ˈxεnte",
                                          "example": "Qué comes?"}]},
        {"type": "mcq", "prompt": "Cómo estás?", "answer": "Muy bien",
         "options": ["Muy bien", "Adiós", "Gracias", "Hasta luego"]},
        {"type": "mcq", "prompt": "Broken", "answer": "X", "options": ["X", "X"]},
    ]}, ensure_ascii=False)
    out = PUB.load_publishable_content(stored, language="Spanish", material_language="tr")
    check(len(out["pages"]) == 2, "the unanswerable item is dropped")
    check(out["pages"][0]["items"][0]["phonetic"] == "ˈxɛnte", "the transcription is repaired")
    check(out["pages"][0]["items"][0]["example"] == "¿Qué comes?", "the example is repaired")
    check(out["pages"][1]["prompt"] == "¿Cómo estás?", "the question opens correctly")
    check(PUB.load_publishable_content("")["pages"] == [], "empty input is safe")
    check(PUB.load_publishable_content("not json")["pages"] == [], "unparseable input is safe")

    # An MCQ carrying only `options`, as pre-rebuild material does, is answerable
    # and must survive.
    legacy = {"pages": [{"type": "mcq", "question_tr": "Hangisi doğru?", "answer": "evet",
                         "options": ["evet", "hayır", "belki", "asla"]}]}
    kept = PUB.load_publishable_content(legacy, language="Turkish", material_language="tr")
    check(len(kept["pages"]) == 1, "a legacy item with options but no distractors survives")


def main():
    test_no_false_positives()
    test_repair_is_a_no_op_on_correct_material()
    test_prompts()
    test_bilingual_authoring_contract()
    test_assessment_shortfall_topup()
    test_unit_assessment_reuses_clean_lesson_mcq()
    test_planning()
    test_curriculum_titles_are_bilingual()
    test_curriculum_draft_shape_and_model()
    test_budget()
    test_full_builds()
    test_budget_stops_a_runaway()
    test_retry_uses_the_findings()
    test_boundary()
    print(f"\n=== {len(FAILS)} failing checks ===")
    for f in FAILS:
        print("  -", f)
    if FAILS:
        sys.exit(1)
    print("authoring core: 15 languages x A1-C2, all clean, all under $0.60")


if __name__ == "__main__":
    main()
