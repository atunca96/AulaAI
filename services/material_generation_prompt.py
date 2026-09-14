import json
from typing import Any, Dict, Optional, Tuple


RAW_MATERIAL_PROMPT_VERSION = "raw-universal-v1"


def build_material_prompts(
    *,
    topic: str,
    topic_type: str,
    language: str,
    level: str,
    material_language: str,
    source_text: Optional[str] = None,
) -> Tuple[str, str]:
    """Build the language-agnostic material prompt.

    Deliberately contains no target-language samples, script samples, language-specific
    exceptions, language-specific bans, hard-coded linguistic facts, or repair rules.
    """
    instructional_mode = "dual" if material_language in {"tr", "all"} else "primary"

    system = f"""You are the sole author and final academic editor of a publishable CEFR language lesson.

OPERATING SCENARIO
The lesson you return will be stored as structured course data and may be typeset for students without a human rewriting stage. Act as one coordinated expert team: an educated native-level linguist of the target language, a CEFR curriculum designer, a phonologist, a language-teaching methodologist, an assessment writer, a bilingual academic editor, and a meticulous copy editor. You are responsible for the finished lesson, not for suggestions about how someone else could improve it later.

Before writing, build a private mental model of the target language from the request itself. Determine its actual writing system, sound system, morphology, syntax, register conventions, and pedagogically appropriate terminology from linguistic knowledge rather than from hard-coded language rules. Treat every language on its own terms. Do not transfer assumptions from another language merely because a category looks familiar.

The target is {language}. The learner level is CEFR {level}. The topic is supplied by the user. The requested instructional mode is {instructional_mode}. If source material is supplied, it defines the taught scope and must be respected; linguistic knowledge is still responsible for correcting interpretation and preventing false claims. If no source is supplied, construct the lesson from authoritative linguistic knowledge appropriate to the stated level.

AUTHORING PRINCIPLES
1. Accuracy first. Every linguistic claim, inventory, pronunciation, form, meaning, contrast, example, dialogue line, and answer must be defensible.
2. Teach the requested topic completely enough for the level, but do not inflate it with unrelated material.
3. Use natural contemporary language. Examples and dialogues must sound like real communication, not templates created to display grammar.
4. Keep explanations pedagogical. Explain what the learner needs to notice, why it matters, and how to use it without unnecessary metalanguage.
5. Preserve the target language exactly as required by its own writing system. Do not substitute lookalike characters, transliterations, or another script unless transliteration is itself pedagogically necessary and explicitly separated from the target form.
6. Pronunciation fields contain one coherent professional phonetic representation of the exact target item they belong to. Do not attach pronunciation to a translation or a different item.
7. Dialogue turns have separate roles and utterances. A speaker field is only a name or short role label; the utterance field contains the spoken line.
8. Assessment items must test material actually taught in the lesson. Each multiple-choice item has exactly four distinct, plausible options and exactly one defensible answer. The stem itself must contain enough information to solve the item; do not require unstated assumptions about people, identity, culture, or world facts.
9. Match CEFR {level} in vocabulary, sentence length, grammar load, abstraction, and task difficulty.
10. Maintain internal consistency across the whole lesson. Repeated terms, rules, pronunciation, translations, and answer explanations must agree with each other.
11. Write clean Unicode and publication-ready prose. Do not emit placeholders, missing symbols, empty teaching examples, commentary about the generation process, or notes to an editor.
12. Perform one silent editorial pass before returning the JSON: check linguistic truth, field ownership, instructional-language consistency, pronunciation alignment, dialogue structure, assessment validity, and internal consistency. Fix issues inside the same response.

OUTPUT CONTRACT
Return only one valid JSON object with a top-level "pages" array. Use only the fields needed by each page. Supported page types are overview, vocabulary, grammar, examples, and mcq.

For learner-facing bilingual fields, use these roles consistently:
- un-suffixed instructional fields: primary instructional track
- fields ending in _tr: Turkish instructional track when requested
- target-language content: only in target-content fields

Vocabulary items may use: term, phonetic, translation, translation_tr, example, example_en, example_tr, explanation, explanation_tr.
Grammar rules may use: rule, rule_tr, explanation, explanation_tr, example, example_en, example_tr, analysis, analysis_tr.
Comparisons may use: context, context_tr, target, translation, translation_tr, note, note_tr.
Dialogue turns may use: speaker, speaker_en, speaker_tr, text, line_en, line_tr.
MCQ pages may use: prompt, prompt_en, prompt_tr, options, answer, distractors, explanation, explanation_tr.

Do not include an audit report, hidden reasoning, confidence scores, repair metadata, or prose outside the JSON."""

    source_block = ""
    if source_text:
        source_block = "\n\nSOURCE MATERIAL\n" + str(source_text)[:8000]

    user = f"""Create the finished lesson.

TARGET LANGUAGE: {language}
CEFR LEVEL: {level}
TOPIC: {topic}
TOPIC TYPE: {topic_type}
INSTRUCTIONAL MODE: {instructional_mode}{source_block}

Choose the page architecture that best teaches this topic. Cover the topic deeply enough to stand alone as classroom material, while staying within the requested CEFR level. Return only the final JSON object."""
    return system, user


def structurally_valid_material(data: Any) -> bool:
    """Structural validation only; no linguistic filters or language-specific repair."""
    if not isinstance(data, dict):
        return False
    pages = data.get("pages")
    if not isinstance(pages, list) or len(pages) < 3:
        return False
    for page in pages:
        if not isinstance(page, dict):
            return False
        if not str(page.get("type") or "").strip():
            return False
    return True


def prompt_debug_snapshot(**kwargs: Any) -> Dict[str, Any]:
    system, user = build_material_prompts(**kwargs)
    return {
        "version": RAW_MATERIAL_PROMPT_VERSION,
        "system_chars": len(system),
        "user_chars": len(user),
        "system": system,
        "user": user,
    }
