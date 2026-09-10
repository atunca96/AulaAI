"""Runtime policy for assessment generation.

Keeps the large legacy ai_engine stable while injecting a universal V6.2 policy
for every supported language, CEFR level, topic, and assessment call.
"""


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

        v62_policy = """
ASSESSMENT ENGINE V6.2 — UNIVERSAL COVERAGE POLICY

These rules apply to EVERY supported language, CEFR level, topic, and source type. They override weaker or conflicting diversity wording below.

1. BUILD A TOPIC-SPECIFIC COVERAGE MAP FIRST
Before writing questions, silently identify the distinct teachable targets actually present in the topic/source: vocabulary meanings and contrasts, grammar rules/forms, communicative functions, pragmatic choices, pronunciation distinctions, orthographic rules when explicitly taught, discourse patterns, comprehension targets, and other language skills appropriate to the CEFR level. Build the batch from different targets in that map.

2. ONE LEARNING OBJECTIVE PER QUESTION
Every question must test a different underlying language-learning objective. Changing names, numbers, nouns, sentence order, direction, examples, locations, stories, or surface wording does NOT create a new objective. If two questions could share the same one-line learning objective, keep only one.

3. PRIOR QUESTIONS EXHAUST THEIR OBJECTIVES
Treat all previous prompts and answers supplied in the request as already-used learning objectives. Do not paraphrase, reverse, re-skin, rename, renumber, or otherwise recreate the same target in a new scenario.

4. TARGET-LANGUAGE KNOWLEDGE MUST BE NECESSARY
A learner should need knowledge of the target language and the lesson content to answer correctly. Reject questions whose answer can be derived mainly from arithmetic, general/world knowledge, geography, trivia, visual pattern recognition, common-sense logic, counting, or information explicitly revealed by the prompt itself.

5. STAY INSIDE THE PEDAGOGICAL SCOPE
Do not invent unrelated knowledge just to create variety. Expand only to natural, CEFR-appropriate uses of the same lesson theme. For narrow topics, vary the linguistic skill being tested rather than importing outside facts.

6. NO SHALLOW META-TRIVIA
Do not ask about string length, number of letters, which option merely looks correctly spelled, whether a word is written as one word, accent/tilde presence, character shape, or similar visual/meta properties unless that exact orthographic feature is explicitly the lesson objective. For alphabet/pronunciation lessons, test genuine sound-letter use in authentic language, not trivia about symbols.

7. FORMAT DIVERSITY MUST FOLLOW OBJECTIVE DIVERSITY
Use a natural mix of situational choice, dialogue response, contextual comprehension, form/meaning discrimination, sentence completion, interpretation, and production-oriented recognition as appropriate to the topic. Do not reuse one question archetype more than twice, and do not use format variation to disguise a repeated learning objective.

8. ANSWER AND DISTRACTOR QUALITY
The correct answer and all distractors must belong to the same grammatical/semantic class, be plausible at the learner's level, and avoid visual or length giveaways. Distractors should represent realistic learner confusions related to the exact target, not random wrong answers.

9. TOPIC-TYPE ADAPTATION
Adapt the assessment method to the content instead of forcing every topic into the same templates. Vocabulary should test use/contrast/context; grammar should test form-function distinctions in context; pronunciation should test authentic sound distinctions; communicative topics should test what a speaker would naturally understand or say; reading/comprehension should test meaning from context. Apply the equivalent principle to any other topic type.

10. FINAL PAIRWISE AUDIT
Before returning JSON, compare every pair of questions and silently label each with its one-line learning objective. Replace any pair whose objectives overlap materially. Also replace any item that tests outside knowledge more than language knowledge, leaks its answer, falls outside the source/topic, or would remain answerable by a non-speaker.
"""

        # Remove legacy examples that can anchor generation to one language or exercise style.
        legacy_examples = [
            '* Example: "¿Cuánto es setenta más treinta?"\n',
            '* Example: "¿En cuál de las siguientes palabras la letra \'g\' se pronuncia con un sonido fuerte (/x/) ante vocal?" [gente, gato, goma, gusto]\n',
        ]
        for example in legacy_examples:
            old_system = old_system.replace(example, "")

        rewritten[system_idx]["content"] = v62_policy + old_system.replace(
            "Pedagogic Assessment Engine (V5)",
            "Pedagogic Assessment Engine (V6.2)",
            1,
        )

        for i, m in enumerate(rewritten):
            if isinstance(m, dict) and m.get("role") == "user":
                content = str(m.get("content", ""))
                if "TASK: Generate EXACTLY" in content:
                    rewritten[i]["content"] = (
                        "UNIVERSAL COVERAGE REQUIREMENT: First derive distinct learning objectives from THIS topic/source, then write one question per objective. "
                        "Do not use different scenarios to disguise the same task. Every item must primarily test target-language knowledge, stay inside the topic, and remain CEFR-appropriate. "
                        "Avoid outside-knowledge, arithmetic, trivia, visual-pattern, and meta-spelling questions unless such knowledge is explicitly the lesson target.\n\n"
                        + content
                    )
                    break

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_prompt_policy_installed = True
