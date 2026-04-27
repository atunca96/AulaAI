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
    # Debug directory contents to verify mount
    try:
        print(f"[DEBUG] Root contents: {os.listdir('/app')}")
        if os.path.exists('/app/data'):
            print(f"[DEBUG] Data contents: {os.listdir('/app/data')}")
    except: pass
else:
    DATA_DIR = os.path.join(os.getcwd(), "data")

BOOKS_DIR = os.path.join(DATA_DIR, "books")
# Universal discovery: Look for ANY existing database to prevent data loss
potential_paths = [
    "/app/data/aula.db",
    "/app/database.sqlite",
    "/app/data/prototype.db",
    "/app/aula.db",
    os.path.join(os.getcwd(), "aula.db"),
    os.path.join(os.getcwd(), "data", "aula.db")
]

IS_GHOST_DB = False
if IS_RAILWAY:
    # 1. Check for ANY existing data across all potential paths
    found_path = None
    for path in potential_paths:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            print(f"[DB] FOUND EXISTING DATA at {path} ({os.path.getsize(path)} bytes)")
            found_path = path
            break
    
    if found_path:
        DB_PATH = found_path
        IS_GHOST_DB = False
    else:
        # 2. If no data, wait for the VOLUME MOUNT itself to appear
        print("[DB] No existing data found. Verifying volume mount...")
        for attempt in range(30):
            if os.path.exists("/app/data"):
                print("[DB] Persistent volume /app/data detected. Starting fresh.")
                DB_PATH = "/app/data/aula.db"
                IS_GHOST_DB = True # Fresh start on the real volume
                break
            print(f"[DB] Waiting for Railway volume mount... ({attempt+1}/30)")
            time.sleep(1)
        else:
            print("[FATAL ERROR] Persistent volume NOT FOUND after 30s. Crashing to force restart.")
            import sys
            sys.exit(1)
else:
    DB_PATH = os.path.join(os.getcwd(), "data", "aula.db")
    IS_GHOST_DB = not os.path.exists(DB_PATH)
    IS_GHOST_DB = not os.path.exists(DB_PATH)

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
    # Persistence Sentinel: NEVER allow a connection if the volume is missing on Railway
    if IS_RAILWAY and not os.path.exists("/app/data"):
        print("[CRITICAL] VOLUME DISCONNECTED DURING OPERATION! Blocking DB access to prevent data loss.")
        raise ConnectionError("Railway volume disconnected. Please check your dashboard.")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL") # High performance concurrency
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
        
        # ALWAYS ensure the primary lecturer has the correct password on start
        lecturer_id = "lecturer-demo-id"
        c.execute("INSERT OR REPLACE INTO users (id, name, email, password, role, status, created_at) VALUES (?,?,?,?,?,'approved','2024-01-01 00:00:00')",
                  (lecturer_id, "Alper Tunca", "atunca96@gmail.com", "ALper2002@", "lecturer"))
        db.commit()

        # Run demo course seeding ONLY if the DB is actually empty
        if not IS_GHOST_DB and c.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0:
            print("[DB] Seeding demo course...")
            _seed_course_only(c)
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

def _seed_course_only(c):
    """Seed the database with a clean, universal demo course."""
    lecturer_id = "lecturer-demo-id"
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
