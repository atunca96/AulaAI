from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "pdf_academic_renderer.py"
s = p.read_text(encoding="utf-8")

helper = '\ndef _target_language_label(course_lang: str, is_tr: bool) -> str:\n    raw = str(course_lang or "").strip()\n    key = raw.casefold()\n    aliases = {\n        "spanish": "spanish", "ispanyolca": "spanish", "español": "spanish",\n        "german": "german", "almanca": "german", "deutsch": "german",\n        "french": "french", "fransızca": "french", "francais": "french", "français": "french",\n        "italian": "italian", "italyanca": "italian", "italiano": "italian",\n        "portuguese": "portuguese", "portekizce": "portuguese", "português": "portuguese", "portugues": "portuguese",\n        "russian": "russian", "rusça": "russian", "русский": "russian",\n        "chinese": "chinese", "çince": "chinese", "中文": "chinese",\n        "japanese": "japanese", "japonca": "japanese", "日本語": "japanese",\n        "arabic": "arabic", "arapça": "arabic", "العربية": "arabic",\n        "turkish": "turkish", "türkçe": "turkish", "turkce": "turkish",\n        "dutch": "dutch", "hollandaca": "dutch", "nederlands": "dutch",\n        "swedish": "swedish", "isveççe": "swedish", "svenska": "swedish",\n        "korean": "korean", "korece": "korean", "한국어": "korean",\n        "greek": "greek", "yunanca": "greek", "ελληνικά": "greek",\n        "english": "english", "ingilizce": "english", "i̇ngilizce": "english",\n    }\n    canonical = aliases.get(key, key)\n    tr = {\n        "spanish": "İspanyolca", "german": "Almanca", "french": "Fransızca",\n        "italian": "İtalyanca", "portuguese": "Portekizce", "russian": "Rusça",\n        "chinese": "Çince", "japanese": "Japonca", "arabic": "Arapça",\n        "turkish": "Türkçe", "dutch": "Hollandaca", "swedish": "İsveççe",\n        "korean": "Korece", "greek": "Yunanca", "english": "İngilizce",\n    }\n    en = {\n        "spanish": "Spanish", "german": "German", "french": "French",\n        "italian": "Italian", "portuguese": "Portuguese", "russian": "Russian",\n        "chinese": "Chinese", "japanese": "Japanese", "arabic": "Arabic",\n        "turkish": "Turkish", "dutch": "Dutch", "swedish": "Swedish",\n        "korean": "Korean", "greek": "Greek", "english": "English",\n    }\n    return (tr if is_tr else en).get(canonical, raw or ("Hedef Dil" if is_tr else "Target Language"))\n'

if "def _target_language_label(" not in s:
    anchor = "\ndef _e(value):\n"
    if anchor in s:
        s = s.replace(anchor, "\n" + helper + anchor, 1)
    else:
        print("v28: helper anchor unavailable")

labels_to_add = {
    "alphabet": ("Alphabet", "Alfabe"),
    "practice": ("Practice", "Alıştırma"),
    "examples": ("Examples", "Örnekler"),
    "overview": ("Overview", "Genel Bakış"),
    "mcq": ("Quick Check", "Hızlı Değerlendirme"),
}
for key, pair in labels_to_add.items():
    line = f"    '{key}': ('{pair[0]}', '{pair[1]}'),\n"
    if line not in s:
        marker = "    'phonetics': ('Phonetics', 'Fonetik'),\n"
        if marker in s:
            s = s.replace(marker, marker + line, 1)

old_header = "'Hedef Dilde Örnek' if is_tr else 'Target-Language Example'"
new_header = "(f'{_target_language_label(course_lang, True)} Örnek' if is_tr else f'{_target_language_label(course_lang, False)} Example')"
if old_header in s:
    s = s.replace(old_header, new_header, 1)

old_cover = "f'<div class=\"cover-sub\">{_e(course_lang)} · {level_word} {_e(course_level)}{sem}</div>'"
new_cover = "f'<div class=\"cover-sub\">{_e(_target_language_label(course_lang, is_tr))} · {level_word} {_e(course_level)}{sem}</div>'"
if old_cover in s:
    s = s.replace(old_cover, new_cover, 1)

s = s.replace("    cont = '<div class=\"cont\">devam</div>' if continued else ''\n", "    cont = ''\n", 1)

page_word_line = "        page_word = 'Sayfa' if self.is_tr else 'Page'\n"
footer_line = "        footer_text = 'AulaAI Eğitim Sistemi · Kapsamlı Ders Materyali' if self.is_tr else 'AulaAI Educational System · Self-Contained Course Material'\n"
if footer_line not in s and page_word_line in s:
    s = s.replace(page_word_line, page_word_line + footer_line, 1)
s = s.replace(
    "            page.insert_text(fitz.Point(38, 823), 'AulaAI Educational System · Self-Contained Course Material', fontsize=6.7, color=(0.42, 0.42, 0.42))",
    "            page.insert_text(fitz.Point(38, 823), footer_text, fontsize=6.7, color=(0.42, 0.42, 0.42))",
    1,
)

p.write_text(s, encoding="utf-8")
print("Applied v28: deterministic PDF localization and actual target-language headings")