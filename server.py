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
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db, init_db
from services.content_engine import generate_activity, generate_quiz, grade_response, generate_dialogue_activity
from services.mastery import compute_mastery, generate_weekly_report

PORT = int(os.environ.get("PORT", 3000))
STATIC_DIR = os.path.join(os.path.dirname(__file__), "public")

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
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

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
            return self._get_quiz(quiz_id)
        elif path == "/api/quizzes":
            course_id = params.get("course_id", [None])[0]
            return self._get_quizzes(course_id)
        elif path == "/api/report":
            course_id = params.get("course_id", [None])[0]
            return self._get_report(course_id)
        elif path == "/api/activity":
            topic_id = params.get("topic_id", [None])[0]
            return self._get_activity(topic_id)
        elif path.startswith("/api/"):
            return self._send_error("Not found", 404)
        else:
            return self._serve_static(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/login":
            return self._login()
        elif path == "/api/register":
            return self._register()
        elif path == "/api/quiz/create":
            return self._create_quiz()
        elif path == "/api/quiz/submit":
            return self._submit_quiz()
        elif path == "/api/activity/respond":
            return self._submit_activity_response()
        elif path == "/api/report/generate":
            return self._generate_report()
        elif path == "/api/session/start":
            return self._start_session()
        elif path == "/api/assignment/create":
            return self._create_assignment()
        else:
            return self._send_error("Not found", 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    # ── API Implementations ─────────────────────────────────

    def _login(self):
        body = self._read_body()
        email = body.get("email", "")
        password = body.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ? AND password = ?",
                          (email, password)).fetchone()
        db.close()

        if user:
            user = dict(user)
            self._send_json({
                "success": True,
                "user": {"id": user["id"], "name": user["name"],
                         "email": user["email"], "role": user["role"]}
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

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            db.close()
            return self._send_error("An account with this email already exists")

        student_id = _uid()
        db.execute("INSERT INTO users VALUES (?,?,?,?,?,datetime('now'))",
                   (student_id, name, email, password, "student"))

        # Auto-enroll in the first course
        course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
        if course:
            db.execute("INSERT INTO enrollments VALUES (?,?,?,datetime('now'))",
                       (_uid(), student_id, course["id"]))

        db.commit()
        db.close()

        self._send_json({
            "success": True,
            "user": {"id": student_id, "name": name,
                     "email": email, "role": "student"}
        })

    def _get_courses(self):
        db = get_db()
        courses = db.execute("SELECT * FROM courses").fetchall()
        db.close()
        self._send_json([dict(c) for c in courses])

    def _get_curriculum(self, course_id):
        db = get_db()
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
                t_dict["content"] = json.loads(t_dict["content_json"])
                qcount = db.execute(
                    "SELECT COUNT(*) as cnt FROM questions WHERE topic_id = ?", (t["id"],)
                ).fetchone()["cnt"]
                t_dict["question_count"] = qcount
                ch_dict["topics"].append(t_dict)
            result.append(ch_dict)

        db.close()
        self._send_json(result)

    def _get_students(self, course_id):
        db = get_db()
        if not course_id:
            course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
            course_id = course["id"] if course else None

        students = db.execute("""
            SELECT u.id, u.name, u.email FROM users u
            JOIN enrollments e ON u.id = e.student_id
            WHERE e.course_id = ?
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

        db.close()
        self._send_json(result)

    def _get_student_progress(self, student_id):
        if not student_id:
            return self._send_error("student_id required")

        db = get_db()
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

        db.close()
        self._send_json({
            "masteries": [dict(m) for m in masteries],
            "recent_responses": [dict(r) for r in responses],
        })

    def _get_questions(self, topic_id):
        if not topic_id:
            return self._send_error("topic_id required")

        db = get_db()
        questions = db.execute(
            "SELECT * FROM questions WHERE topic_id = ? AND approved = 1", (topic_id,)
        ).fetchall()
        db.close()

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

        db = get_db()
        topic = db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
        db.close()

        if not topic:
            return self._send_error("Topic not found", 404)

        activities = generate_activity(dict(topic), count=6)

        # Add a dialogue activity if available
        dialogue = generate_dialogue_activity()
        activities.append(dialogue)

        self._send_json({"topic": dict(topic), "activities": activities})

    def _get_quizzes(self, course_id):
        db = get_db()
        if not course_id:
            course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
            course_id = course["id"] if course else None

        quizzes = db.execute(
            "SELECT * FROM quizzes WHERE course_id = ? ORDER BY created_at DESC", (course_id,)
        ).fetchall()
        db.close()
        self._send_json([dict(q) for q in quizzes])

    def _get_quiz(self, quiz_id):
        if not quiz_id:
            return self._send_error("quiz_id required")

        db = get_db()
        quiz = db.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
        if not quiz:
            db.close()
            return self._send_error("Quiz not found", 404)

        questions = db.execute("""
            SELECT q.* FROM questions q
            JOIN quiz_questions qq ON q.id = qq.question_id
            WHERE qq.quiz_id = ?
            ORDER BY qq.sort_order
        """, (quiz_id,)).fetchall()

        result = dict(quiz)
        result["questions"] = []
        for q in questions:
            q_dict = dict(q)
            if q_dict["distractors"]:
                q_dict["distractors"] = json.loads(q_dict["distractors"])
            result["questions"].append(q_dict)

        db.close()
        self._send_json(result)

    def _create_quiz(self):
        body = self._read_body()
        course_id = body.get("course_id")
        chapter_id = body.get("chapter_id")
        title = body.get("title", "Quiz")
        count = body.get("count", 10)

        db = get_db()
        if not course_id:
            course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
            course_id = course["id"]

        # Get topics for this chapter (or all)
        if chapter_id:
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
                   (quiz_id, course_id, title, chapter_id))

        for i, q in enumerate(questions):
            db.execute("INSERT OR IGNORE INTO quiz_questions VALUES (?,?,?)",
                       (quiz_id, q["id"], i))

        db.commit()
        db.close()
        self._send_json({"quiz_id": quiz_id, "question_count": len(questions)})

    def _submit_quiz(self):
        body = self._read_body()
        quiz_id = body.get("quiz_id")
        student_id = body.get("student_id")
        answers = body.get("answers", {})  # {question_id: answer}

        db = get_db()
        results = []
        total_score = 0

        for qid, student_answer in answers.items():
            question = db.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
            if not question:
                continue

            score, feedback = grade_response(question["type"], student_answer, question["answer"])
            total_score += score

            # Save response
            db.execute("INSERT INTO responses VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
                       (_uid(), student_id, qid, "quiz", quiz_id,
                        student_answer, score, "auto", feedback))

            # Update mastery
            topic_id = question["topic_id"]
            existing = db.execute(
                "SELECT score FROM mastery_scores WHERE student_id = ? AND topic_id = ?",
                (student_id, topic_id)
            ).fetchone()

            new_score = score if not existing else (existing["score"] * 0.7 + score * 0.3)
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
        db.close()

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
            db = get_db()
            db.execute("INSERT INTO responses VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
                       (_uid(), student_id, question_id, "session", _uid(),
                        answer, score, "auto", feedback))
            db.commit()
            db.close()

        self._send_json({"score": score, "feedback": feedback})

    def _get_report(self, course_id):
        db = get_db()
        if not course_id:
            course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
            course_id = course["id"] if course else None

        report = generate_weekly_report(db, course_id)
        db.close()
        self._send_json(report)

    def _generate_report(self):
        body = self._read_body()
        course_id = body.get("course_id")

        db = get_db()
        if not course_id:
            course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
            course_id = course["id"]

        report = generate_weekly_report(db, course_id)
        db.close()
        self._send_json(report)

    def _start_session(self):
        body = self._read_body()
        course_id = body.get("course_id")
        chapter_id = body.get("chapter_id")
        topic_id = body.get("topic_id")

        db = get_db()
        if not course_id:
            course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
            course_id = course["id"]

        session_id = _uid()
        db.execute("INSERT INTO sessions VALUES (?,?,?,date('now'),'active',datetime('now'),NULL)",
                   (session_id, course_id, chapter_id))
        db.commit()

        # Generate activities for the session
        if topic_id:
            topic = db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
            activities = generate_activity(dict(topic), count=8) if topic else []
        else:
            activities = []

        db.close()
        self._send_json({
            "session_id": session_id,
            "status": "active",
            "activities": activities
        })

    def _create_assignment(self):
        body = self._read_body()
        course_id = body.get("course_id")
        chapter_id = body.get("chapter_id")
        title = body.get("title", "Assignment")
        due_at = body.get("due_at")

        db = get_db()
        if not course_id:
            course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
            course_id = course["id"]

        assignment_id = _uid()
        db.execute("INSERT INTO assignments VALUES (?,?,?,?,?,datetime('now'))",
                   (assignment_id, course_id, title, chapter_id, due_at))

        # Add questions from the chapter
        if chapter_id:
            topics = db.execute("SELECT id FROM topics WHERE chapter_id = ?", (chapter_id,)).fetchall()
            topic_ids = [t["id"] for t in topics]
            questions = generate_quiz(topic_ids, db, count=15)
            for i, q in enumerate(questions):
                db.execute("INSERT OR IGNORE INTO assignment_questions VALUES (?,?,?)",
                           (assignment_id, q["id"], i))

        db.commit()
        db.close()
        self._send_json({"assignment_id": assignment_id, "title": title})


def main():
    init_db()
    server = http.server.HTTPServer(("0.0.0.0", PORT), APIHandler)
    print(f"""
============================================================
  Spanish AI System - Prototype
  Textbook: Aula Internacional Plus 1

  Server running at: http://localhost:{PORT}

  Lecturer login: garcia@university.edu / demo123
  Students: Register at the login page
============================================================
    """)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
