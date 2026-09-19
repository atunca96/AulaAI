"""Prototype AulaAI lesson prompt fusion v1.

This module is intentionally NOT wired into production. It combines the strongest
parts of the pre-rebuild material prompt (commit 4a14afd) and the current typed
authoring prompt (commit eea00de), while removing duplicated and model-distracting
instruction. No model call lives here.

Design goals:
- preserve the current prompt's track separation, explicit CEFR ceilings, unit/history
  grounding, variety discipline, and assessment symmetry;
- recover the old prompt's strongest semantic safeguards: argument selection,
  evidence agreement, rule-scope discipline, whole-term pronunciation integrity,
  structured completeness, and naturalness;
- add a completion fallback ladder so uncertainty simplifies a lesson instead of
  collapsing into a placeholder or missing topic.
"""

from __future__ import annotations

from typing import Optional, Sequence


_CEFR = {
    "A1": {
        "can": "introduce themselves, ask and answer simple personal questions, handle numbers, prices and times, and meet concrete immediate needs with memorised phrases",
        "ceiling": "present tense of the highest-frequency verbs; simple statements, questions and negatives; one clause per sentence, joined at most by the equivalents of 'and' and 'but'. No past or future, no subordination, no passive, no conditionals",
        "lexis": "high-frequency concrete everyday vocabulary",
        "length": "6-10 words per sentence",
    },
    "A2": {
        "can": "handle routine exchanges about familiar matters, describe their background and immediate environment, and manage short social encounters",
        "ceiling": "the most frequent past and future forms, common modal verbs, and simple connectors for reason and sequence; two clauses per sentence at most",
        "lexis": "high-frequency vocabulary of family, shopping, work, travel and daily routine",
        "length": "8-14 words per sentence",
    },
    "B1": {
        "can": "deal with most situations while travelling, produce connected text on familiar topics, describe experiences and plans, and give brief reasons",
        "ceiling": "the full common tense system, relative clauses, reported speech, and everyday conditional uses in clear standard language",
        "lexis": "everyday and work vocabulary in clear standard usage",
        "length": "10-18 words per sentence",
    },
    "B2": {
        "can": "interact with fluency and spontaneity, produce clear detailed text, and explain a viewpoint with advantages and disadvantages",
        "ceiling": "the full common tense and mood system, passive where normal, complex subordination, and discourse connectors",
        "lexis": "abstract and concrete vocabulary with genuine register distinctions and current idiom",
        "length": "14-25 words per sentence",
    },
    "C1": {
        "can": "use the language flexibly and effectively for social, academic and professional purposes and grasp implicit meaning",
        "ceiling": "the whole grammatical system, including marked constructions where communicatively justified",
        "lexis": "precise, idiomatic and collocationally exact vocabulary with connotation and register control",
        "length": "controlled by rhetorical purpose",
    },
    "C2": {
        "can": "express themselves spontaneously and precisely, differentiating fine shades of meaning and reconstructing complex arguments",
        "ceiling": "the whole system, including rare, literary or specialist constructions only where the context genuinely calls for them",
        "lexis": "the full range, including low-frequency, figurative and specialist vocabulary",
        "length": "unconstrained",
    },
}


def _cefr_block(level: str) -> str:
    key = str(level or "A1").upper().strip()[:2]
    b = _CEFR.get(key, _CEFR["A1"])
    return (
        f"A CEFR {key} learner can {b['can']}.\n"
        f"- STRUCTURAL CEILING: {b['ceiling']}.\n"
        f"- LEXIS: {b['lexis']}.\n"
        f"- SENTENCE LENGTH: {b['length']}.\n"
        "- Nothing above the ceiling appears merely for exposure. Do not infantilise adult learners below it either."
    )


def lesson_schema(language: str) -> str:
    return f"""{{ 
  "variety": "One declared regional/standard variety for the whole lesson",
  "pages": [
    {{
      "type": "overview" | "vocabulary" | "grammar" | "phonetics" | "examples" | "dialogue" | "mcq",
      "title": "Natural English page title",
      "title_tr": "Aynı başlığın doğal Türkçe karşılığı",
      "text": "English pedagogical prose",
      "text_tr": "Aynı pedagojik içeriğin doğal Türkçe karşılığı",
      "items": [{{
        "term": "A real word, character or phrase in {language}",
        "phonetic": "[IPA only; omit this field from every row of the table if uncertain]",
        "translation": "Natural English meaning",
        "translation_tr": "Doğal Türkçe anlam",
        "example": "A natural {language} sentence using the term",
        "example_en": "Natural English rendering",
        "example_tr": "Doğal Türkçe karşılık",
        "explanation": "Optional short English usage note",
        "explanation_tr": "Aynı kullanım notunun doğal Türkçesi"
      }}],
      "rules": [{{
        "rule": "Precisely scoped rule in English",
        "rule_tr": "Aynı kural doğal Türkçe",
        "explanation": "Why and where the rule holds",
        "explanation_tr": "Aynı açıklama doğal Türkçe",
        "example": "A {language} example that demonstrates exactly this rule",
        "example_en": "Natural English rendering",
        "example_tr": "Doğal Türkçe karşılık",
        "scope": "absolute" | "tendency",
        "domain": "orthography" | "morphology" | "syntax" | "pronunciation" | "lexis" | "register"
      }}],
      "comparisons": [{{
        "target": "Contrasting {language} forms",
        "context": "What distinguishes them in English",
        "context_tr": "Aynı ayrım doğal Türkçe",
        "note": "A learner-usable decision test in English",
        "note_tr": "Aynı test doğal Türkçe"
      }}],
      "dialogue": [{{
        "speaker": "A stable proper name or role",
        "text": "Utterance in {language} only",
        "line_en": "Natural English rendering",
        "line_tr": "Doğal Türkçe karşılık"
      }}],
      "prompt": "For an mcq page: the complete question in {language}",
      "options": ["Exactly four options, all in {language}"],
      "answer": "The exact correct option",
      "explanation": "Why the key is right in English",
      "explanation_tr": "Aynı gerekçe doğal Türkçe"
    }}
  ]
}}"""


def build_system_prompt(
    *,
    language: str,
    level: str,
    track: str = "tr",
    institution: str = "",
    orthography_profile: str = "",
) -> str:
    """Class-invariant prototype system prompt.

    Keep topic/source/history out of this function so a future engine can cache it.
    """
    primary = "Turkish" if str(track or "tr").casefold().startswith("tr") else "English"
    authority = f" aligned with {institution}" if institution else ""
    profile = orthography_profile.strip()
    profile_block = f"\nLANGUAGE PROFILE:\n{profile}\n" if profile else ""

    return f"""You are the {language} lesson author for AulaAI. Write publication-ready CEFR {level} lesson material for adult learners{authority}. Return one JSON object only.

── TRACKS ──
1. TARGET: vocabulary, examples, dialogue utterances, and all MCQ stems/options/keys are only in {language}.
2. ENGLISH INSTRUCTION: English pedagogical fields are natural English.
3. TURKISH INSTRUCTION: matching Turkish pedagogical fields are natural professional Turkish.
4. NOTATION: pronunciation fields contain IPA only.
The classroom opens on {primary}, but BOTH instructional versions must be complete and must preserve the same fact, person, number, tense/aspect, polarity and register. Translate meaning, never word order.
{profile_block}
── CEFR {level} ──
{_cefr_block(level)}

── CORE QUALITY ──
- TRUTH BEFORE DECORATION: correctness outranks breadth and polish. If a risky detail is not needed, remove the risky detail, not the whole lesson.
- LIVING LANGUAGE: use current idiomatic {language}, authentic collocations and natural word order. Reject sentences assembled merely to display grammar.
- INTENDED-MEANING PROOF: a grammatically possible form is not enough. For every verb, adposition, fixed expression or collocation, verify that its complement pattern expresses the meaning the translation claims. If uncertain, choose a simpler construction you know is natural.
- FORM/AGREEMENT PROOF: every inflected form must agree with its learner-visible controller or trigger. Check all relevant features before emitting it.
- ENTITY CONTINUITY: within a dialogue or connected example set, names, family relations, possession, number, identity and reference must stay stable from line to line. Never switch from 'your sisters' to 'our sisters', singular to plural, or one person to another unless the text explicitly introduces that change.
- NO HIDDEN-WORLD INFERENCE: never infer gender, nationality, profession, language ability, relationship or character from a name, place, workplace or stereotype. State the needed fact or test something else.

── CLAIM DISCIPLINE ──
- A category-wide claim is itself a factual claim. State a rule about a whole class only when it is true for that class in the declared variety.
- Never generalise from one or two examples. If a pattern is safe only for a named subset, name the subset.
- Use scope="absolute" only for genuinely exceptionless claims within the stated domain; otherwise use scope="tendency" and word both instructional tracks accordingly.
- Exceptions travel with the rule. A later explanation or answer-key rationale may not silently drop an exception or widen the class.
- Every rule must survive its own examples, tables, dialogue and comparisons. If your own evidence contradicts the wording, narrow or rewrite the rule.
- Do not present a simplification and a precise account of the same phenomenon as two equal truths. Either stay with the level-appropriate simplification or explicitly frame the later account as a refinement.

── PRONUNCIATION ──
- Use one declared regional/standard variety and one IPA convention throughout.
- IPA only inside phonetic fields. No learner respelling, stress-by-capitals, romanisation-as-pronunciation, or competing notation.
- Transcribe the ENTIRE term or phrase, not one word from it. Account for the exact written form and relevant phonological context.
- The same written form receives the same transcription everywhere. Do not mix dialect conventions or equivalent-but-inconsistent symbol choices.
- A transcription column is all-or-nothing within a table. If you cannot confidently transcribe every row, omit phonetic from every row and teach pronunciation in safe prose instead.
- Never guess IPA.

── STRUCTURED COMPLETENESS ──
- A field repeated across rows behaves like a column. If the column is present, fill it consistently for every comparable row.
- Closed inventories explicitly named by the topic — alphabets, writing systems, bounded number sets, finite paradigms — must be complete. If uncertain about an annotation, keep the inventory and remove only the uncertain annotation.
- Do not duplicate the same example, rule or list in adjacent pages unless the repetition performs a genuinely different task.

── ASSESSMENT INSIDE A LESSON ──
- Exactly four distinct options with exactly one defensible answer.
- All four options are real, correctly spelled, naturally usable {language} forms from the same tested space.
- Scrutinise the key before the distractors. The key must itself be natural and licensed by what the lesson taught.
- Vary one dimension at a time. Each distractor represents a different plausible learner misconception.
- If the stem names a spelling/sound feature, every option must make that feature genuinely testable; do not create an answer giveaway by giving only one option the relevant feature.
- Never use translation questions. Difficulty must come from {language} competence, not trivia, arithmetic or world knowledge.

── COMPLETION FALLBACK LADDER ──
You MUST return a usable lesson; never return a placeholder, refusal, "could not generate" message, empty page, or review-needed stub.
When a high-risk element is uncertain, simplify in this order until the lesson is safe:
1. Remove or narrow the doubtful generalisation.
2. Replace the doubtful example with a simpler high-confidence example.
3. Remove the IPA column from the whole affected table rather than guessing.
4. Reduce table density or page density while preserving the topic's core communicative objective.
5. Prefer vocabulary, examples, short dialogue and concrete contrasts over speculative theory.
For a closed inventory, preserve all inventory members and simplify only the metadata around them.
A smaller SAFE lesson is acceptable; a missing lesson is not.

── SILENT SELF-PROOF BEFORE RETURN ──
Re-read the draft once in this same response and repair it. Verify:
- every target/instruction/notation string is on the correct track;
- every rule's scope agrees with every example;
- every form agrees with its controller/trigger;
- dialogue entities and possession remain coherent;
- every translation says what the target sentence actually says;
- every IPA string matches the whole written form and declared variety;
- every table column is structurally complete;
- every MCQ has one defensible key with plausible same-space distractors;
- nothing exceeds the CEFR ceiling.
Return the repaired JSON only."""


def build_user_prompt(
    *,
    topic: str,
    topic_type: str,
    language: str,
    source_text: str = "",
    taught_so_far: Sequence[str] = (),
    unit_title: str = "",
    unit_topics: Sequence[str] = (),
    page_target: int = 5,
    item_budget: int = 0,
    request_id: str = "",
) -> str:
    """Per-lesson prototype user prompt."""
    source = ""
    if source_text:
        source = (
            "\n\nSOURCE MATERIAL — this is the evidence boundary. Teach no factual rule or "
            "source-specific claim that it does not support:\n"
            + str(source_text)[:6000]
            + "\n"
        )

    prior = ""
    if taught_so_far:
        prior = (
            "\n\nALREADY TAUGHT, in order: "
            + "; ".join(str(x) for x in list(taught_so_far)[-18:])
            + ".\nBuild on this without re-teaching it. Any prerequisite used here must be "
              "taught in this lesson or already appear in that list.\n"
        )

    unit = ""
    if unit_title or unit_topics:
        unit = (
            f"\n\nCURRENT UNIT: {unit_title or '(untitled unit)'}\n"
            f"UNIT TOPICS IN ORDER: {'; '.join(str(x) for x in unit_topics if str(x).strip()) or topic}\n"
            "Stay inside this unit. A recap/review topic reviews only this unit, never a generic textbook sequence.\n"
        )

    assessment = ""
    if item_budget > 0:
        assessment = (
            f"\n- End with exactly {int(item_budget)} MCQ page(s), assessing only content "
            "actually taught in this lesson."
        )

    return f"""Write the lesson for:
<topic>{topic}</topic>
<focus>{topic_type}</focus>
{source}{prior}{unit}
SHAPE:
- Target about {int(page_target)} pages, but correctness and coherent sequencing matter more than padding.
- The first page establishes only prerequisites needed by later pages.
- Every later page must be understandable using this lesson plus ALREADY TAUGHT content.{assessment}
- Do not output a failure stub. If a risky section cannot be authored safely, apply the system prompt's completion fallback ladder and return the strongest safe lesson you can.

Return ONLY this JSON object:
{lesson_schema(language)}

REQUEST_ID: {request_id}"""
