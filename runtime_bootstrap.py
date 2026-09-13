import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Railway can reuse image layers / mounted runtime state. Apply the PDF export
# finalizers against the exact server.py that will actually execute, immediately
# before startup. Both scripts are written to be idempotent.
for rel in (
    "scripts/patch_actual_pdf_export_v34.py",
    "scripts/patch_pdf_export_final_v37.py",
):
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"runtime PDF finalizer missing: {rel}")
    runpy.run_path(str(path), run_name="__main__")

server = ROOT / "server.py"
source = server.read_text(encoding="utf-8")
required = (
    "AulaAI Eğitim Sistemi · Bağımsız Ders Materyali",
    "def _pdf_export_language_name(",
    "requested_lang =",
    '"pronunciation": ("Pronunciation", "Telaffuz")',
    '"communication": ("Communication", "İletişim")',
)
missing = [x for x in required if x not in source]
if missing:
    raise RuntimeError("runtime PDF verification failed: " + ", ".join(missing))

print("[BOOT] Runtime PDF exporter verified on executable server.py")
runpy.run_path(str(server), run_name="__main__")
