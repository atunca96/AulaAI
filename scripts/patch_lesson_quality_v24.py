from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'services' / 'ai_engine.py'
s = p.read_text(encoding='utf-8')

rules = '''
<lesson_quality_v24>
- Keep every lesson strictly appropriate to CEFR {level}; depth comes from clarity, useful examples, contrasts and practice, not unnecessary advanced content.
- Teach the exact objective completely but avoid redundant explanations, tangential rules, speculative details and repetition.
- Examples and dialogues must be natural, idiomatic and demonstrate the exact point being taught. Preserve valency, collocations, case/preposition choice, word order and register.
- Preserve names, people, roles, places, numbers, dates, times and meanings consistently across target-language, English and Turkish fields.
- Never invent grammar rules, exceptions, word forms, idioms, pronunciation claims or cultural facts. If uncertain, simplify or omit.
- Before output, check correctness, naturalness, CEFR fit, progression, duplication, translation fidelity and internal consistency; rewrite anything ambiguous, awkward or unsupported.
</lesson_quality_v24>

<formative_mcq_quality_v24>
- Every material-internal MCQ must test something explicitly taught or directly demonstrated in this lesson.
- The question must be answerable from the lesson without outside facts, generic common sense or unrelated logical deduction.
- Prefer language competence, contextual comprehension and grammatical discrimination; do not turn beginner material into family-tree puzzles, riddles or trick reasoning tasks.
- Taught knowledge may be transferred to a fresh natural example, but no new rule, exception, lexical meaning, collocation or register distinction may be required.
- Exactly one option must be correct. Distractors must be plausible learner errors tied to the same learning objective, never nonsense or random fillers.
- Keep stems and options inside CEFR {level}. If a clean four-option item cannot be written, omit the MCQ rather than fabricate one.
- Check each MCQ using only this lesson before returning it.
</formative_mcq_quality_v24>
'''

if '<lesson_quality_v24>' not in s:
    anchor = '<output_schema>\n'
    if anchor in s:
        s = s.replace(anchor, rules + '\n' + anchor, 1)
    else:
        print('v24: output_schema anchor unavailable; leaving source unchanged')

old = 'Generate as many pages as this topic requires to be covered at the highest textbook quality.'
new = 'Use only as many pages as necessary to teach this exact topic completely at CEFR {level}; quality and classroom usefulness outrank length.'
if old in s:
    s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('Applied deploy-safe lesson quality v24')
