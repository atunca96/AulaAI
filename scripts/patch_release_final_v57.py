from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"
TAG = "# AULAAI_RELEASE_FINAL_V57"

guard = guard_path.read_text(encoding="utf-8")
if TAG not in guard:
    guard += r'''

# AULAAI_RELEASE_FINAL_V57
# Final zero-LLM publication invariants. This layer is intentionally narrow:
# it never invents semantic content, never retries generation, and never drops
# substantive lesson pages. It may omit only an MCQ whose keyed answer depends
# on an unstated identity/biographical fact.
import re as _v57_re
import unicodedata as _v57_ud


def _v57_fold(value):
    text = _v57_ud.normalize("NFD", str(value or "")).casefold()
    text = "".join(ch for ch in text if _v57_ud.category(ch) != "Mn")
    return text.replace("ı", "i")


def _v57_mcq_prompt(page):
    if not isinstance(page, dict):
        return ""
    for key in ("prompt_tr", "question_tr", "stem_tr", "prompt_en", "question_en", "stem_en", "prompt", "question", "stem", "text_tr", "text_en", "text"):
        value = page.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _v57_mcq_explanation(page):
    if not isinstance(page, dict):
        return ""
    return " ".join(str(page.get(key) or "") for key in (
        "explanation_tr", "analysis_tr", "explanation_en", "analysis_en", "explanation", "analysis"
    ))


def _v57_mcq_like(page):
    if not isinstance(page, dict):
        return False
    if str(page.get("type") or "").strip().casefold() == "mcq":
        return True
    return bool((page.get("options") or page.get("choices")) and _v57_mcq_prompt(page))


def _v57_unsafe_mcq(page):
    if not _v57_mcq_like(page):
        return False
    prompt = _v57_mcq_prompt(page)
    explanation = _v57_mcq_explanation(page)
    p = _v57_fold(prompt)
    e = _v57_fold(explanation)

    gender_words = r"\b(kadin|erkek|disil|eril|female|male|woman|man|feminine|masculine)\b"
    explicit_gender = bool(_v57_re.search(gender_words, p)) or any(x in p for x in (
        "женщина", "мужчина", "девушка", "мальчик", "девочка", "мать", "отец", "мама", "папа",
        "сестра", "брат", "бабушка", "дедушка", "wife", "husband", "mother", "father", "sister", "brother",
    ))
    explanation_uses_gender = bool(_v57_re.search(gender_words, e))
    explanation_uses_name = bool(_v57_re.search(r"\b(isim|adi|adinin|name)\b", e))
    if explanation_uses_name and explanation_uses_gender and not explicit_gender:
        return True

    # Hidden-world entailment: birthplace/residence/workplace does not establish
    # nationality, language ability, profession, ethnicity or gender. Require the
    # explanation itself to reveal that the answer depends on such an identity fact.
    biography = any(marker in p for marker in (
        "dogdu", "dogmus", "dogum", "yasiyor", "yasadi", "ikamet", "calisiyor", "calisti",
        "born", "birthplace", "lives", "lived", "resides", "resided", "works", "worked",
        "родил", "рожден", "жив", "работ", "nacio", "nacido", "vive", "trabaja",
        "geboren", "lebt", "arbeitet", "nee", "habite", "travaille",
    ))
    identity = bool(_v57_re.search(
        r"\b(milliyet|uyruk|nationality|national|ethnicity|etnisite|dil|konus|language|speak|speaks|spoken|meslek|profession|occupation|job|disil|eril|female|male|feminine|masculine)\b",
        e,
    ))
    if biography and identity:
        return True
    return False


def _v57_prune_only_unsafe_mcq_children(node):
    if isinstance(node, list):
        kept = []
        for item in node:
            if isinstance(item, dict) and _v57_mcq_like(item) and _v57_unsafe_mcq(item):
                continue
            kept.append(_v57_prune_only_unsafe_mcq_children(item))
        return kept
    if isinstance(node, dict):
        return {key: _v57_prune_only_unsafe_mcq_children(value) for key, value in node.items()}
    return node


_v57_previous_integrity = enforce_material_integrity

def enforce_material_integrity(data, language=None, material_language="tr"):
    out = _v57_previous_integrity(data, language=language, material_language=material_language)
    if not isinstance(out, dict):
        return out
    pages = out.get("pages")
    if isinstance(pages, list):
        kept = []
        removed = []
        for idx, page in enumerate(pages):
            if isinstance(page, dict) and _v57_mcq_like(page) and _v57_unsafe_mcq(page):
                removed.append({"index": idx, "reason": "v57-hidden-world-mcq"})
                continue
            kept.append(_v57_prune_only_unsafe_mcq_children(page))
        out["pages"] = kept
        if removed:
            prior = out.get("_integrity_removed_mcq")
            if not isinstance(prior, list):
                prior = []
            out["_integrity_removed_mcq"] = prior + removed
    else:
        out = _v57_prune_only_unsafe_mcq_children(out)
    return out
'''
    guard_path.write_text(guard, encoding="utf-8")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    renderer += r'''

# AULAAI_RELEASE_FINAL_V57
import re as _v57r_re
import unicodedata as _v57r_ud


def _v57_tr_meta(value):
    if not isinstance(value, str) or not value:
        return value
    text = value
    replacements = (
        (r"\bPrepositional\s+Case\b", "Edat Durumu"),
        (r"\bNominative\b", "Yalın Hâl"),
        (r"\bAccusative\b", "Belirtme Hâli"),
        (r"\bGenitive\b", "İlgi/Tamlayan Hâli"),
        (r"\bDative\b", "Yönelme Hâli"),
        (r"\bInstrumental\b", "Araç Hâli"),
        (r"\bMasculine\b", "eril"),
        (r"\bFeminine\b", "dişil"),
        (r"\bNeuter\b", "nötr"),
    )
    for pattern, replacement in replacements:
        text = _v57r_re.sub(pattern, replacement, text, flags=_v57r_re.IGNORECASE)
    text = _v57r_re.sub(r"\b(Edat Durumu|Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli)\s+[Cc]ase\b", r"\1", text)
    text = _v57r_re.sub(r"(?i)\bİlgi\s*/\s*İlgi\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", text)
    text = _v57r_re.sub(r"(?i)\bİlgi\s*/\s*Tamlayan\s*(?:H[âa]li)?\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", text)
    text = _v57r_re.sub(r"(?i)\b(Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\s*\(\s*\1\s*\)", r"\1", text)
    text = _v57r_re.sub(r"(?i)\b(Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\s*/\s*\1\b", r"\1", text)
    text = _v57r_re.sub(r'["\'„“]?-д-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", text, flags=_v57r_re.IGNORECASE)
    text = _v57r_re.sub(r'["\'„“]?-d-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", text, flags=_v57r_re.IGNORECASE)
    return text


_v57_previous_pick = _pick

def _pick(obj, en_key, tr_key, is_tr):
    value = _v57_previous_pick(obj, en_key, tr_key, is_tr)
    return _v57_tr_meta(value) if is_tr else value


_v57_previous_comparison_blocks = _comparison_blocks

def _comparison_blocks(page, is_tr):
    if not is_tr or not isinstance(page, dict):
        return _v57_previous_comparison_blocks(page, is_tr)
    clone = dict(page)
    comparisons = page.get("comparisons") or []
    if isinstance(comparisons, dict):
        comparisons = [comparisons]
    if isinstance(comparisons, list):
        cleaned = []
        for item in comparisons:
            if isinstance(item, dict):
                c = dict(item)
                for key, value in list(c.items()):
                    if isinstance(value, str):
                        c[key] = _v57_tr_meta(value)
                cleaned.append(c)
            else:
                cleaned.append(_v57_tr_meta(item) if isinstance(item, str) else item)
        clone["comparisons"] = cleaned
    return _v57_previous_comparison_blocks(clone, is_tr)


def _v57_display_phonetic(value):
    text = str(value or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in _v57r_re.split(r"\s*/\s*", text) if part.strip()]
    rendered = []
    for part in parts:
        rendered.append(part if part.startswith("[") and part.endswith("]") else f"[{part}]")
    return " / ".join(rendered)


def _v57_is_grapheme_inventory(items):
    if not isinstance(items, list) or len(items) < 5:
        return False
    compact = paired = usable = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or item.get("word") or "").strip()
        if not term:
            continue
        usable += 1
        tokens = [token for token in term.split() if token]
        chars = "".join(tokens)
        if 1 <= len(chars) <= 4:
            compact += 1
        if len(tokens) == 2 and len(tokens[0]) == len(tokens[1]) == 1 and tokens[0].casefold() == tokens[1].casefold():
            paired += 1
    return usable >= 5 and (compact / usable) >= 0.75 and ((paired / usable) >= 0.30 or usable >= 15)


def _v57_renderer_unsafe_mcq(page):
    try:
        from services.material_quality_guard import _v57_unsafe_mcq
        return bool(_v57_unsafe_mcq(page))
    except Exception:
        return False


_v57_previous_normalize_pages = _normalize_pages

def _normalize_pages(content):
    pages = _v57_previous_normalize_pages(content)
    return [page for page in pages if not _v57_renderer_unsafe_mcq(page)]
'''

    # Enforce one visual pronunciation convention on the actual vocabulary-table
    # render path even if an earlier patch missed its exact source anchor.
    renderer, phon_count = _v57r_re.subn(
        r"(?m)^(\s*)phon\s*=\s*item\.get\('phonetic'\)\s*or\s*item\.get\('pronunciation'\)\s*or\s*''\s*$",
        r"\1phon = _v57_display_phonetic(item.get('phonetic') or item.get('pronunciation') or '')",
        renderer,
        count=1,
    )
    if phon_count == 0 and "_v54_display_phonetic" in renderer:
        renderer = renderer.replace("_v54_display_phonetic(phon)", "_v57_display_phonetic(phon)", 1)

    # Structural alphabet/script tables get semantically correct headers without
    # language-specific script hardcoding.
    renderer = renderer.replace(
        "'Terim / Kelime' if is_tr else 'Term / Word'",
        "('Harf / İşaret' if is_tr else 'Letter / Sign') if _v57_is_grapheme_inventory(items) else ('Terim / Kelime' if is_tr else 'Term / Word')",
        1,
    )
    renderer = renderer.replace(
        "'Telaffuz' if is_tr else 'Phonetic'",
        "('Temel Ses (IPA)' if is_tr else 'Basic Sound (IPA)') if _v57_is_grapheme_inventory(items) else ('Telaffuz' if is_tr else 'Phonetic')",
        1,
    )
    renderer_path.write_text(renderer, encoding="utf-8")

print("Applied v57 final publication invariants")
