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

    # High-confidence workplace -> profession inference. Do not fabricate a cue;
    # remove the item and let the rest of the assessment stand.
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

    # High-confidence trait -> absolute-frequency inference. A trait such as
    # punctuality does not entail NEVER/ALWAYS behavior.
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


def _v54_repair_mcq_entailment(page, material_language):
    # v54 used to prepend invented gender cues to otherwise valid questions.
    # Never change the semantic premise of an assessment deterministically.
    # Unsafe items are pruned by _v54_unsafe_mcq; safe items remain untouched.
    return None


def sanitize_instructional_metalanguage(value, material_language="tr"):
    text = _v55_previous_meta(value, material_language)
    if str(material_language or "").strip().casefold() not in {"tr", "turkish", "türkçe", "turkce"}:
        return text
    text = re.sub(r"\bzero[- ]copula\b", "sıfır bağlayıcı", text, flags=re.IGNORECASE)
    text = re.sub(r"\bnominatif\b", "Yalın Hâl", text, flags=re.IGNORECASE)
    text = re.sub(r"\bgenitif\b", "İlgi/Tamlayan Hâli", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)\bİlgi\s*/\s*İlgi\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", text)
    text = re.sub(r"(?i)\bİlgi\s*/\s*Tamlayan\s*(?:H[âa]li)?\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", text)
    text = re.sub(r"(?i)\b(Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\s*\(\s*\1\s*\)", r"\1", text)
    text = re.sub(r"(?i)\b(Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\s*/\s*\1\b", r"\1", text)
    text = re.sub(r'["\'„“]?-д-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", text, flags=re.IGNORECASE)
    text = re.sub(r'["\'„“]?-d-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", text, flags=re.IGNORECASE)
    return text
'''
    guard_path.write_text(guard, encoding="utf-8")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    renderer += r'''

# AULAAI_RELEASE_HARDENING_V55
_v55_previous_pdf_unsafe_mcq = _v54_pdf_unsafe_mcq


def _v55_display_phonetic_cell(value):
    """Idempotent publication formatter for simple and composite IPA fields."""
    text = str(value or "").strip()
    if not text:
        return ""

    # Repeatedly remove only a redundant OUTER bracket pair when the inside is
    # already a slash-separated sequence of complete [IPA] groups.
    for _ in range(3):
        if not (text.startswith("[[") and text.endswith("]]")):
            break
        inner = text[1:-1].strip()
        groups = re.findall(r"\[[^\]\n]+\]", inner)
        residue = re.sub(r"\[[^\]\n]+\]", "", inner)
        if len(groups) >= 2 and not residue.replace("/", "").replace(" ", ""):
            text = " / ".join(groups)
        else:
            break

    groups = re.findall(r"\[[^\]\n]+\]", text)
    residue = re.sub(r"\[[^\]\n]+\]", "", text)
    if len(groups) >= 2 and not residue.replace("/", "").replace(" ", ""):
        return " / ".join(groups)

    parts = [p.strip() for p in text.split("/") if p.strip()]
    if len(parts) > 1:
        return " / ".join(
            p if (p.startswith("[") and p.endswith("]")) else f"[{p}]"
            for p in parts
        )
    return text if (text.startswith("[") and text.endswith("]")) else f"[{text}]"


def _v54_display_phonetic(value):
    # Keep v54's public helper name for compatibility, but make it idempotent.
    return _v55_display_phonetic_cell(value)


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

    # Normalize at the actual table-cell render boundary as well. This makes the
    # fix independent of earlier v54 source substitutions and of how the model
    # serialized a composite phonetic field.
    phon_cell = 'f\'<td><span class="phon">{_e(phon)}</span></td>\''
    phon_cell_new = 'f\'<td><span class="phon">{_e(_v55_display_phonetic_cell(phon))}</span></td>\''
    if phon_cell in renderer:
        renderer = renderer.replace(phon_cell, phon_cell_new, 1)
    elif '_v55_display_phonetic_cell(phon)' not in renderer:
        raise RuntimeError("v55 phonetic render-cell anchor missing")

    # Rule fallbacks (notably breakdown) can bypass _pick/_v52_meta. Sanitize the
    # final learner-facing Turkish strings immediately before HTML rendering.
    rule_anchor = "            bits = ['<div class=\"rule\">']"
    rule_cleanup = """            if is_tr:\n                r_title = _v52_meta(r_title, \"tr\")\n                r_expl = _v52_meta(r_expl, \"tr\")\n                r_example_trans = _v52_meta(r_example_trans, \"tr\")\n                r_analysis = _v52_meta(r_analysis, \"tr\")\n            bits = ['<div class=\"rule\">']"""
    if rule_anchor in renderer:
        renderer = renderer.replace(rule_anchor, rule_cleanup, 1)
    elif 'r_analysis = _v52_meta(r_analysis, "tr")' not in renderer:
        raise RuntimeError("v55 rule render-boundary anchor missing")

    renderer_path.write_text(renderer, encoding="utf-8")

print("Applied v55 surgical hardening: prune unsafe inference, no fabricated cues, render-boundary IPA/meta cleanup")
