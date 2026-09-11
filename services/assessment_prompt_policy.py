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
ASSESSMENT ENGINE V6.7 — SOURCE-GROUNDED OBJECTIVE SCHEDULER

This policy applies to every supported language, CEFR level and topic. It overrides weaker or conflicting variety instructions.

1. SOURCE EVIDENCE IS THE AUTHORITY
Use only teaching points supported by the supplied lesson evidence. The topic title alone is never sufficient evidence for a question target.

2. TEST LEARNER COMPETENCE, NOT LINGUISTIC TRIVIA
Prefer knowledge a learner actually needs to understand, produce, choose or interpret the target language. Descriptive terminology, etymology, historical roots, abstract phonetic labels and spelling trivia are assessable only when they are explicitly a central learning objective of the source, appropriate for the CEFR level, and useful to the learner. When a practical application can test the same point, test the application instead of asking for terminology.

3. DISTINCT OBJECTIVES INSIDE THE CURRENT BATCH
Every item in the CURRENT response must test a materially different source-backed objective. Changing only a word, numeral, name, example, setting or story is not enough. Canonical objective keys must be unique within the current response.

4. PREVIOUS OBJECTIVES ARE SOFT PRIORITIES, NOT LIFETIME BANS
Previous-question context may contain entries beginning with `USED OBJECTIVE KEY`. Prefer objectives that have not been used recently. However, if the lesson is narrow and unused objectives are exhausted, you MAY revisit a broader previously used area only when the new item tests a materially different sub-target, application, form-function distinction, usage condition or comprehension demand. Do not repeat the same fact/question with different decoration. When revisiting a broad area, use a refined canonical key that describes the genuinely different sub-target.

5. TRUE REPEATS REMAIN FORBIDDEN
Never repeat or closely paraphrase an earlier prompt, answer mapping, rule question, communicative exchange or semantic target. Examples such as asking the same spelling rule again, the same restaurant phrase again, or the same form-function fact with slightly different wording are still repeats.

6. EVIDENCE BREADTH
When multiple evidence families are available, use several of them. A 10-item batch should normally draw from at least three available families and no single family should dominate. Never invent outside content just to satisfy breadth.

7. LANGUAGE KNOWLEDGE MUST DECIDE THE ANSWER
Reject questions solvable mainly through arithmetic, counting, chronology, geography, world knowledge, trivia, visual resemblance, common-sense logic or facts stated directly in the prompt unless that exact skill is explicitly taught by the lesson.

8. FORMAT SERVES THE OBJECTIVE
Use situational choice, dialogue response, contextual comprehension, form-function discrimination, sentence completion, interpretation or another suitable form according to the source-backed objective. Do not use a new format merely to disguise a repeated objective.

9. DISTRACTORS REPRESENT REAL CONFUSIONS
All options must be grammatically and semantically comparable and plausible at the learner's level. Avoid absurd alternatives, visual giveaways and options that can be eliminated without target-language knowledge.

10. CANONICAL OBJECTIVE KEY — MANDATORY
For every generated question, the `why` field MUST begin with exactly one marker: [[OBJ:canonical-key]]. After the marker, write one short English explanation. The key must be lowercase English, concise and describe the underlying linguistic/communicative objective rather than the scenario. Equivalent objectives inside the current batch must use the same key and therefore cannot both survive. Do not put this marker in any other field.

11. COMPACT OUTPUT
Keep `why` and `why_tr` to one short sentence each. Keep translations natural but concise. Do not add prose outside the required JSON. This is required so the complete requested batch fits in one response.

12. FINAL AUDIT
Before returning JSON, verify that current-batch objective keys are unique, every item has source support, no earlier question is semantically repeated, and every item is appropriate for the learner level.
"""

        rewritten[system_idx]["content"] = (
            policy
            + old_system.replace(
                "Pedagogic Assessment Engine (V5)",
                "Pedagogic Assessment Engine (V6.7)",
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

            # The core generator normally over-asks (e.g. 15 candidates for a 10-item
            # batch). With translations + explanations that can exceed the 25-second,
            # 2000-token assessment budget and produce truncated JSON. Ask for at most
            # ten complete candidates per call; the guard performs one bounded refill
            # only when validation leaves a partial batch.
            match = re.search(r"TASK: Generate EXACTLY\s+(\d+)", content)
            if match:
                try:
                    generated = int(match.group(1))
                    if generated > 10:
                        content = content[:match.start(1)] + "10" + content[match.end(1):]
                except Exception:
                    pass

            rewritten[i]["content"] = (
                "OBJECTIVE-SCHEDULER REQUIREMENT: Ground every item in the SOURCE MATERIAL. Keep every objective unique inside this response. "
                "Treat any `USED OBJECTIVE KEY` entries in previous-question context as objectives to avoid when unused source-backed alternatives exist, not as permanent bans. "
                "Never repeat the same semantic question/fact from an earlier round. The English `why` field must begin with [[OBJ:canonical-key]]. "
                "Keep translations and explanations concise so the full JSON batch completes.\n\n"
                + content
            )
            break

        # Assessment calls fail fast. Lesson/material calls never enter this branch.
        try:
            kwargs["max_tokens"] = min(int(kwargs.get("max_tokens", 2000)), 2000)
        except Exception:
            kwargs["max_tokens"] = 2000
        try:
            kwargs["temperature"] = min(float(kwargs.get("temperature", 0.55)), 0.55)
        except Exception:
            kwargs["temperature"] = 0.55
        kwargs["allow_fallback"] = False

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_prompt_policy_installed = True
