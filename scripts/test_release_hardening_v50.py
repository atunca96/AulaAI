from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# V51 intentionally runs from this already-wired build step so no extra runtime
# model call/retry or Docker-stage expansion is introduced.
runpy.run_path(str(ROOT / "scripts" / "patch_release_hardening_v51.py"), run_name="__main__")

from services.material_quality_guard import safe_unicode_normalize, enforce_material_integrity, sanitize_dialogue_speaker
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

    payload = {"pages": [{"type": "vocabulary", "items": [{
        "term": "И и", "phonetic": "", "translation": "Letter I (sound: [i])",
        "translation_tr": "İ harfi (ses: [i])",
    }]}]}
    item = enforce_material_integrity(payload, "Russian", material_language="tr")["pages"][0]["items"][0]
    assert item["phonetic"] == "[i]"
    assert "(ses: [i])" not in item.get("translation_tr", "")
    assert "(sound: [i])" not in item.get("translation", "")

    payload2 = {"pages": [{"type": "vocabulary", "items": [{
        "term": "Ж ж", "phonetic": "[ʐ]", "translation": "Letter Zh (sound: [j])",
        "translation_tr": "J harfi (ses: [j])",
    }]}]}
    item2 = enforce_material_integrity(payload2, "Russian", material_language="tr")["pages"][0]["items"][0]
    assert item2["phonetic"] == "[ʐ]"
    assert "[j]" not in item2["translation"] and "[j]" not in item2["translation_tr"]

    payload3 = {"pages": [{"items": [{"term": "дом", "phonetic": "[ˈdo-mə]"}], "text": "дом [ˈdo-mə]"}]}
    cleaned3 = enforce_material_integrity(payload3, "Russian", material_language="tr")
    assert cleaned3["pages"][0]["items"][0]["phonetic"] == "[ˈdomə]"
    assert "[ˈdomə]" in cleaned3["pages"][0]["text"]

    assert sanitize_dialogue_speaker("Официант (Waiter)") == "Официант"
    assert sanitize_dialogue_speaker("Anna (Student)") == "Anna"
    assert sanitize_dialogue_speaker("Анна (Anna)") == "Анна"
    assert sanitize_dialogue_speaker("Öğretmen") == "Öğretmen"

    bad = {"type": "mcq", "prompt": "Q", "options": ["a", "a", "c", "d"], "answer": "a"}
    out = enforce_material_integrity({"pages": [{"type": "overview", "text": "x"}, bad]}, "German", material_language="tr")
    assert len(out["pages"]) == 2 and "_integrity_removed_mcq" not in out

    good = {"type": "mcq", "prompt": "Q", "options": ["a", "b", "c", "d"], "answer": "c", "correct_index": 0}
    out2 = enforce_material_integrity({"pages": [good]}, "German", material_language="tr")
    assert out2["pages"][0]["correct_index"] == 2

    assert _pick({"text": "Hello", "text_tr": "Merhaba"}, "text", "text_tr", True) == "Merhaba"
    assert _pick({"text": "Hello"}, "text", "text_tr", True) == ""
    assert _pick({"text_tr": "Merhaba"}, "text", "text_tr", False) == ""

    engine = (ROOT / "services" / "ai_engine.py").read_text(encoding="utf-8")
    assert "AULAAI_INLINE_PUBLICATION_QA_V51" in engine
    assert "material_language=material_language" in engine
    start = engine.index("<aulaai_unified_quality_contract>")
    end = engine.index("</aulaai_unified_quality_contract>", start) + len("</aulaai_unified_quality_contract>")
    contract = engine[start:end]
    assert len(contract) < 6500, len(contract)
    assert "STEM MUST PROVE THE ANSWER" in contract
    assert "unstated real-world premise" in contract
    assert "Tet-rad" in contract
    assert "Speaker labels contain only" in contract

    print(f"[V51] All release hardening regression tests PASSED; contract chars={len(contract)}")


if __name__ == "__main__":
    run()
