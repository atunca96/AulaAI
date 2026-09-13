from pathlib import Path
import runpy

root = Path(__file__).resolve().parents[1]
runpy.run_path(str(root / "scripts" / "patch_actual_pdf_export_v34_base.py"), run_name="__main__")
runpy.run_path(str(root / "scripts" / "patch_pdf_export_final_v37.py"), run_name="__main__")
print("Applied v34+v37 final PDF export pipeline")
