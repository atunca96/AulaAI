from pathlib import Path

path = Path('worker.py')
src = path.read_text(encoding='utf-8')

regen_old = '''            finally:\n                try:\n                    from services.bilingual_finisher import finalize_course_bilingual_data\n                    finalize_course_bilingual_data(course_id)\n                except Exception as b_err:\n                    print(f"[WORKER] Warning: finalize_course_bilingual_data failed: {b_err}")\n                with db_connection() as db:\n'''
regen_new = '''            finally:\n                # enrich_classroom_phase2 owns bilingual finalization. Do not run it\n                # again here: a second pass retranslates the freshly generated course.\n                with db_connection() as db:\n'''

full_old = '''        # Finalize bilingual data before releasing course build\n        try:\n            from services.bilingual_finisher import finalize_course_bilingual_data\n            finalize_course_bilingual_data(course_id)\n        except Exception as b_err:\n            print(f"[PIPELINE] Warning: finalize_course_bilingual_data failed: {b_err}")\n\n        # Finalize\n'''
full_new = '''        # enrich_classroom_phase2 already performs the single authoritative\n        # bilingual finalization before returning.\n\n        # Finalize\n'''

if regen_old not in src:
    raise RuntimeError('REGENERATE duplicate bilingual-finalizer anchor not found')
if full_old not in src:
    raise RuntimeError('FULL PIPELINE duplicate bilingual-finalizer anchor not found')

src = src.replace(regen_old, regen_new, 1)
src = src.replace(full_old, full_new, 1)
path.write_text(src, encoding='utf-8')
print('Removed duplicate worker bilingual finalization passes')
