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

        # Remove legacy blocks that rewarded cosmetic scenario variety and supplied
        # archetypes which the model repeatedly copied.
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

        policy = """
ASSESSMENT ENGINE V6.6 — SOURCE-GROUNDED OBJECTIVE POLICY

This policy applies to every supported language, CEFR level and topic. It overrides weaker or conflicting variety instructions.

1. SOURCE EVIDENCE IS THE AUTHORITY
Use only teaching points supported by the supplied lesson evidence. The topic title alone is never sufficient evidence for a question target.

2. TEST LEARNER COMPETENCE, NOT LINGUISTIC TRIVIA
Prefer knowledge a learner actually needs to understand, produce, choose or interpret the target language. Descriptive linguistic facts, terminology, etymology, historical roots, abstract phonetic labels and spelling trivia are assessable only when they are explicitly a central learning objective of the source, appropriate for the CEFR level, and useful to the learner. When a practical application can test the same point, test the application instead of asking the learner to name the terminology.

3. DISTINCT OBJECTIVES, NOT DIFFERENT DECORATIONS
Changing names, numbers, nouns, examples, settings, direction or story does not create a new objective. If two questions require essentially the same language knowledge or mental operation, they are duplicates. Systematic lists/paradigms must not receive separate objectives merely because the item value changes unless an item has a genuinely different form, use or rule.

4. EVIDENCE BREADTH
When multiple evidence families are available, use several of them. A 10-item batch should normally draw from at least three available families and no single family should dominate. Never invent outside content just to satisfy breadth.

5. LANGUAGE KNOWLEDGE MUST DECIDE THE ANSWER
Reject questions solvable mainly through arithmetic, counting, chronology, geography, world knowledge, trivia, visual resemblance, common-sense logic or facts stated directly in the prompt unless that exact skill is explicitly taught by the lesson.

6. FORMAT SERVES THE OBJECTIVE
Use situational choice, dialogue response, contextual comprehension, form-function discrimination, sentence completion, interpretation or another suitable form according to the source-backed objective. Do not use a new format merely to disguise a repeated objective.

7. DISTRACTORS REPRESENT REAL CONFUSIONS
All options must be grammatically and semantically comparable and plausible at the learner's level. Avoid absurd alternatives, visual giveaways and options that can be eliminated without target-language knowledge.

8. CANONICAL OBJECTIVE KEY — MANDATORY
For every generated question, the `why` field MUST begin with exactly one machine-readable marker in this form: [[OBJ:canonical-key]]. After the marker, write the normal concise English explanation.
The key must be lowercase English, short, stable and describe the underlying source-backed language objective rather than the scenario or surface answer. Equivalent questions MUST receive the same key even if wording, names, numbers, examples or direction change. For a systematic paradigm, changing only the member being looked up does NOT justify a new key. Give a different key only when the learner must know a genuinely different linguistic distinction or communicative function.
Do not put this marker in prompt, answer, distractors, translations or `why_tr`.

9. FINAL AUDIT
Before returning JSON, compare the canonical objective keys. Replace every duplicate key. Also replace any question that lacks clear source support, is too meta for the level, depends more on outside knowledge than language knowledge, leaks its answer or could reliably be solved by a non-speaker.
"""

        rewritten[system_idx]["content"] = (
            policy
            + old_system.replace(
                "Pedagogic Assessment Engine (V5)",
                "Pedagogic Assessment Engine (V6.6)",
                1,
            )
        )

        for i, m in enumerate(rewritten):
            if not isinstance(m, dict) or m.get("role") != "user":
                continue
            content = str(m.get("content", ""))
            if "TASK: Generate EXACTLY" not in content:
                continue

            # Remove the old random emphasis block. Keep source, history and schema.
            content = re.sub(
                r"\n\s*PEDAGOGICAL EMPHASIS:.*?(?=\n\s*JSON STRUCTURE:)",
                "\n",
                content,
                flags=re.S,
            )

            # The core generator historically asks for 15 candidates for a 10-item
            # batch. Twelve is enough headroom while reducing latency/output size.
            match = re.search(r"TASK: Generate EXACTLY\s+(\d+)", content)
            if match:
                try:
                    generated = int(match.group(1))
                    if generated > 12:
                        content = content[:match.start(1)] + "12" + content[match.end(1):]
                except Exception:
                    pass

            rewritten[i]["content"] = (
                "OBJECTIVE-KEY REQUIREMENT: Ground every item in the SOURCE MATERIAL. Prioritize learner-usable language competence over descriptive trivia. "
                "The English `why` field must begin with [[OBJ:canonical-key]], where semantically equivalent tasks use the same stable key. "
                "Do not create a new key merely because a word, numeral, example, name or scenario changed.\n\n"
                + content
            )
            break

        # Assessment calls must fail fast. Material/lesson calls never enter this branch.
        try:
            kwargs["max_tokens"] = min(int(kwargs.get("max_tokens", 2000)), 2000)
        except Exception:
            kwargs["max_tokens"] = 2000
        try:
            kwargs["temperature"] = min(float(kwargs.get("temperature", 0.6)), 0.6)
        except Exception:
            kwargs["temperature"] = 0.6
        kwargs["allow_fallback"] = False

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_prompt_policy_installed = True
