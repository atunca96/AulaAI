"""The instructional-track lock, English as a taught language, and the question contract.

Three things are asserted here, all deterministically and without a single
paid model call:

1. ROUTING — which instructional track a course publishes, for every taught
   language, under every interface language. The English/Turkish pair is locked
   by what the course teaches; every other language still follows the session.
   This is the property that a UI-language switch must not be able to break, so
   it is tested at the resolver every caller goes through rather than at each
   caller.

2. ISOLATION — the special pair changes the material prompt for English and
   Turkish and for nothing else. The general multilingual prompt is compared
   against the version in git HEAD~ semantics by structure: if the special path
   ever leaks into Spanish, the general two-track section disappears and this
   fails.

3. THE QUESTION CONTRACT — that the system half is genuinely class-invariant
   (which is what makes it cacheable) and that the per-request half carries
   everything that varies. A regression here is silent: the prompt still works,
   it just stops being cached and costs several times more.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAILS = []


def check(condition, label):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        FAILS.append(label)


# ── 1. Routing ────────────────────────────────────────────────────────────────
def test_routing():
    print("\n[1] instructional-track routing")
    from services.language_profiles import (
        TAUGHT_LANGUAGES, resolve_track, locked_track, is_special_pair,
        normalize_language, track_notice,
    )

    check("English" in TAUGHT_LANGUAGES, "English is an offered taught language")
    check("Turkish" in TAUGHT_LANGUAGES, "Turkish is an offered taught language")
    check(len(TAUGHT_LANGUAGES) == 15, "15 taught languages offered")

    # The pair is locked whatever the session asks for, whatever is stored.
    for ui in ("tr", "en", None, "de", ""):
        for declared in ("tr", "en", None):
            check(resolve_track("English", ui, declared) == "tr",
                  f"English course -> tr track (ui={ui!r}, declared={declared!r})")
            check(resolve_track("Turkish", ui, declared) == "en",
                  f"Turkish course -> en track (ui={ui!r}, declared={declared!r})")

    # Every other language still follows the session, then the stored value.
    ordinary = [l for l in TAUGHT_LANGUAGES if l not in ("English", "Turkish")]
    for language in ordinary:
        check(resolve_track(language, "tr", "en") == "tr", f"{language}: ui tr wins")
        check(resolve_track(language, "en", "tr") == "en", f"{language}: ui en wins")
        check(resolve_track(language, None, "en") == "en", f"{language}: stored track used when no ui")
        check(resolve_track(language, None, None) == "tr", f"{language}: default track")
        check(locked_track(language) is None, f"{language} is not locked")
        check(not is_special_pair(language), f"{language} is not a special pair")

    # Names the rest of the system actually produces must resolve.
    for spelling in ("english", "İngilizce", "ingilizce", "EN"):
        check(normalize_language(spelling) == "English", f"{spelling!r} normalises to English")
    for spelling in ("turkish", "Türkçe", "turkce", "TR"):
        check(normalize_language(spelling) == "Turkish", f"{spelling!r} normalises to Turkish")
    check(normalize_language("Detecting...") == "", "'Detecting...' is not a taught language")
    check(resolve_track("Detecting...", "en", "tr") == "en", "undetected language still follows the session")

    # The lecturer is told, in their own interface language.
    check("Turkish" in track_notice("English", "en"), "English notice names Turkish (EN copy)")
    check("Türkçe" in track_notice("English", "tr"), "English notice names Türkçe (TR copy)")
    check("English" in track_notice("Turkish", "en"), "Turkish notice names English (EN copy)")
    check(track_notice("Spanish", "en") == "", "no notice for an ordinary language")


# ── 2. English as a first-class taught language ───────────────────────────────
def test_english_is_first_class():
    print("\n[2] English wired end to end, not just into a dropdown")
    from services.cefr_reference import LANGUAGE_CEFR_STANDARDS, get_cefr_conditioning
    from services.language_data import ALPHABETS, LANGUAGE_PEDAGOGY, get_reference_prompt, get_pedagogical_guidelines

    check("English" in LANGUAGE_CEFR_STANDARDS, "English has CEFR authority standards")
    check("English" in ALPHABETS, "English has alphabet reference data")
    check(len(ALPHABETS["English"]["items"]) == 26, "English alphabet is complete")
    check("English" in LANGUAGE_PEDAGOGY, "English has pedagogical guidance")
    check(len(get_reference_prompt("English")) > 200, "English reference prompt is non-empty")

    guidance = get_pedagogical_guidelines("English", "A1")
    check("TARGET LANGUAGE SPECIFICS (English)" in guidance, "English pedagogy reaches the prompt")
    check("article" in guidance.lower(), "English guidance names the article trap")
    check(len(get_cefr_conditioning("English", "B1")) > 500, "English CEFR conditioning is substantive")

    # Turkish, the other half of the pair, must be equally complete.
    for key, container, label in (
        ("Turkish", LANGUAGE_CEFR_STANDARDS, "CEFR standards"),
        ("Turkish", ALPHABETS, "alphabet data"),
        ("Turkish", LANGUAGE_PEDAGOGY, "pedagogy"),
    ):
        check(key in container, f"Turkish has {label}")


# ── 3. Special-pair isolation ─────────────────────────────────────────────────
def test_special_pair_isolation():
    print("\n[3] the special pair changes English and Turkish, and nothing else")
    from services.material_generation_prompt import build_material_prompts
    from services.special_pair_profile import profile_for

    general_marker = "ENGLISH TRACK: title, text, explanation"
    ordinary = ["Spanish", "German", "French", "Italian", "Portuguese", "Russian",
                "Chinese", "Japanese", "Arabic", "Dutch", "Swedish", "Korean", "Greek"]
    for language in ordinary:
        sys_p, _ = build_material_prompts(language=language, level="A1", topic="T",
                                          topic_type="grammar", official_institution="I")
        check(general_marker in sys_p, f"{language} keeps the general two-track section")
        check("<taught_pair>" not in sys_p, f"{language} gets no special-pair section")
        check(profile_for(language) is None, f"{language} has no special-pair profile")

    en_p, _ = build_material_prompts(language="English", level="A1", topic="Articles",
                                     topic_type="grammar", official_institution="I")
    check(general_marker not in en_p, "English replaces the general two-track section")
    check("<taught_pair>" in en_p, "English gets the contrastive pair section")
    check("TURKISH TRACK" in en_p and "PUBLISHED INSTRUCTIONAL TRACK" in en_p,
          "English publishes the Turkish track")
    check("Turkish-speaking learners of English" in en_p, "English names its audience")

    tr_p, _ = build_material_prompts(language="Turkish", level="A1", topic="Vowel Harmony",
                                     topic_type="grammar", official_institution="I")
    check("ENGLISH TRACK" in tr_p and "PUBLISHED INSTRUCTIONAL TRACK" in tr_p,
          "Turkish publishes the English track")
    check("vowel harmony" in tr_p.lower(), "Turkish names its contrastive anchors")

    # Everything the pipeline depends on downstream must survive the swap.
    for name, prompt in (("English", en_p), ("Turkish", tr_p)):
        for section in ("<output_schema>", "<claim_scope>", "<mcq_quality>",
                        "<final_same_pass_check>", "<linguistic_truth>"):
            check(section in prompt, f"{name} keeps {section}")


# ── 4. The question contract ──────────────────────────────────────────────────
def test_question_contract():
    print("\n[4] question contract: invariant system half, per-request user half")
    from services import question_contract as qc
    from services.cefr_reference import get_cefr_conditioning
    from services.language_data import get_pedagogical_guidelines

    def system_for(language="Spanish", level="A1"):
        return qc.build_system_prompt(
            language=language, level=level,
            cefr_guidance=get_cefr_conditioning(language, level),
            pedagogy_guidance=get_pedagogical_guidelines(language, level),
        )

    base = system_for()
    check(system_for() == base, "system prompt is deterministic")

    # The whole point: two different topics in the same class must send the same
    # prefix, or the provider has nothing to cache.
    users = []
    for topic, count, focus in (("Greetings", 13, None), ("Ser vs Estar", 18, "focus_grammar"),
                                ("Market Dialogue", 10, "focus_lexicon")):
        users.append(qc.build_user_prompt(
            language="Spanish", level="A1", topic_title=topic, topic_type="vocabulary",
            gen_count=count, content_str="SOURCE", variety_focus="V",
            focus_directive=focus, request_id="r"))
    check(len(set(users)) == 3, "user prompts differ per request")

    for topic in ("Greetings", "Ser vs Estar"):
        check(topic not in base, f"topic {topic!r} never enters the system prompt")
    for token in ("focus_grammar", "SUB-BATCH FOCUS", "UNIQUE_REQUEST_ID", "SOURCE MATERIAL"):
        check(token not in base, f"{token!r} never enters the system prompt")
    check(not re.search(r"\bEXACTLY 13\b", base), "batch size never enters the system prompt")

    # Different class, different prefix — that is legitimate and expected.
    check(system_for("German", "A1") != base, "system prompt varies by taught language")
    check(system_for("Spanish", "B2") != base, "system prompt varies by level")

    # The per-request half must carry what the system half gave up.
    u = users[1]
    check("Ser vs Estar" in u, "user prompt carries the topic")
    check("EXACTLY 18" in u, "user prompt carries the batch size")
    check("SUB-BATCH FOCUS" in u, "user prompt carries the focus directive")
    check("SOURCE" in u, "user prompt carries the source material")

    # Rolling history and reference data ride in the user half too.
    hist = qc.build_user_prompt(
        language="Spanish", level="A1", topic_title="T", topic_type="v", gen_count=13,
        content_str="S", variety_focus="V", forbidden_prompts=["¿Qué tal?"],
        forbidden_answers=["hola"], reference_data="REFDATA", request_id="r")
    check("¿Qué tal?" in hist and "hola" in hist, "rolling history reaches the model")
    check("REFDATA" in hist, "reference data reaches the model")

    # Every rule the old prompt enforced must still be stated once.
    required = [
        "100% in {language}".replace("{language}", "Spanish"),
        "BLANK PRESERVATION", "COMPLETE LINGUISTIC COMBINATION", "SCENARIO TRANSFER ONLY",
        "[RULE]", "[CONTRAST]", "SYMMETRIC SCRUTINY", "HOMOGENEITY", "LENGTH SYMMETRY",
        "ZERO INFERENCE LEAPS", "NO ARITHMETIC", "STRICT CONFIDENCE THRESHOLD",
        "cognate", "duplicates", "near-miss",
    ]
    for phrase in required:
        check(phrase in base, f"contract still states: {phrase}")

    # ...and once is the point. The old prompt printed the valency mandate six
    # times and the Gate A/B block twice, in both messages.
    check(base.count("SCENARIO TRANSFER ONLY") == 1, "scenario-transfer rule stated once")
    check(base.count("SYMMETRIC SCRUTINY") == 1, "symmetric-scrutiny rule stated once")

    # Budgets are derived, not static.
    check(qc.overproduction_count(10) == 13, "10 requested -> 13 generated")
    check(qc.overproduction_count(20) == 26, "20 requested -> 26 generated")
    check(qc.overproduction_count(3) == 10, "small batches keep a workable floor")
    for n in (5, 10, 15, 20):
        c = qc.overproduction_count(n)
        check(c > n, f"overproduction margin kept at count={n}")
        check(qc.output_token_budget(c) >= c * qc.TOKENS_PER_ITEM,
              f"output budget covers {c} items in full")
    # The old rule was a flat 250/item against a 5000 ceiling, so an ordinary
    # activity sat in the slowest timeout tier for no reason.
    check(qc.output_token_budget(13) < 5000, "an ordinary batch is well under the old flat ceiling")
    check(qc.output_token_budget(13) <= 4000, "an ordinary batch stays out of the slowest timeout tier")
    check(qc.output_token_budget(500) == 6000, "an absurd batch is still capped")


# ── 5. The reader mirrors the backend ─────────────────────────────────────────
def test_reader_mirrors_backend():
    print("\n[5] the in-app reader resolves the track the same way the backend does")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = open(os.path.join(root, "public", "js", "app.js"), encoding="utf-8").read()

    check("const AulaLang" in app, "front end has a single language-architecture module")
    check("AulaLang.resolveTrack(_taught, currentLang, _declaredTrack)" in app,
          "reader asks the resolver rather than reading currentLang directly")
    check("AulaLang.lockedTrack(" in app, "PDF export consults the lock")
    check("AulaLang.notice(" in app, "the lecturer is shown the rule before generating")
    check("english: 'tr'" in app and "turkish: 'en'" in app,
          "front-end lock matches services/language_profiles.py")

    # The old unconditional "interface language wins" line must be gone, or the
    # lock is bypassable from the reader.
    check("? currentLang\n      : ((_declaredTrack" not in app,
          "unconditional ui-language override removed from the reader")


def main():
    test_routing()
    test_english_is_first_class()
    test_special_pair_isolation()
    test_question_contract()
    test_reader_mirrors_backend()
    print(f"\n=== {len(FAILS)} failing checks ===")
    if FAILS:
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("language pair, English support and question contract: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
