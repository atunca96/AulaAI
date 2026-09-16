"""The English/Turkish teaching pair, as an explicit profile over the proven prompt.

Every other taught language in this product has the same shape: a foreign target,
explained to the learner in Turkish or in English, and the learner chooses which.
English and Turkish break that shape, because for them one of the two
instructional tracks *is* the target language. A Turkish speaker learning English
is not served by an English-medium explanation of English at A1, and an English
speaker learning Turkish is not served by a Turkish-medium one.

The requirement was a dedicated, revised variant of the material-generation
system for this pair rather than a change to the general multilingual pipeline.
Copying two thousand lines would have satisfied the letter of that and made both
copies worse: every material-quality fix after today would have to be made twice,
and the second copy is the one that gets forgotten. So the core prompt stays
exactly as it is — one file, one set of publication invariants, one renderer —
and this module supplies the only two things that genuinely differ:

  * `bilingual_tracks_override` — what "the two tracks" means when one of them is
    the target language, replacing the general section rather than contradicting
    it from a distance;
  * `pair_section` — the contrastive pedagogy that is the actual product value
    here: what a Turkish speaker gets wrong in English, and what an English
    speaker gets wrong in Turkish.

`profile_for(language)` returns None for every other taught language, and the
general path is then byte-for-byte what it was before this module existed. That
is the safety property worth having: the special path cannot silently alter
Spanish.
"""

from typing import Dict, Optional

from services.language_profiles import normalize_language, locked_track


_ENGLISH_TRACKS = """<bilingual_tracks>
This course teaches English, and publishes its instruction in Turkish. Both field families are still generated in the same response, but they are not symmetrical here.

TURKISH TRACK (title_tr, text_tr, explanation_tr, example_tr, rule_tr, analysis_tr, context_tr, note_tr, pitfall_tr) — THIS IS THE PUBLISHED INSTRUCTIONAL TRACK.
- Natural, professional Turkish written for Turkish-speaking learners of English. Every explanation, rule statement, heading, task instruction, gloss and answer rationale the learner reads comes from here, so no piece of teaching may exist only in the English fields.
- Use standard Turkish grammatical terminology (`Belirtme Hâli`, `çoğul`, `sıfat`, `edat`, `yardımcı fiil`); never leak English shorthand such as `pl.`, `sg.`, `adj.` into Turkish fields.
- Turkish phonetic reference points are correct and expected here: this is the one course type where comparing an English sound to the nearest Turkish sound is the right teaching move, not a leak.

ENGLISH TRACK (title, text, explanation, example_en, rule, analysis, context, note, pitfall) — SECONDARY.
- A monolingual English-medium restatement of the same teaching, pitched at CEFR {level}. It must assert exactly what the Turkish track asserts: same proposition, entities, polarity, quantity, role and communicative force.
- It is never the only place a rule, example or rationale appears, and it never carries teaching the Turkish track omits.

TARGET-LANGUAGE MATERIAL: every `term`, `example`, dialogue line, MCQ option and quotation is English, because English is what is being taught.
- When an MCQ tests a contrast IN English, the options ARE the English forms. Do NOT emit `options_tr` for such an item: translating the options deletes the distinction the question asks about. Localise the stem and the explanation instead.
- When an MCQ tests metalinguistic knowledge and the options are explanatory phrases, give both `options` and matching `options_tr`.
</bilingual_tracks>"""


_TURKISH_TRACKS = """<bilingual_tracks>
This course teaches Turkish, and publishes its instruction in English. Both field families are still generated in the same response, but they are not symmetrical here.

ENGLISH TRACK (title, text, explanation, example_en, rule, analysis, context, note, pitfall) — THIS IS THE PUBLISHED INSTRUCTIONAL TRACK.
- Natural English written for English-speaking learners of Turkish. Every explanation, rule statement, heading, task instruction, gloss and answer rationale the learner reads comes from here, so no piece of teaching may exist only in the Turkish fields.
- Use standard English grammatical terminology (accusative, plural, postposition, vowel harmony, agglutination) and standard English abbreviations.
- English phonetic reference points are correct and expected here: comparing a Turkish sound to the nearest English sound is the right teaching move in this course type.

TURKISH TRACK (title_tr, text_tr, explanation_tr, example_tr, rule_tr, analysis_tr, context_tr, note_tr, pitfall_tr) — SECONDARY.
- A monolingual Turkish-medium restatement of the same teaching, pitched at CEFR {level}. It must assert exactly what the English track asserts: same proposition, entities, polarity, quantity, role and communicative force.
- It is never the only place a rule, example or rationale appears.

TARGET-LANGUAGE MATERIAL: every `term`, `example`, dialogue line, MCQ option and quotation is Turkish, because Turkish is what is being taught.
- When an MCQ tests a contrast IN Turkish, the options ARE the Turkish forms. Do NOT emit `options_en`/`options_tr` for such an item; localise the stem and the explanation instead.
- When an MCQ tests metalinguistic knowledge and the options are explanatory phrases, give both `options` and matching `options_tr`.
</bilingual_tracks>"""


_ENGLISH_PAIR = """<taught_pair>
Audience: Turkish-speaking learners of English at CEFR {level}. This is the whole reason the Turkish track is the published one, so teach the contrast rather than ignoring it.
- Anchor explanations in what a Turkish speaker actually finds unfamiliar, when the topic touches it: articles (a / an / the) where Turkish has none; fixed SVO order against Turkish SOV; the absence of grammatical gender against Turkish's absence of it too (a genuine simplification worth saying out loud); prepositions as separate words rather than case suffixes; auxiliary `do` in questions and negatives; present perfect against the Turkish past; the consonants /θ/, /ð/, /w/, /ŋ/; vowel length and the weak /ə/; word stress, which Turkish places differently.
- Name the interference explicitly when it is the point of the lesson ("Türkçede belirli artikel yoktur, bu yüzden..."), and do not manufacture a contrast where the topic does not have one.
- Do not bring a third language into the comparison. English and Turkish are the only two languages this course discusses.
- English examples are contemporary and natural — standard British or American usage, consistently within a lesson. No invented sentences that exist only to display a structure.
</taught_pair>"""


_TURKISH_PAIR = """<taught_pair>
Audience: English-speaking learners of Turkish at CEFR {level}. This is the whole reason the English track is the published one, so teach the contrast rather than ignoring it.
- Anchor explanations in what an English speaker actually finds unfamiliar, when the topic touches it: two-way and four-way vowel harmony; agglutinative suffix order (stem + plural + possessive + case); the case system where English uses prepositions; SOV word order and postpositions (için, ile, gibi); the absence of grammatical gender and of a definite article; consonant mutation (kitap → kitabı) and assimilation; the letters ı/i, ö, ü, ğ, ç, ş, and the ı/i distinction in particular.
- Name the contrast explicitly when it is the point of the lesson ("English marks this with a preposition; Turkish marks it with a case suffix"), and do not manufacture one where the topic does not have one.
- Do not bring a third language into the comparison. Turkish and English are the only two languages this course discusses.
- Turkish examples are contemporary standard Istanbul Turkish, natural for adult learners.
</taught_pair>"""


_PROFILES: Dict[str, Dict[str, str]] = {
    "English": {
        "track": "tr",
        "instruction_language": "Turkish",
        "bilingual_tracks": _ENGLISH_TRACKS,
        "pair_section": _ENGLISH_PAIR,
    },
    "Turkish": {
        "track": "en",
        "instruction_language": "English",
        "bilingual_tracks": _TURKISH_TRACKS,
        "pair_section": _TURKISH_PAIR,
    },
}


def profile_for(language: Optional[str], level: str = "A1") -> Optional[Dict[str, str]]:
    """The special-pair profile for this taught language, or None.

    None means "use the general multilingual path unchanged" — which is what
    every other language gets, and what makes this safe to add.
    """
    canonical = normalize_language(language)
    profile = _PROFILES.get(canonical)
    if not profile:
        return None
    return {
        "language": canonical,
        "track": profile["track"],
        "instruction_language": profile["instruction_language"],
        "bilingual_tracks": profile["bilingual_tracks"].replace("{level}", str(level)),
        "pair_section": profile["pair_section"].replace("{level}", str(level)),
    }


def is_special_pair_course(language: Optional[str]) -> bool:
    return locked_track(language) is not None
