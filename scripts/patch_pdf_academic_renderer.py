from pathlib import Path

path = Path('server.py')
src = path.read_text(encoding='utf-8')
marker = 'AULA_ACADEMIC_PDF_RENDERER_V2'
if marker in src:
    print('Academic PDF renderer v2 already injected')
else:
    anchor = '''        is_tr = (lang == "tr")

        # --- Human-readable topic type labels ---
'''
    replacement = '''        is_tr = (lang == "tr")

        # AULA_ACADEMIC_PDF_RENDERER_V2
        # Consolidated production renderer. It is fully local / zero-AI and has
        # its own legacy-shape + pagination hardening. Keep the proven legacy
        # exporter below as a final safety fallback.
        try:
            from services.pdf_renderer_v12 import render_course_pdf
            pdf_bytes, academic_course_name = render_course_pdf(course_id, lang)
            safe_name = "".join(c if (c.isalnum() or c in "-_") else "_" for c in academic_course_name).strip("_") or "Course_Materials"
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
            print(f"[ACADEMIC PDF FALLBACK] {academic_pdf_err}")
            traceback.print_exc()

        # --- Human-readable topic type labels ---
'''
    count = src.count(anchor)
    if count != 1:
        raise RuntimeError(f'academic PDF v2 anchor matched {count} times')
    src = src.replace(anchor, replacement, 1)
    path.write_text(src, encoding='utf-8')
    print('Enabled consolidated academic PDF renderer v12 with legacy fallback')
