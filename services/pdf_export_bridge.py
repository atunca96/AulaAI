from urllib.parse import parse_qs, urlparse
from services.pdf_academic_renderer import render_course_pdf


def serve_pdf(handler, course_id):
    query = parse_qs(urlparse(handler.path).query)
    lang = (query.get("lang", ["en"])[0] or "en").lower()
    if lang not in ("en", "tr"):
        lang = "en"

    pdf_bytes, course_name = render_course_pdf(course_id, lang=lang)
    safe_name = "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(course_name or "course")).strip("_")
    filename = f"{safe_name}_AulaAI_{lang.upper()}.pdf"

    handler.send_response(200)
    handler.send_header("Content-Type", "application/pdf")
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.send_header("Content-Length", str(len(pdf_bytes)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    handler.send_header("X-AulaAI-PDF-Renderer", "academic-v43")
    handler.end_headers()
    handler.wfile.write(pdf_bytes)
