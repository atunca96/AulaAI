from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
engine_path = ROOT / "services" / "ai_engine.py"
s = engine_path.read_text(encoding="utf-8")

# Remove legacy material-output sanitizer stack. The new material path relies on
# generation quality plus structural validation, not language-specific repair.
start = s.find("def universal_sanitize_english(")
end = s.find("def _normalize_lesson_pages(", start)
if start < 0 or end < 0:
    raise RuntimeError("raw reset: sanitizer block anchors missing")
replacement = '''def universal_sanitize_english(text: str) -> str:\n    return text\n\ndef _sanitize_turkish_content(text: str) -> str:\n    return text\n\ndef _sanitize_deep_bilingual(obj):\n    return obj\n\n'''
s = s[:start] + replacement + s[end:]

# Replace the complete lesson-generation and translation path with the raw,
# language-agnostic prompt. No post-generation linguistic filtering is used.
start = s.find("def translate_lesson_to_turkish(")
end = s.find("def ai_explain_word(", start)
if start < 0 or end < 0:
    raise RuntimeError("raw reset: lesson block anchors missing")

raw_generation = '''def translate_lesson_to_turkish(lesson_dict, language=None):\n    # Legacy compatibility only. New material generation creates requested\n    # instructional tracks in the original generation call.\n    return lesson_dict\n\n\ndef generate_full_lesson(topic, topic_type, language, count=6, level=\"A1\", source_text=None, material_language=\"tr\"):\n    from services.material_generation_prompt import build_material_prompts, structurally_valid_material\n\n    system_prompt, user_prompt = build_material_prompts(\n        topic=topic,\n        topic_type=topic_type,\n        language=language,\n        level=level,\n        material_language=material_language,\n        source_text=source_text,\n    )\n\n    with open(\"pipeline.log\", \"a\", encoding=\"utf-8\") as f:\n        f.write(f\"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-RAW] '{topic}' {level} {language} prompt_chars={len(system_prompt) + len(user_prompt)}\\n\")\n\n    result = _call_ai(\n        [{\"role\": \"system\", \"content\": system_prompt}, {\"role\": \"user\", \"content\": user_prompt}],\n        model=MODEL_LESSON,\n        max_tokens=8192,\n        temperature=0.2,\n        json_mode=True,\n        allow_fallback=False,\n    )\n\n    if structurally_valid_material(result):\n        return result\n\n    with open(\"pipeline.log\", \"a\", encoding=\"utf-8\") as f:\n        f.write(f\"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-RAW-ABORT] '{topic}' returned invalid material structure\\n\")\n    return {\"pages\": []}\n\n\n'''
s = s[:start] + raw_generation + s[end:]

# Retire the final Turkish syntax healer as a material repair mechanism. Keep the
# public function for compatibility with unrelated call sites.
start = s.find("def heal_turkish_syntax(")
if start >= 0:
    next_def = s.find("\ndef ", start + 5)
    if next_def < 0:
        next_def = len(s)
    s = s[:start] + "def heal_turkish_syntax(text: str) -> str:\n    return text\n" + s[next_def:]

engine_path.write_text(s, encoding="utf-8")
print("Applied raw universal material-generation reset")
