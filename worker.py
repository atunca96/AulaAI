import sys
import traceback
import threading
import time
import os
from services.pdf_pipeline import start_pipeline_background

def heartbeat():
    while True:
        # Using stderr for heartbeat to keep stdout clean for JSON if needed
        print("[PIPELINE] Heartbeat: Worker is still processing...", file=sys.stderr)
        sys.stderr.flush()
        time.sleep(30)

def main():
    # Start heartbeat in background
    h_thread = threading.Thread(target=heartbeat, daemon=True)
    h_thread.start()
    
    try:
        if len(sys.argv) < 5:
            print("Usage: worker.py <pdf_path> <toc_range> <lecturer_id> <course_id> [course_name] [manual_toc_path]")
            sys.exit(1)

        pdf_path = sys.argv[1]
        toc_range = sys.argv[2]
        lecturer_id = sys.argv[3]
        course_id = sys.argv[4]
        course_name = sys.argv[5] if len(sys.argv) > 5 else "Untitled Course"
        manual_toc_path = sys.argv[6] if len(sys.argv) > 6 else None

        manual_toc = None
        if manual_toc_path and os.path.exists(manual_toc_path):
            with open(manual_toc_path, "r", encoding="utf-8") as f:
                manual_toc = f.read()

        print(f"[PIPELINE] Worker starting FULL PIPELINE for Course {course_id} ({course_name})")
        # start_pipeline_background handles Phase 1 and then internally triggers enrichment
        start_pipeline_background(pdf_path, toc_range, lecturer_id, course_id, course_name, manual_toc=manual_toc)
        print(f"[PIPELINE] Worker finished FULL PIPELINE for Course {course_id}")

    except Exception as e:
        print("[PIPELINE] FATAL ERROR in worker.py:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)

if __name__ == "__main__":
    main()
