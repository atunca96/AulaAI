from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"
TAG = "# AULAAI_RELEASE_CLEANUP_V56_QUALITY"

guard = guard_path.read_text(encoding="utf-8")
if "# AULAAI_RELEASE_CLEANUP_V56" not in guard:
    raise RuntimeError("v56 base cleanup must be applied before v56 quality overlay")

if TAG not in guard:
    guard += r'''

# AULAAI_RELEASE_CLEANUP_V56_QUALITY
# Zero-LLM quality cleanup with a hard structural invariant:
# this overlay may remove only a page whose OWN type is exactly "mcq".
# It never returns unsafe flags and never removes substantive content pages.
import re as _v56q_re
import unicodedata as _v56q_ud

_V56Q_BAD_RU_OPTIONS = {
    "готовю", "италие", "городи", "ребеноки", "ребёноки", "другы", "книгы",
}
_V56Q_IPA_SINGLE = {
    "б":"b", "в":"v", "г":"ɡ", "д":"d", "ж":"ʐ", "з":"z", "к":"k",
    "л":"ɫ", "м":"m", "н":"n", "п":"p", "р":"r", "с":"s", "т":"t",
    "ф":"f", "х":"x", "ц":"t͡s", "ч":"t͡ɕ", "ш":"ʂ", "щ":"ɕː", "й":"j",
}


def _v56q_fold(value):
    text = _v56q_ud.normalize("NFD", str(value or "")).casefold()
    return "".join(ch for ch in text if _v56q_ud.category(ch) != "Mn").replace("ı", "i")


def _v56q_page_is_mcq(page):
    return isinstance(page, dict) and str(page.get("type") or "").strip().casefold() == "mcq"


def _v56q_prompt(page):
    for key in ("prompt_tr", "question_tr", "stem_tr", "prompt", "question", "stem", "text_tr", "text"):
        value = page.get(key) if isinstance(page, dict) else None
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _v56q_explanation(page):
    if not isinstance(page, dict):
        return ""
    return " ".join(str(page.get(k) or "") for k in (
        "explanation_tr", "analysis_tr", "explanation", "analysis", "explanation_en"
    ))


def _v56q_stressless(value):
    # Remove only pedagogical stress marks. Do not strip all combining marks:
    # doing so turns Cyrillic й into и and breaks exact lexical checks.
    text = _v56q_ud.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if ch not in {"\u0300", "\u0301"})
    return _v56q_ud.normalize("NFC", text).casefold()


def _v56q_bad_option(value):
    raw = _v56q_stressless(value).strip()
    if _v56_impossible_russian_option(value):
        return True
    compact = _v56q_re.sub(r"[^а-яё]", "", raw)
    if compact in _V56Q_BAD_RU_OPTIONS:
        return True
    normalized_space = _v56q_re.sub(r"\s+", " ", raw)
    if normalized_space in {"по русский", "на русскому"}:
        return True
    return False


def _v56q_explanation_admits_malformed_distractor(page):
    e = _v56q_fold(_v56q_explanation(page))
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


def _v56q_hidden_name_gender(page):
    prompt = _v56q_prompt(page)
    explanation = _v56q_explanation(page)
    p = _v56q_fold(prompt)
    e = _v56q_fold(explanation)

    if not any(x in e for x in ("ozne", "subject")):
        return False
    if not any(x in e for x in ("disil", "eril", "female", "male", "feminine", "masculine")):
        return False

    if any(x in p for x in (
        "disil", "eril", "kadin", "erkek", "female", "male", "woman", "man",
        "женщина", "мужчина", "девушка", "мальчик", "девочка", "мать", "отец",
        "мама", "папа", "сестра", "брат", "бабушка", "дедушка",
        "wife", "husband", "mother", "father", "sister", "brother",
    )):
        return False

    quoted = _v56q_re.findall(
        r"['«“\"]([A-ZА-ЯЁÇĞİÖŞÜ][A-Za-zА-Яа-яЁёÇĞİÖŞÜçğıöşü-]{1,30})['»”\"]",
        explanation,
    )
    return any(token in prompt for token in quoted)


def _v56q_unsafe_mcq(page, material_language="tr"):
    if not _v56q_page_is_mcq(page):
        return False
    try:
        if _v54_unsafe_mcq(page, material_language):
            return True
    except Exception:
        pass
    options = page.get("options") or page.get("choices") or []
    if isinstance(options, list) and any(_v56q_bad_option(v) for v in options if isinstance(v, str)):
        return True
    if _v56q_explanation_admits_malformed_distractor(page):
        return True
    if _v56q_hidden_name_gender(page):
        return True
    return False


def _v56q_strip_cyrillic_respelling(text):
    if not isinstance(text, str) or not text:
        return text
    return _v56q_re.sub(
        r"([А-Яа-яЁё\u0300\u0301]{3,})\s*\[([А-Яа-яЁё\u0300\u0301]{3,})\]",
        r"\1",
        text,
    )


def _v56q_normalize_alphabet_item(item):
    if not isinstance(item, dict):
        return item
    term = str(item.get("term") or item.get("word") or "")
    compact = "".join(
        ch for ch in _v56q_ud.normalize("NFD", term).casefold()
        if _v56q_ud.category(ch) != "Mn" and ch.isalpha()
    )
    if compact in {"ч", "чч"}:
        item["phonetic"] = "[t͡ɕ]"
    elif compact in {"щ", "щщ"}:
        item["phonetic"] = "[ɕː]"
    elif compact in {"ъ", "ъъ", "ь", "ьь"}:
        item["phonetic"] = ""
    return item


def _v56q_clean_tree(node, language="", parent_key=""):
    """Leaf-only cleanup. Never deletes a dict/list/item and never emits unsafe."""
    is_russian = _v56_is_russian(language)
    if isinstance(node, str):
        text = node
        if parent_key in _V56_TR_KEYS or str(parent_key).endswith("_tr"):
            text = _v56_turkish_text(text)
        if is_russian and parent_key in _V56_TARGET_KEYS:
            text, _ignored_unsafe = _v56_russian_text(text)
            text = _v56q_strip_cyrillic_respelling(text)
        return text
    if isinstance(node, list):
        return [_v56q_clean_tree(v, language, parent_key) for v in node]
    if not isinstance(node, dict):
        return node
    out = {k: _v56q_clean_tree(v, language, str(k)) for k, v in node.items()}
    if is_russian:
        _v56q_normalize_alphabet_item(out)
    return out


_v56q_previous_release_cleanup = _v56_release_cleanup

def _v56_release_cleanup(data, language=""):
    out = _v56q_previous_release_cleanup(data, language)
    if not isinstance(out, dict):
        return out

    if not _v56_is_russian(language):
        return _v56q_clean_tree(out, language)

    pages = out.get("pages")
    if not isinstance(pages, list):
        return _v56q_clean_tree(out, language)

    kept = []
    removed = []
    for idx, page in enumerate(pages):
        if _v56q_page_is_mcq(page) and _v56q_unsafe_mcq(page, "tr"):
            removed.append({"index": idx, "reason": "v56-quality-mcq-only"})
            continue
        kept.append(_v56q_clean_tree(page, language))

    out["pages"] = kept
    if removed:
        prior = out.get("_integrity_removed_mcq")
        if not isinstance(prior, list):
            prior = []
        out["_integrity_removed_mcq"] = prior + removed
    return out
'''
    guard_path.write_text(guard, encoding="utf-8")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    renderer += r'''

# AULAAI_RELEASE_CLEANUP_V56_QUALITY
_V56Q_RENDER_IPA_SINGLE = {
    "б":"b", "в":"v", "г":"ɡ", "д":"d", "ж":"ʐ", "з":"z", "к":"k",
    "л":"ɫ", "м":"m", "н":"n", "п":"p", "р":"r", "с":"s", "т":"t",
    "ф":"f", "х":"x", "ц":"t͡s", "ч":"t͡ɕ", "ш":"ʂ", "щ":"ɕː", "й":"j",
}

def _v56q_render_is_russian(language):
    value = str(language or "").casefold()
    return "russian" in value or "rusça" in value or "рус" in value


def _v56q_display_option(value, language=""):
    text = str(value or "").strip()
    if not _v56q_render_is_russian(language):
        return text

    m = re.fullmatch(r"(\[[^\]\n]+\])\s*\(([^()]*)\)", text)
    if m:
        gloss = m.group(2).casefold()
        if any(phrase in gloss for phrase in (
            "similar to", "short i-like", "clear long", "close front",
            "rounded back", "clear rounded", "full stressed", "sound due to",
            "unstressed 'a'", "unstressed a",
        )):
            text = m.group(1)

    m = re.fullmatch(r"\[([А-Яа-яЁё])([ʲː]?)\]", text)
    if m:
        letter = m.group(1).casefold()
        base = _V56Q_RENDER_IPA_SINGLE.get(letter)
        if base:
            mark = m.group(2)
            if mark == "ʲ" and letter == "л":
                return "[lʲ]"
            return f"[{base}{mark}]"
    return text
'''

    anchor = "                        options = localized if isinstance(localized, list) and len(localized) == len(raw_options) else raw_options\n"
    replacement = anchor + "                        options = [_v56q_display_option(opt, course_lang) for opt in options]\n"
    if anchor not in renderer:
        raise RuntimeError("v56 quality renderer option anchor missing")
    renderer = renderer.replace(anchor, replacement, 1)
    renderer_path.write_text(renderer, encoding="utf-8")

print("Applied v56 quality overlay: mcq-only pruning + leaf publication normalization")
