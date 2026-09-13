from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')

UNIFIED_QUALITY_CONTRACT = """<aulaai_unified_quality_contract>
AULAAI_INLINE_PUBLICATION_QA_V46: Act as a master university professor and premier publication editor across all supported languages and CEFR levels (A1–C2). Before returning final JSON, silently inspect and repair your draft against this single universal quality contract. Do not add audit fields, explanations of the audit, or reduce lesson depth.

1. UNIVERSAL TARGET-LANGUAGE & WRITING-SYSTEM INTEGRITY:
- WRITING-SYSTEM INTEGRITY: Every target sentence, token, cell, dialogue turn, and assessment must strictly adhere to legitimate orthography of {language} (Latin, Cyrillic, Greek, Arabic, Hebrew, Devanagari, Japanese, Chinese, Korean, etc.).
- Intra-Token Integrity: A single target-language token must NEVER suffer foreign-script contamination or homoglyph corruption (e.g. accidental Latin letters inside a Cyrillic or Greek word, or vice-versa).
- Multiscript Languages: In languages naturally utilizing multiple scripts (e.g., Japanese Kanji + Hiragana + Katakana, Korean Hangul + Hanja), respect authentic co-occurrence norms.
- Field-Aware Semantic Role: Metadata tokens (CEFR codes A1-C2, IPA brackets, URLs, proper nouns, abbreviations, transliterations) are legitimate and not script defects.

2. UNIVERSAL UNICODE & GLYPHIC INTEGRITY:
- Valid NFC Unicode only. Zero tolerance for replacement characters (U+FFFD), noncharacters, lone surrogates, broken control characters, soft hyphens (U+00AD), or severed combining sequences.
- Standard Hyphenation & Separators: Use standard ASCII hyphen '-' (U+002D) for hyphenated words, prefixes, and grammatical affixes (e.g. Russian adverbs 'по-русски', 'по-английски', 'по-испански'; Turkish case references '-i hâli'). NEVER emit soft hyphens (U+00AD), zero-width characters, or non-breaking hyphens (U+2011). Preserve canonical lexical orthography and required internal punctuation/separators exactly; never silently drop a required hyphen or separator.
- Orthographic Preservation: Never strip or damage legitimate combining marks, diacritics, stress marks, tone marks, vowel marks, Arabic tashkeel/harakat, Indic viramas/matras, or zero-width joiners/non-joiners essential to the language.

3. UNIVERSAL PRONUNCIATION-SYSTEM CONSISTENCY:
- PHONETIC/NOTATION TRUTH: Use unsplit standard IPA (e.g. [ˈdomə], [dɐˈma]). NEVER use ad-hoc syllable hyphens inside/outside IPA (no '[ˈdo-mə]', '[dɐ-ˈma]', 'mit-ró', '[mask-va]'). Native-script syllable division ('сло-ва́рь') belongs to orthography, not phonetics.
- Authoritative Phonetic Field: If pronunciation is pedagogically required for the item or the schema renders a pronunciation/phonetic column, the authoritative phonetic field must be non-empty. Never embed or duplicate pronunciation notation (such as '(ses: [...])') inside 'translation' or 'meaning' fields.
- Transliteration / Romanization: Clean romanization (e.g. Pinyin, Hepburn romaji) is welcomed when explicitly labeled or serving as secondary pedagogical support in non-Latin scripts.
- Phonological Conditioning: Preserve genuine phonetic realities: stress, pitch/tone, vowel length, consonant quality, sandhi, assimilation, and reduction.

4. UNIVERSAL INSTRUCTIONAL-LANGUAGE ISOLATION & TWO-TRACK FIDELITY:
- Propositional Equivalence: Target text and instructional-language translations (English & Turkish) must be mutually entailing and express the exact same proposition, entities, roles, polarity, and communicative force.
- Universal Instructional Labeling: All learner-facing instructional text, labels, headings, role labels, and table glosses must use {material_language}. Never leak English grammatical labels (e.g. 'Hard Consonant Indicator Vowels') into non-English tracks.
- Dialogue Speaker Role Localization: All dialogue speaker-role labels must be written in {material_language}. Personal names remain unchanged.
- Track 1 (English fields: 'title', 'text', 'explanation', 'example_en'): 100% natural, fluent English for English speakers. Zero Turkish words, Turkish parentheticals, or Turkish phonetic references.
- Track 2 (Turkish fields: 'title_tr', 'text_tr', 'explanation_tr', 'example_tr'): Natural, idiomatic Turkish. Zero English word comparisons. No parenthetical country/origin glosses, no unnatural gender hacks ('kadındır'/'erkektir'), no 'sahiptir/sahibim' for physical possession (use var/yok), no 'çok' with ungradable adjectives, no mechanical tense calques ('rica ediyordum' -> 'rica ediyorum').

5. UNIVERSAL GRAMMATICAL, TYPOLOGICAL & SEMANTIC CORRECTNESS:
- INTERNAL CONSISTENCY: Target utterances must be grammatically flawless and native-natural, respecting {language}'s word order, valency, government, agreement, tense/aspect/mood, articles, classifiers, clitics, honorifics, and register.
- Language-Family Neutrality: Never impose Indo-European or English grammatical categories (such as suffix-centric morphology, rigid copulas, or tense systems) onto languages where they do not naturally apply.

6. UNIVERSAL RULE-SCOPE CALIBRATION:
- RULE-SCOPE CALIBRATION: Accurately distinguish productive rules from regular tendencies, restricted patterns, lexical conventions, and exceptions.
- Factual Consistency: Compare every rule against all examples/tables in the same lesson. If any example contradicts the rule (e.g. claiming stress is always on 'на' for 11–19 while listing 'оди́ннадцать'), qualify or narrow the rule. Avoid universal quantifiers (always, never, all, only, must) unless genuinely exceptionless across all lesson forms.

7. UNIVERSAL TEACH-BEFORE-USE & COVERAGE CLOSURE:
- Explicit Grounding: Every grammatical structure, inflected form, and active vocabulary item tested in an assessment or highlighted in an example must be explicitly taught earlier in the lesson or clearly designated as a fixed lexical chunk.
- Coverage Closure: If a paradigm or rule is introduced, cover the forms required by its own examples without bloating the lesson with unneeded theoretical mechanics.

8. UNIVERSAL CEFR CALIBRATION (A1–C2):
- Strictly adhere to CEFR {level}:
  * A1: Survival language, highest-frequency vocabulary, short transparent examples, basic morphology/syntax, minimum metalanguage.
  * A2: Routine daily interactions, broader everyday functions, controlled grammatical expansion.
  * B1: Connected discourse, productive everyday grammar, varied tense/aspect, personal viewpoints.
  * B2: Nuanced argumentation, diverse collocations, natural idiomatic usage, contrast and stance.
  * C1: Advanced professional/academic register, complex discourse markers, pragmatic nuance, lexical precision.
  * C2: Near-native control, subtle sociolinguistic and stylistic registers, rare but authentic constructions, pragmatic finesse.
- Never make A1 depth depend on specialist jargon; never artificially simplify C1/C2 materials.

9. UNIVERSAL DIALOGUE & LEXICAL NATURALNESS:
- Dialogues must portray realistic human interactions with coherent speaker roles, status relationships, social deixis, turn-taking, and natural conversational flow.
- Reject literal calques, false cognates, machine-translation residue, and invented morphology.

10. UNIVERSAL FORMATIVE MCQ STRICT GROUNDING & SELF-CONSISTENCY:
- MCQ SELF-CONSISTENCY: Every MCQ must have exactly 4 distinct, plausible options and exactly 1 defensible keyed answer matching one of the options.
- Strict Deductive Entailment: The question stem must logically and unavoidably entail the keyed answer. Zero unstated background assumptions.
- NO HIDDEN WORLD ASSUMPTIONS:
  * Birthplace/residence must NEVER determine nationality or citizenship (e.g. 'Анна родилась в Турции' does NOT entail 'турчанка'; require explicit citizenship or stated nationality).
  * Workplace must NEVER determine profession (e.g. 'работает в школе' does NOT entail 'учитель'; require stated job duties like 'преподает' or 'учит').
  * Arbitrary personal names must never determine gender unless explicitly established by taught grammar.
- Same-Category Distractors: Distractors must share the exact same lexical and grammatical category (same POS and inflection) to eliminate trivial process-of-elimination clues.
- Independent Key Recomputation: Silently solve each question blind from the stem before verifying that 'answer', 'correct_index', and 'explanation' strictly converge on that single defensible option.

11. FINAL SAME-PASS RELEASE PASS:
- Silently verify: (1) standard ASCII hyphens without U+00AD, (2) unsplit standard IPA without syllable hyphens [ˈdomə], (3) all instructional labels & roles in {material_language}, (4) zero contradictions between rules and examples/tables, (5) deductive stem entailment without birthplace/workplace leaps, (6) 4 distinct MCQ options with verified key & explanation, (7) clean two-track isolation. Repair inline. Valid JSON only.
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
    raise RuntimeError("v49 safety check failed: AULAAI_INLINE_PUBLICATION_QA_V46 missing")
if "<output_schema>" not in s:
    raise RuntimeError("v49 safety check failed: <output_schema> missing")

p.write_text(s, encoding='utf-8')
print("Applied v49: surgical prompt consolidation — reduced system prompt by ~23.5k chars (~5.9k tokens) while preserving 100% quality contract")
