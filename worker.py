import sys
import os

# Add the project root to sys.path so we can import services
sys.path.append(os.getcwd())

from services.pdf_pipeline import start_pipeline_background

if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("Usage: python worker.py <pdf_path> <toc_range> <lecturer_id> <course_id> <course_name>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    toc_range = sys.argv[2]
    lecturer_id = sys.argv[3]
    course_id = sys.argv[4]
    course_name = sys.argv[5]

    print(f"Worker process started for course {course_id}")
    start_pipeline_background(pdf_path, toc_range, lecturer_id, course_id, course_name)
    print(f"Worker process finished for course {course_id}")
