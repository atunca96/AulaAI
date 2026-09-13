from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"
engine_path = ROOT / "services" / "ai_engine.py"
TAG = "# AULAAI_RELEASE_HARDENING_V54"

guard = guard_path.read_text(encoding="utf-8")
if TAG not in guard:
    guard += r'''

# AULAAI_RELEASE_HARDENING_V54
_v54_previous_integrity = enforce_material_integrity


def _v54_fold(text):
    text = unicodedata.normalize("NFD", str(text or "")).casefold()
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _v54_collect_authoritative_phonetics(node, out):
    if isinstance(node, dict):
        term = node.get("term") or node.get("word") or node.get("phrase") or node.get("target")
        phon = str(node.get("phonetic") or "").strip()
        if term and phon.startswith("[") and phon.endswith("]"):
            key = _v54_fold(term).strip()
            if len(key) >= 2:
                out[key] = phon
        for value in node.values():
            _v54_collect_authoritative_phonetics(value, out)
    elif isinstance(node, list):
        for value in node:
            _v54_collect_authoritative_phonetics(value, out)


def _v54_sync_one_string(text, phonetics):
    if not isinstance(text, str) or "[" not in text or "]" not in text:
        return text
    groups = list(re.finditer(r"\[[^\]\n]{1,100}\]", text))
    if len(groups) != 1:
        return text
    folded = _v54_fold(text)
    for term, authoritative in phonetics.items():
        if term and term in folded:
            current = groups[0].group(0)
            if _v54_fold(current) != _v54_fold(authoritative):
                return text[:groups[0].start()] + authoritative + text[groups[0].end():]
    return text


def _v54_sync_prose_phonetics(node, phonetics, parent_key=""):
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if key == "phonetic":
                continue
            if isinstance(value, str):
                node[key] = _v54_sync_one_string(value, phonetics)
            elif isinstance(value, (dict, list)):
                _v54_sync_prose_phonetics(value, phonetics, key)
    elif isinstance(node, list):
        for value in node:
            _v54_sync_prose_phonetics(value, phonetics, parent_key)


def _v54_prompt_key(page, material_language):
    tr = str(material_language or "").casefold() in {"tr", "turkish", "türkçe", "turkce"}
    candidates = ("prompt_tr", "question_tr", "stem_tr", "prompt", "question", "stem") if tr else ("prompt_en", "question_en", "stem_en", "prompt", "question", "stem")
    return next((k for k in candidates if isinstance(page.get(k), str) and page.get(k).strip()), None)


def _v54_explanation_key(page, material_language):
    tr = str(material_language or "").casefold() in {"tr", "turkish", "türkçe", "turkce"}
    candidates = ("explanation_tr", "explanation", "explanation_en") if tr else ("explanation_en", "explanation", "explanation_tr")
    return next((k for k in candidates if isinstance(page.get(k), str) and page.get(k).strip()), None)


def _v54_is_mcq(page, material_language):
    if not isinstance(page, dict):
        return False
    if str(page.get("type") or "").casefold() == "mcq":
        return True
    return bool((page.get("options") or page.get("choices")) and _v54_prompt_key(page, material_language))


def _v54_unsafe_mcq(page, material_language):
    """High-precision rejection only: remove questions whose keyed answer needs an unstated identity fact."""
    if not _v54_is_mcq(page, material_language):
        return False
    pk = _v54_prompt_key(page, material_language)
    ek = _v54_explanation_key(page, material_language)
    prompt = str(page.get(pk) or "") if pk else ""
    explanation = str(page.get(ek) or "") if ek else ""
    p = _v54_fold(prompt)
    e = _v54_fold(explanation)

    explicit_gender = bool(re.search(r"\b(kadin|erkek|disil|eril|female|male|woman|man)\b", p))
    gender_reason = bool(re.search(r"\b(kadin|erkek|disil|eril|female|male|woman|man)\b", e))
    name_reason = bool(re.search(r"\b(isim|adi|adinin|name)\b", e))
    if name_reason and gender_reason and not explicit_gender:
        return True

    biography_markers = (
        "dogdu", "dogmus", "yasiyor", "yasadi", "calisiyor", "calisti",
        "born", "lives", "lived", "works", "worked", "resides", "resided",
        "родил", "жив", "работ", "nacio", "nacido", "vive", "trabaja",
        "geboren", "lebt", "arbeitet", "nee", "habite", "travaille",
    )
    biography = any(marker in p for marker in biography_markers)
    identity_result = bool(re.search(
        r"\b(milliyet|uyruk|nationality|national|dil|konus|language|speak|speaks|spoken|meslek|profession|occupation|job)\b",
        e,
    ))
    if biography and identity_result:
        return True
    return False


def _v54_prune_unsafe_mcqs(node, material_language):
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if isinstance(value, list):
                kept = []
                for item in value:
                    if isinstance(item, dict) and _v54_unsafe_mcq(item, material_language):
                        continue
                    _v54_prune_unsafe_mcqs(item, material_language)
                    kept.append(item)
                node[key] = kept
            elif isinstance(value, dict):
                _v54_prune_unsafe_mcqs(value, material_language)
    elif isinstance(node, list):
        kept = []
        for item in node:
            if isinstance(item, dict) and _v54_unsafe_mcq(item, material_language):
                continue
            _v54_prune_unsafe_mcqs(item, material_language)
            kept.append(item)
        node[:] = kept


def _v54_repair_mcq_entailment(page, material_language):
    # Remaining MCQs may still receive harmless explicit-cue repair, but unsafe
    # name/biography identity questions are pruned before this function runs.
    if not _v54_is_mcq(page, material_language):
        return
    pk = _v54_prompt_key(page, material_language)
    ek = _v54_explanation_key(page, material_language)
    if not pk or not ek:
        return
    prompt = page[pk]
    explanation = page[ek]
    p = _v54_fold(prompt)
    e = _v54_fold(explanation)
    tr = str(material_language or "").casefold() in {"tr", "turkish", "türkçe", "turkce"}

    female = bool(re.search(r"\b(kadin|disil|female|woman)\b", e))
    male = bool(re.search(r"\b(erkek|eril|male|man)\b", e))
    explicit_gender = bool(re.search(r"\b(kadin|erkek|disil|eril|female|male|woman|man)\b", p))
    if (female or male) and not explicit_gender and "isim" not in e and "name" not in e:
        cue = ("Bu soruda özne açıkça kadın olarak verilmiştir. " if female else "Bu soruda özne açıkça erkek olarak verilmiştir. ") if tr else ("In this question, the subject is explicitly female. " if female else "In this question, the subject is explicitly male. ")
        page[pk] = cue + prompt


def _v54_walk_mcqs(node, material_language):
    if isinstance(node, dict):
        _v54_repair_mcq_entailment(node, material_language)
        for value in node.values():
            if isinstance(value, (dict, list)):
                _v54_walk_mcqs(value, material_language)
    elif isinstance(node, list):
        for value in node:
            _v54_walk_mcqs(value, material_language)


def enforce_material_integrity(data, language=None, material_language="tr"):
    out = _v54_previous_integrity(data, language=language, material_language=material_language)
    if not isinstance(out, dict):
        return out
    # Prefer omission to invented facts. A weak MCQ is less valuable than no MCQ.
    _v54_prune_unsafe_mcqs(out, material_language)
    phonetics = {}
    _v54_collect_authoritative_phonetics(out, phonetics)
    if phonetics:
        _v54_sync_prose_phonetics(out, phonetics)
    _v54_walk_mcqs(out, material_language)
    return out
'''
    guard_path.write_text(guard, encoding="utf-8")

engine = engine_path.read_text(encoding="utf-8")
if "AULAAI_GRAPHEME_PHONETICS_V54" not in engine:
    anchors = [
        "- When pronunciation is pedagogically required or a pronunciation column exists, `phonetic` must be populated and is authoritative. Never duplicate or contradict pronunciation inside meaning/translation/gloss.",
        "- When pronunciation is pedagogically required or a pronunciation column exists, `phonetic` must be populated and authoritative. Never duplicate or contradict it inside meaning/translation/gloss.",
    ]
    anchor = next((a for a in anchors if a in engine), None)
    grapheme_rule = "- AULAAI_GRAPHEME_PHONETICS_V54: For alphabet/script/grapheme inventory rows, `phonetic` means BASIC SOUND VALUE(S) IN STANDARD IPA, not the spoken name of the letter and not a transliteration. If a grapheme has context-dependent core realizations, include the defensible main IPA values separated by ` / ` and explain the conditioning briefly in the meaning/explanation field; never pretend a context-sensitive grapheme has one invariant sound. Non-sounding signs/markers must not receive invented IPA."
    if anchor is None:
        heading = "2. PRONUNCIATION — ONE AUTHORITATIVE SYSTEM"
        pos = engine.find(heading)
        if pos < 0:
            raise RuntimeError("v54 pronunciation section missing")
        line_end = engine.find("\n", pos)
        engine = engine[:line_end] + "\n" + grapheme_rule + engine[line_end:]
    else:
        engine = engine.replace(anchor, anchor + "\n" + grapheme_rule, 1)

    final_marker = "If no, rewrite it now."
    omission_rule = " If an MCQ would require inferring gender, nationality, profession, language ability, ethnicity, relationship, or another identity fact from a name, birthplace, residence, workplace, or stereotype, discard that candidate and generate a different question; omission is preferable to an unsupported inference."
    if omission_rule.strip() not in engine and final_marker in engine:
        engine = engine.replace(final_marker, final_marker + omission_rule, 1)
    engine_path.write_text(engine, encoding="utf-8")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    renderer += r'''

# AULAAI_RELEASE_HARDENING_V54
_v54_previous_localized_title = _localized_title


def _localized_title(title, is_tr, content=None, title_maps=None, explicit_title_tr=None):
    value = _v54_previous_localized_title(title, is_tr, content, title_maps, explicit_title_tr)
    try:
        return _v52_meta(value, "tr" if is_tr else "en")
    except Exception:
        return value


def _v54_is_grapheme_inventory(items):
    """Detect alphabet/script inventory tables structurally, without language names."""
    if not isinstance(items, list) or len(items) < 5:
        return False
    compact = 0
    paired = 0
    usable = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or item.get("word") or "").strip()
        if not term:
            continue
        usable += 1
        tokens = [t for t in term.split() if t]
        chars = "".join(tokens)
        if 1 <= len(chars) <= 4:
            compact += 1
        if len(tokens) == 2 and len(tokens[0]) == 1 and len(tokens[1]) == 1 and tokens[0].casefold() == tokens[1].casefold():
            paired += 1
    if usable < 5:
        return False
    return (compact / usable) >= 0.75 and ((paired / usable) >= 0.30 or usable >= 15)


def _v54_display_phonetic(value):
    text = str(value or "").strip()
    if not text:
        return ""
    parts = [p.strip() for p in text.split("/")]
    if len(parts) > 1:
        return " / ".join(p if (p.startswith("[") and p.endswith("]")) else f"[{p}]" for p in parts if p)
    return text if (text.startswith("[") and text.endswith("]")) else f"[{text}]"


def _v54_instructional(value, is_tr):
    try:
        return _v52_meta(value, "tr" if is_tr else "en")
    except Exception:
        return value


def _v54_pdf_unsafe_mcq(page, prompt, is_tr):
    if not isinstance(page, dict):
        return False
    explanation = page.get("explanation_tr") if is_tr else page.get("explanation_en")
    explanation = explanation or page.get("explanation") or ""
    def fold(text):
        import unicodedata
        t = unicodedata.normalize("NFD", str(text or "")).casefold()
        return "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    p, e = fold(prompt), fold(explanation)
    explicit_gender = bool(re.search(r"\b(kadin|erkek|disil|eril|female|male|woman|man)\b", p))
    if bool(re.search(r"\b(isim|adi|adinin|name)\b", e)) and bool(re.search(r"\b(kadin|erkek|disil|eril|female|male|woman|man)\b", e)) and not explicit_gender:
        return True
    bio = any(x in p for x in ("dogdu", "dogmus", "yasiyor", "yasadi", "calisiyor", "born", "lives", "works", "resides", "родил", "жив", "работ", "nacio", "vive", "trabaja", "geboren", "lebt", "arbeitet", "habite", "travaille"))
    identity = bool(re.search(r"\b(milliyet|uyruk|nationality|national|dil|konus|language|speak|speaks|spoken|meslek|profession|occupation|job)\b", e))
    return bio and identity
'''

    # Comparison targets were one of the last renderer paths bypassing the
    # instructional-language sanitizer (e.g. masculine/feminine, nominative/accusative).
    renderer = renderer.replace(
        "        target = cmp.get('target') or ''",
        "        target = _v54_instructional(cmp.get('target') or '', is_tr)",
        1,
    )

    # Always present the dedicated phonetic field consistently as bracketed IPA.
    renderer = renderer.replace(
        "                            phon = item.get('phonetic') or item.get('pronunciation') or ''",
        "                            phon = _v54_display_phonetic(item.get('phonetic') or item.get('pronunciation') or '')",
        1,
    )

    # Structural alphabet header relabel. Match only the stable first two header
    # lines so earlier localization patches may freely alter later columns.
    short_headers = """                        headers = (
                            'Terim / Kelime' if is_tr else 'Term / Word',
                            'Telaffuz' if is_tr else 'Phonetic',"""
    short_headers_new = """                        is_grapheme_inventory = _v54_is_grapheme_inventory(items)
                        headers = (
                            ('Harf / İşaret' if is_tr else 'Letter / Sign') if is_grapheme_inventory else ('Terim / Kelime' if is_tr else 'Term / Word'),
                            ('Temel Ses (IPA)' if is_tr else 'Basic Sound (IPA)') if is_grapheme_inventory else ('Telaffuz' if is_tr else 'Phonetic'),"""
    if short_headers in renderer:
        renderer = renderer.replace(short_headers, short_headers_new, 1)
    else:
        print("V54: alphabet header relabel unavailable; continuing without publication failure")

    # Legacy/persisted material may bypass generation-time guard. Publication gets
    # the same high-precision crop: omit unsupported identity MCQs rather than print
    # a fabricated premise. Answer-key numbering remains consistent because skipped
    # questions never increment question_counter or append to answers.
    mcq_anchor = """                        prompt = _mcq_prompt(page, is_tr)
                        if not prompt:
                            continue
                        question_counter += 1"""
    mcq_new = """                        prompt = _mcq_prompt(page, is_tr)
                        if not prompt:
                            continue
                        if _v54_pdf_unsafe_mcq(page, prompt, is_tr):
                            last_mcq_section = None
                            continue
                        question_counter += 1"""
    if mcq_anchor not in renderer:
        raise RuntimeError("v54 MCQ publication anchor missing")
    renderer = renderer.replace(mcq_anchor, mcq_new, 1)

    renderer_path.write_text(renderer, encoding="utf-8")

print("Applied v54 realistic hardening: unsafe MCQs pruned, IPA display normalized, instructional leakage closed")
