import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Replace the previous iOS pull-to-refresh handler at container startup.
# Important: once Safari has seen preventDefault() during a touch sequence,
# simply stopping preventDefault() after a direction reversal does not restore
# native scrolling for that same sequence. Therefore we must not cancel normal
# page gestures in the first place. The replacement is intentionally scoped to
# the non-scrollable mobile login screen, where a downward drag at the top can
# only be browser pull-to-refresh.
app_js = ROOT / "public" / "js" / "app.js"
source = app_js.read_text(encoding="utf-8")
marker = "// ── Pull-to-refresh suppression (iOS Safari) ──"
pos = source.find(marker)
if pos < 0:
    raise RuntimeError("iOS PTR handler marker missing")
source = source[:pos].rstrip() + "\n\n" + r'''// ── Pull-to-refresh suppression (iOS Safari) ──
// Do not intercept ordinary document scrolling. On iOS, cancelling even one
// touchmove can hand the rest of that touch sequence to JS, so reversing the
// finger afterwards may no longer resume native scrolling. Only the mobile
// login screen is protected here: it is designed to fit one viewport and has
// no legitimate document scroll at its top edge.
(function suppressPullToRefresh() {
  var startX = 0;
  var startY = 0;
  var tracking = false;
  var loginGesture = false;

  function mobileLoginActive() {
    var login = document.getElementById('login-screen');
    return !!(login && login.classList.contains('active') && window.matchMedia('(max-width: 768px)').matches);
  }

  document.addEventListener('touchstart', function (e) {
    tracking = e.touches.length === 1;
    loginGesture = tracking && mobileLoginActive();
    if (!loginGesture) return;
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
  }, { passive: true });

  document.addEventListener('touchmove', function (e) {
    if (!tracking || !loginGesture || e.touches.length !== 1) return;

    var dx = e.touches[0].clientX - startX;
    var dy = e.touches[0].clientY - startY;
    if (dy <= 0 || Math.abs(dy) <= Math.abs(dx)) return;

    var doc = document.scrollingElement || document.documentElement;
    if (doc.scrollTop > 0) return;

    e.preventDefault();
  }, { passive: false });

  function endGesture() {
    tracking = false;
    loginGesture = false;
  }
  document.addEventListener('touchend', endGesture, { passive: true });
  document.addEventListener('touchcancel', endGesture, { passive: true });
})();
'''
app_js.write_text(source, encoding="utf-8")

# Force Safari to fetch this JS rather than reuse the previous gesture handler.
index_html = ROOT / "public" / "index.html"
index = index_html.read_text(encoding="utf-8")
index = index.replace("/js/app.js?v=20260917_login04", "/js/app.js?v=20260917_ptr02", 1)
index_html.write_text(index, encoding="utf-8")

server = ROOT / "server.py"
print("[BOOT] applied scoped iOS pull-to-refresh fix")
print("[BOOT] starting AulaAI")
runpy.run_path(str(server), run_name="__main__")
