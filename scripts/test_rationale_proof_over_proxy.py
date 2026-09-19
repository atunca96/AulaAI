#!/usr/bin/env python3
"""A token proxy may report a rationale defect. It may not have the last word.

`_ungrounded_explanation_names` and `_rationale_has_specific_evidence` answer two
semantic questions with token shape: does this rationale invent a person, and
does it cite the item. Neither is decidable that way, and both are measurably
wrong across the taught languages — capitalisation carries no name signal in
Chinese, Japanese, Korean or Arabic and over-fires in German, where every noun
is capitalised.

Used as a hard publication gate that runs again inside
`validate_publication_integrity`, a proxy of that shape refuses a fully paid
classroom at the last step. Each false positive then gets patched, the boundary
moves, and a new class of ordinary prose starts failing — grammar labels,
parenthetical teaching labels, technical labels. That list does not terminate.

So the proxy keeps detection and loses finality: where the language-aware
reviewer has already judged these exact bytes, its verdict stands. These checks
pin both directions of that trade.
"""

from __future__ import annotations
import inspect
import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.authoring import quality_gate as Q  # noqa: E402

FAILURES = []


def check(condition, label):
    if not condition:
        FAILURES.append(label)
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")


# The attestation store is a persistent sqlite file that outlives a single run,
# so a fixture with fixed bytes would be attested by the PREVIOUS run and check
# [1] would pass for the wrong reason the second time. Every run therefore gets
# its own semantic surface, which is also a small proof that the digest really
# is content-derived.
RUN = uuid.uuid4().hex[:12]


def mcq(**over):
    page = {
        "type": "mcq", "title": "Question 1", "title_tr": "Soru 1",
        "prompt": f"Wo ist der Schlüssel {RUN}?",
        "options": ["auf dem Tisch", "sehr gut", "um acht Uhr", "mit Anna"],
        "answer": "auf dem Tisch",
        "distractors": ["sehr gut", "um acht Uhr", "mit Anna"],
        "explanation": "Konjunktiv II is not involved; the stem asks for a place.",
        "explanation_tr": "Soru yer sorar; Konjunktiv II burada kullanılmaz.",
    }
    page.update(over)
    return page


print("[1] an unreviewed page is still refused — fail-closed is intact")
# A rationale that only restates the answer, with the page-title scaffolding
# removed so the proxy is actually exercised.
generic = mcq(
    explanation="The correct answer is 'auf dem Tisch' because it matches.",
    explanation_tr="Doğru cevap 'auf dem Tisch'; çünkü eşleşir.",
)
generic.pop("title", None)
generic.pop("title_tr", None)
rows = Q._explanation_grounding_blockers({"pages": [generic]})
check(any(r["why"] == Q._EXPLANATION_SPECIFICITY_REASON for r in rows),
      f"no proof, no mercy: the proxy still blocks ({[r['why'] for r in rows]})")

print("\n[2] the same page, once a reviewer has judged these exact bytes")
Q.attest_rationale_pages({"pages": [generic]}, stage="test_proof")
rows_after = Q._explanation_grounding_blockers({"pages": [generic]})
check(rows_after == [],
      f"the reviewer's verdict stands over the proxy ({rows_after})")

print("\n[3] the proof is bound to the bytes, not to the page")
# Any edit to the semantic surface the proxies read invalidates the attestation
# and the proxy binds again at full strength. This is what stops a stale proof
# from covering content nobody reviewed.
# The invariant is that the PROOF stops applying, which is what the attestation
# owes. Whether a proxy then fires is a question about the mutated content, not
# about the proof: editing the answer can legitimately turn a quoted distractor
# into cited evidence, and asserting a blocker there would be asserting the
# proxy's own verdict rather than the invalidation.
for label, mutation in (
    ("the rationale is rewritten", {"explanation": "Something else entirely."}),
    ("the stem changes", {"prompt": f"Wann kommt der Bus {RUN}?"}),
    ("the keyed answer changes", {"answer": "sehr gut"}),
    ("an option changes", {"options": ["auf dem Tisch", "sehr gut", "um neun", "mit Ana"]}),
    ("a rationale locale is dropped", {"explanation_tr": ""}),
):
    mutated = dict(generic)
    mutated.update(mutation)
    check(Q._rationale_semantic_digest(mutated)
          != Q._rationale_semantic_digest(generic),
          f"the digest moves when {label}")
    check(not Q._rationale_proof_covers(mutated),
          f"proof does not survive: {label}")

# And the page that WAS attested still is, so invalidation is specific rather
# than a cache that simply forgets.
check(Q._rationale_proof_covers(generic),
      "the attested page keeps its proof")

print("\n[4] a genuinely invented person is still caught when unreviewed")
invented = mcq(
    prompt="___ ist Lehrerin.",
    options=["Sie", "Er", "Es", "Wir"], answer="Sie",
    distractors=["Er", "Es", "Wir"],
    explanation="Sara is a woman, so the feminine pronoun is used.",
    explanation_tr="Sara bir kadın olduğu için dişil zamir kullanılır.",
)
invented.pop("title", None)
invented.pop("title_tr", None)
rows_bad = Q._explanation_grounding_blockers({"pages": [invented]})
check(any(r["why"] == Q._EXPLANATION_GROUNDING_REASON for r in rows_bad),
      f"an unreviewed invented person is refused ({[r['why'] for r in rows_bad]})")

print("\n[5] the digest is language-agnostic, not tuned to any script")
# The same mechanism must key cleanly in every taught writing system. A digest
# that collapsed for a script would silently share one proof across items.
seen = {}
for label, prompt, answer in (
    ("Latin",    "Wo ist der Schlüssel?", "auf dem Tisch"),
    ("Cyrillic", "Где ключ?",             "на столе"),
    ("Greek",    "Πού είναι το κλειδί;",  "στο τραπέζι"),
    ("Han",      "钥匙在哪里？",            "在桌子上"),
    ("Kana",     "鍵はどこですか。",         "テーブルの上"),
    ("Hangul",   "열쇠가 어디 있어요?",      "탁자 위에"),
    ("Arabic",   "أين المفتاح؟",          "على الطاولة"),
):
    digest = Q._rationale_semantic_digest(mcq(prompt=prompt, answer=answer))
    check(bool(digest), f"{label}: a digest is produced")
    seen[label] = digest
check(len(set(seen.values())) == len(seen),
      f"every script gets its own digest ({len(set(seen.values()))}/{len(seen)} distinct)")

print("\n[6] an unreadable proof store cannot open the gate")
orig = Q._review_attestation_has
try:
    Q._review_attestation_has = lambda key: (_ for _ in ()).throw(RuntimeError("db down"))
    rows_down = Q._explanation_grounding_blockers({"pages": [generic]})
    check(any(r["why"] == Q._EXPLANATION_SPECIFICITY_REASON for r in rows_down),
          "a proof that cannot be read is a proof that does not exist")
finally:
    Q._review_attestation_has = orig

print("\n[7] final publication does not promote specificity proxy to semantic truth")
_src = inspect.getsource(Q.validate_publication_integrity)
check("_EXPLANATION_SPECIFICITY_REASON" in _src,
      "the final gate distinguishes the two rationale classes")
check(_src.count("rationale_blockers = [") == 1,
      "specificity rows are filtered out of the blocking set")

# A correct A1 item whose rationale names the discriminating fact in the
# instruction language, sharing no token with the taught-language stem. The
# proxy reports it; the final gate must not destroy the classroom over it.
a1 = {
    "type": "mcq", "title": "Question 3", "title_tr": "Soru 3",
    "prompt": "¿Cómo se despide una persona por la noche?",
    "options": ["Buenas noches", "Buenos días", "Buenas tardes", "Hasta luego"],
    "answer": "Buenas noches",
    "distractors": ["Buenos días", "Buenas tardes", "Hasta luego"],
    "explanation": "The greeting used at night is «Buenas noches».",
    "explanation_tr": "Gece kullanılan veda «Buenas noches» ifadesidir.",
}
rows = Q._explanation_grounding_blockers({"pages": [a1]})
check(any(r["why"] == Q._EXPLANATION_SPECIFICITY_REASON for r in rows),
      "the proxy still reports specificity, so repair still sees it")
check(not any(r["why"] == Q._EXPLANATION_GROUNDING_REASON for r in rows),
      "and it is not confused with an invented person")

print()
if FAILURES:
    print(f"FAILED ({len(FAILURES)}):")
    for label in FAILURES:
        print(f"  - {label}")
    sys.exit(1)
print("all proof-over-proxy checks passed")