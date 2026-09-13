from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"
TAG = "# AULAAI_RELEASE_HARDENING_V55"

guard = guard_path.read_text(encoding="utf-8")
if TAG not in guard:
    guard += r'''

# AULAAI_RELEASE_HARDENING_V55
_v55_previous_unsafe_mcq = _v54_unsafe_mcq
_v55_previous_meta = sanitize_instructional_metalanguage


def _v55_fold(text):
    # v54's Unicode fold intentionally preserves letters; for deterministic
    # Turkish keyword matching, normalize dotless i as well.
    return _v54_fold(text).replace("ı", "i")


def _v55_option_text(page):
    values = page.get("options") or page.get("choices") or []
    return " ".join(str(v or "") for v in values)


def _v54_unsafe_mcq(page, material_language):
    if _v55_previous_unsafe_mcq(page, material_language):
        return True
    if not _v54_is_mcq(page, material_language):
        return False
    pk = _v54_prompt_key(page, material_language)
    prompt = str(page.get(pk) or "") if pk else ""
    p = _v55_fold(prompt)
    opts = _v55_fold(_v55_option_text(page))

    workplace_fact = any(x in p for x in (
        "calisiyor", "calisir", "work at", "works at", "works in", "working at", "working in",
        "arbeitet", "travaille", "trabaja", "lavora", "trabalha", "работает", "работа в",
    ))
    profession_question = any(x in p for x in (
        "meslegi", "meslek nedir", "profession", "occupation", "job is", "what does", "beruf",
        "profession est", "profesion", "profissão", "професс", "кем он", "кем она",
    ))
    if workplace_fact and profession_question:
        return True

    trait_fact = any(x in p for x in (
        "dakik", "punctual", "punktlich", "ponctuel", "puntual", "pontual", "пунктуал",
    ))
    absolute_frequency_option = any(x in opts for x in (
        "nikogda", "vsegda", "never", "always", "niemals", "immer", "jamais", "toujours",
        "nunca", "siempre", "mai", "sempre", "никогда", "всегда",
    ))
    if trait_fact and absolute_frequency_option:
        return True
    return False


def sanitize_instructional_metalanguage(value, material_language="tr"):
    text = _v55_previous_meta(value, material_language)
    if str(material_language or "").strip().casefold() not in {"tr", "turkish", "türkçe", "turkce"}:
        return text
    text = re.sub(r"\bzero[- ]copula\b", "sıfır bağlayıcı", text, flags=re.IGNORECASE)
    text = re.sub(r"\bnominatif\b", "Yalın Hâl", text, flags=re.IGNORECASE)
    text = re.sub(r"\bgenitif\b", "İlgi/Tamlayan Hâli", text, flags=re.IGNORECASE)
    return text
'''
    guard_path.write_text(guard, encoding="utf-8")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    renderer += r'''

# AULAAI_RELEASE_HARDENING_V55
_v55_previous_pdf_unsafe_mcq = _v54_pdf_unsafe_mcq


def _v54_display_phonetic(value):
    """Normalize display without double-wrapping already bracketed composite IPA."""
    text = str(value or "").strip()
    if not text:
        return ""

    if text.startswith("[[") and text.endswith("]]" ):
        inner = text[1:-1].strip()
        groups = re.findall(r"\[[^\]\n]+\]", inner)
        residue = re.sub(r"\[[^\]\n]+\]", "", inner)
        if len(groups) >= 2 and not residue.replace("/", "").replace(" ", ""):
            return " / ".join(groups)

    groups = re.findall(r"\[[^\]\n]+\]", text)
    residue = re.sub(r"\[[^\]\n]+\]", "", text)
    if len(groups) >= 2 and not residue.replace("/", "").replace(" ", ""):
        return " / ".join(groups)

    parts = [p.strip() for p in text.split("/") if p.strip()]
    if len(parts) > 1:
        return " / ".join(p if (p.startswith("[") and p.endswith("]")) else f"[{p}]" for p in parts)
    return text if (text.startswith("[") and text.endswith("]")) else f"[{text}]"


def _v54_pdf_unsafe_mcq(page, prompt, is_tr):
    if _v55_previous_pdf_unsafe_mcq(page, prompt, is_tr):
        return True
    if not isinstance(page, dict):
        return False

    def fold(text):
        import unicodedata
        t = unicodedata.normalize("NFD", str(text or "")).casefold()
        t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
        return t.replace("ı", "i")

    p = fold(prompt)
    opts = fold(" ".join(str(v or "") for v in (page.get("options") or page.get("choices") or [])))
    workplace_fact = any(x in p for x in (
        "calisiyor", "calisir", "work at", "works at", "works in", "working at", "working in",
        "arbeitet", "travaille", "trabaja", "lavora", "trabalha", "работает", "работа в",
    ))
    profession_question = any(x in p for x in (
        "meslegi", "meslek nedir", "profession", "occupation", "job is", "what does", "beruf",
        "profession est", "profesion", "profissão", "професс", "кем он", "кем она",
    ))
    if workplace_fact and profession_question:
        return True

    trait_fact = any(x in p for x in (
        "dakik", "punctual", "punktlich", "ponctuel", "puntual", "pontual", "пунктуал",
    ))
    absolute_frequency_option = any(x in opts for x in (
        "nikogda", "vsegda", "never", "always", "niemals", "immer", "jamais", "toujours",
        "nunca", "siempre", "mai", "sempre", "никогда", "всегда",
    ))
    return trait_fact and absolute_frequency_option
'''
    renderer_path.write_text(renderer, encoding="utf-8")

print("Applied v55 surgical hardening: unsafe inference pruning, composite IPA display, Turkish metalanguage cleanup")
