import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent

app_js = ROOT / "public" / "js" / "app.js"
source = app_js.read_text(encoding="utf-8")
marker = "// ── Pull-to-refresh suppression (iOS Safari) ──"
pos = source.find(marker)
if pos < 0: raise RuntimeError("iOS PTR handler marker missing")
source = source[:pos].rstrip() + "\n"

double_render = """  const alreadyOpen = !!document.querySelector('.study-topic-btn.active');
  if (isStudyTab && targetTopic && !alreadyOpen) {
    showStudyTopic(targetTopic, targetPage);
  } else if (isStudyTab && (!curriculum || curriculum.length === 0)) {"""
single_render = """  if (isStudyTab && (!curriculum || curriculum.length === 0)) {"""
if source.count(double_render) != 1:
    raise RuntimeError("material double-render guard changed")
source = source.replace(double_render, single_render, 1)

# Classroom entry used to repaint the same reader repeatedly: once before reveal,
# again through the post-reveal switchTab, then several more times while
# initLecturer/initStudent settled. Keep the first complete pre-reveal paint and
# make later renderStudyBook calls no-ops only for the duration of that entry.
render_decl = "function renderStudyBook() {"
if source.count(render_decl) != 1:
    raise RuntimeError("renderStudyBook declaration changed")
source = source.replace(render_decl, render_decl + "\n  if (window.__aulaClassroomStudyPaintLocked) return;", 1)

first_paint = "  renderStudyBook();\n\n  // 4. Restore exact study topic synchronously if on study materials or book"
locked_paint = "  renderStudyBook();\n  window.__aulaClassroomStudyPaintLocked = true;\n\n  // 4. Restore exact study topic synchronously if on study materials or book"
if source.count(first_paint) != 1:
    raise RuntimeError("classroom first material paint changed")
source = source.replace(first_paint, locked_paint, 1)

post_reveal_lecturer = """    if (tabBtn) {
      switchTab(tabBtn, false, !_isNavigatingFromPopState);
    } else {"""
post_reveal_lecturer_fixed = """    if (tabBtn) {
      // Target tab was already activated before the dashboard was revealed.
      // Do not repaint the reader after reveal.
    } else {"""
if source.count(post_reveal_lecturer) != 1:
    raise RuntimeError("lecturer post-reveal tab block changed")
source = source.replace(post_reveal_lecturer, post_reveal_lecturer_fixed, 1)

post_reveal_student = """    if (tabBtn) {
      switchTab(tabBtn, true, !_isNavigatingFromPopState);
    } else {"""
post_reveal_student_fixed = """    if (tabBtn) {
      // Target tab was already activated before the dashboard was revealed.
      // Do not repaint the reader after reveal.
    } else {"""
if source.count(post_reveal_student) != 1:
    raise RuntimeError("student post-reveal tab block changed")
source = source.replace(post_reveal_student, post_reveal_student_fixed, 1)

lecturer_init = "    await initLecturer();\n  } else {"
lecturer_init_fixed = "    await initLecturer();\n  } else {"
if source.count(lecturer_init) != 1:
    raise RuntimeError("lecturer init block changed")

unlock_anchor = """    await initStudent();
  }

  // Ensure the route URL is updated"""
unlock_fixed = """    await initStudent();
  }
  window.__aulaClassroomStudyPaintLocked = false;

  // Ensure the route URL is updated"""
if source.count(unlock_anchor) != 1:
    raise RuntimeError("classroom material unlock anchor changed")
source = source.replace(unlock_anchor, unlock_fixed, 1)

app_js.write_text(source, encoding="utf-8")

styles = ROOT / "public" / "css" / "styles.css"
css = styles.read_text(encoding="utf-8")
css += r'''
@media (max-width:768px){
 .screen.active{animation:none!important;transform:none!important;opacity:1!important}
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
boot_style = """    <style id=\"aula-boot-paint\">\n        html,body{margin:0;min-height:100%;background:#09162a;color-scheme:dark}\n        html[data-theme=\"light\"],html[data-theme=\"light\"] body{background:#f4f7fb;color-scheme:light}\n    </style>\n"""
head_anchor='    <meta charset="UTF-8">\n'
if boot_style not in index:
    if head_anchor not in index: raise RuntimeError("head boot-paint anchor missing")
    index=index.replace(head_anchor,head_anchor+boot_style,1)
index=index.replace('/js/app.js?v=20260917_login04','/js/app.js?v=20260917_ptr28',1).replace('/css/styles.css?v=20260917_login04','/css/styles.css?v=20260917_ptr28',1)
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
 function cleanExtras(){if(!mobile)return;var p=document.querySelector('.outline-sheet__panel');if(!p)return;p.querySelectorAll('.outline-sheet__actions button,.outline-sheet__actions a').forEach(function(el){var h=((el.textContent||'')+' '+(el.getAttribute('onclick')||'')+' '+(el.getAttribute('href')||'')+' '+(el.getAttribute('aria-label')||'')+' '+(el.getAttribute('title')||'')).replace(/\s+/g,' ').toLowerCase();if(/pdf|download|arayüz dili\s*:|interface\s*:|interface language\s*:/.test(h))el.remove()})}
 function cleanDesktop(){if(mobile)return;document.querySelectorAll('.mtoolbar button,.mtoolbar a').forEach(function(el){var h=((el.textContent||'')+' '+(el.title||'')+' '+(el.getAttribute('aria-label')||'')+' '+(el.getAttribute('onclick')||'')+' '+(el.getAttribute('href')||'')).toLowerCase();if(/pdf|download/.test(h))el.remove()})}
 var sy=0,locked=false;function panel(){var root=document.getElementById('study-outline-sheet'),p=document.querySelector('.outline-sheet__panel');if(!root||!p||root.classList.contains('hidden'))return null;var r=p.getBoundingClientRect(),s=getComputedStyle(p);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'?p:null}function scrollLock(){if(!mobile)return;var open=!!panel();if(open&&!locked){sy=scrollY||0;Object.assign(document.body.style,{position:'fixed',top:(-sy)+'px',left:'0',right:'0',width:'100%'});locked=true}else if(!open&&locked){['position','top','left','right','width'].forEach(function(k){document.body.style[k]=''});scrollTo(0,sy);locked=false}}
 function sync(){lockFields();blurStartup();prep();cleanExtras();cleanDesktop();requestAnimationFrame(scrollLock)}
 var q=false;new MutationObserver(function(){if(q)return;q=true;requestAnimationFrame(function(){q=false;sync()})}).observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['class','style','hidden']});
 document.addEventListener('DOMContentLoaded',function(){sync();requestAnimationFrame(blurStartup)},{once:true});addEventListener('pageshow',sync);document.addEventListener('focusin',function(e){if(!mobile)return;var el=e.target;if(el&&el.closest&&el.closest('#login-screen')&&/^(INPUT|TEXTAREA)$/.test(el.tagName)&&el.dataset.aulaStartupUnlocked!=='1'){lock(el);el.blur()}},true);document.addEventListener('touchstart',unlock,{capture:true,passive:true});document.addEventListener('pointerdown',unlock,{capture:true,passive:true});

 var lastLoginTap=0,lastLoginTarget=null;
 document.addEventListener('touchend',function(e){
   if(!mobile||e.touches.length)return;
   var t=e.target&&e.target.closest?e.target.closest('#login-screen input,#login-screen textarea,#login-screen button,#login-screen a,#login-screen label'):null;
   if(!t){lastLoginTap=0;lastLoginTarget=null;return}
   var now=Date.now();
   if(t===lastLoginTarget&&now-lastLoginTap<350)e.preventDefault();
   lastLoginTap=now;lastLoginTarget=t;
 },{capture:true,passive:false});
 document.addEventListener('click',function(e){if(!mobile){requestAnimationFrame(cleanDesktop);return}var t=e.target&&e.target.closest?e.target.closest('.outline__unit-title'):null;if(!t)return;e.preventDefault();e.stopImmediatePropagation();toggle(t)},true);
})();
</script>
<script>
(function(){
 const t0=performance.now(), rows=[];
 function active(){return Array.from(document.querySelectorAll('.screen.active')).map(x=>x.id||x.className).join(',')||'-'}
 function snap(event,extra){
   const loading=document.getElementById('loading-screen');
   const s={t:+(performance.now()-t0).toFixed(1),event,ready:document.readyState,active:active(),loading:loading?getComputedStyle(loading).display:'missing',extra:extra||''};
   rows.push(s); window.__AULA_STARTUP_TRACE=rows;
   try{localStorage.setItem('aula_startup_trace',JSON.stringify(rows))}catch(e){}
   console.log('[AULA-TRACE]',s);
   try{fetch('/api/version?startup_trace='+encodeURIComponent(JSON.stringify(s)),{cache:'no-store',keepalive:true}).catch(()=>{})}catch(e){}
 }
 window.__AULA_TRACE=snap;
 snap('trace-installed');
 document.addEventListener('DOMContentLoaded',()=>snap('DOMContentLoaded'),{once:true});
 addEventListener('load',()=>snap('window-load'),{once:true});
 addEventListener('pageshow',e=>snap('pageshow','persisted='+e.persisted));
 try{new PerformanceObserver(list=>list.getEntries().forEach(e=>snap('paint',e.name+'@'+e.startTime.toFixed(1)))).observe({type:'paint',buffered:true})}catch(e){}
 new MutationObserver(ms=>{let relevant=false;for(const m of ms){const el=m.target.nodeType===1?m.target:m.target.parentElement;if(el&&(el.matches?.('.screen,#loading-screen,#s-ai-book-content-area,#ai-book-content-area')||el.closest?.('.screen,#loading-screen,#s-ai-book-content-area,#ai-book-content-area'))){relevant=true;break}}if(relevant)snap('dom-mutation')}).observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['class','style','hidden']});
 ['selectClassroom','switchTab','renderStudyBook','showStudyTopic','showScreen'].forEach(name=>{let tries=0;const timer=setInterval(()=>{tries++;const fn=window[name];if(typeof fn==='function'&&!fn.__aulaTraced){const wrapped=function(){snap(name+':start',Array.from(arguments).slice(0,2).map(x=>typeof x==='object'?'[object]':String(x)).join('|'));try{return fn.apply(this,arguments)}finally{snap(name+':end')}};wrapped.__aulaTraced=true;window[name]=wrapped;clearInterval(timer)}else if(tries>200)clearInterval(timer)},25)});
 setTimeout(()=>snap('trace-5s'),5000);setTimeout(()=>snap('trace-10s'),10000);
})();
</script>
'''
anchor='<script src="/js/bilingual_materials.js?v=20260911_v016" defer></script>'
if anchor not in index: raise RuntimeError("script anchor missing")
index_html.write_text(index.replace(anchor,mobile_guards+'\n    '+anchor,1),encoding="utf-8")

# Quiz drafts should generate exactly the requested number first. The existing
# generate_quiz hard-completion/top-up path then asks only for any true deficit.
server_path = ROOT / "server.py"
server_source = server_path.read_text(encoding="utf-8")
quiz_parallel = "                if requested_count >= 8:\n"
quiz_single_count = "                        count=requested_count + 6,\n"
if server_source.count(quiz_parallel) != 1:
    raise RuntimeError("quiz parallel generation branch changed")
if server_source.count(quiz_single_count) != 1:
    raise RuntimeError("quiz single generation count changed")
server_source = server_source.replace(quiz_parallel, "                if False and requested_count >= 8:\n", 1)
server_source = server_source.replace(quiz_single_count, "                        count=requested_count,\n", 1)
server_path.write_text(server_source, encoding="utf-8")

runpy.run_path(str(ROOT/"server.py"),run_name="__main__")
