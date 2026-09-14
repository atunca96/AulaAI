from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_generation_prompt import build_material_prompts

engine = (ROOT / "services" / "ai_engine.py").read_text(encoding="utf-8")
assert "# AULAAI_CANONICAL_MATERIAL_PROMPT" in engine
assert "from services.material_generation_prompt import build_material_prompts" in engine
assert "system_prompt, user_prompt = build_material_prompts(" in engine

system_prompt, user_prompt = build_material_prompts(
    language="Example Language",
    level="A1",
    topic="Alphabet",
    topic_type="pronunciation",
    official_institution="Example Institute",
    source_text=None,
)
for marker in (
    "A1/A2: concrete, high-frequency",
    "BASIC SOUND VALUE(S) IN STANDARD IPA",
    "Pronunciation data is publication-critical",
    "Never guess IPA from spelling",
    "Never insert a sound that is absent from the standard pronunciation",
    "Cross-check every `phonetic` against its exact `term` or example",
    "personal name alone never establishes grammatical gender",
    "all semantic answer options and the keyed answer must be in that same instructional language",
):
    assert marker in system_prompt, marker

assert "unnecessary metalanguage" in user_prompt
assert "publication-ready CEFR A1 Example Language lesson" in user_prompt
print("[CANONICAL-PROMPT] single-source material prompt tests PASSED")
