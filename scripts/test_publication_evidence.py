#!/usr/bin/env python3
"""Regression tests for lesson-internal evidence relationships.

Every fixture is synthetic and uses invented target-language forms, so nothing
here can pass by recognising a real language. The point is that the detectors
work from STRUCTURE — token counts, transcription reuse, digit coverage,
polarity cues between the two instructional tracks — and never from knowing what
any target-language string means.

These cover failure CLASSES, not the specific production sentences that exposed
them: contradiction between prose and its own table, an exception known in one
section and missing in a parallel one, a phrase transcribed as only its first
word, prose disagreeing with the published transcription, translation tracks
that state different things, and answer-key rationales escaping review.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.publication_evidence import (  # noqa: E402
    FLAG_COVERAGE_GAP,
    FLAG_THIN_GENERALIZATION,
    FLAG_IPA_BORROWED,
    FLAG_PHRASE_IPA_PARTIAL,
    FLAG_PROSE_IPA_CONFLICT,
    FLAG_RATIONALE_CLAIM,
    FLAG_TRANSLATION_NUMERAL,
    FLAG_TRANSLATION_POLARITY,
    collect_coverage_gaps,
    collect_evidence_risks,
    collect_phonetic_integrity_risks,
    collect_prose_phonetic_conflicts,
    collect_rationale_claims,
    collect_thin_generalizations,
    collect_translation_mismatches,
)
from services.publication_invariants import (  # noqa: E402
    MAX_REVIEWABLE_CLAIMS,
    apply_assessment_invariants,
    apply_publication_invariants,
    build_claim_review_request,
    collect_reviewable_claims,
    find_absolute_claims,
    hedge_absolute_claims,
    normalize_claim_record,
)

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        FAILURES.append(f"{name}: {detail}")
        print(f"  FAIL  {name} :: {detail}")


def flags(risks):
    out = set()
    for r in risks:
        out |= set(r.get("quantifiers") or [])
    return out


# ── 7. Phrase-level IPA cannot silently contain only the headword ───────────

def test_phrase_ipa_partial():
    lesson = {"pages": [{
        "type": "vocabulary",
        "items": [
            {"term": "zolan", "phonetic": "[ˈzolan]", "translation_tr": "ne"},
            # Three-word phrase carrying a single-word transcription.
            {"term": "zolan mira tev", "phonetic": "[ˈzolan]", "translation_tr": "bu ne"},
        ],
    }]}
    risks = collect_phonetic_integrity_risks(lesson)
    check("7 partial phrase transcription detected", FLAG_PHRASE_IPA_PARTIAL in flags(risks), flags(risks))
    check("7 transcription reuse from shorter term detected", FLAG_IPA_BORROWED in flags(risks), flags(risks))
    check("7 risk points at the offending field",
          any(r["path"].endswith("items.1.phonetic") for r in risks), [r["path"] for r in risks])


def test_phrase_ipa_complete_is_clean():
    lesson = {"pages": [{
        "type": "vocabulary",
        "items": [
            {"term": "zolan", "phonetic": "[ˈzolan]", "translation_tr": "ne"},
            {"term": "zolan mira tev", "phonetic": "[ˈzolan ˈmira tev]", "translation_tr": "bu ne"},
        ],
    }]}
    check("7b complete phrase transcription not flagged",
          collect_phonetic_integrity_risks(lesson) == [], "false positive")


def test_single_word_never_flagged():
    lesson = {"pages": [{"type": "vocabulary", "items": [
        {"term": "brevik", "phonetic": "[ˈbrɛvik]", "translation_tr": "ev"}]}]}
    check("7c single-word entry not flagged", collect_phonetic_integrity_risks(lesson) == [])


# ── 8. IPA / prose disagreement ─────────────────────────────────────────────

def test_prose_ipa_conflict():
    lesson = {"pages": [{
        "type": "grammar",
        "items": [{"term": "davkar", "phonetic": "[dɐfˈkar]", "translation_tr": "dil"}],
        "rules": [{
            "rule_tr": "davkar sözcüğünde vurgu ilk hecededir: [ˈdafkar] biçiminde okunur.",
        }],
    }]}
    risks = collect_prose_phonetic_conflicts(lesson, material_language="tr")
    check("8 prose transcription conflicting with table detected",
          FLAG_PROSE_IPA_CONFLICT in flags(risks), flags(risks))
    if risks:
        check("8 both transcriptions supplied as evidence",
              any("dɐfˈkar" in e for e in risks[0]["examples"]), risks[0]["examples"])


def test_prose_ipa_agreement_is_clean():
    lesson = {"pages": [{
        "type": "grammar",
        "items": [{"term": "davkar", "phonetic": "[dɐfˈkar]", "translation_tr": "dil"}],
        "rules": [{"rule_tr": "davkar sözcüğü [dɐfˈkar] biçiminde okunur."}],
    }]}
    check("8b matching prose transcription not flagged",
          collect_prose_phonetic_conflicts(lesson, material_language="tr") == [], "false positive")


# ── 5 + 6. Cross-section coverage gap / inconsistent scope ──────────────────

def test_cross_section_coverage_gap():
    """One section knows an extra case; a parallel section omits it."""
    lesson = {"pages": [
        {"type": "grammar", "rules": [{
            "rule_tr": "1 ile biten sayılarda tekil biçim, 2, 3, 4 ile bitenlerde ikinci biçim kullanılır.",
        }]},
        {"type": "grammar", "rules": [{
            "rule_tr": "1 ile biten sayılarda tekil biçim, 2, 3, 4 ile bitenlerde ikinci biçim; "
                       "ancak 11, 12, 13, 14 sayıları bu kuralın dışındadır.",
        }]},
    ]}
    risks = collect_coverage_gaps(lesson, material_language="tr")
    check("5/6 narrower parallel rule detected", FLAG_COVERAGE_GAP in flags(risks), flags(risks))
    check("5/6 the NARROWER rule is the one flagged",
          any(r["path"].startswith("pages.0") for r in risks), [r["path"] for r in risks])
    if risks:
        check("5/6 the missing cases are named in evidence",
              any("11" in e for e in risks[0]["examples"]), risks[0]["examples"])


def test_consistent_sections_not_flagged():
    lesson = {"pages": [
        {"type": "grammar", "rules": [{"rule_tr": "1 ile biten sayılarda A, 2, 3, 4 ile bitenlerde B."}]},
        {"type": "grammar", "rules": [{"rule_tr": "1 ile biten sayılarda A, 2, 3, 4 ile bitenlerde B."}]},
    ]}
    check("6b sections with identical coverage not flagged",
          collect_coverage_gaps(lesson, material_language="tr") == [], "false positive")


# ── 9. Translation correspondence ───────────────────────────────────────────

def test_translation_polarity_mismatch():
    lesson = {"pages": [{"type": "examples", "items": [
        {"term": "mira tev zolan", "example_en": "I do not have a book",
         "example_tr": "Bir kitabım var"}]}]}
    risks = collect_translation_mismatches(lesson)
    check("9 polarity mismatch between tracks detected",
          FLAG_TRANSLATION_POLARITY in flags(risks), flags(risks))


def test_translation_numeral_mismatch():
    lesson = {"pages": [{"type": "examples", "items": [
        {"term": "x", "example_en": "There are 5 books", "example_tr": "3 kitap var"}]}]}
    check("9b numeral mismatch between tracks detected",
          FLAG_TRANSLATION_NUMERAL in flags(collect_translation_mismatches(lesson)))


def test_translation_agreement_is_clean():
    lesson = {"pages": [{"type": "examples", "items": [
        {"term": "x", "example_en": "There are 5 books", "example_tr": "5 kitap var"},
        {"term": "y", "example_en": "I do not have a book", "example_tr": "Kitabım yok"},
        {"term": "z", "example_en": "I have a book", "example_tr": "Bir kitabım var"}]}]}
    check("9c matching tracks not flagged",
          collect_translation_mismatches(lesson) == [], collect_translation_mismatches(lesson))


# ── 10 + 11. Answer-key rationales ──────────────────────────────────────────

def test_rationale_social_claim_routed():
    lesson = {"pages": [{
        "type": "mcq",
        "prompt": "Which greeting?",
        "options": ["vorma", "dalno", "tesk", "brev"],
        "answer": "vorma",
        "explanation_tr": "dalno sadece yakın arkadaşlar için kullanılır; resmî ortamda asla kullanılmaz.",
    }]}
    risks = collect_rationale_claims(lesson, material_language="tr")
    check("10 categorical social rationale routed for review",
          FLAG_RATIONALE_CLAIM in flags(risks), flags(risks))
    merged = collect_reviewable_claims(lesson, material_language="tr")
    check("10 rationale reaches the single bounded review list",
          any(FLAG_RATIONALE_CLAIM in (c.get("quantifiers") or []) for c in merged),
          [c.get("quantifiers") for c in merged])
    _, payload = build_claim_review_request(merged, "Testish", "A1")
    check("10 rationale payload carries its domain",
          any(p["domain"] == "social" for p in payload), payload[:1])


def test_valid_answer_key_unchanged():
    key = [{"question": "Which form?", "options": ["a", "b", "c", "d"], "answer": "b",
            "explanation": "Option b is the second form, as shown in the table."}]
    out = apply_assessment_invariants(key, language="Testish", material_language="tr")
    check("11 valid answer key preserved", out == key, out)


def test_assessment_boundary_drops_invalid_and_sanitizes():
    key = [
        {"question": "Q", "options": ["a", "b", "c", "d"], "answer": "a", "explanation": "fine"},
        {"question": "Bad", "options": ["a", "a"], "answer": "zz", "explanation": "broken"},
        {"question": "Uni", "options": ["a", "b", "c", "d"], "answer": "a",
         "explanation": "cleantext"},
    ]
    out = apply_assessment_invariants(key, language="Testish", material_language="tr")
    check("11b invalid assessment item dropped", len(out) == 2, out)
    check("11b private-use character removed from rationale",
          all("" not in (q.get("explanation") or "") for q in out), out)


def test_rationale_structural_claim_not_routed():
    lesson = {"pages": [{
        "type": "mcq", "prompt": "Q", "options": ["a", "b", "c", "d"], "answer": "a",
        "explanation_tr": "Bu ek her zaman ünsüzden sonra yazılır.",
    }]}
    check("10b structural rationale not routed as a social claim",
          collect_rationale_claims(lesson, material_language="tr") == [], "over-routed")


# ── 15. Idempotence ─────────────────────────────────────────────────────────

def test_idempotent_transformations():
    lesson = {"pages": [{
        "type": "vocabulary",
        "title_tr": "Selamlaşma",
        "items": [
            {"term": "vorma", "phonetic": "[ˈvorma]", "translation_tr": "selam"},
            {"term": "vorma", "phonetic": "[ˈvorma]", "translation_tr": "selam"},
            {"term": "dalno", "phonetic": "[ˈdalno]", "translation_tr": "merhaba"},
        ],
        "rules": [{"rule_tr": "Bu ek her zaman eklenir.", "scope": "tendency"}],
    }]}
    import copy
    once = apply_publication_invariants(copy.deepcopy(lesson), language="Testish",
                                        material_language="tr", topic="Selam", copy=True)
    twice = apply_publication_invariants(copy.deepcopy(once), language="Testish",
                                         material_language="tr", topic="Selam", copy=True)
    check("15 publication invariants are idempotent", once == twice, "second pass changed output")

    risks_once = collect_evidence_risks(once, material_language="tr")
    risks_twice = collect_evidence_risks(twice, material_language="tr")
    check("15b evidence detection is stable across passes",
          [r["path"] for r in risks_once] == [r["path"] for r in risks_twice])

    key = [{"question": "Q", "options": ["a", "b", "c", "d"], "answer": "a", "explanation": "fine"}]
    a = apply_assessment_invariants(key, language="Testish", material_language="tr")
    b = apply_assessment_invariants(a, language="Testish", material_language="tr")
    check("15c assessment invariants are idempotent", a == b)


# ── 16. Unknown target language fails safely ────────────────────────────────

def test_unknown_language_fails_safe():
    lesson = {"pages": [{
        "type": "vocabulary",
        "items": [{"term": "qqq www", "phonetic": "[qqq]", "translation_xx": "zzz"}],
        "rules": [{"rule_xx": "Aina qqq kaytetaan."}],
    }]}
    # Structural signals still work (they are language-neutral); nothing is invented
    # for an instructional language the system does not know.
    risks = collect_evidence_risks(lesson, material_language="xx")
    check("16 unknown instructional language produces no invented classification",
          all(r.get("domain") in ("structural", "unknown", None) for r in risks),
          [r.get("domain") for r in risks])
    check("16b unknown language never raises", True)


def test_malformed_shapes_never_raise():
    for bad in (None, [], "text", {"pages": None}, {"pages": [None, 5, {"items": None}]},
                {"pages": [{"items": [None, "x", {"term": None}]}]}):
        collect_evidence_risks(bad, material_language="tr")
        collect_reviewable_claims(bad, material_language="tr")
        apply_assessment_invariants(bad)
    check("16c malformed shapes never raise", True)


# ── Bounded cost ────────────────────────────────────────────────────────────

def test_review_volume_is_capped():
    items = [{"term": f"term{i} extra", "phonetic": "[t]", "translation_tr": "x"} for i in range(60)]
    rules = [{"rule_tr": f"Resmî ortamda her zaman term{i} kullanılır.", "scope": "absolute"}
             for i in range(60)]
    lesson = {"pages": [{"type": "vocabulary", "items": items, "rules": rules}]}
    claims = collect_reviewable_claims(lesson, material_language="tr")
    check("COST review list is hard-capped",
          len(claims) <= MAX_REVIEWABLE_CLAIMS, len(claims))
    system, payload = build_claim_review_request(claims, "Testish", "A1")
    check("COST one request for all claims", isinstance(payload, list) and len(payload) == len(claims))


# ── Repair contract: a correct fix must survive application ─────────────────

def test_repair_contract_separates_context_from_field():
    """The reviewer reads context; it writes only the field named at `path`.

    Conflating the two silently discarded correct repairs: a replacement for a
    short field was size-checked against the longer display context and rejected
    for being "too short".
    """
    lesson = {"pages": [{"type": "vocabulary", "items": [
        {"term": "zolan", "phonetic": "[ˈzolan]", "translation_tr": "ne"},
        {"term": "zolan mira tev", "phonetic": "[ˈzolan]", "translation_tr": "bu ne"}]}]}
    risks = collect_phonetic_integrity_risks(lesson)
    check("REPAIR risk separates read-context from writable field",
          risks and risks[0]["text"] != risks[0]["field_value"], risks[:1])
    check("REPAIR writable field is the transcription alone",
          risks and risks[0]["field_value"] == "[ˈzolan]", risks[:1])
    check("REPAIR transcription risks may be honestly omitted",
          risks and risks[0]["repair"] == "omit_ok", risks[:1])

    _, payload = build_claim_review_request(risks, "Testish", "A1")
    check("REPAIR payload exposes replace_this and repair policy",
          payload and payload[0]["replace_this"] == "[ˈzolan]"
          and payload[0]["repair"] == "omit_ok", payload[:1])


def test_prose_claims_keep_default_repair_contract():
    prose = [{"path": "pages.0.rules.0.rule_tr", "text": "Resmî ortamlarda her zaman X kullanılır."}]
    record = normalize_claim_record(prose[0])
    check("REPAIR prose defaults to rescope", record["repair"] == "rescope", record)
    check("REPAIR prose writes back what it read",
          record["field_value"] == record["text"], record)


# ── Exclusivity is a scope claim ────────────────────────────────────────────

def test_exclusivity_is_detected_but_never_auto_rewritten():
    for text, code in [("X sadece yakın arkadaşlar için kullanılır.", "tr"),
                       ("X yalnızca resmî ortamlarda kullanılır.", "tr"),
                       ("X is only for peers and close acquaintances.", "en"),
                       ("X is used exclusively in formal settings.", "en")]:
        check(f"EXCL detected [{code}] {text[:34]!r}",
              find_absolute_claims(text, code) != [], text)

    # Deterministic code cannot tell restricted usage from a plain count, so it
    # must never rewrite exclusivity wording - only route it.
    for text, code in [("Bu kuralda sadece iki biçim vardır.", "tr"),
                       ("There are only two forms.", "en")]:
        check(f"EXCL never auto-rewritten [{code}]",
              hedge_absolute_claims(text, code) == text, hedge_absolute_claims(text, code))

    lesson = {"pages": [{"type": "vocabulary",
                         "items": [{"term": "vorma", "translation_tr": "selam"}],
                         "rules": [{"rule_tr": "vorma sadece yakın arkadaşlar arasında kullanılır.",
                                    "scope": "absolute", "domain": "register"}]}]}
    claims = collect_reviewable_claims(lesson, material_language="tr")
    check("EXCL restrictive register claim reaches review",
          any(c["path"].endswith("rule_tr") for c in claims), [c["path"] for c in claims])


# ── Generalizing from a single instance ─────────────────────────────────────

def test_thin_generalization_detected():
    lesson = {"pages": [{"type": "grammar",
                         "items": [{"term": "zolan"}, {"term": "mirka"},
                                   {"term": "tevor"}, {"term": "brenil"}],
                         "rules": [{"rule_tr": "zolan biçiminde olduğu gibi, bu ek her zaman kullanılır."}]}]}
    risks = collect_thin_generalizations(lesson, material_language="tr")
    check("THIN single-instance generalization detected",
          FLAG_THIN_GENERALIZATION in flags(risks), flags(risks))
    if risks:
        check("THIN evidence names the lone instance",
              any("zolan" in e for e in risks[0]["examples"]), risks[0]["examples"])


def test_thin_generalization_precision():
    multi = {"pages": [{"type": "grammar",
                        "items": [{"term": "zolan"}, {"term": "mirka"},
                                  {"term": "tevor"}, {"term": "brenil"}],
                        "rules": [{"rule_tr": "zolan, mirka ve tevor biçimlerinde bu ek her zaman kullanılır."}]}]}
    check("THIN not fired when several instances are cited",
          collect_thin_generalizations(multi, material_language="tr") == [], "false positive")

    plain = {"pages": [{"type": "grammar",
                        "items": [{"term": "zolan"}, {"term": "mirka"}, {"term": "tevor"}],
                        "rules": [{"rule_tr": "zolan bir selamlama biçimidir."}]}]}
    check("THIN not fired on a non-generalizing statement",
          collect_thin_generalizations(plain, material_language="tr") == [], "false positive")


# ── Text-layer integrity is a publication invariant ─────────────────────────

def test_text_integrity_is_part_of_the_boundary():
    import copy
    dirty = {"pages": [{"type": "vocabulary", "text_tr": "a\ufffeb",
                        "items": [{"term": "x\uf8ffy", "example": "m\x01n"}]}]}
    once = apply_publication_invariants(copy.deepcopy(dirty), language="Testish",
                                        material_language="tr", topic="t", copy=True)
    check("TEXT boundary strips unpublishable codepoints",
          "\uf8ff" not in repr(once) and "\x01" not in repr(once), repr(once)[:140])
    twice = apply_publication_invariants(copy.deepcopy(once), language="Testish",
                                         material_language="tr", topic="t", copy=True)
    check("TEXT boundary sanitation is idempotent", once == twice, "second pass differed")
    preserve = {"pages": [{"type": "vocabulary", "items": [
        {"term": "café", "phonetic": "[t͡ɕɪˈtɨrnət͡sətʲ]", "translation_tr": "日本語 العربية"}]}]}
    kept = apply_publication_invariants(copy.deepcopy(preserve), language="Testish",
                                        material_language="tr", topic="t", copy=True)
    check("TEXT valid scripts and IPA preserved", kept == preserve, kept)


def main():
    print("[TEST] publication evidence: IPA integrity, coverage gaps, translations, answer keys")
    for fn in (
        test_phrase_ipa_partial,
        test_phrase_ipa_complete_is_clean,
        test_single_word_never_flagged,
        test_prose_ipa_conflict,
        test_prose_ipa_agreement_is_clean,
        test_cross_section_coverage_gap,
        test_consistent_sections_not_flagged,
        test_translation_polarity_mismatch,
        test_translation_numeral_mismatch,
        test_translation_agreement_is_clean,
        test_rationale_social_claim_routed,
        test_valid_answer_key_unchanged,
        test_assessment_boundary_drops_invalid_and_sanitizes,
        test_rationale_structural_claim_not_routed,
        test_idempotent_transformations,
        test_unknown_language_fails_safe,
        test_malformed_shapes_never_raise,
        test_review_volume_is_capped,
        test_repair_contract_separates_context_from_field,
        test_prose_claims_keep_default_repair_contract,
        test_exclusivity_is_detected_but_never_auto_rewritten,
        test_thin_generalization_detected,
        test_thin_generalization_precision,
        test_text_integrity_is_part_of_the_boundary,
    ):
        fn()
    if FAILURES:
        print(f"\n[TEST] FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("[TEST] publication evidence: all checks passed")


if __name__ == "__main__":
    main()
