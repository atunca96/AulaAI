"""
Content Engine — Handles generation of quizzes and assignments via OpenRouter.
"""

import random
import json
import uuid
from datetime import datetime
from services.ai_engine import is_ai_available, ai_generate_activity, ai_generate_questions, ai_grade_open_response, is_transparent_cognate


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

    # ANTI-COGNATE STRATEGY: Prioritize non-cognates so questions are challenging and not obvious giveaways
    non_cognates = [it for it in items if not is_transparent_cognate(it[0], it[1])]
    cognates = [it for it in items if is_transparent_cognate(it[0], it[1])]
    selected_items = (non_cognates + cognates)[:count]

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
    for target_word, source_word in selected_items:
        is_cognate = is_transparent_cognate(target_word, source_word)
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

            if is_cognate:
                prompt_text = f"In authentic {language} discourse, identify the proper definition context for '{target_word}':"
            else:
                prompt_text = f"What does '{target_word}' mean?" if language == "English" else f"What does the {language} word '{target_word}' mean?"

            activities.append({
                "id": _uid(),
                "type": "mcq",
                "prompt": prompt_text,
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

            if is_cognate:
                prompt_text = f"In a formal {language} communicative scenario, select the correct term representing '{source_word}':"
            else:
                prompt_text = f"How do you say '{source_word}' in {language}?"

            activities.append({
                "id": _uid(),
                "type": "mcq",
                "prompt": prompt_text,
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


def generate_quiz(topic_ids, student_mastery=None, count=10, progress_callback=None, is_quiz=False, ui_lang="en"):
    """
    Generate a quiz pulling questions from given topics.
    If student_mastery is provided, adjusts difficulty.
    """
    from database import db_connection, get_db
    import uuid
    
    # 1. Discovery
    topic_to_chapter = {}
    all_chapter_ids = set()
    forbidden_questions = []
    
    with db_connection() as db_conn:
        c = db_conn.cursor()
        for tid in topic_ids:
            row_ch = c.execute("SELECT chapter_id FROM topics WHERE id = ?", (tid,)).fetchone()
            cid = row_ch["chapter_id"] if row_ch else "unknown"
            topic_to_chapter[tid] = cid
            all_chapter_ids.add(cid)
            
            # LIVE-ONLY: Pull the last 20 questions generated for this topic to use as a "Forbidden List"
            # This ensures the AI doesn't repeat itself even if we don't use these questions in the quiz.
            recent = c.execute("SELECT prompt, answer FROM questions WHERE topic_id = ? ORDER BY id DESC LIMIT 20", (tid,)).fetchall()
            for r in recent:
                forbidden_questions.append({"prompt": r["prompt"], "answer": r["answer"]})
        
        print(f"[LIVE-ONLY] Quiz generation started. Forbidden pool size: {len(forbidden_questions)}")

    # 2. Skip DB recycling - Always use AI for maximum variety
    questions = []

    # 3. BIG BATCH AI Generation
    if is_ai_available():
        needed = count
        print(f"[AI] Live-Only Batch: Requesting {needed} fresh questions for {len(topic_ids)} topics")
        
        # Surgically sample up to 6 topics and extract only key terms (prevents 1.2M char token blowout)
        target_ids = random.sample(topic_ids, min(6, len(topic_ids))) if len(topic_ids) > 6 else list(topic_ids)
        topics_summary = []
        with db_connection() as db_conn:
            for tid in target_ids:
                t_row = db_conn.execute("SELECT title, type, content FROM topics WHERE id = ?", (tid,)).fetchone()
                if t_row:
                    key_terms = []
                    if t_row["content"]:
                        try:
                            tc = json.loads(t_row["content"])
                            for p in tc.get("pages", []):
                                for it in p.get("items", []):
                                    if it.get("term"):
                                        tr_val = it.get("translation_tr") or it.get("translation")
                                        key_terms.append(f"{it.get('term')} ({tr_val})")
                                    if len(key_terms) >= 5: break
                        except: pass
                    topics_summary.append({
                        "id": tid,
                        "title": t_row["title"],
                        "type": t_row["type"],
                        "key_vocab": key_terms[:5]
                    })
        
        # Use first topic's language and level as base
        base_lang = "Unknown"
        material_language = "en"
        course_level = "A1"
        if topics_summary:
            with db_connection() as db_conn:
                l_row = db_conn.execute("""
                    SELECT co.language, co.material_language, co.level FROM courses co
                    JOIN chapters ch ON co.id = ch.course_id
                    JOIN topics t ON ch.id = t.chapter_id
                    WHERE t.id = ?
                """, (topics_summary[0]["id"],)).fetchone()
                if l_row:
                    base_lang = l_row["language"] if l_row["language"] else "Unknown"
                    if "material_language" in l_row.keys() and l_row["material_language"]:
                        material_language = l_row["material_language"]
                    if "level" in l_row.keys() and l_row["level"]:
                        course_level = l_row["level"]
        
        if ui_lang and ui_lang in ["tr", "en"]:
            material_language = ui_lang

        # Call the unified engine
        from services.ai_engine import ai_generate_questions
        new_qs = ai_generate_questions(
            topic_title="Quiz/Review", 
            topic_type="mixed_curriculum",
            topic_content={"topics": topics_summary},
            language=base_lang,
            count=needed,
            level=course_level,
            existing_questions=forbidden_questions,
            is_quiz=is_quiz,
            material_language=material_language
        )
        if new_qs:
            with db_connection() as db_conn:
                for q in new_qs:
                    if len(questions) >= count:
                        break
                    tid = q.get("topic_id") or random.choice(topic_ids)
                    q_id = str(uuid.uuid4())
                    distractors = q.get("distractors", [])
                    # Ensure options are assembled and shuffled for the UI
                    options = [q.get("answer", "")] + distractors
                    random.shuffle(options)
                    
                    db_conn.execute(
                        "INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, approved) VALUES (?,?,?,?,?,?,?,1)",
                        (q_id, tid, q.get("type", "mcq"), q.get("prompt", ""), q.get("answer", ""),
                         json.dumps(distractors), course_level)
                    )
                    questions.append({
                        "id": q_id, "topic_id": tid,
                        "type": q.get("type", "mcq"), "prompt": q.get("prompt", ""),
                        "answer": q.get("answer", ""), "distractors": distractors, 
                        "options": options, "difficulty": course_level
                    })
                db_conn.commit()
            from services.state import bump_version
            bump_version()

        print(f"[QUIZ] After first AI call: have {len(questions)}/{count}")

    # ── DETERMINISTIC FILL (Prevents Runaway Retries & Credit Drain) ──
    if len(questions) < count and is_ai_available():
        # Single extra pass if needed
        still_needed = count - len(questions)
        from services.ai_engine import ai_generate_questions
        extra_qs = ai_generate_questions(
            topic_title="Quiz/Review",
            topic_type="mixed_curriculum",
            topic_content={"topics": topics_summary},
            language=base_lang,
            count=still_needed,
            level=course_level,
            existing_questions=forbidden_questions + questions,
            is_quiz=is_quiz,
            material_language=material_language
        )
        if extra_qs:
            with db_connection() as db_conn:
                for q in extra_qs:
                    if len(questions) >= count:
                        break
                    tid = q.get("topic_id") or (random.choice(topic_ids) if topic_ids else "")
                    q_id = str(uuid.uuid4())
                    distractors = q.get("distractors", [])
                    options = [q.get("answer", "")] + distractors
                    random.shuffle(options)
                    
                    db_conn.execute(
                        "INSERT INTO questions (id, topic_id, type, prompt, answer, distractors, difficulty, approved) VALUES (?,?,?,?,?,?,?,1)",
                        (q_id, tid, q.get("type", "mcq"), q.get("prompt", ""), q.get("answer", ""),
                         json.dumps(distractors), course_level)
                    )
                    questions.append({
                        "id": q_id, "topic_id": tid,
                        "type": q.get("type", "mcq"), "prompt": q.get("prompt", ""),
                        "answer": q.get("answer", ""), "distractors": distractors, 
                        "options": options, "difficulty": course_level
                    })
                db_conn.commit()
            from services.state import bump_version
            bump_version()

    # Deterministic safety net: if still needed, pull from existing approved DB questions
    if len(questions) < count:
        with db_connection() as db_conn:
            existing_rows = db_conn.execute(
                "SELECT id, topic_id, type, prompt, answer, distractors, difficulty FROM questions WHERE approved = 1 ORDER BY RANDOM() LIMIT ?",
                (count - len(questions),)
            ).fetchall()
            for r in existing_rows:
                if len(questions) >= count: break
                if not any(q["prompt"] == r["prompt"] for q in questions):
                    d_list = json.loads(r["distractors"]) if r["distractors"] else []
                    opts = [r["answer"]] + d_list
                    random.shuffle(opts)
                    questions.append({
                        "id": r["id"], "topic_id": r["topic_id"],
                        "type": r["type"], "prompt": r["prompt"],
                        "answer": r["answer"], "distractors": d_list,
                        "options": opts, "difficulty": r["difficulty"]
                    })

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
