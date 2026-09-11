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

        # Replace the old assessment protocol wholesale. Keeping fragments of V5 here
        # caused conflicting incentives (free thematic expansion, phonetic/meta examples,
        # cosmetic scenario variety). CEFR/language guidance outside this block remains.
        constitution = """
PEDAGOGIC PROTOCOL & MANDATES — ASSESSMENT ENGINE V7.0
This is the authoritative assessment policy. It overrides every weaker or conflicting assessment instruction or example.

1. SOURCE-LOCKED TRUTH
Every tested fact, form, rule, meaning, contrast and usage condition must be supported by SOURCE MATERIAL. The topic title is context, not evidence. Never invent cultural facts, prices, times, locations, scientific facts, grammar rules or language comparisons.

2. TEST LEARNER COMPETENCE, NOT LINGUISTIC TRIVIA
Prefer practical meaning, form-function, grammar, contextual use, comprehension, pragmatic choice and source-taught contrasts. Do NOT test etymology, historical roots, word roots, prefixes, suffixes, morphemes, stems, linking elements, letter counts, accent-mark trivia, phonetic terminology, IPA labels, sound labels, or comparisons with other languages unless that exact discipline is explicitly the lesson's central topic.

3. DISTINCT UNDERLYING OBJECTIVES
Before writing questions, internally allocate materially different learner objectives. Changing only a word, numeral, name, object, setting, price, time or story is NOT a new objective. Do not disguise the same lookup, spelling fact, rule or answer mapping with a new scenario. For a narrow lesson, diversify through genuinely different source-backed communicative functions, form-function distinctions, usage conditions and comprehension demands; never escape into meta-trivia.

4. NO COSMETIC OR RECENT REPEATS
Treat previous questions and `USED OBJECTIVE KEY` entries as strong avoidance signals. Do not repeat or closely paraphrase an earlier prompt, answer mapping, rule, communicative exchange or semantic target. Within the current batch, each objective must be materially distinct.

5. CONTEXT MUST UNIQUELY DETERMINE THE ANSWER
A scenario is valid only if the linguistic evidence in it makes exactly one option correct. Never invent arbitrary exact values merely to force a vocabulary answer. If the context does not determine the answer, replace the question rather than adding a weak story.

6. NO ANSWER LEAKS OR REPRESENTATION GIVEAWAYS
Do not reveal the answer as a digit, translation, parenthetical cue, equivalent representation, quoted solution or obvious reformulation in the prompt or its translations. Direct representation-conversion drills (for example numeral-to-word or translation-to-target) are allowed only when the source explicitly teaches that exact reading/writing objective, and should be used sparingly rather than dominating a batch.

7. REAL, NATURAL DISTRACTORS ONLY
Every distractor must be a real and natural target-language form or a source-backed alternative of the same grammatical and semantic class as the answer. NEVER invent pseudoforms by changing letters, accents or endings merely to resemble the answer. NEVER import lookalikes from another language. Intentional malformed forms are allowed only when orthography/form discrimination is explicitly central to the lesson.

8. CLEAN MCQ STRUCTURE
Return exactly one correct answer plus exactly three distinct distractors. After case/diacritic normalization, all four options must still be distinct. No slash-combined multi-answer options. Options must be comparable in grammatical role, semantic class and approximate specificity; no absurd or visually obvious decoys.

9. PEDAGOGICAL FORMAT BALANCE
Choose the format that best tests each objective: contextual comprehension, practical choice, dialogue/pragmatics, form-function discrimination, grammar application, source-backed contrast, or concise completion. Do not use format changes to hide repeated objectives. When the source permits breadth, no single broad format/operation should dominate the batch.

10. CANONICAL OBJECTIVE KEY
Every English `why` field MUST begin exactly with `[[OBJ:operation:underlying-target]]`. `operation` must be one of: meaning, contextual-use, grammar, orthography-form, comprehension, contrast, pragmatic-use, pronunciation. `underlying-target` describes the transferable learner skill, never an incidental example, numeral, name or scenario.

11. TARGET-LANGUAGE AND CEFR DISCIPLINE
`prompt`, `answer` and all distractors must be natural target-language text appropriate to the requested CEFR level. Do not introduce advanced terminology merely to create variety. Higher-level terminology is still forbidden unless it is source-backed and genuinely central.

12. COMPACT OUTPUT FOR ONE-PASS GENERATION
Keep prompts concise. After the objective marker, `why` is at most 8 English words and `why_tr` at most 8 Turkish words. `translation_en` and `translation_tr` should normally be at most 14 words. No prose outside JSON. Completeness is more important than decorative wording.

13. FINAL INTERNAL AUDIT
Before returning JSON, inspect every item and silently replace any item that is source-unsupported, meta-trivia, a repeated objective, weakly answerable, an answer leak, pseudoform-based, structurally invalid, CEFR-inappropriate or semantically mismatched. Return only the audited candidate set.
"""

        protocol_pattern = r"PEDAGOGIC PROTOCOL & MANDATES:.*?(?=\n\s*RESPONSE FORMAT:)"
        if re.search(protocol_pattern, old_system, flags=re.S):
            old_system = re.sub(protocol_pattern, constitution.strip(), old_system, flags=re.S)
        else:
            old_system = constitution + "\n\n" + old_system

        rewritten[system_idx]["content"] = old_system.replace(
            "Pedagogic Assessment Engine (V5)",
            "Pedagogic Assessment Engine (V7.0)",
            1,
        )

        for i, m in enumerate(rewritten):
            if not isinstance(m, dict) or m.get("role") != "user":
                continue
            content = str(m.get("content", ""))
            if "TASK: Generate EXACTLY" not in content:
                continue

            # Remove old randomness/cosmetic-variety blocks. Source, prior-question
            # history and the JSON schema remain untouched.
            content = re.sub(
                r"\n\s*PEDAGOGICAL EMPHASIS:.*?(?=\n\s*JSON STRUCTURE:)",
                "\n",
                content,
                flags=re.S,
            )

            # ai_generate_questions intentionally asks for an over-complete candidate
            # pool (c+5 / 1.5x) and then keeps the best c items. V6.9 accidentally
            # collapsed every candidate pool above ten back to ten, which caused repair
            # cascades. Preserve that built-in pool. Only cap very large requests to
            # keep the response inside the assessment token budget.
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
                "ONE-PASS QUALITY DIRECTIVE: Plan the objective set before writing. Use SOURCE MATERIAL only. "
                "Replace bad candidates internally instead of returning them. No meta-linguistic trivia, morphology jargon, cross-language trivia, pseudoforms, arbitrary exact-value scenarios, answer leaks, or cosmetic repeats. "
                "All distractors must be real natural target-language alternatives. Every `why` starts with [[OBJ:operation:underlying-target]]. Keep JSON compact enough to finish the whole candidate pool.\n\n"
                + content
            )
            break

        # Keep assessment calls under the 25-second provider timeout tier.
        try:
            kwargs["max_tokens"] = min(int(kwargs.get("max_tokens", 2000)), 2000)
        except Exception:
            kwargs["max_tokens"] = 2000
        try:
            kwargs["temperature"] = min(float(kwargs.get("temperature", 0.34)), 0.34)
        except Exception:
            kwargs["temperature"] = 0.34
        kwargs["allow_fallback"] = False

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_prompt_policy_installed = True
