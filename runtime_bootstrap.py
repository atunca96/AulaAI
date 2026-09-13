import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
server = ROOT / "server.py"
source = server.read_text(encoding="utf-8")

required = (
    "AulaAI Eğitim Sistemi · Bağımsız Ders Materyali",
    "_pdf_final_tr_labels",
    "AulaAI PDF Engine v37-final",
)
missing = [x for x in required if x not in source]
if missing:
    raise RuntimeError("runtime PDF verification failed: " + ", ".join(missing))

print("[BOOT] Final PDF exporter verified")
runpy.run_path(str(server), run_name="__main__")
