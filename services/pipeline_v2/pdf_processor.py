import logging
import pdfplumber
import hashlib
import threading
from typing import List
from .ocr import extract_text_ocr, check_ocr_available
from .parser import clean_lines, chunk_lines, build_curriculum
from .llm import detect_structure, tag_topics

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

def extract_text_pdfplumber(pdf_path: str) -> List[str]:
    logger.info(f"Extracting text via pdfplumber for {pdf_path}")
    lines = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    lines.extend(text.splitlines())
    except Exception as e:
        logger.error(f"Failed to extract text with pdfplumber: {e}")
    return lines

def process_text(lines: List[str]) -> dict:
    """
    Core extraction logic that takes raw lines and returns a structured curriculum.
    """
    if not lines:
        return {"units": []}

    cleaned_lines = clean_lines(lines)
    
    chunks = chunk_lines(cleaned_lines, size=40)
    
    structured_lines = []
    total_chunks = len(chunks)
    for i, chunk in enumerate(chunks, 1):
        logger.info(f"Processing chunk {i}/{total_chunks}")
        structured_chunk = detect_structure(chunk)
        structured_lines.extend(structured_chunk)

    topics_to_tag = [item.get("text") for item in structured_lines if item.get("type") == "TOPIC" and item.get("text")]
    
    # Chunk topics for tagging to avoid huge requests
    topic_chunks = chunk_lines(topics_to_tag, size=30)
    tagged_topics = []
    total_topic_chunks = len(topic_chunks)
    for i, t_chunk in enumerate(topic_chunks, 1):
        logger.info(f"Processing chunk {i}/{total_topic_chunks}")
        tagged_chunk = tag_topics(t_chunk)
        tagged_topics.extend(tagged_chunk)

    curriculum = build_curriculum(structured_lines, tagged_topics)
    return curriculum

def process_pdf(pdf_path: str) -> dict:
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
        lines = extract_text_pdfplumber(pdf_path)
    else:
        if not check_ocr_available():
            raise RuntimeError("OCR is required for this PDF, but Tesseract is not installed.")
        logger.info("OCR USED")
        lines = extract_text_ocr(pdf_path)

    if not lines:
        raise ValueError("Failed to extract any text from the PDF.")

    curriculum = process_text(lines)
    
    # 4. Store result
    with _process_lock:
        processed_files_v2[file_hash] = curriculum
        
    return curriculum
