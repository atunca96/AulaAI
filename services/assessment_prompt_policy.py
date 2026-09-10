"""Runtime policy for assessment generation.

Injects a compact universal assessment policy without touching lesson/material
generation. The policy applies only to Pedagogic Assessment Engine calls.
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

        # Remove the two legacy sections that most strongly conflict with objective-first
        # generation. They rewarded cosmetic scenario variety and supplied archetypes the
        # model repeatedly imitated. All language/CEFR/translation/distractor rules remain.
        old_system = re.sub(
            r"\n\s*6\. THEMATIC BREADTH & AUTHENTIC COMMUNICATIVE EXPANSION:.*?(?=\n\s*7\. DISTRACTOR)",
            "\n",
            old_system,
            flags=re.S,
        )
        old_system = re.sub(
            r"\n\s*8\. COMMUNICATIVE QUESTION ARCHETYPES & FORMAT VARIETY \(CRITICAL\):.*?(?=\n\s*RESPONSE FORMAT:)",
            "\n",
            old_system,
            flags=re.S,
        )

        # Remove individual legacy examples that can anchor generation to a specific
        # language or shallow exercise style.
        legacy_examples = [
            '* Example: "¿Cuánto es setenta más treinta?"\n',
            '* Example: "¿En cuál de las siguientes palabras la letra \'g\' se pronuncia con un sonido fuerte (/x/) ante vocal?" [gente, gato, goma, gusto]\n',
        ]
        for example in legacy_examples:
            old_system = old_system.replace(example, "")

        v63_policy = """
ASSESSMENT ENGINE V6.3 — UNIVERSAL OBJECTIVE-FIRST POLICY

This policy applies to every supported language, CEFR level, topic, source type, quiz and activity. It overrides weaker or conflicting variety instructions.

1. DERIVE THE LEARNING TARGETS FIRST
Before writing any question, silently map the distinct teachable targets actually supported by THIS topic/source. Targets may include vocabulary use/contrast, grammar form-function, communicative function, pragmatics, pronunciation, orthography only when explicitly taught, discourse, and comprehension. Do not invent unrelated targets merely to fill the batch.

2. ONE TARGET PER QUESTION; ONE QUESTION PER TARGET
Each question must test one clear target, and no two questions may test materially the same target. Changing names, numbers, nouns, examples, direction, setting, or story does not create a new target. If the learner performs essentially the same mental/language operation twice, replace one.

3. PREVIOUS QUESTIONS CONSUME THEIR TARGETS
Treat supplied previous questions as already-used objectives. Do not paraphrase, reverse, rename, renumber, or re-skin them. Reuse a broad theme only when the new question tests a genuinely different language distinction.

4. LANGUAGE KNOWLEDGE MUST DECIDE THE ANSWER
The correct option must depend primarily on knowledge of the target language and the lesson. Reject ideas solvable mainly by arithmetic, counting, chronology, geography, world knowledge, trivia, visual resemblance, common-sense logic, or facts explicitly stated in the prompt unless that exact skill is explicitly taught by the source.

5. SOURCE-FAITHFUL EXPANSION
Stay within the pedagogical scope of the topic. Natural CEFR-appropriate contextualization is allowed, but do not introduce outside facts just to create apparent variety. Narrow topics should vary linguistic distinctions, usage, register, form, comprehension or communicative purpose rather than unrelated content.

6. FORMAT SERVES THE TARGET
Choose the question format that best tests the target: situational choice, dialogue response, contextual comprehension, form/meaning discrimination, sentence completion, interpretation, or another appropriate form. Do not force every topic into the same template. No single archetype should dominate the batch.

7. NO SHALLOW META QUESTIONS
Do not test string length, letter count, which answer merely looks correctly spelled, one-word-vs-multiple-word trivia, accent/tilde presence, character shape, or similar visual properties unless that exact orthographic distinction is explicitly taught. Pronunciation/alphabet topics must test authentic sound-letter use, not symbol trivia.

8. DISTRACTORS MUST REPRESENT REAL CONFUSIONS
Correct answer and distractors must share the same grammatical/semantic class and be plausible at the learner's level. Distractors should reflect realistic confusions around the target, not random wrong answers, absurd alternatives, or obvious visual/length giveaways.

9. FINAL AUDIT BEFORE JSON
Silently label every proposed question with its one-line learning objective. Compare every pair. Replace any pair with overlapping objectives. Replace any item that depends more on outside knowledge than language knowledge, leaks its answer, drifts outside the topic/source, or can be solved reliably by a non-speaker.
"""

        rewritten[system_idx]["content"] = (
            v63_policy
            + old_system.replace(
                "Pedagogic Assessment Engine (V5)",
                "Pedagogic Assessment Engine (V6.3)",
                1,
            )
        )

        for i, m in enumerate(rewritten):
            if not isinstance(m, dict) or m.get("role") != "user":
                continue
            content = str(m.get("content", ""))
            if "TASK: Generate EXACTLY" not in content:
                continue

            # Remove legacy random emphasis/format blocks that compete with the universal
            # objective-first policy. Keep task, topic, source, history and JSON schema.
            content = re.sub(
                r"\n\s*PEDAGOGICAL EMPHASIS:.*?(?=\n\s*JSON STRUCTURE:)",
                "\n",
                content,
                flags=re.S,
            )
            rewritten[i]["content"] = (
                "OBJECTIVE-FIRST REQUIREMENT: Derive distinct teachable targets from THIS topic/source before writing questions. "
                "Each item must test a different target-language objective; cosmetic scenario changes do not count as diversity. "
                "Do not substitute arithmetic, general knowledge, trivia, or visual pattern tasks unless the source explicitly teaches that skill.\n\n"
                + content
            )
            break

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_prompt_policy_installed = True
