from pathlib import Path

root = Path(__file__).resolve().parents[1]
ai_path = root / "services" / "ai_engine.py"
pipe_path = root / "services" / "legacy" / "pdf_pipeline.py"

ai = ai_path.read_text(encoding="utf-8")
pipe = pipe_path.read_text(encoding="utf-8")

# 1) The main lesson model already generates and persists both English and Turkish
# learner-facing fields. Never spend another model call translating the lesson
# after generation. Missing bilingual pronunciation content is handled by the
# generation-time validation/retry gate added in v21.
old_translate = '''    # Only run secondary translation fallback if Turkish was not provided natively
    if material_language in ["tr", "all"] and not has_turkish:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-TRANSLATE-FALLBACK] '{topic}' lacks native Turkish, running translator...\\n")
        lesson_dict = translate_lesson_to_turkish(lesson_dict, language=language)

    return lesson_dict
'''
new_translate = '''    # Native bilingual lesson fields are authoritative. A second translation
    # model pass is intentionally disabled: it adds cost/latency and can overwrite
    # the pedagogy produced by the lesson model.
    if material_language in ["tr", "all"] and not has_turkish:
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [LESSON-BILINGUAL-NATIVE] '{topic}' has incomplete native Turkish fields; no secondary translator will run.\\n")

    return lesson_dict
'''
count_translate = ai.count(old_translate)
if count_translate != 1:
    raise RuntimeError(f"v22 translator anchor expected 1, found {count_translate}")
ai = ai.replace(old_translate, new_translate, 1)

# 2) Long lesson requests previously received four transport/provider attempts
# inside _call_ai, while generate_full_lesson itself already has three independent
# generation attempts. Keep the three quality attempts, but cap MODEL_LESSON's
# internal provider attempts at two. Worst case drops from 12 requests/topic to 6
# without reducing the lesson's content budget or schema.
old_attempts = '            max_attempts = 2 if max_tokens <= 2500 else 4'
new_attempts = '            max_attempts = 2 if (model == MODEL_LESSON or max_tokens <= 2500) else 4'
count_attempts = ai.count(old_attempts)
if count_attempts != 1:
    raise RuntimeError(f"v22 provider retry anchor expected 1, found {count_attempts}")
ai = ai.replace(old_attempts, new_attempts, 1)

# Shorten only the delay between fresh lesson-generation attempts. Keep all three
# attempts so content quality/reliability is unchanged.
old_sleep = '            time.sleep(2.0 * attempt_idx)'
new_sleep = '            time.sleep(0.75 * attempt_idx)'
count_sleep = ai.count(old_sleep)
if count_sleep != 1:
    raise RuntimeError(f"v22 lesson retry sleep anchor expected 1, found {count_sleep}")
ai = ai.replace(old_sleep, new_sleep, 1)

# 3) The last run had 30 topics and a long-tail after most workers had already
# finished. Raise the default pool modestly from 16 to 20 so stragglers start
# earlier. This does not create extra topic/model calls; it only overlaps them.
old_workers = '''        # 16 concurrent workers — tuned for Gemini 3.7 Flash high throughput
        max_workers = int(os.getenv("PIPELINE_MAX_WORKERS", "16"))'''
new_workers = '''        # 20 concurrent workers — modestly reduce 30-topic tail latency without changing work volume
        max_workers = int(os.getenv("PIPELINE_MAX_WORKERS", "20"))'''
count_workers = pipe.count(old_workers)
if count_workers != 1:
    raise RuntimeError(f"v22 worker anchor expected 1, found {count_workers}")
pipe = pipe.replace(old_workers, new_workers, 1)

# Guardrails: do not touch the proven 8192-token lesson budget or the three outer
# generation attempts. The optimization must only remove redundant work/retries.
if 'max_tokens=8192' not in ai:
    raise RuntimeError("v22 guard: lesson token budget changed unexpectedly")
if 'for attempt_idx in range(1, 4):' not in ai:
    raise RuntimeError("v22 guard: three lesson quality attempts must remain")
if 'lesson_dict = translate_lesson_to_turkish(lesson_dict' in ai:
    raise RuntimeError("v22 guard: secondary lesson translator call still active")
if 'max_attempts = 2 if (model == MODEL_LESSON or max_tokens <= 2500) else 4' not in ai:
    raise RuntimeError("v22 guard: lesson provider retry cap missing")
if 'PIPELINE_MAX_WORKERS", "20"' not in pipe:
    raise RuntimeError("v22 guard: worker pool optimization missing")

ai_path.write_text(ai, encoding="utf-8")
pipe_path.write_text(pipe, encoding="utf-8")
print("Applied v22: native bilingual only; lower lesson retry overhead; 20-worker enrichment")
