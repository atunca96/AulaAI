# Root-cause note: the blocking validators, audited together

Written after `ca87655`, where lesson review stopped on
`The House and Locations / Prepositions of Place / pages[3]`:

```
review_lesson:...Prepositions of Place                 ok=True
review_render_name_gender:...pages.3.prompt            ok=True
-> the repair's own post-write probe:
   name/gender page repair still refused in the tr export
   ... answer depends on gender inferred from a personal name
```

## Which validator is wrong

`render_contract`'s name/gender rule — and the fault is the rule, not the
repair and not the model. Measured on the production page shape before any
change:

```
stem            Ana está ___ la mesa.
options         debajo de / encima de / al lado de / detrás de
name tokens     {ana}
explanation_tr  name_word=True gender_word=True shared_name=[]
explanation     name_word=False gender_word=True shared_name=[]
-> hidden_world_reason: "answer depends on gender inferred from a personal name"
```

The rationale never mentions Ana. It explains the gender of `«mesa»`, which is
why `shared_name` is empty. The rule fired anyway, through its weakest branch:
*a person appears somewhere in the stem* AND *a name-word appears somewhere in
the rationale*. Neither signal is about the answer, and the answer here is a
preposition — no fact about anybody's gender selects among four different
prepositions. The hypothesis in the brief was right: the detector was still
co-occurrence wearing a relation's clothes.

The same audit found three more defects in the same family, all measured, not
assumed:

| # | measured behaviour | direction |
|---|---|---|
| 1 | `Ana está ___ la mesa` + `«mesa» dişil bir isim` | false positive (production) |
| 2 | `Книга большая. Какая форма?` — `Какая` counted as a personal name | false positive |
| 3 | `'Марина' bir kadın ismidir` — the quoted name was discarded as taught vocabulary, so the rule could not see the person it is about | **false negative** |
| 4 | `Ella trabaja en un hospital. ¿Qué significa «hospital»?` — refused by biography→identity although the answer is a translation | false positive |

(3) and the earlier `Ayşe kadın ismidir` miss mean this rule has been letting
real defects through while refusing valid lessons. It was not simply too
strict.

## Why the last few runs failed in different places

They are not one drift. Sorting the series honestly:

**Independent defects, correctly diagnosed and fixed where they were:**

* malformed reviewer patch path — a provider response-shape defect;
* MCQ option/distractor structural mismatch — a real content defect whose
  repair could not express the fix;
* missing EN/TR counterpart + persistence divergence — a checkpoint-ordering
  defect;
* risk-review partial coverage — a response-shape defect the schema cannot
  constrain.

**Symptoms of validator/repair contract drift — one cause, two appearances:**

* the repeated name→gender refusals on `Adjective Agreement`, `A Family
  Photograph`, and now `Prepositions of Place`.

Each of those was patched at the point it surfaced (statement scoping, then a
person-token relation) without the rule ever being given the thing it was
actually missing: a link to the **answer**. That is why the same blocker kept
reappearing on unrelated topics. The convergence controller did its job in
every case — it dispatched the right strategy and refused to loop — but a
controller can only be as correct as its classification, and here the
classification was faithful to a validator that was wrong.

## Is the gate's claim of authority true?

Mostly yes, with one real exception found:

* The render loop's MCQ admission is `render_contract.page_is_renderable`
  (`pdf_renderer_v12.py:1310`) — the same function the gate calls. Single
  source of truth, as designed.
* `_v54_pdf_unsafe_mcq` still exists in the renderer carrying the old lexical
  predicate, but it is dead code — no call site.
* **`_v56_release_cleanup` is a live second drop point.** It runs inside
  `_normalize_content` for Russian courses and silently removes MCQ pages,
  judged by `_v56q_unsafe_mcq` → `_v54_unsafe_mcq`: a private copy of the
  hidden-world rules that has not been updated since. Measured: it drops
  `Вчера Анна весь вечер ______ новую книгу` (genuinely unsafe — correct) and
  also `Каждый вечер я ______ ужин дома` (a conjugation drill — its own
  malformed-distractor rule, not a hidden-world call).

## The invariant, stated

> A hidden-world blocker fires only when the risky inference is present **and**
> that inference could change which option is correct.

Per blocker, after the audit:

| blocker | risky inference | can it decide the answer? |
|---|---|---|
| name → gender | a statement ties a gender claim to a person the item names | options are a form paradigm, **or** two options are gender values, **or** the statement names the keyed answer |
| biography → identity | stem states a biographical fact, rationale derives an identity one | the question is not a gloss of a word the stem itself quotes |
| workplace → profession | both signals already in the stem | already answer-anchored — unchanged |
| trait → absolute frequency | trait in the stem, frequency read from the **options** | already answer-anchored — unchanged |

Everything in the second column is computed from the option set, the fields and
what the rationale attributes its claim to. No language, no CEFR level, and no
lexicon was extended: the gender-value check reuses the lists the rule already
had.

## What changed

* `render_contract`: the dependency conjunct above, on name/gender and on
  biography→identity; quoted **proper nouns** are now cited people rather than
  taught vocabulary (fixing defect 3), quoted **common** nouns still exempt
  grammar prose (fixing defect 2).
* `legacy_text._v56q_unsafe_mcq`: its hidden-world half now delegates to
  `render_contract.hidden_world_reason` instead of keeping a private copy. Its
  two own rules — a malformed option string, a rationale that admits one of its
  own distractors is not a word — are untouched; they are not modelled
  elsewhere and removing them would have loosened the gate.
* `quality_gate`: the name/gender class now lists `render_stem` as a bounded
  fallback after the atomic page repair. Removing the person from the stem
  clears the blocker too, so this is a second real route rather than a dead
  end. Fingerprint/non-progress logic and the ban on whole-unit retries are
  unchanged.

The repair strategy itself was audited and left alone: when the blocker is
genuine it keeps `answer`/`options`/`distractors` immutable, rewrites the stem
and both rationales together, and is accepted only when
`RC.page_is_renderable` passes for both export locales. Nothing was rewritten to
satisfy a regex; the detector simply stops raising the blocker when there is
nothing to repair.

## Known limits, stated rather than hidden

* A gender cue present only in the **taught** language (`Ana es una mujer`) is
  not recognised as explicit evidence — that needs a per-language lexicon. Such
  an item is still refused **when its rationale reasons from the name**, which
  is a genuine defect in the rationale; if the rationale cites the supplied
  evidence instead, it is admitted. Both cases are in the regression.
* `personal_name_tokens` still treats any capitalised, non-lexical, non-quoted
  stem token as a possible person. That is deliberate over-collection: the
  dependency conjunct is what keeps it from producing refusals, and defect 2 is
  covered by a control.
* `_v56_release_cleanup`'s two remaining rules drop pages at render time
  without the gate modelling them. Russian-only and pre-existing; not touched
  here because modelling them is a separate change and removing them would
  loosen publication.
