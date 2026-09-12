from pathlib import Path

# Forward-only PDF export hardening.
# Goal: never keep the browser/proxy request open while a large classroom PDF is rendered.
# The renderer stays v12; this patch only changes transport/orchestration and filename safety.

server_path = Path('server.py')
server = server_path.read_text(encoding='utf-8')

# 1) Global in-memory export job registry. Jobs are short-lived and binary payloads are
# removed after download / expiry, so this does not become a permanent cache.
global_anchor = "_cache = {}\n_cache_lock = threading.Lock()\n"
if global_anchor not in server:
    raise RuntimeError('PDF async global anchor not found')
globals_block = """_cache = {}\n_cache_lock = threading.Lock()\n\n# AULA_PDF_ASYNC_EXPORT_V13\n_pdf_export_jobs = {}\n_pdf_export_jobs_lock = threading.Lock()\n\ndef _pdf_export_cleanup():\n    now = time.time()\n    with _pdf_export_jobs_lock:\n        for _jid in list(_pdf_export_jobs.keys()):\n            _job = _pdf_export_jobs.get(_jid) or {}\n            if now - float(_job.get('created_at') or now) > 900:\n                _pdf_export_jobs.pop(_jid, None)\n\ndef _pdf_safe_filename(name, lang):\n    # HTTP headers are latin-1 in BaseHTTPRequestHandler. Keep the fallback filename\n    # strictly ASCII so Chinese/Russian/Turkish course names can never break end_headers().\n    raw = str(name or 'Course_Materials')\n    safe = ''.join(ch if (ch.isascii() and (ch.isalnum() or ch in '-_')) else '_' for ch in raw)\n    safe = '_'.join(part for part in safe.split('_') if part)[:90] or 'Course_Materials'\n    return f\"{safe}_AulaAI_{str(lang or 'en').upper()}.pdf\"\n\ndef _start_pdf_export_job(course_id, lang):\n    _pdf_export_cleanup()\n    job_id = str(uuid.uuid4())\n    with _pdf_export_jobs_lock:\n        _pdf_export_jobs[job_id] = {\n            'status': 'processing', 'created_at': time.time(), 'course_id': course_id,\n            'lang': lang, 'progress': 5, 'message': 'PDF hazırlanıyor' if lang == 'tr' else 'Preparing PDF'\n        }\n\n    def _worker():\n        try:\n            from services.pdf_renderer_v12 import render_course_pdf\n            with _pdf_export_jobs_lock:\n                if job_id in _pdf_export_jobs:\n                    _pdf_export_jobs[job_id]['progress'] = 15\n            pdf_bytes, course_name = render_course_pdf(course_id, lang)\n            if not isinstance(pdf_bytes, (bytes, bytearray)) or not bytes(pdf_bytes).startswith(b'%PDF'):\n                raise RuntimeError('Renderer returned invalid PDF data')\n            filename = _pdf_safe_filename(course_name, lang)\n            with _pdf_export_jobs_lock:\n                if job_id in _pdf_export_jobs:\n                    _pdf_export_jobs[job_id].update({\n                        'status': 'ready', 'progress': 100, 'bytes': bytes(pdf_bytes),\n                        'filename': filename, 'size': len(pdf_bytes),\n                        'message': 'Hazır' if lang == 'tr' else 'Ready'\n                    })\n            print(f'[PDF V13] Ready job={job_id} course={course_id} lang={lang} bytes={len(pdf_bytes)}')\n        except Exception as exc:\n            print(f'[PDF V13 ERROR] job={job_id} course={course_id}: {exc}')\n            traceback.print_exc()\n            with _pdf_export_jobs_lock:\n                if job_id in _pdf_export_jobs:\n                    _pdf_export_jobs[job_id].update({\n                        'status': 'error', 'progress': 100, 'error': str(exc),\n                        'message': 'PDF oluşturulamadı' if lang == 'tr' else 'PDF generation failed'\n                    })\n\n    threading.Thread(target=_worker, daemon=True, name=f'pdf-export-{job_id[:8]}').start()\n    return job_id\n"""
server = server.replace(global_anchor, globals_block, 1)

# 2) Add non-blocking start/status/download routes immediately before the old sync route.
route_anchor = '''        elif path.startswith("/api/courses/") and path.endswith("/export-pdf"):\n            # Extract course_id from /api/courses/{id}/export-pdf\n'''
if route_anchor not in server:
    raise RuntimeError('PDF export route anchor not found')
route_block = '''        elif path.startswith("/api/courses/") and path.endswith("/export-pdf-async"):\n            parts = path.split("/")\n            cid = parts[3] if len(parts) >= 5 else None\n            if not cid:\n                return self._send_error("course_id required", 400)\n            qp = parse_qs(parsed.query)\n            pdf_lang = str(qp.get("lang", ["en"])[0] or "en").lower()\n            if pdf_lang not in ("en", "tr"):\n                pdf_lang = "en"\n            jid = _start_pdf_export_job(cid, pdf_lang)\n            return self._send_json({"job_id": jid, "status": "processing", "progress": 5}, status=202)\n        elif path == "/api/pdf-export/status":\n            qp = parse_qs(parsed.query)\n            jid = str(qp.get("job_id", [""])[0] or "")\n            _pdf_export_cleanup()\n            with _pdf_export_jobs_lock:\n                job = dict(_pdf_export_jobs.get(jid) or {})\n            if not job:\n                return self._send_error("PDF export job not found", 404)\n            # Never serialize the binary payload through JSON.\n            job.pop("bytes", None)\n            return self._send_json(job)\n        elif path == "/api/pdf-export/download":\n            qp = parse_qs(parsed.query)\n            jid = str(qp.get("job_id", [""])[0] or "")\n            with _pdf_export_jobs_lock:\n                job = _pdf_export_jobs.get(jid)\n                if job and job.get("status") == "ready":\n                    payload = job.get("bytes")\n                    filename = job.get("filename") or "Course_Materials_AulaAI.pdf"\n                else:\n                    payload = None\n                    filename = None\n            if not job:\n                return self._send_error("PDF export job not found", 404)\n            if job.get("status") == "error":\n                return self._send_error(job.get("error") or "PDF export failed", 500)\n            if not payload:\n                return self._send_error("PDF is still being prepared", 409)\n            self.send_response(200)\n            self.send_header("Content-Type", "application/pdf")\n            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')\n            self.send_header("Content-Length", str(len(payload)))\n            self.send_header("Cache-Control", "no-store")\n            self.end_headers()\n            self.wfile.write(payload)\n            with _pdf_export_jobs_lock:\n                _pdf_export_jobs.pop(jid, None)\n            return\n        elif path.startswith("/api/courses/") and path.endswith("/export-pdf"):\n            # Extract course_id from /api/courses/{id}/export-pdf\n'''
server = server.replace(route_anchor, route_block, 1)

# 3) Harden the existing synchronous fallback filename too. This path remains available
# for compatibility but the browser will use async v13.
server = server.replace(
    '            safe_name = "".join(c if (c.isalnum() or c in "-_") else "_" for c in academic_course_name).strip("_") or "Course_Materials"\n            filename = f"{safe_name}_AulaAI_{lang.upper()}.pdf"\n',
    '            filename = _pdf_safe_filename(academic_course_name, lang)\n',
    1,
)
server_path.write_text(server, encoding='utf-8')

# 4) Replace only the browser download function. Rendering happens in a background job;
# the UI polls a cheap JSON endpoint and downloads once ready. This survives proxy request
# time limits on large 50-100+ page classroom PDFs.
app_path = Path('public/js/app.js')
app = app_path.read_text(encoding='utf-8')
start_marker = 'async function downloadCourseMaterialPDF() {'
end_marker = '\nwindow.downloadCourseMaterialPDF = downloadCourseMaterialPDF;'
start = app.find(start_marker)
end = app.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError('downloadCourseMaterialPDF anchors not found')

new_fn = r'''async function downloadCourseMaterialPDF() {
  if (!courseId) {
    showNotification(currentLang === 'tr' ? 'Lütfen önce bir sınıf seçin.' : 'Please select a classroom first.', 'error');
    return;
  }

  const pdfLang = await showPdfLangPicker();
  if (!pdfLang) return;

  const tr = currentLang === 'tr';
  const candidates = [...document.querySelectorAll('button, a')].filter(el => {
    const oc = el.getAttribute && (el.getAttribute('onclick') || '');
    return oc.includes('downloadCourseMaterialPDF');
  });
  const btn = candidates[0] || null;
  const originalHtml = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.style.opacity = '0.65'; }

  const headers = { 'X-Session-Token': localStorage.getItem('aula_session') || '' };
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  try {
    if (btn) btn.textContent = tr ? 'PDF hazırlanıyor…' : 'Preparing PDF…';
    showNotification(tr ? 'PDF arka planda hazırlanıyor…' : 'PDF is being prepared in the background…', 'info');

    const startRes = await fetch(`/api/courses/${encodeURIComponent(courseId)}/export-pdf-async?lang=${encodeURIComponent(pdfLang)}`, {
      method: 'GET', headers, cache: 'no-store'
    });
    const startText = await startRes.text();
    let startData = {};
    try { startData = JSON.parse(startText || '{}'); } catch (_) {}
    if (!startRes.ok || !startData.job_id) {
      throw new Error(startData.error || startData.message || startText || `PDF export could not start (${startRes.status})`);
    }

    const jobId = startData.job_id;
    const deadline = Date.now() + 4 * 60 * 1000;
    let statusData = null;
    while (Date.now() < deadline) {
      await sleep(850);
      const statusRes = await fetch(`/api/pdf-export/status?job_id=${encodeURIComponent(jobId)}`, {
        method: 'GET', headers, cache: 'no-store'
      });
      const statusText = await statusRes.text();
      try { statusData = JSON.parse(statusText || '{}'); } catch (_) { statusData = {}; }
      if (!statusRes.ok) throw new Error(statusData.error || statusData.message || statusText || 'PDF status check failed');
      if (btn) {
        const p = Math.max(5, Math.min(99, Number(statusData.progress || 15)));
        btn.textContent = `${tr ? 'PDF hazırlanıyor' : 'Preparing PDF'}… ${p}%`;
      }
      if (statusData.status === 'error') throw new Error(statusData.error || statusData.message || 'PDF generation failed');
      if (statusData.status === 'ready') break;
    }
    if (!statusData || statusData.status !== 'ready') {
      throw new Error(tr ? 'PDF oluşturma zaman aşımına uğradı.' : 'PDF generation timed out.');
    }

    const response = await fetch(`/api/pdf-export/download?job_id=${encodeURIComponent(jobId)}`, {
      method: 'GET', headers, cache: 'no-store'
    });
    if (!response.ok) {
      const msg = await response.text();
      throw new Error(msg || `PDF download failed (${response.status})`);
    }
    const blob = await response.blob();
    if (!blob || blob.size < 1000 || !String(blob.type || '').includes('pdf')) {
      throw new Error(tr ? 'Sunucu geçerli bir PDF döndürmedi.' : 'Server did not return a valid PDF.');
    }

    const courseName = (currentCourse && currentCourse.name) || 'Course_Materials';
    const safeFilename = courseName.replace(/[^a-zA-Z0-9_\-\u00C0-\u024F]/g, '_').replace(/_+/g, '_');
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${safeFilename}_AulaAI_${pdfLang.toUpperCase()}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 3000);
    showNotification(tr ? '✅ PDF başarıyla indirildi!' : '✅ PDF downloaded successfully!', 'success');
  } catch (e) {
    console.error('[PDF Export V13]', e);
    showNotification((tr ? 'PDF oluşturulamadı: ' : 'PDF export failed: ') + (e && e.message ? e.message : String(e)), 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.style.opacity = ''; btn.innerHTML = originalHtml; }
  }
}
'''
app = app[:start] + new_fn + app[end:]
app_path.write_text(app, encoding='utf-8')

print('Applied PDF async export v13: background render + polling + ASCII-safe headers')
