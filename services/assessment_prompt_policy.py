"""Runtime prompt policy for assessment generation.

Keeps the large legacy ai_engine stable while replacing only the V5 assessment
instructions with a tighter V6.1 policy. Non-assessment LLM calls are untouched.
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

        v61_policy = """
ASSESSMENT ENGINE V6.1 — COVERAGE-FIRST GENERATION

These rules override weaker or conflicting diversity wording below.

1. PLAN THE COVERAGE BEFORE WRITING
Silently create a coverage plan with one distinct language-learning objective per question. Generate the questions only after the objectives are non-overlapping. Different stories, names, numbers, objects, or locations do NOT make two questions different if the learner performs the same linguistic task.

2. ONE OBJECTIVE = ONE QUESTION
Do not test the same vocabulary mapping, grammatical fact, communicative function, pronunciation distinction, number-reading task, spelling fact, relationship, or reasoning operation twice in the same batch. Do not repeat an exhausted objective from previous questions either.

3. LANGUAGE KNOWLEDGE MUST BE NECESSARY
Every item must primarily test the target language. Reject ideas that are mainly arithmetic, geography/general knowledge, visual pattern recognition, or world knowledge with target-language words wrapped around them.

4. NUMBER TOPICS: TEST LANGUAGE, NOT MATH
For number-related topics, arithmetic may appear in at most TWO questions. All other questions must use genuinely different linguistic functions, chosen across areas such as: saying a price, understanding a price, telling time, age, dates, addresses, phone digits, room/line/platform numbers, quantities, measurements, ordering, schedules, and number forms in natural utterances.
Crucially, "read/pronounce this numeral in context" is ONE objective. Do NOT repeat it with a hotel room, page number, shoe size, bus line, address, platform, price, or any other changed wrapper.

5. NO META-SPELLING OR FORM-TRIVIA
Do not ask whether a number/word is written as one word, which option contains an accent/tilde, how many letters it has, which spelling merely looks right, or similar string-property trivia unless orthography itself is explicitly the lesson topic.

6. NO GENERAL-KNOWLEDGE SUBSTITUTES
Do not ask facts such as how many countries, days, continents, planets, corners, or other factual quantities merely to elicit a number. The tested knowledge must come from the language lesson, not outside knowledge.

7. FORMAT BREADTH
Use a balanced mix of situational choice, dialogue response, contextual comprehension, form/meaning discrimination, and at most two fill-in-the-blank items. Do not reuse the same question archetype more than twice.

8. FINAL PAIRWISE AUDIT
Before returning JSON, compare every pair of questions. For each pair ask: "Could both be described by the same one-line learning objective?" If yes, replace one. Also replace any question a non-speaker could answer reliably without target-language knowledge.
"""

        # Remove legacy examples that bias the model toward arithmetic/meta-trivia.
        legacy_examples = [
            '* Example: "¿Cuánto es setenta más treinta?"\n',
            '* Example: "¿En cuál de las siguientes palabras la letra \'g\' se pronuncia con un sonido fuerte (/x/) ante vocal?" [gente, gato, goma, gusto]\n',
        ]
        for example in legacy_examples:
            old_system = old_system.replace(example, "")

        rewritten[system_idx]["content"] = v61_policy + old_system.replace(
            "Pedagogic Assessment Engine (V5)",
            "Pedagogic Assessment Engine (V6.1)",
            1,
        )

        for i, m in enumerate(rewritten):
            if isinstance(m, dict) and m.get("role") == "user":
                content = str(m.get("content", ""))
                if "TASK: Generate EXACTLY" in content:
                    rewritten[i]["content"] = (
                        "COVERAGE-FIRST REQUIREMENT: Decide all distinct learning objectives before writing any question. "
                        "Do not create paraphrases of one task. For number topics, arithmetic <= 2 and numeral-reading/pronunciation-in-context <= 1. "
                        "Do not use general-knowledge quantity questions or spelling/tilde/one-word trivia.\n\n"
                        + content
                    )
                    break

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_prompt_policy_installed = True
