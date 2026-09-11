"""Assessment-only minimal direct writer.

Calls the current provider wrapper once with a deliberately small pedagogical prompt
and a minimal JSON contract. The requested question count is authoritative: no
oversampling, ranking, semantic repair, or candidate filtering is performed here.
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


def _instruction_language(material_language):
    value = str(material_language or "en").strip().lower()
    if value in {"tr", "turkish", "türkçe", "turkce"}:
        return "Turkish"
    return "English"


def install(ai_engine_module, raw_generate_questions=None):
    if getattr(ai_engine_module, "_assessment_direct_single_pass_experiment", False):
        return

    def direct_generate(*args, **kwargs):
        topic_title = _arg(args, kwargs, "topic_title", 0, "")
        topic_content = _arg(args, kwargs, "topic_content", 2, "")
        language = _arg(args, kwargs, "language", 3, "Target language")
        level = _arg(args, kwargs, "level", 5, "A1")
        source_text_override = _arg(args, kwargs, "source_text_override", 9, None)
        model_override = _arg(args, kwargs, "model_override", 10, None)
        material_language = _arg(args, kwargs, "material_language", 11, "en")
        instruction_language = _instruction_language(material_language)

        try:
            requested = max(1, int(_arg(args, kwargs, "count", 4, 10) or 10))
        except Exception:
            requested = 10

        asked = requested
        source = _source_text(topic_content, source_text_override)

        system = "You are an expert language teacher creating a rigorous, fair CEFR-aligned assessment."

        user = f"""Create a {requested}-question assessment based on the lesson material below for a CEFR {level} {language} class.

The test should accurately measure what students learned and be pedagogically appropriate for their CEFR level. Choose the most important knowledge and skills to assess yourself. Assess different parts of the lesson; do not ask multiple questions that test the same fact or rule in slightly different wording. Distractors should be plausible and appropriate for the class level.

Write the assessment in {instruction_language}, while preserving authentic {language} words, phrases, letters, and forms when they are being tested.

TOPIC: {topic_title}

LESSON MATERIAL:
{source}

Return exactly {requested} multiple-choice questions as JSON.
Each question must contain only:
- prompt
- answer
- exactly 3 distinct distractors

Return this shape:
{{"data":[{{"prompt":"...","answer":"...","distractors":["...","...","..."]}}]}}"""

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
        for q in raw_items[:requested]:
            if not isinstance(q, dict):
                continue
            prompt = str(q.get("prompt", "") or "").strip()
            answer = str(q.get("answer", "") or "").strip()
            distractors = q.get("distractors")
            if not prompt or not answer or not isinstance(distractors, list) or len(distractors) != 3:
                continue

            clean = [str(d or "").strip() for d in distractors]
            if not all(clean):
                continue

            try:
                qid = ai_engine_module._uid()
            except Exception:
                qid = None
            item = {
                "type": "mcq",
                "prompt": prompt,
                "answer": answer,
                "distractors": clean,
                "options": [answer] + clean,
            }
            if qid:
                item["id"] = qid
            public.append(item)

        try:
            print(
                f"[ASSESSMENT-DIRECT-MINIMAL] requested={requested} asked={asked} "
                f"received={len(raw_items)} returned={len(public)} instruction={instruction_language} "
                f"fields=prompt,answer,distractors",
                flush=True,
            )
        except Exception:
            pass
        return public

    ai_engine_module.ai_generate_questions = direct_generate
    ai_engine_module._assessment_direct_single_pass_experiment = True
