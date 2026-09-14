from pathlib import Path

path = Path(__file__).resolve().parent / "patch_release_final_v57.py"
text = path.read_text(encoding="utf-8")
text = text.replace("_v57r_re.subn(", "__import__('re').subn(")
text = text.replace(
    "isim|adi|adinin|name",
    "isim|ismi|adi|adinin|name",
)
path.write_text(text, encoding="utf-8")
print("Applied v57 build compatibility + Turkish name-gender matcher fix")
