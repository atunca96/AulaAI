import html
import json
import os
import re
import tempfile
from typing import Dict, List, Optional, Sequence, Tuple

import fitz

from database import db_connection


CSS = r'''
@page { margin: 0; }
body { font-family: sans-serif; font-size: 9pt; color: #1f2937; line-height: 1.34; }
.cover { text-align: center; margin: 4px 0 16px 0; padding-bottom: 11px; border-bottom: 0.8px solid #94a3b8; }
.cover-title { font-size: 20pt; font-weight: 700; margin: 0 0 5px 0; color: #0f172a; }
.cover-sub { font-size: 10.5pt; font-weight: 600; margin: 0 0 3px 0; color: #334155; }
.cover-meta { font-size: 7.4pt; color: #64748b; }
.unit { font-size: 13pt; font-weight: 700; margin: 11px 0 6px 0; padding-bottom: 3px; border-bottom: 0.8px solid #94a3b8; color: #0f172a; }
.topic { font-size: 10.7pt; font-weight: 700; margin: 7px 0 1px 0; color: #0f172a; }
.kind { display: block; font-size: 6.8pt; font-weight: 600; color: #64748b; margin: 0 0 5px 0; }
.sec { font-size: 8.4pt; font-weight: 700; margin: 6px 0 4px 0; color: #334155; }
.p { margin: 0; color: #334155; }
.rule { border-left: 1.3px solid #94a3b8; padding-left: 8px; margin: 0; }
.dialogue { margin: 0; }
.line { margin: 0 0 3px 0; }
.speaker { font-weight: 700; color: #334155; }
.translation { color: #64748b; font-style: italic; }
table.vocab { width: 100%; border-collapse: collapse; margin: 3px 0 0 0; font-size: 7.25pt; }
table.vocab th { text-align: left; font-weight: 700; color: #111827; background: #f1f5f9; border-top: 0.7px solid #94a3b8; border-bottom: 0.7px solid #94a3b8; padding: 3.6px 4.5px; line-height: 1.2; }
table.vocab td { vertical-align: top; border-bottom: 0.35px solid #d1d5db; padding: 3.6px 4.5px; line-height: 1.22; }
table.vocab tr { page-break-inside: avoid; break-inside: avoid; }
.term { font-weight: 700; color: #111827; }
.phon { color: #475569; font-size: 6.9pt; }
.meaning { color: #047857; }
.example { color: #334155; }
.example-tr { color: #64748b; }
.mcq { border: 0.55px solid #cbd5e1; padding: 6px 8px; margin: 0; background: #fff; page-break-inside: avoid; break-inside: avoid; }
.mcq-q { font-weight: 700; margin: 0 0 4px 0; color: #111827; }
.mcq-opt { margin: 1.7px 0; color: #374151; }
.compare { border-top: 0.45px solid #d1d5db; padding-top: 4px; margin-top: 3px; }
.answer { margin: 0 0 4px 0; }
'''

TYPE_LABELS = {
    'vocabulary': ('Vocabulary', 'Kelime Bilgisi'),
    'grammar': ('Grammar', 'Dilbilgisi'),
    'phonetics': ('Phonetics', 'Fonetik'),
    'functional_language': ('Functional Language', 'İşlevsel Dil'),
    'functional': ('Functional', 'İşlevsel Dil'),
    'cultural_context': ('Cultural Context', 'Kültürel Bağlam'),
    'dialogue': ('Dialogue', 'Diyalog'),
    'examples': ('Examples', 'Örnekler'),
    'reading': ('Reading', 'Okuma'),
    'writing': ('Writing', 'Yazma'),
    'listening': ('Listening', 'Dinleme'),
    'speaking': ('Speaking', 'Konuşma'),
}


def _e(value):
    return html.escape(str(value or ''))


def _pick(obj, en_key, tr_key, is_tr):
    if not isinstance(obj, dict):
        return ''
    if is_tr:
        return obj.get(tr_key) or obj.get(en_key) or ''
    return obj.get(en_key) or obj.get(tr_key) or ''


def _kind(kind, is_tr):
    key = str(kind or 'lesson').strip().lower()
    pair = TYPE_LABELS.get(key, (key.replace('_', ' ').title(), key.replace('_', ' ').title()))
    return pair[1] if is_tr else pair[0]


def _load_title_maps():
    cache: Dict[str, str] = {}
    canonical: Dict[str, str] = {}
    try:
        from services.curriculum_translator import load_title_cache, CANONICAL_TITLE_MAP
        cache = load_title_cache() or {}
        canonical = CANONICAL_TITLE_MAP or {}
    except Exception:
        pass
    ci_cache = {str(k).strip().casefold(): str(v).strip() for k, v in cache.items() if k and v}
    ci_canonical = {str(k).strip().casefold(): str(v).strip() for k, v in canonical.items() if k and v}
    return cache, ci_cache, ci_canonical


def _localized_title(title: str, is_tr: bool, content: Optional[dict], title_maps, explicit_tr: str = '') -> str:
    title = str(title or '').strip()
    if not is_tr:
        return title
    if explicit_tr and str(explicit_tr).strip() and str(explicit_tr).strip() != title:
        return str(explicit_tr).strip()
    if isinstance(content, dict):
        metadata = content.get('metadata') if isinstance(content.get('metadata'), dict) else {}
        for value in (
            content.get('topic_title_tr'), content.get('chapter_title_tr'),
            content.get('localized_title_tr'), content.get('title_tr'),
            metadata.get('topic_title_tr'), metadata.get('chapter_title_tr'),
            metadata.get('localized_title_tr'), metadata.get('title_tr'),
        ):
            if value and str(value).strip() and str(value).strip() != title:
                return str(value).strip()
    exact, ci_cache, ci_canonical = title_maps
    if title in exact and str(exact[title]).strip():
        return str(exact[title]).strip()
    folded = title.casefold()
    if folded in ci_cache:
        return ci_cache[folded]
    if folded in ci_canonical:
        return ci_canonical[folded]
    return title


def _column_exists(db, table: str, column: str) -> bool:
    try:
        rows = db.execute(f'PRAGMA table_info({table})').fetchall()
        for row in rows:
            name = row['name'] if hasattr(row, 'keys') else row[1]
            if str(name) == column:
                return True
    except Exception:
        pass
    return False


def _normalize_content(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {'pages': raw}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {'pages': parsed}
        except Exception:
            return {}
    return {}


def _normalize_pages(content):
    if not isinstance(content, dict):
        return []
    pages = content.get('pages') or []
    if isinstance(pages, dict):
        pages = [pages]
    if not isinstance(pages, list):
        return []
    return [p for p in pages if isinstance(p, dict)]


def _infer_page_type(page: dict) -> str:
    ptype = str(page.get('type') or '').strip().lower()
    if page.get('rules') or page.get('rules_tr') or page.get('grammar') or page.get('comparisons'):
        return 'grammar'
    if page.get('items') or page.get('vocabulary') or page.get('words'):
        return 'vocabulary'
    if page.get('dialogue') or page.get('conversations') or page.get('conversation') or page.get('turns') or page.get('lines'):
        return 'examples'
    if page.get('prompt') or page.get('question') or page.get('stem') or page.get('options') or page.get('choices'):
        return 'mcq'
    return ptype


def _norm_key(value: str) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip()).casefold()


def _is_spanish(course_lang: str) -> bool:
    value = _norm_key(course_lang)
    return value in {'es', 'spa', 'spanish', 'español', 'espanol'} or 'spanish' in value or 'españ' in value


def _strict_spanish_letter_key(term: str):
    s = str(term or '').strip()
    if not s:
        return None
    valid = set('ABCDEFGHIJKLMNÑOPQRSTUVWXYZ') | {'CH', 'LL', 'RR'}
    if re.fullmatch(r'[A-ZÑ]{1,2}', s):
        up = s.upper()
        return up if up in valid else None
    m = re.fullmatch(r'([A-Za-zÑñ]{1,2})\s*[,/]\s*([A-Za-zÑñ]{1,2})', s)
    if m:
        left, right = m.group(1).upper(), m.group(2).upper()
        if left == right and left in valid:
            return left
    return None


def _spanish_alphabet_data(term: str, course_lang: str):
    if not _is_spanish(course_lang):
        return None
    key = _strict_spanish_letter_key(term)
    if not key:
        return None
    try:
        from services.bilingual_finisher import SPANISH_ALPHABET_DATA
        return SPANISH_ALPHABET_DATA.get(key)
    except Exception:
        return None


def _alphabet_leak_values(course_lang: str):
    if not _is_spanish(course_lang):
        return set()
    try:
        from services.bilingual_finisher import SPANISH_ALPHABET_DATA
        values = set()
        for data in SPANISH_ALPHABET_DATA.values():
            for key in ('spelling', 'name_tr', 'name_en'):
                text = str(data.get(key) or '').strip()
                if text:
                    values.add(text.casefold())
        return values
    except Exception:
        return set()


def _direct_vocab_meaning(item: dict, is_tr: bool, term: str, course_lang: str) -> str:
    alphabet_data = _spanish_alphabet_data(term, course_lang)
    if alphabet_data:
        return str(alphabet_data.get('name_tr' if is_tr else 'name_en') or '')
    if is_tr:
        keys = ('translation_tr','meaning_tr','turkish','tr','gloss_tr','definition_tr',
                'meaning','translation','translation_en','meaning_en','english','gloss_en')
        locale_keys = ('tr','turkish','translation_tr','meaning_tr','gloss_tr','definition_tr')
    else:
        keys = ('translation_en','meaning_en','english','gloss_en','definition_en',
                'meaning','translation','translation_tr','meaning_tr','turkish','gloss_tr')
        locale_keys = ('en','english','translation_en','meaning_en','gloss_en','definition_en')
    leaks = _alphabet_leak_values(course_lang)
    candidates = [item.get(k) for k in keys]
    for container_key in ('translations','meanings','glosses','localized','localizations'):
        container = item.get(container_key)
        if isinstance(container, dict):
            candidates.extend(container.get(k) for k in locale_keys)
    for value in candidates:
        if isinstance(value, (dict, list, tuple)):
            continue
        text = str(value or '').strip()
        if text and text.casefold() not in leaks:
            return text
    return ''


def _aligned_example_gloss(item: dict, term: str, is_tr: bool) -> str:
    target = str(item.get('example') or item.get('example_target') or item.get('target_example') or '').strip()
    translated = str((item.get('example_tr') if is_tr else item.get('example_en')) or '').strip()
    if not target or not translated or not term:
        return ''
    def segments(text):
        return [p.strip(' \t\r\n“”\"') for p in re.split(r'(?:^|\s)[—–]\s*|\n+', text) if p and p.strip(' \t\r\n“”\"')]
    a, b = segments(target), segments(translated)
    if len(a) != len(b) or not a:
        return ''
    needle = _norm_key(term).strip(' .!?¿¡“”\"')
    for idx, part in enumerate(a):
        if _norm_key(part).strip(' .!?¿¡“”\"') == needle:
            return b[idx].strip()
    return ''


def _collect_vocab_memory(topic_payloads, course_lang: str):
    memory = {'en': {}, 'tr': {}}
    for content in topic_payloads:
        for page in _normalize_pages(content):
            items = page.get('items') or page.get('vocabulary') or page.get('words') or []
            if isinstance(items, dict):
                items = list(items.values()) if items and all(isinstance(v, dict) for v in items.values()) else [items]
            if not isinstance(items, list):
                continue
            for item in items[:500]:
                if not isinstance(item, dict):
                    continue
                term = item.get('term') or item.get('word') or item.get('phrase') or item.get('sentence') or item.get('target') or ''
                key = _norm_key(term)
                if not key:
                    continue
                en = _direct_vocab_meaning(item, False, term, course_lang)
                tr = _direct_vocab_meaning(item, True, term, course_lang)
                if en:
                    memory['en'].setdefault(key, en)
                if tr:
                    memory['tr'].setdefault(key, tr)
    return memory


def _vocab_meaning(item: dict, is_tr: bool, term: str, course_lang: str, memory) -> str:
    direct = _direct_vocab_meaning(item, is_tr, term, course_lang)
    if direct:
        return direct
    remembered = (memory.get('tr' if is_tr else 'en') or {}).get(_norm_key(term))
    if remembered:
        return remembered
    return _aligned_example_gloss(item, term, is_tr)


def _mcq_prompt(page: dict, is_tr: bool) -> str:
    keys = ('prompt_tr','prompt','question_tr','question','stem_tr','stem','text_tr','text') if is_tr else (
        'prompt_en','prompt','question_en','question','stem_en','stem','text_en','text'
    )
    for key in keys:
        value = page.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''


def _table_html(headers: Sequence[str], rows: Sequence[str]) -> str:
    return (
        '<table class="vocab"><tr>'
        f'<th style="width:18%">{headers[0]}</th><th style="width:13%">{headers[1]}</th>'
        f'<th style="width:21%">{headers[2]}</th><th style="width:27%">{headers[3]}</th>'
        f'<th style="width:21%">{headers[4]}</th></tr>' + ''.join(rows) + '</table>'
    )


def _doc(fragment: str) -> str:
    return f'<!doctype html><html><head><meta charset="utf-8"></head><body>{fragment}</body></html>'


class AcademicPaginator:
    def __init__(self, course_name: str, is_tr: bool):
        self.course_name = course_name
        self.is_tr = is_tr
        self.mediabox = fitz.paper_rect('a4')
        self.x0, self.x1 = 38, 557
        self.top, self.bottom = 42, 801
        self.full_rect = fitz.Rect(self.x0, self.top, self.x1, self.bottom)
        self.usable_height = self.bottom - self.top
        fd, self.temp_path = tempfile.mkstemp(suffix='.pdf')
        os.close(fd)
        self.writer = fitz.DocumentWriter(self.temp_path)
        self.device = None
        self.page_open = False
        self.y = self.top

    def _start_page(self):
        self.device = self.writer.begin_page(self.mediabox)
        self.page_open = True
        self.y = self.top

    def _end_page(self):
        if self.page_open:
            self.writer.end_page()
            self.page_open = False
            self.device = None

    def _story(self, fragment: str, allow_row_split: bool = False):
        css = CSS
        if allow_row_split:
            css += '\ntable.vocab tr { page-break-inside:auto !important; break-inside:auto !important; }'
        return fitz.Story(html=_doc(fragment), user_css=css)

    def _rect(self):
        return fitz.Rect(self.x0, self.y, self.x1, self.bottom)

    def _probe(self, fragment: str, rect: fitz.Rect, allow_row_split: bool = False):
        story = self._story(fragment, allow_row_split=allow_row_split)
        more, filled = story.place(rect)
        return (not bool(more)), fitz.Rect(filled), story

    def _draw_fitting(self, fragment: str, rect: fitz.Rect, gap: float) -> bool:
        fits, filled, story = self._probe(fragment, rect)
        if not fits:
            return False
        story.draw(self.device)
        self.y = max(self.y, filled.y1) + gap
        return True

    def _flow_oversized(self, fragment: str, gap: float, allow_row_split: bool = False):
        story = self._story(fragment, allow_row_split=allow_row_split)
        page_guard = 0
        while True:
            page_guard += 1
            if page_guard > 120:
                raise RuntimeError('PDF block exceeded safe pagination limit')
            if not self.page_open:
                self._start_page()
            rect = self._rect()
            more, filled = story.place(rect)
            filled = fitz.Rect(filled)
            made_progress = filled.height > 0.5 or filled.y1 > rect.y0 + 0.5
            if made_progress:
                story.draw(self.device)
            if not more:
                self.y = max(self.y, filled.y1 if made_progress else self.y) + gap
                return
            if not made_progress:
                if self.y > self.top + 1:
                    self._end_page(); self._start_page(); continue
                if not allow_row_split:
                    story = self._story(fragment, allow_row_split=True)
                    allow_row_split = True
                    continue
                raise RuntimeError('PDF block cannot make pagination progress')
            self._end_page(); self._start_page()

    def place_html(self, fragment: str, gap: float = 5.0, keep: bool = True):
        if not fragment:
            return
        if not self.page_open:
            self._start_page()
        if self._draw_fitting(fragment, self._rect(), gap):
            return
        fits_full, _, _ = self._probe(fragment, self.full_rect)
        if keep and fits_full and self.y > self.top + 1:
            self._end_page(); self._start_page()
            if self._draw_fitting(fragment, self._rect(), gap):
                return
        self._flow_oversized(fragment, gap)

    def _max_rows_that_fit(self, prefix: str, headers, rows: Sequence[str], rect: fitz.Rect) -> int:
        lo, hi, best = 1, len(rows), 0
        while lo <= hi:
            count = (lo + hi) // 2
            frag = prefix + _table_html(headers, rows[:count])
            fits, _, _ = self._probe(frag, rect)
            if fits:
                best = count; lo = count + 1
            else:
                hi = count - 1
        return best

    def place_vocab(self, prefix: str, headers, rows: List[str], gap: float = 6.0):
        if not rows:
            self.place_html(prefix, gap=gap, keep=True); return
        if not self.page_open:
            self._start_page()
        if len(rows) <= 36:
            whole = prefix + _table_html(headers, rows)
            if self._draw_fitting(whole, self._rect(), gap):
                return
            fits_full, _, _ = self._probe(whole, self.full_rect)
            if fits_full and (self.bottom - self.y) < self.usable_height * 0.24:
                self._end_page(); self._start_page()
                if self._draw_fitting(whole, self._rect(), gap):
                    return
        pending = list(rows)
        first = True
        while pending:
            if not self.page_open:
                self._start_page()
            pfx = prefix if first else ''
            max_rows = self._max_rows_that_fit(pfx, headers, pending, self._rect())
            if max_rows < 2 and len(pending) > 2 and self.y > self.top + 1:
                self._end_page(); self._start_page()
                max_rows = self._max_rows_that_fit(pfx, headers, pending, self._rect())
            if max_rows <= 0:
                self._flow_oversized(pfx + _table_html(headers, pending[:1]), 0, allow_row_split=True)
                pending = pending[1:]; first = False; continue
            if len(pending) - max_rows == 1 and max_rows > 2:
                max_rows -= 1
            frag = pfx + _table_html(headers, pending[:max_rows])
            if not self._draw_fitting(frag, self._rect(), 0):
                self._flow_oversized(frag, 0, allow_row_split=True)
            pending = pending[max_rows:]
            first = False
            if pending:
                self._end_page(); self._start_page()
        self.y += gap

    def _max_lines_that_fit(self, prefix: str, lines: Sequence[str], rect: fitz.Rect) -> int:
        lo, hi, best = 1, len(lines), 0
        while lo <= hi:
            count = (lo + hi) // 2
            frag = prefix + '<div class="dialogue">' + ''.join(lines[:count]) + '</div>'
            fits, _, _ = self._probe(frag, rect)
            if fits:
                best = count; lo = count + 1
            else:
                hi = count - 1
        return best

    def place_dialogue(self, prefix: str, lines: List[str], gap: float = 5.0):
        if not lines:
            self.place_html(prefix, gap=gap, keep=True); return
        if not self.page_open:
            self._start_page()
        if len(lines) <= 30:
            whole = prefix + '<div class="dialogue">' + ''.join(lines) + '</div>'
            if self._draw_fitting(whole, self._rect(), gap):
                return
        pending = list(lines)
        first = True
        while pending:
            pfx = prefix if first else ''
            max_lines = self._max_lines_that_fit(pfx, pending, self._rect())
            if max_lines < 2 and len(pending) > 2 and self.y > self.top + 1:
                self._end_page(); self._start_page()
                max_lines = self._max_lines_that_fit(pfx, pending, self._rect())
            if max_lines <= 0:
                self._flow_oversized(pfx + '<div class="dialogue">' + pending[0] + '</div>', 0)
                pending = pending[1:]; first = False; continue
            if len(pending) - max_lines == 1 and max_lines > 2:
                max_lines -= 1
            frag = pfx + '<div class="dialogue">' + ''.join(pending[:max_lines]) + '</div>'
            if not self._draw_fitting(frag, self._rect(), 0):
                self._flow_oversized(frag, 0)
            pending = pending[max_lines:]
            first = False
            if pending:
                self._end_page(); self._start_page()
        self.y += gap

    def page_break(self):
        self._end_page(); self._start_page()

    def finish(self) -> bytes:
        self._end_page()
        self.writer.close()
        doc = fitz.open(self.temp_path)
        total = len(doc)
        page_word = 'Sayfa' if self.is_tr else 'Page'
        for idx, page in enumerate(doc):
            if idx > 0:
                page.insert_text(fitz.Point(38, 27), f'AulaAI · {self.course_name}', fontsize=7, color=(0.42,0.42,0.42))
            page.insert_text(fitz.Point(38, 823), 'AulaAI Educational System · Self-Contained Course Material', fontsize=6.7, color=(0.42,0.42,0.42))
            page.insert_text(fitz.Point(493, 823), f'{page_word} {idx+1} / {total}', fontsize=6.7, color=(0.42,0.42,0.42))
        out = doc.tobytes()
        doc.close()
        try:
            os.remove(self.temp_path)
        except OSError:
            pass
        return out


def _render_rule_blocks(page: dict, is_tr: bool):
    blocks = []
    rules = page.get('rules') or []
    if is_tr and isinstance(page.get('rules_tr'), list) and page.get('rules_tr') and isinstance(page.get('rules_tr')[0], dict):
        rules = page.get('rules_tr')
    if isinstance(rules, dict):
        rules = [rules]
    elif not isinstance(rules, list):
        rules = [rules] if rules else []
    for rule in rules:
        if isinstance(rule, dict):
            r_title = _pick(rule, 'rule', 'rule_tr', is_tr) or rule.get('name') or ''
            r_expl = _pick(rule, 'explanation', 'explanation_tr', is_tr) or rule.get('desc') or ''
            r_example = rule.get('example') or rule.get('target') or ''
            r_example_trans = (rule.get('example_tr') or rule.get('translation_tr') or rule.get('turkish') or '') if is_tr else (rule.get('example_en') or rule.get('translation') or '')
            r_analysis = _pick(rule, 'analysis', 'analysis_tr', is_tr) or rule.get('breakdown') or ''
            bits = ['<div class="rule">']
            if r_title: bits.append(f'<p class="p"><strong>{_e(r_title)}</strong></p>')
            if r_expl: bits.append(f'<p class="p">{_e(r_expl)}</p>')
            if r_example:
                bits.append(f'<div class="sec">{"Örnek Kullanım" if is_tr else "Example Usage"}</div><p class="p"><em>{_e(r_example)}</em></p>')
            if r_example_trans: bits.append(f'<p class="translation">{_e(r_example_trans)}</p>')
            if r_analysis: bits.append(f'<p class="p"><strong>{"Dilbilgisi Analizi" if is_tr else "Structural Breakdown"}:</strong> {_e(r_analysis)}</p>')
            bits.append('</div>')
            blocks.append(''.join(bits))
        elif rule:
            blocks.append(f'<div class="rule"><p class="p">{_e(rule)}</p></div>')
    return blocks


def _comparison_blocks(page: dict, is_tr: bool):
    items = page.get('comparisons') or []
    if isinstance(items, dict): items = [items]
    elif not isinstance(items, list): items = [items] if items else []
    blocks = []
    for cmp in items:
        if not isinstance(cmp, dict): cmp = {'target': str(cmp)}
        ctx = _pick(cmp, 'context', 'context_tr', is_tr)
        target = cmp.get('target') or ''
        trans = _pick(cmp, 'translation', 'translation_tr', is_tr)
        note = _pick(cmp, 'note', 'note_tr', is_tr) or cmp.get('note') or ''
        if ctx or target or trans or note:
            blocks.append(
                f'<div class="compare"><strong>{_e(ctx)}</strong> {_e(target)}'
                + (f' → {_e(trans)}' if trans else '')
                + (f' <span class="translation">{_e(note)}</span>' if note else '')
                + '</div>'
            )
    return blocks


def render_course_pdf(course_id: str, lang: str = 'en') -> Tuple[bytes, str]:
    is_tr = (lang == 'tr')
    title_maps = _load_title_maps()
    answers: List[Dict] = []
    question_counter = 0

    with db_connection() as db:
        course = db.execute('SELECT name, language, level, semester FROM courses WHERE id = ?', (course_id,)).fetchone()
        if not course:
            raise ValueError('Course not found')
        course_name = course[0] or 'Course Materials'
        course_lang = course[1] or 'General'
        course_level = course[2] or 'All Levels'
        semester = course[3] or ''

        ch_has_tr = _column_exists(db, 'chapters', 'title_tr')
        top_has_tr = _column_exists(db, 'topics', 'title_tr')
        ch_select = 'id, number, title' + (', title_tr' if ch_has_tr else '')
        chapters = db.execute(f'SELECT {ch_select} FROM chapters WHERE course_id = ? ORDER BY number ASC, id ASC', (course_id,)).fetchall()

        paginator = AcademicPaginator(course_name, is_tr)
        sem = f' ({_e(semester)})' if semester else ''
        meta = 'Kapsamlı Ders Notları ve Alıştırmalar' if is_tr else 'Comprehensive Lesson Notes and Exercises'
        level_word = 'Seviye' if is_tr else 'Level'
        cover = (
            f'<div class="cover"><div class="cover-title">{_e(course_name)}</div>'
            f'<div class="cover-sub">{_e(course_lang)} · {level_word} {_e(course_level)}{sem}</div>'
            f'<div class="cover-meta">AulaAI — {meta}</div></div>'
        )
        paginator.place_html(cover, gap=8, keep=True)

        for ch in chapters:
            ch_id, ch_num, ch_title = ch[0], ch[1], ch[2]
            ch_title_tr = ch[3] if ch_has_tr and len(ch) > 3 else ''
            display_ch = _localized_title(ch_title, is_tr, None, title_maps, ch_title_tr)
            unit_html = f'<div class="unit">{"Ünite" if is_tr else "Unit"} {_e(ch_num)}: {_e(display_ch)}</div>'

            top_select = 'id, type, title' + (', title_tr' if top_has_tr else '') + ', content'
            topic_rows = db.execute(f'SELECT {top_select} FROM topics WHERE chapter_id = ? ORDER BY sort_order ASC, id ASC', (ch_id,)).fetchall()
            if not topic_rows:
                paginator.place_html(unit_html, keep=True)
                continue

            parsed_topics = []
            for row in topic_rows:
                if top_has_tr:
                    top_id, top_type, top_title, top_title_tr, top_content = row[0], row[1], row[2], row[3], row[4]
                else:
                    top_id, top_type, top_title, top_content = row[0], row[1], row[2], row[3]
                    top_title_tr = ''
                content = _normalize_content(top_content)
                parsed_topics.append((top_id, top_type, top_title, top_title_tr, content))

            try:
                vocab_memory = _collect_vocab_memory([x[4] for x in parsed_topics], course_lang)
            except Exception as exc:
                print(f'[PDF V12] Vocabulary memory skipped: {exc}')
                vocab_memory = {'en': {}, 'tr': {}}

            chapter_prefix_pending = unit_html
            for _top_id, top_type, top_title, top_title_tr, content in parsed_topics:
                display_top = _localized_title(top_title, is_tr, content, title_maps, top_title_tr)
                topic_html = (
                    f'<div class="topic">{_e(display_top or ("Konu" if is_tr else "Topic"))}</div>'
                    f'<div class="kind">{_e(_kind(top_type, is_tr))}</div>'
                )
                topic_prefix_pending = chapter_prefix_pending + topic_html
                chapter_prefix_pending = ''
                pages = _normalize_pages(content)
                if not pages:
                    paginator.place_html(topic_prefix_pending, keep=True)
                    continue

                last_mcq_section = None
                for page in pages:
                    ptype = _infer_page_type(page)
                    raw_title = page.get('title') or ''
                    title = _localized_title(raw_title, is_tr, page, title_maps, page.get('title_tr') or '')
                    if ptype == 'mcq' and title:
                        title = re.sub(r'^\s*\d+\.\s*', '', str(title)).strip()
                    section_key = _norm_key(title) if title else ''
                    if ptype == 'mcq':
                        section = '' if section_key and section_key == last_mcq_section else (f'<div class="sec">{_e(title)}</div>' if title else '')
                        last_mcq_section = section_key or last_mcq_section
                    else:
                        last_mcq_section = None
                        section = f'<div class="sec">{_e(title)}</div>' if title else ''
                    prefix = topic_prefix_pending + section
                    topic_prefix_pending = ''

                    if ptype in ('overview', 'grammar'):
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        blocks = _render_rule_blocks(page, is_tr) + _comparison_blocks(page, is_tr)
                        lead = prefix + (f'<div class="rule"><p class="p">{_e(text)}</p></div>' if text else '')
                        if blocks:
                            paginator.place_html(lead + blocks[0], gap=4, keep=True)
                            for block in blocks[1:]: paginator.place_html(block, gap=4, keep=True)
                        elif text:
                            paginator.place_html(lead, gap=5, keep=True)

                    elif ptype == 'vocabulary':
                        items = page.get('items') or page.get('vocabulary') or page.get('words') or []
                        if isinstance(items, dict):
                            items = list(items.values()) if items and all(isinstance(v, dict) for v in items.values()) else [items]
                        elif not isinstance(items, list):
                            items = [items] if items not in (None, '') else []
                        if not items:
                            paginator.place_html(prefix, keep=True); continue
                        headers = (
                            'Terim / Kelime' if is_tr else 'Term / Word',
                            'Telaffuz' if is_tr else 'Phonetic',
                            'Anlam' if is_tr else 'Translation',
                            'Hedef Dilde Örnek' if is_tr else 'Target-Language Example',
                            'Türkçe Çeviri' if is_tr else 'English Translation',
                        )
                        rows = []
                        for item in items:
                            if not isinstance(item, dict): item = {'term': str(item)}
                            term = item.get('term') or item.get('word') or item.get('phrase') or item.get('sentence') or item.get('target') or ''
                            phon = item.get('phonetic') or item.get('pronunciation') or ''
                            meaning = _vocab_meaning(item, is_tr, term, course_lang, vocab_memory)
                            ex_target = item.get('example') or item.get('example_target') or item.get('target_example') or ''
                            ex_translation = item.get('example_tr') if is_tr else item.get('example_en')
                            if not ex_translation: ex_translation = item.get('example_en') or item.get('example_tr') or ''
                            rows.append(
                                '<tr>'
                                f'<td><span class="term">{_e(term)}</span></td>'
                                f'<td><span class="phon">{_e(phon)}</span></td>'
                                f'<td><span class="meaning">{_e(meaning)}</span></td>'
                                f'<td><span class="example">{_e(ex_target)}</span></td>'
                                f'<td><span class="example-tr">{_e(ex_translation)}</span></td>'
                                '</tr>'
                            )
                        paginator.place_vocab(prefix, headers, rows)

                    elif ptype in ('examples', 'dialogue'):
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        intro = prefix + (f'<p class="p">{_e(text)}</p>' if text else '')
                        dialogue_items = page.get('dialogue') or page.get('conversations') or page.get('conversation') or page.get('turns') or page.get('lines') or []
                        if isinstance(dialogue_items, dict): dialogue_items = [dialogue_items]
                        elif not isinstance(dialogue_items, list): dialogue_items = [dialogue_items] if dialogue_items else []
                        lines = []
                        for d in dialogue_items:
                            if not isinstance(d, dict): d = {'text': str(d)}
                            spk = d.get('speaker') or d.get('name') or '?'
                            said = d.get('text') or d.get('line') or d.get('target') or ''
                            translated = (d.get('line_tr') or d.get('translation_tr')) if is_tr else (d.get('line_en') or d.get('translation_en'))
                            trans_html = f' <span class="translation">({_e(translated)})</span>' if translated else ''
                            lines.append(f'<div class="line"><span class="speaker">{_e(spk)}:</span> “{_e(said)}”{trans_html}</div>')
                        paginator.place_dialogue(intro, lines)

                    elif ptype == 'comparisons':
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        blocks = _comparison_blocks(page, is_tr)
                        lead = prefix + (f'<p class="p">{_e(text)}</p>' if text else '')
                        if blocks:
                            paginator.place_html(lead + blocks[0], gap=3, keep=True)
                            for block in blocks[1:]: paginator.place_html(block, gap=3, keep=True)
                        elif text:
                            paginator.place_html(lead, gap=3, keep=True)

                    elif ptype == 'mcq':
                        prompt = _mcq_prompt(page, is_tr)
                        if not prompt:
                            continue
                        question_counter += 1
                        raw_options = page.get('options') or page.get('choices') or []
                        if isinstance(raw_options, dict): raw_options = list(raw_options.values())
                        elif not isinstance(raw_options, list): raw_options = [raw_options] if raw_options else []
                        localized = page.get('options_tr') if is_tr else page.get('options_en')
                        options = localized if isinstance(localized, list) and len(localized) == len(raw_options) else raw_options
                        opts_html = ''.join(f'<div class="mcq-opt">{chr(65+i)}) {_e(opt)}</div>' for i, opt in enumerate(options))
                        frag = prefix + f'<div class="mcq"><div class="mcq-q">{question_counter}. {_e(prompt)}</div>{opts_html}</div>'
                        paginator.place_html(frag, gap=5, keep=True)

                        answer = page.get('answer') or ''
                        explanation = _pick(page, 'explanation', 'explanation_tr', is_tr) or ''
                        letter = ''
                        display_answer = str(answer or '')
                        try:
                            idx = [str(o).strip() for o in raw_options].index(str(answer).strip())
                            letter = chr(65 + idx)
                            if idx < len(options): display_answer = str(options[idx])
                        except Exception:
                            pass
                        answers.append({'number': question_counter, 'letter': letter, 'answer': display_answer, 'explanation': explanation})

                    else:
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        if text:
                            paginator.place_html(prefix + f'<p class="p">{_e(text)}</p>', gap=5, keep=True)

        if answers:
            paginator.page_break()
            paginator.place_html(f'<div class="unit">{"Cevap Anahtarı" if is_tr else "Answer Key"}</div>', gap=5, keep=True)
            for entry in answers:
                key = f"{entry['number']}. " + (f"{entry['letter']}) " if entry.get('letter') else '') + entry.get('answer','')
                expl = entry.get('explanation') or ''
                frag = f'<div class="answer"><strong>{_e(key)}</strong>' + (f'<br><span class="translation">{_e(expl)}</span>' if expl else '') + '</div>'
                paginator.place_html(frag, gap=2.5, keep=True)

        return paginator.finish(), course_name
