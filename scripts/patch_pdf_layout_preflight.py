from pathlib import Path

path = Path('server.py')
src = path.read_text(encoding='utf-8')

anchor = '''            full_html = "".join(parts)

            # ── Render with fitz.Story ────────────────────────────────────────
'''
replacement = '''            full_html = "".join(parts)

            # ── Measured pagination preflight ────────────────────────────────
            # PyMuPDF Story does not reliably honor CSS break-inside rules for
            # complex HTML. Instead of forcing every block onto a new page, tag
            # only coherent short blocks, perform an actual Story layout pass,
            # detect which tagged blocks are split across pages, and insert a
            # page break only before blocks that genuinely split. Repeat a few
            # times because moving one block can change later page boundaries.
            import re as _pdf_re

            _keep_seq = [0]
            def _next_keep_id(kind):
                _keep_seq[0] += 1
                return f"pdfkeep-{kind}-{_keep_seq[0]}"

            # MCQ boxes are always short enough to remain intact.
            def _tag_mcq(m):
                return f'<div class="mcq-box" id="{_next_keep_id("mcq")}">'
            full_html = _pdf_re.sub(r'<div class="mcq-box">', _tag_mcq, full_html)

            # Keep contiguous dialogue lines together. We only tag groups with
            # 2+ lines, leaving isolated lines alone.
            def _tag_dialogue(m):
                kid = _next_keep_id("dialogue")
                return f'<div id="{kid}">' + m.group(0) + '</div>'
            full_html = _pdf_re.sub(
                r'(?:<div class="diag-line">.*?</div>){2,}',
                _tag_dialogue,
                full_html,
                flags=_pdf_re.S,
            )

            # Short vocabulary tables should stay together; long tables remain
            # naturally pageable by rows.
            def _tag_vocab(m):
                table_html = m.group(0)
                if table_html.count('<tr>') <= 10:
                    kid = _next_keep_id("vocab")
                    return table_html.replace('<table class="vt">', f'<table class="vt" id="{kid}">', 1)
                return table_html
            full_html = _pdf_re.sub(r'<table class="vt">.*?</table>', _tag_vocab, full_html, flags=_pdf_re.S)

            def _split_keep_ids(html_text):
                probe = fitz.Story(html=html_text)
                page_rect = fitz.paper_rect("a4")
                content_rect = fitz.Rect(36, 44, 559, 800)
                starts = {}
                ends = {}
                page_no = 0
                more = 1

                while more:
                    more, _ = probe.place(content_rect)
                    current_page = page_no

                    def _record(pos):
                        kid = getattr(pos, 'id', None)
                        if not kid or not str(kid).startswith('pdfkeep-'):
                            return
                        flags = int(getattr(pos, 'open_close', 0) or 0)
                        if flags & 1 and kid not in starts:
                            starts[kid] = current_page
                        if flags & 2:
                            ends[kid] = current_page

                    probe.element_positions(_record)
                    page_no += 1
                    if page_no > 400:
                        break

                return {kid for kid, start_page in starts.items() if ends.get(kid, start_page) != start_page}

            _already_forced = set()
            for _pass in range(4):
                _split_ids = _split_keep_ids(full_html)
                _targets = [kid for kid in _split_ids if kid not in _already_forced]
                if not _targets:
                    break
                changed = False
                for kid in _targets:
                    marker = f'id="{kid}"'
                    pos = full_html.find(marker)
                    if pos < 0:
                        continue
                    tag_start = full_html.rfind('<', 0, pos)
                    if tag_start < 0:
                        continue
                    # If an MCQ has a section heading immediately before it,
                    # move that heading with the question instead of orphaning it.
                    break_at = tag_start
                    if '-mcq-' in kid:
                        prefix = full_html[max(0, tag_start - 800):tag_start]
                        hm = list(_pdf_re.finditer(r'<div class="sec-h">.*?</div>\\s*$', prefix, flags=_pdf_re.S))
                        if hm:
                            break_at = max(0, tag_start - 800) + hm[-1].start()
                    full_html = full_html[:break_at] + '<div style="page-break-before:always"></div>' + full_html[break_at:]
                    _already_forced.add(kid)
                    changed = True
                if not changed:
                    break

            # ── Render with fitz.Story ────────────────────────────────────────
'''

count = src.count(anchor)
if count != 1:
    raise RuntimeError(f'PDF preflight anchor matched {count} times')
src = src.replace(anchor, replacement, 1)
path.write_text(src, encoding='utf-8')
print('Applied measured PDF pagination preflight')
