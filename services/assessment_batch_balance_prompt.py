"""Assessment-only batch balance prompt guard.

Adds one narrow generation directive after V7.4 without changing validators, refill,
history, or lesson/material generation.
"""


def install(ai_engine_module):
    if getattr(ai_engine_module, "_assessment_batch_balance_prompt_installed", False):
        return

    original_call = ai_engine_module._call_ai

    def governed_call(messages, *args, **kwargs):
        if not isinstance(messages, list):
            return original_call(messages, *args, **kwargs)

        rewritten = [dict(m) if isinstance(m, dict) else m for m in messages]
        is_assessment = any(
            isinstance(m, dict)
            and m.get("role") == "system"
            and "Pedagogic Assessment Engine" in str(m.get("content", ""))
            for m in rewritten
        )
        if not is_assessment:
            return original_call(messages, *args, **kwargs)

        directive = (
            "\n\nBATCH BALANCE OVERRIDE: Unless pronunciation or orthography is explicitly the central taught topic, "
            "pronunciation, sound-label, letter-shape and orthography-meta objectives must remain a small minority of the batch "
            "(for batches of 8 or more, no more than two combined). Never repeat the same underlying transferable target within "
            "the same batch, even with different wording, examples, nouns, numerals or contexts. If the source is too narrow to "
            "support enough distinct high-value objectives, prefer contextual meaning/use, agreement, form-function, comprehension "
            "and communicative application before any meta-linguistic trivia. Do not invent extra facts to satisfy this balance."
        )

        for i, m in enumerate(rewritten):
            if isinstance(m, dict) and m.get("role") == "user" and "TASK: Generate EXACTLY" in str(m.get("content", "")):
                rewritten[i]["content"] = str(m.get("content", "")) + directive
                break

        return original_call(rewritten, *args, **kwargs)

    governed_call.__wrapped__ = original_call
    ai_engine_module._call_ai = governed_call
    ai_engine_module._assessment_batch_balance_prompt_installed = True
