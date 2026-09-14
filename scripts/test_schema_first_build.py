from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
engine = (ROOT / "services" / "ai_engine.py").read_text(encoding="utf-8")

assert "AULAAI_SCHEMA_FIRST_V54" in engine
assert "typed semantic slots" in engine
assert "ASSESSMENT DOMAIN" in engine
assert "DIALOGUE STRUCTURE" in engine
assert "WRITING-SYSTEM OBJECTS ARE DATA" in engine
assert "PRONUNCIATION — ONE SOURCE OF TRUTH" in engine
assert "personal name alone" in engine
assert "unstated real-world premise" in engine

print("[SCHEMA-FIRST] build contract PASSED")
