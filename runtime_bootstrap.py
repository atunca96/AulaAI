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

  /* Material page: preserve the existing responsive layout, only remove x overflow. */
  .study-container,
  .study-content-panel,
  .study-content-area,
  .study-topic-wrapper,
  .study-card {
    min-width: 0 !important;
    box-sizing: border-box !important;
  }
  .study-container,
  .study-content-panel { overflow-x: clip !important; }
  .study-content-area,
  .study-topic-wrapper,
  .study-card { max-width: 100% !important; }

  .study-card img,
  .study-card video,
  .study-card iframe,
  .study-card table,
  .study-card pre { max-width: 100% !important; }

  .study-card p,
  .study-card li,
  .study-card code,
  .study-card pre,
  .vocab-row__ipa,
  .phonetic-badge {
    max-width: 100% !important;
    white-space: normal !important;
    overflow-wrap: anywhere !important;
    word-break: break-word !important;
  }

  /* Unit/topic outline sheet is also vertical-only on phones. */
  .outline-sheet__panel {
    width: calc(100vw - 24px) !important;
    max-width: calc(100vw - 24px) !important;
    min-width: 0 !important;
    overflow-x: hidden !important;
    box-sizing: border-box !important;
  }
  .outline-sheet__panel *,
  .outline__unit,
  .outline__unit-title,
  .outline__topic,
  .outline__pages,
  .outline__page {
    min-width: 0 !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
  }
  .outline__unit-title,
  .outline__topic,
  .outline__page,
  .outline__label {
    white-space: normal !important;
    overflow-wrap: anywhere !important;
    word-break: break-word !important;
  }

  /* On mobile the outline starts at unit level. Tapping a unit heading reveals
     its topic/sub-header choices; choosing the topic keeps the app's existing
     selection handler intact. */
  .outline__unit-title[data-aula-unit-toggle="1"] {
    width: 100%;
    min-height: 44px;
    padding: 8px 10px;
    margin-bottom: 4px;
    border-radius: var(--radius);
    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
  }
  .outline__unit-title[data-aula-unit-toggle="1"]::after {
    content: '›';
    margin-inline-start: auto;
    font-size: 20px;
    line-height: 1;
    transform: rotate(90deg);
    transition: transform .15s ease;
  }
  .outline__unit.is-aula-expanded > .outline__unit-title::after {
    transform: rotate(-90deg);
  }
  .outline__unit:not(.is-aula-expanded) > :not(.outline__unit-title) {
    display: none !important;
  }
}
'''
styles.write_text(css, encoding="utf-8")

index_html = ROOT / "public" / "index.html"
index = index_html.read_text(encoding="utf-8")
index = index.replace("/js/app.js?v=20260917_login04", "/js/app.js?v=20260917_ptr12", 1)
index = index.replace("/css/styles.css?v=20260917_login04", "/css/styles.css?v=20260917_ptr12", 1)

mobile_guards = r'''
    <script>
    (function () {
        if (!window.matchMedia('(max-width: 768px)').matches) return;

        /* Login: no startup keyboard/focus until the exact field is tapped. */
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
        function lockLoginFields() { loginFields().forEach(lockField); }
        function clearStartupFocus() {
            var active = document.activeElement;
            if (active && active.closest && active.closest('#login-screen') &&
                /^(INPUT|TEXTAREA)$/.test(active.tagName) &&
                active.dataset.aulaStartupUnlocked !== '1') active.blur();
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

        /* Material outline: present units first, then reveal that unit's
           sub-headers/topics without invoking the topic-selection handler. */
        function prepareOutline() {
            document.querySelectorAll('.outline__unit').forEach(function (unit) {
                var title = unit.querySelector(':scope > .outline__unit-title');
                if (!title || title.dataset.aulaUnitToggle === '1') return;
                title.dataset.aulaUnitToggle = '1';
                title.setAttribute('role', 'button');
                title.setAttribute('tabindex', '0');
                title.setAttribute('aria-expanded', 'false');
            });
        }
        function toggleUnit(title) {
            var unit = title.closest('.outline__unit');
            if (!unit) return;
            var opening = !unit.classList.contains('is-aula-expanded');
            document.querySelectorAll('.outline__unit.is-aula-expanded').forEach(function (other) {
                if (other !== unit) {
                    other.classList.remove('is-aula-expanded');
                    var t = other.querySelector(':scope > .outline__unit-title');
                    if (t) t.setAttribute('aria-expanded', 'false');
                }
            });
            unit.classList.toggle('is-aula-expanded', opening);
            title.setAttribute('aria-expanded', opening ? 'true' : 'false');
        }

        var observer = new MutationObserver(function () {
            lockLoginFields();
            clearStartupFocus();
            prepareOutline();
        });
        observer.observe(document.documentElement, { childList: true, subtree: true });
        document.addEventListener('DOMContentLoaded', function () {
            lockLoginFields();
            clearStartupFocus();
            prepareOutline();
            requestAnimationFrame(clearStartupFocus);
        }, { once: true });
        window.addEventListener('pageshow', function () {
            lockLoginFields();
            clearStartupFocus();
            prepareOutline();
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

        document.addEventListener('click', function (e) {
            var title = e.target && e.target.closest ? e.target.closest('.outline__unit-title[data-aula-unit-toggle="1"]') : null;
            if (!title) return;
            e.preventDefault();
            e.stopPropagation();
            toggleUnit(title);
        }, true);
        document.addEventListener('keydown', function (e) {
            var title = e.target && e.target.closest ? e.target.closest('.outline__unit-title[data-aula-unit-toggle="1"]') : null;
            if (!title || (e.key !== 'Enter' && e.key !== ' ')) return;
            e.preventDefault();
            e.stopPropagation();
            toggleUnit(title);
        }, true);
    })();
    </script>
'''
anchor = '<script src="/js/bilingual_materials.js?v=20260911_v016" defer></script>'
if anchor not in index:
    raise RuntimeError("script anchor missing")
index = index.replace(anchor, mobile_guards + "\n    " + anchor, 1)
index_html.write_text(index, encoding="utf-8")

server = ROOT / "server.py"
print("[BOOT] applied iOS overscroll + login focus + mobile material/outline fixes")
print("[BOOT] starting AulaAI")
runpy.run_path(str(server), run_name="__main__")
