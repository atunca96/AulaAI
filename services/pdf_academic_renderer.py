import html
import json
import os
import tempfile
from typing import Dict, List, Tuple

import fitz

from database import db_connection


CSS = r'''
@page { margin: 0; }
body { font-family: sans-serif; font-size: 9pt; color: #111827; line-height: 1.38; }
.cover { text-align: center; margin: 2px 0 18px 0; padding-bottom: 12px; border-bottom: 1px solid #9ca3af; }
.cover-title { font-size: 20pt; font-weight: 700; margin: 0 0 5px 0; color: #111827; }
.cover-sub { font-size: 10.5pt; font-weight: 600; margin: 0 0 3px 0; color: #374151; }
.cover-meta { font-size: 7.5pt; color: #6b7280; }
.unit { font-size: 13pt; font-weight: 700; margin: 14px 0 7px 0; padding-bottom: 4px; border-bottom: 1px solid #9ca3af; color: #111827; }
.topic { font-size: 10.5pt; font-weight: 700; margin: 8px 0 5px 0; color: #111827; }
.kind { font-size: 7pt; font-weight: 600; color: #6b7280; margin-left: 5px; }
.sec { font-size: 8.2pt; font-weight: 700; margin: 6px 0 4px 0; color: #374151; }
.p { margin: 0; color: #374151; }
.rule { border-left: 1.5px solid #9ca3af; padding-left: 8px; margin: 0 0 6px 0; }
.keep { width: 100%; border-collapse: collapse; margin: 0 0 6px 0; }
.keep > tbody > tr > td, .keep > tr > td { border: none; padding: 0; vertical-align: top; }
.dialogue { margin: 0 0 5px 0; }
.line { margin: 0 0 3px 0; }
.speaker { font-weight: 700; color: #1f2937; }
.translation { color: #6b7280; font-style: italic; }
table.vocab { width: 100%; border-collapse: collapse; margin: 4px 0 8px 0; font-size: 7.4pt; }
table.vocab th { text-align: left; font-weight: 700; color: #111827; background: #f3f4f6; border-top: 0.7px solid #9ca3af; border-bottom: 0.7px solid #9ca3af; padding: 4px 5px; }
table.vocab td { vertical-align: top; border-bottom: 0.4px solid #d1d5db; padding: 4px 5px; line-height: 1.28; }
table.vocab tr { page-break-inside: avoid; break-inside: avoid; }
.term { font-weight: 700; }
.phon { color: #4b5563; font-size: 7pt; }
.meaning { color: #065f46; }
.example { color: #374151; }
.example-tr { color: #6b7280; }
.mcq { border: 0.6px solid #cbd5e1; padding: 7px 9px; margin: 0; }
.mcq-q { font-weight: 700; margin: 0 0 5px 0; color: #111827; }
.mcq-opt { margin: 2px 0; color: #374151; }
.compare { border-top: 0.5px solid #d1d5db; padding-top: 4px; margin-top: 4px; }
.answer-key { page-break-before: always; }
.answer { margin: 0 0 4px 0; }
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


def _keep(inner: str) -> str:
    return f'<table class="keep"><tr><td>{inner}</td></tr></table>'


def _render_html(html_text: str, course_name: str, is_tr: bool) -> bytes:
    fd, temp_path = tempfile.mkstemp(suffix='.pdf')
    os.close(fd)
    try:
        story = fitz.Story(html=html_text, user_css=CSS)
        writer = fitz.DocumentWriter(temp_path)
        story.write(writer, lambda n, filled: (fitz.paper_rect('a4'), fitz.Rect(38, 42, 557, 801), None))
        writer.close()

        doc = fitz.open(temp_path)
        total = len(doc)
        page_word = 'Sayfa' if is_tr else 'Page'
        for idx, page in enumerate(doc):
            if idx > 0:
                page.insert_text(fitz.Point(38, 27), f'AulaAI · {course_name}', fontsize=7, color=(0.42, 0.42, 0.42))
            page.insert_text(fitz.Point(38, 823), 'AulaAI Educational System · Self-Contained Course Material', fontsize=6.7, color=(0.42, 0.42, 0.42))
            page.insert_text(fitz.Point(493, 823), f'{page_word} {idx + 1} / {total}', fontsize=6.7, color=(0.42, 0.42, 0.42))
        out = doc.tobytes()
        doc.close()
        return out
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass


def render_course_pdf(course_id: str, lang: str = 'en') -> Tuple[bytes, str]:
    is_tr = (lang == 'tr')
    answers: List[Dict] = []
    question_counter = 0
    parts = ["<!doctype html><html><head><meta charset='utf-8'></head><body>"]

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
        level_word = 'Seviye' if is_tr else 'Level'
        parts.append(
            f'<div class="cover"><div class="cover-title">{_e(course_name)}</div>'
            f'<div class="cover-sub">{_e(course_lang)} · {level_word} {_e(course_level)}{sem}</div>'
            f'<div class="cover-meta">AulaAI — {meta}</div></div>'
        )

        chapters = db.execute(
            'SELECT id, number, title FROM chapters WHERE course_id = ? ORDER BY number ASC, id ASC',
            (course_id,)
        ).fetchall()

        for ch_id, ch_num, ch_title in chapters:
            unit_word = 'Ünite' if is_tr else 'Unit'
            unit_html = f'<div class="unit">{unit_word} {_e(ch_num)}: {_e(ch_title)}</div>'
            chapter_prefix_pending = unit_html

            topics = db.execute(
                'SELECT id, type, title, content FROM topics WHERE chapter_id = ? ORDER BY sort_order ASC, id ASC',
                (ch_id,)
            ).fetchall()

            if not topics:
                parts.append(_keep(chapter_prefix_pending))
                continue

            for _top_id, top_type, top_title, top_content in topics:
                topic_html = (
                    f'<div class="topic">{_e(top_title or ("Konu" if is_tr else "Topic"))}'
                    f'<span class="kind">{_e(_kind(top_type, is_tr))}</span></div>'
                )
                topic_prefix_pending = chapter_prefix_pending + topic_html
                chapter_prefix_pending = ''

                try:
                    content = json.loads(top_content) if top_content else {}
                except Exception:
                    content = {}
                pages = content.get('pages') or []

                if not pages:
                    parts.append(_keep(topic_prefix_pending))
                    continue

                for page in pages:
                    ptype = page.get('type', '')
                    title = _pick(page, 'title', 'title_tr', is_tr)
                    section = f'<div class="sec">{_e(title)}</div>' if title else ''
                    prefix = topic_prefix_pending + section
                    topic_prefix_pending = ''

                    if ptype in ('overview', 'grammar'):
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        if text:
                            body = prefix + f'<div class="rule"><p class="p">{_e(text)}</p></div>'
                            parts.append(_keep(body) if len(str(text)) <= 700 else body)
                        elif prefix:
                            parts.append(_keep(prefix))

                    elif ptype == 'vocabulary':
                        items = page.get('items') or []
                        if not items:
                            if prefix:
                                parts.append(_keep(prefix))
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
                        parts.append(prefix + table)

                    elif ptype == 'examples':
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        dialogue = page.get('dialogue') or []
                        if prefix or text:
                            intro = prefix + (f'<p class="p">{_e(text)}</p>' if text else '')
                            parts.append(_keep(intro) if len(str(text or '')) <= 500 else intro)
                        # Keep 3 dialogue lines at a time: no split line, no giant empty page.
                        for i in range(0, len(dialogue), 3):
                            chunk = dialogue[i:i+3]
                            lines = []
                            for d in chunk:
                                spk = d.get('speaker') or '?'
                                said = d.get('text') or d.get('line') or ''
                                translated = d.get('line_tr') if is_tr else d.get('line_en')
                                trans_html = f' <span class="translation">({_e(translated)})</span>' if translated else ''
                                lines.append(f'<div class="line"><span class="speaker">{_e(spk)}:</span> “{_e(said)}”{trans_html}</div>')
                            parts.append(_keep('<div class="dialogue">' + ''.join(lines) + '</div>'))

                    elif ptype == 'comparisons':
                        text = _pick(page, 'text', 'text_tr', is_tr)
                        if prefix or text:
                            intro = prefix + (f'<p class="p">{_e(text)}</p>' if text else '')
                            parts.append(_keep(intro) if len(str(text or '')) <= 500 else intro)
                        for cmp in page.get('comparisons') or []:
                            ctx = _pick(cmp, 'context', 'context_tr', is_tr)
                            target = cmp.get('target') or ''
                            trans = _pick(cmp, 'translation', 'translation_tr', is_tr)
                            note = _pick(cmp, 'note', 'note_tr', is_tr) or cmp.get('note') or ''
                            parts.append(_keep(
                                f'<div class="compare"><strong>{_e(ctx)}</strong> {_e(target)}'
                                + (f' → {_e(trans)}' if trans else '')
                                + (f' <span class="translation">{_e(note)}</span>' if note else '')
                                + '</div>'
                            ))

                    elif ptype == 'mcq':
                        question_counter += 1
                        prompt = _pick(page, 'prompt_en', 'prompt_tr', is_tr) or page.get('prompt') or ''
                        raw_options = page.get('options') or []
                        localized_options = page.get('options_tr') if is_tr else page.get('options_en')
                        options = localized_options if isinstance(localized_options, list) and len(localized_options) == len(raw_options) else raw_options
                        opts_html = ''.join(f'<div class="mcq-opt">{chr(65+i)}) {_e(opt)}</div>' for i, opt in enumerate(options))
                        # Native one-row table is the non-splittable unit in Story.
                        parts.append(_keep(prefix + f'<div class="mcq"><div class="mcq-q">{question_counter}. {_e(prompt)}</div>{opts_html}</div>'))

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
                        if prefix or text:
                            body = prefix + (f'<p class="p">{_e(text)}</p>' if text else '')
                            parts.append(_keep(body) if len(str(text or '')) <= 700 else body)

    if answers:
        key_title = 'Cevap Anahtarı' if is_tr else 'Answer Key'
        parts.append(f'<div class="answer-key"><div class="unit">{key_title}</div>')
        for entry in answers:
            key = f"{entry['number']}. " + ((entry['letter'] + ') ') if entry['letter'] else '') + entry['answer']
            expl = f' <span class="translation">{_e(entry["explanation"])}</span>' if entry.get('explanation') else ''
            parts.append(f'<div class="answer">{_e(key)}{expl}</div>')
        parts.append('</div>')

    parts.append('</body></html>')
    pdf_bytes = _render_html(''.join(parts), course_name, is_tr)
    return pdf_bytes, course_name
