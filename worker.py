import sys
import traceback
import threading
import time
import os
from services.pipeline_v2.orchestrator import start_pipeline_v2

def heartbeat():
    while True:
        # Using stderr for heartbeat to keep stdout clean for JSON if needed
        print("[PIPELINE] Heartbeat: Worker is still processing...", file=sys.stderr)
        sys.stderr.flush()
        time.sleep(30)

def main():
    # Load environment variables for worker stability
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v

    # Start heartbeat in background
    h_thread = threading.Thread(target=heartbeat, daemon=True)
    h_thread.start()
    
    with open("pipeline.log", "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] [WORKER] Process started with args: {sys.argv}\n")
    
    try:
        # Check if this is a REBUILD (1 argument) or a FULL PIPELINE (4+ arguments)
        if len(sys.argv) == 2:
            course_id = sys.argv[1]
            from services.legacy.pdf_pipeline import enrich_classroom_phase2
            from database import db_connection
            
            with open("pipeline.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] [WORKER] Starting REGENERATE mode for Course {course_id}\n")
            
            with db_connection() as db:
                row = db.execute("SELECT name, textbook FROM courses WHERE id=?", (course_id,)).fetchone()
                course_name = row["name"] if row else "Unknown Course"
                pdf_path = row["textbook"] if row else None
            
            try:
                # Phase 2 Only - use the correct function name!
                enrich_classroom_phase2(course_id, pdf_path)
            except Exception as e:
                with open("pipeline.log", "a", encoding="utf-8") as f:
                    f.write(f"[{time.strftime('%H:%M:%S')}] [WORKER] ERROR during REGENERATE: {str(e)}\n")
                    f.write(traceback.format_exc())
                raise e
            finally:
                with db_connection() as db:
                    db.execute("UPDATE courses SET is_building=0 WHERE id=?", (course_id,))
                    db.commit()

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

        manual_toc = None
        if manual_toc_path and os.path.exists(manual_toc_path) and manual_toc_path != "NONE":
            with open(manual_toc_path, "r", encoding="utf-8") as f:
                manual_toc = f.read()

        print(f"[PIPELINE] Worker starting FULL PIPELINE (V2) for Course {course_id} ({course_name})")
        start_pipeline_v2(pdf_path, course_id, lecturer_id, manual_toc=manual_toc)
        print(f"[PIPELINE] Worker finished FULL PIPELINE (V2) for Course {course_id}")

    except Exception as e:
        print("[PIPELINE] FATAL ERROR in worker.py:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)

if __name__ == "__main__":
    main()
