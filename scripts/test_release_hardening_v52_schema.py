from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(ROOT / "scripts" / "patch_release_hardening_v53.py"), run_name="__main__")

from services.material_quality_guard import sanitize_instructional_metalanguage
from services.pdf_renderer_v12 import _pick, _v52_dialogue_speaker

assert _v52_dialogue_speaker({"speaker": "Студент", "speaker_tr": "Öğrenci", "speaker_en": "Student"}, True) == "Öğrenci"
assert sanitize_instructional_metalanguage("Nominativ", "tr") == "Yalın Hâl"
assert sanitize_instructional_metalanguage("Genitiv", "tr") == "İlgi/Tamlayan Hâli"

engine = (ROOT / "services" / "ai_engine.py").read_text(encoding="utf-8")
assert "AULAAI_RELEASE_HARDENING_V52" in engine
assert '"phonetic": "[standard IPA only; never learner respelling]"' in engine
assert '"speaker_tr": "Turkish role or same proper name"' in engine
assert '"speaker_en": "English role or same proper name"' in engine
assert '"text": "Utterance only in {language}; no instructional-language gloss words"' in engine
assert "AULAAI_SCHEMA_FIRST_V54" in engine
assert "ASSESSMENT DOMAIN" in engine
assert "WRITING-SYSTEM OBJECTS ARE DATA" in engine
assert "PRONUNCIATION — ONE SOURCE OF TRUTH" in engine
assert "personal name alone" in engine
assert "unstated real-world premise" in engine
print("[V53-SCHEMA] regression tests PASSED")
