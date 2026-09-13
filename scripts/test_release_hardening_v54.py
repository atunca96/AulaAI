from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_quality_guard import enforce_material_integrity, sanitize_instructional_metalanguage


def run():
    lesson = {
        "pages": [
            {"type": "vocabulary", "items": [{"term": "banana", "phonetic": "[bəˈnænə]", "translation": "banana"}]},
            {"type": "grammar", "rules": [{"analysis": "banana is pronounced [banana]."}]},
        ]
    }
    out = enforce_material_integrity(lesson, "English", material_language="en")
    assert out["pages"][1]["rules"][0]["analysis"] == "banana is pronounced [bəˈnænə]."

    assert sanitize_instructional_metalanguage("Edat Durumu Case", "tr") == "Edat Durumu"

    guard = (ROOT / "services" / "material_quality_guard.py").read_text(encoding="utf-8")
    renderer = (ROOT / "services" / "pdf_renderer_v12.py").read_text(encoding="utf-8")
    assert "AULAAI_RELEASE_HARDENING_V54" in guard
    assert "AULAAI_RELEASE_HARDENING_V54" in renderer
    assert "_v54_repair_mcq_entailment" in guard
    assert "_v54_previous_localized_title" in renderer

    print("[V54] structural regression tests PASSED")


if __name__ == "__main__":
    run()
