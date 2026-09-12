from pathlib import Path

root = Path(__file__).resolve().parents[1]
ai_path = root / "services" / "ai_engine.py"
ai = ai_path.read_text(encoding="utf-8")

# v23 intentionally targets ONLY the lesson/material generation prompt.
# The standalone quiz generator already has its own stricter assessment pipeline
# and is left untouched.

# 1) Stop equating quality with encyclopedic length. Keep academic rigor, but
# make CEFR containment and published-coursebook usefulness the priority.
old_authority = '''- Maintain high academic rigor, first-principles explanations, and exhaustive educational depth.
- Never write shallow, brief summaries or placeholder content. Treat every topic with the depth of a university textbook chapter.'''
new_authority = '''- Maintain high academic rigor while staying strictly inside CEFR Level {level}; depth means clarity, precision, useful examples, and secure mastery of the stated objective, NOT extra advanced content.
- Write a complete published-coursebook lesson rather than an encyclopedic or university-level chapter. Prefer the minimum sufficient explanation that fully teaches the objective, and never inflate length for its own sake.'''
count_authority = ai.count(old_authority)
if count_authority != 1:
    raise RuntimeError(f"v23 authority anchor expected 1, found {count_authority}")
ai = ai.replace(old_authority, new_authority, 1)

# 2) Add a universal lesson-level editorial quality contract. This attacks the
# concrete defects seen in generated PDFs: over-density, repeated rules, name/
# fact drift across translations, unnecessarily advanced material, and examples
# that are technically related but not fully defensible.
quality_block = r'''
<lesson_quality_control>
LESSON QUALITY CONTROL — ACCURACY, CEFR CONTAINMENT & EDITORIAL CONSISTENCY (HARD REQUIREMENTS):
1. QUALITY OVER LENGTH:
   - Completeness means fully teaching the stated objective at CEFR {level}; it does NOT mean adding every adjacent rule, exception, synonym, cultural note, or later-level structure that happens to be related.
   - Use only as much explanation and as many pages as the learner needs. Never expand a lesson merely to appear comprehensive.
2. STRICT CEFR CONTAINMENT:
   - Every grammar point, lexical item, exception, dialogue move, explanation, and assessment item must be appropriate and genuinely useful at CEFR {level} for this exact topic.
   - Do not preview later-level grammar or terminology unless it is indispensable to understand the requested {level} objective; when it is not indispensable, omit it.
   - Especially at A1/A2, prefer high-frequency concrete language, short transparent explanations, and immediately usable patterns over theoretical completeness.
3. PEDAGOGICAL PROGRESSION & ANTI-REPETITION:
   - Introduce each concept once in the clearest place, then reinforce it through examples or practice.
   - Revisit an earlier concept only when the new section adds a genuinely new layer, contrast, communicative function, or difficulty. Do not restate the same rule in different words to create volume.
   - Build from recognition -> controlled understanding -> natural application. Do not jump to exceptions before the core pattern is secure.
4. EXAMPLE INTEGRITY:
   - Every example must demonstrate the exact point being taught and sound like something a native speaker could naturally say or write in the stated situation.
   - Never distort lexical valency, collocation, case/preposition choice, word order, register, or pragmatic meaning just to showcase a rule.
   - A simple, fully defensible example is always preferable to a sophisticated but uncertain one.
5. CROSS-FIELD FACT & ENTITY CONSISTENCY:
   - Preserve names, titles, speaker identities, gender where linguistically relevant, places, relationships, numbers, dates, times, quantities, and factual details exactly across the target-language sentence, English field, and Turkish field.
   - Never introduce name drift, role drift, number drift, pronoun mismatch, or speaker swaps during translation or explanation.
6. TRANSLATION FIDELITY WITHOUT CALQUE:
   - Translate communicative meaning naturally, but do not add, delete, reverse, or alter factual content.
   - A translation may localize syntax or a speech-act formula for naturalness, but it must preserve who did what, to whom, where, when, and with what meaning.
7. STRICT TRUTH & UNCERTAINTY POLICY:
   - Never invent a grammatical rule, exception, word form, idiom, collocation, pronunciation claim, cultural fact, or usage distinction.
   - If a detail is uncertain, simplify, omit it, or use a safer high-confidence example instead of approximating.
8. SILENT EDITORIAL PASS BEFORE OUTPUT:
   - Before returning JSON, silently review every page for target-language correctness, native naturalness, CEFR fit, pedagogical progression, duplicate content, contradictions, translation fidelity, entity consistency, and internal agreement between rules and examples.
   - Rewrite or remove any sentence that is awkward, ambiguous, repetitive, unsupported, unnecessarily advanced, or not fully defensible.
</lesson_quality_control>
'''
natural_anchor = '<natural_authenticity_mandate>\n'
count_natural = ai.count(natural_anchor)
if count_natural != 1:
    raise RuntimeError(f"v23 natural-auth anchor expected 1, found {count_natural}")
ai = ai.replace(natural_anchor, quality_block + '\n' + natural_anchor, 1)

# 3) Material-internal quick checks need their own compact contract. Unlike the
# standalone quiz engine, these MCQs are generated inside the lesson call itself.
# Ground them in what the lesson actually taught, allow realistic learner errors,
# and explicitly ban puzzle-style difficulty and world-knowledge questions.
assessment_block = r'''
<formative_assessment_quality_mandate>
MATERIAL-INTERNAL FORMATIVE ASSESSMENT QUALITY (HARD REQUIREMENTS FOR pages[type="mcq"]):
1. LESSON-DEPENDENT ONLY:
   - Every quick-check question must test a learning objective, rule, vocabulary item, contrast, meaning distinction, pronunciation point, or communicative function that this generated lesson itself explicitly teaches or directly demonstrates.
   - The question must be answerable from the lesson. Never require outside facts, generic world knowledge, unstated assumptions, cultural trivia, or unrelated logical deduction.
2. LANGUAGE LEARNING, NOT PUZZLES:
   - Prefer direct language competence, contextual comprehension, grammatical discrimination, and natural communicative use.
   - Never turn simple material into family-tree puzzles, riddle-like chains, trick questions, arbitrary category games, or reasoning tasks whose difficulty comes from decoding the scenario rather than knowing {language}.
3. SAFE TRANSFER OF TAUGHT KNOWLEDGE:
   - You MAY place a taught rule or vocabulary item into a fresh, natural CEFR-appropriate example so the learner applies rather than merely copies the lesson.
   - You MUST NOT introduce a new grammatical rule, exception, lexical meaning, collocation, register distinction, or required vocabulary that was not taught in the lesson.
4. EXACTLY ONE DEFENSIBLE ANSWER:
   - Verify the full stem and all four options so exactly one option is correct according to the lesson and standard {language}.
   - The keyed answer must itself be natural, idiomatic, grammatically correct, and fully compatible with the taught rule or example.
5. PEDAGOGICAL DISTRACTORS:
   - Distractors should represent plausible learner confusions tied to the SAME taught objective: wrong article/case, wrong agreement, wrong conjugation, wrong word order, a nearby taught meaning, or a contextually inappropriate taught expression.
   - For grammar discrimination, an ungrammatical distractor is allowed when it is a realistic learner error produced by misapplying the exact rule being tested. Never fabricate nonsense, nonexistent morphology, random off-topic words, or joke answers.
   - Do not make the correct answer obvious through option length, category mismatch, register mismatch, or three absurd fillers.
6. CEFR CALIBRATION:
   - The linguistic difficulty of the stem, context, and options must not exceed CEFR {level}. Do not hide an A1 rule inside B1/B2 vocabulary or syntax.
7. OMIT RATHER THAN FABRICATE:
   - An MCQ page is optional. If the lesson does not support a clean four-option question with one unambiguous answer, omit that MCQ page rather than inventing content or weakening quality.
8. SILENT SOLVE-CHECK:
   - Before output, solve every generated MCQ using only the lesson you just created. Confirm the answer is taught, exactly one option works, each distractor fails for a clear lesson-related reason, and no wording depends on information outside the lesson. Rewrite or remove any question that fails.
</formative_assessment_quality_mandate>
'''
output_anchor = '<output_schema>\n'
count_output = ai.count(output_anchor)
if count_output != 1:
    raise RuntimeError(f"v23 output-schema anchor expected 1, found {count_output}")
ai = ai.replace(output_anchor, assessment_block + '\n' + output_anchor, 1)

# 4) Make the final internal planning pass explicitly check the real failure
# modes before JSON is emitted.
old_reasoning_tail = '''   - If the original source does not provide sufficient evidence for a defensible structural rule, omit it rather than synthesizing one.
Then generate the complete, exhaustive JSON lesson structure.'''
new_reasoning_tail = '''   - If the original source does not provide sufficient evidence for a defensible structural rule, omit it rather than synthesizing one.
7. Final editorial verification before output:
   - Check every target-language form, rule, example, dialogue line, and translation for correctness and native naturalness.
   - Check names, roles, pronouns, places, numbers, dates, times, and meanings for exact agreement across target-language, English, and Turkish fields.
   - Remove unnecessary repetition and anything that exceeds CEFR {level} without being essential to this topic.
   - Solve every formative MCQ using only this lesson. If the answer is not uniquely supported, or the question tests reasoning/world knowledge instead of the taught language, rewrite it or omit the MCQ page.
Then generate the complete, carefully edited JSON lesson structure.'''
count_reasoning = ai.count(old_reasoning_tail)
if count_reasoning != 1:
    raise RuntimeError(f"v23 reasoning-tail anchor expected 1, found {count_reasoning}")
ai = ai.replace(old_reasoning_tail, new_reasoning_tail, 1)

# 5) Replace the old length-maximizing final directive with a quality-maximizing
# one. This keeps complete coverage but prevents the model from treating page
# count and advanced detail as quality signals.
old_final = '''CRITICAL: Do NOT summarize. Do NOT write brief pages. Generate the FULL, DEEP, AUTHENTIC educational content.
Generate as many pages as this topic requires to be covered at the highest textbook quality.
Respond with ONLY the JSON object. No markdown, no prose outside the JSON.'''
new_final = '''CRITICAL: Produce complete teaching coverage without inflating the lesson. Quality, CEFR fit, internal consistency, factual/translation fidelity, and classroom teachability outrank length.
Use only as many pages as necessary to teach this exact topic completely at CEFR {level}; omit redundant, tangential, speculative, or unnecessarily advanced material.
Every material-internal MCQ must pass the formative assessment quality mandate above; if a clean question cannot be produced, omit that MCQ page.
Respond with ONLY the JSON object. No markdown, no prose outside the JSON.'''
count_final = ai.count(old_final)
if count_final != 1:
    raise RuntimeError(f"v23 final-directive anchor expected 1, found {count_final}")
ai = ai.replace(old_final, new_final, 1)

# Build-time guardrails: verify the new material prompt contract exists and the
# old length-maximizing instruction is gone. Do not touch standalone quiz prompt.
required = [
    '<lesson_quality_control>',
    '<formative_assessment_quality_mandate>',
    'Quality, CEFR fit, internal consistency, factual/translation fidelity, and classroom teachability outrank length.',
    'solve every generated MCQ using only this lesson'.lower(),
]
low = ai.lower()
if required[0] not in ai or required[1] not in ai or required[2] not in ai or required[3] not in low:
    raise RuntimeError('v23 guard: lesson quality directives missing after patch')
if 'Treat every topic with the depth of a university textbook chapter.' in ai:
    raise RuntimeError('v23 guard: old length-maximizing authority directive still present')
if 'Generate as many pages as this topic requires to be covered at the highest textbook quality.' in ai:
    raise RuntimeError('v23 guard: old page-maximizing final directive still present')
if 'def ai_generate_questions(' not in ai:
    raise RuntimeError('v23 guard: standalone quiz generator unexpectedly missing')

ai_path.write_text(ai, encoding="utf-8")
print("Applied v23: CEFR-contained lesson quality + grounded material-internal formative assessments")
