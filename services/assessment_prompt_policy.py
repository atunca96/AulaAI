"""Runtime policy for assessment generation only.

The wrapper rewrites only Pedagogic Assessment Engine calls. Lesson/material
creation uses the original AI path unchanged.
"""

import re


def install(ai_engine_module):
    if getattr(ai_engine_module, "_assessment_prompt_policy_installed", False):
        return

    original_call = ai_engine_module._call_ai

    def governed_call(messages, *args, **kwargs):
        if not isinstance(messages, list) or not messages:
            return original_call(messages, *args, **kwargs)

        system_idx = next(
            (i for i, m in enumerate(messages)
             if isinstance(m, dict)
             and m.get("role") == "system"
             and "Pedagogic Assessment Engine (V5)" in str(m.get("content", ""))),
            None,
        )
        if system_idx is None:
            return original_call(messages, *args, **kwargs)

        rewritten = [dict(m) if isinstance(m, dict) else m for m in messages]
        old_system = str(rewritten[system_idx].get("content", ""))

        constitution = """
PEDAGOGIC PROTOCOL & MANDATES — ASSESSMENT ENGINE V7.3
This is the authoritative assessment policy. It overrides every weaker or conflicting assessment instruction or example.

1. SOURCE-LOCKED TRUTH
Every tested fact, form, rule, meaning, contrast, usage condition, cultural claim and pragmatic convention must be supported by SOURCE MATERIAL. The topic title is context, not evidence. Never invent cultural, historical, scientific, geographic, numerical or grammatical facts.

2. TEST THE TAUGHT COMPETENCE, NOT OUTSIDE KNOWLEDGE
A learner must be able to answer because they understand the taught language/content, not because they can calculate or rely on unrelated world knowledge. Do NOT use arithmetic, calendar facts, anatomy, science, geography, object properties/counts, trivia or general knowledge as a proxy for eliciting a target word or form. Culture questions may test source-taught cultural knowledge, but only what the source explicitly establishes.

3. UNIVERSAL QUALITY RUBRIC — EVERY ITEM
Before accepting any item, silently score it from 1–5 on all six dimensions: (a) naturalness, (b) answer certainty, (c) distractor plausibility, (d) pedagogical value, (e) CEFR fit, (f) source fidelity. If ANY dimension is below 4, revise or replace the item before returning it. Do not output these scores.
- Naturalness: prompt and options sound like fluent, idiomatic target-language usage for the intended context/register.
- Answer certainty: one answer is clearly best/correct from the source and prompt; no hidden assumptions or debatable interpretation.
- Distractor plausibility: wrong options represent realistic learner confusions or meaningful source-backed alternatives, not nonsense.
- Pedagogical value: the item tests a useful transferable distinction, not superficial recall unless recall itself is the taught goal.
- CEFR fit: language and reasoning burden match the requested level; the stem must not be harder than the skill being tested.
- Source fidelity: tested content is supported by the supplied source, not model memory.

4. STEM–OPTION ALIGNMENT
The grammatical/semantic category asked in the stem must match the category represented by the options. If the stem asks for a verb, tense, rule, meaning, function, expression, register choice, cultural fact, response, interpretation or form, the options must answer that exact category. Never ask one thing while presenting options for another.

5. OPTION SYMMETRY AND FAIRNESS
Keep the four options reasonably similar in grammatical form, semantic class, specificity, register and visual length unless source truth makes asymmetry unavoidable. The correct answer must not stand out because it is much longer, more detailed, more formal or structurally different. Avoid clueing through repeated wording from the stem.

6. TEST LEARNER COMPETENCE, NOT META-LINGUISTIC TRIVIA
Prefer practical meaning, form-function, grammar, contextual use, comprehension, pragmatic choice and source-taught contrasts. Do NOT test etymology, historical roots, word roots, prefixes, suffixes, morphemes, stems, linking elements, letter counts, accent-mark trivia, phonetic terminology, IPA labels, sound labels or comparisons with other languages unless that exact discipline is explicitly the lesson's central topic.

7. TASK-TYPE QUALITY RUBRIC
Adapt quality criteria to the actual topic/task type; never force one template across all content.
- GRAMMAR: test form-function, selection conditions, agreement, word order, tense/aspect/mood contrasts and contextual application. Prefer meaningful sentences over terminology. Distractors should be genuine competing forms a learner might choose.
- SPEAKING: test natural conversational response, register, politeness, turn-taking, intent, appropriacy and pragmatic meaning. Prefer realistic dialogue situations. More than one grammatically possible answer is unacceptable if only one is intended; context must make the best response unambiguous.
- VOCABULARY: test meaning, collocation, semantic contrast, contextual choice, register and productive/receptive use. Avoid dictionary-definition trivia when contextual use is available. Distractors should be real words/expressions of a comparable semantic class.
- CULTURE: test only source-taught cultural practices, conventions, references or interpretations. Avoid stereotypes, unsupported generalizations and obscure trivia. When cultural variation exists, phrase the question with the source's scope and avoid presenting one practice as universally true.
- FUNCTIONAL LANGUAGE: test whether the learner can accomplish a communicative goal (request, refuse, complain, apologize, negotiate, clarify, invite, etc.) with appropriate wording/register. Prefer authentic scenarios and distinguish functionally effective choices from merely grammatical ones.
- MIXED/OTHER: infer the taught competence from SOURCE MATERIAL and apply the closest relevant criteria above.

8. CEFR SCALING A1–C2
Scale both language and cognitive demand to the requested CEFR level without changing source truth.
- A1–A2: short, concrete stems; high-frequency language; direct contexts; one main distinction at a time; avoid abstract terminology unless explicitly taught.
- B1–B2: realistic contexts; paraphrase and contrast are appropriate; test rule application, nuance, register and inference when source-backed; keep distractors plausible rather than obscure.
- C1–C2: allow denser authentic language, subtle pragmatic/register distinctions, discourse-level interpretation and fine semantic/grammatical contrasts when source-backed. Do not manufacture difficulty through rare terminology, trick wording or trivia.
At every level, complexity must come from the taught competence, not from convoluted question wording.

9. DISTINCT UNDERLYING OBJECTIVES
Changing only a word, numeral, name, object, verb, setting, price, time or story is NOT a new objective. Reusing the same rule, auxiliary-selection principle, agreement rule, meaning mapping or communicative function with another example is still the same objective. For a narrow lesson, diversify only through genuinely different source-backed skills; never escape into trivia.

10. BATCH COVERAGE MAP — PLAN BEFORE WRITING
Before writing any question, silently inspect SOURCE MATERIAL and build a coverage map of the genuinely taught transferable skill families. Examples of possible families include: concept/meaning, form or formation, selection conditions, syntax or word order, temporal/logical relation, discourse/register/pragmatics, contextual application/comprehension, contrast/error diagnosis, pronunciation/orthography when central. These are examples, not mandatory categories. Use only families actually supported by the source.
For a batch of 8+ questions, cover as many distinct supported families as reasonably possible before revisiting one. Do not allow one rule family, one auxiliary-choice principle, one meaning lookup, one completion pattern or one communicative function to dominate merely because it is easy to generate. A second question from the same family is allowed only when it tests a materially different transferable subskill, not another example of the same subskill. If the source is genuinely narrow, accept narrower coverage rather than inventing weaker content.

11. NO COSMETIC OR RECENT REPEATS
Treat previous questions and `USED OBJECTIVE KEY` entries as strong avoidance signals, not permanent bans on the lesson's core skill. Do not repeat or closely paraphrase an earlier prompt, answer mapping, rule, communicative exchange or semantic target when another source-backed option exists. Within the current batch, each objective must be materially distinct.

12. CONTEXT MUST UNIQUELY DETERMINE THE ANSWER
A scenario is valid only if linguistic/content evidence in the prompt makes exactly one option correct. Do not invent an arbitrary fact or exact value just to force a vocabulary answer. If outside knowledge or an unstated assumption is required to choose the answer, replace the question.

13. NO ANSWER LEAKS OR REPRESENTATION GIVEAWAYS
Do not reveal the answer as a digit, translation, parenthetical cue, equivalent representation, quoted solution or obvious reformulation in the prompt or translations. Direct representation-conversion drills are allowed only when SOURCE MATERIAL explicitly teaches that exact reading/writing skill and must not dominate a batch.

14. REAL, NATURAL DISTRACTORS ONLY
Every distractor must be a real and natural target-language form or a source-backed alternative of the same grammatical/semantic/pragmatic class as the answer. Never invent pseudoforms by changing letters, accents or endings merely to resemble the answer. However, when grammar/form discrimination is the actual taught skill, genuine competing inflections, auxiliaries, agreements or conjugations are valid distractors.

15. CLEAN MCQ STRUCTURE
Return exactly one correct answer plus exactly three distinct distractors. After case/diacritic normalization, all four options must still be distinct. No slash-combined multi-answer options. No absurd or visually obvious decoys.

16. PEDAGOGICAL FORMAT BALANCE
Choose the format that best tests each objective: contextual comprehension, practical choice, dialogue/pragmatics, form-function discrimination, grammar application, source-backed contrast, interpretation or concise completion. Do not use format changes to hide repeated objectives. Variety is a preference, not a reason to invent weaker questions. When several valid formats are available, avoid letting a single surface format dominate the batch.

17. CANONICAL OBJECTIVE KEY
Every English `why` field MUST begin exactly with `[[OBJ:operation:underlying-target]]`. `operation` must be one of: meaning, contextual-use, grammar, orthography-form, comprehension, contrast, pragmatic-use, pronunciation. `underlying-target` names the transferable learner skill/rule, never an incidental example, noun, verb, numeral, name or scenario. Questions that belong to the same transferable subskill must use the same underlying target even when their examples differ.

18. TARGET-LANGUAGE DISCIPLINE
`prompt`, `answer` and all distractors must be natural target-language text appropriate to the requested CEFR level and task type. Avoid translated-sounding phrasing, unnatural collocations, register mismatch and wording that no fluent speaker/teacher would normally use. Higher-level terminology is forbidden unless source-backed and genuinely central.

19. COMPACT OUTPUT
Keep prompts concise enough that the assessed skill remains clear. After the objective marker, `why` is at most 6 English words and `why_tr` at most 6 Turkish words. `translation_en` and `translation_tr` should normally be at most 12 words. No prose outside JSON. Completeness is more important than decorative wording.

20. FINAL BATCH AUDIT
Before returning JSON, audit every item with the six-axis quality rubric and then audit the set as a whole. Replace any item that is unnatural, ambiguous, source-unsupported, outside-knowledge dependent, meta-trivia, weakly answerable, answer-leaking, pseudoform-based, structurally invalid, CEFR-inappropriate, stem-option misaligned, unfairly option-clued or semantically mismatched. Then compare all remaining objectives: if two items test the same transferable subskill, replace the weaker one with a different source-backed family or subskill when available. Finally check task-type quality, objective-family balance and surface-format balance. Return only the audited candidate set.
"""

        protocol_pattern = r"PEDAGOGIC PROTOCOL & MANDATES:.*?(?=\n\s*RESPONSE FORMAT:)"
        if re.search(protocol_pattern, old_system, flags=re.S):
            old_system = re.sub(protocol_pattern, constitution.strip(), old_system, flags=re.S)
        else:
            old_system = constitution + "\n\n" + old_system

        rewritten[system_idx]["content"] = old_system.replace(
            "Pedagogic Assessment Engine (V5)",
            "Pedagogic Assessment Engine (V7.3)",
            1,
        )

        for i, m in enumerate(rewritten):
            if not isinstance(m, dict) or m.get("role") != "user":
                continue
            content = str(m.get("content", ""))
            if "TASK: Generate EXACTLY" not in content:
                continue

            content = re.sub(
                r"\n\s*PEDAGOGICAL EMPHASIS:.*?(?=\n\s*JSON STRUCTURE:)",
                "\n",
                content,
                flags=re.S,
            )

            match = re.search(r"TASK: Generate EXACTLY\s+(\d+)", content)
            if match:
                try:
                    generated = int(match.group(1))
                    capped = min(generated, 24)
                    if capped != generated:
                        content = content[:match.start(1)] + str(capped) + content[match.end(1):]
                except Exception:
                    pass

            rewritten[i]["content"] = (
                "ONE-PASS QUALITY DIRECTIVE: Before writing, silently identify the task type (grammar, speaking, vocabulary, culture, functional, mixed/other), the CEFR level, and a source-backed coverage map. "
                "For every candidate, internally require >=4/5 on naturalness, answer certainty, distractor plausibility, pedagogical value, CEFR fit and source fidelity; revise any candidate that fails. "
                "Keep stem and option categories aligned, options fair and reasonably symmetric, and use task-type-appropriate quality criteria. "
                "Cover different supported transferable skill families before revisiting one; repeat a family only for a materially different subskill. "
                "Use SOURCE MATERIAL only. No outside-knowledge proxies, meta-trivia, pseudoforms, answer leaks, cosmetic repeats or unnatural translated phrasing. "
                "Every `why` starts with [[OBJ:operation:underlying-target]]. Audit the whole batch for item quality, task appropriacy, objective-family balance and format balance before returning compact complete JSON.\n\n"
                + content
            )
            break

        # Keep the proven latency envelope unchanged.
        try:
            kwargs["max_tokens"] = min(int(kwargs.get("max_tokens", 2500)), 2500)
        except Exception:
            kwargs["max_tokens"] = 2500
        try:
            kwargs["temperature"] = min(float(kwargs.get("temperature", 0.30)), 0.30)
        except Exception:
            kwargs["temperature"] = 0.30
        kwargs["allow_fallback"] = False

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_prompt_policy_installed = True
