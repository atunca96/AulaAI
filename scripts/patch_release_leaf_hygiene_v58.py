from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
renderer_path = ROOT / "services" / "pdf_renderer_v12.py"
TAG = "# AULAAI_RELEASE_LEAF_HYGIENE_V58"

guard = guard_path.read_text(encoding="utf-8")
if "# AULAAI_RELEASE_PRONUNCIATION_V57" not in guard:
    raise RuntimeError("v57 pronunciation layer must be applied before v58 leaf hygiene")

if TAG not in guard:
    guard += r'''

# AULAAI_RELEASE_LEAF_HYGIENE_V58
# Structure-preserving publication cleanup only: no pruning, no semantic guesses.
from services.publication_leaf_sanitizer import sanitize_publication_leaves as _v58_sanitize_leaves

_v58_previous_integrity = enforce_material_integrity

def enforce_material_integrity(data, language=None, material_language="tr"):
    out = _v58_previous_integrity(data, language=language, material_language=material_language)
    return _v58_sanitize_leaves(out, language or "", material_language or "")
'''
    guard_path.write_text(guard, encoding="utf-8")

renderer = renderer_path.read_text(encoding="utf-8")
if TAG not in renderer:
    renderer += r'''

# AULAAI_RELEASE_LEAF_HYGIENE_V58
# Export-time safety for already persisted material. Renderer does not reliably
# expose the instructional locale here, so only target-language/phonetic hygiene
# runs at this boundary; instructional-label localization stays in integrity.
from services.publication_leaf_sanitizer import sanitize_publication_leaves as _v58_render_sanitize
_v58_previous_normalize_content = _normalize_content

def _normalize_content(raw, language=None):
    normalized = _v58_previous_normalize_content(raw, language)
    if isinstance(normalized, dict) and language:
        return _v58_render_sanitize(normalized, language, "")
    return normalized
'''
    renderer_path.write_text(renderer, encoding="utf-8")

print("Applied v58 leaf-only publication hygiene: no pruning, no semantic guessing")
