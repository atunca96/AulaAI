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

# (Templates removed for language-agnostic AulaAI 3.0)


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
                        distractors = a.get("distractors", [])
                        options = list(distractors)
                        if a.get("answer") and a.get("answer") not in options:
                            options.append(a.get("answer"))
                        random.shuffle(options)
                        activity["options"] = options
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

    # Simple semantic categorizer for smart distractors
    def _categorize_words(words_dict):
        categories = {"short": [], "medium": [], "long": []}
        for target, source in words_dict.items():
            length = len(source)
            if length <= 4:
                categories["short"].append((target, source))
            elif length <= 7:
                categories["medium"].append((target, source))
            else:
                categories["long"].append((target, source))
        return categories

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


def generate_quiz(topic_ids, student_mastery=None, count=10, progress_callback=None, is_quiz=False):
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
        
        # Pull existing approved questions to fill part of the quota
        # Skip DB pull for quizzes — existing questions may be in English (A1/A2 practice)
        # and quizzes must be strictly in the target language.
        if not is_quiz:
            for tid in topic_ids:
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
                    q["chapter_id"] = topic_to_chapter.get(tid, "unknown")
                    chapter_groups[q["chapter_id"]].append(q)

    # 2. Balanced Assembly
    questions = []
    # Seed one from every chapter that has questions in DB
    shuffled_chapters = list(all_chapter_ids)
    random.shuffle(shuffled_chapters)
    
    for cid in shuffled_chapters:
        group = chapter_groups.get(cid, [])
        if group:
            random.shuffle(group)
            questions.append(group.pop())
            if len(questions) >= count: break

    # 3. BIG BATCH AI Generation for remaining gaps
    if len(questions) < count and is_ai_available():
        needed = count - len(questions)
        print(f"[AI] Quiz Big Batch: Requesting {needed} questions for {len(topic_ids)} topics")
        
        # Build a consolidated prompt for multiple topics
        topics_summary = []
        with db_connection() as db_conn:
            for tid in topic_ids:
                t_row = db_conn.execute("SELECT title, type, content FROM topics WHERE id = ?", (tid,)).fetchone()
                if t_row:
                    topics_summary.append({
                        "id": tid,
                        "title": t_row["title"],
                        "type": t_row["type"],
                        "content": json.loads(t_row["content"]) if t_row["content"] else {}
                    })
        
        # Use first topic's language as base
        base_lang = "Unknown"
        if topics_summary:
            with db_connection() as db_conn:
                l_row = db_conn.execute("""
                    SELECT co.language FROM courses co
                    JOIN chapters ch ON co.id = ch.course_id
                    JOIN topics t ON ch.id = t.chapter_id
                    WHERE t.id = ?
                """, (topics_summary[0]["id"],)).fetchone()
                base_lang = l_row["language"] if l_row else "Unknown"

        # Call the unified engine
        from services.ai_engine import ai_generate_questions
        new_qs = ai_generate_questions(
            topic_title="Quiz/Review", 
            topic_type="mixed_curriculum",
            topic_content={"topics": topics_summary},
            language=base_lang,
            count=needed,
            existing_questions=questions,
            is_quiz=is_quiz
        )
        if new_qs:
            with db_connection() as db_conn:
                for q in new_qs:
                    if len(questions) >= count:
                        break
                    tid = q.get("topic_id") or random.choice(topic_ids)
                    q_id = str(uuid.uuid4())
                    distractors = q.get("distractors", [])
                    db_conn.execute(
                        "INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, approved) VALUES (?,?,?,?,?,?,?,1)",
                        (q_id, tid, q.get("type", "mcq"), q.get("prompt", ""), q.get("answer", ""),
                         json.dumps(distractors), "A1.1")
                    )
                    questions.append({
                        "id": q_id, "topic_id": tid,
                        "type": q.get("type", "mcq"), "prompt": q.get("prompt", ""),
                        "answer": q.get("answer", ""), "distractors": distractors, "difficulty": "A1.1"
                    })
                db_conn.commit()
            from services.state import bump_version
            bump_version()

        print(f"[QUIZ] After first AI call: have {len(questions)}/{count}")

    # ── AI RETRY LOOP ── Keep requesting until count is met or retries exhausted ──
    MAX_QUIZ_AI_PASSES = 3
    quiz_ai_pass = 0
    while len(questions) < count and is_ai_available() and quiz_ai_pass < MAX_QUIZ_AI_PASSES:
        quiz_ai_pass += 1
        still_needed = count - len(questions)
        print(f"[QUIZ] AI pass {quiz_ai_pass}: still need {still_needed} questions")

        # Re-build topics summary (first pass already did this; reuse if available)
        if quiz_ai_pass == 1:
            pass  # topics_summary and base_lang already set from the block above
        # For subsequent passes topics_summary / base_lang are already in scope

        from services.ai_engine import ai_generate_questions
        extra_qs = ai_generate_questions(
            topic_title="Quiz/Review",
            topic_type="mixed_curriculum",
            topic_content={"topics": topics_summary},
            language=base_lang,
            count=still_needed,
            existing_questions=questions,  # forbidden list grows each pass
            is_quiz=is_quiz
        )

        if extra_qs:
            with db_connection() as db_conn:
                for q in extra_qs:
                    if len(questions) >= count:
                        break
                    tid = q.get("topic_id") or random.choice(topic_ids)
                    q_id = str(uuid.uuid4())
                    distractors = q.get("distractors", [])
                    db_conn.execute(
                        "INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, approved) VALUES (?,?,?,?,?,?,?,1)",
                        (q_id, tid, q.get("type", "mcq"), q.get("prompt", ""), q.get("answer", ""),
                         json.dumps(distractors), "A1.1")
                    )
                    questions.append({
                        "id": q_id, "topic_id": tid,
                        "type": q.get("type", "mcq"), "prompt": q.get("prompt", ""),
                        "answer": q.get("answer", ""), "distractors": distractors, "difficulty": "A1.1"
                    })
                db_conn.commit()
            from services.state import bump_version
            bump_version()

        print(f"[QUIZ] After AI pass {quiz_ai_pass}: have {len(questions)}/{count}")

    final_quiz = questions[:count]
    print(f"[QUIZ] FINAL: requested={count} returned={len(final_quiz)}")
    if progress_callback:
        progress_callback(100)
    return final_quiz


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
            from services.ai_engine import ai_grade_open_response
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
