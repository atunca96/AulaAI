import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# iOS Safari: keep the working native overscroll fix untouched.
app_js = ROOT / "public" / "js" / "app.js"
source = app_js.read_text(encoding="utf-8")
marker = "// ── Pull-to-refresh suppression (iOS Safari) ──"
pos = source.find(marker)
if pos < 0:
    raise RuntimeError("iOS PTR handler marker missing")
source = source[:pos].rstrip() + "\n"
app_js.write_text(source, encoding="utf-8")

styles = ROOT / "public" / "css" / "styles.css"
css = styles.read_text(encoding="utf-8")
css += r'''

/* iOS Safari pull-to-refresh boundary. */
@media (max-width: 768px) {
  #login-screen.active {
    height: 100dvh;
    min-height: 100dvh;
    overflow-y: scroll;
    overscroll-behavior-y: contain;
    -webkit-overflow-scrolling: touch;
  }
  #login-screen.active::after {
    content: '';
    display: block;
    height: 1px;
    width: 1px;
    pointer-events: none;
  }

  /* The real material layout uses these study-* containers. The existing
     tablet rule deliberately sets their overflow to visible, which allowed a
     nowrap/desktop-width child to enlarge the page horizontally on iPhone. */
  .study-container,
  .study-content-panel,
  .study-content-area,
  .study-topic-wrapper,
  .study-card {
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
    overflow-x: hidden !important;
  }

  .study-content-panel,
  .study-card {
    overflow-y: visible !important;
  }

  .study-card *,
  .study-content-area *,
  .study-topic-wrapper * {
    min-width: 0 !important;
    max-width: 100% !important;
    box-sizing: border-box;
  }

  .study-card p,
  .study-card li,
  .study-card span,
  .study-card code,
  .study-card pre,
  .study-content-area p,
  .study-content-area li,
  .study-content-area span,
  .study-content-area code,
  .study-content-area pre {
    white-space: normal !important;
    overflow-wrap: anywhere !important;
    word-break: break-word !important;
  }

  .study-card img,
  .study-card video,
  .study-card iframe,
  .study-card table,
  .study-card pre {
    max-width: 100% !important;
  }
}
'''
styles.write_text(css, encoding="utf-8")

index_html = ROOT / "public" / "index.html"
index = index_html.read_text(encoding="utf-8")
index = index.replace("/js/app.js?v=20260917_login04", "/js/app.js?v=20260917_ptr10", 1)
index = index.replace("/css/styles.css?v=20260917_login04", "/css/styles.css?v=20260917_ptr10", 1)

# Mobile login fields stay read-only until that specific field is intentionally
# touched. Programmatic focus can still paint :focus on a read-only input, so
# clear it before first paint; because readOnly is still set, no keyboard can
# start. Scrolling elsewhere never unlocks the fields.
keyboard_guard = r'''
    <script>
    (function () {
        if (!window.matchMedia('(max-width: 768px)').matches) return;

        function loginFields() {
            return document.querySelectorAll('#login-screen input, #login-screen textarea');
        }
        function lockField(el) {
            if (!el || el.dataset.aulaStartupUnlocked === '1') return;
            if (!el.readOnly) {
                el.readOnly = true;
                el.dataset.aulaStartupReadonly = '1';
            }
        }
        function lockLoginFields() {
            loginFields().forEach(lockField);
        }
        function clearStartupFocus() {
            var active = document.activeElement;
            if (active && active.closest && active.closest('#login-screen') &&
                /^(INPUT|TEXTAREA)$/.test(active.tagName) &&
                active.dataset.aulaStartupUnlocked !== '1') {
                active.blur();
            }
        }
        function unlockTouchedField(e) {
            var el = e.target && e.target.closest ? e.target.closest('#login-screen input, #login-screen textarea') : null;
            if (!el) return;
            el.dataset.aulaStartupUnlocked = '1';
            if (el.dataset.aulaStartupReadonly === '1') {
                el.readOnly = false;
                delete el.dataset.aulaStartupReadonly;
            }
        }

        var observer = new MutationObserver(function () {
            lockLoginFields();
            clearStartupFocus();
        });
        observer.observe(document.documentElement, { childList: true, subtree: true });
        document.addEventListener('DOMContentLoaded', function () {
            lockLoginFields();
            clearStartupFocus();
            requestAnimationFrame(clearStartupFocus);
        }, { once: true });
        window.addEventListener('pageshow', function () {
            lockLoginFields();
            clearStartupFocus();
        });
        document.addEventListener('focusin', function (e) {
            var el = e.target;
            if (!el || !el.closest || !el.closest('#login-screen')) return;
            if (!/^(INPUT|TEXTAREA)$/.test(el.tagName)) return;
            if (el.dataset.aulaStartupUnlocked === '1') return;
            lockField(el);
            el.blur();
        }, true);
        document.addEventListener('touchstart', unlockTouchedField, { capture: true, passive: true });
        document.addEventListener('pointerdown', unlockTouchedField, { capture: true, passive: true });
    })();
    </script>
'''
anchor = '<script src="/js/bilingual_materials.js?v=20260911_v016" defer></script>'
if anchor not in index:
    raise RuntimeError("script anchor missing")
index = index.replace(anchor, keyboard_guard + "\n    " + anchor, 1)
index_html.write_text(index, encoding="utf-8")

server = ROOT / "server.py"
print("[BOOT] applied native iOS overscroll + login focus + real mobile study overflow fix")
print("[BOOT] starting AulaAI")
runpy.run_path(str(server), run_name="__main__")
