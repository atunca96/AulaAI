import logging
import pytesseract
from typing import List
from concurrent.futures import ThreadPoolExecutor
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)

def check_ocr_available() -> bool:
    try:
        pytesseract.get_tesseract_version()
        return True
    except pytesseract.TesseractNotFoundError:
        return False
    except Exception:
        return False

def process_page_image(image) -> List[str]:
    """Run OCR on a single PIL Image and return extracted lines."""
    try:
        text = pytesseract.image_to_string(image)
        if text:
            return text.splitlines()
        return []
    except Exception as e:
        logger.error(f"OCR failed for a page: {e}")
        return []

def parse_ocr_toc_range(toc_range_str: str):
    if not toc_range_str or toc_range_str == "0-0":
        return 1, None
    try:
        if "-" in toc_range_str:
            sp, ep = toc_range_str.split("-")
            first = max(1, int(sp.strip()))
            last = int(ep.strip())
            return first, last
        elif toc_range_str.strip().isdigit():
            p = int(toc_range_str.strip())
            if p >= 1:
                return p, p
    except Exception as e:
        logger.error(f"Error parsing ocr toc_range '{toc_range_str}': {e}")
    return 1, None

def extract_text_ocr(pdf_path: str, max_workers: int = 4, toc_range: str = None) -> List[str]:
    logger.info(f"Extracting text via OCR for {pdf_path} (range: {toc_range})")
    try:
        first_page, last_page = parse_ocr_toc_range(toc_range)
        images = convert_from_path(pdf_path, first_page=first_page, last_page=last_page)
    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {e}")
        return []

    if not images:
        return []

    texts = []
    # Use ThreadPoolExecutor for parallel OCR processing to avoid fork deadlock issues in threaded servers
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(process_page_image, images)
        for page_lines in results:
            if page_lines:
                texts.extend(page_lines)
                
    return texts
