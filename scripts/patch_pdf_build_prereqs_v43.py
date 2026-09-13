from pathlib import Path
import runpy

root = Path(__file__).resolve().parents[1]

# One build-time PDF mutation only: wire the existing /export-pdf endpoint to
# services/pdf_renderer_v12.py. The renderer itself is committed source and must
# not be rewritten by a chain of historical PDF patches.
runpy.run_path(str(root / "scripts" / "patch_pdf_academic_renderer.py"), run_name="__main__")

print("PDF build ready: single renderer hook -> services/pdf_renderer_v12.py")
