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
ASSESSMENT ENGINE V6.8 — SOURCE-GROUNDED OBJECTIVE SCHEDULER

This policy applies to every supported language, CEFR level and topic. It overrides weaker or conflicting variety instructions.

1. SOURCE EVIDENCE IS THE AUTHORITY
Use only teaching points supported by the supplied lesson evidence. The topic title alone is never sufficient evidence for a question target.

2. TEST LEARNER COMPETENCE, NOT LINGUISTIC TRIVIA
Prefer knowledge a learner actually needs to understand, produce, choose or interpret the target language. Descriptive terminology, etymology, historical roots, abstract phonetic labels, accent-mark trivia and spelling micro-trivia are assessable only when explicitly central to the source, level-appropriate and useful. When practical application can test the same point, test the application instead of terminology.

3. DISTINCT UNDERLYING OBJECTIVES INSIDE THE CURRENT BATCH
Every item in the CURRENT response must test a materially different source-backed objective. Changing only a word, numeral, kinship term, name, example, setting, price, time, object or story is NOT a new objective. Sibling vocabulary items tested through the same lookup/use operation count as the same broad objective unless the source teaches a genuinely different usage condition, rule, contrast or communicative function. Do not fill a batch with multiple cosmetic variants of the same operation.

4. PREVIOUS OBJECTIVES ARE SOFT PRIORITIES, NOT LIFETIME BANS
Previous-question context may contain entries beginning with `USED OBJECTIVE KEY`. Prefer objectives that have not been used recently. If the lesson is narrow and unused objectives are exhausted, revisit a broader area only when the new item tests a materially different sub-target, application, form-function distinction, usage condition or comprehension demand. Do not repeat the same fact/question with different decoration.

5. TRUE REPEATS REMAIN FORBIDDEN
Never repeat or closely paraphrase an earlier prompt, answer mapping, rule question, communicative exchange or semantic target. A new scenario does not make an old objective new.

6. BREADTH BEFORE COSMETIC VARIETY
When the source supports it, distribute a 10-item batch across at least four distinct operations/evidence families and normally use no more than three items from the same broad operation. Valid operations include meaning, contextual use, grammar, orthographic form, comprehension, contrast, pragmatic use and pronunciation. If the source genuinely lacks that breadth, use materially different sub-targets rather than inventing outside content.

7. LANGUAGE KNOWLEDGE MUST DECIDE THE ANSWER
Reject questions solvable mainly through arithmetic, counting, chronology, geography, world knowledge, trivia, visual resemblance or common-sense logic. The context must uniquely support the intended answer. Do not invent a situation that only weakly suggests an exact answer: for example, merely saying that weather is very cold does not uniquely imply zero degrees. Do not reveal the answer as a digit, translation, parenthetical cue or equivalent representation in the prompt.

8. FORMAT SERVES THE OBJECTIVE
Use situational choice, dialogue response, contextual comprehension, form-function discrimination, sentence completion, interpretation or another suitable form according to the source-backed objective. Do not use a new format merely to disguise a repeated objective.

9. DISTRACTORS REPRESENT REAL CONFUSIONS
All options must be grammatically and semantically comparable and plausible at the learner's level. For meaning/context/usage questions, distractors must be real, natural target-language forms supported by the lesson or normal language use; never invent pseudoforms or borrow lookalikes from another language. Deliberate misspellings are allowed only when the objective itself explicitly tests orthographic/form discrimination. Avoid absurd alternatives and visual giveaways.

10. CANONICAL OBJECTIVE KEY — MANDATORY STRUCTURE
For every generated question, the English `why` field MUST begin with exactly one marker in this form: [[OBJ:operation:underlying-target]]. `operation` MUST be exactly one of: meaning, contextual-use, grammar, orthography-form, comprehension, contrast, pragmatic-use, pronunciation. `underlying-target` must describe the transferable linguistic/communicative target, never the scenario, example name or incidental numeral. Questions that differ only by sibling vocabulary item or scenario but test the same operation and transferable target MUST use the same key and therefore cannot both survive. After the marker, write one short English explanation. Do not put the marker in any other field.

11. COMPACT OUTPUT
Keep `why` and `why_tr` to one short sentence each. Keep translations natural but concise. Do not add prose outside the required JSON. Complete JSON is more important than decorative wording.

12. FINAL AUDIT
Before returning JSON, verify that every current-batch objective is materially distinct, every item has source support, no earlier question is semantically repeated, every context uniquely determines its answer, distractors are legitimate, and every item is appropriate for the learner level.
"""

        rewritten[system_idx]["content"] = (
            policy
            + old_system.replace(
                "Pedagogic Assessment Engine (V5)",
                "Pedagogic Assessment Engine (V6.8)",
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

            # Large over-generation caused truncation and latency. Keep one compact
            # first batch; the guard performs a single small bounded repair if needed.
            match = re.search(r"TASK: Generate EXACTLY\s+(\d+)", content)
            if match:
                try:
                    generated = int(match.group(1))
                    if generated > 10:
                        content = content[:match.start(1)] + "10" + content[match.end(1):]
                except Exception:
                    pass

            rewritten[i]["content"] = (
                "OBJECTIVE-SCHEDULER REQUIREMENT: Ground every item in SOURCE MATERIAL and make underlying objectives materially distinct, not merely different scenarios or sibling vocabulary examples. "
                "Treat `USED OBJECTIVE KEY` entries as objectives to avoid when unused source-backed alternatives exist. "
                "The English `why` field must begin with [[OBJ:operation:underlying-target]], using one allowed operation from the system policy. "
                "Contexts must uniquely determine the answer; distractors must be legitimate; keep output compact and complete.\n\n"
                + content
            )
            break

        # Assessment calls fail fast. Lesson/material calls never enter this branch.
        try:
            kwargs["max_tokens"] = min(int(kwargs.get("max_tokens", 2000)), 2000)
        except Exception:
            kwargs["max_tokens"] = 2000
        try:
            kwargs["temperature"] = min(float(kwargs.get("temperature", 0.50)), 0.50)
        except Exception:
            kwargs["temperature"] = 0.50
        kwargs["allow_fallback"] = False

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_prompt_policy_installed = True
