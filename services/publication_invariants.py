"""Canonical deterministic publication invariants for AulaAI material.

This module is the single boundary for *deterministic* publication invariants that
are not Unicode/script repair (which lives in material_quality_guard) and not
rendering (which lives in pdf_renderer_v12).

Responsibilities, and only these:
  1. Structural assessment validity  -> prune only pages whose OWN type is "mcq".
  2. Accidental local duplication    -> collapse immediately-repeated content.
  3. Pedagogically empty filler      -> detect and flag; never publish silently.
  4. Claim-scope discipline          -> detect absolute/universal claims, and hedge
                                        ONLY claims the generator itself declared
                                        to be tendencies.
 4b. Evidence-exceeding claims       -> near-universal claims whose named exception
                                        set the lesson's own phonetic data refutes.
 4c. Claim domain                    -> tell a categorical structural rule from a
                                        contextual social/register convention, and
                                        find claims that nearby lesson content
                                        materially weakens.
 4d. Bounded-review request          -> build the single claim-review prompt and
                                        payload consumed by the existing verifier.

Sections 4b-4d only ever *route* claims to the one bounded semantic review that
already exists. They add no model call, and they never rewrite a claim: deciding
whether a social convention is genuinely universal is semantic work this module
deliberately refuses to fake.

Design rules enforced here:
  * Nothing in this module invents linguistic content.
  * Nothing here removes a substantive content page.
  * Every language-specific table is explicitly keyed by instructional language.
    An unknown instructional language yields a no-op, never a guess.
  * No assumptions about word boundaries, casing, scripts or whitespace beyond
    what Unicode itself guarantees (works for CJK, RTL and combining-mark scripts).
"""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

# ── Instructional-language resolution ───────────────────────────────────────

_LANGUAGE_ALIASES: Dict[str, str] = {
    "tr": "tr", "turkish": "tr", "türkçe": "tr", "turkce": "tr",
    "en": "en", "english": "en", "ingilizce": "en",
    "es": "es", "spanish": "es", "español": "es", "espanol": "es", "ispanyolca": "es",
    "de": "de", "german": "de", "deutsch": "de", "almanca": "de",
    "fr": "fr", "french": "fr", "français": "fr", "francais": "fr", "fransızca": "fr",
    "it": "it", "italian": "it", "italiano": "it", "italyanca": "it",
    "pt": "pt", "portuguese": "pt", "português": "pt", "portekizce": "pt",
    "ru": "ru", "russian": "ru", "rusça": "ru", "rusca": "ru",
}


def instructional_code(value: Any) -> Optional[str]:
    """Resolve an instructional-language label to a supported code, else None."""
    key = str(value or "").strip().casefold()
    return _LANGUAGE_ALIASES.get(key)


# ── 1. Structural assessment validity ───────────────────────────────────────

def _page_type(page: Any) -> str:
    if not isinstance(page, dict):
        return ""
    return str(page.get("type") or "").strip().casefold()


def prune_invalid_mcq_pages(data: Any) -> Any:
    """Remove ONLY pages whose own declared type is 'mcq' and which fail structural
    MCQ validation (option count, duplicate options, key alignment, placeholder or
    structurally malformed distractors).

    A page of any other type is never removed, regardless of what it contains.
    """
    if not isinstance(data, dict):
        return data
    pages = data.get("pages")
    if not isinstance(pages, list):
        return data

    try:
        from services.material_quality_guard import validate_mcq
    except Exception:  # pragma: no cover - guard import must not break publication
        return data

    kept: List[Any] = []
    removed: List[Dict[str, Any]] = []
    for index, page in enumerate(pages):
        if _page_type(page) == "mcq":
            try:
                ok, reason = validate_mcq(page)
            except Exception:
                ok, reason = True, ""
            if not ok:
                removed.append({"index": index, "reason": f"structural-mcq:{reason}"})
                continue
        kept.append(page)

    data["pages"] = kept
    if removed:
        prior = data.get("_integrity_removed_mcq")
        data["_integrity_removed_mcq"] = (prior if isinstance(prior, list) else []) + removed
    return data


# ── 2. Accidental local duplication ─────────────────────────────────────────

# Sentence/bullet boundary. Delimiters are captured so that the original spacing —
# including scripts that use no space after a terminator (CJK) — is preserved
# exactly when segments are dropped.
_SEGMENT_SPLIT = re.compile(r"([.!?。！？۔।]+\s*|\n+)")


def _fold_for_identity(value: Any) -> str:
    """Script-agnostic identity key: NFKC, casefolded, punctuation/space stripped."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(
        ch for ch in text
        if not unicodedata.category(ch).startswith(("P", "Z", "C"))
    )


def _collapse_repeated_segments(text: Any) -> Any:
    """Drop a sentence/bullet that exactly repeats the segment immediately before it."""
    if not isinstance(text, str) or len(text) < 12:
        return text
    parts = _SEGMENT_SPLIT.split(text)
    if len(parts) < 3:
        return text
    out: List[str] = []
    previous_key = None
    changed = False
    for index in range(0, len(parts), 2):
        segment = parts[index]
        delimiter = parts[index + 1] if index + 1 < len(parts) else ""
        key = _fold_for_identity(segment)
        if key and key == previous_key:
            changed = True
            continue
        out.append(segment + delimiter)
        if key:
            previous_key = key
    if not changed:
        return text
    return "".join(out).strip()


def _entry_identity(entry: Any, keys: Tuple[str, ...]) -> str:
    if isinstance(entry, dict):
        return "\u241f".join(_fold_for_identity(entry.get(k)) for k in keys)
    return _fold_for_identity(entry)


def _collapse_adjacent_entries(entries: Any, keys: Tuple[str, ...]) -> Any:
    """Remove a list entry identical to the entry immediately preceding it."""
    if not isinstance(entries, list) or len(entries) < 2:
        return entries
    out = []
    previous = None
    for entry in entries:
        identity = _entry_identity(entry, keys)
        if identity and identity.strip("\u241f") and identity == previous:
            continue
        out.append(entry)
        previous = identity
    return out


_PROSE_KEYS = (
    "text", "explanation", "analysis", "note", "context", "rule", "pitfall",
    "summary", "tip", "meaning", "definition",
)

_ITEM_IDENTITY_KEYS = ("term", "word", "target", "translation", "translation_tr")
_RULE_IDENTITY_KEYS = ("rule", "rule_tr", "explanation", "explanation_tr", "example")
_COMPARISON_IDENTITY_KEYS = ("target", "note", "note_tr", "translation")
_DIALOGUE_IDENTITY_KEYS = ("speaker", "text")


def _is_prose_key(key: str) -> bool:
    base = re.sub(r"_(?:en|tr|es|de|fr|it|pt|ru)$", "", str(key).casefold())
    return base in _PROSE_KEYS


def collapse_adjacent_duplicates(data: Any) -> Any:
    """Collapse accidental *local* duplication.

    Only immediate repetition is removed: a segment repeating the segment right
    before it, a list entry identical to its direct predecessor, or a page whose
    prose is byte-identical to the previous page's prose. Deliberate pedagogical
    reinforcement across non-adjacent sections is preserved untouched.
    """
    if not isinstance(data, dict):
        return data
    pages = data.get("pages")
    if not isinstance(pages, list):
        return data

    previous_prose: Dict[str, str] = {}
    for page in pages:
        if not isinstance(page, dict):
            previous_prose = {}
            continue

        for key, value in list(page.items()):
            if isinstance(value, str) and _is_prose_key(key):
                collapsed = _collapse_repeated_segments(value)
                identity = _fold_for_identity(collapsed)
                # Identical prose repeated on the directly preceding page is accidental.
                if identity and previous_prose.get(str(key)) == identity and len(identity) >= 24:
                    collapsed = ""
                page[key] = collapsed

        for container, keys in (
            ("items", _ITEM_IDENTITY_KEYS),
            ("vocabulary", _ITEM_IDENTITY_KEYS),
            ("words", _ITEM_IDENTITY_KEYS),
            ("rules", _RULE_IDENTITY_KEYS),
            ("comparisons", _COMPARISON_IDENTITY_KEYS),
            ("dialogue", _DIALOGUE_IDENTITY_KEYS),
        ):
            if isinstance(page.get(container), list):
                page[container] = _collapse_adjacent_entries(page[container], keys)

        for entry_list in ("rules", "comparisons", "items"):
            for entry in page.get(entry_list) or []:
                if isinstance(entry, dict):
                    for key, value in list(entry.items()):
                        if isinstance(value, str) and _is_prose_key(key):
                            entry[key] = _collapse_repeated_segments(value)

        previous_prose = {
            str(k): _fold_for_identity(v)
            for k, v in page.items()
            if isinstance(v, str) and _is_prose_key(k) and v.strip()
        }

    return data


# ── 3. Pedagogically empty filler ───────────────────────────────────────────

def _self_referential(value: Any, term: Any) -> bool:
    """True when a field merely restates the term it is supposed to explain."""
    v, t = _fold_for_identity(value), _fold_for_identity(term)
    return bool(v) and bool(t) and (v == t or v == t + t)


_CEFR_TOKEN = re.compile(r"\b[ABC][12]\b")


def is_generic_filler_item(item: Any, topic: str = "") -> bool:
    """Structural (not keyword-based) detection of pedagogically empty lexical rows."""
    if not isinstance(item, dict):
        return False
    term = item.get("term") or item.get("word") or ""
    if not str(term).strip():
        return True
    signals = 0
    phonetic = str(item.get("phonetic") or "").strip()
    # Fake IPA that is just the term echoed back inside brackets.
    if phonetic and _self_referential(phonetic.strip("[]/"), term):
        signals += 1
    if phonetic in ("[...]", "[…]", "[]"):
        signals += 1
    # Example that is only the headword (or the topic title) with punctuation.
    example = item.get("example") or ""
    if _self_referential(example, term) or (topic and _self_referential(example, topic)):
        signals += 1
    # Meaning that only restates the topic title rather than the item.
    for key in ("translation", "translation_tr", "meaning"):
        value = item.get(key)
        if topic and value and _fold_for_identity(topic) and _fold_for_identity(topic) in _fold_for_identity(value) and len(_fold_for_identity(value)) <= len(_fold_for_identity(topic)) + 12:
            signals += 1
            break
    # A vocabulary row whose headword IS the lesson topic is a topic label, not a word.
    if topic and _self_referential(term, topic):
        signals += 1
    return signals >= 2


def is_generic_filler_page(page: Any, topic: str = "") -> bool:
    """A structurally valid page carrying no teachable content."""
    if not isinstance(page, dict):
        return False
    if page.get("_synthetic_placeholder"):
        return True
    ptype = _page_type(page)

    if ptype in ("vocabulary", ""):
        items = page.get("items") or page.get("vocabulary") or page.get("words")
        if isinstance(items, list) and items:
            filler = sum(1 for it in items if is_generic_filler_item(it, topic))
            if filler >= max(1, int(len(items) * 0.6)):
                return True

    if ptype == "mcq":
        # An MCQ whose keyed answer is a meta-statement about the CEFR level itself
        # tests nothing about the language.
        answer = str(page.get("answer") or "")
        if _CEFR_TOKEN.search(answer) and topic and _fold_for_identity(topic) not in _fold_for_identity(answer):
            options = [str(o) for o in (page.get("options") or [])]
            if sum(1 for o in options if _CEFR_TOKEN.search(o)) <= 1 and len(answer.split()) >= 6:
                return True
    return False


def flag_generic_filler(data: Any, topic: str = "") -> Any:
    """Mark filler pages for review instead of silently publishing them as teaching."""
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return data
    flagged = []
    for index, page in enumerate(data["pages"]):
        if is_generic_filler_page(page, topic):
            if isinstance(page, dict):
                page["_review_required"] = True
            flagged.append(index)
    if flagged:
        data["_review_required"] = True
        data["_filler_pages"] = flagged
    return data


# ── 4. Claim-scope discipline ───────────────────────────────────────────────
#
# Absolute quantifiers are detected per instructional language. Detection alone
# never rewrites anything: text is hedged only when the generator itself declared
# the claim to be a tendency (``scope``), i.e. when the generator's own prose
# contradicts the generator's own scope declaration.

_ABSOLUTE_CLAIM_PATTERNS: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "tr": (
        (r"\bher\s+zaman\b", "genellikle"),
        (r"\bdaima\b", "çoğunlukla"),
        (r"\bmutlaka\b", "genellikle"),
        (r"\bhiçbir\s+zaman\b", "çoğunlukla"),
        (r"\basla\b", "genellikle"),
        (r"\bistisnasız\b", "çoğu durumda"),
        (r"\btüm\s+durumlarda\b", "çoğu durumda"),
        (r"\bdüzenli\s+olarak\b", "çoğunlukla"),
        (r"\bkuralsız\s+değildir\b", "genellikle düzenlidir"),
        # Deontic obligation/prohibition: categorical in force, not in quantity.
        (r"\bzorunludur\b", "genellikle beklenir"),
        (r"\bzorunlu\s+olarak\b", "genellikle"),
        (r"\bmecburidir\b", "genellikle beklenir"),
        (r"\bşarttır\b", "genellikle beklenir"),
        (r"\bsarttir\b", "genellikle beklenir"),
        (r"\bkesinlikle\b", "genellikle"),
        (r"\byasaktır\b", "genellikle uygun değildir"),
    ),
    "en": (
        (r"\balways\b", "usually"),
        (r"\bnever\b", "usually does not"),
        (r"\bin\s+all\s+cases\b", "in most cases"),
        (r"\bwithout\s+exception\b", "in most cases"),
        (r"\bevery\s+time\b", "usually"),
        (r"\binvariably\b", "typically"),
        (r"\bis\s+mandatory\b", "is normally expected"),
        (r"\bis\s+obligatory\b", "is normally expected"),
        (r"\bis\s+required\b", "is normally expected"),
        (r"\bis\s+forbidden\b", "is normally avoided"),
        (r"\bis\s+prohibited\b", "is normally avoided"),
        (r"\bmust\s+always\b", "should normally"),
        (r"\bmust\s+never\b", "should normally not"),
    ),
    "es": (
        (r"\bsiempre\b", "normalmente"),
        (r"\bnunca\b", "normalmente no"),
        (r"\bsin\s+excepción\b", "en la mayoría de los casos"),
        (r"\ben\s+todos\s+los\s+casos\b", "en la mayoría de los casos"),
        (r"\bes\s+obligatorio\b", "normalmente se espera"),
        (r"\bes\s+obligatoria\b", "normalmente se espera"),
        (r"\bestá\s+prohibido\b", "normalmente se evita"),
    ),
    "de": (
        (r"\bimmer\b", "meistens"),
        (r"\bniemals\b", "normalerweise nicht"),
        (r"\bausnahmslos\b", "in den meisten Fällen"),
        (r"\bin\s+allen\s+Fällen\b", "in den meisten Fällen"),
        (r"\bist\s+obligatorisch\b", "wird normalerweise erwartet"),
        (r"\bist\s+Pflicht\b", "wird normalerweise erwartet"),
        (r"\bist\s+verboten\b", "wird normalerweise vermieden"),
        (r"\bmuss\s+immer\b", "sollte normalerweise"),
    ),
    "fr": (
        (r"\btoujours\b", "généralement"),
        (r"\bjamais\b", "généralement pas"),
        (r"\bsans\s+exception\b", "dans la plupart des cas"),
        (r"\bdans\s+tous\s+les\s+cas\b", "dans la plupart des cas"),
        (r"\best\s+obligatoire\b", "est normalement attendu"),
        (r"\best\s+interdit\b", "est normalement évité"),
        (r"\bdoit\s+toujours\b", "doit normalement"),
    ),
    "it": (
        (r"\bsempre\b", "di solito"),
        (r"\bmai\b", "di solito non"),
        (r"\bsenza\s+eccezioni\b", "nella maggior parte dei casi"),
        (r"\bè\s+obbligatorio\b", "di norma è atteso"),
        (r"\bè\s+vietato\b", "di norma si evita"),
        (r"\bdeve\s+sempre\b", "di norma deve"),
    ),
    "pt": (
        (r"\bsempre\b", "normalmente"),
        (r"\bnunca\b", "normalmente não"),
        (r"\bsem\s+exceção\b", "na maioria dos casos"),
        (r"\bé\s+obrigatório\b", "normalmente espera-se"),
        (r"\bé\s+proibido\b", "normalmente evita-se"),
        (r"\bdeve\s+sempre\b", "normalmente deve"),
    ),
    "ru": (
        (r"\bвсегда\b", "обычно"),
        (r"\bникогда\b", "обычно не"),
        (r"\bбез\s+исключений\b", "в большинстве случаев"),
        (r"\bобязательно\b", "как правило"),
        (r"\bзапрещено\b", "как правило не принято"),
    ),
}

# Exclusivity / restriction wording. "X is used ONLY for Y" forecloses every
# other context, so it is a scope claim exactly as categorical as "always" - and
# it was invisible to the claim layer, which is how restrictive register claims
# kept publishing unreviewed.
#
# These are DETECTION-ONLY and deliberately absent from the table above:
# deterministic code cannot tell restricted *usage* ("used only in formal
# speech") from a plain count ("there are only two forms"), and rewriting the
# second would corrupt a correct sentence. Detection routes the claim to the
# bounded reviewer, which can tell the difference; nothing here ever rewrites.
_EXCLUSIVITY_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "tr": (r"\bsadece\b", r"\byalnızca\b", r"\byalnizca\b", r"\bsırf\b", r"\bsirf\b",
           r"\byalnız\b", r"\bdışında\s+kullanılmaz\b"),
    "en": (r"\bonly\s+for\b", r"\bonly\s+in\b", r"\bonly\s+when\b", r"\bonly\s+with\b",
           r"\bonly\s+used\b", r"\bused\s+only\b", r"\bexclusively\b", r"\bsolely\b",
           r"\breserved\s+for\b"),
    "es": (r"\bsólo\s+se\b", r"\bsolo\s+se\b", r"\búnicamente\b", r"\bexclusivamente\b"),
    "de": (r"\bnur\s+für\b", r"\bnur\s+bei\b", r"\bnur\s+in\b", r"\bausschließlich\b"),
    "fr": (r"\buniquement\b", r"\bexclusivement\b", r"\bseulement\s+pour\b"),
    "it": (r"\bsoltanto\b", r"\besclusivamente\b", r"\bsolo\s+per\b"),
    "pt": (r"\bapenas\s+para\b", r"\bapenas\s+em\b", r"\bexclusivamente\b"),
    "ru": (r"\bтолько\s+для\b", r"\bтолько\s+в\b", r"\bисключительно\b"),
}


_TENDENCY_SCOPES = {
    "tendency", "tendencies", "typical", "usual", "general", "preference",
    "eğilim", "egilim", "genel", "yaygın", "yaygin",
    "tendencia", "tendenz", "tendance", "tendenza", "тенденция",
}
_ABSOLUTE_SCOPES = {"absolute", "exceptionless", "kesin", "mutlak", "invariable"}

# Quoted target-language material and code spans are never touched.
_PROTECTED_SPAN = re.compile(r'(`[^`\n]*`|“[^”\n]*”|«[^»\n]*»|"[^"\n]*"|\'[^\'\n]{1,80}\')')


def find_absolute_claims(text: Any, instructional_language: Any) -> List[str]:
    """Return categorical-scope wording found outside quoted target material.

    Covers quantifiers and deontic obligation (which are also hedged automatically
    when the generator declared a tendency) plus exclusivity wording, which is
    detected here but never rewritten deterministically - see _EXCLUSIVITY_PATTERNS.
    """
    code = instructional_code(instructional_language)
    if not isinstance(text, str) or not text.strip():
        return []
    patterns = _ABSOLUTE_CLAIM_PATTERNS.get(code or "")
    exclusivity = _EXCLUSIVITY_PATTERNS.get(code or "", ())
    if not patterns and not exclusivity:
        return []
    found: List[str] = []
    parts = _PROTECTED_SPAN.split(text)
    for i in range(0, len(parts), 2):
        for pattern, _ in (patterns or ()):
            found.extend(m.group(0) for m in re.finditer(pattern, parts[i], flags=re.IGNORECASE))
        for pattern in exclusivity:
            found.extend(m.group(0) for m in re.finditer(pattern, parts[i], flags=re.IGNORECASE))
    return found


def hedge_absolute_claims(text: Any, instructional_language: Any) -> Any:
    """Downgrade absolute quantifiers to scoped wording in instructional prose."""
    code = instructional_code(instructional_language)
    patterns = _ABSOLUTE_CLAIM_PATTERNS.get(code or "")
    if not patterns or not isinstance(text, str) or not text.strip():
        return text
    parts = _PROTECTED_SPAN.split(text)
    for i in range(0, len(parts), 2):
        for pattern, replacement in patterns:
            parts[i] = re.sub(pattern, replacement, parts[i], flags=re.IGNORECASE)
    return "".join(parts)


_TRACK_SUFFIX = re.compile(r"_(en|tr|es|de|fr|it|pt|ru)$")


def _track_language(key: str, material_language: Any) -> Optional[str]:
    """Instructional language that a given field is written in, or None if unknown."""
    match = _TRACK_SUFFIX.search(str(key).casefold())
    if match:
        return match.group(1)
    # Untagged instructional prose in this codebase is the English track.
    return "en"


_CLAIM_FIELDS = ("rule", "explanation", "analysis", "note", "text", "pitfall")


def _claim_bearing_fields(entry: Dict[str, Any]) -> List[str]:
    out = []
    for key in entry:
        base = _TRACK_SUFFIX.sub("", str(key).casefold())
        if base in _CLAIM_FIELDS and isinstance(entry.get(key), str):
            out.append(key)
    return out


def apply_declared_scope(data: Any, material_language: str = "tr") -> Any:
    """Hedge absolute wording in rules the generator itself declared to be tendencies.

    Rules declared (or left) absolute are NOT rewritten here: deterministic code
    cannot establish linguistic truth, so it only enforces internal consistency
    between the generator's declared scope and its own wording.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return data
    for page in data["pages"]:
        if not isinstance(page, dict):
            continue
        for entry in (page.get("rules") or []) + (page.get("comparisons") or []):
            if not isinstance(entry, dict):
                continue
            scope = str(entry.get("scope") or "").strip().casefold()
            if scope not in _TENDENCY_SCOPES:
                continue
            for key in _claim_bearing_fields(entry):
                entry[key] = hedge_absolute_claims(entry[key], _track_language(key, material_language))
    return data


def collect_unscoped_absolute_claims(data: Any, material_language: str = "tr", limit: int = 12) -> List[Dict[str, Any]]:
    """List absolute claims worth spending the bounded verifier call on.

    A claim qualifies when it uses absolute wording AND either:

      * the generator did not declare it exceptionless, or
      * it reads as a social/register/cultural/pedagogical convention.

    The second condition is the fix for a real production failure. Previously an
    explicit ``scope: "absolute"`` suppressed review outright, which made the
    generator the sole judge of its own strongest claims. That is sound for a
    structural law - deterministic code has no business second-guessing a spelling
    or morphology rule the generator marked categorical - but it is exactly
    backwards for contextual conventions, where the generator is most prone to
    publish beginner simplifications ("this greeting is mandatory for teachers")
    as exceptionless linguistic law. A declared scope is still respected for
    structural and unclassifiable claims, so ordinary lessons are unaffected.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return []
    claims: List[Dict[str, Any]] = []
    for p_index, page in enumerate(data["pages"]):
        if not isinstance(page, dict):
            continue
        containers: List[Tuple[str, int, Dict[str, Any]]] = [("page", p_index, page)]
        for container in ("rules", "comparisons"):
            for e_index, entry in enumerate(page.get(container) or []):
                if isinstance(entry, dict):
                    containers.append((container, e_index, entry))
        for container, index, entry in containers:
            scope = str(entry.get("scope") or "").strip().casefold()
            declared_absolute = scope in _ABSOLUTE_SCOPES
            for key in _claim_bearing_fields(entry):
                text = entry[key]
                code = _track_language(key, material_language)
                matches = find_absolute_claims(text, code)
                if not matches:
                    continue
                domain = _declared_domain(entry) or classify_claim_domain(text, code)
                if declared_absolute and domain != "social":
                    continue
                # Page-level prose is narrative, not a declared rule: it carries no
                # `scope` and no rule framing, so absolute wording alone is not
                # evidence of a claim ("he always has breakfast" is a story). Require
                # a positive teaching-domain cue before spending review on it.
                # Entries under `rules`/`comparisons` are claims by construction.
                if container == "page" and domain is None:
                    continue
                path = f"pages.{p_index}.{key}" if container == "page" else f"pages.{p_index}.{container}.{index}.{key}"
                claims.append({
                    "path": path,
                    "text": text[:600],
                    "quantifiers": sorted(set(matches)),
                    "examples": _claim_evidence(page, exclude=text),
                    "domain": domain or "unknown",
                })
                if len(claims) >= limit:
                    return claims
    return claims


_DECLARED_DOMAINS = {
    "orthography": "structural", "spelling": "structural", "morphology": "structural",
    "syntax": "structural", "grammar": "structural", "pronunciation": "structural",
    "phonology": "structural", "lexis": None, "lexical": None, "meaning": None,
    "register": "social", "politeness": "social", "culture": "social",
    "cultural": "social", "social": "social", "pedagogy": "social",
    "pedagogical": "social", "usage": "social",
}


def _declared_domain(entry: Dict[str, Any]) -> Optional[str]:
    """Honour a generator-declared `domain`, when it is one we understand.

    The generator labelling its own claim is cheap and more reliable than cue
    matching, but it is advisory only: an unknown or missing label falls through
    to :func:`classify_claim_domain`, never to a guess.
    """
    raw = str(entry.get("domain") or "").strip().casefold()
    return _DECLARED_DOMAINS.get(raw) if raw in _DECLARED_DOMAINS else None


def _sibling_examples(page: Dict[str, Any], limit: int = 6) -> List[str]:
    """Target-language evidence present on the same page, for contradiction checking."""
    out: List[str] = []
    for container in ("items", "vocabulary", "words", "rules", "comparisons"):
        for entry in page.get(container) or []:
            if not isinstance(entry, dict):
                continue
            term = str(entry.get("term") or entry.get("word") or entry.get("target") or "").strip()
            phon = str(entry.get("phonetic") or "").strip()
            example = str(entry.get("example") or "").strip()
            snippet = " ".join(x for x in (term, phon, example) if x)
            if snippet:
                out.append(snippet[:120])
            if len(out) >= limit:
                return out
    return out


# ── 4b. Generalizations that exceed their own local evidence ───────────────
#
# The claim-scope mechanism above (section 4) catches hard absolute wording
# ("always", "never", "without exception"). It does NOT catch a claim that is
# already hedged ("almost all X do Y") but names a specific member as the
# counter-case while the SAME lesson's own evidence (vocabulary items with
# authoritative IPA transcriptions, possibly on a different page) shows an
# ADDITIONAL member behaving the same divergent way that the claim never
# names. That is a distinct failure mode: the wording is not overclaimed in
# absolute terms, but the claimed EXCEPTION SET is narrower than the material's
# own displayed evidence.
#
# This is checked, not guessed: the only property tested is the position of
# the IPA primary-stress mark relative to the end of the transcription
# (counted in IPA vowel symbols after the mark), for words on the SAME lesson
# that share a long trailing substring with the named exception term. That is
# literal use of data the generator already marked as authoritative, not a
# phonological model built from regexes. When the required data is missing —
# no shared-suffix family, or any family member lacks a stress mark — nothing
# is claimed, by design; a "can't compute" case is never treated as a hit.
#
# Detection is fully deterministic. Correction is not attempted here: knowing
# the true, complete exception set (which may include members not present on
# this page at all) requires linguistic knowledge no regex has, so a detected
# contradiction is queued for the SAME bounded verifier already used for
# unscoped absolute claims (services/ai_engine.py::_verify_absolute_claims) —
# not a new model call.

_IPA_VOWELS = set("aeiouyɪʏʊɘɵɤɯɨʉɐəɛœɜɞʌɔæɶɑɒ")

_NEAR_UNIVERSAL_HEDGE_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "tr": (r"\bneredeyse\s+t[üu]m\b", r"\bhemen\s+hemen\s+t[üu]m\b", r"\b[çc]o[ğg]unlu[ğg]u\b",
           r"\b[çc]o[ğg]unlukla\b", r"\bgenellikle\b"),
    "en": (r"\balmost\s+all\b", r"\bnearly\s+all\b", r"\bthe\s+majority\s+of\b",
           r"\bmost\s+(?:of\s+the\s+)?\w+\b", r"\bgenerally\b"),
    "es": (r"\bcasi\s+todos\b", r"\bla\s+mayor[ií]a\b", r"\bgeneralmente\b"),
    "de": (r"\bfast\s+alle\b", r"\bdie\s+meisten\b", r"\bin\s+der\s+regel\b"),
    "fr": (r"\bpresque\s+tous\b", r"\bla\s+plupart\b", r"\bg[ée]n[ée]ralement\b"),
    "it": (r"\bquasi\s+tutti\b", r"\bla\s+maggior\s+parte\b", r"\bgeneralmente\b"),
    "pt": (r"\bquase\s+todos\b", r"\ba\s+maioria\b", r"\bgeralmente\b"),
    "ru": (r"\bпочти\s+вс[её]\b", r"\bбольшинств\w*\b", r"\bобычно\b"),
}

_EXCEPTION_MARKER_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "tr": (r"\bistisna\w*\b", r"\bhari[çc]\b", r"\bd[ıi][şs][ıi]nda\b"),
    "en": (r"\bexcept\w*\b", r"\bwith\s+the\s+exception\b"),
    "es": (r"\bexcepto\b", r"\bsalvo\b", r"\bexcepci[oó]n\w*\b"),
    "de": (r"\baußer\b", r"\bausnahme\w*\b"),
    "fr": (r"\bsauf\b", r"\bexception\w*\b"),
    "it": (r"\beccetto\b", r"\beccezion\w*\b"),
    "pt": (r"\bexceto\b", r"\bexce[cç][aã]o\w*\b"),
    "ru": (r"\bисключен\w*\b", r"\bкроме\b"),
}


def _has_generalization_marker(text: str, code: Optional[str]) -> bool:
    """True when the text hedges toward near-universality or names an exception,
    in either case implying a claim about which members of a set are typical
    and which are not."""
    if not code or not isinstance(text, str) or not text.strip():
        return False
    patterns = _NEAR_UNIVERSAL_HEDGE_PATTERNS.get(code, ()) + _EXCEPTION_MARKER_PATTERNS.get(code, ())
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def _collect_lesson_terms(data: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
    """Map a folded term to (original term, authoritative phonetic) across the
    WHOLE lesson, not just one page — the contradicting evidence is typically on
    a separate vocabulary page from the grammar rule that generalizes over it."""
    out: Dict[str, Tuple[str, str]] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            term = node.get("term") or node.get("word") or node.get("target")
            phon = node.get("phonetic")
            if term and isinstance(phon, str) and phon.strip():
                key = _fold_for_identity(term)
                if key and key not in out:
                    out[key] = (str(term), phon)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data.get("pages"))
    return out


def _shared_suffix_len(a: str, b: str) -> int:
    fa, fb = _fold_for_identity(a), _fold_for_identity(b)
    n = 0
    for ca, cb in zip(reversed(fa), reversed(fb)):
        if ca != cb:
            break
        n += 1
    return n


def _stress_syllables_from_end(phonetic: Any) -> Optional[int]:
    """Count IPA vowel symbols after the primary-stress mark, to the end of the
    transcription. A generic, script-independent proxy for stress placement that
    needs no knowledge of any specific language's syllable structure. Returns
    None when the transcription carries no primary-stress mark at all — that is
    a "cannot compute" result, not a zero."""
    text = str(phonetic or "")
    if "ˈ" not in text:
        return None
    tail = text[text.index("ˈ") + 1:]
    return sum(1 for ch in tail if ch in _IPA_VOWELS)


def _named_terms_in_text(text: str, lesson_terms: Dict[str, Tuple[str, str]]) -> List[str]:
    """Lesson-known target-language terms that appear (quoted or bare) inside the
    given prose. Catches both `'termin'` and a bare embedded term, since generated
    Turkish/English prose does not consistently quote inline target words."""
    folded_text = _fold_for_identity(text)
    found = []
    for term, _ in lesson_terms.values():
        fterm = _fold_for_identity(term)
        if len(fterm) >= 3 and fterm in folded_text:
            found.append(term)
    return found


def _find_generalization_contradiction(
    anchor_terms: List[str], lesson_terms: Dict[str, Tuple[str, str]]
) -> Optional[Dict[str, Any]]:
    """Return contradiction evidence when the lesson's own data shows a member,
    other than the ones named in `anchor_terms`, patterning with the named
    exception(s) rather than with the majority — i.e. an undisclosed additional
    exception. Returns None whenever the required data is incomplete: a small
    family, a missing stress mark anywhere in the family, or no genuine
    divergence between the anchor(s) and the majority is treated as "cannot
    confirm", never as a positive result.
    """
    anchor_keys = {_fold_for_identity(t) for t in anchor_terms if t}
    anchor_entries = [(k, lesson_terms[k]) for k in anchor_keys if k in lesson_terms]
    if not anchor_entries:
        return None

    # Family = lesson terms sharing a long trailing substring with an anchor term,
    # i.e. plausibly the same morphological/lexical class the claim is about.
    family: List[Tuple[str, str, str]] = []
    for key, (term, phon) in lesson_terms.items():
        fterm_len = len(_fold_for_identity(term))
        if fterm_len < 4:
            continue
        overlap = max(_shared_suffix_len(term, a_term) for _, (a_term, _) in anchor_entries)
        threshold = max(3, min(fterm_len, min(len(_fold_for_identity(a_term)) for _, (a_term, _) in anchor_entries)) // 2)
        if overlap >= threshold:
            family.append((key, term, phon))
    if len(family) < 3:
        return None

    values: Dict[str, int] = {}
    for key, _term, phon in family:
        v = _stress_syllables_from_end(phon)
        if v is None:
            # Any family member without computable data means the family-wide
            # comparison is unreliable: do not guess.
            return None
        values[key] = v

    anchor_values = {k: values[k] for k in anchor_keys if k in values}
    if not anchor_values:
        return None
    non_anchor = {k: v for k, v in values.items() if k not in anchor_keys}
    if len(non_anchor) < 2:
        return None

    counts: Dict[int, int] = {}
    for v in non_anchor.values():
        counts[v] = counts.get(v, 0) + 1
    majority_value = max(counts.items(), key=lambda kv: kv[1])[0]

    # The claim only makes sense as an "exception" framing if the anchor(s)
    # genuinely diverge from the majority pattern.
    if all(v == majority_value for v in anchor_values.values()):
        return None

    lookup = {key: term for key, term, _ in family}
    phon_lookup = {key: phon for key, _, phon in family}
    outliers = [k for k, v in non_anchor.items() if v != majority_value]
    if not outliers:
        return None

    evidence = [f"{lookup[k]} {phon_lookup[k]} (named exception)" for k in anchor_keys if k in anchor_values]
    evidence += [f"{lookup[k]} {phon_lookup[k]} (patterns like the named exception, not named)" for k in outliers]
    evidence += [
        f"{lookup[k]} {phon_lookup[k]} (patterns with the majority)"
        for k, v in non_anchor.items() if v == majority_value
    ][:3]
    return {"evidence": evidence}


def collect_generalization_contradictions(
    data: Any, material_language: str = "tr", limit: int = 8
) -> List[Dict[str, Any]]:
    """Find near-universal or exception-framed claims whose named exception set
    is narrower than what the lesson's own evidence shows.

    This is the general form of "local evidence contradicts the generated
    generalization": nothing here is specific to stress, to Russian, or to
    numbers — it operates on whatever shared-suffix family and phonetic data the
    lesson happens to contain, in any instructional or target language.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return []
    lesson_terms = _collect_lesson_terms(data)
    if len(lesson_terms) < 3:
        return []

    claims: List[Dict[str, Any]] = []
    for p_index, page in enumerate(data["pages"]):
        if not isinstance(page, dict):
            continue
        containers: List[Tuple[str, int, Dict[str, Any]]] = []
        for container in ("rules", "comparisons"):
            for e_index, entry in enumerate(page.get(container) or []):
                if isinstance(entry, dict):
                    containers.append((container, e_index, entry))
        for container, index, entry in containers:
            for key in _claim_bearing_fields(entry):
                text = entry.get(key)
                if not isinstance(text, str) or not text.strip():
                    continue
                code = _track_language(key, material_language)
                if not _has_generalization_marker(text, code):
                    continue
                anchor_terms = _named_terms_in_text(text, lesson_terms)
                if not anchor_terms:
                    continue
                result = _find_generalization_contradiction(anchor_terms, lesson_terms)
                if not result:
                    continue
                claims.append({
                    "path": f"pages.{p_index}.{container}.{index}.{key}",
                    "text": text[:600],
                    "quantifiers": ["generalization-narrower-than-evidence"],
                    "examples": result["evidence"],
                })
                if len(claims) >= limit:
                    return claims
    return claims


# ── 4c. Claim domain: structural law vs contextual convention ───────────────
#
# Sections 4 and 4b treat every absolute claim alike. That is wrong in one
# specific, recurring way: absolute wording is *legitimate* for an orthographic,
# morphological, syntactic or phonological law ("after this grapheme that vowel
# is never written") and *suspect* for a social/register convention ("this
# greeting is mandatory for teachers"). Both read identically to a quantifier
# matcher, so section 4 either over-hedges real rules or, as in production, lets
# contextual conventions publish as exceptionless linguistic law.
#
# This section adds the minimum needed to tell those two apart. It does NOT
# decide linguistic truth - it decides which claims deserve the bounded semantic
# review that already exists. The cue lexicon is explicitly keyed by
# instructional language; an unrecognised language classifies as None, which
# restores exactly the pre-existing behaviour rather than guessing.

_DOMAIN_CUES: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "tr": {
        "social": (
            "resmî", "resmi", "gayriresmî", "samimi", "teklifsiz", "nazik", "nezaket",
            "kibar", "saygı", "hitap", "üslup", "uslup", "bağlam", "baglam", "ortam",
            "kültür", "kultur", "görgü", "gorgu", "öğretmen", "ogretmen", "amir",
            "patron", "müşteri", "musteri", "yabancı", "yabanci", "arkadaş", "arkadas",
            "akran", "selamlaş", "selamlas", "vedalaş", "vedalas", "büyükler",
        ),
        "structural": (
            "harf", "ünlü", "unlu", "ünsüz", "unsuz", "hece", "vurgu", "çekim", "cekim",
            "gövde", "govde", "çoğul", "cogul", "tekil", "eril", "dişil", "disil",
            "cinsiyet", "sözdizimi", "sozdizimi", "sıralama", "siralama", "yazım",
            "yazim", "yazılır", "yazilir", "okunur", "telaffuz", "fiil", "isim",
            "sıfat", "sifat", "zamir", "edat", "uyum", "ünsüzler", "hâl eki", "hal eki",
        ),
    },
    "en": {
        "social": (
            "formal", "informal", "polite", "politeness", "courtesy", "respect",
            "register", "etiquette", "culture", "cultural", "situation", "context",
            "teacher", "boss", "supervisor", "customer", "elder", "stranger",
            "friend", "peer", "greeting", "farewell", "address someone", "social",
        ),
        "structural": (
            "letter", "vowel", "consonant", "syllable", "stress", "suffix", "prefix",
            "ending", "case", "gender", "plural", "singular", "conjugat", "declen",
            "stem", "root", "spell", "written", "write", "word order", "agreement",
            "pronounce", "pronunciation", "verb", "noun", "adjective", "pronoun",
            "preposition", "grapheme", "orthograph",
        ),
    },
    "es": {
        "social": (
            "formal", "informal", "cortesía", "cortesia", "respeto", "registro",
            "educado", "cultura", "contexto", "situación", "situacion", "profesor",
            "cliente", "jefe", "desconocido", "amigo", "saludo", "despedida",
        ),
        "structural": (
            "letra", "vocal", "consonante", "sílaba", "silaba", "acento", "sufijo",
            "prefijo", "terminación", "terminacion", "género", "genero", "plural",
            "singular", "conjuga", "declina", "raíz", "raiz", "ortograf", "escribe",
            "pronuncia", "verbo", "sustantivo", "adjetivo", "pronombre",
        ),
    },
    "de": {
        "social": (
            "formell", "informell", "höflich", "hoflich", "höflichkeit", "hoflichkeit",
            "respekt", "register", "kultur", "kontext", "situation", "lehrer",
            "kunde", "chef", "fremde", "freund", "begrüßung", "begrussung", "anrede",
        ),
        "structural": (
            "buchstabe", "vokal", "konsonant", "silbe", "betonung", "suffix", "präfix",
            "prafix", "endung", "kasus", "genus", "plural", "singular", "konjugier",
            "deklin", "stamm", "rechtschreib", "geschrieben", "ausspra", "verb",
            "substantiv", "adjektiv", "pronomen", "wortstellung",
        ),
    },
    "fr": {
        "social": (
            "formel", "informel", "poli", "politesse", "respect", "registre",
            "culture", "contexte", "situation", "professeur", "client", "patron",
            "inconnu", "ami", "salutation", "adresser",
        ),
        "structural": (
            "lettre", "voyelle", "consonne", "syllabe", "accent", "suffixe", "préfixe",
            "prefixe", "terminaison", "genre", "pluriel", "singulier", "conjug",
            "déclin", "declin", "radical", "orthograph", "écrit", "ecrit",
            "prononc", "verbe", "nom", "adjectif", "pronom",
        ),
    },
    "it": {
        "social": (
            "formale", "informale", "cortesia", "rispetto", "registro", "cultura",
            "contesto", "situazione", "insegnante", "cliente", "capo", "amico",
            "saluto", "rivolgersi",
        ),
        "structural": (
            "lettera", "vocale", "consonante", "sillaba", "accento", "suffisso",
            "prefisso", "desinenza", "genere", "plurale", "singolare", "coniug",
            "declin", "radice", "ortograf", "scritt", "pronunc", "verbo", "sostantivo",
            "aggettivo", "pronome",
        ),
    },
    "pt": {
        "social": (
            "formal", "informal", "cortesia", "respeito", "registro", "cultura",
            "contexto", "situação", "situacao", "professor", "cliente", "chefe",
            "amigo", "saudação", "saudacao", "dirigir-se",
        ),
        "structural": (
            "letra", "vogal", "consoante", "sílaba", "silaba", "acento", "sufixo",
            "prefixo", "terminação", "terminacao", "género", "genero", "plural",
            "singular", "conjuga", "declina", "raiz", "ortograf", "escrit",
            "pronunc", "verbo", "substantivo", "adjetivo", "pronome",
        ),
    },
    "ru": {
        "social": (
            "формальн", "неформальн", "вежлив", "уважени", "регистр", "культур",
            "контекст", "ситуаци", "учител", "клиент", "начальник", "друг",
            "приветстви", "обращени",
        ),
        "structural": (
            "буква", "гласн", "согласн", "слог", "ударени", "суффикс", "приставк",
            "окончани", "падеж", "род", "множественн", "единственн", "спряжени",
            "склонени", "основа", "орфограф", "пишется", "произнос", "глагол",
            "существительн", "прилагательн", "местоимени",
        ),
    },
}

# Prose that admits a competing option in the same breath ("both X and Y",
# "Y is also usable"). Used only as corroboration next to a competing term.
_ALTERNATIVE_MARKERS: Dict[str, Tuple[str, ...]] = {
    "tr": ("hem ", " de kullanıl", " da kullanıl", "veya", "ya da", "alternatif",
           "her iki", "ikisi de", "hem de", " de uygun", " da uygun"),
    "en": ("both", "also", "as well", "either", "alternatively", " too", "or "),
    "es": ("ambos", "ambas", "también", "tambien", "o bien", "cualquiera"),
    "de": ("beide", "auch", "sowohl", "oder"),
    "fr": ("les deux", "aussi", "également", "egalement", "ou bien"),
    "it": ("entrambi", "anche", "oppure"),
    "pt": ("ambos", "também", "tambem", "ou ainda"),
    "ru": ("оба", "также", "тоже", "либо", "или"),
}

_DOMAIN_CUE_RE: Dict[Tuple[str, str], "re.Pattern[str]"] = {}


def _domain_cue_regex(code: str, domain: str) -> Optional["re.Pattern[str]"]:
    """Word-initial cue matcher: matches a cue at a word start and tolerates any
    inflectional/agglutinative tail, which is what Turkish and Russian need."""
    key = (code, domain)
    if key not in _DOMAIN_CUE_RE:
        cues = _DOMAIN_CUES.get(code, {}).get(domain)
        if not cues:
            _DOMAIN_CUE_RE[key] = None  # type: ignore[assignment]
        else:
            pattern = "|".join(re.escape(c) for c in sorted(cues, key=len, reverse=True))
            _DOMAIN_CUE_RE[key] = re.compile(r"(?<!\w)(?:" + pattern + r")", re.IGNORECASE)
    return _DOMAIN_CUE_RE[key]


def _domain_cue_hits(text: Any, code: Optional[str], domain: str) -> List[str]:
    """Distinct cue strings of one domain present in the text."""
    regex = _domain_cue_regex(code or "", domain)
    if regex is None or not isinstance(text, str) or not text.strip():
        return []
    return sorted({m.group(0).casefold() for m in regex.finditer(text)})


def classify_claim_domain(text: Any, instructional_language: Any) -> Optional[str]:
    """Classify a claim as ``"social"``, ``"structural"`` or None (unknown).

    Deliberately coarse. The only distinction that matters downstream is whether
    absolute wording is *expected* (a structural law) or *suspect* (a contextual
    convention). Social cues win ties because a claim that invokes formality,
    politeness, social roles or situation is a claim about usage-in-context even
    when it also names a grammatical form - that conflation is the exact defect
    this section exists to catch. An unknown instructional language, or prose with
    no cues at all, returns None and is handled exactly as before.
    """
    code = instructional_code(instructional_language)
    if not code or code not in _DOMAIN_CUES:
        return None
    social = len(_domain_cue_hits(text, code, "social"))
    structural = len(_domain_cue_hits(text, code, "structural"))
    if social and social >= structural:
        return "social"
    if structural:
        return "structural"
    return None


def _collect_lesson_expressions(data: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
    """Every target-language expression the lesson names, phonetics or not.

    ``_collect_lesson_terms`` requires an authoritative phonetic because the
    stress detector compares transcriptions. A register or usage claim is about
    expressions that frequently carry no IPA at all, so this collector must not
    inherit that requirement - otherwise the contradiction detector below would
    silently reduce to a phonetics-only check.
    """
    out: Dict[str, Tuple[str, str]] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            term = _entry_term(node)
            if term:
                key = _fold_for_identity(term)
                if key and key not in out:
                    out[key] = (term, str(node.get("phonetic") or ""))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data.get("pages"))
    return out


def _entry_prose(entry: Dict[str, Any], limit: int = 200) -> str:
    """Instructional prose attached to a lesson entry, in field order."""
    chunks: List[str] = []
    for key in entry:
        base = _TRACK_SUFFIX.sub("", str(key).casefold())
        if base in _CLAIM_FIELDS or base in ("context", "translation", "usage"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                chunks.append(value.strip())
    return " ".join(chunks)[:limit]


def _entry_term(entry: Dict[str, Any]) -> str:
    for key in ("term", "word", "target", "expression", "phrase"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _page_entries(page: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for container in ("items", "vocabulary", "words", "rules", "comparisons", "dialogue", "lines"):
        for entry in page.get(container) or []:
            if isinstance(entry, dict):
                out.append(entry)
    return out


def _claim_evidence(page: Dict[str, Any], limit: int = 6, exclude: str = "") -> List[str]:
    """Same-page evidence including the instructional prose attached to each entry.

    ``_sibling_examples`` deliberately carries term + IPA + example, which is what
    the stress-generalization detector needs. A register claim is contradicted by
    *prose* ("usable in both formal and informal settings"), so that prose has to
    survive into the payload or the verifier cannot see the contradiction the
    lesson already contains.
    """
    skip = _fold_for_identity(exclude) if exclude else ""
    out: List[str] = []
    for entry in _page_entries(page):
        term = _entry_term(entry)
        phon = str(entry.get("phonetic") or "").strip()
        example = str(entry.get("example") or "").strip()
        prose = _entry_prose(entry, limit=160)
        snippet = " ".join(x for x in (term, phon, example, prose) if x)
        # A claim is not evidence for itself; echoing it back only costs payload.
        if not snippet or (skip and skip in _fold_for_identity(snippet)):
            continue
        out.append(snippet[:240])
        if len(out) >= limit:
            break
    return out


def collect_scope_contradictions(
    data: Any, material_language: str = "tr", limit: int = 8
) -> List[Dict[str, Any]]:
    """Absolute claims that nearby lesson content materially weakens.

    The general form of section 4b, with no dependency on phonetics: a claim
    states categorically that expression X is the one to use in some context, and
    a sibling entry on the same page presents a *different* expression together
    with prose that explicitly admits an alternative ("both formal and informal",
    "can also be used"), in a context the two visibly share.

    All three conditions are required, which is what keeps this conservative:

      * absolute wording in the claim (section 4's detector);
      * a competing target-language term that the claim does not itself name;
      * an alternative-admitting marker in that term's prose, plus evidence that
        the two really address one context - a shared cue token, or both sides
        describing a social-register context (see _contradicting_alternatives).

    Returns claim/evidence records for the existing bounded verifier. It never
    rewrites anything: whether the alternative genuinely defeats the claim is a
    semantic judgement this layer does not make.
    """
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        return []
    lesson_terms = _collect_lesson_expressions(data)
    found: List[Dict[str, Any]] = []
    for p_index, page in enumerate(data["pages"]):
        if not isinstance(page, dict):
            continue
        entries = _page_entries(page)
        for container in ("rules", "comparisons"):
            for e_index, entry in enumerate(page.get(container) or []):
                if not isinstance(entry, dict):
                    continue
                for key in _claim_bearing_fields(entry):
                    text = entry.get(key)
                    if not isinstance(text, str) or not text.strip():
                        continue
                    code = _track_language(key, material_language)
                    matches = find_absolute_claims(text, code)
                    if not matches:
                        continue
                    claim_cues = _context_cues(text, code)
                    if not claim_cues:
                        continue
                    named = {_fold_for_identity(t) for t in _named_terms_in_text(text, lesson_terms)}
                    if not named:
                        continue
                    claim_domain = classify_claim_domain(text, code)
                    evidence = _contradicting_alternatives(
                        entries, named, claim_cues, claim_domain == "social", code
                    )
                    if not evidence:
                        continue
                    found.append({
                        "path": f"pages.{p_index}.{container}.{e_index}.{key}",
                        "text": text[:600],
                        "quantifiers": sorted(set(matches)) + [_CONTRADICTION_FLAG],
                        "examples": evidence,
                        "domain": claim_domain or "unknown",
                    })
                    if len(found) >= limit:
                        return found
    return found


_CONTRADICTION_FLAG = "nearby-alternative-contradicts-claim"


def _context_cues(text: Any, code: Any) -> set:
    """Domain cues of either kind, used as a proxy for 'the context this is about'."""
    lang = instructional_code(code)
    return set(_domain_cue_hits(text, lang, "social")) | set(_domain_cue_hits(text, lang, "structural"))


def _contradicting_alternatives(
    entries: List[Dict[str, Any]], named: set, claim_cues: set, claim_is_social: bool, code: Any
) -> List[str]:
    """Sibling entries presenting a competing term as an admitted alternative.

    The alternative must sit in a context the claim itself invoked. A shared cue
    token is the strong form of that test; two social-register contexts is the
    weak form, admitted because near-synonymous context words ("for teachers" and
    "in formal settings") describe one situation without sharing a token.
    """
    lang = instructional_code(code)
    markers = _ALTERNATIVE_MARKERS.get(lang or "", ())
    if not markers:
        return []
    out: List[str] = []
    for entry in entries:
        term = _entry_term(entry)
        if not term or _fold_for_identity(term) in named:
            continue
        prose = _entry_prose(entry, limit=240)
        if not prose:
            continue
        folded = prose.casefold()
        if not any(marker in folded for marker in markers):
            continue
        shares_cue = bool(claim_cues & _context_cues(prose, code))
        both_social = claim_is_social and bool(_domain_cue_hits(prose, lang, "social"))
        if not (shares_cue or both_social):
            continue
        out.append(f"{term}: {prose}"[:240])
        if len(out) >= 3:
            break
    return out


# ── 4d. Bounded-review request construction ─────────────────────────────────

_DOMAIN_GUIDANCE = (
    "Each item carries a `domain`:\n"
    "  structural - orthography, spelling, morphology, syntax or phonology. Absolute wording is "
    "normal and often correct here. KEEP it absolute when the rule really is categorical within "
    "its stated scope; a true spelling prohibition, an invariant form or a categorical agreement "
    "rule must NOT be weakened merely for containing always/never.\n"
    "  social - register, politeness, cultural convention or pedagogical recommendation. These are "
    "contextual norms, not linguistic laws. Publish them as exceptionless only if the convention "
    "really admits no acceptable alternative for a learner at this level; otherwise rescope to "
    "wording such as 'usually', 'as a standard choice', 'in most formal contexts', 'a safe choice "
    "at this level' - in the SAME instructional language. Do not convert the claim into vague "
    "hedging: keep it concrete and directive, only accurate about its scope.\n"
    "  unknown - judge on the merits; when genuinely unsure prefer rescope over keep.\n"
    "A flag of `nearby-alternative-contradicts-claim` means the lesson itself shows another "
    "acceptable option in the same context; treat the claim as overscoped unless the evidence "
    "plainly does not apply.\n"
    "Evidence-relationship flags report a conflict inside the lesson's own material. Resolve the "
    "conflict; do not merely soften wording:\n"
    "  phrase-ipa-covers-only-part-of-term / ipa-identical-to-a-different-shorter-term - the "
    "transcription does not describe the whole headword. Supply the transcription for the ENTIRE "
    "term. If you are not confident of the full transcription, return the field with no "
    "transcription rather than an invented one; never pad it to look complete.\n"
    "  prose-transcription-conflicts-with-authoritative-ipa - the prose shows a transcription that "
    "disagrees with the one the lesson publishes for that term. Make the prose agree with the "
    "published transcription, or state the point without a transcription.\n"
    "  parallel-rule-states-narrower-coverage-than-a-sibling-rule - a sibling rule covers cases "
    "this one omits. Add the missing case to this rule when it genuinely applies, or narrow this "
    "rule's stated scope so it no longer implies it covers them.\n"
    "  instructional-tracks-disagree-on-polarity / -on-a-numeral - the English and Turkish "
    "renderings state different things. Correct the field so both tracks express the same "
    "proposition; change only the field you are given.\n"
    "  answer-key-rationale-makes-a-publishable-claim - this is answer-key prose, held to the same "
    "standard as lesson prose. Apply the domain rules above to it.\n"
)


def normalize_claim_record(claim: Dict[str, Any]) -> Dict[str, Any]:
    """Fill in the repair contract a claim does not state for itself.

    Every reviewable record must say three separable things: what the reviewer
    READS (`text`), what may be WRITTEN back and at which path (`field_value` at
    `path`), and HOW it may be repaired (`repair`). For ordinary prose these
    coincide and the defaults apply. For a risk about a non-prose field - a
    transcription, say - they do not, and leaving them implicit meant a correct
    repair was size-checked against the wrong string and dropped.

    repair:
      rescope  - prose; rewrite in place, keeping meaning and instructional language
      omit_ok  - a field that is better absent than wrong (an unconfirmable
                 transcription); the reviewer may clear it instead of guessing
    """
    record = dict(claim)
    record.setdefault("field_value", record.get("text") or "")
    record.setdefault("repair", "rescope")
    record.setdefault("domain", "unknown")
    record.setdefault("quantifiers", [])
    record.setdefault("examples", [])
    return record


def build_claim_review_request(claims: List[Dict[str, Any]], language: Any, level: Any) -> Tuple[str, List[Dict[str, Any]]]:
    """Build the (system prompt, payload) pair for the ONE bounded claim review.

    Lives here, next to the detectors that decide what gets reviewed, so the
    metadata the detectors attach and the instructions the reviewer receives
    cannot drift apart. This adds no model call: it only shapes the existing one.
    """
    records = [normalize_claim_record(c) for c in claims]
    payload = [
        {
            "id": i,
            "claim": c["text"],
            "replace_this": c["field_value"],
            "repair": c["repair"],
            "domain": c["domain"],
            "flag": c["quantifiers"],
            "same_lesson_evidence": c["examples"],
        }
        for i, c in enumerate(records)
    ]
    system = (
        f"You verify the scope of teaching claims in {language} material at CEFR {level}.\n"
        "Each item is a generalization: stated in absolute terms (always/never/mandatory/without "
        "exception, or the equivalent in the instructional language), or hedged toward "
        "near-universality while naming one or more members as the exception.\n"
        + _DOMAIN_GUIDANCE +
        "For each item decide ONE of:\n"
        '  keep    - the claim is genuinely accurate as stated, in the stated scope\n'
        '  rescope - the claim is a tendency, a contextual norm, or has real exceptions the wording '
        "does not allow for: rewrite it in the SAME instructional language with accurate scope, "
        "keeping every correct fact and every example reference intact\n"
        '  correct - the claim contradicts the supplied same-lesson evidence: rewrite it minimally '
        "so it is true. If the evidence shows a member behaving like the named exception(s) that the "
        "claim does not name, prefer naming that member alongside the existing exception(s) over "
        "silently dropping the discrepancy, when doing so fits naturally; otherwise soften the "
        "claim's exception framing so it no longer implies completeness.\n"
        "Rules: never add new rules, vocabulary, examples or facts beyond what the evidence already "
        "names; never change the instructional language; never lengthen a claim by more than about "
        "30 percent.\n"
        "`claim` is what you read; `replace_this` is the exact text that will be overwritten by your "
        "`value`. They are the same for prose, and different when the risk is about a data field: "
        "there, `claim` shows the field together with the headword it belongs to for context, and "
        "`value` must be ONLY the replacement for `replace_this` - never the headword, never both.\n"
        "When `repair` is `omit_ok`, the field is better empty than wrong. If you cannot supply a "
        "confident, complete value, answer `omit` and the field is dropped. Never pad it to look "
        "complete, and never guess a transcription.\n"
        'Return ONLY: {"verdicts":[{"id":0,"action":"keep|rescope|correct|omit","value":"replacement for replace_this, or null"}]}'
    )
    return system, payload


# Hard ceiling on what one review may carry. The bounded call has a fixed token
# budget, so an unusually defective lesson must not be allowed to grow the request
# until the response truncates. Detectors run in descending order of mechanical
# certainty, so the claims that survive the cap are the best-evidenced ones.
MAX_REVIEWABLE_CLAIMS = 16


def collect_reviewable_claims(data: Any, material_language: str = "tr") -> List[Dict[str, Any]]:
    """Every claim the deterministic layer wants the bounded verifier to look at.

    One list, one downstream model call, hard-capped at MAX_REVIEWABLE_CLAIMS.
    Ordering is stable and de-duplicated by path so a claim caught by several
    detectors is reviewed once, carrying every reason and all of its evidence.
    """
    claims = collect_unscoped_absolute_claims(data, material_language=material_language)
    by_path = {c["path"]: c for c in claims}

    def _evidence_risks(payload: Any, material_language: str = "tr") -> List[Dict[str, Any]]:
        # Imported lazily so publication_invariants stays importable on its own and
        # an evidence-layer problem can never break claim-scope review.
        from services.publication_evidence import collect_evidence_risks
        return collect_evidence_risks(payload, material_language=material_language)

    for collect in (collect_generalization_contradictions, collect_scope_contradictions, _evidence_risks):
        try:
            extra = collect(data, material_language=material_language)
        except Exception:
            # A detector failing must never cost the lesson its other review signals.
            continue
        for claim in extra:
            existing = by_path.get(claim["path"])
            if existing is None:
                claims.append(claim)
                by_path[claim["path"]] = claim
                continue
            # Same claim, second reason. Merge the reason and the targeted evidence
            # instead of dropping them: which detector ran first is an accident, and
            # the contradiction evidence is the most informative part of the payload.
            merged_flags = list(existing.get("quantifiers") or [])
            for flag in claim.get("quantifiers") or []:
                if flag not in merged_flags:
                    merged_flags.append(flag)
            existing["quantifiers"] = merged_flags
            evidence = list(claim.get("examples") or [])
            for item in existing.get("examples") or []:
                if item not in evidence:
                    evidence.append(item)
            existing["examples"] = evidence[:8]
            if existing.get("domain") in (None, "unknown"):
                existing["domain"] = claim.get("domain") or existing.get("domain")
    return claims[:MAX_REVIEWABLE_CLAIMS]


# ── Assessment publication boundary ─────────────────────────────────────────

def apply_assessment_invariants(questions: Any, language: Any = None, material_language: str = "tr") -> Any:
    """Deterministic publication discipline for independently generated assessments.

    Assessments never passed through any publication boundary: `generate_full_lesson`
    had one, and the quiz path simply did not, which is why answer-key rationales
    could publish categorical social claims that lesson prose could no longer. The
    rationale is instructional text a learner reads and believes, so it is held to
    the same standard here.

    Strictly deterministic and strictly bounded - NO model call is made on this
    path. A standalone quiz has no lesson-wide evidence to reason against and no
    existing bounded review to join, so adding a semantic call here would be a new
    per-quiz cost. Instead this applies exactly the transformations that are safe
    without semantic judgement:

      * character-level sanitation, so the answer key cannot ship a corrupted
        text layer;
      * hedging of absolute wording in rationales the generator itself marked as a
        tendency - the same self-consistency rule lesson prose obeys;
      * structural validity, dropping only items that fail MCQ validation.

    Rationales embedded in lesson pages are a different case: those DO reach the
    bounded reviewer, through collect_rationale_claims, at no extra call.
    """
    if not isinstance(questions, list):
        return questions
    try:
        from services.material_quality_guard import safe_unicode_normalize, validate_mcq
    except Exception:
        safe_unicode_normalize = None  # type: ignore[assignment]
        validate_mcq = None  # type: ignore[assignment]

    out: List[Any] = []
    for question in questions:
        if not isinstance(question, dict):
            out.append(question)
            continue
        item = dict(question)

        scope = str(item.get("scope") or "").strip().casefold()
        for key in list(item):
            value = item.get(key)
            if not isinstance(value, str) or not value.strip():
                continue
            if safe_unicode_normalize is not None:
                value = safe_unicode_normalize(value, language)
            base = _TRACK_SUFFIX.sub("", str(key).casefold())
            if base in _RATIONALE_FIELDS and scope in _TENDENCY_SCOPES:
                value = hedge_absolute_claims(value, _track_language(key, material_language))
            item[key] = value

        if validate_mcq is not None and (item.get("options") or item.get("choices")):
            try:
                ok, _reason = validate_mcq(item)
            except Exception:
                ok = True
            if not ok:
                continue
        out.append(item)
    return out


_RATIONALE_FIELDS = ("explanation", "rationale", "why", "feedback", "answer_explanation")


# ── Orchestrator ────────────────────────────────────────────────────────────

def apply_publication_invariants(
    data: Any,
    language: Optional[str] = None,
    material_language: str = "tr",
    topic: str = "",
    copy: bool = True,
) -> Any:
    """Apply every deterministic publication invariant. Idempotent and content-safe."""
    if not isinstance(data, dict):
        return data
    out = deepcopy(data) if copy else data
    out = prune_invalid_mcq_pages(out)
    out = collapse_adjacent_duplicates(out)
    out = apply_declared_scope(out, material_language=material_language)
    out = flag_generic_filler(out, topic=topic)
    out = apply_text_layer_integrity(out, language=language)
    return out


def apply_text_layer_integrity(data: Any, language: Optional[str] = None) -> Any:
    """Normalize characters in every string the lesson will publish.

    This belongs to the publication boundary rather than to generation. Character
    sanitation used to run only as a generation-time step, so anything that
    reached persistence by another route - material generated before the rule
    existed, content written by a different path, an imported or edited lesson -
    rendered with its original bytes intact. The renderer already re-applies the
    publication invariants for exactly that reason (see
    pdf_renderer_v12._publication_invariants); text integrity was the one
    invariant missing from that set, which is how noncharacter separators kept
    surviving into the PDF text layer.

    It is pure character normalization: it authors nothing, changes no structure,
    and is idempotent, so applying it at both generation and render is safe.
    """
    if not isinstance(data, dict):
        return data
    try:
        from services.material_quality_guard import safe_unicode_normalize
    except Exception:
        return data

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            for key, value in node.items():
                node[key] = walk(value)
            return node
        if isinstance(node, list):
            for index, value in enumerate(node):
                node[index] = walk(value)
            return node
        if isinstance(node, str) and node:
            try:
                return safe_unicode_normalize(node, language)
            except Exception:
                return node
        return node

    try:
        return walk(data)
    except Exception:
        return data


# ── Path addressing (used by the bounded claim verifier) ────────────────────

def set_by_path(data: Any, path: str, value: Any) -> bool:
    """Set an existing dotted path such as ``pages.0.rules.1.explanation_tr``.

    Only assigns to a field that already exists, so a verifier can repair wording
    but can never introduce new structure, pages or fields.
    """
    if not isinstance(path, str) or not path.strip():
        return False
    node: Any = data
    parts = [p for p in path.split(".") if p != ""]
    if not parts:
        return False
    for part in parts[:-1]:
        if isinstance(node, list):
            if not part.isdigit() or int(part) >= len(node):
                return False
            node = node[int(part)]
        elif isinstance(node, dict):
            if part not in node:
                return False
            node = node[part]
        else:
            return False
    last = parts[-1]
    if isinstance(node, dict) and last in node:
        node[last] = value
        return True
    if isinstance(node, list) and last.isdigit() and int(last) < len(node):
        node[int(last)] = value
        return True
    return False
