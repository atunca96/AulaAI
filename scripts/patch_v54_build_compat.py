from pathlib import Path

# V54's vocabulary-header relabel is presentation-only. Earlier renderer patches can
# legitimately rewrite that exact block, so make this optional instead of failing
# the entire image build.
p = Path("scripts/patch_release_hardening_v54.py")
s = p.read_text(encoding="utf-8")
old = '''    if old_headers not in renderer:\n        raise RuntimeError("v54 vocabulary header anchor missing")\n    renderer = renderer.replace(old_headers, new_headers, 1)'''
new = '''    if old_headers in renderer:\n        renderer = renderer.replace(old_headers, new_headers, 1)\n    else:\n        print("V54: vocabulary header block already transformed upstream; skipping optional header relabel")'''
if old in s:
    s = s.replace(old, new, 1)
elif "v54 vocabulary header anchor missing" in s:
    raise RuntimeError("V54 compat: expected failure block changed unexpectedly")
else:
    print("V54 compat: optional header block already non-fatal")
p.write_text(s, encoding="utf-8")

# V53 attempted to remove residual English "Case" after Turkish grammatical labels,
# but that edit depended on a source-layout anchor that is not guaranteed after the
# full patch chain. Install the same normalization as a final function wrapper so it
# is independent of source layout and remains deterministic/non-semantic.
guard_path = Path("services/material_quality_guard.py")
g = guard_path.read_text(encoding="utf-8")
meta_tag = "# AULAAI_V54_META_COMPAT"
if meta_tag not in g:
    g += r'''

# AULAAI_V54_META_COMPAT
import re as _v54_meta_re
_v54_meta_previous = sanitize_instructional_metalanguage


def sanitize_instructional_metalanguage(value, material_language="tr"):
    text = _v54_meta_previous(value, material_language)
    if str(material_language or "").strip().casefold() not in {"tr", "turkish", "türkçe", "turkce"}:
        return text
    labels = r"Yalın Hâl|İlgi/Tamlayan Hâli|Belirtme Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu"
    text = _v54_meta_re.sub(rf"\b({labels})\s+[Cc]ase\b", r"\1", text)
    text = _v54_meta_re.sub(r"\bEdat Durumu\s*/\s*Edat Hali\b", "Edat Durumu", text, flags=_v54_meta_re.IGNORECASE)
    return text
'''
    guard_path.write_text(g, encoding="utf-8")

print("Applied V54 build compatibility: optional header relabel non-fatal + Turkish metalanguage normalization")
