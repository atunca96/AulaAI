from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")

contract = r'''<aulaai_unified_quality_contract>
AULAAI_INLINE_PUBLICATION_QA_V51: Generate publication-grade material in this SAME call. No audit fields, second API call, retry, or extra lesson scope.
AULAAI_SCHEMA_FIRST_V54: JSON fields are typed semantic slots. Put correct content in the correct slot before returning JSON; downstream code must not be expected to infer, translate, filter, or semantically repair it.

FIELD OWNERSHIP:
- Target fields contain authentic {language}: target terms, examples, dialogue utterances, quoted forms, and target-form assessment options.
- Turkish instructional fields contain natural Turkish only except exact target forms being taught. English instructional fields contain natural English only except exact target forms.
- phonetic belongs only to its sibling target item and contains authoritative standard IPA. Never attach target IPA to a gloss, speaker label, or unrelated example.
- Speaker labels contain only the actual proper name or short role; never an utterance.

ASSESSMENT DOMAIN — STEM MUST PROVE THE ANSWER:
Choose one option domain per MCQ: target-form/grammar/spelling => all options target-language forms; pronunciation => all options the required notation; Turkish meaning/comprehension => all options Turkish; English meaning/comprehension => all options English. Never mix domains. Exactly four distinct plausible same-category options and one defensible answer. Re-solve so answer, correct_index and explanation converge. The stem itself must prove the answer. If proof needs any unstated real-world premise, rewrite it. A personal name alone, birthplace, residence, workplace, school, or city does not establish gender, nationality, ethnicity, profession, language ability, or identity.

DIALOGUE STRUCTURE:
Each turn uses separate slots: speaker = name/short target role; speaker_tr/speaker_en = localized role or same proper name; text = utterance only in {language}; line_tr/line_en = faithful instructional rendering. Never swap speaker and text. Never leave text empty while speaker contains a sentence.

WRITING-SYSTEM OBJECTS ARE DATA:
When teaching a letter, kana, character, diacritic, tone mark, vowel mark, length mark, combining mark, punctuation sign or orthographic symbol, emit the literal Unicode symbol itself. Never describe a mark then leave empty parentheses or empty quotes. Preserve legitimate combining/stress/tone marks, Japanese dakuten/handakuten/chōonpu, Arabic/Indic marks and ZWJ/ZWNJ. Natural multiscript languages are valid. Emit NFC Unicode with no replacement/noncharacter/control/soft-hyphen artifacts.

PRONUNCIATION — ONE SOURCE OF TRUTH:
Use standard IPA only for learner-facing pronunciation. No ad-hoc respellings or capitalization-for-stress such as Tet-rad, mi-TRO, mı-la-KO. If a lexical item recurs, its IPA must stay compatible with the same context and phonological analysis. Transliteration/romanization may exist only as a clearly separate pedagogical function. Preserve real stress, tone, vowel length, palatalization, reduction and assimilation.

TRUTH / CEFR / CONSISTENCY:
Grammar, spelling, phonology, valency, agreement, word order, particles, case/adposition government, register and meaning must be native-natural for {language}. Never impose another language's categories. Cross-check every inventory count, list membership, paradigm, rule and example. Absolute claims only when genuinely true in scope. Match CEFR {level}; test only material already taught or introduced as a fixed chunk.

FINAL SILENT PASS: validate by FIELD ROLE, not surface heuristics: correct language in each slot; one-domain MCQ options; Speaker labels contain only names/roles; non-empty utterances; literal writing-system symbols present; IPA attached to the correct sibling item with no competing representation; counts/rules/examples consistent; every MCQ solvable without an unstated real-world premise. Repair within this same call and return valid JSON only.
</aulaai_unified_quality_contract>'''

start = s.find("<aulaai_unified_quality_contract>")
end_tag = "</aulaai_unified_quality_contract>"
end = s.find(end_tag, start)
if start < 0 or end < 0:
    raise RuntimeError("schema-first contract anchor missing")
end += len(end_tag)
s = s[:start] + contract + s[end:]
p.write_text(s, encoding="utf-8")
print(f"Applied schema-first generation contract; chars={len(contract)}")
