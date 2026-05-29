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

def parse_toc_range(toc_range_str: str, total_pages: int):
    if not toc_range_str or toc_range_str == "0-0":
        return range(0, total_pages)
    try:
        if "-" in toc_range_str:
            sp, ep = toc_range_str.split("-")
            start_p = max(1, int(sp.strip()))
            end_p = min(total_pages, int(ep.strip()))
            return range(start_p - 1, end_p)
        elif toc_range_str.strip().isdigit():
            p = int(toc_range_str.strip())
            if 1 <= p <= total_pages:
                return range(p - 1, p)
    except Exception as e:
        logger.error(f"Error parsing toc_range '{toc_range_str}': {e}")
    return range(0, total_pages)

def get_temp_pdf_for_range(pdf_path: str, toc_range: str) -> str:
    """Extracts the pages in toc_range and saves to a temp file, returning its path."""
    import fitz
    import tempfile
    import os
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        page_indices = []
        if toc_range and toc_range != "0-0":
            try:
                if "-" in toc_range:
                    sp, ep = toc_range.split("-")
                    start_p = max(1, int(sp.strip()))
                    end_p = min(total_pages, int(ep.strip()))
                    page_indices = list(range(start_p - 1, end_p))
                elif toc_range.strip().isdigit():
                    p = int(toc_range.strip())
                    if 1 <= p <= total_pages:
                        page_indices = [p - 1]
            except Exception as e:
                logger.error(f"Error parsing toc_range for temp PDF: {e}")
        
        if not page_indices:
            doc.close()
            return pdf_path
            
        temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(temp_fd)
        
        doc.select(page_indices)
        doc.save(temp_path)
        doc.close()
        logger.info(f"Saved temporary PDF for range {toc_range} to {temp_path} ({len(page_indices)} pages)")
        return temp_path
    except Exception as e:
        logger.error(f"Failed to create temp PDF: {e}")
        return pdf_path

def extract_text_pdfplumber(pdf_path: str, toc_range: str = None) -> List[str]:
    logger.info(f"Extracting text via pdfplumber for {pdf_path} (range: {toc_range})")
    lines = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            page_indices = parse_toc_range(toc_range, total_pages)
            for idx in page_indices:
                page = pdf.pages[idx]
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

def process_pdf(pdf_path: str, toc_range: str = None) -> dict:
    # 1. Generate file hash
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()
    file_hash = hashlib.md5(file_bytes).hexdigest()

    # 2. Check cache (include range in cache key to handle rebuild updates with different ranges)
    cache_key = f"{file_hash}_{toc_range or ''}"
    with _process_lock:
        if cache_key in processed_files_v2:
            logger.info("CACHE HIT")
            return processed_files_v2[cache_key]

    # 3. Intelligent dual-pipeline selection
    if is_text_pdf(pdf_path):
        logger.info(f"PDF {pdf_path} identified as TEXT PDF. Using local pdfplumber (FREE).")
        lines = extract_text_pdfplumber(pdf_path, toc_range=toc_range)
        curriculum = process_text(lines)
    elif check_ocr_available():
        logger.info(f"PDF {pdf_path} is SCANNED. Local Tesseract OCR is available. Running local OCR (FREE).")
        lines = extract_text_ocr(pdf_path, toc_range=toc_range)
        curriculum = process_text(lines)
    else:
        # Fallback to OpenRouter Mistral OCR (Expensive last resort)
        logger.warning(f"PDF {pdf_path} is SCANNED and no local OCR is available. Falling back to OpenRouter Mistral OCR (EXPENSIVE).")
        from .llm import extract_curriculum_from_pdf_direct, normalize_curriculum
        import os
        
        # Optimize fallback: Create a small temp PDF containing only the TOC pages
        temp_pdf = get_temp_pdf_for_range(pdf_path, toc_range)
        try:
            curriculum = extract_curriculum_from_pdf_direct(temp_pdf)
            curriculum = normalize_curriculum(curriculum)
        finally:
            if temp_pdf != pdf_path and os.path.exists(temp_pdf):
                try:
                    os.remove(temp_pdf)
                except Exception:
                    pass
    
    # 4. Store result in cache
    with _process_lock:
        processed_files_v2[cache_key] = curriculum
        
    return curriculum

