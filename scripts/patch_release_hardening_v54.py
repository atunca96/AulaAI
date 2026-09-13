from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"
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


def _v54_repair_mcq_entailment(page, material_language):
    if not isinstance(page, dict) or str(page.get("type") or "").casefold() != "mcq":
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
    name_reason = bool(re.search(r"\b(isim|adi|adinin|name)\b", e))
    explicit_gender = bool(re.search(r"\b(kadin|erkek|disil|eril|female|male|woman|man)\b", p))
    if name_reason and (female or male) and not explicit_gender:
        if tr:
            cue = "Bu soruda özne açıkça kadın olarak verilmiştir. " if female else "Bu soruda özne açıkça erkek olarak verilmiştir. "
        else:
            cue = "In this question, the subject is explicitly female. " if female else "In this question, the subject is explicitly male. "
        page[pk] = cue + prompt
        prompt = page[pk]
        p = _v54_fold(prompt)

    biography = bool(re.search(r"\b(dogdu|dogmus|yasiyor|yasadi|calisiyor|calisti|born|lives|lived|works|worked|resides|resided)\b", p))
    nationality = bool(re.search(r"\b(milliyet|uyruk|nationality|national)\b", e))
    language_fact = bool(re.search(r"\b(dil|konus|language|speak|speaks|spoken)\b", e))
    profession = bool(re.search(r"\b(meslek|profession|occupation|job)\b", e))

    if biography and (nationality or language_fact or profession):
        if tr:
            if nationality:
                prefix = "Yalnızca dilbilgisel biçime göre seçiniz: boşlukta cümle yapısına uyan milliyet biçimi gereklidir; ikamet veya doğum yeri milliyeti kanıtlamaz. "
            elif language_fact:
                prefix = "Yalnızca dilbilgisel biçime göre seçiniz: boşlukta konuşulan dili bildiren uygun dil ifadesi gereklidir; doğum veya ikamet yeri dil yeterliliğini kanıtlamaz. "
            else:
                prefix = "Yalnızca dilbilgisel biçime göre seçiniz: boşlukta cümle yapısına uyan meslek ifadesi gereklidir; işyeri veya yaşam yeri mesleği kanıtlamaz. "
            page[ek] = "Doğru seçenek cümlenin dilbilgisel yapısı ve gereken sözcük türü/çekim biçimiyle belirlenir; biyografik bilgiden kimlik sonucu çıkarılmaz."
        else:
            if nationality:
                prefix = "Choose only by grammatical form: the blank requires the nationality form licensed by the sentence; residence or birthplace does not prove nationality. "
            elif language_fact:
                prefix = "Choose only by grammatical form: the blank requires the language expression licensed by the sentence; birthplace or residence does not prove language ability. "
            else:
                prefix = "Choose only by grammatical form: the blank requires the profession expression licensed by the sentence; workplace or residence does not prove profession. "
            page[ek] = "The answer is determined by the sentence grammar and required word class/form; no identity fact is inferred from biography."
        if not _v54_fold(page[pk]).startswith(_v54_fold(prefix)):
            page[pk] = prefix + page[pk]


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
    phonetics = {}
    _v54_collect_authoritative_phonetics(out, phonetics)
    if phonetics:
        _v54_sync_prose_phonetics(out, phonetics)
    _v54_walk_mcqs(out, material_language)
    return out
'''
    guard_path.write_text(guard, encoding="utf-8")

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
'''
    renderer_path.write_text(renderer, encoding="utf-8")

print("Applied v54 structural entailment and phonetic consistency hardening")
