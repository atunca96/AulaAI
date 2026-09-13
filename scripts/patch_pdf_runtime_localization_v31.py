from pathlib import Path

p = Path(__file__).resolve().parents[1] / "services" / "pdf_academic_renderer.py"
s = p.read_text(encoding="utf-8")

# v25/v26/v28 run before this script and may already have localized the renderer.
# v31 is the final runtime verifier/normalizer, so it must be idempotent and accept
# either the original source or the already-patched source.

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
        "dutch": "Hollandaca", "nederlands": "Hollandaca", "hollandaca": "Hollandaca",
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
        "dutch": "Dutch", "nederlands": "Dutch", "hollandaca": "Dutch",
        "swedish": "Swedish", "svenska": "Swedish", "isveççe": "Swedish",
        "korean": "Korean", "한국어": "Korean", "korece": "Korean",
        "greek": "Greek", "ελληνικά": "Greek", "yunanca": "Greek",
    }
    return (tr if is_tr else en).get(key, raw or ("Hedef Dil" if is_tr else "Target Language"))
'''

# Reuse the older helper if present. Only add v31's helper on an unpatched renderer.
if "def _target_language_label(" not in s and "def _display_language_name(" not in s:
    anchor = "\ndef _table_html(headers: Sequence[str], rows: Sequence[str], continued: bool = False) -> str:\n"
    if anchor not in s:
        raise RuntimeError("v31 renderer helper anchor missing")
    s = s.replace(anchor, helper + anchor, 1)

helper_name = "_target_language_label" if "def _target_language_label(" in s else "_display_language_name"

# Normalize cover subtitle regardless of which earlier patch state we receive.
cover_variants = [
    "f'<div class=\"cover-sub\">{_e(course_lang)} · {level_word} {_e(course_level)}{sem}</div>'",
    "f'<div class=\"cover-sub\">{_e(_display_language_name(course_lang, is_tr))} · {level_word} {_e(course_level)}{sem}</div>'",
]
cover_final = f"f'<div class=\"cover-sub\">{{_e({helper_name}(course_lang, is_tr))}} · {{level_word}} {{_e(course_level)}}{{sem}}</div>'"
for old in cover_variants:
    if old in s:
        s = s.replace(old, cover_final, 1)

# Normalize vocabulary header regardless of v25/v28 already having changed it.
header_variants = [
    "'Hedef Dilde Örnek' if is_tr else 'Target-Language Example',",
    "(f'{_display_language_name(course_lang, True)} Örnek' if is_tr else f'{_display_language_name(course_lang, False)} Example'),",
]
header_final = f"(f'{{{helper_name}(course_lang, True)}} Örnek' if is_tr else f'{{{helper_name}(course_lang, False)}} Example'),"
for old in header_variants:
    if old in s:
        s = s.replace(old, header_final, 1)

# v25/v28 may already have the same final header using _target_language_label.
# No replacement is needed in that case.

# Normalize footer. v28 introduces footer_text; older source writes literal English.
old_literal_footer = "page.insert_text(fitz.Point(38, 823), 'AulaAI Educational System · Self-Contained Course Material', fontsize=6.7, color=(0.42, 0.42, 0.42))"
if old_literal_footer in s:
    s = s.replace(
        old_literal_footer,
        "page.insert_text(fitz.Point(38, 823), ('AulaAI Eğitim Sistemi · Bağımsız Ders Materyali' if self.is_tr else 'AulaAI Educational System · Self-Contained Course Material'), fontsize=6.7, color=(0.42, 0.42, 0.42))",
        1,
    )

s = s.replace(
    "footer_text = 'AulaAI Eğitim Sistemi · Kapsamlı Ders Materyali' if self.is_tr else 'AulaAI Educational System · Self-Contained Course Material'",
    "footer_text = 'AulaAI Eğitim Sistemi · Bağımsız Ders Materyali' if self.is_tr else 'AulaAI Educational System · Self-Contained Course Material'",
    1,
)

# Verify semantic end-state rather than requiring v31-specific strings.
localized_cover_ok = (
    f"{helper_name}(course_lang, is_tr)" in s
    and "cover-sub" in s
)
localized_header_ok = (
    f"{helper_name}(course_lang, True)" in s
    and " Örnek" in s
)
localized_footer_ok = "AulaAI Eğitim Sistemi · Bağımsız Ders Materyali" in s
stale_header_gone = "'Hedef Dilde Örnek' if is_tr" not in s

checks = {
    "language helper": f"def {helper_name}(" in s,
    "localized cover": localized_cover_ok,
    "dynamic table header": localized_header_ok,
    "localized footer": localized_footer_ok,
    "generic Turkish table header removed": stale_header_gone,
}
missing = [name for name, ok in checks.items() if not ok]
if missing:
    raise RuntimeError("v31 runtime renderer localization incomplete: " + ", ".join(missing))

p.write_text(s, encoding="utf-8")
print("Applied v31: verified localization in actual academic PDF renderer")
