"""What the learner actually receives, checked after it is rendered.

Every other gate in this system reads the canonical JSON. That is the right
place for almost everything, and it is not sufficient, because the renderer is
a second author: it rewrites font CMaps, folds presentation forms, localizes
labels, paginates, and composes answer keys. A page can be clean in the
database and wrong on paper.

The reported defects of that shape are all deterministic:

  * malformed Unicode in the text layer — U+FFFE and friends reached a
    published PDF while the canonical content passed `unicode_corruption`;
  * the same long line printed twice in a rendered passage;
  * the pipeline's own vocabulary appearing in learner-visible text;
  * a transcription whose aspiration is written with a plain `h` instead of the
    modifier letter, which is a different claim about the sound.

None of these needs a model to judge, and none of them is visible from the
canonical side alone. So they are checked here, on the bytes, and reported with
enough location to act on.

This module deliberately does NOT decide what happens next. It returns findings;
the caller logs them, fails a build, or refuses a publication according to its
own contract. A renderer audit that raised from inside the renderer would make
every ad-hoc export a publication gate, which is not what it is for.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Sequence

__all__ = [
    "ArtifactFinding", "audit_pdf_bytes", "audit_rendered_text",
    "summarise", "blocking",
]


class ArtifactFinding:
    __slots__ = ("code", "detail", "page", "sample")

    def __init__(self, code: str, detail: str, *, page: Any = None,
                 sample: str = ""):
        self.code = code
        self.detail = detail
        self.page = page
        self.sample = sample[:120]

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        where = f" page {self.page}" if self.page is not None else ""
        return f"<{self.code}{where}: {self.detail}>"


# ── Malformed Unicode in the text layer ──────────────────────────────────────
# U+FFFD marks a character that was already lost; U+FFFE/U+FFFF and the other
# noncharacters must never appear in text at all; surrogates and private-use
# codepoints mean the text layer is carrying glyph ids rather than characters.

_NONCHARACTERS = frozenset(
    list(range(0xFDD0, 0xFDF0))
    + [cp for plane in range(0, 17) for cp in (plane * 0x10000 + 0xFFFE,
                                               plane * 0x10000 + 0xFFFF)]
)


def _malformed_codepoints(text: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for ch in text:
        cp = ord(ch)
        label = ""
        if cp == 0:
            label = "NUL"
        elif cp == 0xFFFD:
            label = "U+FFFD replacement character"
        elif cp in _NONCHARACTERS:
            label = f"U+{cp:04X} noncharacter"
        elif unicodedata.category(ch) in ("Co", "Cs"):
            label = f"U+{cp:04X} ({unicodedata.category(ch)})"
        if label:
            counts[label] = counts.get(label, 0) + 1
    return counts


# ── The same line, printed twice ─────────────────────────────────────────────
# Mirrors `audit.repeated_sentences` but works on rendered LINES, because that
# is the unit the renderer produces and the unit a reader sees doubled. Short
# lines repeat legitimately — headings, labels, option letters — so only a
# substantial line counts, and only when it repeats within one page.

_MIN_REPEAT_WORDS = 6


def _repeated_lines(lines: Sequence[str]) -> List[str]:
    seen: Dict[str, int] = {}
    order: List[str] = []
    for raw in lines:
        line = " ".join(str(raw).split())
        if len(line.split()) < _MIN_REPEAT_WORDS:
            continue
        key = line.casefold()
        if key not in seen:
            order.append(line)
        seen[key] = seen.get(key, 0) + 1
    return [line for line in order if seen[line.casefold()] > 1]


# ── The pipeline's own vocabulary ────────────────────────────────────────────
# ONLY strings this system emits about itself. Not words that merely sound
# internal: "Fail belirteci" is the ordinary Turkish grammatical term for an
# agent marker (fâil = the doer), and `von` + Dativ marking the agent is exactly
# what a passive lesson must teach — refusing it would block passive voice in
# every Turkish-track course. The test for inclusion here is that the pipeline,
# not the language, produces the string.

_META_TOKENS = (
    "render_contract", "quality_gate", "QualityGateError", "page_is_renderable",
    "hidden_world_reason", "invented_form_taught", "duplicate_options",
    "unicode_corruption", "alien_script_token", "wrong_instructional_language",
    "publication blockers", "strategies_tried", "render_rows", "topic_id",
    "explanation_tr", "explanation_en", "rationale_specific", "checked_ids",
    "scope_checked_ids", "final_scope_safe", "counterexample_tested",
    "_review_required", "BLOCK", "blocker", "patches", "material_language",
)
_META_RE = re.compile(
    "|".join(re.escape(token) for token in _META_TOKENS)
)


# ── Transcription notation ───────────────────────────────────────────────────
# Aspiration is the modifier letter U+02B0, not a following `h`: [kʰ] is one
# aspirated stop, [kh] is a stop followed by a separate /h/. In a phonetics
# lesson that difference is the lesson. Checked only inside bracketed
# transcriptions so ordinary prose containing "kh" is untouched.

_TRANSCRIPTION = re.compile(r"\[([^\[\]\n]{1,120})\]")
_PLAIN_ASPIRATION = re.compile(r"[pbtdkgqʔ]h")


def audit_rendered_text(pages: Sequence[str]) -> List[ArtifactFinding]:
    """Every deterministic defect visible in the rendered text, page by page."""
    out: List[ArtifactFinding] = []
    for index, page_text in enumerate(pages, 1):
        text = str(page_text or "")
        if not text.strip():
            continue

        for label, count in sorted(_malformed_codepoints(text).items()):
            out.append(ArtifactFinding(
                "artifact_malformed_unicode",
                f"{label} x{count}", page=index, sample=text))

        for line in _repeated_lines(text.splitlines()):
            out.append(ArtifactFinding(
                "artifact_duplicate_line",
                "printed more than once on this page", page=index, sample=line))

        for match in _META_RE.finditer(text):
            start = max(0, match.start() - 30)
            out.append(ArtifactFinding(
                "artifact_meta_leak",
                f"pipeline vocabulary {match.group(0)!r} in learner text",
                page=index, sample=text[start:match.end() + 30]))

        for transcription in _TRANSCRIPTION.findall(text):
            hit = _PLAIN_ASPIRATION.search(transcription)
            if hit:
                out.append(ArtifactFinding(
                    "artifact_notation_defect",
                    f"aspiration written {hit.group(0)!r}; IPA uses the "
                    f"modifier letter (ʰ), a plain h is a separate segment",
                    page=index, sample=transcription))
    return out


def audit_pdf_bytes(pdf: bytes) -> List[ArtifactFinding]:
    """Audit a rendered PDF by reading its text layer back out.

    A failure to open or read the document is reported as a finding rather than
    raised: the caller decides what an unreadable artifact means, and an audit
    that crashed would be indistinguishable from one that passed.
    """
    try:
        import fitz
    except Exception as exc:  # pragma: no cover - environment without PyMuPDF
        return [ArtifactFinding("artifact_audit_unavailable",
                                f"cannot read the PDF: {exc!r}")]
    try:
        doc = fitz.open(stream=pdf, filetype="pdf")
    except Exception as exc:
        return [ArtifactFinding("artifact_unreadable",
                                f"the rendered PDF cannot be opened: {exc!r}")]
    try:
        pages = [page.get_text() for page in doc]
    finally:
        doc.close()
    return audit_rendered_text(pages)


def blocking(findings: Sequence[ArtifactFinding]) -> List[ArtifactFinding]:
    """Findings a publication must not carry. Every code here is one."""
    return [f for f in findings if f.code != "artifact_audit_unavailable"]


def summarise(findings: Sequence[ArtifactFinding], limit: int = 6) -> str:
    rows = [
        f"page {f.page}: {f.code} — {f.detail}" if f.page is not None
        else f"{f.code} — {f.detail}"
        for f in findings[:limit]
    ]
    extra = len(findings) - len(rows)
    if extra > 0:
        rows.append(f"(+{extra} more)")
    return "; ".join(rows)
