#!/usr/bin/env python3
"""Regression: bilingual completeness is proven and checkpointed before review.

Production showed `Countries and Nationalities: incomplete EN/TR field pairs:
pages.5.text_tr` at the publication refusal, and the log chain explains it:

    review_preflight_repair:Countries and Nationalities ok=True
    [QUALITY-GATE] preflight checkpoint persisted 1 deterministic repair patch(es)
    review_lesson:...:Countries and Nationalities ok=True      <- no bilingual retry
    ... later abort on an unrelated renderer blocker in A Family Photograph

Bilingual completeness was a tail check inside review_unit_lessons, so a gap the
broad reviewer happened to fill produced no `review_bilingual_retry` call and
the filled content only reached the database if the ENTIRE gate passed. The
unrelated abort meant the persisted snapshot stayed at preflight level, with
pages.5.text_tr still empty, and the outer validation refused the course over a
gap that had in fact been repaired in memory.

Bilingual completeness is now its own deterministic-detect + exact-repair stage
ahead of broad review, and its proven output is checkpointed before any review
budget is spent on lessons.
"""

from __future__ import annotations
import hashlib
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("OPENROUTER_API_KEY", "fixture-key-never-used")
DATA_DIR = tempfile.mkdtemp(prefix="aulaai-bilingual-")
os.environ["AULAAI_DATA_DIR"] = DATA_DIR

from services import state as _state  # noqa: E402
_state.VERSION_FILE = os.path.join(DATA_DIR, "version.txt")

import database  # noqa: E402
database.DB_PATH = os.path.join(DATA_DIR, "aula.db")
database.init_db()
from database import db_connection  # noqa: E402

from services.authoring import quality_gate as Q  # noqa: E402
from services.authoring import transport as T  # noqa: E402
from services.legacy import pdf_pipeline as P  # noqa: E402

SOURCE = "A nationality describes the country a person belongs to."
COUNTERPART = "Bir milliyet, kişinin ait olduğu ülkeyi tanımlar."


def countries_content():
    """The production shape: page 5 has `text` and no `text_tr` at all."""
    return {
        "pages": [
            {"type": "overview", "text": "Countries and nationalities.",
             "text_tr": "Ülkeler ve milliyetler."},
            {"type": "vocabulary", "title": "Countries", "title_tr": "Ülkeler",
             "items": [{"term": "España", "translation": "Spain",
                        "translation_tr": "İspanya"}]},
            {"type": "text", "text": "Nationalities agree in gender.",
             "text_tr": "Milliyetler cinsiyete göre uyum sağlar."},
            {"type": "text", "text": "Add -o or -a to the stem.",
             "text_tr": "Gövdeye -o veya -a eklenir."},
            {"type": "text", "text": "Some forms are invariable.",
             "text_tr": "Bazı biçimler değişmezdir."},
            # The gap. `text_tr` is not merely empty — the key is absent.
            {"type": "text", "text": SOURCE},
        ]
    }


def family_content():
    return {
        "pages": [
            {"type": "overview", "text": "A family photograph.",
             "text_tr": "Bir aile fotoğrafı."},
        ]
    }


def seed(course_id):
    with db_connection() as db:
        db.execute("DELETE FROM topics WHERE chapter_id IN "
                   "(SELECT id FROM chapters WHERE course_id=?)", (course_id,))
        db.execute("DELETE FROM chapters WHERE course_id=?", (course_id,))
        db.execute("DELETE FROM courses WHERE id=?", (course_id,))
        db.execute("INSERT INTO courses (id,name,language,level,material_language) "
                   "VALUES (?,?,?,?,?)",
                   (course_id, "Spanish A1", "Spanish", "A1", "tr"))
        chapter = f"{course_id}-ch1"
        db.execute("INSERT INTO chapters (id,course_id,number,title,title_tr) "
                   "VALUES (?,?,?,?,?)",
                   (chapter, course_id, 1, "Unit 1: Identity", "Ünite 1: Kimlik"))
        for sort_order, (topic_id, title, content) in enumerate((
            (f"{chapter}-countries", "Countries and Nationalities", countries_content()),
            (f"{chapter}-family", "A Family Photograph", family_content()),
        ), start=1):
            db.execute(
                "INSERT INTO topics (id,chapter_id,type,title,title_tr,content,sort_order) "
                "VALUES (?,?,?,?,?,?,?)",
                (topic_id, chapter, "vocabulary", title, title,
                 json.dumps(content, ensure_ascii=False), sort_order),
            )
        db.execute(
            "INSERT INTO topics (id,chapter_id,type,title,title_tr,content,sort_order) "
            "VALUES (?,?,?,?,?,?,?)",
            (f"{chapter}-assess", chapter, "unit_assessment", "Unit Assessment",
             "Ünite Değerlendirmesi", json.dumps({"pages": []}, ensure_ascii=False), 9),
        )
        db.commit()


def stored(topic_id):
    with db_connection() as db:
        row = db.execute("SELECT content FROM topics WHERE id=?", (topic_id,)).fetchone()
    return json.loads(row[0])


def digest(content):
    return hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# 1. The detector sees the gap and names its source; the slot walker and the
#    public proof agree.
# ---------------------------------------------------------------------------

content = countries_content()
assert "text_tr" not in content["pages"][5]
assert Q.missing_bilingual_pairs(content) == ["pages.5.text_tr"], \
    Q.missing_bilingual_pairs(content)

slots = Q._missing_bilingual_slots(content)
assert len(slots) == 1, slots
assert slots[0]["path"] == ["pages", 5, "text_tr"], slots[0]
assert slots[0]["field"] == "text_tr" and slots[0]["target_locale"] == "tr"
assert slots[0]["source_field"] == "text" and slots[0]["source_locale"] == "en"
assert slots[0]["source_value"] == SOURCE
# The two predicates are one implementation, so they cannot drift apart.
assert Q._missing_bilingual_pairs(content) == [
    ".".join(map(str, row["path"])) for row in slots
]

# ---------------------------------------------------------------------------
# 2. A complete bilingual topic is a no-op and costs no model call.
# ---------------------------------------------------------------------------

orig_call_model = Q.T.call_model


def refuse_provider(messages, **kwargs):
    raise AssertionError("a complete bilingual topic must not call the model")


clean = countries_content()
clean["pages"][5]["text_tr"] = COUNTERPART
clean_snapshot = json.loads(json.dumps(clean, ensure_ascii=False))
try:
    Q.T.call_model = refuse_provider
    assert Q.repair_bilingual_preflight(
        units=[{"title": "Unit 1", "topics": [
            {"id": "c", "title": "Countries and Nationalities", "content": clean,
             "is_assessment": False}
        ]}],
        language="Spanish", level="A1", track="tr", budget=Q.ReviewBudget(0.22),
    ) == 0
    # An English-taught course has no EN/TR obligation at all.
    gap = countries_content()
    assert Q.repair_bilingual_preflight(
        units=[{"title": "Unit 1", "topics": [
            {"id": "c", "title": "Countries and Nationalities", "content": gap,
             "is_assessment": False}
        ]}],
        language="English", level="A1", track="tr", budget=Q.ReviewBudget(0.22),
    ) == 0
finally:
    Q.T.call_model = orig_call_model

assert clean == clean_snapshot, "a complete topic must not be touched"

# ---------------------------------------------------------------------------
# 3. The gap is filled by one exact call that only ever sees the source field as
#    evidence, and the source itself is never copied into the target.
# ---------------------------------------------------------------------------

calls = []


def counterpart_provider(messages, **kwargs):
    payload = json.loads(messages[-1]["content"])
    calls.append(payload)
    assert payload["path"] == ["pages", 5, "text_tr"], payload["path"]
    assert payload["field"] == "text_tr"
    assert payload["target_locale"] == "tr"
    assert payload["source_field"] == "text"
    assert payload["source_locale"] == "en"
    assert payload["source_value"] == SOURCE
    return T.Response(data={"value": COUNTERPART, "reason": "Turkish counterpart."},
                      input_tokens=180, output_tokens=40, cost=0.0003,
                      model=kwargs.get("model", ""))


def copying_provider(messages, **kwargs):
    # The failure mode the stage exists to refuse: the source echoed back.
    return T.Response(data={"value": SOURCE, "reason": "echo"},
                      input_tokens=180, output_tokens=40, cost=0.0003,
                      model=kwargs.get("model", ""))


def empty_provider(messages, **kwargs):
    return T.Response(data={"value": "   ", "reason": "blank"},
                      input_tokens=180, output_tokens=10, cost=0.0003,
                      model=kwargs.get("model", ""))


for provider, label in ((copying_provider, "copied source"),
                        (empty_provider, "empty counterpart")):
    victim = countries_content()
    try:
        Q.T.call_model = provider
        Q.repair_bilingual_preflight(
            units=[{"title": "Unit 1", "topics": [
                {"id": "c", "title": "Countries and Nationalities",
                 "content": victim, "is_assessment": False}
            ]}],
            language="Spanish", level="A1", track="tr", budget=Q.ReviewBudget(0.22),
        )
    except Q.QualityGateError:
        pass
    else:
        raise AssertionError(f"{label} must fail closed")
    finally:
        Q.T.call_model = orig_call_model
    # The slot was prepared but never filled with anything unproven.
    assert not str(victim["pages"][5].get("text_tr") or "").strip(), victim["pages"][5]

# ---------------------------------------------------------------------------
# 4. The production scenario end to end: the bilingual gap is repaired and
#    checkpointed, THEN an unrelated later topic raises, and the persisted
#    snapshot still carries the repair.
# ---------------------------------------------------------------------------

seed("bilingual")
assert "text_tr" not in stored("bilingual-ch1-countries")["pages"][5]

BOOM = "A Family Photograph: renderer-contract blockers remain"
reviewed = []

orig_lessons = Q.review_unit_lessons


def exploding_lessons(*, unit_title, topics, language, level, track, budget,
                      unit_topic_titles=()):
    """Stands in for the unrelated renderer blocker that aborted the real run."""
    for topic in topics:
        reviewed.append(topic["title"])
        # Every lesson reaching broad review is already bilingually complete.
        assert not Q.missing_bilingual_pairs(topic["content"]), topic["title"]
    raise Q.QualityGateError(BOOM)


in_memory = {}
try:
    Q.T.call_model = counterpart_provider
    Q.review_unit_lessons = exploding_lessons
    try:
        P._run_publication_quality_gate("bilingual", "Spanish", "A1", "tr")
    except Q.QualityGateError as exc:
        assert BOOM in str(exc), exc
    else:
        raise AssertionError("the unrelated later failure must still fail closed")
finally:
    Q.T.call_model = orig_call_model
    Q.review_unit_lessons = orig_lessons

assert len(calls) == 1, calls
# Both lessons reach broad review bilingually complete, on the first attempt and
# on the unit's one bounded retry.
assert reviewed == ["Countries and Nationalities", "A Family Photograph"] * 2, reviewed

persisted = stored("bilingual-ch1-countries")
assert persisted["pages"][5]["text_tr"] == COUNTERPART, persisted["pages"][5]
assert persisted["pages"][5]["text"] == SOURCE, persisted["pages"][5]
assert Q.missing_bilingual_pairs(persisted) == [], Q.missing_bilingual_pairs(persisted)

# The checkpoint wrote exactly the object the stage proved — same JSON, same hash.
in_memory_content = countries_content()
in_memory_content["pages"][5]["text_tr"] = COUNTERPART
assert digest(persisted) == digest(in_memory_content), (
    digest(persisted), digest(in_memory_content)
)
assert json.dumps(persisted, ensure_ascii=False, sort_keys=True) == \
    json.dumps(in_memory_content, ensure_ascii=False, sort_keys=True)

# ---------------------------------------------------------------------------
# 5. A bilingual stage that cannot complete a topic checkpoints nothing.
# ---------------------------------------------------------------------------

seed("bilingual_fail")
before = stored("bilingual_fail-ch1-countries")
try:
    Q.T.call_model = copying_provider
    Q.review_unit_lessons = exploding_lessons
    try:
        P._run_publication_quality_gate("bilingual_fail", "Spanish", "A1", "tr")
    except Q.QualityGateError as exc:
        assert "bilingual" in str(exc).casefold(), exc
    else:
        raise AssertionError("an unprovable bilingual repair must fail closed")
finally:
    Q.T.call_model = orig_call_model
    Q.review_unit_lessons = orig_lessons

assert stored("bilingual_fail-ch1-countries") == before, "nothing may be checkpointed"

print("[BILINGUAL-PREFLIGHT] pages.5.text_tr repaired, proven and checkpointed "
      "before review; a later unrelated failure leaves the repair persisted")
