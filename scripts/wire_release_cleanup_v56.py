from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'Dockerfile'
s = p.read_text(encoding='utf-8')
anchor = '    && python scripts/test_canonical_material_prompt.py \\\n'
insert = anchor + '    && python scripts/patch_release_cleanup_v56.py \\\n    && python scripts/test_release_cleanup_v56.py \\\n'
if 'patch_release_cleanup_v56.py' not in s:
    if anchor not in s:
        raise RuntimeError('v56 Docker anchor missing')
    s = s.replace(anchor, insert, 1)
    p.write_text(s, encoding='utf-8')
print('Wired v56 release cleanup into Dockerfile')
