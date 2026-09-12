import sys
import os

# Ensure Windows Python 3.8+ finds OpenSSL and extension DLLs
if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
    for _p in [os.path.join(sys.base_prefix, "DLLs"), os.path.join(sys.exec_prefix, "DLLs")]:
        if os.path.exists(_p):
            try:
                os.add_dll_directory(_p)
            except Exception:
                pass

import traceback
import threading
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.pipeline_v2.orchestrator import start_pipeline_v2

def heartbeat():
    while True:
        print("[PIPELINE] Heartbeat: Worker is still processing...", file=sys.stderr)
        sys.stderr.flush()
        time.sleep(30)

def main():
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

    h_thread = threading.Thread(target=heartbeat, daemon=True)
    h_thread.start()

    with open("pipeline.log", "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] [WORKER] Process started with args: {sys.argv}\n")

    course_id = None
    if len(sys.argv) >= 2:
        if len(sys.argv) < 5:
            course_id = sys.argv[1]
        else:
            course_id = sys.argv[4]

    if course_id:
        pid_file = os.path.join("data", "workers", f"{course_id}.pid")
        os.makedirs(os.path.dirname(pid_file), exist_ok=True)

        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    old_pid = int(f.read().strip())
                if old_pid != os.getpid():
                    import signal
                    if sys.platform == "win32":
                        import subprocess
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(old_pid)], capture_output=True)
                    else:
                        os.kill(old_pid, signal.SIGTERM)
                    with open("pipeline.log", "a", encoding="utf-8") as f:
                        f.write(f"[{time.strftime('%H:%M:%S')}] [WORKER] Terminated stale worker {old_pid} for course {course_id}\n")
            except Exception:
                pass

        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))

    try:
        if 2 <= len(sys.argv) <= 4:
            course_id = sys.argv[1]
            gen_id = sys.argv[2] if len(sys.argv) >= 3 else "LEGACY"
            source_markdown_path = sys.argv[3] if len(sys.argv) == 4 else None

            if source_markdown_path == "NONE":
                source_markdown_path = None

            from services.legacy.pdf_pipeline import enrich_classroom_phase2
            from database import db_connection

            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] [WORKER] Starting REGENERATE mode for Course {course_id}\n")

            with db_connection() as db:
                row = db.execute("SELECT name, textbook FROM courses WHERE id=?", (course_id,)).fetchone()
                course_name = row["name"] if row else "Unknown Course"
                pdf_path = row["textbook"] if row else None
                db.execute("UPDATE courses SET progress = 0, total_steps = 0, is_building = 1, build_stage = 'enriching', build_message = 'Starting lesson rebuild...', build_started_at = ? WHERE id = ? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')", (time.time(), course_id, gen_id, gen_id))
                db.commit()

            try:
                enrich_classroom_phase2(course_id, pdf_path, source_markdown_path=source_markdown_path, gen_id=gen_id)
            except Exception as e:
                with open("pipeline.log", "a", encoding="utf-8") as f:
                    f.write(f"[{time.strftime('%H:%M:%S')}] [WORKER] ERROR during REGENERATE: {str(e)}\n")
                    f.write(traceback.format_exc())
                raise e
            finally:
                # enrich_classroom_phase2 already performs the single authoritative
                # bilingual finalization. Do not run it again here.
                with db_connection() as db:
                    db.execute("UPDATE courses SET is_building = 0, build_stage = 'completed', build_message = 'Classroom is ready!' WHERE id=? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')", (course_id, gen_id, gen_id))
                    db.commit()
                from database import enroll_permanent_students_in_course
                enroll_permanent_students_in_course(course_id)

            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] [WORKER] Finished REGENERATE mode for Course {course_id}\n")
            return

        if len(sys.argv) < 5:
            print("Usage: worker.py <pdf_path> <toc_range> <lecturer_id> <course_id> [course_name] [manual_toc_path]")
            sys.exit(1)

        pdf_path = sys.argv[1]
        toc_range = sys.argv[2]
        lecturer_id = sys.argv[3]
        course_id = sys.argv[4]
        course_name = sys.argv[5] if len(sys.argv) > 5 else "Untitled Course"
        manual_toc_path = sys.argv[6] if len(sys.argv) > 6 else None
        source_markdown_path = sys.argv[7] if len(sys.argv) > 7 else None
        language = sys.argv[8] if len(sys.argv) > 8 else "Detecting..."
        level = sys.argv[9] if len(sys.argv) > 9 else "A1"
        gen_id = sys.argv[10] if len(sys.argv) > 10 else "LEGACY"

        manual_toc = None
        if manual_toc_path and os.path.exists(manual_toc_path) and manual_toc_path != "NONE":
            with open(manual_toc_path, "r", encoding="utf-8") as f:
                manual_toc = f.read()

        from database import db_connection
        with db_connection() as db:
            db.execute("UPDATE courses SET progress = 0, total_steps = 0, is_building = 1, build_stage = 'analyzing', build_message = 'Ders programı analiz ediliyor...', build_started_at = ? WHERE id = ? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')", (time.time(), course_id, gen_id, gen_id))
            db.commit()

        print(f"[PIPELINE] Worker starting FULL PIPELINE (V2) for Course {course_id} ({course_name})")
        start_pipeline_v2(pdf_path, course_id, lecturer_id, manual_toc=manual_toc, language=language, level=level, gen_id=gen_id, toc_range=toc_range)

        print(f"[PIPELINE] Worker starting ENRICHMENT (Phase 2) for Course {course_id}")
        from services.legacy.pdf_pipeline import enrich_classroom_phase2
        from database import db_connection

        with db_connection() as db:
            db.execute("""
                UPDATE courses SET total_steps = (
                    SELECT COUNT(*) FROM topics t
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ?
                ), build_stage = 'enriching', build_message = 'Ders içerikleri hazırlanıyor...' WHERE id = ? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')
            """, (course_id, course_id, gen_id, gen_id))
            db.commit()

        try:
            enrich_classroom_phase2(course_id, pdf_path, source_markdown_path=source_markdown_path, gen_id=gen_id)
            print(f"[PIPELINE] Worker finished ENRICHMENT for Course {course_id}")
        except Exception as e:
            print(f"[PIPELINE] ERROR during ENRICHMENT: {e}")
            with db_connection() as db:
                db.execute("UPDATE courses SET is_building = 0, build_stage = 'failed', build_message = ? WHERE id = ? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')", (f"Enrichment error: {str(e)[:120]}", course_id, gen_id, gen_id))
                db.commit()

        # enrich_classroom_phase2 already runs bilingual finalization once.
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0, build_stage = 'completed', progress = 100, build_message = 'Classroom is ready!' WHERE id = ? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')", (course_id, gen_id, gen_id))
            db.commit()
        from database import enroll_permanent_students_in_course
        enroll_permanent_students_in_course(course_id)

        print(f"[PIPELINE] Worker finished FULL PIPELINE (V2 + Enrichment) for Course {course_id}")

    except Exception:
        print("[PIPELINE] FATAL ERROR in worker.py:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)

if __name__ == "__main__":
    main()
