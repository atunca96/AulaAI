from pathlib import Path

p = Path("services/ai_engine.py")
s = p.read_text(encoding="utf-8")

marker = "# AULAAI_MATERIAL_COMPLETENESS_FAIL_CLOSED_V58"
if marker in s:
    raise SystemExit(0)

old = '''    if not lesson_dict or not isinstance(lesson_dict, dict) or not lesson_dict.get("pages") or len(lesson_dict.get("pages", [])) < 3:\n        with open("pipeline.log", "a", encoding="utf-8") as f:\n            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-ABORT] '{topic}' failed after 3 attempts on {MODEL_LESSON}.\\n")\n        return {"pages": []}\n'''

new = '''    if not lesson_dict or not isinstance(lesson_dict, dict) or not lesson_dict.get("pages") or len(lesson_dict.get("pages", [])) < 3:\n        # AULAAI_MATERIAL_COMPLETENESS_FAIL_CLOSED_V58\n        with open("pipeline.log", "a", encoding="utf-8") as f:\n            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-ABORT] '{topic}' failed after 3 attempts on {MODEL_LESSON}; refusing to publish an empty topic.\\n")\n        raise RuntimeError(f"Incomplete lesson topic after 3 attempts: {topic!r} produced fewer than 3 pages")\n'''

if old not in s:
    raise RuntimeError("v58 completeness abort boundary missing")

s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("Applied v58 completeness fail-closed: incomplete topics can no longer publish as empty shells")
