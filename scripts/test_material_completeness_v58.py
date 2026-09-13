from pathlib import Path

engine = Path("services/ai_engine.py").read_text(encoding="utf-8")
prompt = Path("services/material_generation_prompt.py").read_text(encoding="utf-8")

assert "# AULAAI_MATERIAL_COMPLETENESS_FAIL_CLOSED_V58" in engine
assert "Incomplete lesson topic after 3 attempts" in engine
assert "return {\"pages\": []}" not in engine[engine.index("# AULAAI_MATERIAL_COMPLETENESS_FAIL_CLOSED_V58") - 500: engine.index("# AULAAI_MATERIAL_COMPLETENESS_FAIL_CLOSED_V58") + 1000]
assert "for attempt_idx in range(1, 4):" in engine
assert 'len(norm_dict.get("pages", [])) >= 3' in engine

assert "<completeness_contract>" in prompt
assert "at least 3 substantive `pages`" in prompt
assert "A title-only page does not count" in prompt
assert "Never collapse the whole topic to zero pages" in prompt
assert "fewer than 3 pages is an incomplete result" in prompt

print("[V58] material completeness fail-closed regression tests PASSED")
