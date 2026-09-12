from pathlib import Path

path = Path('services/pdf_academic_renderer.py')
src = path.read_text(encoding='utf-8')

# 1) Allow an emergency table-row split only when a single vocabulary row is
# taller than a full A4 content area. Normal rows remain atomic.
old_story = '''    def _story(self, fragment: str):
        return fitz.Story(html=_doc(fragment), user_css=CSS)
'''
new_story = '''    def _story(self, fragment: str, allow_row_split: bool = False):
        css = CSS
        if allow_row_split:
            css += "\\ntable.vocab tr { page-break-inside: auto !important; break-inside: auto !important; }"
        return fitz.Story(html=_doc(fragment), user_css=css)
'''
if src.count(old_story) != 1:
    raise RuntimeError(f'_story anchor matched {src.count(old_story)} times')
src = src.replace(old_story, new_story, 1)

old_flow = '''    def _flow_oversized(self, fragment: str, gap: float):
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
'''
new_flow = '''    def _flow_oversized(self, fragment: str, gap: float, allow_row_split: bool = False):
        # Oversized logical blocks are allowed to flow, but never let PyMuPDF
        # enter a no-progress page loop (possible with an unsplittable tall row).
        story = self._story(fragment, allow_row_split=allow_row_split)
        page_guard = 0
        while True:
            page_guard += 1
            if page_guard > 300:
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
                # If this happened in remaining space, retry once from a fresh page.
                if self.y > self.top + 1:
                    self._end_page()
                    self._start_page()
                    continue
                # A full fresh page still cannot accept the block. Rebuild the
                # story with row splitting enabled. This only affects pathological
                # single rows that are themselves taller than one page.
                if not allow_row_split:
                    story = self._story(fragment, allow_row_split=True)
                    allow_row_split = True
                    continue
                raise RuntimeError('PDF block cannot make pagination progress')
            self._end_page()
            self._start_page()
'''
if src.count(old_flow) != 1:
    raise RuntimeError(f'_flow_oversized anchor matched {src.count(old_flow)} times')
src = src.replace(old_flow, new_flow, 1)

old_single_row = '''            if max_rows <= 0:
                self._flow_oversized(pfx + _table_html(headers, pending[:1], continued=not first), 0)
                pending = pending[1:]
                first = False
                continue
'''
new_single_row = '''            if max_rows <= 0:
                # Pathological legacy material can contain one vocabulary row
                # taller than an entire page. Keep ordinary rows atomic, but let
                # this one exceptional row flow rather than hanging forever.
                self._flow_oversized(
                    pfx + _table_html(headers, pending[:1], continued=not first),
                    0,
                    allow_row_split=True,
                )
                pending = pending[1:]
                first = False
                continue
'''
if src.count(old_single_row) != 1:
    raise RuntimeError(f'single-row anchor matched {src.count(old_single_row)} times')
src = src.replace(old_single_row, new_single_row, 1)

# 2) Normalize historical/heterogeneous lesson JSON instead of assuming every
# old course already has the current {pages:[...]} schema.
old_content = '''                try:
                    content = json.loads(top_content) if top_content else {}
                except Exception:
                    content = {}
'''
new_content = '''                try:
                    content = json.loads(top_content) if top_content else {}
                except Exception:
                    content = {}
                if isinstance(content, list):
                    content = {'pages': content}
                elif not isinstance(content, dict):
                    content = {}
'''
if src.count(old_content) != 1:
    raise RuntimeError(f'content normalization anchor matched {src.count(old_content)} times')
src = src.replace(old_content, new_content, 1)

old_pages = '''                pages = content.get('pages') or []
                if not pages:
                    paginator.place_html(topic_prefix_pending, keep=True)
                    continue

                for page in pages:
                    ptype = page.get('type', '')
'''
new_pages = '''                pages = content.get('pages') or []
                if isinstance(pages, dict):
                    pages = [pages]
                elif not isinstance(pages, list):
                    pages = []
                pages = [p for p in pages if isinstance(p, dict)]
                if not pages:
                    paginator.place_html(topic_prefix_pending, keep=True)
                    continue

                for page in pages:
                    ptype = page.get('type', '')
'''
if src.count(old_pages) != 1:
    raise RuntimeError(f'pages normalization anchor matched {src.count(old_pages)} times')
src = src.replace(old_pages, new_pages, 1)

old_items = '''                        rows = []
                        for item in items:
                            term = item.get('term') or item.get('word') or ''
'''
new_items = '''                        rows = []
                        for item in items:
                            if not isinstance(item, dict):
                                item = {'term': str(item)}
                            term = item.get('term') or item.get('word') or ''
'''
if src.count(old_items) != 1:
    raise RuntimeError(f'items normalization anchor matched {src.count(old_items)} times')
src = src.replace(old_items, new_items, 1)

old_dialogue = '''                        lines = []
                        for d in page.get('dialogue') or []:
                            spk = d.get('speaker') or '?'
'''
new_dialogue = '''                        lines = []
                        dialogue_items = page.get('dialogue') or []
                        if isinstance(dialogue_items, dict):
                            dialogue_items = [dialogue_items]
                        elif not isinstance(dialogue_items, list):
                            dialogue_items = [str(dialogue_items)] if dialogue_items else []
                        for d in dialogue_items:
                            if not isinstance(d, dict):
                                d = {'text': str(d)}
                            spk = d.get('speaker') or '?'
'''
if src.count(old_dialogue) != 1:
    raise RuntimeError(f'dialogue normalization anchor matched {src.count(old_dialogue)} times')
src = src.replace(old_dialogue, new_dialogue, 1)

old_comparisons = '''                        for cmp in page.get('comparisons') or []:
                            ctx = _pick(cmp, 'context', 'context_tr', is_tr)
'''
new_comparisons = '''                        comparison_items = page.get('comparisons') or []
                        if isinstance(comparison_items, dict):
                            comparison_items = [comparison_items]
                        elif not isinstance(comparison_items, list):
                            comparison_items = [str(comparison_items)] if comparison_items else []
                        for cmp in comparison_items:
                            if not isinstance(cmp, dict):
                                cmp = {'target': str(cmp)}
                            ctx = _pick(cmp, 'context', 'context_tr', is_tr)
'''
if src.count(old_comparisons) != 1:
    raise RuntimeError(f'comparison normalization anchor matched {src.count(old_comparisons)} times')
src = src.replace(old_comparisons, new_comparisons, 1)

# 3) Defensive option normalization for legacy MCQ shapes.
old_options = '''                        raw_options = page.get('options') or []
                        localized_options = page.get('options_tr') if is_tr else page.get('options_en')
                        options = localized_options if isinstance(localized_options, list) and len(localized_options) == len(raw_options) else raw_options
'''
new_options = '''                        raw_options = page.get('options') or []
                        if isinstance(raw_options, dict):
                            raw_options = list(raw_options.values())
                        elif not isinstance(raw_options, list):
                            raw_options = [raw_options] if raw_options else []
                        localized_options = page.get('options_tr') if is_tr else page.get('options_en')
                        options = localized_options if isinstance(localized_options, list) and len(localized_options) == len(raw_options) else raw_options
'''
if src.count(old_options) != 1:
    raise RuntimeError(f'options normalization anchor matched {src.count(old_options)} times')
src = src.replace(old_options, new_options, 1)

path.write_text(src, encoding='utf-8')
print('Applied academic PDF v6: no-progress guard + legacy content hardening')
