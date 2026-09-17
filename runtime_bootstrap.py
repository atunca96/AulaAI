import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# iOS Safari: do not cancel touchmove at all. A cancelled touch sequence can
# stay captured for the remainder of that finger gesture, which is exactly the
# direction-reversal lock we were seeing. Instead, make the mobile login a real
# nested vertical scroller with a 1px boundary buffer. MobileSafari keeps the
# gesture owned by that scroller, so it does not chain to the document/browser
# pull-to-refresh, while scrolling remains entirely native.
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

/* iOS Safari pull-to-refresh boundary.
   Keep this native: no touchmove preventDefault. The login becomes a genuine
   nested scroller by one physical CSS pixel, which keeps Safari's gesture on
   the element instead of handing it to document pull-to-refresh. */
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
}
'''
styles.write_text(css, encoding="utf-8")

index_html = ROOT / "public" / "index.html"
index = index_html.read_text(encoding="utf-8")
index = index.replace("/js/app.js?v=20260917_login04", "/js/app.js?v=20260917_ptr04", 1)
index = index.replace("/css/styles.css?v=20260917_login04", "/css/styles.css?v=20260917_ptr04", 1)

# Mobile Safari may restore focus to the login field while reopening/restoring
# the page, which immediately raises the software keyboard. Blur any restored
# form focus after the initial page restore. This does not block normal taps:
# after startup the fields behave exactly as before.
keyboard_guard = r'''
    <script>
    (function () {
        function dismissRestoredMobileFocus() {
            if (!window.matchMedia('(max-width: 768px)').matches) return;
            var active = document.activeElement;
            if (active && /^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName)) active.blur();
        }
        window.addEventListener('pageshow', function () {
            requestAnimationFrame(function () {
                requestAnimationFrame(dismissRestoredMobileFocus);
            });
        });
        window.addEventListener('load', function () {
            setTimeout(dismissRestoredMobileFocus, 150);
        });
    })();
    </script>
'''
if "</body>" not in index:
    raise RuntimeError("index body closing tag missing")
index = index.replace("</body>", keyboard_guard + "\n</body>", 1)
index_html.write_text(index, encoding="utf-8")

server = ROOT / "server.py"
print("[BOOT] applied native iOS overscroll boundary + mobile focus guard")
print("[BOOT] starting AulaAI")
runpy.run_path(str(server), run_name="__main__")
