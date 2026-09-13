from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_quality_guard import sanitize_instructional_metalanguage

engine = (ROOT / "services" / "ai_engine.py").read_text(encoding="utf-8")
assert '"phonetic": "[standard IPA only; never learner respelling]"' in engine
assert '"speaker_tr": "Turkish role or same proper name"' in engine
assert '"speaker_en": "English role or same proper name"' in engine
assert '"text": "Utterance only in {language}; no instructional-language gloss words"' in engine
assert "verify every stated count/list/category agrees internally" in engine

assert sanitize_instructional_metalanguage("Nominativ", "tr") == "Yalın Hâl"
assert sanitize_instructional_metalanguage("Genitiv", "tr") == "İlgi/Tamlayan Hâli"
assert sanitize_instructional_metalanguage("Akkusativ", "tr") == "Belirtme Hâli"
assert sanitize_instructional_metalanguage("Dativ", "tr") == "Yönelme Hâli"
assert sanitize_instructional_metalanguage('Rusça "Nominativ" terimi', "tr") == 'Rusça "Nominativ" terimi'

print("[V53] precision regression tests PASSED")
