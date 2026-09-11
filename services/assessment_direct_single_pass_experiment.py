"""Temporary assessment-only single-pass experiment.

Uses the raw ai_generate_questions function captured before assessment guard/calibration
wrappers are installed. The V7.4 prompt policy still applies at _call_ai level, but no
candidate rejection, diversity filtering, pseudoform rejection, repair, or refill is
performed here. Lesson/material generation is untouched.
"""

import re

_OBJ_RE = re.compile(r"^\s*\[\[OBJ:[^\]]+\]\]\s*", re.I)


def install(ai_engine_module, raw_generate_questions):
    if getattr(ai_engine_module, "_assessment_direct_single_pass_experiment", False):
        return

    def direct_generate(*args, **kwargs):
        try:
            count = kwargs.get("count")
            if count is None and len(args) > 4:
                count = args[4]
            requested = max(1, int(count or 10))
        except Exception:
            requested = 10

        # Direct mode intentionally keeps zero semantic filtering. We only ask Gemini
        # for a little numerical headroom because live runs often return slightly fewer
        # parsed MCQs than requested. The caller still receives at most `requested` items.
        asked = requested + (4 if requested >= 8 else max(3, requested))
        call_args = list(args)
        call_kwargs = dict(kwargs)
        if len(call_args) > 4:
            call_args[4] = asked
            call_kwargs.pop("count", None)
        else:
            call_kwargs["count"] = asked

        questions = raw_generate_questions(*call_args, **call_kwargs) or []
        public = []
        for q in questions:
            if not isinstance(q, dict):
                public.append(q)
                continue
            item = dict(q)
            item["why"] = _OBJ_RE.sub("", str(item.get("why", "") or "")).lstrip(" :-—")
            item.pop("_objective_key", None)
            item.pop("_objective_operation", None)
            item.pop("_objective_target", None)
            public.append(item)

        result = public[:requested]
        try:
            print(
                f"[ASSESSMENT-DIRECT-EXPERIMENT] requested={requested} asked={asked} "
                f"received={len(questions)} returned={len(result)} filters=0 repairs=0",
                flush=True,
            )
        except Exception:
            pass
        return result

    direct_generate.__wrapped__ = raw_generate_questions
    ai_engine_module.ai_generate_questions = direct_generate
    ai_engine_module._assessment_direct_single_pass_experiment = True
