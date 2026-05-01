"""
OCR Fallback Module — Extracts text from image-based (scanned) PDFs.

Uses PyMuPDF to render pages as images and sends them to a vision-capable
AI model via OpenRouter for text extraction. Zero system-level dependencies.

This module is only invoked when normal text extraction fails or yields
insufficient content.
"""

import os
import re
import base64
import json
import time
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

    # Noise ratio: if less than 40% of chars are alphanumeric, it's garbage
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

        # Sample evenly across the document (skip page 0 which is often a cover)
        step = max(1, total_pages // sample_pages)
        pages_to_check = [min(i * step, total_pages - 1) for i in range(sample_pages)]
        # Always include a middle page
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

        # If more than half the sampled pages are image-based, treat entire PDF as scanned
        return ratio >= 0.5

    except Exception as e:
        _log(f"Error checking if PDF is image-based: {e}")
        return False


# ── OCR via Vision AI ────────────────────────────────────────────────

def _render_page_to_base64(page, dpi=200):
    """Renders a PyMuPDF page to a base64-encoded PNG string."""
    # Scale matrix for target DPI (default PyMuPDF is 72 DPI)
    scale = dpi / 72.0
    mat = None
    try:
        import fitz
        mat = fitz.Matrix(scale, scale)
    except:
        pass

    pix = page.get_pixmap(matrix=mat) if mat else page.get_pixmap()
    png_bytes = pix.tobytes("png")
    return base64.b64encode(png_bytes).decode("utf-8")


def _ocr_page_via_vision(base64_png, page_num, api_key):
    """
    Sends a page image to a vision-capable AI model for text extraction.
    Returns the extracted text string.
    """
    import urllib.request
    import urllib.error

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aulaai.com",
        "X-Title": "AulaAI-OCR"
    }

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Extract ALL text from this scanned page image. "
                        "Preserve the original text exactly as written — do not translate, summarize, or interpret. "
                        "Maintain paragraph breaks and logical structure. "
                        "If there are tables, preserve them in a readable format. "
                        "If the page is blank or contains only images with no text, respond with: [BLANK PAGE]. "
                        "Return ONLY the extracted text, no commentary."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_png}"
                    }
                }
            ]
        }
    ]

    # Try vision-capable models in order
    models_to_try = [
        "google/gemini-2.0-flash-lite-preview-02-05:free",
        "google/gemini-2.5-flash",
        "anthropic/claude-3-haiku",
    ]

    last_error = "Unknown"
    for model in models_to_try:
        try:
            payload = json.dumps({
                "model": model,
                "messages": messages,
                "max_tokens": 4000,
                "temperature": 0.1
            }).encode("utf-8")

            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)

                if "choices" in res_json and res_json["choices"]:
                    content = res_json["choices"][0]["message"]["content"].strip()
                    if content and content != "[BLANK PAGE]":
                        _log(f"Page {page_num}: Extracted {len(content)} chars via {model}")
                        return content
                    elif content == "[BLANK PAGE]":
                        _log(f"Page {page_num}: Blank page detected by {model}")
                        return ""

                if "error" in res_json:
                    last_error = res_json["error"].get("message", "API Error")
                    _log(f"Page {page_num}: Model {model} error: {last_error}")

        except Exception as e:
            last_error = str(e)
            _log(f"Page {page_num}: Model {model} failed: {last_error}")
            time.sleep(0.5)

    _log(f"Page {page_num}: All vision models failed. Last error: {last_error}")
    return ""


def ocr_pdf_pages(pdf_path, start_page=None, end_page=None):
    """
    OCR a range of pages from an image-based PDF.
    Returns text in the same "Source Page X" format used by the existing pipeline.

    Args:
        pdf_path: Path to the PDF file
        start_page: 1-indexed start page (inclusive). None = first page.
        end_page: 1-indexed end page (inclusive). None = last page.

    Returns:
        str: Combined text with "# Source Page X" markers
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        _log("ERROR: OPENROUTER_API_KEY not set, cannot perform OCR")
        return ""

    try:
        import fitz
        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        # Convert to 0-indexed
        s = (start_page - 1) if start_page else 0
        e = end_page if end_page else total_pages
        s = max(0, s)
        e = min(e, total_pages)

        _log(f"Starting OCR for pages {s+1}-{e} of {pdf_path} ({e - s} pages)")

        result_parts = []

        for page_idx in range(s, e):
            page = doc[page_idx]

            # First try normal text extraction — only OCR if it fails
            normal_text = page.get_text()
            if not is_image_based_page(normal_text, page_idx):
                # This page has good text, use it directly
                result_parts.append(f"# Source Page {page_idx + 1}\n{normal_text.strip()}")
                continue

            # Render page to image and OCR via vision AI
            base64_png = _render_page_to_base64(page, dpi=200)
            ocr_text = _ocr_page_via_vision(base64_png, page_idx + 1, api_key)

            if ocr_text:
                # Basic cleanup
                ocr_text = _cleanup_ocr_text(ocr_text)
                result_parts.append(f"# Source Page {page_idx + 1}\n{ocr_text}")
            else:
                result_parts.append(f"# Source Page {page_idx + 1}\n[No readable text found]")

        doc.close()

        combined = "\n\n".join(result_parts)
        _log(f"OCR complete: {len(result_parts)} pages processed, {len(combined)} total chars")
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
            if len(stripped) < 5:  # Short symbol-only lines are noise
                continue
        cleaned_lines.append(line)

    text = '\n'.join(cleaned_lines)

    # Collapse 3+ consecutive blank lines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
