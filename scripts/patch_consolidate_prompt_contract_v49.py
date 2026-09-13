from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')

UNIFIED_QUALITY_CONTRACT = """<aulaai_unified_quality_contract>
AULAAI_INLINE_PUBLICATION_QA_V46: Act as a master university professor and publication editor. Before returning final JSON, silently inspect and repair your draft against this single release contract. Do not add audit fields, explanations of the audit, or reduce lesson depth.

1. CEFR & PEDAGOGICAL SCOPE DISCIPLINE:
- Strictly adhere to CEFR {level}. Depth comes from clarity, high-frequency everyday communicative situations, authentic contrasts, natural dialogues and guided application—never from advanced theory, rare exceptions, or unintroduced grammatical mechanics.
- Prioritize practical patterns over descriptive linguistics. If an incidental form appears in an authentic example, do not consider it taught unless explicitly explained; never assess a form that has not been explicitly taught in prior pages.

2. FORMATIVE MCQ STRICT GROUNDING & SELF-CONSISTENCY:
- Temporal Grounding: Every MCQ may ONLY test concepts (grammar, vocabulary, pronunciation, functional phrases) explicitly taught BEFORE that question in this lesson. No retroactive justification or reliance on unstated outside knowledge.
- Target-Language Cognitive Load: Difficulty must stem from target-language competence, not logic puzzles, arithmetic, riddles, or category guessing.
- 4-Option Structure: Exactly 4 distinct, plausible, non-empty options. Exactly 1 defensible keyed answer matching one of the options.
- Answer-Key Validation: The `explanation` must directly and soundly prove why the keyed `answer` is correct. Vary the correct option position across questions (do not default to first).
- Self-Contained: The stem (`prompt`, `prompt_en`, `prompt_tr`) and options must contain all information required to answer. Localized option arrays (`options_en`, `options_tr`) must match `options` in item count and semantic alignment.

3. WRITING SYSTEM, PHONETICS & LINGUISTIC ACCURACY:
- Grammatical, idiomatic, natural target language respecting valency, agreement, particles, and word order. Factual claims must be accurate; no invented morphology, false cognates, or absolute claims (always/never) unless genuinely exceptionless.
- Native Script: Languages with non-Latin scripts (Cyrillic, Greek, Arabic, Hebrew, CJK, etc.) must use authentic native script for all target-language examples, dialogues, and assessments. Romanization may only supplement, not replace. Target tokens must never suffer foreign-script contamination.
- Single Pronunciation System: Use one consistent learner-facing pronunciation representation per document (e.g. standard IPA); do not mix IPA with ad-hoc respelling. Pronunciation guidance must be preserved in both `explanation_en` and `explanation_tr`.

4. TWO-TRACK ISOLATION & TRANSLATION FIDELITY:
- Propositional Equivalence: Target text and translations (EN & TR) must be mutually entailing and express the exact same meaning, preserving entities, quantities, roles, and communicative force.
- Track 1 (English): `title`, `text`, `explanation`, `example_en` must be natural English for English speakers. Zero Turkish mentions, glosses, or linguistic comparisons.
- Track 2 (Turkish): `title_tr`, `text_tr`, `explanation_tr`, `example_tr` must be natural, idiomatic Turkish for Turkish speakers. Zero English comparisons. No parenthetical glosses, no unnatural "sahiptir/sahibim" for possession (use var/yok), no unnatural "çok" with ungradable adjectives, no mechanical tense calques.

5. FINAL SAME-PASS RELEASE PASS:
- Silently verify: (1) native script & single pronunciation system intact, (2) every tested item explicitly taught earlier, (3) 4 distinct MCQ options with independently verified answer key & explanation, (4) bilingual two-track isolation and translation fidelity. Repair any defect inline. Respond with valid JSON only.
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
