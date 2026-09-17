import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent

app_js = ROOT / "public" / "js" / "app.js"
source = app_js.read_text(encoding="utf-8")
marker = "// ── Pull-to-refresh suppression (iOS Safari) ──"
pos = source.find(marker)
if pos < 0: raise RuntimeError("iOS PTR handler marker missing")
app_js.write_text(source[:pos].rstrip() + "\n", encoding="utf-8")

styles = ROOT / "public" / "css" / "styles.css"
css = styles.read_text(encoding="utf-8")
css += r'''
@media (max-width:768px){
 #login-screen.active{height:100dvh;min-height:100dvh;overflow-y:scroll;overscroll-behavior-y:contain;-webkit-overflow-scrolling:touch}
 #login-screen.active::after{content:'';display:block;height:1px;width:1px;pointer-events:none}
 .study-container{min-height:0!important;height:auto!important}
 .study-container,.study-content-panel,.study-content-area,.study-topic-wrapper,.study-card{min-width:0!important;box-sizing:border-box!important}
 .study-container,.study-content-panel{overflow-x:clip!important}
 .study-content-area,.study-topic-wrapper,.study-card{max-width:100%!important}
 .study-card img,.study-card video,.study-card iframe,.study-card table,.study-card pre{max-width:100%!important}
 .study-meta,.study-meta *,.cefr-level-subtitle,.cefr-level-subtitle *,#s-ai-book-content-area>.study-meta,#ai-book-content-area>.study-meta{min-width:0!important;max-width:100%!important;box-sizing:border-box!important;white-space:normal!important;overflow-wrap:anywhere!important;word-break:break-word!important}
 #s-ai-book-content-area .study-card *,#ai-book-content-area .study-card *{min-width:0!important;max-width:100%!important;box-sizing:border-box!important}
 #s-ai-book-content-area .study-card p,#s-ai-book-content-area .study-card li,#s-ai-book-content-area .study-card span,#s-ai-book-content-area .study-card div,#s-ai-book-content-area .study-card code,#s-ai-book-content-area .study-card pre,#ai-book-content-area .study-card p,#ai-book-content-area .study-card li,#ai-book-content-area .study-card span,#ai-book-content-area .study-card div,#ai-book-content-area .study-card code,#ai-book-content-area .study-card pre,.vocab-row__ipa,.phonetic-badge{overflow-wrap:anywhere!important;word-break:break-word!important}
 .vocab-row__ipa,.phonetic-badge{white-space:normal!important}

 .outline__pages{display:none!important}
 .outline-sheet__panel{width:calc(100vw - 24px)!important;max-width:calc(100vw - 24px)!important;min-width:0!important;overflow-x:hidden!important;overscroll-behavior:contain!important;box-sizing:border-box!important}
 .outline-sheet__panel *,.outline__unit,.outline__unit-title,.outline__topic{min-width:0!important;max-width:100%!important;box-sizing:border-box!important}
 .outline__unit-title,.outline__topic{white-space:normal!important;overflow-wrap:anywhere!important;word-break:break-word!important}
 .outline__topic{font-size:var(--fs-2xs)!important;font-weight:var(--fw-medium)!important;text-transform:none!important;letter-spacing:var(--ls-normal)!important;line-height:1.4!important;color:var(--text-secondary);padding:var(--space-3) var(--space-5)!important}
 .outline__topic.is-current{color:var(--text-primary);font-weight:var(--fw-semibold)!important}
 .outline__unit-title[data-aula-unit-toggle="1"]{width:100%;min-height:44px;padding:8px 10px;margin-bottom:4px;border-radius:var(--radius);cursor:pointer;user-select:none;-webkit-user-select:none}
 .outline__unit-title[data-aula-unit-toggle="1"]::after{content:'›';margin-inline-start:auto;font-size:20px;line-height:1;transform:rotate(90deg);transition:transform .15s ease}
 .outline__unit[data-aula-expanded="1"]>.outline__unit-title::after{transform:rotate(-90deg)}
 .outline__unit:not([data-aula-expanded="1"])>:not(.outline__unit-title){display:none!important}
}
'''
styles.write_text(css,encoding="utf-8")

index_html=ROOT/"public"/"index.html"
index=index_html.read_text(encoding="utf-8")
index=index.replace('/js/app.js?v=20260917_login04','/js/app.js?v=20260917_ptr17',1).replace('/css/styles.css?v=20260917_login04','/css/styles.css?v=20260917_ptr17',1)
mobile_guards=r'''
<script>
(function(){
 var mobile=matchMedia('(max-width:768px)').matches;
 function fields(){return document.querySelectorAll('#login-screen input,#login-screen textarea')}
 function lock(el){if(!el||el.dataset.aulaStartupUnlocked==='1')return;if(!el.readOnly){el.readOnly=true;el.dataset.aulaStartupReadonly='1'}}
 function lockFields(){if(mobile)fields().forEach(lock)}
 function blurStartup(){if(!mobile)return;var a=document.activeElement;if(a&&a.closest&&a.closest('#login-screen')&&/^(INPUT|TEXTAREA)$/.test(a.tagName)&&a.dataset.aulaStartupUnlocked!=='1')a.blur()}
 function unlock(e){if(!mobile)return;var el=e.target&&e.target.closest?e.target.closest('#login-screen input,#login-screen textarea'):null;if(!el)return;el.dataset.aulaStartupUnlocked='1';if(el.dataset.aulaStartupReadonly==='1'){el.readOnly=false;delete el.dataset.aulaStartupReadonly}}
 function prep(){if(!mobile)return;document.querySelectorAll('.outline__unit').forEach(function(u){var t=u.querySelector(':scope>.outline__unit-title');if(!t)return;t.dataset.aulaUnitToggle='1';t.setAttribute('role','button');t.setAttribute('tabindex','0');t.setAttribute('aria-expanded',u.dataset.aulaExpanded==='1'?'true':'false')})}
 function toggle(t){var u=t.closest('.outline__unit');if(!u)return;var open=u.dataset.aulaExpanded!=='1';document.querySelectorAll('.outline__unit[data-aula-expanded="1"]').forEach(function(o){if(o!==u){delete o.dataset.aulaExpanded;var x=o.querySelector(':scope>.outline__unit-title');if(x)x.setAttribute('aria-expanded','false')}});if(open)u.dataset.aulaExpanded='1';else delete u.dataset.aulaExpanded;t.setAttribute('aria-expanded',open?'true':'false')}
 function cleanExtras(){if(!mobile)return;var p=document.querySelector('.outline-sheet__panel');if(!p)return;Array.from(p.querySelectorAll('button,a,[role="button"],div')).forEach(function(el){var text=(el.textContent||'').replace(/\s+/g,' ').trim().toLowerCase(),act=((el.getAttribute('onclick')||'')+' '+(el.getAttribute('href')||'')+' '+(el.getAttribute('aria-label')||'')+' '+(el.getAttribute('title')||'')).toLowerCase();if(!(/pdf indir|download pdf|pdf download/.test(text)||/pdf/.test(act)||/arayüz dili\s*:|interface language\s*:/.test(text)))return;var row=el;while(row.parentElement&&row.parentElement!==p&&row.parentElement.children.length===1)row=row.parentElement;if(row!==p)row.remove()})}
 function cleanDesktop(){if(mobile)return;document.querySelectorAll('.mtoolbar button,.mtoolbar a').forEach(function(el){var h=((el.textContent||'')+' '+(el.title||'')+' '+(el.getAttribute('aria-label')||'')+' '+(el.getAttribute('onclick')||'')+' '+(el.getAttribute('href')||'')).toLowerCase();if(/pdf|download/.test(h))el.remove()})}
 var sy=0,locked=false;function panel(){var p=document.querySelector('.outline-sheet__panel');if(!p)return null;var r=p.getBoundingClientRect(),s=getComputedStyle(p);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'?p:null}function scrollLock(){if(!mobile)return;var open=!!panel();if(open&&!locked){sy=scrollY||0;Object.assign(document.body.style,{position:'fixed',top:(-sy)+'px',left:'0',right:'0',width:'100%'});locked=true}else if(!open&&locked){['position','top','left','right','width'].forEach(function(k){document.body.style[k]=''});scrollTo(0,sy);locked=false}}
 function sync(){lockFields();blurStartup();prep();cleanExtras();cleanDesktop();requestAnimationFrame(scrollLock)}
 var q=false;new MutationObserver(function(){if(q)return;q=true;requestAnimationFrame(function(){q=false;sync()})}).observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['class','style','hidden']});
 document.addEventListener('DOMContentLoaded',function(){sync();requestAnimationFrame(blurStartup)},{once:true});addEventListener('pageshow',sync);document.addEventListener('focusin',function(e){if(!mobile)return;var el=e.target;if(el&&el.closest&&el.closest('#login-screen')&&/^(INPUT|TEXTAREA)$/.test(el.tagName)&&el.dataset.aulaStartupUnlocked!=='1'){lock(el);el.blur()}},true);document.addEventListener('touchstart',unlock,{capture:true,passive:true});document.addEventListener('pointerdown',unlock,{capture:true,passive:true});
 document.addEventListener('click',function(e){if(!mobile){requestAnimationFrame(cleanDesktop);return}var t=e.target&&e.target.closest?e.target.closest('.outline__unit-title'):null;if(!t)return;e.preventDefault();e.stopImmediatePropagation();toggle(t)},true);
})();
</script>
'''
anchor='<script src="/js/bilingual_materials.js?v=20260911_v016" defer></script>'
if anchor not in index: raise RuntimeError("script anchor missing")
index_html.write_text(index.replace(anchor,mobile_guards+'\n    '+anchor,1),encoding="utf-8")
runpy.run_path(str(ROOT/"server.py"),run_name="__main__")
