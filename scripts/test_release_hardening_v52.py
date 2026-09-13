from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_quality_guard import sanitize_instructional_metalanguage
from services.pdf_renderer_v12 import _pick, _v52_dialogue_speaker


def run():
    assert _v52_dialogue_speaker({"speaker": "Студент", "speaker_tr": "Öğrenci", "speaker_en": "Student"}, True) == "Öğrenci"
    assert _v52_dialogue_speaker({"speaker": "Преподаватель", "speaker_tr": "Öğretmen"}, True) == "Öğretmen"
    assert _v52_dialogue_speaker({"speaker": "Анна"}, True) == "Анна"

    text = "он (masculine) vs она (feminine) vs оно (neuter)"
    assert sanitize_instructional_metalanguage(text, "tr") == "он (eril) vs она (dişil) vs оно (nötr)"
    assert sanitize_instructional_metalanguage('İngilizce "masculine" sözcüğü', "tr") == 'İngilizce "masculine" sözcüğü'
    assert sanitize_instructional_metalanguage("masculine", "en") == "masculine"
    assert _pick({"text_tr": "Prepositional hali"}, "text", "text_tr", True) == "Edat Durumu hali"
    assert sanitize_instructional_metalanguage("Nominativ", "tr") == "Yalın Hâl"
    assert sanitize_instructional_metalanguage("Genitiv", "tr") == "İlgi/Tamlayan Hâli"

    engine = (ROOT / "services" / "ai_engine.py").read_text(encoding="utf-8")
    assert "AULAAI_RELEASE_HARDENING_V52" in engine
    assert '"phonetic": "[standard IPA only; never learner respelling]"' in engine
    assert '"speaker_tr": "Turkish role or same proper name"' in engine
    assert '"speaker_en": "English role or same proper name"' in engine
    assert '"text": "Utterance only in {language}; no instructional-language gloss words"' in engine
    assert "verify every stated count/list/category agrees internally" in engine
    assert "personal name alone" in engine

    print("[V53] precision localization/schema regression tests PASSED")


if __name__ == "__main__":
    run()
