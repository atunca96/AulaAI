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
    "noun", "sentence", "phrase", "question", "вопрос", "существительн", 
    "глагол", "наречие", "прилагательн", "местоимени", "падеж", "склонени",
    "кто", "что", "чей", "как", "где", "когда", "куда", "откуда", "почему", "зачем", "сколько",
    "where", "what", "who", "when", "why", "how", "whose", "whom",
    "qual", "quien", "quién", "como", "cómo", "donde", "dónde", "quando", "cuándo", "porque", "por qué",
    "quel", "qui", "comment", "où", "quand", "pourquoi"
]

READING_KEYS = [
    "reading", "lectura", "lesen", "lecture", "text", "story",
    "cultura", "culture", "kultur", "civilization", "video",
    "film", "película", "song", "canción", "lied", "chanson",
    "literatur", "poesía", "poetry", "poème", "novela", "novel",
    "article", "interview", "entrevista",
]

META_SKIP = [
    "about", "author", "license", "preface", "index",
    "bibliography", "appendix", "glossary", "glosario",
    "acknowledgment", "copyright", "introduction to the",
    "table of contents", "answer key", "respuestas",
    "credits", "maps", "map of", "scope and sequence",
    "contents", "sommaire", "table des matières", "inhalt", 
    "inhaltsverzeichnis", "indice", "índice", "sommario",
    "sumário", "содержание", "оглавление", "içindekiler",
    "المحتويات", "目录", "目次", "extracted content", "source page",
    "приложение", "аудио", "page", "chapter", "unit", "lección", "leccion",
    "урок", "задание", "упражнение"
]


def classify_topic(title):
    """Classify a topic title as vocabulary or grammar."""
    t_lower = title.lower()
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
    r'(?:unit|chapter|module|unidad|unité|lektion|kapitel|lección|leccion|tema|thème|chapitre|modulo|módulo|etapa|paso|stufe)'
    r'\s*\.?\s*(\d+)'           # "Unit 1", "Unidad 1", etc.
    r'|(\d+)\s*[.:/\-–—]\s*'   # "1. Title", "1: Title", "1/ Title"
    r'|([IVXLC]+)\s*[.:/\-–—]\s*'  # "I. Title", "IV: Title"
    r')',
    re.IGNORECASE
)

# Detect if a line is a chapter/unit header
def is_chapter_header(line, prev_indent=0):
    """
    Determines if a line is a chapter/unit header.
    Returns (True, chapter_number_str) or (False, None).
    """
    stripped = line.strip()
    if not stripped or len(stripped) < 3:
        return False, None

    # Skip meta sections
    if is_meta_section(stripped):
        return False, None

    # Check against unit patterns
    m = UNIT_PATTERN.match(stripped)
    if m:
        num = m.group(1) or m.group(2) or m.group(3)
        return True, num

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
    Parse raw curriculum text into structured chapters.

    Returns: list of chapter dicts matching the expected schema:
        [{"title": "...", "page": N, "topics": [{"title": "...", "type": "...", "page": N}]}]
    """
    if not text or not text.strip():
        return []

    lines = text.split('\n')

    # 1. Basic clean and noise removal
    cleaned_lines = []
    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            continue

        # Remove bullet markers but DO NOT strip hyphens that are attached to words
        # (e.g. suffixes like -OBa- should not be stripped of their hyphen)
        # We only strip standalone bullets or hyphens followed by space
        stripped = re.sub(r'^[\u2022\u25E6\u25AA\u25CF\u25CB•◦▪●○◆◇►▸▹\*]\s*', '', line.strip())
        stripped = re.sub(r'^-\s+', '', stripped).strip()

        # Remove leading numbering like "1.", "1)", "a.", "a)", "1.1", "1.1."
        sub_number_match = re.match(r'^(\d+\.)+\d*\s+', stripped)
        if sub_number_match:
            pass  # Keep it — the chapter detection handles "1." separately

        if not stripped:
            continue
            
        # Single short tokens or non-alphabetic fragments
        if len(stripped) < 3 and not stripped.isdigit():
            continue
            
        # Hard noise removal: broken symbols like "ee he", "es :", "С О"
        if re.search(r'^[a-zа-яA-ZА-ЯёЁ]\s[a-zа-яA-ZА-ЯёЁ]$', stripped, re.IGNORECASE) or re.search(r'[a-zA-Zа-яА-ЯёЁ]\s*:', stripped) and len(stripped) < 6:
            continue
            
        # Non-alphabetic fragments (must contain at least one letter)
        if not re.search(r'[a-zA-Zа-яА-ЯёЁ]', stripped):
            continue
            
        # Specific OCR artifacts
        if stripped.startswith("ーー") or stripped == "ee he":
            continue
            
        # Fake headers or generic all caps headings (e.g., "CASES.", "REVIEW")
        if stripped.isupper() and len(stripped) < 15 and not re.search(r'\d', stripped):
            continue
            
        # Ignore lines that are ONLY digits or digits with symbols (like "147", "1-20")
        if re.match(r'^[\d\s\-\.\/]+$', stripped):
            continue

        cleaned_lines.append({'raw': stripped, 'indent': get_indent_level(line)})

    # 2. Split mixed lines (pipe, tab, or 3+ spaces)
    split_lines = []
    for entry in cleaned_lines:
        line_text = entry['raw']
        # Split on | or tab or 3+ spaces, or period followed by space and Capital
        # We split on spaces separating distinct sentences, but keep the period on the first sentence.
        sub_parts = re.split(r'\s*\|\s*|\t+|\s{3,}', line_text)
        
        for sp in sub_parts:
            # 1. Split on commas/spaces followed by major structural keywords that imply a new concept
            # Use a NON-CAPTURING group so re.split doesn't return the delimiters!
            grammar_split_pattern = r'(?<=[a-zA-Zа-яА-ЯёЁ.,])\s+(?=(?:The verbs?|The accusative|The dative|The genitive|The prepositional|The nominative|The instrumental|The modal|The imperative|Adjectives|Adverbs|Pronouns|Конструкции|Наречия|Verbs)\b)'
            sp_parts = re.split(grammar_split_pattern, sp)
            
            for p1 in sp_parts:
                if not p1.strip(): continue
                # 2. Further split "The verb. Personal pronouns." -> ["The verb.", "Personal pronouns."]
                sentence_parts = re.split(r'(?<=[a-zA-Zа-яА-ЯёЁ]\.)\s+(?=[A-ZА-ЯЁ])', p1)
                for p2 in sentence_parts:
                    if p2.strip():
                        split_lines.append({'raw': p2.strip(), 'indent': entry['indent']})

    # 3. Merge broken lines
    merged_lines = []
    i = 0
    while i < len(split_lines):
        curr_entry = split_lines[i]
        curr = curr_entry['raw']
        
        while i + 1 < len(split_lines):
            nxt_entry = split_lines[i+1]
            nxt = nxt_entry['raw']
            
            # Condition to merge:
            is_terminal = bool(re.search(r'[.!?::;]\s*$', curr))
            nxt_is_continuation = bool(re.match(r'^([a-zа-я]|-)', nxt))
            is_comma = bool(re.search(r',\s*$', curr))
            is_bracket = bool(re.match(r'^[\[({]', nxt))
            
            # Words that strongly imply the sentence is unfinished
            hanging_words = r'(the|of|and|in|on|with|for|to|vs\.?|or|a|an|personal|case|suffixes)$'
            is_hanging = bool(re.search(hanging_words, curr, re.IGNORECASE))
            
            if (not is_terminal and nxt_is_continuation) or is_comma or is_bracket or is_hanging:
                curr = curr + " " + nxt
                i += 1
            else:
                break
                
        merged_lines.append({'raw': curr, 'indent': curr_entry['indent']})
        i += 1

    # 4. Extract pages and detect headers
    entries = []
    for entry in merged_lines:
        cleaned, page = extract_page_number(entry['raw'])
        if cleaned and len(cleaned) > 1:
            is_ch, ch_num = is_chapter_header(cleaned)
            entries.append({
                'raw': cleaned,
                'page': page,
                'indent': entry['indent'],
                'is_header': is_ch,
                'chapter_num': ch_num,
            })

    if not entries:
        return []

    # 5. Build structure
    chapters = []
    current_chapter = None

    def is_valid_topic(text):
        if re.match(r'^[\d\s\-\.\/]+$', text) or len(text) < 3:
            return False
        # Remove fake headers (e.g. "CASES.", "REVIEW")
        if text.isupper() and len(text) < 20 and not re.search(r'\d', text):
            return False
        # Remove meta sections
        if is_meta_section(text):
            return False
        return True

    for entry in entries:
        raw_t = entry['raw']
        if is_meta_section(raw_t):
            continue

        if entry['is_header']:
            # Start a new chapter
            if current_chapter:
                chapters.append(current_chapter)
            current_chapter = {
                'title': raw_t,
                'page': entry['page'],
                'topics': []
            }
        elif current_chapter is not None:
            # This is a topic under the current chapter
            if is_valid_topic(raw_t):
                current_chapter['topics'].append({
                    'title': raw_t,
                    'type': classify_topic(raw_t),
                    'page': entry['page'],
                })
        else:
            # No chapter started yet — treat as orphan topic
            if not chapters:
                current_chapter = {
                    'title': 'Curriculum Topics',
                    'page': entry['page'],
                    'topics': []
                }
            if is_valid_topic(raw_t):
                current_chapter['topics'].append({
                    'title': raw_t,
                    'type': classify_topic(raw_t),
                    'page': entry['page'],
                })

    # Don't forget the last chapter
    if current_chapter and (current_chapter.get('topics') or current_chapter.get('title')):
        chapters.append(current_chapter)

    # 6. If chapters have no topics (just headers), treat subsequent lines as topics
    if chapters and all(len(ch.get('topics', [])) == 0 for ch in chapters):
        rebuilt = []
        for i, ch in enumerate(chapters):
            if i == 0 or (i > 0 and ch.get('chapter_num')):
                rebuilt.append(ch)
            elif rebuilt:
                rebuilt[-1]['topics'].append({
                    'title': ch['title'],
                    'type': classify_topic(ch['title']),
                    'page': ch.get('page'),
                })
    # 7. Add arbitrary unit grouping for flat topic lists
    # If there is only one chapter and it has > 12 topics, we group them into Unit 1, Unit 2...
    if len(chapters) == 1 and len(chapters[0].get('topics', [])) > 12:
        topics = chapters[0]['topics']
        units = []
        current_unit = []
        
        for i, topic in enumerate(topics):
            current_unit.append(topic)
            
            # Check if we should split
            if len(current_unit) >= 8:
                if i + 1 < len(topics):
                    next_topic = topics[i+1]
                    # Try to split on theme change
                    if topic['type'] != next_topic['type']:
                        units.append(current_unit)
                        current_unit = []
                    elif len(current_unit) >= 12:
                        units.append(current_unit)
                        current_unit = []
                        
        if current_unit:
            units.append(current_unit)
            
        # Rebuild chapters
        chapters = []
        for i, u in enumerate(units):
            chapters.append({
                'title': f"Unit {i+1}",
                'page': u[0].get('page'),
                'topics': u
            })

    # 8. Final normalization (trim, deduplicate)
    for ch in chapters:
        seen = set()
        clean_topics = []
        for t in ch.get('topics', []):
            # Trim trailing punctuation like comma or dash if it's dangling at the end
            title = re.sub(r'[\s,\-]+$', '', t['title']).strip()
            # Title case for formatting? No, keep original case but ensure first letter is capital if possible
            if title and title[0].islower():
                title = title[0].upper() + title[1:]
            
            # Deduplicate within chapter
            t_key = title.lower()
            if t_key not in seen:
                seen.add(t_key)
                t['title'] = title
                clean_topics.append(t)
        ch['topics'] = clean_topics
        ch['title'] = ch['title'].strip()

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
