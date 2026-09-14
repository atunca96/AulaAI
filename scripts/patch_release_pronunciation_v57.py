from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"
TAG = "# AULAAI_RELEASE_PRONUNCIATION_V57"

guard = guard_path.read_text(encoding="utf-8")
if "# AULAAI_RELEASE_CLEANUP_V56_QUALITY" not in guard:
    raise RuntimeError("v56 quality overlay must be applied before v57 pronunciation layer")

if TAG not in guard:
    guard += r'''

# AULAAI_RELEASE_PRONUNCIATION_V57
# Curated pronunciation correction only.  This layer never guesses IPA, never
# deletes an item/page, and never changes prompt/model/retry behavior.
from services.pronunciation_lexicon import apply_canonical_pronunciation_overrides as _v57_apply_pronunciation

_v57_previous_integrity = enforce_material_integrity

def enforce_material_integrity(data, language=None, material_language="tr"):
    out = _v57_previous_integrity(data, language=language, material_language=material_language)
    return _v57_apply_pronunciation(out, language or "")
'''
    guard_path.write_text(guard, encoding="utf-8")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    renderer += r'''

# AULAAI_RELEASE_PRONUNCIATION_V57
# Apply the same exact-match pronunciation overrides at export time so already
# persisted lessons receive the correction without mutating their structure.
from services.pronunciation_lexicon import apply_canonical_pronunciation_overrides as _v57_render_pronunciation
_v57_previous_normalize_content = _normalize_content

def _normalize_content(raw, language=None):
    normalized = _v57_previous_normalize_content(raw, language)
    if isinstance(normalized, dict) and language:
        return _v57_render_pronunciation(normalized, language)
    return normalized
'''
    renderer_path.write_text(renderer, encoding="utf-8")

print("Applied v57 curated pronunciation lexicon: exact-match, leaf-only, zero-LLM")
