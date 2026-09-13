from pathlib import Path

engine = Path("services/ai_engine.py")
s = engine.read_text(encoding="utf-8")
s = s.replace('"phonetic": "[IPA / phonetic guide]"', '"phonetic": "[standard IPA only; never learner respelling]"', 1)
s = s.replace('"speaker": "Speaker",', '"speaker": "Proper name or target-language role",\n          "speaker_en": "English role or same proper name",\n          "speaker_tr": "Turkish role or same proper name",', 1)
s = s.replace('"text": "Utterance in {language}"', '"text": "Utterance only in {language}; no instructional-language gloss words"', 1)
s = s.replace('FINAL SILENT PASS: canonical spelling/Unicode; pronunciation completeness and one-system consistency;', 'FINAL SILENT PASS: canonical spelling/Unicode; pronunciation completeness and one-system consistency; verify every stated count/list/category agrees internally;', 1)
engine.write_text(s, encoding="utf-8")

guard = Path("services/material_quality_guard.py")
g = guard.read_text(encoding="utf-8")
anchor = '    (r"\\bneuter\\b", "nötr"),\n)'
if anchor in g:
    g = g.replace(anchor, '    (r"\\bneuter\\b", "nötr"),\n    (r"\\bnominativ\\b", "Yalın Hâl"),\n    (r"\\bgenitiv\\b", "İlgi/Tamlayan Hâli"),\n    (r"\\bakkusativ\\b", "Belirtme Hâli"),\n    (r"\\bdativ\\b", "Yönelme Hâli"),\n)', 1)
guard.write_text(g, encoding="utf-8")
print("Applied v53 precision hardening")
