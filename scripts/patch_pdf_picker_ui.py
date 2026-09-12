from pathlib import Path

path = Path('public/js/app.js')
src = path.read_text(encoding='utf-8')
marker = 'AULA_COMPACT_PDF_LANGUAGE_PICKER_V3'
if marker not in src:
    src += r'''

// AULA_COMPACT_PDF_LANGUAGE_PICKER_V3
(() => {
  function installPicker() {
    if (typeof window.showPdfLangPicker !== 'function' && typeof showPdfLangPicker !== 'function') return false;

    const picker = function() {
      return new Promise(resolve => {
        const old = document.getElementById('pdf-lang-modal');
        if (old) old.remove();
        const tr = (typeof currentLang !== 'undefined' ? currentLang : localStorage.getItem('aula_lang')) === 'tr';
        const modal = document.createElement('div');
        modal.id = 'pdf-lang-modal';
        modal.style.cssText = 'position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(2,8,23,.72);backdrop-filter:blur(6px);padding:18px;';
        modal.innerHTML = `
          <div style="width:min(390px,100%);background:#102541;border:1px solid rgba(148,163,184,.22);border-radius:22px;padding:22px;box-shadow:0 28px 80px rgba(0,0,0,.45);color:#f8fafc;">
            <div style="font-size:20px;font-weight:800;margin-bottom:6px;">${tr ? 'PDF Dilini Seç' : 'Choose PDF Language'}</div>
            <div style="font-size:13px;color:#aeb9c8;margin-bottom:18px;">${tr ? 'İndirilecek materyalin dilini seç.' : 'Choose the language for the downloaded material.'}</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
              <button data-pdf-lang="tr" type="button" style="appearance:none;border:1px solid rgba(148,163,184,.25);background:#0b1d33;color:#f8fafc;border-radius:14px;padding:16px 10px;display:flex;flex-direction:column;align-items:center;gap:7px;cursor:pointer;">
                <span style="font-size:15px;font-weight:900;letter-spacing:.8px;color:#d7a94b;">TR</span>
                <span style="font-size:14px;font-weight:750;">Türkçe</span>
              </button>
              <button data-pdf-lang="en" type="button" style="appearance:none;border:1px solid rgba(148,163,184,.25);background:#0b1d33;color:#f8fafc;border-radius:14px;padding:16px 10px;display:flex;flex-direction:column;align-items:center;gap:7px;cursor:pointer;">
                <span style="font-size:15px;font-weight:900;letter-spacing:.8px;color:#d7a94b;">EN</span>
                <span style="font-size:14px;font-weight:750;">English</span>
              </button>
            </div>
            <button id="pdf-picker-cancel-v3" type="button" style="appearance:none;border:0;background:transparent;color:#94a3b8;width:100%;margin-top:15px;padding:8px;font-size:13px;cursor:pointer;">${tr ? 'İptal' : 'Cancel'}</button>
          </div>`;
        document.body.appendChild(modal);
        const done = value => { if (modal.isConnected) modal.remove(); resolve(value); };
        modal.querySelectorAll('[data-pdf-lang]').forEach(b => b.addEventListener('click', () => done(b.dataset.pdfLang)));
        modal.querySelector('#pdf-picker-cancel-v3').addEventListener('click', () => done(null));
        modal.addEventListener('click', e => { if (e.target === modal) done(null); });
      });
    };

    window.showPdfLangPicker = picker;
    try { showPdfLangPicker = picker; } catch (_) {}
    return true;
  }

  let tries = 0;
  const timer = setInterval(() => {
    tries += 1;
    if (installPicker() || tries > 50) clearInterval(timer);
  }, 100);
})();
'''
    path.write_text(src, encoding='utf-8')

print('Installed compact PDF language picker v3')
