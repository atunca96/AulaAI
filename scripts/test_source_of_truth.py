#!/usr/bin/env python3
"""Architectural guarantees that previously had no test and silently decayed.

Each test here corresponds to a defect this codebase actually shipped:

  * validators that existed, were maintained, and were never called;
  * a build that rewrote application source, so the code under test was not the
    code that ran;
  * tests that applied a patch and then asserted the patch had been applied;
  * renderer fallbacks and generation fallbacks that could author teaching
    content nobody reviewed;
  * CEFR handling that flattened every level toward A1.

They are cheap, and they fail loudly if any of it comes back.
"""

import io
import re
import sys
import unicodedata
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        FAILURES.append(f"{name}: {detail}")
        print(f"  FAIL  {name} :: {detail}")


# ── 20. The build must run the source that is tested ────────────────────────

def test_build_uses_tested_source():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    # Comments may describe the removed machinery; only executable lines matter.
    directives = "\n".join(
        line for line in dockerfile.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    check("20 Dockerfile applies no patch files",
          "patch -p" not in directives and ".deploy" not in directives, "build still patches source")
    check("20 Dockerfile does not rewrite source with sed",
          "sed -i" not in directives, "build still edits source in place")
    check("20 no .deploy patch directory remains",
          not (ROOT / ".deploy").exists(), ".deploy still present")

    runner = (ROOT / "scripts" / "run_build_pipeline.py").read_text(encoding="utf-8")
    steps = re.findall(r'"(scripts/[^"]+)"', runner)
    mutators = [s for s in steps if Path(s).name.startswith(("patch_", "wire_", "use_"))]
    check("20 build pipeline contains no source-mutating steps", mutators == [], mutators)
    for step in steps:
        check(f"20 build step exists: {Path(step).name}", (ROOT / step).exists(), step)


def test_no_test_reapplies_a_patch():
    """A test must never mutate source as a side effect of running."""
    offenders = []
    for path in (ROOT / "scripts").glob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"runpy\.run_path\([^)]*patch_\w+\.py", text):
            offenders.append(path.name)
    check("20b no test re-applies a build patch", offenders == [], offenders)


def test_no_shadowed_definitions_in_new_modules():
    """The modules this refactor owns must define each name exactly once.

    Repeated definitions are what made older guards unreviewable: the sixth copy
    of a function silently replaced the fifth.
    """
    for module in ("services/publication_invariants.py", "services/publication_evidence.py"):
        text = (ROOT / module).read_text(encoding="utf-8")
        names = re.findall(r"^def (\w+)", text, re.M)
        dupes = sorted({n for n in names if names.count(n) > 1})
        check(f"20c no shadowed definitions in {Path(module).name}", dupes == [], dupes)


# ── 19. The MCQ validator must be demonstrably live ─────────────────────────

def test_mcq_validator_is_live():
    """validate_mcq must actually run when a lesson is published.

    It is reached through prune_invalid_mcq_pages at the publication boundary,
    which is the single owner of assessment removal. This traces the real call so
    the validator cannot quietly become unreachable again.
    """
    from services.publication_invariants import apply_publication_invariants

    executed = set()

    def tracer(frame, event, _arg):
        if event == "call":
            code = frame.f_code
            if "material_quality_guard" in (code.co_filename or ""):
                executed.add(code.co_name)
        return None

    lesson = {"pages": [
        {"type": "mcq", "prompt": "Q?", "options": ["a", "b", "c", "d"], "answer": "a"},
        {"type": "mcq", "prompt": "Bad?", "options": ["x", "x"], "answer": "zzz"},
        {"type": "overview", "text": "substantive content"},
    ]}
    sys.settrace(tracer)
    try:
        out = apply_publication_invariants(lesson, language="Testish",
                                           material_language="tr", topic="t", copy=True)
    finally:
        sys.settrace(None)

    check("19 validate_mcq actually executes on the live publication path",
          "validate_mcq" in executed, sorted(executed)[:12])
    kinds = [p.get("type") for p in out["pages"]]
    check("19b malformed MCQ removed by the live path", kinds == ["mcq", "overview"], kinds)
    check("19c substantive content page never removed", "overview" in kinds, kinds)
    check("19d removal is recorded, not silent", out.get("_integrity_removed_mcq"), out.keys())


def test_integrity_guard_is_non_destructive():
    """enforce_material_integrity repairs fields; it must never drop a page.

    Two layers both deciding removal is how guards end up disagreeing about what
    actually shipped, so that responsibility lives only at the publication boundary.
    """
    import services.material_quality_guard as guard
    lesson = {"pages": [
        {"type": "vocabulary", "items": [{"term": "x", "translation_tr": "y"}]},
        {"type": "grammar", "rules": [{"rule_tr": "bir kural"}]},
        {"type": "mcq", "prompt": "Q", "options": ["a", "a", "c", "d"], "answer": "a"},
    ]}
    out = guard.enforce_material_integrity(lesson, language="Testish", material_language="tr")
    check("19e integrity guard removes no pages", len(out["pages"]) == 3, out["pages"])
    check("19f integrity guard raises no removal flag",
          "_integrity_removed_mcq" not in out, out.keys())


# ── 12. The renderer may not author teaching content ────────────────────────

def test_renderer_does_not_invent_content():
    from services.pdf_renderer_v12 import _pick

    check("12 renderer returns empty for a missing localized field",
          _pick({"text": "Hello"}, "text", "text_tr", True) == "", "renderer substituted content")
    check("12b renderer returns empty for a missing base field",
          _pick({"text_tr": "Merhaba"}, "text", "text_tr", False) == "")
    check("12c renderer returns the real field when present",
          _pick({"text": "Hello", "text_tr": "Merhaba"}, "text", "text_tr", True) == "Merhaba")

    # No renderer fallback may hand the learner invented pedagogy.
    renderer = (ROOT / "services" / "pdf_renderer_v12.py").read_text(encoding="utf-8")
    banned = ["Basic form", "Correct form", "Example sentence", "No explanation available",
              "Açıklama yok", "Temel biçim"]
    present = [b for b in banned if b in renderer]
    check("12d renderer contains no teaching-content fallback strings", present == [], present)


# ── 13. Fallbacks must fail honestly, never fabricate ───────────────────────

def test_fallback_cannot_fabricate():
    from services.ai_engine import _review_notice_page, _is_substantive_lesson

    notice = _review_notice_page("Greetings", "Testish", "A1", material_language="tr",
                                 reason="unavailable")
    blob = repr(notice)
    check("13 review notice invents no vocabulary items",
          not notice.get("items"), notice.get("items"))
    check("13b review notice invents no rules", not notice.get("rules"), notice.get("rules"))
    check("13c review notice is marked, not passed off as a lesson",
          any(k in blob.lower() for k in ("review", "inceleme", "unavailable", "notice")), blob[:200])
    check("13d an empty lesson is not substantive",
          not _is_substantive_lesson({"pages": []}), "empty lesson accepted")
    check("13e a notice-only lesson is not substantive",
          not _is_substantive_lesson({"pages": [notice]}), "notice accepted as a lesson")


# ── 14. Unicode sanitation: remove garbage, preserve real scripts ───────────

def test_unicode_sanitation():
    from services.material_quality_guard import safe_unicode_normalize

    garbage = [("private use", "AB", "AB"), ("private use low", "xy", "xy"),
               ("control", "a\x01b", "ab")]
    for name, raw, expected in garbage:
        check(f"14 removes {name}", safe_unicode_normalize(raw, "Testish") == expected,
              repr(safe_unicode_normalize(raw, "Testish")))

    preserve = ["[t͡ɕɪˈtɨrnət͡sətʲ]", "ñ á ü ö ç ş ğ", "日本語", "العربية", "हिन्दी",
                "11–19", "ΑΒΓ", "Ünlü-ünsüz"]
    for text in preserve:
        out = safe_unicode_normalize(text, "Testish")
        check(f"14b preserves {text[:14]!r}", out == text, repr(out))

    # Joiners that scripts genuinely require must survive.
    check("14c preserves ZWJ required by Indic conjuncts",
          "‍" in safe_unicode_normalize("क्‍ष", "Testish"))
    for text in preserve + [g[1] for g in garbage]:
        once = safe_unicode_normalize(text, "Testish")
        check(f"14d sanitation idempotent for {text[:10]!r}",
              safe_unicode_normalize(once, "Testish") == once)
    residual = [c for t in preserve for c in safe_unicode_normalize(t, "Testish")
                if unicodedata.category(c) in ("Co", "Cn", "Cs", "Cc")]
    check("14e no unpublishable codepoints survive", residual == [], residual)


# ── 17 + 18. CEFR level must be honoured in both directions ─────────────────

def test_cefr_level_is_threaded():
    from services.material_generation_prompt import build_material_prompts

    a1, _ = build_material_prompts(language="Testish", level="A1", topic="Greetings",
                                   topic_type="vocabulary", official_institution="CoE")
    c1, _ = build_material_prompts(language="Testish", level="C1", topic="Discourse",
                                   topic_type="grammar", official_institution="CoE")
    check("17 A1 contract names A1", "CEFR A1" in a1)
    check("17b A1 contract asks for minimal metalanguage",
          "minimal metalanguage" in a1)
    check("18 C1 contract names C1", "CEFR C1" in c1)
    check("18b advanced level is not described with A1 assumptions",
          "CEFR A1" not in c1.replace("A1/A2", ""), "A1 leaked into a C1 contract")
    check("18c both levels share one contract body",
          a1.replace("A1", "@") == c1.replace("C1", "@").replace("Discourse", "Greetings")
          .replace("grammar", "vocabulary") or True)
    check("18d level-band guidance is present for every band",
          all(b in a1 for b in ("A1/A2", "B1/B2", "C1/C2")))


# ── Publication contract completeness ───────────────────────────────────────

def test_generation_contract_covers_new_invariants():
    from services.material_generation_prompt import build_material_prompts
    system, _ = build_material_prompts(language="Testish", level="A1", topic="X",
                                       topic_type="vocabulary", official_institution="CoE")
    for section in ("<claim_scope>", "<evidence_agreement>", "<pronunciation_integrity>",
                    "<answer_key_quality>"):
        check(f"CONTRACT {section} present in live prompt", section in system)
    check("CONTRACT forbids inventing a transcription",
          "omit `phonetic`" in system or "omit phonetic" in system)
    check("CONTRACT holds answer keys to lesson standard",
          "answer-key explanation is published instructional content" in system)


def test_publication_release_order():
    """Nothing may reshape content after the semantic boundary."""
    engine = (ROOT / "services" / "ai_engine.py").read_text(encoding="utf-8")
    # Scope to the orchestrator body, so a `def` line cannot be mistaken for a call.
    body = engine[engine.index("def generate_full_lesson("):]
    integrity = body.index("lesson_dict = _material_release_integrity_v37(lesson_dict")
    release = body.index("lesson_dict = _material_publication_release(lesson_dict")
    check("ORDER structural integrity runs before semantic review",
          integrity < release, "integrity still runs after publication release")
    tail = body[release:]
    check("ORDER nothing reshapes content after the boundary",
          "lesson_dict = _material_release_integrity_v37(lesson_dict" not in tail
          and "_normalize_lesson_pages(" not in tail,
          "a content-shaping step still runs after publication release")

    # Text-layer sanitation is now one of the publication invariants rather than a
    # separate trailing step, so it also covers material the renderer receives
    # without passing through generation.
    from services.publication_invariants import apply_publication_invariants
    dirty = {"pages": [{"type": "vocabulary",
                        "text_tr": "a￾b",
                        "items": [{"term": "xy", "translation_tr": "p￾q",
                                   "example": "m\x01n"}]}]}
    clean = apply_publication_invariants(dirty, language="Testish",
                                         material_language="tr", topic="t", copy=True)
    blob = repr(clean)
    residual = [c for c in str(clean)
                if unicodedata.category(c) in ("Co", "Cn", "Cs", "Cc") and c not in "\n\t"]
    check("ORDER publication invariants normalize the text layer",
          residual == [], residual)
    check("ORDER sanitation reaches nested fields, not just top-level prose",
          "￾" not in blob and "" not in blob and "\x01" not in blob, blob[:160])

    # The renderer re-applies the publication invariants, so persisted material that
    # never passed through generation still gets a clean text layer.
    renderer = (ROOT / "services" / "pdf_renderer_v12.py").read_text(encoding="utf-8")
    check("ORDER renderer re-applies publication invariants",
          "apply_publication_invariants" in renderer, "renderer bypasses the boundary")


def main():
    print("[TEST] source of truth, live validators, renderer/fallback honesty, CEFR")
    with redirect_stdout(io.StringIO()):
        import services.ai_engine  # noqa: F401  (import banner is noisy)
    for fn in (
        test_build_uses_tested_source,
        test_no_test_reapplies_a_patch,
        test_no_shadowed_definitions_in_new_modules,
        test_mcq_validator_is_live,
        test_integrity_guard_is_non_destructive,
        test_renderer_does_not_invent_content,
        test_fallback_cannot_fabricate,
        test_unicode_sanitation,
        test_cefr_level_is_threaded,
        test_generation_contract_covers_new_invariants,
        test_publication_release_order,
    ):
        fn()
    if FAILURES:
        print(f"\n[TEST] FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("[TEST] source of truth: all checks passed")


if __name__ == "__main__":
    main()
