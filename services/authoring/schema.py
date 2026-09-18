"""What every field in a lesson IS — its role, its language, its repertoire.

This module exists because of one defect. A Spanish A1 lesson published the
pronunciation of *cena* as ``[ˈθενα]``: theta, then GREEK epsilon, nu and alpha
where IPA wants ``e``, ``n``, ``a``. A script-integrity guard was running over
that string and passed it, and it passed for a reason that no amount of extra
patterns would have fixed. The guard had to allow Greek inside a phonetic field,
because θ genuinely IS the IPA symbol for a voiceless dental fricative and lives
at the Greek codepoint U+03B8. Having allowed Greek, it allowed all of Greek.

The guard could not do better because it did not know what it was looking at. It
received a string. It did not know the string was a *phonetic transcription*, in
which exactly three Greek codepoints are legal and the rest are corruption; nor
that the string two fields over was *Spanish prose*, in which none are; nor that
the one after that was *Turkish instructional prose*, in which a Spanish
inverted question mark would be as wrong as the Greek.

So the first thing this rebuild establishes is a type system for content. Every
field name a lesson or an assessment item can carry is declared here exactly
once, with:

  * its **role** — what kind of thing it is (target-language material,
    instructional prose, phonetic notation, a gloss, structural metadata);
  * its **track** — which language it must be written in, where that is fixed.

Every validator and every repair in this package dispatches on the role. None of
them pattern-match a bare string, because a bare string is not enough
information to judge and never was. Adding a field to the wire format means
adding it here, and a field that is not declared here is reported rather than
silently trusted.

The wire format itself — the JSON shape the renderers and the database read —
is deliberately unchanged. It is the contract between generation and
presentation, the renderers honour it correctly, and rewriting it would have
turned a rebuild of the generation core into a rebuild of the whole product.
What changed is that the shape is now *described* somewhere, instead of being
implied by twenty places that each guessed at it.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, FrozenSet, Iterator, List, Optional, Tuple

__all__ = [
    "Role", "FieldSpec", "spec_for", "walk_fields", "declared_fields",
    "ScriptProfile", "profile_for_language", "canonical_language",
    "IPA_REPERTOIRE", "is_ipa_clean", "stray_ipa_codepoints",
    "TARGET", "INSTRUCTION", "NOTATION", "GLOSS", "META", "EVIDENCE", "NAME",
]


# ── Roles ─────────────────────────────────────────────────────────────────────
# Five kinds of content and one kind of non-content. The distinction that
# matters most is TARGET vs INSTRUCTION vs NOTATION: they are three different
# languages living in adjacent keys of the same dict, and nearly every defect
# this package catches is one of them wearing another's clothes.

TARGET = "target"           # the language being taught: a word, a sentence, an option
INSTRUCTION = "instruction"  # pedagogical prose, in the course's instructional track
NOTATION = "notation"        # phonetic transcription — IPA, and only IPA
GLOSS = "gloss"              # a translation of target material into the instructional track
EVIDENCE = "evidence"        # a citation of the source material a claim rests on
NAME = "name"                # a proper name or speaker label; may be either language
META = "meta"                # enums, ids, counters — never learner-facing prose

Role = str


class FieldSpec:
    """The declared type of one field name.

    ``track`` is 'en' or 'tr' when the field belongs to a specific instructional
    track, and None when it follows the course (TARGET fields follow the taught
    language; a role-less META field follows nothing).
    """

    __slots__ = ("role", "track", "note")

    def __init__(self, role: Role, track: Optional[str] = None, note: str = ""):
        self.role = role
        self.track = track
        self.note = note

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"FieldSpec({self.role!r}, track={self.track!r})"


# ── The field map ─────────────────────────────────────────────────────────────
# Every key the wire format uses, in one table. Sorted by the container it
# appears in, but looked up by name alone: the format never gives one name two
# meanings, and keeping it that way is a property worth protecting — `text` on a
# page is instructional prose while `text` on a dialogue turn is the utterance
# itself, which is the single exception and is handled by DIALOGUE_FIELDS below.

_FIELDS: Dict[str, FieldSpec] = {
    # Page level
    "type": FieldSpec(META),
    "title": FieldSpec(INSTRUCTION, "en"),
    "title_tr": FieldSpec(INSTRUCTION, "tr"),
    "text": FieldSpec(INSTRUCTION, "en"),
    "text_tr": FieldSpec(INSTRUCTION, "tr"),

    # Lexical items
    "term": FieldSpec(TARGET),
    "word": FieldSpec(TARGET),
    "phonetic": FieldSpec(NOTATION),
    "pronunciation": FieldSpec(NOTATION),
    "ipa": FieldSpec(NOTATION),
    "transcription": FieldSpec(NOTATION),
    "translation": FieldSpec(GLOSS, "en"),
    "translation_en": FieldSpec(GLOSS, "en"),
    "translation_tr": FieldSpec(GLOSS, "tr"),
    "meaning": FieldSpec(GLOSS, "en"),
    "example": FieldSpec(TARGET),
    "sample": FieldSpec(TARGET),
    "example_en": FieldSpec(GLOSS, "en"),
    "example_tr": FieldSpec(GLOSS, "tr"),
    "explanation": FieldSpec(INSTRUCTION, "en"),
    "explanation_en": FieldSpec(INSTRUCTION, "en"),
    "explanation_tr": FieldSpec(INSTRUCTION, "tr"),

    # Rules
    "rule": FieldSpec(INSTRUCTION, "en"),
    "rule_tr": FieldSpec(INSTRUCTION, "tr"),
    "analysis": FieldSpec(INSTRUCTION, "en"),
    "analysis_tr": FieldSpec(INSTRUCTION, "tr"),
    "scope": FieldSpec(META),
    "domain": FieldSpec(META),
    "provenance": FieldSpec(META),
    "precision": FieldSpec(META),
    "source_evidence": FieldSpec(EVIDENCE),
    "source_taught": FieldSpec(EVIDENCE),

    # Comparisons
    "target": FieldSpec(TARGET),
    "context": FieldSpec(INSTRUCTION, "en"),
    "context_tr": FieldSpec(INSTRUCTION, "tr"),
    "note": FieldSpec(INSTRUCTION, "en"),
    "note_tr": FieldSpec(INSTRUCTION, "tr"),

    # Dialogue
    "speaker": FieldSpec(NAME),
    "speaker_en": FieldSpec(NAME, "en"),
    "speaker_tr": FieldSpec(NAME, "tr"),
    "line_en": FieldSpec(GLOSS, "en"),
    "line_tr": FieldSpec(GLOSS, "tr"),

    # Assessment
    "prompt": FieldSpec(TARGET, note="the WHOLE item, asked in the taught language"),
    "question": FieldSpec(TARGET),
    "stem": FieldSpec(TARGET),
    "answer": FieldSpec(TARGET),
    "options": FieldSpec(TARGET),
    "choices": FieldSpec(TARGET),
    "distractors": FieldSpec(TARGET),
    "options_tr": FieldSpec(GLOSS, "tr"),
    "options_en": FieldSpec(GLOSS, "en"),
    "why": FieldSpec(INSTRUCTION, "en"),
    "why_tr": FieldSpec(INSTRUCTION, "tr"),
    "correct_index": FieldSpec(META),
    "stem_scope": FieldSpec(META),
    "cognitive_task": FieldSpec(META),
    "material_section": FieldSpec(META),
    "module": FieldSpec(META),
    "evidence": FieldSpec(EVIDENCE),
    "id": FieldSpec(META),
    "variety": FieldSpec(META, note="the regional standard this lesson teaches"),
}

# `text` inside a dialogue turn is the utterance, not instructional prose. It is
# the only name whose meaning depends on its container, so it is the only
# override — and naming it here beats letting a validator guess.
DIALOGUE_FIELDS: Dict[str, FieldSpec] = {"text": FieldSpec(TARGET)}

# Containers whose entries carry fields of their own.
ENTRY_CONTAINERS: Tuple[str, ...] = (
    "items", "vocabulary", "words", "examples", "rules", "comparisons",
)


def spec_for(field: str, container: str = "") -> Optional[FieldSpec]:
    """The declared type of `field`, or None if the format does not declare it."""
    if container == "dialogue" and field in DIALOGUE_FIELDS:
        return DIALOGUE_FIELDS[field]
    return _FIELDS.get(field)


def declared_fields() -> FrozenSet[str]:
    return frozenset(_FIELDS)


def walk_fields(node, container: str = "") -> Iterator[Tuple[list, str, FieldSpec, str]]:
    """Every typed string in a lesson or item tree.

    Yields ``(owner, key, spec, value)`` where `owner` is the list or dict that
    holds the value, so a caller can repair in place. A list of strings under a
    typed name (``options``, ``distractors``) yields one tuple per element with
    the list as owner and the index as key.

    Undeclared keys are skipped rather than guessed at; `undeclared_fields`
    reports them separately so a schema drift is visible instead of silent.
    """
    if isinstance(node, dict):
        for key, value in list(node.items()):
            spec = spec_for(key, container)
            if isinstance(value, str):
                if spec is not None:
                    yield node, key, spec, value
            elif isinstance(value, list):
                if spec is not None and all(isinstance(v, str) for v in value):
                    for index, item in enumerate(value):
                        yield value, index, spec, item
                else:
                    sub = key if key in ENTRY_CONTAINERS or key == "dialogue" else container
                    for found in walk_fields(value, sub):
                        yield found
            elif isinstance(value, dict):
                sub = key if key in ENTRY_CONTAINERS or key == "dialogue" else container
                for found in walk_fields(value, sub):
                    yield found
    elif isinstance(node, list):
        for value in node:
            for found in walk_fields(value, container):
                yield found


def undeclared_fields(node, container: str = "") -> List[str]:
    """Key names carrying prose that the schema does not declare."""
    found: List[str] = []

    def visit(n, cont):
        if isinstance(n, dict):
            for key, value in n.items():
                if isinstance(value, str) and value.strip():
                    if spec_for(key, cont) is None and key not in found:
                        found.append(key)
                elif isinstance(value, (dict, list)):
                    visit(value, key if key in ENTRY_CONTAINERS or key == "dialogue" else cont)
        elif isinstance(n, list):
            for value in n:
                visit(value, cont)

    visit(node, container)
    return found


# ── IPA ───────────────────────────────────────────────────────────────────────
# A phonetic field is not "text that may contain anything unusual". It is a
# transcription in one alphabet with a closed repertoire, and that closure is
# what makes `[ˈθενα]` detectable at all.
#
# The subtlety the old guard died on: the IPA borrows exactly three letters from
# Greek and encodes them at their Greek codepoints — theta U+03B8, beta U+03B2
# and chi U+03C7. Every other Greek letter has an IPA counterpart at a DIFFERENT
# codepoint (ɛ is U+025B, not ε U+03B5; ɣ is U+0263, not γ U+03B3). So "Greek is
# allowed here" is false and "Greek is forbidden here" is also false. The true
# statement is a list, and this is it.

_IPA_BORROWED_FROM_GREEK = frozenset("θβχ")

# The IPA also borrows a short, closed list from the accented Latin ranges, and
# only these. The rest of Latin-1 — á é í ó ú and the other acute-accented
# vowels — is deliberately NOT admitted: in a phonetic field those letters are
# almost always a learner respelling that has been typed into the wrong column
# ("GÁ-to"), which is a defect this check exists to find.
#
# Found by sweeping the published IPA chart against this repertoire rather than
# by waiting for a language that needs one to fail: ŋ and ħ are core consonants
# that happen to live in Latin Extended, ⱱ and ⁿ in later blocks entirely.
_IPA_BORROWED_FROM_LATIN = frozenset(
    "æçðøœ"      # U+00E6 U+00E7 U+00F0 U+00F8 U+0153
    "ħŋ"         # U+0127 pharyngeal fricative, U+014B eng
    "ǀǁǂǃ"       # U+01C0-U+01C3, the four click consonants
    "ⁿⱱ"         # U+207F nasal release, U+2C71 labiodental flap
)

# Defined by the Unicode blocks the IPA actually occupies rather than by a list
# of symbols typed out by hand. The first attempt here WAS such a list, and it
# silently omitted the alveolo-palatals ɕ and ʑ — so a correct Korean
# transcription, [t͡ɕip], was reported as corrupt. A hand-written inventory of a
# 160-symbol alphabet will always be missing something, and what it is missing
# is invisible until a language that needs it is taught.
_IPA_BLOCKS: Tuple[Tuple[int, int], ...] = (
    (0x0061, 0x007A),  # a-z, which the IPA shares with the Latin alphabet
    (0x0250, 0x02AF),  # IPA Extensions — the whole block is IPA by definition
    (0x02B0, 0x02FF),  # Spacing modifiers: ʰ ʲ ʷ ˈ ˌ ː ˑ ˞ and the tone letters
    (0x0300, 0x036F),  # Combining diacritics: nasalisation, devoicing, tie bars
    (0x1D00, 0x1DBF),  # Phonetic Extensions and their supplement
    (0x1DC0, 0x1DFF),  # Combining Diacritical Marks Supplement
    (0xA700, 0xA71F),  # Modifier Tone Letters
)

# Punctuation and delimiters a transcription legitimately contains.
_IPA_PUNCTUATION = frozenset("[]()/.|‖‿-–—  ‍͡")

IPA_REPERTOIRE: FrozenSet[str] = frozenset(
    [chr(cp) for low, high in _IPA_BLOCKS for cp in range(low, high + 1)]
) | _IPA_BORROWED_FROM_GREEK | _IPA_BORROWED_FROM_LATIN | _IPA_PUNCTUATION


def stray_ipa_codepoints(text: str) -> List[str]:
    """Characters in a phonetic field that the IPA has no business containing.

    Returns the offending characters, so a caller can say which ones rather than
    only that something was wrong. Combining marks are accepted wholesale — they
    are how the IPA writes nasalisation, devoicing and length, and enumerating
    every legal base+mark pair would be a longer list than the alphabet.
    """
    if not isinstance(text, str) or not text:
        return []
    bad: List[str] = []
    for ch in unicodedata.normalize("NFC", text):
        if ch in IPA_REPERTOIRE:
            continue
        category = unicodedata.category(ch)
        if category in ("Mn", "Zs", "Cf"):
            continue
        if ch.isdigit():
            continue
        if ch not in bad:
            bad.append(ch)
    return bad


def is_ipa_clean(text: str) -> bool:
    return not stray_ipa_codepoints(text)


# Greek letters that are NOT IPA symbols, mapped to the IPA character a writer
# reaching for that shape almost certainly meant. Used only where the mapping is
# unambiguous: α could be either `a` or `ɑ` and is therefore absent, and being
# absent is what makes it a reported defect rather than a silent guess.
GREEK_TO_IPA: Dict[str, str] = {
    "γ": "ɣ",   # U+03B3 Greek gamma -> U+0263 Latin gamma (voiced velar fricative)
    "ε": "ɛ",   # U+03B5 Greek epsilon -> U+025B open-mid front unrounded
    "ν": "n",   # U+03BD Greek nu -> the alveolar nasal is plain n
    "ο": "o",   # U+03BF Greek omicron -> o
    "ι": "i",   # U+03B9 Greek iota -> i
    "υ": "u",   # U+03C5 Greek upsilon -> u
    "ρ": "r",   # U+03C1 Greek rho -> r
    "τ": "t",
    "κ": "k",
    "μ": "m",
    "π": "p",
    "σ": "s",
    "δ": "d",
    "λ": "l",
}


# ── Scripts and orthographic convention, per taught language ─────────────────
# Fifteen languages are taught. Each has a writing system its material must use
# throughout, and most have at least one convention whose omission is a spelling
# error rather than a style choice — the kind a learner copies.

class ScriptProfile:
    """What the writing system of one taught language requires."""

    __slots__ = ("language", "scripts", "opens_questions", "opens_exclamations",
                 "question_mark", "comma", "full_stop", "notes", "variety")

    def __init__(self, language: str, scripts: Tuple[str, ...], *,
                 opens_questions: bool = False, opens_exclamations: bool = False,
                 question_mark: str = "?", comma: str = ",", full_stop: str = ".",
                 notes: str = "", variety: str = ""):
        self.language = language
        self.scripts = scripts
        self.opens_questions = opens_questions
        self.opens_exclamations = opens_exclamations
        self.question_mark = question_mark
        self.comma = comma
        self.full_stop = full_stop
        self.notes = notes
        # The regional standard the course teaches. A lesson that leaves this
        # implicit picks a different one per page: the published Spanish A1
        # material taught ⟨c⟩ before e/i as [θ] in one table and named the
        # letter C as [ˈse] in the next, which are Castilian and Latin American
        # respectively. Naming the variety once, in the cached prefix, is what
        # makes "the lesson contradicts itself" a checkable statement.
        self.variety = variety


# Unicode ranges per script name, used to decide whether a character belongs to
# a language's writing system. Latin covers the accented ranges every European
# language here needs; the rest are their own blocks.
SCRIPT_RANGES: Dict[str, Tuple[Tuple[int, int], ...]] = {
    "Latin": ((0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F), (0x1E00, 0x1EFF)),
    "Cyrillic": ((0x0400, 0x04FF), (0x0500, 0x052F)),
    "Greek": ((0x0370, 0x03FF), (0x1F00, 0x1FFF)),
    "Arabic": ((0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)),
    "Han": ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF)),
    "Kana": ((0x3040, 0x309F), (0x30A0, 0x30FF)),
    "Hangul": ((0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F)),
}

_PROFILES: Dict[str, ScriptProfile] = {
    # Spanish is the reason this table exists: ¿ and ¡ are obligatory, and a
    # course that prints "Cómo estás?" teaches the punctuation of a different
    # language while claiming to teach this one.
    "Spanish": ScriptProfile(
        "Spanish", ("Latin",), opens_questions=True, opens_exclamations=True,
        variety="European (Castilian) Spanish: distinción, so ⟨c⟩ before e/i and ⟨z⟩ are [θ]",
        notes="every question opens with ¿ and every exclamation with ¡"),
    "English": ScriptProfile(
        "English", ("Latin",), variety="British English spelling and usage"),
    "German": ScriptProfile(
        "German", ("Latin",), variety="Standard German (Bundesdeutsch)",
        notes="every noun is capitalised; ß is a letter, not a substitute for ss"),
    "French": ScriptProfile(
        "French", ("Latin",), variety="Metropolitan French",
        notes="a narrow no-break space precedes ? ! : ; and sits inside « »"),
    "Italian": ScriptProfile("Italian", ("Latin",), variety="Standard Italian"),
    "Portuguese": ScriptProfile(
        "Portuguese", ("Latin",), variety="European Portuguese",
        notes="post-1990 orthographic agreement spelling"),
    "Dutch": ScriptProfile("Dutch", ("Latin",), variety="Netherlandic Dutch",
                           notes="the digraph ij capitalises as IJ, never Ij"),
    "Swedish": ScriptProfile("Swedish", ("Latin",), variety="Rikssvenska"),
    "Turkish": ScriptProfile(
        "Turkish", ("Latin",), variety="Istanbul standard Turkish",
        notes="dotted and dotless i are different letters in both cases: i/İ and ı/I"),
    "Russian": ScriptProfile("Russian", ("Cyrillic",), variety="Standard literary Russian",
                             notes="ё is written in learner material, not replaced by е"),
    # Greek ends a question with a semicolon, not a question mark, and closes a
    # word with final sigma. Both are ordinary spelling in Greek and look like
    # typos to everyone else.
    "Greek": ScriptProfile(
        "Greek", ("Greek",), question_mark=";", variety="Standard Modern Greek (δημοτική)",
        notes="a question ends in ';' not '?'; final sigma ς closes a word, medial σ does not"),
    "Arabic": ScriptProfile(
        "Arabic", ("Arabic",), question_mark="؟", comma="،",
        variety="Modern Standard Arabic",
        notes="right-to-left; Arabic comma ، and question mark ؟; short vowels only where taught"),
    "Chinese": ScriptProfile(
        "Chinese", ("Han",), question_mark="？", comma="，", full_stop="。",
        variety="Standard Mandarin in simplified characters",
        notes="fullwidth punctuation throughout; pinyin is a separate taught object, not a gloss"),
    "Japanese": ScriptProfile(
        "Japanese", ("Han", "Kana"), question_mark="？", comma="、", full_stop="。",
        variety="Standard Japanese (標準語)",
        notes="fullwidth punctuation; kanji carry furigana only where the lesson teaches them"),
    "Korean": ScriptProfile("Korean", ("Hangul", "Han"), variety="Standard Seoul Korean",
                            notes="hangul throughout; hanja only where explicitly taught"),
}

_ALIASES: Dict[str, str] = {
    "ingilizce": "English", "inglés": "English", "ingles": "English", "en": "English",
    "türkçe": "Turkish", "turkce": "Turkish", "tr": "Turkish",
    "español": "Spanish", "espanol": "Spanish", "ispanyolca": "Spanish",
    "castellano": "Spanish", "es": "Spanish",
    "deutsch": "German", "almanca": "German", "de": "German",
    "français": "French", "francais": "French", "fransızca": "French",
    "fransizca": "French", "fr": "French",
    "italiano": "Italian", "italyanca": "Italian", "it": "Italian",
    "português": "Portuguese", "portugues": "Portuguese", "portekizce": "Portuguese",
    "pt": "Portuguese",
    "русский": "Russian", "rusça": "Russian", "rusca": "Russian", "ru": "Russian",
    "中文": "Chinese", "çince": "Chinese", "cince": "Chinese", "zh": "Chinese",
    "mandarin": "Chinese",
    "日本語": "Japanese", "japonca": "Japanese", "ja": "Japanese",
    "العربية": "Arabic", "arapça": "Arabic", "arapca": "Arabic", "ar": "Arabic",
    "nederlands": "Dutch", "felemenkçe": "Dutch", "felemenkce": "Dutch",
    "hollandaca": "Dutch", "nl": "Dutch",
    "svenska": "Swedish", "isveççe": "Swedish", "isvecce": "Swedish", "sv": "Swedish",
    "한국어": "Korean", "korece": "Korean", "ko": "Korean",
    "ελληνικά": "Greek", "yunanca": "Greek", "el": "Greek",
}


def canonical_language(value) -> Optional[str]:
    """The canonical English name of a taught language, or None if not taught."""
    name = str(value or "").strip()
    if not name:
        return None
    if name in _PROFILES:
        return name
    folded = name.casefold()
    for canon in _PROFILES:
        if canon.casefold() == folded:
            return canon
    return _ALIASES.get(folded)


def profile_for_language(value) -> Optional[ScriptProfile]:
    canon = canonical_language(value)
    return _PROFILES.get(canon) if canon else None


def script_of(ch: str) -> Optional[str]:
    cp = ord(ch)
    for name, ranges in SCRIPT_RANGES.items():
        for low, high in ranges:
            if low <= cp <= high:
                return name
    return None


_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def foreign_script_tokens(text: str, profile: ScriptProfile) -> List[str]:
    """Words mixing a script the language does not use into one that it does.

    Deliberately per-TOKEN rather than per-string. A Turkish gloss beside a
    Russian term is two languages in two fields, which is correct; a single
    token holding both Cyrillic and Latin is one word that got corrupted, which
    never is. Judging the whole string would condemn the first case, which is
    why the old guard had to be so heavily qualified that it stopped firing.
    """
    if not isinstance(text, str) or not text:
        return []
    allowed = set(profile.scripts)
    bad: List[str] = []
    for token in _WORD.findall(unicodedata.normalize("NFC", text)):
        scripts = {s for s in (script_of(c) for c in token) if s}
        if not scripts:
            continue
        # A token is corrupt when it mixes the language's own script with a
        # foreign one. A token entirely in a foreign script is a quotation or a
        # loanword and is judged elsewhere, with context this function lacks.
        if scripts & allowed and scripts - allowed and token not in bad:
            bad.append(token)
    return bad
