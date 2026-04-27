"""
Content Engine — Handles generation of quizzes and assignments via OpenRouter.
"""

import random
import json
import uuid
from datetime import datetime
from services.ai_engine import is_ai_available, ai_generate_activity, ai_generate_questions, ai_grade_open_response


def _uid():
    return str(uuid.uuid4())


# ── Activity Templates ──────────────────────────────────────────

FILL_BLANK_TEMPLATES = {
    "Spanish": {
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
            {"prompt": "Tú ___ (comer) en la cafetería.", "answer": "comes", "hint": "-er: -o, -es, -e, -emos, -áis, -en"},
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


def generate_activity(topic_data, difficulty="standard", count=5, language="English"):
    """
    Generate an activity set for a given topic.
    Uses AI when available, falls back to mock templates.
    Returns a list of question dicts ready for the frontend.
    """
    topic_type = topic_data.get("type", "vocabulary")
    content = json.loads(topic_data["content"]) if isinstance(topic_data.get("content"), str) else topic_data.get("content", {})

    # Try AI-powered generation first
    if is_ai_available():
        try:
            ai_activities = ai_generate_activity(topic_data["title"], topic_type, content, language=language, count=count)
            if ai_activities:
                print(f"[AI] Generated {len(ai_activities)} activities for '{topic_data['title']}' ({language})")
                result = []
                for a in ai_activities:
                    activity = {
                        "id": _uid(),
                        "type": a.get("type", "mcq"),
                        "prompt": a.get("prompt", ""),
                        "answer": a.get("answer", ""),
                        "difficulty": difficulty,
                    }
                    if a.get("type") == "mcq":
                        activity["options"] = a.get("options", [])
                    if a.get("hint"):
                        activity["hint"] = a["hint"]
                    result.append(activity)
                return result
        except Exception as e:
            print(f"[AI] Fallback to mock: {e}")

    # Fallback to mock templates (Only for vocabulary, as grammar mock is fill-blank)
    if topic_type == "vocabulary":
        return _generate_vocab_activity(content, difficulty, count, language)
    elif topic_type == "grammar":
        return _generate_grammar_activity(topic_data["title"], content, difficulty, count, language)
    return []


def _generate_vocab_activity(content, difficulty, count, language):
    """Generate vocabulary MCQ activities with smart distractors."""
    words = content.get("words", {})
    if not words: return []
    items = list(words.items()) # List of (target_word, source_word)
    random.shuffle(items)

    # Import semantic categorizer for smart distractors
    from database import _categorize_words
    categories = _categorize_words(words)

    activities = []
    for target_word, source_word in items[:count]:
        is_reverse = random.choice([True, False])

        # Find this word's category
        word_cat = None
        for cat, members in categories.items():
            if source_word in [m[1] for m in members]:
                word_cat = cat
                break

        if not is_reverse:
            # Source distractors
            same_cat = [e for (s, e) in categories.get(word_cat, []) if e != source_word] if word_cat else []
            all_pool = [e for e in words.values() if e != source_word]
            if len(same_cat) >= 3:
                random.shuffle(same_cat)
                distractors = same_cat[:3]
            else:
                distractors = same_cat[:]
                remaining = [e for e in all_pool if e not in distractors]
                random.shuffle(remaining)
                distractors += remaining[:3 - len(distractors)]

            options = distractors + [source_word]
            random.shuffle(options)

            activities.append({
                "id": _uid(),
                "type": "mcq",
                "prompt": f"What does '{target_word}' mean?" if language == "English" else f"What does the {language} word '{target_word}' mean?",
                "options": options,
                "answer": source_word,
                "difficulty": difficulty,
            })
        else:
            # Target distractors
            same_cat_t = [s for (s, e) in categories.get(word_cat, []) if s != target_word] if word_cat else []
            all_pool_t = [s for s in words.keys() if s != target_word]
            if len(same_cat_t) >= 3:
                random.shuffle(same_cat_t)
                distractors_t = same_cat_t[:3]
            else:
                distractors_t = same_cat_t[:]
                remaining_t = [s for s in all_pool_t if s not in distractors_t]
                random.shuffle(remaining_t)
                distractors_t += remaining_t[:3 - len(distractors_t)]

            options_t = distractors_t + [target_word]
            random.shuffle(options_t)

            activities.append({
                "id": _uid(),
                "type": "mcq",
                "prompt": f"How do you say '{source_word}' in {language}?",
                "options": options_t,
                "answer": target_word,
                "difficulty": difficulty,
            })

    return activities[:count]


def _generate_grammar_activity(title, content, difficulty, count, language):
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
    elif "art\u00edculo" in title_lower:
        template_key = "articles"
    elif "comparativ" in title_lower or "demostrativ" in title_lower:
        template_key = "comparatives"

    # Only use templates if the language is supported
    if language in FILL_BLANK_TEMPLATES and template_key and template_key in FILL_BLANK_TEMPLATES[language]:
        templates = FILL_BLANK_TEMPLATES[language][template_key]
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

    # Fallback: generate from examples in content
    examples = content.get("examples", [])
    activities = []
    for ex in examples[:count]:
        if isinstance(ex, dict):
            p = ex.get("prompt", ex.get("text", ""))
            a = ex.get("answer", "")
            h = ex.get("hint", "")
        else:
            # Heuristic: try to find a word to blank out
            words = ex.rstrip(".").split()
            if len(words) >= 3:
                blank_idx = random.randint(1, len(words)-2)
                a = words[blank_idx]
                words[blank_idx] = "___"
                p = " ".join(words)
                h = ""
            else: continue
            
        if p and a:
            activities.append({
                "id": _uid(),
                "type": "fill_blank",
                "prompt": p,
                "answer": a,
                "hint": h,
                "difficulty": difficulty,
            })
    return activities


def generate_quiz(topic_ids, student_mastery=None, count=10, progress_callback=None):
    """
    Generate a quiz pulling questions from given topics.
    If student_mastery is provided, adjusts difficulty.
    """
    from database import db_connection, get_db
    import uuid
    
    # 1. Discovery & Initial Pull
    topic_to_chapter = {}
    chapter_groups = {} # chapter_id -> [questions from DB]
    all_chapter_ids = set()
    
    with db_connection() as db_conn:
        c = db_conn.cursor()
        for tid in topic_ids:
            row_ch = c.execute("SELECT chapter_id FROM topics WHERE id = ?", (tid,)).fetchone()
            cid = row_ch["chapter_id"] if row_ch else "unknown"
            topic_to_chapter[tid] = cid
            all_chapter_ids.add(cid)
            if cid not in chapter_groups: chapter_groups[cid] = []
        
        print(f"[DEBUG] generate_quiz: topic_ids count={len(topic_ids)}, unique chapters identified={len(all_chapter_ids)}: {all_chapter_ids}")
            
            rows = c.execute(
                "SELECT * FROM questions WHERE topic_id = ? AND approved = 1 AND type = 'mcq' ORDER BY RANDOM()",
                (tid,)
            ).fetchall()
            
            for row in rows:
                q = dict(row)
                try:
                    raw_dist = json.loads(q["distractors"]) if isinstance(q["distractors"], str) else q["distractors"]
                    q["distractors"] = [d for d in raw_dist if isinstance(d, str) and d.strip()]
                except: q["distractors"] = []
                if not q["distractors"]: continue
                q["chapter_id"] = cid
                chapter_groups[cid].append(q)

    # 2. Balanced Assembly
    questions = []
    # Phase A: Seed one from every chapter that has questions in DB
    shuffled_chapters = list(all_chapter_ids)
    random.shuffle(shuffled_chapters)
    
    for cid in shuffled_chapters:
        group = chapter_groups.get(cid, [])
        if group:
            random.shuffle(group)
            questions.append(group.pop())
            if len(questions) >= count: break

    # 3. AI Generation for missing chapters or filling gaps
    max_retries = 3
    retry_count = 0
    
    import concurrent.futures
    from services.state import bump_version
    from services.ai_engine import ai_generate_questions, is_ai_available

    while len(questions) < count and is_ai_available() and retry_count < max_retries:
        retry_count += 1
        needed = count - len(questions)
        
        # Identify chapters STILL missing representation
        present_chapters = set(q.get("chapter_id") for q in questions)
        missing_chapters = all_chapter_ids - present_chapters
        
        targets = []
        if missing_chapters:
            # Pick 1 topic from each missing chapter up to 5 parallel targets
            for mcid in list(missing_chapters)[:5]:
                t_in_c = [tid for tid, cid in topic_to_chapter.items() if cid == mcid]
                if t_in_c: targets.append(random.choice(t_in_c))
        else:
            # Just fill the gap
            targets = random.sample(topic_ids, min(len(topic_ids), 3))
            
        if not targets: break

        def _gen_for_topic(tid, batch):
            from database import db_connection
            try:
                with db_connection() as thread_conn:
                    tc = thread_conn.cursor()
                    t_data = tc.execute("SELECT title, type, content, difficulty FROM topics WHERE id = ?", (tid,)).fetchone()
                    if not t_data: return [], tid, ""
                    
                    l_row = tc.execute("""
                        SELECT co.language FROM courses co
                        JOIN chapters ch ON co.id = ch.course_id
                        JOIN topics t ON ch.id = t.chapter_id
                        WHERE t.id = ?
                    """, (tid,)).fetchone()
                    language = l_row["language"] if l_row else "Unknown" 
                    parsed_content = json.loads(t_data["content"]) if t_data["content"] else {}
                    
                    return ai_generate_questions(t_data["title"], t_data["type"], parsed_content, language, batch, level=t_data["difficulty"]), tid, t_data["title"]
            except Exception as e:
                print(f"[ERROR] Parallel AI Gen failed for {tid}: {e}")
                return [], tid, ""

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(targets)) as executor:
            # If we have missing chapters, we take only 1-2 questions per target to ensure we see them all
            is_balancing = len(missing_chapters) > 0
            batch_size = 2 if is_balancing else max(needed // len(targets) + 1, 5)
            
            futures = [executor.submit(_gen_for_topic, tid, batch_size) for tid in targets]
            
            for f in concurrent.futures.as_completed(futures):
                new_qs, tid, t_title = f.result()
                if new_qs:
                    cid = topic_to_chapter.get(tid, "unknown")
                    added_this_batch = 0
                    with db_connection() as db_conn:
                        for q in new_qs:
                            if not q.get("prompt") or not q.get("answer"): continue
                            # If we are balancing, we take only 1-2 per topic initially to leave room for others
                            if is_balancing and added_this_batch >= 2: break
                            if len(questions) >= count + 5: break 
                            
                            q_id = str(uuid.uuid4())
                            distractors = q.get("distractors", [])
                            if not isinstance(distractors, list): distractors = []
                            
                            db_conn.execute("INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, approved) VALUES (?,?,?,?,?,?,?,1)",
                                       (q_id, tid, q.get("type", "mcq"), q.get("prompt", ""), q.get("answer", ""), 
                                        json.dumps(distractors), "A1.1"))
                            
                            questions.append({
                                "id": q_id, "topic_id": tid, "chapter_id": cid,
                                "type": q.get("type", "mcq"), "prompt": q.get("prompt", ""),
                                "answer": q.get("answer", ""), "distractors": distractors, "difficulty": "A1.1"
                            })
                            added_this_batch += 1
                        db_conn.commit()
                    if added_this_batch > 0:
                        bump_version()
                        print(f"[AI] Forced balance gen: {added_this_batch} questions for chapter {cid} (topic {t_title})")
                
                if progress_callback:
                    current_prog = 20 + int((len(questions) / count) * 80)
                    progress_callback(min(current_prog, 99))

    if progress_callback: progress_callback(100)
    return questions[:count]


def generate_dialogue_activity(language="Unknown"):
    """Generate a dialogue ordering activity."""
    if is_ai_available():
        try:
            prompt = f"""Generate a dialogue between two people in {language} for A1 level.
Include 6-8 lines.
Return ONLY valid JSON:
{{
  "title": "Dialogue Title",
  "lines": [
    {{ "order": 1, "speaker": "A", "text": "..." }},
    {{ "order": 2, "speaker": "B", "text": "..." }}
  ]
}}"""
            from services.ai_engine import _call_ai
            result = _call_ai([{"role": "user", "content": prompt}])
            if result:
                lines = result.get("lines", [])
                correct_order = [l["text"] for l in sorted(lines, key=lambda x: x.get("order", 0))]
                scrambled = lines[:]
                random.shuffle(scrambled)
                return {
                    "id": _uid(),
                    "type": "dialogue_order",
                    "title": result.get("title", "Dialogue"),
                    "scrambled_lines": [l["text"] for l in scrambled],
                    "correct_order": correct_order,
                    "speakers": {l["text"]: l["speaker"] for l in lines},
                }
        except Exception as e:
            print(f"[AI] Dialogue generation error: {e}")

    # [CLEANUP] Removed Spanish-specific hardcoded fallbacks
    return None
    
    return None


def grade_response(question_type, student_answer, correct_answer):
    """Grade a student response."""
    if student_answer is None: student_answer = ""
    if correct_answer is None: correct_answer = ""
        
    student_clean = str(student_answer).strip().lower()
    correct_clean = str(correct_answer).strip().lower()

    if student_clean == correct_clean:
        return 1.0, "Correct! \u2713"

    if question_type == "fill_blank" and is_ai_available():
        try:
            ai_result = ai_grade_open_response("Fill in the blank", student_answer, correct_answer)
            if ai_result: return ai_result[0], ai_result[1]
        except Exception: pass

    distance = _levenshtein(student_clean, correct_clean)
    if distance <= 1 and len(correct_clean) > 3:
        return 0.8, f"Almost! The correct answer is '{correct_answer}'."
    elif distance <= 2 and len(correct_clean) > 5:
        return 0.5, f"Close, but the correct answer is '{correct_answer}'."
    else:
        return 0.0, f"Incorrect. The correct answer is '{correct_answer}'."


def _levenshtein(s1, s2):
    """Compute Levenshtein distance."""
    if len(s1) < len(s2): return _levenshtein(s2, s1)
    if len(s2) == 0: return len(s1)
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
