import logging
import pdfplumber
import hashlib
import threading
from typing import List
from .ocr import extract_text_ocr, check_ocr_available
from .parser import clean_lines, chunk_lines, build_curriculum
from .llm import extract_curriculum

logger = logging.getLogger(__name__)

processed_files_v2 = {}
_process_lock = threading.Lock()

def is_text_pdf(pdf_path: str, threshold: int = 50) -> bool:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text_length = 0
            # Check up to 3 pages to be safe
            for i, page in enumerate(pdf.pages):
                if i > 2:
                    break
                text = page.extract_text()
                if text:
                    text_length += len(text.strip())
            return text_length > threshold
    except Exception as e:
        logger.error(f"Failed to check PDF type: {e}")
        return False

def extract_text_pdfplumber(pdf_path: str, page_limit: int = None) -> List[str]:
    logger.info(f"Extracting text via pdfplumber for {pdf_path}")
    lines = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = pdf.pages[:page_limit] if page_limit else pdf.pages
            for page in pages:
                text = page.extract_text()
                if text:
                    lines.extend(text.splitlines())
    except Exception as e:
        logger.error(f"Failed to extract text with pdfplumber: {e}")
    return lines

def process_text(lines: List[str]) -> dict:
    """
    Highly cost-optimized single-pass extraction logic that avoids chunking slowness
    and enables the LLM to perform global deduplication and clean, consolidated grouping.
    """
    if not lines:
        return {"units": []}

    cleaned_lines = clean_lines(lines)
    full_text = "\n".join(cleaned_lines)
    
    # Debug: log the first 2000 chars of what we're sending to the LLM
    import logging as _logging
    _root_log = _logging.getLogger("pipeline_debug")
    try:
        with open("pipeline.log", "a", encoding="utf-8") as _f:
            _f.write(f"[PDF-TEXT-SAMPLE] First 2000 chars of extracted text:\n{full_text[:2000]}\n[END-SAMPLE]\n")
    except Exception:
        pass
    
    logger.info("Processing entire curriculum text in a single pass (super fast).")
    from .llm import extract_curriculum
    curriculum = extract_curriculum(full_text)
    
    return curriculum

def process_pdf(pdf_path: str, page_limit: int = None) -> dict:
    # 1. Generate file hash
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()
    file_hash = hashlib.md5(file_bytes).hexdigest()

    # 2. Check cache
    with _process_lock:
        if file_hash in processed_files_v2:
            logger.info("CACHE HIT")
            return processed_files_v2[file_hash]

    # 3. Intelligent dual-pipeline selection
    if is_text_pdf(pdf_path):
        logger.info(f"PDF {pdf_path} identified as TEXT PDF. Using local pdfplumber (FREE).")
        lines = extract_text_pdfplumber(pdf_path, page_limit=page_limit)
        curriculum = process_text(lines)
    elif check_ocr_available():
        logger.info(f"PDF {pdf_path} is SCANNED. Local Tesseract OCR is available. Running local OCR (FREE).")
        lines = extract_text_ocr(pdf_path, page_limit=page_limit)
        curriculum = process_text(lines)
    else:
        # Fallback to OpenRouter Mistral OCR (Expensive last resort)
        logger.warning(f"PDF {pdf_path} is SCANNED and no local OCR is available. Falling back to OpenRouter Mistral OCR (EXPENSIVE).")
        from .llm import extract_curriculum_from_pdf_direct, normalize_curriculum
        curriculum = extract_curriculum_from_pdf_direct(pdf_path)
        curriculum = normalize_curriculum(curriculum)
    
    # 4. Store result in cache
    with _process_lock:
        processed_files_v2[file_hash] = curriculum
        
    return curriculum

