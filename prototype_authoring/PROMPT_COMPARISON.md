# AulaAI prompt fusion v1 — comparison notes

This is a design note only. Nothing in this directory is connected to production.

## Compared revisions

| Side | Revision | Prompt source |
| --- | --- | --- |
| Pre-rebuild / legacy | `4a14afd880943f286c41fdbdc9fa85db27768f0c` | `services/material_generation_prompt.py` |
| Current typed authoring | `eea00de6875fa3018ab41ed791ba2c42b31bc3a4` | `services/authoring/prompts.py` + `quality_contract.py` |

The legacy prompt is approximately 38k characters in one material-generation module and contains many overlapping quality clauses. The current authoring prompt is structurally cleaner: class-invariant system instructions are separated from per-lesson topic/source/history, with a typed wire schema and shared quality contract.

## Side-by-side assessment

| Dimension | Legacy prompt | Current prompt | Fusion decision |
| --- | --- | --- | --- |
| CEFR control | Broad band guidance, especially strong A1/A2 practicality | Explicit per-band capability, structural ceiling, lexicon and sentence length | **Keep current.** It is more operational and easier for the model to obey. |
| Track separation | Strong bilingual instructions but spread across a very large contract | Four explicit tracks: target, English instruction, Turkish instruction, notation | **Keep current.** Cleaner mental model. |
| Naturalness | Exceptionally detailed; rejects translationese, grammar-display sentences and unnatural collocations | Good but much shorter | **Recover legacy's semantic core**, compressed into living-language + intended-meaning proof. |
| Argument / valency selection | Explicitly distinguishes morphological correctness from correct meaning and complement licensing | Mostly implicit | **Recover.** This prevents grammatically valid but semantically wrong examples. |
| Claim scope | Very detailed absolute/tendency discipline, evidence agreement, "do not generalise one example" | Shared truth/scope contract, but shorter | **Recover the highest-value clauses.** Category-wide claims must be proved or narrowed. |
| Rule/example consistency | Explicit "your own displayed evidence may not refute the rule" and exception propagation | Present in self-check but less forceful | **Recover.** This directly targets broad false rules. |
| Pronunciation | Strong full-term transcription, consistency, no partial columns, no foreign-script contamination | Excellent IPA/Greek-codepoint/variety discipline and all-or-none columns | **Merge both.** Current notation hygiene + legacy whole-term/evidence consistency. |
| Structured completeness | Applies to any repeated table field | Mainly explicit for IPA | **Recover generally.** Any repeated field acts like a column. |
| Dialogue coherence | Natural roles/register stressed, but entity-state continuity not explicit enough | Natural dialogue but no explicit possession/entity invariant | **Add new invariant.** Names, possession, relations and number must remain stable. |
| Assessments | Very rich distractor contract, source grounding, one varying dimension | Cleaner version adds symmetric key scrutiny, shared-trigger test and hidden-world inference ban | **Keep current core**, plus legacy same-space plausibility where it adds signal. |
| Source grounding | Strong source evidence/provenance structures | Source text is an evidence boundary; user prompt carries unit/history context | **Keep current architecture.** Do not re-add provenance fields to every generated rule because they inflate output. |
| Course/unit context | Weak compared with current | Explicit `taught_so_far`, `unit_title`, `unit_topics` | **Keep current.** |
| Prompt size / attention | Very long and repetitive; several rules restate one another | Shorter, cleaner, cacheable | **Do not restore the legacy prompt wholesale.** Only recover rules with direct learner-visible value. |
| Failure behaviour | "Omit what you cannot state confidently" but no explicit safe completion ladder | "Smaller correct lesson beats fuller doubtful one", but raw test still produced placeholder/missing lessons | **Add completion fallback ladder.** Simplify risky parts; never collapse an entire topic into a stub. |

## What the A/B artifacts imply

The old artifact was more complete, but contained more semantic, IPA and deterministic defects. The current raw generator produced materially cleaner lessons when it succeeded, yet the no-review/no-repair run collapsed many topics into placeholders and lost entire unit assessments.

That means the next prototype should not choose between "legacy completeness" and "current correctness". It needs:

1. **Current architecture and explicit constraints** for correctness.
2. **Legacy semantic proof rules** for naturalness, valency, rule scope and evidence agreement.
3. **A new safe-completion strategy** so uncertainty reduces ambition instead of deleting a lesson.

## Fusion principles implemented in `prompt_fusion_v1.py`

### Preserved from current

- class-invariant system prompt / per-request user prompt split;
- explicit CEFR ceilings;
- four-track separation;
- one declared variety;
- IPA-only pronunciation convention;
- unit and already-taught context;
- hidden-world inference prohibition;
- symmetric scrutiny of answer keys and distractors;
- one-varying-dimension MCQs;
- shared-trigger anti-giveaway rule;
- compact wire schema.

### Recovered from legacy

- "grammatical is not enough; intended meaning must be licensed";
- complement/argument-selection checking;
- do not generalise from one example;
- category-wide claim quantification;
- exceptions travel with a rule;
- every rule must survive its own examples and tables;
- whole-term IPA transcription;
- general table-column completeness;
- no silent precision shift between simplified and exact explanations;
- naturalness over forced structural coverage.

### New after the benchmark

**Entity continuity**
A connected dialogue/example set must preserve possession, family relation, number and referent identity unless a change is explicitly introduced. This directly covers errors like switching from "your sisters" to "our sisters" inside the same exchange.

**Completion fallback ladder**
The model is forbidden to emit a placeholder/refusal. When confidence drops, it narrows the rule, replaces the example, removes the IPA column, reduces density, or falls back to concrete vocabulary/examples/dialogue. For closed inventories it keeps the inventory and drops only uncertain metadata.

## Intentionally not restored

- language-specific examples inside the universal rules;
- long lists of near-duplicate prohibitions;
- mandatory source-evidence/provenance fields on every rule;
- extra precision metadata that increases output without directly helping the learner;
- production wiring, review, repair, validation, model calls or deployment changes.

## Status

`prototype_authoring/prompt_fusion_v1.py` is a non-production prompt prototype only. It is not imported anywhere and cannot generate material by itself. The next step can build a small isolated engine around it without touching the production pipeline.
