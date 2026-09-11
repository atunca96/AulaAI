"""Structural integrity checks for generated lesson payloads.

This module never changes lesson-generation prompts or content. It only detects
persisted topic payloads that contain no usable lesson pages so a build cannot be
reported as successful while lessons are blank.
"""

import json

_PAGE_METADATA_KEYS = {"type", "title", "title_tr", "id", "sort_order"}


def _has_displayable_value(value):
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float, bool)):
        return True
    if isinstance(value, list):
        return any(_has_displayable_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_displayable_value(item) for item in value.values())
    return False


def _page_has_content(page):
    if not isinstance(page, dict) or not page:
        return False
    return any(
        key not in _PAGE_METADATA_KEYS and _has_displayable_value(value)
        for key, value in page.items()
    )


def has_lesson_pages(content):
    """Return True only when a lesson payload contains at least one usable content page."""
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
    return any(_page_has_content(page) for page in pages)


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
