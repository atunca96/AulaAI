"""
Fast Deterministic Curriculum Parser

Replaces AI-based curriculum parsing with regex + heuristic parsing.
Handles bullet lists, numbered outlines, table formats, and flat text.
Produces the same output schema as the AI parser:

    {"chapters": [{"title": "...", "page": N, "topics": [{"title": "...", "type": "...", "page": N}]}]}

Design: Single-pass, language-agnostic, zero dependencies beyond stdlib.
"""

import re

# ── Topic Type Classification ────────────────────────────────────────

GRAMMAR_KEYS = [
    "verb", "conjugat", "grammar", "gramática", "grammatik", "grammaire",
    "tense", "pronoun", "pronom", "article", "artículo", "artikel",
    "preposition", "préposition", "preposi", "syntax", "word order",
    "subjunctiv", "indicativ", "imperativ", "conditional", "gerund",
    "infinitiv", "particip", "reflexiv", "possessiv", "demonstrativ",
    "comparat", "superlativ", "negat", "interrogat", "passiv",
    "adjective", "adverb", "plural", "singular", "declens", "conjug",
    "struktur", "regla", "regel", "règle", "satzbau", "satzstellung",
    "accord", "concordan", "case", "kasus", "fall", "casus", "cas",
    "noun", "sentence", "phrase", "вопрос", "существительн", 
    "глагол", "наречие", "прилагательн", "местоимени", "падеж", "склонени",
    "чей", "кто", "что", "где", "когда", "куда", "откуда", "почему", "как", "сколько",
    "quien", "que", "donde", "cuando", "como", "cuanto", "por que", "cual",
    "isim", "fiil", "sıfat", "zarf", "zamir", "cümle", "gramer", "dilbilgisi",
    "werkwoord", "zelfstandig naamwoord", "bijvoeglijk", "bijwoord", "zin", "grammatica",
    "substantiv", "adjektiv", "mening", "grammatik", "грамматика", "лексика", "навыки",
    "ρήμα", "ουσιαστικό", "επίθετο", "επίρρημα", "γραμματική", "πρόταση",
    "فعل", "اسم", "صفة", "ظرف", "جملة", "قواعد",
    "动词", "名词", "形容词", "副词", "句子", "语法",
    "動詞", "名詞", "形容詞", "副詞", "文", "文法",
    "동사", "명사", "형용사", "부사", "문장", "문법"
]

READING_KEYS = [
    "reading", "lectura", "lesen", "lecture", "text", "story",
    "cultura", "culture", "kultur", "civilization", "video",
    "film", "película", "song", "canción", "lied", "chanson",
    "literatur", "poesía", "poetry", "poème", "novela", "novel",
    "article", "interview", "entrevista",
]

META_SKIP = [
    "about", "author", "license", "preface", "index", "bibliography", "appendix", 
    "glossary", "glosario", "acknowledgment", "copyright", "introduction to the",
    "table of contents", "answer key", "respuestas", "credits", "maps", "map of", 
    "scope and sequence", "contents", "sommaire", "table des matières", "inhalt", 
    "inhaltsverzeichnis", "indice", "índice", "sommario", "sumário", "содержание", 
    "оглавление", "içindekiler", "extracted content", "source page", "приложение", 
    "аудио", "задание", "упражнение", "русский на каждый день", "review", 
    "references", "точкару", "точка ру", "дополнительно", "тесты", 
    "проверьте себя", "extra practice", "workbook", "cuaderno", "arbeitsbuch", 
    "exercice", "test yourself", "self-check", "audio scripts", "transcripts", 
    "интервью", "миграционной карты", "коммуникативные задания", "аудиоприложение", 
    "проверь себя", "ответы к заданиям", "ссылки"
]


def classify_topic(title):
    """Classify a topic title as vocabulary or grammar based on function."""
    t_lower = title.lower()
    # Interrogative function is always Grammar
    if '?' in title or '¿' in title:
        return "grammar"
    # Structural keywords across 15+ languages
    if any(k in t_lower for k in GRAMMAR_KEYS):
        return "grammar"
    return "vocabulary"


def is_meta_section(title):
    """Returns True if the title looks like a non-teaching section."""
    t_lower = title.lower().strip()
    return any(m in t_lower for m in META_SKIP)


# ── Page Number Extraction ───────────────────────────────────────────

def extract_page_number(line):
    """
    Extract a page number from a line.
    Handles:
      - Trailing numbers: "Unit 1: Greetings .... 23"
      - Parenthesized: "(p. 23)" or "(Page 23)"
      - Dotted leaders: "Topic Name ......... 45"
      - [Page X] markers from PDF extraction
    Returns (cleaned_line, page_number) or (line, None).
    """
    # [Page X] markers
    m = re.search(r'\[Page\s*(\d+)\]', line)
    if m:
        page = int(m.group(1))
        cleaned = re.sub(r'\[Page\s*\d+\]', '', line).strip()
        return cleaned, page

    # Parenthesized page refs: (p. 23), (Page 23), (S. 23), (pág. 23)
    m = re.search(r'\((?:p(?:age|ág)?\.?\s*)?(\d+)\)\s*$', line, re.IGNORECASE)
    if m:
        page = int(m.group(1))
        cleaned = line[:m.start()].strip()
        return cleaned, page

    # Trailing number after dots/spaces/tabs: "Topic Name .... 45" or "Topic Name    45"
    m = re.search(r'[\s.·…_-]{3,}(\d+)\s*$', line)
    if m:
        page = int(m.group(1))
        cleaned = line[:m.start()].strip()
        return cleaned, page

    # Simple trailing number (at least 2 spaces before it)
    m = re.search(r'\s{2,}(\d+)\s*$', line)
    if m:
        page = int(m.group(1))
        cleaned = line[:m.start()].strip()
        return cleaned, page

    return line, None


# ── Unit/Chapter Header Detection ────────────────────────────────────

# Language-agnostic unit markers
UNIT_PATTERN = re.compile(
    r'^(?:'
    r'(?:unit|chapter|module|unidad|unité|lektion|kapitel|lección|leccion|tema|thème|chapitre|modulo|módulo|etapa|paso|stufe|урок|раздел|часть)'
    r'\s*\.?\s*(\d+)'           # "Unit 1", "Unidad 1", etc.
    r'|(\d+)\s*[.:/\\\-–—]\s*'  # "1. Title", "1: Title", "1/ Title"
    r'|([IVXLC]+)\s*[.:/\\\-–—]\s*'  # "I. Title", "IV: Title"
    r')',
    re.IGNORECASE
)

# Detect if a line is a chapter/unit header
def is_chapter_header(line):
    """
    Determines if a line is a chapter/unit header.
    Returns (True, chapter_number_str) or (False, None).
    """
    # Clean leading Markdown symbols
    clean_line = re.sub(r'^[#\*_\-\s]+', '', line.strip()).strip()
    if not clean_line or len(clean_line) < 3:
        return False, None

    # Skip meta sections
    if is_meta_section(clean_line):
        return False, None

    # 1. Standard Patterns
    m = UNIT_PATTERN.match(clean_line)
    if m:
        num = m.group(1) or m.group(2) or m.group(3)
        return True, num

    # 2. Heuristic: All-caps short lines that don't look like topics
    # Topics in this book are often "RECURSOS ..." or start with lowercase.
    # Unit headers are often "DIAADIA", "EL BARRIO", "NOSOTROS Y NOSOTRAS"
    if clean_line.isupper() and len(clean_line) < 35:
        # Exclude common noisy caps that are NOT units
        if not any(k in clean_line for k in ["RECURSOS", "GRAMATICALES", "COMUNICATIVOS", "LÉXICOS", "VOCABULARIO"]):
            return True, "H" # Heuristic header

    return False, None


# ── Indentation Detection ────────────────────────────────────────────

def get_indent_level(line):
    """Returns the indentation level (number of leading spaces/tabs)."""
    stripped = line.lstrip()
    if not stripped:
        return 0
    indent = len(line) - len(stripped)
    # Convert tabs to 4 spaces equivalent
    tab_count = line[:indent].count('\t')
    space_count = indent - tab_count
    return tab_count * 4 + space_count


# ── Main Parser ──────────────────────────────────────────────────────

def parse_curriculum_text(text):
    """
    Parse curriculum text into structured units/chapters.
    Rewritten for higher stability and fewer fragments.
    """
    if not text or not text.strip():
        return []

    chapters = []
    current_chapter = None
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 1. Internal Bullet Splitting: "Topic 1 • Topic 2 • Topic 3"
        # We split the line and treat each part as a separate topic/line
        if '•' in line:
            parts = [p.strip() for p in line.split('•') if p.strip()]
            lines[i:i+1] = parts
            line = lines[i]

        # 2. Detect Chapter/Unit Header
        is_ch, ch_num = is_chapter_header(line)
        if is_ch:
            if current_chapter: chapters.append(current_chapter)
            title = re.sub(r'^[#\*_\-\s.:/]+|[#\*_\-\s.:/]+$', '', line).strip()
            # Clean "3/ " from title if matched by UNIT_PATTERN
            title = re.sub(r'^\d+\s*[.:/\\\-–—]\s*', '', title).strip()
            current_chapter = {"title": title, "topics": []}
            i += 1
            continue

        # 2. Topic Discovery & Merging
        # We look ahead to see if the next lines are continuations of this topic
        # Topics usually end with [vocabulary] or [grammar] or are bullet points
        content = line
        topic_type = classify_topic(content)
        
        # If this line has a tag, use it immediately
        tag_match = re.search(r'[\[\(]\s*(vocabulary|grammar)\s*[\]\)]', content, re.I)
        if tag_match:
            topic_type = tag_match.group(1).lower()
            content = content[:tag_match.start()].strip()
        else:
            # Look ahead: merge until we hit a new bullet, a new unit, or a tag
            while i + 1 < len(lines):
                nxt = lines[i+1]
                if is_chapter_header(nxt)[0]: break
                if nxt.startswith('-') or nxt.startswith('•') or nxt.startswith('*'): break
                
                nxt_tag = re.search(r'[\[\(]\s*(vocabulary|grammar)\s*[\]\)]', nxt, re.I)
                if nxt_tag:
                    topic_type = nxt_tag.group(1).lower()
                    content += " " + nxt[:nxt_tag.start()].strip()
                    i += 1
                    break
                
                # Check if next line is a continuation (lowercase or starts with punctuation)
                if nxt[0].islower() or not nxt[0].isalnum():
                    content += " " + nxt
                    i += 1
                else:
                    break

        # Cleanup content
        content = re.sub(r'^[#\*_\-\s.:/]+', '', content).strip()
        if len(content) > 3 and not is_meta_section(content):
            if not current_chapter:
                current_chapter = {"title": "Unit 1", "topics": []}
            
            current_chapter["topics"].append({
                "title": content,
                "type": topic_type,
                "page": None
            })
        
        i += 1

    if current_chapter: chapters.append(current_chapter)

    # Final Deduplication & Normalization
    for ch in chapters:
        seen = set()
        unique_topics = []
        for t in ch["topics"]:
            key = t["title"].lower()
            if key not in seen:
                seen.add(key)
                unique_topics.append(t)
        ch["topics"] = unique_topics
    
    return chapters



def parse_table_format(text):
    """
    Detect and parse table-formatted TOC.
    Tables have consistent delimiters (|, tabs, or multi-space columns).

    Returns: list of chapter dicts, or empty list if not a table.
    """
    lines = [l for l in text.split('\n') if l.strip()]
    if len(lines) < 3:
        return []

    # Detect pipe-delimited tables
    pipe_lines = [l for l in lines if '|' in l]
    if len(pipe_lines) > len(lines) * 0.5:
        return _parse_pipe_table(pipe_lines)

    # Detect tab-delimited tables
    tab_lines = [l for l in lines if '\t' in l]
    if len(tab_lines) > len(lines) * 0.5:
        return _parse_tab_table(tab_lines)

    return []


def _parse_pipe_table(lines):
    """Parse pipe-delimited table rows into chapters."""
    chapters = []
    current_chapter = None

    for line in lines:
        # Skip separator lines (---|----|---)
        if re.match(r'^[\s|:-]+$', line):
            continue

        cells = [c.strip() for c in line.split('|') if c.strip()]
        if not cells:
            continue

        # Try to detect page number in any cell
        page = None
        for cell in cells:
            if cell.isdigit():
                page = int(cell)
                break

        # First meaningful cell is likely the title
        title = cells[0] if cells else ""
        if not title or is_meta_section(title):
            continue

        is_ch, ch_num = is_chapter_header(title)
        if is_ch:
            if current_chapter:
                chapters.append(current_chapter)
            current_chapter = {'title': title, 'page': page, 'topics': []}
        elif current_chapter:
            current_chapter['topics'].append({
                'title': title,
                'type': classify_topic(title),
                'page': page,
            })
        else:
            current_chapter = {'title': 'Unit 1', 'page': page, 'topics': []}
            current_chapter['topics'].append({
                'title': title,
                'type': classify_topic(title),
                'page': page,
            })

    if current_chapter:
        chapters.append(current_chapter)
    return chapters


def _parse_tab_table(lines):
    """Parse tab-delimited table rows into chapters."""
    chapters = []
    current_chapter = None

    for line in lines:
        cells = [c.strip() for c in line.split('\t') if c.strip()]
        if not cells:
            continue

        page = None
        for cell in cells:
            if cell.isdigit():
                page = int(cell)
                break

        title = cells[0]
        if not title or is_meta_section(title):
            continue

        is_ch, ch_num = is_chapter_header(title)
        if is_ch:
            if current_chapter:
                chapters.append(current_chapter)
            current_chapter = {'title': title, 'page': page, 'topics': []}
        elif current_chapter:
            current_chapter['topics'].append({
                'title': title,
                'type': classify_topic(title),
                'page': page,
            })
        else:
            current_chapter = {'title': 'Unit 1', 'page': page, 'topics': []}
            current_chapter['topics'].append({
                'title': title,
                'type': classify_topic(title),
                'page': page,
            })

    if current_chapter:
        chapters.append(current_chapter)
    return chapters


# ── Public Entry Point ───────────────────────────────────────────────

def fast_parse_curriculum(text):
    """
    Main entry point. Attempts table parsing first, then falls back
    to general text parsing. Returns the same schema as the AI parser.

    Returns: list of chapter dicts
    """
    if not text or not text.strip():
        return []

    # Try table format first
    chapters = parse_table_format(text)
    if chapters:
        return chapters

    # General text parsing
    return parse_curriculum_text(text)
