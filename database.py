import sqlite3
import json
import random
import os
import uuid
import re
from datetime import datetime, timezone, timedelta

# Path Configuration
DATA_DIR = os.path.join(os.getcwd(), "data")
BOOKS_DIR = os.path.join(os.getcwd(), "public", "books")
DB_PATH = os.path.join(DATA_DIR, "aula.db")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BOOKS_DIR, exist_ok=True)

def _uid(): return str(uuid.uuid4())

def get_db():
    """Context manager for database connections (Backward compat)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
            activity_status TEXT DEFAULT 'idle',
            activity_progress INTEGER DEFAULT 0,
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

        c.execute('''CREATE TABLE IF NOT EXISTS responses (
            id TEXT PRIMARY KEY,
            student_id TEXT,
            question_id TEXT,
            answer TEXT,
            correct_answer TEXT,
            is_correct INTEGER,
            context_type TEXT,
            context_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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

        c.execute('''CREATE TABLE IF NOT EXISTS enrollments (
            student_id TEXT,
            course_id TEXT,
            status TEXT DEFAULT 'pending',
            pin TEXT,
            enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(student_id, course_id)
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
            report_data TEXT,
            week_start TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Run seeding if empty
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            print("[DB] Seeding initial data...")
            _seed_data(c)
        
        conn.commit()

    # ── MIGRATIONS (For existing persistent volumes) ────────
    _run_migrations()

def _run_migrations():
    """Manually add missing columns to existing tables if they were created with old schema."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        migrations = [
            ("courses", "progress", "INTEGER DEFAULT 0"),
            ("courses", "activity_status", "TEXT DEFAULT 'idle'"),
            ("courses", "activity_progress", "INTEGER DEFAULT 0"),
            ("courses", "language", "TEXT DEFAULT 'Turkish'"),
            ("courses", "level", "TEXT DEFAULT 'A1'"),
            ("quizzes", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("assignments", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("enrollments", "enrolled_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("chapters", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("topics", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("users", "status", "TEXT DEFAULT 'approved'")
        ]
        
        for table, column, definition in migrations:
            try:
                # Check if column exists
                cursor = c.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                if column not in columns:
                    print(f"[MIGRATION] Adding column {column} to {table}...")
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            except Exception as e:
                print(f"[MIGRATION ERROR] Failed to migrate {table}.{column}: {e}")
        
        conn.commit()

def _seed_data(c):
    """Seed the database with a clean, universal demo lecturer and course."""

    # ── Lecturer ────────────────────────────────────────────
    lecturer_id = "lecturer-demo-id"
    c.execute("INSERT OR IGNORE INTO users (id, name, email, password, role, status, created_at) VALUES (?,?,?,?,?,'approved','2024-01-01 00:00:00')",
              (lecturer_id, "Alper Tunca", "atunca96@gmail.com", "ALper2002@", "lecturer"))
    
    existing = c.execute("SELECT id FROM users WHERE email=?", ("atunca96@gmail.com",)).fetchone()
    if existing:
        lecturer_id = existing[0]

    # ── Course ──────────────────────────────────────────────
    course_id = "11111"
    c.execute("INSERT OR IGNORE INTO courses (id, name, semester, textbook, lecturer_id, code, language, level) VALUES (?,?,?,?,?,?,?,?)",
              (course_id, "Demo Classroom", "Spring 2026", "AI Generated", lecturer_id, "11111", "Turkish", "A1"))

    # ── Demo Curriculum ────────────────
    curriculum = _get_demo_curriculum()

    for ch in curriculum:
        chapter_id = f"ch-demo-{ch['number']}"
        c.execute("INSERT OR IGNORE INTO chapters VALUES (?,?,?,?)",
                  (chapter_id, course_id, ch["number"], ch["title"]))

        for i, topic in enumerate(ch["topics"]):
            topic_id = f"topic-demo-{ch['number']}-{i+1}"
            c.execute("INSERT OR IGNORE INTO topics VALUES (?,?,?,?,?,?,?,?)",
                      (topic_id, chapter_id, topic["type"], topic["title"],
                       topic["difficulty"], json.dumps(topic["content"]), None, i))

def _get_demo_curriculum():
    """Generic demo curriculum structure."""
    return [
        {
            "number": 1,
            "title": "Welcome to Language Learning",
            "topics": [
                {
                    "type": "vocabulary",
                    "title": "Greetings & Basics",
                    "difficulty": "A1",
                    "content": {
                        "words": {
                            "Merhaba": "Hello",
                            "Nasılsın?": "How are you?",
                            "Teşekkür ederim": "Thank you",
                            "Güle güle": "Goodbye"
                        }
                    }
                }
            ]
        }
    ]

def _generate_seed_questions(topic):
    """Generic placeholder for seed questions."""
    return []

def _categorize_words(words):
    """Placeholder for categorization logic."""
    return {}

if __name__ == "__main__":
    init_db()
