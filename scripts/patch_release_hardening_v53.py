from pathlib import Path
import runpy

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

# Replace the old compact prompt contract with the schema-first contract in the
# same already-wired build stage. No new runtime call/retry/filter is introduced.
runpy.run_path("scripts/patch_schema_first_v54.py", run_name="__main__")
print("Applied v53 precision hardening + schema-first generation contract")
