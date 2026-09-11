"""
Content Engine — Handles generation of quizzes and assignments via OpenRouter.
"""

import random
import re
import json
import uuid
from datetime import datetime
from services.ai_engine import is_ai_available, ai_generate_activity, ai_generate_questions, ai_grade_open_response, is_transparent_cognate, _sanitize_blank_translations


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


def generate_assessment_set(topic_ids, count=10, is_quiz=False, ui_lang="en", existing_questions=None, progress_callback=None, generation_seed=None):
    """
    Unified assessment generation engine for both Quizzes and Activities.
    - If single topic (Activities): loads topic directly with 100% topic fidelity.
    - If multiple topics (Quizzes / Drafts): balances across curriculum units.
    - Enforces diverse communicative question types (dialogues, situational, cloze).
    - Eliminates shallow translation questions entirely.
    - Generates full explanations ('why' and 'why_tr') for interactive student feedback.
    """
    from database import db_connection
    import uuid
    import random as py_random
    
    if not topic_ids:
        return []

    c_count = int(count)
    if progress_callback:
        progress_callback(15, "Ders içeriği taranıyor..." if ui_lang == "tr" else "Scanning lesson content...")

    forbidden_questions = list(existing_questions or [])

    with db_connection() as db_conn:
        cursor = db_conn.cursor()
        for tid in topic_ids:
            # Pull recent questions for this topic to forbid exact repeats
            recent = cursor.execute("SELECT prompt, answer FROM questions WHERE topic_id = ? ORDER BY id DESC LIMIT 50", (tid,)).fetchall()
            for r in recent:
                forbidden_questions.append({"prompt": r["prompt"], "answer": r["answer"]})

    # Base language & level discovery
    base_lang = "Unknown"
    material_language = "en"
    course_level = "A1"
    with db_connection() as db_conn:
        first_tid = topic_ids[0]
        l_row = db_conn.execute("""
            SELECT co.language, co.material_language, co.level FROM courses co
            JOIN chapters ch ON co.id = ch.course_id
            JOIN topics t ON ch.id = t.chapter_id
            WHERE t.id = ?
        """, (first_tid,)).fetchone()
        if l_row:
            base_lang = l_row["language"] if l_row["language"] else "Unknown"
            if "material_language" in l_row.keys() and l_row["material_language"]:
                material_language = l_row["material_language"]
            if "level" in l_row.keys() and l_row["level"]:
                course_level = l_row["level"]

    if ui_lang and ui_lang in ["tr", "en"]:
        material_language = ui_lang

    questions = []

    if progress_callback:
        progress_callback(40, "Yapay zekâ ile özgün sorular üretiliyor..." if ui_lang == "tr" else "AI generating unique questions...")

    if is_ai_available():
        from services.ai_engine import ai_generate_questions

        # Case A: Single topic assessment (e.g. Activity) -> 100% topic fidelity
        if len(topic_ids) == 1:
            tid = topic_ids[0]
            with db_connection() as db_conn:
                t_row = db_conn.execute("SELECT title, type, content FROM topics WHERE id = ?", (tid,)).fetchone()
            
            if t_row:
                topic_title = t_row["title"]
                topic_type = t_row["type"] or "vocabulary"
                try:
                    topic_content = json.loads(t_row["content"]) if isinstance(t_row["content"], str) else (t_row["content"] or {})
                except Exception:
                    topic_content = {}

                new_qs = ai_generate_questions(
                    topic_title=topic_title,
                    topic_type=topic_type,
                    topic_content=topic_content,
                    language=base_lang,
                    count=c_count,
                    level=course_level,
                    existing_questions=forbidden_questions,
                    is_quiz=is_quiz,
                    material_language=material_language,
                    generation_seed=generation_seed
                )
                if new_qs:
                    for q in new_qs:
                        q_id = str(uuid.uuid4())
                        distractors = q.get("distractors", [])
                        options = [q.get("answer", "")] + distractors
                        py_random.shuffle(options)
                        t_en = q.get("translation_en") or q.get("translation", "")
                        t_tr = q.get("translation_tr") or q.get("translation", "")
                        why_en = q.get("why", "Correct answer based on the lesson.")
                        why_tr = q.get("why_tr", "Ders içeriğine göre doğru seçenek.")

                        questions.append({
                            "id": q_id,
                            "topic_id": tid,
                            "type": q.get("type", "mcq"),
                            "prompt": q.get("prompt", ""),
                            "translation": t_tr if material_language == "tr" else t_en,
                            "translation_en": t_en,
                            "translation_tr": t_tr,
                            "answer": q.get("answer", ""),
                            "distractors": distractors,
                            "options": options,
                            "difficulty": course_level,
                            "why": why_en,
                            "why_tr": why_tr,
                            "evidence": q.get("evidence", ""),
                            "material_section": q.get("material_section", ""),
                            "cognitive_task": q.get("cognitive_task", "")
                        })

        # Case B: Multi-topic assessment (e.g. Quiz / Review) -> Balanced cross-topic curriculum
        else:
            target_ids = py_random.sample(topic_ids, min(6, len(topic_ids))) if len(topic_ids) > 6 else list(topic_ids)
            topics_summary = []
            with db_connection() as db_conn:
                for tid in target_ids:
                    t_row = db_conn.execute("SELECT title, type, content FROM topics WHERE id = ?", (tid,)).fetchone()
                    if t_row:
                        key_terms = []
                        key_grammar = []
                        key_dialogues = []
                        key_texts = []
                        if t_row["content"]:
                            try:
                                tc = json.loads(t_row["content"])
                                for p in tc.get("pages", []):
                                    ptype = str(p.get("type", "")).lower()
                                    ptext = (p.get("text") or "").strip()
                                    if ptext and len(key_texts) < 2:
                                        key_texts.append(ptext[:400])

                                    # Extract dialogue lines
                                    if p.get("dialogue") and isinstance(p["dialogue"], list) and len(key_dialogues) < 3:
                                        for d in p["dialogue"][:4]:
                                            spk = d.get("speaker") or "Speaker"
                                            txt = d.get("text") or d.get("line") or ""
                                            trans = (d.get("line_tr") or d.get("translation_tr")) if material_language == "tr" else (d.get("line_en") or d.get("translation_en") or d.get("translation") or "")
                                            if txt:
                                                key_dialogues.append(f"{spk}: \"{txt}\"" + (f" ({trans})" if trans else ""))

                                    # Extract items (vocab & grammar)
                                    for it in p.get("items", []):
                                        if isinstance(it, dict):
                                            term = (it.get("term") or it.get("word") or it.get("rule") or "").strip()
                                            tr_val = (it.get("translation_tr") if material_language == "tr" and it.get("translation_tr") else (it.get("translation_en") or it.get("translation") or it.get("meaning") or "")).strip()
                                            ex = (it.get("example") or it.get("sample") or "").strip()
                                            expl = (it.get("explanation_tr") if material_language == "tr" and it.get("explanation_tr") else (it.get("explanation_en") or it.get("explanation") or "")).strip()
                                            if term:
                                                disp = f"{term} ({tr_val})" if tr_val else term
                                                if ex: disp += f" [ex: {ex}]"
                                                if expl: disp += f" [rule: {expl}]"
                                                if any(k in ptype for k in ["grammar", "rule", "pattern"]) or "rule" in it:
                                                    if len(key_grammar) < 6: key_grammar.append(disp)
                                                else:
                                                    if len(key_terms) < 8: key_terms.append(disp)
                            except Exception: pass
                        topics_summary.append({
                            "id": tid,
                            "title": t_row["title"],
                            "type": t_row["type"],
                            "key_vocab": key_terms[:8],
                            "key_grammar": key_grammar[:6],
                            "key_dialogues": key_dialogues[:3],
                            "key_texts": key_texts[:2]
                        })

            new_qs = ai_generate_questions(
                topic_title="Quiz/Review",
                topic_type="mixed_curriculum",
                topic_content={"topics": topics_summary},
                language=base_lang,
                count=c_count,
                level=course_level,
                existing_questions=forbidden_questions,
                is_quiz=is_quiz,
                material_language=material_language,
                generation_seed=generation_seed
            )
            if new_qs:
                for q in new_qs:
                    tid = q.get("topic_id") or py_random.choice(topic_ids)
                    q_id = str(uuid.uuid4())
                    distractors = q.get("distractors", [])
                    if len(distractors) < 3:
                        continue
                    options = [q.get("answer", "")] + distractors[:3]
                    py_random.shuffle(options)
                    t_en = q.get("translation_en") or q.get("translation", "")
                    t_tr = q.get("translation_tr") or q.get("translation", "")
                    why_en = q.get("why", "Correct answer based on the lesson.")
                    why_tr = q.get("why_tr", "Ders içeriğine göre doğru seçenek.")

                    if re.search(r'_{2,}', q.get("prompt", "")):
                        t_en, t_tr = _sanitize_blank_translations(q.get("prompt", ""), q.get("answer", ""), t_en, t_tr, why_en, why_tr)

                    questions.append({
                        "id": q_id,
                        "topic_id": tid,
                        "type": q.get("type", "mcq"),
                        "prompt": q.get("prompt", ""),
                        "translation": t_tr if material_language == "tr" else t_en,
                        "translation_en": t_en,
                        "translation_tr": t_tr,
                        "answer": q.get("answer", ""),
                        "distractors": distractors,
                        "options": options,
                        "difficulty": course_level,
                        "why": why_en,
                        "why_tr": why_tr,
                        "evidence": q.get("evidence", ""),
                        "material_section": q.get("material_section", ""),
                        "cognitive_task": q.get("cognitive_task", "")
                    })

        # Supplementary AI pass ONLY if first batch yielded severely fewer than requested (e.g. < 70%)
        if len(questions) < max(int(c_count * 0.7), 1):
            still_needed = max(c_count - len(questions), 3)
            sub_forbidden = forbidden_questions + [{"prompt": q["prompt"], "answer": q["answer"]} for q in questions]
            if len(topic_ids) == 1 and 'topic_title' in locals():
                extra_qs = ai_generate_questions(
                    topic_title=topic_title,
                    topic_type=topic_type,
                    topic_content=topic_content,
                    language=base_lang,
                    count=still_needed,
                    level=course_level,
                    existing_questions=sub_forbidden,
                    is_quiz=is_quiz,
                    material_language=material_language,
                    generation_seed=(generation_seed + 1) if generation_seed is not None else None
                )
            elif 'topics_summary' in locals():
                extra_qs = ai_generate_questions(
                    topic_title="Quiz/Review",
                    topic_type="mixed_curriculum",
                    topic_content={"topics": topics_summary},
                    language=base_lang,
                    count=still_needed,
                    level=course_level,
                    existing_questions=sub_forbidden,
                    is_quiz=is_quiz,
                    material_language=material_language,
                    generation_seed=(generation_seed + 1) if generation_seed is not None else None
                )
            else:
                extra_qs = []

            if extra_qs:
                for q in extra_qs:
                    if len(questions) >= c_count: break
                    tid = q.get("topic_id") or topic_ids[0]
                    q_id = str(uuid.uuid4())
                    distractors = q.get("distractors", [])
                    if len(distractors) < 3:
                        continue
                    options = [q.get("answer", "")] + distractors[:3]
                    py_random.shuffle(options)
                    t_en = q.get("translation_en") or q.get("translation", "")
                    t_tr = q.get("translation_tr") or q.get("translation", "")
                    why_en = q.get("why", "Correct answer based on the lesson.")
                    why_tr = q.get("why_tr", "Ders içeriğine göre doğru seçenek.")

                    if re.search(r'_{2,}', q.get("prompt", "")):
                        t_en, t_tr = _sanitize_blank_translations(q.get("prompt", ""), q.get("answer", ""), t_en, t_tr, why_en, why_tr)

                    questions.append({
                        "id": q_id,
                        "topic_id": tid,
                        "type": q.get("type", "mcq"),
                        "prompt": q.get("prompt", ""),
                        "translation": t_tr if material_language == "tr" else t_en,
                        "translation_en": t_en,
                        "translation_tr": t_tr,
                        "answer": q.get("answer", ""),
                        "distractors": distractors,
                        "options": options,
                        "difficulty": course_level,
                        "why": why_en,
                        "why_tr": why_tr
                    })

    if progress_callback:
        progress_callback(75, "Pedagojik kurallar ve seçenekler doğrulanıyor..." if ui_lang == "tr" else "Validating options and pedagogy...")

    # Strict Topic-Isolated Safety Net (Only for non-quiz offline activities if questions < count)
    if not is_quiz and len(questions) < c_count:
        with db_connection() as db_conn:
            placeholders = ",".join("?" * len(topic_ids))
            existing_rows = db_conn.execute(
                f"SELECT id, topic_id, type, prompt, answer, distractors, difficulty FROM questions WHERE topic_id IN ({placeholders}) AND approved = 1 ORDER BY RANDOM() LIMIT ?",
                list(topic_ids) + [c_count - len(questions)]
            ).fetchall()
            for r in existing_rows:
                if len(questions) >= c_count: break
                if not any(q["prompt"] == r["prompt"] for q in questions):
                    try:
                        d_list = json.loads(r["distractors"]) if r["distractors"] else []
                    except Exception:
                        d_list = []
                    if len(d_list) < 3:
                        continue
                    opts = [r["answer"]] + d_list[:3]
                    py_random.shuffle(opts)
                    questions.append({
                        "id": r["id"],
                        "topic_id": r["topic_id"],
                        "type": r["type"],
                        "prompt": r["prompt"],
                        "translation": "",
                        "translation_en": "",
                        "translation_tr": "",
                        "answer": r["answer"],
                        "distractors": d_list,
                        "options": opts,
                        "difficulty": r["difficulty"],
                        "why": "Correct answer based on the lesson.",
                        "why_tr": "Ders içeriğine göre doğru seçenek."
                    })

    if progress_callback:
        progress_callback(90, "Çeviriler ve açıklamalar optimize ediliyor..." if ui_lang == "tr" else "Optimizing translations and hints...")

    from services.state import bump_version
    bump_version()

    final_set = questions
    if progress_callback:
        progress_callback(100, "Sorular hazır!" if ui_lang == "tr" else "Questions ready!")

    return final_set

def generate_quiz(topic_ids, student_mastery=None, count=10, progress_callback=None, is_quiz=True, ui_lang="en", existing_questions=None, generation_seed=None):
    """Backward compatibility wrapper delegating to unified generate_assessment_set."""
    return generate_assessment_set(topic_ids=topic_ids, count=count, is_quiz=is_quiz, ui_lang=ui_lang, existing_questions=existing_questions, progress_callback=progress_callback, generation_seed=generation_seed)


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
