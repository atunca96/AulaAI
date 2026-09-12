import html
import json
import os
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
.mcq { border: 0.55px solid #cbd5e1; padding: 6px 8px; margin: 0; background: #fff; }
.mcq-q { font-weight: 700; margin: 0 0 4px 0; color: #111827; }
.mcq-opt { margin: 1.7px 0; color: #374151; }
.compare { border-top: 0.45px solid #d1d5db; padding-top: 4px; margin-top: 3px; }
.answer { margin: 0 0 4px 0; }
.cont { font-size: 6.8pt; color: #94a3b8; margin: 0 0 2px 0; }
'''

TYPE_LABELS = {
    'vocabulary': ('Vocabulary', 'Kelime Bilgisi'),
    'grammar': ('Grammar', 'Dilbilgisi'),
    'phonetics': ('Phonetics', 'Fonetik'),
    'functional_language': ('Functional Language', 'İşlevsel Dil'),
    'cultural_context': ('Cultural Context', 'Kültürel Bağlam'),
    'dialogue': ('Dialogue', 'Diyalog'),
    'reading': ('Reading', 'Okuma'),
    'writing': ('Writing', 'Yazma'),
    'listening': ('Listening', 'Dinleme'),
    'speaking': ('Speaking', 'Konuşma'),
}


def _e(value):
    return html.escape(str(value or ''))


def _pick(obj, en_key, tr_key, is_tr):
    if is_tr:
        return obj.get(tr_key) or obj.get(en_key) or ''
    return obj.get(en_key) or obj.get(tr_key) or ''


def _kind(kind, is_tr):
    pair = TYPE_LABELS.get(kind, (str(kind or 'lesson').replace('_', ' ').title(), str(kind or 'lesson').replace('_', ' ').title()))
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


def _localized_title(title: str, is_tr: bool, content: Optional[dict], title_maps) -> str:
    title = str(title or '').strip()
    if not is_tr:
        return title
    if content:
        candidates = [
            content.get('title_tr'),
            content.get('topic_title_tr'),
            content.get('localized_title_tr'),
            (content.get('metadata') or {}).get('title_tr') if isinstance(content.get('metadata'), dict) else None,
        ]
        for value in candidates:
            if value and str(value).strip():
                return str(value).strip()
    exact, ci_cache, ci_canonical = title_maps
    if title in exact and str(exact[title]).strip():
        return str(exact[title]).strip()
    key = title.casefold()
    if key in ci_cache:
        return ci_cache[key]
    if key in ci_canonical:
        return ci_canonical[key]
    return title


def _table_html(headers: Sequence[str], rows: Sequence[str], continued: bool = False) -> str:
    cont = '<div class="cont">devam</div>' if continued else ''
    return (
        cont + '<table class="vocab"><tr>'
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

    def _story(self, fragment: str):
        return fitz.Story(html=_doc(fragment), user_css=CSS)

    def _rect(self):
        return fitz.Rect(self.x0, self.y, self.x1, self.bottom)

    def _probe(self, fragment: str, rect: fitz.Rect):
        story = self._story(fragment)
        more, filled = story.place(rect)
        return (not bool(more)), fitz.Rect(filled), story

    def _draw_fitting(self, fragment: str, rect: fitz.Rect, gap: float) -> bool:
        fits, filled, story = self._probe(fragment, rect)
        if not fits:
            return False
        story.draw(self.device)
        self.y = max(self.y, filled.y1) + gap
        return True

    def _flow_oversized(self, fragment: str, gap: float):
        story = self._story(fragment)
        while True:
            if not self.page_open:
                self._start_page()
            more, filled = story.place(self._rect())
            filled = fitz.Rect(filled)
            story.draw(self.device)
            if not more:
                self.y = max(self.y, filled.y1) + gap
                return
            self._end_page()
            self._start_page()

    def place_html(self, fragment: str, gap: float = 5.0, keep: bool = True):
        if not fragment:
            return
        if not self.page_open:
            self._start_page()
        if self._draw_fitting(fragment, self._rect(), gap):
            return
        fits_full, _, _ = self._probe(fragment, self.full_rect)
        if keep and fits_full and self.y > self.top + 1:
            self._end_page()
            self._start_page()
            if self._draw_fitting(fragment, self._rect(), gap):
                return
        self._flow_oversized(fragment, gap)

    def _max_rows_that_fit(self, prefix: str, headers, rows: Sequence[str], rect: fitz.Rect, continued=False) -> int:
        best = 0
        for count in range(1, len(rows) + 1):
            frag = prefix + _table_html(headers, rows[:count], continued=continued)
            fits, _, _ = self._probe(frag, rect)
            if fits:
                best = count
            else:
                break
        return best

    def place_vocab(self, prefix: str, headers, rows: List[str], gap: float = 6.0):
        if not rows:
            self.place_html(prefix, gap=gap, keep=True)
            return
        if not self.page_open:
            self._start_page()
        whole = prefix + _table_html(headers, rows)
        if self._draw_fitting(whole, self._rect(), gap):
            return
        fits_full, _, _ = self._probe(whole, self.full_rect)
        remaining_height = self.bottom - self.y
        if fits_full and remaining_height < self.usable_height * 0.24:
            self._end_page()
            self._start_page()
            self._draw_fitting(whole, self._rect(), gap)
            return

        pending = list(rows)
        first = True
        while pending:
            if not self.page_open:
                self._start_page()
            pfx = prefix if first else ''
            max_rows = self._max_rows_that_fit(pfx, headers, pending, self._rect(), continued=not first)
            if max_rows < 2 and len(pending) > 2 and self.y > self.top + 1:
                self._end_page()
                self._start_page()
                max_rows = self._max_rows_that_fit(pfx, headers, pending, self._rect(), continued=not first)
            if max_rows <= 0:
                self._flow_oversized(pfx + _table_html(headers, pending[:1], continued=not first), 0)
                pending = pending[1:]
                first = False
                continue
            if len(pending) - max_rows == 1 and max_rows > 2:
                max_rows -= 1
            frag = pfx + _table_html(headers, pending[:max_rows], continued=not first)
            if not self._draw_fitting(frag, self._rect(), 0):
                self._flow_oversized(frag, 0)
            pending = pending[max_rows:]
            first = False
            if pending:
                self._end_page()
                self._start_page()
        self.y += gap

    def _max_lines_that_fit(self, prefix: str, lines: Sequence[str], rect: fitz.Rect) -> int:
        best = 0
        for count in range(1, len(lines) + 1):
            frag = prefix + '<div class="dialogue">' + ''.join(lines[:count]) + '</div>'
            fits, _, _ = self._probe(frag, rect)
            if fits:
                best = count
            else:
                break
        return best

    def place_dialogue(self, prefix: str, lines: List[str], gap: float = 5.0):
        if not lines:
            self.place_html(prefix, gap=gap, keep=True)
            return
        if not self.page_open:
            self._start_page()
        whole = prefix + '<div class="dialogue">' + ''.join(lines) + '</div>'
        if self._draw_fitting(whole, self._rect(), gap):
            return
        fits_full, _, _ = self._probe(whole, self.full_rect)
        remaining_height = self.bottom - self.y
        if fits_full and remaining_height < self.usable_height * 0.22:
            self._end_page()
            self._start_page()
            self._draw_fitting(whole, self._rect(), gap)
            return

        pending = list(lines)
        first = True
        while pending:
            pfx = prefix if first else ''
            max_lines = self._max_lines_that_fit(pfx, pending, self._rect())
            if max_lines < 2 and len(pending) > 2 and self.y > self.top + 1:
                self._end_page()
                self._start_page()
                max_lines = self._max_lines_that_fit(pfx, pending, self._rect())
            if max_lines <= 0:
                self._flow_oversized(pfx + '<div class="dialogue">' + pending[0] + '</div>', 0)
                pending = pending[1:]
                first = False
                continue
            if len(pending) - max_lines == 1 and max_lines > 2:
                max_lines -= 1
            frag = pfx + '<div class="dialogue">' + ''.join(pending[:max_lines]) + '</div>'
            self._draw_fitting(frag, self._rect(), 0)
            pending = pending[max_lines:]
            first = False
            if pending:
                self._end_page()
                self._start_page()
        self.y += gap

    def page_break(self):
        self._end_page()
        self._start_page()

    def finish(self) -> bytes:
        self._end_page()
        self.writer.close()
        doc = fitz.open(self.temp_path)
        total = len(doc)
        page_word = 'Sayfa' if self.is_tr else 'Page'
        for idx, page in enumerate(doc):
            if idx > 0:
                page.insert_text(fitz.Point(38, 27), f'AulaAI · {self.course_name}', fontsize=7, color=(0.42, 0.42, 0.42))
            page.insert_text(fitz.Point(38, 823), 'AulaAI Educational System · Self-Contained Course Material', fontsize=6.7, color=(0.42, 0.42, 0.42))
            page.insert_text(fitz.Point(493, 823), f'{page_word} {idx + 1} / {total}', fontsize=6.7, color=(0.42, 0.42, 0.42))
        out = doc.tobytes()
        doc.close()
        try:
            os.remove(self.temp_path)
        except Exception:
            pass
        return out


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

        chapters = db.execute(
            'SELECT id, number, title FROM chapters WHERE course_id = ? ORDER BY number ASC, id ASC',
            (course_id,)
        ).fetchall()

        for ch_id, ch_num, ch_title in chapters:
            display_ch = _localized_title(ch_title, is_tr, None, title_maps)
            unit_word = 'Ünite' if is_tr else 'Unit'
            unit_html = f'<div class="unit">{unit_word} {_e(ch_num)}: {_e(display_ch)}</div>'
            chapter_prefix_pending = unit_html

            topics = db.execute(
                'SELECT id, type, title, content FROM topics WHERE chapter_id = ? ORDER BY sort_order ASC, id ASC',
                (ch_id,)
            ).fetchall()
            if not topics:
                paginator.place_html(chapter_prefix_pending, keep=True)
                continue

            for _top_id, top_type, top_title, top_content in topics:
                try:
                    content = json.loads(top_content) if top_content else {}
                except Exception:
                    content = {}
                display_top = _localized_title(top_title, is_tr, content, title_maps)
                topic_html = (
                    f'<div class="topic">{_e(display_top or ("Konu" if is_tr else "Topic"))}</div>'
                    f'<div class="kind">{_e(_kind(top_type, is_tr))}</div>'
                )
                topic_prefix_pending = chapter_prefix_pending + topic_html
                chapter_prefix_pending = ''
                pages = content.get('pages') or []
                if not pages:
                    paginator.place_html(topic_prefix_pending, keep=True)
                    continue

                for page in pages:
                    ptype = page.get('type', '')
                    title = _pick(page, 'title', 'title_tr', is_tr)
                    section = f'<div class="sec">{_e(title)}</div>' if title else ''
                    prefix = topic_prefix_pending + section
                    topic_prefix_pending = ''

                    if ptype in ('overview', 'grammar'):
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        body = prefix + (f'<div class="rule"><p class="p">{_e(text)}</p></div>' if text else '')
                        paginator.place_html(body, gap=5, keep=True)

                    elif ptype == 'vocabulary':
                        items = page.get('items') or []
                        if not items:
                            paginator.place_html(prefix, keep=True)
                            continue
                        headers = (
                            'Terim / Kelime' if is_tr else 'Term / Word',
                            'Telaffuz' if is_tr else 'Phonetic',
                            'Anlam' if is_tr else 'Translation',
                            'Hedef Dilde Örnek' if is_tr else 'Target-Language Example',
                            'Türkçe Çeviri' if is_tr else 'English Translation',
                        )
                        rows = []
                        for item in items:
                            term = item.get('term') or item.get('word') or ''
                            phon = item.get('phonetic') or ''
                            meaning = item.get('translation_tr') if is_tr else (item.get('translation') or item.get('translation_en'))
                            if not meaning:
                                meaning = item.get('translation') or ''
                            ex_target = item.get('example') or item.get('example_target') or item.get('target_example') or ''
                            ex_translation = item.get('example_tr') if is_tr else item.get('example_en')
                            if not ex_translation:
                                ex_translation = item.get('example_en') or item.get('example_tr') or ''
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

                    elif ptype == 'examples':
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        intro = prefix + (f'<p class="p">{_e(text)}</p>' if text else '')
                        lines = []
                        for d in page.get('dialogue') or []:
                            spk = d.get('speaker') or '?'
                            said = d.get('text') or d.get('line') or ''
                            translated = d.get('line_tr') if is_tr else d.get('line_en')
                            trans_html = f' <span class="translation">({_e(translated)})</span>' if translated else ''
                            lines.append(f'<div class="line"><span class="speaker">{_e(spk)}:</span> “{_e(said)}”{trans_html}</div>')
                        paginator.place_dialogue(intro, lines)

                    elif ptype == 'comparisons':
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        intro = prefix + (f'<p class="p">{_e(text)}</p>' if text else '')
                        if intro:
                            paginator.place_html(intro, gap=3, keep=True)
                        for cmp in page.get('comparisons') or []:
                            ctx = _pick(cmp, 'context', 'context_tr', is_tr)
                            target = cmp.get('target') or ''
                            trans = _pick(cmp, 'translation', 'translation_tr', is_tr)
                            note = _pick(cmp, 'note', 'note_tr', is_tr) or cmp.get('note') or ''
                            frag = (
                                f'<div class="compare"><strong>{_e(ctx)}</strong> {_e(target)}'
                                + (f' → {_e(trans)}' if trans else '')
                                + (f' <span class="translation">{_e(note)}</span>' if note else '')
                                + '</div>'
                            )
                            paginator.place_html(frag, gap=3, keep=True)

                    elif ptype == 'mcq':
                        question_counter += 1
                        prompt = _pick(page, 'prompt_en', 'prompt_tr', is_tr) or page.get('prompt') or ''
                        raw_options = page.get('options') or []
                        localized_options = page.get('options_tr') if is_tr else page.get('options_en')
                        options = localized_options if isinstance(localized_options, list) and len(localized_options) == len(raw_options) else raw_options
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
                            if idx < len(options):
                                display_answer = str(options[idx])
                        except Exception:
                            pass
                        answers.append({'number': question_counter, 'letter': letter, 'answer': display_answer, 'explanation': explanation})

                    else:
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        body = prefix + (f'<p class="p">{_e(text)}</p>' if text else '')
                        paginator.place_html(body, gap=5, keep=True)

        if answers:
            paginator.page_break()
            key_title = 'Cevap Anahtarı' if is_tr else 'Answer Key'
            paginator.place_html(f'<div class="unit">{key_title}</div>', gap=4, keep=True)
            for entry in answers:
                key = f"{entry['number']}. " + ((entry['letter'] + ') ') if entry['letter'] else '') + entry['answer']
                expl = f' <span class="translation">{_e(entry["explanation"])}</span>' if entry.get('explanation') else ''
                paginator.place_html(f'<div class="answer">{_e(key)}{expl}</div>', gap=2, keep=True)

        pdf_bytes = paginator.finish()
        return pdf_bytes, course_name
