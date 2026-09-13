import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
runpy.run_path(str(ROOT / "scripts" / "patch_pdf_final_v40.py"), run_name="__main__")

server = ROOT / "server.py"
source = server.read_text(encoding="utf-8")
required = (
    "AulaAI Eğitim Sistemi — Bağımsız Ders Materyali",
    "def _pdf_language_name(",
    "AulaAI PDF Engine v42",
    "_pdf_active_labels",
)
missing = [x for x in required if x not in source]
if missing:
    raise RuntimeError("runtime PDF v42 verification failed: " + ", ".join(missing))

print("[BOOT] active PDF exporter v42 verified")
runpy.run_path(str(server), run_name="__main__")
