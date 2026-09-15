#!/usr/bin/env python3
"""AulaAI build verification suite.

This used to be a 58-step pipeline in which 43 steps REWROTE the application
source at build time. That made the deployed code unreadable: checked-in source
and runtime source differed by thousands of lines, every fix was authored blind
against a file nobody could review, and each new patch appended another copy of
a function instead of editing it (enforce_material_integrity existed six times,
_pick five times), so later patches silently shadowed earlier ones.

The build-time mutation output is now frozen into the checked-in modules, so
what you read here is exactly what runs in production. This runner therefore
only VERIFIES; it never modifies source. Adding a step that writes to the
application tree re-creates the defect this consolidation removed.
"""

import os
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

# Verification steps only. Each must be read-only with respect to the app tree.
VERIFICATION_STEPS = [
    "scripts/smoke_test_pdf_renderer.py",
    "scripts/test_release_hardening_v50.py",
    "scripts/test_release_hardening_v52.py",
    "scripts/test_release_hardening_v54.py",
    "scripts/test_release_hardening_v55.py",
    "scripts/test_release_cleanup_v56.py",
    "scripts/test_page_level_integrity_v56.py",
    "scripts/test_release_quality_v56.py",
    "scripts/test_canonical_material_prompt.py",
    "scripts/test_release_final_v57.py",
    "scripts/test_micro_quality_polish.py",
    "scripts/test_material_release_integrity_v37.py",
    "scripts/test_substantive_lesson_integrity.py",
    "scripts/test_universal_quality.py",
    "scripts/test_publication_invariants.py",
    "scripts/test_publication_evidence.py",
    "scripts/test_source_of_truth.py",
]

COMPILE_TARGETS = [
    "server.py",
    "worker.py",
    "runtime_bootstrap.py",
    "services/ai_engine.py",
    "services/publication_invariants.py",
    "services/publication_evidence.py",
    "services/material_generation_prompt.py",
    "services/material_quality_guard.py",
    "services/content_engine.py",
    "services/bilingual_finisher.py",
    "services/pdf_renderer_v12.py",
    "services/pdf_academic_renderer.py",
    "services/legacy/pdf_pipeline.py",
]


def _clear_project_modules():
    """Drop cached project modules so each step imports current source."""
    prefixes = ("services", "database", "server", "worker", "runtime_bootstrap")
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith(prefixes):
            del sys.modules[mod_name]


def run_pipeline():
    total_start = time.perf_counter()
    step_count = len(VERIFICATION_STEPS)
    print(f"[AULAAI-BUILD] Running {step_count} verification steps against checked-in source...")

    for idx, rel_path in enumerate(VERIFICATION_STEPS, 1):
        script_path = ROOT / rel_path
        if not script_path.exists():
            print(f"[{idx}/{step_count}] ERROR: Missing script {rel_path}", file=sys.stderr)
            sys.exit(1)

        _clear_project_modules()
        t0 = time.perf_counter()

        try:
            runpy.run_path(str(script_path), run_name="__main__")
        except SystemExit as se:
            if se.code not in (0, None):
                print(f"[{idx}/{step_count}] FAILED {rel_path} with exit code {se.code}", file=sys.stderr)
                sys.exit(se.code)
        except Exception:
            # Subprocess fallback for steps needing clean process isolation.
            res = subprocess.run([sys.executable, str(script_path)], cwd=str(ROOT))
            if res.returncode != 0:
                print(f"[{idx}/{step_count}] FAILED {rel_path} with exit code {res.returncode}", file=sys.stderr)
                sys.exit(res.returncode)

        dt = time.perf_counter() - t0
        print(f"  [{idx:2d}/{step_count}] OK ({dt:4.2f}s) {rel_path}")

    print("[AULAAI-BUILD] Verifying bytecode compilation (py_compile)...")
    t_comp = time.perf_counter()
    compiled = 0
    for target in COMPILE_TARGETS:
        target_path = ROOT / target
        if target_path.exists():
            py_compile.compile(str(target_path), doraise=True)
            compiled += 1
    dt_comp = time.perf_counter() - t_comp
    print(f"  [py_compile] {compiled} files compiled cleanly ({dt_comp:4.2f}s)")

    total_time = time.perf_counter() - total_start
    print(f"[AULAAI-BUILD] ALL {step_count} VERIFICATION STEPS PASSED in {total_time:.2f}s!\n")


if __name__ == "__main__":
    run_pipeline()
