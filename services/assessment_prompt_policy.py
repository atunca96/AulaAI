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

        constitution = """
PEDAGOGIC PROTOCOL & MANDATES — ASSESSMENT ENGINE V7.1
This is the authoritative assessment policy. It overrides every weaker or conflicting assessment instruction or example.

1. SOURCE-LOCKED TRUTH
Every tested fact, form, rule, meaning, contrast and usage condition must be supported by SOURCE MATERIAL. The topic title is context, not evidence. Never invent cultural, historical, scientific, geographic, numerical or grammatical facts.

2. TEST LANGUAGE COMPETENCE, NOT OUTSIDE KNOWLEDGE
A learner must be able to answer because they understand the taught language, not because they can calculate or know a world fact. Do NOT use arithmetic, calendar facts, anatomy, science, geography, object properties/counts, trivia or general knowledge as a proxy for eliciting a target word or form. Such facts are allowed only when SOURCE MATERIAL explicitly teaches them and they are themselves part of the linguistic objective.

3. TEST LEARNER COMPETENCE, NOT META-LINGUISTIC TRIVIA
Prefer practical meaning, form-function, grammar, contextual use, comprehension, pragmatic choice and source-taught contrasts. Do NOT test etymology, historical roots, word roots, prefixes, suffixes, morphemes, stems, linking elements, letter counts, accent-mark trivia, phonetic terminology, IPA labels, sound labels or comparisons with other languages unless that exact discipline is explicitly the lesson's central topic.

4. DISTINCT UNDERLYING OBJECTIVES
Before writing questions, internally allocate materially different learner objectives. Changing only a word, numeral, name, object, verb, setting, price, time or story is NOT a new objective. Reusing the same rule, auxiliary-selection principle, agreement rule, meaning mapping or communicative function with another example is still the same objective. For a narrow lesson, diversify only through genuinely different source-backed skills; never escape into trivia.

5. NO COSMETIC OR RECENT REPEATS
Treat previous questions and `USED OBJECTIVE KEY` entries as strong avoidance signals. Do not repeat or closely paraphrase an earlier prompt, answer mapping, rule, communicative exchange or semantic target. Within the current batch, each objective must be materially distinct.

6. CONTEXT MUST UNIQUELY DETERMINE THE ANSWER
A scenario is valid only if linguistic evidence in the prompt makes exactly one option correct. Do not invent an arbitrary fact or exact value just to force a vocabulary answer. If outside knowledge is required to choose the answer, replace the question.

7. NO ANSWER LEAKS OR REPRESENTATION GIVEAWAYS
Do not reveal the answer as a digit, translation, parenthetical cue, equivalent representation, quoted solution or obvious reformulation in the prompt or translations. Direct representation-conversion drills are allowed only when SOURCE MATERIAL explicitly teaches that exact reading/writing skill and must not dominate a batch.

8. REAL, NATURAL DISTRACTORS ONLY
Every distractor must be a real and natural target-language form or a source-backed alternative of the same grammatical and semantic class as the answer. Never invent pseudoforms by changing letters, accents or endings merely to resemble the answer. However, when grammar/form discrimination is the actual taught skill, genuine competing inflections, auxiliaries, agreements or conjugations are valid distractors.

9. CLEAN MCQ STRUCTURE
Return exactly one correct answer plus exactly three distinct distractors. After case/diacritic normalization, all four options must still be distinct. No slash-combined multi-answer options. Options must be comparable in grammatical role, semantic class and specificity; no absurd or visually obvious decoys.

10. PEDAGOGICAL FORMAT BALANCE
Choose the format that best tests each objective: contextual comprehension, practical choice, dialogue/pragmatics, form-function discrimination, grammar application, source-backed contrast or concise completion. Do not use format changes to hide repeated objectives. Variety is a preference, not a reason to invent weaker questions.

11. CANONICAL OBJECTIVE KEY
Every English `why` field MUST begin exactly with `[[OBJ:operation:underlying-target]]`. `operation` must be one of: meaning, contextual-use, grammar, orthography-form, comprehension, contrast, pragmatic-use, pronunciation. `underlying-target` names the transferable learner skill/rule, never an incidental example, noun, verb, numeral, name or scenario.

12. TARGET-LANGUAGE AND CEFR DISCIPLINE
`prompt`, `answer` and all distractors must be natural target-language text appropriate to the requested CEFR level. Do not introduce advanced terminology merely to create variety. Higher-level terminology is still forbidden unless source-backed and genuinely central.

13. COMPACT OUTPUT
Keep prompts concise. After the objective marker, `why` is at most 6 English words and `why_tr` at most 6 Turkish words. `translation_en` and `translation_tr` should normally be at most 12 words. No prose outside JSON. Completeness is more important than decorative wording.

14. FINAL INTERNAL AUDIT
Before returning JSON, inspect every item and silently replace any item that is source-unsupported, outside-knowledge dependent, meta-trivia, a repeated objective, weakly answerable, an answer leak, pseudoform-based, structurally invalid, CEFR-inappropriate or semantically mismatched. Return only the audited candidate set.
"""

        protocol_pattern = r"PEDAGOGIC PROTOCOL & MANDATES:.*?(?=\n\s*RESPONSE FORMAT:)"
        if re.search(protocol_pattern, old_system, flags=re.S):
            old_system = re.sub(protocol_pattern, constitution.strip(), old_system, flags=re.S)
        else:
            old_system = constitution + "\n\n" + old_system

        rewritten[system_idx]["content"] = old_system.replace(
            "Pedagogic Assessment Engine (V5)",
            "Pedagogic Assessment Engine (V7.1)",
            1,
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
                "ONE-PASS QUALITY DIRECTIVE: Plan distinct transferable language objectives before writing. "
                "Use SOURCE MATERIAL only. A question must test language competence, never arithmetic or outside-world knowledge used merely to force an answer. "
                "No meta-linguistic trivia, morphology jargon, cross-language trivia, pseudoforms, answer leaks or cosmetic repeats. "
                "Grammar/form lessons may use genuine competing inflections and auxiliaries. Every `why` starts with [[OBJ:operation:underlying-target]]. Keep JSON compact and complete.\n\n"
                + content
            )
            break

        # ai_engine keeps max_tokens <= 2500 in the same fast (25 s) provider timeout
        # tier. The extra headroom reduces truncated 8/10 or 9/10 JSON batches without
        # moving assessments into the slower timeout tier.
        try:
            kwargs["max_tokens"] = min(int(kwargs.get("max_tokens", 2500)), 2500)
        except Exception:
            kwargs["max_tokens"] = 2500
        try:
            kwargs["temperature"] = min(float(kwargs.get("temperature", 0.30)), 0.30)
        except Exception:
            kwargs["temperature"] = 0.30
        kwargs["allow_fallback"] = False

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_prompt_policy_installed = True
