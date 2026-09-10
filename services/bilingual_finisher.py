import os
import json
import re
import time
import urllib.request
import urllib.error
import logging

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_FILE = os.path.join(ROOT_DIR, "bilingual_materials.json")
BUNDLE_FILE = os.path.join(ROOT_DIR, "public", "js", "bilingual_materials.js")

SPANISH_ALPHABET_SPELLINGS = {
    "A": "a", "B": "be", "C": "ce", "D": "de", "E": "e", "F": "efe",
    "G": "ge", "H": "hache", "I": "i", "J": "jota", "K": "ka",
    "L": "ele", "M": "eme", "N": "ene", "Ñ": "eñe", "O": "o",
    "P": "pe", "Q": "cu", "R": "ere", "RR": "erre", "S": "ese",
    "T": "te", "U": "u", "V": "uve", "W": "uve doble", "X": "equis",
    "Y": "i griega", "Z": "zeta"
}

def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "sentence_pairs": {},
        "sentence_pairs_tr_en": {},
        "vocab_pairs": {},
        "title_pairs": {}
    }

def _save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save bilingual cache: {e}")

def _call_openrouter(prompt):
    from services.ai_engine import _call_ai
    model = os.getenv("MODEL_TRANSLATOR", os.getenv("MODEL_STRUCTURAL", "openai/gpt-oss-120b"))
    res = _call_ai([{"role": "user", "content": prompt}], model=model, max_tokens=2500, temperature=0.1, json_mode=True)
    return res if isinstance(res, dict) and "error_details" not in res else {}

def batch_translate_strings(strings, target_lang="tr"):
    """Translates a list of strings to target_lang, using cache and OpenRouter."""
    if not strings:
        return {}

    cache = _load_cache()
    if "title_pairs" not in cache: cache["title_pairs"] = {}
    if "sentence_pairs" not in cache: cache["sentence_pairs"] = {}
    if "sentence_pairs_tr_en" not in cache: cache["sentence_pairs_tr_en"] = {}
    if "vocab_pairs" not in cache: cache["vocab_pairs"] = {}

    dest_map = cache["sentence_pairs"] if target_lang == "tr" else cache["sentence_pairs_tr_en"]
    results = {}
    needed = []

    for s in strings:
        if not s or not isinstance(s, str):
            continue
        s_clean = s.strip()
        if not s_clean:
            continue
        # Check cache
        if s_clean in dest_map:
            results[s_clean] = dest_map[s_clean]
        elif s_clean in cache.get("vocab_pairs", {}):
            results[s_clean] = cache["vocab_pairs"][s_clean]
        elif s_clean in cache.get("title_pairs", {}):
            results[s_clean] = cache["title_pairs"][s_clean]
        else:
            needed.append(s_clean)

    # Translate missing strings in parallel batches
    batch_size = 12
    chunks = [needed[i:i+batch_size] for i in range(0, len(needed), batch_size)]
    total_chunks = len(chunks)
    dest_name = "Turkish" if target_lang == "tr" else "English"
    print(f"[BILINGUAL] Translating {len(needed)} items in {total_chunks} batches (parallel)...", flush=True)

    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    cache_lock = threading.Lock()

    def translate_chunk(chunk_idx, chunk):
        indexed_input = {str(idx): chunk[idx] for idx in range(len(chunk))}
        prompt = f"""You are a master bilingual language educator and expert translator.
Translate each educational string in the JSON object into completely natural, idiomatic, CEFR-aligned {dest_name}.

STRICT RULES:
- NATURAL, REAL-LIFE VOICE: The translations must read like a modern, professionally published language textbook—NEVER like cold, literal machine translation. Avoid stiff calques.
- Keep ALL foreign target terms, Spanish/Greek words, and phrases in single quotes EXACTLY as they are. E.g. 'lavarse', 'por vs para', 'el alfabeto'.
- Translate explanations, instructions, example sentences, and meanings naturally, warmly, and clearly into {dest_name}.
- You MUST return a JSON object with the EXACT SAME string keys ("0", "1", ...) mapping each key to its {dest_name} translation string.
{"" if dest_name != "Turkish" else """
CRITICAL TURKISH ANTI-PATTERNS — STRICTLY FORBIDDEN:
A. NO parenthetical glosses: NEVER write "(Meksika'dan)", "(otuz bir güne sahiptir)" or any similar parenthetical explanation inside a translation. Just translate naturally.
B. NO gender hacks: Turkish has NO grammatical gender. NEVER write "kadındır" or "erkektir" to mark a subject's gender in a nationality/identity context. Just use the nationality adjective directly: ✅ "O Meksikalıdır." not ❌ "O bir Meksikalı kadındır."
C. NO tense calques for ordering: When Spanish 'quería', French 'je voudrais', German 'ich hätte gern' appear in an ordering/polite-request context, translate using natural Turkish speech-act formulas: ✅ "alabilir miyim?" / "rica ediyorum" — NOT ❌ "istiyordum" / "rica ediyordum".
D. NO 'sahiptir'/'sahibim' for physical possession: Use 'var' structures instead. ✅ "güzel gözleri var" / "yeşil gözlüdür" — NOT ❌ "güzel gözlere sahiptir".
E. NO 'çok' with ungradable adjectives: ✅ "devasa", "muazzam" — NOT ❌ "çok devasa", "çok muazzam".
F. NO unnatural articles before food items in ordering: ✅ "kızarmış ekmek" — NOT ❌ "bir kızarmış ekmek".
"""}
Input:
{json.dumps(indexed_input, ensure_ascii=False, indent=2)}
"""
        res = _call_openrouter(prompt)
        chunk_res = {}
        if isinstance(res, dict):
            mapping = res
            if len(res) == 1 and isinstance(list(res.values())[0], dict):
                mapping = list(res.values())[0]
            elif "translations" in res and isinstance(res["translations"], dict):
                mapping = res["translations"]

            for idx_str, trans in mapping.items():
                try:
                    idx = int(idx_str)
                    if 0 <= idx < len(chunk) and isinstance(trans, str):
                        orig = chunk[idx]
                        trans_clean = trans.strip()
                        chunk_res[orig] = trans_clean
                except (ValueError, TypeError):
                    continue

        with cache_lock:
            for k, v in chunk_res.items():
                dest_map[k] = v
                results[k] = v
            _save_cache(cache)
        print(f"[BILINGUAL] Batch {chunk_idx+1}/{total_chunks} complete ({len(chunk_res)} translated)", flush=True)
        return chunk_res

    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = [executor.submit(translate_chunk, i, c) for i, c in enumerate(chunks)]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                print(f"[BILINGUAL] Batch error: {e}", flush=True)

    _save_cache(cache)
    return results

def rebuild_bilingual_bundle():
    """Rebuilds public/js/bilingual_materials.js from current bilingual_materials.json."""
    cache = _load_cache()
    en_tr = cache.get("sentence_pairs", {})
    tr_en = cache.get("sentence_pairs_tr_en", {})
    vocab = cache.get("vocab_pairs", {})
    titles = cache.get("title_pairs", {})

    # Build comprehensive sentence maps
    en_tr_map = {}
    for k, v in en_tr.items():
        if k and v:
            if k.strip().lower() == 'on':
                continue
            en_tr_map[k.strip()] = v.strip()
            en_nobullet = re.sub(r'^[•\-\*\s]+', '', k.strip()).strip()
            tr_nobullet = re.sub(r'^[•\-\*\s]+', '', v.strip()).strip()
            en_tr_map[en_nobullet] = tr_nobullet

    tr_en_map = {}
    for k, v in tr_en.items():
        if k and v:
            tr_en_map[k.strip()] = v.strip()
            tr_nobullet = re.sub(r'^[•\-\*\s]+', '', k.strip()).strip()
            en_nobullet = re.sub(r'^[•\-\*\s]+', '', v.strip()).strip()
            tr_en_map[tr_nobullet] = en_nobullet

    # Vocab directional maps
    vocab_en_tr = {}
    vocab_tr_en = {}
    for k, v in vocab.items():
        if not k or not v: continue
        k_c, v_c = k.strip(), v.strip()
        if (len(k_c) <= 1 and k_c != 'I') or (len(v_c) <= 1 and v_c != 'I'): continue
        if k_c.lower() == 'on' and v_c.lower() == 'üzerinde': continue
        is_k_tr = bool(re.search(r'[çğıöşüÇĞİÖŞÜ\u011f\u011e\u0131\u0130\u00f6\u00d6\u015f\u015e\u00fc\u00dc\u00e7\u00c7]', k_c))
        if is_k_tr:
            vocab_tr_en[k_c] = v_c
            vocab_tr_en[k_c.lower()] = v_c
            vocab_en_tr[v_c] = k_c
            vocab_en_tr[v_c.lower()] = k_c
        else:
            vocab_en_tr[k_c] = v_c
            vocab_en_tr[k_c.lower()] = v_c
            vocab_tr_en[v_c] = k_c
            vocab_tr_en[v_c.lower()] = k_c

    # Enforce authentic pragmatic translations
    vocab_en_tr["Good afternoon"] = "Tünaydın"
    vocab_en_tr["good afternoon"] = "Tünaydın"
    vocab_tr_en["Tünaydın"] = "Good afternoon"
    vocab_tr_en["tünaydın"] = "Good afternoon"
    vocab_tr_en["İyi öğleden sonra"] = "Good afternoon"
    vocab_tr_en["iyi öğleden sonra"] = "Good afternoon"
    vocab_en_tr["I"] = "Ben"
    vocab_tr_en["Ben"] = "I"
    vocab_en_tr["I am"] = "(Ben) ...yim / ...yım"

    # Cardinal numbers protection (never allow 'on' -> 'üzerinde' or 'diez' -> 'üzerinde')
    cardinal_numbers = [
        ("zero", "sıfır"), ("cero", "sıfır"),
        ("one", "bir"), ("uno", "bir"),
        ("two", "iki"), ("dos", "iki"),
        ("three", "üç"), ("tres", "üç"),
        ("four", "dört"), ("cuatro", "dört"),
        ("five", "beş"), ("cinco", "beş"),
        ("six", "altı"), ("seis", "altı"),
        ("seven", "yedi"), ("siete", "yedi"),
        ("eight", "sekiz"), ("ocho", "sekiz"),
        ("nine", "dokuz"), ("nueve", "dokuz"),
        ("ten", "on"), ("diez", "on"), ("on", "on"),
        ("eleven", "on bir"), ("once", "on bir"),
        ("twelve", "on iki"), ("doce", "on iki"),
        ("thirteen", "on üç"), ("trece", "on üç"),
        ("fourteen", "on dört"), ("catorce", "on dört"),
        ("fifteen", "on beş"), ("quince", "on beş"),
        ("sixteen", "on altı"), ("dieciséis", "on altı"),
        ("seventeen", "on yedi"), ("diecisiete", "on yedi"),
        ("eighteen", "on sekiz"), ("dieciocho", "on sekiz"),
        ("nineteen", "on dokuz"), ("diecinueve", "on dokuz"),
        ("twenty", "yirmi"), ("veinte", "yirmi")
    ]
    for en_src, tr_dst in cardinal_numbers:
        vocab_en_tr[en_src] = tr_dst
        vocab_en_tr[en_src.lower()] = tr_dst
        vocab_en_tr[en_src.capitalize()] = tr_dst.capitalize()
        vocab_tr_en[tr_dst] = en_src
        vocab_tr_en[tr_dst.lower()] = en_src
        vocab_tr_en[tr_dst.capitalize()] = en_src.capitalize()

    # Page titles pairs
    page_titles = [
        ["Alfabeto Master List", "Alfabe Ana Listesi"],
        ["Essential Vocabulary", "Temel Kelimeler"],
        ["Phonetic Sounds of the Alphabet", "Alfabenin Fonetik Sesleri"],
        ["Practical Application", "Pratik Uygulama"],
        ["Sound Practice", "Ses Pratiği"],
        ["Spanish Alphabet", "İspanyol Alfabesi"],
        ["Structural Focus", "Yapısal Odak"],
        ["Essential Verbs", "Temel Fiiller"],
        ["Vocabulary Knowledge", "Temel Kelime Bilgisi"],
        ["Vocabulary Repertoire", "Temel Kelime Dağarcığı"],
        ["Basic Prepositions of Place", "Temel Yer Edatları"],
        ["Using the Alphabet in Context", "Alfabeyi Bağlam İçinde Kullanma"],
        ["Key Vocabulary", "Önemli Kelimeler"],
        ["Important Words", "Önemli Kelimeler"],
        ["Grammar & Key Rules", "Dilbilgisi ve Temel Kurallar"],
        ["Vocabulary Cheat Sheet", "Kelime İpucu Listesi"],
        ["Quick Check", "Hızlı Kontrol"],
        ["Practical Usage", "Pratik Kullanım"],
        ["Common Mistakes", "Yaygın Hatalar"],
        ["Cultural Context", "Kültürel Bağlam"],
        ["Cultural Insights", "Kültürel Bilgiler"],
        ["Dialogue Practice", "Diyalog Pratiği"]
    ]
    for k, v in titles.items():
        if [k, v] not in page_titles and [v, k] not in page_titles:
            page_titles.append([k, v])

    js_content = f"""// AulaAI Bilingual Educational Materials Dictionary
// Auto-compiled to guarantee instant 0ms switching between English and Turkish
window.EDUCATIONAL_SENTENCE_MAP_EN_TR = {json.dumps(en_tr_map, ensure_ascii=False, indent=2)};

window.EDUCATIONAL_SENTENCE_MAP_TR_EN = {json.dumps(tr_en_map, ensure_ascii=False, indent=2)};

window.VOCAB_MAP_EN_TR = {json.dumps(vocab_en_tr, ensure_ascii=False, indent=2)};

window.VOCAB_MAP_TR_EN = {json.dumps(vocab_tr_en, ensure_ascii=False, indent=2)};

window.PAGE_TITLE_PAIRS = {json.dumps(page_titles, ensure_ascii=False, indent=2)};
"""
    try:
        with open(BUNDLE_FILE, "w", encoding="utf-8") as f:
            f.write(js_content)
    except Exception as e:
        logger.error(f"Failed to write bilingual bundle: {e}")

def finalize_course_bilingual_data(course_id: str):
    import sys
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)
    from database import db_connection
    try:
        from services.state import bump_version
    except Exception:
        bump_version = lambda: None
    print(f"[BILINGUAL] Finalizing bilingual data for course {course_id}...")

    with db_connection() as db:
        chapters = db.execute("SELECT id, number, title, title_tr FROM chapters WHERE course_id = ? ORDER BY number", (course_id,)).fetchall()
        topics = db.execute("""
            SELECT t.id, t.chapter_id, t.title, t.title_tr, t.content 
            FROM topics t
            JOIN chapters ch ON t.chapter_id = ch.id
            WHERE ch.course_id = ?
            ORDER BY ch.number, t.sort_order
        """, (course_id,)).fetchall()

    if not chapters or not topics:
        return

    # 1. Collect all titles and content strings
    to_translate_to_tr = []
    
    from services.curriculum_translator import is_clean_turkish
    
    # Chapters
    for ch in chapters:
        if ch["title"] and (not ch["title_tr"] or not is_clean_turkish(ch["title_tr"])):
            to_translate_to_tr.append(ch["title"].strip())

    # Topics & Lessons
    topic_data_list = []
    for t in topics:
        if t["title"] and (not t["title_tr"] or not is_clean_turkish(t["title_tr"])):
            to_translate_to_tr.append(t["title"].strip())
            
        try:
            content = json.loads(t["content"] or "{}")
        except Exception:
            content = {}
            
        pages = content.get("pages", [])
        for p in pages:
            # Page title
            if p.get("title") and (not p.get("title_tr") or not is_clean_turkish(p.get("title_tr"))):
                to_translate_to_tr.append(p["title"].strip())
            # Bullet points / explanation
            has_native_text = bool(p.get("text_tr") and p.get("text_tr").strip() and p.get("text_tr") != p.get("text"))
            has_native_expl = bool(p.get("explanation_tr") and p.get("explanation_tr").strip() and p.get("explanation_tr") != p.get("explanation"))
            if not has_native_text and not has_native_expl:
                txt = p.get("text") or p.get("explanation") or p.get("intro") or ""
                if txt and isinstance(txt, str):
                    for line in txt.split("\n"):
                        cl = re.sub(r'^[•\-\*\s]+', '', line).strip()
                        if cl and len(cl) > 2:
                            to_translate_to_tr.append(cl)

            # Vocab items
            items = p.get("items") or p.get("vocabulary") or p.get("words") or []
            for it in items:
                if isinstance(it, dict):
                    term_clean = (it.get("term") or it.get("word") or "").strip().upper()
                    if term_clean in SPANISH_ALPHABET_SPELLINGS:
                        continue
                    v = it.get("translation") or it.get("meaning") or it.get("english") or ""
                    if v and isinstance(v, str) and len(v.strip()) > 1 and (not it.get("translation_tr") or it.get("translation_tr") == v):
                        to_translate_to_tr.append(v.strip())
                    expl = it.get("explanation") or it.get("explanation_en") or ""
                    if expl and isinstance(expl, str) and len(expl.strip()) > 2 and (not it.get("explanation_tr") or it.get("explanation_tr") == expl):
                        to_translate_to_tr.append(expl.strip())
            # MCQ
            if p.get("prompt") and (not p.get("prompt_tr") or p.get("prompt_tr") == p.get("prompt")):
                to_translate_to_tr.append(p["prompt"].strip())
            if p.get("explanation") and (not p.get("explanation_tr") or p.get("explanation_tr") == p.get("explanation")):
                to_translate_to_tr.append(p["explanation"].strip())

        topic_data_list.append((t["id"], t["title"], content))

    # 2. Batch translate everything missing
    unique_needed = list(set(to_translate_to_tr))
    print(f"[BILINGUAL] Translating {len(unique_needed)} unique strings for course {course_id}...")
    trans_map = batch_translate_strings(unique_needed, target_lang="tr")

    # Also record in title_pairs
    cache = _load_cache()
    if "title_pairs" not in cache: cache["title_pairs"] = {}
    for ch in chapters:
        t_en = ch["title"]
        if t_en in trans_map:
            cache["title_pairs"][t_en] = trans_map[t_en]
    for t in topics:
        t_en = t["title"]
        if t_en in trans_map:
            cache["title_pairs"][t_en] = trans_map[t_en]
    _save_cache(cache)

    from services.concept_explanations import get_concept_explanation

    # 3. Apply translations directly into database
    with db_connection() as db:
        # Update chapters
        for ch in chapters:
            ch_tr = trans_map.get(ch["title"].strip()) if (not ch["title_tr"] or not is_clean_turkish(ch["title_tr"])) else ch["title_tr"]
            if ch_tr:
                db.execute("UPDATE chapters SET title_tr = ? WHERE id = ?", (ch_tr, ch["id"]))

        # Update topics
        for tid, ttitle, content in topic_data_list:
            t_row = next((x for x in topics if x["id"] == tid), None)
            t_curr = t_row["title_tr"] if t_row else None
            t_tr = trans_map.get(ttitle.strip()) if (not t_curr or not is_clean_turkish(t_curr)) else t_curr
            if not t_tr:
                t_tr = ttitle
            pages = content.get("pages", [])
            for p in pages:
                # Title
                if p.get("title"):
                    if p["title"].strip() == "Essential Vocabulary":
                        p["title_tr"] = "Temel Kelimeler"
                    elif not p.get("title_tr") or p.get("title_tr") == p.get("title"):
                        p["title_tr"] = trans_map.get(p["title"].strip(), p["title"])
                # Text / bullets
                has_native_text = bool(p.get("text_tr") and p.get("text_tr").strip() and p.get("text_tr") != p.get("text"))
                has_native_expl = bool(p.get("explanation_tr") and p.get("explanation_tr").strip() and p.get("explanation_tr") != p.get("explanation"))
                if not has_native_text:
                    txt = p.get("text") or p.get("intro") or ""
                    if txt and isinstance(txt, str):
                        lines = txt.split("\n")
                        tr_lines = []
                        for line in lines:
                            cl = re.sub(r'^[•\-\*\s]+', '', line).strip()
                            if not cl:
                                tr_lines.append(line)
                                continue
                            bullet_match = re.match(r'^([•\-\*\s]+)', line)
                            bullet = bullet_match.group(1) if bullet_match else "• "
                            translated_cl = trans_map.get(cl, cl)
                            tr_lines.append(bullet + translated_cl)
                        p["text_tr"] = "\n".join(tr_lines)
                if not has_native_expl:
                    expl_txt = p.get("explanation") or ""
                    if expl_txt and isinstance(expl_txt, str):
                        lines = expl_txt.split("\n")
                        tr_lines = []
                        for line in lines:
                            cl = re.sub(r'^[•\-\*\s]+', '', line).strip()
                            if not cl:
                                tr_lines.append(line)
                                continue
                            bullet_match = re.match(r'^([•\-\*\s]+)', line)
                            bullet = bullet_match.group(1) if bullet_match else "• "
                            translated_cl = trans_map.get(cl, cl)
                            tr_lines.append(bullet + translated_cl)
                        p["explanation_tr"] = "\n".join(tr_lines)
                    elif p.get("text_tr"):
                        p["explanation_tr"] = p["text_tr"]
                # Vocab items
                items = p.get("items") or p.get("vocabulary") or p.get("words") or []
                for it in items:
                    if isinstance(it, dict):
                        term_clean = (it.get("term") or it.get("word") or "").strip().upper()
                        if term_clean in SPANISH_ALPHABET_SPELLINGS:
                            spelling = SPANISH_ALPHABET_SPELLINGS[term_clean]
                            it["translation"] = spelling
                            it["translation_en"] = spelling
                            it["translation_tr"] = spelling
                            it["turkish"] = spelling
                            continue
                        v = it.get("translation") or it.get("meaning") or it.get("english") or ""
                        if v and isinstance(v, str):
                            v_clean = v.strip()
                            if not it.get("translation_tr") or it.get("translation_tr") == v_clean:
                                v_tr = trans_map.get(v_clean, v_clean)
                                it["translation_tr"] = v_tr
                                it["turkish"] = v_tr
                            it["translation_en"] = v_clean
                        
                        # Explanation enrichment & translation
                        expl = it.get("explanation") or it.get("explanation_en") or ""
                        if it.get("explanation_tr") and it.get("explanation_tr") != expl:
                            it["explanation_en"] = expl or it.get("explanation") or ""
                        elif expl and isinstance(expl, str) and len(expl.strip()) > 2:
                            expl_clean = expl.strip()
                            it["explanation_en"] = expl_clean
                            it["explanation_tr"] = trans_map.get(expl_clean, it.get("explanation_tr") or expl_clean)
                            it["explanation"] = it["explanation_en"]
                        else:
                            c_tr = get_concept_explanation(it.get("term"), v, "tr")
                            c_en = get_concept_explanation(it.get("term"), v, "en")
                            if c_en:
                                it["explanation"] = c_en
                                it["explanation_en"] = c_en
                                it["explanation_tr"] = c_tr
                # MCQ
                if p.get("prompt") and (not p.get("prompt_tr") or p.get("prompt_tr") == p.get("prompt")):
                    p["prompt_tr"] = trans_map.get(p["prompt"].strip(), p["prompt"])
                if p.get("explanation") and (not p.get("explanation_tr") or p.get("explanation_tr") == p.get("explanation")):
                    p["explanation_tr"] = trans_map.get(p["explanation"].strip(), p["explanation"])

            # Save enriched bilingual content
            db.execute("UPDATE topics SET title_tr = ?, content = ? WHERE id = ?", 
                       (t_tr, json.dumps(content, ensure_ascii=False), tid))
        db.commit()

    # 4. Re-compile frontend bundle and bump version
    rebuild_bilingual_bundle()
    bump_version()
    logger.info(f"[BILINGUAL] Successfully finalized bilingual curriculum for course {course_id}!")

if __name__ == "__main__":
    import sys
    cid = sys.argv[1] if len(sys.argv) > 1 else '2d28c33e-90ed-4a4c-a8af-0bc2435358ab'
    finalize_course_bilingual_data(cid)
    print("Done finalize_course_bilingual_data for", cid)
