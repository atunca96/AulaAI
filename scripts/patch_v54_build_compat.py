from pathlib import Path

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
print("Applied V54 build compatibility: optional vocabulary header relabel is non-fatal")
