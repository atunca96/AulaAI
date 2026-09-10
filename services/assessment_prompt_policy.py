"""Runtime prompt policy for assessment generation.

Keeps the large legacy ai_engine stable while replacing only the V5 assessment
instructions with a tighter V6 policy. Non-assessment LLM calls are untouched.
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

        # Preserve all dynamically injected CEFR/language guidance, but prepend the
        # rules that the model must optimize before cosmetic scenario variety.
        v6_policy = """
ASSESSMENT ENGINE V6 — PEDAGOGICAL DIVERSITY OVERRIDE

These rules have higher priority than any weaker or conflicting variety wording below:

1. DISTINCT LEARNING TARGETS, NOT DISTINCT STORIES
Before writing the batch, silently assign a one-line pedagogical target to every question. Every target must be different. Two questions are duplicates if they test the same vocabulary mapping, grammatical fact, relationship, communicative function, pronunciation distinction, or reasoning operation — even when names, numbers, direction, wording, setting, or story are changed.

2. PREVIOUS QUESTIONS ARE EXHAUSTED TARGETS
Treat every previous question and answer supplied in the request as a learning target that has already been used. Do not paraphrase it, reverse it, swap names/numbers, or ask the same underlying fact in another scenario.

3. LANGUAGE KNOWLEDGE MUST BE NECESSARY
The learner must need knowledge of the target language to answer. Do not produce items solvable mainly through arithmetic, general knowledge, visual spelling clues, pattern spotting, or logic independent of the language.

4. NUMBER-TOPIC RULE
When the topic involves numbers, spread assessment across authentic language functions: prices, time, age, dates, addresses, phone numbers, quantities, ordering, measurements, schedules, and interpreting numbers in context. Arithmetic may appear in at most TWO questions per generated batch. Changing operands does not create a new pedagogical target.

5. NO META-SPELLING TRIVIA
Do not ask which word has an accent/tilde, how many letters a word has, whether a number is written as one word, which word is longer, or similar string-property trivia unless that exact orthographic rule is explicitly the lesson topic.

6. FORMAT BREADTH
Use a genuine mix of situational choice, dialogue response, contextual comprehension, form/meaning discrimination, and at most two fill-in-the-blank questions. Do not reuse one question template more than twice.

7. FINAL SELF-CHECK
Before returning JSON, compare every pair of questions. If two can be described by essentially the same learning objective, replace one. If a non-speaker could answer without knowing the target language, replace it.

"""

        # Remove the old math example because models were imitating it heavily.
        old_system = old_system.replace(
            '* Example: "¿Cuánto es setenta más treinta?"\n', ""
        )
        old_system = old_system.replace(
            'You are the ', 'You are the ', 1
        )
        rewritten[system_idx]["content"] = v6_policy + old_system.replace(
            "Pedagogic Assessment Engine (V5)",
            "Pedagogic Assessment Engine (V6)",
            1,
        )

        # Reinforce batch planning immediately before the user payload so the
        # instruction remains salient even with long source material/history.
        for i, m in enumerate(rewritten):
            if isinstance(m, dict) and m.get("role") == "user":
                content = str(m.get("content", ""))
                if "TASK: Generate EXACTLY" in content:
                    rewritten[i]["content"] = (
                        "BATCH PLANNING REQUIREMENT: Build a coverage set, not a set of paraphrases. "
                        "Each question must test a different underlying language-learning objective. "
                        "For number topics, use no more than two arithmetic questions and prioritize authentic linguistic uses of numbers.\n\n"
                        + content
                    )
                    break

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_prompt_policy_installed = True
