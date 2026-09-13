from pathlib import Path

path = Path("scripts/patch_release_hardening_v55.py")
s = path.read_text(encoding="utf-8")
old = """    phon_cell = 'f\\'<td><span class=\"phon\">{_e(phon)}</span></td>\\''
    phon_cell_new = 'f\\'<td><span class=\"phon\">{_e(_v55_display_phonetic_cell(phon))}</span></td>\\''
    if phon_cell in renderer:
        renderer = renderer.replace(phon_cell, phon_cell_new, 1)
    elif '_v55_display_phonetic_cell(phon)' not in renderer:
        raise RuntimeError(\"v55 phonetic render-cell anchor missing\")
"""
new = """    phon_cell_new = 'f\\'<td><span class=\"phon\">{_e(_v55_display_phonetic_cell(phon))}</span></td>\\''
    for phon_cell in (
        'f\\'<td><span class=\"phon\">{_e(_v54_display_phonetic(phon))}</span></td>\\'',
        'f\\'<td><span class=\"phon\">{_e(phon)}</span></td>\\'',
    ):
        if phon_cell in renderer:
            renderer = renderer.replace(phon_cell, phon_cell_new, 1)
            break
    if '_v55_display_phonetic_cell(phon)' not in renderer:
        raise RuntimeError(\"v55 phonetic render-cell anchor missing\")
"""
if old not in s:
    raise RuntimeError("v55 compat anchor missing")
path.write_text(s.replace(old, new, 1), encoding="utf-8")
print("Applied v55 build compatibility")
