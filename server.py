"""
Main server — Python stdlib HTTP server with REST API routing.
No external dependencies required.
"""

import http.server
import json
import os
import sys
import uuid
import sqlite3
import threading
import time
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db, init_db, db_connection
from services.content_engine import generate_activity, generate_quiz, grade_response, generate_dialogue_activity
from services.mastery import compute_mastery, generate_weekly_report
from services.ai_engine import is_ai_available, ai_generate_report_insights
from services.pdf_pipeline import process_pdf_to_classroom

PORT = int(os.environ.get("PORT", 3000))
STATIC_DIR = os.path.join(os.path.dirname(__file__), "public")

# ── Live-sync version counter ──
# Incremented on every data mutation; clients poll /api/version to detect changes.
_data_version = 0
_version_lock = threading.Lock()

def _bump_version():
    global _data_version
    with _version_lock:
        _data_version += 1

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

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

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
        if path == "/" or path == "":
            path = "/index.html"

        filepath = os.path.join(STATIC_DIR, path.lstrip("/"))
        filepath = os.path.normpath(filepath)

        # Security: ensure path is within STATIC_DIR
        if not filepath.startswith(os.path.normpath(STATIC_DIR)):
            self.send_error(403)
            return

        if not os.path.isfile(filepath):
            # SPA fallback: serve index.html for unknown paths
            filepath = os.path.join(STATIC_DIR, "index.html")

        ext = os.path.splitext(filepath)[1]
        content_type = MIME_TYPES.get(ext, "application/octet-stream")

        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    # ── GET routes ──────────────────────────────────────────

    def do_GET(self):
        try:
            self._handle_GET()
        except Exception as e:
            print(f"[ERROR] GET {self.path}: {e}")
            try:
                self._send_json({"error": "Internal server error"}, 500)
            except Exception:
                pass

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
            return self._get_student_progress(student_id)
        elif path == "/api/questions":
            topic_id = params.get("topic_id", [None])[0]
            return self._get_questions(topic_id)
        elif path == "/api/quiz/take":
            quiz_id = params.get("quiz_id", [None])[0]
            student_id = params.get("student_id", [None])[0]
            return self._get_quiz(quiz_id, student_id)
        elif path == "/api/quizzes":
            course_id = params.get("course_id", [None])[0]
            student_id = params.get("student_id", [None])[0]
            return self._get_quizzes(course_id, student_id)
        elif path == "/api/messages":
            student_id = params.get("student_id", [None])[0]
            return self._get_messages(student_id)
        elif path == "/api/report":
            course_id = params.get("course_id", [None])[0]
            return self._get_report(course_id)
        elif path == "/api/activity":
            topic_id = params.get("topic_id", [None])[0]
            return self._get_activity(topic_id)
        elif path == "/api/student/stats":
            student_id = params.get("student_id", [None])[0]
            return self._get_student_stats(student_id)
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
            return self._send_json({"version": _data_version})
        elif path == "/health" or path == "/api/health":
            return self._send_json({"status": "ok", "time": datetime.now().isoformat()})
        elif path.startswith("/api/"):
            return self._send_error("Not found", 404)
        else:
            return self._serve_static(path)

    def do_POST(self):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] POST {self.path}")
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

    def _handle_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        # Classroom management routes (check these first to be safe)
        if path == "/api/classroom/delete":
            return self._delete_classroom()
        elif path == "/api/classroom/create-from-pdf":
            return self._create_classroom_from_pdf()
            
        # Other routes
        elif path == "/api/login":
            return self._login()
        elif path == "/api/student/login":
            return self._student_login()
        elif path == "/api/register":
            return self._register()
        elif path == "/api/students/pending":
            return self._get_pending_students()
        elif path == "/api/students/approve":
            return self._approve_student()
        elif path == "/api/quiz/create":
            return self._create_quiz()
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
        else:
            self._send_error("Not found", 404)

    def _reset_data(self):
        """Erase all student data while preserving curriculum and lecturer account."""
        body = self._read_body()
        confirm = body.get("confirm")
        if confirm != "ERASE ALL DATA":
            return self._send_error("Confirmation text does not match")

        with db_connection() as db:
            db.execute("DELETE FROM responses")
            db.execute("DELETE FROM mastery_scores")
            db.execute("DELETE FROM quiz_questions")
            db.execute("DELETE FROM quizzes")
            db.execute("DELETE FROM assignment_questions")
            db.execute("DELETE FROM assignments")
            db.execute("DELETE FROM sessions")
            db.execute("DELETE FROM enrollments")
            db.execute("DELETE FROM messages")
            db.execute("DELETE FROM users WHERE role = 'student'")
            db.execute("DELETE FROM weekly_reports")
            db.commit()

        _bump_version()
        print("[RESET] All student data erased by lecturer.")
        self._send_json({"success": True, "message": "All student data has been erased."})

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
        
        _bump_version()
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
        _bump_version()
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
        _bump_version()
        self._send_json({"success": True})

    def _get_pending_students(self):
        """Lecturer only: Get students waiting for approval."""
        with db_connection() as db:
            students = db.execute("SELECT id, name, email, created_at FROM users WHERE role = 'student' AND status = 'pending' ORDER BY created_at DESC").fetchall()
        self._send_json([dict(s) for s in students])

    def _approve_student(self):
        """Lecturer only: Approve a pending student."""
        body = self._read_body()
        student_id = body.get("student_id")
        if not student_id:
            return self._send_error("student_id required")
            
        with db_connection() as db:
            db.execute("UPDATE users SET status = 'approved' WHERE id = ? AND role = 'student'", (student_id,))
            db.commit()
            
        _bump_version()
        self._send_json({"success": True})

    def _get_user_status(self, user_id):
        """Check current approval status for a user."""
        if not user_id:
            return self._send_error("user_id required")
        with db_connection() as db:
            user = db.execute("SELECT status FROM users WHERE id = ?", (user_id,)).fetchone()
        if user:
            self._send_json({"status": user["status"] or "approved"})
        else:
            self._send_error("User not found", 404)

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
            "provider": "Groq (Llama 3.3 70B)" if is_ai_available() else "Mock Engine",
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

        _bump_version()
        self._send_json({
            "success": True,
            "user": {"id": student_id, "name": name,
                     "email": email, "role": "student", "status": "pending"}
        })

    def _student_login(self):
        """Student login by student number. Auto-registers on first login."""
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

            if user:
                # Existing student — verify name matches
                user = dict(user)
                stored_name = user["name"].strip().lower()
                input_name = name.strip().lower()
                if stored_name != input_name:
                    return self._send_error("Student number and name do not match")
                
                self._send_json({
                    "success": True,
                    "user": {"id": user["id"], "name": user["name"],
                             "email": user["email"], "role": "student", "status": user.get("status", "approved")}
                })
            else:
                # New student — auto-register
                if not name:
                    return self._send_error("Name is required for first login")

                student_id = _uid()
                db.execute("INSERT INTO users (id, name, email, password, role, status, created_at) VALUES (?,?,?,?,?,?,datetime('now'))",
                           (student_id, name, email_key, student_number, "student", "pending"))

                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                if course:
                    db.execute("INSERT INTO enrollments VALUES (?,?,?,datetime('now'))",
                               (_uid(), student_id, course["id"]))

                db.commit()
                _bump_version()
                self._send_json({
                    "success": True,
                    "user": {"id": student_id, "name": name,
                             "email": email_key, "role": "student", "status": "pending"}
                })

    def _get_courses(self):
        with db_connection() as db:
            courses = db.execute("SELECT * FROM courses").fetchall()
        self._send_json([dict(c) for c in courses])

    def _get_curriculum(self, course_id):
        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                course_id = course["id"] if course else None

            chapters = db.execute(
                "SELECT * FROM chapters WHERE course_id = ? ORDER BY number", (course_id,)
            ).fetchall()

            result = []
            for ch in chapters:
                ch_dict = dict(ch)
                topics = db.execute(
                    "SELECT * FROM topics WHERE chapter_id = ? ORDER BY sort_order", (ch["id"],)
                ).fetchall()
                ch_dict["topics"] = []
                for t in topics:
                    t_dict = dict(t)
                    t_dict["content"] = json.loads(t_dict["content"])
                    qcount = db.execute(
                        "SELECT COUNT(*) as cnt FROM questions WHERE topic_id = ?", (t["id"],)
                    ).fetchone()["cnt"]
                    t_dict["question_count"] = qcount
                    ch_dict["topics"].append(t_dict)
                result.append(ch_dict)

        self._send_json(result)

    def _get_students(self, course_id):
        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                course_id = course["id"] if course else None

            students = db.execute("""
                SELECT u.id, u.name, u.email FROM users u
                JOIN enrollments e ON u.id = e.student_id
                WHERE e.course_id = ? AND (u.status = 'approved' OR u.status IS NULL)
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

    def _get_student_progress(self, student_id):
        if not student_id:
            return self._send_error("student_id required")

        with db_connection() as db:
            # Get mastery per topic
            masteries = db.execute("""
                SELECT t.title, t.type, ms.score, ch.title as chapter_title, ch.number
                FROM mastery_scores ms
                JOIN topics t ON ms.topic_id = t.id
                JOIN chapters ch ON t.chapter_id = ch.id
                WHERE ms.student_id = ?
                ORDER BY ch.number, t.sort_order
            """, (student_id,)).fetchall()

            # Recent responses
            responses = db.execute("""
                SELECT r.score, r.submitted_at, q.prompt, q.type as question_type
                FROM responses r
                JOIN questions q ON r.question_id = q.id
                WHERE r.student_id = ?
                ORDER BY r.submitted_at DESC LIMIT 20
            """, (student_id,)).fetchall()

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
        for q in questions:
            q_dict = dict(q)
            if q_dict["distractors"]:
                q_dict["distractors"] = json.loads(q_dict["distractors"])
            result.append(q_dict)

        self._send_json(result)

    def _get_activity(self, topic_id):
        if not topic_id:
            return self._send_error("topic_id required")

        with db_connection() as db:
            topic = db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()

        if not topic:
            return self._send_error("Topic not found", 404)

        with db_connection() as db:
            row = db.execute("""
                SELECT co.language FROM courses co
                JOIN chapters ch ON co.id = ch.course_id
                JOIN topics t ON ch.id = t.chapter_id
                WHERE t.id = ?
            """, (topic_id,)).fetchone()
            language = row["language"] if row else "Spanish"

        activities = generate_activity(dict(topic), count=6, language=language)

        # Add a dialogue activity if available
        dialogue = generate_dialogue_activity(language=language)
        activities.append(dialogue)

        self._send_json({"topic": dict(topic), "activities": activities})

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
            for q in questions:
                q_dict = dict(q)
                if q_dict.get("distractors"):
                    try:
                        q_dict["distractors"] = json.loads(q_dict["distractors"])
                    except Exception:
                        q_dict["distractors"] = []
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
            for q in questions:
                qd = dict(q)
                if qd["distractors"]:
                    qd["distractors"] = json.loads(qd["distractors"])
                questions_list.append(qd)

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
                course_id = course["id"]

            if chapter_id and chapter_id != "all":
                topics = db.execute("SELECT id FROM topics WHERE chapter_id = ?", (chapter_id,)).fetchall()
            else:
                topics = db.execute("""
                    SELECT t.id FROM topics t
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ?
                """, (course_id,)).fetchall()

            topic_ids = [t["id"] for t in topics]
            questions = generate_quiz(topic_ids, db, count=count)

            quiz_id = _uid()
            db.execute("INSERT INTO quizzes VALUES (?,?,?,?,datetime('now'),datetime('now','+1 day'),15,datetime('now'))",
                       (quiz_id, course_id, title, None if chapter_id == "all" else chapter_id))

            for i, q in enumerate(questions):
                db.execute("INSERT OR IGNORE INTO quiz_questions VALUES (?,?,?)",
                           (quiz_id, q["id"], i))

            db.commit()
        _bump_version()
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
            questions = generate_quiz(topic_ids, db, count=count)
            result = []
            for q in questions:
                q_dict = dict(q)
                if isinstance(q_dict.get("distractors"), str):
                    try:
                        q_dict["distractors"] = json.loads(q_dict["distractors"])
                    except:
                        q_dict["distractors"] = []
                result.append(q_dict)
                
        self._send_json({"questions": result})

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
                
            for i, q in enumerate(questions):
                qid = q.get("id")
                if not qid or str(qid).startswith("new_"):
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
                    db.execute("INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,1,datetime('now'))",
                               (qid, topic_id, q.get("type", "mcq"), q.get("prompt"), q.get("answer"),
                                json.dumps(distractors), "custom", None, "{}"))
                
                if pub_type == "quiz":
                    db.execute("INSERT OR IGNORE INTO quiz_questions VALUES (?,?,?)", (pub_id, qid, i))
                else:
                    db.execute("INSERT OR IGNORE INTO assignment_questions VALUES (?,?,?)", (pub_id, qid, i))
            
            db.commit()
        _bump_version()
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

        _bump_version()
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

        _bump_version()
        self._send_json({"score": score, "feedback": feedback})

    def _get_student_stats(self, student_id):
        if not student_id: return self._send_error("ID required")
        with db_connection() as db:
            stats = {
                "quizzes": db.execute("SELECT COUNT(DISTINCT context_id) FROM responses WHERE student_id = ? AND context_type = 'quiz'", (student_id,)).fetchone()[0],
                "practice": db.execute("SELECT COUNT(*) FROM responses WHERE student_id = ? AND context_type = 'practice'", (student_id,)).fetchone()[0],
                "assignments": db.execute("SELECT COUNT(DISTINCT context_id) FROM responses WHERE student_id = ? AND context_type = 'assignment'", (student_id,)).fetchone()[0],
            }
        self._send_json(stats)

    def _get_report(self, course_id):
        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                course_id = course["id"] if course else None
            report = generate_weekly_report(db, course_id)
        self._send_json(report)

    def _generate_report(self):
        body = self._read_body()
        course_id = body.get("course_id")

        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                course_id = course["id"]
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
                language = row["language"] if row else "Spanish"
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

        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                if course:
                    course_id = course["id"]
                else:
                    return self._send_error("No courses found")

            assignment_id = _uid()
            db.execute("INSERT INTO assignments VALUES (?,?,?,?,?,datetime('now'))",
                       (assignment_id, course_id, title, None if chapter_id == "all" else chapter_id, due_at))

            if chapter_id and chapter_id != "all":
                topics = db.execute("SELECT id FROM topics WHERE chapter_id = ?", (chapter_id,)).fetchall()
            else:
                topics = db.execute("""
                    SELECT t.id FROM topics t
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ?
                """, (course_id,)).fetchall()

            topic_ids = [t["id"] for t in topics]
            questions = generate_quiz(topic_ids, db, count=count)
            for i, q in enumerate(questions):
                db.execute("INSERT OR IGNORE INTO assignment_questions VALUES (?,?,?)",
                           (assignment_id, q["id"], i))
            db.commit()

        _bump_version()
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

        _bump_version()
        self._send_json({"average": total_score / max(len(answers), 1)})

    def _get_messages(self, student_id=None):
        with db_connection() as db:
            if student_id:
                messages = db.execute("""
                    SELECT m.*, u.name as student_name 
                    FROM messages m 
                    JOIN users u ON m.student_id = u.id 
                    WHERE m.student_id = ?
                    ORDER BY m.created_at ASC
                """, (student_id,)).fetchall()
            else:
                messages = db.execute("""
                    SELECT m.*, u.name as student_name 
                    FROM messages m 
                    JOIN users u ON m.student_id = u.id 
                    ORDER BY m.created_at DESC
                """).fetchall()
            self._send_json([dict(m) for m in messages])

    def _message_send(self):
        body = self._read_body()
        student_id = body.get("student_id")
        content = body.get("content", "").strip()
        sender = body.get("sender", "student")
        if not student_id or not content:
            return self._send_error("student_id and content required")
        
        with db_connection() as db:
            db.execute("INSERT INTO messages (id, student_id, sender, content) VALUES (?,?,?,?)",
                       (_uid(), student_id, sender, content))
            db.commit()
        _bump_version()
        self._send_json({"success": True})

    def _message_read(self):
        body = self._read_body()
        message_id = body.get("message_id")
        if not message_id:
            return self._send_error("message_id required")
        
        with db_connection() as db:
            db.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (message_id,))
            db.commit()
        _bump_version()
        self._send_json({"success": True})

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
        body = self.rfile.read(length)
        
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
        fields, files = self._read_multipart()
        if not files or "pdf" not in files:
            return self._send_error("PDF file required")
        
        toc_range = fields.get("toc_range", "1-5")
        lecturer_id = fields.get("lecturer_id")
        
        if not lecturer_id:
            return self._send_error("lecturer_id required")
            
        pdf_data = files["pdf"]["content"]
        pdf_filename = files["pdf"]["filename"]
        
        # Save temp file
        temp_path = os.path.join(os.path.dirname(__file__), "scratch", f"upload_{_uid()}.pdf")
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "wb") as f:
            f.write(pdf_data)
            
        try:
            result = process_pdf_to_classroom(temp_path, toc_range, lecturer_id)
            if result.get("success"):
                _bump_version()
                self._send_json(result)
            else:
                self._send_error(result.get("error", "Failed to process PDF"))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _delete_classroom(self):
        body = self._read_body()
        course_id = body.get("course_id")
        if not course_id:
            return self._send_error("course_id required")
            
        with db_connection() as db:
            course = db.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
            if not course:
                return self._send_error("Course not found")
            
            # Protection for Spanish classroom
            if course["name"] == "Spanish 101" or "Spanish" in course["name"] or course["textbook"] == "Aula Internacional Plus 1":
                return self._send_error("Default Spanish classroom cannot be deleted", 403)
            
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
            
            # 5. Delete curriculum (questions, topics, chapters)
            # Questions are linked to topics
            db.execute("DELETE FROM questions WHERE topic_id IN (SELECT t.id FROM topics t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.course_id = ?)", (course_id,))
            db.execute("DELETE FROM topics WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id = ?)", (course_id,))
            db.execute("DELETE FROM chapters WHERE course_id = ?", (course_id,))
            
            # 6. Finally delete the course
            db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
            db.commit()
            
        _bump_version()
        self._send_json({"success": True})

def main():
    init_db()
    
    # ThreadingHTTPServer: each request in its own thread — one slow request can't block the site
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), APIHandler)
    server.daemon_threads = True  # threads die when main thread dies
    
    print(f"""
============================================================
  AulaAI — Spanish Learning System
  Textbook: Aula Internacional Plus 1

  Server running at: http://localhost:{PORT}
  Mode: Threaded (crash-safe)

  Lecturer login: garcia@university.edu / demo123
  Students: Register at the login page
============================================================
    """)
    
    while True:  # auto-restart loop
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Server started on port {PORT}")
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[Server] Shutting down...")
            server.shutdown()
            break
        except Exception as e:
            print(f"[CRITICAL] Server error: {e} — restarting in 2s...")
            time.sleep(2)


if __name__ == "__main__":
    main()
