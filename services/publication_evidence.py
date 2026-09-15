"""Lesson-internal evidence relationships, and the contradiction risks they expose.

`publication_invariants` asks whether a *claim* is scoped honestly. This module
asks a different and complementary question:

    Does what the lesson publishes agree with the evidence the lesson itself
    already contains?

That question is what the recurring production defects actually had in common.
A table showed mixed stress while the prose beneath it claimed uniformity. One
section knew an exception; a parallel section published the rule without it. A
phrase carried the transcription of only its first word. An analysis quoted a
transcription that disagreed with the authoritative one in the vocabulary table.
None of these need target-language knowledge to *suspect* - only to resolve.

So this module is deliberately a risk detector, never an authority:

  * it works on relationships between fields (term <-> IPA, claim <-> rows,
    claim <-> claim, target <-> translation), not on linguistic truth;
  * every signal it emits is routed into the ONE bounded semantic review that
    already exists, with the specific conflicting evidence attached;
  * it adds no model call of its own and no per-row/per-page verification;
  * it never rewrites content.

Language agnosticism: nothing here encodes truth about any target language. The
signals are structural (token counts, transcription reuse, digit coverage,
polarity markers). Where surface cues are unavoidable they are limited to the
instructional languages, which are a product invariant (Turkish or English) -
never to the language being taught.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

from services.publication_invariants import (
    _claim_bearing_fields,
    _entry_prose,
    _entry_term,
    _fold_for_identity,
    _page_entries,
    _track_language,
    classify_claim_domain,
    find_absolute_claims,
    instructional_code,
)

# Risk flags. These are contracts with the bounded reviewer: each names what the
# deterministic layer observed, never what it concluded.
FLAG_PHRASE_IPA_PARTIAL = "phrase-ipa-covers-only-part-of-term"
FLAG_IPA_BORROWED = "ipa-identical-to-a-different-shorter-term"
FLAG_PROSE_IPA_CONFLICT = "prose-transcription-conflicts-with-authoritative-ipa"
FLAG_COVERAGE_GAP = "parallel-rule-states-narrower-coverage-than-a-sibling-rule"
FLAG_TRANSLATION_POLARITY = "instructional-tracks-disagree-on-polarity"
FLAG_TRANSLATION_NUMERAL = "instructional-tracks-disagree-on-a-numeral"
FLAG_RATIONALE_CLAIM = "answer-key-rationale-makes-a-publishable-claim"


# ── Shared text helpers ─────────────────────────────────────────────────────

_IPA_BRACKET = re.compile(r"[\[/]([^\[\]/]{2,80})[\]/]")
_WORD_SPLIT = re.compile(r"[\s ]+")
# Marks that decorate a transcription without being segments of their own.
_IPA_DECORATION = "ˈˌːːˑ.‿͜͡|‖()[]/"


def _strip_ipa_decoration(text: str) -> str:
    out = []
    for ch in text:
        if ch in _IPA_DECORATION:
            continue
        if unicodedata.combining(ch):
            continue
        out.append(ch)
    return "".join(out)


def _ipa_core(value: Any) -> str:
    """Comparable core of a transcription: no brackets, spacing or stress marks."""
    text = str(value or "").strip()
    match = _IPA_BRACKET.search(text)
    if match:
        text = match.group(1)
    return _strip_ipa_decoration(text).replace(" ", "").casefold()


def _token_count(value: Any) -> int:
    parts = [p for p in _WORD_SPLIT.split(str(value or "").strip()) if p]
    return len(parts)


def _ipa_token_count(value: Any) -> int:
    text = str(value or "").strip()
    match = _IPA_BRACKET.search(text)
    if match:
        text = match.group(1)
    parts = [p for p in _WORD_SPLIT.split(text.strip()) if _strip_ipa_decoration(p)]
    return len(parts)


def _is_probably_transcription(value: Any) -> bool:
    """A bracketed span that looks like IPA rather than a gloss or an aside.

    Requires at least one character that belongs to phonetic notation and no
    ASCII sentence punctuation, so '[see page 4]' and '(for example)' are not
    mistaken for transcriptions.
    """
    core = _ipa_core(value)
    if len(core) < 2:
        return False
    if any(ch in core for ch in ",;!?"):
        return False
    return any(
        ch in core
        for ch in "ɐəɛɪʊʏøœɔæɑɒʌɨɯʉɤʁʃʒʈɖɟɡŋɲʎʔʕħʂʐɕʑθðɫɾʀχβɸɣʋɹɻʈːʲʷˠˤ"
    ) or bool(re.search(r"[a-z]", core))


# ── 1. Term <-> transcription integrity ─────────────────────────────────────

def _collect_authoritative_phonetics(data: Any) -> Dict[str, Tuple[str, str]]:
    """folded term -> (original term, phonetic) for every entry that carries one."""
    out: Dict[str, Tuple[str, str]] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            term = _entry_term(node)
            phon = node.get("phonetic") or node.get("pronunciation")
            if term and isinstance(phon, str) and phon.strip():
                key = _fold_for_identity(term)
                if key and key not in out:
                    out[key] = (term, phon.strip())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data.get("pages") if isinstance(data, dict) else None)
    return out


def collect_phonetic_integrity_risks(data: Any, limit: int = 8) -> List[Dict[str, Any]]:
    """Entries whose transcription does not plausibly describe their own headword.

    Two structural signals, neither of which needs to know the target language:

      * a multi-token phrase transcribed with markedly fewer transcription tokens
        than the phrase has words - the "phrase carries only its first word's IPA"
        defect, caught by counting, not by phonology;
      * a transcription byte-identical to the transcription of a *different,
        shorter* headword elsewhere in the lesson - transcription reuse, which is
        how a phrase silently inherits a single word's IPA.

    A short function word legitimately shares a transcription with a longer form
    only by coincidence, so the second signal requires the other term to be a
    strict prefix-or-substring relationship in folded form before reporting.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return []
    authoritative = _collect_authoritative_phonetics(data)
    risks: List[Dict[str, Any]] = []
    seen_paths = set()

    for p_index, page in enumerate(data["pages"]):
        if not isinstance(page, dict):
            continue
        for container in ("items", "vocabulary", "words", "examples"):
            for e_index, entry in enumerate(page.get(container) or []):
                if not isinstance(entry, dict):
                    continue
                term = _entry_term(entry)
                phon = entry.get("phonetic") or entry.get("pronunciation")
                if not term or not isinstance(phon, str) or not phon.strip():
                    continue
                if not _is_probably_transcription(phon):
                    continue
                path = f"pages.{p_index}.{container}.{e_index}.phonetic"
                if path in seen_paths:
                    continue
                words = _token_count(term)
                ipa_tokens = _ipa_token_count(phon)
                flags: List[str] = []
                evidence: List[str] = []

                if words >= 2 and ipa_tokens < words:
                    flags.append(FLAG_PHRASE_IPA_PARTIAL)
                    evidence.append(
                        f"headword '{term}' has {words} words; transcription '{phon.strip()}' "
                        f"has {ipa_tokens} transcription token(s)"
                    )

                core = _ipa_core(phon)
                folded_term = _fold_for_identity(term)
                for other_key, (other_term, other_phon) in authoritative.items():
                    if other_key == folded_term or _ipa_core(other_phon) != core:
                        continue
                    # Only a containment relationship indicates inheritance rather
                    # than two genuinely homophonous headwords.
                    if other_key and other_key in folded_term and len(other_key) < len(folded_term):
                        flags.append(FLAG_IPA_BORROWED)
                        evidence.append(
                            f"'{term}' carries the same transcription as the shorter "
                            f"'{other_term}' ({other_phon})"
                        )
                        break

                if flags:
                    seen_paths.add(path)
                    risks.append({
                        "path": path,
                        "text": f"{term} {phon.strip()}",
                        "quantifiers": flags,
                        "examples": evidence,
                        "domain": "structural",
                    })
                    if len(risks) >= limit:
                        return risks
    return risks


def collect_prose_phonetic_conflicts(data: Any, material_language: str = "tr", limit: int = 6) -> List[Dict[str, Any]]:
    """Prose that quotes a transcription disagreeing with the authoritative one.

    When explanatory prose names a lesson term and also shows a bracketed
    transcription, that transcription must match the `phonetic` field the lesson
    publishes for that term. A mismatch is a genuine internal contradiction and
    is detectable without knowing what either transcription means.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return []
    authoritative = _collect_authoritative_phonetics(data)
    if not authoritative:
        return []
    risks: List[Dict[str, Any]] = []

    for p_index, page in enumerate(data["pages"]):
        if not isinstance(page, dict):
            continue
        containers: List[Tuple[str, int, Dict[str, Any]]] = [("page", p_index, page)]
        for container in ("rules", "comparisons", "items", "vocabulary"):
            for e_index, entry in enumerate(page.get(container) or []):
                if isinstance(entry, dict):
                    containers.append((container, e_index, entry))
        for container, index, entry in containers:
            entry_term_folded = _fold_for_identity(_entry_term(entry))
            for key in _claim_bearing_fields(entry):
                text = entry.get(key)
                if not isinstance(text, str) or not text.strip():
                    continue
                quoted = [m.group(0) for m in _IPA_BRACKET.finditer(text)]
                quoted = [q for q in quoted if _is_probably_transcription(q)]
                if not quoted:
                    continue
                folded_text = _fold_for_identity(text)
                for term_key, (term, phon) in authoritative.items():
                    if len(term_key) < 3:
                        continue
                    if term_key not in folded_text and term_key != entry_term_folded:
                        continue
                    truth = _ipa_core(phon)
                    if not truth:
                        continue
                    # Only conflict when the prose shows a transcription for this
                    # term and none of the shown transcriptions match it.
                    if any(_ipa_core(q) == truth for q in quoted):
                        continue
                    path = (
                        f"pages.{p_index}.{key}" if container == "page"
                        else f"pages.{p_index}.{container}.{index}.{key}"
                    )
                    risks.append({
                        "path": path,
                        "text": text[:600],
                        "quantifiers": [FLAG_PROSE_IPA_CONFLICT],
                        "examples": [
                            f"lesson publishes '{term}' as {phon}",
                            f"this prose shows {', '.join(quoted[:3])}",
                        ],
                        "domain": "structural",
                    })
                    break
                if len(risks) >= limit:
                    return risks
    return risks


# ── 2. Cross-section coverage gaps ──────────────────────────────────────────

# Digits and digit ranges are written the same way in every instructional
# language this product supports, which makes numeric coverage a language-neutral
# way to compare how wide two parallel rules claim to be.
_NUMERIC_TOKEN = re.compile(r"\d+\s*[-–—]\s*\d+|\d+")


def _numeric_tokens(text: str) -> set:
    out = set()
    for match in _NUMERIC_TOKEN.finditer(text or ""):
        out.add(re.sub(r"\s*[-–—]\s*", "-", match.group(0)))
    return out


def collect_coverage_gaps(data: Any, material_language: str = "tr", limit: int = 6) -> List[Dict[str, Any]]:
    """Parallel rules where one section knows a case the other silently omits.

    Two claims are treated as parallel when they share at least two numeric
    tokens - enough to indicate they partition the same space (the same endings,
    the same ranges) rather than merely both containing a digit. If one of them
    then names additional cases the other never mentions, the narrower claim is
    reported as possibly incomplete.

    This is the cross-section analogue of the same-page contradiction check, and
    it is what catches "section A gives the exception, section B publishes the
    rule without it". It asserts nothing about which claim is right.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return []
    claims: List[Dict[str, Any]] = []
    for p_index, page in enumerate(data["pages"]):
        if not isinstance(page, dict):
            continue
        for container in ("rules", "comparisons"):
            for e_index, entry in enumerate(page.get(container) or []):
                if not isinstance(entry, dict):
                    continue
                for key in _claim_bearing_fields(entry):
                    text = entry.get(key)
                    if not isinstance(text, str) or not text.strip():
                        continue
                    nums = _numeric_tokens(text)
                    if len(nums) < 2:
                        continue
                    claims.append({
                        "path": f"pages.{p_index}.{container}.{e_index}.{key}",
                        "text": text,
                        "nums": nums,
                        "code": _track_language(key, material_language),
                    })

    risks: List[Dict[str, Any]] = []
    for i, a in enumerate(claims):
        for b in claims:
            if a is b or a["code"] != b["code"]:
                continue
            shared = a["nums"] & b["nums"]
            extra = b["nums"] - a["nums"]
            # b covers everything a covers, plus cases a never mentions.
            if len(shared) >= 2 and extra and not (a["nums"] - b["nums"]):
                risks.append({
                    "path": a["path"],
                    "text": a["text"][:600],
                    "quantifiers": [FLAG_COVERAGE_GAP],
                    "examples": [
                        f"this rule covers {sorted(a['nums'])}",
                        f"a parallel rule also covers {sorted(extra)}: {b['text'][:200]}",
                    ],
                    "domain": classify_claim_domain(a["text"], a["code"]) or "structural",
                })
                break
        if len(risks) >= limit:
            break
    return risks


# ── 3. Translation correspondence ───────────────────────────────────────────
#
# Only the two instructional tracks are compared against each other. Both are
# product invariants (Turkish and English), so their polarity and numerals can be
# read directly; the target language is never parsed.

_NEGATION_CUES = {
    "en": (r"\bnot\b", r"\bno\b", r"\bnever\b", r"\bn't\b", r"\bnothing\b", r"\bnone\b",
           r"\bwithout\b", r"\bcannot\b", r"\bdoes\s+not\b", r"\bdon't\b"),
    "tr": (r"\bdeğil", r"\byok\b", r"\bhiç\b", r"\basla\b", r"\bolmaz\b", r"\bsız\b",
           r"\bhayır\b", r"\bmaz\b", r"\bmez\b"),
}


def _has_negation(text: str, code: str) -> bool:
    for pattern in _NEGATION_CUES.get(code, ()):
        if re.search(pattern, text or "", flags=re.IGNORECASE):
            return True
    return False


_TRACK_PAIRS = (
    ("example_en", "example_tr"),
    ("translation", "translation_tr"),
    ("text", "text_tr"),
    ("rule", "rule_tr"),
    ("explanation", "explanation_tr"),
    ("note", "note_tr"),
    ("line_en", "line_tr"),
)


def collect_translation_mismatches(data: Any, limit: int = 8) -> List[Dict[str, Any]]:
    """English and Turkish renderings of the same content that disagree.

    Both tracks describe one proposition. When they disagree on polarity or on a
    numeral, at least one of them misrepresents the target-language material, and
    that is visible without reading the target language at all.

    Turkish negation is suffixal, so the cue list is necessarily approximate;
    the check therefore only fires when one track is *clearly* negated and the
    other carries no negation cue at all, and it reports a risk rather than
    editing either side.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return []
    risks: List[Dict[str, Any]] = []

    def check(entry: Dict[str, Any], base_path: str) -> None:
        for en_key, tr_key in _TRACK_PAIRS:
            en = entry.get(en_key)
            tr = entry.get(tr_key)
            if not isinstance(en, str) or not isinstance(tr, str):
                continue
            if not en.strip() or not tr.strip():
                continue
            flags: List[str] = []
            evidence: List[str] = []
            en_neg, tr_neg = _has_negation(en, "en"), _has_negation(tr, "tr")
            if en_neg != tr_neg:
                flags.append(FLAG_TRANSLATION_POLARITY)
                evidence.append(
                    f"English track is {'negative' if en_neg else 'affirmative'}; "
                    f"Turkish track is {'negative' if tr_neg else 'affirmative'}"
                )
            en_nums, tr_nums = _numeric_tokens(en), _numeric_tokens(tr)
            if en_nums and tr_nums and en_nums != tr_nums:
                flags.append(FLAG_TRANSLATION_NUMERAL)
                evidence.append(f"English numerals {sorted(en_nums)} vs Turkish {sorted(tr_nums)}")
            if flags:
                risks.append({
                    "path": f"{base_path}.{tr_key}",
                    "text": tr[:600],
                    "quantifiers": flags,
                    "examples": evidence + [f"English track: {en[:200]}"],
                    "domain": "structural",
                })

    for p_index, page in enumerate(data["pages"]):
        if not isinstance(page, dict):
            continue
        check(page, f"pages.{p_index}")
        for container in ("items", "vocabulary", "words", "rules", "comparisons", "dialogue", "examples"):
            for e_index, entry in enumerate(page.get(container) or []):
                if isinstance(entry, dict):
                    check(entry, f"pages.{p_index}.{container}.{e_index}")
                    if len(risks) >= limit:
                        return risks[:limit]
    return risks[:limit]


# ── 4. Answer-key rationales as publishable claims ──────────────────────────

_RATIONALE_KEYS = ("explanation", "rationale", "why", "feedback", "answer_explanation")


def iter_rationale_fields(data: Any) -> Iterable[Tuple[str, str, str]]:
    """Yield (path, field_value, instructional_code) for every answer-key rationale.

    An MCQ explanation is instructional prose that a learner reads and believes.
    It is published material, so it belongs under the same claim discipline as
    lesson prose - which it historically escaped, because assessments never
    reached the publication boundary at all.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return
    for p_index, page in enumerate(data["pages"]):
        if not isinstance(page, dict):
            continue
        candidates: List[Tuple[str, Dict[str, Any]]] = [(f"pages.{p_index}", page)]
        for container in ("questions", "mcqs", "items", "assessment"):
            for e_index, entry in enumerate(page.get(container) or []):
                if isinstance(entry, dict):
                    candidates.append((f"pages.{p_index}.{container}.{e_index}", entry))
        for base, entry in candidates:
            for key in entry:
                stem = re.sub(r"_(en|tr)$", "", str(key).casefold())
                if stem not in _RATIONALE_KEYS:
                    continue
                value = entry.get(key)
                if isinstance(value, str) and value.strip():
                    code = "tr" if str(key).casefold().endswith("_tr") else "en"
                    yield f"{base}.{key}", value, code


def collect_rationale_claims(data: Any, material_language: str = "tr", limit: int = 8) -> List[Dict[str, Any]]:
    """Answer-key rationales that make categorical claims needing the same review.

    Selection mirrors lesson prose exactly: absolute wording plus a social or
    contextual reading. A rationale that simply states which option is correct
    carries no absolute wording and is never routed, so ordinary assessments cost
    nothing extra.
    """
    risks: List[Dict[str, Any]] = []
    for path, value, code in iter_rationale_fields(data):
        effective = code if code in ("tr", "en") else material_language
        matches = find_absolute_claims(value, effective)
        if not matches:
            continue
        domain = classify_claim_domain(value, effective)
        if domain != "social":
            # Structural rationales are usually legitimate; only route them when
            # nothing else is competing for the review budget.
            continue
        risks.append({
            "path": path,
            "text": value[:600],
            "quantifiers": sorted(set(matches)) + [FLAG_RATIONALE_CLAIM],
            "examples": [],
            "domain": "social",
        })
        if len(risks) >= limit:
            break
    return risks


# ── Aggregate ───────────────────────────────────────────────────────────────

def collect_evidence_risks(data: Any, material_language: str = "tr", limit: int = 20) -> List[Dict[str, Any]]:
    """Every evidence-relationship risk, de-duplicated by path and bounded.

    Ordered by how mechanically certain the signal is, so that when the budget is
    exhausted the strongest evidence is what reaches the reviewer.
    """
    collectors = (
        collect_phonetic_integrity_risks,
        collect_prose_phonetic_conflicts,
        collect_coverage_gaps,
        collect_translation_mismatches,
        collect_rationale_claims,
    )
    out: List[Dict[str, Any]] = []
    by_path: Dict[str, Dict[str, Any]] = {}
    for collector in collectors:
        try:
            if collector is collect_phonetic_integrity_risks or collector is collect_translation_mismatches:
                found = collector(data)
            else:
                found = collector(data, material_language=material_language)
        except Exception:
            # One detector failing must never cost the lesson its other signals.
            continue
        for risk in found:
            existing = by_path.get(risk["path"])
            if existing is None:
                out.append(risk)
                by_path[risk["path"]] = risk
                if len(out) >= limit:
                    return out
                continue
            for flag in risk.get("quantifiers") or []:
                if flag not in existing["quantifiers"]:
                    existing["quantifiers"].append(flag)
            for item in risk.get("examples") or []:
                if item not in existing["examples"]:
                    existing["examples"].append(item)
    return out
