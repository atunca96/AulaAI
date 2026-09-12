from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'services' / 'pdf_academic_renderer.py'
s = p.read_text(encoding='utf-8')

helper = r'''

def _target_language_label(course_lang: str, is_tr: bool) -> str:
    """Return the actual course language name for PDF vocabulary table headers."""
    raw = str(course_lang or '').strip()
    key = raw.casefold()

    aliases = {
        'spanish': 'spanish', 'ispanyolca': 'spanish', 'español': 'spanish',
        'german': 'german', 'almanca': 'german', 'deutsch': 'german',
        'french': 'french', 'fransızca': 'french', 'francais': 'french', 'français': 'french',
        'italian': 'italian', 'italyanca': 'italian', 'italiano': 'italian',
        'portuguese': 'portuguese', 'portekizce': 'portuguese', 'português': 'portuguese', 'portugues': 'portuguese',
        'russian': 'russian', 'rusça': 'russian', 'русский': 'russian',
        'chinese': 'chinese', 'çince': 'chinese', '中文': 'chinese',
        'japanese': 'japanese', 'japonca': 'japanese', '日本語': 'japanese',
        'arabic': 'arabic', 'arapça': 'arabic', 'العربية': 'arabic',
        'turkish': 'turkish', 'türkçe': 'turkish', 'turkce': 'turkish',
        'dutch': 'dutch', 'hollandaca': 'dutch', 'nederlands': 'dutch',
        'swedish': 'swedish', 'isveççe': 'swedish', 'svenska': 'swedish',
        'korean': 'korean', 'korece': 'korean', '한국어': 'korean',
        'greek': 'greek', 'yunanca': 'greek', 'ελληνικά': 'greek',
        'english': 'english', 'ingilizce': 'english', 'İngilizce': 'english',
    }
    canonical = aliases.get(key, key)

    tr = {
        'spanish': 'İspanyolca', 'german': 'Almanca', 'french': 'Fransızca',
        'italian': 'İtalyanca', 'portuguese': 'Portekizce', 'russian': 'Rusça',
        'chinese': 'Çince', 'japanese': 'Japonca', 'arabic': 'Arapça',
        'turkish': 'Türkçe', 'dutch': 'Hollandaca', 'swedish': 'İsveççe',
        'korean': 'Korece', 'greek': 'Yunanca', 'english': 'İngilizce',
    }
    en = {
        'spanish': 'Spanish', 'german': 'German', 'french': 'French',
        'italian': 'Italian', 'portuguese': 'Portuguese', 'russian': 'Russian',
        'chinese': 'Chinese', 'japanese': 'Japanese', 'arabic': 'Arabic',
        'turkish': 'Turkish', 'dutch': 'Dutch', 'swedish': 'Swedish',
        'korean': 'Korean', 'greek': 'Greek', 'english': 'English',
    }
    mapping = tr if is_tr else en
    return mapping.get(canonical, raw or ('Hedef Dil' if is_tr else 'Target Language'))
'''

if 'def _target_language_label(' not in s:
    anchor = '\ndef render_course_pdf(course_id: str, lang: str = \'en\') -> Tuple[bytes, str]:\n'
    if anchor in s:
        s = s.replace(anchor, helper + anchor, 1)

old = "                            'Hedef Dilde Örnek' if is_tr else 'Target-Language Example',"
new = "                            (f'{_target_language_label(course_lang, True)} Örnek' if is_tr else f'{_target_language_label(course_lang, False)} Example'),"
if old in s:
    s = s.replace(old, new, 1)

p.write_text(s, encoding='utf-8')
print('Applied v25: vocabulary tables show the actual course language name')
