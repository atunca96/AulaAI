import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
server = ROOT / "server.py"
print("[BOOT] starting AulaAI")
runpy.run_path(str(server), run_name="__main__")
