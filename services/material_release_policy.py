from copy import deepcopy
import re
import unicodedata


_TR_META_REPLACEMENTS = (
    (r"\bzero[- ]copula\b", "sıfır bağlayıcı"),
    (r"\bnominatif\b", "Yalın Hâl"),
    (r"\bgenitif\b", "İlgi/Tamlayan Hâli"),
)

_ENGLISH_OPTION_MARKERS = {
    "plural", "singular", "masculine", "feminine", "neuter", "only",
    "unstressed", "stressed", "sound", "rounded", "unrounded", "front",
    "back", "close", "open", "mid", "full", "like", "formal", "informal",
}

# One-letter transliterations used only to repair a mixed Latin+Cyrillic token
# inside a Turkish learner-facing field. Pure Cyrillic target-language tokens
# are never transliterated by this table.
_CYR_TO_LATIN_SAFE = {
    "а": "a", "А": "A", "б": "b", "Б": "B", "в": "v", "В": "V",
    "г": "g", "Г": "G", "д": "d", "Д": "D", "е": "e", "Е": "E",
    "з": "z", "З": "Z", "и": "i", "И": "I", "к": "k", "К": "K",
    "л": "l", "Л": "L", "м": "m", "М": "M", "н": "n", "Н": "N",
    "о": "o", "О": "O", "п": "p", "П": "P", "р": "r", "Р": "R",
    "с": "s", "С": "S", "т": "t", "Т": "T", "у": "u", "У": "U",
    "ф": "f", "Ф": "F",
}

_TR_INSTRUCTIONAL_KEYS = {
    "title_tr", "text_tr", "explanation_tr", "example_tr", "rule_tr",
    "analysis_tr", "context_tr", "note_tr", "pitfall_tr", "translation_tr",
    "prompt_tr", "question_tr", "stem_tr", "line_tr", "speaker_tr",
    "meaning_tr", "definition_tr", "breakdown_tr",
}


def _fold(value):
    text = unicodedata.normalize("NFD", str(value or "")).casefold()
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("ı", "i")


def _is_russian(language):
    folded = _fold(language)
    return any(x in folded for x in ("russian", "rusca", "рус"))


def _has_non_latin(text):
    return any(ch.isalpha() and "LATIN" not in unicodedata.name(ch, "") for ch in str(text or ""))


def _clean_option(value):
    text = str(value or "").strip()
    match = re.search(r"\s*\(([^()]*)\)\s*$", text)
    if not match:
        return text
    core = text[:match.start()].rstrip()
    words = {w.casefold() for w in re.findall(r"[A-Za-z]+", match.group(1))}
    ipa_core = bool(re.fullmatch(r"\[[^\]]+\]", core))
    if (words & _ENGLISH_OPTION_MARKERS) and (_has_non_latin(core) or ipa_core):
        return core
    return text


def _clean_comparison_target(value):
    text = str(value or "")
    if not _has_non_latin(text):
        return text
    # Remove only an orphan ASCII learner-respelling token at the very end.
    # IPA contrasts containing two or more bracket groups remain untouched.
    groups = re.findall(r"\[[^\]\n]+\]", text)
    if len(groups) >= 2:
        return text
    return re.sub(r"\s*\[[A-Za-z]{2,16}\](?=\s*[?!.,;:]|\s*$)", "", text)


def _repair_mixed_latin_cyrillic_tokens(text):
    if not isinstance(text, str) or not text:
        return text

    def repl(match):
        token = match.group(0)
        has_latin = any(ch.isalpha() and "LATIN" in unicodedata.name(ch, "") for ch in token)
        has_cyr = any(ch.isalpha() and "CYRILLIC" in unicodedata.name(ch, "") for ch in token)
        if not (has_latin and has_cyr):
            return token
        out = []
        for ch in token:
            if "CYRILLIC" in unicodedata.name(ch, ""):
                mapped = _CYR_TO_LATIN_SAFE.get(ch)
                if mapped is None:
                    return token
                out.append(mapped)
            else:
                out.append(ch)
        repaired = "".join(out)
        if all((not ch.isalpha()) or "LATIN" in unicodedata.name(ch, "") for ch in repaired):
            return repaired
        return token

    return re.sub(r"[^\W\d_]+", repl, text, flags=re.UNICODE)


def _clean_turkish_instructional(value):
    text = _repair_mixed_latin_cyrillic_tokens(str(value or ""))
    for pattern, replacement in _TR_META_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _prompt(page):
    for key in ("prompt_tr", "question_tr", "stem_tr", "prompt", "question", "stem", "text_tr", "text"):
        value = page.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _explanation(page):
    parts = []
    for key in ("explanation_tr", "analysis_tr", "explanation", "analysis"):
        value = page.get(key)
        if value:
            parts.append(str(value))
    return " ".join(parts)


def _options(page):
    value = page.get("options") or page.get("choices") or []
    return [str(x or "") for x in value] if isinstance(value, list) else []


def _looks_like_mcq(page):
    if not isinstance(page, dict):
        return False
    kind = str(page.get("type") or "").strip().casefold()
    return kind == "mcq" or (len(_options(page)) >= 2 and bool(_prompt(page)))


def _has_explicit_gender_cue(prompt_folded):
    cues = (
        "disil", "eril", "kadin", "erkek", "kiz", "oglan", "anne", "baba", "abla", "agabey",
        "female", "male", "woman", "man", "girl", "boy", "mother", "father", "sister", "brother",
        "женщ", "мужчин", "девуш", "мальчик", "мать", "отец", "сест", "брат",
    )
    return any(cue in prompt_folded for cue in cues)


def _unsafe_identity_inference(page):
    p = _fold(_prompt(page))
    e = _fold(_explanation(page))
    opts = _fold(" ".join(_options(page)))

    # If the rationale itself says the answer follows from grammatical/biological
    # gender but the learner-facing stem does not state a gender cue, the item is
    # ambiguous (e.g. a personal name used as the only cue). Crop it.
    gender_reason = any(x in e for x in (
        "ozne disil", "ozne eril", "disil isim", "eril isim", "female name", "male name",
        "name is feminine", "name is masculine", "woman's name", "man's name",
    ))
    if gender_reason and not _has_explicit_gender_cue(p):
        return True

    workplace_fact = any(x in p for x in (
        "calisiyor", "calisir", "works at", "works in", "working at", "working in",
        "arbeitet", "travaille", "trabaja", "lavora", "trabalha", "работает", "работа в",
    ))
    profession_answer = any(x in (p + " " + e) for x in (
        "meslegi", "meslek", "profession", "occupation", "job is", "beruf", "професс", "кем он", "кем она",
    ))
    if workplace_fact and profession_answer:
        return True

    location_fact = any(x in p for x in (
        "dogdu", "dogmus", "yasiyor", "ikamet", "born in", "lives in", "resides in",
        "nacio", "nacio", "vive en", "родил", "живет в", "живёт в",
    ))
    identity_answer = any(x in (p + " " + e) for x in (
        "milliyet", "uyruk", "nationality", "vatandas", "citizen", "native speaker",
        "anadili", "language ability", "националь", "граждан",
    ))
    if location_fact and identity_answer:
        return True

    trait_fact = any(x in p for x in ("dakik", "punctual", "punktlich", "ponctuel", "puntual", "пунктуал"))
    absolute = any(x in opts for x in ("never", "always", "niemals", "immer", "jamais", "toujours", "nunca", "siempre", "никогда", "всегда"))
    if trait_fact and absolute:
        return True

    return False


def _invalid_russian_option(option):
    # High-confidence modern Russian spelling impossibilities from the standard
    # seven-letter rule. If one appears in an MCQ, crop the whole item instead of
    # publishing a fabricated nonword distractor.
    text = str(option or "").casefold()
    return bool(re.search(r"[гкхжчшщ]ы", text))


def _unsafe_mcq(page, language):
    if not _looks_like_mcq(page):
        return False
    if _unsafe_identity_inference(page):
        return True
    if _is_russian(language) and any(_invalid_russian_option(x) for x in _options(page)):
        return True
    return False


def _normalize_russian_grapheme_item(item, language):
    if not (_is_russian(language) and isinstance(item, dict)):
        return item
    term = str(item.get("term") or item.get("word") or "").strip()
    letters = re.sub(r"\s+", "", term).casefold()
    if letters in {"ч", "чч"}:
        item["phonetic"] = "[t͡ɕ]"
    elif letters in {"щ", "щщ"}:
        item["phonetic"] = "[ɕː]"
    elif letters in {"ъ", "ъъ", "ь", "ьь"}:
        item["phonetic"] = ""
    return item


def _walk(node, language="", parent_key=""):
    if isinstance(node, list):
        out = []
        for item in node:
            if isinstance(item, dict) and _unsafe_mcq(item, language):
                continue
            out.append(_walk(item, language, parent_key))
        return out
    if not isinstance(node, dict):
        return node

    if _unsafe_mcq(node, language):
        return None

    out = {}
    for key, value in node.items():
        if key in {"options", "options_tr", "distractors"} and isinstance(value, list):
            out[key] = [_clean_option(x) if isinstance(x, str) else _walk(x, language, key) for x in value]
        elif key == "answer" and isinstance(value, str):
            out[key] = _clean_option(value)
        elif key in _TR_INSTRUCTIONAL_KEYS and isinstance(value, str):
            out[key] = _clean_turkish_instructional(value)
        elif key == "target" and parent_key == "comparisons" and isinstance(value, str):
            out[key] = _clean_comparison_target(value)
        elif isinstance(value, (dict, list)):
            out[key] = _walk(value, language, key)
        else:
            out[key] = value

    if parent_key in {"items", "vocabulary", "words"}:
        out = _normalize_russian_grapheme_item(out, language)
    return out


def apply_release_policy(data, language=""):
    """Final zero-LLM publication policy. Prefer omission to fabricated repair."""
    if not isinstance(data, (dict, list)):
        return data
    cleaned = _walk(deepcopy(data), language)
    return cleaned if cleaned is not None else data
