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

        legacy_examples = [
            '* Example: "¿Cuánto es setenta más treinta?"\n',
            '* Example: "¿En cuál de las siguientes palabras la letra \'g\' se pronuncia con un sonido fuerte (/x/) ante vocal?" [gente, gato, goma, gusto]\n',
        ]
        for example in legacy_examples:
            old_system = old_system.replace(example, "")

        v64_policy = """
ASSESSMENT ENGINE V6.4 — EVIDENCE-GROUNDED OBJECTIVE POLICY

This policy applies to every supported language, CEFR level, topic, quiz and activity. It overrides weaker or conflicting variety instructions.

1. SOURCE EVIDENCE IS THE AUTHORITY
The SOURCE MATERIAL may contain an ASSESSMENT EVIDENCE PACK extracted from the existing lesson. Every learning objective and every correct answer must be supported by that evidence. Do not invent a new target merely because it is broadly related to the topic title.

2. DERIVE TEACHING POINTS BEFORE QUESTIONS
Silently extract a list of distinct teachable points from the source: vocabulary meanings/usages, grammar rules and form-function contrasts, communicative functions, pragmatic/register choices, pronunciation distinctions, explicitly taught orthography, examples, dialogue patterns and comprehension targets. Build questions from those points, not from general knowledge about the topic.

3. ONE TEACHING POINT PER QUESTION
Each question must test one clear source-backed point, and no two questions may test materially the same point. Changing names, numbers, objects, direction, setting or story does not create a new objective. If two questions require essentially the same knowledge or operation, replace one.

4. PREVIOUS QUESTIONS CONSUME THEIR TARGETS
Treat supplied previous questions as already-used objectives. Do not paraphrase, reverse, rename, renumber or re-skin them. Reuse a broad theme only if the new item tests a genuinely different source-backed distinction.

5. LANGUAGE KNOWLEDGE MUST DECIDE THE ANSWER
The correct option must depend primarily on knowledge of the target language and lesson. Reject questions solvable mainly by arithmetic, counting, chronology, geography, world knowledge, trivia, visual resemblance, common-sense logic or facts explicitly stated in the prompt unless the source itself explicitly teaches that exact skill.

6. DO NOT FILL GAPS WITH INVENTED CONTENT
If the source supports fewer distinct high-quality objectives than the requested batch size, deepen valid source-backed contrasts, usage conditions, register choices, comprehension or examples. Never pad the batch with unrelated facts, generic topic trivia or artificial math/logic tasks.

7. FORMAT SERVES THE TEACHING POINT
Choose the format best suited to the source-backed target: contextual meaning, situational choice, dialogue response, form-function discrimination, sentence completion, interpretation, comprehension or another appropriate form. Do not use different formats merely to disguise a repeated target.

8. NO SHALLOW META QUESTIONS
Do not test string length, letter count, which answer merely looks correctly spelled, one-word-vs-multiple-word trivia, accent/tilde presence, character shape or similar visual properties unless that exact orthographic distinction is explicitly taught in the source.

9. DISTRACTORS MUST REPRESENT REAL CONFUSIONS
Correct answer and distractors must share the same grammatical/semantic class and be plausible at the learner's level. Distractors should reflect realistic confusions around the exact source-backed target, not random wrong answers or visual giveaways.

10. FINAL EVIDENCE AUDIT
Before returning JSON, silently label every question with (a) its one-line learning objective and (b) the source evidence that supports it. Replace any item that lacks clear source support, overlaps another objective, depends more on outside knowledge than language knowledge, leaks its answer, or could be solved reliably by a non-speaker.
"""

        rewritten[system_idx]["content"] = (
            v64_policy
            + old_system.replace(
                "Pedagogic Assessment Engine (V5)",
                "Pedagogic Assessment Engine (V6.4)",
                1,
            )
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
            rewritten[i]["content"] = (
                "EVIDENCE-GROUNDED REQUIREMENT: Use the SOURCE MATERIAL as the authority. First extract distinct teaching points that are explicitly supported there, then write one question per teaching point. "
                "Do not generate objectives from the topic title alone. Do not pad the set with arithmetic, general knowledge, trivia, chronology, visual-pattern or meta-spelling tasks unless the source explicitly teaches that exact skill. "
                "Every correct answer must be traceable to the source evidence.\n\n"
                + content
            )
            break

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_prompt_policy_installed = True
