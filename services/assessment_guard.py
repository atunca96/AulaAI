"""Lightweight semantic diversity guard for AI-generated assessments.

The guard is language/CEFR/topic agnostic. It keeps a broader local history for
post-generation duplicate filtering, while sending only a small recent window to
the model and allowing at most one repair call. Lesson/material generation is not
involved.
"""

import threading
import unicodedata
from difflib import SequenceMatcher

_GENERIC_WORDS = {
    "que", "quien", "quienes", "cual", "cuales", "como", "cuando", "donde",
    "esta", "este", "estas", "estos", "esa", "ese", "esas", "esos", "una", "uno",
    "unos", "unas", "del", "las", "los", "por", "para", "con", "sin", "sobre",
    "entre", "segun", "correcta", "correcto", "opcion", "frase", "completa",
    "selecciona", "indica", "persona", "alguien", "amigo", "amiga", "dice",
    "pregunta", "respuesta", "relacion", "parentesco", "familia", "familiar",
    "what", "which", "who", "whom", "whose", "where", "when", "how", "the",
    "this", "that", "these", "those", "your", "their", "with", "from", "into",
    "correct", "answer", "option", "sentence", "complete", "choose", "select",
    "person", "someone", "friend", "says", "question", "relationship", "family",
    "hangi", "nedir", "kimdir", "nasil", "dogru", "cevap", "secenek", "cumle",
    "tamamla", "sec", "kisi", "birisi", "arkadas", "diyor", "soru", "iliski",
    "aile", "icin", "ile", "olan", "olarak", "sonra", "gore", "kendi",
}

_ANSWER_GLUE = {
    "mi", "mis", "tu", "tus", "su", "sus", "el", "la", "los", "las", "un", "una",
    "es", "son", "my", "your", "his", "her", "their", "the", "a", "an", "is", "are",
    "benim", "senin", "onun", "bir", "bu", "o", "dir", "dır", "dur", "dür",
}

_TOPIC_HISTORY = {}
_HISTORY_LOCK = threading.Lock()
_HISTORY_LIMIT = 80
_MODEL_HISTORY_LIMIT = 24
_MAX_REPAIR_ROUNDS = 1

_META_MARKERS = (
    "tilde", "acento grafico", "acento gráfico", "una sola palabra", "en una sola palabra",
    "cuantas letras", "cuántas letras", "que letra", "qué letra", "como se escribe correctamente",
    "cómo se escribe correctamente", "written as one word", "how many letters", "which letter",
    "has an accent mark", "tek kelime", "kac harf", "kaç harf", "hangi harf",
)


def _norm(text):
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    chars = []
    for ch in text:
        if unicodedata.combining(ch):
            continue
        chars.append(ch if (ch.isalnum() or ch.isspace()) else " ")
    return " ".join("".join(chars).split())


def _tokens(text, answer=False):
    stop = _ANSWER_GLUE if answer else _GENERIC_WORDS
    return {token for token in _norm(text).split() if len(token) >= 2 and token not in stop}


def _compact(text):
    return "".join(ch for ch in _norm(text) if not ch.isspace())


def _is_dense_script_text(text):
    n = _norm(text)
    compact = _compact(n)
    if len(compact) < 4:
        return False
    return n.count(" ") <= 1 and any(ord(ch) > 0x2E7F for ch in compact)


def _char_ngrams(text, n=3):
    compact = _compact(text)
    if not compact:
        return set()
    if len(compact) <= n:
        return {compact}
    return {compact[i:i+n] for i in range(len(compact) - n + 1)}


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _containment(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _semantic_overlap(text1, text2):
    if _is_dense_script_text(text1) or _is_dense_script_text(text2):
        g1, g2 = _char_ngrams(text1), _char_ngrams(text2)
        return max(_jaccard(g1, g2), 0.8 * _containment(g1, g2))
    t1, t2 = _tokens(text1), _tokens(text2)
    if len(t1) >= 2 and len(t2) >= 2:
        return max(_jaccard(t1, t2), 0.8 * _containment(t1, t2))
    g1, g2 = _char_ngrams(text1), _char_ngrams(text2)
    return max(_jaccard(g1, g2), 0.8 * _containment(g1, g2))


def _answer_overlap(answer1, answer2):
    a1, a2 = _norm(answer1), _norm(answer2)
    if not a1 or not a2:
        return 0.0
    if a1 == a2:
        return 1.0
    t1, t2 = _tokens(a1, answer=True), _tokens(a2, answer=True)
    if t1 and t2:
        overlap = _containment(t1, t2)
        if overlap:
            return overlap
    return _containment(_char_ngrams(a1, 2), _char_ngrams(a2, 2))


def _same_semantic_target(q1, q2):
    p1, p2 = _norm(q1.get("prompt")), _norm(q2.get("prompt"))
    a1, a2 = _norm(q1.get("answer")), _norm(q2.get("answer"))
    if not p1 or not p2:
        return False
    if p1 == p2 or SequenceMatcher(None, p1, p2).ratio() >= 0.88:
        return True

    prompt_overlap = _semantic_overlap(p1, p2)
    answer_overlap = _answer_overlap(a1, a2)
    dense_script = _is_dense_script_text(p1) or _is_dense_script_text(p2)

    if answer_overlap >= 0.95 and prompt_overlap >= (0.15 if dense_script else 0.20):
        return True
    if answer_overlap >= 0.70 and prompt_overlap >= (0.28 if dense_script else 0.34):
        return True
    if prompt_overlap >= (0.56 if dense_script else 0.62):
        return True
    return False


def _is_shallow_meta_question(q):
    prompt = _norm(q.get("prompt"))
    return bool(prompt) and any(_norm(marker) in prompt for marker in _META_MARKERS)


def dedupe_questions(candidates, prior=None, limit=None):
    accepted = []
    references = [q for q in (prior or []) if isinstance(q, dict)]
    for q in candidates or []:
        if not isinstance(q, dict) or not q.get("prompt") or not q.get("answer"):
            continue
        if _is_shallow_meta_question(q):
            continue
        if any(_same_semantic_target(q, old) for old in references + accepted):
            continue
        accepted.append(q)
        if limit and len(accepted) >= limit:
            break
    return accepted


def _arg(args, kwargs, name, index, default=None):
    if name in kwargs:
        return kwargs[name]
    if len(args) > index:
        return args[index]
    return default


def _history_key(args, kwargs):
    topic_title = _norm(_arg(args, kwargs, "topic_title", 0, ""))
    topic_type = _norm(_arg(args, kwargs, "topic_type", 1, ""))
    language = _norm(_arg(args, kwargs, "language", 3, ""))
    level = _norm(_arg(args, kwargs, "level", 5, ""))
    return "|".join((language, level, topic_type, topic_title))


def _get_history(key):
    if not key:
        return []
    with _HISTORY_LOCK:
        return list(_TOPIC_HISTORY.get(key, []))


def _remember(key, questions):
    if not key:
        return
    with _HISTORY_LOCK:
        history = _TOPIC_HISTORY.setdefault(key, [])
        for q in questions or []:
            if isinstance(q, dict) and q.get("prompt") and q.get("answer"):
                history.append({"prompt": q.get("prompt", ""), "answer": q.get("answer", "")})
        if len(history) > _HISTORY_LIMIT:
            del history[:-_HISTORY_LIMIT]


def _with_existing(args, kwargs, existing):
    call_args = list(args)
    call_kwargs = dict(kwargs)
    if len(call_args) >= 7:
        call_args[6] = existing
        call_kwargs.pop("existing_questions", None)
    else:
        call_kwargs["existing_questions"] = existing
    return call_args, call_kwargs


def install(ai_engine_module):
    if getattr(ai_engine_module, "_semantic_diversity_guard_installed", False):
        return

    original = ai_engine_module.ai_generate_questions

    def guarded_ai_generate_questions(*args, **kwargs):
        requested = _arg(args, kwargs, "count", 4, 10)
        try:
            requested = max(1, int(requested or 10))
        except Exception:
            requested = 10

        supplied_prior = _arg(args, kwargs, "existing_questions", 6, []) or []
        supplied_prior = [q for q in supplied_prior if isinstance(q, dict)]
        h_key = _history_key(args, kwargs)
        history = _get_history(h_key)

        # Full history is used locally for filtering, but only a compact recent window
        # goes into the LLM prompt. This prevents regeneration from getting slower as
        # the session grows.
        full_prior = supplied_prior + history
        model_prior = full_prior[-_MODEL_HISTORY_LIMIT:]
        first_args, first_kwargs = _with_existing(args, kwargs, model_prior)

        first = original(*first_args, **first_kwargs)
        accepted = dedupe_questions(first, prior=full_prior, limit=requested)
        rejected = max(0, len(first or []) - len(accepted))

        repair_round = 0
        if len(accepted) < requested and _MAX_REPAIR_ROUNDS:
            repair_round = 1
            missing = requested - len(accepted)
            seen_generated = [q for q in (first or []) if isinstance(q, dict)]
            repair_prior = (model_prior + accepted + seen_generated)[-_MODEL_HISTORY_LIMIT:]

            repair_kwargs = dict(kwargs)
            repair_kwargs["count"] = min(requested, missing + 3)
            repair_args = list(args)
            if len(repair_args) >= 5:
                repair_args[4] = repair_kwargs.pop("count")
            repair_args, repair_kwargs = _with_existing(repair_args, repair_kwargs, repair_prior)

            extra = original(*repair_args, **repair_kwargs)
            fresh = dedupe_questions(extra, prior=full_prior + accepted, limit=missing)
            accepted.extend(fresh)

        _remember(h_key, accepted)

        try:
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(
                    f"[ASSESSMENT-DIVERSITY] requested={requested} first={len(first or [])} "
                    f"rejected={rejected} history={len(history)} model_history={len(model_prior)} "
                    f"final={len(accepted)} repairs={repair_round}\n"
                )
        except Exception:
            pass

        return accepted[:requested]

    ai_engine_module.ai_generate_questions = guarded_ai_generate_questions
    ai_engine_module._semantic_diversity_guard_installed = True
