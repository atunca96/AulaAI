from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"
engine_path = ROOT / "services" / "ai_engine.py"
TAG = "# AULAAI_RELEASE_HARDENING_V52"

guard = guard_path.read_text(encoding="utf-8")
if TAG not in guard:
    guard += r'''

# AULAAI_RELEASE_HARDENING_V52
_TR_FIXED_META = (
    (r"\bprepositional\b", "Edat Durumu"),
    (r"\bgenitive\b", "İlgi/Tamlayan Hâli"),
    (r"\bnominative\b", "Yalın Hâl"),
    (r"\baccusative\b", "Belirtme Hâli"),
    (r"\bdative\b", "Yönelme Hâli"),
    (r"\binstrumental\b", "Araç Hâli"),
    (r"\bmasculine\b", "eril"),
    (r"\bfeminine\b", "dişil"),
    (r"\bneuter\b", "nötr"),
)


def sanitize_instructional_metalanguage(value, material_language="tr"):
    text = safe_unicode_normalize(str(value or ""))
    if str(material_language or "").strip().casefold() not in {"tr", "turkish", "türkçe", "turkce"}:
        return text
    parts = re.split(r'(`[^`\n]*`|“[^”\n]*”|«[^»\n]*»|"[^"\n]*")', text)
    for i in range(0, len(parts), 2):
        for pattern, replacement in _TR_FIXED_META:
            parts[i] = re.sub(pattern, replacement, parts[i], flags=re.IGNORECASE)
    res = "".join(parts)
    res = re.sub(r"(?i)\bİlgi\s*/\s*İlgi\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", res)
    res = re.sub(r"(?i)\bİlgi\s*/\s*Tamlayan\s*(?:H[âa]li)?\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", res)
    res = re.sub(r"(?i)\b(Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\s*\(\s*\1\s*\)", r"\1", res)
    if re.search(r'(?i)\b(?:ехать|еха[-–—]|ehat|ekhat)\b', res):
        res = re.sub(r'["\'„“]?-д-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", res, flags=re.IGNORECASE)
        res = re.sub(r'["\'„“]?-d-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", res, flags=re.IGNORECASE)
    return res
'''
    guard_path.write_text(guard, encoding="utf-8")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    old = "spk = sanitize_dialogue_speaker(d.get('speaker') or d.get('name') or '?')"
    if old not in renderer:
        raise RuntimeError("v52 speaker anchor missing")
    renderer = renderer.replace(old, "spk = _v52_dialogue_speaker(d, is_tr)", 1)
    renderer += r'''

# AULAAI_RELEASE_HARDENING_V52
from services.material_quality_guard import sanitize_instructional_metalanguage as _v52_meta
_v52_pick = _pick
_v52_mcq_prompt = _mcq_prompt
_v52_vocab_meaning = _vocab_meaning


def _pick(obj, en_key, tr_key, is_tr):
    value = _v52_pick(obj, en_key, tr_key, is_tr)
    return _v52_meta(value, "tr" if is_tr else "en")


def _mcq_prompt(page, is_tr):
    value = _v52_mcq_prompt(page, is_tr)
    return _v52_meta(value, "tr" if is_tr else "en")


def _vocab_meaning(item, is_tr, term, course_lang, memory):
    value = _v52_vocab_meaning(item, is_tr, term, course_lang, memory)
    return _v52_meta(value, "tr" if is_tr else "en")


def _v52_dialogue_speaker(turn, is_tr):
    if not isinstance(turn, dict):
        return "?"
    keys = ("speaker_tr", "name_tr", "speaker", "name") if is_tr else ("speaker_en", "name_en", "speaker", "name")
    value = next((turn.get(k) for k in keys if turn.get(k)), "?")
    return sanitize_dialogue_speaker(value)
'''
    renderer_path.write_text(renderer, encoding="utf-8")

engine = engine_path.read_text(encoding="utf-8")
if TAG not in engine:
    speaker_anchor = "Speaker labels contain only the actual name or the correctly localized role — never `Role (English Role)`, duplicate transliteration, or foreign metadata annotations."
    speaker_new = "Speaker labels contain only the actual name or the correctly localized role. For role/title speakers, emit `speaker_tr` and `speaker_en`; PDF rendering selects the requested locale field. Proper names remain unchanged. Never emit `Role (English Role)`, duplicate transliteration, or foreign metadata annotations."
    if speaker_anchor not in engine:
        raise RuntimeError("v52 speaker contract anchor missing")
    engine = engine.replace(speaker_anchor, speaker_new, 1)
    final_anchor = "If no, rewrite it now. Return valid JSON only."
    final_new = "If no, rewrite it now. A personal name alone is never a sufficient grammatical cue when answer options differ by person-form morphology; place the needed cue explicitly in the stem. Return valid JSON only."
    if final_anchor not in engine:
        raise RuntimeError("v52 final audit anchor missing")
    engine = engine.replace(final_anchor, final_new, 1)
    engine += "\n" + TAG + "\n"
    engine_path.write_text(engine, encoding="utf-8")

print("Applied v52 surgical hardening")
