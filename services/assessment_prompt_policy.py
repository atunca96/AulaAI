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
ASSESSMENT ENGINE V6.9 — FINAL LEGACY QUALITY POLICY

This policy applies to every supported language, CEFR level and topic. It overrides weaker or conflicting assessment instructions.

1. SOURCE IS THE BOUNDARY
Use only source-backed language knowledge. Do not create facts, forms, rules, cultural claims, scientific claims or contrasts that are not taught by the supplied lesson evidence.

2. TEST USEFUL LANGUAGE COMPETENCE
Prefer meaning, form-function, grammar, contextual use, comprehension, pragmatic choice and source-taught contrasts. Reject etymology, historical roots, phonetic terminology, IPA labels, accent-mark trivia, letter trivia, morphology jargon such as prefix/suffix/morpheme/stem, and comparisons with other languages unless that exact area is explicitly central to the lesson.

3. EVERY QUESTION MUST HAVE A DISTINCT UNDERLYING OBJECTIVE
Changing a numeral, vocabulary item, name, object, setting, price, time or story does not create a new objective. Sibling vocabulary items tested with the same lookup/completion operation count as one broad objective unless they teach a genuinely different rule, usage condition, contrast or communicative function. A 10-item batch should normally span at least four materially different objective/operation families when the source permits.

4. NO COSMETIC REPEATS
Do not repeat the same rule, answer mapping, communicative exchange, spelling fact, lookup operation or semantic target with different decoration. Previous `USED OBJECTIVE KEY` entries are strong avoidance signals.

5. CONTEXT MUST UNIQUELY DETERMINE THE ANSWER
Do not invent weak clues merely to force an exact answer. Examples of forbidden logic: "it is very cold" therefore exactly zero degrees; "a ticket costs ___" with no source-backed price cue; an arbitrary room/floor/time with no explicit cue. If the context does not uniquely determine the answer, choose another objective.

6. NO ANSWER LEAKS
Never reveal the answer as a digit, translation, parenthetical cue, equivalent representation or quoted solution in the prompt. Do not write `(6)` and ask for `seis`, or show a translated answer and ask the learner to reproduce it.

7. DISTRACTORS MUST BE REAL AND PLAUSIBLE
For meaning, context and usage questions, every distractor must be a real, natural target-language form or a source-backed alternative. Never invent pseudoforms such as altered spellings solely to look similar, and never borrow a lookalike from another language. Deliberate misspellings are acceptable only when the lesson itself is centrally about orthography/spelling and the question directly tests that taught distinction.

8. OPTIONS MUST BE STRUCTURALLY CLEAN
Exactly one answer and exactly three distinct distractors. No duplicate option after accent/case normalization. No slash-combined multi-answer option such as `dos / dos`. All four options must be comparable in grammatical and semantic type.

9. FORMAT DIVERSITY SERVES PEDAGOGY
Use a balanced mix of contextual completion, form-function discrimination, rule application, comprehension, dialogue/pragmatic choice, meaning and source-backed contrast. Do not let blank-completion or direct lookup dominate the batch when other taught objectives exist.

10. CANONICAL OBJECTIVE KEY
Every `why` field MUST begin with exactly `[[OBJ:operation:underlying-target]]`. `operation` must be one of: meaning, contextual-use, grammar, orthography-form, comprehension, contrast, pragmatic-use, pronunciation. `underlying-target` describes the transferable learner skill, never the incidental example or numeral.

11. COMPACTNESS IS REQUIRED FOR SPEED
After the objective marker, keep `why` to at most 8 English words and `why_tr` to at most 8 Turkish words. Keep `translation_en` and `translation_tr` to at most 14 words each. Prompts should be concise and natural. Do not add decorative prose. Complete all requested questions inside the token budget.

12. FINAL SELF-AUDIT BEFORE JSON
For every item verify: source-backed, useful, unique objective, uniquely answerable context, no answer leak, no meta-trivia unless central, four distinct plausible options, no pseudoforms, and CEFR-appropriate language. If any item fails, replace it before returning JSON.
"""

        rewritten[system_idx]["content"] = (
            policy
            + old_system.replace(
                "Pedagogic Assessment Engine (V5)",
                "Pedagogic Assessment Engine (V6.9)",
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

            # Avoid the old 15-candidate over-generation. Ten compact complete items
            # are faster and more useful than a truncated oversized response.
            match = re.search(r"TASK: Generate EXACTLY\s+(\d+)", content)
            if match:
                try:
                    generated = int(match.group(1))
                    if generated > 10:
                        content = content[:match.start(1)] + "10" + content[match.end(1):]
                except Exception:
                    pass

            rewritten[i]["content"] = (
                "FINAL-QUALITY REQUIREMENT: Generate only source-backed, materially distinct learner objectives. "
                "No meta-linguistic trivia, morphology jargon, cross-language trivia, pseudoform distractors, arbitrary exact-number contexts, answer leaks, or cosmetic repeats. "
                "Every `why` begins with [[OBJ:operation:underlying-target]]. Keep all explanations/translations extremely compact so the complete requested batch fits in one response.\n\n"
                + content
            )
            break

        try:
            kwargs["max_tokens"] = min(int(kwargs.get("max_tokens", 2000)), 2000)
        except Exception:
            kwargs["max_tokens"] = 2000
        try:
            kwargs["temperature"] = min(float(kwargs.get("temperature", 0.42)), 0.42)
        except Exception:
            kwargs["temperature"] = 0.42
        kwargs["allow_fallback"] = False

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_prompt_policy_installed = True
