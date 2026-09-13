import re
import unicodedata

_MARKERS = {
    "plural", "singular", "masculine", "feminine", "neuter", "only",
    "unstressed", "stressed", "sound", "rounded", "unrounded", "front",
    "back", "close", "open", "mid", "full", "like", "formal", "informal",
}


def _has_non_latin(text):
    return any(
        ch.isalpha() and "LATIN" not in unicodedata.name(ch, "")
        for ch in str(text or "")
    )


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
    return re.sub(r"\s*\[[A-Za-z]{2,16}\](?=\s*[?!.,;:]|\s*$)", "", text)


def _clean_tree(node):
    if isinstance(node, list):
        return [_clean_tree(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {}
    for key, value in node.items():
        if key in {"options", "options_tr", "distractors"} and isinstance(value, list):
            out[key] = [_clean_option(x) if isinstance(x, str) else _clean_tree(x) for x in value]
        elif key == "answer" and isinstance(value, str):
            out[key] = _clean_option(value)
        elif key == "comparisons" and isinstance(value, list):
            cleaned = []
            for item in value:
                item = _clean_tree(item)
                if isinstance(item, dict) and isinstance(item.get("target"), str):
                    item["target"] = _clean_target(item["target"])
                cleaned.append(item)
            out[key] = cleaned
        elif isinstance(value, (dict, list)):
            out[key] = _clean_tree(value)
        else:
            out[key] = value
    return out


def _install():
    try:
        import services.material_quality_guard as guard
        previous = guard.enforce_material_integrity

        def enforce_material_integrity(data, *args, **kwargs):
            return _clean_tree(previous(data, *args, **kwargs))

        guard.enforce_material_integrity = enforce_material_integrity
    except Exception as exc:
        print(f"[V56] guard hook skipped: {exc}")

    try:
        import services.pdf_renderer_v12 as renderer
        previous_normalize = renderer._normalize_content

        def _normalize_content(raw):
            return _clean_tree(previous_normalize(raw))

        renderer._normalize_content = _normalize_content
    except Exception as exc:
        print(f"[V56] renderer hook skipped: {exc}")


_install()
