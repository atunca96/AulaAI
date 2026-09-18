#!/usr/bin/env python3
"""The bounded convergence contract, proved as a matrix rather than per incident.

Every production failure so far was a different defect meeting the same
orchestration bug: a hand-rolled chain in which one blocker class had no
strategy that could express its fix, and the only fallback was re-reviewing the
whole unit and arriving at the same answer at full price.

This proves the contract the controller now holds, with provider-free
deterministic fixtures:

    detect the exact blocker
      -> classify it into one of the existing narrow strategies
      -> repair only that class's smallest surface
      -> re-run audit + bilingual completeness + renderer contract
      -> continue until clean, or until a fingerprint repeats (non-progress)

Success is never "a rule was relaxed". It is the authoritative validators
passing again.
"""

from __future__ import annotations
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")

from services.authoring import audit as A  # noqa: E402
from services.authoring import quality_gate as Q  # noqa: E402
from services.authoring import render_contract as RC  # noqa: E402

ORIG_CALL = Q._call_review
FAILURES = []
SCENARIOS = 0


def check(condition, label):
    global SCENARIOS
    SCENARIOS += 1
    print(("  PASS  " if condition else "  FAIL  ") + label)
    if not condition:
        FAILURES.append(label)


class Provider:
    """A scripted provider. Any unscripted stage is a test failure."""

    def __init__(self, responses):
        self.responses = dict(responses)
        self.calls = []

    def __call__(self, **kwargs):
        stage = kwargs["stage"]
        self.calls.append(stage)
        for prefix, value in self.responses.items():
            if stage.startswith(prefix):
                return value(kwargs) if callable(value) else value
        raise AssertionError(f"unscripted model call: {stage}")


def run(topic, responses, *, language="Spanish", level="A1", track="tr"):
    provider = Provider(responses)
    try:
        Q._call_review = provider
        applied = Q.converge_topic(
            topic=topic, language=language, level=level, track=track,
            budget=Q.ReviewBudget(0.22), unit_title="Unit 1",
        )
    finally:
        Q._call_review = ORIG_CALL
    return applied, provider.calls


def spanish_topic(pages, topic_id="t1", title="Topic"):
    return {"id": topic_id, "title": title, "content": {"pages": pages},
            "is_assessment": False}


def clean_pages():
    return [
        {"type": "text", "text": "Adjectives agree.", "text_tr": "Sıfatlar uyum sağlar."},
        {"type": "mcq", "title": "Agreement", "title_tr": "Uyum",
         "prompt": "La mujer es ___. (alto)", "answer": "alta",
         "options": ["alta", "alto", "altos", "altas"],
         "distractors": ["alto", "altos", "altas"],
         "explanation": "The stated noun «mujer» is feminine, so «alta» agrees.",
         "explanation_tr": "Belirtilen «mujer» dişil olduğu için «alta» kullanılır.",
         "why": "Agreement follows the stated noun.",
         "why_tr": "Uyum, belirtilen sözcüğe göre olur."},
    ]


print("\n[1] a real personal-name -> gender rationale is refused")
named = {
    "type": "mcq", "title": "Agreement", "prompt": "Ayşe nasıl biri? ___",
    "answer": "alta", "options": ["alta", "alto", "altos", "altas"],
    "distractors": ["alto", "altos", "altas"],
    "explanation_en": "The stated noun is feminine.",
    "explanation_tr": "Ayşe kadın ismidir, bu yüzden sıfat dişil olur.",
}
check(RC.hidden_world_reason(named) == RC.NAME_GENDER_REASON,
      "Turkish 'Ayşe kadın ismidir' (agglutinated) is refused")
english_named = dict(named, prompt="Ana es ___. (alto)",
                     explanation_en="Ana is a feminine name, so «alta».",
                     explanation_tr="Belirtilen sözcük dişildir.")
check(RC.hidden_world_reason(english_named) == RC.NAME_GENDER_REASON,
      "English 'Ana is a feminine name' is refused")
unnamed_claim = dict(named, prompt="Ana es ___. (alto)",
                     explanation_en="The name is feminine, so «alta».",
                     explanation_tr="Belirtilen sözcük dişildir.")
check(RC.hidden_world_reason(unnamed_claim) == RC.NAME_GENDER_REASON,
      "'the name is feminine' on an item that names a person is refused")


print("\n[2] Turkish grammatical-noun terminology is safe")
for label, tr in (
    ("«mujer» dişil bir isim olduğu için", "«mujer» dişil bir isim olduğu için «alta» kullanılır."),
    ("Soruda geçen isim dişildir", "Soruda geçen isim dişildir; sıfat «alta» olur."),
    ("«hombre» eril bir isimdir", "«hombre» eril bir isimdir; sıfat «alto» olur."),
):
    page = dict(clean_pages()[1], explanation_tr=tr)
    check(RC.page_is_renderable(page, True)[0] and RC.page_is_renderable(page, False)[0],
          f"accepted: {label}")
noun_en = dict(clean_pages()[1], explanation_en="The noun is feminine, so «alta» agrees.")
check(RC.page_is_renderable(noun_en, True)[0] and RC.page_is_renderable(noun_en, False)[0],
      "accepted: English 'the noun is feminine'")


print("\n[3] a Spanish page converges through the atomic name/gender repair")
topic = spanish_topic([
    clean_pages()[0],
    {"type": "mcq", "title": "Agreement", "title_tr": "Uyum",
     "prompt": "Ana es ___. (alto)", "answer": "alta",
     "options": ["alta", "alto", "altos", "altas"],
     "distractors": ["alto", "altos", "altas"],
     "explanation": "Ana is a feminine name, so «alta».",
     "explanation_tr": "Ana kadın ismidir; bu yüzden «alta».",
     "why": "Agreement.", "why_tr": "Uyum."},
], title="Adjective Agreement and Physical Description")
before_page = copy.deepcopy(topic["content"]["pages"][1])
applied, calls = run(topic, {
    "review_render_name_gender:": {
        "stem": "La mujer es ___. (alto)",
        "explanation_en": "The stated noun «mujer» is feminine, so «alta» agrees.",
        "explanation_tr": "Belirtilen «mujer» dişil bir isim olduğu için «alta».",
        "reason": "Ask from the stated noun.",
    },
})
page = topic["content"]["pages"][1]
check(applied == 1 and len(calls) == 1, f"one bounded page-scoped call ({calls})")
check(page["answer"] == before_page["answer"]
      and page["options"] == before_page["options"]
      and page["distractors"] == before_page["distractors"],
      "answer, options and distractors unchanged")
check("Ana" not in page["prompt"] and "Ana" not in page["explanation_tr"],
      "the personal name is gone from stem and rationale")
check(RC.page_is_renderable(page, True)[0] and RC.page_is_renderable(page, False)[0],
      "renderer contract passes for TR and EN")
check(Q._topic_render_blockers(topic["content"]) == []
      and not A.blocking(Q._audit_topic(topic, language="Spanish", track="tr")),
      "topic is clean under audit and renderer contract")


print("\n[4] a malformed patch path does not kill the valid patches beside it")
victim = spanish_topic([{
    "type": "vocabulary", "title": "Numbers", "title_tr": "Sayılar",
    "items": [{"term": "veinte", "example": "Tengo veinte años."},
              {"term": "treinta", "example": "Hay treinta sillas."}],
}])
applied = Q._apply_patches({"t1": victim}, [
    {"topic_id": "t1", "path": ["pages", ",", "items", "5", "example"],
     "old": "Tengo veinte años.", "value": "x", "reason": "malformed"},
    {"topic_id": "t1", "path": ["pages", ",", "items", "5", "example"],
     "old": "Tengo veinte años.", "value": "x", "reason": "malformed again"},
    {"topic_id": "t1", "path": ["pages", "0", "items", "1", "example"],
     "old": "Hay treinta sillas.", "value": "Hay treinta sillas en el aula.",
     "reason": "valid"},
])
items = victim["content"]["pages"][0]["items"]
check(applied == 1 and items[1]["example"] == "Hay treinta sillas en el aula.",
      "the valid patch in the same batch is applied")
check(items[0]["example"] == "Tengo veinte años." and len(items) == 2,
      "the malformed path writes nothing and invents nothing")


print("\n[5] a duplicate option + distractor shortfall converges to a clean audit")
mcq = {"type": "mcq", "title": "Negation", "title_tr": "Olumsuzluk",
       "prompt": "¿Cómo se niega «Hablo francés»?", "answer": "No hablo francés.",
       "options": ["No hablo francés.", "No hablo francés.", "Hablo francés.",
                   "Hablas francés."],
       "why": "Negation uses «no».", "why_tr": "Olumsuzluk «no» ile kurulur."}
topic = spanish_topic([mcq], title="Simple Negation")
start = A.summarise(A.blocking(Q._audit_topic(topic, language="Spanish", track="tr")))
check(start.get("duplicate_options") == 1 and start.get("distractor_count") == 1,
      f"both structural blockers present at the start ({start})")
applied, calls = run(topic, {
    "review_mcq_option_set:": {
        "answer": "No hablo francés.",
        "options": ["No hablo francés.", "Hablo francés.", "Hablas francés.",
                    "Habláis francés."],
        "distractors": ["Hablo francés.", "Hablas francés.", "Habláis francés."],
        "reason": "Replace the repeated key.",
    },
})
page = topic["content"]["pages"][0]
identities = {A.option_identity(o) for o in page["options"]}
check(len(page["options"]) == 4 and len(identities) == 4
      and A.option_identity(page["answer"]) in identities,
      "four learner-distinct options with the key among them")
check(not A.blocking(Q._audit_topic(topic, language="Spanish", track="tr")),
      "the deterministic audit is clean")


print("\n[6] see scripts/test_bilingual_preflight_checkpoint.py")
# The full DB-backed proof — repair, checkpoint, unrelated later failure, and a
# persisted snapshot that still carries the counterpart — lives there because it
# needs a real SQLite fixture. Here we hold the controller's half of it: a
# missing counterpart is dispatched to the exact bilingual strategy.
topic = spanish_topic([
    {"type": "text", "text": "A nationality names a country.", "text_tr": "Milliyet bir ülkeyi adlandırır."},
    {"type": "text", "text": "Some forms are invariable."},
])
applied, calls = run(topic, {
    "review_bilingual_exact:": lambda kw: (
        {"value": "Bazı biçimler değişmezdir.", "reason": "counterpart"}
        if kw["payload"]["path"] == ["pages", 1, "text_tr"]
        and kw["payload"]["source_value"] == "Some forms are invariable."
        else (_ for _ in ()).throw(AssertionError(kw["payload"]))
    ),
})
check(applied == 1 and Q.missing_bilingual_pairs(topic["content"]) == [],
      "the missing counterpart is filled from its own source field")
check(topic["content"]["pages"][1]["text"] == "Some forms are invariable.",
      "the source field is evidence, never overwritten")


print("\n[7] the same blocker on the same content is not repaired twice")
topic = spanish_topic([dict(clean_pages()[1],
                            prompt="Ana es ___. (alto)",
                            explanation="Ana is a feminine name, so «alta».",
                            explanation_tr="Ana kadın ismidir; bu yüzden «alta».")],
                      title="Stuck")
noop = {"stem": "Ana es ___. (alto)",
        "explanation_en": "Ana is a feminine name, so «alta».",
        "explanation_tr": "Ana kadın ismidir; bu yüzden «alta».",
        "reason": "unchanged"}
provider = Provider({"review_render_name_gender:": noop})
raised = None
try:
    Q._call_review = provider
    Q.converge_topic(topic=topic, language="Spanish", level="A1", track="tr",
                     budget=Q.ReviewBudget(0.22), unit_title="Unit 1")
except Q.QualityGateError as exc:
    raised = exc
finally:
    Q._call_review = ORIG_CALL
check(raised is not None, f"a non-progressing repair fails closed ({str(raised)[:60]})")
check(len(provider.calls) == 1,
      f"the same strategy is not called again for the same fingerprint "
      f"({provider.calls})")
check("still refused" in str(raised) and "tr export" in str(raised),
      "the strategy proves its own output and names the locale that refused it")

# And the controller's own non-progress path: a strategy that changes nothing
# and does not raise. The same fingerprint is never dispatched twice, and the
# diagnostic names the unresolved blocker and the strategies that were tried.
orig_audit = Q._audit_topic
stuck_finding = A.Finding("unresolvable_defect", A.BLOCK, path="",
                          field="no_such_field", detail="cannot be located")
provider = Provider({})
raised = None
try:
    Q._audit_topic = lambda *a, **k: [stuck_finding]
    Q._call_review = provider
    Q.converge_topic(topic=spanish_topic(clean_pages(), title="NoProgress"),
                     language="Spanish", level="A1", track="tr",
                     budget=Q.ReviewBudget(0.22), unit_title="Unit 1")
except Q.QualityGateError as exc:
    raised = exc
finally:
    Q._audit_topic = orig_audit
    Q._call_review = ORIG_CALL
check(raised is not None and "not converging" in str(raised)
      and "unresolvable_defect" in str(raised),
      f"a no-op strategy ends in an exact diagnostic ({str(raised)[:70]})")
check(provider.calls == [],
      f"and the strategy that cannot express it is attempted once, not looped "
      f"({provider.calls})")


print("\n[8] a repair that turns one blocker into another repairable one converges")
# Repairing the option set leaves a stem the renderer then refuses; the
# controller dispatches the NEW class rather than reporting the old one.
topic2 = spanish_topic([{
    "type": "mcq", "title": "Agreement", "title_tr": "Uyum",
    "prompt": "Ana es ___. (alto)", "answer": "alta",
    "options": ["alta", "alta", "alto", "altos"],
    "explanation": "Ana is a feminine name, so «alta».",
    "explanation_tr": "Ana kadın ismidir; bu yüzden «alta».",
    "why": "Agreement.", "why_tr": "Uyum.",
}], title="Morphing")
applied2, calls2 = run(topic2, {
    "review_mcq_option_set:": {
        "answer": "alta",
        "options": ["alta", "alto", "altos", "altas"],
        "distractors": ["alto", "altos", "altas"],
        "reason": "rebuild",
    },
    "review_render_name_gender:": {
        "stem": "La mujer es ___. (alto)",
        "explanation_en": "The stated noun «mujer» is feminine, so «alta» agrees.",
        "explanation_tr": "Belirtilen «mujer» dişil bir isim olduğu için «alta».",
        "reason": "Ask from the stated noun.",
    },
})
check([c.split(":")[0] for c in calls2] == ["review_mcq_option_set",
                                            "review_render_name_gender"],
      f"both classes dispatched, structural first ({calls2})")
page = topic2["content"]["pages"][0]
check(not A.blocking(Q._audit_topic(topic2, language="Spanish", track="tr"))
      and Q._topic_render_blockers(topic2["content"]) == []
      and Q.missing_bilingual_pairs(topic2["content"]) == [],
      "all three validators pass after convergence")


print("\n[9] a genuinely non-repairable structural invariant still fails closed")
broken = {"id": "x", "title": "Broken", "content": "not an object",
          "is_assessment": False}
provider = Provider({})
raised = None
try:
    Q._call_review = provider
    Q.converge_topic(topic=broken, language="Spanish", level="A1", track="tr",
                     budget=Q.ReviewBudget(0.22), unit_title="Unit 1")
except Q.QualityGateError as exc:
    raised = exc
finally:
    Q._call_review = ORIG_CALL
check(raised is not None and "non-repairable" in str(raised),
      f"unreadable content is refused, never repaired ({str(raised)[:60]})")
check(provider.calls == [], "and it costs no model call")

provider = Provider({})
raised = None
try:
    Q._call_review = provider
    Q.converge_topic(topic={"id": "y", "title": "Empty", "content": 7,
                            "is_assessment": False},
                     language="Spanish", level="A1", track="tr",
                     budget=Q.ReviewBudget(0.22), unit_title="Unit 1")
except Q.QualityGateError as exc:
    raised = exc
finally:
    Q._call_review = ORIG_CALL
check(raised is not None, "a corrupt schema is refused rather than guessed at")


print("\n[10] a clean course is a no-op")
topic = spanish_topic(clean_pages(), title="Clean")
snapshot = copy.deepcopy(topic["content"])
provider = Provider({})
try:
    Q._call_review = provider
    applied = Q.converge_topic(topic=topic, language="Spanish", level="A1",
                              track="tr", budget=Q.ReviewBudget(0.22),
                              unit_title="Unit 1")
finally:
    Q._call_review = ORIG_CALL
check(applied == 0 and provider.calls == [], "no repairs and no model calls")
check(topic["content"] == snapshot, "content is byte-identical afterwards")


print(f"\n=== {len(FAILURES)} failing checks of {SCENARIOS} ===")
for row in FAILURES:
    print("  -", row)
if FAILURES:
    sys.exit(1)
print("[CONVERGENCE] detect -> classify -> minimal repair -> re-prove -> "
      "bounded by fingerprint, fail-closed at the edges")
