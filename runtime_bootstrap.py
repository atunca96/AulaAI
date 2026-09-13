import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Apply PDF finalizers against the exact server.py that will execute. v38 is
# intentionally last because it patches/verifies the live downloadable endpoint.
for rel in (
    "scripts/patch_actual_pdf_export_v34.py",
    "scripts/patch_pdf_export_final_v37.py",
    "scripts/patch_pdf_actual_endpoint_v38.py",
):
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"runtime PDF finalizer missing: {rel}")
    runpy.run_path(str(path), run_name="__main__")

server = ROOT / "server.py"
source = server.read_text(encoding="utf-8")
required = (
    "AulaAI Eğitim Sistemi — Bağımsız Ders Materyali",
    "_pdf_tr_labels = {",
    "_pdf_tr_language_names = {",
    '"AulaAI PDF Engine v38"',
)
missing = [x for x in required if x not in source]
if missing:
    raise RuntimeError("runtime live PDF verification failed: " + ", ".join(missing))

print("[BOOT] Live downloadable PDF endpoint verified as v38")
runpy.run_path(str(server), run_name="__main__")
