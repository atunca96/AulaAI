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

SPANISH_ALPHABET_DATA = {
    "A": {
        "spelling": "la a",
        "name_tr": "a harfi (la a)",
        "name_en": "Letter A (la a)",
        "expl_en": "Open and bright vowel sound, pronounced cleanly like the 'a' in 'father'; never slurred or weakened.",
        "expl_tr": "Türkçedeki 'a' sesi gibi açık ve net okunur; asla yuvarlanmaz veya zayıflatılmaz."
    },
    "B": {
        "spelling": "la be",
        "name_tr": "b harfi (la be)",
        "name_en": "Letter B (la be)",
        "expl_en": "Pronounced as a soft bilabial stop [b] at the start of a phrase, and a gentle approximant [β] between vowels.",
        "expl_tr": "Kelime başında Türkçedeki 'b' gibidir; iki ünlü arasında dudaklar birbirine tam değmeden yumuşakça çıkar."
    },
    "C": {
        "spelling": "la ce",
        "name_tr": "c harfi (la ce)",
        "name_en": "Letter C (la ce)",
        "expl_en": "Hard [k] before a, o, u (casa, coche, cuna); soft [s] or [θ] before e, i (cero, cine).",
        "expl_tr": "a, o, u önünde 'k' sesi verir (casa, coche); e ve i önünde ise 's' veya peltek 's' olarak okunur (cero, cine)."
    },
    "CH": {
        "spelling": "la che",
        "name_tr": "ch harfi (la che)",
        "name_en": "Letter CH (la che)",
        "expl_en": "Voiceless postalveolar affricate, pronounced crisply like 'ch' in 'chocolate' or 'cheese'.",
        "expl_tr": "Türkçedeki 'ç' sesi gibi net ve sert bir sestir (chico, chocolate)."
    },
    "D": {
        "spelling": "la de",
        "name_tr": "d harfi (la de)",
        "name_en": "Letter D (la de)",
        "expl_en": "Dental stop [d] at word start; softens to a gentle approximant [ð] (like 'th' in 'this') between vowels.",
        "expl_tr": "Kelime başında net 'd' sesi verir; ünlüler arasında ise yumuşayarak peltek bir ton alır."
    },
    "E": {
        "spelling": "la e",
        "name_tr": "e harfi (la e)",
        "name_en": "Letter E (la e)",
        "expl_en": "Mid-front invariant vowel, pronounced cleanly like 'e' in 'bed'; never gliding into an 'ee' sound.",
        "expl_tr": "Türkçedeki 'e' sesi gibi sabit ve nettir; asla diftonglaşmaz veya uzatılmaz."
    },
    "F": {
        "spelling": "la efe",
        "name_tr": "f harfi (la efe)",
        "name_en": "Letter F (la efe)",
        "expl_en": "Voiceless labiodental fricative, pronounced exactly like 'f' in 'father' or 'fine'.",
        "expl_tr": "Türkçedeki 'f' sesiyle aynıdır; üst dişler alt dudağa hafifçe değer."
    },
    "G": {
        "spelling": "la ge",
        "name_tr": "g harfi (la ge)",
        "name_en": "Letter G (la ge)",
        "expl_en": "Hard [g] before a, o, u (gato, gusto); raspy fricative [x] from the throat before e, i (gente, girasol).",
        "expl_tr": "a, o, u önünde sert 'g' (gato); e ve i önünde ise boğazdan hırıltılı 'h' sesi verir (gente)."
    },
    "H": {
        "spelling": "la hache",
        "name_tr": "h harfi (la hache)",
        "name_en": "Letter H (la hache)",
        "expl_en": "Always completely silent in Spanish; never pronounced under any circumstances (hola sounds like 'ola').",
        "expl_tr": "İspanyolcada daima sessizdir, asla okunmaz (hola sözcüğü 'ola' şeklinde okunur)."
    },
    "I": {
        "spelling": "la i",
        "name_tr": "i harfi (la i)",
        "name_en": "Letter I (la i)",
        "expl_en": "Close front vowel, pronounced like 'ee' in 'see' or 'machine'; crisp and distinct.",
        "expl_tr": "Türkçedeki 'i' sesi gibi net ve kısadır; asla yuvarlanmaz veya zayıflatılmaz."
    },
    "J": {
        "spelling": "la jota",
        "name_tr": "j harfi (la jota)",
        "name_en": "Letter J (la jota)",
        "expl_en": "Voiceless velar/uvular fricative from the throat, like the Scottish 'ch' in 'loch' or strong 'h' in 'hotel'.",
        "expl_tr": "Boğazın arkasından gelen hırıltılı bir 'h' sesidir (Almanca 'ach' gibi)."
    },
    "K": {
        "spelling": "la ka",
        "name_tr": "k harfi (la ka)",
        "name_en": "Letter K (la ka)",
        "expl_en": "Found only in foreign loanwords; pronounced as a crisp [k] as in 'kite'.",
        "expl_tr": "Yabancı kökenli sözcüklerde bulunur; sert ve net 'k' sesi verir."
    },
    "L": {
        "spelling": "la ele",
        "name_tr": "l harfi (la ele)",
        "name_en": "Letter L (la ele)",
        "expl_en": "Voiced alveolar lateral, pronounced with the tongue tip against the upper gum ridge like 'l' in 'light'.",
        "expl_tr": "Türkçedeki ince 'l' sesi gibi dil ucu üst damağa değerek berrak çıkar."
    },
    "LL": {
        "spelling": "la elle",
        "name_tr": "ll harfi (la elle)",
        "name_en": "Letter LL (la elle)",
        "expl_en": "Pronounced like the 'y' in 'yes' across most Hispanic dialects; historically a palatal lateral [ʎ].",
        "expl_tr": "Günümüz İspanyolcasında çoğunlukla 'y' sesi (yağmur gibi) olarak telaffuz edilir."
    },
    "M": {
        "spelling": "la eme",
        "name_tr": "m harfi (la eme)",
        "name_en": "Letter M (la eme)",
        "expl_en": "Bilabial nasal, pronounced cleanly like the 'm' in 'mother'.",
        "expl_tr": "Türkçedeki 'm' sesi ile tamamen aynıdır; dudaklar kapatılarak çıkarılır."
    },
    "N": {
        "spelling": "la ene",
        "name_tr": "n harfi (la ene)",
        "name_en": "Letter N (la ene)",
        "expl_en": "Alveolar nasal, pronounced cleanly like the 'n' in 'night'.",
        "expl_tr": "Türkçedeki 'n' sesi ile tamamen aynıdır; dil ucu üst damağa değer."
    },
    "Ñ": {
        "spelling": "la eñe",
        "name_tr": "ñ harfi (la eñe)",
        "name_en": "Letter Ñ (la eñe)",
        "expl_en": "Voiced palatal nasal, pronounced like the 'ny' in 'canyon' or 'onion'.",
        "expl_tr": "Damaktan çıkan 'n+y' birleşik sesidir (kanyon sözcüğündeki 'ny' gibi)."
    },
    "O": {
        "spelling": "la o",
        "name_tr": "o harfi (la o)",
        "name_en": "Letter O (la o)",
        "expl_en": "Back mid rounded vowel, pronounced cleanly like the 'o' in 'for' or 'order'; never diphthongized.",
        "expl_tr": "Türkçedeki 'o' sesi gibi yuvarlak ve nettir; asla diftonglaşmaz."
    },
    "P": {
        "spelling": "la pe",
        "name_tr": "p harfi (la pe)",
        "name_en": "Letter P (la pe)",
        "expl_en": "Voiceless bilabial stop, pronounced crisply like 'p' in 'spot' without heavy aspiration.",
        "expl_tr": "Türkçedeki 'p' sesi gibi nefes patlaması olmadan net çıkar."
    },
    "Q": {
        "spelling": "la cu",
        "name_tr": "q harfi (la cu)",
        "name_en": "Letter Q (la cu)",
        "expl_en": "Always followed by silent 'u' (qu) before e or i, pronounced as [k] (queso sounds like 'keso').",
        "expl_tr": "Daima 'qu' şeklinde e veya i önünde gelir; 'u' okunmaz, sert 'k' sesi verir (queso -> keso)."
    },
    "R": {
        "spelling": "la ere",
        "name_tr": "r harfi (la ere)",
        "name_en": "Letter R (la ere)",
        "expl_en": "A single alveolar tap, like the rapid 'tt' in American English 'butter' or 'city'.",
        "expl_tr": "Hafif ve tek bir dil vuruşuyla çıkan yumuşak 'r' sesidir."
    },
    "RR": {
        "spelling": "la erre",
        "name_tr": "rr harfi (la erre)",
        "name_en": "Letter RR (la erre)",
        "expl_en": "A multi-tap vibrant trill produced by vibrating the tip of the tongue against the alveolar ridge.",
        "expl_tr": "Dil ucunun üst damakta hızla titretilmesiyle oluşan kuvvetli, çift 'r' sesidir."
    },
    "S": {
        "spelling": "la ese",
        "name_tr": "s harfi (la ese)",
        "name_en": "Letter S (la ese)",
        "expl_en": "Voiceless alveolar sibilant, pronounced cleanly like the 's' in 'sun'.",
        "expl_tr": "Türkçedeki 's' sesi gibi temiz ve nettir."
    },
    "T": {
        "spelling": "la te",
        "name_tr": "t harfi (la te)",
        "name_en": "Letter T (la te)",
        "expl_en": "Dental stop, pronounced with the tongue directly against the back of the upper front teeth, like 't' in 'stop'.",
        "expl_tr": "Dil ucu üst dişlerin arkasına basılarak çıkan sert 't' sesidir."
    },
    "U": {
        "spelling": "la u",
        "name_tr": "u harfi (la u)",
        "name_en": "Letter U (la u)",
        "expl_en": "Close back rounded vowel, pronounced cleanly like the 'oo' in 'moon' or 'lunar'.",
        "expl_tr": "Türkçedeki 'u' sesi gibi dudaklar öne uzatılarak net çıkarılır."
    },
    "V": {
        "spelling": "la uve",
        "name_tr": "v harfi (la uve)",
        "name_en": "Letter V (la uve)",
        "expl_en": "Phonetically identical to 'b' in Spanish; pronounced with both lips, without biting the lower lip.",
        "expl_tr": "İspanyolcada 'b' ile tamamen aynıdır; alt dudak ısırılmadan yumuşakça telaffuz edilir."
    },
    "W": {
        "spelling": "la uve doble",
        "name_tr": "w harfi (la uve doble)",
        "name_en": "Letter W (la uve doble)",
        "expl_en": "Appears exclusively in loanwords; pronounced like English [w] in 'water' or [b].",
        "expl_tr": "Yalnızca yabancı sözcüklerde bulunur; İngilizce 'w' sesi gibi okunur."
    },
    "X": {
        "spelling": "la equis",
        "name_tr": "x harfi (la equis)",
        "name_en": "Letter X (la equis)",
        "expl_en": "Pronounced as [ks] between vowels (éxito) and often as [s] before consonants (extra).",
        "expl_tr": "İki ünlü arasında 'ks' (éxito), sessiz harflerden önce ise genellikle 's' okunur."
    },
    "Y": {
        "spelling": "la i griega / ye",
        "name_tr": "y harfi (la i griega / ye)",
        "name_en": "Letter Y (la i griega / ye)",
        "expl_en": "Pronounced like the 'y' in 'yes' before vowels; sounds like 'ee' in 'see' at word ends (hoy, rey).",
        "expl_tr": "Ünlü önünde 'y' sesi, tek başına veya kelime sonunda ise 'i' gibi okunur."
    },
    "Z": {
        "spelling": "la zeta",
        "name_tr": "z harfi (la zeta)",
        "name_en": "Letter Z (la zeta)",
        "expl_en": "Pronounced as voiceless [θ] ('th' in 'thin') in Spain, and as [s] in Latin America.",
        "expl_tr": "İspanya'da peltek 's' (İngilizce 'think' gibi), Latin Amerika'da ise düz 's' okunur."
    }
}

SPANISH_ALPHABET_SPELLINGS = {k: v["spelling"] for k, v in SPANISH_ALPHABET_DATA.items()}

def extract_letter_key(term):
    if not term or not isinstance(term, str):
        return None
    s = term.strip()
    if len(s) == 1:
        u = s.upper()
        return u if u in SPANISH_ALPHABET_DATA else None
    letters = re.sub(r'[^A-Za-zÑñÁÉÍÓÚÜáéíóúü]', '', s)
    if not letters:
        return None
    u = letters.upper()
    if u in ["CH", "CHCH"]:
        return "CH"
    if u in ["LL", "LLLL"]:
        return "LL"
    if u in ["RR", "RRRR"]:
        return "RR"
    if len(set(u)) == 1 and len(u) <= 4:
        return u[0] if u[0] in SPANISH_ALPHABET_DATA else None
    first_part = re.split(r'[\s,/-]+', s)[0].upper()
    clean_p = re.sub(r'[^A-Za-zÑñ]', '', first_part)
    if clean_p in SPANISH_ALPHABET_DATA:
        return clean_p
    return None

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

    turkish_rules = ""
    if dest_name == "Turkish":
        turkish_rules = """
CRITICAL TURKISH ANTI-PATTERNS — STRICTLY FORBIDDEN:
A. NO parenthetical glosses: NEVER write "(Meksika'dan)", "(otuz bir güne sahiptir)" or any similar parenthetical explanation inside a translation. Just translate naturally.
B. NO gender hacks: Turkish has NO grammatical gender. NEVER write "kadındır" or "erkektir" to mark a subject's gender in a nationality/identity context. Just use the nationality adjective directly: ✅ "O Meksikalıdır." not ❌ "O bir Meksikalı kadındır."
C. NO tense calques for ordering: When Spanish 'quería', French 'je voudrais', German 'ich hätte gern' appear in an ordering/polite-request context, translate using natural Turkish speech-act formulas: ✅ "alabilir miyim?" / "rica ediyorum" — NOT ❌ "istiyordum" / "rica ediyordum".
D. NO 'sahiptir'/'sahibim' for physical possession: Use 'var' structures instead. ✅ "güzel gözleri var" / "yeşil gözlüdür" — NOT ❌ "güzel gözlere sahiptir".
E. NO 'çok' with ungradable adjectives: ✅ "devasa", "muazzam" — NOT ❌ "çok devasa", "çok muazzam".
F. NO unnatural articles before food items in ordering: ✅ "kızarmış ekmek" — NOT ❌ "bir kızarmış ekmek".
"""

    def translate_chunk(chunk_idx, chunk):
        indexed_input = {str(idx): chunk[idx] for idx in range(len(chunk))}
        prompt = f"""You are a master bilingual language educator and expert translator.
Translate each educational string in the JSON object into completely natural, idiomatic, CEFR-aligned {dest_name}.

STRICT RULES:
- NATURAL, REAL-LIFE VOICE: The translations must read like a modern, professionally published language textbook—NEVER like cold, literal machine translation. Avoid stiff calques.
- Keep ALL foreign target terms, Spanish/Greek words, and phrases in single quotes EXACTLY as they are. E.g. 'lavarse', 'por vs para', 'el alfabeto'.
- Translate explanations, instructions, example sentences, and meanings naturally, warmly, and clearly into {dest_name}.
- You MUST return a JSON object with the EXACT SAME string keys ("0", "1", ...) mapping each key to its {dest_name} translation string.
{turkish_rules}
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
            tr_en_map[tr_nobullet] = en_nobullet

    # Ensure all alphabet phonetics explanations are registered in bilingual sentence maps
    for let, adata in SPANISH_ALPHABET_DATA.items():
        expl_en = adata["expl_en"].strip()
        expl_tr = adata["expl_tr"].strip()
        en_tr_map[expl_en] = expl_tr
        tr_en_map[expl_tr] = expl_en
        # Also clean versions
        en_tr_map[re.sub(r'^[•\-\*\s]+', '', expl_en)] = re.sub(r'^[•\-\*\s]+', '', expl_tr)
        tr_en_map[re.sub(r'^[•\-\*\s]+', '', expl_tr)] = re.sub(r'^[•\-\*\s]+', '', expl_en)

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
                    raw_term = it.get("term") or it.get("word") or ""
                    letter_key = extract_letter_key(raw_term)
                    if letter_key and letter_key in SPANISH_ALPHABET_DATA:
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
                        raw_term = (it.get("term") or it.get("word") or "").strip()
                        letter_key = extract_letter_key(raw_term)
                        if letter_key and letter_key in SPANISH_ALPHABET_DATA:
                            adata = SPANISH_ALPHABET_DATA[letter_key]
                            it["translation"] = adata["spelling"]
                            it["translation_en"] = adata["name_en"]
                            it["translation_tr"] = adata["name_tr"]
                            it["turkish"] = adata["name_tr"]
                            it["explanation_en"] = adata["expl_en"]
                            it["explanation_tr"] = adata["expl_tr"]
                            it["explanation"] = adata["expl_en"]
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
                        is_tr_expl = bool(re.search(r'[çğıöşüÇĞİÖŞÜ]|\b(sesi|gibi|açık|net|okunur|asla|harfi|anlamına|gelir)\b', expl, re.I))
                        if is_tr_expl:
                            it["explanation_tr"] = expl.strip()
                            en_expl = trans_map.get(expl.strip()) or it.get("explanation_en") or ""
                            if not en_expl or en_expl == expl.strip() or bool(re.search(r'[çğıöşüÇĞİÖŞÜ]', en_expl)):
                                en_expl = get_concept_explanation(it.get("term"), v, "en") or ""
                            if en_expl:
                                en_expl = re.sub(r'like\s+the\s+[\'"]?([a-zA-Z])[\'"]?\s+sound\s+in\s+Turkish', r"like '\1' in English", en_expl, flags=re.I)
                                en_expl = re.sub(r'like\s+in\s+Turkish|as\s+in\s+Turkish', 'clean and distinct', en_expl, flags=re.I)
                                en_expl = re.sub(r'in\s+Turkish', 'in standard pronunciation', en_expl, flags=re.I)
                                it["explanation_en"] = en_expl
                                it["explanation"] = en_expl
                        elif it.get("explanation_tr") and it.get("explanation_tr") != expl:
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
