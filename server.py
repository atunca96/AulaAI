import sys
import os

# Ensure Windows Python 3.8+ finds OpenSSL and extension DLLs
if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
    for _p in [os.path.join(sys.base_prefix, "DLLs"), os.path.join(sys.exec_prefix, "DLLs")]:
        if os.path.exists(_p):
            try:
                os.add_dll_directory(_p)
            except Exception:
                pass

import http.server
import json
import uuid
import sqlite3
import threading
import time
import logging
import subprocess
import random as py_random
import re
import traceback
import concurrent.futures
import unicodedata
import difflib

logging.basicConfig(level=logging.WARNING, format='%(message)s')
from urllib.parse import urlparse, parse_qs
import urllib.request
from datetime import datetime, timedelta, timezone

def file_log(msg):
    with open("pipeline.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [SERVER] {msg}\n")
        f.flush()

VERSION = "1.0.4-BIG-BATCH-FIX"

# Add project root to path
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, ROOT_DIR)

from database import get_db, init_db, db_connection, DATA_DIR, BOOKS_DIR
from services.content_engine import generate_activity, generate_quiz, grade_response, generate_dialogue_activity
from services.mastery import compute_mastery, generate_weekly_report
from services.ai_engine import is_ai_available, ai_generate_report_insights, ai_generate_activity_batch, ai_explain_word, ai_explain_activity
from services.legacy.pdf_pipeline import process_pdf_to_classroom
from services.state import bump_version, get_version
from services.dictionary_service import get_definition, clean_word

PORT = int(os.environ.get("PORT", 3000))
# Manual .env loader for local dev stability
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8-sig") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                os.environ[k.strip().lstrip('\ufeff')] = v.strip()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
STATIC_DIR = os.path.join(ROOT_DIR, "public")

import hashlib
def hash_password(password: str) -> str:
    return hashlib.sha256((password + "AulaAI_Salt").encode('utf-8')).hexdigest()

# Auto-reload logic
def watch_files():
    last_mtime = {}
    while True:
        try:
            for root, dirs, files in os.walk(ROOT_DIR):
                if any(x in root for x in ["scratch", ".git", "__pycache__", ".vscode", "data"]):
                    continue
                for f in files:
                    if f.endswith('.py'):
                        path = os.path.join(root, f)
                        try:
                            mtime = os.path.getmtime(path)
                            if path in last_mtime and mtime > last_mtime[path]:
                                print(f"[RELOAD] Change detected in {f}, restarting...")
                                os.execv(sys.executable, [sys.executable] + sys.argv)
                            last_mtime[path] = mtime
                        except: pass
        except: pass
        time.sleep(1)

# Only start auto-reload in local dev (no PORT or RAILWAY env)
if not os.environ.get("PORT") and not os.environ.get("RAILWAY_ENVIRONMENT"):
    threading.Thread(target=watch_files, daemon=True).start()

_startup_t = time.time()
print(f"--- AULA AI SERVER v{VERSION} [FIX-STABILIZE-V2] STARTING ---")


# ── DISK CLEANUP ──────────────────────────────────────────
def cleanup_storage():
    """Purges temporary extraction files and orphaned textbooks to prevent disk leaks."""
    try:
        if not os.path.exists(BOOKS_DIR): return
        now = time.time()
        count = 0
        
        # Get active course IDs from DB to prevent deleting valid textbooks
        active_course_ids = set()
        try:
            with db_connection() as db:
                rows = db.execute("SELECT id FROM courses").fetchall()
                for r in rows:
                    active_course_ids.add(r["id"])
        except Exception as e:
            print(f"[CLEANUP] Warning: Could not read active courses from DB: {e}")
            # If DB is malformed/unreachable, do NOT run cleanup to be safe
            return

        for f in os.listdir(BOOKS_DIR):
            fpath = os.path.join(BOOKS_DIR, f)
            if not os.path.isfile(fpath):
                continue
            
            # Case 1: Temporary files generated during extraction/OCR
            if f.startswith("extract_") or f.startswith("ocr_") or f.startswith("toc_") or f.startswith("marker_"):
                if now - os.path.getmtime(fpath) > 2 * 3600: # 2 hours
                    try:
                        os.remove(fpath)
                        count += 1
                    except: pass
            
            # Case 2: Uploaded textbooks or source files
            elif f.startswith("course_"):
                # Extract course ID from filename (e.g. course_UID.pdf, course_UID_source.md, course_UID_toc.txt)
                # Filename pattern: course_[shared_uid]...
                import re
                match = re.match(r"^course_([a-zA-Z0-9\-]+)(?:_source\.md|_toc\.txt|_toc\.json|\.pdf)$", f)
                if match:
                    course_id = match.group(1)
                    if course_id not in active_course_ids:
                        # File is orphaned (its course was deleted or creation aborted)
                        if now - os.path.getmtime(fpath) > 2 * 3600: # 2 hours
                            try:
                                os.remove(fpath)
                                count += 1
                            except: pass
        if count > 0:
            print(f"[CLEANUP] Purged {count} orphaned/temporary files from {BOOKS_DIR}")
    except Exception as e:
        print(f"[CLEANUP] Error: {e}")

# Run cleanup on startup and periodically
def periodic_cleanup():
    while True:
        cleanup_storage()
        time.sleep(3600) # Every hour

cleanup_storage()
threading.Thread(target=periodic_cleanup, daemon=True).start()

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

# ── TTS Audio Cache (LRU, stores raw MP3 bytes) ──
_tts_cache = {}
_tts_cache_lock = threading.Lock()
_TTS_CACHE_MAX = 200

def get_tts_cache(key):
    with _tts_cache_lock:
        return _tts_cache.get(key)

def set_tts_cache(key, audio_bytes):
    with _tts_cache_lock:
        if len(_tts_cache) >= _TTS_CACHE_MAX:
            # Evict oldest entry
            oldest_key = next(iter(_tts_cache))
            del _tts_cache[oldest_key]
        _tts_cache[key] = audio_bytes

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
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


_activity_tasks = {}
_activity_tasks_lock = threading.Lock()

def get_activity_task(task_id):
    with _activity_tasks_lock:
        return _activity_tasks.get(task_id)

def set_activity_task(task_id, data):
    with _activity_tasks_lock:
        now = time.time()
        for k in list(_activity_tasks.keys()):
            if now - _activity_tasks[k].get("created_at", now) > 1800:
                _activity_tasks.pop(k, None)
        if task_id in _activity_tasks:
            _activity_tasks[task_id].update(data)
        else:
            data["created_at"] = now
            _activity_tasks[task_id] = data

_draft_course_batches = {}
_draft_course_lock = threading.Lock()

def _get_draft_batch_key(course_id, topic_id="all"):
    return f"{str(course_id)}:{str(topic_id or 'all')}"

def normalize_prompt_text(text):
    if not text:
        return ""
    t = unicodedata.normalize('NFKD', str(text).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'[^\w\s]', ' ', t)
    return " ".join(t.split())

def is_near_identical_question(p1, p2):
    norm1 = normalize_prompt_text(p1)
    norm2 = normalize_prompt_text(p2)
    if not norm1 or not norm2:
        return False
    if norm1 == norm2:
        return True
    return difflib.SequenceMatcher(None, norm1, norm2).ratio() > 0.88

def extract_pedagogic_keywords(text):
    if not text:
        return []
    norm = normalize_prompt_text(text)
    stopwords = {
        "hangisi", "hangisinde", "asagidaki", "cumlede", "dogru", "yanlis", "olarak",
        "kullanilmistir", "vardir", "yoktur", "ifadesi", "anlamina", "gelen", "uygun",
        "seciniz", "cumledeki", "bosluga", "hangisinin", "paragrafta", "verilen",
        "etmek", "olmak", "yapmak", "kilmak", "eylemek", "kalmak", "durumunda", "durumundayiz",
        "halinde", "birlikte", "uzere", "dair", "gore", "kadar", "dolayi", "oturu", "ragmen", "karsin",
        "gibi", "icin", "ile", "veya", "yahut", "olan", "ederek", "edildi", "edilmesi",
        "oldugu", "olmasi", "yapan", "yapilan", "tarafindan", "yonelik",
        "which", "where", "what", "when", "that", "this", "from", "with", "have", "been",
        "cual", "donde", "como", "para", "pero", "esta", "este", "es", "son", "un", "una"
    }
    return [w for w in norm.split() if len(w) >= 3 and w not in stopwords]

def extract_prompt_quotes(text):
    if not text:
        return []
    raw_quotes = re.findall(r'["\'\u201c\u2018]([^\u201d\u2019"\'\n]{6,})["\'\u201d\u2019]', str(text))
    return [normalize_prompt_text(q) for q in raw_quotes if len(normalize_prompt_text(q)) >= 6]

def is_test_conflict(cand, accepted):
    """
    Evaluates test-internal independence between two questions:
    1. Prompt stem similarity: > 82% duplicate prompt text.
    2. Answer equivalence: normalized answers are identical or near-identical (> 80%).
    3. Prompt Quotes Comparison: target sentences in quotes match (> 75%) or match another question's answer.
    4. Longest Common Substring between Answer and Prompt: multi-word shared target >= 18 chars.
    5. Target idiom/lemma overlap: candidate answer shares significant root/idiom with accepted answer.
    6. Suffix / morphological target identity: e.g. both test '-casina / -cesine'.
    """
    if not isinstance(cand, dict) or not isinstance(accepted, dict):
        return False
    cand_p = cand.get("prompt", "")
    acc_p = accepted.get("prompt", "")
    cand_a = cand.get("answer", "")
    acc_a = accepted.get("answer", "")

    norm_cand_p = normalize_prompt_text(cand_p)
    norm_acc_p = normalize_prompt_text(acc_p)
    norm_ca = normalize_prompt_text(cand_a)
    norm_aa = normalize_prompt_text(acc_a)

    # 1. Prompt similarity
    if norm_cand_p and norm_acc_p:
        if is_near_identical_question(cand_p, acc_p) or difflib.SequenceMatcher(None, norm_cand_p, norm_acc_p).ratio() > 0.82:
            return True

    # 2. Answer equivalence
    if norm_ca and norm_aa:
        if norm_ca == norm_aa:
            return True
        if difflib.SequenceMatcher(None, norm_ca, norm_aa).ratio() > 0.80:
            return True

    # 3. Prompt Quotes Comparison (target sentence duplication & giveaway)
    cand_quotes = extract_prompt_quotes(cand_p)
    acc_quotes = extract_prompt_quotes(acc_p)
    
    # Prompt quote vs Prompt quote (both testing near-identical target sentences)
    for cq in cand_quotes:
        for aq in acc_quotes:
            if cq == aq or difflib.SequenceMatcher(None, cq, aq).ratio() > 0.75:
                return True

    # Prompt quote vs Answers (one asks about the sentence that the other gives as answer)
    for cq in cand_quotes:
        if norm_aa and (cq == norm_aa or difflib.SequenceMatcher(None, cq, norm_aa).ratio() > 0.75):
            return True
    for aq in acc_quotes:
        if norm_ca and (aq == norm_ca or difflib.SequenceMatcher(None, aq, norm_ca).ratio() > 0.75):
            return True

    # 4. Target idiom / keyword overlap in answers
    ca_words = extract_pedagogic_keywords(cand_a)
    aa_words = extract_pedagogic_keywords(acc_a)
    if ca_words and aa_words:
        # Single keyword answer duplicate (e.g. both answers are "mamafih" or "tenzih")
        if len(ca_words) == 1 and len(aa_words) == 1 and ca_words[0] == aa_words[0]:
            return True
        if len(ca_words) == 1 and ca_words[0] in aa_words:
            return True
        if len(aa_words) == 1 and aa_words[0] in ca_words:
            return True
        # Both answers testing duplicate adverbial suffix (-casına / -cesine)
        if any(cw.endswith(('cesine', 'casina')) for cw in ca_words) and any(aw.endswith(('cesine', 'casina')) for aw in aa_words):
            return True
        # Multi-word idiom overlap: share at least 2 significant stems/words
        matches = 0
        for w1 in ca_words:
            if len(w1) < 4:
                continue
            for w2 in aa_words:
                if len(w2) < 4:
                    continue
                if w1 == w2 or (len(w1) >= 5 and len(w2) >= 5 and (w1[:5] == w2[:5] or w1 in w2 or w2 in w1)):
                    matches += 1
                    break
        if matches >= 2:
            return True

    # 5. Multi-word idiom answer prefix overlap (e.g. "gozunu karartmak" vs "gozunu karartti")
    cand_a_words = [w for w in normalize_prompt_text(cand_a).split() if len(w) >= 3]
    acc_a_words = [w for w in normalize_prompt_text(acc_a).split() if len(w) >= 3]
    if len(cand_a_words) >= 2 and len(acc_a_words) >= 2:
        if cand_a_words[:2] == acc_a_words[:2]:
            return True

    # 6. Multi-word idiom or key phrase giveaway (e.g. "gozunu karartmak" / "gozunu karartti")
    for phrase, other_prompt in [(cand_a, norm_acc_p), (acc_a, norm_cand_p)]:
        p_words = [w for w in normalize_prompt_text(phrase).split() if len(w) >= 4]
        if len(p_words) >= 2:
            p_prefix = " ".join(p_words[:2])
            if p_prefix in other_prompt:
                return True

    # 7. Shared grammatical construction markers in prompts
    for kw in ["casina", "cesine"]:
        if kw in norm_cand_p and kw in norm_acc_p:
            return True

    return False

def record_course_draft_batch(course_id, questions, topic_id="all"):
    """
    Retain all questions from exactly the two most recent completed quiz drafts for the same course/topic.
    """
    if not course_id or not isinstance(questions, list) or len(questions) == 0:
        return
    cid = str(course_id)
    tid = str(topic_id or "all")
    key = _get_draft_batch_key(cid, tid)

    clean_batch = []
    seen = set()
    for q in questions:
        if isinstance(q, dict) and (q.get("prompt") or q.get("answer")):
            p = str(q.get("prompt", "")).strip()
            a = str(q.get("answer", "")).strip()
            if p and p.lower() not in seen:
                seen.add(p.lower())
                clean_batch.append({"prompt": p, "answer": a})

    if not clean_batch:
        return

    with _draft_course_lock:
        if key not in _draft_course_batches:
            _draft_course_batches[key] = []

        last_batch = _draft_course_batches[key][-1] if _draft_course_batches[key] else None
        is_duplicate_batch = False
        if last_batch and len(last_batch) == len(clean_batch):
            if all(lq.get("prompt") == cq.get("prompt") for lq, cq in zip(last_batch, clean_batch)):
                is_duplicate_batch = True

        if not is_duplicate_batch:
            _draft_course_batches[key].append(clean_batch)
            _draft_course_batches[key] = _draft_course_batches[key][-2:]

        try:
            with db_connection() as db:
                batch_id = _uid()
                db.execute(
                    "INSERT INTO draft_test_batches (id, course_id, topic_id, questions_json, created_at) VALUES (?,?,?,?,datetime('now'))",
                    (batch_id, cid, tid, json.dumps(clean_batch, ensure_ascii=False))
                )
                db.execute("""
                    DELETE FROM draft_test_batches 
                    WHERE course_id=? AND topic_id=? AND id NOT IN (
                        SELECT id FROM draft_test_batches WHERE course_id=? AND topic_id=? ORDER BY created_at DESC, rowid DESC LIMIT 2
                    )
                """, (cid, tid, cid, tid))
                db.commit()
        except Exception as e:
            print(f"[DB] Error recording draft batch: {e}")

def get_course_draft_batches(course_id, topic_id="all"):
    """
    Returns all questions from exactly the two most recent completed quiz drafts for the same course/topic.
    Questions from the third-most-recent test or older must not be loaded into generation context or used for duplicate filtering.
    """
    if not course_id:
        return []
    cid = str(course_id)
    tid = str(topic_id or "all")
    key = _get_draft_batch_key(cid, tid)

    with _draft_course_lock:
        if key not in _draft_course_batches or not _draft_course_batches[key]:
            _draft_course_batches[key] = []
            try:
                with db_connection() as db:
                    rows = db.execute(
                        "SELECT questions_json FROM draft_test_batches WHERE course_id=? AND topic_id=? ORDER BY created_at ASC, rowid ASC",
                        (cid, tid)
                    ).fetchall()
                    rows = rows[-2:]
                    for r in rows:
                        if r["questions_json"]:
                            b_qs = json.loads(r["questions_json"])
                            if isinstance(b_qs, list):
                                _draft_course_batches[key].append(b_qs)
            except Exception as e:
                print(f"[DB] Error loading draft batches: {e}")

        result = []
        for batch in _draft_course_batches[key][-2:]:
            for q in batch:
                if isinstance(q, dict) and q.get("prompt"):
                    result.append(q)
        return result

def record_course_draft_questions(course_id, questions, topic_id="all"):
    record_course_draft_batch(course_id, questions, topic_id)

def get_course_draft_questions(course_id, topic_id="all"):
    return get_course_draft_batches(course_id, topic_id)


class APIHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler with REST API routing."""

    def _verify_course_ownership(self, db, course_id):
        """Returns True ONLY if user is the lecturer owner of this course or primary admin."""
        role = self._get_user_role()
        user_id = self._get_user_id()
        if not user_id or role == 'student': return False # Students NEVER own classrooms
        if user_id == 'lecturer-demo-id': return True # Admin can manage all
        
        row = db.execute("SELECT lecturer_id FROM courses WHERE id=?", (course_id,)).fetchone()
        if not row: return False
        return row["lecturer_id"] == user_id

    def _verify_course_access(self, db, course_id):
        """Returns True if user is lecturer, admin, or an enrolled student."""
        role = self._get_user_role()
        user_id = self._get_user_id()
        if not user_id: return False
        if role in ('lecturer', 'admin'): return True
        if role == 'student':
            row = db.execute("SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?", (user_id, course_id)).fetchone()
            return bool(row)
        return False

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

    def _get_user_id(self):
        """Extract user_id from headers or query parameters and update last_seen activity."""
        uid = self.headers.get("X-User-Id") or self.headers.get("X-Lecturer-Id")
        if not uid:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            uid = params.get("user_id", [None])[0] or params.get("lecturer_id", [None])[0]
        
        if uid:
            try:
                with db_connection() as db:
                    row = db.execute("""
                        SELECT (last_seen IS NULL OR (strftime('%s','now') - strftime('%s',last_seen) > 12)) as was_inactive
                        FROM users WHERE id = ?
                    """, (uid,)).fetchone()
                    was_inactive = bool(row and row[0])
                    db.execute("""
                        UPDATE users SET last_seen = CURRENT_TIMESTAMP 
                        WHERE id = ? AND (last_seen IS NULL OR (strftime('%s','now') - strftime('%s',last_seen) >= 3))
                    """, (uid,))
                    db.commit()
                    if was_inactive:
                        bump_version()
            except: pass
        return uid

    def _get_user_role(self):
        """Extract user_id and look up authentic role in DB to prevent spoofing."""
        user_id = self._get_user_id()
        if not user_id:
            return None
        with db_connection() as db:
            row = db.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                return row["role"]
        return None

    def _require_lecturer(self):
        """Enforce lecturer or admin role. Sends 403 Forbidden if not authorized."""
        role = self._get_user_role()
        if role not in ("lecturer", "admin"):
            self._send_error("Forbidden: Lecturer privileges required", status=403)
            return False
        return True

    def _require_admin(self):
        """Enforce admin email or admin role. Sends 403 Forbidden if not authorized."""
        user_id = self._get_user_id()
        if not user_id:
            self._send_error("Forbidden: Admin privileges required", status=403)
            return False
        if user_id == 'lecturer-demo-id':
            return True
        with db_connection() as db:
            row = db.execute("SELECT email, role FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row or (row["email"] != "atunca96@gmail.com" and row["role"] != "admin"):
                self._send_error("Forbidden: Admin privileges required", status=403)
                return False
        return True

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
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            body = self.rfile.read(length)
            return json.loads(body)
        except Exception:
            return {}

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
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
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
            if not self._require_lecturer(): return
            course_id = params.get("course_id", [None])[0]
            return self._get_students(course_id)
        elif path == "/api/student/progress":
            student_id = params.get("student_id", [None])[0]
            course_id = params.get("course_id", [None])[0]
            return self._get_student_progress(student_id, course_id)
        elif path == "/api/student/enrollments":
            student_id = params.get("student_id", [None])[0]
            return self._get_student_enrollments(student_id)
        elif path == "/api/questions":
            topic_id = params.get("topic_id", [None])[0]
            return self._get_questions(topic_id)
        elif path == "/api/quiz/take":
            quiz_id = params.get("quiz_id", [None])[0]
            student_id = params.get("student_id", [None])[0]
            return self._get_quiz(quiz_id, student_id)
        elif path in ("/api/classroom/progress", "/api/curriculum/status"):
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
            if not self._require_lecturer(): return
            course_id = params.get("course_id", [None])[0]
            return self._get_report(course_id)
        elif path == "/api/activity/progress":
            course_id = params.get("course_id", [None])[0]
            return self._activity_progress(course_id)
        elif path == "/api/draft/progress":
            if not self._require_lecturer(): return
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
            if not self._require_lecturer(): return
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
            if not self._require_lecturer(): return
            assignment_id = params.get("assignment_id", [None])[0]
            return self._get_assignment_responses(assignment_id)
        elif path == "/api/ai-status":
            return self._get_ai_status()
        elif path == "/api/students/pending":
            if not self._require_lecturer(): return
            return self._get_pending_students()
        elif path == "/api/admin/all-students":
            if not self._require_admin(): return
            return self._admin_get_all_students()
        elif path == "/api/user/status":
            user_id = params.get("user_id", [None])[0]
            return self._get_user_status(user_id)
        elif path == "/api/user/heartbeat":
            return self._user_heartbeat()
        elif path == "/api/version":
            return self._send_json({"version": get_version()})
        elif path == "/api/blueprints":
            from services.ai_engine import list_blueprint_cache
            return self._send_json({"blueprints": list_blueprint_cache()})
        elif path == "/api/dictionary":
            word = params.get("word", [None])[0]
            lang = params.get("lang", [None])[0]
            context = params.get("context", [None])[0]
            ui_lang = params.get("ui_lang", ["en"])[0]
            if not word: return self._send_error("word required")
            
            # Context-aware and language-aware cache key
            clean_w = word.replace('\u200e', '').replace('\u200f', '').strip(' \t\n\r"\'“”«»`').lower()
            cache_key = f"dict_{lang}_{clean_w}_{ui_lang}" + (f"_ctx_{context[:30]}" if context else "")
            cached = get_cache(cache_key)
            if cached: return self._send_json(cached)
            
            result = get_definition(word, lang or "en", context=context, target_lang=ui_lang)
            set_cache(cache_key, result)
            return self._send_json(result)
        elif path == "/api/dictionary/ai-explain":
            word = params.get("word", [None])[0]
            lang = params.get("lang", [None])[0]
            course_id = params.get("course_id", [None])[0]
            ui_lang = params.get("ui_lang", ["en"])[0]
            if not word: return self._send_error("word required")
            
            material_language = "en"
            if course_id:
                try:
                    with db_connection() as db:
                        row = db.execute("SELECT material_language FROM courses WHERE id=?", (course_id,)).fetchone()
                        if row and row["material_language"]:
                            material_language = row["material_language"]
                except Exception as e:
                    print(f"[ERROR] Failed to query material_language for dictionary explain: {e}")
            
            if ui_lang and ui_lang in ["tr", "en"]:
                material_language = ui_lang
                
            result = ai_explain_word(word, lang or "English", material_language=material_language)
            return self._send_json(result)
        elif path == "/api/tts":
            return self._tts_speak()
        elif path == "/health" or path == "/api/health":
            return self._send_json({"status": "ok", "time": datetime.now().isoformat()})
        elif path.startswith("/api/"):
            return self._send_error("Not found", 404)
        else:
            return self._serve_static(path)

    def _tts_speak(self):
        """TTS via Google Translate — fast, free, correct language."""
        try:
            parsed_url = urlparse(self.path)
            qp = parse_qs(parsed_url.query)
            
            text = qp.get("text", [None])[0]
            lang = qp.get("lang", ["en"])[0]

            if not text or len(text.strip()) == 0:
                return self._send_error("text required")
            
            text = text.strip()[:200]

            # Frontend now sends ISO codes directly (de, es, tr, etc.)
            # Fall back to mapping only if a full language name is sent
            lang_codes = {
                'german': 'de', 'deutsch': 'de', 'spanish': 'es', 'español': 'es',
                'french': 'fr', 'turkish': 'tr', 'italian': 'it', 'portuguese': 'pt',
                'arabic': 'ar', 'japanese': 'ja', 'chinese': 'zh', 'korean': 'ko',
                'russian': 'ru', 'english': 'en', 'dutch': 'nl', 'polish': 'pl',
                'greek': 'el', 'hindi': 'hi', 'hebrew': 'he', 'persian': 'fa',
            }
            lang_clean = lang.split('(')[0].strip().lower() if lang else 'en'
            # If already a 2-3 letter code, use directly
            tl = lang_clean if len(lang_clean) <= 3 else lang_codes.get(lang_clean, lang_clean[:2])

            # Check cache
            cache_key = f"tts_{tl}_{text.lower()}"
            cached_audio = get_tts_cache(cache_key)
            if cached_audio:
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(cached_audio)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(cached_audio)
                return

            # Google Translate TTS
            from urllib.parse import quote
            tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={quote(text)}&tl={tl}&client=tw-ob"
            
            req = urllib.request.Request(tts_url)
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            req.add_header("Referer", "https://translate.google.com/")
            
            with urllib.request.urlopen(req, timeout=8) as response:
                audio_bytes = response.read()

            set_tts_cache(cache_key, audio_bytes)

            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(audio_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(audio_bytes)
        except Exception as e:
            import traceback
            print(f"[TTS ERROR] {e}")
            traceback.print_exc()
            return self._send_error(f"TTS failed: {str(e)}")

    def _wipe_curriculum(self):
        """Delete all chapters and topics for a classroom to start fresh."""
        body = self._read_body()
        course_id = body.get("course_id")
        if not course_id: return self._send_error("Missing course_id")

        try:
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

                # 4. Delete quizzes and assignments
                db.execute("DELETE FROM quizzes WHERE course_id = ?", (course_id,))
                db.execute("DELETE FROM assignments WHERE course_id = ?", (course_id,))
                db.execute("DELETE FROM quiz_questions WHERE quiz_id NOT IN (SELECT id FROM quizzes)")
                db.execute("DELETE FROM assignment_questions WHERE assignment_id NOT IN (SELECT id FROM assignments)")
                
                # 5. Reset building status and all progress flags
                db.execute("""
                    UPDATE courses SET 
                        is_building = 0, 
                        progress = 0, 
                        total_steps = 0,
                        draft_progress = 0,

                        draft_status = 'idle',
                        activity_status = 'idle',
                        activity_progress = 0,
                        activity_total = 0,
                        textbook = 'AI Generated'
                    WHERE id = ?
                """, (course_id,))
                db.commit()
        except Exception as e:
            print(f"[ERROR] _wipe_curriculum: {e}")
            return self._send_error(str(e))

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
            force = body.get("force", False)
            if course["is_building"] and not force: return self._send_error("Course is already building")

            # IDENTITY PRESERVATION: Do NOT delete chapters or topics, as Phase 2 Enrichment needs them as a skeleton.
            # We only clear the 'content' field and existing questions to ensure a fresh, deep generation.
            db.execute("DELETE FROM questions WHERE topic_id IN (SELECT t.id FROM topics t JOIN chapters ch ON t.chapter_id = ch.id WHERE ch.course_id = ?)", (course_id,))
            db.execute("UPDATE topics SET content = NULL WHERE chapter_id IN (SELECT id FROM chapters WHERE course_id = ?)", (course_id,))
            
            # Generate a new generation_id to ignore updates from zombie workers
            import uuid
            gen_id = str(uuid.uuid4())

            # Reset is_building flag to trigger worker
            db.execute("UPDATE courses SET is_building = 1, progress = 0, total_steps = 0, generation_id = ?, build_stage = 'starting', build_message = 'Restarting build process...', build_started_at = ? WHERE id = ?", (gen_id, time.time(), course_id))
            db.commit()

        # KILL OLD WORKER (Server-Side Executioner)
        pid_file = os.path.join("data", "workers", f"{course_id}.pid")
        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    old_pid = int(f.read().strip())
                import signal
                if sys.platform == "win32":
                    import subprocess
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(old_pid)], capture_output=True)
                else:
                    os.kill(old_pid, signal.SIGTERM)
                print(f"[SERVER] Terminated stale worker {old_pid} for course {course_id}")
            except: pass

        # Start the background worker
        import subprocess
        try:
            # TRY TO FIND SOURCE MARKDOWN: Check if a matching .md exists for the textbook
            source_markdown_path = "NONE"
            with db_connection() as db:
                row = db.execute("SELECT textbook FROM courses WHERE id=?", (course_id,)).fetchone()
                if row and row["textbook"]:
                    # textbook is like /books/course_UID.pdf -> guess /books/course_UID_source.md
                    potential_md = row["textbook"].replace(".pdf", "_source.md")
                    full_path = os.path.join(BOOKS_DIR, os.path.basename(potential_md))
                    if os.path.exists(full_path):
                        source_markdown_path = full_path
                        print(f"[SERVER] Found source markdown for rebuild: {source_markdown_path}")

            worker_path = os.path.join(ROOT_DIR, "worker.py")
            cmd = [sys.executable, worker_path, course_id, gen_id, source_markdown_path]
            
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            if sys.platform == "win32":
                log_file = open("pipeline.log", "a", encoding="utf-8")
                subprocess.Popen(cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT, 
                               creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
                log_file.close()
            else:
                subprocess.Popen(cmd, env=env, close_fds=True)
            self._send_json({"status": "success", "message": "Rebuild started"})
        except Exception as e:
            self._send_error(f"Failed to start worker: {e}")

    def _get_classroom_progress(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        course_id = params.get("course_id", [None])[0]
        if not course_id: return self._send_error("course_id required")

        with db_connection() as db:
            row = db.execute("""
                SELECT is_building, progress, total_steps, build_stage, build_message, build_started_at 
                FROM courses WHERE id=?
            """, (course_id,)).fetchone()
            if not row: return self._send_error("Course not found")
            
            is_building = bool(row["is_building"])
            progress = row["progress"] or 0
            total = row["total_steps"] or 0
            stage = row["build_stage"] or ("enriching" if is_building else "idle")
            message = row["build_message"] or ""
            started_at = row["build_started_at"] or 0
            elapsed = (time.time() - started_at) if started_at > 0 else 0

            # STALE/TIMEOUT PROTECTION: If building has run > 15 minutes, auto-recover
            if is_building and started_at > 0 and elapsed > 900:
                print(f"[SERVER] Stale build detected for {course_id} (elapsed {elapsed:.0f}s). Auto-recovering...")
                db.execute("UPDATE courses SET is_building = 0, build_stage = 'timeout', build_message = 'Build timed out. Please click Force Restart.' WHERE id = ?", (course_id,))
                db.commit()
                is_building = False
                stage = "timeout"
                message = "Build timed out. Please click Force Restart."

            if not is_building:
                if stage == "failed":
                    percentage = 0
                    if not message: message = "Build encountered an error."
                elif stage == "timeout":
                    percentage = 0
                elif stage == "stopped":
                    percentage = 0
                    if not message: message = "Ders üretimi durduruldu."
                else:
                    percentage = 100
                    if not message: message = "Classroom is ready!"
            else:
                # Calculate accurate, monotonic progress based on granular pipeline stages
                if stage == "starting":
                    percentage = 3
                    if not message: message = "Starting build process..."
                elif stage == "analyzing":
                    percentage = 6
                    if not message: message = "Analyzing textbook syllabus..."
                elif stage == "structuring":
                    percentage = 10
                    if not message: message = "Structuring course chapters and topics..."
                elif stage == "enriching":
                    if total > 0:
                        topic_ratio = min(1.0, max(0.0, progress / total))
                        percentage = 10 + int(topic_ratio * 82)
                    else:
                        percentage = 10
                    if not message:
                        message = f"Generating lesson materials ({progress}/{total})..." if total > 0 else "Generating lesson materials..."
                elif stage == "finalizing":
                    percentage = 94
                    if not message: message = "Finalizing bilingual translations..."
                else:
                    raw = int((progress / total) * 100) if total > 0 else 3
                    percentage = min(92, max(3, raw))
                    if not message: message = "Building classroom content..."

                # Ensure it never claims 100% while still building
                percentage = min(98, max(3, percentage))

            return self._send_json({
                "course_id": course_id,
                "is_building": is_building,
                "stage": stage,
                "message": message,
                "progress": progress,
                "total": total,
                "percentage": percentage,
                "elapsed_seconds": int(elapsed) if is_building and started_at > 0 else 0
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
        if path == "/api/admin/upload-db":
            if not self._require_admin(): return
            return self._admin_upload_db()
        elif path == "/api/classroom/delete":
            if not self._require_lecturer(): return
            return self._delete_classroom()
        elif path in ("/api/classroom/rebuild", "/api/curriculum/rebuild"):
            if not self._require_lecturer(): return
            return self._classroom_rebuild()
        elif path == "/api/classroom/wipe-curriculum":
            if not self._require_lecturer(): return
            return self._wipe_curriculum()
        elif path == "/api/curriculum/chapter/delete":
            if not self._require_lecturer(): return
            return self._delete_chapter()
        elif path == "/api/curriculum/topic/delete":
            if not self._require_lecturer(): return
            return self._delete_topic()
        elif path == "/api/marker/extract":
            if not self._require_lecturer(): return
            file_log("MARKER: Received extraction request (Routing to Pipeline V2)")
            fields, files = self._read_multipart()
            if not files or "pdf" not in files:
                return self._send_error("PDF file required")
            
            pdf_data = files["pdf"]["content"]
            safe_id = _uid()
            temp_pdf = os.path.join(BOOKS_DIR, f"extract_{safe_id}.pdf")
            
            with open(temp_pdf, "wb") as f:
                f.write(pdf_data)
            
            try:
                from services.pipeline_v2.pdf_processor import process_pdf
                toc_range = fields.get("toc_range")
                if not toc_range or toc_range.strip() == "" or toc_range == "0-0":
                    toc_range = None
                
                if toc_range:
                    file_log(f"MARKER: Extracting curriculum using user range: {toc_range}")
                    curriculum = process_pdf(temp_pdf, toc_range=toc_range)
                else:
                    file_log("MARKER: Extracting curriculum using default page limit (30)")
                    curriculum = process_pdf(temp_pdf, page_limit=30)
                
                # Convert V2 JSON to the Markdown format the Architect frontend expects
                final_details = []
                for unit in curriculum.get("units", []):
                    u_title = unit.get("title", "Unit")
                    markdown_lines = [f"## {u_title}"]
                    for topic in unit.get("topics", []):
                        t_text = topic.get("text", "")
                        t_tag = topic.get("tag", "vocabulary")
                        markdown_lines.append(f"- {t_text} [{t_tag}]")
                    final_details.append("\n".join(markdown_lines))
                
                markdown = "\n\n".join(final_details)
                
                return self._send_json({
                    "success": True, 
                    "markdown": markdown,
                    "language": fields.get("language", "Spanish") # Default to Spanish for AulaAI
                })
            except Exception as e:
                file_log(f"V2 EXTRACTION ERROR: {e}")
                return self._send_error(f"Extraction failed: {str(e)}")
            finally:
                if os.path.exists(temp_pdf):
                    try: os.remove(temp_pdf)
                    except: pass
                # Clean up everything in BOOKS_DIR that is temporary or old
                cleanup_storage()

        elif path == "/api/classroom/create-from-pdf":
            if not self._require_lecturer(): return
            return self._create_classroom_from_pdf()
        elif path == "/api/classroom/create-from-scratch":
            if not self._require_lecturer(): return
            return self._create_classroom_from_scratch()
        elif path == "/api/classroom/stop-build":
            if not self._require_lecturer(): return
            return self._stop_classroom_build()
        elif path == "/api/draft/curriculum":
            if not self._require_lecturer(): return
            return self._draft_curriculum()
        elif path == "/api/translate/material":
            return self._translate_material()
            
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
            return self._send_error("Forbidden: Feature disabled", 403)
        elif path == "/api/register":
            return self._register()
        elif path == "/api/user/logout":
            return self._logout()
        elif path == "/api/user/heartbeat":
            return self._user_heartbeat()
        elif path == "/api/user/delete":
            return self._send_error("Forbidden: Feature disabled", 403)
        elif path == "/api/students/pending":
            if not self._require_lecturer(): return
            return self._get_pending_students()
        elif path == "/api/students/approve":
            if not self._require_lecturer(): return
            return self._approve_student()
        elif path == "/api/quiz/create":
            if not self._require_lecturer(): return
            return self._create_quiz()
        elif path == "/api/activity/start":
            return self._activity_start()
        elif path == "/api/quiz/submit":
            return self._submit_quiz()
        elif path == "/api/activity/respond":
            return self._submit_activity_response()
        elif path == "/api/activity/explain":
            return self._explain_activity_question()
        elif path == "/api/assignment/create":
            if not self._require_lecturer(): return
            return self._create_assignment()
        elif path == "/api/assignment/submit":
            return self._submit_assignment()
        elif path == "/api/draft/generate":
            if not self._require_lecturer(): return
            return self._draft_generate()
        elif path == "/api/draft/publish":
            if not self._require_lecturer(): return
            return self._draft_publish()
        elif path == "/api/report/generate":
            if not self._require_lecturer(): return
            return self._generate_report()
        elif path == "/api/session/start":
            return self._start_session()
        elif path == "/api/data/reset":
            if not self._require_admin(): return
            return self._reset_data()
        elif path == "/api/student/delete":
            if not self._require_lecturer(): return
            return self._delete_student()
        elif path == "/api/quiz/delete":
            if not self._require_lecturer(): return
            return self._delete_quiz()
        elif path == "/api/assignment/delete":
            if not self._require_lecturer(): return
            return self._delete_assignment()
        elif path == "/api/message/send":
            return self._message_send()
        elif path == "/api/message/read":
            return self._message_read()
        elif path == "/api/question/update":
            if not self._require_lecturer(): return
            return self._question_update()
        elif path == "/api/question/delete":
            if not self._require_lecturer(): return
            return self._question_delete()
        elif path == "/api/admin/hard-reset":
            if not self._require_admin(): return
            return self._admin_hard_reset()
        elif path == "/api/admin/reset-students":
            if not self._require_admin(): return
            return self._admin_reset_students()
        elif path == "/api/admin/reset-student-pin":
            if not self._require_admin(): return
            return self._admin_reset_student_pin()
        elif path == "/api/admin/reset-student-progress":
            if not self._require_admin(): return
            return self._admin_reset_student_progress()
        elif path == "/api/blueprint/delete":
            if not self._require_admin(): return
            return self._delete_blueprint()
        elif path == "/api/blueprint/delete-all":
            if not self._require_admin(): return
            return self._delete_all_blueprints()
        elif path == "/api/admin/set-student-password" or path == "/api/student/set-password":
            if not self._require_admin(): return
            return self._admin_set_student_password()
        elif path == "/api/admin/create-student":
            if not self._require_admin(): return
            return self._admin_create_student()
        else:
            self._send_error("Not found", 404)

    def _delete_blueprint(self):
        """Deletes a single cached blueprint. Restricted to primary admin."""
        if not self._is_admin():
            return self._send_error("Unauthorized", 403)
        data = self._read_body()
        language = data.get("language", "")
        level = data.get("level", "")
        if not language or not level:
            return self._send_error("language and level required")
        from services.ai_engine import delete_blueprint_cache
        deleted = delete_blueprint_cache(language, level)
        return self._send_json({"success": True, "deleted": deleted})

    def _delete_all_blueprints(self):
        """Deletes all cached blueprints. Restricted to primary admin."""
        if not self._is_admin():
            return self._send_error("Unauthorized", 403)
        import os, glob
        cache_dir = os.path.join("services", "blueprints")
        count = 0
        if os.path.exists(cache_dir):
            for f in glob.glob(os.path.join(cache_dir, "*.json")):
                os.remove(f)
                count += 1
        print(f"[CACHE] Purged {count} blueprint(s).")
        return self._send_json({"success": True, "deleted_count": count})

    def _is_admin(self):
        """Returns true ONLY if the current user is the system administrator."""
        user_id = self._get_user_id()
        if not user_id: return False
        
        # Hardcoded primary admin check for system management
        if user_id == 'lecturer-demo-id': return True
        
        with db_connection() as db:
            row = db.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
            if row and row["email"] == 'atunca96@gmail.com':
                return True
        return False

    def _is_authority(self):
        """Returns true if caller is website admin or a lecturer."""
        user_id = self._get_user_id()
        if not user_id: return False
        if self._is_admin(): return True
        if user_id in ['lecturer-demo-id', 'ela-lecturer-id']: return True
        with db_connection() as db:
            row = db.execute("SELECT role, email FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                if row["email"] in ['atunca96@gmail.com', 'ela94216@gmail.com']: return True
                if row["role"] in ['lecturer', 'admin']: return True
        return False

    def _admin_set_student_password(self):
        """Sets or resets the password for a student. Accessible by admin or lecturer."""
        if not self._is_authority():
            return self._send_error("Unauthorized", 403)
        body = self._read_body()
        student_id = body.get("student_id")
        student_number = body.get("student_number")
        new_password = body.get("password", "").strip()

        if not new_password:
            return self._send_error("New password is required")

        hashed_pwd = hash_password(new_password)

        with db_connection() as db:
            if student_id:
                user = db.execute("SELECT id FROM users WHERE id = ? AND role = 'student'", (student_id,)).fetchone()
            elif student_number:
                email_key = f"{student_number.strip()}@student.aulaai"
                user = db.execute("SELECT id FROM users WHERE email = ? AND role = 'student'", (email_key,)).fetchone()
            else:
                return self._send_error("student_id or student_number is required")

            if not user:
                return self._send_error("Student not found", 404)

            db.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_pwd, user["id"]))
            db.commit()

        bump_version()
        return self._send_json({"success": True})

    def _admin_create_student(self):
        """Creates a new student account with student number, name, and password. Admin or Lecturer."""
        if not self._is_authority():
            return self._send_error("Unauthorized", 403)
        body = self._read_body()
        student_number = body.get("student_number", "").strip()
        name = body.get("name", "").strip()
        password = body.get("password", "").strip()
        course_id = body.get("course_id")

        if not student_number:
            return self._send_error("Student number is required")
        if not name:
            return self._send_error("Full name is required")
        if not password:
            return self._send_error("Password is required")

        email_key = f"{student_number}@student.aulaai"
        hashed_pwd = hash_password(password)

        with db_connection() as db:
            existing = db.execute("SELECT id FROM users WHERE email = ?", (email_key,)).fetchone()
            if existing:
                return self._send_error("A student with this student number already exists", 409)

            student_id = _uid()
            db.execute("INSERT INTO users (id, name, email, password, role, status, created_at) VALUES (?,?,?,?,?,?,datetime('now'))",
                       (student_id, name, email_key, hashed_pwd, "student", "approved"))

            if course_id:
                db.execute("INSERT OR IGNORE INTO enrollments (id, student_id, course_id, status, enrolled_at) VALUES (?,?,?,?,datetime('now'))",
                           (_uid(), student_id, course_id, "approved"))

            db.commit()

        bump_version()
        return self._send_json({
            "success": True,
            "student": {
                "id": student_id,
                "name": name,
                "student_number": student_number,
                "email": email_key
            }
        })

    def _read_body_silent(self):
        """Reads body without crashing if empty."""
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length == 0: return None
            return json.loads(self.rfile.read(length).decode('utf-8'))
        except: return None

    def _admin_get_all_students(self):
        """Returns all student accounts across the entire system. Admin only."""
        if not self._is_admin():
            return self._send_error("Unauthorized", 403)
        with db_connection() as db:
            students = db.execute("""
                SELECT u.id, u.name, u.email, u.status, u.created_at, u.last_seen,
                       CASE 
                           WHEN u.last_seen IS NOT NULL AND (strftime('%s','now') - strftime('%s', u.last_seen)) <= 12 THEN 1 
                           ELSE 0 
                       END as is_active,
                       GROUP_CONCAT(DISTINCT c.name) as enrolled_in,
                       COUNT(DISTINCT e.course_id) as course_count,
                       COALESCE((SELECT COUNT(*) FROM responses r WHERE r.student_id = u.id), 0) as total_responses
                FROM users u
                LEFT JOIN enrollments e ON u.id = e.student_id
                LEFT JOIN courses c ON e.course_id = c.id
                WHERE u.role = 'student'
                GROUP BY u.id
                ORDER BY u.created_at DESC
            """).fetchall()
            
            from database import PERMANENT_STUDENTS
            perm_numbers = {s['number'] for s in PERMANENT_STUDENTS}
            perm_emails = {f"{s['number']}@student.aulaai" for s in PERMANENT_STUDENTS}

            res = []
            for s in students:
                item = dict(s)
                num = (item.get('email') or '').split('@')[0]
                item['is_permanent'] = bool(item.get('email') in perm_emails or num in perm_numbers or str(item.get('id', '')).replace('student-', '') in perm_numbers)
                res.append(item)
            return self._send_json(res)

    def _admin_reset_student_pin(self):
        """Resets the PIN for a specific student across all their enrollments. Admin only."""
        if not self._is_admin():
            return self._send_error("Unauthorized", 403)
        body = self._read_body()
        student_id = body.get("student_id")
        if not student_id:
            return self._send_error("student_id required")
        with db_connection() as db:
            db.execute("UPDATE enrollments SET pin = NULL WHERE student_id = ?", (student_id,))
            db.commit()
        return self._send_json({"success": True})

    def _admin_reset_student_progress(self):
        """Wipes all quiz results, assignment responses, and mastery scores for a student. Admin only."""
        if not self._is_admin():
            return self._send_error("Unauthorized", 403)
        body = self._read_body()
        student_id = body.get("student_id")
        if not student_id:
            return self._send_error("student_id required")
        with db_connection() as db:
            db.execute("DELETE FROM responses WHERE student_id = ?", (student_id,))
            db.execute("DELETE FROM mastery_scores WHERE student_id = ?", (student_id,))
            db.commit()
        return self._send_json({"success": True})

    def _admin_reset_students(self):
        """Deletes ALL student accounts and their associated data. Admin only."""
        if not self._is_admin():
            return self._send_error("Unauthorized", 403)
        body = self._read_body()
        confirm = body.get("confirm")
        if confirm != "RESET ALL STUDENTS":
            return self._send_error("Confirmation failed")
        try:
            from database import sync_permanent_students_and_enrollments, PERMANENT_STUDENTS
            perm_emails = {f"{s['number']}@student.aulaai" for s in PERMANENT_STUDENTS}
            perm_nums = {s['number'] for s in PERMANENT_STUDENTS}
            with db_connection() as db:
                all_students = db.execute("SELECT id, email FROM users WHERE role = 'student'").fetchall()
                non_perm_ids = [
                    r[0] for r in all_students 
                    if r[1] not in perm_emails and r[1].split('@')[0] not in perm_nums and str(r[0]).replace('student-', '') not in perm_nums
                ]
                if non_perm_ids:
                    placeholders = ','.join('?' * len(non_perm_ids))
                    db.execute(f"DELETE FROM responses WHERE student_id IN ({placeholders})", non_perm_ids)
                    db.execute(f"DELETE FROM mastery_scores WHERE student_id IN ({placeholders})", non_perm_ids)
                    db.execute(f"DELETE FROM messages WHERE student_id IN ({placeholders})", non_perm_ids)
                    db.execute(f"DELETE FROM enrollments WHERE student_id IN ({placeholders})", non_perm_ids)
                    db.execute(f"DELETE FROM sessions WHERE user_id IN ({placeholders})", non_perm_ids)
                    db.execute(f"DELETE FROM users WHERE id IN ({placeholders})", non_perm_ids)
                    db.commit()
                # Re-synchronize permanent students
                sync_permanent_students_and_enrollments(db)
            bump_version()
            return self._send_json({"success": True, "deleted": len(non_perm_ids)})
        except Exception as e:
            return self._send_error(f"Reset failed: {str(e)}")

    def _admin_hard_reset(self):
        """Hard delete everything. Restricted to primary admin email."""
        if not self._is_admin():
            return self._send_error("Unauthorized", 403)
        
        body = self._read_body()
        confirm = body.get("confirm")
        if confirm != "HARD DELETE EVERYTHING":
            return self._send_error("Confirmation failed")

        try:
            with db_connection() as db:
                tables = [
                    'weekly_reports', 'assignment_questions', 'assignment_submissions', 'assignments',
                    'quiz_questions', 'quiz_results', 'quizzes', 'responses', 'response_history',
                    'questions', 'activities', 'topics', 'chapters', 'enrollments', 'mastery_scores',
                    'student_mastery', 'messages', 'courses', 'sessions'
                ]
                for table in tables:
                    db.execute(f"DROP TABLE IF EXISTS {table}")
                db.commit()
            
            # Re-initialize DB to create fresh tables
            from database import init_db
            init_db()
            
            self._send_json({"success": True, "message": "All classroom data has been wiped. Fresh start ready."})
        except Exception as e:
            self._send_error(f"Reset failed: {str(e)}")

    def _logout(self):
        body = self._read_body_silent() or {}
        user_id = body.get("user_id") if isinstance(body, dict) else None
        if not user_id:
            user_id = self._get_user_id()
        if user_id:
            with db_connection() as db:
                db.execute("UPDATE users SET last_seen = NULL WHERE id = ?", (user_id,))
                db.commit()
            bump_version()
        return self._send_json({"success": True})

    def _user_heartbeat(self):
        body = self._read_body_silent() or {}
        user_id = body.get("user_id") if isinstance(body, dict) else None
        if not user_id:
            user_id = self._get_user_id()
        if not user_id:
            return self._send_error("user_id required", 400)
        
        with db_connection() as db:
            row = db.execute("""
                SELECT (last_seen IS NULL OR (strftime('%s','now') - strftime('%s', last_seen)) > 12) as was_inactive
                FROM users WHERE id = ?
            """, (user_id,)).fetchone()
            was_inactive = bool(row and row[0])
            db.execute("UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
            db.commit()
            if was_inactive:
                bump_version()
        return self._send_json({"success": True, "active": True})

    def _delete_user_account(self):
        user_id = self._get_user_id()
        if not user_id:
            return self._send_error("Authentication required")
        
        with db_connection() as db:
            # Delete EVERYTHING related to this user
            db.execute("DELETE FROM responses WHERE student_id = ?", (user_id,))
            db.execute("DELETE FROM mastery_scores WHERE student_id = ?", (user_id,))
            db.execute("DELETE FROM enrollments WHERE student_id = ?", (user_id,))
            db.execute("DELETE FROM messages WHERE student_id = ?", (user_id,))
            db.execute("DELETE FROM users WHERE id = ?", (user_id,))
            db.commit()
            
        bump_version()
        self._send_json({"success": True})

    def _reset_data(self):
        """Erase student data. Can be classroom-specific or global."""
        body = self._read_body()
        confirm = body.get("confirm")
        course_id = body.get("course_id")

        if confirm != "ERASE ALL DATA":
            return self._send_error("Confirmation text does not match")

        with db_connection() as db:
            if course_id:
                # OWNERSHIP CHECK: Ensure the lecturer owns this classroom
                if not self._verify_course_ownership(db, course_id):
                    return self._send_error("Forbidden: You do not own this classroom", 403)

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
                db.execute("DELETE FROM sessions WHERE course_id = ?", (course_id,))
            else:
                # GLOBAL RESET DISABLED FOR SAFETY
                return self._send_error("Global reset is disabled to prevent data loss.", 403)

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
        course_id = body.get("course_id")
        if not student_id:
            return self._send_error("student_id required")
            
        from database import PERMANENT_STUDENTS
        perm_emails = {f"{s['number']}@student.aulaai" for s in PERMANENT_STUDENTS}
        perm_nums = {s['number'] for s in PERMANENT_STUDENTS}

        with db_connection() as db:
            user = db.execute("SELECT email FROM users WHERE id = ?", (student_id,)).fetchone()
            if user:
                email = user[0] or ""
                num = email.split('@')[0]
                if email in perm_emails or num in perm_nums or str(student_id).replace('student-', '') in perm_nums:
                    return self._send_error("Permanent student accounts cannot be removed", 400)

            if course_id:
                # Classroom-scoped removal: Only unenroll student from this course!
                db.execute("DELETE FROM responses WHERE student_id = ? AND course_id = ?", (student_id, course_id))
                db.execute("DELETE FROM messages WHERE student_id = ? AND course_id = ?", (student_id, course_id))
                db.execute("DELETE FROM enrollments WHERE student_id = ? AND course_id = ?", (student_id, course_id))
            else:
                # Global removal: Delete profile and all records!
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

    def _admin_upload_db(self):
        """Temporary admin endpoint: upload a DB file. Restricted to primary admin."""
        if not self._is_admin():
            return self._send_error("Unauthorized", 403)
        
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return self._send_error("No data received")
        
        db_bytes = self.rfile.read(length)
        
        from database import DB_PATH, IS_RAILWAY
        target = DB_PATH if IS_RAILWAY else os.path.join("data", "aula.db")
        
        # Backup existing DB before overwriting
        backup = target + ".backup"
        if os.path.exists(target):
            import shutil
            shutil.copy2(target, backup)
            print(f"[ADMIN] Backed up existing DB to {backup}")
        
        with open(target, "wb") as f:
            f.write(db_bytes)
        
        size = os.path.getsize(target)
        print(f"[ADMIN] Uploaded DB: {size} bytes -> {target}")
        
        # Re-run migrations on the uploaded DB to ensure schema compatibility
        from database import _run_migrations
        _run_migrations()
        
        return self._send_json({"success": True, "size": size, "path": target})

    def _get_ai_status(self):
        """Return whether AI is configured and available."""
        self._send_json({
            "ai_enabled": is_ai_available(),
            "provider": ("OpenRouter (Gemini 2.5 Flash + GPT-4o-mini)" if is_ai_available() else "Mock Engine"),
            "features": {
                "dynamic_activities": is_ai_available(),
                "smart_grading": is_ai_available(),
                "ai_reports": is_ai_available()
            }
        })

    def _login(self):
        body = self._read_body()
        email = (body.get("email") or "").strip()
        password = (body.get("password") or "").strip()
        
        hashed_pwd = hash_password(password)
        clean_num = email.split('@')[0].strip()
        email_key = f"{clean_num}@student.aulaai"
        stu_id = f"student-{clean_num}"

        with db_connection() as db:
            user = db.execute(
                "SELECT * FROM users WHERE (email = ? OR email = ? OR id = ?) AND password = ?",
                (email, email_key, stu_id, hashed_pwd)
            ).fetchone()

            if user:
                user = dict(user)
                # Auto-enrollment for permanent developer students only
                if user.get("role") == "student":
                    from database import PERMANENT_STUDENTS
                    perm_emails = {f"{s['number']}@student.aulaai" for s in PERMANENT_STUDENTS}
                    perm_nums = {s['number'] for s in PERMANENT_STUDENTS}
                    u_email = user.get("email") or ""
                    u_id = str(user.get("id") or "")
                    is_perm = u_email in perm_emails or u_email.split('@')[0] in perm_nums or u_id.replace('student-', '') in perm_nums
                    if is_perm:
                        courses = db.execute("SELECT id FROM courses").fetchall()
                        for c_row in courses:
                            cid = c_row[0]
                            existing = db.execute("SELECT id, status FROM enrollments WHERE student_id = ? AND course_id = ?", (user["id"], cid)).fetchone()
                            if not existing:
                                import uuid
                                db.execute("INSERT OR IGNORE INTO enrollments (id, student_id, course_id, status, pin, enrolled_at, last_active) VALUES (?, ?, ?, 'approved', NULL, datetime('now'), datetime('now'))", (str(uuid.uuid4()), user["id"], cid))
                            elif existing[1] != 'approved':
                                db.execute("UPDATE enrollments SET status = 'approved' WHERE id = ?", (existing[0],))
                        db.commit()

                # Set last_seen activity immediately on login
                db.execute("UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
                db.commit()
                bump_version()

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
            
        hashed_pwd = hash_password(password)

        with db_connection() as db:
            existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                return self._send_error("An account with this email already exists")

            student_id = _uid()
            db.execute("INSERT INTO users (id, name, email, password, role, status, created_at) VALUES (?,?,?,?,?,?,datetime('now'))",
                       (student_id, name, email, hashed_pwd, "student", "pending"))

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

    def _get_student_enrollments(self, student_id):
        if not student_id:
            return self._send_error("student_id is required")
        with db_connection() as db:
            from database import PERMANENT_STUDENTS
            perm_emails = {f"{s['number']}@student.aulaai" for s in PERMANENT_STUDENTS}
            perm_nums = {s['number'] for s in PERMANENT_STUDENTS}
            u = db.execute("SELECT email FROM users WHERE id = ?", (student_id,)).fetchone()
            u_email = u[0] if u else ""
            is_perm = u_email in perm_emails or u_email.split('@')[0] in perm_nums or str(student_id).replace('student-', '') in perm_nums
            if is_perm:
                courses = db.execute("SELECT id FROM courses").fetchall()
                for c_row in courses:
                    cid = c_row[0]
                    existing = db.execute("SELECT id, status FROM enrollments WHERE student_id = ? AND course_id = ?", (student_id, cid)).fetchone()
                    if not existing:
                        import uuid
                        db.execute("""
                            INSERT OR IGNORE INTO enrollments (id, student_id, course_id, status, pin, enrolled_at, last_active)
                            VALUES (?, ?, ?, 'approved', NULL, datetime('now'), datetime('now'))
                        """, (str(uuid.uuid4()), student_id, cid))
                    elif existing[1] != 'approved':
                        db.execute("UPDATE enrollments SET status = 'approved' WHERE id = ?", (existing[0],))
                db.commit()

            enrollments = db.execute("""
                SELECT e.*, c.name as course_name, c.code as course_code, c.textbook, c.language, c.level
                FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                WHERE e.student_id = ?
                ORDER BY e.enrolled_at DESC
            """, (student_id,)).fetchall()
            return self._send_json({"enrollments": [dict(e) for e in enrollments]})

    def _student_portal_login(self):
        """Student enters portal with student number and password."""
        body = self._read_body()
        student_id = body.get("student_id")
        student_number = (body.get("student_number") or "").strip()
        password = (body.get("password") or "").strip()

        if student_id and not password:
            return self._get_student_enrollments(student_id)

        if not student_number:
            return self._send_error("Student number is required")
        if not password:
            return self._send_error("Password is required")

        clean_num = student_number.split('@')[0].strip()
        email_key = f"{clean_num}@student.aulaai"
        hashed_pwd = hash_password(password)
        
        with db_connection() as db:
            user = db.execute(
                "SELECT * FROM users WHERE (email = ? OR email = ? OR id = ?) AND role = 'student'",
                (student_number, email_key, f"student-{clean_num}")
            ).fetchone()
            if not user:
                return self._send_error("Invalid student number or password", 401)
            
            user = dict(user)
            user_pwd = user.get("password") or ""
            
            if not user_pwd or user_pwd == "[STUDENT_PORTAL]" or user_pwd != hashed_pwd:
                return self._send_error("Invalid student number or password", 401)
            
            # Auto-enrollment for permanent developer students only
            from database import PERMANENT_STUDENTS
            perm_emails = {f"{s['number']}@student.aulaai" for s in PERMANENT_STUDENTS}
            perm_nums = {s['number'] for s in PERMANENT_STUDENTS}
            u_email = user.get("email") or ""
            u_id = str(user.get("id") or "")
            is_perm = u_email in perm_emails or u_email.split('@')[0] in perm_nums or u_id.replace('student-', '') in perm_nums
            if is_perm:
                all_courses = db.execute("SELECT id FROM courses").fetchall()
                for c_row in all_courses:
                    cid = c_row[0]
                    existing_enroll = db.execute("SELECT id, status FROM enrollments WHERE student_id = ? AND course_id = ?", (user["id"], cid)).fetchone()
                    if not existing_enroll:
                        import uuid
                        db.execute("""
                            INSERT OR IGNORE INTO enrollments (id, student_id, course_id, status, pin, enrolled_at, last_active)
                            VALUES (?, ?, ?, 'approved', NULL, datetime('now'), datetime('now'))
                        """, (str(uuid.uuid4()), user["id"], cid))
                    elif existing_enroll[1] != 'approved':
                        db.execute("UPDATE enrollments SET status = 'approved' WHERE id = ?", (existing_enroll[0],))
                db.commit()

            # Set last_seen activity immediately on student portal login
            db.execute("UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
            db.commit()
            bump_version()

            # Fetch all enrollments
            enrollments = db.execute("""
                SELECT e.*, c.name as course_name, c.code as course_code, c.textbook, c.language, c.level
                FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                WHERE e.student_id = ?
                ORDER BY e.enrolled_at DESC
            """, (user["id"],)).fetchall()
            
            self._send_json({
                "user": {"id": user["id"], "name": user["name"],
                         "email": user["email"], "role": user["role"], "status": user.get("status", "approved")},
                "enrollments": [dict(e) for e in enrollments]
            })

    def _student_join_classroom(self):
        body = self._read_body()
        student_id = body.get("student_id")
        raw_code = body.get("code") or ""
        code = str(raw_code).strip()
        
        if not student_id:
            return self._send_error("student_id is required")
        if not code:
            return self._send_error("Classroom code is required")
        
        with db_connection() as db:
            course = db.execute("SELECT id, name, code, language, level FROM courses WHERE UPPER(TRIM(code)) = UPPER(TRIM(?))", (code,)).fetchone()
            if not course:
                return self._send_error("Invalid classroom code. Please verify the code with your teacher.")
            
            course_id = course["id"]
            existing = db.execute("SELECT id, status FROM enrollments WHERE student_id = ? AND course_id = ?", (student_id, course_id)).fetchone()
            
            if not existing:
                db.execute("INSERT INTO enrollments (id, student_id, course_id, status, enrolled_at) VALUES (?,?,?,?,datetime('now'))",
                           (_uid(), student_id, course_id, "pending"))
                db.commit()
                bump_version()
                status = "pending"
            else:
                status = existing["status"]
            
            # Return updated enrollments for this student
            enrollments = db.execute("""
                SELECT e.*, c.name as course_name, c.code as course_code, c.textbook, c.language, c.level
                FROM enrollments e
                JOIN courses c ON e.course_id = c.id
                WHERE e.student_id = ?
                ORDER BY e.enrolled_at DESC
            """, (student_id,)).fetchall()

            return self._send_json({
                "success": True, 
                "status": status,
                "course_id": course_id,
                "course_name": course["name"],
                "enrollments": [dict(e) for e in enrollments]
            })

    def _student_set_pin(self):
        self._send_json({"success": True})

    def _student_access_classroom(self):
        body = self._read_body()
        student_id = body.get("student_id")
        course_id = body.get("course_id")
        
        with db_connection() as db:
            enr = db.execute("SELECT status FROM enrollments WHERE student_id = ? AND course_id = ?", (student_id, course_id)).fetchone()
            if not enr:
                return self._send_error("Not enrolled")
            if enr["status"] != "approved":
                return self._send_error("Not approved")
                
            self._send_json({"success": True})


    def _get_courses(self):
        user_id = self._get_user_id()
        role = self._get_user_role()
        
        with db_connection() as db:
            # IDENTITY SEPARATION: Lecturers only see their own classrooms
            # Admin (atunca96@gmail.com) can see everything for system management
            if role == 'lecturer' and user_id != 'lecturer-demo-id':
                courses = db.execute("SELECT * FROM courses WHERE lecturer_id = ?", (user_id,)).fetchall()
            else:
                # Students and the Primary Admin see all
                courses = db.execute("SELECT * FROM courses").fetchall()
            
            result = []
            for c in courses:
                c_dict = dict(c)
                
                # Attach enrollment status for students
                if role == 'student':
                    enr = db.execute("SELECT status FROM enrollments WHERE student_id=? AND course_id=?", (user_id, c["id"])).fetchone()
                    c_dict["enrollment_status"] = enr["status"] if enr else "none"
                    c_dict.pop("lecturer_id", None)

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

                if c["is_building"]:
                    c_dict["build_progress"] = done
                    c_dict["build_total"] = total if total > 0 else (c["total_steps"] or 28)
                    topic_ratio = (done / total) if total > 0 else 0
                    c_dict["percentage"] = min(96, max(3, (3 if done == 0 else (10 + int(topic_ratio * 85)))))
                    c_dict["progress"] = topic_ratio
                else:
                    c_dict["progress"] = (done / total) if total > 0 else 0
                    c_dict["percentage"] = 100
                result.append(c_dict)
        self._send_json(result)

    def _get_curriculum(self, course_id):
        """Fetch the full curriculum (chapters and topics) for a course."""
        with db_connection() as db:
            if not course_id:
                # For lecturers, no fallback. For students, fallback to first joined? 
                # For now, just return empty if no ID.
                return self._send_json([])
            
            if not self._verify_course_access(db, course_id):
                return self._send_error("Forbidden: You do not have access to this classroom", 403)

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
                    raw_pdf = str(t_dict.get("pdf_url") or "").strip()
                    if raw_pdf and raw_pdf.upper() != "NONE" and not raw_pdf.upper().endswith("/NONE"):
                        t_dict["pdf_url"] = "/books/" + os.path.basename(raw_pdf)
                    else:
                        t_dict["pdf_url"] = None
                    processed_topics.append(t_dict)
                ch_dict["topics"] = processed_topics
                result.append(ch_dict)

        self._send_json(result)

    def _get_students(self, course_id):
        """Fetch all students enrolled in a classroom."""
        with db_connection() as db:
            if not course_id: return self._send_json([])
            
            if not self._verify_course_ownership(db, course_id):
                return self._send_error("Forbidden: You do not own this classroom", 403)

            students = db.execute("""
                SELECT u.id, u.name, u.email, u.status, u.last_seen, e.pin,
                       CASE 
                           WHEN u.last_seen IS NOT NULL AND (strftime('%s','now') - strftime('%s', u.last_seen)) <= 12 THEN 1 
                           ELSE 0 
                       END as is_active
                FROM users u
                JOIN enrollments e ON u.id = e.student_id
                WHERE e.course_id = ? AND e.status = 'approved'
                ORDER BY u.name
            """, (course_id,)).fetchall()

            result = []
            for s in students:
                s_dict = dict(s)
                # Get mastery scores FILTERED by course
                masteries = db.execute("""
                    SELECT ms.score FROM mastery_scores ms
                    JOIN topics t ON ms.topic_id = t.id
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ms.student_id = ? AND ch.course_id = ?
                """, (s["id"], course_id)).fetchall()
                
                if masteries:
                    scores = [m["score"] for m in masteries]
                    s_dict["avg_mastery"] = round(sum(scores) / len(scores), 3)
                else:
                    s_dict["avg_mastery"] = 0.0

                # Response count FILTERED by course
                resp_count = db.execute("""
                    SELECT COUNT(*) as cnt FROM responses r
                    JOIN questions q ON r.question_id = q.id
                    JOIN topics t ON q.topic_id = t.id
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE r.student_id = ? AND ch.course_id = ?
                """, (s["id"], course_id)).fetchone()["cnt"]
                s_dict["total_responses"] = resp_count

                from database import PERMANENT_STUDENTS
                perm_numbers = {ps['number'] for ps in PERMANENT_STUDENTS}
                perm_emails = {f"{ps['number']}@student.aulaai" for ps in PERMANENT_STUDENTS}
                s_email = s_dict.get("email") or ""
                s_num = s_email.split('@')[0]
                s_dict["is_permanent"] = bool(s_email in perm_emails or s_num in perm_numbers or str(s_dict.get("id", "")).replace("student-", "") in perm_numbers)

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
                "SELECT * FROM questions WHERE topic_id = ? AND is_active = 1", (topic_id,)
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
                    py_random.shuffle(opts)
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
            user_id = post_data.get("user_id") or self._get_user_id() or "anonymous"
            ui_lang = post_data.get("ui_lang", "en")
            count = min(20, max(1, int(post_data.get("count", 5))))
            client_existing = post_data.get("existing_questions") or []
            
            if not topic_id or not course_id:
                return self._send_error("Missing info")

            topic_key = str(topic_id)

            # Retain all questions from exactly the two most recent completed test batches for this course/topic
            retained_batches_qs = get_course_draft_batches(course_id, topic_key)
            merged_existing = []
            seen_prompts = set()
            for q in retained_batches_qs:
                if isinstance(q, dict):
                    p = (q.get("prompt") or "").strip()
                    if p and p.lower() not in seen_prompts:
                        seen_prompts.add(p.lower())
                        merged_existing.append(q)

            if isinstance(client_existing, list):
                for q in client_existing:
                    if isinstance(q, dict):
                        p = (q.get("prompt") or "").strip()
                        if p and p.lower() not in seen_prompts:
                            seen_prompts.add(p.lower())
                            merged_existing.append(q)
                
            task_id = str(uuid.uuid4())
            initial_data = {
                "task_id": task_id,
                "course_id": course_id,
                "user_id": user_id,
                "topic_id": topic_id,
                "status": "generating",
                "percentage": 0,
                "results": None
            }
            set_activity_task(task_id, initial_data)
            set_activity_task(f"{course_id}_{user_id}_{topic_id}", initial_data)
            
            # Start background thread
            import threading
            file_log(f"Starting background generation task {task_id} for course {course_id}, user {user_id}, topic {topic_id}")
            thread = threading.Thread(target=self._bg_generate_activities, args=(task_id, course_id, topic_id, count, ui_lang, user_id, merged_existing, topic_key))
            thread.daemon = True
            thread.start()
            
            self._send_json({"status": "success", "task_id": task_id})
        except Exception as e:
            print(f"[ERROR] _activity_start failed: {e}")
            import traceback
            traceback.print_exc()
            self._send_error(str(e))

    def _bg_generate_activities(self, task_id, course_id, topic_id, count, ui_lang="en", user_id=None, existing_questions=None, topic_key=None):
        import re
        import random as py_random
        import time
        import traceback
        
        def update_prog(p, status='generating', results=None, message=None):
            task_dict = {"percentage": p, "status": status}
            if results is not None:
                task_dict["results"] = results
            if message is not None:
                task_dict["message"] = message
            set_activity_task(task_id, task_dict)
            if user_id:
                set_activity_task(f"{course_id}_{user_id}_{topic_id}", task_dict)

        msg_init = "Ders içeriği taranıyor..." if ui_lang == "tr" else "Scanning lesson content..."
        update_prog(15, message=msg_init)

        if not topic_key:
            topic_key = str(topic_id)

        try:
            from services.content_engine import generate_assessment_set

            def progress_cb(pct, msg=None):
                update_prog(pct, message=msg)

            requested_count = int(count)
            t_flow_start = time.time()
            retained_existing_prompts = [
                (q.get("prompt") or "").strip() for q in (existing_questions or [])
                if isinstance(q, dict) and q.get("prompt")
            ]

            t_ai_start = time.time()
            questions = generate_assessment_set(
                topic_ids=[topic_id],
                count=requested_count,
                is_quiz=False,
                ui_lang=ui_lang,
                existing_questions=existing_questions,
                progress_callback=progress_cb,
                generation_seed=py_random.randint(100, 99999)
            )
            t_ai_duration = time.time() - t_ai_start

            t_filter_start = time.time()
            # PASS 1: Strict filter (no repeated prompt from recent rounds or within selection)
            final_questions = []
            for q in (questions or []):
                if not isinstance(q, dict) or not q.get("prompt") or not q.get("answer"):
                    continue
                p = q.get("prompt", "")
                if any(is_near_identical_question(p, rep) for rep in retained_existing_prompts):
                    continue
                if any(is_near_identical_question(p, fq.get("prompt", "")) for fq in final_questions):
                    continue
                final_questions.append(q)
                if len(final_questions) >= requested_count:
                    break

            # PASS 2: Reuse remaining candidates from initial generation whose prompts are distinct before any top-up
            if len(final_questions) < requested_count:
                for q in (questions or []):
                    if not isinstance(q, dict) or not q.get("prompt") or not q.get("answer"):
                        continue
                    p = q.get("prompt", "")
                    if any(q.get("id") == fq.get("id") or q.get("prompt") == fq.get("prompt") for fq in final_questions):
                        continue
                    if any(is_near_identical_question(p, fq.get("prompt", "")) for fq in final_questions):
                        continue
                    final_questions.append(q)
                    if len(final_questions) >= requested_count:
                        break

            # PASS 3: Check database course questions for topic before triggering any AI top-up
            if len(final_questions) < requested_count and topic_id:
                try:
                    with db_connection() as db:
                        db_qs = db.execute("""
                            SELECT id, topic_id, type, prompt, answer, distractors, difficulty
                            FROM questions WHERE topic_id = ? ORDER BY RANDOM() LIMIT 15
                        """, (topic_id,)).fetchall()
                        for r in db_qs:
                            rp = r["prompt"]
                            ra = r["answer"]
                            if any(is_near_identical_question(rp, fq.get("prompt", "")) for fq in final_questions):
                                continue
                            try:
                                d_list = json.loads(r["distractors"]) if r["distractors"] else []
                            except Exception:
                                d_list = []
                            if len(d_list) < 3:
                                continue
                            opts = [ra] + d_list[:3]
                            py_random.shuffle(opts)
                            final_questions.append({
                                "id": r["id"],
                                "topic_id": r["topic_id"],
                                "type": r["type"],
                                "prompt": rp,
                                "translation": "",
                                "translation_en": "",
                                "translation_tr": "",
                                "answer": ra,
                                "distractors": d_list[:3],
                                "options": opts,
                                "difficulty": r["difficulty"],
                                "why": "Lesson reference.",
                                "why_tr": "Ders içeriğine göre doğru seçenek."
                            })
                            if len(final_questions) >= requested_count:
                                break
                except Exception as edb:
                    file_log(f"DB backfill error: {edb}")
            t_filter_duration = time.time() - t_filter_start

            # Top-up pass ONLY if initial candidate pool and DB were exhausted and shortfall remains
            t_topup_duration = 0.0
            if len(final_questions) < requested_count:
                t_topup_start = time.time()
                max_topup_attempts = 2
                topup_attempt = 0
                while len(final_questions) < requested_count and topup_attempt < max_topup_attempts:
                    topup_attempt += 1
                    missing = requested_count - len(final_questions)
                    combined_existing = (existing_questions or []) + final_questions
                    fresh_qs = generate_assessment_set(
                        topic_ids=[topic_id],
                        count=missing,
                        is_quiz=False,
                        ui_lang=ui_lang,
                        existing_questions=combined_existing,
                        progress_callback=progress_cb
                    )
                    if not fresh_qs:
                        break
                    added_any = False
                    for q in fresh_qs:
                        if not isinstance(q, dict) or not q.get("prompt") or not q.get("answer"):
                            continue
                        p = q.get("prompt", "")
                        if any(is_near_identical_question(p, rep) for rep in retained_existing_prompts):
                            continue
                        if any(is_near_identical_question(p, fq.get("prompt", "")) for fq in final_questions):
                            continue
                        final_questions.append(q)
                        added_any = True
                        if len(final_questions) >= requested_count:
                            break
                    if not added_any:
                        break
                t_topup_duration = time.time() - t_topup_start
                file_log(f"[QUIZ-TIMING] Activity top-up pass={t_topup_duration:.2f}s (shortfall={requested_count - len(final_questions)})")
            else:
                file_log("[QUIZ-TIMING] Activity top-up: 0.00s (candidate pool sufficient)")

            final_questions = final_questions[:requested_count]

            t_persist_start = time.time()
            # Record batch into last 2 completed batches history
            record_course_draft_batch(course_id, final_questions, topic_key)

            msg_done = "Sorular hazır!" if ui_lang == "tr" else "Questions ready!"
            update_prog(100, status='done', results=final_questions, message=msg_done)
            t_persist_duration = time.time() - t_persist_start
            t_flow_duration = time.time() - t_flow_start

            file_log(f"[QUIZ-TIMING] Activity: Main AI call={t_ai_duration:.2f}s | Parsing/filtering/reuse={t_filter_duration:.3f}s | Top-up={t_topup_duration:.2f}s | Persistence={t_persist_duration:.3f}s | Total={t_flow_duration:.2f}s")
            print(f"[BG] Activity generation COMPLETED for task {task_id} (user {user_id}) with {len(final_questions)} questions.")

        except Exception as e:
            msg = f"BG Activity Error: {str(e)}"
            print(f"[CRITICAL] {msg}")
            file_log(msg)
            file_log(traceback.format_exc())
            update_prog(0, status='error', message=str(e))

    def _get_activity(self, topic_id):
        if not topic_id:
            return self._send_json([])
        with db_connection() as db:
            row = db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
            if not row:
                return self._send_json([])
            topic = dict(row)
            content = json.loads(topic["content"]) if isinstance(topic.get("content"), str) else (topic.get("content") or {})
            
            if isinstance(content, dict) and content.get("activities"):
                return self._send_json(content["activities"][:10])
            
            from services.ai_engine import ai_generate_activity_batch
            batch = ai_generate_activity_batch(topic.get("title", ""), topic.get("type", "vocabulary"), content, "Spanish", count=10, level=topic.get("difficulty", "A1"), model_override="none")
            return self._send_json(batch or [])

    def _activity_progress(self, course_id=None):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        task_id = params.get("task_id", [None])[0]
        user_id = params.get("user_id", [None])[0] or self._get_user_id()
        topic_id = params.get("topic_id", [None])[0]
        cid = course_id or params.get("course_id", [None])[0]

        task = None
        if task_id:
            task = get_activity_task(task_id)
        if not task and cid and user_id and topic_id:
            task = get_activity_task(f"{cid}_{user_id}_{topic_id}")

        if task:
            return self._send_json({
                "status": task.get("status", "idle"),
                "percentage": task.get("percentage", 0),
                "message": task.get("message", ""),
                "results": task.get("results")
            })

        # Self-healing fallback: if task expired or container restarted, synthesize and return done
        if topic_id:
            with db_connection() as db:
                row = db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
                if row:
                    topic = dict(row)
                    content = json.loads(topic["content"]) if isinstance(topic.get("content"), str) else (topic.get("content") or {})
                    from services.ai_engine import ai_generate_activity_batch
                    batch = ai_generate_activity_batch(topic.get("title", ""), topic.get("type", "vocabulary"), content, "Spanish", count=10, level=topic.get("difficulty", "A1"), model_override="none")
                    if batch:
                        heal_task = {"status": "done", "percentage": 100, "results": batch}
                        if task_id: set_activity_task(task_id, heal_task)
                        return self._send_json(heal_task)

        # Fallback to DB courses table for legacy compatibility
        if cid:
            with db_connection() as db:
                row = db.execute("SELECT activity_status, activity_progress, activity_total, activity_result FROM courses WHERE id=?", (cid,)).fetchone()
                if row:
                    data = dict(row)
                    return self._send_json({
                        "status": data.get("activity_status", "idle"),
                        "percentage": data.get("activity_progress", 0),
                        "results": json.loads(data["activity_result"]) if data["activity_result"] else None
                    })
        return self._send_json({"status": "idle", "percentage": 0, "results": None})

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
                    db.execute("INSERT INTO responses (id, student_id, question_id, context_type, context_id, answer, score, graded_by, feedback) VALUES (?,?,?,?,?,?,?,?,?)",
                               (_uid(), student_id, q["id"], "quiz", quiz_id, "[STARTED]", 0.0, "auto", "Quiz started"))
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
                        py_random.shuffle(opts)
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
                        "total_questions": 0,
                        "answered_count": 0,
                        "has_unsubmitted": False
                    }
                is_started = (r_dict["student_answer"] == "[STARTED]")
                if is_started:
                    students_map[sid]["has_unsubmitted"] = True
                else:
                    students_map[sid]["answered_count"] += 1

                students_map[sid]["answers"].append({
                    "question_id": r_dict["question_id"],
                    "prompt": r_dict["prompt"],
                    "student_answer": r_dict["student_answer"],
                    "correct_answer": r_dict["correct_answer"],
                    "score": r_dict["score"] if not is_started else 0.0,
                    "is_correct": (r_dict["score"] >= 0.8) if not is_started else False,
                    "is_started": is_started,
                    "submitted_at": r_dict["submitted_at"]
                })
                if not is_started:
                    students_map[sid]["total_score"] += r_dict["score"]
                students_map[sid]["total_questions"] += 1

            student_results = []
            completed_scores = []
            for sid, sdata in students_map.items():
                sdata["status"] = "in_progress" if sdata["has_unsubmitted"] else "completed"
                sdata["is_completed"] = not sdata["has_unsubmitted"]
                if sdata["is_completed"]:
                    sdata["average_score"] = round(sdata["total_score"] / max(sdata["total_questions"], 1), 3)
                    completed_scores.append(sdata["average_score"])
                else:
                    sdata["average_score"] = 0.0
                student_results.append(sdata)
            student_results.sort(key=lambda x: (x["status"] != "completed", x["student_name"]))
            class_avg = round(sum(completed_scores) / max(len(completed_scores), 1), 3) if completed_scores else 0.0

        self._send_json({
            "quiz": dict(quiz),
            "questions": questions_list,
            "student_results": student_results,
            "total_students": len(student_results),
            "average_score": class_avg
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

        ui_lang = body.get("ui_lang", "en")

        from services.content_engine import generate_quiz
        questions = generate_quiz(topic_ids, count=count, is_quiz=True, ui_lang=ui_lang)

        quiz_id = _uid()
        with db_connection() as db:
            db.execute("INSERT INTO quizzes (id, course_id, title, due_date, is_published, created_at) VALUES (?,?,?,datetime('now','+1 day'),1,datetime('now'))",
                       (quiz_id, course_id, title))

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
        topic_key = str(chapter_id or "all")
        ui_lang = body.get("ui_lang", "en")
        client_existing = body.get("existing_questions") or []
        try:
            count = min(20, max(1, int(body.get("count", 10))))
        except (ValueError, TypeError):
            count = 10
            
        with db_connection() as db:
            if not course_id:
                course = db.execute("SELECT id FROM courses LIMIT 1").fetchone()
                if course: course_id = course["id"]

            # Save any previous draft questions before resetting draft_result
            prev_draft = db.execute("SELECT draft_result FROM courses WHERE id=?", (course_id,)).fetchone()
            if prev_draft and prev_draft["draft_result"]:
                try:
                    prev_qs = json.loads(prev_draft["draft_result"])
                    if isinstance(prev_qs, list) and prev_qs:
                        record_course_draft_batch(course_id, prev_qs, topic_key)
                except Exception:
                    pass
                
            if chapter_id and chapter_id != "all" and chapter_id != "":
                # Quizzes strictly cover the entire unit (Chapter)
                is_chapter = db.execute("SELECT id FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
                if is_chapter:
                    topics = db.execute("SELECT id FROM topics WHERE chapter_id = ?", (chapter_id,)).fetchall()
                else:
                    # If a topic ID was passed, expand to its full parent chapter so quizzes always cover the full unit
                    is_topic = db.execute("SELECT chapter_id FROM topics WHERE id = ?", (chapter_id,)).fetchone()
                    if is_topic and is_topic["chapter_id"]:
                        topics = db.execute("SELECT id FROM topics WHERE chapter_id = ?", (is_topic["chapter_id"],)).fetchall()
                    else:
                        topics = []
            else:
                topics = db.execute("""
                    SELECT t.id FROM topics t
                    JOIN chapters ch ON t.chapter_id = ch.id
                    WHERE ch.course_id = ?
                """, (course_id,)).fetchall()
                
            topic_ids = [t["id"] for t in topics]

            # Retain all questions from exactly the two most recent completed quiz drafts for the same course/topic
            retained_batches_qs = get_course_draft_batches(course_id, topic_key)
            merged_existing = []
            seen_prompts = set()
            
            for q in retained_batches_qs:
                if isinstance(q, dict):
                    p = (q.get("prompt") or "").strip()
                    if p and p.lower() not in seen_prompts:
                        seen_prompts.add(p.lower())
                        merged_existing.append(q)

            # Current batch context (e.g. from client request or active draft)
            if isinstance(client_existing, list):
                for q in client_existing:
                    if isinstance(q, dict):
                        p = (q.get("prompt") or "").strip()
                        if p and p.lower() not in seen_prompts:
                            seen_prompts.add(p.lower())
                            merged_existing.append(q)

            db.execute("UPDATE courses SET draft_status='generating', draft_progress=0, draft_result=NULL WHERE id=?", (course_id,))
            db.commit()
            
        import threading
        thread = threading.Thread(target=self._bg_generate_draft, args=(course_id, topic_ids, count, ui_lang, merged_existing, topic_key))
        thread.daemon = True
        thread.start()
        
        self._send_json({"status": "success"})

    def _bg_generate_draft(self, course_id, topic_ids, count, ui_lang="en", existing_questions=None, topic_key="all"):
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

            class ProgressState:
                def __init__(self):
                    self.current_milestone = 10
                    self.is_done = False
            
            state = ProgressState()

            def ticker_worker():
                last_written_p = 0
                est_time = max(6.0, (count * 0.25) + 4.5)
                start_time = time.time()
                
                while not state.is_done:
                    time.sleep(1.0)
                    elapsed = time.time() - start_time
                    
                    import math
                    k = 2.0 / est_time 
                    predicted_p = int(95 * (1 - math.exp(-k * elapsed)))
                    if predicted_p > 98: predicted_p = 98
                    if predicted_p >= last_written_p + 4:
                        last_written_p = predicted_p
                        update_draft_prog(predicted_p)
            
            ticker_thread = threading.Thread(target=ticker_worker, daemon=True)
            ticker_thread.start()

            requested_count = int(count)
            retained_existing_prompts = [
                (q.get("prompt") or "").strip() for q in (existing_questions or [])
                if isinstance(q, dict) and q.get("prompt")
            ]
            retained_existing_answers = [
                (q.get("answer") or "").strip() for q in (existing_questions or [])
                if isinstance(q, dict) and q.get("answer")
            ]

            t_flow_start = time.time()
            try:
                # Concurrent sub-batch generation for speed (7-10s) when count >= 8
                t_ai_start = time.time()
                topup_time = 0.0
                topup_calls = 0
                if requested_count >= 8:
                    half = (requested_count + 1) // 2
                    count_a = max(half + 6, 12)
                    count_b = max((requested_count - half) + 6, 12)
                    
                    topics_a = topic_ids
                    topics_b = topic_ids

                    # Check if selected topics contain explicit grammar rules or contrasts (via preassembled cache)
                    has_explicit_grammar = False
                    try:
                        from services.quiz_source_cache import get_or_assemble_quiz_source
                        with db_connection() as db:
                            placeholders = ','.join('?' for _ in topic_ids)
                            rows = db.execute(f"SELECT id, title, type, content FROM topics WHERE id IN ({placeholders})", topic_ids).fetchall()
                            for r in rows:
                                q_src = get_or_assemble_quiz_source(r["id"], r["title"], r["type"] or "concept", r["content"], ui_lang)
                                if q_src["has_explicit_grammar"]:
                                    has_explicit_grammar = True
                                    break
                    except Exception as e_check:
                        file_log(f"Error checking topic grammar rules: {e_check}")
                        has_explicit_grammar = True

                    dir_a = "focus_grammar" if has_explicit_grammar else None

                    timing_ctx_a = {}
                    timing_ctx_b = {}
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                        future_a = executor.submit(
                            generate_quiz,
                            topics_a,
                            count=count_a,
                            is_quiz=True,
                            ui_lang=ui_lang,
                            existing_questions=existing_questions,
                            generation_seed=101,
                            focus_directive=dir_a,
                            timing_ctx=timing_ctx_a
                        )
                        future_b = executor.submit(
                            generate_quiz,
                            topics_b,
                            count=count_b,
                            is_quiz=True,
                            ui_lang=ui_lang,
                            existing_questions=existing_questions,
                            generation_seed=202,
                            focus_directive="focus_lexicon",
                            timing_ctx=timing_ctx_b
                        )
                        res_a = []
                        res_b = []
                        try:
                            res_a = future_a.result() or []
                        except Exception as ea:
                            file_log(f"Sub-batch A error: {ea}")
                        try:
                            res_b = future_b.result() or []
                        except Exception as eb:
                            file_log(f"Sub-batch B error: {eb}")
                    questions = res_a + res_b
                    topup_time = max(timing_ctx_a.get("top_up", 0.0), timing_ctx_b.get("top_up", 0.0))
                    topup_calls = timing_ctx_a.get("topup_ai_calls", 0) + timing_ctx_b.get("topup_ai_calls", 0)
                else:
                    timing_ctx_single = {}
                    questions = generate_quiz(
                        topic_ids,
                        count=requested_count + 6,
                        is_quiz=True,
                        ui_lang=ui_lang,
                        existing_questions=existing_questions,
                        generation_seed=101,
                        timing_ctx=timing_ctx_single
                    )
                    topup_time = timing_ctx_single.get("top_up", 0.0)
                    topup_calls = timing_ctx_single.get("topup_ai_calls", 0)
                t_ai_duration = time.time() - t_ai_start
                
                t_filter_start = time.time()
                # PASS 1: Strict filter (no repeated prompt, no repeated answer from recent rounds, zero test conflict)
                final_questions = []
                for q in (questions or []):
                    if not isinstance(q, dict) or not q.get("prompt") or not q.get("answer"):
                        continue
                    p = q.get("prompt", "")
                    a = q.get("answer", "")
                    # Check against previous 2 completed test batches
                    if any(is_near_identical_question(p, rep) for rep in retained_existing_prompts):
                        continue
                    if any(normalize_prompt_text(a) == normalize_prompt_text(rep_a) for rep_a in retained_existing_answers):
                        continue
                    # Enforce strict test-internal independence (zero duplicate suffixes, idioms, or answer leaks)
                    if any(is_test_conflict(q, fq) for fq in final_questions):
                        continue
                    final_questions.append(q)
                    if len(final_questions) >= requested_count:
                        break

                # PASS 2 (SAFETY NET): If strict cross-test answer filter left a shortfall (< requested_count),
                # backfill from candidates whose PROMPTS are completely unique and have zero test conflicts,
                # relaxing only the cross-test identical answer check with older test rounds.
                if len(final_questions) < requested_count:
                    for q in (questions or []):
                        if not isinstance(q, dict) or not q.get("prompt") or not q.get("answer"):
                            continue
                        p = q.get("prompt", "")
                        a = q.get("answer", "")
                        if any(q.get("id") == fq.get("id") or q.get("prompt") == fq.get("prompt") for fq in final_questions):
                            continue
                        if any(is_near_identical_question(p, rep) for rep in retained_existing_prompts):
                            continue
                        if any(is_near_identical_question(p, fq.get("prompt", "")) for fq in final_questions):
                            continue
                        if any(normalize_prompt_text(a) == normalize_prompt_text(fq.get("answer", "")) for fq in final_questions):
                            continue
                        if any(is_test_conflict(q, fq) for fq in final_questions):
                            continue
                        final_questions.append(q)
                        if len(final_questions) >= requested_count:
                            break

                # PASS 3 (DATABASE SAFETY NET): If still short, backfill from available course questions in DB
                if len(final_questions) < requested_count and topic_ids:
                    try:
                        with db_connection() as db:
                            placeholders = ",".join("?" * len(topic_ids))
                            db_qs = db.execute(f"""
                                SELECT id, topic_id, type, prompt, answer, distractors, difficulty
                                FROM questions
                                WHERE topic_id IN ({placeholders})
                                ORDER BY RANDOM() LIMIT 25
                            """, list(topic_ids)).fetchall()
                            for r in db_qs:
                                rp = str(r["prompt"] or "").strip()
                                ra = str(r["answer"] or "").strip()
                                if "[" in rp or "]" in rp or "[" in ra or "]" in ra:
                                    continue
                                if any(is_near_identical_question(rp, fq.get("prompt", "")) for fq in final_questions):
                                    continue
                                if any(normalize_prompt_text(ra) == normalize_prompt_text(fq.get("answer", "")) for fq in final_questions):
                                    continue
                                try:
                                    d_list = json.loads(r["distractors"]) if r["distractors"] else []
                                except Exception:
                                    d_list = []
                                d_list = [str(d).strip() for d in d_list if str(d).strip() and "[" not in str(d) and "]" not in str(d)]
                                if len(d_list) < 3:
                                    continue
                                opts = [ra] + d_list[:3]
                                py_random.shuffle(opts)
                                final_questions.append({
                                    "id": r["id"],
                                    "topic_id": r["topic_id"],
                                    "type": r["type"],
                                    "prompt": rp,
                                    "translation": "",
                                    "translation_en": "",
                                    "translation_tr": "",
                                    "answer": ra,
                                    "distractors": d_list[:3],
                                    "options": opts,
                                    "difficulty": r["difficulty"],
                                    "why": "Lesson reference.",
                                    "why_tr": "Ders içeriğine göre doğru seçenek."
                                })
                                if len(final_questions) >= requested_count:
                                    break
                    except Exception as edb:
                        file_log(f"Safety net DB backfill error: {edb}")

                # PASS 4 (CANDIDATE POOL GUARANTEED BACKFILL): Ensure test NEVER has fewer than requested_count
                if len(final_questions) < requested_count:
                    for q in (questions or []):
                        if not isinstance(q, dict) or not q.get("prompt") or not q.get("answer"):
                            continue
                        p = (q.get("prompt") or "").strip()
                        a = (q.get("answer") or "").strip()
                        if "[" in p or "]" in p or "[" in a or "]" in a:
                            continue
                        if any(is_near_identical_question(p, fq.get("prompt", "")) for fq in final_questions):
                            continue
                        if any(normalize_prompt_text(a) == normalize_prompt_text(fq.get("answer", "")) for fq in final_questions):
                            continue
                        final_questions.append(q)
                        if len(final_questions) >= requested_count:
                            break
                t_filter_duration = time.time() - t_filter_start
            finally:
                state.is_done = True
                ticker_thread.join(timeout=1.0)

            # Enforce hard completion invariant: Draft is only complete if exactly requested_count questions are assembled
            if len(final_questions) < requested_count:
                file_log(f"Draft question count shortfall ({len(final_questions)} < {requested_count}) for {course_id}. Aborting draft.")
                print(f"[BG] Draft question count shortfall ({len(final_questions)} < {requested_count}) for {course_id}. Marked draft_status='error'.")
                with db_connection() as db:
                    db.execute("UPDATE courses SET draft_status='error' WHERE id=?", (course_id,))
                    db.commit()
                return

            final_questions = final_questions[:requested_count]

            t_persist_start = time.time()
            record_course_draft_batch(course_id, final_questions, topic_key)

            with db_connection() as db:
                db.execute("UPDATE courses SET draft_status='done', draft_progress=100, draft_result=? WHERE id=?", 
                           (json.dumps(final_questions, ensure_ascii=False), course_id))
                db.commit()
            t_persist_duration = time.time() - t_persist_start
            t_flow_duration = time.time() - t_flow_start
            
            log_draft_msg = f"[QUIZ-TIMING] Draft: Main AI calls={t_ai_duration:.2f}s (candidates={len(questions)}) | Filtering/dedup/backfill={t_filter_duration:.3f}s | Top-up={topup_time:.2f}s (calls={topup_calls}) | Persistence={t_persist_duration:.3f}s | Total={t_flow_duration:.2f}s"
            file_log(log_draft_msg)
            print(log_draft_msg)
            print(f"[BG] Quiz Draft generation COMPLETED for {course_id} with {len(final_questions)} fresh questions.")
                
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
                db.execute("INSERT INTO quizzes (id, course_id, title, due_date, is_published, created_at) VALUES (?,?,?,datetime('now','+1 day'),1,datetime('now'))",
                           (pub_id, course_id, title))
            else:
                db.execute("INSERT INTO assignments (id, course_id, title, description, due_date, is_published, created_at) VALUES (?,?,?,?,?,?,datetime('now'))",
                           (pub_id, course_id, title, None if chapter_id == "all" else chapter_id, due_at, 1))
                
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
                    db.execute("INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, metadata, is_active) VALUES (?,?,?,?,?,?,?,?,?)",
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
                    db.execute("INSERT INTO responses (id, student_id, question_id, context_type, context_id, answer, score, graded_by, feedback) VALUES (?,?,?,?,?,?,?,?,?)",
                               (_uid(), student_id, qid, "quiz", quiz_id,
                                student_answer, score, "auto", feedback))

                topic_id = question["topic_id"]
                existing = db.execute(
                    "SELECT score FROM mastery_scores WHERE student_id = ? AND topic_id = ?",
                    (student_id, topic_id)
                ).fetchone()

                current_score = existing["score"] if (existing and existing["score"] is not None) else score
                new_score = (current_score * 0.7 + score * 0.3)
                db.execute("INSERT OR REPLACE INTO mastery_scores (student_id, topic_id, score) VALUES (?,?,?)",
                           (student_id, topic_id, round(new_score, 3)))

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

    def _explain_activity_question(self):
        body = self._read_body()
        prompt = body.get("prompt")
        correct_answer = body.get("correct_answer")
        student_answer = body.get("student_answer")
        language = body.get("language", "English")
        course_id = body.get("course_id")
        ui_lang = body.get("ui_lang", "en")
        
        if not all([prompt, correct_answer, student_answer]):
            return self._send_error("Missing required fields for explanation", 400)
            
        material_language = "en"
        if course_id:
            try:
                with db_connection() as db:
                    row = db.execute("SELECT material_language FROM courses WHERE id=?", (course_id,)).fetchone()
                    if row and row["material_language"]:
                        material_language = row["material_language"]
            except Exception as e:
                print(f"[ERROR] Failed to query material_language for activity explain: {e}")
                
        if ui_lang and ui_lang in ["tr", "en"]:
            material_language = ui_lang
            
        result = ai_explain_activity(prompt, correct_answer, student_answer, language, material_language=material_language)
        return self._send_json(result)

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
                db.execute("INSERT INTO responses (id, student_id, question_id, context_type, context_id, answer, score, graded_by, feedback) VALUES (?,?,?,?,?,?,?,?,?)",
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
                    db.execute("INSERT OR REPLACE INTO mastery_scores (student_id, topic_id, score) VALUES (?,?,?)",
                               (student_id, tid, round(new_score, 3)))
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
                    SELECT co.language, co.material_language FROM courses co
                    JOIN chapters ch ON co.id = ch.course_id
                    JOIN topics t ON ch.id = t.chapter_id
                    WHERE t.id = ?
                """, (topic_id,)).fetchone()
                language = row["language"] if row and row["language"] else "Unknown"
                material_language = row["material_language"] if row and "material_language" in row.keys() else "en"
                activities = generate_activity(dict(topic), count=8, language=language, material_language=material_language) if topic else []
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
            db.execute("INSERT INTO assignments (id, course_id, title, description, due_date, is_published, created_at) VALUES (?,?,?,?,?,?,datetime('now'))",
                       (assignment_id, course_id, title, None if chapter_id == "all" else chapter_id, due_at, 1))

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
        questions = generate_quiz(topic_ids, count=count, is_quiz=False)
        
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
                        "answered": 0,
                        "answered_count": 0,
                        "has_unsubmitted": False
                    }
                q = question_map.get(row["question_id"], {})
                is_started = (row["student_answer"] == "[STARTED]")
                if is_started:
                    students[sid]["has_unsubmitted"] = True
                else:
                    students[sid]["answered_count"] += 1

                students[sid]["answers"].append({
                    "question_id": row["question_id"],
                    "prompt": q.get("prompt", ""),
                    "correct_answer": q.get("answer", ""),
                    "student_answer": row["student_answer"],
                    "score": row["score"] if not is_started else 0.0,
                    "is_correct": (row["score"] >= 0.8) if not is_started else False,
                    "is_started": is_started
                })
                if not is_started:
                    students[sid]["total_score"] += row["score"]
                students[sid]["answered"] += 1

            result = []
            completed_scores = []
            for s in students.values():
                s["status"] = "in_progress" if s["has_unsubmitted"] else "completed"
                s["is_completed"] = not s["has_unsubmitted"]
                s["total_questions"] = len(question_map)
                if s["is_completed"]:
                    s["average_score"] = round(s["total_score"] / max(s["total_questions"], 1), 3)
                    completed_scores.append(s["average_score"])
                else:
                    s["average_score"] = 0.0
                result.append(s)

            class_avg = round(sum(completed_scores) / max(len(completed_scores), 1), 3) if completed_scores else 0.0

        self._send_json({
            "assignment_id": assignment_id,
            "title": assignment["title"],
            "total_questions": len(question_map),
            "student_results": sorted(result, key=lambda x: (x["status"] != "completed", -x["average_score"])),
            "average_score": class_avg
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
                    completed = db.execute("SELECT 1 FROM responses WHERE student_id = ? AND context_id = ? AND context_type = 'assignment' AND answer != '[STARTED]' LIMIT 1", (student_id, a["id"])).fetchone()
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
                    db.execute("INSERT INTO responses (id, student_id, question_id, context_type, context_id, answer, score, graded_by, feedback) VALUES (?,?,?,?,?,?,?,?,?)",
                               (_uid(), student_id, qid, "assignment", aid, student_answer, score, "auto", feedback))
                tid = question.get("topic_id") if isinstance(question, dict) else (question["topic_id"] if question and "topic_id" in question.keys() else None)
                if tid:
                    existing = db.execute("SELECT score FROM mastery_scores WHERE student_id = ? AND topic_id = ?", (student_id, tid)).fetchone()
                    current_score = existing["score"] if (existing and existing["score"] is not None) else score
                    new_score = (current_score * 0.7 + score * 0.3)
                    db.execute("INSERT OR REPLACE INTO mastery_scores (student_id, topic_id, score) VALUES (?,?,?)",
                               (student_id, tid, round(new_score, 3)))
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
        if not result or len(result) < 4:
            # Fallback to cached blueprint if available
            from services.ai_engine import _get_blueprint_path
            cache_file = _get_blueprint_path(language, level)
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cached_data = json.load(f)
                        if cached_data and cached_data.get("chapters") and len(cached_data["chapters"]) >= 4:
                            result = cached_data["chapters"]
                except Exception:
                    pass

        if not result: return self._send_error("Failed to generate syllabus", 500)
        
        try:
            from services.curriculum_translator import ensure_bilingual_curriculum
            result = ensure_bilingual_curriculum(result)
        except Exception as e:
            print(f"[CURRICULUM] Warning: ensure_bilingual_curriculum in _draft_curriculum: {e}")
            
        return self._send_json({"syllabus": result})

    def _create_classroom_from_scratch(self):
        """Creates a classroom without a PDF."""
        data = self._read_body()
        language = data.get("language")
        level = data.get("level")
        course_name = data.get("course_name")
        chapters = data.get("chapters") 
        lecturer_id = data.get("lecturer_id")
        material_language = data.get("material_language", "tr")
        
        cid = data.get("course_id")
        # Ensure we treat falsy/null values as None
        course_id = cid if cid and cid != "null" and cid != "undefined" else None
        
        
        from services.legacy.pdf_pipeline import process_manual_to_classroom
        result = process_manual_to_classroom(chapters, language, level, lecturer_id, course_name, existing_course_id=course_id, material_language=material_language)
        return self._send_json(result)

    def _stop_classroom_build(self):
        """Stops an ongoing classroom generation process and terminates its background worker."""
        data = self._read_body()
        course_id = data.get("course_id")
        if not course_id:
            return self._send_error("course_id required")

        # 1. Terminate worker process via PID file if running
        pid_file = os.path.join("data", "workers", f"{course_id}.pid")
        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r", encoding="utf-8") as f:
                    pid = int(f.read().strip())
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
                else:
                    import signal
                    os.kill(pid, signal.SIGTERM)
                file_log(f"Terminated worker PID {pid} for stopped course {course_id}")
            except Exception as e:
                file_log(f"Error terminating worker PID: {e}")
            try:
                os.remove(pid_file)
            except Exception:
                pass

        # 2. Update database to stop state
        with db_connection() as db:
            db.execute("""
                UPDATE courses 
                SET is_building = 0, build_stage = 'stopped', build_message = 'Ders üretimi kullanıcı tarafından durduruldu.' 
                WHERE id = ?
            """, (course_id,))
            db.commit()

        bump_version()
        file_log(f"Build stopped for Course {course_id}")
        return self._send_json({"success": True, "message": "Ders üretimi durduruldu."})

    def _translate_material(self):
        """Translates educational material text between English and Turkish on demand for newly created classrooms."""
        data = self._read_body()
        text = data.get("text", "").strip()
        target_lang = data.get("target_lang", "tr").lower()
        if not text:
            return self._send_json({"translated": ""})

        # Check local pre-compiled cache first
        cache_path = os.path.join(os.path.dirname(__file__), "bilingual_materials.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                if target_lang == "tr" and text in cache.get("sentence_pairs", {}):
                    return self._send_json({"translated": cache["sentence_pairs"][text]})
                if target_lang == "en" and text in cache.get("sentence_pairs_tr_en", {}):
                    return self._send_json({"translated": cache["sentence_pairs_tr_en"][text]})
                if text in cache.get("vocab_pairs", {}):
                    return self._send_json({"translated": cache["vocab_pairs"][text]})
            except Exception:
                pass

        # If not cached, translate via OpenRouter
        try:
            from services.ai_engine import _call_ai
            dest = "Turkish" if target_lang == "tr" else "English"
            prompt = f"Translate the following educational text into natural, CEFR-aligned {dest}. Keep all foreign terms (e.g. Spanish, Greek) in quotes exactly as they are. Return ONLY a JSON object: {{\"translation\": \"...\"}}\n\nText:\n{text}"
            res = _call_ai([{"role": "user", "content": prompt}], max_tokens=1000, temperature=0.1)
            translated = res.get("translation") or res.get("text") or res.get("result") if isinstance(res, dict) else str(res)
            if not translated or translated == "{}" or translated == "None":
                translated = text
            return self._send_json({"translated": translated})
        except Exception as e:
            return self._send_json({"translated": text, "error": str(e)})

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
            external_markdown = fields.get("external_markdown")
            lecturer_id = fields.get("lecturer_id")
            
            # ALLOW MOCK/MARKDOWN ONLY CREATION
            if not (files and "pdf" in files) and not external_markdown:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG] No PDF and no Markdown provided")
                return self._send_error("PDF file or Markdown analysis required")
            
            course_name = fields.get("course_name")
            toc_range = fields.get("toc_range", "1-20")
            manual_toc = fields.get("manual_toc")
            external_markdown = fields.get("external_markdown")
            lecturer_id = fields.get("lecturer_id")
            language = fields.get("language")
            level = fields.get("level", "A1")
            material_language = fields.get("material_language", "en")
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [DEBUG] Processing Request for {lecturer_id} | Name: {course_name} | Language: {language} | Material Lang: {material_language}")
            
            if not lecturer_id:
                return self._send_error("lecturer_id required")
                
            # LINKED FILE NAMING: Use a shared UID for PDF and Markdown to ensure rebuild stability
            shared_uid = _uid()
            pdf_path = "NONE"
            if files and "pdf" in files:
                pdf_data = files["pdf"]["content"]
                
                # Save file persistently in data/books/
                safe_filename = f"course_{shared_uid}.pdf"
                os.makedirs(BOOKS_DIR, exist_ok=True)
                pdf_path = os.path.join(BOOKS_DIR, safe_filename)
                
                file_log(f"[DEBUG] Saving PDF to {pdf_path} ({len(pdf_data)} bytes)")
                with open(pdf_path, "wb") as f:
                    f.write(pdf_data)
            
            # Save External Markdown if provided
            source_md_path = None
            if external_markdown:
                safe_md_name = f"course_{shared_uid}_source.md"
                source_md_path = os.path.join(BOOKS_DIR, safe_md_name)
                with open(source_md_path, "w", encoding="utf-8") as f:
                    f.write(external_markdown)
                file_log(f"[DEBUG] External Markdown saved to {source_md_path}")
 
            file_log('LAUNCHING ARCHITECT PIPELINE')
            result = process_pdf_to_classroom(
                pdf_path, 
                toc_range, 
                lecturer_id, 
                course_name=course_name, 
                manual_toc=manual_toc,
                source_markdown_path=source_md_path,
                language=language,
                level=level,
                material_language=material_language
            )
            
            file_log(f"[DEBUG] Pipeline result: {result}")

            if result.get("success"):
                if result.get("course_id"):
                    from database import enroll_permanent_students_in_course
                    enroll_permanent_students_in_course(result["course_id"])
                bump_version()
                self._send_json(result)
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] _create_classroom_from_pdf: {e}")
            import traceback
            traceback.print_exc()
            return self._send_json({"success": False, "error": str(e)}, 500)

    def _delete_classroom(self):
        body = self._read_body()
        course_id = body.get("course_id")
        if not course_id:
            return self._send_error("course_id required")
            
        with db_connection() as db:
            if not self._verify_course_ownership(db, course_id):
                return self._send_error("Forbidden: You do not own this classroom", 403)
        
        try:
            with db_connection() as db:
                course = db.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
                if not course:
                    return self._send_error("Course not found")
                
                # [CLEANUP] All classrooms can now be deleted
                if False: 
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
                
                # Generate a new batch of 15 questions (total cap is 30)
                count = 15
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

    def _delete_chapter(self):
        data = self._read_body()
        chapter_id = data.get("chapter_id")
        if not chapter_id: return self._send_error("Missing chapter_id")
        with db_connection() as db:
            db.execute("DELETE FROM topics WHERE chapter_id = ?", (chapter_id,))
            db.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
            db.commit()
        return self._send_json({"success": True})

    def _delete_topic(self):
        data = self._read_body()
        topic_id = data.get("topic_id")
        if not topic_id: return self._send_error("Missing topic_id")
        with db_connection() as db:
            db.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
            db.commit()
        return self._send_json({"success": True})

def _cleanup_orphaned_building_flags():
    """Reset building and activity flags for tasks that were interrupted by a server restart."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [STARTUP] Resetting orphaned building and activity flags...")
    with db_connection() as db:
        # 1. Reset Classroom Building flags (interrupted builds)
        db.execute("""
            UPDATE courses SET is_building = 0, build_stage = 'interrupted', build_message = 'Build interrupted by server restart'
            WHERE is_building = 1
        """)
        
        # 2. Reset Activity Generation flags (Always reset on startup since threads are gone)
        db.execute("UPDATE courses SET activity_status = 'idle', activity_progress = 0 WHERE activity_status = 'generating'")
        
        db.commit()

def _repair_german_corruption():
    """Surgical repair for German OCR artifacts (e.g. Arabic characters replacing 'ß')"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [MAINTENANCE] Checking for German character corruption...")
    with db_connection() as db:
        # Patterns to fix
        replacements = [
            ("hei ى t", "heißt"),
            ("hei ىt", "heißt"),
            ("hei ى", "heißt"),
            (" ى ", " ß "),
            ("ى", "ß")
        ]
        
        # Repair Topics
        topics = db.execute("SELECT id, title FROM topics WHERE title LIKE '%ى%'").fetchall()
        for t in topics:
            old_title = t["title"]
            new_title = old_title
            for search, replace in replacements:
                new_title = new_title.replace(search, replace)
            
            if old_title != new_title:
                print(f"[REPAIR] Fixing Topic: '{old_title}' -> '{new_title}'")
                db.execute("UPDATE topics SET title = ? WHERE id = ?", (new_title, t["id"]))

        # Repair Chapters
        chapters = db.execute("SELECT id, title FROM chapters WHERE title LIKE '%ى%'").fetchall()
        for c in chapters:
            old_title = c["title"]
            new_title = old_title
            for search, replace in replacements:
                new_title = new_title.replace(search, replace)
            
            if old_title != new_title:
                print(f"[REPAIR] Fixing Chapter: '{old_title}' -> '{new_title}'")
                db.execute("UPDATE chapters SET title = ? WHERE id = ?", (new_title, c["id"]))

        db.commit()

class RobustServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True

def main():
    try:
        # Startup: wait for volume before DB init, with retries for Railway timing instability
        from database import _wait_for_volume
        if not _wait_for_volume(context="startup/init_db"):
            print("[FATAL] Volume unavailable at startup after retries. Exiting to force Railway restart.")
            sys.exit(1)
        init_db()
        _cleanup_orphaned_building_flags()
        _repair_german_corruption()
        
        server = RobustServer(("0.0.0.0", PORT), APIHandler)
        server.daemon_threads = True
        
        print(f"""
============================================================
  AulaAI — Language Learning System
  Textbook: Aula Internacional Plus 1

  Server running at: http://localhost:{PORT}
  Mode: Threaded (crash-safe)
  Maintenance: Auto-cleanup of stale tasks (30min timeout)

  Lecturer login: atunca96@gmail.com / [Secured]
  Students: Register at the login page
============================================================
        """)
        
        elapsed = round(time.time() - _startup_t, 2)
        print(f"[READY] AulaAI listening on 0.0.0.0:{PORT} — startup took {elapsed}s")
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
