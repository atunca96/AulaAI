"""Cheap deterministic scorecard for legacy/V2 shadow comparisons.

This is intentionally a proxy layer, not a pedagogical oracle. It uses no LLM or
embedding calls, so it adds no provider latency/cost. Objective validation is a
separate follow-up layer.
"""

import re
import unicodedata
from difflib import SequenceMatcher


def _norm(value):
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    chars = []
    for ch in text:
        if unicodedata.combining(ch):
            continue
        chars.append(ch if (ch.isalnum() or ch.isspace()) else " ")
    return " ".join("".join(chars).split())


def _tokens(value):
    return {t for t in _norm(value).split() if len(t) >= 2}


def _containment(a, b):
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def _question_near_repeat(a, b):
    p1, p2 = _norm(a.get("prompt")), _norm(b.get("prompt"))
    if not p1 or not p2:
        return False
    if p1 == p2 or SequenceMatcher(None, p1, p2).ratio() >= 0.86:
        return True
    a1, a2 = _norm(a.get("answer")), _norm(b.get("answer"))
    return bool(a1 and a1 == a2 and _containment(_tokens(p1), _tokens(p2)) >= 0.42)


def _objective_surface(value):
    text = _norm(value)
    text = re.sub(r"\b\d+\b", " n ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _objective_proxy_repeat(a, b):
    p1, p2 = _objective_surface(a.get("prompt")), _objective_surface(b.get("prompt"))
    if not p1 or not p2:
        return False
    if SequenceMatcher(None, p1, p2).ratio() >= 0.76:
        return True
    return _containment(_tokens(p1), _tokens(p2)) >= 0.72


def _valid_mcq(q):
    if not isinstance(q, dict):
        return False
    prompt = str(q.get("prompt", "")).strip()
    answer = str(q.get("answer", "")).strip()
    ds = [str(x).strip() for x in (q.get("distractors") or []) if str(x).strip()]
    if not prompt or not answer or len(ds) != 3:
        return False
    norms = [_norm(answer)] + [_norm(x) for x in ds]
    return bool(all(norms) and len(set(norms)) == 4)


def _source_grounded_proxy(q, source_text):
    source_n = _norm(source_text)
    if not source_n:
        return None
    answer_n = _norm(q.get("answer"))
    if answer_n and len(answer_n) >= 2 and answer_n in source_n:
        return True
    src = _tokens(source_n)
    ans = {x for x in _tokens(answer_n) if len(x) >= 3}
    if ans and _containment(ans, src) >= 0.5:
        return True
    prompt = {x for x in _tokens(q.get("prompt")) if len(x) >= 4}
    return bool(prompt and _containment(prompt, src) >= 0.18)


_META_MARKERS = (
    "etymology", "etymological", "latin root", "historical root", "letter count",
    "how many letters", "which letter", "diphthong", "phonetic label", "acento grafico",
    "acento gráfico", "cuantas letras", "cuántas letras", "raiz latina", "raíz latina",
    "etimologia", "etimología", "kaç harf", "hangi harf",
)


def _outside_meta_proxy(q):
    p = _norm(q.get("prompt"))
    if not p:
        return False
    if any(_norm(marker) in p for marker in _META_MARKERS):
        return True
    raw = str(q.get("prompt", ""))
    if re.search(r"\b\d+\s*[+×*/]\s*\d+\b", raw):
        return True
    math_markers = ("sumar", "suma", "multiplicar", "multiply", "add", "subtract", "topla", "çarp")
    return any(_norm(m) in p for m in math_markers)


def _pair_rate(questions, fn):
    n = len(questions)
    if n < 2:
        return 0.0
    duplicate_items = set()
    for i in range(n):
        for j in range(i + 1, n):
            if fn(questions[i], questions[j]):
                duplicate_items.add(i)
                duplicate_items.add(j)
    return round(len(duplicate_items) / n, 4)


def build_scorecard(questions, requested_count, source_text=""):
    qs = [q for q in (questions or []) if isinstance(q, dict)]
    requested = max(1, int(requested_count or 1))
    valid_rate = sum(1 for q in qs if _valid_mcq(q)) / requested

    grounding_checks = [_source_grounded_proxy(q, source_text) for q in qs]
    grounding_known = [x for x in grounding_checks if x is not None]
    grounding_rate = (
        round(sum(1 for x in grounding_known if x) / len(grounding_known), 4)
        if grounding_known else None
    )

    question_dup = _pair_rate(qs, _question_near_repeat)
    objective_dup_proxy = _pair_rate(qs, _objective_proxy_repeat)
    outside_meta = round(sum(1 for q in qs if _outside_meta_proxy(q)) / requested, 4)
    count_match = len(qs) == requested

    grounding_component = 1.0 if grounding_rate is None else grounding_rate
    composite = (
        (0.35 if count_match else 0.0)
        + 0.20 * min(1.0, valid_rate)
        + 0.15 * grounding_component
        + 0.15 * (1.0 - min(1.0, question_dup))
        + 0.10 * (1.0 - min(1.0, objective_dup_proxy))
        + 0.05 * (1.0 - min(1.0, outside_meta))
    )

    return {
        "score_version": "shadow_proxy_v1",
        "composite_score": round(composite * 100.0, 2),
        "requested_count_match": count_match,
        "returned_count": len(qs),
        "valid_mcq_rate": round(min(1.0, valid_rate), 4),
        "source_grounding_proxy_rate": grounding_rate,
        "question_duplicate_rate": question_dup,
        "objective_duplicate_proxy_rate": objective_dup_proxy,
        "outside_meta_proxy_rate": outside_meta,
        "hard_gates": {
            "count_match": count_match,
            "valid_structure": valid_rate >= 0.99,
        },
        "manual_calibration_required": True,
        "proxy_warning": "Grounding/objective/meta metrics are deterministic proxies, not final pedagogical validation.",
    }
