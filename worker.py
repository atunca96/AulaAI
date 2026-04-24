import sys
import os
from datetime import datetime

# Add the project root to sys.path so we can import services
sys.path.append(os.getcwd())

from services.pdf_pipeline import start_pipeline_background

if __name__ == "__main__":
    if len(sys.argv) < 6:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER] Error: Missing arguments.")
        print("Usage: python worker.py <pdf_path> <toc_range> <lecturer_id> <course_id> <course_name>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    toc_range = sys.argv[2]
    lecturer_id = sys.argv[3]
    course_id = sys.argv[4]
    course_name = sys.argv[5]

    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER] Background process starting for course {course_id} ({course_name})", flush=True)
    try:
        start_pipeline_background(pdf_path, toc_range, lecturer_id, course_id, course_name)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER] Background process finished successfully for course {course_id}", flush=True)
    except Exception as e:
        import traceback
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [WORKER] CRITICAL ERROR: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
