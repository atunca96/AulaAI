from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_quality_guard import _v58_turkish_publication_text, enforce_material_integrity
from services import pdf_renderer_v12 as renderer


def run():
    alphabet = "Rus Kiril alfabesi 33 harften oluşur: 10 sesli harf (а, е, ё, и, й, о, у, ы, э, ю, я), 21 sessiz harf ve 2 işaret."
    cleaned = _v58_turkish_publication_text(alphabet, russian=True)
    assert "10 sesli harf (а, е, ё, и, о, у, ы, э, ю, я)" in cleaned
    assert "и, й, о" not in cleaned

    stress = "11 ile 19 arasındaki sayılar düzenli olarak -надцать ile biter ve vurgu daima -дцать ekinden önceki heceye (-на-) düşer."
    cleaned = _v58_turkish_publication_text(stress, russian=True)
    assert "12–19" in cleaned
    assert "одиннадцать" in cleaned
    assert "-дин-" in cleaned
    assert "vurgu daima" not in cleaned

    assert _v58_turkish_publication_text("Soru zamiri canl具合 durumunu yansıtır.") == "Soru zamiri canlılık durumunu yansıtır."
    assert _v58_turkish_publication_text("Rusçada tanımlık (harf-i tarif / article) yoktur.") == "Rusçada tanımlık yoktur."
    assert _v58_turkish_publication_text("tamlayan çoğul (Genitivus pluralis) hali") == "tamlayan çoğul hâli"

    lesson = {
        "pages": [{
            "type": "overview",
            "text_tr": alphabet + " " + stress + " Soru zamiri canl具合 durumunu yansıtır.",
            "note_tr": "Rusçada tanımlık (harf-i tarif / article) yoktur.",
            "analysis_tr": "tamlayan çoğul (Genitivus pluralis) hali",
            "example": "й",
        }]
    }
    out = enforce_material_integrity(lesson, language="Russian", material_language="tr")
    page = out["pages"][0]
    assert "и, й, о" not in page["text_tr"]
    assert "vurgu daima" not in page["text_tr"]
    assert "具合" not in page["text_tr"]
    assert "article" not in page["note_tr"].lower()
    assert "Genitivus" not in page["analysis_tr"]
    assert page["example"] == "й"

    # Non-Russian material must not receive Russian-specific factual rewrites.
    other = enforce_material_integrity({"pages": [{"type": "overview", "text_tr": alphabet}]}, language="Spanish", material_language="tr")
    assert "и, й, о" in other["pages"][0]["text_tr"]

    # Renderer boundary must perform the same cleanup for already-persisted DB content.
    normalized = renderer._normalize_content({"pages": [{"type": "overview", "text_tr": alphabet + " Soru zamiri canl具合 durumunu yansıtır."}]}, "Russian")
    rendered_text = normalized["pages"][0]["text_tr"]
    assert "и, й, о" not in rendered_text
    assert "具合" not in rendered_text

    source = (ROOT / "services" / "pdf_renderer_v12.py").read_text(encoding="utf-8")
    assert "AULAAI_RELEASE_FINAL_V58" in source

    print("[V58] zero-cost final factual/publication regression tests PASSED")


if __name__ == "__main__":
    run()
