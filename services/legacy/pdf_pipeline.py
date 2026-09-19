# LEGACY - DO NOT USE
# TO BE REMOVED AFTER VALIDATION
import os
import random
import threading
import subprocess
import sys
import json
import copy
import concurrent.futures
import time
import urllib.request
import traceback
from datetime import datetime
from database import db_connection, _uid
from services.state import bump_version
from services.ai_engine import detect_language, generate_full_lesson, _call_ai

MAX_TOTAL_TOPICS = 1000

def file_log(msg):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [PIPELINE] {msg}\n")
            f.flush()
        # Also print to stdout for worker.py to capture if needed
        print(f"[{timestamp}] [PIPELINE] {msg}", flush=True)
    except: pass

def _log(msg):
    file_log(msg)


def _run_quality_units_serially(*, units, reviewer, stage, on_complete,
                                quality_error_cls):
    """Run quality-unit work fail-fast, one unit at a time.

    The old max_workers=1 ThreadPoolExecutor still submitted every unit up front.
    If unit N failed, executor shutdown waited for already-queued N+1.. units,
    hiding the real terminal error behind later successful model-call logs and
    wasting review budget. Serial execution makes the failure boundary exact.

    There is deliberately no whole-unit retry here any more. Convergence is the
    reviewer's own job now: `converge_topic` dispatches each blocker to the
    strategy that owns it and stops the moment a fingerprint repeats, so a
    second blind pass over the unit could only re-derive the same answer at
    full price. In production it did exactly that — the same malformed patch,
    the same renderer refusal, twice — while re-sending lessons that had
    already passed. Removing it is what pays for the extra bounded repairs
    inside the controller without touching the review ceiling.
    """
    total = len(units)
    applied = 0
    done = 0
    for unit in units:
        try:
            applied += reviewer(unit)
        except quality_error_cls as failure:
            _log(
                f"[QUALITY-GATE] {stage} failed for {unit['title']}: {failure}"
            )
            raise
        done += 1
        _log(
            f"[QUALITY-GATE] {stage} {done}/{total} complete "
            f"({unit['title']})."
        )
        on_complete(done, total, unit)
    return applied


def _run_quality_units_parallel_snapshots(*, units, reviewer, stage, on_complete,
                                          quality_error_cls, max_workers=3):
    """Parallelize independent unit review without parallel mutation.

    Each worker receives a deep-copy snapshot. Model calls and any local
    convergence happen on that isolated copy. Only after every unit in the stage
    succeeds are content snapshots merged back to the live unit objects, in
    original order, on the caller thread. Therefore concurrency cannot create
    cross-unit patch races or partially mutate the publication candidate.
    """
    total = len(units)
    if total <= 1 or int(max_workers or 1) <= 1:
        return _run_quality_units_serially(
            units=units, reviewer=reviewer, stage=stage,
            on_complete=on_complete, quality_error_cls=quality_error_cls,
        )

    workers = min(max(1, int(max_workers)), total)

    def _one(index_and_unit):
        index, original = index_and_unit
        snapshot = copy.deepcopy(original)
        try:
            applied = reviewer(snapshot)
            return index, snapshot, applied, None
        except quality_error_cls as failure:
            return index, snapshot, 0, failure

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_one, enumerate(units)))

    results.sort(key=lambda row: row[0])
    failures = [row for row in results if row[3] is not None]
    if failures:
        index, _snapshot, _applied, failure = failures[0]
        unit = units[index]
        _log(f"[QUALITY-GATE] {stage} failed for {unit['title']}: {failure}")
        raise failure

    applied_total = 0
    for done, (index, snapshot, applied, _failure) in enumerate(results, 1):
        original = units[index]
        snap_by_id = {str(t["id"]): t for t in snapshot.get("topics") or []}
        for topic in original.get("topics") or []:
            snap_topic = snap_by_id.get(str(topic["id"]))
            if snap_topic is not None:
                topic["content"] = copy.deepcopy(snap_topic["content"])
        applied_total += int(applied or 0)
        _log(
            f"[QUALITY-GATE] {stage} {done}/{total} complete "
            f"({original['title']})."
        )
        on_complete(done, total, original)
    return applied_total


def generate_classroom_code():
    return "".join([str(random.randint(0, 9)) for _ in range(5)])

def start_pipeline_background(pdf_path, toc_range, lecturer_id, course_id, course_name, manual_toc=None, source_markdown_path=None, language=None):
    """
    Background worker that runs Phase 1 and Phase 2.
    """
    start_time = datetime.now()
    toc_text = ""
    # Use provided language or default to Detecting...
    if not language:
        language = "Detecting..."
    
    try:
        _log(f"Phase 1: Starting for {course_id} ({course_name})")
        
        # Initialize language from DB if already set (manual creation)
        with db_connection() as db:
            row = db.execute("SELECT language FROM courses WHERE id = ?", (course_id,)).fetchone()
            if row and row[0] and row[0] != "Detecting...":
                language = row[0]
                _log(f"Using pre-set language: {language}")

        chapters_data = []
        is_pre_parsed = False
        
        # Check if manual_toc is already a structured JSON
        if manual_toc and manual_toc.strip().startswith('{'):
            try:
                data = json.loads(manual_toc)
                if "chapters" in data:
                    _log("Pre-parsed JSON curriculum detected.")
                    chapters_data = data["chapters"]
                    is_pre_parsed = True
            except: pass

        if not is_pre_parsed:
            # 1. Extract TOC Text (if range provided)
            if pdf_path != "NONE" and toc_range:
                _log("Step 1: Extracting TOC text from PDF...")
                try:
                    import fitz # PyMuPDF
                    doc = fitz.open(pdf_path)
                    
                    start_p = 1
                    end_p = 1
                    
                    if "-" in toc_range:
                        sp, ep = toc_range.split("-")
                        start_p = int(sp)
                        end_p = int(ep)
                    elif toc_range.strip().isdigit():
                        start_p = int(toc_range.strip())
                        end_p = start_p

                    for p in range(start_p-1, min(end_p, len(doc))):
                        toc_text += doc[p].get_text()
                    doc.close()
                    _log(f"TOC Extraction complete. Length: {len(toc_text)} chars")
                    
                    # OCR FALLBACK: If text extraction yielded nothing useful, try vision OCR
                    from services.legacy.ocr_fallback import is_image_based_page, ocr_pdf_pages
                    if is_image_based_page(toc_text):
                        _log("TOC text is empty/garbage — activating OCR fallback...")
                        ocr_toc = ocr_pdf_pages(pdf_path, start_page=start_p, end_page=end_p)
                        if ocr_toc and len(ocr_toc.strip()) > len(toc_text.strip()):
                            toc_text = ocr_toc
                            _log(f"OCR TOC extraction successful: {len(toc_text)} chars")
                        else:
                            _log("OCR fallback did not improve TOC extraction.")
                except Exception as e:
                    _log(f"ERROR in TOC Extraction: {e}")

            # 2. Detect Language
            _log("Step 2: Detecting language...")
            language = "Unknown"
            
            # Get course name for hint
            course_name = "Unknown Course"
            with db_connection() as db:
                row = db.execute("SELECT name FROM courses WHERE id = ?", (course_id,)).fetchone()
                if row: course_name = row[0]

            text_for_lang = manual_toc if manual_toc else toc_text
            if text_for_lang and text_for_lang.strip():
                try:
                    language = detect_language(text_for_lang, hint=course_name)
                except:
                    language = "Unknown"
            _log(f"Language detected: {language}")
            # Detection can only now tell us this is an English or Turkish class,
            # after the row was written with whatever track the lecturer picked.
            # Re-lock it here, or the build would generate material on a track the
            # course is not allowed to publish.
            from services.language_profiles import locked_track
            with db_connection() as db:
                forced = locked_track(language)
                if forced:
                    db.execute("UPDATE courses SET language = ?, material_language = ? WHERE id = ?",
                               (language, forced, course_id))
                    _log(f"Instructional track locked to '{forced}' for a {language} class.")
                else:
                    db.execute("UPDATE courses SET language = ? WHERE id = ?", (language, course_id))
                db.commit()
            
            bump_version()
            
            # 3. Parse Structure
            _log("Step 3: Analyzing curriculum structure...")
            
            # If we have a source markdown but no manual TOC, use the markdown to find structure
            if not manual_toc and source_markdown_path and os.path.exists(source_markdown_path):
                with open(source_markdown_path, "r", encoding="utf-8") as f:
                    manual_toc = f.read()
                _log("Using Source Markdown for structural analysis.")

            if manual_toc:
                _log(f"RAW MANUAL TOC RECEIVED ({len(manual_toc)} chars)")
                _log("Using Manual Curriculum provided by teacher.")
                parse_source = manual_toc
            else:
                _log("Extracting curriculum from PDF TOC text.")
                parse_source = toc_text

            # PRIMARY: Fast deterministic parser (milliseconds)
            import time as _t
            _parse_start = _t.time()
            from services.legacy.fast_parser import fast_parse_curriculum
            chapters_data = fast_parse_curriculum(parse_source)
            _parse_ms = (_t.time() - _parse_start) * 1000
            _log(f"Fast parser completed in {_parse_ms:.0f}ms → {len(chapters_data)} chapters")

            # FALLBACK: AI parsing only if fast parser produced nothing
            if not chapters_data:
                _log("Fast parser returned 0 chapters — falling back to AI parsing...")
                prompt_lang = language if language and language != "Detecting..." else "the target"
                prompt = f"""
                Task: Convert this messy curriculum text into a structured JSON Roadmap for a {prompt_lang} course.
                Input can be: numbered lists, plain text, indented outlines, or comma-separated items.
                
                Rules:
                1. Identify Chapters/Units: Look for overarching grouping headers ('Chapter', 'Unit', 'Module', 'Lektion', 'Tema', 'Unidad', etc.).
                2. CHUNKING FLAT LISTS (CRITICAL): If the curriculum is just a long flat list of lessons/topics with no explicit chapters, YOU MUST group them into logical sequential chapters.
                3. Types: Assign a type ('vocabulary', 'grammar', or 'reading') to each topic based on its title.
                4. CRITICAL: Skip meta-sections like 'About', 'Authors', 'License', 'Preface', 'Index', 'Bibliography', 'Appendix', etc.
                5. ORDER: You MUST list chapters and topics in the exact sequential order they appear in the text (strictly ascending page numbers).
                6. LANGUAGE: If the language is unknown, focus on extracting the literal titles without translating them.
                
                Return ONLY a valid JSON object with this exact structure:
                {{
                  "chapters": [
                    {{
                      "title": "Unit 1: ...",
                      "page": 12,
                      "topics": [
                        {{ "title": "Topic Name", "type": "vocabulary", "page": 13 }}
                      ]
                    }}
                  ]
                }}
                
                Manual Text to Parse:
                {parse_source}
                """
                resp = _call_ai([{"role": "user", "content": prompt}], max_tokens=4000)
                try:
                    if isinstance(resp, dict):
                        chapters_data = resp.get("chapters", [])
                    elif isinstance(resp, str) and resp.strip():
                        clean_resp = resp.replace("```json", "").replace("```", "").strip()
                        start_idx = clean_resp.find('{')
                        end_idx = clean_resp.rfind('}')
                        if start_idx != -1 and end_idx != -1:
                            clean_resp = clean_resp[start_idx:end_idx+1]
                        data = json.loads(clean_resp)
                        chapters_data = data.get("chapters", [])
                except Exception as e:
                    _log(f"AI Parsing also failed ({e}).")
        
        if not chapters_data:
            _log("ERROR: All parsing attempts failed.")
            with db_connection() as db:
                db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
                db.commit()
            return
            
        _log(f"Structure parsed. Found {len(chapters_data)} chapters.")

        # 4. Create structure in DB
        _log("Step 4: Creating classroom structure in DB...")
        with db_connection() as db:
            db.execute("UPDATE courses SET language = ? WHERE id = ?", (language, course_id))
            from services.language_data import resolve_curriculum_tr
            for idx, ch in enumerate(chapters_data):
                chapter_id = _uid()
                ch_num = idx + 1
                ch_title = str(ch.get("title", "Untitled Chapter"))
                ch_page = ch.get("page")
                ch_tr = resolve_curriculum_tr(ch_title, ch.get("title_tr"))
                db.execute("INSERT INTO chapters (id, course_id, number, title, page_number, title_tr) VALUES (?,?,?,?,?,?)",
                           (chapter_id, course_id, ch_num, ch_title, ch_page, ch_tr))
                for topic_idx, topic in enumerate(ch.get("topics", [])):
                    topic_id = _uid()
                    t_title = topic.get("title", "Untitled Topic")
                    t_type = topic.get("type", "vocabulary")
                    t_page = topic.get("page")
                    t_tr = resolve_curriculum_tr(t_title, topic.get("title_tr"))
                    db.execute("INSERT INTO topics (id, chapter_id, type, title, difficulty, content, sort_order, page_number, pdf_url, title_tr) VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (topic_id, chapter_id, t_type, t_title, "A1.1", json.dumps({}), topic_idx, t_page, "/books/" + os.path.basename(pdf_path), t_tr))
            db.commit()
        _log("Structure creation complete.")
        bump_version()
        
        # Phase 2: Enrichment
        _log(f"Phase 1 Complete for {course_id}. Starting Phase 2...")
        
        # SURGICAL OCR: If no source markdown exists and the PDF is scanned,
        # generate source markdown via OCR for ONLY the pages mentioned in the topics
        if not source_markdown_path and pdf_path and pdf_path != "NONE":
            try:
                from services.legacy.ocr_fallback import is_image_based_pdf, ocr_pdf_pages
                if is_image_based_pdf(pdf_path):
                    _log("Image-based PDF detected — generating surgical OCR source markdown...")
                    
                    # 1. Collect all unique pages mentioned in topics
                    all_pages = set()
                    for ch in chapters_data:
                        for t in ch.get("topics", []):
                            p = t.get("page")
                            if p:
                                all_pages.add(p)
                                # Always take +1 page for context spillover
                                all_pages.add(p + 1)
                    
                    if all_pages:
                        page_list = sorted(list(all_pages))
                        _log(f"Phase 2: Target surgical OCR for {len(page_list)} unique pages")
                        
                        from database import BOOKS_DIR
                        ocr_md_path = os.path.join(BOOKS_DIR, f"ocr_{course_id}.md")
                        ocr_text = ocr_pdf_pages(pdf_path, page_list=page_list)
                        
                        if ocr_text and len(ocr_text) > 100:
                            with open(ocr_md_path, "w", encoding="utf-8") as f:
                                f.write(ocr_text)
                            source_markdown_path = ocr_md_path
                            _log(f"Surgical OCR source markdown saved: {len(ocr_text)} chars -> {ocr_md_path}")
                        else:
                            _log("Surgical OCR produced insufficient text.")
                    else:
                        _log("No page numbers found in topics, cannot perform surgical OCR.")
            except Exception as e:
                _log(f"OCR fallback error (non-fatal): {e}")
        
        enrich_classroom_phase2(course_id, pdf_path, source_markdown_path=source_markdown_path)
        
        # ── FINAL STEP: Release UI Lock ──
        # Only set is_building = 0 when EVERYTHING is finished (Lessons + Starter Questions)
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
            db.commit()
        _log(f"CRITICAL: Classroom {course_id} is now FULLY enriched and ready.")
        bump_version()

    except Exception as e:
        _log(f"CRITICAL ERROR in Phase 1: {e}")
        traceback.print_exc()
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0 WHERE id = ?", (course_id,))
            db.commit()

def enrich_classroom_phase2(course_id, pdf_path, manual_toc_path=None, source_markdown_path=None, gen_id="LEGACY"):
    """
    Final optimized Phase 2 enrichment.
    """
    start_time = datetime.now()
    # Open a spend ledger for this class. Everything the enrichment phase charges
    # to the provider lands here, so "what did this class cost" is answered by a
    # measurement at the end of the build rather than by an estimate afterwards.
    try:
        from services import generation_cost
        generation_cost.reset(f"course {course_id}")
    except Exception:
        generation_cost = None
    # The class lexicon is scoped to one build. Carrying it between courses would
    # let one language's vocabulary establish pronunciations for another's.
    try:
        from services import class_lexicon
        class_lexicon.reset(f"course {course_id}")
    except Exception:
        pass
    manual_toc = None
    if manual_toc_path and os.path.exists(manual_toc_path):
        with open(manual_toc_path, "r", encoding="utf-8") as f:
            manual_toc = f.read()

    source_markdown_content = None
    page_chunks = {} 
    if source_markdown_path and os.path.exists(source_markdown_path):
        try:
            with open(source_markdown_path, "r", encoding="utf-8") as f:
                source_markdown_content = f.read()
            _log(f"Phase 2: Loaded external source markdown ({len(source_markdown_content)} chars)")
            
            import re
            parts = re.split(r'(?:\[Page\s*(\d+)\]|#\s*Source Page\s*(\d+))', source_markdown_content)
            for i in range(1, len(parts), 3):
                try:
                    p1 = parts[i]
                    p2 = parts[i+1]
                    p_num = int(p1) if p1 else int(p2)
                    p_text = parts[i+2].strip()
                    page_chunks[p_num] = p_text
                except: pass
            _log(f"Phase 2: Indexed {len(page_chunks)} normalized page chunks.")
        except Exception as e:
            _log(f"Phase 2 ERROR reading source markdown: {e}")

    try:
        with db_connection() as db:
            db.row_factory = lambda cursor, row: row 
            course = db.execute("SELECT language, level, material_language FROM courses WHERE id = ?", (course_id,)).fetchone()
            language = course[0] if course else "Unknown"
            level = course[1] if course and len(course) > 1 else "A1"
            material_language = course[2] if course and len(course) > 2 and course[2] else "tr"
            
            _log(f"Phase 2: Targeted Course={course_id}, Lang={language}, Level={level}, Material Lang={material_language}")
            
            chapters = db.execute("SELECT id, title, number FROM chapters WHERE course_id = ? ORDER BY number", (course_id,)).fetchall()
            _log(f"Phase 2: DB returned {len(chapters)} chapters for this course.")
            
            chapters_data = []
            for ch in chapters:
                topics = db.execute("SELECT id, title, type, page_number FROM topics WHERE chapter_id = ? ORDER BY sort_order", (ch[0],)).fetchall()
                _log(f"  - Chapter '{ch[1]}' ({ch[0]}): Found {len(topics)} topics.")
                chapters_data.append({
                    "id": ch[0],
                    "title": ch[1],
                    "topics": [{"id": t[0], "title": t[1], "type": t[2], "page": t[3]} for t in topics]
                })
        
        total_topics = sum(len(c["topics"]) for c in chapters_data)
        if total_topics == 0:
            _log(f"WARNING: ZERO topics found for {course_id}. Build ending immediately.")
            return
 
        _log(f"Phase 2: Proceeding with enrichment for {total_topics} topics across {len(chapters_data)} chapters...")
        
        # ── HELPER: SURGICAL CONTEXT ──
        def get_surgical_context(page_num, full_text, topic_title=""):
            if not full_text: return ""
            if page_num and page_num in page_chunks:
                context_chunk = ""
                for p in range(page_num, page_num + 3):
                    if p in page_chunks:
                        context_chunk += f"\n[Page {p}]\n{page_chunks[p]}\n"
                if len(context_chunk) > 100: return context_chunk
            
            if page_num:
                p_marker = f"Page {page_num}"
                idx = full_text.find(p_marker)
                if idx != -1: return full_text[max(0, idx-200):idx+8000]
            
            if topic_title and len(topic_title) > 3:
                import re
                h_pattern = rf"(?:^|\n)#+\s*.*{re.escape(topic_title)}.*"
                h_match = re.search(h_pattern, full_text, re.IGNORECASE)
                if h_match: return full_text[max(0, h_match.start()-200):h_match.start()+8000]
            
            return full_text[:8000]
 
        def process_topic_task(t_id, t_title, t_type, language, level, course_id, source_text=None, material_language="en", unit_index=None, unit_total=None, topics_completed=0, unit_title="", unit_topics=()):
            from services.ai_engine import generate_full_lesson, _is_substantive_lesson, synthesize_substantive_lesson
            try:
                with db_connection() as db:
                    db.execute("UPDATE courses SET build_message = ? WHERE id = ? AND is_building = 1", (f"Ders üretiliyor: {t_title}", course_id))
                    db.commit()
                bump_version()
            except Exception: pass
            lesson = None
            try:
                lesson = generate_full_lesson(
                    t_title, t_type, language, 5, level,
                    source_text=source_text, material_language=material_language,
                    unit_index=unit_index, unit_total=unit_total,
                    topics_completed=topics_completed,
                    unit_title=unit_title, unit_topics=unit_topics,
                )
            except Exception as gen_err:
                _log(f"[TOPIC-TASK] generate_full_lesson failed for '{t_title}': {gen_err}")

            if isinstance(lesson, dict) and lesson.get("_review_required"):
                _log(
                    f"[TOPIC-TASK] Topic '{t_title}' reached review-notice state; "
                    "retrying this topic once before persistence."
                )
                try:
                    retry = generate_full_lesson(
                        t_title, t_type, language, 5, level,
                        source_text=source_text, material_language=material_language,
                        unit_index=unit_index, unit_total=unit_total,
                        topics_completed=topics_completed,
                        unit_title=unit_title, unit_topics=unit_topics,
                    )
                    if isinstance(retry, dict) and not retry.get("_review_required"):
                        lesson = retry
                except Exception as retry_err:
                    _log(f"[TOPIC-TASK] targeted retry failed for '{t_title}': {retry_err}")

            if not lesson or not isinstance(lesson, dict) or not _is_substantive_lesson(lesson):
                _log(f"[TOPIC-TASK] Topic '{t_title}' produced empty/non-substantive lesson. Keeping explicit review notice; publication gate will not serve it.")
                lesson = synthesize_substantive_lesson(t_title, t_type, language, level, source_text=source_text, material_language=material_language)

            return {"content": lesson, "t_id": t_id, "t_title": t_title}
 
        # 20 concurrent workers — modestly reduce 30-topic tail latency without changing work volume
        max_workers = int(os.getenv("PIPELINE_MAX_WORKERS", "20"))

        queued = []
        _unit_total = len(chapters_data)
        _seen = 0
        for _u_idx, ch in enumerate(chapters_data, 1):
            _unit_title = str(ch.get("title") or "")
            _unit_topics = tuple(
                str(t.get("title") or "") for t in (ch.get("topics") or [])
                if isinstance(t, dict) and str(t.get("title") or "").strip()
            )
            for topic in ch.get("topics", []):
                if len(queued) >= MAX_TOTAL_TOPICS:
                    break
                stext = get_surgical_context(topic.get("page"), source_markdown_content, topic_title=topic.get("title"))
                # `topics_completed` is this topic's position in the course, which
                # is what the assessment language budget needs: a lesson early in
                # unit 1 may only phrase its questions out of what unit 1 has
                # taught by then.
                queued.append((
                    topic.get("id"), topic.get("title"), topic.get("type"), stext,
                    _u_idx, _unit_total, _seen, _unit_title, _unit_topics,
                ))
                _seen += 1
        topic_count = len(queued)

        # Every topic in a class is generated from a byte-identical system prompt:
        # it varies only by language, level and institution, which are fixed for
        # the class. That prefix is by far the largest input the pipeline pays for,
        # and providers serve a repeated prefix from cache at a fraction of the
        # price — but only once they have served it at least once. Firing all the
        # topics at the same instant guarantees none of them can benefit, because
        # no request has returned when the rest are dispatched. Letting the first
        # topic land before the others go out changes nothing about what is
        # generated; it only stops the class from paying full price for the same
        # prefix N times. The cost is one lesson's latency, once per build, and
        # the ledger's cache-hit ratio reports whether it worked.
        prime_first = (
            str(os.getenv("AULAAI_PREFIX_CACHE_PRIME", "1")).strip().lower() not in ("0", "false", "off", "no")
            and topic_count >= 3
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_topic = {}

            def _submit(entry):
                (
                    t_id, t_title, t_type, stext, u_idx, u_total, done_before,
                    unit_title, unit_topics,
                ) = entry
                fut = executor.submit(
                    process_topic_task, t_id, t_title, t_type, language, level, course_id,
                    source_text=stext, material_language=material_language,
                    unit_index=u_idx, unit_total=u_total, topics_completed=done_before,
                    unit_title=unit_title, unit_topics=unit_topics,
                )
                future_to_topic[fut] = t_title
                return fut

            rest = queued
            if prime_first:
                first_future = _submit(queued[0])
                rest = queued[1:]
                _log(f"Phase 2: priming shared prompt prefix with '{queued[0][1]}' before fan-out.")
                # Publish the priming wait as the real stage it is. Generating this
                # first lesson takes as long as any other, and until now the build
                # sat at the curriculum-ready figure for its whole duration with no
                # message, so a minute or more of genuine work looked like a frozen
                # bar. The topic count is announced here too, so the interval reports
                # what it is working towards instead of an unexplained pause.
                with db_connection() as db:
                    db.execute(
                        "UPDATE courses SET total_steps = ?, progress = 0, build_stage = 'priming', build_message = ? WHERE id = ? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')",
                        (topic_count, f"İlk ders üretiliyor ({topic_count} ders hazırlanacak)...", course_id, gen_id, gen_id),
                    )
                    db.commit()
                bump_version()
                # Wait, but never let a slow or hung first topic hold the build:
                # the timeout is a ceiling, not a requirement, and the remaining
                # topics are dispatched either way.
                concurrent.futures.wait([first_future], timeout=float(os.getenv("AULAAI_PREFIX_CACHE_PRIME_TIMEOUT", "240")))
            for entry in rest:
                _submit(entry)

            # ANNOUNCE TOTAL STEPS & STAGE: So the progress bar knows its target
            with db_connection() as db:
                db.execute("UPDATE courses SET total_steps = ?, progress = 0, build_stage = 'enriching', build_message = ? WHERE id = ? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')", (topic_count, f"Dersler üretilmeye başlandı ({topic_count} ders)...", course_id, gen_id, gen_id))
                db.commit()
            bump_version()

            # ── PROGRESS & DB UPDATES (CENTRALIZED) ──
            completed = 0
            for future in concurrent.futures.as_completed(future_to_topic):
                completed += 1
                try:
                    res = future.result()
                    t_title = res.get("t_title", "Topic")
                    t_content = res.get("content")
                    if not t_content or not isinstance(t_content, dict) or not t_content.get("pages"):
                        from services.ai_engine import synthesize_substantive_lesson
                        t_content = synthesize_substantive_lesson(t_title, "concept", language, level, material_language=material_language)
                    build_msg = f"Ders tamamlandı ({completed}/{topic_count}): {t_title}"
                    with db_connection() as db:
                        db.execute("UPDATE topics SET content = ? WHERE id = ?", (json.dumps(t_content, ensure_ascii=False), res["t_id"]))
                        db.execute("UPDATE courses SET progress = ?, build_stage = 'enriching', build_message = ? WHERE id = ? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')", (completed, build_msg, course_id, gen_id, gen_id))
                        db.commit()
                    _log(f"Enrichment: {completed}/{topic_count} DONE ({t_title}).")
                    bump_version()
                except Exception as e:
                    _log(f"Topic Error: {e}")
                    failed_title = future_to_topic.get(future, "Topic")
                    try:
                        from services.ai_engine import synthesize_substantive_lesson
                        fallback_content = synthesize_substantive_lesson(failed_title, "concept", language, level, material_language=material_language)
                        with db_connection() as db:
                            db.execute("UPDATE topics SET content = ? WHERE title = ? AND chapter_id IN (SELECT id FROM chapters WHERE course_id = ?)", (json.dumps(fallback_content, ensure_ascii=False), failed_title, course_id))
                            db.commit()
                    except Exception as db_err:
                        _log(f"Failed fallback commit for {failed_title}: {db_err}")

        # ── PHASE 2a.5: PHONETIC COMPLETENESS ──
        # Material generation occasionally returns a real vocabulary row with an
        # empty phonetic field. Repair only those blanks, once per class, without
        # touching any existing transcription.
        try:
            _repair_missing_phonetics(course_id, language)
        except Exception as phon_err:
            _log(f"[PHONETIC-COMPLETE] repair skipped: {phon_err}")

        # ── PHASE 2b: UNIT ASSESSMENTS ──
        # Every unit closes with a ten-question assessment drawn from that unit
        # and nothing else. It runs here, after the unit's topics exist, because
        # it is built from the material the learner was actually shown rather
        # than from the curriculum's intention. Units are independent, so they
        # are generated concurrently; a unit that cannot produce ten publishable
        # questions publishes none, and the build continues.
        try:
            _build_unit_assessments(course_id, language, level, material_language, gen_id)
        except Exception as ua_err:
            _log(f"[UNIT-ASSESSMENT] phase skipped: {ua_err}")

        # ── PHASE 2c: FAIL-CLOSED PUBLICATION QUALITY GATE ──
        # Generation is cheap and broad; review is narrow and independent.
        # Every unit is reviewed by Gemini 3.7 Flash, all ten assessment questions
        # are adversarially checked, and deterministic publication integrity verifies rules,
        # IPA and MCQs. A failed/incomplete review aborts publication rather
        # than silently shipping a classroom we did not actually verify.
        certified = _run_publication_until_ready(
            course_id, language, level, material_language,
            gen_id=gen_id, progress=topic_count, total_steps=topic_count,
        )

        _log(f"Phase 2 Complete for {course_id}.")
        if generation_cost is not None:
            try:
                generation_cost.emit_summary()
            except Exception as cost_err:
                _log(f"Cost summary unavailable: {cost_err}")
        _log("Bilingual post-processor disabled: using persisted bilingual lesson fields from the AI engine.")
        # _run_publication_until_ready does not return until the persisted rows
        # themselves pass the publication proof and mark_ready succeeds. A
        # content refusal is therefore internal retry feedback, not a terminal
        # user-visible state.
        _log(f"[PUBLICATION] READY certified from persisted rows: "
             f"topics={certified['topics']} mcqs={certified['mcqs']} "
             f"unit_assessment_questions={certified['unit_assessment_questions']}")
        from database import enroll_permanent_students_in_course
        enroll_permanent_students_in_course(course_id)
        bump_version()

    except Exception as e:
        _log(f"FATAL Phase 2: {e}")
        traceback.print_exc()
        with db_connection() as db:
            db.execute("UPDATE courses SET is_building = 0, build_stage = 'failed', build_message = ? WHERE id = ?", (f"Build error: {str(e)[:120]}", course_id))
            db.commit()



def _repair_missing_phonetics(course_id, language):
    """Fill genuinely blank vocabulary-table phonetics in one conditional batch.

    Existing non-empty transcriptions are authoritative and never overwritten.
    Exact input-term echoing prevents the completion call from mutating spelling.
    """
    with db_connection() as db:
        rows = db.execute(
            "SELECT id, content FROM topics WHERE chapter_id IN "
            "(SELECT id FROM chapters WHERE course_id = ?) "
            "AND (type IS NULL OR type != ?)",
            (course_id, UNIT_ASSESSMENT_TYPE),
        ).fetchall()

    parsed = []
    missing = {}
    examples = []

    def scan(container):
        if not isinstance(container, list):
            return
        for entry in container:
            if not isinstance(entry, dict):
                continue
            term = str(entry.get("term") or entry.get("word") or entry.get("target") or "").strip()
            phonetic = str(entry.get("phonetic") or "").strip()
            if not term or not any(ch.isalpha() for ch in term):
                continue
            if phonetic:
                if len(examples) < 16:
                    examples.append((term, phonetic))
            else:
                # Keep an explicit typed slot so the semantic quality gate can
                # repair it later even if the batch completion returns no safe
                # transcription for this term.
                entry.setdefault("phonetic", "")
                missing.setdefault(term, []).append(entry)

    for topic_id, raw in rows:
        try:
            content = json.loads(raw or "{}") if isinstance(raw, str) else (raw or {})
        except Exception:
            continue
        if not isinstance(content, dict):
            continue
        parsed.append((topic_id, content))
        for page in content.get("pages") or []:
            if not isinstance(page, dict):
                continue
            for key in ("items", "vocabulary", "words"):
                scan(page.get(key))

    if not missing:
        _log("[PHONETIC-COMPLETE] no blank phonetic rows.")
        return 0

    terms = list(missing)[:160]
    calibration = "\n".join(f"- {term}: {phon}" for term, phon in examples[:12]) or "(none)"
    prompt = f"""Fill missing phonetic transcriptions for a {language} language course.
Return ONLY valid JSON in this exact shape: {{"items":[{{"term":"EXACT INPUT TERM","phonetic":"[standard IPA]"}}]}}.
Preserve each term exactly. Return one item per input term. `phonetic` must be a pronunciation transcription, never a translation or a letter name. Match the IPA convention shown by the existing class examples. If a term genuinely has no spoken pronunciation, return an empty string.
Existing class examples:\n{calibration}\n\nTerms missing phonetics:\n""" + "\n".join(f"- {term}" for term in terms)

    response = _call_ai(
        [{"role": "user", "content": prompt}],
        max_tokens=min(3600, 180 + 28 * len(terms)),
        temperature=0.0,
        json_mode=True,
        allow_fallback=True,
        cost_stage="phonetic_completion",
        cost_subject=f"course {course_id}",
    )
    payload = response.get("items") if isinstance(response, dict) else response
    if not isinstance(payload, list):
        _log(f"[PHONETIC-COMPLETE] provider returned no usable mapping for {len(terms)} blank terms.")
        return 0

    allowed = set(terms)
    mapping = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        phonetic = str(item.get("phonetic") or "").strip()
        if term in allowed and phonetic and len(phonetic) <= 120:
            # Never persist look-alike Unicode as if it were valid IPA. The
            # publication reviewer can correct a rejected transcription from
            # the word itself; this batch step may only store already-clean IPA.
            from services.authoring import schema as _authoring_schema
            if not _authoring_schema.stray_ipa_codepoints(phonetic):
                mapping[term] = phonetic
            else:
                _log(f"[PHONETIC-COMPLETE] rejected non-IPA completion for {term!r}: {phonetic!r}")

    filled = 0
    for term, entries in missing.items():
        phonetic = mapping.get(term)
        if not phonetic:
            continue
        for entry in entries:
            if not str(entry.get("phonetic") or "").strip():
                entry["phonetic"] = phonetic
                filled += 1

    changed_topics = 0
    with db_connection() as db:
        for topic_id, content in parsed:
            current = db.execute("SELECT content FROM topics WHERE id = ?", (topic_id,)).fetchone()
            serialized = json.dumps(content, ensure_ascii=False)
            if current and current[0] != serialized:
                db.execute("UPDATE topics SET content = ? WHERE id = ?", (serialized, topic_id))
                changed_topics += 1
        db.commit()

    _log(f"[PHONETIC-COMPLETE] filled {filled} blank row(s) across {changed_topics} topic(s) in one batch call.")
    if filled:
        bump_version()
    return filled



def _run_publication_until_ready(course_id, language, level, material_language,
                                 gen_id=None, progress=None, total_steps=None):
    """Keep publication refusals inside the machine until the classroom passes.

    A QualityGateError is not a product state. It is validator feedback for the
    next repair attempt. The exact exception text — the same text that used to
    become `Publication refused: ...` — is fed verbatim into the next targeted
    repair prompt. The user only sees an in-progress quality-review state.

    This loop intentionally has no content-retry ceiling. Every candidate still
    has to pass the unchanged quality gate and the persisted-row proof before
    READY, so persistence/retry replaces terminal refusal without weakening any
    validator.
    """
    from services.authoring import quality_gate as Q
    from services.authoring import publication_state as PS

    retry_attempt = 0
    while True:
        try:
            _run_publication_quality_gate(
                course_id, language, level, material_language, gen_id=gen_id
            )

            # Do the persisted proof BEFORE mark_ready. mark_ready records a
            # refusal as build_stage='failed' on exception; proving first keeps
            # transient repairable content failures invisible to the user.
            PS.verify_publishable(course_id)
            return PS.mark_ready(
                course_id, gen_id, progress=progress, total_steps=total_steps
            )

        except (Q.QualityGateError, PS.NotPublishable) as failure:
            retry_attempt += 1
            publication_error = str(failure)
            _log(
                f"[QUALITY-SELF-HEAL] retry {retry_attempt} intercepted "
                f"publication refusal: {publication_error}"
            )

            # Never surface the refusal in the course card. Logs retain the full
            # diagnostic; the UI only reports that quality repair is continuing.
            with db_connection() as db:
                db.execute(
                    "UPDATE courses SET is_building=1, build_stage='quality_review', "
                    "build_message=? WHERE id=? AND "
                    "(generation_id=? OR generation_id IS NULL OR ?='LEGACY')",
                    (
                        f"Quality review: automatic repair retry {retry_attempt}",
                        course_id, gen_id, gen_id,
                    ),
                )
                db.commit()
            bump_version()

            try:
                units = PS.load_persisted_units(course_id)
                # Fresh bounded budget per feedback attempt. The outer retry is
                # unbounded; a single bad provider response cannot reserve an
                # unbounded amount at once.
                feedback_budget = Q.ReviewBudget(
                    float(os.getenv("QUALITY_SELF_HEAL_ATTEMPT_BUDGET", "0.18"))
                )
                changed = Q.repair_publication_refusal_feedback(
                    units=units,
                    language=language,
                    level=level,
                    track=material_language,
                    publication_error=publication_error,
                    retry_attempt=retry_attempt,
                    budget=feedback_budget,
                )

                if changed:
                    with db_connection() as db:
                        for unit in units:
                            for topic in unit.get("topics") or []:
                                db.execute(
                                    "UPDATE topics SET content=? WHERE id=?",
                                    (
                                        json.dumps(
                                            topic.get("content") or {},
                                            ensure_ascii=False,
                                        ),
                                        topic.get("id"),
                                    ),
                                )
                        db.commit()
                    bump_version()
                    _log(
                        f"[QUALITY-SELF-HEAL] retry {retry_attempt} persisted "
                        f"{changed} feedback-driven patch(es); rerunning the "
                        f"full publication proof."
                    )
                else:
                    _log(
                        f"[QUALITY-SELF-HEAL] retry {retry_attempt} produced no "
                        f"safe patch; the next attempt will receive the same "
                        f"authoritative refusal plus a new retry ordinal."
                    )

            except Q.QualityGateError as retry_failure:
                # Provider/schema/budget failures during the repair prompt are
                # retry transport failures, not publication verdicts.
                _log(
                    f"[QUALITY-SELF-HEAL] retry {retry_attempt} repair call "
                    f"did not complete: {retry_failure}"
                )
            except PS.NotPublishable as retry_failure:
                _log(
                    f"[QUALITY-SELF-HEAL] retry {retry_attempt} could not load "
                    f"a publishable-shaped snapshot yet: {retry_failure}"
                )

            # Avoid a hot spin if the provider repeatedly gives no usable patch.
            time.sleep(min(5.0, 0.35 * retry_attempt))


def _run_publication_quality_gate(course_id, language, level, material_language, gen_id=None,
                                  generation_spend_override=None):
    """Review, patch and re-audit every learner-visible field before READY."""
    from services.authoring import quality_gate as Q

    # Keep the product's $0.60/classroom promise across generation AND review,
    # not as two unrelated ceilings. Phase 2's measured provider ledger already
    # contains lessons/assessments. Reserve two cents for the earlier curriculum
    # call (the phase-2 ledger is reset after curriculum planning), then give the
    # semantic gate only the smaller of its normal allowance and real headroom.
    generation_spend = 0.0
    if generation_spend_override is not None:
        generation_spend = max(0.0, float(generation_spend_override))
    else:
        try:
            from services import generation_cost as _generation_cost
            generation_spend = float(
                (_generation_cost.summary().get("total") or {}).get("cost") or 0.0
            )
        except Exception:
            pass
    review_headroom = 0.60 - generation_spend - 0.02
    if review_headroom <= 0:
        raise Q.QualityGateError(
            f"no publication-review budget remains: generation already spent "
            f"${generation_spend:.4f} before the curriculum reserve"
        )
    # QUALITY_REVIEW_CEILING_USD is the historical/nominal target, not a
    # second hard stop inside the already-enforced $0.60 classroom ceiling.
    # The quality pipeline now includes semantic review, risk review, assessment
    # proof and bounded transport recovery; refusing a required retry merely
    # because it crosses the old $0.22 sub-cap wastes the calls already paid for.
    # Use the real class-wide headroom as the hard publication-review ceiling.
    budget = Q.ReviewBudget(review_headroom)
    _log(
        f"[QUALITY-GATE] generation=${generation_spend:.4f}; "
        f"review hard ceiling=${budget.ceiling:.4f}; "
        f"nominal review target=${Q.QUALITY_REVIEW_CEILING_USD:.4f}; "
        f"curriculum reserve=$0.0200"
    )
    with db_connection() as db:
        chapters = db.execute(
            "SELECT id, title, number FROM chapters WHERE course_id = ? ORDER BY number",
            (course_id,),
        ).fetchall()
        units = []
        for chapter in chapters:
            rows = db.execute(
                "SELECT id, title, type, content, sort_order FROM topics "
                "WHERE chapter_id = ? ORDER BY sort_order",
                (chapter[0],),
            ).fetchall()
            lesson_topics = []
            assessment_topic = None
            all_topics = []
            for row in rows:
                try:
                    content = json.loads(row[3] or "{}") if isinstance(row[3], str) else (row[3] or {})
                except Exception as parse_err:
                    # Never substitute an empty lesson for one we cannot read.
                    # An empty dict audits perfectly clean, passes every check
                    # below, and is then written back over the real row by the
                    # persist step at the end of this function — silently
                    # emptying a topic and calling the course publishable.
                    raise Q.QualityGateError(
                        f"unreadable stored content for topic {row[0]!r} "
                        f"({row[1]!r}): {parse_err}"
                    )
                topic = {
                    "id": row[0], "title": row[1], "type": row[2],
                    "content": content,
                    "is_assessment": row[2] == UNIT_ASSESSMENT_TYPE,
                }
                all_topics.append(topic)
                if topic["is_assessment"]:
                    assessment_topic = topic
                else:
                    lesson_topics.append(topic)
            if lesson_topics:
                units.append({
                    "chapter_id": chapter[0], "title": chapter[1],
                    "number": chapter[2], "lessons": lesson_topics,
                    "assessment": assessment_topic, "topics": all_topics,
                })

    if not units:
        raise Q.QualityGateError("publication gate found no units")
    if any(unit.get("assessment") is None for unit in units):
        missing = [unit["title"] for unit in units if unit.get("assessment") is None]
        raise Q.QualityGateError(
            "publication gate refuses a course with missing unit assessment(s): "
            + ", ".join(missing)
        )

    # Cheap fail-fast pass: deterministic lesson blockers are exact and known
    # before broad semantic review. Repair them first, prove them clean, and
    # persist that proven correction as a checkpoint. A provider failure here
    # now costs one tiny repair call instead of repeating the full ~$0.12 review.
    preflight_units = [{"title": u["title"], "topics": u["topics"]} for u in units]
    preflight_patches = Q.repair_deterministic_preflight(
        units=preflight_units,
        language=language,
        level=level,
        track=material_language,
        budget=budget,
    )
    if preflight_patches:
        with db_connection() as db:
            for unit in units:
                for topic in unit["lessons"]:
                    db.execute(
                        "UPDATE topics SET content = ? WHERE id = ?",
                        (json.dumps(topic["content"], ensure_ascii=False), topic["id"]),
                    )
            db.execute(
                "UPDATE courses SET build_stage='quality_review', build_message=? WHERE id=?",
                ("Quality review: deterministic repairs checkpointed", course_id),
            )
            db.commit()
        bump_version()
        _log(
            f"[QUALITY-GATE] preflight checkpoint persisted "
            f"{preflight_patches} deterministic repair patch(es)."
        )

    # Bilingual completeness is proven and checkpointed BEFORE broad review.
    # It used to be a tail check inside lesson review, so a gap the broad
    # reviewer happened to fill only reached the database if the ENTIRE gate
    # passed. When a later unrelated failure aborted the run, the persisted
    # snapshot stayed at preflight level and the outer publication validation
    # refused the course over a counterpart that had in fact been repaired.
    def _checkpoint_bilingual_topic(topic, patch_count):
        # Topic-level transaction: never persist a half-repaired topic, but once
        # this exact topic is proven complete, keep that proof even if a later
        # topic/provider call fails.
        incomplete = Q.missing_bilingual_pairs(topic["content"])
        if incomplete:
            raise Q.QualityGateError(
                f"{topic['title']}: refusing to checkpoint incomplete "
                f"EN/TR field pairs: " + ", ".join(incomplete[:8])
            )
        with db_connection() as db:
            db.execute(
                "UPDATE topics SET content = ? WHERE id = ?",
                (json.dumps(topic["content"], ensure_ascii=False), topic["id"]),
            )
            db.execute(
                "UPDATE courses SET build_stage='quality_review', build_message=? WHERE id=?",
                (f"Quality review: bilingual topic checkpointed — {topic['title']}", course_id),
            )
            db.commit()
        bump_version()
        _log(
            f"[QUALITY-GATE] bilingual topic checkpoint persisted "
            f"{patch_count} repair(s): {topic['title']}"
        )

    bilingual_patches = Q.repair_bilingual_preflight(
        units=preflight_units,
        language=language,
        level=level,
        track=material_language,
        budget=budget,
        on_topic_complete=_checkpoint_bilingual_topic,
    )
    if bilingual_patches:
        _log(
            f"[QUALITY-GATE] bilingual preflight completed "
            f"{bilingual_patches} exact counterpart repair(s)."
        )

    _log(
        f"[QUALITY-GATE] reviewing {len(units)} unit(s) with {Q.REVIEW_MODEL}; "
        f"targeted repairs use {Q.REPAIR_MODEL}."
    )
    lesson_patches = 0
    assessment_patches = 0

    # OpenRouter admission control can reject otherwise valid zero-cost calls
    # when several review requests start at once. Review-only retries are already
    # expensive, so prefer reliability over a short wall-clock win: one lesson
    # unit worker at a time. Assessment review is already serialized below.
    review_workers = 1

    def _review_lessons(unit):
        return Q.review_unit_lessons(
            unit_title=unit["title"], topics=unit["lessons"],
            language=language, level=level, track=material_language,
            budget=budget,
            unit_topic_titles=[t.get("title") for t in unit["lessons"]],
        )

    def _review_risks(unit):
        return Q.review_unit_risk_claims(
            unit_title=unit["title"], topics=unit["lessons"],
            language=language, level=level, track=material_language,
            budget=budget,
        )

    def _review_assessment(unit):
        return Q.review_unit_assessment(
            unit_title=unit["title"], assessment_topic=unit["assessment"],
            lesson_topics=unit["lessons"], language=language, level=level,
            track=material_language, budget=budget,
        )

    def _review_rationales(unit):
        return Q.review_unit_mcq_rationales(
            unit_title=unit["title"], topics=unit["topics"],
            language=language, level=level, track=material_language,
            budget=budget,
        )

    def _review_complex_notation(unit):
        return Q.review_unit_complex_notation(
            unit_title=unit["title"], topics=unit["lessons"],
            language=language, level=level, budget=budget,
        )

    # Six units are independent snapshots, so running only three workers paid
    # two full latency waves in every semantic stage without improving proof
    # quality. Default to one worker per normal six-unit classroom. The hard
    # ceiling, isolated snapshots, serial merge, budget reservations and 429
    # backoff remain unchanged.
    review_workers = max(1, min(8, int(os.getenv("QUALITY_REVIEW_WORKERS", "6"))))
    _log(
        f"[QUALITY-GATE] lesson review running with {review_workers} isolated "
        f"unit snapshot worker(s); merge remains serial."
    )

    def _lesson_complete(done, total, unit):
        with db_connection() as db:
            db.execute(
                "UPDATE courses SET build_stage='quality_review', build_message=? WHERE id=?",
                (f"Quality review: lessons {done}/{total}", course_id),
            )
            db.commit()

    lesson_patches += _run_quality_units_parallel_snapshots(
        units=units,
        reviewer=_review_lessons,
        stage="lesson review",
        on_complete=_lesson_complete,
        quality_error_cls=Q.QualityGateError,
        max_workers=review_workers,
    )
    _log(
        f"[QUALITY-BUDGET] after lessons spent=${budget.spent:.4f}; "
        f"remaining=${max(0.0, budget.ceiling - budget.spent):.4f}"
    )

    risk_patches = 0
    _log(
        f"[QUALITY-GATE] pedagogical-risk review running with {review_workers} "
        f"isolated unit snapshot worker(s)."
    )
    with db_connection() as db:
        db.execute(
            "UPDATE courses SET build_stage='quality_review', build_message=? WHERE id=?",
            (f"Quality review: pedagogical risks 0/{len(units)}", course_id),
        )
        db.commit()
    def _risk_complete(done, total, unit):
        with db_connection() as db:
            db.execute(
                "UPDATE courses SET build_stage='quality_review', build_message=? WHERE id=?",
                (f"Quality review: pedagogical risks {done}/{total}", course_id),
            )
            db.commit()

    risk_patches += _run_quality_units_parallel_snapshots(
        units=units,
        reviewer=_review_risks,
        stage="risk review",
        on_complete=_risk_complete,
        quality_error_cls=Q.QualityGateError,
        max_workers=review_workers,
    )
    _log(
        f"[QUALITY-BUDGET] after risk review spent=${budget.spent:.4f}; "
        f"remaining=${max(0.0, budget.ceiling - budget.spent):.4f}"
    )

    complex_notation_patches = 0
    _log(
        f"[QUALITY-GATE] complex pronunciation review running with "
        f"{review_workers} isolated unit snapshot worker(s)."
    )
    with db_connection() as db:
        db.execute(
            "UPDATE courses SET build_stage='quality_review', build_message=? WHERE id=?",
            (f"Quality review: pronunciation 0/{len(units)}", course_id),
        )
        db.commit()
    def _notation_complete(done, total, unit):
        with db_connection() as db:
            db.execute(
                "UPDATE courses SET build_stage='quality_review', build_message=? WHERE id=?",
                (f"Quality review: pronunciation {done}/{total}", course_id),
            )
            db.commit()

    complex_notation_patches += _run_quality_units_parallel_snapshots(
        units=units,
        reviewer=_review_complex_notation,
        stage="complex pronunciation review",
        on_complete=_notation_complete,
        quality_error_cls=Q.QualityGateError,
        max_workers=review_workers,
    )
    _log(
        f"[QUALITY-BUDGET] after notation review spent=${budget.spent:.4f}; "
        f"remaining=${max(0.0, budget.ceiling - budget.spent):.4f}"
    )

    # Assessment payloads are the largest review calls. Run them one at a time:
    # concurrent worst-case budget reservations can reject a healthy third unit
    # even though the first two calls release their reservations seconds later.
    assessment_workers = 1  # hard invariant: large assessment reservations stay serial
    _log(
        "[QUALITY-GATE] assessment review running serially with fail-fast unit boundaries. "
        "It remains serial to preserve worst-case budget headroom for large structured payloads."
    )
    with db_connection() as db:
        db.execute(
            "UPDATE courses SET build_stage='quality_review', build_message=? WHERE id=?",
            (f"Quality review: assessments 0/{len(units)}", course_id),
        )
        db.commit()

    def _assessment_complete(done, total, unit):
        with db_connection() as db:
            db.execute(
                "UPDATE courses SET build_stage='quality_review', build_message=? WHERE id=?",
                (f"Quality review: assessments {done}/{total}", course_id),
            )
            db.commit()

    assessment_patches += _run_quality_units_serially(
        units=units,
        reviewer=_review_assessment,
        stage="assessment review",
        on_complete=_assessment_complete,
        quality_error_cls=Q.QualityGateError,
    )
    _log(
        f"[QUALITY-BUDGET] after assessments spent=${budget.spent:.4f}; "
        f"remaining=${max(0.0, budget.ceiling - budget.spent):.4f}"
    )

    # Ground rationales after assessment editing so the answer key is checked
    # against the final stem/options state. One unit call covers both lesson and
    # assessment MCQs; this widens coverage without adding calls versus the old
    # lesson-only rationale stage.
    rationale_patches = 0
    _log(
        f"[QUALITY-GATE] lesson + assessment rationale grounding running with "
        f"{review_workers} isolated unit snapshot worker(s)."
    )
    with db_connection() as db:
        db.execute(
            "UPDATE courses SET build_stage='quality_review', build_message=? WHERE id=?",
            (f"Quality review: rationale grounding 0/{len(units)}", course_id),
        )
        db.commit()
    def _rationale_complete(done, total, unit):
        with db_connection() as db:
            db.execute(
                "UPDATE courses SET build_stage='quality_review', build_message=? WHERE id=?",
                (f"Quality review: rationale grounding {done}/{total}", course_id),
            )
            db.commit()

    rationale_patches += _run_quality_units_parallel_snapshots(
        units=units,
        reviewer=_review_rationales,
        stage="rationale grounding review",
        on_complete=_rationale_complete,
        quality_error_cls=Q.QualityGateError,
        max_workers=review_workers,
    )
    _log(
        f"[QUALITY-BUDGET] after rationale grounding spent=${budget.spent:.4f}; "
        f"remaining=${max(0.0, budget.ceiling - budget.spent):.4f}"
    )

    reviewed_units = [{"title": u["title"], "topics": u["topics"]} for u in units]
    with db_connection() as db:
        db.execute(
            "UPDATE courses SET build_stage='quality_review', build_message=? WHERE id=?",
            ("Quality review: final verification", course_id),
        )
        db.commit()

    # There is no second semantic verifier. Gemini already reviewed every unit;
    # deterministic publication integrity is the authority. If it can name a
    # repairable learner-visible blocker, give that exact blocker one bounded
    # Gemini repair pass, then prove the contract again.
    final_repair_patches = Q.repair_final_publication_blockers(
        units=reviewed_units,
        language=language, level=level, track=material_language, budget=budget,
    )
    if final_repair_patches:
        _log(f"[QUALITY-GATE] final targeted repair applied {final_repair_patches} patch(es).")

    phonetic_conflict_patches = Q.repair_cross_topic_phonetic_conflicts(
        units=reviewed_units,
        language=language,
        level=level,
        track=material_language,
        budget=budget,
    )
    if phonetic_conflict_patches:
        _log(
            f"[QUALITY-GATE] phonetic-conflict repair applied "
            f"{phonetic_conflict_patches} patch(es)."
        )

    duplicate_stem_patches = Q.repair_duplicate_mcq_stems(
        units=reviewed_units,
        language=language,
        level=level,
        track=material_language,
        budget=budget,
    )
    if duplicate_stem_patches:
        _log(
            f"[QUALITY-GATE] duplicate-stem repair applied "
            f"{duplicate_stem_patches} patch(es)."
        )

    # Prove that the exact post-review objects still contain ten questions per
    # unit, complete EN/TR pairs, no duplicate MCQ stems, and nothing either
    # renderer would silently discard. Only then may the database ever reach READY.
    integrity = Q.validate_publication_integrity(
        units=reviewed_units, language=language, track=material_language,
    )
    _log(
        f"[QUALITY-INTEGRITY] PASS topics={integrity['topics']} "
        f"mcqs={integrity['mcqs']} "
        f"unit_assessment_questions={integrity['unit_assessment_questions']}"
    )

    # Persist only after the entire gate passes. If any reviewer fails, no
    # partially edited mixture is written and the outer build marks the class
    # failed instead of ready.
    with db_connection() as db:
        for unit in units:
            for topic in unit["topics"]:
                db.execute(
                    "UPDATE topics SET content = ? WHERE id = ?",
                    (json.dumps(topic["content"], ensure_ascii=False), topic["id"]),
                )
        db.execute(
            "UPDATE courses SET build_stage = 'quality_review', build_message = ? "
            "WHERE id = ? AND (generation_id = ? OR generation_id IS NULL OR ? = 'LEGACY')",
            ("Yayın kalitesi doğrulandı.", course_id, gen_id, gen_id),
        )
        db.commit()
    bump_version()
    # Fold review spend back into the class-wide observable ledger so the
    # production cost summary includes the quality stage rather than stopping at
    # the author model.
    try:
        from services import generation_cost as _generation_cost
        for row in budget.calls:
            _generation_cost.record_call(
                stage=_generation_cost.STAGE_CLAIM_REVIEW,
                model=str(row.get("model") or ""),
                prompt_tokens=int(row.get("input_tokens") or 0),
                completion_tokens=int(row.get("output_tokens") or 0),
                cost=float(row.get("cost") or 0.0),
                subject=str(row.get("stage") or "publication_review"),
            )
    except Exception:
        pass
    _log(
        f"[QUALITY-GATE] PASS bilingual_patches={bilingual_patches} "
        f"lesson_patches={lesson_patches} "
        f"risk_patches={risk_patches} "
        f"rationale_patches={rationale_patches} "
        f"complex_notation_patches={complex_notation_patches} "
        f"assessment_patches={assessment_patches} "
        f"final_repair_patches={final_repair_patches} "
        f"phonetic_conflict_patches={phonetic_conflict_patches} "
        f"duplicate_stem_patches={duplicate_stem_patches}; "
        + Q.gate_summary(budget)
    )
    return {
        "bilingual_patches": bilingual_patches,
        "lesson_patches": lesson_patches,
        "risk_patches": risk_patches,
        "rationale_patches": rationale_patches,
        "complex_notation_patches": complex_notation_patches,
        "assessment_patches": assessment_patches,
        "final_repair_patches": final_repair_patches,
        "phonetic_conflict_patches": phonetic_conflict_patches,
        "duplicate_stem_patches": duplicate_stem_patches,
        "review_cost": budget.spent,
    }


UNIT_ASSESSMENT_TYPE = "unit_assessment"


def _build_unit_assessments(course_id, language, level, material_language, gen_id=None):
    """Generate and persist the closing assessment for every unit in a course.

    Stored as a synthetic topic at the end of its chapter, carrying lesson-shaped
    `mcq` pages. That choice is deliberate: the reader, the outline, the PDF
    exporter and the navigation already know how to present a topic made of mcq
    pages, so an assessment appears at the end of every unit without a single
    renderer change. `type='unit_assessment'` keeps it identifiable, so the
    lecturer's topic pickers can exclude it from ordinary quiz sources.
    """
    from services.ai_engine import generate_unit_assessment
    from services.assessment_scope import UNIT_ASSESSMENT_COUNT

    with db_connection() as db:
        chapters = db.execute(
            "SELECT id, title, title_tr, number FROM chapters WHERE course_id = ? ORDER BY number", (course_id,)
        ).fetchall()
        units = []
        for ch in chapters:
            rows = db.execute(
                "SELECT id, title, content, sort_order FROM topics WHERE chapter_id = ? AND (type IS NULL OR type != ?) ORDER BY sort_order",
                (ch[0], UNIT_ASSESSMENT_TYPE),
            ).fetchall()
            topics = [{"id": r[0], "title": r[1], "content": r[2]} for r in rows if r[2]]
            max_sort = max([r[3] or 0 for r in rows], default=0)
            if topics:
                if len(ch) >= 4:
                    chapter_title_tr, chapter_number = ch[2] or ch[1], ch[3]
                else:
                    chapter_title_tr, chapter_number = ch[1], ch[2]
                units.append({"chapter_id": ch[0], "title": ch[1], "title_tr": chapter_title_tr, "number": chapter_number,
                              "topics": topics, "next_sort": max_sort + 1})

    if not units:
        return
    total_units = len(units)
    _log(f"[UNIT-ASSESSMENT] building {total_units} unit assessment(s) for {course_id}.")

    def _one(unit):
        try:
            return unit, generate_unit_assessment(
                unit_title=unit["title"], unit_topics=unit["topics"], language=language,
                level=level, material_language=material_language,
                unit_index=unit.get("number"), unit_total=total_units,
            )
        except Exception as exc:
            _log(f"[UNIT-ASSESSMENT] '{unit['title']}' failed: {exc}")
            return unit, []

    results = []
    workers = min(int(os.getenv("PIPELINE_MAX_WORKERS", "20")), max(1, total_units))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for unit, questions in pool.map(_one, units):
            results.append((unit, questions))

    for unit, questions in results:
        if len(questions) != UNIT_ASSESSMENT_COUNT:
            _log(f"[UNIT-ASSESSMENT] '{unit['title']}' produced {len(questions)}; skipped.")
            continue
        content = build_unit_assessment_content(unit["title"], questions, material_language, unit_title_tr=unit.get("title_tr"))
        title_en = unit_assessment_title(unit["title"], "en", unit_title_tr=unit.get("title_tr"))
        title_tr = unit_assessment_title(unit["title"], "tr", unit_title_tr=unit.get("title_tr"))
        with db_connection() as db:
            existing = db.execute(
                "SELECT id FROM topics WHERE chapter_id = ? AND type = ?",
                (unit["chapter_id"], UNIT_ASSESSMENT_TYPE),
            ).fetchone()
            payload = json.dumps(content, ensure_ascii=False)
            if existing:
                db.execute("UPDATE topics SET title = ?, title_tr = ?, content = ? WHERE id = ?",
                           (title_en, title_tr, payload, existing[0]))
            else:
                db.execute(
                    "INSERT INTO topics (id, chapter_id, type, title, title_tr, content, sort_order) VALUES (?,?,?,?,?,?,?)",
                    (_uid(), unit["chapter_id"], UNIT_ASSESSMENT_TYPE, title_en, title_tr, payload, unit["next_sort"]),
                )
            db.commit()
        _log(f"[UNIT-ASSESSMENT] '{unit['title']}' published {len(questions)} questions.")
    bump_version()


def unit_assessment_title(unit_title, material_language="tr", unit_title_tr=None):
    is_tr = str(material_language).casefold() == "tr"
    label = "Ünite Değerlendirmesi" if is_tr else "Unit Assessment"
    chosen = (unit_title_tr or unit_title) if is_tr else unit_title
    return f"{label}: {chosen}" if chosen else label


def build_unit_assessment_content(unit_title, questions, material_language="tr", unit_title_tr=None):
    """Lesson-shaped pages for the stored assessment topic.

    `stem_scope: target_complete` is what tells the publication boundary that the
    stem is a whole question in the taught language and owes no instructional
    localization — the assessment contract, declared rather than inferred.
    """
    is_tr = str(material_language).casefold() == "tr"
    pages = []
    for idx, q in enumerate(questions, 1):
        options = q.get("options") or ([q.get("answer")] + list(q.get("distractors") or []))
        pages.append({
            "type": "mcq",
            "stem_scope": "target_complete",
            "assessment_scope": "unit",
            "title": f"Question {idx}",
            "title_tr": f"Soru {idx}",
            "prompt": q.get("prompt", ""),
            "options": [o for o in options if str(o).strip()][:4],
            "answer": q.get("answer", ""),
            "distractors": list(q.get("distractors") or [])[:3],
            "explanation": q.get("why", ""),
            "explanation_tr": q.get("why_tr", ""),
            "topic_id": q.get("topic_id"),
        })
    heading_en = unit_assessment_title(unit_title, "en", unit_title_tr=unit_title_tr)
    heading_tr = unit_assessment_title(unit_title, "tr", unit_title_tr=unit_title_tr)
    return {"pages": [{"type": "overview", "title": heading_en, "title_tr": heading_tr,
                       "text": "Check what you have learned in this unit.",
                       "text_tr": "Bu ünitede öğrendiklerinizi değerlendirin."}] + pages}


def process_pdf_to_classroom(pdf_path, toc_range, lecturer_id, course_name=None, manual_toc=None, source_markdown_path=None, language=None, level="A1", material_language="tr"):
    import logging
    logging.getLogger(__name__).warning("LEGACY PIPELINE IN USE")
    if not course_name or course_name.strip() == "":
        course_name = os.path.basename(pdf_path).replace(".pdf", "").replace("course_", "")

    # The instructional track is a property of what the course teaches, decided
    # once here and stored, so nothing downstream has to re-derive it.
    from services.language_profiles import resolve_track
    material_language = resolve_track(language, declared=material_language)

    course_id = _uid()
    code = generate_classroom_code()
    textbook_url = "/books/" + os.path.basename(pdf_path)
    
    gen_id = _uid()
    
    with db_connection() as db:
        db.execute("INSERT INTO courses (id, name, semester, textbook, language, level, code, is_building, lecturer_id, generation_id, material_language, build_stage, build_message, build_started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (course_id, course_name, "Fall 2026", textbook_url, language or "Detecting...", level or "A1", code, 1, lecturer_id, gen_id, material_language, "analyzing", "Analyzing textbook syllabus...", time.time()))
        db.commit()
    from database import enroll_permanent_students_in_course
    enroll_permanent_students_in_course(course_id)
    
    manual_toc_file = None
    if manual_toc:
        manual_toc_file = pdf_path.replace(".pdf", "_toc.txt")
        with open(manual_toc_file, "w", encoding="utf-8") as f:
            f.write(manual_toc)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    # Spawn worker to handle curriculum creation and enrichment
    _log(f"Spawning worker for Classroom {course_id}")
    try:
        # Calculate root relative to this file (services/legacy/pdf_pipeline.py)
        ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        worker_path = os.path.join(ROOT_DIR, "worker.py")
        cmd = [sys.executable, worker_path, pdf_path, toc_range or "0-0", str(lecturer_id), str(course_id), course_name]
        if manual_toc_file:
            cmd.append(manual_toc_file)
        else:
            cmd.append("NONE") # Placeholder for manual_toc_file
            
        if source_markdown_path:
            cmd.append(source_markdown_path)
        else:
            cmd.append("NONE")
            
        if language:
            cmd.append(language)
        else:
            cmd.append("Detecting...")
            
        if level:
            cmd.append(level)
        else:
            cmd.append("A1")
            
        cmd.append(gen_id) # 11th Argument
            
        if sys.platform == "win32":
            log_file = open("pipeline.log", "a", encoding="utf-8")
            process = subprocess.Popen(cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT, 
                                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
            log_file.close() # Child keeps its copy
        else:
            process = subprocess.Popen(cmd, env=env, close_fds=True)
            
        _log(f"Worker spawned successfully with PID {process.pid}")
    except Exception as e:
        _log(f"CRITICAL: Failed to spawn worker: {e}")
    
    return {"success": True, "course_id": course_id, "code": code, "name": course_name}


def process_manual_to_classroom(chapters, language, level, lecturer_id, course_name, existing_course_id=None, material_language="tr"):
    # Same lock as the PDF path: English taught -> Turkish instruction, Turkish
    # taught -> English instruction, every other language keeps what was asked
    # for. Enforced at the write so the course row is never in a state the
    # reader has to correct for.
    from services.language_profiles import resolve_track
    material_language = resolve_track(language, declared=material_language)

    gen_id = _uid()
    if existing_course_id:
        course_id = existing_course_id
        # Preserve existing code, but update everything else
        with db_connection() as db:
            course = db.execute("SELECT code FROM courses WHERE id = ?", (course_id,)).fetchone()
            code = course[0] if course else generate_classroom_code()
            db.execute("UPDATE courses SET name = ?, language = ?, level = ?, is_building = 1, semester = ?, textbook = 'AI Generated', generation_id = ?, progress = 0, total_steps = 0, progress_high_water = 0, material_language = ?, build_stage = 'structuring', build_message = 'Müfredat yapısı oluşturuluyor...', build_started_at = ? WHERE id = ?",
                       (course_name, language, level, f"{level} Level", gen_id, material_language, time.time(), course_id))
            db.commit()
    else:
        course_id = _uid()
        code = generate_classroom_code()
        with db_connection() as db:
            db.execute("INSERT INTO courses (id, name, semester, textbook, language, code, is_building, lecturer_id, level, generation_id, material_language, build_stage, build_message, build_started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (course_id, course_name, f"{level} Level", "AI Generated", language, code, 1, lecturer_id, level, gen_id, material_language, "structuring", "Müfredat yapısı oluşturuluyor...", time.time()))
            db.commit()

    from database import enroll_permanent_students_in_course
    enroll_permanent_students_in_course(course_id)

    # Ensure all chapters and topics have clean bilingual titles (EN and TR)
    from services.curriculum_translator import ensure_bilingual_curriculum
    chapters = ensure_bilingual_curriculum(chapters)

    # Process the nested chapters into the worker's expected format
    worker_chapters = []
    for i, chap in enumerate(chapters):
        topics_processed = []
        for j, t in enumerate(chap.get("topics", [])):
            if isinstance(t, dict):
                topics_processed.append({
                    "title": t.get("title", "Untitled Topic"),
                    "title_tr": t.get("title_tr", ""),
                    "type": t.get("type", "vocabulary")
                })
            else:
                topics_processed.append({
                    "title": str(t),
                    "title_tr": "",
                    "type": "vocabulary" if j % 2 == 0 else "grammar"
                })
                
        worker_chapters.append({
            "number": i + 1,
            "title": chap.get("title", f"Unit {i + 1}"),
            "title_tr": chap.get("title_tr", ""),
            "topics": topics_processed
        })
    
    manual_toc_data = {"chapters": worker_chapters}
        
    # Write the manual TOC to a file for the worker
    # We use data/books directory for consistency with persistence
    from database import BOOKS_DIR
    os.makedirs(BOOKS_DIR, exist_ok=True)
    manual_toc_file = os.path.join(BOOKS_DIR, f"toc_{course_id}.json")
    with open(manual_toc_file, "w", encoding="utf-8") as f:
        json.dump(manual_toc_data, f)
        
    # Spawn worker to handle curriculum creation and enrichment
    _log(f"Spawning AI Architect worker: Course {course_id} (Level: {level})")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    worker_path = os.path.join(ROOT_DIR, "worker.py")
    # Args: 0:worker.py, 1:pdf_path, 2:toc_range, 3:lecturer_id, 4:course_id, 5:course_name, 6:manual_toc_file, 7:source_markdown, 8:language, 9:level, 10:gen_id
    cmd = [sys.executable, worker_path, "NONE", "0-0", str(lecturer_id), str(course_id), course_name, manual_toc_file, "NONE", language, level, gen_id]
    
    try:
        if sys.platform == "win32":
            log_file = open("pipeline.log", "a", encoding="utf-8")
            process = subprocess.Popen(cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT, 
                                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
            log_file.close() # Child keeps its copy
        else:
            process = subprocess.Popen(cmd, env=env, close_fds=True)
        _log(f"Worker process started with PID {process.pid}")
    except Exception as e:
        _log(f"CRITICAL: Failed to spawn AI Architect worker: {e}")
    
    return {"success": True, "course_id": course_id, "code": code, "name": course_name}