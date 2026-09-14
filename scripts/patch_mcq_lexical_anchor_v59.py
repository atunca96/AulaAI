from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
guard_path = ROOT / "services" / "material_quality_guard.py"
TAG = "# AULAAI_MCQ_LEXICAL_ANCHOR_V59"

guard = guard_path.read_text(encoding="utf-8")
if "# AULAAI_RELEASE_CLEANUP_V56_QUALITY" not in guard:
    raise RuntimeError("v56 quality overlay must be applied before v59 lexical-anchor guard")

if TAG not in guard:
    guard += r'''

# AULAAI_MCQ_LEXICAL_ANCHOR_V59
# Surgical Russian MCQ quality guard. It removes only an MCQ whose options are
# the four basic Russian 3rd-person pronouns when the stem contains no Russian
# lexical anchor at all. This prevents questions such as:
#   "Where is the newspaper? — ___ is on the table." + Он/Она/Оно/Они
# where the learner must silently translate "newspaper" -> газета before the
# grammatical-gender task can even be solved. No page other than the MCQ itself
# can be removed, and no replacement content is invented.
import re as _v59_re

_V59_RU_PRONOUN_SET = {"он", "она", "оно", "они"}


def _v59_has_cyrillic(value):
    return bool(_v59_re.search(r"[А-Яа-яЁё]", str(value or "")))


def _v59_stem_text(page):
    if not isinstance(page, dict):
        return ""
    parts = []
    for key in ("prompt", "prompt_en", "prompt_tr", "question", "question_en", "question_tr", "stem", "stem_en", "stem_tr"):
        value = page.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value)
    return " ".join(parts)


def _v59_unstated_lexical_bridge(page):
    """Detect only the high-confidence pronoun/gender hidden-translation pattern."""
    if not _v56q_page_is_mcq(page):
        return False
    options = page.get("options") or page.get("choices") or []
    if not isinstance(options, list) or len(options) != 4:
        return False
    normalized = {_v56q_stressless(v).strip() for v in options if isinstance(v, str)}
    if normalized != _V59_RU_PRONOUN_SET:
        return False
    # A Russian noun/phrase in any visible stem field makes the grammatical
    # target explicit. If there is no Cyrillic at all, the item requires an
    # unstated translation bridge and is rejected.
    return not _v59_has_cyrillic(_v59_stem_text(page))


_v59_previous_unsafe_mcq = _v56q_unsafe_mcq

def _v56q_unsafe_mcq(page, material_language="tr"):
    if _v59_previous_unsafe_mcq(page, material_language):
        return True
    return _v59_unstated_lexical_bridge(page)
'''
    guard_path.write_text(guard, encoding="utf-8")

print("Applied v59 MCQ lexical-anchor guard: pronoun/gender hidden-translation items only")
