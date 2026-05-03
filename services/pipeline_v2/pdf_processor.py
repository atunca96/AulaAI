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
    Core extraction logic using strict one-shot LLM generator.
    """
    if not lines:
        return {"units": []}

    # Semantic pre-cleaning
    cleaned_lines = clean_lines(lines)
    full_text = "\n".join(cleaned_lines)
    
    from .llm import extract_curriculum
    curriculum = extract_curriculum(full_text)
    
    return curriculum

def process_pdf(pdf_path: str, page_limit: int = None) -> dict:
    # 1. Generate file hash
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()
    file_hash = hashlib.md5(file_bytes).hexdigest()

    # 3. Check cache
    with _process_lock:
        if file_hash in processed_files_v2:
            logger.info("CACHE HIT")
            return processed_files_v2[file_hash]

    if is_text_pdf(pdf_path):
        lines = extract_text_pdfplumber(pdf_path, page_limit=page_limit)
    else:
        if not check_ocr_available():
            raise RuntimeError("OCR is required for this PDF, but Tesseract is not installed.")
        logger.info("OCR USED")
        from .ocr import extract_text_ocr
        lines = extract_text_ocr(pdf_path, page_limit=page_limit)

    if not lines:
        raise ValueError("Failed to extract any text from the PDF.")

    curriculum = process_text(lines)
    
    # 4. Store result
    with _process_lock:
        processed_files_v2[file_hash] = curriculum
        
    return curriculum
