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
    _collect_lesson_expressions,
    _entry_prose,
    _entry_term,
    _fold_for_identity,
    _has_generalization_marker,
    _named_terms_in_text,
    _page_entries,
    _track_language,
    classify_claim_domain,
    find_absolute_claims,
    declared_precision,
    instructional_code,
    iter_claim_surfaces,
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
FLAG_THIN_GENERALIZATION = "rule-generalizes-from-a-single-cited-instance"
FLAG_SCRIPT_ANOMALY = "target-language-text-contains-a-foreign-script-token"
FLAG_PARTIAL_COLUMN = "structured-field-populated-for-some-siblings-but-not-others"
FLAG_SCOPE_EXTENSION = "restatement-widens-a-rule-the-lesson-taught-narrowly"
FLAG_BOUND_DROPPED = "restatement-omits-an-exception-the-taught-rule-states"
FLAG_NOTATION_FOREIGN = "notation-field-contains-characters-outside-its-notation-system"
FLAG_ORPHAN_FRAGMENT = "explanatory-prose-ends-with-a-dangling-notation-fragment"


# A field declared to hold phonetic notation holds IPA, and IPA is a CLOSED
# repertoire: Latin-derived letters, the IPA and phonetic-extension blocks,
# spacing modifiers, combining diacritics, the Greek letters IPA borrows, and
# punctuation. It is the same repertoire whichever language is being transcribed,
# so membership can be checked without knowing the language at all.
#
# This is a different failure from the Unicode work already in place. That work
# removes codepoints no text may contain (private-use, unassigned, controls).
# These characters are perfectly valid Unicode and perfectly legitimate elsewhere
# in the same lesson - a CJK ideograph, a Cyrillic letter, an Arabic letter - and
# are simply impossible INSIDE a transcription. Only the field's declared type
# makes them detectable, which is why codepoint sanitation could never catch it.
_IPA_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x0020, 0x007E),  # ASCII: letters, brackets, dots, slashes, apostrophes
    (0x00A0, 0x024F),  # Latin-1 Supplement + Latin Extended-A/B  (æ ç ð ø ŋ …)
    (0x0250, 0x02AF),  # IPA Extensions
    (0x02B0, 0x02FF),  # Spacing Modifier Letters (ʰ ʲ ˈ ˌ ː …)
    (0x0300, 0x036F),  # Combining Diacritical Marks
    # IPA borrows exactly three letters from the Greek block, so exactly three are
    # admitted. Admitting the block they happen to live in admitted the whole Greek
    # alphabet with them, and a typed field that accepts ordinary orthography is
    # not a typed field: Greek words published as their own transcription
    # ([ˈμαθιμα] for μάθημα) passed every check, and a stray Greek letter reached an
    # Arabic transcription for the same reason. The rule this encodes is general -
    # a notation field admits the symbols the notation uses, never the script those
    # symbols were taken from.
    (0x03B2, 0x03B2),  # β  voiced bilabial fricative
    (0x03B8, 0x03B8),  # θ  voiceless dental fricative
    (0x03C7, 0x03C7),  # χ  voiceless uvular fricative
    (0x1AB0, 0x1AFF),  # Combining Diacritical Marks Extended
    (0x1E00, 0x1EFF),  # Latin Extended Additional: what NFC composes a base letter
                       # plus an IPA diacritic INTO (e + U+0303 -> ẽ). The combining
                       # form was admitted and the normalized form was not, so a
                       # nasalized vowel was legal until normalization touched it.
    (0x1D00, 0x1D7F),  # Phonetic Extensions
    (0x1DC0, 0x1DFF),  # Combining Diacritical Marks Supplement
    (0x2000, 0x206F),  # General Punctuation (‿ ‖ ′ …)
    (0xA700, 0xA71F),  # Modifier Tone Letters
)

_NOTATION_FIELDS = ("phonetic", "pronunciation", "ipa", "transcription")


# Wording that turns a listed set into an open class: "2, 3, 4 and compound
# numbers ENDING IN 2, 3, 4". The list is finite and checkable; the extension is
# neither, and it is where a correct narrow rule silently becomes a false broad
# one. Instructional-language cues only - the target language is never parsed.
_SCOPE_EXTENSION_MARKERS: Dict[str, Tuple[str, ...]] = {
    "tr": (r"\bile\s+biten", r"\bile\s+bitenler", r"\bbileşik\b", r"\bbilesik\b",
           r"\bve\s+benzerleri\b", r"\bvb\.", r"\bvesaire\b", r"\bbenzer\s+şekilde\b",
           r"\bher\s+türlü\b", r"\bgibi\s+tüm\b", r"\bbütün\s+\w+\s+için\s+de\b"),
    "en": (r"\bending\s+in\b", r"\bending\s+with\b", r"\bcompound\b", r"\band\s+so\s+on\b",
           r"\betc\.", r"\bsimilarly\b", r"\band\s+the\s+like\b", r"\bany\s+\w+\s+ending\b",
           r"\ball\s+\w+\s+that\s+end\b", r"\bthe\s+same\s+applies\s+to\b"),
    "es": (r"\bterminad\w+\s+en\b", r"\bcompuest\w+\b", r"\betc\.", r"\bde\s+igual\s+modo\b"),
    "de": (r"\bendend\w*\s+auf\b", r"\bzusammengesetzt\w*\b", r"\busw\.", r"\bebenso\b"),
    "fr": (r"\bse\s+terminant\s+par\b", r"\bcomposé\w*\b", r"\betc\.", r"\bde\s+même\b"),
    "it": (r"\bche\s+terminano\s+in\b", r"\bcompost\w+\b", r"\becc\.", r"\ballo\s+stesso\s+modo\b"),
    "pt": (r"\bterminad\w+\s+em\b", r"\bcompost\w+\b", r"\betc\.", r"\bda\s+mesma\s+forma\b"),
    "ru": (r"\bоканчивающ\w+\s+на\b", r"\bсоставн\w+\b", r"\bи\s+т\.\s*д\.", r"\bаналогично\b"),
}


# Wording that BOUNDS a rule: it says the class has members that behave
# differently. A rule may perfectly well describe an open class and still be
# exact, provided it carries its exceptions - "numbers ending in 2, 3 or 4,
# except 12, 13 and 14". Losing that clause while repeating the class is how a
# correct rule becomes a false one, so the bound has to be visible to the
# detector, not just the class.
#
# Deliberately narrow: only wording that explicitly marks an exclusion. Generic
# contrastive conjunctions ("but", "however", "ancak") are not listed, because a
# rule may use them for any contrast and treating them as bounds would both
# invent bounds that are not there and excuse restatements that state none.
_EXCEPTION_MARKERS: Dict[str, Tuple[str, ...]] = {
    "tr": (r"\bistisna", r"\bhariç", r"\bharic\b", r"\bharicinde\b", r"\bdışında\b",
           r"\bdisinda\b", r"\bdışıdır\b", r"\bdışındadır\b", r"\bdışsal\b"),
    "en": (r"\bexcept\b", r"\bexcepting\b", r"\bexception", r"\bexcluding\b",
           r"\bexcluded\b", r"\bapart\s+from\b", r"\bother\s+than\b",
           r"\bwith\s+the\s+exception\s+of\b", r"\bdoes\s+not\s+apply\s+to\b"),
    "es": (r"\bexcepto\b", r"\bexcepción", r"\bsalvo\b", r"\ba\s+excepción\s+de\b"),
    "de": (r"\bausser\b", r"\baußer\b", r"\bAusnahme", r"\bausgenommen\b"),
    "fr": (r"\bsauf\b", r"\bexception", r"\bà\s+l'exception\s+de\b", r"\bhormis\b"),
    "it": (r"\btranne\b", r"\beccezione", r"\bsalvo\b", r"\bad\s+eccezione\s+di\b"),
    "pt": (r"\bexceto\b", r"\bexceção", r"\bsalvo\b", r"\bcom\s+exceção\s+de\b"),
    "ru": (r"\bкроме\b", r"\bисключени", r"\bза\s+исключением\b"),
}


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
                        # What the reviewer must READ is the pairing (headword plus
                        # transcription); what it may WRITE is the transcription
                        # field alone. Those differ here, unlike a prose claim, so
                        # both are stated explicitly - conflating them is how a
                        # correct repair used to be measured against the wrong
                        # string and silently discarded.
                        "text": f"{term} {phon.strip()}",
                        "field_value": phon.strip(),
                        "repair": "omit_ok",
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
            # A statement the generator labelled as a deliberate simplification is
            # not contradicting the precise transcription beside it; it is teaching
            # at a coarser grain on purpose, which is legitimate scaffolding. The
            # label is advisory: absent or unrecognised, the check behaves exactly
            # as before rather than assuming intent.
            if declared_precision(entry) == "approximate":
                continue
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
    # Rules only. A rationale answers one question, so it is *expected* to cover
    # less than the rule it draws on; comparing the two would report every correct
    # answer key as an incomplete rule. The direction that matters for a
    # rationale - stating MORE than the lesson taught - is collect_scope_extensions.
    claims: List[Dict[str, Any]] = []
    for surface in iter_claim_surfaces(data, material_language=material_language):
        if surface["kind"] != "rule":
            continue
        nums = _numeric_tokens(surface["text"])
        if len(nums) < 2:
            continue
        claims.append({
            "path": surface["path"], "text": surface["text"],
            "nums": nums, "code": surface["code"], "kind": surface["kind"],
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


# ── 2b. Generalizations resting on a single instance ────────────────────────

def collect_thin_generalizations(data: Any, material_language: str = "tr", limit: int = 6) -> List[Dict[str, Any]]:
    """Rules that state a general pattern while citing exactly one example of it.

    A correct example can still produce an over-broad rule: the lesson shows one
    form, and the explanation around it is written as though the pattern were
    established. Deterministic code cannot know how far the pattern really
    extends - but it can see that the lesson generalized from a single instance
    while other forms sat untouched beside it, and that is a credible risk worth
    one slot in the review that already runs.

    Requires all of:
      * a rule or comparison (not a vocabulary note) that generalizes - absolute
        wording or a near-universal marker;
      * exactly ONE lesson expression named in the claim;
      * at least two further lesson expressions the claim never mentions, so the
        rule genuinely had more material available than it cited.

    The lone instance is supplied as the evidence, so the reviewer can decide
    whether the rule earns its scope or must be narrowed to what is shown.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return []
    expressions = _collect_lesson_expressions(data)
    if len(expressions) < 3:
        return []

    risks: List[Dict[str, Any]] = []
    for surface in iter_claim_surfaces(data, material_language=material_language):
        text, code = surface["text"], surface["code"]
        generalizes = bool(find_absolute_claims(text, code)) or _has_generalization_marker(
            text, instructional_code(code)
        )
        if not generalizes:
            continue
        named = _named_terms_in_text(text, expressions)
        if len(set(_fold_for_identity(t) for t in named)) != 1:
            continue
        unnamed = len(expressions) - 1
        if unnamed < 2:
            continue
        risks.append({
            "path": surface["path"],
            "text": text[:600],
            "quantifiers": [FLAG_THIN_GENERALIZATION],
            "examples": [
                f"the only instance this {surface['kind']} cites: {named[0]}",
                f"the lesson shows {unnamed} other expression(s) it does not mention",
            ],
            "domain": classify_claim_domain(text, code) or "unknown",
        })
        if len(risks) >= limit:
            return risks
    return risks


# Symbols that carry no meaning outside phonetic notation. The repertoire check
# below cannot separate IPA from ordinary prose on its own, because IPA is built
# from Latin letters: every character of '[sinema anlamında]' — a Turkish gloss —
# sits inside the permitted ranges.
#
# Presence of one of these settles it. ABSENCE settles nothing, and treating it
# as disqualifying was wrong: an alphabet table transcribes its vowels as [a],
# [e], [i], [o], [u], which carry no exotic symbol and are perfectly good IPA. A
# first version of this check called all five unusable and reported 130 false
# findings against 341 rows of one real course. What separates a gloss from a
# plain transcription is not the alphabet, it is proportion — a translation runs
# to a different length and word count than the headword it is standing next to.
_IPA_ONLY = set("ˈˌːˑθðʃʒŋɲʎβɣɾʁʔɛɔɪʊæøœɨʌəɑɐɜɡʧʤʝɟçɕʑɸʕħɹɻʈɖɳɭʂʐɬɮʋɥʍɚɝ")


def is_usable_transcription(value: Any, term: Any = "") -> bool:
    """True when `value` can be published as `term`'s transcription.

    Used to decide whether a repaired transcription may be written into a
    lesson. A blank pronunciation cell is a visible gap; a cell holding a
    translation, a letter name or the headword echoed back is a factual error
    the learner cannot detect, so anything that is not recognisably notation
    leaves the cell alone.
    """
    text = " ".join(str(value or "").split())
    if not text or len(text) > 120:
        return False
    # One row may legitimately carry two readings: 'x' is [ks] / [s]. Each side
    # is judged on its own; a slash is an alternation, not prose.
    if "/" in text:
        parts = [p.strip() for p in text.split("/") if p.strip()]
        if 2 <= len(parts) <= 3:
            return all(is_usable_transcription(p, term) for p in parts)
        return False
    if not (text.startswith("[") and text.endswith("]")):
        return False
    inner = text[1:-1].strip()
    if not inner:
        return False
    # A whole word echoed back is not a transcription. A single letter is a
    # different matter: an alphabet table's [a] for 'a' is both an echo and the
    # correct IPA, so the rule applies only to terms long enough to be words.
    head_raw = str(term or "").strip()
    if len(head_raw) > 2 and inner.casefold() == head_raw.casefold():
        return False
    # Sentence punctuation and capitals belong to prose, never to a transcription.
    # The full stop is NOT in that set: IPA separates syllables with it, and
    # rejecting it called [ˈo.la] and [pɾo.feˈsoɾ] unusable — 73 false findings
    # against 347 rows of one real course.
    if re.search(r"[0-9,;!?]", inner) or any(ch.isupper() for ch in inner):
        return False
    if _outside_ipa_repertoire(inner):
        return False
    if any(ch in _IPA_ONLY for ch in inner):
        return True
    # No symbol settles it, so judge by proportion to the headword. A
    # transcription tracks its term's shape; a translation does not.
    head = " ".join(str(term or "").split())
    if not head:
        return True
    if abs(len(inner.split()) - len(head.split())) > 1:
        return False
    return len(inner) <= max(3, len(head) * 2.5)


# ── 1b. Notation fields holding characters from another writing system ──────

def _outside_ipa_repertoire(text: str) -> List[str]:
    """Characters in a transcription that no phonetic notation uses."""
    out: List[str] = []
    for ch in text or "":
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in _IPA_RANGES):
            continue
        if ch in out:
            continue
        out.append(ch)
    return out


def collect_notation_violations(data: Any, limit: int = 8) -> List[Dict[str, Any]]:
    """Transcriptions containing characters from a different writing system.

    Detects semantically impossible content that is nonetheless valid Unicode, so
    no codepoint-level sanitation can see it: an ideograph, a Cyrillic letter or
    an Arabic letter sitting inside an IPA string. The judgement needed is only
    "does this character belong to this notation system", which is a closed-set
    membership test and identical for every target language.

    The repair is deliberately `omit_ok`. A corrupted transcription cannot be
    guessed back deterministically, and a transcription that is absent is honest
    while one that is wrong is a factual error the learner cannot detect.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return []
    risks: List[Dict[str, Any]] = []

    for p_index, page in enumerate(data["pages"]):
        if not isinstance(page, dict):
            continue
        for container in ("items", "vocabulary", "words", "examples"):
            for e_index, entry in enumerate(page.get(container) or []):
                if not isinstance(entry, dict):
                    continue
                for key in list(entry):
                    base = re.sub(r"_(en|tr)$", "", str(key).casefold())
                    if base not in _NOTATION_FIELDS:
                        continue
                    value = entry.get(key)
                    if not isinstance(value, str) or not value.strip():
                        continue
                    foreign = _outside_ipa_repertoire(value)
                    if not foreign:
                        continue
                    shown = ", ".join(f"{c!r} (U+{ord(c):04X})" for c in foreign[:4])
                    risks.append({
                        "path": f"pages.{p_index}.{container}.{e_index}.{key}",
                        "text": f"{_entry_term(entry)} {value}".strip(),
                        "field_value": value,
                        "repair": "omit_ok",
                        "quantifiers": [FLAG_NOTATION_FOREIGN],
                        "examples": [
                            f"this transcription contains {shown}, which belong to no "
                            f"phonetic notation system",
                            "supply the correct transcription for the whole headword, or "
                            "return an empty value rather than a guess",
                        ],
                        "domain": "structural",
                    })
                    if len(risks) >= limit:
                        return risks
    return risks


# ── 1c. Dangling notation fragments in explanatory prose ────────────────────

# A bracketed fragment after the final sentence terminator, with nothing after it.
# The inner text must not be purely numeric: a trailing "[1]" is a citation or a
# footnote marker, which is deliberate and belongs where it is.
_TRAILING_FRAGMENT = re.compile(
    r"[.!?;:。！？]\s*[\[/(]\s*(?![\d.,\s]+[\]/)])([^\[\]/()\s]{1,6})\s*[\]/)]\s*$"
)


def collect_orphan_fragments(data: Any, material_language: str = "tr", limit: int = 6) -> List[Dict[str, Any]]:
    """Explanations that end in a stray notation fragment.

    A transcription inside a sentence is normal teaching prose - "the letter is
    pronounced [a]" - and a single symbol there is legitimate, which is why the
    transcription checks ignore short fragments. A fragment sitting AFTER the
    final full stop with nothing following it is different: it is grammatically
    attached to nothing, so it is residue rather than content, whatever it says.

    Position is the whole signal, so no language is parsed and no judgement is
    made about whether the symbol is correct. The reviewer decides whether to
    integrate it into the sentence or drop it.
    """
    risks: List[Dict[str, Any]] = []
    for surface in iter_claim_surfaces(data, material_language=material_language):
        text = surface["text"].strip()
        if len(text) < 20 or not _TRAILING_FRAGMENT.search(text):
            continue
        risks.append({
            "path": surface["path"],
            "text": text[:600],
            "field_value": text[:600],
            "repair": "rescope",
            "quantifiers": [FLAG_ORPHAN_FRAGMENT],
            "examples": [
                "this explanation ends with a bracketed fragment that follows the final "
                "sentence and belongs to no clause",
                "integrate it into the sentence if it was meant to say something, "
                "otherwise remove it",
            ],
            "domain": "structural",
        })
        if len(risks) >= limit:
            break
    return risks


# ── 2b-bis. Restatements that widen a taught rule ───────────────────────────

def _uses_scope_extension(text: str, code: Any) -> List[str]:
    lang = instructional_code(code)
    out: List[str] = []
    for pattern in _SCOPE_EXTENSION_MARKERS.get(lang or "", ()):
        out.extend(m.group(0) for m in re.finditer(pattern, text or "", flags=re.IGNORECASE))
    return out


def _uses_exception(text: str, code: Any) -> List[str]:
    lang = instructional_code(code)
    out: List[str] = []
    for pattern in _EXCEPTION_MARKERS.get(lang or "", ()):
        out.extend(m.group(0) for m in re.finditer(pattern, text or "", flags=re.IGNORECASE))
    return out


def _relatedness(restatement: Dict[str, Any], rule: Dict[str, Any]) -> int:
    """How strongly a restatement and a rule describe the same territory.

    Two grounded signals: they open the class with the same wording, or they
    quantify over the same numbers. Requiring one of them keeps an exception
    stated in an unrelated part of the lesson from being treated as a bound on
    a claim that has nothing to do with it.
    """
    if restatement["code"] != rule["code"]:
        return 0
    shared_ext = set(m.casefold() for m in _uses_scope_extension(restatement["text"], restatement["code"])) & \
                 set(m.casefold() for m in _uses_scope_extension(rule["text"], rule["code"]))
    shared_nums = _numeric_tokens(restatement["text"]) & _numeric_tokens(rule["text"])
    if not shared_ext and len(shared_nums) < 2:
        return 0
    return len(shared_ext) * 2 + len(shared_nums)


def collect_scope_extensions(data: Any, material_language: str = "tr", limit: int = 6) -> List[Dict[str, Any]]:
    """Restatements that claim more than the rule they are restating.

    A rationale or a later paragraph paraphrases a rule the lesson already
    taught. Every member it names may still be correct, so nothing contradicts
    and no coverage comparison sees anything: the defect is that the restatement
    is WIDER than its source. That happens in two ways, and both are visible
    without knowing the subject matter:

      * the restatement opens a class the lesson never opened - the lesson taught
        a finite listed set, the restatement converts it into "...and any form
        ending in...";
      * the restatement repeats an open class the lesson DID teach, but drops the
        exception the taught rule carries - "numbers ending in 2, 3 or 4, except
        12, 13 and 14" comes back as "numbers ending in 2, 3 or 4".

    The second form is the one that matters most in practice, and an earlier
    version of this detector was blind to it by construction: it bailed out
    whenever any rule used extension wording, on the theory that the lesson then
    genuinely taught the wider scope. That reasoning is inverted for a rule which
    is open BUT BOUNDED. The better the lesson stated "ending in 2, 3 or 4 except
    12-14", the more certainly the detector disabled itself, and a rationale
    repeating the class without the bound escaped every check.

    False-positive discipline: a rationale is *supposed* to be shorter than the
    rule behind it. Omitting irrelevant detail is not widening. So the bound-drop
    case fires only when the restatement itself makes a CLASS-LEVEL claim - it
    uses the extension wording - and still names no exception, while a rule
    covering the same territory names one. A rationale that simply applies the
    rule to the asked instance states no class and is never touched.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return []

    surfaces = list(iter_claim_surfaces(data, material_language=material_language))
    rules = [s for s in surfaces if s["kind"] == "rule"]
    if not rules:
        return []
    opened_by_lesson = any(_uses_scope_extension(s["text"], s["code"]) for s in rules)

    risks: List[Dict[str, Any]] = []
    for surface in surfaces:
        if surface["kind"] == "rule":
            continue
        extensions = _uses_scope_extension(surface["text"], surface["code"])
        if not extensions:
            continue
        rule_shaped = bool(_numeric_tokens(surface["text"])) or _has_generalization_marker(
            surface["text"], instructional_code(surface["code"])
        )
        if not rule_shaped:
            continue

        if not opened_by_lesson:
            taught = next((s["text"] for s in rules if _numeric_tokens(s["text"])), rules[0]["text"])
            risks.append(_scope_risk(
                surface, FLAG_SCOPE_EXTENSION,
                [f"this {surface['kind']} extends the class with: {', '.join(sorted(set(extensions))[:3])}",
                 f"no rule in the lesson states that extension; the rule taught is: {taught[:220]}"],
            ))
        elif not _uses_exception(surface["text"], surface["code"]):
            # The lesson teaches the class. Did it teach it WITH a bound that this
            # restatement has dropped? Compare only against rules describing the
            # same territory, strongest match first.
            bounded = sorted(
                ((_relatedness(surface, r), r) for r in rules
                 if _relatedness(surface, r) and _uses_exception(r["text"], r["code"])),
                key=lambda pair: pair[0], reverse=True,
            )
            if not bounded:
                continue
            _score, source = bounded[0]
            stated = sorted(set(_uses_exception(source["text"], source["code"])))
            risks.append(_scope_risk(
                surface, FLAG_BOUND_DROPPED,
                [f"this {surface['kind']} states the class but names no exception",
                 f"the rule it restates bounds that class ({', '.join(stated[:3])}): {source['text'][:220]}"],
            ))
        if len(risks) >= limit:
            break
    return risks


def _scope_risk(surface: Dict[str, Any], flag: str, evidence: List[str]) -> Dict[str, Any]:
    return {
        "path": surface["path"],
        "text": surface["text"][:600],
        "field_value": surface["text"][:600],
        "repair": "rescope",
        "quantifiers": [flag],
        "examples": evidence,
        "domain": classify_claim_domain(surface["text"], surface["code"]) or "structural",
    }


# ── 2c. Whole-token script corruption ───────────────────────────────────────
#
# Existing Unicode work repairs scripts MIXED INSIDE one token ("-иte"). A
# different corruption survives that: a token that is internally consistent but
# written wholly in the wrong script for the language around it - an accidental
# transliteration, a romanized word dropped into native-script text, an encoding
# round-trip. It is invisible to intra-token harmonization because nothing about
# the token itself is malformed.
#
# This is detectable from script statistics alone. It needs no vocabulary, no
# spelling knowledge and no model: if the surrounding target-language text is
# overwhelmingly one script and a whole alphabetic word sits in another, that is
# a credible corruption, and only a reviewer can say what the word should be.

_TARGET_TEXT_KEYS = ("term", "word", "target", "example", "expression", "phrase")
_TOKEN_SPLIT = re.compile(r"[^\ẁ-ͯ]+", re.UNICODE)


def _script_of(ch: str) -> Optional[str]:
    try:
        from services.material_quality_guard import _char_script
        return _char_script(ch)
    except Exception:
        return None


def _script_profile(text: str) -> Tuple[Optional[str], Dict[str, int]]:
    """Dominant alphabetic script of a string and the per-script letter counts."""
    counts: Dict[str, int] = {}
    for ch in text:
        if not ch.isalpha():
            continue
        script = _script_of(ch)
        if script:
            counts[script] = counts.get(script, 0) + 1
    if not counts:
        return None, counts
    dominant = max(counts.items(), key=lambda kv: kv[1])[0]
    return dominant, counts


def collect_script_anomalies(data: Any, limit: int = 6) -> List[Dict[str, Any]]:
    """Target-language text containing a whole token in a foreign script.

    Deliberately conservative. A field is examined only when its own letters are
    at least 70% one script, so genuinely multiscript material is never judged
    against a majority it does not have. A token is reported only when it is
    wholly alphabetic, at least three letters long, entirely in a different
    script, and not a transcription, an acronym or a term the lesson itself
    teaches - each of which is a legitimate reason for a foreign-script word to
    appear in native-script text.

    Only target-language fields are examined. Instructional fields carry Turkish
    or English by design and would be flagged on every lesson.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return []
    known_terms = {
        _fold_for_identity(term) for term, _ in _collect_lesson_expressions(data).values()
    }
    risks: List[Dict[str, Any]] = []

    def inspect(value: Any, path: str) -> None:
        if not isinstance(value, str) or len(value.strip()) < 3:
            return
        # A transcription legitimately uses Latin/IPA letters inside any language.
        text = _IPA_BRACKET.sub(" ", value)
        dominant, counts = _script_profile(text)
        if not dominant:
            return
        total = sum(counts.values())
        if total < 6 or counts[dominant] / total < 0.7:
            return
        for token in _TOKEN_SPLIT.split(text):
            letters = [c for c in token if c.isalpha()]
            if len(letters) < 3 or not all(c.isalpha() or c.isdigit() for c in token):
                continue
            if any(c.isdigit() for c in token):
                continue
            if token.isupper():  # acronyms are not corruption
                continue
            token_script, token_counts = _script_profile(token)
            if not token_script or token_script == dominant:
                continue
            if len(token_counts) != 1:
                continue  # intra-token mixing is the Unicode layer's job
            if _fold_for_identity(token) in known_terms:
                continue  # the lesson teaches this form deliberately
            risks.append({
                "path": path,
                "text": value[:600],
                "field_value": value[:600],
                "repair": "rescope",
                "quantifiers": [FLAG_SCRIPT_ANOMALY],
                "examples": [
                    f"'{token}' is written in {token_script} while the surrounding "
                    f"text is {dominant}",
                    "if this is an accidental transliteration or encoding damage, "
                    "restore the intended target-language form",
                ],
                "domain": "structural",
            })
            return

    for p_index, page in enumerate(data["pages"]):
        if not isinstance(page, dict):
            continue
        for container in ("items", "vocabulary", "words", "examples", "dialogue", "lines"):
            for e_index, entry in enumerate(page.get(container) or []):
                if not isinstance(entry, dict):
                    continue
                for key in list(entry):
                    base = re.sub(r"_(en|tr)$", "", str(key).casefold())
                    if base in _TARGET_TEXT_KEYS and not str(key).casefold().endswith(("_en", "_tr")):
                        inspect(entry.get(key), f"pages.{p_index}.{container}.{e_index}.{key}")
                    elif str(key).casefold() == "text" and container in ("dialogue", "lines"):
                        inspect(entry.get(key), f"pages.{p_index}.{container}.{e_index}.{key}")
                if len(risks) >= limit:
                    return risks[:limit]
    return risks[:limit]


# ── 2d. Structured completeness ─────────────────────────────────────────────

def collect_partial_columns(data: Any, min_siblings: int = 4, threshold: float = 0.5) -> List[Dict[str, Any]]:
    """Fields that a structured block presents as a column but fills only partly.

    A table promises its columns. When most rows of an inventory carry a field
    and some do not, the gaps read as missing data rather than as a deliberate
    absence - an alphabet whose pronunciation column is populated for a third of
    its letters looks incomplete, not optional.

    Deterministic code must not fill the gaps: inventing the missing values is
    exactly the authoring the renderer and publication layers are forbidden to
    do. So this reports the inconsistency for review rather than repairing it,
    and reports it only when the field is clearly intended as a column - present
    on at least half the siblings, in a block of at least four.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return []
    findings: List[Dict[str, Any]] = []
    for p_index, page in enumerate(data["pages"]):
        if not isinstance(page, dict):
            continue
        for container in ("items", "vocabulary", "words"):
            entries = [e for e in (page.get(container) or []) if isinstance(e, dict)]
            if len(entries) < min_siblings:
                continue
            keys = {k for e in entries for k in e}
            for key in sorted(keys):
                if str(key).startswith("_"):
                    continue
                filled = sum(1 for e in entries
                             if isinstance(e.get(key), str) and e.get(key).strip())
                if filled == len(entries) or filled == 0:
                    continue
                ratio = filled / len(entries)
                if ratio < threshold:
                    continue
                findings.append({
                    "page": p_index,
                    "container": container,
                    "field": key,
                    "filled": filled,
                    "total": len(entries),
                })
    return findings


def mark_partial_columns(data: Any, min_siblings: int = 4, threshold: float = 0.5) -> Any:
    """Mark blocks whose implied columns have gaps, without authoring anything.

    Uses the existing ``_review_required`` convention so partial inventories are
    surfaced the same way filler pages are, rather than publishing silently as
    though complete.
    """
    findings = collect_partial_columns(data, min_siblings=min_siblings, threshold=threshold)
    if not findings:
        return data
    pages = data.get("pages")
    for finding in findings:
        page = pages[finding["page"]]
        if isinstance(page, dict):
            page["_review_required"] = True
            gaps = page.setdefault("_incomplete_fields", [])
            entry = f"{finding['container']}.{finding['field']}: {finding['filled']}/{finding['total']}"
            if entry not in gaps:
                gaps.append(entry)
    data["_review_required"] = True
    return data


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
        collect_notation_violations,
        collect_orphan_fragments,
        collect_prose_phonetic_conflicts,
        collect_coverage_gaps,
        collect_thin_generalizations,
        collect_scope_extensions,
        collect_script_anomalies,
        collect_translation_mismatches,
        collect_rationale_claims,
    )
    out: List[Dict[str, Any]] = []
    by_path: Dict[str, Dict[str, Any]] = {}
    for collector in collectors:
        try:
            if collector in (collect_phonetic_integrity_risks, collect_translation_mismatches,
                             collect_script_anomalies, collect_notation_violations):
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
