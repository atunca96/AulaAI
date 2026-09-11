"""Structural integrity checks for generated lesson payloads.

This module never changes lesson-generation prompts or content. It only detects
persisted topic payloads that contain no usable lesson pages so a build cannot be
reported as successful while lessons are blank.
"""

import json


def has_lesson_pages(content):
    """Return True only when a lesson payload contains at least one non-empty page."""
    if isinstance(content, str):
        try:
            content = json.loads(content or "{}")
        except Exception:
            return False
    if not isinstance(content, dict):
        return False
    pages = content.get("pages")
    if not isinstance(pages, list) or not pages:
        return False
    return any(isinstance(page, dict) and bool(page) for page in pages)


def find_empty_lessons(course_id):
    """Return (topic_id, title) pairs whose persisted lesson payload is structurally empty."""
    from database import db_connection

    with db_connection() as db:
        rows = db.execute(
            """
            SELECT t.id, t.title, t.content
            FROM topics t
            JOIN chapters ch ON t.chapter_id = ch.id
            WHERE ch.course_id = ?
            ORDER BY ch.number, t.sort_order
            """,
            (course_id,),
        ).fetchall()

    empty = []
    for row in rows:
        try:
            topic_id = row["id"]
            title = row["title"]
            content = row["content"]
        except Exception:
            topic_id, title, content = row[0], row[1], row[2]
        if not has_lesson_pages(content):
            empty.append((topic_id, title))
    return empty


def assert_course_lessons_complete(course_id):
    """Raise a concise error when any topic still has an empty lesson payload."""
    empty = find_empty_lessons(course_id)
    if empty:
        sample = ", ".join(str(title) for _, title in empty[:3])
        suffix = "" if len(empty) <= 3 else f" (+{len(empty) - 3} more)"
        raise RuntimeError(f"{len(empty)} lesson(s) are empty: {sample}{suffix}")
    return True
