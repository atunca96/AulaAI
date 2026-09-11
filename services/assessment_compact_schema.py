"""Assessment-only compact output schema for the direct-mode experiment.

Removes prompt translation fields from assessment provider instructions. Lesson/material
calls are untouched.
"""

import re


def install(ai_engine_module):
    if getattr(ai_engine_module, "_assessment_compact_schema_installed", False):
        return

    original_call = ai_engine_module._call_ai

    def compact_call(messages, *args, **kwargs):
        if not isinstance(messages, list):
            return original_call(messages, *args, **kwargs)

        is_assessment = any(
            isinstance(m, dict)
            and m.get("role") == "system"
            and "Pedagogic Assessment Engine" in str(m.get("content", ""))
            for m in messages
        )
        if not is_assessment:
            return original_call(messages, *args, **kwargs)

        rewritten = []
        for m in messages:
            if not isinstance(m, dict):
                rewritten.append(m)
                continue

            item = dict(m)
            text = str(item.get("content", ""))

            # Remove the legacy dual-translation mandate as one block when present.
            text = re.sub(
                r"\n\s*2\. DUAL TRANSLATION & BLANK PRESERVATION MANDATE \(CRITICAL\):.*?(?=\n\s*3\. STRICT ANTI-GIVEAWAY MANDATE:)",
                "\n",
                text,
                flags=re.S,
            )

            # Remove remaining schema/directive lines that request bilingual prompt translations.
            lines = []
            for line in text.splitlines():
                low = line.lower()
                if "translation_en" in low or "translation_tr" in low:
                    continue
                if "blank translation rule" in low:
                    continue
                lines.append(line)
            text = "\n".join(lines)

            if item.get("role") == "user" and "TASK: Generate EXACTLY" in text:
                text = (
                    "COMPACT OUTPUT OVERRIDE: Do not output `translation`, `translation_en`, or `translation_tr`. "
                    "Each MCQ object should contain only the fields needed for assessment: `type`, `prompt`, `answer`, "
                    "`distractors`, `why`, and `why_tr`. Keep `why`/`why_tr` concise.\n\n"
                    + text
                )

            item["content"] = text
            rewritten.append(item)

        return original_call(rewritten, *args, **kwargs)

    ai_engine_module._call_ai = compact_call
    ai_engine_module._assessment_compact_schema_installed = True
