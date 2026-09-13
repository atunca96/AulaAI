from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_quality_guard import safe_unicode_normalize, enforce_material_integrity
from services.pdf_renderer_v12 import _e, _pick


def run():
    assert safe_unicode_normalize("по\u00adрусски") == "по-русски"
    assert safe_unicode_normalize("по\u2011русски") == "по-русски"
    assert safe_unicode_normalize("по\ufffeрусски") == "по-русски"
    assert safe_unicode_normalize("sertlik\ufffeyumuşaklık") == "sertlik-yumuşaklık"
    assert safe_unicode_normalize("11\u201319") == "11\u201319"
    assert safe_unicode_normalize("A\u2014B") == "A\u2014B"
    assert "\u200d" in safe_unicode_normalize("क्\u200dष")
    assert _e("по\ufffeрусски") == "по-русски"

    payload = {
        "pages": [{
            "type": "vocabulary",
            "items": [{
                "term": "И и",
                "phonetic": "",
                "translation": "Letter I (sound: [i])",
                "translation_tr": "İ harfi (ses: [i])",
            }]
        }]
    }
    cleaned = enforce_material_integrity(payload, "Russian", material_language="tr")
    item = cleaned["pages"][0]["items"][0]
    assert item["phonetic"] == "[i]"
    assert "(ses: [i])" not in item.get("translation_tr", "")
    assert "(sound: [i])" not in item.get("translation", "")

    payload2 = {
        "pages": [{
            "type": "vocabulary",
            "items": [{
                "term": "Ж ж",
                "phonetic": "[ʐ]",
                "translation": "Letter Zh (sound: [j])",
                "translation_tr": "J harfi (ses: [j])",
            }]
        }]
    }
    cleaned2 = enforce_material_integrity(payload2, "Russian", material_language="tr")
    item2 = cleaned2["pages"][0]["items"][0]
    assert item2["phonetic"] == "[ʐ]"
    assert "[j]" not in item2["translation"]
    assert "[j]" not in item2["translation_tr"]

    payload3 = {"pages": [{"items": [{"term": "дом", "phonetic": "[ˈdo-mə]"}], "text": "дом [ˈdo-mə]"}]}
    cleaned3 = enforce_material_integrity(payload3, "Russian", material_language="tr")
    assert cleaned3["pages"][0]["items"][0]["phonetic"] == "[ˈdomə]"
    assert "[ˈdomə]" in cleaned3["pages"][0]["text"]

    bad = {"type": "mcq", "prompt": "Q", "options": ["a", "a", "c", "d"], "answer": "a"}
    lesson = {"pages": [{"type": "overview", "text": "x"}, bad]}
    out = enforce_material_integrity(lesson, "German", material_language="tr")
    assert len(out["pages"]) == 2
    assert "_integrity_removed_mcq" not in out

    good = {"type": "mcq", "prompt": "Q", "options": ["a", "b", "c", "d"], "answer": "c", "correct_index": 0}
    out2 = enforce_material_integrity({"pages": [good]}, "German", material_language="tr")
    assert out2["pages"][0]["correct_index"] == 2

    assert _pick({"text": "Hello", "text_tr": "Merhaba"}, "text", "text_tr", True) == "Merhaba"
    assert _pick({"text": "Hello"}, "text", "text_tr", True) == ""
    assert _pick({"text_tr": "Merhaba"}, "text", "text_tr", False) == ""

    engine = (ROOT / "services" / "ai_engine.py").read_text(encoding="utf-8")
    assert "AULAAI_INLINE_PUBLICATION_QA_V50" in engine
    assert "material_language=material_language" in engine
    start = engine.index("<aulaai_unified_quality_contract>")
    end = engine.index("</aulaai_unified_quality_contract>", start) + len("</aulaai_unified_quality_contract>")
    contract = engine[start:end]
    assert len(contract) < 7000, len(contract)
    assert "ad-hoc respelling" in contract
    assert "speaker role" in contract
    assert "hidden-world inference" in contract

    print("[V50] All release hardening regression tests PASSED")


if __name__ == "__main__":
    run()
