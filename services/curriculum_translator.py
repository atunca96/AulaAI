import os
import json
import re
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_FILE = os.path.join(ROOT_DIR, "bilingual_materials.json")

# Common English words/patterns that indicate a string is in English or a Frankenstein hybrid
ENGLISH_INDICATORS = [
    r"\b(understanding|customs|review|application|insights|foundations|routines|exploring|surroundings)\b",
    r"\b(exchanges|interactions|essentials|workplace|communication|traveling|survival|forming)\b",
    r"\b(sentences|activities|relationships|interests|culture|perspectives|situations|dialogues)\b",
    r"\b(greetings|introductions|numbers|alphabet|vowels|consonants|pronunciation|phonetics)\b",
    r"\b(grammar|vocabulary|rules|practice|practical|check|guide|overview|summary)\b",
    r"\b(in|and|the|of|for|with|at|from|by|about|into|through|during|before|after)\b",
    r"\b(world\s+around\s+us|around\s+us|who\s+are\s+you|getting\s+acquainted)\b",
    r"\b(ve\s+ve|pratik\s+application|kültürel\s+içgörüler:\s*understanding)\b"
]

_ENGLISH_REGEX = re.compile("|".join(ENGLISH_INDICATORS), re.IGNORECASE)

# High-frequency educational canonical translations (deterministic backup)
CANONICAL_TITLE_MAP = {
    "the alphabet and foundations": "Alfabe ve Temel Bilgiler",
    "alphabet and foundations": "Alfabe ve Temel Bilgiler",
    "the alphabet": "Alfabe",
    "alphabet": "Alfabe",
    "vowels and consonants": "Sesli ve Sessiz Harfler",
    "pronunciation and phonetics": "Telaffuz ve Fonetik",
    "greetings and introductions": "Selamlaşmalar ve Tanıtımlar",
    "greetings & introductions": "Selamlaşmalar ve Tanıtımlar",
    "basic greetings and farewells": "Temel Selamlaşmalar ve Vedalaşmalar",
    "greetings and farewells": "Selamlaşmalar ve Vedalaşmalar",
    "introducing yourself and others": "Kendinizi ve Başkalarını Tanıtmak",
    "introducing yourself": "Kendini Tanıtma",
    "introducing others": "Başkalarını Tanıtma",
    "polite expressions and requests": "Nazik İfadeler ve İstekler",
    "polite expressions": "Nazik İfadeler",
    "requests": "İstekler",
    "saying hello and goodbye": "Merhaba ve Hoşça Kal Deme",
    "formal vs informal": "Resmi ve Samimi Hitaplar",
    "formal vs informal speech": "Resmi ve Samimi Konuşma",
    "describing yourself and others": "Kendinizi ve Başkalarını Tanımlama",
    "basic adjectives for personal description": "Kişisel Tanım İçin Temel Sıfatlar",
    "basic adjectives": "Temel Sıfatlar",
    "personal description": "Kişisel Tanım",
    "using 'ser' to describe identity": "'Ser' Kullanarak Kimliği Tanımlama",
    "using ser to describe identity": "'Ser' Kullanarak Kimliği Tanımlama",
    "talking about age and nationality": "Yaş ve Milliyet Hakkında Konuşma",
    "age and nationality": "Yaş ve Milliyet",
    "everyday survival vocabulary": "Günlük Hayatta Kalma Kelimeleri",
    "survival vocabulary": "Hayatta Kalma Kelimeleri",
    "everyday survival": "Günlük Hayatta Kalma",
    "essential vocabulary for traveling": "Seyahat İçin Temel Kelimeler",
    "vocabulary for traveling": "Seyahat İçin Kelimeler",
    "essential vocabulary": "Temel Kelimeler",
    "navigating public transportation": "Toplu Taşımada Yol Bulma",
    "public transportation": "Toplu Taşıma",
    "basic food and drink vocabulary": "Temel Yiyecek ve İçecek Kelimeleri",
    "food and drink vocabulary": "Yiyecek ve İçecek Kelimeleri",
    "food and drink": "Yiyecek ve İçecek",
    "basic food and drinks": "Temel Yiyecek ve İçecekler",
    "numbers and basic math": "Sayılar ve Temel Matematik",
    "counting from 1 to 100": "1'den 100'e Sayma",
    "numbers in context": "Bağlam İçinde Sayılar",
    "basic math operations": "Temel Matematik İşlemleri",
    "days, months, and time": "Günler, Aylar ve Zaman",
    "days, months and time": "Günler, Aylar ve Zaman",
    "days of the week": "Haftanın Günleri",
    "months and seasons": "Aylar ve Mevsimler",
    "telling time": "Saati Söyleme",
    "essential survival vocabulary": "Temel Hayatta Kalma Kelimeleri",
    "common emergency phrases": "Acil Durum İfadeleri",
    "asking for help": "Yardım İsteme",
    "basic signs and warnings": "Temel İşaretler ve Uyarılar",
    "physical appearance": "Fiziksel Görünüş",
    "personality traits": "Kişilik Özellikleri",
    "forming basic sentences": "Temel Cümleler Oluşturma",
    "subject pronouns and verb 'to be'": "Özne Zamirleri ve Olmak Fiili",
    "subject pronouns": "Özne Zamirleri",
    "basic sentence structure": "Temel Cümle Yapısı",
    "negation and questions": "Olumsuzluk ve Soru Cümleleri",
    "daily activities and routines": "Günlük Aktiviteler ve Rutinler",
    "everyday routines": "Günlük Rutinler",
    "morning to night routines": "Sabahtan Akşama Rutinler",
    "talking about your day": "Gününüz Hakkında Konuşma",
    "frequency adverbs": "Sıklık Zarfları",
    "family and relationships": "Aile ve İlişkiler",
    "family members": "Aile Üyeleri",
    "describing family relations": "Aile İlişkilerini Anlatma",
    "possessive adjectives": "İyelik Sıfatları",
    "hobbies and interests": "Hobiler ve İlgi Alanları",
    "free time activities": "Boş Zaman Aktiviteleri",
    "sports and games": "Sporlar ve Oyunlar",
    "expressing likes and dislikes": "Beğenileri ve Sevmediklerini Belirtme",
    "food and dining": "Yiyecekler ve Yemek",
    "ordering food": "Yemek Siparişi Verme",
    "at the restaurant": "Restoranda",
    "shopping and clothes": "Alışveriş ve Giysiler",
    "buying clothes": "Kıyafet Satın Alma",
    "asking for prices": "Fiyat Sorma",
    "colors and sizes": "Renkler ve Bedenler",
    "around town and directions": "Şehirde ve Yol Tarifleri",
    "asking for directions": "Yol Tarifi Sorma",
    "places in town": "Şehirdeki Yerler",
    "transportation": "Ulaşım",
    "travel and vacation": "Seyahat ve Tatil",
    "at the airport": "Havalimanında",
    "at the train station": "Tren İstasyonunda",
    "hotel check-in": "Otele Giriş Yapma",
    "cultural insights": "Kültürel Bilgiler",
    "cultural context": "Kültürel Bağlam",
    "review and practice": "Tekrar ve Pratik",
    "review and practical application": "Tekrar ve Pratik Uygulama",
    "practical application": "Pratik Uygulama",
    "comprehensive review": "Kapsamlı Tekrar",
    "the world around us": "Çevremizdeki Dünya",
    "world around us": "Çevremizdeki Dünya",
    "weather and seasons": "Hava Durumu ve Mevsimler",
    "nature and environment": "Doğa ve Çevre",
    "health and emergencies": "Sağlık ve Acil Durumlar",
    "common health issues and symptoms": "Yaygın Sağlık Sorunları ve Belirtiler",
    "seeking help: phrases for emergencies": "Yardım İsteme: Acil Durum İfadeleri",
    "seeking help": "Yardım İsteme",
    "phrases for emergencies": "Acil Durum İfadeleri",
    "visiting a doctor: key questions": "Doktora Gitmek: Anahtar Sorular",
    "visiting a doctor": "Doktora Gitmek",
    "key questions": "Anahtar Sorular",
    "hobbies and free time activities": "Hobiler ve Boş Zaman Aktiviteleri",
    "discussing hobbies: what do you like to do?": "Hobiler Üzerine Tartışmak: Ne Yapmayı Seversin?",
    "common leisure activities: playing sports, reading": "Yaygın Boş Zaman Aktiviteleri: Spor Oynamak, Okumak",
    "making plans with friends: invitations and suggestions": "Arkadaşlarla Plan Yapmak: Davetler ve Öneriler",
    "cultural insights: festivals and traditions": "Kültürel Bilgiler: Festivaller ve Gelenekler",
    "introduction to german festivals: oktoberfest, christmas": "Alman Festivallerine Giriş: Oktoberfest, Noel",
    "common traditions: gifts, food, and celebrations": "Yaygın Gelenekler: Hediyeler, Yemek ve Kutlamalar",
    "basic phrases for celebratory situations": "Kutlama Durumları İçin Temel İfadeler",
    "celebratory situations": "Kutlama Durumları",
    "asking for and giving recommendations": "Tavsiye İstemek ve Vermek",
    "asking for prices and making simple transactions": "Fiyat Sormak ve Basit Alışveriş Yapmak",
    "understanding menus: key phrases": "Menüleri Anlamak: Anahtar İfadeler",
    "essential shopping vocabulary: clothes and accessories": "Temel Alışveriş Kelimeleri: Kıyafetler ve Aksesuarlar",
    "understanding sizes and colors": "Bedenleri ve Renkleri Anlamak",
    "navigating your community": "Toplulukta Yol Tarifi ve İletişim",
    "asking for directions: where is...?": "Yol Tarifi Sormak: ... Nerede?",
    "key places in the community: bank, post office, etc.": "Topluluktaki Önemli Yerler: Banka, Postane, vb.",
    "using public transport: basic vocabulary and phrases": "Toplu Taşımayı Kullanmak: Temel Kelimeler ve İfadeler"
}

def load_title_cache() -> Dict[str, str]:
    """Loads cached title translations from bilingual_materials.json."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("title_pairs", {})
        except Exception as e:
            logger.warning(f"Error loading title cache: {e}")
    return {}

def save_title_cache(pairs: Dict[str, str]):
    """Saves updated title translations back to bilingual_materials.json and rebuilds JS bundle."""
    if not pairs:
        return
    data = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    
    tp = data.setdefault("title_pairs", {})
    changed = False
    for k, v in pairs.items():
        if k and v and tp.get(k) != v:
            tp[k] = v
            changed = True
            
    if changed:
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            try:
                from services.bilingual_finisher import rebuild_bilingual_bundle
                rebuild_bilingual_bundle()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed to save title pairs cache: {e}")

def clean_stutter(text: str) -> str:
    """Removes word duplication, stuttering, and awkward repetitive phrasing."""
    if not text or not isinstance(text, str):
        return ""
    t = str(text).strip()
    t = re.sub(r'\bGünlük\s+Hayatta\s+Hayatta\s+Kalma\b', 'Günlük Hayatta Kalma', t, flags=re.IGNORECASE)
    t = re.sub(r'\bHayatta\s+Hayatta\b', 'Hayatta', t, flags=re.IGNORECASE)
    t = re.sub(r'\bve\s+ve\b', 've', t, flags=re.IGNORECASE)
    t = re.sub(r'\bveya\s+veya\b', 'veya', t, flags=re.IGNORECASE)
    t = re.sub(r'\biçin\s+için\b', 'için', t, flags=re.IGNORECASE)
    t = re.sub(r'\bde\s+de\b', 'de', t, flags=re.IGNORECASE)
    t = re.sub(r'\bda\s+da\b', 'da', t, flags=re.IGNORECASE)
    t = re.sub(r'\bile\s+ile\b', 'ile', t, flags=re.IGNORECASE)
    def _repl_dup(m):
        w = m.group(1)
        if w.lower() in ('yavaş', 'adım', 'tek', 'ayrı', 'az'):
            return m.group(0)
        return w
    t = re.sub(r'\b([a-zA-ZçğıöşüÇĞİÖŞÜâîû]+)\s+\1\b', _repl_dup, t, flags=re.IGNORECASE)
    t = re.sub(r',\s*ve\b', ' ve', t, flags=re.IGNORECASE)
    t = re.sub(r'\s{2,}', ' ', t).strip()
    return t

TR_LETTERS = re.compile(r'[çğıöşüÇĞİÖŞÜâîû]')
TR_WORDS = re.compile(r'\b(ve|veya|ile|için|göre|kadar|temel|pratik|uygulama|tekrar|alfabe|selamlaşma|tanıtım|tanıtımlar|günlük|rutinler|sayılar|zaman|saat|aile|ilişkiler|hobiler|yiyecek|yemek|alışveriş|kıyafet|şehir|ulaşım|seyahat|tatil|kültür|kültürel|bilgiler|bağlam|dilbilgisi|kelimeler|cümleler|ifadeler|fiiller|sıfatlar|zamirler|sorular|çevremizdeki|dünya|doğa|sağlık|iş|okul|ev|yerler|yol|tarifi|hava|durumu|mevsimler|doktora|gitmek|kutlama|durumları|işlevsel|topluluk|hediyeler|kutlamalar|tanım|tanımlama|kimlik)\b', re.IGNORECASE)

EN_WORDS = re.compile(
    r'\b(the|and|of|to|in|for|with|on|at|from|by|about|your|our|their|my|his|her|its|you|we|they|'
    r'describing|talking|using|navigating|understanding|introducing|asking|making|expressing|telling|visiting|seeking|'
    r'review|practice|practical|application|foundations|basics|intermediate|advanced|grammar|vocabulary|'
    r'words|phrases|sentences|daily|activities|routines|food|dining|shopping|environment|travel|traveling|travelling|questions|answers|'
    r'math|operations|culture|insights|context|customs|survival|numbers|counting|alphabet|vowels|consonants|'
    r'pronunciation|phonetics|rules|check|guide|overview|summary|world|around|us|'
    r'functional|language|situations|celebratory|emergencies|emergency|health|traditions|festivals|leisure|sports|'
    r'hobbies|community|recommendations|transactions|menus|accessories|sizes|colors|transport|transportation|places|'
    r'personal|description|identity|adjectives|adjective|nouns|noun|verbs|verb|conversation|dialogues|dialogue|'
    r'objects|friends|friendship|free|time|interests|ordering|buying|giving|directions|family|members|'
    r'feelings|emotions|workplace|office|home|school|weather|seasons|calendar|dates|essential|everyday|simple)\b',
    re.IGNORECASE
)

def is_hybrid(text: str) -> bool:
    """Returns True if the string is a Frankenstein English-Turkish mixture."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if not t:
        return False
    low = t.lower()
    if re.search(r'\bve\s+ve\b', low) or "pratik application" in low or "ve pratik application" in low or "around us" in low:
        return True
    # Exclude target language terms in single quotes (like 'ser', 'estar', 'haben')
    quoted = set(m.strip("'\"").lower() for m in re.findall(r"['\"][^'\"]+['\"]", t))
    matches = [m.lower() for m in EN_WORDS.findall(t)]
    leaked = [m for m in matches if m not in quoted]
    has_tr = bool(TR_LETTERS.search(t) or TR_WORDS.search(t))
    return bool(leaked) and has_tr

def is_pure_english(text: str) -> bool:
    """Returns True if the string is in English."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if not t or is_hybrid(t):
        return False
    if TR_LETTERS.search(t):
        return False
    low = t.lower()
    if low in ("functional language", "cultural context", "vocabulary", "grammar"):
        return True
    quoted = set(m.strip("'\"").lower() for m in re.findall(r"['\"][^'\"]+['\"]", t))
    matches = [m.lower() for m in EN_WORDS.findall(t)]
    leaked = [m for m in matches if m not in quoted]
    return bool(leaked)

def is_clean_turkish(text: str) -> bool:
    """Returns True if the string is genuine Turkish with no leaked English words and no stutter."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if not t or is_hybrid(t) or is_pure_english(t):
        return False
    if re.search(r'\b(ve\s+ve|veya\s+veya|için\s+için|hayatta\s+hayatta)\b', t, re.IGNORECASE):
        return False
    quoted = set(m.strip("'\"").lower() for m in re.findall(r"['\"][^'\"]+['\"]", t))
    matches = [m.lower() for m in EN_WORDS.findall(t)]
    leaked = [m for m in matches if m not in quoted]
    if leaked:
        return False
    low = t.lower()
    if "functional language" in low or "cultural context" in low or "celebratory situations" in low:
        return False
    return True

def is_hybrid_or_english(text: str) -> bool:
    """Returns True if text is either a hybrid or English."""
    return is_hybrid(text) or is_pure_english(text) or not is_clean_turkish(text)

def _clean_title_key(title: str) -> str:
    """Normalizes title for cache lookup by stripping unit prefixes."""
    if not title:
        return ""
    cleaned = re.sub(r'^(unit|chapter|tema|lektion|ünite|bölüm)\s*\d+\s*[:\-]\s*', '', title.strip(), flags=re.IGNORECASE)
    return cleaned.strip()

def translate_titles_batch(titles: List[str], target_lang: str = "tr") -> Dict[str, str]:
    """
    Translates a list of curriculum titles into target_lang ('tr' or 'en').
    Prioritizes:
    1. Exact canonical map
    2. bilingual_materials.json cache (verified clean)
    3. LLM batch translation (via OpenRouter / _call_ai)
    """
    if not titles:
        return {}

    cache = load_title_cache()
    results: Dict[str, str] = {}
    needed: List[str] = []

    for raw in titles:
        if not raw or not isinstance(raw, str):
            continue
        clean = _clean_title_key(raw)
        if not clean:
            continue

        low_clean = clean.lower()

        # 1. Canonical dictionary match
        if target_lang == "tr":
            if low_clean in CANONICAL_TITLE_MAP:
                results[raw] = CANONICAL_TITLE_MAP[low_clean]
                continue
            # Check cached title_pairs
            cached_val = cache.get(clean) or cache.get(raw)
            if cached_val and is_clean_turkish(cached_val):
                results[raw] = cached_val
                continue
        elif target_lang == "en":
            # Reverse canonical match
            rev = next((k for k, v in CANONICAL_TITLE_MAP.items() if v.lower() == low_clean), None)
            if rev:
                results[raw] = rev.title()
                continue
            # Reverse cache lookup
            rev_cached = next((k for k, v in cache.items() if v.lower() == low_clean and not is_hybrid_or_english(k)), None)
            if rev_cached:
                results[raw] = rev_cached
                continue

        needed.append(raw)

    if not needed:
        return results

    # Deduplicate needed
    unique_needed = list(dict.fromkeys(needed))
    dest_name = "Turkish" if target_lang == "tr" else "English"
    logger.info(f"[CURRICULUM TRANSLATOR] Translating {len(unique_needed)} titles to {dest_name} via AI...")

    # Call AI in batches
    batch_size = 25
    newly_translated: Dict[str, str] = {}

    for i in range(0, len(unique_needed), batch_size):
        chunk = unique_needed[i:i + batch_size]
        indexed_input = {str(idx): chunk[idx] for idx in range(len(chunk))}
        
        prompt = f"""You are a master curriculum translator for language learning platforms.
Translate each curriculum unit title or topic title into natural, fluent, grammatically correct {dest_name}.

STRICT RULES:
1. Every translation MUST be 100% fluent {dest_name}. NEVER mix English and Turkish words together.
2. Absolutely NO Frankenstein hybrids like 'Personal Description İçin Temel Sıfatlar' or 'Traveling İçin Temel Kelimeler'.
   Translate the ENTIRE title holistically:
   - 'Basic Adjectives for Personal Description' -> 'Kişisel Tanım İçin Temel Sıfatlar'
   - 'Essential Vocabulary for Traveling' -> 'Seyahat İçin Temel Kelimeler'
   - 'Everyday Survival Vocabulary' -> 'Günlük Hayatta Kalma Kelimeleri'
   - 'Using Ser to Describe Identity' -> ''Ser' Kullanarak Kimliği Tanımlama'
3. NEVER repeat or duplicate words (e.g. NEVER write 'Günlük Hayatta Hayatta Kalma' or 've ve').
4. Keep target language foreign terms (like Spanish verbs 'ser', 'estar' or German verbs) unchanged in single quotes.
5. Return ONLY a JSON object mapping each string index ("0", "1", ...) to its translation string.

Input:
{json.dumps(indexed_input, ensure_ascii=False, indent=2)}"""

        res = None
        try:
            from services.ai_engine import _call_ai
            res = _call_ai([{"role": "user", "content": prompt}], max_tokens=1500, temperature=0.0)
        except Exception as e:
            logger.error(f"[CURRICULUM TRANSLATOR] AI call failed: {e}")

        if isinstance(res, dict):
            mapping = res.get("translations") or res
            for idx_str, trans in mapping.items():
                try:
                    idx = int(idx_str)
                    if 0 <= idx < len(chunk) and isinstance(trans, str):
                        orig = chunk[idx]
                        trans_clean = clean_stutter(trans.strip())
                        if target_lang == "tr":
                            if is_clean_turkish(trans_clean):
                                newly_translated[orig] = trans_clean
                                results[orig] = trans_clean
                            else:
                                try:
                                    from services.language_data import UniversalCurriculumTranslator
                                    uct_val = clean_stutter(UniversalCurriculumTranslator.translate(orig))
                                    if is_clean_turkish(uct_val):
                                        newly_translated[orig] = uct_val
                                        results[orig] = uct_val
                                except Exception: pass
                        elif target_lang == "en":
                            newly_translated[orig] = trans_clean
                            results[orig] = trans_clean
                except (ValueError, TypeError):
                    continue

    # Fallback for anything that AI failed to translate
    for raw in unique_needed:
        if raw not in results or (target_lang == "tr" and not is_clean_turkish(results[raw])):
            clean = _clean_title_key(raw)
            low_clean = clean.lower()
            if target_lang == "tr":
                cand = CANONICAL_TITLE_MAP.get(low_clean)
                if not cand:
                    try:
                        from services.language_data import UniversalCurriculumTranslator
                        uct_cand = clean_stutter(UniversalCurriculumTranslator.translate(clean))
                        if uct_cand and is_clean_turkish(uct_cand):
                            cand = uct_cand
                    except Exception: pass
                results[raw] = clean_stutter(cand or CANONICAL_TITLE_MAP.get(low_clean) or clean)
            else:
                results[raw] = clean

    # Save clean translations to cache
    if newly_translated and target_lang == "tr":
        save_title_cache(newly_translated)

    return results

def ensure_bilingual_curriculum(chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ensures every chapter and topic in chapters has both a valid English 'title'
    and a valid Turkish 'title_tr' without any hybrid artifacts or stutters.
    Performs batch translation for any missing or unclean titles.
    """
    if not chapters:
        return []

    titles_needing_tr: List[str] = []
    titles_needing_en: List[str] = []

    for ch in chapters:
        ch_title = ch.get("title", "").strip()
        ch_tr = clean_stutter(ch.get("title_tr", "").strip())
        ch["title_tr"] = ch_tr

        # Check chapter
        if not ch_tr or not is_clean_turkish(ch_tr) or ch_tr.lower() == ch_title.lower() or is_pure_english(ch_tr) or is_hybrid(ch_tr):
            if ch_title:
                titles_needing_tr.append(ch_title)
        if not ch_title or is_clean_turkish(ch_title) or is_hybrid(ch_title):
            if ch_tr and is_clean_turkish(ch_tr):
                titles_needing_en.append(ch_tr)
            elif ch_title:
                titles_needing_en.append(ch_title)

        # Check topics
        for t in ch.get("topics", []):
            t_title = (t.get("title") if isinstance(t, dict) else str(t)).strip()
            t_tr = clean_stutter((t.get("title_tr", "") if isinstance(t, dict) else "").strip())
            if isinstance(t, dict):
                t["title_tr"] = t_tr

            if not t_tr or not is_clean_turkish(t_tr) or t_tr.lower() == t_title.lower() or is_pure_english(t_tr) or is_hybrid(t_tr):
                if t_title:
                    titles_needing_tr.append(t_title)
            if not t_title or is_clean_turkish(t_title) or is_hybrid(t_title):
                if t_tr and is_clean_turkish(t_tr):
                    titles_needing_en.append(t_tr)
                elif t_title:
                    titles_needing_en.append(t_title)

    # Batch translate missing Turkish
    tr_translations = {}
    if titles_needing_tr:
        tr_translations = translate_titles_batch(titles_needing_tr, target_lang="tr")

    # Batch translate missing English
    en_translations = {}
    if titles_needing_en:
        en_translations = translate_titles_batch(titles_needing_en, target_lang="en")

    # Apply back and sanitize with clean_stutter
    for ch in chapters:
        curr_title = ch.get("title", "").strip()
        curr_tr = clean_stutter(ch.get("title_tr", "").strip())

        # Heal Turkish
        if not curr_tr or not is_clean_turkish(curr_tr) or curr_tr.lower() == curr_title.lower() or is_pure_english(curr_tr) or is_hybrid(curr_tr):
            candidate = tr_translations.get(curr_title, curr_tr or curr_title)
            ch["title_tr"] = clean_stutter(candidate)
        else:
            ch["title_tr"] = clean_stutter(curr_tr)

        # Heal English
        if not curr_title or is_clean_turkish(curr_title) or is_hybrid(curr_title):
            ch["title"] = en_translations.get(curr_tr, en_translations.get(curr_title, curr_title))

        # Heal Topics
        for t in ch.get("topics", []):
            if not isinstance(t, dict):
                continue
            topic_title = t.get("title", "").strip()
            topic_tr = clean_stutter(t.get("title_tr", "").strip())

            if not topic_tr or not is_clean_turkish(topic_tr) or topic_tr.lower() == topic_title.lower() or is_pure_english(topic_tr) or is_hybrid(topic_tr):
                candidate = tr_translations.get(topic_title, topic_tr or topic_title)
                t["title_tr"] = clean_stutter(candidate)
            else:
                t["title_tr"] = clean_stutter(topic_tr)

            if not topic_title or is_clean_turkish(topic_title) or is_hybrid(topic_title):
                t["title"] = en_translations.get(topic_tr, en_translations.get(topic_title, topic_title))

    return chapters
