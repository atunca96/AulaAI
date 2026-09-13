from pathlib import Path
import runpy

root = Path(__file__).resolve().parents[1]
for name in (
    "patch_pdf_title_localization.py",
    "patch_pdf_zero_ai_export.py",
    "patch_pdf_picker_ui.py",
    "patch_pdf_academic_renderer.py",
    "patch_pdf_academic_renderer_v4.py",
    "patch_pdf_academic_renderer_v5.py",
    "patch_pdf_academic_renderer_v6.py",
    "patch_pdf_academic_renderer_v7.py",
    "patch_pdf_academic_renderer_v8.py",
    "patch_pdf_semantic_integrity_v9.py",
):
    runpy.run_path(str(root / "scripts" / name), run_name="__main__")
print("Applied proven PDF build prerequisites; runtime patch stacking remains disabled")
