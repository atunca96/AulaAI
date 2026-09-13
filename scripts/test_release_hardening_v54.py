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

    unsafe = {
        "pages": [
            {
                "type": "assessment",
                "prompt": "This is Alex. ___ is here.",
                "options": ["A", "B", "C", "D"],
                "answer": "A",
                "explanation": "Alex is a woman's name, so choose the female form.",
            },
            {
                "type": "mcq",
                "prompt": "Alex was born in Country X. Alex is ____.",
                "options": ["A", "B", "C", "D"],
                "answer": "A",
                "explanation": "Choose the nationality form.",
            },
            {
                "type": "mcq",
                "prompt": "Choose the correct form for a feminine noun.",
                "options": ["A", "B", "C", "D"],
                "answer": "A",
                "explanation": "The noun is explicitly feminine.",
            },
        ]
    }
    safe = enforce_material_integrity(unsafe, "Example", material_language="en")
    assert len(safe["pages"]) == 1
    assert safe["pages"][0]["answer"] == "A"

    assert sanitize_instructional_metalanguage("Edat Durumu Case", "tr") == "Edat Durumu"

    guard = (ROOT / "services" / "material_quality_guard.py").read_text(encoding="utf-8")
    renderer = (ROOT / "services" / "pdf_renderer_v12.py").read_text(encoding="utf-8")
    assert "AULAAI_RELEASE_HARDENING_V54" in guard
    assert "AULAAI_RELEASE_HARDENING_V54" in renderer
    assert "_v54_prune_unsafe_mcqs" in guard
    assert "_v54_pdf_unsafe_mcq" in renderer
    assert "_v54_display_phonetic" in renderer
    assert "Temel Ses (IPA)" in renderer
    assert "target = _v54_instructional" in renderer

    print("[V54] realistic quality regression tests PASSED")


if __name__ == "__main__":
    run()
