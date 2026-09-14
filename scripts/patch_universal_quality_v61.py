from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
TAG = "# AULAAI_UNIVERSAL_QUALITY_V61"

guard = guard_path.read_text(encoding="utf-8")
if "# AULAAI_MCQ_LEXICAL_ANCHOR_V59" not in guard:
    raise RuntimeError("v59 MCQ guard must be applied before v61")

if TAG not in guard:
    guard += r'''

# AULAAI_UNIVERSAL_QUALITY_V61
# High-confidence assessment cleanliness only. This wrapper can reject only an
# MCQ page; it never mutates or deletes substantive teaching pages.
import re as _v61_re

_V61_ENGLISH_PROSE = _v61_re.compile(
    r"\b(?:it is|it changes|it is pronounced|completely silent|because|before the stress|full,? long|sound)\b",
    _v61_re.I,
)
_V61_NONLATIN = _v61_re.compile(r"[\u0400-\u052f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\u0600-\u06ff\u0370-\u03ff]")
_V61_ASCII_OPTION = _v61_re.compile(r"^[A-Za-z][A-Za-z '\-]*$")


def _v61_text(page, *keys):
    parts = []
    for key in keys:
        value = page.get(key) if isinstance(page, dict) else None
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return " ".join(parts)


def _v61_options(page):
    options = page.get("options") or page.get("choices") or [] if isinstance(page, dict) else []
    return options if isinstance(options, list) else []


def _v61_instructional_option_leak(page, material_language="tr"):
    if not _v56q_page_is_mcq(page):
        return False
    lang = str(material_language or "").casefold()
    if not (lang in {"tr", "turkish", "türkçe", "turkce"} or "türk" in lang or "turk" in lang):
        return False
    options = _v61_options(page)
    if len(options) != 4 or not all(isinstance(x, str) for x in options):
        return False

    # Clear English explanatory prose inside a Turkish-track MCQ.
    if any(_V61_ENGLISH_PROSE.search(x) for x in options):
        return True

    # Shared options cannot safely represent a semantic translation MCQ for both
    # EN and TR tracks. For non-Latin target anchors + plain Latin semantic words,
    # omit the MCQ rather than publish a locale-dependent choice set.
    prompt_tr = _v61_text(page, "prompt_tr", "question_tr", "stem_tr")
    semantic = any(token in prompt_tr.casefold() for token in ("anlamı nedir", "ne anlama gelir", "türkçe karşılığı", "karşılığı nedir"))
    stem_all = _v61_text(page, "prompt", "prompt_en", "prompt_tr", "question", "question_tr", "stem", "stem_tr")
    if semantic and _V61_NONLATIN.search(stem_all) and all(_V61_ASCII_OPTION.fullmatch(x.strip()) for x in options):
        return True
    return False


_v61_previous_unsafe_mcq = _v56q_unsafe_mcq

def _v56q_unsafe_mcq(page, material_language="tr"):
    if _v61_previous_unsafe_mcq(page, material_language):
        return True
    return _v61_instructional_option_leak(page, material_language)
'''
    guard_path.write_text(guard, encoding="utf-8")

print("Applied v61 universal MCQ cleanliness guard")
