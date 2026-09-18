"""The only place a classroom may be declared ready, and the proof it needs.

A fresh Spanish A1 build published Unit 2 with nine assessment questions, Unit 3
with eight, and Greek look-alike characters throughout its IPA — from a system
whose deterministic gate catches every one of those defects. The gate was not
broken. Its verdict was thrown away.

`enrich_classroom_phase2` records `build_stage='failed'` when the publication
gate refuses a course. `worker.py` then ran this, in both of its build modes:

    try:
        enrich_classroom_phase2(...)
    except Exception:
        ...
    finally:
        UPDATE courses SET build_stage='completed',
                           build_message='Classroom is ready!'

A `finally` in one mode and an unconditional statement after the `except` in the
other. Either way the refusal was written to the database and overwritten one
statement later, by a caller whose only evidence was that the function had
returned. The export route checks publication state and refuses `failed`
correctly — it simply never saw a `failed`. And because a refused gate never
reaches its persist step, the rows that were then exported held the *pre-review*
generation output: the un-reviewed payload, complete with the items the render
contract refuses and the transcriptions the auditor blocks.

So READY was an assertion made by whoever ran the build last, not a fact about
the classroom. This module makes it a fact:

  * `verify_publishable` re-loads the PERSISTED rows — the same rows the PDF
    renderer will read, at the moment the decision is made — and proves the
    publication invariants on them. Nothing is taken on trust from an earlier
    stage, so a mutation between validation and now cannot pass unnoticed.
  * `mark_ready` is the only writer of the ready state, and it calls
    `verify_publishable` first. A caller cannot grant READY; it can only ask,
    and be refused.
  * `assert_exportable` re-proves the same invariants at export time, against
    the rows the renderer is about to consume, so the artifact the learner
    receives cannot describe a different classroom from the one that was
    certified — however a course came to be marked ready, including before this
    module existed.

Nothing here is language- or locale-specific: every rule it enforces comes from
`quality_gate.validate_publication_integrity` and the render contract, which are
driven by the course's own declared language and instructional track.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

__all__ = [
    "NotPublishable", "READY_STAGE", "verify_publishable", "mark_ready",
    "mark_failed", "assert_exportable", "load_persisted_units",
]


class NotPublishable(Exception):
    """The persisted classroom violates a publication invariant."""


READY_STAGE = "completed"
READY_MESSAGE = "Classroom is ready!"

# Stages that mean "this classroom is not finished, or was refused". The export
# route refuses these outright; `mark_ready` can only move a course out of one
# of them by proving the invariants.
UNPUBLISHED_STAGES = frozenset({
    "failed", "quality_review", "enriching", "priming", "analyzing",
    "building", "generating", "structuring", "finalizing", "starting",
    "timeout", "interrupted", "stopped",
})


def load_persisted_units(course_id: str) -> List[Dict[str, Any]]:
    """Every unit of a course, read back exactly as the renderer reads it.

    This deliberately loads from the database rather than accepting an in-memory
    structure. The whole failure being fixed here is a decision made about one
    object and applied to another, so the object this module judges is the one
    the exporter will actually consume.
    """
    from database import db_connection

    units: List[Dict[str, Any]] = []
    with db_connection() as db:
        chapters = db.execute(
            "SELECT id, title, number FROM chapters WHERE course_id = ? ORDER BY number",
            (course_id,),
        ).fetchall()
        for chapter in chapters:
            rows = db.execute(
                "SELECT id, title, type, content FROM topics WHERE chapter_id = ? "
                "ORDER BY sort_order",
                (chapter[0],),
            ).fetchall()
            topics = []
            for row in rows:
                raw = row[3]
                try:
                    content = json.loads(raw) if isinstance(raw, str) else (raw or {})
                except Exception as parse_err:
                    # An unreadable row is not an empty lesson. Substituting one
                    # would audit perfectly clean and certify a classroom whose
                    # content nobody can read.
                    raise NotPublishable(
                        f"unreadable stored content for topic {row[0]!r} "
                        f"({row[1]!r}): {parse_err}"
                    )
                topics.append({
                    "id": row[0], "title": row[1], "type": row[2],
                    "content": content,
                    "is_assessment": row[2] == "unit_assessment",
                })
            units.append({"title": chapter[1], "number": chapter[2], "topics": topics})
    return units


def _course_row(course_id: str) -> Optional[Dict[str, Any]]:
    from database import db_connection

    with db_connection() as db:
        row = db.execute(
            "SELECT language, level, material_language, build_stage, is_building "
            "FROM courses WHERE id = ?", (course_id,),
        ).fetchone()
    if not row:
        return None
    return {"language": row[0] or "", "level": row[1] or "",
            "material_language": row[2] or "tr", "build_stage": row[3] or "",
            "is_building": bool(row[4])}


def verify_publishable(course_id: str) -> Dict[str, int]:
    """Prove the publication invariants against the persisted rows, or raise.

    Returns the counts the proof established — topics, MCQs and unit-assessment
    questions — so a caller can record what it certified rather than restating
    it from an earlier stage.
    """
    from services.authoring import quality_gate as Q

    course = _course_row(course_id)
    if course is None:
        raise NotPublishable(f"course {course_id!r} does not exist")

    units = load_persisted_units(course_id)
    if not units:
        raise NotPublishable("the classroom has no units")

    try:
        return Q.validate_publication_integrity(
            units=units,
            language=course["language"],
            track=course["material_language"],
        )
    except Q.QualityGateError as exc:
        raise NotPublishable(str(exc)) from exc


def mark_failed(course_id: str, reason: str, gen_id: Optional[str] = None) -> None:
    """Record that a classroom may not be published, and why."""
    from database import db_connection

    message = f"Publication refused: {str(reason)[:160]}"
    with db_connection() as db:
        db.execute(
            "UPDATE courses SET is_building = 0, build_stage = 'failed', "
            "build_message = ? WHERE id = ? "
            "AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')",
            (message, course_id, gen_id, gen_id),
        )
        db.commit()


def mark_ready(course_id: str, gen_id: Optional[str] = None, *,
               progress: Optional[int] = None,
               total_steps: Optional[int] = None) -> Dict[str, int]:
    """Declare a classroom ready — only after proving it may be.

    This is the single writer of the ready state. On refusal the course is
    recorded as failed and `NotPublishable` is raised, so a caller that ignores
    the exception still cannot leave a refused classroom exportable.
    """
    from database import db_connection

    try:
        certified = verify_publishable(course_id)
    except NotPublishable as exc:
        mark_failed(course_id, str(exc), gen_id)
        raise

    fields = ["is_building = 0", "build_stage = ?", "build_message = ?"]
    params: List[Any] = [READY_STAGE, READY_MESSAGE]
    if total_steps is not None:
        fields.append("total_steps = ?")
        params.append(int(total_steps))
    if progress is not None:
        fields.append("progress = ?")
        params.append(int(progress))
    params.extend([course_id, gen_id, gen_id])

    with db_connection() as db:
        db.execute(
            f"UPDATE courses SET {', '.join(fields)} WHERE id = ? "
            "AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')",
            tuple(params),
        )
        db.commit()
    return certified


def assert_exportable(course_id: str) -> Dict[str, int]:
    """The check the export route runs before it renders anything.

    Publication state alone is not enough. A course marked ready before this
    module existed, or by a path that has not been brought through `mark_ready`,
    carries a stage that proves nothing — and the defect being fixed here is
    precisely a ready state that no proof stands behind. So the invariants are
    re-proved here, against the rows the renderer is about to read.
    """
    course = _course_row(course_id)
    if course is None:
        raise NotPublishable("course not found")
    stage = str(course["build_stage"]).strip().casefold()
    if course["is_building"] or stage in UNPUBLISHED_STAGES:
        raise NotPublishable(
            "this classroom has not passed publication review"
            if stage != "failed" else
            "this classroom failed publication review and cannot be exported"
        )
    return verify_publishable(course_id)
