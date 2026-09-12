from pathlib import Path

path = Path('services/pdf_academic_renderer.py')
src = path.read_text(encoding='utf-8')

# V8 is language-agnostic. The failure mode was content-shape / pagination cost,
# not Spanish itself: large or legacy lessons could make the renderer perform
# hundreds/thousands of progressively larger Story probes before returning.

# 1) Replace linear O(n^2)-ish pagination probing with monotonic binary search.
old_rows = '''    def _max_rows_that_fit(self, prefix: str, headers, rows: Sequence[str], rect: fitz.Rect, continued=False) -> int:\n        best = 0\n        for count in range(1, len(rows) + 1):\n            frag = prefix + _table_html(headers, rows[:count], continued=continued)\n            fits, _, _ = self._probe(frag, rect)\n            if fits:\n                best = count\n            else:\n                break\n        return best\n'''
new_rows = '''    def _max_rows_that_fit(self, prefix: str, headers, rows: Sequence[str], rect: fitz.Rect, continued=False) -> int:\n        # Fit is monotonic: if N rows do not fit, N+1 rows cannot fit either.\n        # Binary search avoids rebuilding 1,2,3,...N progressively larger Stories.\n        lo, hi, best = 1, len(rows), 0\n        while lo <= hi:\n            count = (lo + hi) // 2\n            frag = prefix + _table_html(headers, rows[:count], continued=continued)\n            fits, _, _ = self._probe(frag, rect)\n            if fits:\n                best = count\n                lo = count + 1\n            else:\n                hi = count - 1\n        return best\n'''
if src.count(old_rows) != 1:
    raise RuntimeError(f'row-fit anchor matched {src.count(old_rows)} times')
src = src.replace(old_rows, new_rows, 1)

old_lines = '''    def _max_lines_that_fit(self, prefix: str, lines: Sequence[str], rect: fitz.Rect) -> int:\n        best = 0\n        for count in range(1, len(lines) + 1):\n            frag = prefix + '<div class="dialogue">' + ''.join(lines[:count]) + '</div>'\n            fits, _, _ = self._probe(frag, rect)\n            if fits:\n                best = count\n            else:\n                break\n        return best\n'''
new_lines = '''    def _max_lines_that_fit(self, prefix: str, lines: Sequence[str], rect: fitz.Rect) -> int:\n        lo, hi, best = 1, len(lines), 0\n        while lo <= hi:\n            count = (lo + hi) // 2\n            frag = prefix + '<div class="dialogue">' + ''.join(lines[:count]) + '</div>'\n            fits, _, _ = self._probe(frag, rect)\n            if fits:\n                best = count\n                lo = count + 1\n            else:\n                hi = count - 1\n        return best\n'''
if src.count(old_lines) != 1:
    raise RuntimeError(f'line-fit anchor matched {src.count(old_lines)} times')
src = src.replace(old_lines, new_lines, 1)

# 2) Do not build one enormous whole-table / whole-dialogue Story merely to learn
# that a large collection cannot fit on one A4 page. This was a major timeout risk.
old_vocab_probe = '''        whole = prefix + _table_html(headers, rows)\n        if self._draw_fitting(whole, self._rect(), gap):\n            return\n        fits_full, _, _ = self._probe(whole, self.full_rect)\n        remaining_height = self.bottom - self.y\n        if fits_full and remaining_height < self.usable_height * 0.24:\n            self._end_page()\n            self._start_page()\n            self._draw_fitting(whole, self._rect(), gap)\n            return\n'''
new_vocab_probe = '''        whole = prefix + _table_html(headers, rows)\n        # A normal A4 page cannot usefully hold a very large vocabulary collection.\n        # For large collections, go straight to bounded page-chunk fitting instead of\n        # laying out the entire table multiple times.\n        fits_full = False\n        if len(rows) <= 36:\n            if self._draw_fitting(whole, self._rect(), gap):\n                return\n            fits_full, _, _ = self._probe(whole, self.full_rect)\n        remaining_height = self.bottom - self.y\n        if fits_full and remaining_height < self.usable_height * 0.24:\n            self._end_page()\n            self._start_page()\n            self._draw_fitting(whole, self._rect(), gap)\n            return\n'''
if src.count(old_vocab_probe) != 1:
    raise RuntimeError(f'vocab whole-probe anchor matched {src.count(old_vocab_probe)} times')
src = src.replace(old_vocab_probe, new_vocab_probe, 1)

old_dialog_probe = '''        whole = prefix + '<div class="dialogue">' + ''.join(lines) + '</div>'\n        if self._draw_fitting(whole, self._rect(), gap):\n            return\n        fits_full, _, _ = self._probe(whole, self.full_rect)\n        remaining_height = self.bottom - self.y\n        if fits_full and remaining_height < self.usable_height * 0.22:\n            self._end_page()\n            self._start_page()\n            self._draw_fitting(whole, self._rect(), gap)\n            return\n'''
new_dialog_probe = '''        whole = prefix + '<div class="dialogue">' + ''.join(lines) + '</div>'\n        fits_full = False\n        if len(lines) <= 30:\n            if self._draw_fitting(whole, self._rect(), gap):\n                return\n            fits_full, _, _ = self._probe(whole, self.full_rect)\n        remaining_height = self.bottom - self.y\n        if fits_full and remaining_height < self.usable_height * 0.22:\n            self._end_page()\n            self._start_page()\n            self._draw_fitting(whole, self._rect(), gap)\n            return\n'''
if src.count(old_dialog_probe) != 1:
    raise RuntimeError(f'dialogue whole-probe anchor matched {src.count(old_dialog_probe)} times')
src = src.replace(old_dialog_probe, new_dialog_probe, 1)

# 3) Normalize all supported historical collection keys before iterating them.
# This makes the renderer robust across languages and across old/new generated classes.
old_items = '''                    elif ptype == 'vocabulary':\n                        items = page.get('items') or []\n                        if not items:\n                            paginator.place_html(prefix, keep=True)\n                            continue\n'''
new_items = '''                    elif ptype == 'vocabulary':\n                        items = page.get('items') or page.get('vocabulary') or page.get('words') or []\n                        if isinstance(items, dict):\n                            # Some historical payloads used an object keyed by term.\n                            if items and all(isinstance(v, dict) for v in items.values()):\n                                items = list(items.values())\n                            else:\n                                items = [items]\n                        elif not isinstance(items, list):\n                            items = [items] if items not in (None, '') else []\n                        if not items:\n                            paginator.place_html(prefix, keep=True)\n                            continue\n'''
if src.count(old_items) != 1:
    raise RuntimeError(f'vocabulary collection anchor matched {src.count(old_items)} times')
src = src.replace(old_items, new_items, 1)

old_dialogue_source = '''                        lines = []\n                        dialogue_items = page.get('dialogue') or []\n'''
new_dialogue_source = '''                        lines = []\n                        dialogue_items = (page.get('dialogue') or page.get('conversations') or\n                                          page.get('conversation') or page.get('turns') or\n                                          page.get('lines') or [])\n'''
if src.count(old_dialogue_source) != 1:
    raise RuntimeError(f'dialogue collection anchor matched {src.count(old_dialogue_source)} times')
src = src.replace(old_dialogue_source, new_dialogue_source, 1)

# 4) Tighten the no-progress guard. A classroom PDF should never need hundreds of
# continuation pages for one logical block; failing fast lets the endpoint fallback
# rather than leaving a browser request spinning indefinitely.
src = src.replace("            if page_guard > 300:\n", "            if page_guard > 120:\n", 1)

path.write_text(src, encoding='utf-8')
print('Applied academic PDF v8: bounded pagination + legacy collection normalization')
