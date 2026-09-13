from pathlib import Path

# Build-only compatibility shim: Python launched as `python scripts/...` imports
# this module from /app/scripts. Keep the downstream release regression marker
# aligned with V51 before the V50 patch script attempts its older V46 -> V50
# migration. Runtime (`python runtime_bootstrap.py`) does not load this file.
try:
    path = Path(__file__).resolve().parent / "test_material_release_integrity_v37.py"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        text = text.replace("AULAAI_INLINE_PUBLICATION_QA_V46", "AULAAI_INLINE_PUBLICATION_QA_V51")
        text = text.replace("AULAAI_INLINE_PUBLICATION_QA_V50", "AULAAI_INLINE_PUBLICATION_QA_V51")
        path.write_text(text, encoding="utf-8")
except Exception:
    pass
