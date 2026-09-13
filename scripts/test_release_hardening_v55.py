from pathlib import Path
import copy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_quality_guard import enforce_material_integrity, sanitize_instructional_metalanguage
from services.pdf_renderer_v12 import _v54_display_phonetic, _v54_pdf_unsafe_mcq


def run():
    workplace = {
        "type": "mcq",
        "prompt_tr": "Oleg okulda calisiyor. Onun meslegi nedir?",
        "options": ["A", "B", "C", "D"],
        "answer": "A",
        "explanation_tr": "Okul bir calisma yeridir.",
    }
    punctual = {
        "type": "mcq",
        "prompt_tr": "Ivan ise ___ gec kalir, cunku cok dakik bir insandir.",
        "options": ["never", "usually", "always", "often"],
        "answer": "never",
        "explanation_tr": "Dakik oldugu icin asla gec kalmaz.",
    }
    safe = {
        "type": "mcq",
        "prompt_tr": "Muhendis fabrikada hangi edati kullanir?",
        "options": ["A", "B", "C", "D"],
        "answer": "C",
        "explanation_tr": "Ders kuralina gore dogru secenek C.",
    }

    assert _v54_pdf_unsafe_mcq(workplace, workplace["prompt_tr"], True)
    assert _v54_pdf_unsafe_mcq(punctual, punctual["prompt_tr"], True)
    assert not _v54_pdf_unsafe_mcq(safe, safe["prompt_tr"], True)

    lesson = {"pages": [copy.deepcopy(workplace), copy.deepcopy(punctual), copy.deepcopy(safe)]}
    out = enforce_material_integrity(lesson, "Example", material_language="tr")
    assert len(out["pages"]) == 1, out
    assert out["pages"][0]["answer"] == "C"

    assert _v54_display_phonetic("[[ipa1] / [ipa2]]") == "[ipa1] / [ipa2]"
    assert _v54_display_phonetic("[b] / [b2]") == "[b] / [b2]"
    assert _v54_display_phonetic("b / b2") == "[b] / [b2]"
    assert _v54_display_phonetic("[kto]") == "[kto]"

    cleaned = sanitize_instructional_metalanguage("Zero-Copula yapisi nominatif ve Genitif ile aciklanir.", "tr")
    assert "Zero-Copula" not in cleaned
    assert "nominatif" not in cleaned
    assert "Genitif" not in cleaned
    assert "sıfır bağlayıcı" in cleaned.casefold()
    assert "Yalın Hâl" in cleaned
    assert "İlgi/Tamlayan Hâli" in cleaned

    print("[V55] surgical inference/IPA/metalanguage regression tests PASSED")


if __name__ == "__main__":
    run()
