"""Semantic/objective diversity guard for AI-generated assessments only.

Language, CEFR and topic agnostic. Material generation is not involved.
"""

import re
import threading
import unicodedata
from difflib import SequenceMatcher

_TOPIC_HISTORY = {}
_HISTORY_LOCK = threading.Lock()
_HISTORY_LIMIT = 80
_MODEL_HISTORY_LIMIT = 16
_MAX_REPAIR_ROUNDS = 1

_GENERIC_WORDS = {
    "que", "quien", "cual", "como", "cuando", "donde", "esta", "este", "una", "uno",
    "del", "las", "los", "por", "para", "con", "sin", "correcta", "correcto",
    "opcion", "frase", "completa", "selecciona", "indica", "persona", "dice", "pregunta",
    "what", "which", "who", "where", "when", "how", "the", "this", "that", "your",
    "their", "with", "from", "correct", "answer", "option", "sentence", "complete",
    "choose", "select", "person", "says", "question", "hangi", "nedir", "kimdir",
    "nasil", "dogru", "cevap", "secenek", "cumle", "tamamla", "sec", "kisi", "soru",
}

_ANSWER_GLUE = {
    "mi", "mis", "tu", "tus", "su", "sus", "el", "la", "los", "las", "un", "una",
    "es", "son", "my", "your", "his", "her", "their", "the", "a", "an", "is", "are",
    "benim", "senin", "onun", "bir", "bu", "o", "dir", "dır", "dur", "dür",
}

_META_MARKERS = (
    "tilde", "acento grafico", "acento gráfico", "una sola palabra", "en una sola palabra",
    "cuantas letras", "cuántas letras", "que letra", "qué letra", "written as one word",
    "how many letters", "which letter", "has an accent mark", "tek kelime", "kac harf",
    "kaç harf", "hangi harf",
)

_OBJ_RE = re.compile(r"^\s*\[\[OBJ:([^\]]+)\]\]\s*", re.I)


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
    return {t for t in _norm(text).split() if len(t) >= 2 and t not in stop}


def _compact(text):
    return "".join(ch for ch in _norm(text) if not ch.isspace())


def _is_dense_script_text(text):
    n = _norm(text)
    c = _compact(n)
    return len(c) >= 4 and n.count(" ") <= 1 and any(ord(ch) > 0x2E7F for ch in c)


def _ngrams(text, n=3):
    c = _compact(text)
    if not c:
        return set()
    if len(c) <= n:
        return {c}
    return {c[i:i+n] for i in range(len(c) - n + 1)}


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def _containment(a, b):
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def _semantic_overlap(a, b):
    if _is_dense_script_text(a) or _is_dense_script_text(b):
        x, y = _ngrams(a), _ngrams(b)
        return max(_jaccard(x, y), 0.8 * _containment(x, y))
    x, y = _tokens(a), _tokens(b)
    if len(x) >= 2 and len(y) >= 2:
        return max(_jaccard(x, y), 0.8 * _containment(x, y))
    x, y = _ngrams(a), _ngrams(b)
    return max(_jaccard(x, y), 0.8 * _containment(x, y))


def _answer_overlap(a, b):
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    x, y = _tokens(a, answer=True), _tokens(b, answer=True)
    if x and y:
        score = _containment(x, y)
        if score:
            return score
    return _containment(_ngrams(a, 2), _ngrams(b, 2))


def _prepare_question(q):
    if not isinstance(q, dict):
        return q
    why = str(q.get("why", "") or "")
    match = _OBJ_RE.match(why)
    if match:
        key = _norm(match.group(1))
        if key:
            q["_objective_key"] = key
        q["why"] = why[match.end():].lstrip(" :-—")
    return q


def _objective_same(q1, q2):
    k1 = _norm(q1.get("_objective_key", ""))
    k2 = _norm(q2.get("_objective_key", ""))
    if not k1 or not k2:
        return False
    if k1 == k2 or SequenceMatcher(None, k1, k2).ratio() >= 0.92:
        return True
    t1, t2 = set(k1.split()), set(k2.split())
    return len(t1) >= 2 and len(t2) >= 2 and _containment(t1, t2) >= 0.85


def _same_semantic_target(q1, q2):
    if _objective_same(q1, q2):
        return True

    p1, p2 = _norm(q1.get("prompt")), _norm(q2.get("prompt"))
    a1, a2 = _norm(q1.get("answer")), _norm(q2.get("answer"))
    if not p1 or not p2:
        return False
    if p1 == p2 or SequenceMatcher(None, p1, p2).ratio() >= 0.88:
        return True

    prompt_overlap = _semantic_overlap(p1, p2)
    answer_overlap = _answer_overlap(a1, a2)
    dense = _is_dense_script_text(p1) or _is_dense_script_text(p2)
    if answer_overlap >= 0.95 and prompt_overlap >= (0.15 if dense else 0.20):
        return True
    if answer_overlap >= 0.70 and prompt_overlap >= (0.28 if dense else 0.34):
        return True
    return prompt_overlap >= (0.56 if dense else 0.62)


def _is_shallow_meta(q):
    prompt = _norm(q.get("prompt"))
    return bool(prompt) and any(_norm(marker) in prompt for marker in _META_MARKERS)


def dedupe_questions(candidates, prior=None, limit=None):
    accepted = []
    refs = [_prepare_question(q) for q in (prior or []) if isinstance(q, dict)]
    for raw in candidates or []:
        if not isinstance(raw, dict) or not raw.get("prompt") or not raw.get("answer"):
            continue
        q = _prepare_question(raw)
        if _is_shallow_meta(q):
            continue
        if any(_same_semantic_target(q, old) for old in refs + accepted):
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
    return "|".join((
        _norm(_arg(args, kwargs, "language", 3, "")),
        _norm(_arg(args, kwargs, "level", 5, "")),
        _norm(_arg(args, kwargs, "topic_type", 1, "")),
        _norm(_arg(args, kwargs, "topic_title", 0, "")),
    ))


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
                history.append({
                    "prompt": q.get("prompt", ""),
                    "answer": q.get("answer", ""),
                    "_objective_key": q.get("_objective_key", ""),
                })
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
        try:
            requested = max(1, int(_arg(args, kwargs, "count", 4, 10) or 10))
        except Exception:
            requested = 10

        supplied = _arg(args, kwargs, "existing_questions", 6, []) or []
        supplied = [_prepare_question(q) for q in supplied if isinstance(q, dict)]
        key = _history_key(args, kwargs)
        history = _get_history(key)
        full_prior = supplied + history
        model_prior = full_prior[-_MODEL_HISTORY_LIMIT:]

        first_args, first_kwargs = _with_existing(args, kwargs, model_prior)
        first = original(*first_args, **first_kwargs)
        accepted = dedupe_questions(first, prior=full_prior, limit=requested)

        first_count = len(first or [])
        rejected = max(0, first_count - len(accepted))
        objective_missing = sum(
            1 for q in (first or [])
            if isinstance(q, dict) and not _prepare_question(q).get("_objective_key")
        )

        repair_round = 0
        missing = requested - len(accepted)
        # Do not compound a failed/slow upstream call. One small repair is allowed
        # only when the first call produced a mostly complete usable batch.
        if _MAX_REPAIR_ROUNDS and 0 < missing <= 4 and accepted:
            repair_round = 1
            seen = [q for q in (first or []) if isinstance(q, dict)]
            repair_prior = (model_prior + accepted + seen)[-_MODEL_HISTORY_LIMIT:]
            repair_args = list(args)
            repair_kwargs = dict(kwargs)
            repair_count = missing + 2
            if len(repair_args) >= 5:
                repair_args[4] = repair_count
                repair_kwargs.pop("count", None)
            else:
                repair_kwargs["count"] = repair_count
            repair_args, repair_kwargs = _with_existing(repair_args, repair_kwargs, repair_prior)
            extra = original(*repair_args, **repair_kwargs)
            accepted.extend(dedupe_questions(extra, prior=full_prior + accepted, limit=missing))

        accepted = accepted[:requested]
        _remember(key, accepted)

        try:
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(
                    f"[ASSESSMENT-DIVERSITY] requested={requested} first={first_count} "
                    f"rejected={rejected} objective_missing={objective_missing} history={len(history)} "
                    f"final={len(accepted)} repairs={repair_round}\n"
                )
        except Exception:
            pass

        return accepted

    ai_engine_module.ai_generate_questions = guarded_ai_generate_questions
    ai_engine_module._semantic_diversity_guard_installed = True
