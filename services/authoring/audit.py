"""Everything that can be proved wrong about a lesson without asking a model.

The guard this replaces was ~2,600 lines in which `validate_mcq` and
`safe_unicode_normalize` were each defined three times, later definitions
wrapping earlier ones through `_v50_previous_*`, `_v58_previous_*` chains. Every
release had appended a layer rather than changing one, so the file's behaviour
was the sum of five historical opinions and no single place said what the rules
were. It still missed six defect classes in one Spanish A1 PDF.

This is the same job done once. Three properties are deliberate:

1. **Every check dispatches on the field's declared role.** A validator is never
   handed a bare string. `schema.py` says whether it is looking at target-
   language material, instructional prose, a phonetic transcription or a gloss,
   and the check that runs is the one that applies to that kind of content.
   This is what `[ˈθενα]` needed: the repertoire of a phonetic field is closed,
   and the repertoire of Spanish prose is a different closed set.

2. **Findings are data, not exceptions.** Nothing here raises, deletes or
   rewrites. It returns a list of what is wrong, with a path, a code and a
   severity. `repair.py` fixes what is mechanically fixable and the engine
   decides whether what remains is worth another generation. A guard that both
   detects and destroys can never be asked "what would you have done?", which is
   why the old one could not be tested without running the whole pipeline.

3. **A lesson is checked against itself.** The most valuable findings here are
   not pattern matches — they are internal contradictions. A lesson that
   transcribes ⟨c⟩ as [θ] on one page and names the letter [ˈse] on the next has
   told us it is wrong, in its own words, and no external knowledge of Spanish
   is required to see it. `transcription_conflicts` is that check, and it works
   the same way in all fifteen languages.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from services.authoring import schema as S

__all__ = [
    "Finding", "BLOCK", "REPAIR", "WARN",
    "audit_lesson", "audit_item", "audit_items",
    "respelling_tokens", "transcription_conflicts", "instructional_language_of",
    "hypothetical_markers", "unicode_defects",
]


BLOCK = "block"    # must not reach a learner
REPAIR = "repair"  # deterministically fixable; repair.py owns it
WARN = "warn"      # worth reporting, not worth failing a build over


class Finding:
    """One provable defect, with enough context to fix or to explain it."""

    __slots__ = ("code", "severity", "path", "field", "role", "detail", "value")

    def __init__(self, code: str, severity: str, *, path: str = "", field: str = "",
                 role: str = "", detail: str = "", value: str = ""):
        self.code = code
        self.severity = severity
        self.path = path
        self.field = field
        self.role = role
        self.detail = detail
        self.value = value

    def __repr__(self) -> str:
        where = f"{self.path}.{self.field}" if self.path else self.field
        return f"<{self.severity}:{self.code} at {where} {self.detail}>"

    def as_dict(self) -> Dict[str, str]:
        return {"code": self.code, "severity": self.severity, "path": self.path,
                "field": self.field, "role": self.role, "detail": self.detail,
                "value": self.value[:120]}


# ── Instructional-language identification ────────────────────────────────────
# The instructional track is only ever English or Turkish — that is the whole
# set, by product design — so telling them apart is a closed problem and a
# function-word list is a legitimate solution rather than a heuristic pile.
# Function words, never content words: they carry almost no risk of colliding
# with a taught language's vocabulary, and they are what prose is built from.

_EN_FUNCTION = frozenset("""
the a an and or but if then than that this these those with without from for to
of in on at by as is are was were be been being do does did have has had will
would can could should may might must not no yes you your they their it its we
our he she his her which what when where who whom how why because so such each
every both all some any more most other another same very just only also there
here about into over under between during before after while until
""".split())

_TR_FUNCTION = frozenset("""
ve veya ama fakat ancak çünkü eğer ise ile için gibi kadar sonra önce daha çok
az en bir bu şu o bunlar şunlar onlar ben sen biz siz onun benim senin bizim
sizin onların var yok değil mi mı mu mü ki de da ta te ya ise ne nasıl neden
niçin hangi kim kimin nerede nereye nereden zaman şey her hep bazı tüm bütün
olarak üzere göre doğru yanlış evet hayır
""".split())

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _tokens(text: str) -> List[str]:
    folded = unicodedata.normalize("NFC", str(text or "")).casefold()
    # Turkish dotted/dotless i survives casefold differently per locale; fold
    # both to a common form for matching only, never for output.
    folded = folded.replace("ı", "i").replace("İ".casefold(), "i")
    return _WORD_RE.findall(folded)


def instructional_language_of(text: str) -> Optional[str]:
    """'en', 'tr', or None when the prose is neither or too short to tell.

    Scored by share of function words rather than by any single marker, so a
    Turkish sentence quoting an English term is still Turkish and an English
    sentence quoting a Turkish one is still English.
    """
    tokens = _tokens(text)
    if len(tokens) < 4:
        return None
    en = sum(1 for t in tokens if t in _EN_FUNCTION)
    tr = sum(1 for t in tokens if t in _TR_FUNCTION)
    if en == tr:
        return None
    lead, hits = ("en", en) if en > tr else ("tr", tr)

    # Two thresholds, and both are needed. Short function words are exactly
    # where European languages collide: Spanish *en*, *el*, *a*, *no*, German
    # *was*, *in*, Dutch *is*, *in* are all English function words too. A
    # five-word Spanish stem containing one of them would score 20% and be
    # condemned as English on the strength of a single coincidence.
    #
    # Requiring THREE separate hits as well as a third of the sentence makes a
    # collision have to happen three times over, which prose in another language
    # does not do. The cost is that a short sentence in the wrong language goes
    # undetected — a false negative, which another check may still catch, and
    # which is the right way round: blocking correct Spanish is a defect the
    # learner sees, missing one bad sentence is a defect a reviewer sees.
    if hits < 3:
        return None
    return lead if hits / len(tokens) >= 0.30 else None


# ── A second pronunciation system ────────────────────────────────────────────
# A document may teach pronunciation with IPA or with learner respelling. It may
# not do both: the learner cannot know that [ˈmesa] and 'meh-sah' are the same
# claim, and having seen two systems will trust neither. The published Spanish
# lesson carried `[ˈkasa]` and `'gah-toh'` and `GÁ-to` on adjacent pages.
#
# Detected by shape, in two forms that are each unambiguous:
#   * a hyphenated token with a run of capitals — GÁ-to, te-LÉ-fo-no — which is
#     how respelling marks stress and which no orthography writes;
#   * a quoted hyphenated syllable string — 'meh-sah', 'ge-a-te-o' — where the
#     quotation is what separates it from an ordinary hyphenated compound.

_CAPS_RESPELL = re.compile(r"\b[^\W\d_]*[A-ZÀ-ÞĞİŞÇÖÜ]{2,}[^\W\d_]*(?:-[^\W\d_]+)+\b", re.UNICODE)
_QUOTED_RESPELL = re.compile(
    r"['\"‘’“”«»]\s*([^\W\d_]{1,5}(?:-[^\W\d_]{1,5}){1,})\s*['\"‘’“”«»]", re.UNICODE)


def respelling_tokens(text: str) -> List[str]:
    """Ad-hoc pronunciation respellings found in `text`."""
    if not isinstance(text, str) or not text:
        return []
    found: List[str] = []
    for match in _CAPS_RESPELL.finditer(text):
        token = match.group(0)
        if token not in found:
            found.append(token)
    for match in _QUOTED_RESPELL.finditer(text):
        token = match.group(1)
        if token not in found and any(ch.isalpha() for ch in token):
            found.append(token)
    return found


# ── Self-contradiction: the same grapheme, two transcriptions ────────────────

_BRACKETED = re.compile(r"\[([^\]\n]{1,40})\]")


def _strip_stress(ipa: str) -> str:
    return re.sub(r"[ˈˌ.\s]", "", str(ipa or ""))


def transcription_conflicts(lesson: Any) -> List[Tuple[str, List[str]]]:
    """Orthographic forms this lesson transcribes two incompatible ways.

    The strongest kind of finding available without knowing the language: the
    material contradicts itself, so it is wrong whatever the truth is, and
    saying so needs no opinion about Spanish, Greek or Korean.

    The published Spanish lesson taught ⟨c⟩ before e/i as [θ] in a consonant
    table and then named the letter C as [ˈse] in an alphabet table, and taught
    ⟨g⟩ before e/i as [x] while naming G as [ˈhe]. Both are visible here as one
    term carrying two transcriptions that are not the same string.

    Compared with stress marks and syllable dots removed, because [ˈkasa] and
    [kasa] are the same claim about sounds, and a lesson is allowed to mark
    stress in one place and not another.
    """
    # A transcription belongs to the orthographic form beside it, so this walks
    # the containers rather than `walk_fields`' flattened stream, which has by
    # design forgotten which term each string sat next to.
    index: Dict[str, List[str]] = {}
    for _entry, term, ipa in _notation_pairs(lesson):
        key = term.casefold().strip()
        if not key or not ipa.strip():
            continue
        bucket = index.setdefault(key, [])
        if _strip_stress(ipa) not in [_strip_stress(x) for x in bucket]:
            bucket.append(ipa)
    return [(term, forms) for term, forms in index.items() if len(forms) > 1]


def _notation_pairs(lesson: Any) -> Iterable[Tuple[dict, str, str]]:
    """(entry, orthographic form, transcription) for every transcribed item."""
    def visit(node):
        if isinstance(node, dict):
            term = ""
            for name in ("term", "word", "target"):
                if isinstance(node.get(name), str) and node[name].strip():
                    term = node[name].strip()
                    break
            if term:
                for name in ("phonetic", "pronunciation", "ipa", "transcription"):
                    value = node.get(name)
                    if isinstance(value, str) and value.strip():
                        yield node, term, value.strip()
                        break
            for value in node.values():
                if isinstance(value, (dict, list)):
                    for found in visit(value):
                        yield found
        elif isinstance(node, list):
            for value in node:
                for found in visit(value):
                    yield found

    return visit(lesson)


# ── Forms the material itself flags as not real ──────────────────────────────
# The published lesson printed `gueso` in a table of Spanish words and labelled
# it "(varsayımsal: sert-g peynir)" — hypothetical. An A1 learner has no way to
# know which rows of a table are real words. A lesson that has to invent a form
# to demonstrate a rule has chosen the wrong rule or the wrong example.

_HYPOTHETICAL = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"\bvarsay[ıi]msal\b", r"\bhipotetik\b", r"\buydurma\b", r"\bger[çc]ek\s+bir\s+kelime\s+de[ğg]il",
    r"\bhypothetical\b", r"\bnot\s+a\s+real\s+word\b", r"\binvented\b", r"\bmade[- ]up\b",
    r"\bdoes\s+not\s+exist\b", r"\bnon-?word\b", r"\bfictitious\b",
    r"\bhipot[ée]tico\b", r"\bno\s+es\s+una\s+palabra\s+real\b",
))


def hypothetical_markers(text: str) -> List[str]:
    if not isinstance(text, str) or not text:
        return []
    return [m.pattern for m in _HYPOTHETICAL if m.search(text)]


# ── Unicode integrity ────────────────────────────────────────────────────────

_UNPUBLISHABLE = frozenset({"Co", "Cn", "Cs"})
_FORMAT_KEEP = frozenset({"‌", "‍", "‎", "‏", "⁠", "\n", "\t"})


def unicode_defects(text: str) -> List[str]:
    """Characters that must never reach a published text layer."""
    if not isinstance(text, str) or not text:
        return []
    bad: List[str] = []
    for ch in text:
        if ch in _FORMAT_KEEP:
            continue
        if ch == "�":
            name = "U+FFFD replacement character"
        else:
            category = unicodedata.category(ch)
            if category in _UNPUBLISHABLE or category == "Cc":
                name = f"U+{ord(ch):04X} ({category})"
            elif (ord(ch) & 0xFFFE) == 0xFFFE or 0xFDD0 <= ord(ch) <= 0xFDEF:
                name = f"U+{ord(ch):04X} noncharacter"
            else:
                continue
        if name not in bad:
            bad.append(name)
    return bad


# ── Assessment items ─────────────────────────────────────────────────────────

def _normalise_option(text: Any) -> str:
    """Identity of an option as a learner reads it — diacritics KEPT.

    Stripping them would collapse `café`/`cafe` and `él`/`el` into one key, and
    those contrasts are the entire content of an accent item.
    """
    if not text:
        return ""
    folded = unicodedata.normalize("NFC", str(text).strip().casefold())
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", folded, flags=re.UNICODE)).strip()


def _fold_diacritics(text: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text or "").casefold().strip())
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w\s]", "", stripped).strip()


# The keys an item's question may live under. `prompt` is what this package
# emits; the rest are shapes stored by earlier generations of the product, and
# the renderer already reads all of them — so the auditor must too, or it
# condemns for "missing_stem" an item the page will happily print.
_STEM_KEYS = ("prompt", "prompt_tr", "prompt_en", "question", "question_tr", "question_en",
              "stem", "stem_tr", "stem_en")


def _resolve_stem(item: Dict[str, Any]) -> str:
    for key in _STEM_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def audit_item(item: Dict[str, Any], *, language: str = "", track: str = "tr",
               path: str = "") -> List[Finding]:
    """Everything provably wrong with one multiple-choice item."""
    out: List[Finding] = []

    def add(code, severity, **kw):
        out.append(Finding(code, severity, path=path, **kw))

    if not isinstance(item, dict):
        return [Finding("not_an_object", BLOCK, path=path)]

    stem = _resolve_stem(item)
    answer = str(item.get("answer") or "").strip()

    options = item.get("options")
    if not isinstance(options, list) or not options:
        options = item.get("choices") if isinstance(item.get("choices"), list) else None

    # `distractors` is what a generator emits; `options` is what a learner reads,
    # and material written before this rebuild carries only the second. An item
    # with four options and a valid key is answerable whether or not anything
    # ever split them apart, so the distractors are derived when absent rather
    # than being demanded — requiring the field dropped whole pages of stored
    # lessons that were perfectly fine.
    raw_d = item.get("distractors")
    if isinstance(raw_d, list):
        distractors = [str(d).strip() for d in raw_d if str(d).strip()]
    elif options:
        distractors = [str(o).strip() for o in options
                       if str(o).strip() and _normalise_option(o) != _normalise_option(answer)]
    else:
        distractors = []

    if not stem:
        add("missing_stem", BLOCK, field="prompt")
    if not answer:
        add("missing_answer", BLOCK, field="answer")
    if len(distractors) != 3:
        add("distractor_count", BLOCK, field="distractors", detail=f"{len(distractors)} of 3")

    option_list = options if options else ([answer] + distractors)
    keys = [_normalise_option(o) for o in option_list]
    present = [k for k in keys if k]
    if len(present) != len(option_list):
        add("empty_option", BLOCK, field="options")
    if len(set(present)) != len(present):
        add("duplicate_options", BLOCK, field="options",
            detail="two options read identically to a learner")
    if isinstance(options, list) and options and _normalise_option(answer) not in set(keys):
        add("answer_not_in_options", BLOCK, field="answer")

    # When both wire representations exist they must describe the same three
    # wrong choices. A semantic reviewer that changes options but forgets the
    # stored distractors otherwise creates a page whose renderer and auditor can
    # disagree about what the learner is answering.
    if isinstance(options, list) and isinstance(raw_d, list) and answer:
        option_wrong = sorted(
            _normalise_option(o) for o in options
            if str(o).strip() and _normalise_option(o) != _normalise_option(answer)
        )
        stored_wrong = sorted(_normalise_option(d) for d in distractors)
        if option_wrong != stored_wrong:
            add("option_distractor_mismatch", BLOCK, field="distractors",
                detail="options minus the key do not equal stored distractors")

    # One option is another one misspelt, among otherwise distinct forms. A
    # healthy set is either ONE word in competing spellings (a spelling item) or
    # four genuinely different forms; anything between the two is a typo
    # standing in for a distractor.
    words = [str(o).strip() for o in option_list if str(o).strip()]
    if len(words) == 4 and all(len(_normalise_option(w)) >= 3 for w in words):
        groups = {_fold_diacritics(w) for w in words}
        if 1 < len(groups) < len(words):
            add("mixed_spelling_variants", BLOCK, field="options",
                detail="one option is another one with a diacritic changed")

    # The key chosen by its shape rather than its meaning.
    if answer and len(words) >= 3:
        others = [w for w in words if _normalise_option(w) != _normalise_option(answer)]
        if others:
            longest, shortest = max(map(len, others)), min(map(len, others))
            if len(answer) >= 2 * longest and len(answer) - longest >= 12:
                add("key_length_outlier", BLOCK, field="answer", detail="key is twice the longest option")
            elif shortest >= 2 * len(answer) and shortest - len(answer) >= 12:
                add("key_length_outlier", BLOCK, field="answer", detail="key is half the shortest option")

    # A feature the stem names that only the key exhibits: the learner answers
    # by scanning for a letter and never consults the rule.
    for feature in _giveaway_features(stem, answer, words):
        add("feature_only_in_key", BLOCK, field="prompt", detail=f"only the key contains {feature!r}")

    # Track discipline: the rationale must speak the published instructional
    # language, and the stem must be in the taught language, not in the
    # instructional one.
    wanted = "why_tr" if str(track).casefold() == "tr" else "why"
    if not str(item.get(wanted) or "").strip():
        add("missing_rationale", WARN, field=wanted)

    taught = S.canonical_language(language)
    if stem and taught not in ("English", "Turkish"):
        detected = instructional_language_of(stem)
        if detected in ("en", "tr"):
            add("stem_in_instructional_language", BLOCK, field="prompt",
                detail=f"stem reads as {detected}", value=stem)

    # A gap the gloss fills in for the learner.
    if re.search(r"[_＿﹍﹏‗]{2,}", stem):
        for gloss_key in ("translation_en", "translation_tr"):
            gloss = str(item.get(gloss_key) or "")
            if not gloss:
                continue
            if not re.search(r"[_＿﹍﹏‗]{2,}", gloss):
                add("gap_lost_in_gloss", REPAIR, field=gloss_key)
            elif len(_fold_diacritics(answer)) >= 3 and \
                    f" {_fold_diacritics(answer)} " in f" {_fold_diacritics(gloss)} ":
                add("answer_revealed_in_gloss", BLOCK, field=gloss_key)

    out.extend(_audit_typed_strings(item, language=language, track=track, path=path))
    return out


_QUOTE_MARKS = "'\"‘’“”„‚«»‹›「」『』｢｣〈〉"
_QUOTED_FEATURE = re.compile(
    r"[{q}]\s*([^\s{q}]{{1,3}})\s*[{q}]".format(q=re.escape(_QUOTE_MARKS)))
_NAMED_LETTER = re.compile(r"(?<![^\W\d_])([^\W\d_]{1,3})(?![^\W\d_])")


def _giveaway_features(stem: str, answer: str, options: Sequence[str]) -> List[str]:
    if not stem or not answer or len(options) < 3:
        return []
    pool = [str(o).casefold() for o in options if str(o).strip()]
    key = answer.casefold()
    candidates = list(_QUOTED_FEATURE.findall(stem))
    if any(ch.islower() for ch in stem):
        candidates += [t for t in _NAMED_LETTER.findall(stem) if t.isupper()]
    found: List[str] = []
    for raw in candidates:
        feature = raw.casefold()
        if not feature or not all(ch.isalpha() for ch in feature):
            continue
        if feature not in key:
            continue
        if sum(1 for o in pool if feature in o) == 1 and feature not in found:
            found.append(feature)
    return found


# ── The typed sweep ──────────────────────────────────────────────────────────

def _audit_typed_strings(node: Any, *, language: str, track: str,
                         path: str = "") -> List[Finding]:
    """Run each role's own rules over every typed string in `node`."""
    out: List[Finding] = []
    profile = S.profile_for_language(language)
    taught = S.canonical_language(language)
    track = str(track or "tr").casefold()

    for _owner, key, spec, value in S.walk_fields(node):
        field = str(key)
        text = str(value)
        if not text.strip():
            continue

        for defect in unicode_defects(text):
            out.append(Finding("unicode_corruption", BLOCK, path=path, field=field,
                               role=spec.role, detail=defect, value=text))

        if spec.role == S.NOTATION:
            stray = S.stray_ipa_codepoints(text)
            if stray:
                # A look-alike Unicode character is not safely repairable from
                # shape alone. Greek epsilon might have been intended as [e] or
                # [ɛ], for example; silently choosing one can create a valid-IPA
                # string that is linguistically false. Block it and let the
                # semantic reviewer correct the transcription from the word.
                out.append(Finding(
                    "non_ipa_in_transcription", BLOCK,
                    path=path, field=field, role=spec.role,
                    detail="not IPA: " + " ".join(f"U+{ord(c):04X} {c!r}" for c in stray),
                    value=text))
            if respelling_tokens(text):
                out.append(Finding("respelling_in_notation", BLOCK, path=path, field=field,
                                   role=spec.role, detail="a transcription field must be IPA",
                                   value=text))

        elif spec.role == S.TARGET:
            if profile is not None:
                foreign = S.foreign_script_tokens(text, profile)
                if foreign:
                    out.append(Finding("mixed_script_token", BLOCK, path=path, field=field,
                                       role=spec.role, detail=", ".join(foreign[:3]), value=text))
                alien = S.alien_script_tokens(text, profile)
                if alien:
                    out.append(Finding("alien_script_token", BLOCK, path=path, field=field,
                                       role=spec.role, detail=", ".join(alien[:3]), value=text))
                if profile.opens_questions and _unopened(text, "?", "¿"):
                    out.append(Finding("missing_opening_question_mark", REPAIR, path=path,
                                       field=field, role=spec.role, value=text))
                if profile.opens_exclamations and _unopened(text, "!", "¡"):
                    out.append(Finding("missing_opening_exclamation_mark", REPAIR, path=path,
                                       field=field, role=spec.role, value=text))
            # Instructional prose wearing a target field: "r (at the start of a
            # word)" published as a Spanish vocabulary term.
            if taught not in ("English", "Turkish"):
                detected = instructional_language_of(text)
                if detected in ("en", "tr"):
                    out.append(Finding("instructional_prose_in_target_field", BLOCK, path=path,
                                       field=field, role=spec.role,
                                       detail=f"reads as {detected}", value=text))

        elif spec.role in (S.INSTRUCTION, S.GLOSS):
            expected = spec.track or track
            detected = instructional_language_of(text)
            if detected and expected in ("en", "tr") and detected != expected:
                out.append(Finding("wrong_instructional_language", BLOCK, path=path, field=field,
                                   role=spec.role,
                                   detail=f"declared {expected}, reads as {detected}", value=text))
            # Learner-facing prose had NO script check at all, so a Greek
            # look-alike inside a gloss or an explanation passed everything —
            # which is how `once [ˈονθε]` and `zumo [el ˈθυμο]` reached a
            # published Spanish PDF.
            if profile is not None:
                alien = S.alien_script_tokens(text, profile)
                if alien:
                    out.append(Finding("alien_script_token", BLOCK, path=path, field=field,
                                       role=spec.role, detail=", ".join(alien[:3]), value=text))
            if spec.role == S.GLOSS and (spec.track or track) == "tr" \
                    and english_number_gloss(text):
                out.append(Finding("locale_leak_in_gloss", BLOCK, path=path, field=field,
                                   role=spec.role,
                                   detail="a Turkish gloss written in English number words",
                                   value=text))
            for token in respelling_tokens(text):
                out.append(Finding("second_pronunciation_system", BLOCK, path=path, field=field,
                                   role=spec.role,
                                   detail=f"ad-hoc respelling {token!r} beside IPA", value=text))
            for _marker in hypothetical_markers(text):
                out.append(Finding("invented_form_taught", BLOCK, path=path, field=field,
                                   role=spec.role,
                                   detail="the lesson marks its own example as not a real word",
                                   value=text))
    return out


# ── Locale leakage that is too short to identify by function words ───────────
# A published Turkish Spanish-course vocabulary table glossed `veintinueve` as
# "twenty-nine". `instructional_language_of` abstains there and should: two
# tokens, neither a function word, is not enough evidence to call a language.
# Two narrower checks catch it without guessing.

# Every English number word. Numbers are a closed set, they are exactly where
# this leak appears, and no Turkish gloss is ever spelled "twenty" — so this
# costs nothing in false positives and catches the whole vocabulary class.
_EN_NUMBER_WORDS = frozenset("""
zero one two three four five six seven eight nine ten eleven twelve thirteen
fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty
sixty seventy eighty ninety hundred thousand million
first second third fourth fifth sixth seventh eighth ninth tenth
""".split())


def english_number_gloss(text: str) -> bool:
    """True when a gloss is written entirely as English number words."""
    tokens = [t for t in _WORD_RE.findall(str(text or "").casefold()) if t]
    if not tokens or len(tokens) > 4:
        return False
    return all(t in _EN_NUMBER_WORDS for t in tokens)


# Pairs of fields that are the same content in the two instructional languages.
_BILINGUAL_PAIRS = (
    ("title", "title_tr"), ("text", "text_tr"), ("translation", "translation_tr"),
    ("translation_en", "translation_tr"), ("example_en", "example_tr"),
    ("explanation", "explanation_tr"), ("explanation_en", "explanation_tr"),
    ("rule", "rule_tr"), ("analysis", "analysis_tr"), ("context", "context_tr"),
    ("note", "note_tr"), ("line_en", "line_tr"), ("why", "why_tr"),
)


def identical_bilingual_glosses(node: Any) -> List[Tuple[str, str]]:
    """English and Turkish fields holding the identical multi-word string.

    One language copied into the other's slot. Restricted to values of two or
    more words (or a hyphenated compound, which is how "twenty-nine" appears),
    because a single token really can be the same in both — "pizza", "taksi" —
    and flagging those would fire on every correct loanword in the product.
    """
    found: List[Tuple[str, str]] = []

    def visit(entry: Any) -> None:
        if isinstance(entry, dict):
            for en_key, tr_key in _BILINGUAL_PAIRS:
                en_value = str(entry.get(en_key) or "").strip()
                tr_value = str(entry.get(tr_key) or "").strip()
                if not en_value or en_value.casefold() != tr_value.casefold():
                    continue
                if not any(ch.islower() for ch in en_value):
                    continue          # an acronym or a proper noun
                words = _WORD_RE.findall(en_value)
                if len(words) < 2 and "-" not in en_value:
                    continue          # a plausible shared loanword
                pair = (f"{en_key}/{tr_key}", en_value[:60])
                if pair not in found:
                    found.append(pair)
            for value in entry.values():
                if isinstance(value, (dict, list)):
                    visit(value)
        elif isinstance(entry, list):
            for value in entry:
                visit(value)

    visit(node)
    return found


def _unopened(text: str, closer: str, opener: str) -> bool:
    """True when `text` closes a question/exclamation it never opened."""
    if closer not in text:
        return False
    depth = 0
    for ch in text:
        if ch == opener:
            depth += 1
        elif ch == closer:
            if depth == 0:
                return True
            depth -= 1
    return False


# ── The lesson ───────────────────────────────────────────────────────────────

def audit_lesson(lesson: Any, *, language: str = "", track: str = "tr") -> List[Finding]:
    """Every provable defect in a complete lesson."""
    if not isinstance(lesson, dict):
        return [Finding("not_a_lesson", BLOCK)]

    out: List[Finding] = _audit_typed_strings(lesson, language=language, track=track)

    for term, forms in transcription_conflicts(lesson):
        out.append(Finding("self_contradicting_transcription", BLOCK, field="phonetic",
                           role=S.NOTATION, detail=f"{term!r} transcribed as " +
                           " and ".join(repr(f) for f in forms[:3])))

    for fields, value in identical_bilingual_glosses(lesson):
        out.append(Finding("locale_leak_in_gloss", BLOCK, field=fields, role=S.GLOSS,
                           detail="one language copied into the other's field", value=value))

    pages = lesson.get("pages")
    if isinstance(pages, list):
        for index, page in enumerate(pages):
            if not isinstance(page, dict):
                continue
            where = f"pages[{index}]"
            if str(page.get("type") or "").strip().casefold() == "mcq":
                for finding in audit_item(page, language=language, track=track, path=where):
                    out.append(finding)
            out.extend(_audit_transcription_coverage(page, where))

    for name in S.undeclared_fields(lesson):
        out.append(Finding("undeclared_field", WARN, field=name,
                           detail="carries prose but the schema does not type it"))

    out.extend(_audit_every_string(lesson, language=language))

    # The universal pass deliberately overlaps the typed ones, so the same
    # defect can be reported twice for one string. Report it once.
    seen = set()
    unique: List[Finding] = []
    for finding in out:
        key = (finding.code, finding.path, str(finding.field), finding.detail,
               finding.value)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


# Keys that are identifiers and routing metadata rather than anything a learner
# reads. Everything else in the tree is treated as prose that could reach a page.
_NON_PROSE_KEYS = frozenset({
    "id", "topic_id", "type", "stem_scope", "assessment_scope", "correct_index",
    "module", "material_section", "scope", "domain", "provenance", "precision",
    "variety", "cognitive_task",
})


def _explicable_as_ipa(token: str) -> bool:
    """True when every foreign character in a token is a legitimate IPA symbol.

    The IPA borrows θ, β, χ and ɣ at their Greek codepoints, and a transcription
    is often written without brackets — `ˈonθe` is correct Castilian. The
    universal pass must not condemn those, and it must still catch `ˈονθε`,
    where ο, ν and ε are Greek look-alikes that the IPA does not contain. Asking
    the repertoire rather than the script settles both cases with one rule.
    """
    return all(ch in S.IPA_REPERTOIRE or ch.isascii() for ch in token)


def _audit_every_string(lesson: Any, *, language: str = "") -> List[Finding]:
    """Writing-system integrity for EVERY string in the tree, typed or not.

    Script integrity is a property of a string that reaches a page, not of the
    role the schema happens to give its key. The role-based checks only ever saw
    declared fields, so `prompt_tr`, `question_tr`, `stem_tr`, `text_en`,
    `phrase`, `sentence`, `meaning_tr` and the dialogue fields — all of which the
    PDF renderer reads and prints — were unvalidated channels straight to the
    learner. A Greek look-alike in any of them reached the page with nothing
    having looked at it, and adding each missing name to the schema would only
    close the ones somebody remembered.

    So this asks the question of everything, and schema drift stops being able
    to create a new hole. It is language-agnostic by construction: what counts
    as alien comes from the taught language's own script profile, Latin is
    always permitted, and bracketed transcriptions are exempt.
    """
    profile = S.profile_for_language(language) if language else None
    if profile is None:
        return []
    out: List[Finding] = []

    def visit(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in _NON_PROSE_KEYS:
                    continue
                visit(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                visit(value, f"{path}[{index}]")
        elif isinstance(node, str) and node:
            field = path.rsplit(".", 1)[-1].split("[")[0]
            alien = [token for token in S.alien_script_tokens(node, profile)
                     if not _explicable_as_ipa(token)]
            if alien:
                out.append(Finding("alien_script_token", BLOCK, path=path, field=field,
                                   detail=", ".join(alien[:3]), value=node))

    visit(lesson, "")
    return out


def _audit_transcription_coverage(page: Dict[str, Any], path: str) -> List[Finding]:
    """A table where some rows are transcribed and others are silently not.

    The published lesson gave IPA for ⟨ch⟩, ⟨ll⟩ and ⟨rr⟩ and left ⟨ñ⟩, ⟨z⟩ and
    ⟨j⟩ blank in the same table. A learner reads the gap as "this one has no
    sound". Either the column belongs to the table or it does not.
    """
    out: List[Finding] = []
    for container in S.ENTRY_CONTAINERS:
        entries = page.get(container)
        if not isinstance(entries, list) or len(entries) < 3:
            continue
        rows = [e for e in entries if isinstance(e, dict) and
                any(str(e.get(k) or "").strip() for k in ("term", "word", "target"))]
        if len(rows) < 3:
            continue
        transcribed = [bool(str(e.get("phonetic") or "").strip()) for e in rows]
        filled = sum(transcribed)
        if 0 < filled < len(rows):
            missing = [str(rows[i].get("term") or rows[i].get("word") or "")
                       for i, ok in enumerate(transcribed) if not ok]
            out.append(Finding("partial_transcription_column", BLOCK,
                               path=f"{path}.{container}", field="phonetic", role=S.NOTATION,
                               detail=f"{filled} of {len(rows)} rows transcribed; missing: " +
                                      ", ".join(m for m in missing[:5] if m)))
    return out


def audit_items(items: Sequence[Dict[str, Any]], *, language: str = "",
                track: str = "tr") -> List[List[Finding]]:
    return [audit_item(item, language=language, track=track, path=f"items[{i}]")
            for i, item in enumerate(items or [])]


def blocking(findings: Iterable[Finding]) -> List[Finding]:
    return [f for f in findings if f.severity == BLOCK]


def summarise(findings: Iterable[Finding]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for finding in findings:
        counts[finding.code] = counts.get(finding.code, 0) + 1
    return counts
