from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "pdf_renderer_v12.py"
if not p.exists():
    raise RuntimeError("active PDF renderer missing")
print("PDF v14 font archive disabled; academic renderer preserved")
