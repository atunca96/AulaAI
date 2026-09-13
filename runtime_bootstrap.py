import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
runpy.run_path(str(ROOT / "scripts" / "patch_pdf_final_v40.py"), run_name="__main__")

server = ROOT / "server.py"
source = server.read_text(encoding="utf-8")
required = (
    "AULAAI_PDF_ACADEMIC_V43",
    "services.pdf_export_bridge",
)
missing = [x for x in required if x not in source]
if missing:
    raise RuntimeError("runtime PDF v43 bridge verification failed: " + ", ".join(missing))

print("[BOOT] academic PDF renderer bridge v43 verified")
runpy.run_path(str(server), run_name="__main__")
