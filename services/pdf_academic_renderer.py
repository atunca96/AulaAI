import html
import json
import os
import tempfile
from typing import List, Dict, Tuple

import fitz

from database import db_connection


CSS = r'''
body { font-family: sans-serif; font-size: 9pt; color: #111827; line-height: 1.42; }
.cover { text-align: center; margin-bottom: 14px; }
.cover-title { font-size: 20pt; font-weight: 700; color: #111827; margin: 0 0 5px 0; }
.cover-sub { font-size: 11pt; font-weight: 600; color: #374151; margin: 0 0 3px 0; }
.cover-meta { font-size: 7.5pt; color: #6b7280; }
.unit { font-size: 13pt; font-weight: 700; color: #111827; margin: 8px 0 7px 0; padding-bottom: 3px; border-bottom: 1px solid #9ca3af; }
.topic { font-size: 11pt; font-weight: 700; color: #111827; margin: 6px 0 5px 0; }
.topic-kind { font-size: 7pt; font-weight: 600; color: #6b7280; margin-left: 5px; }
.sec { font-size: 8pt; font-weight: 700; color: #374151; margin: 4px 0 4px 0; }
.p { margin: 0; color: #374151; }
.rule { border-left: 1.5px solid #9ca3af; padding-left: 8px; }
.dialogue { margin: 0; }
.line { margin: 0 0 3px 0; }
.speaker { font-weight: 700; color: #374151; }
.translation { color: #6b7280; font-style: italic; }
table.vocab { width: 100%; border-collapse: collapse; font-size: 7.6pt; }
table.vocab th { text-align: left; font-weight: 700; color: #111827; border-top: 1px solid #9ca3af; border-bottom: 1px solid #9ca3af; padding: 4px 5px; background: #f3f4f6; }
table.vocab td { vertical-align: top; border-bottom: 0.45px solid #d1d5db; padding: 4px 5px; }
.term { font-weight: 700; }
.phon { color: #4f46e5; font-size: 7pt; }
.meaning { color: #047857; }
.example { color: #374151; }
.example-tr { color: #6b7280; }
.mcq { border: 0.7px solid #cbd5e1; padding: 7px 9px; }
.mcq-q { font-weight: 700; margin: 0 0 5px 0; }
.mcq-opt { margin: 2px 0; }
.compare { border-top: 0.5px solid #d1d5db; padding-top: 4px; margin-top: 3px; }
.compare strong { color: #111827; }
.answer { margin: 0 0 5px 0; }
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


def _topic_kind(kind, is_tr):
    pair = TYPE_LABELS.get(kind, (str(kind or 'lesson').replace('_', ' ').title(), str(kind or 'lesson').replace('_', ' ').title()))
    return pair[1] if is_tr else pair[0]


def _block(inner: str) -> str:
    return f'<!doctype html><html><head><meta charset="utf-8"></head><body>{inner}</body></html>'


def _render_blocks(blocks: List[str], course_name: str, is_tr: bool) -> bytes:
    mediabox = fitz.paper_rect('a4')
    x0, x1 = 40, 555
    top, bottom = 44, 798
    full_rect = fitz.Rect(x0, top, x1, bottom)

    fd, path = tempfile.mkstemp(suffix='.pdf')
    os.close(fd)
    writer = fitz.DocumentWriter(path)

    device = None
    page_open = False
    y = top

    def start_page():
        nonlocal device, page_open, y
        device = writer.begin_page(mediabox)
        page_open = True
        y = top

    def end_page():
        nonlocal page_open, device
        if page_open:
            writer.end_page()
            page_open = False
            device = None

    def make_story(fragment: str):
        return fitz.Story(html=fragment, user_css=CSS)

    def place_block(fragment: str, gap: float = 6.0):
        nonlocal y
        if not page_open:
            start_page()

        # Trial in remaining space. If it fits, commit it there.
        story = make_story(fragment)
        remaining = fitz.Rect(x0, y, x1, bottom)
        more, filled = story.place(remaining)
        if not more:
            story.draw(device)
            y = max(y, filled.y1) + gap
            return

        # It does not fit completely in the remainder. Restart the block on a fresh page.
        if y > top + 2:
            end_page()
            start_page()
            story = make_story(fragment)
            more, filled = story.place(full_rect)

        # If the block itself is taller than one page, allow only this oversized block to flow.
        while True:
            story.draw(device)
            if not more:
                y = max(top, filled.y1) + gap
                return
            end_page()
            start_page()
            more, filled = story.place(full_rect)

    for frag in blocks:
        place_block(frag)

    end_page()
    writer.close()

    doc = fitz.open(path)
    total = len(doc)
    page_word = 'Sayfa' if is_tr else 'Page'
    for i, page in enumerate(doc):
        if i > 0:
            page.insert_text(fitz.Point(40, 27), f'AulaAI · {course_name}', fontsize=7, color=(0.42, 0.42, 0.42))
        page.insert_text(fitz.Point(40, 823), 'AulaAI Educational System · Self-Contained Course Material', fontsize=6.8, color=(0.42, 0.42, 0.42))
        page.insert_text(fitz.Point(490, 823), f'{page_word} {i + 1} / {total}', fontsize=6.8, color=(0.42, 0.42, 0.42))
    out = doc.tobytes()
    doc.close()
    try:
        os.remove(path)
    except Exception:
        pass
    return out


def render_course_pdf(course_id: str, lang: str = 'en') -> Tuple[bytes, str]:
    is_tr = (lang == 'tr')
    blocks: List[str] = []
    answers: List[Dict] = []
    qnum = 0

    with db_connection() as db:
        course = db.execute('SELECT name, language, level, semester FROM courses WHERE id = ?', (course_id,)).fetchone()
        if not course:
            raise ValueError('Course not found')
        course_name = course[0] or 'Course Materials'
        course_lang = course[1] or 'General'
        course_level = course[2] or 'All Levels'
        semester = course[3] or ''

        sem = f' ({_e(semester)})' if semester else ''
        meta = 'Kapsamlı Ders Notları ve Alıştırmalar' if is_tr else 'Comprehensive Lesson Notes and Exercises'
        blocks.append(_block(
            f'<div class="cover"><div class="cover-title">{_e(course_name)}</div>'
            f'<div class="cover-sub">{_e(course_lang)} · Seviye {_e(course_level)}{sem}</div>'
            f'<div class="cover-meta">AulaAI — {meta}</div></div>'
        ))

        chapters = db.execute(
            'SELECT id, number, title, title_tr FROM chapters WHERE course_id = ? ORDER BY number ASC, id ASC',
            (course_id,)
        ).fetchall()

        for ch in chapters:
            ch_id, ch_num, ch_title, ch_title_tr = ch
            unit_word = 'Ünite' if is_tr else 'Unit'
            display_ch = ch_title_tr if (is_tr and ch_title_tr) else ch_title
            unit_prefix = f'<div class="unit">{unit_word} {_e(ch_num)}: {_e(display_ch)}</div>'

            topics = db.execute(
                'SELECT id, type, title, title_tr, content FROM topics WHERE chapter_id = ? ORDER BY sort_order ASC, id ASC',
                (ch_id,)
            ).fetchall()

            if not topics:
                blocks.append(_block(unit_prefix))
                continue

            chapter_prefix_pending = unit_prefix
            for top in topics:
                top_id, top_type, top_title, top_title_tr, top_content = top
                display_top = top_title_tr if (is_tr and top_title_tr) else top_title
                topic_prefix = chapter_prefix_pending + (
                    f'<div class="topic">{_e(display_top or ("Konu" if is_tr else "Topic"))}'
                    f'<span class="topic-kind">{_e(_topic_kind(top_type, is_tr))}</span></div>'
                )
                chapter_prefix_pending = ''

                try:
                    content = json.loads(top_content) if top_content else {}
                except Exception:
                    content = {}
                pages = content.get('pages') or []
                if not pages:
                    blocks.append(_block(topic_prefix))
                    continue

                prefix_pending = topic_prefix
                for page in pages:
                    ptype = page.get('type', '')
                    title = _pick(page, 'title', 'title_tr', is_tr)
                    section = f'<div class="sec">{_e(title)}</div>' if title else ''
                    prefix = prefix_pending + section
                    prefix_pending = ''

                    if ptype in ('overview', 'grammar'):
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        if text:
                            blocks.append(_block(prefix + f'<div class="rule"><p class="p">{_e(text)}</p></div>'))
                        elif prefix:
                            blocks.append(_block(prefix))

                    elif ptype == 'vocabulary':
                        items = page.get('items') or []
                        if not items:
                            if prefix:
                                blocks.append(_block(prefix))
                            continue
                        h_term = 'Terim / Kelime' if is_tr else 'Term / Word'
                        h_phon = 'Telaffuz' if is_tr else 'Phonetic'
                        h_mean = 'Anlam' if is_tr else 'Translation'
                        h_ex = 'Hedef Dilde Örnek' if is_tr else 'Target-Language Example'
                        h_tr = 'Türkçe Çeviri' if is_tr else 'English Translation'
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
                        table = (
                            '<table class="vocab"><tr>'
                            f'<th style="width:18%">{h_term}</th><th style="width:13%">{h_phon}</th>'
                            f'<th style="width:21%">{h_mean}</th><th style="width:27%">{h_ex}</th>'
                            f'<th style="width:21%">{h_tr}</th></tr>' + ''.join(rows) + '</table>'
                        )
                        blocks.append(_block(prefix + table))

                    elif ptype == 'examples':
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        lines = []
                        for d in page.get('dialogue') or []:
                            spk = d.get('speaker') or '?'
                            said = d.get('text') or d.get('line') or ''
                            translated = d.get('line_tr') if is_tr else d.get('line_en')
                            trans_html = f' <span class="translation">({_e(translated)})</span>' if translated else ''
                            lines.append(f'<div class="line"><span class="speaker">{_e(spk)}:</span> “{_e(said)}”{trans_html}</div>')
                        body = (f'<p class="p">{_e(text)}</p>' if text else '') + '<div class="dialogue">' + ''.join(lines) + '</div>'
                        blocks.append(_block(prefix + body))

                    elif ptype == 'comparisons':
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        comps = []
                        for cmp in page.get('comparisons') or []:
                            ctx = _pick(cmp, 'context', 'context_tr', is_tr)
                            target = cmp.get('target') or ''
                            trans = _pick(cmp, 'translation', 'translation_tr', is_tr)
                            note = _pick(cmp, 'note', 'note_tr', is_tr) or cmp.get('note') or ''
                            comps.append(
                                f'<div class="compare"><strong>{_e(ctx)}</strong> {_e(target)}'
                                + (f' → {_e(trans)}' if trans else '')
                                + (f' <span class="translation">{_e(note)}</span>' if note else '')
                                + '</div>'
                            )
                        blocks.append(_block(prefix + (f'<p class="p">{_e(text)}</p>' if text else '') + ''.join(comps)))

                    elif ptype == 'mcq':
                        qnum += 1
                        prompt = _pick(page, 'prompt_en', 'prompt_tr', is_tr) or page.get('prompt') or ''
                        raw_options = page.get('options') or []
                        localized_options = page.get('options_tr') if is_tr else page.get('options_en')
                        options = localized_options if isinstance(localized_options, list) and len(localized_options) == len(raw_options) else raw_options
                        opts_html = ''.join(f'<div class="mcq-opt">{chr(65+i)}) {_e(opt)}</div>' for i, opt in enumerate(options))
                        blocks.append(_block(prefix + f'<div class="mcq"><div class="mcq-q">{qnum}. {_e(prompt)}</div>{opts_html}</div>'))
                        answer = page.get('answer') or ''
                        letter = ''
                        display_answer = answer
                        try:
                            idx = [str(x).strip() for x in raw_options].index(str(answer).strip())
                            letter = chr(65 + idx)
                            if idx < len(options):
                                display_answer = options[idx]
                        except Exception:
                            pass
                        answers.append({'n': qnum, 'letter': letter, 'answer': display_answer, 'explanation': _pick(page, 'explanation', 'explanation_tr', is_tr)})

                    else:
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        if prefix or text:
                            blocks.append(_block(prefix + (f'<p class="p">{_e(text)}</p>' if text else '')))

    if answers:
        title = 'Cevap Anahtarı' if is_tr else 'Answer Key'
        blocks.append(_block(f'<div class="unit">{title}</div>'))
        for entry in answers:
            key = f"{entry['n']}. " + (f"{entry['letter']}) " if entry.get('letter') else '') + _e(entry.get('answer'))
            expl = f' <span class="translation">{_e(entry.get("explanation"))}</span>' if entry.get('explanation') else ''
            blocks.append(_block(f'<div class="answer"><strong>{key}</strong>{expl}</div>'))

    return _render_blocks(blocks, course_name, is_tr), course_name
