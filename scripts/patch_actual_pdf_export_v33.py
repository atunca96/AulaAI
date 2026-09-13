from pathlib import Path

p = Path(__file__).resolve().parents[1] / "server.py"
s = p.read_text(encoding="utf-8")

start_marker = "    def _export_course_pdf(self, course_id):\n"
end_marker = "    def _wipe_curriculum(self):\n"
if start_marker not in s or end_marker not in s:
    raise RuntimeError("v33 actual PDF export function anchors missing")

before, rest = s.split(start_marker, 1)
body, after = rest.split(end_marker, 1)

# This script intentionally touches ONLY the actual /api/courses/{id}/export-pdf
# implementation. It does not change generation, material JSON, or other renderers.

helper = '''
        def _pdf_export_language_name(value, turkish):
            raw = str(value or "").strip()
            key = raw.casefold()
            aliases = {
                "english": "english", "ingilizce": "english", "i̇ngilizce": "english",
                "german": "german", "deutsch": "german", "almanca": "german",
                "spanish": "spanish", "español": "spanish", "ispanyolca": "spanish",
                "french": "french", "français": "french", "francais": "french", "fransızca": "french",
                "italian": "italian", "italiano": "italian", "italyanca": "italian",
                "portuguese": "portuguese", "português": "portuguese", "portugues": "portuguese", "portekizce": "portuguese",
                "russian": "russian", "русский": "russian", "rusça": "russian",
                "chinese": "chinese", "中文": "chinese", "çince": "chinese",
                "japanese": "japanese", "日本語": "japanese", "japonca": "japanese",
                "arabic": "arabic", "العربية": "arabic", "arapça": "arabic",
                "turkish": "turkish", "türkçe": "turkish", "turkce": "turkish",
                "dutch": "dutch", "nederlands": "dutch", "hollandaca": "dutch", "felemenkçe": "dutch", "flemenkçe": "dutch",
                "swedish": "swedish", "svenska": "swedish", "isveççe": "swedish",
                "korean": "korean", "한국어": "korean", "korece": "korean",
                "greek": "greek", "ελληνικά": "greek", "yunanca": "greek",
            }
            canonical = aliases.get(key, key)
            tr_names = {
                "english": "İngilizce", "german": "Almanca", "spanish": "İspanyolca",
                "french": "Fransızca", "italian": "İtalyanca", "portuguese": "Portekizce",
                "russian": "Rusça", "chinese": "Çince", "japanese": "Japonca",
                "arabic": "Arapça", "turkish": "Türkçe", "dutch": "Hollandaca",
                "swedish": "İsveççe", "korean": "Korece", "greek": "Yunanca",
            }
            en_names = {
                "english": "English", "german": "German", "spanish": "Spanish",
                "french": "French", "italian": "Italian", "portuguese": "Portuguese",
                "russian": "Russian", "chinese": "Chinese", "japanese": "Japanese",
                "arabic": "Arabic", "turkish": "Turkish", "dutch": "Dutch",
                "swedish": "Swedish", "korean": "Korean", "greek": "Greek",
            }
            return (tr_names if turkish else en_names).get(canonical, raw or ("Hedef Dil" if turkish else "Target Language"))
'''

if "def _pdf_export_language_name(" not in body:
    anchor = '        is_tr = (lang == "tr")\n'
    if anchor not in body:
        raise RuntimeError("v33 lang/is_tr anchor missing in actual exporter")
    body = body.replace(anchor, anchor + helper + '        level_word = "Seviye" if is_tr else "Level"\n', 1)
elif 'level_word = "Seviye" if is_tr else "Level"' not in body:
    anchor = '        is_tr = (lang == "tr")\n'
    body = body.replace(anchor, anchor + '        level_word = "Seviye" if is_tr else "Level"\n', 1)

# Normalize the cover subtitle line by semantic role, irrespective of earlier build patches.
lines = body.splitlines(keepends=True)
cover_hits = 0
header_hits = 0
for idx, line in enumerate(lines):
    if 'cover-sub' in line and 'course_lang' in line:
        indent = line[:len(line) - len(line.lstrip())]
        lines[idx] = indent + "f'<div class=\"cover-sub\">{E(_pdf_export_language_name(course_lang, is_tr))} &middot; {level_word} {E(course_level)}{sem_str}</div>'\n"
        cover_hits += 1
    if line.lstrip().startswith('h_ex') and '=' in line:
        indent = line[:len(line) - len(line.lstrip())]
        lines[idx] = indent + 'h_ex    = f"{_pdf_export_language_name(course_lang, True)} Örnek" if is_tr else f"{_pdf_export_language_name(course_lang, False)} Example"\n'
        header_hits += 1
body = ''.join(lines)

if cover_hits != 1:
    raise RuntimeError(f"v33 expected exactly one actual cover subtitle, found {cover_hits}")
if header_hits != 1:
    raise RuntimeError(f"v33 expected exactly one actual vocabulary example header, found {header_hits}")

# Localize the footer in the ACTUAL fitz export loop.
pg_anchor = '                pg_word = "Sayfa" if is_tr else "Page"\n'
footer_assign = '                footer_text = "AulaAI Eğitim Sistemi · Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System · Self-Contained Course Material"\n'
if footer_assign not in body:
    if pg_anchor not in body:
        raise RuntimeError("v33 page/footer anchor missing in actual exporter")
    body = body.replace(pg_anchor, pg_anchor + footer_assign, 1)

lines = body.splitlines(keepends=True)
footer_literal_hits = 0
for idx, line in enumerate(lines):
    if "AulaAI Educational System" in line and "footer_text =" not in line:
        # The actual exporter writes the footer as a standalone argument line.
        if line.strip().startswith(('"AulaAI Educational System', "'AulaAI Educational System")):
            indent = line[:len(line) - len(line.lstrip())]
            lines[idx] = indent + "footer_text,\n"
            footer_literal_hits += 1
body = ''.join(lines)

# End-state verification is deliberately scoped to this one function.
required = {
    "localized language helper": "def _pdf_export_language_name(" in body,
    "localized cover": "E(_pdf_export_language_name(course_lang, is_tr))" in body,
    "localized level label": 'level_word = "Seviye" if is_tr else "Level"' in body,
    "dynamic target-language column": '_pdf_export_language_name(course_lang, True)} Örnek' in body,
    "localized footer": "AulaAI Eğitim Sistemi · Bağımsız Ders Materyali" in body,
    "footer variable used": "footer_text," in body,
}
missing = [name for name, ok in required.items() if not ok]
if missing:
    raise RuntimeError("v33 actual PDF export localization incomplete: " + ", ".join(missing))

# Prove the stale user-visible forms cannot survive inside the real exporter.
if '>{E(course_lang)} &middot;' in body:
    raise RuntimeError("v33 stale raw course language remains in actual cover")
if 'Hedef Dilde Örnek' in body:
    raise RuntimeError("v33 stale generic target-language table header remains in actual exporter")

s = before + start_marker + body + end_marker + after
p.write_text(s, encoding="utf-8")
print(f"Applied v33: root-fixed actual course PDF exporter (footer replacements={footer_literal_hits})")
