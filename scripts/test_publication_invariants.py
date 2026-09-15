#!/usr/bin/env python3
"""Regression tests for the deterministic publication boundary.

Focus: the claim-scope layer must route *contextual* conventions to bounded
semantic review while leaving *categorical structural* rules alone. Every case
below is synthetic and constructed so that no case depends on a particular
natural language, alphabet, CEFR level or topic being special-cased in the code.

The tests assert routing and metadata only. Whether a given social convention is
genuinely universal is a semantic question this layer deliberately does not
answer - that judgement stays with the existing bounded verifier.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.publication_invariants import (  # noqa: E402
    apply_publication_invariants,
    build_claim_review_request,
    classify_claim_domain,
    collect_reviewable_claims,
    collect_scope_contradictions,
    collect_unscoped_absolute_claims,
    find_absolute_claims,
    hedge_absolute_claims,
    prune_invalid_mcq_pages,
)

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        FAILURES.append(f"{name}: {detail}")
        print(f"  FAIL  {name} :: {detail}")


def paths(claims):
    return {c["path"] for c in claims}


def by_path(claims, path):
    for c in claims:
        if c["path"] == path:
            return c
    return None


# ── 1. Valid hard orthographic rule ─────────────────────────────────────────
# Categorical spelling prohibition, fully supported by its own examples, and
# declared absolute by the generator. Must NOT be routed to review purely for
# containing "never": weakening true orthography is its own quality defect.

def test_valid_orthographic_rule():
    lesson = {"pages": [{
        "type": "grammar",
        "items": [
            {"term": "QI", "explanation_tr": "Q harfinden sonra I harfi yazılır."},
            {"term": "QA", "explanation_tr": "Q harfinden sonra A harfi yazılır."},
        ],
        "rules": [{
            "rule_tr": "Q harfinden sonra asla Y harfi yazılmaz; bunun yerine I harfi yazılır.",
            "scope": "absolute",
            "domain": "orthography",
        }],
    }]}
    claims = collect_reviewable_claims(lesson, material_language="tr")
    check("1 orthographic rule preserved (not routed to review)",
          claims == [], f"unexpectedly routed: {paths(claims)}")
    check("1 orthographic rule classifies structural",
          classify_claim_domain(lesson["pages"][0]["rules"][0]["rule_tr"], "tr") == "structural",
          classify_claim_domain(lesson["pages"][0]["rules"][0]["rule_tr"], "tr"))
    before = lesson["pages"][0]["rules"][0]["rule_tr"]
    apply_publication_invariants(lesson, material_language="tr", copy=False)
    check("1 orthographic wording not rewritten by deterministic pass",
          lesson["pages"][0]["rules"][0]["rule_tr"] == before, "text was mutated")


# ── 2. Valid invariant morphology ───────────────────────────────────────────
# "This form does not change for gender/number", with every displayed example
# agreeing. Absolute wording is correct here and must survive.

def test_valid_invariant_morphology():
    lesson = {"pages": [{
        "type": "grammar",
        "items": [
            {"term": "ZOLA", "explanation_tr": "Eril biçim: ZOLA."},
            {"term": "ZOLA", "explanation_tr": "Dişil biçim: ZOLA."},
            {"term": "ZOLA", "explanation_tr": "Çoğul biçim: ZOLA."},
        ],
        "rules": [{
            "rule_tr": "ZOLA sıfatı cinsiyet ve çoğul için asla çekim eki almaz; biçim her zaman aynıdır.",
            "scope": "absolute",
            "domain": "morphology",
        }],
    }]}
    claims = collect_reviewable_claims(lesson, material_language="tr")
    check("2 invariant morphology preserved", claims == [], f"unexpectedly routed: {paths(claims)}")
    check("2 invariant morphology classifies structural",
          classify_claim_domain(lesson["pages"][0]["rules"][0]["rule_tr"], "tr") == "structural")


# ── 3. Social/register convention written as absolute ───────────────────────
# The production failure class. The generator declares scope "absolute"; nearby
# material shows a second expression acceptable in the same context. Must be
# routed to review and must NOT publish unchanged.

def test_social_convention_absolute():
    lesson = {"pages": [{
        "type": "vocabulary",
        "items": [
            {"term": "VORMA", "translation_tr": "Resmî selamlama"},
            {"term": "DALNO", "translation_tr": "Selamlama",
             "explanation_tr": "Hem resmî hem samimi ortamlarda kullanılabilir."},
        ],
        "rules": [{
            "rule_tr": "Resmî ortamlarda her zaman VORMA kullanılır.",
            "scope": "absolute",
            "domain": "register",
        }],
    }]}
    claims = collect_reviewable_claims(lesson, material_language="tr")
    target = "pages.0.rules.0.rule_tr"
    check("3 social absolute claim routed to review despite scope=absolute",
          target in paths(claims), f"got {paths(claims)}")
    claim = by_path(claims, target)
    check("3 social claim carries social domain", claim and claim["domain"] == "social",
          claim["domain"] if claim else "missing")
    check("3 contradicting alternative reaches the verifier payload",
          claim and any("DALNO" in e for e in claim["examples"]),
          claim["examples"] if claim else "missing")
    _, payload = build_claim_review_request(claims, "Testish", "A1")
    check("3 payload exposes domain to the verifier",
          payload and payload[0]["domain"] == "social", payload[:1])


def test_social_convention_without_declared_domain():
    """Same defect with no generator-declared `domain`: cue classification alone
    must still route it. The generator label is advisory, never load-bearing."""
    lesson = {"pages": [{
        "type": "vocabulary",
        "items": [{"term": "VORMA", "translation_tr": "Resmî selamlama"}],
        "rules": [{
            "rule_tr": "Öğretmene ve müşteriye karşı VORMA kullanmak zorunludur.",
            "scope": "absolute",
        }],
    }]}
    claims = collect_reviewable_claims(lesson, material_language="tr")
    check("3b deontic 'zorunludur' detected as absolute wording",
          find_absolute_claims(lesson["pages"][0]["rules"][0]["rule_tr"], "tr") != [],
          "obligation wording not detected")
    check("3b undeclared social claim still routed", len(claims) == 1, f"got {paths(claims)}")


# ── 4. Politeness guidance using never/always ───────────────────────────────

def test_politeness_guidance():
    lesson = {"pages": [{
        "type": "grammar",
        "items": [{"term": "TOSKA", "translation_tr": "Gayri resmî veda"}],
        "rules": [{
            "rule_tr": "Amire veya müşteriye asla TOSKA denmez; daima BRENIL kullanılır.",
            "scope": "absolute",
            "domain": "politeness",
        }],
    }]}
    claims = collect_reviewable_claims(lesson, material_language="tr")
    check("4 politeness guidance routed to review", len(claims) == 1, f"got {paths(claims)}")
    claim = claims[0] if claims else None
    check("4 politeness claim marked social", claim and claim["domain"] == "social")
    system, _ = build_claim_review_request(claims, "Testish", "A1")
    check("4 reviewer instructed to keep categorical structural rules absolute",
          "must NOT be weakened merely for containing" in system)
    check("4 reviewer instructed to rescope contextual norms", "contextual norms" in system)


# ── 5. Valid contextual tendency ────────────────────────────────────────────
# Already correctly scoped. Nothing to detect, nothing to spend a call on.

def test_valid_contextual_tendency():
    lesson = {"pages": [{
        "type": "grammar",
        "items": [{"term": "VORMA", "translation_tr": "Resmî selamlama"}],
        "rules": [{
            "rule_tr": "VORMA, resmî bağlamlarda genellikle tercih edilir.",
            "scope": "tendency",
            "domain": "register",
        }],
    }]}
    claims = collect_reviewable_claims(lesson, material_language="tr")
    check("5 well-scoped tendency not routed", claims == [], f"got {paths(claims)}")
    before = lesson["pages"][0]["rules"][0]["rule_tr"]
    apply_publication_invariants(lesson, material_language="tr", copy=False)
    check("5 well-scoped tendency text untouched",
          lesson["pages"][0]["rules"][0]["rule_tr"] == before)


# ── 6. Local internal contradiction ─────────────────────────────────────────
# A rule says "always X" while a sibling entry presents Y as also acceptable in
# a context the claim itself named. Must be caught, with the contradiction
# flagged explicitly and the competing entry supplied as evidence.

def test_local_internal_contradiction():
    lesson = {"pages": [{
        "type": "vocabulary",
        "items": [
            {"term": "VORMA", "translation_tr": "Resmî selamlama"},
            {"term": "DALNO", "translation_tr": "Selamlama",
             "explanation_tr": "Resmî ortamlarda da kullanılabilir, samimi ortamlarda da."},
        ],
        "rules": [{
            "rule_tr": "Resmî ortamlarda her zaman VORMA kullanılır.",
            "scope": "tendency",
        }],
    }]}
    contradictions = collect_scope_contradictions(lesson, material_language="tr")
    check("6 internal contradiction detected", len(contradictions) == 1,
          f"got {len(contradictions)}")
    if contradictions:
        c = contradictions[0]
        check("6 contradiction names the competing entry",
              any("DALNO" in e for e in c["examples"]), c["examples"])
    merged = collect_reviewable_claims(lesson, material_language="tr")
    claim = by_path(merged, "pages.0.rules.0.rule_tr")
    check("6 contradiction flag merged onto the single reviewed claim",
          claim and "nearby-alternative-contradicts-claim" in claim["quantifiers"],
          claim["quantifiers"] if claim else "missing")
    check("6 claim reviewed exactly once (no duplicate payload entry)",
          len(merged) == 1, f"got {paths(merged)}")


def test_contradiction_is_not_phonetics_only():
    """The contradiction detector must not depend on IPA/stress data existing."""
    lesson = {"pages": [{
        "type": "vocabulary",
        "items": [
            {"term": "VORMA", "translation_tr": "Resmî biçim"},
            {"term": "DALNO", "translation_tr": "Biçim",
             "explanation_tr": "Resmî ortamlarda da uygundur, samimi ortamlarda da."},
        ],
        "rules": [{"rule_tr": "Resmî ortamlarda her zaman VORMA kullanılır.", "scope": "tendency"}],
    }]}
    for page in lesson["pages"]:
        for item in page["items"]:
            assert "phonetic" not in item
    check("6b contradiction found with no phonetic data present",
          len(collect_scope_contradictions(lesson, material_language="tr")) == 1)


# ── 7. No false positive on ordinary narrative ──────────────────────────────

def test_no_false_positive_narrative():
    lesson = {"pages": [{
        "type": "overview",
        "text_tr": "Ali her zaman sabah kahvaltı yapar ve okula yürüyerek gider.",
        "items": [{"term": "KAHVE", "translation_tr": "Kahve",
                   "example_tr": "O her zaman kahve içer."}],
        "dialogue": [{"speaker": "Ali", "text": "Ben her zaman erken kalkarım."}],
    }]}
    claims = collect_reviewable_claims(lesson, material_language="tr")
    check("7 narrative prose with 'her zaman' not routed", claims == [], f"got {paths(claims)}")
    before = lesson["pages"][0]["text_tr"]
    apply_publication_invariants(lesson, material_language="tr", copy=False)
    check("7 narrative prose not rewritten",
          lesson["pages"][0]["text_tr"] == before, "narrative was mutated")
    check("7 dialogue line not rewritten",
          lesson["pages"][0]["dialogue"][0]["text"] == "Ben her zaman erken kalkarım.")


def test_quoted_target_material_protected():
    """Absolute-looking wording inside quoted target material is never touched."""
    text = 'Öğrenci "I always study" cümlesini kurar.'
    check("7b quoted target material left intact",
          hedge_absolute_claims(text, "tr") == text, hedge_absolute_claims(text, "tr"))


# ── 8. Unknown language / unknown domain: fail safe ─────────────────────────

def test_unknown_language_fails_safe():
    lesson = {"pages": [{
        "type": "grammar",
        "items": [{"term": "VORMA", "translation_xx": "greeting"}],
        "rules": [{"rule_xx": "Aina VORMA kaytetaan virallisissa tilanteissa.", "scope": "absolute"}],
    }]}
    claims = collect_reviewable_claims(lesson, material_language="xx")
    check("8 unknown instructional language produces no claims", claims == [], f"got {paths(claims)}")
    check("8 unknown language classifies as None",
          classify_claim_domain("Aina VORMA kaytetaan", "xx") is None)
    check("8 unknown language hedging is a no-op",
          hedge_absolute_claims("Aina VORMA kaytetaan", "xx") == "Aina VORMA kaytetaan")


def test_unknown_domain_fails_safe():
    """Absolute wording with no domain cues at all classifies as unknown and keeps
    the pre-existing routing rule: reviewed only if not declared absolute."""
    claim_text = "VORMA her zaman ZOLA ile birlikte gelir."
    check("8b cue-free claim classifies as unknown",
          classify_claim_domain(claim_text, "tr") is None, classify_claim_domain(claim_text, "tr"))
    declared = {"pages": [{"rules": [{"rule_tr": claim_text, "scope": "absolute"}]}]}
    check("8b unknown-domain + declared absolute keeps legacy bypass",
          collect_unscoped_absolute_claims(declared, material_language="tr") == [])
    undeclared = {"pages": [{"rules": [{"rule_tr": claim_text, "scope": "tendency"}]}]}
    got = collect_unscoped_absolute_claims(undeclared, material_language="tr")
    check("8b unknown-domain + undeclared still reviewed", len(got) == 1, f"got {paths(got)}")
    check("8b unknown domain reported honestly, not guessed",
          got and got[0]["domain"] == "unknown", got[0]["domain"] if got else "missing")


def test_malformed_input_never_raises():
    for bad in (None, [], "text", {"pages": None}, {"pages": [None, 3, {"rules": None}]}):
        collect_reviewable_claims(bad, material_language="tr")
        collect_scope_contradictions(bad, material_language="tr")
        apply_publication_invariants(bad, material_language="tr")
    check("8c malformed lesson shapes never raise", True)


# ── Preservation of already-closed behaviour ────────────────────────────────

def test_preserves_existing_invariants():
    """Guard the behaviours this change must not regress."""
    mcq = {"pages": [
        {"type": "mcq", "prompt": "Q?", "options": ["a", "b", "c", "d"], "answer": "a"},
        {"type": "mcq", "prompt": "", "options": [], "answer": ""},
        {"type": "vocabulary", "items": [{"term": "X", "translation_tr": "Y"}]},
    ]}
    pruned = prune_invalid_mcq_pages(mcq)
    kinds = [p.get("type") for p in pruned["pages"]]
    check("R1 invalid MCQ page pruned, valid MCQ and content pages kept",
          kinds == ["mcq", "vocabulary"], kinds)

    dup = {"pages": [{"type": "vocabulary", "items": [
        {"term": "A", "translation_tr": "a"},
        {"term": "A", "translation_tr": "a"},
        {"term": "B", "translation_tr": "b"},
    ]}]}
    collapsed = apply_publication_invariants(dup, material_language="tr", copy=True)
    check("R2 adjacent duplicates still collapsed",
          len(collapsed["pages"][0]["items"]) == 2, collapsed["pages"][0]["items"])

    tendency = {"pages": [{"rules": [
        {"rule_tr": "Bu ek her zaman eklenir.", "scope": "tendency"},
    ]}]}
    apply_publication_invariants(tendency, material_language="tr", copy=False)
    check("R3 declared-tendency absolute wording still hedged",
          "her zaman" not in tendency["pages"][0]["rules"][0]["rule_tr"],
          tendency["pages"][0]["rules"][0]["rule_tr"])

    check("R4 single bounded review request for many claims",
          len(build_claim_review_request([{"text": "a"}, {"text": "b"}], "L", "A1")[1]) == 2)


def test_stress_generalization_detector_intact():
    """The number-stress fix must keep working, unchanged, through the new
    aggregator. Family of >=3 terms, one named exception, one silent outlier."""
    from services.publication_invariants import collect_generalization_contradictions
    lesson = {"pages": [{
        "type": "vocabulary",
        "items": [
            {"term": "odinnatsat", "phonetic": "ɐˈdʲinətsətʲ"},
            {"term": "dvenatsat", "phonetic": "dvʲɪˈnatsətʲ"},
            {"term": "trinatsat", "phonetic": "trʲɪˈnatsətʲ"},
            {"term": "chetyrnatsat", "phonetic": "tɕɪˈtɨrnətsətʲ"},
            {"term": "pyatnatsat", "phonetic": "pʲɪtˈnatsətʲ"},
        ],
        "rules": [{
            "rule_tr": "Neredeyse tüm sayılarda vurgu -na- hecesindedir; tek istisna chetyrnatsat sözcüğüdür.",
            "scope": "tendency",
        }],
    }]}
    found = collect_generalization_contradictions(lesson, material_language="tr")
    check("R5 stress-generalization detector still fires", len(found) == 1, f"got {len(found)}")
    merged = collect_reviewable_claims(lesson, material_language="tr")
    check("R5 stress claim reaches the aggregated review list",
          any("generalization-narrower-than-evidence" in (c.get("quantifiers") or [])
              for c in merged), [c.get("quantifiers") for c in merged])


def main():
    print("[TEST] publication invariants: claim domain, scope routing, contradictions")
    for fn in (
        test_valid_orthographic_rule,
        test_valid_invariant_morphology,
        test_social_convention_absolute,
        test_social_convention_without_declared_domain,
        test_politeness_guidance,
        test_valid_contextual_tendency,
        test_local_internal_contradiction,
        test_contradiction_is_not_phonetics_only,
        test_no_false_positive_narrative,
        test_quoted_target_material_protected,
        test_unknown_language_fails_safe,
        test_unknown_domain_fails_safe,
        test_malformed_input_never_raises,
        test_preserves_existing_invariants,
        test_stress_generalization_detector_intact,
    ):
        fn()
    if FAILURES:
        print(f"\n[TEST] FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("[TEST] publication invariants: all checks passed")


if __name__ == "__main__":
    main()
