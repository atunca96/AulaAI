from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"
TAG = "# AULAAI_RELEASE_FINAL_V58"


def _append_guard():
    guard = guard_path.read_text(encoding="utf-8")
    if TAG in guard:
        return
    guard += r'''

# AULAAI_RELEASE_FINAL_V58
# Zero-LLM, zero-retry final publication cleanup for mechanically provable
# residue. Russian-specific factual repairs are exact/high-confidence and run
# only for confirmed Russian target-language material.
import re as _v58_re


def _v58_is_russian(language):
    value = str(language or "").casefold()
    return "russian" in value or "rusça" in value or "рус" in value


def _v58_is_turkish(material_language):
    return str(material_language or "").casefold() in {"tr", "turkish", "türkçe", "turkce"}


def _v58_turkish_publication_text(value, russian=False):
    if not isinstance(value, str) or not value:
        return value
    text = value

    # Publication corruption observed in learner-facing Turkish prose.
    text = text.replace("canl具合", "canlılık")

    # Remove residual foreign metalanguage where the Turkish term is already
    # present or can be expressed without ambiguity.
    text = _v58_re.sub(r"(?i)tanımlık\s*\(\s*harf-i\s+tarif\s*/\s*article\s*\)", "tanımlık", text)
    text = _v58_re.sub(r"(?i)tamlayan\s+çoğul\s*\(\s*Genitivus\s+pluralis\s*\)\s+h[âa]li", "tamlayan çoğul hâli", text)
    text = _v58_re.sub(r"(?i)\bGenitivus\s+pluralis\b", "tamlayan çoğul", text)

    if russian:
        # Russian has 10 vowel letters. Й is not one of them. Correct only the
        # explicit 10-vowel inventory sentence, preserving every other list.
        text = _v58_re.sub(
            r"10\s+sesli\s+harf\s*\(\s*а\s*,\s*е\s*,\s*ё\s*,\s*и\s*,\s*й\s*,\s*о\s*,\s*у\s*,\s*ы\s*,\s*э\s*,\s*ю\s*,\s*я\s*\)",
            "10 sesli harf (а, е, ё, и, о, у, ы, э, ю, я)",
            text,
            flags=_v58_re.IGNORECASE,
        )

        # 11 is the exception: оди́ннадцать is stressed on -дин-, while 12–19
        # take stress on -на-. Replace only the known over-generalized claim.
        text = _v58_re.sub(
            r"11\s+ile\s+19\s+arasındaki\s+sayılar\s+düzenli\s+olarak\s+-надцать\s+ile\s+biter\s+ve\s+vurgu\s+daima\s+-дцать\s+ekinden\s+önceki\s+heceye\s*\(-на-\)\s+düşer\.?",
            "11–19 arasındaki sayılar -надцать ile biter. 12–19 arasındaki sayılarda vurgu -на- hecesine düşer; одиннадцать sözcüğünde ise vurgu -дин- hecesindedir.",
            text,
            flags=_v58_re.IGNORECASE,
        )
    return text


def _v58_clean_tree(node, russian=False, turkish=True):
    if isinstance(node, str):
        return _v58_turkish_publication_text(node, russian=russian) if turkish else node
    if isinstance(node, list):
        return [_v58_clean_tree(v, russian=russian, turkish=turkish) for v in node]
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            # Only learner-facing Turkish/unqualified instructional strings are
            # normalized. Explicit target-language fields stay untouched.
            k = str(key)
            target_only = k in {"term", "word", "target", "example", "sentence", "answer", "expression", "phrase", "native"}
            child_turkish = turkish and not target_only and not k.endswith("_en")
            out[key] = _v58_clean_tree(value, russian=russian, turkish=child_turkish)
        return out
    return node


_v58_previous_integrity = enforce_material_integrity

def enforce_material_integrity(data, language=None, material_language="tr"):
    out = _v58_previous_integrity(data, language=language, material_language=material_language)
    if not isinstance(out, dict):
        return out
    if not _v58_is_turkish(material_language):
        return out
    return _v58_clean_tree(out, russian=_v58_is_russian(language), turkish=True)
'''
    guard_path.write_text(guard, encoding="utf-8")


def _append_renderer():
    renderer = renderer_path.read_text(encoding="utf-8")
    if TAG in renderer:
        return
    renderer += r'''

# AULAAI_RELEASE_FINAL_V58
from services.material_quality_guard import _v58_clean_tree as _v58_publication_clean_tree
from services.material_quality_guard import _v58_is_russian as _v58_publication_is_russian

_v58_previous_normalize_content = _normalize_content

def _normalize_content(raw, language=None):
    normalized = _v58_previous_normalize_content(raw, language) if language is not None else _v58_previous_normalize_content(raw)
    if isinstance(normalized, dict):
        return _v58_publication_clean_tree(
            normalized,
            russian=_v58_publication_is_russian(language or ""),
            turkish=True,
        )
    return normalized
'''

    # Ensure render_course_pdf passes course_lang through this final boundary.
    renderer = renderer.replace(
        "                content = _normalize_content(top_content)\n",
        "                content = _normalize_content(top_content, course_lang)\n",
        1,
    )
    renderer_path.write_text(renderer, encoding="utf-8")


_append_guard()
_append_renderer()
print("Applied v58 zero-cost final factual/publication cleanup")
