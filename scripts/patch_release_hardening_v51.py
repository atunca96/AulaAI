from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"
engine_path = ROOT / "services" / "ai_engine.py"

TAG = "# AULAAI_RELEASE_HARDENING_V51"

guard = guard_path.read_text(encoding="utf-8")
if TAG not in guard:
    guard += r'''

# AULAAI_RELEASE_HARDENING_V51
def sanitize_dialogue_speaker(value):
    """Keep the canonical speaker label; remove trailing annotation metadata."""
    text = safe_unicode_normalize(str(value or "")).strip()
    if not text:
        return text
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\s*\([^()\n]{1,80}\)\s*$", "", text).strip()
    return text
'''
    guard_path.write_text(guard, encoding="utf-8")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    import_line = "from database import db_connection\n"
    if import_line not in renderer:
        raise RuntimeError("v51 renderer import anchor missing")
    renderer = renderer.replace(import_line, import_line + "from services.material_quality_guard import sanitize_dialogue_speaker\n", 1)
    old = "spk = d.get('speaker') or d.get('name') or '?'"
    new = "spk = sanitize_dialogue_speaker(d.get('speaker') or d.get('name') or '?')"
    if old not in renderer:
        raise RuntimeError("v51 speaker render anchor missing")
    renderer = renderer.replace(old, new, 1)
    renderer += "\n# AULAAI_RELEASE_HARDENING_V51\n"
    renderer_path.write_text(renderer, encoding="utf-8")

engine = engine_path.read_text(encoding="utf-8")
contract = r'''<aulaai_unified_quality_contract>
AULAAI_INLINE_PUBLICATION_QA_V51: Before returning final JSON, silently solve and repair the draft once inside this same call. Add no audit fields, no extra sections, no second API call, and do not increase lesson scope.

1. CANONICAL LANGUAGE / ORTHOGRAPHY
- Target-language text must use authentic canonical spelling, morphology, punctuation and legitimate scripts for {language}. The same lexical item must never appear with two spellings in one lesson. Preserve required internal separators/hyphens and valid diacritics/stress/tone marks; emit NFC Unicode with no replacement/noncharacter/control/soft-hyphen artifacts.
- Multiscript languages, IPA, CEFR codes, URLs, proper names, abbreviations and explicitly labeled transliteration are legitimate.

2. PRONUNCIATION — ONE AUTHORITATIVE SYSTEM
- When pronunciation is pedagogically required or a pronunciation column exists, `phonetic` must be populated and is authoritative. Never duplicate or contradict pronunciation inside meaning/translation/gloss.
- If IPA is used, use standard unsplit IPA only. Do not add learner respellings, capitalization-for-stress, phonetic-looking Latin approximations, or syllable-split demonstrations such as `Tet-rad`, `mi-TRO`, `mı-la-KO` in prose/dialogue. A target word may be syllabified only when syllabification itself is the explicit lesson objective; do not pair it with a second Latin respelling.
- Established transliteration systems may appear only in their own clearly distinct pedagogical field.

3. INSTRUCTIONAL-LANGUAGE ISOLATION
- Every learner-facing heading, label, speaker role, table label, explanation, instruction, gloss and metadata description must use the selected material/instructional language. Speaker labels contain only the actual name or the correctly localized role — never `Role (English Role)`, duplicate transliteration, or foreign metadata annotations.
- Target-language examples/quotations, proper nouns, international notation and deliberate multilingual comparisons are exempt. Required localized counterparts must express the same proposition and must not be left empty when their counterpart is populated.

4. LINGUISTIC TRUTH / INTERNAL CONSISTENCY
- Grammar, spelling, phonology, stress, valency, agreement, case/adposition government, word order, tense/aspect/mood, particles, register and lexical meaning must be accurate and native-natural. Never project another language's categories onto {language}.
- Cross-check every rule against every example/table/dialogue in the lesson. If an example contradicts a rule, repair one before output. Absolute words such as always/never/all/only are allowed only for genuinely exceptionless claims inside the stated scope.
- Do not restate the same teaching fact in multiple fields without a clear exercise purpose; preserve depth while removing redundant output.

5. CEFR / NATURALNESS
- Match CEFR {level} strictly. A1/A2 remain concrete, high-frequency and communicative with minimal metalanguage; higher levels may add productive nuance/register as appropriate. Dialogues must sound like plausible native interaction, not translation templates.
- Test only material already taught or explicitly introduced as a fixed chunk.

6. MCQ — STEM MUST PROVE THE ANSWER
- Exactly 4 distinct plausible same-category options and exactly 1 defensible answer. Before finalizing EACH MCQ, silently prove in one sentence that the stem itself entails the keyed answer using only language knowledge explicitly taught in the lesson. Do not output that proof.
- If the proof requires ANY unstated real-world premise, rewrite the stem/options. Residence, birthplace, city lived in, workplace, school or a personal name do not establish nationality, occupation or another answer-relevant identity fact. Example: “Anna lived in London” does NOT entail `англичанка`; the stem must explicitly provide the fact needed to select that form.
- Re-solve every MCQ from stem/options after drafting. `answer`, `correct_index` and explanation must identify the same option. Difficulty must come from {language}, not trivia, arithmetic or hidden-world inference.

FINAL SILENT PASS: canonical spelling/Unicode; pronunciation completeness and one-system consistency; no foreign speaker/label metadata; rule-example consistency; CEFR fit; natural dialogue; and for every MCQ ask: “Can the keyed answer be proven from the stem alone without an unstated premise?” If no, rewrite it now. Return valid JSON only.
</aulaai_unified_quality_contract>'''

start = engine.find("<aulaai_unified_quality_contract>")
end_tag = "</aulaai_unified_quality_contract>"
end = engine.find(end_tag, start)
if start < 0 or end < 0:
    raise RuntimeError("v51 unified contract anchor missing")
end += len(end_tag)
engine = engine[:start] + contract + engine[end:]
engine_path.write_text(engine, encoding="utf-8")
print(f"Applied v51 release hardening; unified contract chars={len(contract)}")
