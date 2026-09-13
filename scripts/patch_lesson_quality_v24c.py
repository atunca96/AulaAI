from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "ai_engine.py"
s = p.read_text(encoding="utf-8")

lesson_addition = r'''

7. EXAMPLE-SENTENCE PROOF OBLIGATION
- Every vocabulary-table example is teaching content, not decoration. Before accepting a row, silently parse the complete target-language example and verify morphology, syntax, particles/case/prepositions, agreement, word order, valency, collocation, counters/classifiers and register as a native editor would.
- Never map an English/Turkish surface pattern directly into the target language. In languages with counters/classifiers, articles, case, noun classes, agreement or obligatory particles, use the target language's actual native construction. A bare numeral + noun is forbidden when that language requires a counter/classifier or another construction.
- A correct vocabulary word inside an incorrect sentence is still a fatal error. Replace the whole example with a simpler high-confidence sentence rather than preserving a doubtful frame.
- Examples must not secretly depend on a grammar structure that has not been taught yet unless that structure is completely transparent and nonessential to the learning point. Prefer already-taught carrier syntax.

8. PUBLICATION CLEANLINESS & ZERO CONTAMINATION
- Output must contain only intentional educational content. Never emit editor notes, hidden labels, debug words, placeholder fragments, model scratch text, unrelated foreign-language tokens, malformed Unicode/noncharacters or accidental copy-paste debris inside any field.
- Re-read every bilingual row as a five-column unit: term -> pronunciation -> meaning -> target-language example -> localized translation. All five cells must describe the same lexical item and the example/translation must be mutually entailing.

9. HIGH-FREQUENCY FIRST, THEORY SECOND
- At A1/A2, choose the most frequent, immediately usable native construction. Do not spend scarce beginner attention on specialist terminology, exhaustive exceptions or descriptive-linguistics theory when a practical pattern is sufficient.
- A topic may be intellectually interesting but still inappropriate for the requested CEFR level. Omit it when it does not improve the learner's ability to understand or communicate at that level.
'''

if "7. EXAMPLE-SENTENCE PROOF OBLIGATION" not in s and "</lesson_quality_v24>" in s:
    s = s.replace("</lesson_quality_v24>", lesson_addition + "\n</lesson_quality_v24>", 1)

mcq_addition = r'''

10. OBJECTIVE-BALANCED ASSESSMENT
- Maintain an internal objective ledger for this lesson. Each material-internal MCQ must claim one explicit objective from that ledger.
- Do not use two MCQs to test the same transformation, inflection, lexical distinction or rule through essentially the same cognitive operation. If objective coverage is limited, generate fewer MCQs rather than repeat one objective.
- Across the lesson, prioritize complementary evidence of learning: recognition, contextual application, communicative choice, grammatical discrimination and comprehension, while staying strictly within explicitly taught content.
- A distractor must be useful evidence about a plausible misconception. Random semantic-category outsiders, obvious fillers and accidental nonsense lower assessment quality and must be replaced.

11. CARRIER-LANGUAGE MINIMIZATION
- At A1/A2 the wording surrounding the tested feature must be easier than the feature itself. Avoid long source-language explanations, unnecessary subordinate clauses or extra vocabulary that makes a simple language objective cognitively harder.
- When a short direct target-language context can test the objective, prefer it over a metalinguistic puzzle or translation-heavy stem.
'''

if "10. OBJECTIVE-BALANCED ASSESSMENT" not in s and "</formative_mcq_quality_v24>" in s:
    s = s.replace("</formative_mcq_quality_v24>", mcq_addition + "\n</formative_mcq_quality_v24>", 1)

preflight_addition = r'''
- Treat every vocabulary example as if it will be quoted by a language teacher: verify the COMPLETE sentence, not only the highlighted word.
- For numeral/counting examples, verify the target language's native counter/classifier/number syntax rather than mirroring English/Turkish noun phrases.
- Scan every string for accidental editor/model debris or unrelated tokens; delete or rewrite any contaminated field.
- Build an assessment-objective ledger and reject duplicate MCQs that test the same rule with the same cognitive operation.
- If a sentence is merely understandable but not what an educated native teacher would naturally publish, rewrite it to the simplest natural form.
'''

anchor = "- Final quality floor: silently rate Accuracy, Naturalness, CEFR Fit, Pedagogy, Grounding, Localization Fidelity, Entity Consistency and Classroom Usability; revise or omit any failing content until every category is at least 9.5/10.\n"
if "Treat every vocabulary example as if it will be quoted by a language teacher" not in s and anchor in s:
    s = s.replace(anchor, anchor + preflight_addition, 1)

p.write_text(s, encoding="utf-8")
print("Applied v24c: native example proofing, contamination ban and objective-balanced MCQs")