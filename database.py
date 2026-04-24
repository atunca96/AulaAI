"""
Database module — SQLite setup, schema creation, and seed data for
Aula Internacional Plus 1 curriculum.
"""

import sqlite3
import json
import uuid
import os
import math
import random
from contextlib import contextmanager
from datetime import datetime, timedelta

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "data", "prototype.db"))


def get_db():
    """Get a database connection with row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def db_connection():
    """Context manager that ensures the database connection is always closed."""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Create all tables and seed with curriculum data."""
    conn = get_db()
    c = conn.cursor()

    # ── Schema ──────────────────────────────────────────────
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('lecturer','student')),
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # ── Safe Migration: Add status column to existing DB ────
    try:
        c.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'approved'")
    except sqlite3.OperationalError:
        pass # Column already exists
        
    c.executescript("""

        CREATE TABLE IF NOT EXISTS courses (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            semester TEXT NOT NULL,
            textbook TEXT,
            language TEXT DEFAULT 'Spanish',
            lecturer_id TEXT REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # ── Safe Migration: Add language column to existing courses table ──
    try:
        c.execute("ALTER TABLE courses ADD COLUMN language TEXT DEFAULT 'Spanish'")
    except sqlite3.OperationalError:
        pass # Column already exists

    c.executescript("""
            id TEXT PRIMARY KEY,
            student_id TEXT REFERENCES users(id),
            course_id TEXT REFERENCES courses(id),
            enrolled_at TEXT DEFAULT (datetime('now')),
            UNIQUE(student_id, course_id)
        );

        CREATE TABLE IF NOT EXISTS chapters (
            id TEXT PRIMARY KEY,
            course_id TEXT REFERENCES courses(id),
            number INTEGER NOT NULL,
            title TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS topics (
            id TEXT PRIMARY KEY,
            chapter_id TEXT REFERENCES chapters(id),
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            difficulty TEXT DEFAULT 'A1.1',
            content TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY,
            topic_id TEXT REFERENCES topics(id),
            type TEXT NOT NULL,
            prompt TEXT NOT NULL,
            answer TEXT NOT NULL,
            distractors TEXT,
            difficulty TEXT NOT NULL,
            variant_group TEXT,
            metadata TEXT,
            approved INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS quizzes (
            id TEXT PRIMARY KEY,
            course_id TEXT REFERENCES courses(id),
            title TEXT NOT NULL,
            chapter_id TEXT REFERENCES chapters(id),
            opens_at TEXT,
            closes_at TEXT,
            time_limit_minutes INTEGER DEFAULT 15,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS quiz_questions (
            quiz_id TEXT REFERENCES quizzes(id),
            question_id TEXT REFERENCES questions(id),
            sort_order INTEGER DEFAULT 0,
            PRIMARY KEY (quiz_id, question_id)
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id TEXT PRIMARY KEY,
            course_id TEXT REFERENCES courses(id),
            title TEXT NOT NULL,
            chapter_id TEXT REFERENCES chapters(id),
            due_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS assignment_questions (
            assignment_id TEXT REFERENCES assignments(id),
            question_id TEXT REFERENCES questions(id),
            sort_order INTEGER DEFAULT 0,
            PRIMARY KEY (assignment_id, question_id)
        );

        CREATE TABLE IF NOT EXISTS responses (
            id TEXT PRIMARY KEY,
            student_id TEXT REFERENCES users(id),
            question_id TEXT REFERENCES questions(id),
            context_type TEXT NOT NULL,
            context_id TEXT NOT NULL,
            answer TEXT NOT NULL,
            score REAL CHECK (score >= 0 AND score <= 1),
            graded_by TEXT DEFAULT 'auto',
            feedback TEXT,
            submitted_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS mastery_scores (
            id TEXT PRIMARY KEY,
            student_id TEXT REFERENCES users(id),
            topic_id TEXT REFERENCES topics(id),
            score REAL CHECK (score >= 0 AND score <= 1),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(student_id, topic_id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            student_id TEXT REFERENCES users(id),
            sender TEXT DEFAULT 'student',
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            course_id TEXT REFERENCES courses(id),
            chapter_id TEXT REFERENCES chapters(id),
            session_date TEXT,
            status TEXT DEFAULT 'scheduled',
            started_at TEXT,
            ended_at TEXT
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id TEXT PRIMARY KEY,
            course_id TEXT REFERENCES courses(id),
            title TEXT NOT NULL,
            chapter_id TEXT REFERENCES chapters(id),
            due_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS assignment_questions (
            assignment_id TEXT REFERENCES assignments(id),
            question_id TEXT REFERENCES questions(id),
            sort_order INTEGER,
            PRIMARY KEY (assignment_id, question_id)
        );

        CREATE TABLE IF NOT EXISTS weekly_reports (
            id TEXT PRIMARY KEY,
            course_id TEXT REFERENCES courses(id),
            week_number INTEGER NOT NULL,
            report_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(course_id, week_number)
        );

        CREATE INDEX IF NOT EXISTS idx_responses_student ON responses(student_id);
        CREATE INDEX IF NOT EXISTS idx_responses_context ON responses(context_type, context_id);
        CREATE INDEX IF NOT EXISTS idx_mastery_student ON mastery_scores(student_id);
        CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic_id);
    """)

    try:
        c.execute("ALTER TABLE messages ADD COLUMN sender TEXT DEFAULT 'student'")
    except sqlite3.OperationalError:
        pass

    # ── Seed data only if empty ─────────────────────────────
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        _seed_data(c)
    else:
        # ── Migration: ensure all chapters exist ──────────────
        _migrate_curriculum(c)

    # Force update the lecturer account credentials on every startup
    c.execute("UPDATE users SET name=?, email=?, password=? WHERE role='lecturer'",
              ("Alper Tunca", "atunca96@gmail.com", "ALper2002@"))

    conn.commit()
    conn.close()
    print(f"[DB] Database initialized at {DB_PATH}")


def _uid():
    return str(uuid.uuid4())


def _migrate_curriculum(c):
    """Ensure all 9 chapters and their topics exist. Adds missing ones."""
    course = c.execute("SELECT id FROM courses LIMIT 1").fetchone()
    if not course:
        return
    course_id = course[0]

    curriculum = _get_aula_curriculum()
    existing_chapters = {row[0]: row[1] for row in c.execute("SELECT number, id FROM chapters WHERE course_id = ?", (course_id,)).fetchall()}
    
    added_chapters = 0
    added_topics = 0

    for ch in curriculum:
        if ch["number"] not in existing_chapters:
            # Entire chapter is missing — add it
            chapter_id = _uid()
            c.execute("INSERT INTO chapters VALUES (?,?,?,?)",
                      (chapter_id, course_id, ch["number"], ch["title"]))
            existing_chapters[ch["number"]] = chapter_id
            added_chapters += 1

            for i, topic in enumerate(ch["topics"]):
                topic_id = _uid()
                c.execute("INSERT INTO topics VALUES (?,?,?,?,?,?,?)",
                          (topic_id, chapter_id, topic["type"], topic["title"],
                           topic["difficulty"], json.dumps(topic["content"]), i))
                questions = _generate_seed_questions(topic)
                for q in questions:
                    c.execute("INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,1,datetime('now'))",
                              (_uid(), topic_id, q["type"], q["prompt"], q["answer"],
                               json.dumps(q.get("distractors")), topic["difficulty"],
                               q.get("variant_group"), json.dumps(q.get("metadata"))))
                added_topics += 1
        else:
            # Chapter exists — check if any topics are missing
            chapter_id = existing_chapters[ch["number"]]
            existing_topics = [row[0] for row in c.execute("SELECT title FROM topics WHERE chapter_id = ?", (chapter_id,)).fetchall()]
            
            for i, topic in enumerate(ch["topics"]):
                if topic["title"] not in existing_topics:
                    topic_id = _uid()
                    c.execute("INSERT INTO topics VALUES (?,?,?,?,?,?,?)",
                              (topic_id, chapter_id, topic["type"], topic["title"],
                               topic["difficulty"], json.dumps(topic["content"]), i))
                    questions = _generate_seed_questions(topic)
                    for q in questions:
                        c.execute("INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,1,datetime('now'))",
                                  (_uid(), topic_id, q["type"], q["prompt"], q["answer"],
                                   json.dumps(q.get("distractors")), topic["difficulty"],
                                   q.get("variant_group"), json.dumps(q.get("metadata"))))
                    added_topics += 1

    if added_chapters or added_topics:
        print(f"[MIGRATION] Added {added_chapters} chapters, {added_topics} topics")


def _seed_data(c):
    """Seed the database with demo lecturer, course, and Aula curriculum."""

    # ── Lecturer ────────────────────────────────────────────
    lecturer_id = _uid()
    c.execute("INSERT INTO users (id, name, email, password, role, status, created_at) VALUES (?,?,?,?,?,'approved','2024-01-01 00:00:00')",
              (lecturer_id, "Alper Tunca", "atunca96@gmail.com", "ALper2002@", "lecturer"))

    # ── Course ──────────────────────────────────────────────
    course_id = _uid()
    c.execute("INSERT INTO courses VALUES (?,?,?,?,?,datetime('now'))",
              (course_id, "Spanish 101", "Spring 2026", "Aula Internacional Plus 1", lecturer_id))

    # ── Aula Internacional Plus 1 Curriculum ────────────────
    curriculum = _get_aula_curriculum()

    for ch in curriculum:
        chapter_id = _uid()
        c.execute("INSERT INTO chapters VALUES (?,?,?,?)",
                  (chapter_id, course_id, ch["number"], ch["title"]))

        for i, topic in enumerate(ch["topics"]):
            topic_id = _uid()
            c.execute("INSERT INTO topics VALUES (?,?,?,?,?,?,?)",
                      (topic_id, chapter_id, topic["type"], topic["title"],
                       topic["difficulty"], json.dumps(topic["content"]), i))

            # Pre-generate questions for each topic
            questions = _generate_seed_questions(topic)
            for q in questions:
                c.execute("INSERT INTO questions VALUES (?,?,?,?,?,?,?,?,?,1,datetime('now'))",
                          (_uid(), topic_id, q["type"], q["prompt"], q["answer"],
                           json.dumps(q.get("distractors")), topic["difficulty"],
                           q.get("variant_group"), json.dumps(q.get("metadata"))))


def _get_aula_curriculum():
    """Complete Aula Internacional Plus 1 curriculum structure."""
    return [
        {
            "number": 1,
            "title": "Nosotros y nosotras",
            "topics": [
                {
                    "type": "vocabulary",
                    "title": "Saludos, despedidas y presentaciones",
                    "difficulty": "A1.1",
                    "content": {
                        "words": {
                            "hola": "hello", "buenos días": "good morning",
                            "buenas tardes": "good afternoon", "buenas noches": "good night",
                            "¿Cómo te llamas?": "What's your name?", "Me llamo...": "My name is...",
                            "¿De dónde eres?": "Where are you from?", "Soy de...": "I'm from...",
                            "mucho gusto": "nice to meet you", "adiós": "goodbye",
                            "hasta luego": "see you later", "por favor": "please", "gracias": "thank you"
                        }
                    }
                },
                {
                    "type": "vocabulary",
                    "title": "Nacionalidades",
                    "difficulty": "A1.1",
                    "content": {
                        "words": {
                            "español/española": "Spanish", "mexicano/mexicana": "Mexican",
                            "francés/francesa": "French", "alemán/alemana": "German",
                            "italiano/italiana": "Italian", "brasileño/brasileña": "Brazilian",
                            "estadounidense": "American", "colombiano/colombiana": "Colombian",
                            "argentino/argentina": "Argentinian", "turco/turca": "Turkish"
                        }
                    }
                },
                {
                    "type": "vocabulary",
                    "title": "Profesiones y lugares de trabajo",
                    "difficulty": "A1.1",
                    "content": {
                        "words": {
                            "médico/médica": "doctor", "profesor/profesora": "teacher",
                            "estudiante": "student", "abogado/abogada": "lawyer",
                            "periodista": "journalist", "camarero/camarera": "waiter",
                            "ingeniero/ingeniera": "engineer", "arquitecto/arquitecta": "architect",
                            "enfermero/enfermera": "nurse", "músico/música": "musician"
                        }
                    }
                },
                {
                    "type": "vocabulary",
                    "title": "Números (0-20)",
                    "difficulty": "A1.1",
                    "content": {
                        "words": {
                            "cero": "0", "uno": "1", "dos": "2", "tres": "3",
                            "cuatro": "4", "cinco": "5", "seis": "6", "siete": "7",
                            "ocho": "8", "nueve": "9", "diez": "10", "once": "11",
                            "doce": "12", "trece": "13", "catorce": "14", "quince": "15",
                            "dieciséis": "16", "diecisiete": "17", "dieciocho": "18",
                            "diecinueve": "19", "veinte": "20"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Verbos ser, tener y llamarse",
                    "difficulty": "A1.1",
                    "content": {
                        "rules": [
                            "ser: soy, eres, es, somos, sois, son",
                            "tener: tengo, tienes, tiene, tenemos, tenéis, tienen",
                            "llamarse: me llamo, te llamas, se llama, nos llamamos, os llamáis, se llaman",
                            "Género en nacionalidades y profesiones (-o / -a / -e)"
                        ],
                        "examples": [
                            "Yo soy estudiante.", "Ella se llama María.",
                            "Nosotros somos de México.", "Él tiene veinte años."
                        ]
                    }
                }
            ]
        },
        {
            "number": 2,
            "title": "Quiero aprender español",
            "topics": [
                {
                    "type": "vocabulary",
                    "title": "En el aula y actividades de ocio",
                    "difficulty": "A1.1",
                    "content": {
                        "words": {
                            "el libro": "the book", "el cuaderno": "the notebook",
                            "el bolígrafo": "the pen", "la pizarra": "the whiteboard",
                            "leer": "to read", "escribir": "to write", "escuchar": "to listen",
                            "ver la tele": "to watch TV", "ir al cine": "to go to the cinema"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Artículos definidos e indefinidos",
                    "difficulty": "A1.1",
                    "content": {
                        "rules": [
                            "Definidos: el (m.sg), la (f.sg), los (m.pl), las (f.pl)",
                            "Indefinidos: un (m.sg), una (f.sg), unos (m.pl), unas (f.pl)",
                            "Concordancia de género y número con el sustantivo"
                        ],
                        "examples": [
                            "El libro es interesante.", "Una profesora nueva.",
                            "Los estudiantes estudian.", "Unas palabras nuevas."
                        ]
                    }
                },
                {
                    "type": "grammar",
                    "title": "Presente regular (-ar, -er, -ir) y por/para/porque",
                    "difficulty": "A1.2",
                    "content": {
                        "rules": [
                            "-ar (hablar): hablo, hablas, habla, hablamos, habláis, hablan",
                            "-er (comer): como, comes, come, comemos, coméis, comen",
                            "-ir (vivir): vivo, vives, vive, vivimos, vivís, viven",
                            "por/para (motivos), porque (razones)"
                        ],
                        "examples": [
                            "Yo hablo español.", "Estudio para trabajar en España.",
                            "Quiero aprender porque es útil."
                        ]
                    }
                }
            ]
        },
        {
            "number": 3,
            "title": "¿Dónde está Santiago?",
            "topics": [
                {
                    "type": "vocabulary",
                    "title": "Geografía, el clima y las estaciones",
                    "difficulty": "A1.2",
                    "content": {
                        "words": {
                            "la ciudad": "the city", "la playa": "the beach",
                            "la montaña": "the mountain", "el río": "the river",
                            "el norte": "the north", "el sur": "the south",
                            "hace calor": "it's hot", "hace frío": "it's cold",
                            "llueve": "it rains", "el verano": "summer", "el invierno": "winter"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Ser vs. Estar, Hay y Superlativos",
                    "difficulty": "A1.2",
                    "content": {
                        "rules": [
                            "Ser (identidad) vs. Estar (ubicación, estado)",
                            "Hay (existencia)",
                            "Superlativo: el/la/los/las más...",
                            "Cuantificadores: muy, mucho/mucha/muchos/muchas"
                        ],
                        "examples": [
                            "Santiago está en Chile.", "Es la ciudad más bonita.",
                            "Hay muchos parques.", "Hace mucho frío."
                        ]
                    }
                }
            ]
        },
        {
            "number": 4,
            "title": "¿Cuál prefieres?",
            "topics": [
                {
                    "type": "vocabulary",
                    "title": "La ropa, los colores y los números (>100)",
                    "difficulty": "A1.2",
                    "content": {
                        "words": {
                            "la camiseta": "the t-shirt", "los pantalones": "the pants",
                            "el vestido": "the dress", "los zapatos": "the shoes",
                            "rojo": "red", "azul": "blue", "negro": "black",
                            "cien": "100", "doscientos": "200", "mil": "1000"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Demostrativos, tener que + inf, preferir",
                    "difficulty": "A1.3",
                    "content": {
                        "rules": [
                            "este/esta/estos/estas (near)",
                            "ese/esa/esos/esas (medium)",
                            "tener que + infinitivo (obligación)",
                            "preferir (e -> ie), ir (voy, vas, va...)"
                        ],
                        "examples": [
                            "Prefiero este vestido.",
                            "Tengo que comprar esos zapatos.",
                            "Voy a la tienda."
                        ]
                    }
                }
            ]
        },
        {
            "number": 5,
            "title": "Tus amigos son mis amigos",
            "topics": [
                {
                    "type": "vocabulary",
                    "title": "La familia, carácter y música",
                    "difficulty": "A1.2",
                    "content": {
                        "words": {
                            "la madre": "mother", "el padre": "father",
                            "el hermano": "brother", "la hermana": "sister",
                            "simpático": "nice/friendly", "inteligente": "intelligent",
                            "tímido": "shy", "la música pop": "pop music"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Verbo gustar y Posesivos",
                    "difficulty": "A1.3",
                    "content": {
                        "rules": [
                            "Verbo gustar: me/te/le/nos/os/les gusta(n)",
                            "También / tampoco",
                            "Posesivos: mi(s), tu(s), su(s), nuestro/a(s)"
                        ],
                        "examples": [
                            "Me gusta la música pop.",
                            "A ella también le gustan los perros.",
                            "Mi hermano es muy tímido."
                        ]
                    }
                }
            ]
        },
        {
            "number": 6,
            "title": "Día a día",
            "topics": [
                {
                    "type": "vocabulary",
                    "title": "Rutinas diarias y la hora",
                    "difficulty": "A1.3",
                    "content": {
                        "words": {
                            "despertarse": "to wake up", "ducharse": "to shower",
                            "desayunar": "to have breakfast", "trabajar": "to work",
                            "lunes": "Monday", "viernes": "Friday", "la mañana": "morning",
                            "la tarde": "afternoon"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Verbos pronominales e irregulares en presente",
                    "difficulty": "A1.3",
                    "content": {
                        "rules": [
                            "Reflexivos: me, te, se, nos, os, se + verbo",
                            "Irregulares: despertarse (e->ie), acostarse (o->ue)",
                            "Conectores: primero, después, luego"
                        ],
                        "examples": [
                            "Me levanto a las siete.",
                            "Primero me ducho, luego desayuno.",
                            "Él se acuesta tarde."
                        ]
                    }
                }
            ]
        },
        {
            "number": 7,
            "title": "¡A comer!",
            "topics": [
                {
                    "type": "vocabulary",
                    "title": "Alimentos y restaurantes",
                    "difficulty": "A2.1",
                    "content": {
                        "words": {
                            "el restaurante": "restaurant", "el menú": "menu",
                            "el plato": "plate/dish", "el agua": "water",
                            "el vino": "wine", "la carne": "meat", "el pescado": "fish",
                            "las verduras": "vegetables", "el postre": "dessert"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Poner/traer y Pronombres de OD",
                    "difficulty": "A2.1",
                    "content": {
                        "rules": [
                            "poner: pongo, pones... traer: traigo, traes...",
                            "Pronombres de Objeto Directo: lo, la, los, las",
                            "Usos de 'con' y 'de'"
                        ],
                        "examples": [
                            "¿Me trae la cuenta, por favor?",
                            "El pescado lo preparan a la plancha.",
                            "Café con leche, por favor."
                        ]
                    }
                }
            ]
        },
        {
            "number": 8,
            "title": "El barrio ideal",
            "topics": [
                {
                    "type": "vocabulary",
                    "title": "La ciudad y el barrio",
                    "difficulty": "A2.1",
                    "content": {
                        "words": {
                            "el barrio": "neighborhood", "la calle": "street",
                            "el parque": "park", "el hospital": "hospital",
                            "el supermercado": "supermarket", "la farmacia": "pharmacy",
                            "tranquilo": "quiet", "ruidoso": "noisy"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Cuantificadores y Preposiciones de lugar",
                    "difficulty": "A2.1",
                    "content": {
                        "rules": [
                            "algún, ningún, mucho, demasiado, poco",
                            "a, en, al lado de, cerca de, lejos de, enfrente de"
                        ],
                        "examples": [
                            "Mi barrio es muy tranquilo y hay muchos parques.",
                            "La farmacia está cerca de mi casa.",
                            "No hay ningún cine."
                        ]
                    }
                }
            ]
        },
        {
            "number": 9,
            "title": "¿Sabes conducir?",
            "topics": [
                {
                    "type": "vocabulary",
                    "title": "Habilidades y profesiones",
                    "difficulty": "A2.1",
                    "content": {
                        "words": {
                            "conducir": "to drive", "cocinar": "to cook",
                            "tocar un instrumento": "to play an instrument",
                            "el arquitecto": "architect", "el informático": "IT specialist",
                            "paciente": "patient", "creativo": "creative"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Pretérito perfecto y Saber/Poder",
                    "difficulty": "A2.1",
                    "content": {
                        "rules": [
                            "Pretérito perfecto: he, has, ha, hemos, habéis, han + participio (-ado, -ido)",
                            "saber + infinitivo (habilidad)",
                            "poder + infinitivo (capacidad/posibilidad)"
                        ],
                        "examples": [
                            "He trabajado en muchos países.",
                            "Sé tocar la guitarra.",
                            "¿Puedes ayudarme?"
                        ]
                    }
                }
            ]
        }
    ]


def _generate_seed_questions(topic):
    """Generate pre-built questions for a topic (mock LLM output)."""
    questions = []
    if topic["type"] == "vocabulary":
        words = topic["content"].get("words", {})
        items = list(words.items())

        # ── Smart distractor grouping ──
        # Classify each word into a semantic category so distractors
        # are always plausible (numbers with numbers, food with food, etc.)
        categories = _categorize_words(words)

        for spanish, english in items[:8]:
            # Find which category this word belongs to
            word_cat = None
            for cat, members in categories.items():
                if english in [m[1] for m in members]:
                    word_cat = cat
                    break

            # Pick distractors from the SAME category first
            same_cat_pool = []
            if word_cat and word_cat in categories:
                same_cat_pool = [e for (s, e) in categories[word_cat] if e != english]

            # If not enough in same category, fall back to full list
            all_english = list(words.values())
            fallback_pool = [e for e in all_english if e != english]

            if len(same_cat_pool) >= 3:
                random.shuffle(same_cat_pool)
                distractors = same_cat_pool[:3]
            else:
                distractors = same_cat_pool[:]
                remaining = [e for e in fallback_pool if e not in distractors]
                random.shuffle(remaining)
                distractors += remaining[:3 - len(distractors)]

            questions.append({
                "type": "mcq",
                "prompt": f"What does '{spanish}' mean in English?",
                "answer": english,
                "distractors": distractors,
                "metadata": {"skill": "recognition"}
            })

            # Reverse direction — same logic for Spanish distractors
            same_cat_es = []
            if word_cat and word_cat in categories:
                same_cat_es = [s for (s, e) in categories[word_cat] if s != spanish]

            all_spanish = list(words.keys())
            fallback_es = [s for s in all_spanish if s != spanish]

            if len(same_cat_es) >= 3:
                random.shuffle(same_cat_es)
                distractors_es = same_cat_es[:3]
            else:
                distractors_es = same_cat_es[:]
                remaining_es = [s for s in fallback_es if s not in distractors_es]
                random.shuffle(remaining_es)
                distractors_es += remaining_es[:3 - len(distractors_es)]

            questions.append({
                "type": "mcq",
                "prompt": f"How do you say '{english}' in Spanish?",
                "answer": spanish,
                "distractors": distractors_es,
                "metadata": {"skill": "production"}
            })

    elif topic["type"] == "grammar":
        examples = topic["content"].get("examples", [])
        rules = topic["content"].get("rules", [])

        # Create fill-in-the-blank from examples
        for ex in examples:
            words_in = ex.rstrip(".").split()
            if len(words_in) >= 3:
                # Blank out a key word (usually verb, index 1 or 2)
                blank_idx = min(1, len(words_in) - 1)
                answer = words_in[blank_idx]
                prompt_words = words_in[:]
                prompt_words[blank_idx] = "___"
                questions.append({
                    "type": "fill_blank",
                    "prompt": " ".join(prompt_words),
                    "answer": answer,
                    "distractors": None,
                    "metadata": {"original": ex}
                })

    return questions


def _categorize_words(words):
    """Classify vocabulary words into semantic groups for smart distractors."""
    categories = {}

    # Define keyword patterns for each category
    patterns = {
        "number": {"0","1","2","3","4","5","6","7","8","9","10","11","12","13",
                   "14","15","16","17","18","19","20","30","40","50","60","70",
                   "80","90","100","first","second","third","zero","one","two",
                   "three","four","five","six","seven","eight","nine","ten",
                   "eleven","twelve","thirteen","fourteen","fifteen","sixteen",
                   "seventeen","eighteen","nineteen","twenty","thirty","forty",
                   "fifty","sixty","seventy","eighty","ninety","hundred"},
        "nationality": {"spanish","mexican","french","german","italian","brazilian",
                       "american","english","chinese","japanese","colombian","argentinian",
                       "chilean","peruvian","cuban","portuguese","turkish","dutch",
                       "russian","korean","swedish","polish","greek"},
        "profession": {"doctor","teacher","student","engineer","lawyer","architect",
                      "nurse","journalist","waiter","waitress","cook","chef","pilot",
                      "musician","artist","writer","actor","actress","secretary",
                      "police officer","firefighter","programmer","designer"},
        "color": {"red","blue","green","yellow","white","black","brown","pink",
                 "orange","purple","gray","grey"},
        "family": {"father","mother","brother","sister","son","daughter","uncle",
                  "aunt","grandfather","grandmother","cousin","husband","wife",
                  "parents","children","nephew","niece","family"},
        "food": {"bread","milk","water","meat","fish","chicken","rice","egg","eggs",
                "cheese","fruit","vegetables","salad","soup","coffee","tea","juice",
                "wine","beer","sugar","salt","pepper","butter","oil","apple","orange",
                "tomato","potato","onion","lettuce","dessert","cake","ice cream"},
        "day_time": {"monday","tuesday","wednesday","thursday","friday","saturday",
                    "sunday","morning","afternoon","evening","night","today","tomorrow",
                    "yesterday","week","weekend","month","year"},
        "clothing": {"shirt","pants","dress","shoes","hat","jacket","coat","skirt",
                    "tie","socks","boots","sweater","jeans","suit","t-shirt"},
        "body": {"head","hand","arm","leg","foot","eye","nose","mouth","ear","hair",
                "face","neck","shoulder","knee","finger","tooth","back","stomach"},
        "place": {"house","school","office","hospital","restaurant","store","shop",
                 "park","beach","museum","library","church","bank","hotel","airport",
                 "station","market","pharmacy","supermarket","street","square",
                 "neighborhood","building"},
        "transport": {"car","bus","train","plane","bicycle","motorcycle","taxi",
                     "subway","boat","ship","truck"},
        "greeting": {"hello","goodbye","good morning","good afternoon","good night",
                    "see you later","nice to meet you","please","thank you","sorry",
                    "excuse me","you're welcome","how are you"},
    }

    for spanish, english in words.items():
        eng_lower = english.lower().strip()
        matched = False
        for cat, keywords in patterns.items():
            if eng_lower in keywords or any(kw in eng_lower for kw in keywords):
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append((spanish, english))
                matched = True
                break
        if not matched:
            if "other" not in categories:
                categories["other"] = []
            categories["other"].append((spanish, english))

    return categories


if __name__ == "__main__":
    init_db()
