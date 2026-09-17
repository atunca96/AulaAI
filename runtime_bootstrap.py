import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Keep the proven iOS Safari PTR fix: remove the old touch interception.
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
@media (max-width: 768px) {
  #login-screen.active { height:100dvh; min-height:100dvh; overflow-y:scroll; overscroll-behavior-y:contain; -webkit-overflow-scrolling:touch; }
  #login-screen.active::after { content:''; display:block; height:1px; width:1px; pointer-events:none; }

  .study-container { min-height:0 !important; height:auto !important; }
  .study-container,.study-content-panel,.study-content-area,.study-topic-wrapper,.study-card { min-width:0 !important; box-sizing:border-box !important; }
  .study-container,.study-content-panel { overflow-x:clip !important; }
  .study-content-area,.study-topic-wrapper,.study-card { max-width:100% !important; }
  .study-card img,.study-card video,.study-card iframe,.study-card table,.study-card pre { max-width:100% !important; }
  .study-card p,.study-card li,.study-card code,.study-card pre,.vocab-row__ipa,.phonetic-badge { max-width:100% !important; white-space:normal !important; overflow-wrap:anywhere !important; word-break:break-word !important; }

  /* Unit -> topic only. */
  .outline__pages { display:none !important; }
  .outline-sheet__panel { width:calc(100vw - 24px) !important; max-width:calc(100vw - 24px) !important; min-width:0 !important; overflow-x:hidden !important; overscroll-behavior:contain !important; box-sizing:border-box !important; }
  .outline-sheet__panel *,.outline__unit,.outline__unit-title,.outline__topic { min-width:0 !important; max-width:100% !important; box-sizing:border-box !important; }
  .outline__unit-title,.outline__topic { white-space:normal !important; overflow-wrap:anywhere !important; word-break:break-word !important; }
  .outline__unit-title[data-aula-unit-toggle="1"] { width:100%; min-height:44px; padding:8px 10px; margin-bottom:4px; border-radius:var(--radius); cursor:pointer; user-select:none; -webkit-user-select:none; }
  .outline__unit-title[data-aula-unit-toggle="1"]::after { content:'›'; margin-inline-start:auto; font-size:20px; line-height:1; transform:rotate(90deg); transition:transform .15s ease; }
  .outline__unit.is-aula-expanded > .outline__unit-title::after { transform:rotate(-90deg); }
  .outline__unit:not(.is-aula-expanded) > :not(.outline__unit-title) { display:none !important; }
}
'''
styles.write_text(css, encoding="utf-8")

index_html = ROOT / "public" / "index.html"
index = index_html.read_text(encoding="utf-8")
index = index.replace("/js/app.js?v=20260917_login04", "/js/app.js?v=20260917_ptr14", 1)
index = index.replace("/css/styles.css?v=20260917_login04", "/css/styles.css?v=20260917_ptr14", 1)

mobile_guards = r'''
<script>
(function () {
  var mobile = window.matchMedia('(max-width: 768px)').matches;

  /* Login: never let restored/programmatic startup focus raise the keyboard. */
  function loginFields(){ return document.querySelectorAll('#login-screen input, #login-screen textarea'); }
  function lockField(el){ if(!el || el.dataset.aulaStartupUnlocked==='1') return; if(!el.readOnly){ el.readOnly=true; el.dataset.aulaStartupReadonly='1'; } }
  function lockLoginFields(){ if(mobile) loginFields().forEach(lockField); }
  function clearStartupFocus(){ if(!mobile) return; var a=document.activeElement; if(a&&a.closest&&a.closest('#login-screen')&&/^(INPUT|TEXTAREA)$/.test(a.tagName)&&a.dataset.aulaStartupUnlocked!=='1') a.blur(); }
  function unlockTouchedField(e){ if(!mobile) return; var el=e.target&&e.target.closest?e.target.closest('#login-screen input, #login-screen textarea'):null; if(!el)return; el.dataset.aulaStartupUnlocked='1'; if(el.dataset.aulaStartupReadonly==='1'){ el.readOnly=false; delete el.dataset.aulaStartupReadonly; } }

  /* Mobile outline is exactly Unit -> Topic. */
  function prepareOutline(){
    if(!mobile) return;
    document.querySelectorAll('.outline__unit').forEach(function(unit){
      var title=unit.querySelector(':scope > .outline__unit-title');
      if(!title||title.dataset.aulaUnitToggle==='1') return;
      title.dataset.aulaUnitToggle='1'; title.setAttribute('role','button'); title.setAttribute('tabindex','0'); title.setAttribute('aria-expanded','false');
    });
  }
  function toggleUnit(title){
    var unit=title.closest('.outline__unit'); if(!unit)return;
    var opening=!unit.classList.contains('is-aula-expanded');
    document.querySelectorAll('.outline__unit.is-aula-expanded').forEach(function(other){ if(other!==unit){ other.classList.remove('is-aula-expanded'); var t=other.querySelector(':scope > .outline__unit-title'); if(t)t.setAttribute('aria-expanded','false'); } });
    unit.classList.toggle('is-aula-expanded',opening); title.setAttribute('aria-expanded',opening?'true':'false');
  }

  /* Remove the two redundant controls from the mobile unit sheet: its PDF
     download row and its interface-language row. Match by visible copy plus
     action semantics so this survives TR/EN switching without touching topics. */
  function cleanOutlineExtras(){
    if(!mobile) return;
    var panel=document.querySelector('.outline-sheet__panel'); if(!panel)return;
    Array.from(panel.querySelectorAll('button,a,[role="button"],div')).forEach(function(el){
      if(el.dataset.aulaOutlineCleaned==='1') return;
      var text=(el.textContent||'').replace(/\s+/g,' ').trim().toLowerCase();
      var action=((el.getAttribute('onclick')||'')+' '+(el.getAttribute('href')||'')+' '+(el.getAttribute('aria-label')||'')+' '+(el.getAttribute('title')||'')).toLowerCase();
      var pdf=(/pdf indir|download pdf|pdf download/.test(text) || /pdf/.test(action));
      var lang=(/arayüz dili\s*:|interface language\s*:/.test(text));
      if(!pdf&&!lang) return;
      /* Prefer removing the row itself, but never climb into the whole panel. */
      var row=el;
      while(row.parentElement&&row.parentElement!==panel&&row.parentElement.children.length===1) row=row.parentElement;
      if(row!==panel){ row.dataset.aulaOutlineCleaned='1'; row.remove(); }
    });
  }

  /* Desktop already has the canonical PDF action elsewhere. Remove only the
     duplicate download/PDF control in the reader's top material toolbar. */
  function cleanDesktopToolbarPdf(){
    if(mobile) return;
    document.querySelectorAll('.mtoolbar button,.mtoolbar a').forEach(function(el){
      var hay=((el.textContent||'')+' '+(el.getAttribute('title')||'')+' '+(el.getAttribute('aria-label')||'')+' '+(el.getAttribute('onclick')||'')+' '+(el.getAttribute('href')||'')).toLowerCase();
      if(/pdf|download/.test(hay)) el.remove();
    });
  }

  var outlineScrollY=0, outlineLocked=false;
  function visibleOutlinePanel(){ var p=document.querySelector('.outline-sheet__panel'); if(!p)return null; var r=p.getBoundingClientRect(),s=getComputedStyle(p); return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'?p:null; }
  function syncOutlineScrollLock(){
    if(!mobile)return;
    var open=!!visibleOutlinePanel();
    if(open&&!outlineLocked){ outlineScrollY=window.scrollY||0; document.body.style.position='fixed'; document.body.style.top=(-outlineScrollY)+'px'; document.body.style.left='0'; document.body.style.right='0'; document.body.style.width='100%'; outlineLocked=true; }
    else if(!open&&outlineLocked){ document.body.style.position=''; document.body.style.top=''; document.body.style.left=''; document.body.style.right=''; document.body.style.width=''; window.scrollTo(0,outlineScrollY); outlineLocked=false; }
  }

  function sync(){ lockLoginFields(); clearStartupFocus(); prepareOutline(); cleanOutlineExtras(); cleanDesktopToolbarPdf(); requestAnimationFrame(syncOutlineScrollLock); }
  var queued=false;
  new MutationObserver(function(){ if(queued)return; queued=true; requestAnimationFrame(function(){ queued=false; sync(); }); }).observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['class','style','hidden']});
  document.addEventListener('DOMContentLoaded',function(){ sync(); requestAnimationFrame(clearStartupFocus); },{once:true});
  window.addEventListener('pageshow',sync);
  document.addEventListener('focusin',function(e){ if(!mobile)return; var el=e.target; if(!el||!el.closest||!el.closest('#login-screen')||!/^(INPUT|TEXTAREA)$/.test(el.tagName)||el.dataset.aulaStartupUnlocked==='1')return; lockField(el); el.blur(); },true);
  document.addEventListener('touchstart',unlockTouchedField,{capture:true,passive:true});
  document.addEventListener('pointerdown',unlockTouchedField,{capture:true,passive:true});
  document.addEventListener('click',function(e){ if(!mobile){requestAnimationFrame(cleanDesktopToolbarPdf);return;} var title=e.target&&e.target.closest?e.target.closest('.outline__unit-title[data-aula-unit-toggle="1"]'):null; if(!title){requestAnimationFrame(syncOutlineScrollLock);return;} e.preventDefault();e.stopPropagation();toggleUnit(title); },true);
  document.addEventListener('keydown',function(e){ if(!mobile)return; var title=e.target&&e.target.closest?e.target.closest('.outline__unit-title[data-aula-unit-toggle="1"]'):null; if(!title||(e.key!=='Enter'&&e.key!==' '))return; e.preventDefault();e.stopPropagation();toggleUnit(title); },true);
})();
</script>
'''
anchor = '<script src="/js/bilingual_materials.js?v=20260911_v016" defer></script>'
if anchor not in index:
    raise RuntimeError("script anchor missing")
index = index.replace(anchor, mobile_guards + "\n    " + anchor, 1)
index_html.write_text(index, encoding="utf-8")

server = ROOT / "server.py"
print("[BOOT] applied iOS/mobile material fixes + redundant PDF/language cleanup")
print("[BOOT] starting AulaAI")
runpy.run_path(str(server), run_name="__main__")
