from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')

rules = '''
<lesson_quality_v24>
LESSON QUALITY GATE — HARD REQUIREMENTS:

1. CEFR AND SCOPE DISCIPLINE
- Keep every lesson strictly appropriate to CEFR {level}. Depth must come from clarity, useful examples, contrasts, dialogues and practice, not from unnecessary advanced content.
- Teach the exact objective completely, but do not add adjacent grammar, exceptions, terminology or cultural detail merely because it is related.
- A form may appear incidentally in a natural example when unavoidable, but an incidental form is NOT considered taught unless its rule or meaning is explicitly explained.
- Prefer a simple, fully defensible A1/A2 example over a sophisticated example that requires hidden grammar or vocabulary.

2. PEDAGOGICAL SEQUENCING AND PREREQUISITES
- Build each lesson from explicit teaching to guided examples to application. Never assess a rule before it has been explicitly taught.
- Maintain an internal teaching ledger while generating: (a) explicitly taught grammar/rules, (b) explicitly taught active vocabulary, (c) explicitly taught functional expressions/pronunciation points. Only these become eligible assessment targets.
- Content from a later page, later lesson or later unit can never retroactively justify an earlier question.
- Do not repeat the same explanation merely to create volume. Revisit earlier material only when adding a genuinely new contrast, function or level-appropriate application.
- Unit/module titles must accurately describe the material placed under them. Preserve a coherent progression and do not create numbering/title drift or place unrelated modules under a misleading unit heading.

3. NATIVE-LANGUAGE ACCURACY AND NATURALNESS
- Every target-language sentence, rule, example and dialogue line must be grammatically correct, idiomatic, contemporary and natural to a native speaker.
- Preserve lexical valency, collocations, article/case/preposition choice, agreement, word order, register and fixed-expression integrity.
- Never manufacture a rule, exception, inflection, idiom, collocation, pronunciation claim or cultural fact. If uncertain, simplify, replace with a high-confidence example or omit.

4. SOURCE-TRANSLATION SEMANTIC FIDELITY
- Target-language text and every supplied translation must express the SAME proposition. Preserve who did what, to whom, where, when, how much and with what meaning.
- Never enrich, narrow, reinterpret or technically relabel the source during translation. If the translation needs a concept that is not lexically/semantically present in the source, rewrite the source or the translation so they match exactly.
- Example: a sentence meaning 'the boundary/limit is at fifty kilometres' must not be translated as 'the speed limit is fifty kilometres' unless the target-language sentence explicitly states speed limit.
- Natural translation is allowed; semantic drift is not.
- Preserve names, speaker identities, gender where relevant, roles, relationships, places, numbers, dates, times, quantities and polarity consistently across target-language, English and Turkish fields.

5. SELF-CONTAINED EDITORIAL QUALITY
- A learner should be able to understand each explanation and solve each exercise using only knowledge explicitly taught up to that point plus ordinary CEFR-{level} carrier language.
- Do not depend on unexplained technical terminology, unstated cultural knowledge, outside facts or implicit reasoning chains.
- Before output, silently check correctness, native naturalness, CEFR fit, progression, duplicate content, translation fidelity, entity consistency, heading coherence and agreement between every rule and its examples.
- Rewrite or remove anything ambiguous, awkward, unsupported, misleading, internally inconsistent or unnecessarily advanced.
</lesson_quality_v24>

<formative_mcq_quality_v24>
IN-MATERIAL MCQ STRICT GROUNDING — HARD REQUIREMENTS:

1. EXPLICITLY TAUGHT IS NOT THE SAME AS MERELY SEEN
- A grammar form, lexical meaning, pronunciation rule, orthographic rule, pragmatic distinction or functional expression may be TESTED only if it was explicitly taught BEFORE that MCQ.
- Explicitly taught means one of the following: (a) stated in a rule/explanation/contrast, (b) listed with its meaning in the active/core vocabulary teaching content, or (c) explicitly foregrounded as a functional/pronunciation target.
- A form that appears only inside an example, dialogue, translation, incidental sentence or answer explanation is NOT automatically testable.
- Never reverse-engineer a grammar rule from an incidental example. Example: if a page explains only Nominativ possessives, an incidental Akkusativ form such as 'ihren Vater' does NOT authorize a question testing 'ihren'.

2. TEMPORAL GROUNDING
- Treat the lesson as a real classroom sequence. A student must be able to answer using only material that appears BEFORE the question.
- Do not use knowledge introduced later in the same lesson, later in the unit, elsewhere in the course or only in the answer key.

3. ANSWER-DETERMINATIVE LANGUAGE MUST BE TAUGHT
- Every word, form or distinction whose meaning is NECESSARY to infer the correct answer must already be explicitly taught or be truly basic carrier language well below the requested CEFR level.
- Do not use an untaught lexical item in the premise when understanding that item is required to deduce the answer. If 'Ehefrau' was not taught, do not make recognition of 'Ehefrau' the evidence for 'verheiratet'.
- Incidental carrier words may be new only when they are transparent, nonessential and cannot change which option is correct.

4. TARGET-LANGUAGE COMPETENCE MUST CARRY THE COGNITIVE LOAD
- The difficulty must come from understanding or using {language}, not from solving an external logic problem in Turkish/English or from generic world knowledge.
- The UI/instruction language may say things such as 'choose the correct answer', but the evidence that determines the answer should normally be target-language material or an explicitly taught language rule.
- Ban family-tree deduction, riddles, arithmetic, arbitrary category puzzles and reasoning chains whose main challenge would be identical even if {language} were removed.
- For kinship vocabulary, test recognition/use of the target-language kinship item in a linguistically accessible context; do not make the student solve a relationship puzzle in the source language.

5. SAFE TRANSFER, NO HIDDEN NEW KNOWLEDGE
- Taught knowledge may be transferred into a fresh, natural, CEFR-appropriate sentence so the student applies rather than copies the lesson.
- A fresh context must not require a new grammar rule, new inflectional paradigm, new lexical meaning, new collocation, new register distinction or new cultural assumption.
- If generating the fresh example requires knowledge outside the teaching ledger, use a simpler context or choose another taught objective.

6. ONE UNIQUE, DEFENSIBLE ANSWER
- Exactly one option must be correct according to both standard {language} and the material taught before the question.
- The correct answer must not depend on a fact that the lesson did not teach.
- The answer-key explanation must cite/restate the taught rule or taught lexical meaning; it must never introduce new knowledge in order to justify the answer after the fact.

7. PEDAGOGICAL DISTRACTORS
- Distractors must arise from the SAME taught objective and represent plausible learner confusions: article/case choice, agreement, conjugation, word order, a nearby taught meaning or a contextually inappropriate taught expression.
- When grammar discrimination itself is the target, a distractor may be grammatically incorrect only if it is a direct, predictable learner error from the explicitly taught paradigm. Do not invent random malformed words or nonsense forms merely to fill options.
- For vocabulary/comprehension questions, prefer real taught alternatives from the same semantic/functional category.
- Do not make the correct option obvious through length, category, register or three absurd fillers.

8. CEFR AND LANGUAGE LOAD
- Keep the stem, scenario and all options at CEFR {level}. Never hide an A1 learning objective inside B1/B2 syntax or vocabulary.
- At beginner levels, keep carrier syntax shorter and simpler than the knowledge being tested.

9. SILENT NOVICE-SIMULATION CHECK
Before returning each MCQ, silently simulate a student who knows ONLY the teaching ledger up to that exact page:
- Can that student understand every answer-determinative word/form in the stem?
- Was the tested rule/meaning explicitly taught rather than merely encountered?
- Does solving the question primarily require {language} competence?
- Is exactly one answer supported?
- Can every distractor be rejected for a clear reason tied to taught content?
If any answer is NO, rewrite the item. If it still cannot pass, OMIT the MCQ rather than fabricate or weaken it.
</formative_mcq_quality_v24>

<final_material_preflight_v24>
FINAL SILENT PRE-FLIGHT BEFORE JSON OUTPUT:
- Re-solve every material-internal MCQ using only content taught before that question.
- Remove any MCQ that tests incidental/example-only grammar, untaught answer-determinative vocabulary, outside logic or future content.
- Compare every target-language example against its English/Turkish translation for exact semantic equivalence and entity/number consistency.
- Check that unit/module headings accurately cover their content and that numbering/progression is coherent.
- Remove repeated explanations that add no new learning value.
- Prefer omission or simplification over any uncertain linguistic claim.
</final_material_preflight_v24>
'''

if '<lesson_quality_v24>' not in s:
    anchor = '<output_schema>\n'
    if anchor in s:
        s = s.replace(anchor, rules + '\n' + anchor, 1)
    else:
        print('v24: output_schema anchor unavailable; leaving source unchanged')

old = 'Generate as many pages as this topic requires to be covered at the highest textbook quality.'
new = 'Use only as many pages as necessary to teach this exact topic completely at CEFR {level}; quality, explicit teachability, semantic fidelity and classroom usefulness outrank length.'
if old in s:
    s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('Applied v24: strict lesson grounding, semantic fidelity and novice-solvable formative assessment')
