from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.material_generation_prompt import build_material_prompts


def run():
    engine = (ROOT / "services" / "ai_engine.py").read_text(encoding="utf-8")
    assert "# AULAAI_CANONICAL_MATERIAL_PROMPT" in engine
    assert "from services.material_generation_prompt import build_material_prompts" in engine
    assert "system_prompt, user_prompt = build_material_prompts(" in engine
    assert "Build clean, universal, professor-level prompt with full pedagogical freedom" not in engine

    system_prompt, user_prompt = build_material_prompts(
        language="Example Language",
        level="A1",
        topic="Alphabet",
        topic_type="pronunciation",
        official_institution="Example Institute",
        source_text=None,
    )
    assert "A1/A2: concrete, high-frequency" in system_prompt
    assert "BASIC SOUND VALUE(S) IN STANDARD IPA" in system_prompt
    assert "personal name alone never establishes grammatical gender" in system_prompt
    assert "unnecessary metalanguage" in user_prompt
    assert "publication-ready CEFR A1 Example Language lesson" in user_prompt

    print("[CANONICAL-PROMPT] single-source material prompt tests PASSED")


if __name__ == "__main__":
    run()
