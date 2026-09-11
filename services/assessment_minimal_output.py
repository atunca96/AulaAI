"""Assessment-only minimal output schema for the direct single-pass experiment.

Runs inside the assessment prompt-policy wrapper, so it sees the fully governed
assessment prompt immediately before the provider call. Lesson/material calls are
left untouched.
"""

import re


def install(ai_engine_module):
    if getattr(ai_engine_module, "_assessment_minimal_output_installed", False):
        return

    original_call = ai_engine_module._call_ai

    def minimal_call(messages, *args, **kwargs):
        if not isinstance(messages, list) or not messages:
            return original_call(messages, *args, **kwargs)

        is_assessment = any(
            isinstance(m, dict)
            and m.get("role") == "system"
            and "Pedagogic Assessment Engine" in str(m.get("content", ""))
            for m in messages
        )
        if not is_assessment:
            return original_call(messages, *args, **kwargs)

        rewritten = [dict(m) if isinstance(m, dict) else m for m in messages]

        for m in rewritten:
            if not isinstance(m, dict):
                continue
            content = str(m.get("content", ""))

            if m.get("role") == "system":
                content = re.sub(
                    r"\n17\. CANONICAL OBJECTIVE KEY.*?(?=\n18\.)",
                    "\n",
                    content,
                    flags=re.S,
                )
                content = content.replace(
                    "After the objective marker, `why` is at most 6 English words and `why_tr` at most 6 Turkish words. `translation_en` and `translation_tr` should normally be at most 12 words. ",
                    "",
                )
                content += (
                    "\n\nDIRECT MINIMAL OUTPUT OVERRIDE — HIGHEST PRIORITY:\n"
                    "Return only the fields needed for the MCQ itself. Each item must contain exactly: "
                    "type, prompt, answer, distractors. Do not generate translation, translation_en, "
                    "translation_tr, why, why_tr, objective keys, explanations, rationales, metadata, "
                    "or any other per-question fields. Keep all quality rules above, but perform all "
                    "reasoning/auditing silently."
                )

            elif m.get("role") == "user" and "JSON STRUCTURE:" in content:
                content = re.sub(
                    r"JSON STRUCTURE:.*?(?=\n\s*CRITICAL MANDATES:)",
                    "JSON STRUCTURE:\n"
                    "{\n"
                    "  \"data\": [\n"
                    "    {\n"
                    "      \"type\": \"mcq\",\n"
                    "      \"prompt\": \"Question in the target language\",\n"
                    "      \"answer\": \"Correct answer in the target language\",\n"
                    "      \"distractors\": [\"Distractor 1\", \"Distractor 2\", \"Distractor 3\"]\n"
                    "    }\n"
                    "  ]\n"
                    "}\n",
                    content,
                    flags=re.S,
                )
                content = re.sub(
                    r"\n\s*4\) BLANK TRANSLATION RULE:.*?(?=\n\n|$)",
                    "",
                    content,
                    flags=re.S,
                )
                content += (
                    "\n\nMINIMAL OUTPUT: Do not output translations, explanations, why fields, objective "
                    "markers, rationales, or metadata. Output only type, prompt, answer, distractors."
                )

            m["content"] = content

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = minimal_call
    ai_engine_module._assessment_minimal_output_installed = True
