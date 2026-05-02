import logging
import pytesseract
from typing import List
from concurrent.futures import ProcessPoolExecutor
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

def extract_text_ocr(pdf_path: str, max_workers: int = 4) -> List[str]:
    logger.info(f"Extracting text via OCR for {pdf_path}")
    try:
        images = convert_from_path(pdf_path)
    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {e}")
        return []

    if not images:
        return []

    texts = []
    # Use ProcessPoolExecutor for parallel OCR processing
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(process_page_image, images)
        for page_lines in results:
            if page_lines:
                texts.extend(page_lines)
                
    return texts
