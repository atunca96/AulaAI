from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "pdf_academic_renderer.py"
s = p.read_text(encoding="utf-8")

helper = r'''

def _display_language_name(value: str, is_tr: bool) -> str:
    raw = str(value or "").strip()
    key = raw.casefold()
    tr = {
        "english": "İngilizce", "ingilizce": "İngilizce",
        "german": "Almanca", "deutsch": "Almanca", "almanca": "Almanca",
        "spanish": "İspanyolca", "español": "İspanyolca", "ispanyolca": "İspanyolca",
        "french": "Fransızca", "français": "Fransızca", "fransızca": "Fransızca",
        "italian": "İtalyanca", "italiano": "İtalyanca", "italyanca": "İtalyanca",
        "portuguese": "Portekizce", "português": "Portekizce", "portekizce": "Portekizce",
        "russian": "Rusça", "русский": "Rusça", "rusça": "Rusça",
        "chinese": "Çince", "中文": "Çince", "çince": "Çince",
        "japanese": "Japonca", "日本語": "Japonca", "japonca": "Japonca",
        "arabic": "Arapça", "العربية": "Arapça", "arapça": "Arapça",
        "turkish": "Türkçe", "türkçe": "Türkçe",
        "dutch": "Felemenkçe", "nederlands": "Felemenkçe", "flemenkçe": "Felemenkçe", "felemenkçe": "Felemenkçe",
        "swedish": "İsveççe", "svenska": "İsveççe", "isveççe": "İsveççe",
        "korean": "Korece", "한국어": "Korece", "korece": "Korece",
        "greek": "Yunanca", "ελληνικά": "Yunanca", "yunanca": "Yunanca",
    }
    en = {
        "english": "English", "ingilizce": "English",
        "german": "German", "deutsch": "German", "almanca": "German",
        "spanish": "Spanish", "español": "Spanish", "ispanyolca": "Spanish",
        "french": "French", "français": "French", "fransızca": "French",
        "italian": "Italian", "italiano": "Italian", "italyanca": "Italian",
        "portuguese": "Portuguese", "português": "Portuguese", "portekizce": "Portuguese",
        "russian": "Russian", "русский": "Russian", "rusça": "Russian",
        "chinese": "Chinese", "中文": "Chinese", "çince": "Chinese",
        "japanese": "Japanese", "日本語": "Japanese", "japonca": "Japanese",
        "arabic": "Arabic", "العربية": "Arabic", "arapça": "Arabic",
        "turkish": "Turkish", "türkçe": "Turkish",
        "dutch": "Dutch", "nederlands": "Dutch", "flemenkçe": "Dutch", "felemenkçe": "Dutch",
        "swedish": "Swedish", "svenska": "Swedish", "isveççe": "Swedish",
        "korean": "Korean", "한국어": "Korean", "korece": "Korean",
        "greek": "Greek", "ελληνικά": "Greek", "yunanca": "Greek",
    }
    return (tr if is_tr else en).get(key, raw or ("Hedef Dil" if is_tr else "Target Language"))
'''

if "def _display_language_name(" not in s:
    anchor = "\ndef _table_html(headers: Sequence[str], rows: Sequence[str], continued: bool = False) -> str:\n"
    if anchor not in s:
        raise RuntimeError("v31 renderer helper anchor missing")
    s = s.replace(anchor, helper + anchor, 1)

# Footer: localize at the actual renderer that writes final PDF bytes.
old_footer = "page.insert_text(fitz.Point(38, 823), 'AulaAI Educational System · Self-Contained Course Material', fontsize=6.7, color=(0.42, 0.42, 0.42))"
new_footer = "page.insert_text(fitz.Point(38, 823), ('AulaAI Eğitim Sistemi · Bağımsız Ders Materyali' if self.is_tr else 'AulaAI Educational System · Self-Contained Course Material'), fontsize=6.7, color=(0.42, 0.42, 0.42))"
if old_footer in s:
    s = s.replace(old_footer, new_footer, 1)

# Cover subtitle: display the language in the PDF locale rather than DB storage language.
old_cover = "f'<div class=\"cover-sub\">{_e(course_lang)} · {level_word} {_e(course_level)}{sem}</div>'"
new_cover = "f'<div class=\"cover-sub\">{_e(_display_language_name(course_lang, is_tr))} · {level_word} {_e(course_level)}{sem}</div>'"
if old_cover in s:
    s = s.replace(old_cover, new_cover, 1)

# Vocabulary table: use the actual course language name, not a generic placeholder.
old_header = "'Hedef Dilde Örnek' if is_tr else 'Target-Language Example',"
new_header = "(f'{_display_language_name(course_lang, True)} Örnek' if is_tr else f'{_display_language_name(course_lang, False)} Example'),"
if old_header in s:
    s = s.replace(old_header, new_header, 1)

# Fail build if the real renderer still contains the user-visible stale labels.
checks = {
    "language helper": "def _display_language_name(" in s,
    "localized footer": "AulaAI Eğitim Sistemi · Bağımsız Ders Materyali" in s,
    "localized cover": "_display_language_name(course_lang, is_tr)" in s,
    "dynamic table header": "_display_language_name(course_lang, True)" in s,
    "generic Turkish table header removed": "'Hedef Dilde Örnek' if is_tr" not in s,
}
missing = [name for name, ok in checks.items() if not ok]
if missing:
    raise RuntimeError("v31 runtime renderer localization incomplete: " + ", ".join(missing))

p.write_text(s, encoding="utf-8")
print("Applied v31: verified localization in actual academic PDF renderer")
