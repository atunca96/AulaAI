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
    "saying hello and goodbye": "Merhaba ve Hoşça Kal Deme",
    "introducing yourself": "Kendini Tanıtma",
    "formal vs informal": "Resmi ve Samimi Hitaplar",
    "formal vs informal speech": "Resmi ve Samimi Konuşma",
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
    "describing yourself and others": "Kendini ve Başkalarını Tanımlama",
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
    "nature and environment": "Doğa ve Çevre"
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

TR_LETTERS = re.compile(r'[çğıöşüÇĞİÖŞÜâîû]')
TR_WORDS = re.compile(r'\b(ve|veya|ile|için|göre|kadar|temel|pratik|uygulama|tekrar|alfabe|selamlaşma|tanıtım|tanıtımlar|günlük|rutinler|sayılar|zaman|saat|aile|ilişkiler|hobiler|yiyecek|yemek|alışveriş|kıyafet|şehir|ulaşım|seyahat|tatil|kültür|kültürel|bilgiler|bağlam|dilbilgisi|kelimeler|cümleler|ifadeler|fiiller|sıfatlar|zamirler|sorular|çevremizdeki|dünya|doğa|sağlık|iş|okul|ev|yerler|yol|tarifi|hava|durumu|mevsimler)\b', re.IGNORECASE)

EN_WORDS = re.compile(r'\b(the|and|of|to|in|for|with|on|at|from|by|about|your|our|their|my|his|her|its|you|we|they|describing|talking|using|navigating|understanding|introducing|asking|making|expressing|review|practice|practical|application|foundations|basics|intermediate|advanced|grammar|vocabulary|words|phrases|sentences|daily|activities|routines|food|dining|shopping|environment|travel|questions|answers|math|operations|culture|insights|context|customs|survival|numbers|alphabet|vowels|consonants|pronunciation|phonetics|rules|check|guide|overview|summary|world|around|us)\b', re.IGNORECASE)

def is_hybrid(text: str) -> bool:
    """Returns True if the string is a Frankenstein English-Turkish mixture."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if not t:
        return False
    low = t.lower()
    if "ve ve" in low or "pratik application" in low or "ve pratik application" in low or "around us" in low:
        return True
    has_tr = bool(TR_LETTERS.search(t) or TR_WORDS.search(t))
    has_en = bool(EN_WORDS.search(t))
    return has_tr and has_en

def is_pure_english(text: str) -> bool:
    """Returns True if the string is in English."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if not t or is_hybrid(t):
        return False
    if TR_LETTERS.search(t):
        return False
    return bool(EN_WORDS.search(t))

def is_clean_turkish(text: str) -> bool:
    """Returns True if the string is genuine Turkish with no leaked English words."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if not t or is_hybrid(t):
        return False
    if is_pure_english(t):
        return False
    if EN_WORDS.search(t):
        return False
    return True

def is_hybrid_or_english(text: str) -> bool:
    """Returns True if text is either a hybrid or English."""
    return is_hybrid(text) or is_pure_english(text)

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
1. Every translation MUST be 100% fluent {dest_name}. Do NOT mix English and Turkish words together.
2. If translating to Turkish, NEVER output hybrids like 'Review ve Pratik' or 'Cultural Insights: Understanding German Customs'.
   Translate the ENTIRE phrase holistically (e.g. 'Tekrar ve Pratik Uygulama', 'Kültürel Bilgiler: Alman Geleneklerini Anlama').
3. Keep target language foreign terms (like Spanish verbs 'ser vs estar' or French words) unchanged in single quotes.
4. Return ONLY a JSON object mapping each string index ("0", "1", ...) to its translation string.

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
                        trans_clean = trans.strip()
                        if target_lang == "tr" and not is_hybrid_or_english(trans_clean):
                            newly_translated[orig] = trans_clean
                            results[orig] = trans_clean
                        elif target_lang == "en":
                            newly_translated[orig] = trans_clean
                            results[orig] = trans_clean
                except (ValueError, TypeError):
                    continue

    # Fallback for anything that AI failed to translate
    for raw in unique_needed:
        if raw not in results:
            clean = _clean_title_key(raw)
            low_clean = clean.lower()
            if target_lang == "tr":
                results[raw] = CANONICAL_TITLE_MAP.get(low_clean, clean)
            else:
                results[raw] = clean

    # Save clean translations to cache
    if newly_translated and target_lang == "tr":
        save_title_cache(newly_translated)

    return results

def ensure_bilingual_curriculum(chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ensures every chapter and topic in chapters has both a valid English 'title'
    and a valid Turkish 'title_tr' without any hybrid artifacts.
    Performs batch translation for any missing or unclean titles.
    """
    if not chapters:
        return []

    titles_needing_tr: List[str] = []
    titles_needing_en: List[str] = []

    for ch in chapters:
        ch_title = ch.get("title", "").strip()
        ch_tr = ch.get("title_tr", "").strip()

        # Check chapter
        if not ch_tr or not is_clean_turkish(ch_tr):
            if ch_title:
                titles_needing_tr.append(ch_title)
        if not ch_title or is_clean_turkish(ch_title):
            # If title is in Turkish, we need English for title
            if ch_tr:
                titles_needing_en.append(ch_tr)
            elif ch_title:
                titles_needing_en.append(ch_title)

        # Check topics
        for t in ch.get("topics", []):
            t_title = (t.get("title") if isinstance(t, dict) else str(t)).strip()
            t_tr = (t.get("title_tr", "") if isinstance(t, dict) else "").strip()

            if not t_tr or not is_clean_turkish(t_tr):
                if t_title:
                    titles_needing_tr.append(t_title)
            if not t_title or is_clean_turkish(t_title):
                if t_tr:
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

    # Apply back
    for ch in chapters:
        curr_title = ch.get("title", "").strip()
        curr_tr = ch.get("title_tr", "").strip()

        # Heal Turkish
        if not curr_tr or not is_clean_turkish(curr_tr):
            ch["title_tr"] = tr_translations.get(curr_title, curr_tr or curr_title)

        # Heal English
        if not curr_title or is_clean_turkish(curr_title):
            ch["title"] = en_translations.get(curr_tr, en_translations.get(curr_title, curr_title))

        # Heal Topics
        for t in ch.get("topics", []):
            if not isinstance(t, dict):
                continue
            topic_title = t.get("title", "").strip()
            topic_tr = t.get("title_tr", "").strip()

            if not topic_tr or not is_clean_turkish(topic_tr):
                t["title_tr"] = tr_translations.get(topic_title, topic_tr or topic_title)

            if not topic_title or is_clean_turkish(topic_title):
                t["title"] = en_translations.get(topic_tr, en_translations.get(topic_title, topic_title))

    return chapters
