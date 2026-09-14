from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
TAG = "# AULAAI_RELEASE_CLEANUP_V56_FINAL"

guard = guard_path.read_text(encoding="utf-8")
if TAG not in guard:
    guard += r'''

# AULAAI_RELEASE_CLEANUP_V56_FINAL
# Last-mile, zero-LLM cleanup. Keep the proven generation path unchanged.
_V56F_IPA_SINGLE = {
    "б":"b", "в":"v", "г":"ɡ", "д":"d", "ж":"ʐ", "з":"z", "к":"k",
    "л":"ɫ", "м":"m", "н":"n", "п":"p", "р":"r", "с":"s", "т":"t",
    "ф":"f", "х":"x", "ц":"t͡s", "ч":"t͡ɕ", "ш":"ʂ", "щ":"ɕː", "й":"j",
}
_V56F_BAD_OPTIONS = {
    "готовю", "италие", "городи", "ребеноки", "ребёноки", "другы", "книгы",
}


def _v56f_fold(text):
    t = unicodedata.normalize("NFD", str(text or "")).casefold()
    return "".join(ch for ch in t if unicodedata.category(ch) != "Mn").replace("ı", "i")


def _v56f_clean_option(value):
    text = str(value or "").strip()
    # A pronunciation option should be the pronunciation itself; explanatory prose
    # belongs in the question explanation, not inside the option label.
    m = re.fullmatch(r"(\[[^\]\n]+\])\s*\(([^()]*)\)", text)
    if m:
        text = m.group(1)

    # Convert a one-letter Cyrillic phonetic answer to its IPA symbol. This is
    # intentionally limited to single consonants; full Cyrillic respellings are
    # removed from prose instead of being guessed into IPA.
    m = re.fullmatch(r"\[([А-Яа-яЁё])([ʲː]?)\]", text)
    if m:
        base = _V56F_IPA_SINGLE.get(m.group(1).casefold())
        if base:
            mark = m.group(2)
            if mark == "ʲ":
                if m.group(1).casefold() == "л":
                    base = "l"
                return f"[{base}ʲ]"
            if mark == "ː":
                return f"[{base}ː]"
            return f"[{base}]"
    return text


_v56f_previous_russian_text = _v56_russian_text

def _v56_russian_text(text):
    text, unsafe = _v56f_previous_russian_text(text)
    if not isinstance(text, str):
        return text, unsafe
    # Square-bracketed Cyrillic respelling is a second pronunciation system.
    # Keep the lexical form and drop only that learner-facing respelling.
    text = re.sub(
        r"([А-Яа-яЁё\u0300\u0301]+)\s*\[([А-Яа-яЁё\u0300\u0301]+)\]",
        r"\1",
        text,
    )
    return text, unsafe


def _v56f_is_mcq(page):
    if not isinstance(page, dict):
        return False
    if str(page.get("type") or "").strip().casefold() == "mcq":
        return True
    opts = page.get("options") or page.get("choices")
    prompt = next((page.get(k) for k in ("prompt_tr","question_tr","stem_tr","prompt","question","stem") if page.get(k)), None)
    return bool(opts and prompt)


def _v56f_prompt(page):
    for key in ("prompt_tr","question_tr","stem_tr","prompt","question","stem","text_tr","text"):
        value = page.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _v56f_explanation(page):
    return " ".join(str(page.get(k) or "") for k in (
        "explanation_tr", "analysis_tr", "explanation", "analysis", "explanation_en"
    ))


def _v56f_malformed_distractor_explained(page):
    e = _v56f_fold(_v56f_explanation(page))
    if any(x in e for x in (
        "hatali bir form", "hatali form", "hatali durum eki", "gecersiz bir form",
        "uydurma form", "invalid form", "non-word", "misspelling",
    )):
        return True
    if "dogru ek icermez" in e:
        return True
    if "zorunlu" in e and "icermedigi icin" in e and "yanlistir" in e:
        return True
    return False


def _v56f_hidden_name_gender(page):
    prompt = _v56f_prompt(page)
    explanation = _v56f_explanation(page)
    p = _v56f_fold(prompt)
    e = _v56f_fold(explanation)
    if not any(x in e for x in ("disil", "eril", "female", "male", "feminine", "masculine")):
        return False
    explicit = any(x in p for x in (
        "disil", "eril", "kadin", "erkek", "female", "male", "woman", "man",
        "женщина", "мужчина", "девушка", "мальчик", "девочка", "мать", "отец",
        "мама", "папа", "сестра", "брат", "бабушка", "дедушка",
        "wife", "husband", "mother", "father", "sister", "brother",
    ))
    if explicit or not any(x in e for x in ("ozne", "subject")):
        return False
    quoted = re.findall(
        r"['«“\"]([A-ZА-ЯЁÇĞİÖŞÜ][A-Za-zА-Яа-яЁёÇĞİÖŞÜçğıöşü-]{1,30})['»”\"]",
        explanation,
    )
    return any(token in prompt for token in quoted)


def _v56f_bad_option(value):
    raw = _v56_strip_marks(str(value or "")).casefold().strip()
    if _v56_impossible_russian_option(value):
        return True
    compact = re.sub(r"[^а-яё]", "", raw)
    if compact in _V56F_BAD_OPTIONS:
        return True
    if re.search(r"(?:б|п|в|ф|м)ю$", compact) and "ью" not in compact:
        return True
    normalized_space = re.sub(r"\s+", " ", raw)
    if normalized_space in {"по русский", "на русскому"}:
        return True
    return False


def _v56f_unsafe_mcq(page, material_language="tr"):
    if not _v56f_is_mcq(page):
        return False
    try:
        if _v54_unsafe_mcq(page, material_language):
            return True
    except Exception:
        pass
    options = page.get("options") or page.get("choices") or []
    if isinstance(options, list) and any(_v56f_bad_option(x) for x in options if isinstance(x, str)):
        return True
    if _v56f_malformed_distractor_explained(page):
        return True
    if _v56f_hidden_name_gender(page):
        return True
    return False


def _v56f_normalize_alphabet_item(item):
    if not isinstance(item, dict):
        return item
    term = str(item.get("term") or item.get("word") or "")
    compact = "".join(
        ch for ch in unicodedata.normalize("NFD", term).casefold()
        if unicodedata.category(ch) != "Mn" and ch.isalpha()
    )
    if compact in {"ч", "чч"}:
        item["phonetic"] = "[t͡ɕ]"
    elif compact in {"щ", "щщ"}:
        item["phonetic"] = "[ɕː]"
    elif compact in {"ъ", "ъъ", "ь", "ьь"}:
        item["phonetic"] = ""
    return item


def _v56f_walk(node, language="", parent_key=""):
    is_russian = any(x in str(language or "").casefold() for x in ("russian", "rusça", "рус"))
    if isinstance(node, str):
        text = node
        if parent_key in {"options", "choices", "distractors", "answer"}:
            text = _v56f_clean_option(text)
        if parent_key in _V56_TR_KEYS or str(parent_key).endswith("_tr"):
            text = _v56_turkish_text(text)
        if is_russian and (parent_key in _V56_TARGET_KEYS or parent_key in {"options", "choices", "distractors", "answer"}):
            text, unsafe = _v56_russian_text(text)
            return text, unsafe
        return text, False

    if isinstance(node, list):
        out = []
        unsafe = False
        for item in node:
            cleaned, bad = _v56f_walk(item, language, parent_key)
            if cleaned is not None:
                out.append(cleaned)
            unsafe = unsafe or bad
        return out, unsafe

    if not isinstance(node, dict):
        return node, False

    if is_russian and _v56f_unsafe_mcq(node, "tr"):
        return None, True

    out = {}
    unsafe = False
    for key, value in node.items():
        cleaned, bad = _v56f_walk(value, language, str(key))
        if cleaned is not None:
            out[key] = cleaned
        unsafe = unsafe or bad

    if is_russian:
        out = _v56f_normalize_alphabet_item(out)
    return out, unsafe


_v56f_previous_release_cleanup = _v56_release_cleanup

def _v56_release_cleanup(data, language=""):
    out = _v56f_previous_release_cleanup(data, language)
    if not isinstance(out, (dict, list)):
        return out
    cleaned, _ = _v56f_walk(out, language, "")
    return cleaned if cleaned is not None else out
'''
    guard_path.write_text(guard, encoding="utf-8")

print("Applied v56 final one-shot cleanup overlay")
