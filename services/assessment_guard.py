"""Semantic diversity guard for AI-generated assessments.

Filters paraphrased duplicates inside the same generated set and across prior
questions, requests only missing replacements, and prevents one exercise archetype
from dominating an assessment. The detector is language/CEFR agnostic, Unicode-safe,
and does not require embeddings or extra model calls.
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
_HISTORY_LIMIT = 120

_META_MARKERS = (
    "tilde", "acento grafico", "acento gráfico", "se escribe como una sola palabra",
    "cuantas letras", "cuántas letras", "que letra", "qué letra",
    "written as one word", "how many letters", "which letter", "has an accent mark",
    "tek kelime olarak yaz", "kac harf", "kaç harf", "hangi harf",
)

# Broad multilingual calculation cues. They are used only to cap over-representation,
# not to reject calculation questions entirely. This keeps number lessons linguistic
# rather than turning them into math worksheets.
_CALC_MARKERS = (
    # Spanish / Portuguese / Italian / French
    "resultado de", "sumar", "suma", "restar", "resta", "menos", "doble de",
    "multiplicado", "multiplicar", "cuanto pagas", "cuánto pagas", "cuanto dinero",
    "cuánto dinero", "cuantos hay en total", "cuántos hay en total", "cuantos quedan",
    "cuántos quedan", "mais", "somar", "subtrair", "dobro de", "moltiplicato",
    "sottrarre", "doppio di", "additionner", "soustraire", "double de", "multiplie",
    # English / German / Dutch
    "result of", "plus", "minus", "add ", "sum of", "subtract", "double of",
    "multiplied", "how much do you pay", "how many are left", "addieren", "subtrahieren",
    "summe", "doppelte", "multipliziert", "optellen", "aftrekken", "verdubbelen",
    # Turkish
    "toplarsan", "toplam", "arti", "artı", "eksi", "cikar", "çıkar", "iki kati",
    "iki katı", "carpi", "çarpı", "carp", "çarp", "ne kadar odersin", "ne kadar ödersin",
    # Russian / Polish / Greek
    "плюс", "минус", "слож", "выч", "удво", "умнож", "suma", "dodaj", "odejm",
    "podwo", "pomno", "συν", "μειον", "μείον", "αθροισ", "προσθε", "αφαιρε", "αφαίρε",
    "διπλα", "διπλά", "πολλαπλα",
    # Arabic / Persian
    "زائد", "ناقص", "مجموع", "اطرح", "ضعف", "ضرب", "جمع", "منهای",
    # Japanese / Chinese / Korean
    "足す", "たす", "引く", "ひく", "合計", "倍", "掛け", "かけ", "加", "减", "減",
    "总共", "總共", "两倍", "兩倍", "乘", "더하", "빼", "합계", "두 배", "곱하",
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
        containment = _containment(t1, t2)
        if containment:
            return containment
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


def _is_calculation_question(q):
    prompt = _norm(q.get("prompt"))
    if not prompt:
        return False
    return any(_norm(marker) in prompt for marker in _CALC_MARKERS)


def dedupe_questions(candidates, prior=None, limit=None, max_calculations=None, batch_seed=None):
    accepted = list(batch_seed or [])
    seed_count = len(accepted)
    references = [q for q in (prior or []) if isinstance(q, dict)]
    calc_count = sum(1 for q in accepted if _is_calculation_question(q))

    for q in candidates or []:
        if not isinstance(q, dict) or not q.get("prompt") or not q.get("answer"):
            continue
        if _is_shallow_meta_question(q):
            continue
        if max_calculations is not None and _is_calculation_question(q) and calc_count >= max_calculations:
            continue
        if any(_same_semantic_target(q, old) for old in references + accepted):
            continue
        accepted.append(q)
        if _is_calculation_question(q):
            calc_count += 1
        if limit and len(accepted) >= limit:
            break

    return accepted[seed_count:] if batch_seed else accepted


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

        # For a normal 10-question assessment, at most three questions may be
        # primarily arithmetic. Scale gently for other requested sizes.
        max_calculations = max(1, min(3, round(requested * 0.30))) if requested > 1 else 1

        supplied_prior = _arg(args, kwargs, "existing_questions", 6, []) or []
        supplied_prior = [q for q in supplied_prior if isinstance(q, dict)]
        h_key = _history_key(args, kwargs)
        history = _get_history(h_key)
        prior = supplied_prior + history

        first_kwargs = dict(kwargs)
        first_args = list(args)
        if len(first_args) >= 7:
            first_args[6] = prior
            first_kwargs.pop("existing_questions", None)
        else:
            first_kwargs["existing_questions"] = prior

        first = original(*first_args, **first_kwargs)
        accepted = dedupe_questions(
            first, prior=prior, limit=requested, max_calculations=max_calculations
        )
        rejected = max(0, len(first or []) - len(accepted))

        repair_round = 0
        seen_generated = [q for q in (first or []) if isinstance(q, dict)]
        while len(accepted) < requested and repair_round < 3:
            repair_round += 1
            missing = requested - len(accepted)
            repair_kwargs = dict(kwargs)
            repair_kwargs["count"] = min(requested, missing + 4)
            repair_kwargs["existing_questions"] = prior + accepted + seen_generated
            repair_args = list(args)
            if len(repair_args) >= 5:
                repair_args[4] = repair_kwargs.pop("count")
            if len(repair_args) >= 7:
                repair_args[6] = repair_kwargs.pop("existing_questions")

            extra = original(*repair_args, **repair_kwargs)
            seen_generated.extend(q for q in (extra or []) if isinstance(q, dict))
            fresh = dedupe_questions(
                extra,
                prior=prior + accepted,
                limit=missing,
                max_calculations=max_calculations,
                batch_seed=accepted,
            )
            accepted.extend(fresh)

        _remember(h_key, accepted)

        try:
            with open("pipeline.log", "a", encoding="utf-8") as f:
                calc_total = sum(1 for q in accepted if _is_calculation_question(q))
                f.write(
                    f"[ASSESSMENT-DIVERSITY] requested={requested} first={len(first or [])} "
                    f"semantic_or_quality_rejected={rejected} history={len(history)} "
                    f"calculations={calc_total} final={len(accepted)} repairs={repair_round}\n"
                )
        except Exception:
            pass

        return accepted[:requested]

    ai_engine_module.ai_generate_questions = guarded_ai_generate_questions
    ai_engine_module._semantic_diversity_guard_installed = True
