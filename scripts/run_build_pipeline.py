#!/usr/bin/env python3
"""Build-time verification. The image refuses to build if this fails.

This runs inside the Docker image, on the Python the product actually runs
(3.12), against the source exactly as checked in. It never modifies the
application tree — an earlier incarnation of this file rewrote source at build
time across 43 steps, so the code in git and the code in production differed by
thousands of lines and every fix was authored blind. Adding a step that writes
into the app tree re-creates that defect.

Two jobs, and the second is the one that matters most here:

  * run the test suites, which are provider-free and deterministic;
  * byte-compile every module the runtime imports.

The compile pass is not redundant with the tests. Two modules in this tree —
`server.py` and `services/bilingual_finisher.py` — use syntax that is valid only
on Python 3.12, so they cannot be imported by a 3.11 interpreter at all. They
are therefore invisible to any check run outside this image, and this is the
only place a syntax error in them is caught before deploy.
"""

import py_compile
import runpy
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# Read-only with respect to the app tree, every one of them.
VERIFICATION_STEPS = [
    "scripts/test_authoring_audit.py",
    "scripts/test_authoring_core.py",
    "scripts/test_publication_divergence.py",
    # Runs the real gate and the real renderer against a real SQLite database,
    # on the image's own Python. It is the only step that proves READY and the
    # exported PDF agree on the bytes a learner receives.
    "scripts/verify_production_path.py",
    # The state machine that turns a publication verdict into a database state.
    # Nothing tested it, and it was discarding the verdict.
    "scripts/test_publication_state.py",
    # Provider-free orchestration proof: a deterministic renderer blocker missed
    # by Gemini is handed to one bounded targeted Gemini repair before publication.
    "scripts/test_assessment_render_repair.py",
    "scripts/test_assessment_generation_render_filter.py",
    "scripts/test_review_schema_provider_compat.py",
    "scripts/test_gemini_no_reasoning.py",
    "scripts/test_unit_assessment_rescue.py",
    "scripts/test_semantic_patch_reconciliation.py",
    "scripts/test_duplicate_semantic_patch.py",
    "scripts/test_slash_duplicate_patch_reconcile.py",
    "scripts/test_editorial_slash_patch_reconcile.py",
    "scripts/test_cross_topic_duplicate_stem_repair.py",
    "scripts/test_scope_risk_phonetic_gate.py",
    "scripts/test_residual_quality_review.py",
    "scripts/test_rationale_specificity_repair.py",
    "scripts/test_rationale_proof_over_proxy.py",
    "scripts/test_name_gender_proof_parity.py",
    "scripts/test_hypothetical_mood_teachable.py",
    "scripts/test_review_worker_ceiling.py",
    "scripts/test_duplicate_prose.py",
    "scripts/test_artifact_audit.py",
    "scripts/test_embedded_patch_corruption.py",
    "scripts/test_camel_hump_patch_reconcile.py",
    "scripts/test_sentence_camel_corruption.py",
    "scripts/test_assessment_review_budget.py",
    "scripts/test_review_admission_429.py",
    "scripts/test_lesson_render_exact_repair.py",
    "scripts/test_review_reconciliation_v2.py",
    "scripts/test_exact_deterministic_repair.py",
    "scripts/test_preflight_deterministic_repair.py",
    "scripts/test_preflight_exact_residuals.py",
    "scripts/test_empty_semantic_patch.py",
    "scripts/test_gemini_review_chunking.py",
    "scripts/test_final_publication_autorepair.py",
    "scripts/test_no_terra_publication_path.py",
    "scripts/test_quality_gate.py",
    "scripts/test_language_matrix.py",
    "scripts/smoke_test_pdf_renderer.py",
    "scripts/test_micro_quality_polish.py",
    "scripts/test_page_level_integrity_v56.py",
    "scripts/test_release_cleanup_v56.py",
    "scripts/test_release_quality_v56.py",
    "scripts/test_release_final_v57.py",
]

# Every module the runtime imports. A file listed here that does not exist is a
# hard error rather than a skip: the previous version skipped silently, so a
# module deleted without updating this list produced a green build and a broken
# image — which is exactly how a deploy came to fail on a missing file.
COMPILE_TARGETS = [
    "server.py",
    "worker.py",
    "runtime_bootstrap.py",
    "database.py",
    "services/ai_engine.py",
    "services/content_engine.py",
    "services/authoring/__init__.py",
    "services/authoring/schema.py",
    "services/authoring/prompts.py",
    "services/authoring/blueprint.py",
    "services/authoring/transport.py",
    "services/authoring/engine.py",
    "services/authoring/audit.py",
    "services/authoring/repair.py",
    "services/authoring/budget.py",
    "services/authoring/render_contract.py",
    "services/authoring/artifact_audit.py",
    "services/authoring/publication_state.py",
    "services/authoring/publish.py",
    "services/authoring/quality_gate.py",
    "services/authoring/legacy_text.py",
    "services/bilingual_finisher.py",
    "services/pdf_renderer_v12.py",
    "services/pdf_academic_renderer.py",
    "services/pdf_text_layer.py",
    "services/quiz_source_cache.py",
    "services/curriculum_translator.py",
    "services/class_lexicon.py",
    "services/concept_explanations.py",
    "services/assessment_scope.py",
    "services/cefr_reference.py",
    "services/language_data.py",
    "services/language_profiles.py",
    "services/generation_cost.py",
    "services/mastery.py",
    "services/dictionary_service.py",
    "services/special_pair_profile.py",
    "services/marker_service.py",
    "services/state.py",
    "services/legacy/pdf_pipeline.py",
]

# Imported for real, not merely compiled. Compilation proves the syntax; import
# proves the module's top-level references resolve — which is what catches a
# module that survived a deletion only because nothing had imported it yet.
IMPORT_TARGETS = [
    "services.ai_engine",
    "services.content_engine",
    "services.authoring.engine",
    "services.authoring.publish",
    "services.pdf_renderer_v12",
    "services.bilingual_finisher",
    "server",
    "worker",
]


def _clear_project_modules():
    prefixes = ("services", "database", "server", "worker", "runtime_bootstrap")
    for name in list(sys.modules):
        if name.startswith(prefixes):
            del sys.modules[name]


def _reset_review_attestations():
    """Start every build from an empty replay/attestation store.

    The store is a sqlite file that survives between runs, and several checks
    assert how many provider round-trips a path makes. A warm store serves the
    first call from cache, the second never happens, and the check fails — so a
    green build could turn red on a re-run with no source change, which is the
    opposite of what a build verifying checked-in source is for.

    Railway builds in a fresh container and `data/` is in `.railwayignore`, so
    this only ever matters locally; that is precisely where a developer hits it.
    """
    for name in ("aula_quality_review_attest.sqlite3",):
        target = ROOT / "data" / name
        try:
            target.unlink()
            print(f"[AULAAI-BUILD] cleared review attestation store: {name}")
        except FileNotFoundError:
            pass
        except OSError as exc:
            print(f"[AULAAI-BUILD] could not clear {name}: {exc}", file=sys.stderr)


def run_pipeline():
    started = time.perf_counter()
    _reset_review_attestations()
    total = len(VERIFICATION_STEPS)
    print(f"[AULAAI-BUILD] {total} verification steps against checked-in source")

    for index, relative in enumerate(VERIFICATION_STEPS, 1):
        path = ROOT / relative
        if not path.exists():
            print(f"[{index}/{total}] MISSING {relative}", file=sys.stderr)
            sys.exit(1)
        _clear_project_modules()
        step_started = time.perf_counter()
        try:
            runpy.run_path(str(path), run_name="__main__")
        except SystemExit as exit_signal:
            if exit_signal.code not in (0, None):
                print(f"[{index}/{total}] FAILED {relative} ({exit_signal.code})", file=sys.stderr)
                sys.exit(exit_signal.code)
        except Exception:
            outcome = subprocess.run([sys.executable, str(path)], cwd=str(ROOT))
            if outcome.returncode != 0:
                print(f"[{index}/{total}] FAILED {relative} ({outcome.returncode})",
                      file=sys.stderr)
                sys.exit(outcome.returncode)
        print(f"  [{index:2d}/{total}] OK ({time.perf_counter() - step_started:4.2f}s) {relative}")

    print("[AULAAI-BUILD] byte-compiling every runtime module")
    missing = [t for t in COMPILE_TARGETS if not (ROOT / t).exists()]
    if missing:
        print("  MISSING runtime modules: " + ", ".join(missing), file=sys.stderr)
        print("  If one was deleted on purpose, remove it from COMPILE_TARGETS too.",
              file=sys.stderr)
        sys.exit(1)
    compile_started = time.perf_counter()
    for target in COMPILE_TARGETS:
        try:
            py_compile.compile(str(ROOT / target), doraise=True)
        except py_compile.PyCompileError as exc:
            print(f"  SYNTAX ERROR in {target}:\n{exc}", file=sys.stderr)
            sys.exit(1)
    print(f"  [py_compile] {len(COMPILE_TARGETS)} files clean "
          f"({time.perf_counter() - compile_started:4.2f}s)")

    print("[AULAAI-BUILD] importing every entry point")
    _clear_project_modules()
    import importlib
    for name in IMPORT_TARGETS:
        try:
            importlib.import_module(name)
        except Exception as exc:
            print(f"  IMPORT FAILED {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"  [import] {name}")

    print(f"[AULAAI-BUILD] all checks passed in {time.perf_counter() - started:.2f}s\n")


if __name__ == "__main__":
    run_pipeline()
