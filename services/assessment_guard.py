"""Semantic diversity guard for AI-generated assessments.

Filters paraphrased duplicates inside the same generated set and across prior
questions, then requests only the missing replacements. The detector is
language/CEFR agnostic, Unicode-safe, and does not require embeddings or extra
model calls.
"""

import unicodedata
from difflib import SequenceMatcher


_GENERIC_WORDS = {
    # Spanish framing / glue
    "que", "quien", "quienes", "cual", "cuales", "como", "cuando", "donde",
    "esta", "este", "estas", "estos", "esa", "ese", "esas", "esos", "una", "uno",
    "unos", "unas", "del", "las", "los", "por", "para", "con", "sin", "sobre",
    "entre", "segun", "correcta", "correcto", "opcion", "frase", "completa",
    "selecciona", "indica", "persona", "alguien", "amigo", "amiga", "dice",
    "pregunta", "respuesta", "relacion", "parentesco", "familia", "familiar",
    # English framing / glue
    "what", "which", "who", "whom", "whose", "where", "when", "how", "the",
    "this", "that", "these", "those", "your", "their", "with", "from", "into",
    "correct", "answer", "option", "sentence", "complete", "choose", "select",
    "person", "someone", "friend", "says", "question", "relationship", "family",
    # Turkish framing / glue
    "hangi", "nedir", "kimdir", "nasil", "dogru", "cevap", "secenek", "cumle",
    "tamamla", "sec", "kisi", "birisi", "arkadas", "diyor", "soru", "iliski",
    "aile", "icin", "ile", "olan", "olarak", "sonra", "gore", "kendi",
}

_ANSWER_GLUE = {
    "mi", "mis", "tu", "tus", "su", "sus", "el", "la", "los", "las", "un", "una",
    "es", "son", "my", "your", "his", "her", "their", "the", "a", "an", "is", "are",
    "benim", "senin", "onun", "bir", "bu", "o", "dir", "dır", "dur", "dür",
}


def _norm(text):
    """Normalize while preserving letters/digits from every Unicode script."""
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    chars = []
    for ch in text:
        if unicodedata.combining(ch):
            continue
        chars.append(ch if (ch.isalnum() or ch.isspace()) else " ")
    return " ".join("".join(chars).split())


def _tokens(text, answer=False):
    stop = _ANSWER_GLUE if answer else _GENERIC_WORDS
    return {
        token for token in _norm(text).split()
        if len(token) >= 2 and token not in stop
    }


def _compact(text):
    return "".join(ch for ch in _norm(text) if not ch.isspace())


def _is_dense_script_text(text):
    """Detect text whose lexical boundaries are not reliably represented by spaces."""
    n = _norm(text)
    compact = _compact(n)
    if len(compact) < 4:
        return False
    spaces = n.count(" ")
    # CJK/Hangul/Kana typically have very few spaces relative to visible characters.
    return spaces <= 1 and any(ord(ch) > 0x2E7F for ch in compact)


def _char_ngrams(text, n=3):
    """Script-agnostic fallback for Chinese/Japanese and other no-space text."""
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
    """Use word overlap when useful, otherwise Unicode character n-grams."""
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
    """Conservative duplicate detector for paraphrased assessment questions."""
    p1, p2 = _norm(q1.get("prompt")), _norm(q2.get("prompt"))
    a1, a2 = _norm(q1.get("answer")), _norm(q2.get("answer"))
    if not p1 or not p2:
        return False

    if p1 == p2 or SequenceMatcher(None, p1, p2).ratio() >= 0.88:
        return True

    prompt_overlap = _semantic_overlap(p1, p2)
    answer_overlap = _answer_overlap(a1, a2)
    dense_script = _is_dense_script_text(p1) or _is_dense_script_text(p2)

    # Same/wrapper-equivalent target + meaningful scenario overlap.
    if answer_overlap >= 0.95:
        threshold = 0.15 if dense_script else 0.20
        if prompt_overlap >= threshold:
            return True

    if answer_overlap >= 0.70 and prompt_overlap >= (0.28 if dense_script else 0.34):
        return True

    if prompt_overlap >= (0.56 if dense_script else 0.62):
        return True

    return False


def dedupe_questions(candidates, prior=None, limit=None):
    accepted = []
    references = [q for q in (prior or []) if isinstance(q, dict)]
    for q in candidates or []:
        if not isinstance(q, dict) or not q.get("prompt") or not q.get("answer"):
            continue
        if any(_same_semantic_target(q, old) for old in references + accepted):
            continue
        accepted.append(q)
        if limit and len(accepted) >= limit:
            break
    return accepted


def install(ai_engine_module):
    """Wrap ai_generate_questions once, preserving its public API."""
    if getattr(ai_engine_module, "_semantic_diversity_guard_installed", False):
        return

    original = ai_engine_module.ai_generate_questions

    def guarded_ai_generate_questions(*args, **kwargs):
        requested = kwargs.get("count")
        if requested is None and len(args) >= 5:
            requested = args[4]
        try:
            requested = max(1, int(requested or 10))
        except Exception:
            requested = 10

        prior = kwargs.get("existing_questions")
        if prior is None and len(args) >= 7:
            prior = args[6]
        prior = [q for q in (prior or []) if isinstance(q, dict)]

        first = original(*args, **kwargs)
        accepted = dedupe_questions(first, prior=prior, limit=requested)
        rejected = max(0, len(first or []) - len(accepted))

        repair_round = 0
        seen_generated = [q for q in (first or []) if isinstance(q, dict)]
        while len(accepted) < requested and repair_round < 2:
            repair_round += 1
            missing = requested - len(accepted)
            repair_kwargs = dict(kwargs)
            repair_kwargs["count"] = min(requested, missing + 2)
            repair_kwargs["existing_questions"] = prior + accepted + seen_generated

            repair_args = list(args)
            if len(repair_args) >= 5:
                repair_args[4] = repair_kwargs.pop("count")
            if len(repair_args) >= 7:
                repair_args[6] = repair_kwargs.pop("existing_questions")

            extra = original(*repair_args, **repair_kwargs)
            seen_generated.extend(q for q in (extra or []) if isinstance(q, dict))
            fresh = dedupe_questions(extra, prior=prior + accepted, limit=missing)
            accepted.extend(fresh)

        try:
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(
                    f"[ASSESSMENT-DIVERSITY] requested={requested} first={len(first or [])} "
                    f"semantic_rejected={rejected} final={len(accepted)} repairs={repair_round}\n"
                )
        except Exception:
            pass

        return accepted[:requested]

    ai_engine_module.ai_generate_questions = guarded_ai_generate_questions
    ai_engine_module._semantic_diversity_guard_installed = True
