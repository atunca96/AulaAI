"""
OCR Fallback Module — Extracts text from image-based (scanned) PDFs.

Uses PyMuPDF to render pages as images and pytesseract for local OCR.
No AI/API calls. All processing runs locally.

This module is only invoked when normal text extraction fails or yields
insufficient content.
"""

# LEGACY - DO NOT USE
# TO BE REMOVED AFTER VALIDATION
import os
import re
import io
from datetime import datetime


def _log(msg):
    """Log to pipeline.log."""
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open("pipeline.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [OCR] {msg}\n")
            f.flush()
        print(f"[{timestamp}] [OCR] {msg}", flush=True)
    except:
        pass


# ── Detection ────────────────────────────────────────────────────────

def is_image_based_page(page_text, page_index=0):
    """
    Determines if a single page's extracted text indicates an image-based scan.

    Returns True if:
      - Text is empty or extremely short (< 30 chars of real content)
      - Text is mostly noise (high ratio of non-alphanumeric characters)
    """
    if not page_text or not page_text.strip():
        return True

    cleaned = page_text.strip()

    # Strip whitespace for length check
    content_chars = re.sub(r'\s+', '', cleaned)
    if len(content_chars) < 30:
        return True

    # Noise ratio: if less than 35% of chars are alphanumeric, it's garbage
    alnum_count = sum(1 for c in cleaned if c.isalnum())
    if len(cleaned) > 0 and (alnum_count / len(cleaned)) < 0.35:
        return True

    return False


def is_image_based_pdf(pdf_path, sample_pages=5):
    """
    Checks whether a PDF is image-based by sampling a few pages.
    Returns True if the majority of sampled pages have no/garbage text.
    """
    try:
        import fitz
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            return False

        # Sample evenly across the document
        step = max(1, total_pages // sample_pages)
        pages_to_check = [min(i * step, total_pages - 1) for i in range(sample_pages)]
        pages_to_check.append(total_pages // 2)
        pages_to_check = list(set(pages_to_check))[:sample_pages]

        image_pages = 0
        for p_idx in pages_to_check:
            text = doc[p_idx].get_text()
            if is_image_based_page(text, p_idx):
                image_pages += 1

        doc.close()

        ratio = image_pages / len(pages_to_check)
        _log(f"PDF scan check: {image_pages}/{len(pages_to_check)} sampled pages are image-based (ratio={ratio:.2f})")
        return ratio >= 0.5

    except Exception as e:
        _log(f"Error checking if PDF is image-based: {e}")
        return False


# ── Local OCR via pytesseract ────────────────────────────────────────

_tesseract_configured = False

def _get_tesseract():
    """Import pytesseract and auto-discover or auto-install the tesseract binary."""
    global _tesseract_configured
    try:
        import pytesseract
    except ImportError:
        _log("pytesseract not installed — OCR unavailable")
        return None

    # Only do path discovery once
    if not _tesseract_configured:
        _tesseract_configured = True

        import shutil
        import subprocess

        # Check if tesseract is already in PATH
        if shutil.which("tesseract"):
            _log(f"tesseract found in PATH: {shutil.which('tesseract')}")
            return pytesseract

        # Check common locations
        for path in ["/usr/bin/tesseract", "/usr/local/bin/tesseract"]:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                pytesseract.pytesseract.tesseract_cmd = path
                _log(f"tesseract found at: {path}")
                return pytesseract

        # Search nix store
        import glob
        for path in glob.glob("/nix/store/*/bin/tesseract"):
            if os.access(path, os.X_OK):
                pytesseract.pytesseract.tesseract_cmd = path
                _log(f"tesseract found in nix store: {path}")
                return pytesseract

        # NOT FOUND — attempt runtime install via apt-get
        _log("tesseract not found — attempting runtime install via apt-get...")
        try:
            result = subprocess.run(
                ["apt-get", "update", "-qq"],
                capture_output=True, text=True, timeout=30
            )
            # Install tesseract + all 14 AulaAI language packs
            lang_packs = [
                "tesseract-ocr",
                "tesseract-ocr-spa",  # Spanish
                "tesseract-ocr-deu",  # German
                "tesseract-ocr-fra",  # French
                "tesseract-ocr-ita",  # Italian
                "tesseract-ocr-por",  # Portuguese
                "tesseract-ocr-rus",  # Russian
                "tesseract-ocr-chi-sim",  # Chinese (Simplified)
                "tesseract-ocr-jpn",  # Japanese
                "tesseract-ocr-ara",  # Arabic
                "tesseract-ocr-tur",  # Turkish
                "tesseract-ocr-nld",  # Dutch
                "tesseract-ocr-swe",  # Swedish
                "tesseract-ocr-kor",  # Korean
                "tesseract-ocr-ell",  # Greek
            ]
            result = subprocess.run(
                ["apt-get", "install", "-y", "-qq"] + lang_packs,
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                _log("tesseract-ocr installed successfully via apt-get")
                # Verify it's now available
                if shutil.which("tesseract"):
                    _log(f"tesseract now in PATH: {shutil.which('tesseract')}")
                    return pytesseract
                elif os.path.isfile("/usr/bin/tesseract"):
                    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
                    _log("tesseract available at /usr/bin/tesseract")
                    return pytesseract
            else:
                _log(f"apt-get install failed: {result.stderr[:200]}")
        except Exception as e:
            _log(f"Runtime install failed: {e}")

        _log("tesseract could not be installed — OCR unavailable")

    return pytesseract


# Map AulaAI language names → tesseract language codes
TESS_LANG_MAP = {
    "spanish": "spa", "german": "deu", "french": "fra", "italian": "ita",
    "portuguese": "por", "russian": "rus", "chinese": "chi_sim",
    "japanese": "jpn", "arabic": "ara", "turkish": "tur", "dutch": "nld",
    "swedish": "swe", "korean": "kor", "greek": "ell", "english": "eng",
    "persian": "fas",
}

# Cache which language packs are actually installed
_available_langs = None

def _get_available_tess_langs():
    """Check which tesseract language packs are actually installed."""
    global _available_langs
    if _available_langs is not None:
        return _available_langs
    try:
        import subprocess
        result = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            _available_langs = set(result.stdout.strip().split("\n")[1:])  # skip header line
            _log(f"Available tesseract langs: {_available_langs}")
        else:
            _available_langs = {"eng"}
    except:
        _available_langs = {"eng"}
    return _available_langs


def _resolve_ocr_language(language):
    """
    Resolve the language parameter to a tesseract language string.
    Handles None, 'Detecting...', and explicit language names.
    Falls back to all installed packs for best coverage.
    """
    # If explicit language is provided and valid, use it + English
    if language and language.lower() not in ("detecting...", "unknown", ""):
        tess_lang = TESS_LANG_MAP.get(language.lower())
        if tess_lang and tess_lang != "eng":
            available = _get_available_tess_langs()
            if tess_lang in available:
                return f"{tess_lang}+eng"
            else:
                _log(f"Language pack '{tess_lang}' not installed, falling back")

    # No language specified or pack not installed — use all available packs
    # This is slower but handles any script automatically
    available = _get_available_tess_langs()
    # Build a reasonable multi-lang string from installed packs
    # Prioritize common scripts to avoid overwhelming tesseract
    priority = ["rus", "ara", "chi_sim", "jpn", "kor", "ell", "tur",
                "spa", "deu", "fra", "ita", "por", "nld", "swe"]
    active = [l for l in priority if l in available]
    if active:
        # Use up to 4 languages to keep it fast + always include eng
        combo = "+".join(active[:4]) + "+eng"
        return combo

    return "eng"

def ocr_page(page, page_num=0, dpi=200, language=None):
    """
    OCR a single PyMuPDF page using pytesseract.
    
    Args:
        page: PyMuPDF page object
        page_num: Page number for logging
        dpi: Render resolution (higher = better OCR, slower)
        language: AulaAI language name (e.g. 'Russian', 'Spanish') for better accuracy
    
    Returns the extracted text string, or empty string on failure.
    """
    pytesseract = _get_tesseract()
    if not pytesseract:
        return ""

    try:
        from PIL import Image
        import fitz

        # Render page to a high-DPI pixmap
        scale = dpi / 72.0
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat)

        # Convert PyMuPDF pixmap to PIL Image (no temp files)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        # Determine tesseract language code
        tess_lang = _resolve_ocr_language(language)

        # Run tesseract OCR with language-specific model
        text = pytesseract.image_to_string(img, lang=tess_lang)

        if text and text.strip():
            _log(f"Page {page_num}: Extracted {len(text.strip())} chars via tesseract (lang={tess_lang})")

        return text.strip() if text else ""

    except Exception as e:
        _log(f"Page {page_num}: OCR failed: {e}")
        return ""


def ocr_pdf_pages(pdf_path, start_page=None, end_page=None, page_list=None):
    """
    OCR a range or specific list of pages from an image-based PDF.
    Returns text in the same "Source Page X" format used by the existing pipeline.

    Args:
        pdf_path: Path to the PDF file
        start_page: 1-indexed start page (inclusive).
        end_page: 1-indexed end page (inclusive).
        page_list: Explicit list of 1-indexed pages to OCR. Overrides range if provided.

    Returns:
        str: Combined text with "# Source Page X" markers
    """
    pytesseract = _get_tesseract()
    if not pytesseract:
        _log("ERROR: pytesseract not available, cannot perform OCR")
        return ""

    try:
        import fitz
        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        # Determine which pages to process
        if page_list:
            pages_to_ocr = []
            for p in sorted(list(set(page_list))):
                if 1 <= p <= total_pages:
                    pages_to_ocr.append(p - 1) # 0-indexed
        else:
            # Range-based fallback
            s = (start_page - 1) if start_page else 0
            e = end_page if end_page else total_pages
            s = max(0, s)
            e = min(e, total_pages)
            pages_to_ocr = list(range(s, e))

        if not pages_to_ocr:
            doc.close()
            return ""

        _log(f"Starting parallel surgical OCR for {len(pages_to_ocr)} pages of {pdf_path}")
        
        results_map = {}
        lock = threading.Lock()

        def _process_page(p_idx):
            try:
                page = doc[p_idx]
                # First try normal text extraction
                normal_text = page.get_text()
                if not is_image_based_page(normal_text, p_idx):
                    with lock: results_map[p_idx] = f"# Source Page {p_idx + 1}\n{normal_text.strip()}"
                    return

                # Run local OCR
                ocr_text = ocr_page(page, page_num=p_idx + 1)
                if ocr_text:
                    ocr_text = _cleanup_ocr_text(ocr_text)
                    with lock: results_map[p_idx] = f"# Source Page {p_idx + 1}\n{ocr_text}"
                else:
                    with lock: results_map[p_idx] = f"# Source Page {p_idx + 1}\n[No readable text found]"
            except Exception as pe:
                _log(f"Error on page {p_idx+1}: {pe}")

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            executor.map(_process_page, pages_to_ocr)

        doc.close()

        # Reconstruct in order
        result_parts = []
        for p_idx in sorted(pages_to_ocr):
            if p_idx in results_map:
                result_parts.append(results_map[p_idx])

        combined = "\n\n".join(result_parts)
        _log(f"Surgical OCR complete: {len(result_parts)} pages processed")
        return combined

    except Exception as e:
        _log(f"FATAL OCR error: {e}")
        import traceback
        traceback.print_exc()
        return ""


# ── Post-OCR Cleanup ─────────────────────────────────────────────────

def _cleanup_ocr_text(text):
    """
    Minimal cleanup of OCR output:
    - Normalize whitespace
    - Remove obvious noise (isolated single characters, broken fragments)
    - Preserve meaningful content
    """
    if not text:
        return ""

    # Normalize various unicode spaces to regular space
    text = re.sub(r'[\u00a0\u2000-\u200b\u202f\u205f\u3000]', ' ', text)

    # Collapse multiple spaces (but not newlines)
    text = re.sub(r'[ \t]+', ' ', text)

    # Remove lines that are just a single non-word character (OCR noise)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that are just 1-2 random characters (noise)
        if len(stripped) <= 2 and not stripped.isalnum():
            continue
        # Skip lines that are entirely non-alphanumeric symbols
        if stripped and not any(c.isalnum() for c in stripped):
            if len(stripped) < 5:
                continue
        cleaned_lines.append(line)

    text = '\n'.join(cleaned_lines)

    # Collapse 3+ consecutive blank lines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
