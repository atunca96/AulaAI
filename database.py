import sqlite3
import json
import random
import os
import uuid
import threading
import contextlib
import time
from datetime import datetime, timezone

def _uid():
    return str(uuid.uuid4())

# ── PATHING (Absolute for Persistence) ───────────────────
# We use absolute paths to ensure the Railway volume remains mounted correctly.
IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None
if IS_RAILWAY:
    # On Railway, we REQUIRE the /app/data mount. 
    # If it's missing, we are in a 'Ghost' state and should not seed.
    DATA_DIR = "/app/data"
    if not os.path.exists(DATA_DIR):
        print("[CRITICAL] Railway volume /app/data not found! Waiting for mount...")
        os.makedirs(DATA_DIR, exist_ok=True)
else:
    DATA_DIR = os.path.join(os.getcwd(), "data")

BOOKS_DIR = os.path.join(DATA_DIR, "books")
DB_PATH = os.path.join(DATA_DIR, "aula.db")

# Strict check: Wait for volume mount on Railway
IS_GHOST_DB = False
if IS_RAILWAY:
    # We give Railway up to 10 seconds to attach the volume
    for attempt in range(10):
        if os.path.exists(DB_PATH):
            print(f"[DB] Volume found after {attempt}s. Starting normally.")
            IS_GHOST_DB = False
            break
        else:
            print(f"[DB] Waiting for volume mount (Attempt {attempt+1}/10)...")
            time.sleep(1)
    else:
        # If still not found after 10s, it's either a fresh install or a major mount failure
        if not os.path.exists(DB_PATH):
            print("[WARNING] No database found after 10s. Proceeding in 'Fresh Install' mode.")
            IS_GHOST_DB = True

# Thread-safe locks for background tasks
_task_locks = {}
_task_locks_lock = threading.Lock()

def get_task_lock(course_id):
    with _task_locks_lock:
        if course_id not in _task_locks:
            _task_locks[course_id] = threading.Lock()
        return _task_locks[course_id]

@contextlib.contextmanager
def db_connection():
    """Context manager that automatically closes the connection."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def get_db():
    """Backward compatibility alias."""
    return db_connection()

def init_db():
    """Initialize the universal AulaAI database schema."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # User & Role Management
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT,
            status TEXT DEFAULT 'approved',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Multi-Language Classroom Management
        c.execute('''CREATE TABLE IF NOT EXISTS courses (
            id TEXT PRIMARY KEY,
            name TEXT,
            semester TEXT,
            textbook TEXT,
            lecturer_id TEXT,
            code TEXT UNIQUE,
            language TEXT DEFAULT 'Turkish',
            level TEXT DEFAULT 'A1',
            is_building INTEGER DEFAULT 0,
            progress INTEGER DEFAULT 0,
            total_steps INTEGER DEFAULT 0,
            draft_progress INTEGER DEFAULT 0,
            draft_status TEXT DEFAULT 'idle',
            draft_result TEXT,
            activity_status TEXT DEFAULT 'idle',
            activity_progress INTEGER DEFAULT 0,
            activity_total INTEGER DEFAULT 0,
            activity_result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(lecturer_id) REFERENCES users(id)
        )''')

        # Curriculum Structure (Chapters & Topics)
        c.execute('''CREATE TABLE IF NOT EXISTS chapters (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            number INTEGER,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS topics (
            id TEXT PRIMARY KEY,
            chapter_id TEXT,
            type TEXT,
            title TEXT,
            difficulty TEXT,
            content TEXT,
            pdf_url TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(chapter_id) REFERENCES chapters(id)
        )''')

        # The Teacher's Filter: Knowledge Store
        c.execute('''CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            topic_id TEXT,
            type TEXT,
            prompt TEXT,
            answer TEXT,
            distractors TEXT,
            difficulty TEXT,
            variant_group TEXT,
            metadata TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(topic_id) REFERENCES topics(id)
        )''')

        # Student Performance & Mastery
        c.execute('''CREATE TABLE IF NOT EXISTS mastery_scores (
            student_id TEXT,
            topic_id TEXT,
            score REAL,
            attempts INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(student_id, topic_id),
            FOREIGN KEY(student_id) REFERENCES users(id),
            FOREIGN KEY(topic_id) REFERENCES topics(id)
        )''')

        # REFACTORED: The Response Engine
        c.execute('''CREATE TABLE IF NOT EXISTS responses (
            id TEXT PRIMARY KEY,
            student_id TEXT,
            question_id TEXT,
            context_type TEXT,
            context_id TEXT,
            answer TEXT,
            score REAL,
            graded_by TEXT,
            feedback TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(student_id) REFERENCES users(id)
        )''')

        # Communication & Feedback
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            student_id TEXT,
            course_id TEXT,
            sender TEXT,
            content TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Assessment System (Quizzes & Assignments)
        c.execute('''CREATE TABLE IF NOT EXISTS quizzes (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            title TEXT,
            due_date TIMESTAMP,
            is_published INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS quiz_questions (
            quiz_id TEXT,
            question_id TEXT,
            sort_order INTEGER,
            PRIMARY KEY(quiz_id, question_id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS assignments (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            title TEXT,
            description TEXT,
            due_date TIMESTAMP,
            is_published INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS assignment_questions (
            assignment_id TEXT,
            question_id TEXT,
            sort_order INTEGER,
            PRIMARY KEY(assignment_id, question_id)
        )''')

        # REFACTORED: Enrollment Management
        c.execute('''CREATE TABLE IF NOT EXISTS enrollments (
            id TEXT PRIMARY KEY,
            student_id TEXT,
            course_id TEXT,
            status TEXT DEFAULT 'pending',
            pin TEXT,
            enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, course_id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            course_id TEXT,
            expires_at TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS weekly_reports (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            week_number INTEGER,
            report_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )''')

        conn.commit()

    # ── MIGRATIONS (Self-Healing existing data) ────────
    _run_migrations()

    with db_connection() as db:
        c = db.cursor()
        # Run seeding ONLY if not a ghost DB on Railway
        if not IS_GHOST_DB and c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            print("[DB] Seeding initial data...")
            _seed_data(c)
            db.commit()

def _run_migrations():
    """Sequentially apply missing columns for production stability."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        migrations = [
            ("courses", "progress", "INTEGER DEFAULT 0"),
            ("courses", "total_steps", "INTEGER DEFAULT 0"),
            ("courses", "draft_progress", "INTEGER DEFAULT 0"),
            ("courses", "draft_status", "TEXT DEFAULT 'idle'"),
            ("courses", "draft_result", "TEXT"),
            ("courses", "activity_status", "TEXT DEFAULT 'idle'"),
            ("courses", "activity_progress", "INTEGER DEFAULT 0"),
            ("courses", "activity_total", "INTEGER DEFAULT 0"),
            ("courses", "activity_result", "TEXT"),
            ("courses", "language", "TEXT DEFAULT 'Turkish'"),
            ("courses", "level", "TEXT DEFAULT 'A1'"),
            ("enrollments", "id", "TEXT"),
            ("enrollments", "pin", "TEXT"),
            ("enrollments", "enrolled_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("responses", "score", "REAL"),
            ("responses", "feedback", "TEXT"),
            ("responses", "graded_by", "TEXT"),
            ("responses", "submitted_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("questions", "is_active", "INTEGER DEFAULT 1"),
            ("users", "status", "TEXT DEFAULT 'approved'")
        ]
        
        for table, column, definition in migrations:
            try:
                # Use pragma to check if exists to avoid error spam
                c.execute(f"PRAGMA table_info({table})")
                cols = [r[1] for r in c.fetchall()]
                if column not in cols:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                    print(f"[MIGRATION] Added {column} to {table}")
            except sqlite3.OperationalError:
                pass 
        
        # SPECIAL: Populate IDs for legacy enrollments to prevent Approve crashes
        c.execute("UPDATE enrollments SET id = LOWER(HEX(RANDOMBLOB(16))) WHERE id IS NULL")
        
        # SPECIAL: Bridge approved -> is_active for questions bank
        try:
            c.execute("UPDATE questions SET is_active = approved WHERE is_active IS NULL")
        except sqlite3.OperationalError:
            pass

        conn.commit()

def _seed_data(c):
    """Seed the database with a clean, universal demo lecturer and course."""
    lecturer_id = "lecturer-demo-id"
    c.execute("INSERT OR REPLACE INTO users (id, name, email, password, role, status, created_at) VALUES (?,?,?,?,?,'approved','2024-01-01 00:00:00')",
              (lecturer_id, "Alper Tunca", "atunca96@gmail.com", "ALper2002@", "lecturer"))
    
    course_id = "11111"
    c.execute("INSERT OR IGNORE INTO courses (id, name, semester, textbook, lecturer_id, code, language, level) VALUES (?,?,?,?,?,?,?,?)",
              (course_id, "Demo Classroom", "Spring 2026", "AI Generated", lecturer_id, "11111", "Turkish", "A1"))

def _get_demo_curriculum():
    return [
        {
            "number": 1,
            "title": "Welcome to Language Learning",
            "topics": [{"type": "vocabulary", "title": "Greetings & Basics", "difficulty": "A1", "content": {"words": {"Merhaba": "Hello"}}}]
        }
    ]

if __name__ == "__main__":
    init_db()
