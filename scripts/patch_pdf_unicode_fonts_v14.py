from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "pdf_renderer_v12.py"
if not p.exists():
    raise RuntimeError("active PDF renderer missing")
print("PDF unicode patch disabled; academic renderer left unchanged")
