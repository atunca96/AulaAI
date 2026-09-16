"""Canonical AulaAI question-generation contract.

One place defines what a question must be. Quizzes, in-class activities and
assignments all generate through `ai_generate_questions`, so they all read this
file; changing an assessment rule means changing it here, once.

Why this file exists
--------------------
The prompt this replaces had grown to ~47k characters of system message plus
~20k of user message — about 17k tokens of instruction on every single
generation call, before any lesson content was attached. It was not 17k tokens
of distinct instruction. The same requirements were stated three to six times:
the lexical-valency mandate appeared in system sections 6, 7, 10 and 13 and
again in user mandates 1, 5, 7, 11 and 12; the Gate A / Gate B block was printed
verbatim in both messages; "scenario transfer only" appeared seven times. That
is an artefact of hardening question quality by appending, over many passes,
before the real quality bottleneck (the source material) was understood.

Repetition of that kind does not make a rule more binding. It does make every
call slower to prefill and more expensive, and it buries the rules that matter
among restatements of the rules that already worked.

Two structural properties are deliberate here:

1. **The system prompt is class-invariant.** It interpolates the target
   language, the CEFR level and the instructional track — all fixed for a
   course — and nothing else. Topic, question count, source material, rolling
   history and sub-batch focus live in the user message. That makes the system
   prompt a byte-identical prefix across every generation in a class, which is
   what lets `_call_ai(..., cache_system=True)` actually cache it. The previous
   prompt interpolated the topic title and the batch size into the system
   message, so no two calls in a class shared a prefix and nothing could ever be
   cached.

2. **Each rule is stated once, in the place it applies.** Nothing below is a
   restatement of anything above it.
"""

from typing import Any, Dict, List, Optional

__all__ = [
    "build_system_prompt",
    "build_user_prompt",
    "build_topup_prompt",
    "output_token_budget",
    "overproduction_count",
    "JSON_SCHEMA_BLOCK",
]


JSON_SCHEMA_BLOCK = """{
  "data": [
    {
      "type": "mcq",
      "module": "Integer MODULE number this question is drawn from, when the source is a multi-module review syllabus; omit otherwise",
      "material_section": "Concise section pointer, e.g. 'Part 2: Core Lexicon'",
      "evidence": "Concise source reference: the sentence, rule, example or vocabulary item. Not reasoning.",
      "cognitive_task": "situational_decision | dialogue_comprehension | sentence_application | grammatical_discrimination | communicative_collocation",
      "prompt": "Authentic question, 100% in {language}",
      "translation_en": "English translation of the prompt",
      "translation_tr": "Türkçe çevirisi",
      "answer": "Correct answer in {language}",
      "distractors": ["Distractor 1 in {language}", "Distractor 2 in {language}", "Distractor 3 in {language}"],
      "why": "One short sentence, max 15 words",
      "why_tr": "Tek kısa cümle, en fazla 15 kelime"
    }
  ]
}"""


def _same_language_track(language: str) -> Optional[str]:
    """'en'/'tr' when the target language IS one of the translation tracks."""
    name = str(language or "").strip().casefold()
    if name in ("english", "ingilizce"):
        return "en"
    if name in ("turkish", "türkçe", "turkce"):
        return "tr"
    return None


def build_system_prompt(
    *,
    language: str,
    level: str,
    cefr_guidance: str = "",
    pedagogy_guidance: str = "",
) -> str:
    """The class-invariant half of the contract. Cacheable; keep it that way.

    Never interpolate anything that varies between topics, batches or sub-batch
    focus directives into this string — that silently destroys the shared prefix
    and with it the cache discount on every call in the class.
    """
    same_track = _same_language_track(language)
    track_note = ""
    if same_track == "en":
        track_note = (
            "\n- This course teaches English, so 'translation_en' is the prompt itself: "
            "repeat the prompt verbatim there rather than paraphrasing it."
        )
    elif same_track == "tr":
        track_note = (
            "\n- This course teaches Turkish, so 'translation_tr' is the prompt itself: "
            "repeat the prompt verbatim there rather than paraphrasing it."
        )

    return f"""You are the {language} Pedagogic Assessment Engine. You write examiner-grade multiple-choice items for CEFR {level} learners from lesson material supplied with each request. Output is a single JSON object and nothing else.
{cefr_guidance}
{pedagogy_guidance}

── 1. LANGUAGE OF THE ITEM ──
- 'prompt', 'answer' and every distractor are 100% in {language}. No English or Turkish carrier text anywhere in them — frame the scenario, the instruction and the question itself in authentic {language}.
- 'translation_en' and 'translation_tr' translate the prompt; 'why'/'why_tr' explain the key in one sentence of at most 15 words.
- BLANK PRESERVATION: if the prompt contains a blank, both translations keep it as '_____'. Never let a translation reveal the answer word.
  WRONG: prompt "... Le devuelvo _____ euros." -> translation_en "... I return thirty euros to you."
  RIGHT: prompt "... Le devuelvo _____ euros." -> translation_en "... I return _____ euros to you."{track_note}

── 2. GROUNDING: THE MATERIAL IS THE ONLY SOURCE OF OBJECTIVES ──
- Every item assesses vocabulary, grammar, relationships, examples or communicative functions the supplied material explicitly teaches or demonstrates. Never require external facts, unstated assumptions, general world knowledge or invented lesson content.
- Grounding is judged on the COMPLETE LINGUISTIC COMBINATION, not on word co-occurrence. A phrase is not source-supported merely because its individual words appear somewhere in the lesson; the whole head–argument, valency, case/preposition and collocational relationship must be licensed by source-backed usage or by authentic living usage. Synthesising an unattested combination out of words that happen to co-occur is a failure.
- SCENARIO TRANSFER ONLY. Items may place taught language in fresh, realistic, CEFR-{level}-appropriate contexts; they need not be verbatim recall. But "fresh context" means only the EXTERNAL frame — speaker identity, setting, communicative goal, surrounding situation, task format. It never means altering the INTERNAL structure of a taught target: its head–argument relation, valency, complement type, required preposition or case, modifier attachment and selectional restrictions are preserved exactly as demonstrated, unless the source itself attests another compatible pattern. Never substitute a new subject, object, complement or modifier to increase novelty.
- If the source gives too little evidence to form a natural new combination, do not invent one. Reuse the source-backed expression in a genuinely different scenario, pick another source-supported target, or ask a natural semantic/functional question instead.
- Reject items that mainly measure common sense or category matching (where a doctor works; what you do when hungry; obvious consequences of a delay).

── 3. WHAT COUNTS AS EVIDENCE FOR WHAT ──
- '[RULE]' and '[CONTRAST]' entries carrying concrete source evidence are the primary and authoritative source for grammar, inflection, syntactic-function and definitional items.
- Vocabulary items, example sentences, passages and dialogue are lexical and contextual evidence ONLY. Never promote an incidental form, dialogue line, suffix, register effect or pragmatic inference into a taught rule. Dialogue lines are illustrations, never testing targets.
- If a topic carries no explicit source-supported rule or contrast, do not force a grammar item from it — ask a supported lexical, comprehension, contextual or communicative-usage question.
- SURFACE-INDEPENDENT META-LINGUISTIC GROUNDING: this holds however the question is worded — "what is X", "what does X indicate", "what is the function of X", "what condition must hold", "which attitude does X express". If the exact property, function, condition, attitude or definition is not explicitly supported by '[RULE]'/'[CONTRAST]' with source evidence, do not synthesise a general definition from pretraining; convert the item into contextual recognition or application instead.
- FORM vs. CONTEXT: when anything attributes a meaning or function to a form — a morpheme, suffix, case marker, connector, construction — verify the form itself contributes that property. Meaning supplied by the lexical root, the surrounding words, the discourse situation, speaker attitude, register or rhetorical outcome does not belong to the form. If the complete expression carries the meaning but the form alone does not, ask about the complete expression, or drop the candidate. Where the material teaches an idiom, fixed expression, collocation or discourse marker, test the whole expression in context rather than decomposing it into morphemes.
- Keep core linguistic meaning and syntactic function separate from optional contextual, rhetorical and pragmatic effects, in items and in explanations alike. No explanation may be broader than the source supports.

── 4. THE FOUR OPTIONS ──
- Exactly one correct answer and exactly three distinct distractors. Always four options.
- SYMMETRIC SCRUTINY: the keyed answer is examined exactly as hard as the distractors, and first. Before it can be checked for uniqueness it must itself be natural, idiomatic, grammatically well-formed and combinatorially licensed by source-backed usage in {language}. An item is not acceptable merely because the key is distinguishable.
- EVERY option must be a real, correctly formed, naturally usable word, phrase or construction in {language}. Never invent, distort, misspell, mechanically mutate or glue together morphology to manufacture a wrong option. A distractor is wrong because of meaning, pragmatic fit, register or a subtle collocational mismatch with the scenario — never because it is gibberish, an impossible inflection or an unnatural phrase in isolation.
- Validate fixed expressions, collocations and idioms according to {language} itself, never through translation from another language: check which person, object, case, complement, preposition or collocate the expression actually takes, and never attach it to an unnatural object just because the sentence stays interpretable.
- HOMOGENEITY: all four options share the same grammatical type, semantic domain, linguistic level and functional category. Never make the key obvious by mixing registers or categories (a casual remark among formal institutional phrasings; an abstract stance among concrete actions).
- COMPETITIVENESS: at least two distractors are plausible near-misses from the same grammatical or semantic category — a real alternative inflection, a correct tense in the wrong person, a genuine near-synonym that fails the collocational frame, a true statement from elsewhere in the text that misattributes. Zero throwaways that a learner eliminates at a glance. Distractors need not appear verbatim in the source; real CEFR-appropriate learner traps are welcome.
- Reject vocabulary that sounds elevated or formal but is semantically misselected in context. Superficial formality is not precision.
- LENGTH SYMMETRY: the four options stay within ±25% of one another in length. The key is never the longest or most explanatory.
- No two options may be semantically equivalent, and no distractor may be defensible as a second correct answer.

── 5. EXACTLY ONE DEFENSIBLE ANSWER ──
- The scenario supplies every fact needed to answer. Never leave a premise unexplained and expect the learner to guess.
- The stem and the keyed answer test exactly the same concept. For connectives and discourse markers, verify the actual logical relation between the clauses (contrast, consequence, addition, concession, cause, condition) matches the function being tested.
- ZERO INFERENCE LEAPS: what the key asserts must be directly verifiable from what the scenario explicitly states. Do not infer unstated consequences, durations, costs or outcomes from a stated event. Do not over-narrow a general policy to one sub-case, over-generalise one unavailable service to its whole category, or label a vaguely mentioned alternative with a specific sub-category. Never present a conditional or discretionary remedy as a guaranteed entitlement, and never invent locations, facilities or procedural constraints the text does not mention.
- Respect the roles and statuses the scenario states: a transfer point is not a destination, a customer is not staff, a delay is not a cancellation.
- Resolve every ambiguity during generation. Do not emit an item and hope it reads as unique.

── 6. CEFR {level} CALIBRATION ──
- Every prompt and all four options sit inside the CEFR {level} band — neither above it nor childishly below it.
- At B1 specifically: clear standard everyday language. No dense infrastructure jargon, official dispatch terminology, hyper-complex compound nouns or corporate tariff law. Focus on what the speaker does and understands in ordinary public situations.
- All wording is natural, contemporary, living {language} as native speakers, institutions and professionals actually use it: authentic functional collocations for the domain, native cadence, ordinary spoken forms for times and daily routines. No archaisms, no translationese, no word-for-word calques, no stiff test-maker jargon.
- STRICT CONFIDENCE THRESHOLD: if you are not fully confident a phrase you composed is idiomatic and well-formed in {language}, drop that candidate rather than approximating it.

── 7. WHAT NOT TO ASK ──
- The prompt never contains the answer or a stem of it.
- No meta-orthographic trivia: letter names, "which word has a written accent", "which letter is silent", "which word ends in Y". Such items are shallow and usually have several correct answers. Test spelling and accents inside communicative sentences where exactly one option is spelled correctly and the rest are typical learner errors. For phonetics topics, test pronunciation in real words or minimal pairs.
- No transparent cognates as the target: the answer must not be trivially recoverable from English or Turkish.
- No shallow translation drills ("what does X mean", "how do you say X"), no circular definitions that define a word with its own root, no trivial one-word collocation blanks that simply delete the obvious verb.
- No meta-paraphrase ("what did the speaker just say?"). Ask what the person should say or do, or what the information implies.
- No commercial product trivia, brand names, ticket portfolio specifics or invented legal thresholds.
- NO ARITHMETIC OF ANY KIND. This is a language platform. Numbers, prices, times and dates are tested through authentic communicative situations — asking a price, a time, a room number, a date, an age — never as a calculation.

── 8. VARIETY ACROSS A BATCH ──
- Vary the cognitive task and the question format. Never test the same rule or vocabulary category repeatedly through near-identical carrier sentences.
- Distribute items across: (a) pragmatic/situational decision — what is the natural thing to say; (b) functional comprehension — meaning, intent, stated details; (c) contextual sentence application with a blank; (d) linguistic discrimination — which statement is correct and natural; (e) communicative intent and collocation. Only a minority of items in a batch may contain a blank.
- Cover the different PARTS or MODULES of the supplied material rather than mining one section. Do not spend two items on one objective while another section is unrepresented.
- Two items are duplicates when they assess the same target through the same situation, communicative purpose, expression, reasoning path or answer distinction — even when the wording differs. A broader objective may reappear only when the new item genuinely tests a different application, contrast or cognitive operation. Never force novelty at the expense of grounding, level fit or source fidelity.

── 9. BEFORE YOU EMIT ──
Check each candidate against all of the above and discard-and-replace any that fails, rather than emitting it. In particular verify, independently: that no meaning is attributed to a form the form does not carry (§3); that the stem, the key and all three distractors are combinatorially natural in {language} (§2, §4); that exactly one option is defensible (§5); that the level fits (§6); and that the item duplicates nothing else in the batch (§8).

RESPONSE FORMAT: a single JSON object, no prose around it."""


def _forbidden_block(forbidden_prompts: List[str], forbidden_answers: List[str]) -> str:
    if not (forbidden_prompts or forbidden_answers):
        return ""
    answers = ", ".join(f"'{a}'" for a in forbidden_answers[-24:])
    prompts = "\n".join(f"- {p[:110]}" for p in forbidden_prompts[-24:])
    return f"""
ALREADY TESTED (this test and the two retained previous batches) — do not repeat:
- Answers used: [{answers}]
- Stems used:
{prompts}
Avoid the same target retested through essentially the same context and cognitive task. The same broader objective may return only in a genuinely different scenario frame and task.
"""


def _focus_block(focus_directive: Optional[str]) -> str:
    if focus_directive == "focus_grammar":
        return (
            "\nSUB-BATCH FOCUS — GRAMMAR & STRUCTURE: prioritise the explicit '[RULE]' and "
            "'[CONTRAST]' entries in the source. If the source carries none, do NOT reverse-engineer "
            "grammar items; generate supported lexical, communicative, situational or comprehension "
            "items instead.\n"
        )
    if focus_directive == "focus_lexicon":
        return (
            "\nSUB-BATCH FOCUS — LEXICON, IDIOM & PRAGMATICS: concentrate on lexical distinctions, "
            "authentic idioms, professional expressions and situational reactions taught in the "
            "material. Do not drill grammatical suffixes or tense conjugations in this sub-batch.\n"
        )
    return ""


def build_user_prompt(
    *,
    language: str,
    level: str,
    topic_title: str,
    topic_type: str,
    gen_count: int,
    content_str: str,
    variety_focus: str,
    forbidden_prompts: Optional[List[str]] = None,
    forbidden_answers: Optional[List[str]] = None,
    reference_data: str = "",
    focus_directive: Optional[str] = None,
    request_id: str = "",
) -> str:
    """The per-request half: everything that varies between calls."""
    blank_cap = max(2, min(4, round(gen_count * 0.25)))
    return f"""TASK: generate EXACTLY {gen_count} unique {topic_type} questions on '{topic_title}' at CEFR {level}, in {language}.

SOURCE MATERIAL:
{content_str}
{reference_data}{_forbidden_block(forbidden_prompts or [], forbidden_answers or [])}{_focus_block(focus_directive)}
PEDAGOGICAL EMPHASIS FOR THIS BATCH: {variety_focus}

BATCH SHAPE:
- At most {blank_cap} of the {gen_count} items may contain a blank ('_____'). The rest are direct situational, comprehension, discrimination or collocation questions with no blank.
- Spread the {gen_count} items across the different parts/modules of the source above, and across different cognitive tasks.

Return ONLY this JSON object:
{JSON_SCHEMA_BLOCK.replace("{language}", language)}

UNIQUE_REQUEST_ID: {request_id}"""


def build_topup_prompt(
    *,
    language: str,
    level: str,
    topic_title: str,
    topic_type: str,
    shortfall: int,
    content_str: str,
    variety_focus: str,
    rejected_prompts: Optional[List[str]] = None,
    request_id: str = "",
) -> str:
    """Second, smaller request when the first batch did not survive validation.

    It reuses the same cached system prompt, so it costs only its own user
    message plus its (small) output.
    """
    rejected = ""
    if rejected_prompts:
        listed = "\n".join(f"- {p[:110]}" for p in rejected_prompts[-16:])
        rejected = f"\nAlready accepted in this test — do not repeat or paraphrase:\n{listed}\n"
    return f"""TASK: generate EXACTLY {shortfall} further unique {topic_type} questions on '{topic_title}' at CEFR {level}, in {language}. The earlier items in this test were kept; these complete it.

SOURCE MATERIAL:
{content_str}
{rejected}
PEDAGOGICAL EMPHASIS: {variety_focus}
At most 1 of these items may contain a blank ('_____').

Return ONLY this JSON object:
{JSON_SCHEMA_BLOCK.replace("{language}", language)}

UNIQUE_REQUEST_ID: {request_id}"""


# ── Budgets ───────────────────────────────────────────────────────────────────
# These were static and generous: 250 output tokens per requested item against a
# 5000-token ceiling, and 1.5x overproduction with a floor of 14 items whatever
# was asked for. A complete item in the schema above — prompt, two translations,
# answer, three distractors, two rationales, three metadata pointers, plus JSON
# keys — measures out at roughly 170-190 tokens; 250 bought nothing except a
# ceiling high enough to push `_call_ai` into its slowest timeout tier.

TOKENS_PER_ITEM = 200
ENVELOPE_TOKENS = 120


def output_token_budget(gen_count: int, ceiling: int = 6000) -> int:
    """Output ceiling sized from what the batch actually has to write.

    The ceiling is a guard against an absurd request, not the normal case: every
    batch size the product actually issues resolves well below it. Sizing the
    budget also sizes the socket timeout and the retry count in `_call_ai`,
    which read the ceiling as a proxy for how long the answer should take — a
    flat 5000 put a 13-item activity in the same 180-second tier as a full
    lesson.
    """
    return max(900, min(ceiling, int(gen_count) * TOKENS_PER_ITEM + ENVELOPE_TOKENS))


def overproduction_count(count: int) -> int:
    """How many items to ask for so `count` survive deterministic validation.

    Overproduction exists because the validator rejects giveaways, duplicates
    and malformed option sets. It is insurance, not free: every surplus item is
    output tokens and latency. 1.3x with a +3 floor keeps a real margin at every
    batch size the product uses while cutting roughly a fifth of the generated
    text that the old 1.5x/floor-14 rule threw away.
    """
    c = max(1, int(count))
    return max(c + 3, -(-c * 13 // 10), 10)


def estimate_prompt_tokens(*parts: Any) -> int:
    """Cheap deterministic estimate used for telemetry, never for billing."""
    return int(sum(len(str(p)) for p in parts) / 4.0)
