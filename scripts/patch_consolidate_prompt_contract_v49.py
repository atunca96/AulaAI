from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')

UNIFIED_QUALITY_CONTRACT = """<aulaai_unified_quality_contract>
AULAAI_INLINE_PUBLICATION_QA_V46: Produce publication-grade language material in ONE generation pass. Do not add audit fields, extra calls, retries, or post-generation repair assumptions.
AULAAI_SCHEMA_FIRST_V54: Treat the JSON schema as a typed intermediate representation. Correctness comes from putting the right content in the right field before JSON is returned; never rely on downstream filtering to reinterpret or repair meaning.

1. FIELD OWNERSHIP IS ABSOLUTE
- TARGET fields contain only authentic {language}: target terms, target examples, target dialogue utterances, target-form MCQ options, and quoted target-language forms.
- TURKISH instructional fields (*_tr and Turkish-facing meaning/explanation fields) contain natural Turkish only, except exact target-language forms being taught. Do not insert English glosses, English answer options, or English grammatical labels into Turkish prose.
- ENGLISH instructional fields (*_en / English-facing fields) contain natural English only, except exact target-language forms being taught.
- PHONETIC belongs only to its sibling target term/expression and is standard IPA in brackets. Never attach target IPA to a translation, gloss, speaker label, or unrelated example. Never provide a second ad-hoc learner respelling for the same item.

2. ASSESSMENT TYPE DETERMINES OPTION LANGUAGE
Before writing each MCQ, decide its answer domain and keep all four options in exactly that domain:
- target-form / grammar / spelling / pronunciation choice -> all options are target-language forms or IPA as appropriate;
- Turkish meaning / comprehension choice in Turkish material -> all options are Turkish;
- English meaning / comprehension choice in English material -> all options are English.
Never mix domains inside one option set. The stem, keyed answer, correct_index, and explanation must all resolve to the same unique option. The stem itself must contain every fact needed; never infer gender, nationality, ethnicity, profession, language ability, or identity from a name, birthplace, residence, workplace, stereotype, or world knowledge.

3. DIALOGUE IS STRUCTURAL, NOT FREE-FORM
Every dialogue turn has two different semantic slots: SPEAKER and UTTERANCE.
- speaker = only a proper name or short target-language role label; never a sentence, never punctuation-heavy prose.
- speaker_tr / speaker_en = localized role label or the same proper name.
- text = only the utterance in {language}.
- line_tr / line_en = faithful instructional-language rendering of that utterance.
Never swap speaker and text. Never emit an empty utterance paired with a sentence-sized speaker. Maintain coherent turn-taking and register.

4. WRITING-SYSTEM OBJECTS ARE DATA
When teaching an alphabet, kana, character, diacritic, tone mark, vowel mark, length mark, combining mark, punctuation sign, or other orthographic symbol, emit the literal Unicode symbol itself in the relevant target field. Do not describe a visible mark and then leave empty parentheses or empty quotes. Preserve legitimate combining marks, stress marks, dakuten/handakuten, chōonpu, Arabic marks, Indic marks, ZWJ/ZWNJ, and naturally mixed scripts. Valid NFC Unicode only; no replacement characters, noncharacters, lone surrogates, or cross-script homoglyph corruption inside a token.

5. PRONUNCIATION HAS ONE SOURCE OF TRUTH
Use standard IPA only for learner-facing pronunciation. Each IPA value must describe the exact sibling target item. If the same item recurs, keep its pronunciation compatible with the same phonological analysis and context. Explicit transliteration/romanization may coexist only when clearly a separate pedagogical field/function, never as a second pronunciation system. Preserve real stress, tone, vowel length, palatalization, reduction, assimilation, and other conditioning; do not turn tendencies into exceptionless claims.

6. TYPOLOGICAL AND FACTUAL TRUTH
Every target-language utterance must be native-natural and grammatically correct for that language's own typology. Never force English/Indo-European categories onto unrelated languages. Every stated inventory count, list membership, paradigm, exception, and rule scope must agree internally. Absolute words such as always/never/only/every are allowed only when genuinely true within the stated scope.

7. CEFR AND TEACH-BEFORE-TEST
Keep content strictly at CEFR {level} and test only material already taught or clearly introduced as a fixed chunk.
- A1: high-frequency survival language, short transparent examples, basic forms, minimal metalanguage.
- A2: routine daily interaction, broader everyday functions, controlled grammatical expansion.
- B1: connected everyday discourse, productive grammar, varied tense/aspect, personal viewpoints.
- B2: nuanced argumentation, broader collocation, idiomatic usage, contrast and stance.
- C1: advanced academic/professional register, complex discourse, pragmatic nuance, lexical precision.
- C2: near-native control, subtle sociolinguistic/stylistic distinctions, rare but authentic constructions.

8. FINAL SCHEMA VALIDATION BEFORE RETURN
Silently validate the completed JSON by FIELD ROLE, not by surface heuristics:
- no Turkish/English instructional prose inside target utterance fields;
- no English instructional prose inside Turkish-facing fields;
- no sentence-sized speaker values or empty dialogue utterances;
- no missing literal writing-system symbol when the prose claims to teach one;
- no IPA attached to the wrong lexical item and no conflicting second pronunciation representation;
- every MCQ has four distinct same-domain options, one defensible answer, and no hidden-world inference;
- every count/list/rule is internally consistent.
Repair the JSON in the same pass, then return valid JSON only.
</aulaai_unified_quality_contract>
"""

start_marker = "<lesson_quality_v24>"
end_marker = "<output_schema>"

if start_marker not in s or end_marker not in s:
    raise RuntimeError("v49 bloat markers missing in services/ai_engine.py")

start_idx = s.find(start_marker)
end_idx = s.find(end_marker)
if start_idx >= end_idx:
    raise RuntimeError("v49 slice indices invalid")

s = s[:start_idx] + UNIFIED_QUALITY_CONTRACT + s[end_idx:]

if "AULAAI_INLINE_PUBLICATION_QA_V46" not in s:
    raise RuntimeError("v49 safety check failed: publication QA marker missing")
if "AULAAI_SCHEMA_FIRST_V54" not in s:
    raise RuntimeError("v49 safety check failed: schema-first marker missing")
if "<output_schema>" not in s:
    raise RuntimeError("v49 safety check failed: output schema missing")

p.write_text(s, encoding='utf-8')
print("Applied v49 schema-first generation contract: typed field ownership, zero downstream-filter assumptions")
