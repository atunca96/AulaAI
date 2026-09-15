"""Make a rendered PDF's text layer say what the page says.

A PDF carries two parallel representations of the same words. The visual layer is
a sequence of glyph indices positioned on the page; the semantic layer is the
font's ToUnicode CMap, which says what each of those glyphs *means*. Copy, search,
extraction, screen readers and every downstream parser read the second one. A page
can therefore look perfect and still be unreadable to everything that is not a
pair of eyes, and nothing about rendering it will report a problem.

That is what happened to Arabic here. Shaping a cursive script replaces each
letter with a positional variant - initial, medial, final, isolated - and the
renderer builds the CMap by asking the font which character each glyph came from.
Fonts answer that question with the legacy Arabic Presentation Forms codepoints
(U+FB50..U+FDFF, U+FE70..U+FEFF), because those are what their compatibility cmap
tables contain. So a page reading `العربية` extracted as `ﺍﻟﻌﺮﺑﻴﺔ`: visually
identical, semantically a different string, matching no search, and mapping to
characters no Arabic keyboard can produce.

The repair belongs here rather than at the renderer's input, because the
substitution happens inside the layout engine, after the text has left our hands.
Rewriting the CMap after the page is drawn corrects the semantic layer and touches
no glyph, so shaping, ligatures, joining and diacritic placement come out exactly
as the renderer produced them.

The mapping is not invented and is not language-specific: a presentation form's
canonical character is its Unicode compatibility decomposition, so NFKC *is* the
answer, and it is the answer for every script with a presentation-forms block -
Arabic, the Hebrew forms above it, and the Latin `ﬁ`/`ﬂ` ligatures that make a
search for "file" fail. Normalization is applied ONLY to codepoints inside those
blocks. That restriction is the whole safety argument: NFKC applied blindly would
also fold fullwidth CJK punctuation to ASCII and ideographic spaces to U+0020,
silently rewriting text that other languages meant exactly as written.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

# Blocks whose members are rendering variants of some other character, never
# characters an author would type. Everything outside them is left alone.
#   FB00-FB4F  Alphabetic Presentation Forms (Latin ligatures, Hebrew forms)
#   FB50-FDFF  Arabic Presentation Forms-A
#   FE70-FEFF  Arabic Presentation Forms-B
# FE00-FE6F is deliberately excluded: it holds variation selectors, combining
# half marks and CJK compatibility forms, which are not this defect.
_PRESENTATION_BLOCKS: Tuple[Tuple[int, int], ...] = (
    (0xFB00, 0xFDFF),
    (0xFE70, 0xFEFF),
)

_BFCHAR_BLOCK = re.compile(r"beginbfchar(.*?)endbfchar", re.S)
_BFRANGE_BLOCK = re.compile(r"beginbfrange(.*?)endbfrange", re.S)
_PAIR = re.compile(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>")
_RANGE_ARRAY = re.compile(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]", re.S)
_RANGE_SIMPLE = re.compile(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")
_HEX = re.compile(r"<([0-9A-Fa-f]*)>")


def is_presentation_form(codepoint: int) -> bool:
    return any(lo <= codepoint <= hi for lo, hi in _PRESENTATION_BLOCKS)


def canonical_codepoints(codepoints: List[int]) -> Tuple[List[int], bool]:
    """Replace presentation forms with the characters they are forms of.

    One form can expand to several characters - the lam-alef ligatures are a
    single glyph standing for two letters - which the CMap format handles
    natively, since a bfchar destination is a UTF-16BE string rather than one
    value.
    """
    out: List[int] = []
    changed = False
    for cp in codepoints:
        if is_presentation_form(cp):
            folded = unicodedata.normalize("NFKC", chr(cp))
            if folded and folded != chr(cp):
                out.extend(ord(ch) for ch in folded)
                changed = True
                continue
        out.append(cp)
    return out, changed


def _hex_to_codepoints(text: str) -> List[int]:
    """Decode a CMap hex string, which is UTF-16BE and may hold surrogate pairs."""
    text = text.strip()
    if len(text) % 4:
        text = text.ljust(len(text) + (4 - len(text) % 4), "0")
    units = [int(text[i:i + 4], 16) for i in range(0, len(text), 4)]
    out: List[int] = []
    index = 0
    while index < len(units):
        unit = units[index]
        if 0xD800 <= unit <= 0xDBFF and index + 1 < len(units):
            low = units[index + 1]
            if 0xDC00 <= low <= 0xDFFF:
                out.append(0x10000 + ((unit - 0xD800) << 10) + (low - 0xDC00))
                index += 2
                continue
        out.append(unit)
        index += 1
    return out


def _codepoints_to_hex(codepoints: List[int]) -> str:
    parts: List[str] = []
    for cp in codepoints:
        if cp > 0xFFFF:
            scalar = cp - 0x10000
            parts.append("%04X%04X" % (0xD800 + (scalar >> 10), 0xDC00 + (scalar & 0x3FF)))
        else:
            parts.append("%04X" % cp)
    return "".join(parts)


def parse_cmap(text: str) -> Tuple[List[Tuple[int, int, List[int]]], Dict[int, List[int]]]:
    """Read a ToUnicode CMap, keeping ranges as ranges.

    Returns (ranges, chars). A range is kept in its compressed form rather than
    expanded, because almost every range in a real CMap needs no change at all and
    re-emitting it verbatim is what keeps the rewritten CMap the same size as the
    one it replaces. Expanding everything doubled the size of a finished PDF.

    Both destination forms are handled: an explicit array, where each code in the
    range has its own value, and the common form where a single starting value is
    incremented across the range. Array ranges are read as individual characters
    since they carry no arithmetic to preserve.
    """
    ranges: List[Tuple[int, int, List[int]]] = []
    chars: Dict[int, List[int]] = {}

    for block in _BFCHAR_BLOCK.findall(text):
        for source, destination in _PAIR.findall(block):
            chars[int(source, 16)] = _hex_to_codepoints(destination)

    for block in _BFRANGE_BLOCK.findall(text):
        for low, _high, array in _RANGE_ARRAY.findall(block):
            for offset, value in enumerate(_HEX.findall(array)):
                chars[int(low, 16) + offset] = _hex_to_codepoints(value)
        # Array ranges are consumed first so the simple-range pattern cannot
        # mistake the two hex values before a `[` for a start/end/value triple.
        remainder = _RANGE_ARRAY.sub(" ", block)
        for low, high, start in _RANGE_SIMPLE.findall(remainder):
            low_i, high_i = int(low, 16), int(high, 16)
            if high_i < low_i or high_i - low_i > 0xFFFF:
                continue
            base = _hex_to_codepoints(start)
            if base:
                ranges.append((low_i, high_i, base))

    return ranges, chars


def normalize_cmap(
    ranges: List[Tuple[int, int, List[int]]], chars: Dict[int, List[int]]
) -> Tuple[List[Tuple[int, int, List[int]]], Dict[int, List[int]], int]:
    """Fold presentation forms out, expanding only the ranges that need it.

    A range whose members are all ordinary characters survives untouched. A range
    holding even one presentation form is expanded into individual entries,
    because normalization breaks the arithmetic a range depends on - one member
    can become two characters while its neighbours stay one.
    """
    kept: List[Tuple[int, int, List[int]]] = []
    out_chars = dict(chars)
    changed = 0

    for low, high, base in ranges:
        if not any(is_presentation_form(base[-1] + offset) for offset in range(high - low + 1)):
            kept.append((low, high, base))
            continue
        for offset in range(high - low + 1):
            value = list(base)
            value[-1] += offset
            folded, did = canonical_codepoints(value)
            out_chars[low + offset] = folded
            if did:
                changed += 1

    for code in list(out_chars):
        folded, did = canonical_codepoints(out_chars[code])
        if did:
            out_chars[code] = folded
            changed += 1

    return kept, out_chars, changed


def build_cmap(ranges: List[Tuple[int, int, List[int]]], chars: Dict[int, List[int]]) -> bytes:
    """Emit a ToUnicode CMap, ranges first and then individual mappings."""
    lines = [
        "/CIDInit /ProcSet findresource begin",
        "12 dict begin",
        "begincmap",
        "/CIDSystemInfo <</Registry(Adobe)/Ordering(UCS)/Supplement 0>> def",
        "/CMapName /Adobe-Identity-UCS def",
        "/CMapType 2 def",
        "1 begincodespacerange",
        "<0000> <FFFF>",
        "endcodespacerange",
    ]
    ordered_ranges = sorted(ranges)
    for start in range(0, len(ordered_ranges), 100):  # 100 per block, per the spec
        chunk = ordered_ranges[start:start + 100]
        lines.append("%d beginbfrange" % len(chunk))
        for low, high, base in chunk:
            lines.append("<%04X> <%04X> <%s>" % (low, high, _codepoints_to_hex(base)))
        lines.append("endbfrange")

    items = sorted(chars.items())
    for start in range(0, len(items), 100):
        chunk = items[start:start + 100]
        lines.append("%d beginbfchar" % len(chunk))
        for source, codepoints in chunk:
            lines.append("<%04X> <%s>" % (source, _codepoints_to_hex(codepoints)))
        lines.append("endbfchar")

    lines += [
        "endcmap",
        "CMapName currentdict /CMap defineresource pop",
        "end",
        "end",
    ]
    return "\n".join(lines).encode("latin-1", "replace")


def repair_text_layer(doc) -> int:
    """Normalize presentation forms in every ToUnicode CMap of an open document.

    Returns the number of CMaps rewritten. Best-effort by design: a document whose
    text layer could not be improved is still a correct document, so no failure
    here is allowed to stop a PDF being published.
    """
    if doc is None:
        return 0
    repaired = 0
    try:
        length = doc.xref_length()
    except Exception:
        return 0

    for xref in range(1, length):
        try:
            if not doc.xref_is_stream(xref):
                continue
            raw = doc.xref_stream(xref)
        except Exception:
            continue
        if not raw or b"begincmap" not in raw:
            continue
        try:
            text = raw.decode("latin-1", "replace")
            ranges, chars = parse_cmap(text)
            if not ranges and not chars:
                continue
            ranges, chars, changed = normalize_cmap(ranges, chars)
            if not changed:
                continue
            doc.update_stream(xref, build_cmap(ranges, chars))
            repaired += 1
        except Exception:
            continue
    return repaired


def audit_text_layer(doc) -> Dict[str, int]:
    """Count what a downstream reader would actually receive.

    Used by the tests, and worth keeping close to the repair: the only honest
    evidence that a text layer is sound is what comes back out of it.
    """
    presentation = 0
    nul = 0
    total = 0
    for page in doc:
        try:
            text = page.get_text()
        except Exception:
            continue
        total += len(text)
        nul += text.count("\x00")
        presentation += sum(1 for ch in text if is_presentation_form(ord(ch)))
    return {"characters": total, "presentation_forms": presentation, "nul": nul}
