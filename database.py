"""
Database module — SQLite setup, schema creation, and seed data for
Aula Internacional Plus 1 curriculum.
"""

import sqlite3
import json
import uuid
import os
import math
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
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS courses (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            semester TEXT NOT NULL,
            textbook TEXT,
            lecturer_id TEXT REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS enrollments (
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

    # ── Seed data only if empty ─────────────────────────────
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        _seed_data(c)

    # Force update the lecturer account credentials on every startup
    c.execute("UPDATE users SET name=?, email=?, password=? WHERE role='lecturer'",
              ("Alper Tunca", "atunca96@gmail.com", "ALper2002@"))

    conn.commit()
    conn.close()
    print(f"[DB] Database initialized at {DB_PATH}")


def _uid():
    return str(uuid.uuid4())


def _seed_data(c):
    """Seed the database with demo lecturer, course, and Aula curriculum."""

    # ── Lecturer ────────────────────────────────────────────
    lecturer_id = _uid()
    c.execute("INSERT INTO users VALUES (?,?,?,?,?,'2024-01-01 00:00:00')",
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
            "title": "Nosotros",
            "topics": [
                {
                    "type": "vocabulary",
                    "title": "Saludos y presentaciones",
                    "difficulty": "A1.1",
                    "content": {
                        "words": {
                            "hola": "hello", "buenos días": "good morning",
                            "buenas tardes": "good afternoon", "buenas noches": "good night",
                            "¿Cómo te llamas?": "What's your name?",
                            "Me llamo...": "My name is...",
                            "¿De dónde eres?": "Where are you from?",
                            "Soy de...": "I'm from...", "mucho gusto": "nice to meet you",
                            "adiós": "goodbye", "hasta luego": "see you later",
                            "por favor": "please", "gracias": "thank you"
                        }
                    }
                },
                {
                    "type": "vocabulary",
                    "title": "Nacionalidades y países",
                    "difficulty": "A1.1",
                    "content": {
                        "words": {
                            "español/española": "Spanish", "mexicano/mexicana": "Mexican",
                            "estadounidense": "American", "francés/francesa": "French",
                            "alemán/alemana": "German", "italiano/italiana": "Italian",
                            "brasileño/brasileña": "Brazilian", "chino/china": "Chinese",
                            "japonés/japonesa": "Japanese", "inglés/inglesa": "English/British",
                            "argentino/argentina": "Argentine", "colombiano/colombiana": "Colombian"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Verbos ser y llamarse (presente)",
                    "difficulty": "A1.1",
                    "content": {
                        "rules": [
                            "ser: soy, eres, es, somos, sois, son",
                            "llamarse: me llamo, te llamas, se llama, nos llamamos, os llamáis, se llaman"
                        ],
                        "examples": [
                            "Yo soy estudiante.", "Ella se llama María.",
                            "Nosotros somos de México.", "¿Tú eres español?"
                        ]
                    }
                },
                {
                    "type": "vocabulary",
                    "title": "Números del 0 al 20",
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
                }
            ]
        },
        {
            "number": 2,
            "title": "Quiero aprender español",
            "topics": [
                {
                    "type": "vocabulary",
                    "title": "En el aula",
                    "difficulty": "A1.1",
                    "content": {
                        "words": {
                            "el libro": "the book", "el cuaderno": "the notebook",
                            "el bolígrafo": "the pen", "el lápiz": "the pencil",
                            "la pizarra": "the whiteboard", "el profesor": "the teacher (m)",
                            "la profesora": "the teacher (f)", "el estudiante": "the student (m)",
                            "la estudiante": "the student (f)", "la clase": "the class",
                            "el ejercicio": "the exercise", "la palabra": "the word"
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
                    "type": "vocabulary",
                    "title": "Días de la semana y meses",
                    "difficulty": "A1.1",
                    "content": {
                        "words": {
                            "lunes": "Monday", "martes": "Tuesday", "miércoles": "Wednesday",
                            "jueves": "Thursday", "viernes": "Friday", "sábado": "Saturday",
                            "domingo": "Sunday", "enero": "January", "febrero": "February",
                            "marzo": "March", "abril": "April", "mayo": "May"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Presente regular (-ar, -er, -ir)",
                    "difficulty": "A1.2",
                    "content": {
                        "rules": [
                            "-ar (hablar): hablo, hablas, habla, hablamos, habláis, hablan",
                            "-er (comer): como, comes, come, comemos, coméis, comen",
                            "-ir (vivir): vivo, vives, vive, vivimos, vivís, viven"
                        ],
                        "examples": [
                            "Yo hablo español.", "Tú comes en casa.",
                            "Ella vive en Madrid.", "Nosotros estudiamos mucho."
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
                    "title": "Geografía y lugares",
                    "difficulty": "A1.2",
                    "content": {
                        "words": {
                            "la ciudad": "the city", "el país": "the country",
                            "la playa": "the beach", "la montaña": "the mountain",
                            "el río": "the river", "el lago": "the lake",
                            "la isla": "the island", "el norte": "the north",
                            "el sur": "the south", "el este": "the east",
                            "el oeste": "the west", "el centro": "the center"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Ser vs. Estar",
                    "difficulty": "A1.2",
                    "content": {
                        "rules": [
                            "Ser: identidad, origen, profesión, características permanentes",
                            "Estar: ubicación, estado temporal, emociones temporales",
                            "estar: estoy, estás, está, estamos, estáis, están"
                        ],
                        "examples": [
                            "Madrid es la capital de España. (identity)",
                            "Santiago está en Chile. (location)",
                            "Ella es alta. (permanent trait)",
                            "Yo estoy cansado. (temporary state)"
                        ]
                    }
                },
                {
                    "type": "vocabulary",
                    "title": "El clima y el tiempo",
                    "difficulty": "A1.2",
                    "content": {
                        "words": {
                            "hace calor": "it's hot", "hace frío": "it's cold",
                            "hace sol": "it's sunny", "llueve": "it rains",
                            "nieva": "it snows", "hace viento": "it's windy",
                            "nublado": "cloudy", "la temperatura": "the temperature",
                            "el verano": "summer", "el invierno": "winter",
                            "la primavera": "spring", "el otoño": "autumn"
                        }
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
                    "title": "La ropa y los colores",
                    "difficulty": "A1.2",
                    "content": {
                        "words": {
                            "la camiseta": "the t-shirt", "los pantalones": "the pants",
                            "el vestido": "the dress", "los zapatos": "the shoes",
                            "la falda": "the skirt", "la chaqueta": "the jacket",
                            "rojo": "red", "azul": "blue", "verde": "green",
                            "negro": "black", "blanco": "white", "amarillo": "yellow"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Demostrativos y comparativos",
                    "difficulty": "A1.3",
                    "content": {
                        "rules": [
                            "este/esta/estos/estas (this/these - near)",
                            "ese/esa/esos/esas (that/those - medium)",
                            "más... que, menos... que, tan... como"
                        ],
                        "examples": [
                            "Esta camiseta es más bonita que esa.",
                            "Estos zapatos son menos caros que esos.",
                            "Este vestido es tan elegante como ese."
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
                    "title": "La familia",
                    "difficulty": "A1.2",
                    "content": {
                        "words": {
                            "la madre": "mother", "el padre": "father",
                            "el hermano": "brother", "la hermana": "sister",
                            "el abuelo": "grandfather", "la abuela": "grandmother",
                            "el tío": "uncle", "la tía": "aunt",
                            "el primo": "cousin (m)", "la prima": "cousin (f)",
                            "el hijo": "son", "la hija": "daughter"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Posesivos y descripción de personas",
                    "difficulty": "A1.3",
                    "content": {
                        "rules": [
                            "mi/mis, tu/tus, su/sus, nuestro-a/nuestros-as",
                            "tener: tengo, tienes, tiene, tenemos, tenéis, tienen",
                            "Describir: ser + adjetivo / tener + sustantivo"
                        ],
                        "examples": [
                            "Mi hermana tiene pelo largo.",
                            "Nuestros abuelos son muy simpáticos.",
                            "Su primo es alto y tiene ojos verdes."
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
                    "title": "Rutinas diarias",
                    "difficulty": "A1.3",
                    "content": {
                        "words": {
                            "despertarse": "to wake up", "levantarse": "to get up",
                            "ducharse": "to shower", "vestirse": "to get dressed",
                            "desayunar": "to have breakfast", "almorzar": "to have lunch",
                            "cenar": "to have dinner", "acostarse": "to go to bed",
                            "trabajar": "to work", "estudiar": "to study",
                            "hacer ejercicio": "to exercise", "dormir": "to sleep"
                        }
                    }
                },
                {
                    "type": "grammar",
                    "title": "Verbos reflexivos y la hora",
                    "difficulty": "A1.3",
                    "content": {
                        "rules": [
                            "Reflexivos: me, te, se, nos, os, se + verbo",
                            "La hora: Es la una / Son las dos, tres...",
                            "Frecuencia: siempre, normalmente, a veces, nunca"
                        ],
                        "examples": [
                            "Me levanto a las siete de la mañana.",
                            "Ella se ducha antes de desayunar.",
                            "Nosotros nos acostamos a las once."
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
        for spanish, english in items[:8]:
            all_english = list(words.values())
            distractors = [e for e in all_english if e != english][:3]
            questions.append({
                "type": "mcq",
                "prompt": f"What does '{spanish}' mean in English?",
                "answer": english,
                "distractors": distractors,
                "metadata": {"skill": "recognition"}
            })
            # Reverse direction
            all_spanish = list(words.keys())
            distractors_es = [s for s in all_spanish if s != spanish][:3]
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


if __name__ == "__main__":
    init_db()
