from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_quality_guard import enforce_material_integrity, sanitize_instructional_metalanguage
from services.pdf_renderer_v12 import _v54_display_phonetic, _v54_pdf_unsafe_mcq


def run():
    lesson = {
        "pages": [
            {
                "type": "mcq",
                "prompt_tr": "Oleg okulda çalışıyor. Onun mesleği nedir?",
                "options": ["öğretmen", "doktor", "aşçı", "mühendis"],
                "answer": "öğretmen",
                "explanation_tr": "Okul öğretmenin çalışma yeridir.",
            },
            {
                "type": "mcq",
                "prompt_tr": "İvan işe ___ geç kalır, çünkü çok dakik bir insandır.",
                "options": ["никогда не", "обычно", "всегда", "часто"],
                "answer": "никогда не",
                "explanation_tr": "Dakik olduğu için asla geç kalmaz.",
            },
            {
                "type": "mcq",
                "prompt_tr": "Mühendis fabrika___ çalışıyor.",
                "options": ["из", "с", "на", "в"],
                "answer": "на",
                "explanation_tr": "на заводе kalıbı kullanılır.",
            },
        ]
    }
    out = enforce_material_integrity(lesson, "Russian", material_language="tr")
    assert len(out["pages"]) == 1, out
    assert out["pages"][0]["answer"] == "на"

    assert _v54_pdf_unsafe_mcq(lesson["pages"][0], "Oleg okulda çalışıyor. Onun mesleği nedir?", True)
    assert _v54_pdf_unsafe_mcq(lesson["pages"][1], "İvan işe ___ geç kalır, çünkü çok dakik bir insandır.", True)

    assert _v54_display_phonetic("[[ˈruskʲɪj] / [ˈruskəjə]]") == "[ˈruskʲɪj] / [ˈruskəjə]"
    assert _v54_display_phonetic("[b] / [bʲ]") == "[b] / [bʲ]"
    assert _v54_display_phonetic("b / bʲ") == "[b] / [bʲ]"
    assert _v54_display_phonetic("[kto]") == "[kto]"

    cleaned = sanitize_instructional_metalanguage("Zero-Copula yapısı nominatif ve Genitif ile açıklanır.", "tr")
    assert "Zero-Copula" not in cleaned
    assert "nominatif" not in cleaned
    assert "Genitif" not in cleaned
    assert "sıfır bağlayıcı" in cleaned
    assert "Yalın Hâl" in cleaned

    print("[V55] surgical inference/IPA/metalanguage regression tests PASSED")


if __name__ == "__main__":
    run()
