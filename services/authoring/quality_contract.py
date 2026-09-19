"""One semantic quality contract shared by authoring, review and repair.

Keep this block compact. It is injected into cached system prompts, so every rule
here should prevent a learner-visible defect rather than describe style.
"""

QUALITY_CONTRACT_VERSION = "2026-09-19.1"

SHARED_QUALITY_CONTRACT = f"""── AULAAI SHARED QUALITY CONTRACT {QUALITY_CONTRACT_VERSION} ──
- TRUTH BEFORE COVERAGE: never trade correctness for completeness. A smaller
  correct explanation is better than a broad doubtful one.
- SCOPE: a teaching shortcut must not be stated as a universal law. Absolute
  wording is allowed only when the claim is genuinely exceptionless in the
  declared standard/regional variety; otherwise narrow the class or qualify it.
- FORM AND AGREEMENT PROOF: for every inflected form and every keyed assessment
  answer, identify the learner-visible grammatical controller/trigger and verify
  every relevant feature (person, number, grammatical gender, case, definiteness,
  tense/aspect/mood, agreement or analogous language-specific morphology).
  Grammatical gender is not real-world sex; never infer identity features from a
  personal name or stereotype.
- INSTRUCTIONAL LANGUAGE: English and Turkish fields must preserve the same fact,
  person, number, tense/aspect, polarity and register, and each must read as
  natural educational prose when read independently. Translate meaning, not the
  source language's word order or morphology.
- PRONUNCIATION: verify IPA against the exact written form and declared variety,
  including context-sensitive allophony/assimilation where relevant. Use one
  transcription depth and convention consistently; never guess a transcription.
- ASSESSMENT: independently solve the item before trusting its key. Exactly one
  option must be defensible; distractors must be plausible errors from the same
  tested space rather than malformed or obviously irrelevant giveaways.
- PRIORITY: false rule/wrong answer > wrong form/agreement > wrong IPA > material
  overclaim/naturalness > cosmetic style. Never spend correctness work on polish
  while a higher-priority learner-harm defect remains."""

REPAIR_QUALITY_GUARDRAILS = f"""── REPAIR GUARDRAILS {QUALITY_CONTRACT_VERSION} ──
Every replacement must satisfy the same truth, scope, form/agreement, language,
pronunciation and assessment invariants as the shared quality contract. Preserve
all immutable context and CEFR intent. Make the smallest correction that clears
the named defect; never introduce a new learner-visible claim merely to make a
repair easier."""
