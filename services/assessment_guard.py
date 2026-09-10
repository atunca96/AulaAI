"""Semantic diversity guard for AI-generated assessments.

Filters paraphrased duplicates inside the same generated set and across prior
questions, then requests only the missing replacements. This is intentionally
language-agnostic and does not depend on embeddings or extra model calls.
"""

import re
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


def _norm(text):
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text):
    return {
        t for t in _norm(text).split()
        if len(t) >= 3 and t not in _GENERIC_WORDS
    }


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _same_semantic_target(q1, q2):
    """Conservative duplicate detector for paraphrased assessment questions."""
    p1, p2 = _norm(q1.get("prompt")), _norm(q2.get("prompt"))
    a1, a2 = _norm(q1.get("answer")), _norm(q2.get("answer"))
    if not p1 or not p2:
        return False

    # Exact/near-exact prompt duplicates are always duplicates.
    if p1 == p2 or SequenceMatcher(None, p1, p2).ratio() >= 0.88:
        return True

    t1, t2 = _tokens(p1), _tokens(p2)
    overlap = _jaccard(t1, t2)

    # Same target answer + meaningful lexical overlap catches paraphrases such as
    # "hija de mi hermano" vs "tu hermano tiene una hija" without banning the
    # same grammatical form in genuinely unrelated contexts.
    if a1 and a1 == a2:
        if overlap >= 0.26:
            return True
        if len(t1 & t2) >= 2:
            return True

    # Different surface answers can still test the exact same relationship/rule.
    # Require stronger prompt overlap in that case to stay conservative.
    if overlap >= 0.58 and len(t1 & t2) >= 3:
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

        # Only spend additional tokens if semantic filtering actually created a gap.
        # Two small repair rounds are enough to fill normal 10-question assessments
        # while avoiding an infinite generation loop if the source topic is too narrow.
        repair_round = 0
        while len(accepted) < requested and repair_round < 2:
            repair_round += 1
            missing = requested - len(accepted)
            repair_kwargs = dict(kwargs)
            repair_kwargs["count"] = min(requested, missing + 2)
            repair_kwargs["existing_questions"] = prior + accepted + [
                q for q in (first or []) if isinstance(q, dict)
            ]

            # Keep positional callers compatible: remove positional count/existing
            # values before overriding them through kwargs.
            repair_args = list(args)
            if len(repair_args) >= 5:
                repair_args[4] = repair_kwargs.pop("count")
            if len(repair_args) >= 7:
                repair_args[6] = repair_kwargs.pop("existing_questions")

            extra = original(*repair_args, **repair_kwargs)
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
