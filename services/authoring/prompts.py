"""What we ask the model for. One file, two jobs, no fragments.

This replaces ~1,100 lines spread over `material_generation_prompt.py`,
`question_contract.py` and four loose `config/*.txt` files that were
concatenated into the system message at run time. Nobody could read the prompt
that was actually sent without running the code, and the fragments had drifted:
one demanded a single pronunciation system while another modelled examples that
used two.

Two structural properties are load-bearing.

**The system half is class-invariant.** It interpolates the taught language, the
CEFR level, the instructional track and the writing-system profile — all fixed
for a course — and nothing else. Topic, source text, batch size and history live
in the user half. That is what makes the prefix byte-identical across every
generation in a class, which is what makes it cacheable, which is most of how
the cost ceiling is met.

**The rules are the auditor's rules, in prose.** `audit.py` and this file
describe the same three tracks — target language, instructional language,
phonetic notation — because they are the same model of what a lesson is. A rule
stated here that nothing can check is a wish; a check with no rule behind it
punishes the model for something it was never told. Where a rule below is
mechanically checkable, the check exists and is named in a comment.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from services.authoring import schema as S

__all__ = [
    "build_lesson_system", "build_lesson_user",
    "build_assessment_system", "build_assessment_user",
    "lesson_schema_block", "assessment_schema_block", "cefr_band",
]


# ── CEFR ──────────────────────────────────────────────────────────────────────
# Six bands, each saying three things the generator actually needs: what the
# learner can do, what structures may therefore appear, and how long a sentence
# may get. "Appropriate to the level" on its own produced A1 lessons containing
# subjunctives and C1 lessons containing colour words.

_CEFR = {
    "A1": dict(
        can="introduce themselves, ask and answer simple personal questions, handle numbers, "
            "prices and times, and meet concrete immediate needs with memorised phrases",
        ceiling="present tense of the highest-frequency verbs; simple statements, questions and "
                "negatives; one clause per sentence, joined at most by the words for 'and' and "
                "'but'. No past or future, no subordination, no passive, no conditionals",
        lexis="the 500 most frequent words, concrete and everyday",
        length="6-10 words per sentence"),
    "A2": dict(
        can="handle routine exchanges about familiar matters, describe their background, "
            "immediate environment and immediate needs, and manage short social encounters",
        ceiling="the most frequent past and future forms; the common modal verbs; simple "
                "connectors for reason and sequence. Two clauses per sentence at most",
        lexis="high-frequency vocabulary of family, shopping, work, travel and daily routine",
        length="8-14 words per sentence"),
    "B1": dict(
        can="deal with most situations that arise while travelling, produce connected text on "
            "familiar topics, describe experiences and plans, and give brief reasons",
        ceiling="the full common tense system; relative clauses; reported speech; the "
                "conditional in its everyday uses. Clear standard language throughout",
        lexis="everyday and work vocabulary in clear standard usage. No administrative, legal "
              "or technical jargon, and no dense compound nouns",
        length="10-18 words per sentence"),
    "B2": dict(
        can="interact with fluency and spontaneity, produce clear detailed text on a range of "
            "subjects, and explain a viewpoint with its advantages and disadvantages",
        ceiling="the full tense and mood system including subjunctive and passive where the "
                "language uses them; complex subordination; discourse connectors",
        lexis="abstract as well as concrete vocabulary; idiom where it is genuinely current; "
              "register distinctions between formal and informal",
        length="14-25 words per sentence"),
    "C1": dict(
        can="use the language flexibly and effectively for social, academic and professional "
            "purposes, and grasp implicit meaning in demanding texts",
        ceiling="the whole grammatical system, including marked and stylistically motivated "
                "word order; cohesion across paragraphs",
        lexis="precise, idiomatic and collocationally exact; connotation and register carry "
              "meaning and must be right",
        length="unconstrained; controlled by rhetorical purpose rather than by a limit"),
    "C2": dict(
        can="express themselves spontaneously and precisely, differentiating finer shades of "
            "meaning, and reconstruct arguments from several sources",
        ceiling="the whole system, including rare and literary constructions where the context "
                "genuinely calls for them",
        lexis="the full range, including low-frequency, figurative and specialist vocabulary; "
              "nuance between near-synonyms is itself the content",
        length="unconstrained"),
}


def cefr_band(level: str) -> dict:
    key = str(level or "A1").strip().upper()[:2]
    return _CEFR.get(key, _CEFR["A1"])


def _level_block(level: str) -> str:
    band = cefr_band(level)
    key = str(level or "A1").strip().upper()[:2]
    return (
        f"A CEFR {key} learner can {band['can']}.\n"
        f"- STRUCTURAL CEILING: {band['ceiling']}.\n"
        f"- LEXIS: {band['lexis']}.\n"
        f"- SENTENCE LENGTH: {band['length']}.\n"
        f"- Nothing above this ceiling appears anywhere — not in an example, not in a dialogue "
        f"line, not in an assessment option, not 'just for exposure'. Nothing childishly below "
        f"it either: these are adults."
    )


# ── Writing system ────────────────────────────────────────────────────────────

def _orthography_block(language: str) -> str:
    profile = S.profile_for_language(language)
    if profile is None:
        return ""
    lines = [
        f"- SCRIPT: write {profile.language} in {' + '.join(profile.scripts)} throughout. "
        f"A single word must never mix a foreign script into it.",
        f"- PUNCTUATION: this language ends a question with '{profile.question_mark}', "
        f"separates with '{profile.comma}' and ends a sentence with '{profile.full_stop}'.",
    ]
    if profile.opens_questions:
        lines.append("- Every question OPENS with '¿' as well as closing with '?'. "
                     "Every exclamation opens with '¡'. Omitting them is a spelling error.")
    if profile.notes:
        lines.append(f"- {profile.notes}.")
    if profile.variety:
        lines.append(
            f"- VARIETY: this course teaches {profile.variety}. Every pronunciation, spelling, "
            f"word choice and grammatical form in this lesson belongs to that one variety. Do "
            f"not mix standards — a table that transcribes ⟨c⟩ one way and names the letter "
            f"another way has taught two different languages on one page.")
    return "\n".join(lines)


def _track_name(track: str) -> str:
    return "Turkish" if str(track or "tr").casefold().startswith("tr") else "English"


def _suffix(track: str) -> str:
    return "_tr" if str(track or "tr").casefold().startswith("tr") else ""


# ── The shared half ──────────────────────────────────────────────────────────
# Both jobs are governed by the same model of what a lesson contains, so the
# passage that explains it is written once and interpolated into both system
# prompts. It stays class-invariant, so both remain cacheable.

def _tracks_block(language: str, track: str) -> str:
    primary = _track_name(track)
    return f"""── CONTENT TRACKS ──
Every learner-facing string belongs to one of four tracks, and they never swap.

1. TARGET — {language} itself: vocabulary items, example sentences, dialogue utterances,
   and the whole of every assessment question (stem, options and key). These are written
   ONLY in {language}.
2. ENGLISH INSTRUCTION — every English pedagogical field: title, text, translation,
   explanation, rule, context, note, line_en, example_en and why.
3. TURKISH INSTRUCTION — the matching Turkish pedagogical fields: title_tr, text_tr,
   translation_tr, explanation_tr, rule_tr, context_tr, note_tr, line_tr, example_tr
   and why_tr.
4. NOTATION — pronunciation. IPA, and nothing but IPA, inside square brackets.

AulaAI stores BOTH instructional versions in the same lesson. The current classroom
opens on {primary}, but that is only the default view; it does not remove the other
language. English and Turkish fields must express the same teaching content naturally,
never by copying one language into both keys. Target-language material stays identical
between the two instructional views."""


def _notation_block() -> str:
    return """── PRONUNCIATION: ONE SYSTEM ──
- IPA only, always inside [ ]. Never a second system alongside it: no 'meh-sah', no
  'GÁ-to', no 'ye-vo', no capitalised syllables to mark stress, no romanisation used as
  a pronunciation aid. IPA marks stress with ˈ and that is the only way you mark it.
- Use the IPA repertoire and only it. The IPA borrows exactly three letters from Greek —
  θ, β and χ — at their Greek codepoints. Every other IPA symbol has its own codepoint:
  it is ɛ and never ε, ɣ and never γ, n and never ν, a and never α. A transcription
  containing an ordinary Greek letter is corrupt and will be rejected.
- A transcription column is all-or-nothing. If any row of a table carries a
  transcription, every row of that table carries one. A blank cell reads to a learner as
  'this one has no sound'.
- Transcribe the same form the same way everywhere in the lesson. If one page says ⟨c⟩
  before e is [θ], no other page may name that letter [ˈse].
- If you are not confident of a transcription, omit the column from that table entirely
  rather than guessing at one row."""


def _honesty_block(language: str) -> str:
    return f"""── WHAT YOU MAY NOT INVENT ──
- Every form you print is a real, current, well-formed {language} form. Never coin a word
  to illustrate a rule, and never print a form you then describe as hypothetical, made-up
  or not a real word. If a rule needs an example the language does not supply, the rule is
  the wrong rule for this lesson — choose another.
- No etymology, no folk history, no cultural generalisation about speakers.
- Claim scope precisely. 'Always', 'never', 'every' and 'only' are allowed when the
  statement is genuinely exceptionless at this level; otherwise say 'usually', 'most', or
  name the condition. A beginner's shortcut stated as a law is a defect, because the
  learner meets the exception next week and stops trusting the material.
- Teach before you use. Every example, dialogue line and assessment item must be
  interpretable with what THIS lesson and its predecessors have taught. If an example
  needs a mechanism you have not taught, either teach the minimum needed or choose a
  different example. Do not smuggle a form in and hope it passes as decoration."""


def _assessment_rules(language: str, level: str) -> str:
    return f"""── ASSESSMENT ITEMS ──
- Exactly four options: one defensible answer and three distinct distractors. The whole
  item — stem, options, key — is in {language}. Reference glosses and answer-key
  explanations are supplied in BOTH English and Turkish instructional fields. Never a
  translation question, at any level: not 'what does X mean', not 'how
  do you say X'. At {level} that is a reason to ask a SIMPLER {language} question, never a
  reason to fall back on translation.
- SYMMETRIC SCRUTINY: examine the key exactly as hard as the distractors, and first. It
  must itself be natural, idiomatic and licensed by the material before you check that it
  is unique.
- ONE VARYING DIMENSION: the four options differ along exactly the dimension the item
  tests and hold everything else constant. Four persons of one verb in one tense — not one
  person of four verbs. An option differing on two dimensions is eliminable on the one you
  were not asking about.
- ONE MISCONCEPTION EACH: name silently, for each distractor, the single wrong belief that
  makes a learner choose it. Three distractors are three different beliefs. Two distractors
  chosen for the same reason make a three-option item wearing four.
- EVERY option is a real, correctly spelled, naturally usable {language} form. A distractor
  is wrong because of meaning, collocation, register or grammar — never because it is
  misspelled, invented or impossible. An option that is the key with an accent knocked off
  is a typo, not a belief: nobody picks it, and it wastes one of only three chances to find
  out what the learner does not know.
- HOMOGENEITY AND LENGTH: all four share a grammatical category, a semantic domain and a
  register, and sit within a quarter of one another in length. The key is never the longest
  or the most carefully qualified option.
- SHARED TRIGGER: if the stem names a letter, sound or spelling feature, every option
  carries that feature. 'Which word has a silent h', answered by *hotel* among *gato*,
  *mesa* and *casa*, is not a question — only one option has an h at all.
- The stem contains every fact needed to answer, never the answer itself, and never an
  inference the text does not state. No arithmetic: this is a language platform, so
  numbers, prices and times are asked communicatively, never calculated."""


# ── Lesson generation ────────────────────────────────────────────────────────

def build_lesson_system(*, language: str, level: str, track: str = "tr",
                        institution: str = "") -> str:
    """The class-invariant half of the lesson contract. Keep it that way.

    Interpolating a topic here would give every lesson in a course a different
    prefix and silently cost the cache discount on every call — which is most of
    the difference between a build that costs 25 cents and one that costs a
    dollar.
    """
    inst = _track_name(track)
    profile = S.profile_for_language(language)
    authority = f" aligned with {institution}" if institution else ""
    return f"""You are the {language} lesson author for AulaAI. You write publication-ready CEFR {level} lesson material for adult learners{authority}, with parallel English and Turkish instructional fields. The classroom opens on {inst} by default, but BOTH instructional versions must be complete. You return one JSON object and nothing else — no prose around it, no markdown fence.

{_tracks_block(language, track)}

── CEFR {level} ──
{_level_block(level)}

── WRITING {language} ──
{_orthography_block(language)}
- Write living, current {language} as its speakers actually use it: authentic collocations,
  natural word order, the forms people really say. No translationese, no calques from
  {inst}, no stiff textbook register that no native speaker would produce.
- If you are not fully confident a phrase you composed is idiomatic and well-formed, drop
  it and write a simpler one you are sure of. A smaller correct lesson beats a fuller
  doubtful one.

{_notation_block()}

{_honesty_block(language)}

{_assessment_rules(language, level)}

── COVERAGE ──
- Teach the topic completely at this level and stop. Depth means accuracy, useful
  examples and clear sequencing — not padding, not repetition, not metalanguage.
- For a closed inventory the topic names — an alphabet, a writing system, a set of
  numbers explicitly requested — give the whole inventory. For everything else, let
  usefulness decide the length.
- Sequence the pages so each one is interpretable using only what came before it.

── BEFORE YOU RETURN ──
Re-read your own draft once, silently, in this same response, and repair it. Verify, one
at a time: every string is on the right track; every transcription is IPA and agrees with
every other transcription of the same form; no table has a half-filled column; no form is
invented; nothing exceeds the CEFR ceiling; every assessment item has exactly one
defensible answer that you re-derived from the stem without looking at the key. Make no
second call, add no audit fields, and return the repaired JSON only."""


def lesson_schema_block(language: str, track: str = "tr") -> str:
    """The stable bilingual lesson wire shape.

    Target-language forms exist once. Instructional prose exists in both English
    and Turkish because the reader and PDF exporter expose both views.
    """
    return f"""{{ 
  "variety": "The regional standard this lesson teaches, stated once",
  "pages": [
    {{
      "type": "overview" | "vocabulary" | "grammar" | "phonetics" | "examples" | "dialogue" | "mcq",
      "title": "Page title in English",
      "title_tr": "Aynı sayfa başlığı doğal Türkçe",
      "text": "Pedagogical prose in English",
      "text_tr": "Aynı pedagojik içerik doğal Türkçe",
      "items": [{{
        "term": "The word, character or phrase in {language}",
        "phonetic": "[IPA only, or omit the field entirely for every row of this table]",
        "translation": "Meaning in English",
        "translation_tr": "Aynı anlam doğal Türkçe",
        "example": "A natural sentence in {language} using the term",
        "example_en": "That sentence rendered naturally in English",
        "example_tr": "Aynı cümlenin doğal Türkçe karşılığı",
        "explanation": "One short usage note in English, only when it adds something",
        "explanation_tr": "Aynı kullanım notu doğal Türkçe"
      }}],
      "rules": [{{
        "rule": "The rule, stated in English",
        "rule_tr": "Aynı kural doğal Türkçe",
        "explanation": "Why it holds and when, in English",
        "explanation_tr": "Aynı açıklama doğal Türkçe",
        "example": "A {language} sentence that demonstrates exactly this rule",
        "example_en": "That sentence in English",
        "example_tr": "Aynı cümle Türkçe",
        "scope": "absolute" | "tendency",
        "domain": "orthography" | "morphology" | "syntax" | "pronunciation" | "lexis" | "register"
      }}],
      "comparisons": [{{
        "target": "The contrasting {language} forms, e.g. 'ser vs estar'",
        "context": "What distinguishes them, in English",
        "context_tr": "Aynı ayrım doğal Türkçe",
        "note": "The decisive test a learner can apply, in English",
        "note_tr": "Aynı test doğal Türkçe"
      }}],
      "dialogue": [{{
        "speaker": "A first name",
        "text": "The utterance, in {language} only",
        "line_en": "That utterance in English",
        "line_tr": "Aynı söz doğal Türkçe"
      }}],
      "prompt": "For an mcq page: the COMPLETE question in {language}",
      "options": ["Four options, all in {language}"],
      "answer": "The correct option, exactly as it appears in options",
      "explanation": "Why that option is right, in English",
      "explanation_tr": "Aynı gerekçe doğal Türkçe"
    }}
  ]
}}"""


def build_lesson_user(*, topic: str, topic_type: str = "vocabulary",
                      source_text: str = "", taught_so_far: Sequence[str] = (),
                      page_target: int = 5, item_budget: int = 0,
                      track: str = "tr", language: str = "", request_id: str = "",
                      unit_title: str = "", unit_topics: Sequence[str] = ()) -> str:
    """The per-request half: everything that varies between lessons."""
    source = ""
    if source_text:
        source = (f"\n\nSOURCE MATERIAL — the only evidence this lesson may teach from. "
                  f"Do not add content it does not support:\n{str(source_text)[:6000]}\n")
    prior = ""
    if taught_so_far:
        listed = "; ".join(str(t) for t in list(taught_so_far)[-18:])
        prior = (f"\n\nALREADY TAUGHT in this course, in order: {listed}.\n"
                 f"Build on it and do not re-teach it. Everything you use must be either "
                 f"taught here or present in that list.\n")
    unit = ""
    if unit_title or unit_topics:
        sibling_text = "; ".join(str(t) for t in unit_topics if str(t).strip())
        unit = (
            f"\n\nCURRENT UNIT: {unit_title or '(untitled unit)'}\n"
            f"UNIT TOPICS, in curriculum order: {sibling_text or topic}.\n"
            "The lesson MUST stay inside this unit. A review/recap topic must review "
            "THIS unit's topics only; never substitute material from another unit or "
            "from a generic textbook sequence.\n"
        )
    assessment = ""
    if item_budget > 0:
        assessment = (f"\n- Close the lesson with exactly {item_budget} 'mcq' page(s) assessing "
                      f"only what this lesson itself taught.")
    return f"""Write the lesson for:
<topic>{topic}</topic>
<focus>{topic_type}</focus>
{source}{prior}{unit}
SHAPE:
- About {page_target} pages, sequenced so each is readable with only what precedes it.{assessment}

Return ONLY this JSON object:
{lesson_schema_block(language, track)}

REQUEST_ID: {request_id}"""


# ── Assessment generation ────────────────────────────────────────────────────

def build_assessment_system(*, language: str, level: str, track: str = "tr") -> str:
    """Class-invariant half of the assessment contract."""
    inst = _track_name(track)
    return f"""You are the {language} assessment author for AulaAI. You write examiner-grade multiple-choice items for CEFR {level} learners from lesson material supplied with each request. The question stays in {language}; its reference gloss and rationale are produced in BOTH English and Turkish. The classroom opens on {inst} by default. You return one JSON object and nothing else.

{_tracks_block(language, track)}

── CEFR {level} ──
{_level_block(level)}

── WRITING {language} ──
{_orthography_block(language)}

{_assessment_rules(language, level)}

── GROUNDING ──
- Every item assesses something the supplied material explicitly teaches or demonstrates.
  Never require outside facts, general world knowledge or invented lesson content.
- Grounding is judged on the whole combination, not on word co-occurrence. A phrase is not
  supported because its individual words appear somewhere; the head-argument relation,
  the government, the case and the collocation must all be licensed by the source or by
  authentic living usage.
- SCENARIO TRANSFER ONLY: you may place a taught form in a fresh realistic situation, but
  'fresh' means the external frame — who is speaking, where, to what end. It never means
  altering the internal structure of the taught target: its complement, its preposition,
  its case, its modifier attachment stay exactly as the material demonstrates them.
- If the material gives too little to build a natural new combination, do not invent one.
  Reuse the supported expression in a different scenario, or assess something else.
- Reject anything that mainly measures common sense: where a doctor works, what you do
  when hungry, the obvious consequence of a delay.

── VARIETY ACROSS A BATCH ──
- Spread the items across the parts of the material, across cognitive tasks — situational
  decision, comprehension, gapped application, discrimination, collocation — and across
  formats. Only a minority may contain a blank.
- Two items are duplicates when they assess the same target through the same situation and
  the same reasoning path, however differently worded.

── BEFORE YOU RETURN ──
Re-solve every item from its stem and options without looking at your own key, then make
the key and the explanation agree with what you derived. Discard and replace any item that
fails a rule above rather than emitting it. Return the JSON only."""


def assessment_schema_block(language: str, track: str = "tr") -> str:
    return f"""{{ 
  "items": [
    {{
      "material_section": "Which part of the material this comes from",
      "evidence": "The sentence, rule or item it rests on — a citation, not reasoning",
      "cognitive_task": "situational_decision | comprehension | gapped_application | discrimination | collocation",
      "prompt": "The complete question, 100% in {language}",
      "translation_en": "A reference gloss of the prompt in English, keeping any _____ blank as a blank",
      "translation_tr": "Aynı soru kökünün doğal Türkçe referans karşılığı; _____ boşluğu boş kalır",
      "answer": "The correct answer in {language}",
      "distractors": ["Three distractors in {language}"],
      "why": "One sentence in English, at most 15 words, saying why the key is right",
      "why_tr": "Aynı gerekçe doğal Türkçe, en fazla 15 kelime"
    }}
  ]
}}"""


def build_assessment_user(*, title: str, content: str, count: int, language: str = "",
                          track: str = "tr", emphasis: str = "",
                          already_asked: Optional[Sequence[str]] = None,
                          request_id: str = "") -> str:
    history = ""
    if already_asked:
        listed = "\n".join(f"- {str(p)[:110]}" for p in list(already_asked)[-20:])
        history = ("\n\nALREADY ASKED — do not repeat these targets through the same "
                   f"situation and task:\n{listed}\n")
    focus = f"\nEMPHASIS FOR THIS BATCH: {emphasis}\n" if emphasis else ""
    blanks = max(1, min(3, round(int(count) * 0.25)))
    return f"""Write EXACTLY {count} items on '{title}'.

MATERIAL — the only evidence you may assess:
{content}
{history}{focus}
SHAPE:
- At most {blanks} of the {count} items may contain a blank ('_____'). The rest are direct
  situational, comprehension, discrimination or collocation questions.
- Spread them across the parts of the material above.

Return ONLY this JSON object:
{assessment_schema_block(language, track)}

REQUEST_ID: {request_id}"""
