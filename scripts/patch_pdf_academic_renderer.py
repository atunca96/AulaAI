from pathlib import Path

path = Path('server.py')
src = path.read_text(encoding='utf-8')

anchor = '''        is_tr = (lang == "tr")

        # --- Human-readable topic type labels ---
'''
replacement = '''        is_tr = (lang == "tr")

        # Use the block-aware academic renderer. It paginates logical blocks by
        # measuring each block against the actual remaining A4 space, moving a
        # block only when it cannot fit, and allowing only genuinely oversized
        # blocks to flow across pages. No AI/network calls are involved.
        try:
            from services.pdf_academic_renderer import render_course_pdf
            pdf_bytes, academic_course_name = render_course_pdf(course_id, lang)
            safe_name = "".join(c if (c.isalnum() or c in "-_") else "_" for c in academic_course_name).strip("_")
            filename = f"{safe_name}_AulaAI_{lang.upper()}.pdf"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(pdf_bytes)
            return
        except Exception as academic_pdf_err:
            print(f"[ACADEMIC PDF EXPORT ERROR] {academic_pdf_err}")
            traceback.print_exc()
            return self._send_error(f"PDF generation failed: {str(academic_pdf_err)}", 500)

        # --- Human-readable topic type labels ---
'''

count = src.count(anchor)
if count != 1:
    raise RuntimeError(f'academic PDF switch anchor matched {count} times')
src = src.replace(anchor, replacement, 1)
path.write_text(src, encoding='utf-8')
print('Switched PDF export to block-aware academic renderer')
