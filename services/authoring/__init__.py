"""Authoring: everything that writes or judges AulaAI teaching material.

    schema.py     what every field IS — its role, its language, its repertoire
    prompts.py    what we ask the model for, for 15 languages across A1-C2
    blueprint.py  the course plan, so "teach before you use" is checkable
    transport.py  the one way this package talks to a model
    engine.py     ask, repair, audit, and decide whether to ask again
    audit.py      everything provably wrong, without asking a model
    repair.py     the subset that can be fixed without an opinion
    budget.py     the cost ceiling, enforced rather than hoped for
    publish.py    the boundary every reader crosses to obtain content

    legacy_text.py  QUARANTINE — render-time repair of pre-rebuild material

The dependency order is that list, top to bottom: `schema` knows nothing about
the others, `publish` may use anything above it, and nothing imports upwards.
That is what lets each module be tested on its own, which the system this
replaced could not be — its guards both detected and destroyed, so the only way
to test one was to run the whole pipeline and look at the output.

Two rules keep it that way.

**Every check dispatches on a declared field role.** A validator is never handed
a bare string. The defect that prompted the rebuild — a Spanish lesson
publishing the pronunciation of *cena* as [ˈθενα], with Greek letters where IPA
wants e, n and a — was unfindable by a guard that did not know a phonetic field
from a Spanish sentence from a Turkish explanation, and no number of additional
patterns would have made it findable.

**Detection and repair are separate.** `audit.py` returns findings and changes
nothing. `repair.py` fixes what is provably safe — an opening ¿ that Spanish
requires, a Greek ε that can only have meant ɛ — and refuses what would be a
guess, such as a Greek α that could be either `a` or `ɑ`. What survives repair
with blocking findings is regenerated once, with those findings quoted back to
the model, which is the mechanism that replaced a second paid review call.
"""
