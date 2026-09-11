"""Temporary assessment-only minimal direct writer.

Bypasses the legacy ai_generate_questions implementation entirely. It calls the current
provider wrapper directly with a compact assessment prompt and a minimal JSON schema.
Lesson/material generation is untouched.
"""

import json


def _arg(args, kwargs, name, index, default=None):
    if name in kwargs:
        return kwargs.get(name)
    if len(args) > index:
        return args[index]
    return default


def _source_text(topic_content, source_text_override):
    if source_text_override:
        return str(source_text_override)[:8000]
    if isinstance(topic_content, dict):
        try:
            return json.dumps(topic_content, ensure_ascii=False)[:8000]
        except Exception:
            return str(topic_content)[:8000]
    return str(topic_content or "")[:8000]


def install(ai_engine_module, raw_generate_questions=None):
    if getattr(ai_engine_module, "_assessment_direct_single_pass_experiment", False):
        return

    def direct_generate(*args, **kwargs):
        topic_title = _arg(args, kwargs, "topic_title", 0, "")
        topic_type = _arg(args, kwargs, "topic_type", 1, "mixed")
        topic_content = _arg(args, kwargs, "topic_content", 2, "")
        language = _arg(args, kwargs, "language", 3, "Target language")
        level = _arg(args, kwargs, "level", 5, "A1")
        existing_questions = _arg(args, kwargs, "existing_questions", 6, None) or []
        source_text_override = _arg(args, kwargs, "source_text_override", 9, None)
        model_override = _arg(args, kwargs, "model_override", 10, None)

        try:
            requested = max(1, int(_arg(args, kwargs, "count", 4, 10) or 10))
        except Exception:
            requested = 10

        # Numerical headroom only; no semantic candidate filtering/ranking.
        asked = requested + (4 if requested >= 8 else max(3, requested))

        source = _source_text(topic_content, source_text_override)
        recent = []
        for q in existing_questions[:20]:
            if isinstance(q, dict) and q.get("prompt"):
                recent.append(str(q.get("prompt"))[:240])
        recent_block = "\n".join(f"- {p}" for p in recent)

        system = f"""You are a {language} assessment writer for CEFR {level}.
Create natural, source-grounded multiple-choice questions for the taught competence.
Use only the supplied source for tested facts/rules. Keep prompts and all options in {language}.
Each question must have exactly one correct answer and exactly three distinct plausible distractors.
Distractors must be realistic learner confusions, not absurd filler or broken pseudoforms.
Keep stem and options aligned, CEFR-appropriate, concise, and unambiguous.
Avoid arithmetic/general-knowledge proxies, meta-linguistic trivia, answer leaks, cosmetic repeats,
and repeated underlying objectives when the source supports variety. For speaking/functional content,
prefer authentic situations and natural responses. For grammar, use genuine competing forms.
For vocabulary, use nearby semantic alternatives. Silently audit quality before returning.
Return JSON only. Do not output translations, explanations, why fields, rationales, objective keys,
metadata, commentary, or any fields other than prompt, answer, and distractors."""

        user = f"""Generate EXACTLY {asked} unique {topic_type} MCQs.
TOPIC: {topic_title}
LEVEL: {level}
SOURCE MATERIAL:
{source}

AVOID REPEATING THESE RECENT PROMPTS WHEN POSSIBLE:
{recent_block or '- none'}

Return exactly this compact shape:
{{
  "data": [
    {{
      "prompt": "question in {language}",
      "answer": "correct answer in {language}",
      "distractors": ["wrong option 1", "wrong option 2", "wrong option 3"]
    }}
  ]
}}"""

        target_model = model_override or getattr(ai_engine_module, "MODEL_STRUCTURAL", None)
        if target_model and str(target_model).lower() in {"none", "offline", "skip", "disabled"}:
            data = None
        else:
            data = ai_engine_module._call_ai(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                model=target_model,
                max_tokens=10000,
                temperature=0.30,
                json_mode=True,
                allow_fallback=False,
            )

        raw_items = []
        if isinstance(data, dict):
            raw_items = data.get("data") or data.get("questions") or data.get("items") or []
        elif isinstance(data, list):
            raw_items = data

        public = []
        for q in raw_items:
            if not isinstance(q, dict):
                continue
            prompt = str(q.get("prompt", "") or "").strip()
            answer = str(q.get("answer", "") or "").strip()
            distractors = q.get("distractors")
            if not prompt or not answer or not isinstance(distractors, list):
                continue
            clean = []
            for d in distractors:
                text = str(d or "").strip()
                if text and text.casefold() != answer.casefold() and text.casefold() not in {x.casefold() for x in clean}:
                    clean.append(text)
                if len(clean) == 3:
                    break
            if len(clean) != 3:
                continue
            options = [answer] + clean
            try:
                qid = ai_engine_module._uid()
            except Exception:
                qid = None
            item = {
                "type": "mcq",
                "prompt": prompt,
                "answer": answer,
                "distractors": clean,
                "options": options,
            }
            if qid:
                item["id"] = qid
            public.append(item)
            if len(public) >= requested:
                break

        try:
            print(
                f"[ASSESSMENT-DIRECT-MINIMAL] requested={requested} asked={asked} "
                f"received={len(raw_items)} returned={len(public)} fields=prompt,answer,distractors",
                flush=True,
            )
        except Exception:
            pass
        return public

    ai_engine_module.ai_generate_questions = direct_generate
    ai_engine_module._assessment_direct_single_pass_experiment = True
