"""
Main server — Python stdlib HTTP server with REST API routing.
No external dependencies required.
"""

import http.server
import json
import os
import sys
import uuid
import sys
import sqlite3
import threading
import time
import logging
import subprocess
import random as py_random

logging.basicConfig(level=logging.WARNING, format='%(message)s')
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta, timezone

def file_log(msg):
    with open("pipeline.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [SERVER] {msg}\n")
        f.flush()

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db, init_db, db_connection, DATA_DIR, BOOKS_DIR
from services.content_engine import generate_activity, generate_quiz, grade_response, generate_dialogue_activity
from services.mastery import compute_mastery, generate_weekly_report
from services.ai_engine import is_ai_available, ai_generate_report_insights, ai_generate_activity_batch
from services.pdf_pipeline import process_pdf_to_classroom
from services.state import bump_version, get_version

PORT = int(os.environ.get("PORT", 3000))
STATIC_DIR = os.path.join(os.path.dirname(__file__), "public")

# Auto-reload logic
def watch_files():
    last_mtime = {}
    while True:
        for root, dirs, files in os.walk(os.path.dirname(__file__)):
            for f in files:
                if f.endswith('.py'):
                    path = os.path.join(root, f)
                    mtime = os.path.getmtime(path)
                    if path in last_mtime and mtime > last_mtime[path]:
                        print("[RELOAD] Change detected, restarting...")
                        os.execv(sys.executable, ['python'] + sys.argv)
                    last_mtime[path] = mtime
        time.sleep(2)

# Only start auto-reload in local dev (no PORT or RAILWAY env)
if not os.environ.get("PORT") and not os.environ.get("RAILWAY_ENVIRONMENT"):
    threading.Thread(target=watch_files, daemon=True).start()


# Version tracking moved to services.state

# ── Global Cache ──
_cache = {}
_cache_lock = threading.Lock()

def get_cache(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.time() - entry['ts']) < 300: # 5 min TTL
            return entry['data']
    return None

def set_cache(key, data):
    # Caching disabled during stabilization phase
    pass

def clear_cache():
    with _cache_lock:
        _cache.clear()

MIME_TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".pdf": "application/pdf",
}


def _uid():
    return str(uuid.uuid4())


class APIHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler with REST API routing."""

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

    def _get_user_id(self):
        """Extract user_id from query parameters."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        return params.get("user_id", [None])[0]

    def _get_user_role(self):
        """Extract role from query parameters."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        return params.get("role", [None])[0]

    def _send_json(self, data, status=200):
        # Auto-cache eligible GET requests
        if status == 200 and self.command == 'GET' and '/api/' in self.path:
            set_cache(self.path, data)
            
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        try:
            payload = json.dumps(data, default=str, ensure_ascii=False)
            self.wfile.write(payload.encode("utf-8"))
        except Exception as e:
            print(f"[ERROR] Failed to send JSON: {e}")
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def _send_error(self, message, status=400):
        self._send_json({"error": message}, status)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body)

    def _serve_static(self, path):
        """Serve static files from the public directory."""
        if path.startswith("/books/"):
            data_books_dir = os.path.normpath(BOOKS_DIR)
            filepath = os.path.normpath(os.path.join(data_books_dir, path.replace("/books/", "", 1)))
            if not filepath.startswith(data_books_dir):
                self.send_error(403)
                return
            if not os.path.isfile(filepath):
                # Fallback to public/books for default textbook
                filepath = os.path.normpath(os.path.join(STATIC_DIR, path.lstrip("/")))
                if not os.path.isfile(filepath):
                    self.send_error(404)
                    return
        else:
            if path == "/" or path == "":
                path = "/index.html"
    
            filepath = os.path.join(STATIC_DIR, path.lstrip("/"))
            filepath = os.path.normpath(filepath)
    
            # Security: ensure path is within STATIC_DIR
            if not filepath.startswith(os.path.normpath(STATIC_DIR)):
                self.send_error(403)
                return
    
            if not os.path.isfile(filepath):
                # Only fallback to index.html for paths that don't look like static assets
                ext = os.path.splitext(path)[1]
                if ext in ["", ".html"]:
                    filepath = os.path.join(STATIC_DIR, "index.html")
                else:
                    self.send_error(404)
                    return

        ext = os.path.splitext(filepath)[1]
        content_type = MIME_TYPES.get(ext, "application/octet-stream")

        try:
            file_size = os.path.getsize(filepath)
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            
            # Stream the file in chunks to prevent memory spikes and connection resets
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(64 * 1024) # 64KB chunks
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (ConnectionResetError, BrokenPipeError):
                        print(f"[DEBUG] Client disconnected while reading {path}")
                        return
        except FileNotFoundError:
            self.send_error(404)
        except Exception as e:
            print(f"[ERROR] Serving {path}: {e}")
            if not self.wfile.closed:
                self.send_error(500)

    # ── GET routes ──────────────────────────────────────────

    def do_GET(self):
        start_time = time.time()
        try:
            self._handle_GET()
        except Exception as e:
            print(f"[ERROR] GET {self.path}: {e}")
            try:
                self._send_json({"error": "Internal server error"}, 500)
            except Exception:
                pass
        duration = time.time() - start_time
        if duration > 0.1: # Profile slow requests (>100ms)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [PROFILE] slow GET {self.path} ({duration:.3f}s)")

    def _handle_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Health check for Render
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # Cache lookup for GET requests
        cached_data = get_cache(self.path)
        if cached_data:
            return self._send_json(cached_data)

        # API Routes
        if path == "/api/courses":
            return self._get_courses()
        elif path == "/api/curriculum":
            course_id = params.get("course_id", [None])[0]
            return self._get_curriculum(course_id)
        elif path == "/api/students":
            course_id = params.get("course_id", [None])[0]
            return self._get_students(course_id)
        elif path == "/api/student/progress":
            student_id = params.get("student_id", [None])[0]
            course_id = params.get("course_id", [None])[0]
            return self._get_student_progress(student_id, course_id)
        elif path == "/api/questions":
            topic_id = params.get("topic_id", [None])[0]
            return self._get_questions(topic_id)
        elif path == "/api/quiz/take":
            quiz_id = params.get("quiz_id", [None])[0]
            student_id = params.get("student_id", [None])[0]
            return self._get_quiz(quiz_id, student_id)
        elif path == "/api/classroom/progress":
            return self._get_classroom_progress()
        elif path == "/api/quizzes":
            course_id = params.get("course_id", [None])[0]
            student_id = params.get("student_id", [None])[0]
            return self._get_quizzes(course_id, student_id)
        elif path == "/api/messages":
            student_id = params.get("student_id", [None])[0]
            course_id = params.get("course_id", [None])[0]
            return self._get_messages(student_id, course_id)
        elif path == "/api/report":
            course_id = params.get("course_id", [None])[0]
            return self._get_report(course_id)
        elif path == "/api/activity/progress":
            course_id = params.get("course_id", [None])[0]
            return self._activity_progress(course_id)
        elif path == "/api/draft/progress":
            course_id = params.get("course_id", [None])[0]
            return self._draft_progress(course_id)
        elif path == "/api/activity":
            topic_id = params.get("topic_id", [None])[0]
            return self._get_activity(topic_id)
        elif path == "/api/student/stats":
            student_id = params.get("student_id", [None])[0]
            course_id = params.get("course_id", [None])[0]
            return self._get_student_stats(student_id, course_id)
        elif path == "/api/quiz/responses":
            quiz_id = params.get("quiz_id", [None])[0]
            return self._get_quiz_responses(quiz_id)
        elif path == "/api/assignments":
            course_id = params.get("course_id", [None])[0]
            student_id = params.get("student_id", [None])[0]
            return self._get_assignments(course_id, student_id)
        elif path == "/api/assignment/take":
            assignment_id = params.get("assignment_id", [None])[0]
            student_id = params.get("student_id", [None])[0]
            return self._get_assignment(assignment_id, student_id)
        elif path == "/api/assignment/responses":
            assignment_id = params.get("assignment_id", [None])[0]
            return self._get_assignment_responses(assignment_id)
        elif path == "/api/ai-status":
            return self._get_ai_status()
        elif path == "/api/students/pending":
            return self._get_pending_students()
        elif path == "/api/user/status":
            user_id = params.get("user_id", [None])[0]
            return self._get_user_status(user_id)
        elif path == "/api/version":
            return self._send_json({"version": get_version()})
        elif path == "/health" or path == "/api/health":
            return self._send_json({"status": "ok", "time": datetime.now().isoformat()})
        elif path.startswith("/api/"):
            return self._send_error("Not found", 404)
        else:
            return self._serve_static(path)

    def _wipe_curriculum(self):
        """Delete all chapters and topics for a classroom to start fresh."""
        body = self._read_body()
        course_id = body.get("course_id")
        if not course_id: return self._send_error("Missing course_id")

        with db_connection() as db:
            # 1. Delete questions
            db.execute("""
                DELETE FROM questions WHERE topic_id IN (
                    SELECT t.id FROM topics t
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ?
                )
            """, (course_id,))
            
            # 2. Delete topics
            db.execute("DELETE FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id = ?)", (course_id,))
            
            # 3. Delete chapters
            db.execute("DELETE FROM chapters WHERE course_id = ?", (course_id,))
            
            # 4. Reset building status
            db.execute("UPDATE courses SET is_building = 0, progress = 0 WHERE id = ?", (course_id,))
            db.commit()

        bump_version()
        self._send_json({"status": "success", "message": "Curriculum wiped"})

    def _classroom_rebuild(self):
        """Lecturer manually triggers a rebuild of Phase 2 enrichment."""
        body = self._read_body()
        course_id = body.get("course_id")
        if not course_id: return self._send_error("Missing course_id")

        with db_connection() as db:
            course = db.execute("SELECT is_building FROM courses WHERE id = ?", (course_id,)).fetchone()
            if not course: return self._send_error("Course not found")
            if course["is_building"]: return self._send_error("Course is already building")

            # Delete all existing questions/activities for this course to start fresh
            db.execute("""
                DELETE FROM questions WHERE topic_id IN (
                    SELECT t.id FROM topics t
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ?
                )
            """, (course_id,))
            
            # Reset is_building flag to trigger worker
            db.execute("UPDATE courses SET is_building = 1, progress = 0, total_steps = (SELECT COUNT(*) FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id=?)) WHERE id = ?", (course_id, course_id))
            db.commit()

        # Start the background worker
        import subprocess
        try:
            cmd = [sys.executable, "worker.py", course_id]
            log_file = open("pipeline.log", "a", encoding="utf-8")
            
            if sys.platform == "win32":
                subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, 
                               creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, close_fds=True)
            
            log_file.close()
            self._send_json({"status": "success", "message": "Rebuild started"})
        except Exception as e:
            self._send_error(f"Failed to start worker: {e}")

    def _get_classroom_progress(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        course_id = params.get("course_id", [None])[0]
        if not course_id: return self._send_error("course_id required")

        with db_connection() as db:
            row = db.execute("SELECT is_building, progress, total_steps FROM courses WHERE id=?", (course_id,)).fetchone()
            if not row: return self._send_error("Course not found")
            
            is_building = row["is_building"]
            progress = row["progress"] or 0
            total = row["total_steps"] or 1 # Avoid division by zero
            
            percentage = min(100, int((progress / total) * 100)) if is_building else 100
            return self._send_json({
                "course_id": course_id,
                "is_building": bool(is_building),
                "progress": progress,
                "total": total,
                "percentage": percentage
            })

    def do_POST(self):
        start_time = time.time()
        try:
            self._handle_POST()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[ERROR] POST {self.path}: {e}")
            try:
                self._send_json({"error": "Internal server error"}, 500)
            except Exception:
                pass
        duration = time.time() - start_time
        if duration > 0.1:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [PROFILE] slow POST {self.path} ({duration:.3f}s)")

    def _handle_POST(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [POST] {self.path}")
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        # Classroom management routes (check these first to be safe)
        if path == "/api/classroom/delete":
            return self._delete_classroom()
        elif path == "/api/classroom/rebuild":
            return self._classroom_rebuild()
        elif path == "/api/classroom/wipe-curriculum":
            return self._wipe_curriculum()
        elif path == "/api/classroom/create-from-pdf":
            return self._create_classroom_from_pdf()
        elif path == "/api/classroom/create-from-scratch":
            return self._create_classroom_from_scratch()
        elif path == "/api/draft/curriculum":
            return self._draft_curriculum()
            
        # Other routes
        elif path == "/api/login":
            return self._login()
        elif path == "/api/student/login":
            return self._student_portal_login()
        elif path == "/api/student/join":
            return self._student_join_classroom()
        elif path == "/api/student/set-pin":
            return self._student_set_pin()
        elif path == "/api/student/access":
            return self._student_access_classroom()
        elif path == "/api/student/leave":
            return self._student_leave_classroom()
        elif path == "/api/register":
            return self._register()
        elif path == "/api/students/pending":
            return self._get_pending_students()
        elif path == "/api/students/approve":
            return self._approve_student()
        elif path == "/api/quiz/create":
            return self._create_quiz()
        elif path == "/api/activity/start":
            return self._activity_start()
        elif path == "/api/quiz/submit":
            return self._submit_quiz()
        elif path == "/api/activity/respond":
            return self._submit_activity_response()
        elif path == "/api/assignment/create":
            return self._create_assignment()
        elif path == "/api/assignment/submit":
            return self._submit_assignment()
        elif path == "/api/draft/generate":
            return self._draft_generate()
        elif path == "/api/draft/publish":
            return self._draft_publish()
        elif path == "/api/report/generate":
            return self._generate_report()
        elif path == "/api/session/start":
            return self._start_session()
        elif path == "/api/data/reset":
            return self._reset_data()
        elif path == "/api/student/delete":
            return self._delete_student()
        elif path == "/api/quiz/delete":
            return self._delete_quiz()
        elif path == "/api/assignment/delete":
            return self._delete_assignment()
        elif path == "/api/message/send":
            return self._message_send()
        elif path == "/api/message/read":
            return self._message_read()
        elif path == "/api/question/update":
            return self._question_update()
        elif path == "/api/question/delete":
            return self._question_delete()
        elif path == "/api/admin/hard-reset":
            return self._admin_hard_reset()
        else:
            self._send_error("Not found", 404)

    def _admin_hard_reset(self):
        """Hard delete everything. Restricted to admin emails."""
        # Simple body read to get email if needed, but we check the session/user normally
        # For simplicity in this standalone server, we'll check the provided email in the body
        body = self._read_body()
        email = body.get("email")
        confirm = body.get("confirm")

        if email != 'atunca96@gmail.com':
            return self._send_error("Unauthorized", 403)
        if confirm != "HARD DELETE EVERYTHING":
            return self._send_error("Confirmation failed")

        try:
            with db_connection() as db:
                # Drop and recreate tables is the cleanest way to 'hard delete'
                db.execute("DROP TABLE IF EXISTS messages")
                db.execute("DROP TABLE IF EXISTS student_mastery")
                db.execute("DROP TABLE IF EXISTS mastery_scores")
                db.execute("DROP TABLE IF EXISTS response_history")
                db.execute("DROP TABLE IF EXISTS responses")
                db.execute("DROP TABLE IF EXISTS quiz_questions")
                db.execute("DROP TABLE IF EXISTS quiz_results")
                db.execute("DROP TABLE IF EXISTS quizzes")
                db.execute("DROP TABLE IF EXISTS assignment_questions")
                db.execute("DROP TABLE IF EXISTS assignment_submissions")
                db.execute("DROP TABLE IF EXISTS assignments")
                db.execute("DROP TABLE IF EXISTS questions")
                db.execute("DROP TABLE IF EXISTS activities")
                db.execute("DROP TABLE IF EXISTS topics")
                db.execute("DROP TABLE IF EXISTS chapters")
                db.execute("DROP TABLE IF EXISTS enrollments")
                db.execute("DROP TABLE IF EXISTS course_enrollments")
                db.execute("DROP TABLE IF EXISTS weekly_reports")
                db.execute("DROP TABLE IF EXISTS sessions")
                db.execute("DROP TABLE IF EXISTS courses")
                db.execute("DROP TABLE IF EXISTS users")
                db.commit()
            
            # Re-initialize the database schema
            init_db()
            
            # Re-insert the admin user with the STABLE ID used in seed data ('lecturer-demo-id')
            # This ensures they remain the owner of the default '11111' class.
            with db_connection() as db:
                admin_id = "lecturer-demo-id"
                db.execute("INSERT OR REPLACE INTO users (id, name, email, password, role, status) VALUES (?, ?, ?, ?, ?, ?)",
                          (admin_id, 'Alper Tunca', 'atunca96@gmail.com', 'ALper2002@', 'lecturer', 'approved'))
                
                # Ensure the default Spanish 101 class (11111) is assigned to this admin
                db.execute("UPDATE courses SET lecturer_id = ? WHERE id = '11111'", (admin_id,))
                db.commit()

            return self._send_json({"success": True, "message": "Database reset. Admin account and Class 11111 preserved."})
        except Exception as e:
            file_log(f"HARD RESET ERROR: {e}")
            return self._send_error(f"Reset failed: {str(e)}", 500)

    def _reset_data(self):
        """Erase student data. Can be classroom-specific or global (except Spanish 101)."""
        body = self._read_body()
        confirm = body.get("confirm")
        course_id = body.get("course_id")

        if confirm != "ERASE ALL DATA":
            return self._send_error("Confirmation text does not match")

        with db_connection() as db:
            if course_id:
                # CLASSROOM SPECIFIC RESET
                db.execute("DELETE FROM responses WHERE question_id IN (SELECT id FROM questions WHERE topic_id IN (SELECT id FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id = ?)))", (course_id,))
                db.execute("DELETE FROM mastery_scores WHERE topic_id IN (SELECT id FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id = ?))", (course_id,))
                db.execute("DELETE FROM quiz_questions WHERE quiz_id IN (SELECT id FROM quizzes WHERE course_id = ?)", (course_id,))
                db.execute("DELETE FROM quizzes WHERE course_id = ?", (course_id,))
                db.execute("DELETE FROM assignment_questions WHERE assignment_id IN (SELECT id FROM assignments WHERE course_id = ?)", (course_id,))
                db.execute("DELETE FROM assignments WHERE course_id = ?", (course_id,))
                db.execute("DELETE FROM enrollments WHERE course_id = ?", (course_id,))
                db.execute("DELETE FROM messages WHERE course_id = ?", (course_id,))
                db.execute("DELETE FROM weekly_reports WHERE course_id = ?", (course_id,))
                db.execute("DELETE FROM sessions")
            else:
                # GLOBAL RESET (KEEP SPANISH 101)
                SPANISH_ID = '11111'
                db.execute("DELETE FROM responses")
                db.execute("DELETE FROM mastery_scores")
                db.execute("DELETE FROM weekly_reports")
                db.execute("DELETE FROM messages")
                db.execute("DELETE FROM sessions")
                db.execute("DELETE FROM enrollments")
                db.execute("DELETE FROM quiz_questions")
                db.execute("DELETE FROM quizzes")
                db.execute("DELETE FROM assignment_questions")
                db.execute("DELETE FROM assignments")
                db.execute("DELETE FROM users WHERE role = 'student' OR email LIKE '%@student.aulaai'")
                db.execute("DELETE FROM questions WHERE topic_id IN (SELECT t.id FROM topics t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.course_id != ?)", (SPANISH_ID,))
                db.execute("DELETE FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id != ?)", (SPANISH_ID,))
                db.execute("DELETE FROM chapters WHERE course_id != ?", (SPANISH_ID,))
                db.execute("DELETE FROM courses WHERE id != ?", (SPANISH_ID,))

            db.commit()

        bump_version()
        self._send_json({"success": True, "message": "Data has been erased."})

    def _student_leave_classroom(self):
        """Student voluntarily leaves a classroom. Removes all their data for that classroom."""
        body = self._read_body()
        student_id = body.get("student_id")
        course_id = body.get("course_id")

        if not student_id or not course_id:
            return self._send_error("Missing student_id or course_id")

        with db_connection() as db:
            # Verify enrollment exists
            enr = db.execute("SELECT 1 FROM enrollments WHERE student_id = ? AND course_id = ?", (student_id, course_id)).fetchone()
            if not enr:
                return self._send_error("Not enrolled in this classroom")

            # Delete student's responses for questions in this course
            db.execute("""
                DELETE FROM responses WHERE student_id = ? AND question_id IN (
                    SELECT q.id FROM questions q
                    JOIN topics t ON q.topic_id = t.id
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ?
                )
            """, (student_id, course_id))

            # Delete mastery scores for topics in this course
            db.execute("""
                DELETE FROM mastery_scores WHERE student_id = ? AND topic_id IN (
                    SELECT t.id FROM topics t
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ?
                )
            """, (student_id, course_id))

            # Delete messages for this student in this course
            db.execute("DELETE FROM messages WHERE student_id = ? AND course_id = ?", (student_id, course_id))

            # Delete enrollment
            db.execute("DELETE FROM enrollments WHERE student_id = ? AND course_id = ?", (student_id, course_id))

            db.commit()

        bump_version()
        self._send_json({"success": True, "message": "Left classroom successfully."})

    def _delete_student(self):
        body = self._read_body()
        student_id = body.get("student_id")
        if not student_id:
            return self._send_error("student_id required")
            
        with db_connection() as db:
            # Delete related data first
            db.execute("DELETE FROM responses WHERE student_id = ?", (student_id,))
            db.execute("DELETE FROM mastery_scores WHERE student_id = ?", (student_id,))
            db.execute("DELETE FROM enrollments WHERE student_id = ?", (student_id,))
            db.execute("DELETE FROM messages WHERE student_id = ?", (student_id,))
            db.execute("DELETE FROM users WHERE id = ? AND role = 'student'", (student_id,))
            db.commit()
        
        bump_version()
        self._send_json({"success": True})

    def _delete_quiz(self):
        body = self._read_body()
        quiz_id = body.get("quiz_id")
        if not quiz_id: return self._send_error("quiz_id required")
        with db_connection() as db:
            db.execute("DELETE FROM responses WHERE context_id = ?", (quiz_id,))
            db.execute("DELETE FROM quiz_questions WHERE quiz_id = ?", (quiz_id,))
            db.execute("DELETE FROM quizzes WHERE id = ?", (quiz_id,))
            db.commit()
        bump_version()
        self._send_json({"success": True})

    def _delete_assignment(self):
        body = self._read_body()
        assignment_id = body.get("assignment_id")
        if not assignment_id: return self._send_error("assignment_id required")
        with db_connection() as db:
            db.execute("DELETE FROM responses WHERE context_id = ?", (assignment_id,))
            db.execute("DELETE FROM assignment_questions WHERE assignment_id = ?", (assignment_id,))
            db.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
            db.commit()
        bump_version()
        self._send_json({"success": True})

    def _get_pending_students(self):
        """Lecturer only: Get students waiting for approval for a specific classroom."""
        params = parse_qs(urlparse(self.path).query)
        course_id = params.get("course_id", [None])[0]
        
        with db_connection() as db:
            if course_id:
                query = """
                    SELECT u.id, u.name, u.email, e.enrolled_at as created_at 
                    FROM users u 
                    JOIN enrollments e ON u.id = e.student_id 
                    WHERE e.course_id = ? AND e.status = 'pending' 
                    ORDER BY e.enrolled_at DESC
                """
                students = db.execute(query, (course_id,)).fetchall()
            else:
                # Fallback to global pending (legacy support)
                students = db.execute("SELECT id, name, email, created_at FROM users WHERE role = 'student' AND status = 'pending' ORDER BY created_at DESC").fetchall()
        self._send_json([dict(s) for s in students])

    def _approve_student(self):
        """Lecturer only: Approve a pending student for a specific classroom."""
        body = self._read_body()
        student_id = body.get("student_id")
        course_id = body.get("course_id")
        
        if not student_id:
            return self._send_error("student_id required")
            
        with db_connection() as db:
            if course_id:
                # Classroom-specific approval. 
                # Pin is initially NULL so student is prompted to set it on first entry.
                db.execute("UPDATE enrollments SET status = 'approved', pin = NULL WHERE student_id = ? AND course_id = ?", 
                           (student_id, course_id))
            
            # Also sync the global status for compatibility
            db.execute("UPDATE users SET status = 'approved' WHERE id = ? AND role = 'student'", (student_id,))
            db.commit()
            
        bump_version()
        self._send_json({"success": True})

    def _get_user_status(self, user_id):
        """Check current approval status for a user in a specific classroom."""
        params = parse_qs(urlparse(self.path).query)
        course_id = params.get("course_id", [None])[0]
        
        if not user_id:
            return self._send_error("user_id required")
            
        with db_connection() as db:
            user = db.execute("SELECT status FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user:
                return self._send_error("User not found", 404)

            if course_id:
                # Check if course exists first
                course = db.execute("SELECT id FROM courses WHERE id = ?", (course_id,)).fetchone()
                if not course:
                    return self._send_json({"error": "course_deleted", "status": "removed"})
                    
                enr = db.execute("SELECT status FROM enrollments WHERE student_id = ? AND course_id = ?", (user_id, course_id)).fetchone()
                if not enr:
                    return self._send_json({"error": "enrollment_removed", "status": "removed"})
                status = enr["status"]
            else:
                status = user["status"]
                
        self._send_json({"status": status or "pending"})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    # ── API Implementations ─────────────────────────────────

    def _get_ai_status(self):
        """Return whether AI (Groq) is configured and available."""
        self._send_json({
            "ai_enabled": is_ai_available(),
            "provider": "OpenRouter (Gemini 2.0 Flash)" if is_ai_available() else "Mock Engine",
            "features": {
                "dynamic_activities": is_ai_available(),
                "smart_grading": is_ai_available(),
                "ai_reports": is_ai_available()
            }
        })

    def _login(self):
        body = self._read_body()
        email = body.get("email", "")
        password = body.get("password", "")

        with db_connection() as db:
            user = db.execute("SELECT * FROM users WHERE email = ? AND password = ?",
                              (email, password)).fetchone()

        if user:
            user = dict(user)
            self._send_json({
                "success": True,
                "user": {"id": user["id"], "name": user["name"],
                         "email": user["email"], "role": user["role"], "status": user.get("status", "approved")}
            })
        else:
            self._send_error("Invalid credentials", 401)

    def _register(self):
        body = self._read_body()
        name = body.get("name", "").strip()
        email = body.get("email", "").strip()
        password = body.get("password", "").strip()

        if not name or not email or not password:
            return self._send_error("Name, email, and password are required")

        with db_connection() as db:
            existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                return self._send_error("An account with this email already exists")

            student_id = _uid()
            db.execute("INSERT INTO users (id, name, email, password, role, status, created_at) VALUES (?,?,?,?,?,?,datetime('now'))",
                       (student_id, name, email, password, "student", "pending"))

            # Auto-enroll in the first course
            course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
            if course:
                db.execute("INSERT INTO enrollments VALUES (?,?,?,datetime('now'))",
                           (_uid(), student_id, course["id"]))

            db.commit()

        bump_version()
        self._send_json({
            "success": True,
            "user": {"id": student_id, "name": name,
                     "email": email, "role": "student", "status": "pending"}
        })

    def _student_portal_login(self):
        """Phase 1: Student enters portal with number/name."""
        body = self._read_body()
        student_number = body.get("student_number", "").strip()
        name = body.get("name", "").strip()

        if not student_number:
            return self._send_error("Student number is required")
        if not name:
            return self._send_error("Name is required")

        # Use student number as the email key (internal)
        email_key = f"{student_number}@student.aulaai"
        
        with db_connection() as db:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email_key,)).fetchone()
            if not user:
                # Create global student account
                user_id = _uid()
                db.execute("INSERT INTO users (id, name, email, password, role, status, created_at) VALUES (?,?,?,?,?,?,datetime('now'))",
                           (user_id, name, email_key, "[STUDENT_PORTAL]", "student", "approved"))
                db.commit()
                user = {"id": user_id, "name": name, "email": email_key, "role": "student"}
            else:
                user = dict(user)
                if user["name"].strip().lower() != name.strip().lower():
                    return self._send_error("Student number and name do not match")
            
            # Fetch all enrollments
            enrollments = db.execute("""
                SELECT e.*, c.name as course_name, c.code as course_code, c.textbook, c.language
                FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                WHERE e.student_id = ?
            """, (user["id"],)).fetchall()
            
            self._send_json({
                "user": user,
                "enrollments": [dict(e) for e in enrollments]
            })

    def _student_join_classroom(self):
        body = self._read_body()
        student_id = body.get("student_id")
        code = body.get("code")
        
        with db_connection() as db:
            course = db.execute("SELECT id FROM courses WHERE code = ?", (code,)).fetchone()
            if not course:
                return self._send_error("Invalid classroom code")
            
            course_id = course["id"]
            existing = db.execute("SELECT id, status FROM enrollments WHERE student_id = ? AND course_id = ?", (student_id, course_id)).fetchone()
            
            if not existing:
                db.execute("INSERT INTO enrollments (id, student_id, course_id, status, enrolled_at) VALUES (?,?,?,?,datetime('now'))",
                           (_uid(), student_id, course_id, "pending"))
                db.commit()
                bump_version()
                return self._send_json({"success": True, "status": "pending"})
            else:
                return self._send_json({"success": True, "status": existing["status"]})

    def _student_set_pin(self):
        body = self._read_body()
        student_id = body.get("student_id")
        course_id = body.get("course_id")
        pin = body.get("pin")
        
        if not pin or len(pin) != 4:
            return self._send_error("PIN must be 4 digits")
            
        with db_connection() as db:
            db.execute("UPDATE enrollments SET pin = ? WHERE student_id = ? AND course_id = ? AND status = 'approved'", 
                       (pin, student_id, course_id))
            db.commit()
            
        self._send_json({"success": True})

    def _student_access_classroom(self):
        body = self._read_body()
        student_id = body.get("student_id")
        course_id = body.get("course_id")
        pin = body.get("pin")
        
        with db_connection() as db:
            enr = db.execute("SELECT pin, status FROM enrollments WHERE student_id = ? AND course_id = ?", (student_id, course_id)).fetchone()
            if not enr:
                return self._send_error("Not enrolled")
            if enr["status"] != "approved":
                return self._send_error("Not approved")
            
            if enr["pin"] != pin:
                return self._send_error("Invalid PIN")
                
            self._send_json({"success": True})


    def _get_courses(self):
        _cleanup_stale_classrooms()
        user_id = self._get_user_id()
        role = self._get_user_role()
        
        with db_connection() as db:
            courses = db.execute("SELECT * FROM courses").fetchall()
            result = []
            for c in courses:
                c_dict = dict(c)
                
                # Attach enrollment status for students
                if role == 'student':
                    enr = db.execute("SELECT status FROM enrollments WHERE student_id=? AND course_id=?", (user_id, c["id"])).fetchone()
                    c_dict["enrollment_status"] = enr["status"] if enr else "none"

                # Compute progress
                total = db.execute("""
                    SELECT COUNT(t.id) as cnt FROM topics t
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ?
                """, (c["id"],)).fetchone()["cnt"]
                
                done = db.execute("""
                    SELECT COUNT(t.id) as cnt FROM topics t
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ? AND t.content IS NOT NULL AND t.content != '' AND t.content != '{}'
                """, (c["id"],)).fetchone()["cnt"]
                
                c_dict["progress"] = (done / total) if total > 0 else 0
                result.append(c_dict)
        self._send_json(result)

    def _get_curriculum(self, course_id):
        """Fetch the full curriculum (chapters and topics) for a course."""
        with db_connection() as db:
            # If no course_id provided, or if the provided ID doesn't exist, fallback to first course
            exists = False
            if course_id:
                exists = db.execute("SELECT 1 FROM courses WHERE id=?", (course_id,)).fetchone()
            
            if not course_id or not exists:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                course_id = course["id"] if course else None
            
            if not course_id: return self._send_json([])

            chapters = db.execute(
                "SELECT * FROM chapters WHERE course_id = ? ORDER BY number", (course_id,)
            ).fetchall()

            result = []
            for ch in chapters:
                ch_dict = dict(ch)
                topics = db.execute(
                    "SELECT * FROM topics WHERE chapter_id = ? ORDER BY sort_order", (ch["id"],)
                ).fetchall()
                # Include question counts
                processed_topics = []
                for t in topics:
                    t_dict = dict(t)
                    count_row = db.execute("SELECT COUNT(*) as cnt FROM questions WHERE topic_id = ?", (t["id"],)).fetchone()
                    t_dict["question_count"] = count_row["cnt"] if count_row else 0
                    processed_topics.append(t_dict)
                ch_dict["topics"] = processed_topics
                result.append(ch_dict)
        self._send_json(result)

    def _get_students(self, course_id):
        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                course_id = course["id"] if course else None

            students = db.execute("""
                SELECT u.id, u.name, u.email, e.pin FROM users u
                JOIN enrollments e ON u.id = e.student_id
                WHERE e.course_id = ? AND e.status = 'approved'
                ORDER BY u.name
            """, (course_id,)).fetchall()

            result = []
            for s in students:
                s_dict = dict(s)
                # Get mastery scores
                masteries = db.execute(
                    "SELECT score FROM mastery_scores WHERE student_id = ?", (s["id"],)
                ).fetchall()
                if masteries:
                    scores = [m["score"] for m in masteries]
                    s_dict["avg_mastery"] = round(sum(scores) / len(scores), 3)
                else:
                    s_dict["avg_mastery"] = 0.0

                # Response count
                resp_count = db.execute(
                    "SELECT COUNT(*) as cnt FROM responses WHERE student_id = ?", (s["id"],)
                ).fetchone()["cnt"]
                s_dict["total_responses"] = resp_count

                result.append(s_dict)

        self._send_json(result)

    def _get_student_progress(self, student_id, course_id):
        if not student_id:
            return self._send_error("student_id required")

        with db_connection() as db:
            # Get mastery per topic, filtered by course
            masteries = db.execute("""
                SELECT t.title, t.type, ms.score, ch.title as chapter_title, ch.number
                FROM mastery_scores ms
                JOIN topics t ON ms.topic_id = t.id
                JOIN chapters ch ON t.chapter_id = ch.id
                WHERE ms.student_id = ? AND ch.course_id = ?
                ORDER BY ch.number, t.sort_order
            """, (student_id, course_id)).fetchall()

            # Recent responses filtered by course
            responses = db.execute("""
                SELECT r.score, r.submitted_at, q.prompt, q.type as question_type
                FROM responses r
                JOIN questions q ON r.question_id = q.id
                JOIN topics t ON q.topic_id = t.id
                JOIN chapters ch ON t.chapter_id = ch.id
                WHERE r.student_id = ? AND ch.course_id = ?
                ORDER BY r.submitted_at DESC LIMIT 20
            """, (student_id, course_id)).fetchall()

        self._send_json({
            "masteries": [dict(m) for m in masteries],
            "recent_responses": [dict(r) for r in responses],
        })

    def _get_questions(self, topic_id):
        if not topic_id:
            return self._send_error("topic_id required")

        with db_connection() as db:
            questions = db.execute(
                "SELECT * FROM questions WHERE topic_id = ? AND approved = 1", (topic_id,)
            ).fetchall()

        result = []
        import random
        for q in questions:
            q_dict = dict(q)
            if q_dict.get("distractors"):
                try:
                    dist = json.loads(q_dict["distractors"])
                    q_dict["distractors"] = dist
                    # Build the options field for the UI
                    opts = [q_dict["answer"]] + dist
                    random.shuffle(opts)
                    q_dict["options"] = opts
                except Exception:
                    q_dict["distractors"] = []
                    q_dict["options"] = [q_dict["answer"]]
            else:
                q_dict["distractors"] = []
                q_dict["options"] = [q_dict["answer"]]
            result.append(q_dict)

        self._send_json(result)

    def _question_update(self):
        body = self._read_body()
        qid = body.get("id")
        prompt = body.get("prompt")
        answer = body.get("answer")
        distractors = body.get("distractors", [])
        
        with db_connection() as db:
            db.execute("""
                UPDATE questions 
                SET prompt = ?, answer = ?, distractors = ?
                WHERE id = ?
            """, (prompt, answer, json.dumps(distractors), qid))
            db.commit()
        
        bump_version()
        return self._send_json({"success": True})

    def _question_delete(self):
        body = self._read_body()
        qid = body.get("id")
        with db_connection() as db:
            db.execute("DELETE FROM questions WHERE id = ?", (qid,))
            db.commit()
        
        bump_version()
        return self._send_json({"success": True})

    def _activity_start(self):
        file_log("DEBUG: _activity_start endpoint reached")
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            post_data = json.loads(self.rfile.read(content_len).decode("utf-8"))
            topic_id = post_data.get("topic_id")
            course_id = post_data.get("course_id")
            count = int(post_data.get("count", 6))
            
            if not topic_id or not course_id:
                return self._send_error("Missing info")
                
            # Initialize progress
            with db_connection() as db:
                db.execute("""
                    UPDATE courses 
                    SET activity_status='generating', activity_progress=0, activity_total=100, activity_result=NULL
                    WHERE id=?
                """, (course_id,))
                db.commit()
                
            # Start background thread
            import threading
            file_log(f"Starting background generation for course {course_id}, topic {topic_id}")
            thread = threading.Thread(target=self._bg_generate_activities, args=(course_id, topic_id, count))
            thread.daemon = True
            thread.start()
            
            # Final check to ensure status is set
            with db_connection() as db:
                db.execute("UPDATE courses SET activity_status='generating' WHERE id=?", (course_id,))
                db.commit()
            
            self._send_json({"status": "success"})
        except Exception as e:
            print(f"[ERROR] _activity_start failed: {e}")
            import traceback
            traceback.print_exc()
            self._send_error(str(e))

    def _bg_generate_activities(self, course_id, topic_id, count):
        try:
            def update_prog(p, status='generating'):
                # Retry loop for DB locks
                for retry in range(5):
                    try:
                        with db_connection() as db_c:
                            db_c.execute("""
                                UPDATE courses 
                                SET activity_progress=?, activity_status=? 
                                WHERE id=?
                            """, (p, status, course_id))
                            db_c.commit()
                        return
                    except Exception:
                        time.sleep(0.5)

            print(f"[BG] Topic {topic_id}: Wiping entire question database to make room for fresh strict generation.")
            with db_connection() as db:
                db.execute("DELETE FROM responses")
                db.execute("DELETE FROM quiz_questions")
                db.execute("DELETE FROM assignment_questions")
                db.execute("DELETE FROM questions")
                db.commit()

            with db_connection() as db:
                # 1. Fresh fetch (should be empty now)
                rows = db.execute("SELECT id, type, prompt, answer, distractors FROM questions WHERE topic_id = ?", (topic_id,)).fetchall()
                existing_questions = []
                import random
                for r in rows:
                    q = dict(r)
                    try:
                        q["distractors"] = json.loads(q["distractors"])
                    except:
                        q["distractors"] = []
                    
                    # VITAL: Re-assemble the options for the frontend
                    all_opts = [q["answer"]] + q["distractors"]
                    random.shuffle(all_opts)
                    q["options"] = all_opts
                    
                    existing_questions.append(q)
                
                # Check for capacity limit
                if len(existing_questions) >= 30:
                    print(f"[BG] Topic {topic_id} is at max capacity (30). Returning existing pool.")
                    # Satisfy frontend by providing the existing results
                    update_prog(100, status='done')
                    with db_connection() as db_c:
                        db_c.execute("UPDATE courses SET activity_result=? WHERE id=?", (json.dumps(existing_questions), course_id))
                        db_c.commit()
                    return

                row = db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
                if not row:
                    print(f"[ERROR] Topic {topic_id} not found in DB")
                    raise Exception(f"Topic {topic_id} not found")
                topic = dict(row)
                row_c = db.execute("SELECT language FROM courses WHERE id=?", (course_id,)).fetchone()
                language = row_c["language"] if row_c else "Spanish"
            
            print(f"[BG] Starting CUMULATIVE activity generation for {topic['title']} ({language})")
            file_log(f"Starting CUMULATIVE generation for {topic['title']}")

            # Starting...
            update_prog(5)
            
            content = json.loads(topic["content"]) if isinstance(topic.get("content"), str) else topic.get("content", {})
            topic_type = topic.get("type", "vocabulary")

            # Start a simulated progress ticker to keep the bar moving
            import threading
            stop_ticker = threading.Event()
            def progress_ticker():
                p = 5
                while not stop_ticker.is_set() and p < 90:
                    time.sleep(0.6) # Faster ticks for better feedback
                    # Increment more aggressively to reach ~80% in 5-8 seconds
                    p += py_random.randint(5, 12)
                    if p > 90: p = 90
                    update_prog(p)
            
            ticker_thread = threading.Thread(target=progress_ticker, daemon=True)
            ticker_thread.start()
            
            try:
                # Call the unified batch engine with knowledge of existing questions
                raw_activities = ai_generate_activity_batch(
                    topic["title"], 
                    topic_type, 
                    content, 
                    language, 
                    count=count, 
                    level=topic.get("difficulty", "A1"),
                    existing_questions=existing_questions
                ) or []
            finally:
                stop_ticker.set()
                ticker_thread.join(timeout=1.0)

            update_prog(95)

            update_prog(100) # Finished AI work
            
            final_activities = []
            for act in raw_activities:
                if not act or not isinstance(act, dict): continue
                
                # Normalization Layer: Ensure frontend gets exactly what it expects
                atype = act.get("type", "mcq")
                
                # 1. MCQ Normalization
                if atype == 'mcq':
                    ans = act.get("answer", "")
                    dist = act.get("distractors", [])
                    if not isinstance(dist, list): dist = [str(dist)]
                    
                    # Ensure answer is not in distractors
                    dist = [d for d in dist if str(d).strip().lower() != str(ans).strip().lower()]
                    act["distractors"] = dist[:3]
                    
                    if not act.get("options") or not isinstance(act["options"], list) or len(act["options"]) < 2:
                        # Combine answer + distractors if AI used the old format or missed options
                        opts = [ans] + dist
                        py_random.shuffle(opts)
                        act["options"] = opts
                    
                    # Final check: if still no options or no prompt, discard
                    if not act.get("options") or not act.get("prompt"):
                        file_log(f"Discarding broken MCQ: {json.dumps(act)}")
                        continue
                
                # 2. Dialogue Normalization
                if atype == 'dialogue_order':
                    if not act.get("scrambled_lines") and act.get("lines"):
                        act["scrambled_lines"] = act.get("lines")
                    
                    if not act.get("scrambled_lines") or not isinstance(act["scrambled_lines"], list):
                        file_log(f"Discarding broken dialogue: {json.dumps(act)}")
                        continue

                    if not act.get("correct_order"):
                        if act.get("answer"):
                            # If AI sent indices, convert to actual lines
                            if isinstance(act["answer"], list) and len(act["answer"]) > 0 and isinstance(act["answer"][0], int):
                                lines = act.get("scrambled_lines", [])
                                act["correct_order"] = [lines[i] for i in act["answer"] if i < len(lines)]
                            else:
                                act["correct_order"] = act.get("answer")
                        else:
                            # Try to use the original order if it's there
                            act["correct_order"] = act.get("scrambled_lines")
                
                act["id"] = _uid()
                # Ensure distractors and answer are clean string types for the DB
                if 'distractors' in act and isinstance(act['distractors'], list):
                    act['distractors'] = [str(d) for d in act['distractors']]
                
                final_activities.append(act)
            
            # Done!
            print(f"[BG] [{course_id}] Saving {len(final_activities)} activities...")
            try:
                with db_connection() as db:
                    # Mark existing questions as unapproved to avoid conflicts/overwrites
                    db.execute("UPDATE questions SET approved = 0 WHERE topic_id = ?", (topic_id,))
                    
                    db.execute("""
                        UPDATE courses 
                        SET activity_status='done', activity_result=? 
                        WHERE id=?
                    """, (json.dumps(final_activities), course_id))
                    
                    # Also save to questions table for future retrieval
                    for act in final_activities:
                        q_id = _uid()
                        a_type = act.get("type", "mcq")
                        a_prompt = json.dumps(act.get("prompt", ""), ensure_ascii=False) if isinstance(act.get("prompt"), (list, dict)) else str(act.get("prompt", ""))
                        a_answer = json.dumps(act.get("answer", ""), ensure_ascii=False) if isinstance(act.get("answer"), (list, dict)) else str(act.get("answer", ""))
                        distractors = json.dumps(act.get("distractors", []))
                        db.execute("""
                            INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, approved) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                        """, (q_id, topic_id, a_type, a_prompt, a_answer, distractors, "A1.1"))
                    db.commit()
                print(f"[BG] [{course_id}] Save SUCCESSFUL")
            except Exception as e:
                print(f"[ERROR] [{course_id}] Final save failed: {e}")
                file_log(f"Final Save Error: {e}")
                # We still set it to done if we have activities in memory, so the UI can show them
                if final_activities:
                     with db_connection() as db:
                        db.execute("UPDATE courses SET activity_status='done', activity_result=? WHERE id=?", 
                                   (json.dumps(final_activities), course_id))
                        db.commit()
                else:
                    raise e
                
        except Exception as e:
            file_log(f"BG Activity Error: {str(e)}")
            import traceback
            file_log(traceback.format_exc())
            with db_connection() as db:
                db.execute("UPDATE courses SET activity_status='error' WHERE id=?", (course_id,))
                db.commit()

    def _activity_progress(self, course_id):
        if not course_id:
            return self._send_json({"status": "error", "percentage": 0, "message": "Missing course_id"})

        with db_connection() as db:
            row = db.execute("SELECT activity_status, activity_progress, activity_total, activity_result FROM courses WHERE id=?", (course_id,)).fetchone()
            if not row:
                return self._send_json({"status": "error", "percentage": 0, "message": "Course not found"})
            
            data = dict(row)
            status = data.get("activity_status", "idle")
            progress = data.get("activity_progress", 0)
            total = data.get("activity_total") or 100
            
            if total <= 0: total = 100
            percent = min(100, int((progress / total) * 100))
            
            self._send_json({
                "status": status,
                "percentage": percent,
                "results": json.loads(data["activity_result"]) if data["activity_result"] else None
            })

    def _draft_progress(self, course_id):
        if not course_id:
            return self._send_json({"status": "error", "percentage": 0, "message": "Missing course_id"})

        with db_connection() as db:
            row = db.execute("SELECT draft_status, draft_progress, draft_result FROM courses WHERE id=?", (course_id,)).fetchone()
            if not row:
                return self._send_json({"status": "error", "percentage": 0, "message": "Course not found"})
            
            data = dict(row)
            status = data.get("draft_status", "idle")
            progress = data.get("draft_progress", 0)
            
            self._send_json({
                "status": status,
                "percentage": progress,
                "questions": json.loads(data["draft_result"]) if data["draft_result"] else None
            })

    def _get_quizzes(self, course_id, student_id=None):
        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                course_id = course["id"] if course else None

            quizzes = db.execute(
                "SELECT * FROM quizzes WHERE course_id = ? ORDER BY created_at DESC", (course_id,)
            ).fetchall()
            
            result = []
            for q in quizzes:
                q_dict = dict(q)
                if student_id:
                    completed = db.execute(
                        "SELECT 1 FROM responses WHERE student_id = ? AND context_id = ? LIMIT 1",
                        (student_id, q["id"])
                    ).fetchone()
                    q_dict["is_completed"] = True if completed else False
                result.append(q_dict)

        self._send_json(result)

    def _get_quiz(self, quiz_id, student_id=None):
        if not quiz_id:
            return self._send_error("quiz_id required")

        with db_connection() as db:
            quiz = db.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
            if not quiz:
                return self._send_error("Quiz not found", 404)

            questions = db.execute("""
                SELECT q.* FROM questions q
                JOIN quiz_questions qq ON q.id = qq.question_id
                WHERE qq.quiz_id = ?
                ORDER BY qq.sort_order
            """, (quiz_id,)).fetchall()

            if student_id:
                # Check if already started or completed
                existing = db.execute("SELECT 1 FROM responses WHERE student_id = ? AND context_id = ? AND context_type = 'quiz' LIMIT 1", (student_id, quiz_id)).fetchone()
                if existing:
                    return self._send_error("Quiz already taken or in progress. You cannot retake it.", 403)
                
                # Lock it by inserting 0 score for all questions
                for q in questions:
                    db.execute("INSERT INTO responses (id, student_id, question_id, context_type, context_id, answer, score, graded_by, submitted_at) VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
                               (_uid(), student_id, q["id"], "quiz", quiz_id, "[STARTED]", 0.0, "auto"))
                db.commit()

            result = dict(quiz)
            result["questions"] = []
            import random
            for q in questions:
                q_dict = dict(q)
                if q_dict.get("distractors"):
                    try:
                        dist = json.loads(q_dict["distractors"])
                        q_dict["distractors"] = dist
                        # Build options for UI
                        opts = [q_dict["answer"]] + dist
                        random.shuffle(opts)
                        q_dict["options"] = opts
                    except Exception:
                        q_dict["distractors"] = []
                        q_dict["options"] = [q_dict["answer"]]
                else:
                    q_dict["distractors"] = []
                    q_dict["options"] = [q_dict["answer"]]
                result["questions"].append(q_dict)

        self._send_json(result)

    def _get_quiz_responses(self, quiz_id):
        """Get all student responses for a given quiz, grouped by student."""
        if not quiz_id:
            return self._send_error("quiz_id required")

        with db_connection() as db:
            quiz = db.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
            if not quiz:
                return self._send_error("Quiz not found", 404)

            questions = db.execute("""
                SELECT q.id, q.prompt, q.answer, q.type, q.distractors
                FROM questions q
                JOIN quiz_questions qq ON q.id = qq.question_id
                WHERE qq.quiz_id = ?
                ORDER BY qq.sort_order
            """, (quiz_id,)).fetchall()
            questions_list = []
            for row in questions:
                q = dict(row)
                if q["id"] in [sq["id"] for sq in questions_list]: continue
                if q["distractors"]:
                    q["distractors"] = json.loads(q["distractors"])
                questions_list.append(q)

            responses = db.execute("""
                SELECT r.student_id, r.question_id, r.answer AS student_answer,
                       r.score, r.feedback, r.submitted_at,
                       u.name AS student_name,
                       q.prompt, q.answer AS correct_answer, q.type AS question_type
                FROM responses r
                JOIN users u ON r.student_id = u.id
                JOIN questions q ON r.question_id = q.id
                WHERE r.context_type = 'quiz' AND r.context_id = ?
                ORDER BY u.name, r.submitted_at
            """, (quiz_id,)).fetchall()

            students_map = {}
            for r in responses:
                r_dict = dict(r)
                sid = r_dict["student_id"]
                if sid not in students_map:
                    students_map[sid] = {
                        "student_id": sid,
                        "student_name": r_dict["student_name"],
                        "answers": [],
                        "total_score": 0,
                        "total_questions": 0
                    }
                students_map[sid]["answers"].append({
                    "question_id": r_dict["question_id"],
                    "prompt": r_dict["prompt"],
                    "student_answer": r_dict["student_answer"],
                    "correct_answer": r_dict["correct_answer"],
                    "score": r_dict["score"],
                    "is_correct": r_dict["score"] >= 0.8,
                    "submitted_at": r_dict["submitted_at"]
                })
                students_map[sid]["total_score"] += r_dict["score"]
                students_map[sid]["total_questions"] += 1

            student_results = []
            for sid, sdata in students_map.items():
                sdata["average_score"] = round(sdata["total_score"] / max(sdata["total_questions"], 1), 3)
                student_results.append(sdata)
            student_results.sort(key=lambda x: x["student_name"])

        self._send_json({
            "quiz": dict(quiz),
            "questions": questions_list,
            "student_results": student_results,
            "total_students": len(student_results)
        })

    def _create_quiz(self):
        body = self._read_body()
        course_id = body.get("course_id")
        chapter_id = body.get("chapter_id")
        title = body.get("title", "Quiz")
        
        count_val = body.get("count")
        try:
            count = int(count_val) if count_val is not None else 10
        except (ValueError, TypeError):
            count = 10

        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                if course: course_id = course["id"]

            topic_id = body.get("topic_id")
            if topic_id:
                topic_ids = [topic_id]
            elif chapter_id and chapter_id != "all":
                topics = db.execute("SELECT id FROM topics WHERE chapter_id = ?", (chapter_id,)).fetchall()
                topic_ids = list(set(t["id"] for t in topics))
            else:
                topics = db.execute("""
                    SELECT t.id FROM topics t
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ?
                """, (course_id,)).fetchall()
                topic_ids = list(set(t["id"] for t in topics))

        from services.content_engine import generate_quiz
        questions = generate_quiz(topic_ids, count=count)

        quiz_id = _uid()
        with db_connection() as db:
            db.execute("INSERT INTO quizzes VALUES (?,?,?,?,datetime('now'),datetime('now','+1 day'),15,datetime('now'))",
                       (quiz_id, course_id, title, None if chapter_id == "all" else chapter_id))

            for i, q in enumerate(questions):
                db.execute("INSERT OR IGNORE INTO quiz_questions VALUES (?,?,?)",
                           (quiz_id, q["id"], i))
            db.commit()
        bump_version()
        self._send_json({"quiz_id": quiz_id, "question_count": len(questions)})

    def _draft_generate(self):
        body = self._read_body()
        course_id = body.get("course_id")
        chapter_id = body.get("chapter_id")
        try:
            count = int(body.get("count", 10))
        except (ValueError, TypeError):
            count = 10
            
        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                if course: course_id = course["id"]
                
            if chapter_id and chapter_id != "all":
                topics = db.execute("SELECT id FROM topics WHERE chapter_id = ?", (chapter_id,)).fetchall()
            else:
                topics = db.execute("""
                    SELECT t.id FROM topics t
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ?
                """, (course_id,)).fetchall()
                
            topic_ids = [t["id"] for t in topics]
            
        # Start background thread for generation
            import threading
            with db_connection() as db:
                db.execute("UPDATE courses SET draft_status='generating', draft_progress=0, draft_result=NULL WHERE id=?", (course_id,))
                db.commit()
                
            thread = threading.Thread(target=self._bg_generate_draft, args=(course_id, topic_ids, count))
            thread.daemon = True
            thread.start()
            
            self._send_json({"status": "success"})

    def _bg_generate_draft(self, course_id, topic_ids, count):
        try:
            from services.content_engine import generate_quiz
            
            def update_draft_prog(p):
                for retry in range(5):
                    try:
                        with db_connection() as db:
                            db.execute("UPDATE courses SET draft_progress=? WHERE id=?", (p, course_id))
                            db.commit()
                        return
                    except Exception: time.sleep(0.5)

            update_draft_prog(10)
            
            # EXORCISM: Clear out old unfiltered questions for these topics before starting
            with db_connection() as db:
                for tid in topic_ids:
                    db.execute("DELETE FROM questions WHERE topic_id = ?", (tid,))
                db.commit()
            
            try:
                questions = generate_quiz(topic_ids, count=count, progress_callback=update_draft_prog)
            finally:
                pass

            result = []
            for q in questions:
                q_dict = dict(q)
                if isinstance(q_dict.get("distractors"), str):
                    try: q_dict["distractors"] = json.loads(q_dict["distractors"])
                    except: q_dict["distractors"] = []
                
                if isinstance(q_dict.get("distractors"), list):
                    q_dict["distractors"] = [d for d in q_dict["distractors"] if isinstance(d, str) and d.strip()]
                else: q_dict["distractors"] = []
                result.append(q_dict)

            with db_connection() as db:
                db.execute("UPDATE courses SET draft_status='done', draft_progress=100, draft_result=? WHERE id=?", (json.dumps(result), course_id))
                db.commit()
                
        except Exception as e:
            file_log(f"BG Draft Error: {e}")
            with db_connection() as db:
                db.execute("UPDATE courses SET draft_status='error' WHERE id=?", (course_id,))
                db.commit()

    def _draft_publish(self):
        body = self._read_body()
        pub_type = body.get("type", "quiz") # quiz or assignment
        course_id = body.get("course_id")
        chapter_id = body.get("chapter_id")
        title = body.get("title", "Draft")
        due_at = body.get("due_at")
        questions = body.get("questions", [])

        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                if course: course_id = course["id"]
                
            pub_id = _uid()
            if pub_type == "quiz":
                db.execute("INSERT INTO quizzes VALUES (?,?,?,?,datetime('now'),datetime('now','+1 day'),15,datetime('now'))",
                           (pub_id, course_id, title, None if chapter_id == "all" else chapter_id))
            else:
                db.execute("INSERT INTO assignments VALUES (?,?,?,?,?,datetime('now'))",
                           (pub_id, course_id, title, None if chapter_id == "all" else chapter_id, due_at))
                
            seen_ids = set()
            for i, q in enumerate(questions):
                qid = q.get("id")
                if not qid or str(qid).startswith("new_") or qid in seen_ids:
                    qid = _uid()
                    topic_id = None
                    if chapter_id and chapter_id != "all":
                        t = db.execute("SELECT id FROM topics WHERE chapter_id = ? LIMIT 1", (chapter_id,)).fetchone()
                        if t: topic_id = t["id"]
                    if not topic_id:
                        t = db.execute("SELECT id FROM topics LIMIT 1").fetchone()
                        if t: topic_id = t["id"]
                        
                    distractors = q.get("distractors", [])
                    if isinstance(distractors, str):
                        distractors = [d.strip() for d in distractors.split(",") if d.strip()]
                    db.execute("INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, metadata, approved, created_at) VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
                               (qid, topic_id, q.get("type", "mcq"), q.get("prompt"), q.get("answer"),
                                json.dumps(distractors), "custom", "{}", 1))
                
                if qid not in seen_ids:
                    seen_ids.add(qid)
                    if pub_type == "quiz":
                        db.execute("INSERT OR IGNORE INTO quiz_questions VALUES (?,?,?)", (pub_id, qid, len(seen_ids)-1))
                    else:
                        db.execute("INSERT OR IGNORE INTO assignment_questions VALUES (?,?,?)", (pub_id, qid, len(seen_ids)-1))
            
            db.commit()
        bump_version()
        self._send_json({"id": pub_id, "title": title, "question_count": len(questions)})

    def _submit_quiz(self):
        body = self._read_body()
        quiz_id = body.get("quiz_id")
        student_id = body.get("student_id")
        answers = body.get("answers", {})  # {question_id: answer}

        with db_connection() as db:
            results = []
            total_score = 0

            for qid, student_answer in answers.items():
                question = db.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
                if not question:
                    continue

                score, feedback = grade_response(question["type"], student_answer, question["answer"])
                total_score += score

                existing_resp = db.execute("SELECT id FROM responses WHERE student_id = ? AND context_id = ? AND question_id = ?", (student_id, quiz_id, qid)).fetchone()
                if existing_resp:
                    db.execute("UPDATE responses SET answer = ?, score = ?, feedback = ?, submitted_at = datetime('now') WHERE id = ?",
                               (student_answer, score, feedback, existing_resp["id"]))
                else:
                    db.execute("INSERT INTO responses VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
                               (_uid(), student_id, qid, "quiz", quiz_id,
                                student_answer, score, "auto", feedback))

                topic_id = question["topic_id"]
                existing = db.execute(
                    "SELECT score FROM mastery_scores WHERE student_id = ? AND topic_id = ?",
                    (student_id, topic_id)
                ).fetchone()

                current_score = existing["score"] if (existing and existing["score"] is not None) else score
                new_score = (current_score * 0.7 + score * 0.3)
                db.execute("""
                    INSERT OR REPLACE INTO mastery_scores (id, student_id, topic_id, score, updated_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                """, (_uid(), student_id, topic_id, round(new_score, 3)))

                results.append({
                    "question_id": qid,
                    "score": score,
                    "feedback": feedback,
                    "correct_answer": question["answer"]
                })

            db.commit()

        bump_version()
        avg = total_score / max(len(answers), 1)
        self._send_json({
            "total_score": round(total_score, 2),
            "average": round(avg, 3),
            "results": results,
            "question_count": len(answers)
        })

    def _submit_activity_response(self):
        body = self._read_body()
        student_id = body.get("student_id")
        question_id = body.get("question_id")
        answer = body.get("answer", "")
        correct_answer = body.get("correct_answer", "")
        question_type = body.get("question_type", "mcq")

        score, feedback = grade_response(question_type, answer, correct_answer)

        if student_id and question_id:
            with db_connection() as db:
                db.execute("INSERT INTO responses VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
                           (_uid(), student_id, question_id, "practice", _uid(),
                            answer, score, "auto", feedback))
                q = db.execute("SELECT topic_id FROM questions WHERE id = ?", (question_id,)).fetchone()
                if q:
                    tid = q["topic_id"]
                    existing = db.execute(
                        "SELECT score FROM mastery_scores WHERE student_id = ? AND topic_id = ?",
                        (student_id, tid)
                    ).fetchone()
                    new_score = score if not existing else (existing["score"] * 0.7 + score * 0.3)
                    db.execute("INSERT OR REPLACE INTO mastery_scores (id, student_id, topic_id, score, updated_at) VALUES (?,?,?,?,datetime('now'))",
                               (_uid(), student_id, tid, round(new_score, 3)))
                db.commit()

        bump_version()
        self._send_json({"score": score, "feedback": feedback})

    def _get_student_stats(self, student_id, course_id):
        if not student_id: return self._send_error("ID required")
        with db_connection() as db:
            stats = {
                "quizzes": db.execute("""
                    SELECT COUNT(DISTINCT r.context_id) 
                    FROM responses r
                    JOIN quizzes qz ON r.context_id = qz.id
                    WHERE r.student_id = ? AND r.context_type = 'quiz' AND qz.course_id = ?
                """, (student_id, course_id)).fetchone()[0],
                "practice": db.execute("""
                    SELECT COUNT(*) 
                    FROM responses r
                    JOIN topics t ON r.context_id = t.id
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE r.student_id = ? AND r.context_type = 'practice' AND ch.course_id = ?
                """, (student_id, course_id)).fetchone()[0],
                "assignments": db.execute("""
                    SELECT COUNT(DISTINCT r.context_id) 
                    FROM responses r
                    JOIN assignments a ON r.context_id = a.id
                    WHERE r.student_id = ? AND r.context_type = 'assignment' AND a.course_id = ?
                """, (student_id, course_id)).fetchone()[0],
            }
        self._send_json(stats)

    def _get_report(self, course_id):
        with db_connection() as db:
            if not course_id or course_id == 'null':
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                course_id = course["id"] if course else None
            
            if not course_id:
                return self._send_json({"error": "No course found"})
                
            report = generate_weekly_report(db, course_id)
        self._send_json(report)

    def _generate_report(self):
        body = self._read_body()
        course_id = body.get("course_id")

        with db_connection() as db:
            if not course_id or course_id == 'null':
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                course_id = course["id"] if course else None
            
            if not course_id:
                return self._send_json({"error": "No course found"})
                
            report = generate_weekly_report(db, course_id)

        # Enhance with AI insights if available
        if is_ai_available():
            try:
                ai_insights = ai_generate_report_insights({
                    "total_students": report.get("summary", {}).get("total_students", 0),
                    "class_avg_mastery": report.get("summary", {}).get("class_avg_mastery", 0),
                    "at_risk_count": report.get("summary", {}).get("at_risk_count", 0),
                    "review_topics": report.get("review_topics", []),
                    "at_risk_students": [s["name"] for s in report.get("at_risk_students", [])]
                })
                if ai_insights:
                    report["ai_insights"] = ai_insights
            except Exception as e:
                print(f"[AI] Report insights error: {e}")

        self._send_json(report)

    def _start_session(self):
        body = self._read_body()
        course_id = body.get("course_id")
        chapter_id = body.get("chapter_id")
        topic_id = body.get("topic_id")

        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                course_id = course["id"]
            session_id = _uid()
            db.execute("INSERT INTO sessions VALUES (?,?,?,date('now'),'active',datetime('now'),NULL)",
                       (session_id, course_id, chapter_id))
            db.commit()
            if topic_id:
                topic = db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
                row = db.execute("""
                    SELECT co.language FROM courses co
                    JOIN chapters ch ON co.id = ch.course_id
                    JOIN topics t ON ch.id = t.chapter_id
                    WHERE t.id = ?
                """, (topic_id,)).fetchone()
                language = row["language"] if row and row["language"] else "Unknown"
                activities = generate_activity(dict(topic), count=8, language=language) if topic else []
            else:
                activities = []

        self._send_json({
            "session_id": session_id,
            "status": "active",
            "activities": activities
        })

    def _create_assignment(self):
        body = self._read_body()
        course_id = body.get("course_id")
        chapter_id = body.get("chapter_id")
        if not chapter_id:
            chapter_id = None

        title = body.get("title", "Assignment")
        due_at = body.get("due_at")
        
        count_val = body.get("count")
        try:
            count = max(3, min(50, int(count_val) if count_val is not None else 10))
        except (ValueError, TypeError):
            count = 10

        assignment_id = _uid()
        topic_id = body.get("topic_id")
        topic_ids = []

        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                if course:
                    course_id = course["id"]
                else:
                    return self._send_error("No courses found")

            # Create assignment entry first
            db.execute("INSERT INTO assignments VALUES (?,?,?,?,?,datetime('now'))",
                       (assignment_id, course_id, title, None if chapter_id == "all" else chapter_id, due_at))

            if topic_id:
                topic_ids = [topic_id]
            elif chapter_id and chapter_id != "all":
                topics = db.execute("SELECT id FROM topics WHERE chapter_id = ?", (chapter_id,)).fetchall()
                topic_ids = [t["id"] for t in topics]
            else:
                topics = db.execute("""
                    SELECT t.id FROM topics t
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ?
                """, (course_id,)).fetchall()
                topic_ids = [t["id"] for t in topics]
            db.commit()

        from services.content_engine import generate_quiz
        questions = generate_quiz(topic_ids, count=count)
        
        with db_connection() as db:
            for i, q in enumerate(questions):
                db.execute("INSERT OR IGNORE INTO assignment_questions VALUES (?,?,?)",
                           (assignment_id, q["id"], i))
            db.commit()

        bump_version()
        self._send_json({"assignment_id": assignment_id, "title": title, "question_count": len(questions)})

    def _get_assignment_responses(self, assignment_id):
        """Return all student responses for a specific assignment, grouped by student."""
        if not assignment_id:
            return self._send_error("assignment_id required")

        with db_connection() as db:
            assignment = db.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
            if not assignment:
                return self._send_error("Assignment not found", 404)

            questions = db.execute("""
                SELECT q.id, q.prompt, q.answer, q.type FROM questions q
                JOIN assignment_questions aq ON q.id = aq.question_id
                WHERE aq.assignment_id = ?
                ORDER BY aq.sort_order
            """, (assignment_id,)).fetchall()
            question_map = {q["id"]: dict(q) for q in questions}

            rows = db.execute("""
                SELECT r.student_id, r.question_id, r.answer AS student_answer, r.score,
                       u.name AS student_name
                FROM responses r
                JOIN users u ON r.student_id = u.id
                WHERE r.context_type = 'assignment' AND r.context_id = ?
                ORDER BY u.name, r.submitted_at
            """, (assignment_id,)).fetchall()

            students = {}
            for row in rows:
                sid = row["student_id"]
                if sid not in students:
                    students[sid] = {
                        "student_id": sid,
                        "student_name": row["student_name"],
                        "answers": [],
                        "total_score": 0,
                        "answered": 0
                    }
                q = question_map.get(row["question_id"], {})
                students[sid]["answers"].append({
                    "question_id": row["question_id"],
                    "prompt": q.get("prompt", ""),
                    "correct_answer": q.get("answer", ""),
                    "student_answer": row["student_answer"],
                    "score": row["score"],
                    "is_correct": row["score"] >= 0.8
                })
                students[sid]["total_score"] += row["score"]
                students[sid]["answered"] += 1

            result = []
            for s in students.values():
                s["average_score"] = round(s["total_score"] / max(s["answered"], 1), 3)
                s["total_questions"] = len(question_map)
                result.append(s)

        self._send_json({
            "assignment_id": assignment_id,
            "title": assignment["title"],
            "total_questions": len(question_map),
            "student_results": sorted(result, key=lambda x: x["average_score"], reverse=True)
        })

    def _get_assignments(self, course_id, student_id=None):
        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                course_id = course["id"] if course else None
            assignments = db.execute("SELECT * FROM assignments WHERE course_id = ? ORDER BY created_at DESC", (course_id,)).fetchall()
            result = []
            for a in assignments:
                a_dict = dict(a)
                if student_id:
                    completed = db.execute("SELECT 1 FROM responses WHERE student_id = ? AND context_id = ? AND context_type = 'assignment' LIMIT 1", (student_id, a["id"])).fetchone()
                    a_dict["is_completed"] = True if completed else False
                result.append(a_dict)
        self._send_json(result)

    def _get_assignment(self, assignment_id, student_id=None):
        with db_connection() as db:
            assignment = db.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
            if not assignment:
                return self._send_error("Assignment not found", 404)
            questions = db.execute("""
                SELECT q.* FROM questions q
                JOIN assignment_questions aq ON q.id = aq.question_id
                WHERE aq.assignment_id = ?
                ORDER BY aq.sort_order
            """, (assignment_id,)).fetchall()

            if student_id:
                existing = db.execute("SELECT 1 FROM responses WHERE student_id = ? AND context_id = ? AND context_type = 'assignment' LIMIT 1", (student_id, assignment_id)).fetchone()
                if existing:
                    return self._send_error("Assignment already taken or in progress. You cannot retake it.", 403)
                
                for q in questions:
                    db.execute("INSERT INTO responses (id, student_id, question_id, context_type, context_id, answer, score, graded_by, submitted_at) VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
                               (_uid(), student_id, q["id"], "assignment", assignment_id, "[STARTED]", 0.0, "auto"))
                db.commit()

            result = dict(assignment)
            result["questions"] = []
            for q in questions:
                q_dict = dict(q)
                if q_dict.get("distractors"):
                    try:
                        q_dict["distractors"] = json.loads(q_dict["distractors"])
                    except Exception:
                        q_dict["distractors"] = []
                result["questions"].append(q_dict)
        self._send_json(result)

    def _submit_assignment(self):
        body = self._read_body()
        aid = body.get("assignment_id")
        student_id = body.get("student_id")
        answers = body.get("answers", {})

        with db_connection() as db:
            total_score = 0
            results = []
            for qid, student_answer in answers.items():
                question = db.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
                if not question: continue
                score, feedback = grade_response(question["type"], student_answer, question["answer"])
                total_score += score
                existing_resp = db.execute("SELECT id FROM responses WHERE student_id = ? AND context_id = ? AND question_id = ?", (student_id, aid, qid)).fetchone()
                if existing_resp:
                    db.execute("UPDATE responses SET answer = ?, score = ?, feedback = ?, submitted_at = datetime('now') WHERE id = ?",
                               (student_answer, score, feedback, existing_resp["id"]))
                else:
                    db.execute("INSERT INTO responses VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
                               (_uid(), student_id, qid, "assignment", aid, student_answer, score, "auto", feedback))
                tid = question["topic_id"]
                existing = db.execute("SELECT score FROM mastery_scores WHERE student_id = ? AND topic_id = ?", (student_id, tid)).fetchone()
                current_score = existing["score"] if (existing and existing["score"] is not None) else score
                new_score = (current_score * 0.7 + score * 0.3)
                db.execute("INSERT OR REPLACE INTO mastery_scores (id, student_id, topic_id, score, updated_at) VALUES (?,?,?,?,datetime('now'))",
                           (_uid(), student_id, tid, round(new_score, 3)))
            db.commit()

        bump_version()
        self._send_json({"average": total_score / max(len(answers), 1)})

    def _get_messages(self, student_id=None, course_id=None):
        with db_connection() as db:
            if student_id and course_id:
                messages = db.execute("""
                    SELECT m.*, u.name as student_name, c.name as course_name
                    FROM messages m 
                    JOIN users u ON m.student_id = u.id 
                    JOIN courses c ON m.course_id = c.id
                    WHERE m.student_id = ? AND m.course_id = ?
                    ORDER BY m.created_at ASC
                """, (student_id, course_id)).fetchall()
            elif student_id:
                messages = db.execute("""
                    SELECT m.*, u.name as student_name, c.name as course_name
                    FROM messages m 
                    JOIN users u ON m.student_id = u.id 
                    JOIN courses c ON m.course_id = c.id
                    WHERE m.student_id = ?
                    ORDER BY m.created_at ASC
                """, (student_id,)).fetchall()
            elif course_id:
                messages = db.execute("""
                    SELECT m.*, u.name as student_name, c.name as course_name
                    FROM messages m 
                    JOIN users u ON m.student_id = u.id 
                    JOIN courses c ON m.course_id = c.id
                    WHERE m.course_id = ?
                    ORDER BY m.created_at DESC
                """, (course_id,)).fetchall()
            else:
                messages = db.execute("""
                    SELECT m.*, u.name as student_name, c.name as course_name
                    FROM messages m 
                    JOIN users u ON m.student_id = u.id 
                    JOIN courses c ON m.course_id = c.id
                    ORDER BY m.created_at DESC
                """).fetchall()
            self._send_json([dict(m) for m in messages])

    def _message_send(self):
        body = self._read_body()
        student_id = body.get("student_id")
        course_id = body.get("course_id")
        content = body.get("content", "").strip()
        sender = body.get("sender", "student")
        if not student_id or not content:
            return self._send_error("student_id and content required")
        if not course_id:
            # Fallback for old clients if any
            with db_connection() as db:
                course = db.execute("SELECT course_id FROM enrollments WHERE student_id = ? LIMIT 1", (student_id,)).fetchone()
                course_id = course["course_id"] if course else None

        with db_connection() as db:
            db.execute("INSERT INTO messages (id, student_id, course_id, sender, content) VALUES (?,?,?,?,?)",
                       (_uid(), student_id, course_id, sender, content))
            db.commit()
        bump_version()
        self._send_json({"success": True})

    def _message_read(self):
        body = self._read_body()
        message_id = body.get("message_id")
        if not message_id:
            return self._send_error("message_id required")
        
        with db_connection() as db:
            db.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (message_id,))
            db.commit()
        bump_version()
        self._send_json({"success": True})

    def _draft_curriculum(self):
        """AI drafts a curriculum for the architect."""
        data = self._read_body()
        language = data.get("language")
        level = data.get("level")
        course_name = data.get("course_name")
        
        from services.ai_engine import ai_generate_curriculum
        result = ai_generate_curriculum(language, level, course_name)
        if not result: return self._send_error("Failed to generate syllabus", 500)
        return self._send_json({"syllabus": result})

    def _create_classroom_from_scratch(self):
        """Creates a classroom without a PDF."""
        data = self._read_body()
        language = data.get("language")
        level = data.get("level")
        course_name = data.get("course_name")
        chapters = data.get("chapters") 
        lecturer_id = data.get("lecturer_id")
        
        cid = data.get("course_id")
        # Ensure we treat falsy/null values as None
        course_id = cid if cid and cid != "null" and cid != "undefined" else None
        
        from services.pdf_pipeline import process_manual_to_classroom
        result = process_manual_to_classroom(chapters, language, level, lecturer_id, course_name, existing_course_id=course_id)
        return self._send_json(result)

    def _read_multipart(self):
        """Simple multipart parser for PDF upload."""
        import re
        ctype = self.headers.get("Content-Type")
        if not ctype or "multipart/form-data" not in ctype:
            return None, None
        
        try:
            boundary_str = ctype.split("boundary=")[1]
            boundary = b"--" + boundary_str.encode()
        except (IndexError, AttributeError):
            return None, None

        length = int(self.headers.get("Content-Length", 0))
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [UPLOAD] Receiving {length / 1024 / 1024:.2f} MB...")
        
        # Read in one go for now, but we can improve this to stream-parse if needed
        body = self.rfile.read(length)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [UPLOAD] Data received, parsing parts...")
        
        parts = body.split(boundary)
        files = {}
        fields = {}
        
        for part in parts:
            if not part or part.strip() == b"--" or part.strip() == b"":
                continue
            
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1: continue
            
            header = part[:header_end].decode("utf-8", "ignore")
            content = part[header_end+4:]
            
            # Remove trailing \r\n
            if content.endswith(b"\r\n"):
                content = content[:-2]

            name_match = re.search(r'name="([^"]+)"', header)
            if not name_match: continue
            name = name_match.group(1)

            file_match = re.search(r'filename="([^"]+)"', header)
            if file_match:
                files[name] = {"filename": file_match.group(1), "content": content}
            else:
                fields[name] = content.decode("utf-8", "ignore").strip()
                
        return fields, files

    def _create_classroom_from_pdf(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG] Starting _create_classroom_from_pdf")
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG] Reading multipart data...")
            fields, files = self._read_multipart()
            
            if fields is None:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG] Multipart parsing failed (fields is None)")
                return self._send_error("Invalid multipart data")

            print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG] Fields received: {list(fields.keys())}")
            if not files or "pdf" not in files:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG] PDF file missing in request")
                return self._send_error("PDF file required")
            
            course_name = fields.get("course_name")
            toc_range = fields.get("toc_range", "1-5")
            manual_toc = fields.get("manual_toc")
            lecturer_id = fields.get("lecturer_id")
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG] Processing PDF for {lecturer_id} | Name: {course_name} | TOC: {toc_range}")
            if manual_toc:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG] Manual TOC detected (Length: {len(manual_toc)})")

            if not lecturer_id:
                return self._send_error("lecturer_id required")
                
            pdf_data = files["pdf"]["content"]
            pdf_filename = files["pdf"]["filename"]
            
            # Save file persistently in data/books/
            safe_filename = f"course_{_uid()}.pdf"
            os.makedirs(BOOKS_DIR, exist_ok=True)
            pdf_path = os.path.join(BOOKS_DIR, safe_filename)
            
            file_log(f"[DEBUG] Saving PDF to {pdf_path} ({len(pdf_data)} bytes)")

            with open(pdf_path, "wb") as f:
                f.write(pdf_data)
            
            file_log('LAUNCHING PHASE2 THREAD')
            result = process_pdf_to_classroom(pdf_path, toc_range, lecturer_id, course_name=course_name, manual_toc=manual_toc)
            
            file_log(f"[DEBUG] Pipeline result: {result}")

            if result.get("success"):
                bump_version()
                self._send_json(result)
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] _create_classroom_from_pdf: {e}")
            import traceback
            traceback.print_exc()
            return self._send_json({"success": False, "error": str(e)}, 500)
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [CRITICAL] Error in _create_classroom_from_pdf")
            import traceback
            traceback.print_exc()
            self._send_error(f"Server error during processing: {str(e)}")

    def _delete_classroom(self):
        body = self._read_body()
        course_id = body.get("course_id")
        if not course_id:
            return self._send_error("course_id required")
            
        try:
            with db_connection() as db:
                course = db.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
                if not course:
                    return self._send_error("Course not found")
                
                # Protection for the default demo classroom only
                if course["id"] == "spanish-101" or (course["name"] == "Spanish 101" and course["textbook"] == "Aula Internacional Plus 1"):
                    return self._send_error("The default demo classroom cannot be deleted", 403)
                
                # 1. Delete student responses (quizzes, assignments, and topic activities)
                db.execute("DELETE FROM responses WHERE context_id IN (SELECT id FROM quizzes WHERE course_id = ?)", (course_id,))
                db.execute("DELETE FROM responses WHERE context_id IN (SELECT id FROM assignments WHERE course_id = ?)", (course_id,))
                db.execute("DELETE FROM responses WHERE context_id IN (SELECT t.id FROM topics t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.course_id = ?)", (course_id,))
                
                # 2. Delete mastery scores
                db.execute("DELETE FROM mastery_scores WHERE topic_id IN (SELECT t.id FROM topics t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.course_id = ?)", (course_id,))
                
                # 3. Delete quiz and assignment structure
                db.execute("DELETE FROM quiz_questions WHERE quiz_id IN (SELECT id FROM quizzes WHERE course_id = ?)", (course_id,))
                db.execute("DELETE FROM quizzes WHERE course_id = ?", (course_id,))
                db.execute("DELETE FROM assignment_questions WHERE assignment_id IN (SELECT id FROM assignments WHERE course_id = ?)", (course_id,))
                db.execute("DELETE FROM assignments WHERE course_id = ?", (course_id,))
                
                # 4. Delete other course-related entities
                db.execute("DELETE FROM sessions WHERE course_id = ?", (course_id,))
                db.execute("DELETE FROM enrollments WHERE course_id = ?", (course_id,))
                db.execute("DELETE FROM weekly_reports WHERE course_id = ?", (course_id,))
                db.execute("DELETE FROM messages WHERE course_id = ?", (course_id,))
                
                # 5. Delete curriculum (questions, topics, chapters)
                db.execute("DELETE FROM questions WHERE topic_id IN (SELECT t.id FROM topics t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.course_id = ?)", (course_id,))
                db.execute("DELETE FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id = ?)", (course_id,))
                db.execute("DELETE FROM chapters WHERE course_id = ?", (course_id,))
                
                # 6. Delete PDF file if exists
                textbook_path = course["textbook"]
                if textbook_path and textbook_path.startswith("/books/") and not "Aula Internacional" in textbook_path:
                    full_path = os.path.join(STATIC_DIR, textbook_path.lstrip("/"))
                    if os.path.exists(full_path):
                        try: os.remove(full_path)
                        except: pass

                # 7. Finally delete the course
                db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
                db.commit()
                
            bump_version()
            self._send_json({"success": True})
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            file_log(f"Deletion Error: {err_msg}")
            self._send_error(f"Internal server error: {str(e)}", 500)

def _cleanup_stale_classrooms():
    """Find and reset classrooms stuck in 'building' state for too long."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [MAINTENANCE] Cleaning up stale classroom tasks...")
    try:
        with db_connection() as db:
            # Any classroom with is_building=1 created more than 30 minutes ago
            stale_threshold = (datetime.now(timezone.utc) - timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
            stale = db.execute("SELECT id, name FROM courses WHERE is_building = 1 AND created_at < ?", (stale_threshold,)).fetchall()
            
            for course in stale:
                cid = course["id"]
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [MAINTENANCE] Resetting stalled classroom state: {course['name']} ({cid})")
                db.execute("UPDATE courses SET is_building = 0, progress = 0 WHERE id = ?", (cid,))
            
            db.commit()
    except Exception as e:
        print(f"[ERROR] Maintenance cleanup failed: {e}")

def _cleanup_orphaned_building_flags():
    """Reset building and activity flags for tasks that were interrupted by a server restart."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [STARTUP] Resetting orphaned building and activity flags...")
    with db_connection() as db:
        # 1. Reset Classroom Building flags (interrupted builds)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        db.execute("UPDATE courses SET is_building = 0, progress = 0 WHERE is_building = 1 AND created_at < ?", (cutoff,))
        
        # 2. Reset Activity Generation flags (Always reset on startup since threads are gone)
        db.execute("UPDATE courses SET activity_status = 'idle', activity_progress = 0 WHERE activity_status = 'generating'")
        
        # 3. MAINTENANCE: Wipe ALL questions on startup (KEEPING THIS UNTIL VERIFIED)
        print("[MAINTENANCE] Nuclear Wipe: Purging question bank...")
        db.execute("DELETE FROM questions")
        
        db.commit()

class RobustServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True

def main():
    try:
        init_db()
        _cleanup_stale_classrooms()
        _cleanup_orphaned_building_flags()
        
        server = RobustServer(("0.0.0.0", PORT), APIHandler)
        server.daemon_threads = True
        
        print(f"""
============================================================
  AulaAI — Spanish Learning System
  Textbook: Aula Internacional Plus 1

  Server running at: http://localhost:{PORT}
  Mode: Threaded (crash-safe)
  Maintenance: Auto-cleanup of stale tasks (30min timeout)

  Lecturer login: garcia@university.edu / demo123
  Students: Register at the login page
============================================================
        """)
        
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
    except Exception as e:
        print(f"\n[FATAL ERROR] Server failed to start: {e}")
        import traceback
        traceback.print_exc()
        # input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
