"""
Content Engine — Generates questions, activities, and assignments
aligned to Aula Internacional Plus 1 curriculum.
Mock LLM implementation for the prototype (swap-ready for real API).
"""

import random
import json
import uuid
from datetime import datetime


def _uid():
    return str(uuid.uuid4())


# ── Activity Templates ──────────────────────────────────────────

FILL_BLANK_TEMPLATES = {
    "ser_estar": [
        {"prompt": "Madrid ___ la capital de España.", "answer": "es", "hint": "identity → ser"},
        {"prompt": "Yo ___ estudiante de español.", "answer": "soy", "hint": "identity → ser"},
        {"prompt": "Mi hermana ___ muy contenta hoy.", "answer": "está", "hint": "temporary state → estar"},
        {"prompt": "Nosotros ___ en la clase.", "answer": "estamos", "hint": "location → estar"},
        {"prompt": "Ellos ___ de México.", "answer": "son", "hint": "origin → ser"},
        {"prompt": "Tú ___ cansado después de estudiar.", "answer": "estás", "hint": "temporary state → estar"},
        {"prompt": "La profesora ___ muy simpática.", "answer": "es", "hint": "permanent trait → ser"},
        {"prompt": "El libro ___ en la mesa.", "answer": "está", "hint": "location → estar"},
    ],
    "present_regular": [
        {"prompt": "Yo ___ (hablar) español todos los días.", "answer": "hablo", "hint": "-ar: -o, -as, -a, -amos, -áis, -an"},
        {"prompt": "Tú ___ (comer) en la cafetería.", "answer": "comes", "hint": "-er: -o, -es, -e, -emos, -éis, -en"},
        {"prompt": "Ella ___ (vivir) en Barcelona.", "answer": "vive", "hint": "-ir: -o, -es, -e, -imos, -ís, -en"},
        {"prompt": "Nosotros ___ (estudiar) mucho.", "answer": "estudiamos", "hint": "-ar nosotros: -amos"},
        {"prompt": "Ellos ___ (escribir) en el cuaderno.", "answer": "escriben", "hint": "-ir ellos: -en"},
        {"prompt": "Yo ___ (aprender) palabras nuevas.", "answer": "aprendo", "hint": "-er yo: -o"},
    ],
    "reflexive": [
        {"prompt": "Yo ___ (levantarse) a las siete.", "answer": "me levanto", "hint": "reflexive: me + verb"},
        {"prompt": "Ella ___ (ducharse) por la mañana.", "answer": "se ducha", "hint": "reflexive: se + verb"},
        {"prompt": "Nosotros ___ (acostarse) a las once.", "answer": "nos acostamos", "hint": "reflexive: nos + verb"},
        {"prompt": "Tú ___ (vestirse) rápidamente.", "answer": "te vistes", "hint": "reflexive: te + verb (e→i)"},
    ],
    "possessives": [
        {"prompt": "___ hermano se llama Carlos. (yo)", "answer": "Mi", "hint": "mi/mis for yo"},
        {"prompt": "___ padres son muy amables. (tú)", "answer": "Tus", "hint": "tu/tus for tú"},
        {"prompt": "___ casa es grande. (él)", "answer": "Su", "hint": "su/sus for él/ella"},
        {"prompt": "___ profesora es española. (nosotros)", "answer": "Nuestra", "hint": "nuestro/a/os/as for nosotros"},
    ],
    "articles": [
        {"prompt": "___ libro es interesante. (definido, m.sg.)", "answer": "El", "hint": "el (m.sg), la (f.sg)"},
        {"prompt": "Necesito ___ cuaderno. (indefinido, m.sg.)", "answer": "un", "hint": "un (m.sg), una (f.sg)"},
        {"prompt": "___ estudiantes estudian mucho. (definido, m.pl.)", "answer": "Los", "hint": "los (m.pl), las (f.pl)"},
        {"prompt": "Hay ___ palabras nuevas. (indefinido, f.pl.)", "answer": "unas", "hint": "unos (m.pl), unas (f.pl)"},
    ],
    "comparatives": [
        {"prompt": "Esta camiseta es ___ bonita que esa. (more)", "answer": "más", "hint": "más... que = more... than"},
        {"prompt": "Estos zapatos son ___ caros que esos. (less)", "answer": "menos", "hint": "menos... que = less... than"},
        {"prompt": "Mi hermano es ___ alto como mi padre. (as)", "answer": "tan", "hint": "tan... como = as... as"},
    ],
}

DIALOGUE_TEMPLATES = [
    {
        "title": "En la cafetería",
        "lines": [
            {"order": 1, "speaker": "A", "text": "¡Hola! ¿Cómo te llamas?"},
            {"order": 2, "speaker": "B", "text": "Me llamo María. ¿Y tú?"},
            {"order": 3, "speaker": "A", "text": "Soy Carlos. ¿De dónde eres?"},
            {"order": 4, "speaker": "B", "text": "Soy de Colombia. ¿Y tú?"},
            {"order": 5, "speaker": "A", "text": "Soy de España. ¡Mucho gusto!"},
            {"order": 6, "speaker": "B", "text": "¡Igualmente! Hasta luego."},
        ]
    },
    {
        "title": "Describiendo a la familia",
        "lines": [
            {"order": 1, "speaker": "A", "text": "¿Tienes hermanos?"},
            {"order": 2, "speaker": "B", "text": "Sí, tengo una hermana y un hermano."},
            {"order": 3, "speaker": "A", "text": "¿Cómo es tu hermana?"},
            {"order": 4, "speaker": "B", "text": "Es alta y tiene pelo largo."},
            {"order": 5, "speaker": "A", "text": "¿Y tu hermano?"},
            {"order": 6, "speaker": "B", "text": "Es bajo y muy simpático."},
        ]
    },
    {
        "title": "La rutina diaria",
        "lines": [
            {"order": 1, "speaker": "A", "text": "¿A qué hora te levantas?"},
            {"order": 2, "speaker": "B", "text": "Me levanto a las siete."},
            {"order": 3, "speaker": "A", "text": "¿Qué haces después?"},
            {"order": 4, "speaker": "B", "text": "Me ducho y desayuno."},
            {"order": 5, "speaker": "A", "text": "¿A qué hora vas a clase?"},
            {"order": 6, "speaker": "B", "text": "Voy a clase a las nueve."},
        ]
    }
]


def generate_activity(topic_data, difficulty="standard", count=5):
    """
    Generate an activity set for a given topic.
    Returns a list of question dicts ready for the frontend.
    """
    topic_type = topic_data.get("type", "vocabulary")
    content = json.loads(topic_data["content_json"]) if isinstance(topic_data["content_json"], str) else topic_data["content_json"]

    if topic_type == "vocabulary":
        return _generate_vocab_activity(content, difficulty, count)
    elif topic_type == "grammar":
        return _generate_grammar_activity(topic_data["title"], content, difficulty, count)
    return []


def _generate_vocab_activity(content, difficulty, count):
    """Generate vocabulary MCQ activities."""
    words = content.get("words", {})
    items = list(words.items())
    random.shuffle(items)

    activities = []
    for spanish, english in items[:count]:
        is_reverse = random.choice([True, False])
        
        if not is_reverse:
            all_english = list(words.values())
            distractors = [e for e in all_english if e != english]
            random.shuffle(distractors)
            distractors = distractors[:3]

            options = distractors + [english]
            random.shuffle(options)

            activities.append({
                "id": _uid(),
                "type": "mcq",
                "prompt": f"What does '{spanish}' mean?",
                "options": options,
                "answer": english,
                "difficulty": difficulty,
            })
        else:
            all_spanish = list(words.keys())
            distractors_es = [s for s in all_spanish if s != spanish]
            random.shuffle(distractors_es)
            distractors_es = distractors_es[:3]

            options_es = distractors_es + [spanish]
            random.shuffle(options_es)

            activities.append({
                "id": _uid(),
                "type": "mcq",
                "prompt": f"How do you say '{english}' in Spanish?",
                "options": options_es,
                "answer": spanish,
                "difficulty": difficulty,
            })

    return activities[:count]


def _generate_grammar_activity(title, content, difficulty, count):
    """Generate grammar fill-in-the-blank activities."""
    title_lower = title.lower()

    # Match to template bank
    template_key = None
    if "ser" in title_lower and "estar" in title_lower:
        template_key = "ser_estar"
    elif "presente" in title_lower or "regular" in title_lower:
        template_key = "present_regular"
    elif "reflexiv" in title_lower:
        template_key = "reflexive"
    elif "posesiv" in title_lower:
        template_key = "possessives"
    elif "artículo" in title_lower:
        template_key = "articles"
    elif "comparativ" in title_lower or "demostrativ" in title_lower:
        template_key = "comparatives"

    if template_key and template_key in FILL_BLANK_TEMPLATES:
        templates = FILL_BLANK_TEMPLATES[template_key]
        random.shuffle(templates)
        activities = []
        for t in templates[:count]:
            activities.append({
                "id": _uid(),
                "type": "fill_blank",
                "prompt": t["prompt"],
                "answer": t["answer"],
                "hint": t.get("hint", ""),
                "difficulty": difficulty,
            })
        return activities

    # Fallback: generate from examples
    examples = content.get("examples", [])
    activities = []
    for ex in examples[:count]:
        words = ex.rstrip(".").split()
        if len(words) >= 3:
            blank_idx = 1
            answer = words[blank_idx]
            words[blank_idx] = "___"
            activities.append({
                "id": _uid(),
                "type": "fill_blank",
                "prompt": " ".join(words),
                "answer": answer,
                "hint": "",
                "difficulty": difficulty,
            })
    return activities


def generate_quiz(topic_ids, db_conn, student_mastery=None, count=10):
    """
    Generate a quiz pulling questions from given topics.
    If student_mastery is provided, adjusts difficulty.
    """
    c = db_conn.cursor()
    questions = []

    for topic_id in topic_ids:
        rows = c.execute(
            "SELECT * FROM questions WHERE topic_id = ? AND approved = 1 ORDER BY RANDOM() LIMIT ?",
            (topic_id, max(3, count // len(topic_ids)))
        ).fetchall()

        for row in rows:
            q = dict(row)
            if q["distractors"]:
                q["distractors"] = json.loads(q["distractors"])
            questions.append(q)

    random.shuffle(questions)
    return questions[:count]


def generate_dialogue_activity():
    """Generate a dialogue ordering activity."""
    dialogue = random.choice(DIALOGUE_TEMPLATES)
    lines = dialogue["lines"][:]
    correct_order = [l["text"] for l in lines]
    random.shuffle(lines)

    return {
        "id": _uid(),
        "type": "dialogue_order",
        "title": dialogue["title"],
        "scrambled_lines": [l["text"] for l in lines],
        "correct_order": correct_order,
        "speakers": {l["text"]: l["speaker"] for l in dialogue["lines"]},
    }


def grade_response(question_type, student_answer, correct_answer):
    """
    Grade a student response. Returns score (0-1) and feedback.
    """
    student_clean = student_answer.strip().lower()
    correct_clean = correct_answer.strip().lower()

    if question_type in ("mcq", "fill_blank"):
        if student_clean == correct_clean:
            return 1.0, "¡Correcto! ✓"

        # Partial credit for accent errors
        distance = _levenshtein(student_clean, correct_clean)
        if distance <= 1 and len(correct_clean) > 3:
            return 0.8, f"Almost! The correct answer is '{correct_answer}'. Check the accents."
        elif distance <= 2 and len(correct_clean) > 5:
            return 0.5, f"Close, but the correct answer is '{correct_answer}'."
        else:
            return 0.0, f"Incorrect. The correct answer is '{correct_answer}'."

    elif question_type == "translation":
        # Simplified scoring for prototype
        if student_clean == correct_clean:
            return 1.0, "¡Perfecto!"
        distance = _levenshtein(student_clean, correct_clean)
        ratio = 1 - (distance / max(len(correct_clean), 1))
        score = max(0, min(1, ratio))
        if score >= 0.8:
            return score, f"Very good! Minor differences from: '{correct_answer}'"
        elif score >= 0.5:
            return score, f"Partial credit. Expected: '{correct_answer}'"
        else:
            return score, f"Needs work. Expected: '{correct_answer}'"

    return 0.0, "Unable to grade."


def _levenshtein(s1, s2):
    """Compute Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]
