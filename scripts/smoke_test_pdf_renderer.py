import contextlib
import json
import os
import sqlite3
import tempfile

# Build-time smoke test for the actual production renderer. Force local database
# mode so importing database.py never expects Railway's /data mount during build.
os.environ.pop('RAILWAY_ENVIRONMENT', None)

from services import pdf_renderer_v12 as renderer

fd, db_path = tempfile.mkstemp(suffix='.sqlite3')
os.close(fd)

try:
    conn = sqlite3.connect(db_path)
    conn.executescript('''
        CREATE TABLE courses (
            id TEXT PRIMARY KEY, name TEXT, language TEXT, level TEXT, semester TEXT
        );
        CREATE TABLE chapters (
            id TEXT PRIMARY KEY, course_id TEXT, number INTEGER, title TEXT
        );
        CREATE TABLE topics (
            id TEXT PRIMARY KEY, chapter_id TEXT, type TEXT, title TEXT,
            content TEXT, sort_order INTEGER DEFAULT 0
        );
    ''')
    content = {
        'topic_title_tr': 'Tanışma ve Temel İfadeler',
        'pages': [
            {
                'type': 'vocabulary',
                'title': 'Essential Phrases',
                'title_tr': 'Temel İfadeler',
                'items': [
                    {
                        'term': '¿Cómo te llamas?',
                        'translation_en': 'What is your name?',
                        'translation_tr': 'Adın ne?',
                        'example': '—¿Cómo te llamas? —Me llamo Ana.',
                        'example_en': '—What is your name? —My name is Ana.',
                        'example_tr': '—Adın ne? —Benim adım Ana.',
                    }
                ],
            },
            {
                'type': 'mcq',
                'title': '5. Formative Quick-Check',
                'title_tr': '5. Hızlı Kontrol',
                'prompt': '¿Cómo se dice “hello”?',
                'prompt_en': 'How do you say “hello”?',
                'prompt_tr': '“Merhaba” nasıl denir?',
                'options': ['Hola', 'Adiós', 'Gracias', 'Perdón'],
                'options_en': ['Hola', 'Adiós', 'Gracias', 'Perdón'],
                'options_tr': ['Hola', 'Adiós', 'Gracias', 'Perdón'],
                'answer': 'Hola',
                'explanation': 'Hola is the standard greeting.',
                'explanation_tr': 'Hola standart selamlaşmadır.',
            },
        ],
    }
    conn.execute('INSERT INTO courses VALUES (?,?,?,?,?)', ('smoke', 'Spanish A1', 'Spanish', 'A1', ''))
    conn.execute('INSERT INTO chapters VALUES (?,?,?,?)', ('ch1', 'smoke', 1, 'First Contact'))
    conn.execute('INSERT INTO topics VALUES (?,?,?,?,?,?)', ('t1', 'ch1', 'vocabulary', 'Introductions', json.dumps(content, ensure_ascii=False), 0))
    conn.commit()
    conn.close()

    @contextlib.contextmanager
    def fake_db_connection():
        db = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    renderer.db_connection = fake_db_connection

    # First prove compatibility with an older schema lacking title_tr columns.
    for lang in ('en', 'tr'):
        pdf_bytes, _ = renderer.render_course_pdf('smoke', lang)
        if not isinstance(pdf_bytes, (bytes, bytearray)) or not pdf_bytes.startswith(b'%PDF') or len(pdf_bytes) < 1000:
            raise RuntimeError(f'PDF smoke test failed for legacy schema / {lang}')

    # Then prove the current migrated production schema with title_tr columns.
    conn = sqlite3.connect(db_path)
    conn.execute('ALTER TABLE chapters ADD COLUMN title_tr TEXT')
    conn.execute('ALTER TABLE topics ADD COLUMN title_tr TEXT')
    conn.execute("UPDATE chapters SET title_tr = 'İlk Temas' WHERE id = 'ch1'")
    conn.execute("UPDATE topics SET title_tr = 'Tanışmalar' WHERE id = 't1'")
    conn.commit()
    conn.close()

    for lang in ('en', 'tr'):
        pdf_bytes, _ = renderer.render_course_pdf('smoke', lang)
        if not isinstance(pdf_bytes, (bytes, bytearray)) or not pdf_bytes.startswith(b'%PDF') or len(pdf_bytes) < 1000:
            raise RuntimeError(f'PDF smoke test failed for migrated schema / {lang}')

    print('PDF renderer v12 smoke test passed (legacy+migrated schema, EN+TR)')
finally:
    try:
        os.remove(db_path)
    except OSError:
        pass
