from pathlib import Path
import re

path = Path('services/pdf_academic_renderer.py')
src = path.read_text(encoding='utf-8')

# 1) Never print a visible continuation label between split vocabulary pages.
old_cont = '''def _table_html(headers: Sequence[str], rows: Sequence[str], continued: bool = False) -> str:\n    cont = '<div class="cont">devam</div>' if continued else ''\n    return (\n'''
new_cont = '''def _table_html(headers: Sequence[str], rows: Sequence[str], continued: bool = False) -> str:\n    cont = ''\n    return (\n'''
if src.count(old_cont) != 1:
    raise RuntimeError(f'continuation label anchor matched {src.count(old_cont)} times')
src = src.replace(old_cont, new_cont, 1)

# 2) Turkish PDF headings must reuse the Turkish material already stored in the
# structured content before ever falling back to the English topic title.
pattern = re.compile(
    r'''def _localized_title\(title: str, is_tr: bool, content: Optional\[dict\], title_maps\) -> str:\n'''
    r'''(?:    .*\n)+?'''
    r'''    return title\n''',
    re.MULTILINE,
)
replacement = '''def _localized_title(title: str, is_tr: bool, content: Optional[dict], title_maps) -> str:\n    title = str(title or '').strip()\n    if not is_tr:\n        return title\n\n    # Prefer explicit Turkish topic metadata first.\n    if isinstance(content, dict):\n        candidates = [\n            content.get('title_tr'),\n            content.get('topic_title_tr'),\n            content.get('localized_title_tr'),\n        ]\n        metadata = content.get('metadata')\n        if isinstance(metadata, dict):\n            candidates.extend([\n                metadata.get('title_tr'),\n                metadata.get('topic_title_tr'),\n                metadata.get('localized_title_tr'),\n            ])\n        for value in candidates:\n            if value and str(value).strip():\n                return str(value).strip()\n\n    # Reuse the already-generated Turkish version inside the material pages.\n    # This is intentionally zero-AI: no translation request is made here.\n    if isinstance(content, dict):\n        pages = content.get('pages') or []\n        for page in pages:\n            if not isinstance(page, dict):\n                continue\n            for key in ('topic_title_tr', 'title_tr', 'heading_tr'):\n                value = page.get(key)\n                if value and str(value).strip():\n                    return str(value).strip()\n\n    exact, ci_cache, ci_canonical = title_maps\n    if title in exact and str(exact[title]).strip():\n        return str(exact[title]).strip()\n    key = title.casefold()\n    if key in ci_cache:\n        return ci_cache[key]\n    if key in ci_canonical:\n        return ci_canonical[key]\n    return title\n'''
src2, count = pattern.subn(replacement, src, count=1)
if count != 1:
    raise RuntimeError(f'localized title function matched {count} times')
src = src2

path.write_text(src, encoding='utf-8')
print('Applied academic PDF v4: hidden continuation label + Turkish material heading reuse')
