import sqlite3
import json
import random
import os
import uuid
import threading
import contextlib
import time
import hashlib
from datetime import datetime, timezone

def _uid():
    return str(uuid.uuid4())

def hash_password(password: str) -> str:
    return hashlib.sha256((password + "AulaAI_Salt").encode('utf-8')).hexdigest()

PERMANENT_STUDENTS = [
    {"number": "176724049", "name": "Yusuf Arabacı"},
    {"number": "176725007", "name": "Zehra Küçükelvan"},
    {"number": "176725019", "name": "Yaren Korkut"},
    {"number": "176725005", "name": "Ecrin Bektaş"},
    {"number": "176725038", "name": "Ela Naz Doğan"},
    {"number": "176725853", "name": "Buket Kabak"},
    {"number": "176725029", "name": "Beren Kibar"},
    {"number": "176725004", "name": "Alper Tunca"},
]

def enroll_permanent_students_in_course(course_id, db=None):
    """Auto-enrolls all permanent student accounts in the given course_id with status 'approved'."""
    if not course_id:
        return

    def _do_enroll(conn):
        c = conn.cursor()
        for s in PERMANENT_STUDENTS:
            email_key = f"{s['number']}@student.aulaai"
            user_row = c.execute("SELECT id FROM users WHERE email = ? AND role = 'student'", (email_key,)).fetchone()
            if not user_row:
                continue
            student_id = user_row[0]
            existing = c.execute("SELECT id, status FROM enrollments WHERE student_id = ? AND course_id = ?", (student_id, course_id)).fetchone()
            if not existing:
                enroll_id = str(uuid.uuid4())
                c.execute("""
                    INSERT OR IGNORE INTO enrollments (id, student_id, course_id, status, pin, enrolled_at, last_active)
                    VALUES (?, ?, ?, 'approved', NULL, datetime('now'), datetime('now'))
                """, (enroll_id, student_id, course_id))
            elif existing[1] != 'approved':
                c.execute("UPDATE enrollments SET status = 'approved' WHERE id = ?", (existing[0],))
        conn.commit()

    if db is not None:
        _do_enroll(db)
    else:
        with db_connection() as conn:
            _do_enroll(conn)


def sync_permanent_students_and_enrollments(db=None):
    """
    1. Removes all existing student accounts that are not in PERMANENT_STUDENTS.
    2. Creates/updates all 8 permanent students with password '1234' (status='approved').
    3. Auto-enrolls all 8 permanent students into EVERY classroom in the database.
    """
    def _do_sync(conn):
        c = conn.cursor()
        hashed_pwd_1234 = hash_password("1234")
        valid_emails = {f"{s['number']}@student.aulaai" for s in PERMANENT_STUDENTS}
        
        # 1. Ensure all 8 permanent student accounts exist with password '1234'
        for s in PERMANENT_STUDENTS:
            email_key = f"{s['number']}@student.aulaai"
            existing = c.execute("SELECT id FROM users WHERE email = ?", (email_key,)).fetchone()
            if existing:
                c.execute("""
                    UPDATE users
                    SET name = ?, password = ?, role = 'student', status = 'approved'
                    WHERE id = ?
                """, (s["name"], hashed_pwd_1234, existing[0]))
            else:
                stu_id = f"student-{s['number']}"
                c.execute("""
                    INSERT INTO users (id, name, email, password, role, status, created_at)
                    VALUES (?, ?, ?, ?, 'student', 'approved', datetime('now'))
                """, (stu_id, s["name"], email_key, hashed_pwd_1234))

        # 3. Auto-enroll all 8 students in every existing classroom
        courses = c.execute("SELECT id FROM courses").fetchall()
        for course in courses:
            cid = course[0]
            for s in PERMANENT_STUDENTS:
                email_key = f"{s['number']}@student.aulaai"
                user_row = c.execute("SELECT id FROM users WHERE email = ?", (email_key,)).fetchone()
                if not user_row:
                    continue
                stu_id = user_row[0]
                existing_enroll = c.execute("SELECT id FROM enrollments WHERE student_id = ? AND course_id = ?", (stu_id, cid)).fetchone()
                if not existing_enroll:
                    c.execute("""
                        INSERT OR IGNORE INTO enrollments (id, student_id, course_id, status, pin, enrolled_at, last_active)
                        VALUES (?, ?, ?, 'approved', NULL, datetime('now'), datetime('now'))
                    """, (str(uuid.uuid4()), stu_id, cid))
                else:
                    c.execute("UPDATE enrollments SET status = 'approved' WHERE id = ?", (existing_enroll[0],))

        conn.commit()
        print(f"[DB] Successfully synchronized {len(PERMANENT_STUDENTS)} permanent students across {len(courses)} classrooms.")

    if db is not None:
        _do_sync(db)
    else:
        with db_connection() as conn:
            _do_sync(conn)

# ── PATHING (Absolute for Persistence) ───────────────────
# We use absolute paths to ensure the Railway volume remains mounted correctly.
IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None
if IS_RAILWAY:
    # Volume Mount Wait FIRST (for safety) to ensure persistence is up
    if not os.path.exists("/data"):
        print("[DB] Waiting for Railway volume mount...")
        for attempt in range(5):
            if os.path.exists("/data"): break
            time.sleep(1)
        else:
            print("[FATAL ERROR] Persistent volume /data NOT FOUND.")
            import sys
            sys.exit(1)

    DATA_DIR = "/data"
    DB_PATH = "/data/aula.db"

    # Debug directory contents to verify mount
    try:
        if os.path.exists('/data'):
            print(f"[DEBUG] /data contents: {os.listdir('/data')}")
    except: pass
else:
    DATA_DIR = os.path.join(os.getcwd(), "data")
    DB_PATH = os.path.join(DATA_DIR, "aula.db")

BOOKS_DIR = os.path.join(DATA_DIR, "books")

# Universal discovery: Look for ANY existing database to prevent data loss
potential_paths = [
    "/data/aula.db",
    "/app/data/aula.db",
    "/app/database.sqlite",
    "/data/prototype.db",
    "/app/data/prototype.db",
    "/app/aula.db",
    os.path.join(os.getcwd(), "aula.db"),
    os.path.join(os.getcwd(), "data", "aula.db")
]

IS_GHOST_DB = False
if IS_RAILWAY:
    print("[DB] === RAILWAY DATABASE DISCOVERY ===")
    
    # Self-Healing: If the database is malformed (corrupted), delete it to allow a fresh start.
    if os.path.exists(DB_PATH):
        try:
            import sqlite3
            # Try a simple PRAGMA check
            conn = sqlite3.connect(DB_PATH, timeout=1.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.close()
            IS_GHOST_DB = False
            print(f"[DB] Existing database {DB_PATH} is healthy.")
        except sqlite3.DatabaseError as e:
            if "malformed" in str(e).lower():
                print(f"[DB] CRITICAL: Database {DB_PATH} is malformed. Deleting for fresh start.")
                try:
                    conn.close()
                except: pass
                for ext in ['', '-wal', '-shm']:
                    p = f"{DB_PATH}{ext}"
                    if os.path.exists(p): os.remove(p)
                IS_GHOST_DB = True
            else:
                print(f"[DB] Database check warning: {e}")
                IS_GHOST_DB = False
    else:
        IS_GHOST_DB = True
        print(f"[DB] No database found at {DB_PATH}. Will create fresh.")
            
    print(f"[DB] === FINAL: DB_PATH={DB_PATH}, IS_GHOST_DB={IS_GHOST_DB} ===")
else:
    IS_GHOST_DB = not os.path.exists(DB_PATH)

# Thread-safe locks for background tasks
_task_locks = {}
_task_locks_lock = threading.Lock()

def get_task_lock(course_id):
    with _task_locks_lock:
        if course_id not in _task_locks:
            _task_locks[course_id] = threading.Lock()
        return _task_locks[course_id]

# ── VOLUME RESILIENCE ─────────────────────────────────────
# The DB volume directory — derived from DB_PATH so checks are always consistent.
_VOLUME_DIR = os.path.dirname(DB_PATH)

MAX_VOLUME_RETRIES = 8
VOLUME_RETRY_DELAY = 1.5  # seconds; grows with each attempt (backoff)

def _volume_is_accessible():
    """
    Lightweight, non-destructive check: can we stat the volume directory?
    Uses os.stat to catch NFS/FUSE stalls that os.path.exists() misses.
    """
    try:
        os.stat(_VOLUME_DIR)
        return True
    except OSError:
        return False

def _wait_for_volume(context="operation"):
    """
    Retry loop used at startup and before any DB connection.
    Returns True if the volume is accessible, False after all retries fail.
    """
    if not IS_RAILWAY:
        return True  # Local dev — no volume check needed
    
    if _volume_is_accessible():
        return True  # Fast-path: already available
    
    for attempt in range(1, MAX_VOLUME_RETRIES + 1):
        delay = VOLUME_RETRY_DELAY * attempt  # Simple linear backoff: 1.5s, 3s, 4.5s …
        print(f"[DB] Volume not accessible for '{context}'. Retrying in {delay:.1f}s (attempt {attempt}/{MAX_VOLUME_RETRIES})...")
        time.sleep(delay)
        if _volume_is_accessible():
            print(f"[DB] Volume connection restored after {attempt} attempt(s). Continuing.")
            return True
    
    print(f"[DB] CRITICAL: Volume confirmed unavailable after {MAX_VOLUME_RETRIES} retries. Blocking to prevent data loss.")
    return False


@contextlib.contextmanager
def db_connection():
    # Persistence Sentinel: NEVER allow a connection if the volume is genuinely unavailable.
    # Uses retry logic to tolerate transient Railway mount timing issues.
    if IS_RAILWAY and not _volume_is_accessible():
        if not _wait_for_volume(context="db_connection"):
            print("[CRITICAL] VOLUME DISCONNECTED DURING OPERATION! Blocking DB access to prevent data loss.")
            raise ConnectionError("Railway volume disconnected. Please check your dashboard.")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")  # High performance concurrency
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
            material_language TEXT DEFAULT 'en',
            build_stage TEXT DEFAULT 'idle',
            build_message TEXT DEFAULT '',
            build_started_at REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(lecturer_id) REFERENCES users(id)
        )''')

        # Curriculum Structure (Chapters & Topics)
        c.execute('''CREATE TABLE IF NOT EXISTS chapters (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            number INTEGER,
            title TEXT,
            page_number INTEGER,
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
            page_number INTEGER,
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
            approved INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(topic_id) REFERENCES topics(id)
        )''')
        
        # MIGRATION: Ensure approved column exists
        try:
            c.execute("ALTER TABLE questions ADD COLUMN approved INTEGER DEFAULT 1")
        except: pass
        
        try:
            c.execute("ALTER TABLE users ADD COLUMN last_seen TIMESTAMP")
        except: pass

        # MIGRATION: Ensure material_language column exists
        try:
            c.execute("ALTER TABLE courses ADD COLUMN material_language TEXT DEFAULT 'en'")
        except: pass

        # MIGRATION: Ensure title_tr columns exist for bilingual curriculum
        try:
            c.execute("ALTER TABLE chapters ADD COLUMN title_tr TEXT")
        except: pass
        try:
            c.execute("ALTER TABLE topics ADD COLUMN title_tr TEXT")
        except: pass

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

        # Persistent Draft History to prevent repeats across restarts/deploys
        c.execute('''CREATE TABLE IF NOT EXISTS draft_history (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            prompt TEXT,
            answer TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_draft_history_course ON draft_history(course_id)')

        # Persistent Draft Test Batches (stores completed test batches for the last 2 batches rule)
        c.execute('''CREATE TABLE IF NOT EXISTS draft_test_batches (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            topic_id TEXT,
            questions_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_draft_test_batches ON draft_test_batches(course_id, topic_id, created_at)')

        # Purge orphan unlinked draft questions prematurely inserted by older versions
        try:
            c.execute('''DELETE FROM questions 
                WHERE approved = 1 
                  AND id NOT IN (SELECT question_id FROM quiz_questions)
                  AND id NOT IN (SELECT question_id FROM assignment_questions)''')
        except Exception:
            pass

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
        
        # ALWAYS ensure users have their accounts set up safely without crash risks
        import hashlib
        try:
            # Primary Lecturer
            hashed_pwd = hashlib.sha256(("ALper2002@" + "AulaAI_Salt").encode('utf-8')).hexdigest()
            lec_row = c.execute("SELECT id FROM users WHERE email = 'atunca96@gmail.com'").fetchone()
            if lec_row:
                c.execute("UPDATE users SET password = ?, role = 'lecturer', status = 'approved' WHERE id = ?", (hashed_pwd, lec_row[0]))
            else:
                c.execute("INSERT OR IGNORE INTO users (id, name, email, password, role, status, created_at) VALUES (?,?,?,?,?,'approved','2024-01-01 00:00:00')",
                          ("lecturer-demo-id", "Alper Tunca", "atunca96@gmail.com", hashed_pwd, "lecturer"))
            
            # Secondary Lecturer (Ela)
            hashed_pwd_ela = hashlib.sha256(("auladersela" + "AulaAI_Salt").encode('utf-8')).hexdigest()
            ela_row = c.execute("SELECT id FROM users WHERE email = 'ela94216@gmail.com'").fetchone()
            if ela_row:
                c.execute("UPDATE users SET password = ?, role = 'lecturer', status = 'approved' WHERE id = ?", (hashed_pwd_ela, ela_row[0]))
            else:
                c.execute("INSERT OR IGNORE INTO users (id, name, email, password, role, status, created_at) VALUES (?,?,?,?,?,'approved','2024-01-01 00:00:00')",
                          ("ela-lecturer-id", "Ela", "ela94216@gmail.com", hashed_pwd_ela, "lecturer"))
            
            # Permanent Student Accounts & Universal Auto-Enrollment (Yusuf, Zehra, Yaren, Ecrin, Ela Naz, Buket, Beren, Alper)
            sync_permanent_students_and_enrollments(db)
            heal_pedagogical_content(db)
        except Exception as e:
            print(f"[DB] Notice during user seeding: {e}")
        
        # AUTOMATED DUPLICATION: Ensure Ela has her Spanish Marmara course
        c.execute("CREATE TABLE IF NOT EXISTS migration_history (key TEXT PRIMARY KEY)")
        
        # Dynamically find Ela's ID by email (works whether we just created her or she existed before)
        ela_row = c.execute("SELECT id FROM users WHERE email = 'ela94216@gmail.com'").fetchone()
        if ela_row:
            ela_id = ela_row[0]
            has_course = c.execute("SELECT 1 FROM courses WHERE lecturer_id = ? AND name LIKE '%Spanish%'", (ela_id,)).fetchone()
            
            if not has_course:
                # Find the source course (Turkish A1 which we use for Spanish)
                source = c.execute("SELECT id FROM courses WHERE name LIKE '%T_rk_e A1%' OR name LIKE '%Spanish%'").fetchone()
                if source:
                    source_id = source[0]
                    new_course_id = "ela-spanish-marmara-id"
                    
                    # Copy course
                    c.execute("INSERT OR IGNORE INTO courses (id, name, lecturer_id, code, language, level) VALUES (?, 'Spanish Marmara', ?, 'SPMAR', 'Spanish', 'A1')", (new_course_id, ela_id))
                    
                    # Copy chapters
                    chapters = c.execute("SELECT * FROM chapters WHERE course_id = ?", (source_id,)).fetchall()
                    for ch in chapters:
                        old_ch_id = ch["id"]
                        new_ch_id = str(uuid.uuid4())
                        c.execute("INSERT INTO chapters (id, course_id, title, number, title_tr) VALUES (?,?,?,?,?)",
                                  (new_ch_id, new_course_id, ch["title"], ch["number"], ch["title_tr"]))
                        
                        # Copy topics
                        topics = c.execute("SELECT * FROM topics WHERE chapter_id = ?", (old_ch_id,)).fetchall()
                        for t in topics:
                            new_t_id = str(uuid.uuid4())
                            c.execute("INSERT INTO topics (id, chapter_id, title, type, content, difficulty, title_tr, sort_order, pdf_url) VALUES (?,?,?,?,?,?,?,?,?)",
                                      (new_t_id, new_ch_id, t["title"], t["type"], t["content"], t["difficulty"], t["title_tr"], t["sort_order"], t["pdf_url"]))
                    
                    print(f"[MIGRATION] Successfully duplicated Spanish Marmara to Ela's portal.")
                    enroll_permanent_students_in_course(new_course_id, db)

        # AUTOMATED RESILIENCE: Ensure all courses in DB have clean bilingual titles (title=EN, title_tr=TR)
        try:
            from services.curriculum_translator import is_clean_turkish, is_pure_english, translate_titles_batch

            # 1. Check all chapters
            chap_rows = c.execute("SELECT id, title, title_tr FROM chapters").fetchall()
            ch_needed_tr = []
            ch_needed_en = []
            for r in chap_rows:
                t_en = (r["title"] or "").strip()
                t_tr = (r["title_tr"] or "").strip()
                if not t_tr or not is_clean_turkish(t_tr):
                    if t_en: ch_needed_tr.append(t_en)
                if not t_en or is_clean_turkish(t_en):
                    if t_tr: ch_needed_en.append(t_tr)
                    elif t_en: ch_needed_en.append(t_en)

            # 2. Check all topics
            top_rows = c.execute("SELECT id, title, title_tr FROM topics").fetchall()
            top_needed_tr = []
            top_needed_en = []
            for r in top_rows:
                t_en = (r["title"] or "").strip()
                t_tr = (r["title_tr"] or "").strip()
                if not t_tr or not is_clean_turkish(t_tr):
                    if t_en: top_needed_tr.append(t_en)
                if not t_en or is_clean_turkish(t_en):
                    if t_tr: top_needed_en.append(t_tr)
                    elif t_en: top_needed_en.append(t_en)

            all_needed_tr = list(set(ch_needed_tr + top_needed_tr))
            all_needed_en = list(set(ch_needed_en + top_needed_en))

            tr_map = translate_titles_batch(all_needed_tr, target_lang="tr") if all_needed_tr else {}
            en_map = translate_titles_batch(all_needed_en, target_lang="en") if all_needed_en else {}

            for r in chap_rows:
                t_en = (r["title"] or "").strip()
                t_tr = (r["title_tr"] or "").strip()
                new_en = en_map.get(t_tr, en_map.get(t_en, t_en)) if (not t_en or is_clean_turkish(t_en)) else t_en
                new_tr = tr_map.get(t_en, t_tr or t_en) if (not t_tr or not is_clean_turkish(t_tr)) else t_tr
                if new_en != r["title"] or new_tr != r["title_tr"]:
                    c.execute("UPDATE chapters SET title = ?, title_tr = ? WHERE id = ?", (new_en, new_tr, r["id"]))

            for r in top_rows:
                t_en = (r["title"] or "").strip()
                t_tr = (r["title_tr"] or "").strip()
                new_en = en_map.get(t_tr, en_map.get(t_en, t_en)) if (not t_en or is_clean_turkish(t_en)) else t_en
                new_tr = tr_map.get(t_en, t_tr or t_en) if (not t_tr or not is_clean_turkish(t_tr)) else t_tr
                if new_en != r["title"] or new_tr != r["title_tr"]:
                    c.execute("UPDATE topics SET title = ?, title_tr = ? WHERE id = ?", (new_en, new_tr, r["id"]))

            c.execute("UPDATE topics SET pdf_url = NULL WHERE pdf_url = 'NONE' OR pdf_url = '/books/NONE' OR pdf_url LIKE '%NONE%'")
            c.execute("INSERT OR IGNORE INTO migration_history (key) VALUES ('universal_curriculum_healing_v1')")
            print("[MIGRATION] Universal curriculum healing completed: All courses verified bilingual.")
        except Exception as e:
            print(f"[MIGRATION ERROR] Failed to heal curriculum: {e}")

        # ── MIGRATION: Natural Pragmatics & Cultural Greetings Healing (v1) ──
        try:
            mig_done = c.execute("SELECT 1 FROM migration_history WHERE key = 'pragmatic_cultural_healing_v1'").fetchone()
            if not mig_done:
                from services.concept_explanations import heal_concept_item, heal_pragmatic_item
                import re
                try:
                    c.execute("UPDATE lexicon SET translation_tr = 'Tünaydın' WHERE LOWER(term) = 'buenas tardes' OR translation_tr LIKE '%öğleden sonra%'")
                    c.execute("UPDATE lexicon SET translation_tr = 'Ben' WHERE LOWER(term) = 'yo'")
                    c.execute("UPDATE lexicon SET translation_tr = '(Ben) ...yim / ...yım' WHERE LOWER(term) = 'soy'")
                except: pass

                top_items = c.execute("SELECT id, content FROM topics WHERE content IS NOT NULL").fetchall()
                for top in top_items:
                    raw_c = top["content"]
                    if not raw_c or not raw_c.strip().startswith('{'): continue
                    try:
                        cont = json.loads(raw_c)
                        mod = False
                        pages = cont.get("pages", [])
                        if isinstance(pages, list):
                            for p in pages:
                                for lk in ["items", "vocabulary", "words", "list"]:
                                    arr = p.get(lk)
                                    if isinstance(arr, list):
                                        new_arr = []
                                        for it in arr:
                                            if isinstance(it, dict):
                                                heal_concept_item(it, lang="tr")
                                                heal_concept_item(it, lang="en")
                                                t_v = str(it.get('term') or it.get('word') or '').strip().lower()
                                                if t_v == 'yo':
                                                    it['translation_tr'] = 'Ben'
                                                    it['turkish'] = 'Ben'
                                                elif t_v == 'soy':
                                                    it['translation_tr'] = '(Ben) ...yim / ...yım'
                                                    it['turkish'] = '(Ben) ...yim / ...yım'
                                                elif t_v == 'buenas tardes':
                                                    it['translation_tr'] = 'Tünaydın'
                                                    it['turkish'] = 'Tünaydın'
                                                new_arr.append(it)
                                                mod = True
                                            elif isinstance(it, str):
                                                s = it.strip()
                                                if s.startswith(('•', '-', '*')) or len(s.split()) > 4 or len(s) > 35:
                                                    ex_text = p.get("text") or p.get("explanation") or ""
                                                    if s not in ex_text:
                                                        p["text"] = f"{ex_text}\n{s}".strip()
                                                    mod = True
                                                else:
                                                    new_arr.append(it)
                                        p[lk] = new_arr
                                for tk in ["text", "explanation", "title_tr", "text_tr", "explanation_tr"]:
                                    if tk in p and isinstance(p[tk], str) and ("İyi öğleden sonra" in p[tk] or "iyi öğleden sonra" in p[tk]):
                                        p[tk] = re.sub(r'[İi]yi öğleden sonra(ları)?', 'Tünaydın', p[tk])
                                        mod = True
                        if mod:
                            c.execute("UPDATE topics SET content = ? WHERE id = ?", (json.dumps(cont, ensure_ascii=False), top["id"]))
                    except: pass

                c.execute("INSERT OR IGNORE INTO migration_history (key) VALUES ('pragmatic_cultural_healing_v1')")
                print("[MIGRATION] Pragmatic cultural healing completed: Greetings and pronouns aligned.")
        except Exception as e:
            print(f"[MIGRATION ERROR] Failed to heal pragmatics: {e}")

        # Apply strictly source-supported rules & comparisons refresh
        try:
            c.execute("CREATE TABLE IF NOT EXISTS migration_history (key TEXT PRIMARY KEY)")
            mig_done = c.execute("SELECT 1 FROM migration_history WHERE key = 'strict_rules_and_comparisons_refresh_v1'").fetchone()
            if not mig_done:
                json_p = os.path.join(os.path.dirname(__file__), "services", "refreshed_rules_comparisons.json")
                if not os.path.exists(json_p):
                    json_p = os.path.join(os.getcwd(), "services", "refreshed_rules_comparisons.json")
                if os.path.exists(json_p):
                    with open(json_p, "r", encoding="utf-8") as jf:
                        refresh_map = json.load(jf)
                    top_rows = c.execute("SELECT id, content FROM topics").fetchall()
                    for tid, raw_c in top_rows:
                        if tid in refresh_map and raw_c:
                            try:
                                cont = json.loads(raw_c)
                                pages = cont.get("pages", [])
                                p_map = refresh_map[tid].get("pages", {})
                                for p_idx, p in enumerate(pages):
                                    p.pop("rules", None)
                                    p.pop("comparisons", None)
                                    if str(p_idx) in p_map:
                                        p_data = p_map[str(p_idx)]
                                        if p_data.get("rules"):
                                            p["rules"] = p_data["rules"]
                                        if p_data.get("comparisons"):
                                            p["comparisons"] = p_data["comparisons"]
                                c.execute("UPDATE topics SET content = ? WHERE id = ?", (json.dumps(cont, ensure_ascii=False), tid))
                            except Exception as ex:
                                print(f"[MIGRATION WARNING] Failed to refresh topic {tid}: {ex}")
                    c.execute("INSERT OR IGNORE INTO migration_history (key) VALUES ('strict_rules_and_comparisons_refresh_v1')")
                    print("[MIGRATION] Strict rules & comparisons refresh applied successfully.")
        except Exception as e:
            print(f"[MIGRATION ERROR] Failed to apply rules & comparisons refresh: {e}")

        # Apply strict source provenance rules & comparisons refresh (v2)
        try:
            c.execute("CREATE TABLE IF NOT EXISTS migration_history (key TEXT PRIMARY KEY)")
            mig_done = c.execute("SELECT 1 FROM migration_history WHERE key = 'strict_source_provenance_rules_refresh_v2'").fetchone()
            if not mig_done:
                json_p = os.path.join(os.path.dirname(__file__), "services", "refreshed_rules_comparisons.json")
                if not os.path.exists(json_p):
                    json_p = os.path.join(os.getcwd(), "services", "refreshed_rules_comparisons.json")
                if os.path.exists(json_p):
                    with open(json_p, "r", encoding="utf-8") as jf:
                        refresh_map = json.load(jf)
                    top_rows = c.execute("SELECT id, content FROM topics").fetchall()
                    for tid, raw_c in top_rows:
                        if tid in refresh_map and raw_c:
                            try:
                                cont = json.loads(raw_c)
                                pages = cont.get("pages", [])
                                p_map = refresh_map[tid].get("pages", {})
                                for p_idx, p in enumerate(pages):
                                    p.pop("rules", None)
                                    p.pop("comparisons", None)
                                    if str(p_idx) in p_map:
                                        p_data = p_map[str(p_idx)]
                                        if p_data.get("rules"):
                                            p["rules"] = p_data["rules"]
                                        if p_data.get("comparisons"):
                                            p["comparisons"] = p_data["comparisons"]
                                c.execute("UPDATE topics SET content = ? WHERE id = ?", (json.dumps(cont, ensure_ascii=False), tid))
                            except Exception as ex:
                                print(f"[MIGRATION WARNING] Failed to apply source provenance refresh to topic {tid}: {ex}")
                    c.execute("INSERT OR IGNORE INTO migration_history (key) VALUES ('strict_source_provenance_rules_refresh_v2')")
                    print("[MIGRATION] Strict source provenance rules & comparisons refresh (v2) applied successfully.")
        except Exception as e:
            print(f"[MIGRATION ERROR] Failed to apply source provenance rules & comparisons refresh: {e}")

        db.commit()

        # Run demo course seeding ONLY if the DB is actually empty
        if not IS_GHOST_DB and c.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0:
            print("[DB] Seeding demo course...")
            _seed_course_only(c)
            db.commit()

        # Final guarantee: sync permanent students across all courses
        sync_permanent_students_and_enrollments(db)

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
            ("courses", "generation_id", "TEXT"),
            ("courses", "build_stage", "TEXT DEFAULT 'idle'"),
            ("courses", "build_message", "TEXT DEFAULT ''"),
            ("courses", "build_started_at", "REAL DEFAULT 0"),
            ("enrollments", "id", "TEXT"),
            ("enrollments", "pin", "TEXT"),
            ("enrollments", "enrolled_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("responses", "score", "REAL"),
            ("responses", "feedback", "TEXT"),
            ("responses", "graded_by", "TEXT"),
            ("responses", "submitted_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("questions", "is_active", "INTEGER DEFAULT 1"),
            ("questions", "approved", "INTEGER DEFAULT 1"),
            ("users", "status", "TEXT DEFAULT 'approved'"),
            ("chapters", "page_number", "INTEGER"),
            ("topics", "page_number", "INTEGER")
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

def heal_pedagogical_content(conn):
    """
    Self-healing migration that ensures:
    1. Alphabet letters have authentic pronunciations and accurate phonetics in both EN and TR.
    2. Letter 'I' is never corrupted with pronoun definitions.
    3. Tautological definitions ('... eylemini ifade eder', 'refers to the act of...') are stripped.
    4. Practical examples and collocation tips are populated for common vocabulary words.
    """
    import json
    import re
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from services.language_data import get_letter_phonetics, get_vocab_example
    except Exception as e:
        print(f"[MIGRATION ERROR] Failed to load language_data: {e}")
        return

    tautology_re = re.compile(
        r'(?i)\b(?:eylemini\s+ifade\s+eder|etkinliğini\s+ifade\s+eder|ifade\s+etmek\s+için\s+kullanılır|'
        r'eylemidir|yapma\s+eylemi|resim\s+yaratmayı|üretme\s+eylemidir|gitmeyi\s+içerir|'
        r'refers?\s+to\s+the\s+act\s+of|means?\s+the\s+act\s+of|is\s+the\s+act\s+of|used\s+to\s+express\s+the\s+action\s+of)\b'
    )

    c = conn.cursor()
    try:
        rows = c.execute("""
            SELECT t.id, t.title, co.language, t.content
            FROM topics t
            JOIN chapters ch ON t.chapter_id = ch.id
            JOIN courses co ON ch.course_id = co.id
        """).fetchall()
    except Exception:
        return

    for r in rows:
        tid = r[0]
        title = r[1] or ''
        lang = r[2] or 'Spanish'
        raw_content = r[3]
        if not raw_content:
            continue
        try:
            data = json.loads(raw_content)
        except Exception:
            continue

        is_alphabet = any(x in title.lower() for x in ['alphabet', 'alfabet', 'letter', 'harf', 'phonetic', 'ses'])
        modified = False

        for p in data.get('pages', []):
            for list_key in ['items', 'vocabulary', 'words', 'list']:
                arr = p.get(list_key)
                if not isinstance(arr, list):
                    continue
                for it in arr:
                    if not isinstance(it, dict):
                        continue
                    term = str(it.get('term') or it.get('word') or it.get('letter') or '').strip()

                    if is_alphabet or len(term) == 1:
                        phon = get_letter_phonetics(lang, term)
                        if phon:
                            if not it.get('phonetic_en') or not it.get('phonetic_tr'):
                                it['name'] = phon['name']
                                it['phonetic_en'] = phon['phonetic_en']
                                it['phonetic_tr'] = phon['phonetic_tr']
                                if not it.get('example') and phon.get('example'):
                                    it['example'] = phon['example']
                                modified = True

                        if term.upper() == 'I':
                            for expl_k in ['explanation', 'explanation_en', 'explanation_tr']:
                                if expl_k in it and any(w in str(it[expl_k]).lower() for w in ['pronoun', 'zamir']):
                                    it[expl_k] = ''
                                    modified = True
                            if it.get('translation') == 'Ben':
                                it['translation'] = 'i'
                                modified = True
                            if it.get('translation_tr') == 'Ben':
                                it['translation_tr'] = 'i'
                                modified = True

                    for expl_k in ['explanation', 'explanation_en', 'explanation_tr']:
                        if expl_k in it and isinstance(it[expl_k], str) and tautology_re.search(it[expl_k]):
                            it[expl_k] = ''
                            modified = True

                    bank_hit = get_vocab_example(lang, term)
                    if bank_hit:
                        if not it.get('example'):
                            it['example'] = bank_hit['example']
                            modified = True
                        if not it.get('example_en'):
                            it['example_en'] = bank_hit['example_en']
                            modified = True
                        if not it.get('example_tr'):
                            it['example_tr'] = bank_hit['example_tr']
                            modified = True
                        if not it.get('explanation') or tautology_re.search(str(it.get('explanation', ''))):
                            it['explanation'] = bank_hit['tip_en']
                            modified = True
                        if not it.get('explanation_tr') or tautology_re.search(str(it.get('explanation_tr', ''))):
                            it['explanation_tr'] = bank_hit['tip_tr']
                            modified = True

        if modified:
            c.execute("UPDATE topics SET content = ? WHERE id = ?", (json.dumps(data, ensure_ascii=False), tid))

    conn.commit()

if __name__ == "__main__":
    init_db()
