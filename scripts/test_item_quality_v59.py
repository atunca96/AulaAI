"""Distractor plausibility, option-set integrity and target-language orthography.

Three defects this suite pins, all of them things a learner sees on the page:

  1. An item that arrived short of distractors was completed from whatever the
     batch happened to contain at roughly the right length — a greeting landing
     among verb forms, or the key itself with an accent knocked off. Completion
     is now ranked by fit, and the widest pass is still the historical length
     band, so nothing that could be completed before fails to complete now.

  2. Every rule about the OPTION SET was evaluated before the option set
     existed: before supplementation, before deduplication and before the
     language calibrators rewrote the text. The set the learner reads was never
     itself checked. `audit_option_set` is that check, and it repairs by
     swapping a borrowed option before it rejects.

  3. Spanish published questions as "Cómo estás?". Omitting ¿ is not a style
     choice in Spanish and the learner copies it. The repair is additive and
     idempotent, and touches only fields the schema defines as target-language —
     a Turkish rationale in a Spanish course ends in '?' too and takes no ¿.

Everything here is deterministic: no provider call is made anywhere in the file.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")
os.environ["AULAAI_DATA_DIR"] = tempfile.mkdtemp(prefix="aulaai-itemq-")
import database  # noqa: E402
database.DB_PATH = os.path.join(os.environ["AULAAI_DATA_DIR"], "aula.db")
database.init_db()

from services import assessment_validation as av  # noqa: E402
from services import question_contract as qc  # noqa: E402
from services import ai_engine as ae  # noqa: E402
from services import material_quality_guard as mqg  # noqa: E402
from services import publication_invariants as pi  # noqa: E402

FAILS = []


def check(cond, label):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        FAILS.append(label)


# ── 1. The key picked out by its shape ────────────────────────────────────────

def test_key_length_outlier():
    print("\n[1] a key that is chosen by its length")

    balanced = ["La cuenta, por favor", "Otra vez", "Buenas tardes", "Hasta mañana"]
    check(not av.key_length_outlier("La cuenta, por favor", balanced),
          "a key a little longer than its distractors is left alone")

    elaborated = ["Por favor, ¿podría traerme la cuenta cuando pueda?",
                  "La cuenta", "Un café", "Otra vez"]
    check(av.key_length_outlier(elaborated[0], elaborated),
          "a key twice the size of everything beside it is refused")

    odd_one_out = ["Sí", "No lo he entendido bien", "No estoy de acuerdo contigo",
                   "No sé qué decirte ahora"]
    check(av.key_length_outlier("Sí", odd_one_out),
          "a key that is the one short option among three long ones is refused")

    check(not av.key_length_outlier("hablo", ["hablo", "hablas", "habla", "hablan"]),
          "a paradigm of four inflections is never a length outlier")

    item = {"prompt": "Completa: Yo _____ al mercado.", "answer": "Sí",
            "distractors": odd_one_out[1:], "options": odd_one_out,
            "why": "x", "why_tr": "y"}
    problems = av.violations(item, instructional_track="tr")
    check("key_length_outlier" in problems, "the outlier reaches violations()")
    check(av.is_fatal("key_length_outlier"), "and is fatal — it is not a question")


# ── 2. Choosing a borrowed distractor ─────────────────────────────────────────

def test_distractor_fit():
    print("\n[2] which borrowed option actually works as a distractor")

    stem = "Completa: Nosotros _____ en el centro todos los días."
    key = "comemos"

    check(av.distractor_fit(key, "comemos", stem=stem) is None,
          "the key itself is never a distractor")
    check(av.distractor_fit(key, "cómemos", stem=stem) is None,
          "the key with a diacritic added is a typo, not a belief")
    check(av.distractor_fit(key, "comes", stem=stem, chosen=["comes"]) is None,
          "an option already chosen is not chosen twice")
    check(av.distractor_fit(key, "centro", stem=stem) is None,
          "a word already sitting in the carrier sentence is not an alternative")
    check(av.distractor_fit(key, "centro", stem=stem, strict=False) is not None,
          "…but the wide pass still allows it rather than losing the item")
    check(av.distractor_fit(key, "buenos días, ¿qué tal?", stem=stem) is None,
          "a greeting is not an alternative to a verb form")
    check(av.distractor_fit(key, "traducción (comer)", stem=stem, strict=False) is None,
          "a bracketed annotation is never offered as an option")

    ranked = sorted(
        (av.distractor_fit(key, c, stem=stem), c)
        for c in ("comen", "hasta luego mañana", "comer")
        if av.distractor_fit(key, c, stem=stem) is not None
    )
    check([c for _f, c in ranked][:2] == ["comen", "comer"],
          "inflections of the same verb rank above everything else")


# ── 3. The set the learner actually reads ─────────────────────────────────────

def test_option_audit():
    print("\n[3] the option set is judged once it is final")

    check(ae.audit_option_set("¿Qué comes?", "hablo", ["hablas", "habla", "hablan"]) == [],
          "a clean paradigm passes the audit")

    spelling_slip = ae.audit_option_set("Ella es _____.", "francés",
                                        ["francesa", "frances", "franceses"])
    check("mixed_spelling_variants" in spelling_slip,
          "one option that is another one misspelt is caught on the final set")

    duplicate = ae.audit_option_set("Completa: _____", "café", ["té", "café", "agua"])
    check("duplicate_options" in duplicate, "the key repeated as a distractor is caught")

    giveaway = ae.audit_option_set("¿Qué palabra lleva 'h' muda?", "hotel",
                                   ["gato", "mesa", "casa"])
    check(any(v.startswith("feature_only_in_key:") for v in giveaway),
          "a feature only the key carries is caught on the final set")

    # The audit must ask the same questions violations() asks, so the two cannot
    # drift into disagreeing about what is publishable.
    for name in ("duplicate_options", "mixed_spelling_variants", "key_length_outlier",
                 "feature_only_in_key:"):
        check(name in ae._DEFERRED_TO_OPTION_AUDIT,
              f"{name!r} is deferred to the audit rather than judged twice")


# ── 4. Supplementation end to end ─────────────────────────────────────────────

TASKS = ["sentence_application", "grammatical_discrimination", "situational_decision",
         "communicative_collocation", "dialogue_comprehension"]


def _bank_item(index, prompt, answer, distractors):
    return {"type": "mcq", "prompt": prompt, "answer": answer,
            "distractors": list(distractors), "translation_en": "EN " + prompt,
            "translation_tr": "TR " + prompt,
            "why": f"'{answer}' is the taught form here ({index}).",
            "why_tr": f"'{answer}' burada ogretilen bicimdir ({index}).",
            "evidence": f"line {index}: {answer}",
            "material_section": f"Part {index % 3 + 1}",
            "cognitive_task": TASKS[index % len(TASKS)]}


def test_short_items_are_completed_well():
    print("\n[4] an item that arrives short of distractors")

    # Every item but the first is a full, well-formed item; the first arrives
    # with one distractor and must borrow two. The pool deliberately contains
    # both a homogeneous candidate and an obviously wrong-category one.
    bank = [
        _bank_item(0, "Nosotros _____ en el centro todos los días.", "comemos", ["coméis"]),
        _bank_item(1, "Mi hermana _____ café antes de salir de casa.", "toma",
                   ["tomas", "tomar", "tomaron"]),
        _bank_item(2, "Los sábados yo _____ al mercado con mi vecina.", "voy",
                   ["vas", "ir", "fueron"]),
        _bank_item(3, "¿Qué dices al llegar por la mañana a la oficina?", "buenos días",
                   ["buenas noches", "hasta luego", "adiós"]),
        _bank_item(4, "Un compañero te da las gracias. ¿Cómo respondes con naturalidad?",
                   "de nada", ["con permiso", "buen provecho", "hasta pronto"]),
    ]

    def provider(messages, **kw):
        return {"data": [json.loads(json.dumps(b)) for b in bank]}

    ae._call_ai = provider
    ae.is_ai_available = lambda: True
    content = {"pages": [{"title": "Vocab", "type": "vocabulary", "items": [
        {"term": "comen"}, {"term": "comer"}, {"term": "buenos días"},
    ]}]}

    got = ae.ai_generate_questions("Rutinas", "grammar", content, "Spanish",
                                   count=4, level="A1", material_language="tr")
    check(len(got) == 4, "the batch still assembles the requested count")

    completed = [q for q in got if q.get("answer") == "comemos"]
    check(len(completed) == 1, "the short item was completed rather than dropped")
    if completed:
        opts = completed[0]["options"]
        check(len(opts) == 4 and len(set(opts)) == 4, "it reaches the learner with four distinct options")
        check(ae.audit_option_set(completed[0]["prompt"], completed[0]["answer"],
                                  completed[0]["distractors"]) == [],
              "the completed set passes the audit it was completed under")
        borrowed = {o for o in opts if o not in ("comemos", "coméis")}
        greetings = {"buenos días", "de nada", "hasta luego", "buenas noches",
                     "con permiso", "buen provecho", "hasta pronto", "adiós"}
        check(len(borrowed) == 2 and not (borrowed & greetings),
              f"it borrowed single verb forms, never a greeting (got {sorted(borrowed)})")
        check(all(len(b.split()) == 1 for b in borrowed),
              "and kept the option set to one word each, as the key is")

    for q in got:
        check(len(q.get("distractors") or []) == 3 and len(q.get("options") or []) == 4,
              f"'{q.get('answer')}' carries three distractors and four options")


# ── 5. Obligatory target-language punctuation ─────────────────────────────────

def test_target_orthography():
    print("\n[5] punctuation the taught language requires")
    r = mqg.repair_target_orthography

    check(r("Cómo estás?", "Spanish") == "¿Cómo estás?", "a bare Spanish question gets its ¿")
    check(r("Qué bonito!", "Spanish") == "¡Qué bonito!", "and an exclamation its ¡")
    check(r("¿Cómo estás?", "Spanish") == "¿Cómo estás?", "correct Spanish is returned unchanged")
    check(r("Llegas a la recepción. Cuál es la frase?", "Spanish")
          == "Llegas a la recepción. ¿Cuál es la frase?",
          "the mark opens the question, not the paragraph")
    check(r("Perdone, dónde está el baño?", "Spanish") == "Perdone, ¿dónde está el baño?",
          "a courtesy opener stays outside the question")
    check(r("Si tu amigo dice: «Cómo estás?», qué respondes?", "Spanish")
          == "Si tu amigo dice: «¿Cómo estás?», ¿qué respondes?",
          "a quoted question opens inside its own quotation marks")
    check(r("Completa: Nosotros _____ en el centro.", "Spanish")
          == "Completa: Nosotros _____ en el centro.",
          "a statement is not turned into a question")
    check(r("Nasılsın?", "Turkish") == "Nasılsın?", "a language without the convention is untouched")
    check(r(r(r("Cómo estás?", "Spanish"), "Spanish"), "Spanish") == "¿Cómo estás?",
          "the repair is idempotent")

    item = {"type": "mcq", "prompt": "Cómo pides ayuda?", "answer": "Podría ayudarme?",
            "distractors": ["Dame eso ya", "Qué pasa", "Oye, ven aquí"],
            "options": ["Dame eso ya", "Podría ayudarme?", "Qué pasa", "Oye, ven aquí"],
            "translation_tr": "Nasıl yardım istersin?", "why_tr": "Bu kibar biçimdir.",
            "why": "This is the polite form."}
    out = pi.apply_assessment_invariants([item], language="Spanish", material_language="tr")
    check(len(out) == 1, "the repaired item survives the publication boundary")
    if out:
        published = out[0]
        check(published["prompt"] == "¿Cómo pides ayuda?", "the stem is repaired")
        check(published["answer"] == "¿Podría ayudarme?", "the key is repaired")
        check(published["answer"] in published["options"],
              "the key and the option list are repaired as one, so the key is still found")
        check(published["translation_tr"] == "Nasıl yardım istersin?"
              and published["why_tr"] == "Bu kibar biçimdir.",
              "the instructional track is not given Spanish punctuation")

    lesson = {"pages": [{
        "type": "vocabulary", "title": "Saludos", "text": "Is this right?",
        "items": [{"term": "ayudar", "example": "Me puedes ayudar?",
                   "translation_tr": "Yardım eder misin?"}],
        "dialogue": [{"speaker": "Ana", "text": "Cómo estás?", "line_tr": "Nasılsın?"}],
    }]}
    done = pi.apply_target_orthography(lesson, language="Spanish")
    page = done["pages"][0]
    check(page["items"][0]["example"] == "¿Me puedes ayudar?", "a lesson example is repaired")
    check(page["dialogue"][0]["text"] == "¿Cómo estás?", "a dialogue turn is repaired")
    check(page["items"][0]["translation_tr"] == "Yardım eder misin?"
          and page["text"] == "Is this right?",
          "instructional prose beside it is left alone")

    tr_lesson = json.loads(json.dumps(lesson))
    check(pi.apply_target_orthography(tr_lesson, language="Turkish") == json.loads(json.dumps(lesson)),
          "a Turkish course is unchanged by the Spanish convention")


# ── 6. The contract states the rules the audit measures ───────────────────────

def test_contract_states_the_rules():
    print("\n[6] the generation contract carries the new item-writing rules")
    system = qc.build_system_prompt(language="Spanish", level="A1")
    for marker in ("ONE VARYING DIMENSION", "ONE MISCONCEPTION EACH", "FRAME FIT",
                   "NEGATIVE AND EXCLUSIVE STEMS", "ORTHOGRAPHIC CONVENTION"):
        check(marker in system, f"{marker} is stated to the generator")
    check(system.count("ONE VARYING DIMENSION") == 1,
          "and stated once — the contract is not re-bloating by restatement")
    approx = len(system) // 4
    check(approx < 6000, f"the shared system contract stays lean (~{approx} tokens)")

    from services.material_generation_prompt import build_material_prompts
    material_system, _user = build_material_prompts(
        language="Spanish", level="A1", topic="Saludos", topic_type="vocabulary",
        official_institution="Instituto Cervantes")
    for marker in ("One varying dimension", "One misconception each", "Frame fit",
                   "Orthographic convention"):
        check(marker in material_system, f"lesson-internal MCQs are held to it too: {marker!r}")


def main():
    test_key_length_outlier()
    test_distractor_fit()
    test_option_audit()
    test_short_items_are_completed_well()
    test_target_orthography()
    test_contract_states_the_rules()
    print(f"\n=== {len(FAILS)} failing checks ===")
    for f in FAILS:
        print(f"  - {f}")
    if FAILS:
        sys.exit(1)
    print("item quality (distractors, option sets, orthography): all checks passed")


if __name__ == "__main__":
    main()
