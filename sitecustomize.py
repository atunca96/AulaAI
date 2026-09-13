import re
import unicodedata

_MARKERS = {
    "plural", "singular", "masculine", "feminine", "neuter", "only",
    "unstressed", "stressed", "sound", "rounded", "unrounded", "front",
    "back", "close", "open", "mid", "full", "like", "formal", "informal",
}

_TR_KEYS = {
    "title_tr", "text_tr", "explanation_tr", "example_tr", "rule_tr", "analysis_tr",
    "context_tr", "note_tr", "pitfall_tr", "translation_tr", "prompt_tr", "question_tr",
    "stem_tr", "line_tr", "speaker_tr", "meaning_tr", "definition_tr", "breakdown_tr",
}

_CYR_TO_LATIN = {
    "а":"a","А":"A","б":"b","Б":"B","в":"v","В":"V","г":"g","Г":"G",
    "д":"d","Д":"D","е":"e","Е":"E","з":"z","З":"Z","и":"i","И":"I",
    "к":"k","К":"K","л":"l","Л":"L","м":"m","М":"M","н":"n","Н":"N",
    "о":"o","О":"O","п":"p","П":"P","р":"r","Р":"R","с":"s","С":"S",
    "т":"t","Т":"T","у":"u","У":"U","ф":"f","Ф":"F",
}


def _fold(value):
    text = unicodedata.normalize("NFD", str(value or "")).casefold()
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn").replace("ı", "i")


def _is_russian(language):
    f = _fold(language)
    return "russian" in f or "rusca" in f or "рус" in f


def _has_non_latin(text):
    return any(ch.isalpha() and "LATIN" not in unicodedata.name(ch, "") for ch in str(text or ""))


def _clean_option(value):
    text = str(value or "").strip()
    match = re.search(r"\s*\(([^()]*)\)\s*$", text)
    if not match:
        return text
    core = text[:match.start()].rstrip()
    inner = match.group(1)
    words = {w.casefold() for w in re.findall(r"[A-Za-z]+", inner)}
    ipa_core = bool(re.fullmatch(r"\[[^\]]+\]", core))
    if (words & _MARKERS) and (_has_non_latin(core) or ipa_core):
        return core
    return text


def _clean_target(value):
    text = str(value or "")
    if not _has_non_latin(text):
        return text
    groups = re.findall(r"\[[^\]\n]+\]", text)
    if len(groups) >= 2:
        return text
    return re.sub(r"\s*\[[A-Za-z]{2,16}\](?=\s*[?!.,;:]|\s*$)", "", text)


def _repair_mixed_token_text(value):
    text = str(value or "")
    def repl(match):
        token = match.group(0)
        has_latin = any(ch.isalpha() and "LATIN" in unicodedata.name(ch, "") for ch in token)
        has_cyr = any(ch.isalpha() and "CYRILLIC" in unicodedata.name(ch, "") for ch in token)
        if not (has_latin and has_cyr):
            return token
        out = []
        for ch in token:
            if "CYRILLIC" in unicodedata.name(ch, ""):
                mapped = _CYR_TO_LATIN.get(ch)
                if mapped is None:
                    return token
                out.append(mapped)
            else:
                out.append(ch)
        return "".join(out)
    return re.sub(r"[^\W\d_]+", repl, text, flags=re.UNICODE)


def _clean_tr_text(value):
    text = _repair_mixed_token_text(value)
    text = re.sub(r"\bzero[- ]copula\b", "sıfır bağlayıcı", text, flags=re.IGNORECASE)
    text = re.sub(r"\bnominatif\b", "Yalın Hâl", text, flags=re.IGNORECASE)
    text = re.sub(r"\bgenitif\b", "İlgi/Tamlayan Hâli", text, flags=re.IGNORECASE)
    return text


def _prompt(page):
    for key in ("prompt_tr","question_tr","stem_tr","prompt","question","stem","text_tr","text"):
        if page.get(key):
            return str(page.get(key))
    return ""


def _explanation(page):
    return " ".join(str(page.get(k) or "") for k in ("explanation_tr","analysis_tr","explanation","analysis"))


def _options(page):
    value = page.get("options") or page.get("choices") or []
    return [str(x or "") for x in value] if isinstance(value, list) else []


def _explicit_gender_cue(text):
    return any(x in text for x in (
        "disil","eril","kadin","erkek","kiz","oglan","anne","baba","abla","agabey",
        "female","male","woman","man","girl","boy","mother","father","sister","brother",
        "женщ","мужчин","девуш","мальчик","мать","отец","сест","брат",
    ))


def _unsafe_mcq(page, language=""):
    if not isinstance(page, dict) or not _options(page) or not _prompt(page):
        return False
    p = _fold(_prompt(page)); e = _fold(_explanation(page)); opts = _fold(" ".join(_options(page)))

    gender_reason = any(x in e for x in (
        "ozne disil","ozne eril","female subject","male subject","female name","male name",
        "name is feminine","name is masculine","kadin ismi","erkek ismi",
    ))
    if gender_reason and not _explicit_gender_cue(p):
        return True

    marital = any(x in opts for x in ("замужем","женат","холост","married","single","evli","bekar"))
    marital_cue = any(x in p for x in (
        "evli","bekar","married","single","spouse","wife","husband","esi","karisi","kocasi",
        "замуж","женат","холост","муж","жена",
    ))
    if marital and not marital_cue:
        return True

    workplace = any(x in p for x in (
        "calisiyor","calisir","works at","works in","working at","working in","arbeitet","travaille",
        "trabaja","lavora","trabalha","работает","работа в",
    ))
    profession = any(x in (p + " " + e) for x in (
        "meslegi","meslek","profession","occupation","job is","beruf","професс","кем он","кем она",
    ))
    if workplace and profession:
        return True

    location = any(x in p for x in (
        "dogdu","dogmus","yasiyor","ikamet","born in","lives in","resides in","родил","живет в","живёт в",
    ))
    identity = any(x in (p + " " + e) for x in (
        "milliyet","uyruk","nationality","citizen","anadili","native speaker","language ability","националь","граждан",
    ))
    if location and identity:
        return True

    trait = any(x in p for x in ("dakik","punctual","punktlich","ponctuel","puntual","пунктуал"))
    absolute = any(x in opts for x in (
        "never","always","niemals","immer","jamais","toujours","nunca","siempre","никогда","всегда",
    ))
    if trait and absolute:
        return True

    # A standard seven-letter spelling-rule violation is a fabricated Russian
    # distractor, not a pedagogically valid alternative. Crop the item rather
    # than silently correcting an answer choice.
    if _is_russian(language) and any(re.search(r"[гкхжчшщ]ы", str(x).casefold()) for x in _options(page)):
        return True
    return False


def _normalize_item(item, language):
    if not (_is_russian(language) and isinstance(item, dict)):
        return item
    term = re.sub(r"\s+", "", str(item.get("term") or item.get("word") or "")).casefold()
    if term in {"ч","чч"}:
        item["phonetic"] = "[t͡ɕ]"
    elif term in {"щ","щщ"}:
        item["phonetic"] = "[ɕː]"
    elif term in {"ъ","ъъ","ь","ьь"}:
        item["phonetic"] = ""
    return item


def _clean_tree(node, language="", parent_key=""):
    if isinstance(node, list):
        cleaned = []
        for item in node:
            if isinstance(item, dict) and _unsafe_mcq(item, language):
                continue
            child = _clean_tree(item, language, parent_key)
            if child is not None:
                cleaned.append(child)
        return cleaned
    if not isinstance(node, dict):
        return node
    if _unsafe_mcq(node, language):
        return None
    out = {}
    for key, value in node.items():
        if key in {"options", "options_tr", "distractors"} and isinstance(value, list):
            out[key] = [_clean_option(x) if isinstance(x, str) else _clean_tree(x, language, key) for x in value]
        elif key == "answer" and isinstance(value, str):
            out[key] = _clean_option(value)
        elif key in _TR_KEYS and isinstance(value, str):
            out[key] = _clean_tr_text(value)
        elif key == "target" and parent_key == "comparisons" and isinstance(value, str):
            out[key] = _clean_target(value)
        elif isinstance(value, (dict, list)):
            out[key] = _clean_tree(value, language, key)
        else:
            out[key] = value
    if parent_key in {"items","vocabulary","words"}:
        out = _normalize_item(out, language)
    return out


def _install():
    try:
        import services.material_quality_guard as guard
        previous = guard.enforce_material_integrity

        def enforce_material_integrity(data, *args, **kwargs):
            language = kwargs.get("language") or kwargs.get("target_language") or (args[0] if args else "")
            return _clean_tree(previous(data, *args, **kwargs), language=language)

        guard.enforce_material_integrity = enforce_material_integrity
    except Exception as exc:
        print(f"[V57] guard hook skipped: {exc}")

    try:
        import services.pdf_renderer_v12 as renderer
        previous_normalize = renderer._normalize_content

        def _normalize_content(raw):
            return _clean_tree(previous_normalize(raw), language="")

        renderer._normalize_content = _normalize_content
    except Exception as exc:
        print(f"[V57] renderer hook skipped: {exc}")


_install()
