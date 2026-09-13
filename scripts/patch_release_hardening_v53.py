from pathlib import Path

p = Path("services/ai_engine.py")
s = p.read_text(encoding="utf-8")
s = s.replace('"phonetic": "[IPA / phonetic guide]"', '"phonetic": "[standard IPA only]"', 1)
s = s.replace('"speaker": "Speaker",', '"speaker": "Proper name or target-language role",\n          "speaker_en": "English role or same proper name",\n          "speaker_tr": "Turkish role or same proper name",', 1)
s = s.replace('"text": "Utterance in {language}"', '"text": "Utterance only in {language}; no instructional-language gloss words"', 1)
p.write_text(s, encoding="utf-8")
print("Applied v53 schema hardening")
