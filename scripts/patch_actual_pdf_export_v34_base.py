from pathlib import Path
import re

p = Path(__file__).resolve().parents[1] / "server.py"
s = p.read_text(encoding="utf-8")

start_marker = "    def _export_course_pdf(self, course_id):\n"
end_marker = "    def _wipe_curriculum(self):\n"
if start_marker not in s or end_marker not in s:
    raise RuntimeError("v34 actual PDF export function anchors missing")

before, rest = s.split(start_marker, 1)
body, after = rest.split(end_marker, 1)

helper = '''
        def _pdf_export_language_name(value, turkish):
            raw = str(value or "").strip()
            key = raw.casefold()
            aliases = {
                "english": "english", "ingilizce": "english", "i̇ngilizce": "english",
                "german": "german", "deutsch": "german", "almanca": "german",
                "spanish": "spanish", "español": "spanish", "ispanyolca": "spanish",
                "french": "french", "français": "french", "fransızca": "french",
                "italian": "italian", "italiano": "italian", "italyanca": "italian",
                "portuguese": "portuguese", "português": "portuguese", "portekizce": "portuguese",
                "russian": "russian", "русский": "russian", "rusça": "russian",
                "chinese": "chinese", "中文": "chinese", "çince": "chinese",
                "japanese": "japanese", "日本語": "japanese", "japonca": "japanese",
                "arabic": "arabic", "العربية": "arabic", "arapça": "arabic",
                "turkish": "turkish", "türkçe": "turkish",
                "dutch": "dutch", "nederlands": "dutch", "hollandaca": "dutch",
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

anchor = '        is_tr = (lang == "tr")\n'
if "def _pdf_export_language_name(" not in body:
    if anchor not in body:
        raise RuntimeError("v34 lang/is_tr anchor missing")
    body = body.replace(anchor, anchor + helper, 1)
if '        level_word = "Seviye" if is_tr else "Level"\n' not in body:
    body = body.replace(anchor, anchor + '        level_word = "Seviye" if is_tr else "Level"\n', 1)

lines = body.splitlines(keepends=True)
for i, line in enumerate(lines):
    stripped = line.lstrip()
    indent = line[:len(line) - len(stripped)]
    if 'cover-sub' in line and 'course_lang' in line:
        lines[i] = indent + "f'<div class=\"cover-sub\">{E(_pdf_export_language_name(course_lang, is_tr))} &middot; {level_word} {E(course_level)}{sem_str}</div>'\n"
    elif re.match(r'^h_ex\s*=', stripped):
        lines[i] = indent + 'h_ex = f"{_pdf_export_language_name(course_lang, True)} Örnek" if is_tr else f"{_pdf_export_language_name(course_lang, False)} Example"\n'
body = ''.join(lines)

pg_anchor = '                pg_word = "Sayfa" if is_tr else "Page"\n'
footer_assign = '                footer_text = "AulaAI Eğitim Sistemi · Bağımsız Ders Materyali" if is_tr else "AulaAI Educational System · Self-Contained Course Material"\n'
if footer_assign not in body:
    if pg_anchor not in body:
        raise RuntimeError("v34 page/footer anchor missing")
    body = body.replace(pg_anchor, pg_anchor + footer_assign, 1)

lines = body.splitlines(keepends=True)
for i, line in enumerate(lines):
    stripped = line.strip()
    if "AulaAI Educational System" in stripped and "footer_text =" not in stripped:
        if stripped.startswith(('"AulaAI Educational System', "'AulaAI Educational System")):
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = indent + "footer_text,\n"
            break
body = ''.join(lines)

required = ["def _pdf_export_language_name(", "E(_pdf_export_language_name(course_lang, is_tr))", "_pdf_export_language_name(course_lang, True)} Örnek", "AulaAI Eğitim Sistemi · Bağımsız Ders Materyali", "footer_text,"]
missing = [x for x in required if x not in body]
if missing:
    raise RuntimeError("v34 actual PDF export localization incomplete: " + ", ".join(missing))

p.write_text(before + start_marker + body + end_marker + after, encoding="utf-8")
print("Applied v34 base PDF export localization")
