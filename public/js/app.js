// ── State & i18n ──
let currentUser = null;
let courseId = null;
let curriculum = [];
let currentLang = 'en';

const i18n = {
  en: {
    langBtn: '🌐 EN / TR', signInTab: 'Sign In', registerTab: 'Register', welcomeBack: 'Welcome Back', signInHint: 'Sign in to continue', emailLabel: 'Email', passwordLabel: 'Password', signInBtn: 'Sign In', joinClass: 'Join the Class', registerHint: 'Create a student account', nameLabel: 'Full Name', registerBtn: 'Create Account', lecturerAccess: 'Lecturer Access', signOut: 'Sign Out', home: 'Home', practice: 'Practice', quizzes: 'Quizzes', myProgress: 'My Progress', keepUp: 'Keep up the great work!', overallMastery: 'Overall Mastery', strongTopics: 'Strong Topics', needsWork: 'Needs Work', topicsStudied: 'Topics Studied', currentChapter: 'Current Chapter', selectPractice: 'Select a topic to practice', availableQuizzes: 'Available quizzes', trackMastery: 'Track your mastery across topics', noQuizzes: 'No quizzes yet.', takeQuiz: 'Take Quiz', view: 'View', close: 'Close', done: 'Done', submit: 'Submit', check: 'Check', yourScore: 'Your Score', questions: 'questions', correct: 'correct', incorrectAns: 'Incorrect. The answer is:', correctAns: 'The correct answer is:', correctMsg: '¡Correcto! ✓'
  },
  tr: {
    langBtn: '🌐 TR / EN', signInTab: 'Giriş Yap', registerTab: 'Kayıt Ol', welcomeBack: 'Tekrar Hoş Geldiniz', signInHint: 'Devam etmek için giriş yapın', emailLabel: 'E-posta', passwordLabel: 'Şifre', signInBtn: 'Giriş Yap', joinClass: 'Sınıfa Katıl', registerHint: 'Öğrenci hesabı oluştur', nameLabel: 'Ad Soyad', registerBtn: 'Hesap Oluştur', lecturerAccess: 'Öğretmen Girişi', signOut: 'Çıkış Yap', home: 'Ana Sayfa', practice: 'Alıştırma', quizzes: 'Sınavlar', myProgress: 'Gelişimim', keepUp: 'Harika gidiyorsun, devam et!', overallMastery: 'Genel Başarı', strongTopics: 'İyi Olduğum Konular', needsWork: 'Eksiğim Olan Konular', topicsStudied: 'Çalışılan Konular', currentChapter: 'Mevcut Ünite', selectPractice: 'Alıştırma yapmak için bir konu seçin', availableQuizzes: 'Mevcut Sınavlar', trackMastery: 'Konulardaki başarı durumunuzu takip edin', noQuizzes: 'Henüz sınav yok.', takeQuiz: 'Sınava Başla', view: 'Görüntüle', close: 'Kapat', done: 'Bitti', submit: 'Gönder', check: 'Kontrol Et', yourScore: 'Puanınız', questions: 'soru', correct: 'doğru', incorrectAns: 'Yanlış. Doğru cevap:', correctAns: 'Doğru cevap:', correctMsg: 'Doğru! ✓'
  }
};

function t(key) { return i18n[currentLang][key] || key; }

function toggleLanguage() {
  currentLang = currentLang === 'en' ? 'tr' : 'en';
  document.getElementById('lang-btn').textContent = t('langBtn');
  
  // Direct DOM text replacement for static elements
  const walkDOM = (node) => {
    const from = currentLang === 'en' ? i18n['tr'] : i18n['en'];
    const to = currentLang === 'en' ? i18n['en'] : i18n['tr'];
    
    if (node.nodeType === 3) {
      let txt = node.nodeValue.trim();
      let matchKey = Object.keys(from).find(k => from[k] === txt);
      if (matchKey) node.nodeValue = node.nodeValue.replace(txt, to[matchKey]);
    } else if (node.nodeType === 1 && node.nodeName !== 'SCRIPT') {
      if (node.placeholder) {
        let matchKey = Object.keys(from).find(k => from[k] === node.placeholder);
        if (matchKey) node.placeholder = to[matchKey];
      }
      for (let child = node.firstChild; child; child = child.nextSibling) walkDOM(child);
    }
  };
  walkDOM(document.body);

  if (currentUser) {
    if (currentUser.role === 'lecturer') initLecturer();
    else initStudent();
  }
}

// ── API Helper ──
async function api(path, opts = {}) {
  const res = await fetch('/api' + path, {
    method: opts.method || 'GET',
    headers: opts.body ? { 'Content-Type': 'application/json' } : {},
    body: opts.body ? JSON.stringify(opts.body) : undefined
  });
  return res.json();
}

// ── Auth & Login ──
function toggleAuth(type) {
  document.getElementById('tab-login').classList.toggle('active', type === 'login');
  document.getElementById('tab-register').classList.toggle('active', type === 'register');
  document.getElementById('login-form').classList.toggle('hidden', type === 'register');
  document.getElementById('register-form').classList.toggle('hidden', type === 'login');
  document.getElementById('demo-login-btn').classList.toggle('hidden', type === 'register');
}

function fillDemo(role) {
  if (role === 'lecturer') {
    document.getElementById('login-email').value = 'garcia@university.edu';
    document.getElementById('login-password').value = 'demo123';
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const data = await api('/register', { method: 'POST', body: {
    name: document.getElementById('register-name').value,
    email: document.getElementById('register-email').value,
    password: document.getElementById('register-password').value
  }});
  if (data.error) { document.getElementById('register-error').textContent = data.error; document.getElementById('register-error').classList.remove('hidden'); return false; }
  
  currentUser = data.user;
  const courses = await api('/courses');
  if (courses.length) courseId = courses[0].id;
  curriculum = await api('/curriculum?course_id=' + courseId);
  showScreen('student-dashboard');
  initStudent();
  return false;
}

async function handleLogin(e) {
  e.preventDefault();
  const data = await api('/login', { method: 'POST', body: {
    email: document.getElementById('login-email').value,
    password: document.getElementById('login-password').value
  }});
  if (data.error) { document.getElementById('login-error').textContent = data.error; document.getElementById('login-error').classList.remove('hidden'); return false; }
  currentUser = data.user;
  const courses = await api('/courses');
  if (courses.length) courseId = courses[0].id;
  curriculum = await api('/curriculum?course_id=' + courseId);
  showScreen(currentUser.role === 'lecturer' ? 'lecturer-dashboard' : 'student-dashboard');
  if (currentUser.role === 'lecturer') initLecturer(); else initStudent();
  return false;
}

function logout() { currentUser = null; showScreen('login-screen'); }

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

function switchTab(btn) {
  const nav = btn.closest('.topnav') || btn.closest('nav');
  nav.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  const main = btn.closest('.screen').querySelector('main');
  main.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
}

function closeModal() { document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden')); }

// ── Mastery color ──
function masteryColor(s) { return s >= 0.75 ? 'var(--success)' : s >= 0.4 ? 'var(--warning)' : 'var(--danger)'; }
function masteryClass(s) { return s >= 0.75 ? 'success' : s >= 0.4 ? 'warning' : 'danger'; }

// ── Lecturer Init ──
async function initLecturer() {
  document.getElementById('nav-username').textContent = currentUser.name;
  document.getElementById('overview-greeting').textContent = 'Welcome back, ' + currentUser.name.split(' ').pop();
  await loadOverview();
  loadCurriculum();
  populateSelects();
  loadQuizList();
  loadStudentRoster();
}

async function loadOverview() {
  const report = await api('/report?course_id=' + courseId);
  const s = report.summary || {};
  document.getElementById('overview-stats').innerHTML = `
    <div class="stat-card"><div class="stat-label">Students</div><div class="stat-value accent">${s.total_students||0}</div><div class="stat-sub">${s.active_students||0} active this week</div></div>
    <div class="stat-card"><div class="stat-label">Class Mastery</div><div class="stat-value ${masteryClass(s.class_avg_mastery)}">${Math.round((s.class_avg_mastery||0)*100)}%</div><div class="stat-sub">Average across all topics</div></div>
    <div class="stat-card"><div class="stat-label">At Risk</div><div class="stat-value ${s.at_risk_count > 0 ? 'danger' : 'success'}">${s.at_risk_count||0}</div><div class="stat-sub">Students needing attention</div></div>
    <div class="stat-card"><div class="stat-label">Top Performers</div><div class="stat-value success">${s.top_performer_count||0}</div><div class="stat-sub">Mastery above 80%</div></div>`;

  const atRisk = report.at_risk_students || [];
  document.getElementById('at-risk-list').innerHTML = atRisk.length === 0
    ? '<p style="color:var(--text-muted)">No at-risk students 🎉</p>'
    : atRisk.map(s => `<div class="risk-item"><div><span class="risk-name">${s.name}</span></div><div class="risk-badges"><span class="risk-badge ${s.overall_mastery < 0.4 ? 'critical' : 'warning'}">${Math.round(s.overall_mastery*100)}% mastery</span>${s.flags.map(f => `<span class="risk-badge low">${f.replace(/_/g,' ')}</span>`).join('')}</div></div>`).join('');

  const td = report.topic_difficulty || {};
  document.getElementById('topic-difficulty-chart').innerHTML = Object.entries(td).slice(0, 8).map(([name, score]) =>
    `<div class="progress-item"><div class="progress-label"><span>${name}</span><span>${Math.round(score*100)}%</span></div><div class="progress-bar"><div class="progress-fill" style="width:${score*100}%;background:${masteryColor(score)}"></div></div></div>`
  ).join('');
}

function loadCurriculum() {
  document.getElementById('curriculum-tree').innerHTML = curriculum.map((ch, i) => `
    <div class="chapter-block">
      <div class="chapter-header" onclick="this.nextElementSibling.classList.toggle('open');this.querySelector('.chapter-toggle').textContent=this.nextElementSibling.classList.contains('open')?'▾':'▸'">
        <div style="display:flex;align-items:center"><span class="chapter-num">${ch.number}</span><span class="chapter-title">${ch.title}</span></div>
        <span class="chapter-toggle">▸</span>
      </div>
      <div class="chapter-topics">${(ch.topics||[]).map(t => `
        <div class="topic-item">
          <div class="topic-info"><span class="topic-type-badge ${t.type}">${t.type}</span><span class="topic-name">${t.title}</span></div>
          <div class="topic-meta"><span>${t.difficulty}</span><span>${t.question_count||0} questions</span></div>
        </div>`).join('')}
      </div>
    </div>`).join('');
}

function populateSelects() {
  let topicOpts = '', chapterOpts = '';
  curriculum.forEach(ch => {
    chapterOpts += `<option value="${ch.id}">Unit ${ch.number}: ${ch.title}</option>`;
    (ch.topics||[]).forEach(t => { topicOpts += `<option value="${t.id}">U${ch.number} — ${t.title} (${t.type})</option>`; });
  });
  document.getElementById('activity-topic-select').innerHTML = '<option value="">Select a topic...</option>' + topicOpts;
  document.getElementById('quiz-chapter-select').innerHTML = '<option value="">All chapters</option>' + chapterOpts;
}

// ── Activities ──
async function launchActivity() {
  const topicId = document.getElementById('activity-topic-select').value;
  if (!topicId) return alert('Please select a topic');
  const data = await api('/activity?topic_id=' + topicId);
  const preview = document.getElementById('activity-preview');
  preview.classList.remove('hidden');
  preview.innerHTML = '<h2 style="margin-bottom:20px">📋 Generated Activities — ' + (data.topic?.title||'') + '</h2>' +
    (data.activities||[]).map((a, i) => renderActivityCard(a, i, 'preview')).join('');
}

function renderActivityCard(a, idx, ctx) {
  if (a.type === 'mcq') {
    return `<div class="activity-card" id="${ctx}-${idx}"><div class="activity-type-label">Multiple Choice</div><div class="activity-prompt">${a.prompt}</div><div class="options-grid">${(a.options||[]).map(o => `<button class="option-btn" onclick="checkMCQ(this,'${esc(a.answer)}','${ctx}-${idx}')">${o}</button>`).join('')}</div><div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
  }
  if (a.type === 'fill_blank') {
    return `<div class="activity-card" id="${ctx}-${idx}"><div class="activity-type-label">Fill in the Blank</div><div class="activity-prompt">${a.prompt}</div><div><input class="fill-blank-input" id="inp-${ctx}-${idx}" placeholder="Your answer..." onkeydown="if(event.key==='Enter')checkFill('${ctx}-${idx}','${esc(a.answer)}')"><button class="btn btn-primary btn-sm" style="margin-left:8px" onclick="checkFill('${ctx}-${idx}','${esc(a.answer)}')">Check</button></div>${a.hint ? `<div style="margin-top:8px;font-size:13px;color:var(--text-muted)">💡 ${a.hint}</div>` : ''}<div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
  }
  if (a.type === 'dialogue_order') {
    return `<div class="activity-card"><div class="activity-type-label">Dialogue Order — ${a.title||''}</div><div class="activity-prompt">Arrange the dialogue in the correct order:</div><div id="dialogue-${idx}">${(a.scrambled_lines||[]).map((l,j) => `<div class="option-btn" style="margin-bottom:6px;cursor:grab" draggable="true" data-line="${esc(l)}">${l}</div>`).join('')}</div></div>`;
  }
  return '';
}

function esc(s) { return (s||'').replace(/'/g, "\\'").replace(/"/g, '&quot;'); }

function checkMCQ(btn, answer, cardId) {
  const card = document.getElementById(cardId);
  if (card.classList.contains('correct') || card.classList.contains('incorrect')) return;
  const picked = btn.textContent.trim();
  const isCorrect = picked.toLowerCase() === answer.toLowerCase();
  card.querySelectorAll('.option-btn').forEach(b => {
    if (b.textContent.trim().toLowerCase() === answer.toLowerCase()) b.classList.add('correct-answer');
    else if (b === btn && !isCorrect) b.classList.add('wrong-answer');
  });
  card.classList.add(isCorrect ? 'correct' : 'incorrect');
  const fb = document.getElementById('fb-' + cardId);
  fb.classList.remove('hidden');
  fb.className = 'feedback-msg ' + (isCorrect ? 'correct' : 'incorrect');
  fb.textContent = isCorrect ? t('correctMsg') : `${t('incorrectAns')} ${answer}`;
}

function checkFill(id, answer) {
  const inp = document.getElementById('inp-' + id);
  const card = document.getElementById(id);
  if (card.classList.contains('correct') || card.classList.contains('incorrect')) return;
  const isCorrect = inp.value.trim().toLowerCase() === answer.toLowerCase();
  card.classList.add(isCorrect ? 'correct' : 'incorrect');
  const fb = document.getElementById('fb-' + id);
  fb.classList.remove('hidden');
  fb.className = 'feedback-msg ' + (isCorrect ? 'correct' : 'incorrect');
  fb.textContent = isCorrect ? t('correctMsg') : `${t('correctAns')} ${answer}`;
}

// ── Quizzes ──
async function createQuiz() {
  const title = document.getElementById('quiz-title').value || 'Quiz';
  const chapterId = document.getElementById('quiz-chapter-select').value || null;
  const count = parseInt(document.getElementById('quiz-count').value) || 10;
  const data = await api('/quiz/create', { method: 'POST', body: { course_id: courseId, chapter_id: chapterId, title, count } });
  alert('Quiz created with ' + data.question_count + ' questions!');
  loadQuizList();
}

async function loadQuizList() {
  const quizzes = await api('/quizzes?course_id=' + courseId);
  const container = currentUser.role === 'lecturer' ? document.getElementById('quiz-list') : document.getElementById('student-quiz-list');
  container.innerHTML = quizzes.length === 0 ? '<p style="color:var(--text-muted);padding:20px">No quizzes yet. Create one above.</p>'
    : quizzes.map(q => `<div class="card" style="cursor:pointer" onclick="${currentUser.role==='student' ? `takeQuiz('${q.id}')` : ''}"><div class="card-body flex-between"><div><strong>${q.title}</strong><div style="font-size:13px;color:var(--text-muted);margin-top:4px">Created: ${new Date(q.created_at).toLocaleDateString()}</div></div><span class="btn btn-outline btn-sm">${currentUser.role==='student'?'Take Quiz':'View'}</span></div></div>`).join('');
}

async function takeQuiz(quizId) {
  const data = await api('/quiz/take?quiz_id=' + quizId);
  if (!data.questions || data.questions.length === 0) return alert('No questions found');
  const area = document.getElementById('quiz-taking-area');
  area.classList.remove('hidden');
  area.dataset.quizId = quizId;
  area.dataset.questions = JSON.stringify(data.questions);
  area.dataset.current = '0';
  area.dataset.answers = '{}';
  showQuizQuestion(area);
}

function showQuizQuestion(area) {
  const qs = JSON.parse(area.dataset.questions);
  const idx = parseInt(area.dataset.current);
  if (idx >= qs.length) return submitQuizAnswers(area);
  const q = qs[idx];
  area.innerHTML = `<div class="quiz-header"><span class="quiz-progress-text">Question ${idx+1} of ${qs.length}</span><div class="progress-bar" style="width:200px"><div class="progress-fill" style="width:${((idx+1)/qs.length)*100}%;background:var(--accent)"></div></div></div>`;
  if (q.type === 'mcq') {
    const opts = (q.distractors||[]).concat([q.answer]);
    opts.sort(() => Math.random()-0.5);
    area.innerHTML += `<div class="activity-card"><div class="activity-type-label">Question ${idx+1}</div><div class="activity-prompt">${q.prompt}</div><div class="options-grid">${opts.map(o => `<button class="option-btn" onclick="quizAnswer(this,'${esc(q.id)}','${esc(o)}')">${o}</button>`).join('')}</div></div>`;
  } else {
    area.innerHTML += `<div class="activity-card"><div class="activity-type-label">Question ${idx+1}</div><div class="activity-prompt">${q.prompt}</div><input class="fill-blank-input" id="quiz-fill-inp" placeholder="Your answer..." style="width:100%"><button class="btn btn-primary mt-16" onclick="quizAnswer(null,'${esc(q.id)}',document.getElementById('quiz-fill-inp').value)">${t('submit')}</button></div>`;
  }
}

function quizAnswer(btn, qid, answer) {
  const area = document.getElementById('quiz-taking-area');
  const answers = JSON.parse(area.dataset.answers);
  answers[qid] = answer;
  area.dataset.answers = JSON.stringify(answers);
  area.dataset.current = String(parseInt(area.dataset.current) + 1);
  if (btn) { btn.classList.add('selected'); setTimeout(() => showQuizQuestion(area), 300); }
  else showQuizQuestion(area);
}

async function submitQuizAnswers(area) {
  const result = await api('/quiz/submit', { method: 'POST', body: {
    quiz_id: area.dataset.quizId, student_id: currentUser.id, answers: JSON.parse(area.dataset.answers)
  }});
  const pct = Math.round(result.average * 100);
  area.innerHTML = `<div class="quiz-result-card"><div class="quiz-score-label">${t('yourScore')}</div><div class="quiz-score-big" style="color:${masteryColor(result.average)}">${pct}%</div><p style="color:var(--text-secondary);margin-bottom:24px">${result.question_count} ${t('questions')} · ${result.total_score.toFixed(1)} ${t('correct')}</p>${(result.results||[]).map(r => `<div style="text-align:left;padding:10px 16px;border-radius:8px;margin-bottom:6px;background:${r.score>=0.8?'var(--success-bg)':'var(--danger-bg)'};font-size:14px"><strong>${r.score>=0.8?'✓':'✗'}</strong> ${r.feedback}</div>`).join('')}<button class="btn btn-primary mt-24" onclick="document.getElementById('quiz-taking-area').classList.add('hidden')">${t('done')}</button></div>`;
}

// ── Student Roster ──
async function loadStudentRoster() {
  const students = await api('/students?course_id=' + courseId);
  document.getElementById('student-roster').innerHTML = students.map(s => {
    const pct = Math.round(s.avg_mastery * 100);
    return `<div class="student-card" onclick="showStudentDetail('${s.id}','${esc(s.name)}')"><div class="student-name">${s.name}</div><div class="student-mastery-bar"><div class="student-mastery-fill" style="width:${pct}%;background:${masteryColor(s.avg_mastery)}"></div></div><div class="student-meta-row"><span>Mastery: ${pct}%</span><span>${s.total_responses} responses</span></div></div>`;
  }).join('');
}

async function showStudentDetail(sid, name) {
  const data = await api('/student/progress?student_id=' + sid);
  const modal = document.getElementById('student-detail-modal');
  modal.classList.remove('hidden');
  document.getElementById('student-detail-body').innerHTML = `<h2 style="margin-bottom:20px">${name}</h2><h3 style="margin-bottom:16px">Topic Mastery</h3>${(data.masteries||[]).map(m => {
    const pct = Math.round(m.score*100);
    return `<div class="progress-item"><div class="progress-label"><span>${m.title}</span><span>${pct}%</span></div><div class="progress-bar"><div class="progress-fill" style="width:${pct}%;background:${masteryColor(m.score)}"></div></div></div>`;
  }).join('')}<h3 style="margin:24px 0 16px">Recent Activity</h3>${(data.recent_responses||[]).slice(0,10).map(r => `<div style="padding:8px 0;border-bottom:1px solid var(--border);font-size:14px"><span style="color:${r.score>=0.8?'var(--success)':'var(--danger)'};font-weight:600">${Math.round(r.score*100)}%</span> — ${r.prompt?.substring(0,60)||'Question'}</div>`).join('')}`;
}

// ── Reports ──
async function generateReport() {
  document.getElementById('report-content').innerHTML = '<p style="color:var(--text-muted)">Generating report...</p>';
  const r = await api('/report/generate', { method: 'POST', body: { course_id: courseId } });
  const s = r.summary || {};
  document.getElementById('report-content').innerHTML = `
    <div class="stats-grid" style="margin-bottom:28px">
      <div class="stat-card"><div class="stat-label">Class Size</div><div class="stat-value accent">${s.total_students}</div></div>
      <div class="stat-card"><div class="stat-label">Active</div><div class="stat-value success">${s.active_students}</div></div>
      <div class="stat-card"><div class="stat-label">Avg Mastery</div><div class="stat-value ${masteryClass(s.class_avg_mastery)}">${Math.round(s.class_avg_mastery*100)}%</div></div>
      <div class="stat-card"><div class="stat-label">At Risk</div><div class="stat-value ${s.at_risk_count?'danger':'success'}">${s.at_risk_count}</div></div>
    </div>
    <div class="report-section"><h3>⚠️ At-Risk Students</h3>${(r.at_risk_students||[]).map(st => `<div class="risk-item"><div><span class="risk-name">${st.name}</span><span style="margin-left:12px;font-size:13px;color:var(--text-muted)">${st.weak_topics?.join(', ')||'—'}</span></div><div class="risk-badges">${st.flags.map(f => `<span class="risk-badge warning">${f.replace(/_/g,' ')}</span>`).join('')}<span class="risk-badge ${st.overall_mastery<0.4?'critical':'warning'}">${Math.round(st.overall_mastery*100)}%</span></div></div>`).join('')||'<p style="color:var(--text-muted)">None 🎉</p>'}</div>
    <div class="report-section"><h3>📊 Topic Difficulty Ranking</h3>${Object.entries(r.topic_difficulty||{}).map(([n,v]) => `<div class="progress-item"><div class="progress-label"><span>${n}</span><span>${Math.round(v*100)}%</span></div><div class="progress-bar"><div class="progress-fill" style="width:${v*100}%;background:${masteryColor(v)}"></div></div></div>`).join('')}</div>
    <div class="report-section"><h3>🔴 Topics Needing Review</h3>${(r.review_topics||[]).map(t => `<div class="risk-item"><span class="risk-name">${t.topic}</span><span class="risk-badge critical">${Math.round(t.avg_mastery*100)}% avg</span></div>`).join('')||'<p style="color:var(--text-muted)">All topics above threshold</p>'}</div>
    <div class="report-section"><h3>🌟 Top Performers</h3>${(r.top_performers||[]).map(st => `<div class="risk-item"><span class="risk-name">${st.name}</span><span class="risk-badge" style="background:var(--success-bg);color:var(--success)">${Math.round(st.overall_mastery*100)}%</span></div>`).join('')||'—'}</div>`;
}

// ── Student Init ──
async function initStudent() {
  document.getElementById('student-nav-username').textContent = currentUser.name;
  document.getElementById('student-greeting').textContent = '¡Hola, ' + currentUser.name + '!';
  loadStudentHome();
  loadStudentPractice();
  loadQuizList();
  loadStudentProgress();
}

async function loadStudentHome() {
  const progress = await api('/student/progress?student_id=' + currentUser.id);
  const masteries = progress.masteries || [];
  const avg = masteries.length ? masteries.reduce((a,m) => a + m.score, 0) / masteries.length : 0;
  const strong = masteries.filter(m => m.score >= 0.75).length;
  const weak = masteries.filter(m => m.score < 0.4).length;

  document.getElementById('student-stats').innerHTML = `
    <div class="stat-card"><div class="stat-label">${t('overallMastery')}</div><div class="stat-value ${masteryClass(avg)}">${Math.round(avg*100)}%</div></div>
    <div class="stat-card"><div class="stat-label">${t('strongTopics')}</div><div class="stat-value success">${strong}</div></div>
    <div class="stat-card"><div class="stat-label">${t('needsWork')}</div><div class="stat-value ${weak>0?'danger':'success'}">${weak}</div></div>
    <div class="stat-card"><div class="stat-label">${t('topicsStudied')}</div><div class="stat-value accent">${masteries.length}</div></div>`;

  document.getElementById('student-current-chapter').innerHTML = curriculum.length ? `<h4 style="margin-bottom:12px">Unit ${curriculum[0].number}: ${curriculum[0].title}</h4>${(curriculum[0].topics||[]).map(t => `<div class="topic-item"><div class="topic-info"><span class="topic-type-badge ${t.type}">${t.type}</span><span class="topic-name">${t.title}</span></div></div>`).join('')}` : '';
}

function loadStudentPractice() {
  document.getElementById('practice-topics').innerHTML = curriculum.map(ch => (ch.topics||[]).map(t =>
    `<div class="topic-practice-card" onclick="startPractice('${t.id}','${esc(t.title)}')"><div class="topic-type-badge ${t.type}" style="margin-bottom:8px">${t.type}</div><div style="font-weight:600;margin-bottom:4px">${t.title}</div><div style="font-size:13px;color:var(--text-muted)">Unit ${ch.number} · ${t.difficulty}</div></div>`
  ).join('')).join('');
}

async function startPractice(topicId, title) {
  const data = await api('/activity?topic_id=' + topicId);
  const area = document.getElementById('practice-area');
  area.classList.remove('hidden');
  area.innerHTML = `<div class="page-header" style="margin-top:24px"><h2>${t('practice')}: ${title}</h2><button class="btn btn-outline btn-sm" onclick="this.closest('#practice-area').classList.add('hidden')">${t('close')}</button></div>` +
    (data.activities||[]).map((a, i) => renderActivityCard(a, i, 'prac')).join('');
  area.scrollIntoView({ behavior: 'smooth' });
}

async function loadStudentProgress() {
  const data = await api('/student/progress?student_id=' + currentUser.id);
  document.getElementById('progress-chart').innerHTML = (data.masteries||[]).map(m => {
    const pct = Math.round(m.score * 100);
    return `<div class="progress-item"><div class="progress-label"><span>${m.title} <span class="topic-type-badge ${m.type}" style="margin-left:8px">${m.type}</span></span><span>${pct}%</span></div><div class="progress-bar"><div class="progress-fill" style="width:${pct}%;background:${masteryColor(m.score)}"></div></div></div>`;
  }).join('') || '<p style="color:var(--text-muted)">Complete some activities to see your progress!</p>';
}
