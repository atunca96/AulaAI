"""The pronunciation column has no holes in it.

A lesson may omit a transcription it is not sure of — an absent transcription is
honest, an invented one is a factual error a learner cannot detect. What the
reader must never see is a column where most rows carry IPA and a few are blank,
which is indistinguishable from a rendering bug. A shipped A1 book had 25 such
holes in 474 rows.

No paid call is made here: the provider is replaced by a fixture.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")

from services import bilingual_finisher as bf  # noqa: E402

FAILS = []


def check(cond, label):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILS.append(label)


def test_validator():
    print("\n[1] a returned value is IPA, or it is not written")
    for value, term, expected, why in [
        ("[ˈθine]", "cine", True, "IPA with a stress mark is accepted"),
        ("[ˈnweβe]", "nueve", True, "so is one with a non-orthographic symbol"),
        ("[ˈzdrastvujtʲe]", "здравствуйте", True, "across scripts"),
        ("[kæt]", "cat", True, "and in English"),
        ("[sinema anlamında]", "cine", False, "an instructional-language gloss is refused"),
        ("peynir", "queso", False, "bare prose is refused"),
        ("cine", "cine", False, "an echo of the headword is refused"),
        ("[Cine]", "cine", False, "capitals are prose, not notation"),
        ("[ˈkasa, evi]", "casa", False, "so is sentence punctuation"),
        ("[]", "x", False, "empty brackets fill nothing"),
        ("[sol]", "sol", False, "plain ASCII with no IPA-only symbol stays blank"),
    ]:
        check(bf._valid_transcription(value, term) is expected, why)


def test_backfill():
    print("\n[2] the holes close, and nothing else moves")
    content_a = {"pages": [{"type": "vocabulary", "items": [
        {"term": "cine", "phonetic": ""},
        {"term": "casa", "phonetic": "[ˈkasa]"},
        {"term": "el zumo de naranja"},
    ]}]}
    content_b = {"pages": [{"type": "vocabulary", "items": [
        {"term": "cine"}, {"term": "nueve"},
    ]}]}
    tdl = [("t1", "A", content_a), ("t2", "B", content_b)]

    check(sorted(t for t, _ in bf._collect_phonetic_gaps(content_a)) ==
          ["cine", "el zumo de naranja"], "only entries without a transcription are collected")

    calls = []

    def fixture(prompt):
        calls.append(prompt)
        return {"map": {"cine": "[ˈθine]", "nueve": "[ˈnweβe]",
                        "el zumo de naranja": "el zumo de naranja"}}

    real, bf._call_openrouter = bf._call_openrouter, fixture
    try:
        filled = bf.backfill_missing_phonetics(tdl, "Spanish")
    finally:
        bf._call_openrouter = real

    items_a = content_a["pages"][0]["items"]
    items_b = content_b["pages"][0]["items"]
    check(len(calls) == 1, "one batched call for the whole course, not one per lesson")
    check(sorted(l[2:] for l in calls[0].split("\n") if l.startswith("- ")) ==
          ["cine", "el zumo de naranja", "nueve"], "each distinct term is requested once")
    check(items_a[0]["phonetic"] == "[ˈθine]", "a hole is filled")
    check(items_b[0]["phonetic"] == "[ˈθine]", "including in another lesson sharing the term")
    check(items_a[1]["phonetic"] == "[ˈkasa]", "an existing transcription is left alone")
    check(not items_a[2].get("phonetic"), "a rejected value writes nothing rather than prose")
    check(filled == 3, "the count reports entries filled")


def test_no_call_without_gaps():
    print("\n[3] a complete course costs nothing")
    calls = []

    def fixture(prompt):
        calls.append(prompt)
        return {}

    real, bf._call_openrouter = bf._call_openrouter, fixture
    try:
        filled = bf.backfill_missing_phonetics(
            [("t", "T", {"pages": [{"items": [{"term": "a", "phonetic": "[a]"}]}]})], "Spanish")
    finally:
        bf._call_openrouter = real
    check(filled == 0 and not calls, "no gaps means no provider call at all")


def test_contract_is_consistent():
    print("\n[4] the generation contract no longer contradicts itself")
    from services.material_generation_prompt import build_material_prompts
    sys_p, _ = build_material_prompts(language="Spanish", level="A1", topic="T",
                                      topic_type="phonetics", official_institution="X")
    check("omit `phonetic`" in sys_p, "omission is still allowed where the transcription is uncertain")
    check("varies between standard varieties" in sys_p or "accepted standard varieties" in sys_p,
          "but variation between standards is explicitly not a reason to omit")
    check("has a non-empty `phonetic` value" not in sys_p,
          "the final check no longer demands what the integrity rule forbids")


if __name__ == "__main__":
    test_validator()
    test_backfill()
    test_no_call_without_gaps()
    test_contract_is_consistent()
    print(f"\n=== {len(FAILS)} failing checks ===")
    if FAILS:
        for f in FAILS:
            print("  -", f)
        sys.exit(1)
    print("phonetic backfill: all checks passed")
