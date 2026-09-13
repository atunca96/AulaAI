from pathlib import Path

p = Path(__file__).resolve().parents[1] / "server.py"
s = p.read_text(encoding="utf-8")

start_marker = "    def _export_course_pdf(self, course_id):\n"
start = s.rfind(start_marker)
if start < 0:
    raise RuntimeError("active PDF exporter missing")

body_start = start + len(start_marker)
marker = "        # AULAAI_PDF_ACADEMIC_V43\n"
if marker not in s[start:start + 1200]:
    delegate = (
        marker
        + "        from services.pdf_export_bridge import serve_pdf\n"
        + "        return serve_pdf(self, course_id)\n"
    )
    s = s[:body_start] + delegate + s[body_start:]

p.write_text(s, encoding="utf-8")
print("Applied v43: live PDF endpoint delegates to academic renderer")
