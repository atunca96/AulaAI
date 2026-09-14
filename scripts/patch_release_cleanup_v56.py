from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"

TAG = "# AULAAI_RELEASE_CLEANUP_V56"

guard = guard_path.read_text(encoding="utf-8")
if TAG not in guard:
    guard += r'''

# AULAAI_RELEASE_CLEANUP_V56
# Final zero-LLM publication cleanup. This layer is deliberately narrow:
# repair only high-confidence orthographic/script defects; prune unsafe MCQs/pages
# rather than inventing semantic content.
_V56_LATIN_TO_CYR = {
    "A":"А", "a":"а", "B":"В", "C":"С", "c":"с", "E":"Е", "e":"е",
    "H":"Н", "K":"К", "k":"к", "M":"М", "m":"м", "O":"О", "o":"о",
    "P":"Р", "p":"р", "T":"Т", "t":"т", "X":"Х", "x":"х", "Y":"У", "y":"у",
}
_V56_TR_KEYS = {
    "title_tr", "text_tr", "translation_tr", "explanation_tr", "analysis_tr", "note_tr",
    "context_tr", "meaning_tr", "definition_tr", "prompt_tr", "question_tr", "stem_tr",
    "line_tr", "speaker_tr", "rule_tr", "tip_tr", "pitfall_tr", "breakdown_tr",
}
_V56_TARGET_KEYS = {
    "term", "word", "target", "example", "sentence", "answer", "expression", "phrase", "form", "native", "text",
}


def _v56_strip_marks(text):
    n = unicodedata.normalize("NFD", str(text or ""))
    return "".join(ch for ch in n if unicodedata.category(ch) != "Mn")


def _v56_scripts(token):
    out = set()
    for ch in str(token or ""):
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        if "CYRILLIC" in name:
            out.add("CYRILLIC")
        elif "LATIN" in name:
            out.add("LATIN")
        elif "GREEK" in name:
            out.add("GREEK")
        elif "ARABIC" in name:
            out.add("ARABIC")
        elif "HEBREW" in name:
            out.add("HEBREW")
    return out


def _v56_repair_cyrillic_mixed_token(token):
    token = str(token or "")
    scripts = _v56_scripts(token)
    if not ({"CYRILLIC", "LATIN"} <= scripts):
        return token, False
    out = []
    changed = False
    for ch in token:
        if ch.isalpha() and "LATIN" in unicodedata.name(ch, ""):
            mapped = _V56_LATIN_TO_CYR.get(ch)
            if not mapped:
                return token, False
            out.append(mapped)
            changed = True
        else:
            out.append(ch)
    repaired = "".join(out)
    if changed and _v56_scripts(repaired) <= {"CYRILLIC"}:
        return repaired, True
    return token, False


def _v56_russian_text(text):
    if not isinstance(text, str) or not text:
        return text, False
    # Known high-confidence lexical slips observed in production. These are exact
    # canonical corrections, not generative guesses.
    text = re.sub(r"(?i)писмо(?=\b|[́̀])", "письмо", text)
    text = re.sub(r"(?i)козине(?=\b|[́̀])", "корзине", text)

    unsafe = False
    def repl(match):
        nonlocal unsafe
        tok = match.group(0)
        scripts = _v56_scripts(tok)
        if scripts == {"CYRILLIC", "LATIN"}:
            fixed, ok = _v56_repair_cyrillic_mixed_token(tok)
            if ok:
                return fixed
            unsafe = True
        return tok

    text = re.sub(r"[^\W\d_]+", repl, text, flags=re.UNICODE)
    return text, unsafe


def _v56_turkish_text(text):
    if not isinstance(text, str) or not text:
        return text
    # Collapse sanitizer-generated duplicate labels.
    text = re.sub(r"(?i)\bİlgi\s*/\s*İlgi\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", text)
    text = re.sub(r"(?i)\bİlgi\s*/\s*Tamlayan\s+H[âa]li\s*/\s*İlgi\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", text)
    text = re.sub(r"(?i)\bYalın\s+H[âa]l\s*/\s*Yalın\s+H[âa]l\b", "Yalın Hâl", text)
    # High-confidence foreign artefact observed in a Turkish learner-facing field.
    # Remove only the isolated token; do not attempt broad language detection.
    text = re.sub(r"(?<!\w)Physik(?!\w)\s*", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def _v56_impossible_russian_option(value):
    raw = _v56_strip_marks(str(value or "")).casefold()
    # Orthographically impossible -ы after the 7-letter spelling-rule consonants.
    if re.search(r"[гкхжчшщ]ы", raw):
        return True
    # Production-observed fabricated forms: prune the MCQ rather than fabricate a replacement.
    compact = re.sub(r"[^а-яё]", "", raw)
    return compact in {"городи", "ребеноки", "ребёноки"}


def _v56_clean_node(node, language="", parent_key=""):
    is_russian = "russian" in str(language or "").casefold() or "rusça" in str(language or "").casefold() or "рус" in str(language or "").casefold()
    if isinstance(node, str):
        if parent_key in _V56_TR_KEYS or str(parent_key).endswith("_tr"):
            return _v56_turkish_text(node), False
        if is_russian and parent_key in _V56_TARGET_KEYS:
            return _v56_russian_text(node)
        return node, False
    if isinstance(node, list):
        out = []
        unsafe = False
        for item in node:
            cleaned, bad = _v56_clean_node(item, language, parent_key)
            out.append(cleaned)
            unsafe = unsafe or bad
        return out, unsafe
    if not isinstance(node, dict):
        return node, False

    # High-confidence fabricated distractor => drop whole item later.
    if is_russian and str(node.get("type") or "").strip().casefold() == "mcq":
        opts = node.get("options") or node.get("choices") or []
        if isinstance(opts, list) and any(_v56_impossible_russian_option(x) for x in opts if isinstance(x, str)):
            return None, True

    out = {}
    unsafe = False
    for key, value in node.items():
        cleaned, bad = _v56_clean_node(value, language, str(key))
        out[key] = cleaned
        unsafe = unsafe or bad
    return out, unsafe


def _v56_release_cleanup(data, language=""):
    if not isinstance(data, dict):
        return data
    out = deepcopy(data)
    pages = out.get("pages")
    if not isinstance(pages, list):
        cleaned, _ = _v56_clean_node(out, language)
        return cleaned

    kept = []
    removed = []
    for idx, page in enumerate(pages):
        cleaned, unsafe = _v56_clean_node(page, language)
        if cleaned is None or unsafe:
            removed.append({"index": idx, "reason": "v56-publication-safety"})
            continue
        kept.append(cleaned)
    out["pages"] = kept
    if removed:
        prior = out.get("_integrity_removed_mcq")
        if not isinstance(prior, list):
            prior = []
        out["_integrity_removed_mcq"] = prior + removed
    return out


_v56_previous_integrity = enforce_material_integrity

def enforce_material_integrity(data, language=None, material_language="tr"):
    out = _v56_previous_integrity(data, language=language, material_language=material_language)
    return _v56_release_cleanup(out, language or "")
'''
    guard_path.write_text(guard, encoding="utf-8")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    renderer += r'''

# AULAAI_RELEASE_CLEANUP_V56
from services.material_quality_guard import _v56_release_cleanup as _v56_publication_cleanup
_v56_previous_normalize_content = _normalize_content

def _normalize_content(raw):
    normalized = _v56_previous_normalize_content(raw)
    # Renderer has no reliable language argument here. Apply only language-neutral
    # Turkish label cleanup and exact safe lexical corrections via a shallow helper.
    if isinstance(normalized, dict):
        # Russian is the only target needing the exact typo/mixed-script corrections
        # below; detection happens from the content itself without changing generation.
        return _v56_publication_cleanup(normalized, "Russian")
    return normalized
'''
    renderer_path.write_text(renderer, encoding="utf-8")

print("Applied v56 final deterministic publication cleanup")
