import sys
import traceback
import threading
import time
from services.pdf_pipeline import enrich_classroom_phase2

def heartbeat():
    while True:
        print("[PIPELINE] Heartbeat: Worker is still processing...", file=sys.stderr)
        sys.stderr.flush()
        time.sleep(30)

def main():
    # Start heartbeat in background
    h_thread = threading.Thread(target=heartbeat, daemon=True)
    h_thread.start()
    
    try:
        if len(sys.argv) < 5:
            print("Usage: worker.py <pdf_path> <toc_range> <lecturer_id> <course_id> [manual_toc_path]")
            sys.exit(1)

        pdf_path = sys.argv[1]
        toc_range = sys.argv[2]
        lecturer_id = sys.argv[3]
        course_id = sys.argv[4]
        manual_toc_path = sys.argv[5] if len(sys.argv) > 5 else None

        print(f"[PIPELINE] Worker starting Phase 2 for Course {course_id}")
        enrich_classroom_phase2(course_id, pdf_path, manual_toc_path)
        print(f"[PIPELINE] Worker finished Phase 2 for Course {course_id}")

    except Exception as e:
        print("[PIPELINE] FATAL ERROR in worker.py:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)

if __name__ == "__main__":
    main()
