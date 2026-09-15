import html
import json
import os
import re
import tempfile
from typing import Dict, List, Optional, Sequence, Tuple

import fitz

from database import db_connection
from services.material_quality_guard import sanitize_dialogue_speaker


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
.p, .rule, .dialogue, .line, .translation, .term, .phon, .meaning, .example, .example-tr, .mcq-q, .mcq-opt, table.vocab td { unicode-bidi: plaintext; }
'''

TYPE_LABELS = {
    'vocabulary': ('Vocabulary', 'Kelime Bilgisi'),
    'grammar': ('Grammar', 'Dilbilgisi'),
    'phonetics': ('Phonetics', 'Fonetik'),
    'pronunciation': ('Pronunciation', 'Telaffuz'),
    'theory': ('Theory', 'Konu Anlatımı'),
    'functional_language': ('Functional Language', 'İşlevsel Dil'),
    'functional': ('Functional', 'İşlevsel Dil'),
    'cultural_context': ('Cultural Context', 'Kültürel Bağlam'),
    'dialogue': ('Dialogue', 'Diyalog'),
    'examples': ('Examples', 'Örnekler'),
    'reading': ('Reading', 'Okuma'),
    'writing': ('Writing', 'Yazma'),
    'listening': ('Listening', 'Dinleme'),
    'speaking': ('Speaking', 'Konuşma'),
    'practice': ('Practice', 'Alıştırmalar'),
    'review': ('Review', 'Genel Tekrar'),
    'assessment': ('Assessment', 'Değerlendirme'),
    'overview': ('Overview', 'Genel Bakış'),
    'exercise': ('Exercise', 'Alıştırma'),
    'exercises': ('Exercises', 'Alıştırmalar'),
    'mcq': ('Assessment', 'Değerlendirme'),
}


def _e(value):
    raw = str(value or '')
    raw = raw.replace('゛', '†').replace('゜', '‡')
    raw = re.sub(r'(?<![\u3040-\u30ff\u3400-\u9fff\uff66-\uff9f])ー(?![\u3040-\u30ff\u3400-\u9fff\uff66-\uff9f])', '¤', raw)
    return html.escape(raw)


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
    if explicit_tr and str(explicit_tr).strip() and str(explicit_tr).strip().casefold() != title.casefold():
        return str(explicit_tr).strip()
    if isinstance(content, dict):
        metadata = content.get('metadata') if isinstance(content.get('metadata'), dict) else {}
        for value in (
            content.get('topic_title_tr'), content.get('chapter_title_tr'),
            content.get('localized_title_tr'), content.get('title_tr'),
            metadata.get('topic_title_tr'), metadata.get('chapter_title_tr'),
            metadata.get('localized_title_tr'), metadata.get('title_tr'),
        ):
            if value and str(value).strip() and str(value).strip().casefold() != title.casefold():
                return str(value).strip()
    exact, ci_cache, ci_canonical = title_maps
    if title in exact and str(exact[title]).strip():
        return str(exact[title]).strip()
    folded = title.casefold()
    if folded in ci_cache:
        return ci_cache[folded]
    if folded in ci_canonical:
        return ci_canonical[folded]
    if folded in TYPE_LABELS:
        return TYPE_LABELS[folded][1]
    for k, (en_label, tr_label) in TYPE_LABELS.items():
        pattern = rf'^{re.escape(en_label)}\s*([:–—-])\s*(.*)$'
        m = re.match(pattern, title, flags=re.IGNORECASE)
        if m:
            sep = m.group(1)
            rest = m.group(2).strip()
            rest_tr = ci_cache.get(rest.casefold()) or ci_canonical.get(rest.casefold()) or rest
            return f"{tr_label}{sep} {rest_tr}".strip()
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


def _publication_invariants(content, language=None):
    """Apply the same deterministic publication invariants used at generation time.

    Material persisted before those invariants existed (or written by another path)
    must not publish with duplicate MCQ options, placeholder distractors or
    accidentally duplicated blocks just because it skipped the generation boundary.
    The call is deterministic and idempotent, so material that already passed is
    unchanged.
    """
    try:
        from services.publication_invariants import load_publishable_content
        return load_publishable_content(content, language=language)
    except Exception:
        return content if isinstance(content, dict) else {}


def _normalize_content(raw, language=None):
    """Obtain publishable content. Parsing and the publication boundary are one
    step, shared with every other renderer, so no path can acquire content that
    has not crossed it."""
    return _publication_invariants(raw, language=language)


def _normalize_pages(content):
    if not isinstance(content, dict):
        return []
    pages = content.get('pages') or []
    if isinstance(pages, dict):
        pages = [pages]
    if not isinstance(pages, list):
        return []
    valid = []
    for p in pages:
        if not isinstance(p, dict):
            continue
        has_text = bool(str(p.get('text') or p.get('text_tr') or p.get('text_en') or '').strip())
        has_items = bool(p.get('items') or p.get('vocabulary') or p.get('words'))
        has_rules = bool(p.get('rules') or p.get('comparisons') or p.get('grammar') or p.get('rules_tr'))
        has_dialogue = bool(p.get('dialogue') or p.get('conversations'))
        has_mcq = bool((p.get('prompt') or p.get('prompt_tr') or p.get('prompt_en') or p.get('question') or p.get('stem') or str(p.get('type', '')).strip().lower() == 'mcq') and (p.get('options') or p.get('choices')))
        if has_text or has_items or has_rules or has_dialogue or has_mcq:
            valid.append(p)
    return valid


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
        _fontfile = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
        if os.path.exists(_fontfile):
            for _page in doc:
                _placements = []
                for _placeholder, _symbol in (('†', '゛'), ('‡', '゜'), ('¤', 'ー')):
                    for _rect in _page.search_for(_placeholder):
                        _placements.append((_rect, _symbol))
                        _page.add_redact_annot(_rect, fill=None)
                if _placements:
                    _page.apply_redactions()
                    for _rect, _symbol in _placements:
                        _fontsize = max(6.0, _rect.height * 0.80)
                        _baseline = _rect.y1 - (_rect.height * 0.15)
                        _page.insert_text((_rect.x0, _baseline), _symbol, fontname='AulaNotoCJK', fontfile=_fontfile, fontsize=_fontsize)
        total = len(doc)
        page_word = 'Sayfa' if self.is_tr else 'Page'
        for idx, page in enumerate(doc):
            if idx > 0:
                header = f'AulaAI · {self.course_name}'
                page.insert_htmlbox(fitz.Rect(38, 18, 420, 34), f"<span style='font-family:sans-serif;font-size:7pt;color:#6b7280'>{_e(header)}</span>")
            footer_text = 'AulaAI Eğitim Sistemi · Bağımsız Ders Materyali' if self.is_tr else 'AulaAI Educational System · Self-Contained Course Material'
            page.insert_htmlbox(fitz.Rect(38, 814, 430, 832), f"<span style='font-family:sans-serif;font-size:6.7pt;color:#6b7280'>{_e(footer_text)}</span>")
            page.insert_htmlbox(fitz.Rect(465, 814, 558, 832), f"<div style='font-family:sans-serif;font-size:6.7pt;color:#6b7280;text-align:right'>{_e(f'{page_word} {idx+1} / {total}')}</div>")
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
            r_title = _v53_instructional(_pick(rule, 'rule', 'rule_tr', is_tr) or rule.get('name') or '', is_tr)
            r_expl = _v53_instructional(_pick(rule, 'explanation', 'explanation_tr', is_tr) or rule.get('desc') or '', is_tr)
            r_example = rule.get('example') or rule.get('target') or ''
            r_example_trans = _v53_instructional((rule.get('example_tr') or rule.get('translation_tr') or rule.get('turkish') or '') if is_tr else (rule.get('example_en') or rule.get('translation') or ''), is_tr)
            r_analysis = _v53_instructional(_pick(rule, 'analysis', 'analysis_tr', is_tr) or rule.get('breakdown') or '', is_tr)
            if is_tr:
                r_title = _v52_meta(r_title, "tr")
                r_expl = _v52_meta(r_expl, "tr")
                r_example_trans = _v52_meta(r_example_trans, "tr")
                r_analysis = _v52_meta(r_analysis, "tr")
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
            blocks.append(f'<div class="rule"><p class="p">{_e(_v53_instructional(rule, is_tr))}</p></div>')
    return blocks


def _comparison_blocks(page: dict, is_tr: bool):
    items = page.get('comparisons') or []
    if isinstance(items, dict): items = [items]
    elif not isinstance(items, list): items = [items] if items else []
    blocks = []
    for cmp in items:
        if not isinstance(cmp, dict): cmp = {'target': str(cmp)}
        ctx = _pick(cmp, 'context', 'context_tr', is_tr)
        target = _v54_instructional(cmp.get('target') or '', is_tr)
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


def _pdf_language_name(value: str, is_tr: bool) -> str:
    raw = str(value or '').strip()
    if not is_tr:
        return raw
    return {'english':'İngilizce','german':'Almanca','spanish':'İspanyolca','french':'Fransızca','italian':'İtalyanca','portuguese':'Portekizce','russian':'Rusça','chinese':'Çince','japanese':'Japonca','arabic':'Arapça','turkish':'Türkçe','dutch':'Hollandaca','swedish':'İsveççe','korean':'Korece','greek':'Yunanca'}.get(raw.casefold(), raw)


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
        _semester = str(semester or '').strip()
        _level = str(course_level or '').strip()
        if _semester.casefold() in {_level.casefold(), (_level + ' level').casefold()}:
            _semester = ''
        sem = f' ({_e(_semester)})' if _semester else ''
        meta = 'Kapsamlı Ders Notları ve Alıştırmalar' if is_tr else 'Comprehensive Lesson Notes and Exercises'
        level_word = 'Seviye' if is_tr else 'Level'
        cover = (
            f'<div class="cover"><div class="cover-title">{_e(course_name)}</div>'
            f'<div class="cover-sub">{_e(_pdf_language_name(course_lang, is_tr))} · {level_word} {_e(course_level)}{sem}</div>'
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
                content = _normalize_content(top_content, course_lang)
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
                    # The renderer renders; it does not author. A topic with no
                    # persisted material gets an explicit, honest notice rather than
                    # generated scaffolding that a teacher cannot distinguish from
                    # real content.
                    notice = (
                        'Bu konu için yayımlanabilir materyal bulunamadı. Sınıfta kullanmadan önce '
                        'konuyu yeniden üretin veya elle hazırlayın.'
                        if is_tr else
                        'No publishable material is stored for this topic. Regenerate it, or author it '
                        'manually before classroom use.'
                    )
                    paginator.place_html(
                        topic_prefix_pending + f'<div class="rule"><p class="p">{_e(notice)}</p></div>',
                        keep=True,
                    )
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
                        is_grapheme_inventory = _v54_is_grapheme_inventory(items)
                        headers = (
                            ('Harf / İşaret' if is_tr else 'Letter / Sign') if is_grapheme_inventory else (('Harf / İşaret' if is_tr else 'Letter / Sign') if _v57_is_grapheme_inventory(items) else ('Terim / Kelime' if is_tr else 'Term / Word')),
                            ('Temel Ses (IPA)' if is_tr else 'Basic Sound (IPA)') if is_grapheme_inventory else (('Temel Ses (IPA)' if is_tr else 'Basic Sound (IPA)') if _v57_is_grapheme_inventory(items) else ('Telaffuz' if is_tr else 'Phonetic')),
                            'Anlam' if is_tr else 'Translation',
                            (f'{_pdf_language_name(course_lang, True)} Örnek' if is_tr else f'{course_lang} Example'),
                            'Türkçe Çeviri' if is_tr else 'English Translation',
                        )
                        rows = []
                        for item in items:
                            if not isinstance(item, dict): item = {'term': str(item)}
                            term = item.get('term') or item.get('word') or item.get('phrase') or item.get('sentence') or item.get('target') or ''
                            phon = _v54_display_phonetic(item.get('phonetic') or item.get('pronunciation') or '')
                            meaning = _vocab_meaning(item, is_tr, term, course_lang, vocab_memory)
                            ex_target = item.get('example') or item.get('example_target') or item.get('target_example') or ''
                            ex_translation = item.get('example_tr') if is_tr else item.get('example_en')
                            if not ex_translation: ex_translation = item.get('example_en') or item.get('example_tr') or ''
                            rows.append(
                                '<tr>'
                                f'<td><span class="term">{_e(term)}</span></td>'
                                f'<td><span class="phon">{_e(_v55_display_phonetic_cell(phon))}</span></td>'
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
                            spk = _v52_dialogue_speaker(d, is_tr)
                            said = d.get('text') or d.get('line') or d.get('target') or ''
                            translated = (d.get('line_tr') or d.get('translation_tr')) if is_tr else (d.get('line_en') or d.get('translation_en'))
                            translated = _v53_instructional(translated, is_tr) if translated else translated
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
                        if _v54_pdf_unsafe_mcq(page, prompt, is_tr):
                            last_mcq_section = None
                            continue
                        question_counter += 1
                        raw_options = page.get('options') or page.get('choices') or []
                        if isinstance(raw_options, dict): raw_options = list(raw_options.values())
                        elif not isinstance(raw_options, list): raw_options = [raw_options] if raw_options else []
                        localized = page.get('options_tr') if is_tr else page.get('options_en')
                        options = localized if isinstance(localized, list) and len(localized) == len(raw_options) else raw_options
                        options = [_v56q_display_option(opt, course_lang) for opt in options]
                        opts_html = ''.join(f'<div class="mcq-opt">{chr(65+i)}) {_e(opt)}</div>' for i, opt in enumerate(options))
                        frag = prefix + f'<div class="mcq"><div class="mcq-q">{question_counter}. {_e(prompt)}</div>{opts_html}</div>'
                        paginator.place_html(frag, gap=5, keep=True)

                        answer = page.get('answer') or ''
                        if not answer and isinstance(page.get('correct_index'), int) and 0 <= page.get('correct_index') < len(raw_options):
                            answer = raw_options[page.get('correct_index')]
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


# AULAAI_RELEASE_HARDENING_V50
from services.material_quality_guard import safe_unicode_normalize as _v50_unicode_normalize

_v50_original_normalize_content = _normalize_content


def _v50_renderer_clean(node):
    if isinstance(node, str):
        return _v50_unicode_normalize(node)
    if isinstance(node, dict):
        return {k: _v50_renderer_clean(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_v50_renderer_clean(v) for v in node]
    return node


def _normalize_content(raw, language=None):
    return _v50_renderer_clean(_v50_original_normalize_content(raw, language=language))


def _e(value):
    return html.escape(_v50_unicode_normalize(str(value or "")))


_v50_freeform_keys = {
    "title", "text", "explanation", "analysis", "note", "context",
    "rule", "translation", "meaning", "prompt", "question", "stem",
}


def _pick(obj, en_key, tr_key, is_tr):
    if not isinstance(obj, dict):
        return ""
    primary_key, fallback_key = (tr_key, en_key) if is_tr else (en_key, tr_key)
    primary = obj.get(primary_key)
    if primary is not None and str(primary).strip():
        return primary
    base = str(en_key or "").casefold().removesuffix("_en")
    if base in _v50_freeform_keys:
        return ""
    fallback = obj.get(fallback_key)
    return fallback if fallback is not None else ""

# AULAAI_RELEASE_HARDENING_V51


# AULAAI_RELEASE_HARDENING_V52
from services.material_quality_guard import sanitize_instructional_metalanguage as _v52_meta
_v52_pick = _pick
_v52_mcq_prompt = _mcq_prompt
_v52_vocab_meaning = _vocab_meaning


def _pick(obj, en_key, tr_key, is_tr):
    value = _v52_pick(obj, en_key, tr_key, is_tr)
    return _v52_meta(value, "tr" if is_tr else "en")


def _mcq_prompt(page, is_tr):
    value = _v52_mcq_prompt(page, is_tr)
    return _v52_meta(value, "tr" if is_tr else "en")


def _vocab_meaning(item, is_tr, term, course_lang, memory):
    value = _v52_vocab_meaning(item, is_tr, term, course_lang, memory)
    return _v52_meta(value, "tr" if is_tr else "en")


def _v52_dialogue_speaker(turn, is_tr):
    if not isinstance(turn, dict):
        return "?"
    keys = ("speaker_tr", "name_tr", "speaker", "name") if is_tr else ("speaker_en", "name_en", "speaker", "name")
    value = next((turn.get(k) for k in keys if turn.get(k)), "?")
    return sanitize_dialogue_speaker(value)


# AULAAI_RELEASE_HARDENING_V53
def _v53_instructional(value, is_tr):
    try:
        return _v52_meta(value, "tr" if is_tr else "en")
    except Exception:
        return value


# AULAAI_RELEASE_HARDENING_V54
_v54_previous_localized_title = _localized_title


def _localized_title(title, is_tr, content=None, title_maps=None, explicit_title_tr=None):
    value = _v54_previous_localized_title(title, is_tr, content, title_maps, explicit_title_tr)
    try:
        return _v52_meta(value, "tr" if is_tr else "en")
    except Exception:
        return value


def _v54_is_grapheme_inventory(items):
    """Detect alphabet/script inventory tables structurally, without language names."""
    if not isinstance(items, list) or len(items) < 5:
        return False
    compact = 0
    paired = 0
    usable = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or item.get("word") or "").strip()
        if not term:
            continue
        usable += 1
        tokens = [t for t in term.split() if t]
        chars = "".join(tokens)
        if 1 <= len(chars) <= 4:
            compact += 1
        if len(tokens) == 2 and len(tokens[0]) == 1 and len(tokens[1]) == 1 and tokens[0].casefold() == tokens[1].casefold():
            paired += 1
    if usable < 5:
        return False
    return (compact / usable) >= 0.75 and ((paired / usable) >= 0.30 or usable >= 15)


def _v54_display_phonetic(value):
    text = str(value or "").strip()
    if not text:
        return ""
    parts = [p.strip() for p in text.split("/")]
    if len(parts) > 1:
        return " / ".join(p if (p.startswith("[") and p.endswith("]")) else f"[{p}]" for p in parts if p)
    return text if (text.startswith("[") and text.endswith("]")) else f"[{text}]"


def _v54_instructional(value, is_tr):
    try:
        return _v52_meta(value, "tr" if is_tr else "en")
    except Exception:
        return value


def _v54_pdf_unsafe_mcq(page, prompt, is_tr):
    if not isinstance(page, dict):
        return False
    explanation = page.get("explanation_tr") if is_tr else page.get("explanation_en")
    explanation = explanation or page.get("explanation") or ""
    def fold(text):
        import unicodedata
        t = unicodedata.normalize("NFD", str(text or "")).casefold()
        return "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    p, e = fold(prompt), fold(explanation)
    explicit_gender = bool(re.search(r"\b(kadin|erkek|disil|eril|female|male|woman|man)\b", p))
    if bool(re.search(r"\b(isim|adi|adinin|name)\b", e)) and bool(re.search(r"\b(kadin|erkek|disil|eril|female|male|woman|man)\b", e)) and not explicit_gender:
        return True
    bio = any(x in p for x in ("dogdu", "dogmus", "yasiyor", "yasadi", "calisiyor", "born", "lives", "works", "resides", "родил", "жив", "работ", "nacio", "vive", "trabaja", "geboren", "lebt", "arbeitet", "habite", "travaille"))
    identity = bool(re.search(r"\b(milliyet|uyruk|nationality|national|dil|konus|language|speak|speaks|spoken|meslek|profession|occupation|job)\b", e))
    return bio and identity


# AULAAI_RELEASE_HARDENING_V55
_v55_previous_pdf_unsafe_mcq = _v54_pdf_unsafe_mcq


def _v55_display_phonetic_cell(value):
    """Idempotent publication formatter for simple and composite IPA fields."""
    text = str(value or "").strip()
    if not text:
        return ""

    # Repeatedly remove only a redundant OUTER bracket pair when the inside is
    # already a slash-separated sequence of complete [IPA] groups.
    for _ in range(3):
        if not (text.startswith("[[") and text.endswith("]]")):
            break
        inner = text[1:-1].strip()
        groups = re.findall(r"\[[^\]\n]+\]", inner)
        residue = re.sub(r"\[[^\]\n]+\]", "", inner)
        if len(groups) >= 2 and not residue.replace("/", "").replace(" ", ""):
            text = " / ".join(groups)
        else:
            break

    groups = re.findall(r"\[[^\]\n]+\]", text)
    residue = re.sub(r"\[[^\]\n]+\]", "", text)
    if len(groups) >= 2 and not residue.replace("/", "").replace(" ", ""):
        return " / ".join(groups)

    parts = [p.strip() for p in text.split("/") if p.strip()]
    if len(parts) > 1:
        return " / ".join(
            p if (p.startswith("[") and p.endswith("]")) else f"[{p}]"
            for p in parts
        )
    return text if (text.startswith("[") and text.endswith("]")) else f"[{text}]"


def _v54_display_phonetic(value):
    # Keep v54's public helper name for compatibility, but make it idempotent.
    return _v55_display_phonetic_cell(value)


def _v54_pdf_unsafe_mcq(page, prompt, is_tr):
    if _v55_previous_pdf_unsafe_mcq(page, prompt, is_tr):
        return True
    if not isinstance(page, dict):
        return False

    def fold(text):
        import unicodedata
        t = unicodedata.normalize("NFD", str(text or "")).casefold()
        t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
        return t.replace("ı", "i")

    p = fold(prompt)
    opts = fold(" ".join(str(v or "") for v in (page.get("options") or page.get("choices") or [])))
    workplace_fact = any(x in p for x in (
        "calisiyor", "calisir", "work at", "works at", "works in", "working at", "working in",
        "arbeitet", "travaille", "trabaja", "lavora", "trabalha", "работает", "работа в",
    ))
    profession_question = any(x in p for x in (
        "meslegi", "meslek nedir", "profession", "occupation", "job is", "what does", "beruf",
        "profession est", "profesion", "profissão", "професс", "кем он", "кем она",
    ))
    if workplace_fact and profession_question:
        return True

    trait_fact = any(x in p for x in (
        "dakik", "punctual", "punktlich", "ponctuel", "puntual", "pontual", "пунктуал",
    ))
    absolute_frequency_option = any(x in opts for x in (
        "nikogda", "vsegda", "never", "always", "niemals", "immer", "jamais", "toujours",
        "nunca", "siempre", "mai", "sempre", "никогда", "всегда",
    ))
    return trait_fact and absolute_frequency_option


# AULAAI_RELEASE_CLEANUP_V56
from services.material_quality_guard import _v56_release_cleanup as _v56_publication_cleanup
_v56_previous_normalize_content = _normalize_content

def _normalize_content(raw, language=None):
    normalized = _v56_previous_normalize_content(raw, language=language)
    # 'language' is the actual per-course/topic target language (e.g. course_lang
    # from render_course_pdf). Russian-specific corrections must only fire when
    # the content is confirmed Russian - never hardcoded, since this renderer
    # path handles all 14 supported languages.
    if isinstance(normalized, dict) and language:
        return _v56_publication_cleanup(normalized, language)
    return normalized


# AULAAI_RELEASE_CLEANUP_V56_QUALITY
_V56Q_RENDER_IPA_SINGLE = {
    "б":"b", "в":"v", "г":"ɡ", "д":"d", "ж":"ʐ", "з":"z", "к":"k",
    "л":"ɫ", "м":"m", "н":"n", "п":"p", "р":"r", "с":"s", "т":"t",
    "ф":"f", "х":"x", "ц":"t͡s", "ч":"t͡ɕ", "ш":"ʂ", "щ":"ɕː", "й":"j",
}

def _v56q_render_is_russian(language):
    value = str(language or "").casefold()
    return "russian" in value or "rusça" in value or "рус" in value


def _v56q_display_option(value, language=""):
    text = str(value or "").strip()
    if not _v56q_render_is_russian(language):
        return text

    m = re.fullmatch(r"(\[[^\]\n]+\])\s*\(([^()]*)\)", text)
    if m:
        gloss = m.group(2).casefold()
        if any(phrase in gloss for phrase in (
            "similar to", "short i-like", "clear long", "close front",
            "rounded back", "clear rounded", "full stressed", "sound due to",
            "unstressed 'a'", "unstressed a",
        )):
            text = m.group(1)

    m = re.fullmatch(r"\[([А-Яа-яЁё])([ʲː]?)\]", text)
    if m:
        letter = m.group(1).casefold()
        base = _V56Q_RENDER_IPA_SINGLE.get(letter)
        if base:
            mark = m.group(2)
            if mark == "ʲ" and letter == "л":
                return "[lʲ]"
            return f"[{base}{mark}]"
    return text


# AULAAI_RELEASE_FINAL_V57
import re as _v57r_re
import unicodedata as _v57r_ud


def _v57_tr_meta(value):
    if not isinstance(value, str) or not value:
        return value
    text = value
    replacements = (
        (r"\bPrepositional\s+Case\b", "Edat Durumu"),
        (r"\bNominative\b", "Yalın Hâl"),
        (r"\bAccusative\b", "Belirtme Hâli"),
        (r"\bGenitive\b", "İlgi/Tamlayan Hâli"),
        (r"\bDative\b", "Yönelme Hâli"),
        (r"\bInstrumental\b", "Araç Hâli"),
        (r"\bMasculine\b", "eril"),
        (r"\bFeminine\b", "dişil"),
        (r"\bNeuter\b", "nötr"),
    )
    for pattern, replacement in replacements:
        text = _v57r_re.sub(pattern, replacement, text, flags=_v57r_re.IGNORECASE)
    text = _v57r_re.sub(r"\b(Edat Durumu|Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli)\s+[Cc]ase\b", r"\1", text)
    text = _v57r_re.sub(r"(?i)\bİlgi\s*/\s*İlgi\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", text)
    text = _v57r_re.sub(r"(?i)\bİlgi\s*/\s*Tamlayan\s*(?:H[âa]li)?\s*/\s*Tamlayan\s+H[âa]li\b", "İlgi/Tamlayan Hâli", text)
    text = _v57r_re.sub(r"(?i)\b(Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\s*\(\s*\1\s*\)", r"\1", text)
    text = _v57r_re.sub(r"(?i)\b(Yalın Hâl|Belirtme Hâli|İlgi/Tamlayan Hâli|Yönelme Hâli|Araç Hâli|Edat Durumu)\s*/\s*\1\b", r"\1", text)
    if _v57r_re.search(r'(?i)\b(?:ехать|еха[-–—]|ehat|ekhat)\b', text):
        text = _v57r_re.sub(r'["\'„“]?-д-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", text, flags=_v57r_re.IGNORECASE)
        text = _v57r_re.sub(r'["\'„“]?-d-["\'„“]?\s+gövdesi(?:ni)?\s+alır', "gövde 'ед-' biçimine dönüşür", text, flags=_v57r_re.IGNORECASE)
    return text


_v57_previous_pick = _pick

def _pick(obj, en_key, tr_key, is_tr):
    value = _v57_previous_pick(obj, en_key, tr_key, is_tr)
    return _v57_tr_meta(value) if is_tr else value


_v57_previous_comparison_blocks = _comparison_blocks

def _comparison_blocks(page, is_tr):
    if not is_tr or not isinstance(page, dict):
        return _v57_previous_comparison_blocks(page, is_tr)
    clone = dict(page)
    comparisons = page.get("comparisons") or []
    if isinstance(comparisons, dict):
        comparisons = [comparisons]
    if isinstance(comparisons, list):
        cleaned = []
        for item in comparisons:
            if isinstance(item, dict):
                c = dict(item)
                for key, value in list(c.items()):
                    if isinstance(value, str):
                        c[key] = _v57_tr_meta(value)
                cleaned.append(c)
            else:
                cleaned.append(_v57_tr_meta(item) if isinstance(item, str) else item)
        clone["comparisons"] = cleaned
    return _v57_previous_comparison_blocks(clone, is_tr)


def _v57_display_phonetic(value):
    text = str(value or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in _v57r_re.split(r"\s*/\s*", text) if part.strip()]
    rendered = []
    for part in parts:
        rendered.append(part if part.startswith("[") and part.endswith("]") else f"[{part}]")
    return " / ".join(rendered)


def _v57_is_grapheme_inventory(items):
    if not isinstance(items, list) or len(items) < 5:
        return False
    compact = paired = usable = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or item.get("word") or "").strip()
        if not term:
            continue
        usable += 1
        tokens = [token for token in term.split() if token]
        chars = "".join(tokens)
        if 1 <= len(chars) <= 4:
            compact += 1
        if len(tokens) == 2 and len(tokens[0]) == len(tokens[1]) == 1 and tokens[0].casefold() == tokens[1].casefold():
            paired += 1
    return usable >= 5 and (compact / usable) >= 0.75 and ((paired / usable) >= 0.30 or usable >= 15)


def _v57_renderer_unsafe_mcq(page):
    try:
        from services.material_quality_guard import _v57_unsafe_mcq
        return bool(_v57_unsafe_mcq(page))
    except Exception:
        return False


_v57_previous_normalize_pages = _normalize_pages

def _normalize_pages(content):
    pages = _v57_previous_normalize_pages(content)
    return [page for page in pages if not _v57_renderer_unsafe_mcq(page)]

# AULAAI_MICRO_QUALITY_POLISH
from services.material_quality_guard import (
    safe_unicode_normalize as _v58_safe_unicode,
    sanitize_instructional_shorthand as _v58_shorthand,
    deduplicate_morphological_parentheticals as _v58_dedup,
    align_lexical_fields as _v58_align_fields,
    harmonize_mixed_scripts as _v58_harmonize,
)

_v58_previous_pick = _pick

def _pick(obj, en_key, tr_key, is_tr):
    value = _v58_previous_pick(obj, en_key, tr_key, is_tr)
    if is_tr and isinstance(value, str):
        return _v58_dedup(_v58_shorthand(value, "tr"))
    return value

_v58_previous_e = _e

def _e(value):
    raw = _v58_safe_unicode(str(value or ""))
    return _v58_previous_e(raw)

_v58_previous_story = AcademicPaginator._story

def _v58_story(self, fragment: str, *args, **kwargs):
    if fragment and self.is_tr:
        fragment = _v58_shorthand(fragment, "tr")
    if fragment:
        fragment = _v58_safe_unicode(fragment)
    return _v58_previous_story(self, fragment, *args, **kwargs)

AcademicPaginator._story = _v58_story

_v58_previous_normalize_pages = _normalize_pages

def _normalize_pages(content):
    pages = _v58_previous_normalize_pages(content)
    for p in pages:
        if isinstance(p, dict):
            for k in ('items', 'vocabulary', 'words', 'rules', 'comparisons'):
                sub = p.get(k)
                if isinstance(sub, list):
                    for idx, item in enumerate(sub):
                        if isinstance(item, dict):
                            sub[idx] = _v58_align_fields(item)
    return pages
