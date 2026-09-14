from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
engine = (ROOT / "services" / "ai_engine.py").read_text(encoding="utf-8")

for marker in (
    "AULAAI_SCHEMA_FIRST_V54",
    "FIELD OWNERSHIP IS ABSOLUTE",
    "ASSESSMENT TYPE DETERMINES OPTION LANGUAGE",
    "DIALOGUE IS STRUCTURAL, NOT FREE-FORM",
    "WRITING-SYSTEM OBJECTS ARE DATA",
    "PRONUNCIATION HAS ONE SOURCE OF TRUTH",
    "no sentence-sized speaker values or empty dialogue utterances",
    "no missing literal writing-system symbol",
    "no hidden-world inference",
):
    assert marker in engine, marker

assert '"phonetic": "[standard IPA only; never learner respelling]"' in engine
assert '"speaker": "Proper name or target-language role"' in engine
assert '"speaker_en": "English role or same proper name"' in engine
assert '"speaker_tr": "Turkish role or same proper name"' in engine
assert '"text": "Utterance only in {language}; no instructional-language gloss words"' in engine

print("[SCHEMA-FIRST] typed generation contract regressions PASSED")
