// ── State & i18n ──
let currentUser = null;
let courseId = null;
let curriculum = [];
let currentLang = 'en';

const i18n = {
  en: {
    langBtn: '🌐 EN / TR', signInTab: 'Sign In', registerTab: 'Register', welcomeBack: 'Welcome back', signInHint: 'Sign in to continue', emailLabel: 'Email', passwordLabel: 'Password', signInBtn: 'Sign In', joinClass: 'Join the Class', registerHint: 'Create a student account', nameLabel: 'Full Name', registerBtn: 'Create Account', lecturerAccess: 'Lecturer Access', signOut: 'Sign Out', home: 'Home', practice: 'Practice', quizzes: 'Quizzes', myProgress: 'My Progress', keepUp: 'Keep up the great work!', overallMastery: 'Overall Mastery', strongTopics: 'Strong Topics', needsWork: 'Needs Work', topicsStudied: 'Topics Studied', currentChapter: 'Current Chapter', selectPractice: 'Select a topic to practice', availableQuizzes: 'Available quizzes', trackMastery: 'Track your mastery across topics', noQuizzes: 'No quizzes yet.', takeQuiz: 'Take Quiz', view: 'View', close: 'Close', done: 'Done', submit: 'Submit', check: 'Check', yourScore: 'Your Score', questions: 'questions', correct: 'correct', incorrectAns: 'Incorrect. The answer is:', correctAns: 'The correct answer is:', correctMsg: '¡Correcto! ✓', rememberMe: 'Remember Me', takeQuizBtn: 'Take Quiz', viewBtn: 'View',
    Overview: 'Overview', Curriculum: 'Curriculum', Activities: 'Activities', Students: 'Students', Reports: 'Reports', Dashboard: 'Dashboard', 'Class Mastery': 'Class Mastery', 'At Risk': 'At Risk', 'Top Performers': 'Top Performers', '⚠️ At-Risk Students': '⚠️ At-Risk Students', '📊 Topic Difficulty': '📊 Topic Difficulty', 'active this week': 'active this week', 'Average across all topics': 'Average across all topics', 'Students needing attention': 'Students needing attention', 'Mastery above 80%': 'Mastery above 80%', 'No at-risk students 🎉': 'No at-risk students 🎉', mastery: 'mastery',
    'In-Class Activities': 'In-Class Activities', 'Generate and launch live activities': 'Generate and launch live activities', '🚀 Launch Activity': '🚀 Launch Activity', 'Select Chapter & Topic': 'Select Chapter & Topic', 'Generate Activity': 'Generate Activity', 'Quiz Management': 'Quiz Management', 'Create and manage quizzes': 'Create and manage quizzes', '➕ Create New Quiz': '➕ Create New Quiz', 'Quiz Title': 'Quiz Title', 'Chapter': 'Chapter', 'All chapters': 'All chapters', 'Questions': 'Questions', 'Create Quiz': 'Create Quiz', 'Student Roster': 'Student Roster', 'Monitor individual student progress': 'Monitor individual student progress', 'Weekly Report': 'Weekly Report', 'AI-generated class performance analysis': 'AI-generated class performance analysis', '🔄 Generate Report': '🔄 Generate Report', completed: 'Completed', Assignments: 'Assignments', 'Assignment Management': 'Assignment Management', 'Assign homework to your students': 'Assign homework to your students', '➕ Create New Assignment': '➕ Create New Assignment', 'Assignment Title': 'Assignment Title', 'Create Assignment': 'Create Assignment', 'Your homework tasks': 'Your homework tasks', 'My Stats': 'My Stats'
  },
  tr: {
    langBtn: '🌐 TR / EN', signInTab: 'Giriş Yap', registerTab: 'Kayıt Ol', welcomeBack: 'Tekrar Hoş Geldin', signInHint: 'Devam etmek için giriş yapın', emailLabel: 'E-posta', passwordLabel: 'Şifre', signInBtn: 'Giriş Yap', joinClass: 'Sınıfa Katıl', registerHint: 'Öğrenci hesabı oluştur', nameLabel: 'Ad Soyad', registerBtn: 'Hesap Oluştur', lecturerAccess: 'Öğretmen Girişi', signOut: 'Çıkış Yap', home: 'Ana Sayfa', practice: 'Alıştırma', quizzes: 'Sınavlar', myProgress: 'Gelişimim', keepUp: 'Harika gidiyorsun, devam et!', overallMastery: 'Genel Başarı', strongTopics: 'İyi Olduğum Konular', needsWork: 'Eksiğim Olan Konular', topicsStudied: 'Çalışılan Konular', currentChapter: 'Mevcut Ünite', selectPractice: 'Alıştırma yapmak için bir konu seçin', availableQuizzes: 'Mevcut Sınavlar', trackMastery: 'Konulardaki başarı durumunuzu takip edin', noQuizzes: 'Henüz sınav yok.', takeQuiz: 'Sınava Başla', view: 'Görüntüle', close: 'Kapat', done: 'Bitti', submit: 'Gönder', check: 'Kontrol Et', yourScore: 'Puanınız', questions: 'soru', correct: 'doğru', incorrectAns: 'Yanlış. Doğru cevap:', correctAns: 'Doğru cevap:', correctMsg: 'Doğru! ✓', rememberMe: 'Beni Hatırla', takeQuizBtn: 'Sınava Başla', viewBtn: 'Görüntüle',
    Overview: 'Genel Bakış', Curriculum: 'Müfredat', Activities: 'Etkinlikler', Students: 'Öğrenciler', Reports: 'Raporlar', Dashboard: 'Kontrol Paneli', 'Class Mastery': 'Sınıf Başarısı', 'At Risk': 'Riskli', 'Top Performers': 'En İyiler', '⚠️ At-Risk Students': '⚠️ Riskli Öğrenciler', '📊 Topic Difficulty': '📊 Konu Zorluğu', 'active this week': 'bu hafta aktif', 'Average across all topics': 'Tüm konularda ortalama', 'Students needing attention': 'Dikkat gerektiren öğrenciler', 'Mastery above 80%': '%80 üzeri başarı', 'No at-risk students 🎉': 'Riskli öğrenci yok 🎉', mastery: 'başarı',
    'In-Class Activities': 'Sınıf İçi Etkinlikler', 'Generate and launch live activities': 'Canlı etkinlikler oluştur ve başlat', '🚀 Launch Activity': '🚀 Etkinlik Başlat', 'Select Chapter & Topic': 'Ünite ve Konu Seç', 'Generate Activity': 'Etkinlik Oluştur', 'Quiz Management': 'Sınav Yönetimi', 'Create and manage quizzes': 'Sınav oluştur ve yönet', '➕ Create New Quiz': '➕ Yeni Sınav Oluştur', 'Quiz Title': 'Sınav Başlığı', 'Chapter': 'Ünite', 'All chapters': 'Tüm üniteler', 'Questions': 'Soru Sayısı', 'Create Quiz': 'Sınav Oluştur', 'Student Roster': 'Öğrenci Listesi', 'Monitor individual student progress': 'Bireysel öğrenci gelişimini izle', 'Weekly Report': 'Haftalık Rapor', 'AI-generated class performance analysis': 'Yapay zeka destekli sınıf performans analizi', '🔄 Generate Report': '🔄 Rapor Oluştur', completed: 'Tamamlandı', Assignments: 'Ödevler', 'Assignment Management': 'Ödev Yönetimi', 'Assign homework to your students': 'Öğrencilerinize ödev atayın', '➕ Create New Assignment': '➕ Yeni Ödev Oluştur', 'Assignment Title': 'Ödev Başlığı', 'Create Assignment': 'Ödev Oluştur', 'Your homework tasks': 'Ödev görevleriniz', 'My Stats': 'İstatistiklerim'
  }
};

function t(key) { return i18n[currentLang][key] || key; }

function toggleLanguage() {
  currentLang = currentLang === 'en' ? 'tr' : 'en';
  document.getElementById('lang-btn').textContent = t('langBtn');
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

const vocabTR = {
  "hello": "merhaba", "good morning": "günaydın", "good afternoon": "iyi günler", "good night": "iyi geceler",
  "What's your name?": "Adın ne?", "My name is...": "Benim adım...", "Where are you from?": "Nerelisin?",
  "I'm from...": "Ben ...'lıyım", "nice to meet you": "memnun oldum", "goodbye": "hoşça kal", "see you later": "görüşürüz",
  "please": "lütfen", "thank you": "teşekkür ederim", "Spanish": "İspanyol", "Mexican": "Meksikalı",
  "American": "Amerikalı", "French": "Fransız", "German": "Alman", "Italian": "İtalyan", "Brazilian": "Brezilyalı",
  "Chinese": "Çinli", "Japanese": "Japon", "English/British": "İngiliz", "Argentine": "Arjantinli", "Colombian": "Kolombiyalı",
  "Multiple Choice": "Çoktan Seçmeli", "Fill in the Blank": "Boşluk Doldurma", "Arrange the dialogue in the correct order:": "Diyaloğu doğru sıraya koyun:"
};

function translatePrompt(text) {
  if (!text) return '';
  if (currentLang !== 'tr') return text;
  let t = text;
  t = t.replace(/What does '(.*)' mean\?/, "'$1' ne anlama gelir?");
  let match = t.match(/How do you say '(.*)' in Spanish\?/);
  if (match) {
    const wordTR = vocabTR[match[1]] || match[1];
    t = `İspanyolca'da '${wordTR}' nasıl denir?`;
  }
  return vocabTR[t] || t;
}

function translateOption(text) {
  if (currentLang !== 'tr') return text;
  return vocabTR[text] || text;
}

async function api(path, opts = {}) {
  const res = await fetch('/api' + path, {
    method: opts.method || 'GET',
    headers: opts.body ? { 'Content-Type': 'application/json' } : {},
    body: opts.body ? JSON.stringify(opts.body) : undefined
  });
  return res.json();
}

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

async function completeLogin(user) {
  currentUser = user;
  const remember = document.getElementById('login-remember') ? document.getElementById('login-remember').checked : true;
  if (remember) localStorage.setItem('aula_user', JSON.stringify(user));
  else sessionStorage.setItem('aula_user', JSON.stringify(user));
  localStorage.setItem('aula_lang', currentLang);
  const courses = await api('/courses');
  if (courses.length) courseId = courses[0].id;
  curriculum = await api('/curriculum?course_id=' + courseId);
  showScreen(currentUser.role === 'lecturer' ? 'lecturer-dashboard' : 'student-dashboard');
  if (currentUser.role === 'lecturer') initLecturer(); else initStudent();
}

async function handleRegister(e) {
  e.preventDefault();
  const data = await api('/register', { method: 'POST', body: {
    name: document.getElementById('register-name').value,
    email: document.getElementById('register-email').value,
    password: document.getElementById('register-password').value
  }});
  if (data.error) { document.getElementById('register-error').textContent = data.error; document.getElementById('register-error').classList.remove('hidden'); return false; }
  await completeLogin(data.user);
  return false;
}

async function handleLogin(e) {
  e.preventDefault();
  const data = await api('/login', { method: 'POST', body: {
    email: document.getElementById('login-email').value,
    password: document.getElementById('login-password').value
  }});
  if (data.error) { document.getElementById('login-error').textContent = data.error; document.getElementById('login-error').classList.remove('hidden'); return false; }
  await completeLogin(data.user);
  return false;
}

function logout() { 
  currentUser = null; 
  localStorage.removeItem('aula_user');
  sessionStorage.removeItem('aula_user');
  showScreen('login-screen'); 
}

window.addEventListener('DOMContentLoaded', () => {
  const savedLang = localStorage.getItem('aula_lang');
  if (savedLang && savedLang !== currentLang) toggleLanguage();
  const savedUser = localStorage.getItem('aula_user') || sessionStorage.getItem('aula_user');
  if (savedUser) {
    try { completeLogin(JSON.parse(savedUser)).catch(() => showScreen('login-screen')); }
    catch(e) { showScreen('login-screen'); }
  } else showScreen('login-screen');
});

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

function masteryColor(s) { return s >= 0.75 ? 'var(--success)' : s >= 0.4 ? 'var(--warning)' : 'var(--danger)'; }
function masteryClass(s) { return s >= 0.75 ? 'success' : s >= 0.4 ? 'warning' : 'danger'; }

async function initLecturer() {
  document.getElementById('nav-username').textContent = currentUser.name;
  document.getElementById('overview-greeting').textContent = t('welcomeBack') + ', ' + currentUser.name.split(' ').pop();
  await loadOverview();
  loadCurriculum();
  populateSelects();
  loadQuizList();
  loadAssignmentList();
  loadStudentRoster();
}

async function loadOverview() {
  const report = await api('/report?course_id=' + courseId);
  const s = report.summary || {};
  document.getElementById('overview-stats').innerHTML = `
    <div class="stat-card"><div class="stat-label">${t('Students')}</div><div class="stat-value accent">${s.total_students||0}</div><div class="stat-sub">${s.active_students||0} ${t('active this week')}</div></div>
    <div class="stat-card"><div class="stat-label">${t('Class Mastery')}</div><div class="stat-value ${masteryClass(s.class_avg_mastery)}">${Math.round((s.class_avg_mastery||0)*100)}%</div><div class="stat-sub">${t('Average across all topics')}</div></div>
    <div class="stat-card"><div class="stat-label">${t('At Risk')}</div><div class="stat-value ${s.at_risk_count > 0 ? 'danger' : 'success'}">${s.at_risk_count||0}</div><div class="stat-sub">${t('Students needing attention')}</div></div>
    <div class="stat-card"><div class="stat-label">${t('Top Performers')}</div><div class="stat-value success">${s.top_performer_count||0}</div><div class="stat-sub">${t('Mastery above 80%')}</div></div>`;
  const atRisk = report.at_risk_students || [];
  document.getElementById('at-risk-list').innerHTML = atRisk.length === 0 ? `<p style="color:var(--text-muted)">${t('No at-risk students 🎉')}</p>`
    : atRisk.map(s => `<div class="risk-item"><div><span class="risk-name">${s.name}</span></div><div class="risk-badges"><span class="risk-badge ${s.overall_mastery < 0.4 ? 'critical' : 'warning'}">${Math.round(s.overall_mastery*100)}% ${t('mastery')}</span>${s.flags.map(f => `<span class="risk-badge low">${f.replace(/_/g,' ')}</span>`).join('')}</div></div>`).join('');
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
      <div class="chapter-topics">${(ch.topics||[]).map(t => `<div class="topic-item"><div class="topic-info"><span class="topic-type-badge ${t.type}">${t.type}</span><span class="topic-name">${t.title}</span></div><div class="topic-meta"><span>${t.difficulty}</span><span>${t.question_count||0} questions</span></div></div>`).join('')}</div>
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
  const as = document.getElementById('assignment-chapter-select');
  if (as) as.innerHTML = '<option value="">All chapters</option>' + chapterOpts;
}

async function launchActivity() {
  const topicId = document.getElementById('activity-topic-select').value;
  if (!topicId) return alert('Please select a topic');
  const data = await api('/activity?topic_id=' + topicId);
  const preview = document.getElementById('activity-preview');
  preview.classList.remove('hidden');
  preview.innerHTML = '<h2 style="margin-bottom:20px">📋 Generated Activities — ' + (data.topic?.title||'') + '</h2>' + (data.activities||[]).map((a, i) => renderActivityCard(a, i, 'preview')).join('');
}

function renderActivityCard(a, idx, ctx) {
  const p = translatePrompt(a.prompt);
  if (a.type === 'mcq') return `<div class="activity-card" id="${ctx}-${idx}"><div class="activity-type-label">${translateOption('Multiple Choice')}</div><div class="activity-prompt">${p}</div><div class="options-grid">${(a.options||[]).map(o => `<button class="option-btn" data-original="${esc(o)}" onclick="checkMCQ(this,'${esc(a.answer)}','${ctx}-${idx}','${esc(a.id)}')">${translateOption(o)}</button>`).join('')}</div><div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
  if (a.type === 'fill_blank') return `<div class="activity-card" id="${ctx}-${idx}"><div class="activity-type-label">${translateOption('Fill in the Blank')}</div><div class="activity-prompt">${p}</div><div><input class="fill-blank-input" id="inp-${ctx}-${idx}" placeholder="Your answer..."><button class="btn btn-primary btn-sm" style="margin-left:8px" onclick="checkFill('${ctx}-${idx}','${esc(a.answer)}','${esc(a.id)}')">${t('check')}</button></div>${a.hint ? `<div style="margin-top:8px;font-size:13px;color:var(--text-muted)">💡 ${a.hint}</div>` : ''}<div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
  return '';
}

function esc(s) { return (s||'').replace(/'/g, "\\'").replace(/"/g, '&quot;'); }

async function checkMCQ(btn, answer, cardId, qid) {
  const card = document.getElementById(cardId);
  if (card.classList.contains('correct') || card.classList.contains('incorrect')) return;
  const picked = btn.dataset.original || btn.textContent.trim();
  const isCorrect = picked.toLowerCase() === answer.toLowerCase();
  card.querySelectorAll('.option-btn').forEach(b => {
    if ((b.dataset.original || b.textContent.trim()).toLowerCase() === answer.toLowerCase()) b.classList.add('correct-answer');
    else if (b === btn && !isCorrect) b.classList.add('wrong-answer');
  });
  card.classList.add(isCorrect ? 'correct' : 'incorrect');
  document.getElementById('fb-' + cardId).classList.remove('hidden');
  document.getElementById('fb-' + cardId).className = 'feedback-msg ' + (isCorrect ? 'correct' : 'incorrect');
  document.getElementById('fb-' + cardId).textContent = isCorrect ? t('correctMsg') : `${t('incorrectAns')} ${answer}`;
  if (cardId.startsWith('prac')) await api('/activity/respond', { method: 'POST', body: { student_id: currentUser.id, question_id: qid, answer: picked, correct_answer: answer, question_type: 'mcq' }});
}

async function checkFill(id, answer, qid) {
  const inp = document.getElementById('inp-' + id);
  const card = document.getElementById(id);
  if (card.classList.contains('correct') || card.classList.contains('incorrect')) return;
  const val = inp.value.trim();
  const isCorrect = val.toLowerCase() === answer.toLowerCase();
  inp.disabled = true;
  card.classList.add(isCorrect ? 'correct' : 'incorrect');
  document.getElementById('fb-' + id).classList.remove('hidden');
  document.getElementById('fb-' + id).className = 'feedback-msg ' + (isCorrect ? 'correct' : 'incorrect');
  document.getElementById('fb-' + id).textContent = isCorrect ? t('correctMsg') : `${t('incorrectAns')} ${answer}`;
  if (id.startsWith('prac')) await api('/activity/respond', { method: 'POST', body: { student_id: currentUser.id, question_id: qid, answer: val, correct_answer: answer, question_type: 'fill_blank' }});
}

async function createQuiz() {
  const title = document.getElementById('quiz-title').value || 'Quiz';
  const chapterId = document.getElementById('quiz-chapter-select').value || null;
  const count = parseInt(document.getElementById('quiz-count').value) || 10;
  await api('/quiz/create', { method: 'POST', body: { course_id: courseId, chapter_id: chapterId, title, count } });
  loadQuizList();
}

async function loadQuizList() {
  const quizzes = await api(`/quizzes?course_id=${courseId}&student_id=${currentUser.id}`);
  const container = currentUser.role === 'lecturer' ? document.getElementById('quiz-list') : document.getElementById('student-quiz-list');
  if (!container) return;
  container.innerHTML = quizzes.length === 0 ? `<p style="color:var(--text-muted);padding:20px">${t('noQuizzes')}</p>`
    : quizzes.map(q => {
        const isCompleted = q.is_completed && currentUser.role !== 'lecturer';
        return `<div class="card" style="cursor:${isCompleted?'default':'pointer'};opacity:${isCompleted?'0.6':'1'}" onclick="${currentUser.role==='lecturer'?`viewQuiz('${q.id}','${esc(q.title)}')` : (isCompleted?'':`takeQuiz('${q.id}')`)}"><div class="card-body flex-between"><div><strong>${q.title}</strong><div style="font-size:13px;color:var(--text-muted);margin-top:4px">Created: ${new Date(q.created_at).toLocaleDateString()} ${isCompleted?` · <span style="color:var(--success)">✓ ${t('completed')}</span>`:''}</div></div><span class="btn btn-sm ${isCompleted?'btn-ghost':'btn-outline'}">${currentUser.role==='lecturer'?t('viewBtn'):(isCompleted?t('completed'):t('takeQuizBtn'))}</span></div></div>`;
      }).join('');
}

async function viewQuiz(quizId, title) {
  const data = await api('/quiz/take?quiz_id=' + quizId);
  const modal = document.getElementById('student-detail-modal');
  modal.classList.remove('hidden');
  document.getElementById('student-detail-body').innerHTML = `
    <h2 style="margin-bottom:20px">${title}</h2>
    <div style="color:var(--text-secondary); margin-bottom:16px">${data.questions.length} questions</div>
    ${data.questions.map((q, i) => `
      <div style="margin-bottom:12px; padding:12px; background:var(--bg-input); border:1px solid var(--border); border-radius:var(--radius-sm)">
        <div style="font-weight:600; margin-bottom:8px">Q${i+1}: ${q.prompt}</div>
        <div style="font-size:14px">Answer: <strong style="color:var(--success)">${q.answer}</strong></div>
      </div>
    `).join('')}
  `;
}

async function takeQuiz(quizId) {
  const data = await api('/quiz/take?quiz_id=' + quizId);
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
  area.innerHTML = `<div class="quiz-header"><span class="quiz-progress-text">Q${idx+1}/${qs.length}</span></div><div class="activity-card"><div class="activity-prompt">${translatePrompt(q.prompt)}</div>` + 
    (q.type==='mcq' ? `<div class="options-grid">${((q.distractors||[]).concat([q.answer]).sort(()=>Math.random()-0.5)).map(o=>`<button class="option-btn" onclick="quizAnswer(this,'${esc(q.id)}','${esc(o)}')">${translateOption(o)}</button>`).join('')}</div>` : `<input class="fill-blank-input" id="q-inp"><button class="btn btn-primary mt-16" onclick="quizAnswer(null,'${esc(q.id)}',document.getElementById('q-inp').value)">Submit</button>`) + `</div>`;
}

function quizAnswer(btn, qid, ans) {
  const area = document.getElementById('quiz-taking-area');
  const answers = JSON.parse(area.dataset.answers);
  answers[qid] = ans;
  area.dataset.answers = JSON.stringify(answers);
  area.dataset.current = String(parseInt(area.dataset.current) + 1);
  showQuizQuestion(area);
}

async function submitQuizAnswers(area) {
  await api('/quiz/submit', { method: 'POST', body: { quiz_id: area.dataset.quizId, student_id: currentUser.id, answers: JSON.parse(area.dataset.answers) }});
  location.reload();
}

async function loadStudentRoster() {
  const students = await api('/students?course_id=' + courseId);
  document.getElementById('student-roster').innerHTML = students.map(s => {
    const pct = Math.round(s.avg_mastery * 100);
    return `<div class="student-card" onclick="showStudentDetail('${s.id}','${esc(s.name)}')"><div class="flex-between" style="margin-bottom:8px"><div class="student-name" style="margin-bottom:0">${s.name}</div><button class="btn btn-sm" style="background:var(--danger-bg);color:var(--danger);border:1px solid var(--danger);padding:4px 8px" onclick="event.stopPropagation();deleteStudent('${s.id}','${esc(s.name)}')">Kick</button></div><div class="student-mastery-bar"><div class="student-mastery-fill" style="width:${pct}%;background:${masteryColor(s.avg_mastery)}"></div></div><div class="student-meta-row"><span>Mastery: ${pct}%</span><span>${s.total_responses} responses</span></div></div>`;
  }).join('');
}

async function deleteStudent(sid, name) {
  if (confirm(`Are you sure you want to kick ${name} from the class? This cannot be undone.`)) {
    const res = await api('/student/delete', { method: 'POST', body: { student_id: sid } });
    if (!res.error) loadStudentRoster();
  }
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

async function generateReport() {
  document.getElementById('report-content').innerHTML = '<p style="color:var(--text-muted)">Generating report...</p>';
  const r = await api('/report/generate', { method: 'POST', body: { course_id: courseId } });
  const today = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  document.getElementById('report-content').innerHTML = `
    <div style="max-width: 800px; margin: 0 auto; background: var(--bg-card); border-radius: 8px; overflow: hidden; border: 1px solid var(--border);">
      <div style="background: var(--gradient-1); padding: 30px; text-align: center; color: white;">
        <div style="font-size: 32px; margin-bottom: 10px;">🇪🇸</div>
        <h2 style="margin: 0; font-size: 24px; font-weight: 600;">AulaAI Weekly Digest</h2>
        <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 14px;">${today}</p>
      </div>
      <div style="padding: 40px 30px;">
        <p style="font-size: 16px; line-height: 1.6; margin-top: 0;">Hi Professor,</p>
        <p style="font-size: 16px; line-height: 1.6; color: var(--text-secondary);">Here is your AI-generated weekly performance breakdown for <strong>Spanish 101</strong>.</p>
        <div style="display: flex; gap: 20px; margin: 30px 0; flex-wrap: wrap;">
          <div style="flex: 1; min-width: 120px; background: var(--bg-input); border: 1px solid var(--border); padding: 20px; border-radius: 8px; text-align: center;">
            <div style="font-size: 12px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Class Size</div>
            <div style="font-size: 28px; font-weight: 700; margin-top: 5px;">${r.summary?.total_students||0}</div>
          </div>
          <div style="flex: 1; min-width: 120px; background: var(--bg-input); border: 1px solid var(--border); padding: 20px; border-radius: 8px; text-align: center;">
            <div style="font-size: 12px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Class Mastery</div>
            <div style="font-size: 28px; font-weight: 700; margin-top: 5px;">${Math.round((r.summary?.class_avg_mastery||0)*100)}%</div>
          </div>
          <div style="flex: 1; min-width: 120px; background: var(--danger-bg); border: 1px solid var(--danger); padding: 20px; border-radius: 8px; text-align: center;">
            <div style="font-size: 12px; text-transform: uppercase; color: var(--danger); font-weight: 600;">At Risk</div>
            <div style="font-size: 28px; font-weight: 700; color: var(--danger); margin-top: 5px;">${r.summary?.at_risk_count||0}</div>
          </div>
        </div>
        <h3 style="font-size: 18px; border-bottom: 2px solid var(--border); padding-bottom: 10px; margin-top: 40px;">🤖 AI Insights</h3>
        <p style="font-size: 15px; line-height: 1.6; background: var(--bg-input); padding: 15px; border-left: 4px solid var(--accent); border-radius: 0 8px 8px 0;">
          The class is tracking an average mastery of ${Math.round((r.summary?.class_avg_mastery||0)*100)}%. ${(r.review_topics||[]).length > 0 ? 'We noticed some difficulty with <strong>' + r.review_topics[0].topic + '</strong>. We recommend running a quick live activity.' : 'Great job! No major review topics detected right now.'}
        </p>
        <h3 style="font-size: 18px; border-bottom: 2px solid var(--border); padding-bottom: 10px; margin-top: 40px;">📊 Topics Needing Review</h3>
        <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
          ${(r.review_topics||[]).map(td => '<tr style="border-bottom: 1px solid var(--border);"><td style="padding: 12px 0; font-size: 15px; font-weight: 500;">' + td.topic + '</td><td style="padding: 12px 0; text-align: right;"><span style="background: var(--warning-bg); color: var(--warning); padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">' + Math.round(td.avg_mastery*100) + '% avg</span></td></tr>').join('') || '<tr><td style="padding: 12px 0; color: var(--text-muted);">No challenging topics detected.</td></tr>'}
        </table>
        <h3 style="font-size: 18px; border-bottom: 2px solid var(--border); padding-bottom: 10px; margin-top: 40px;">⚠️ Students Needing Intervention</h3>
        ${(r.at_risk_students||[]).length === 0 ? '<p style="color: var(--success); font-weight: 500;">No at-risk students 🎉</p>' :
          '<table style="width: 100%; border-collapse: collapse; margin-top: 15px;">' + r.at_risk_students.map(rs => '<tr style="border-bottom: 1px solid var(--border);"><td style="padding: 12px 0; font-size: 15px; font-weight: 600;">' + rs.name + '</td><td style="padding: 12px 0; text-align: right; color: var(--danger); font-weight: 600;">' + Math.round(rs.overall_mastery*100) + '% overall</td></tr>').join('') + '</table>'}
        <h3 style="font-size: 18px; border-bottom: 2px solid var(--border); padding-bottom: 10px; margin-top: 40px;">👥 ${currentLang === 'tr' ? 'Bireysel Öğrenci Değerlendirmeleri' : 'Individual Student Evaluations'}</h3>
        <div style="margin-top: 15px; display: flex; flex-direction: column; gap: 15px;">
          ${(r.student_reports||[]).map(sr => {
            const isTr = currentLang === 'tr';
            const evalTexts = {
              'excellent': isTr ? "Mükemmel ilerleme kaydediyor." : "Making excellent progress.",
              'good': isTr ? "Genel performansı iyi durumda." : "General performance is good.",
              'fluctuating': isTr ? "Öğrenme sürecinde dalgalanmalar yaşıyor." : "Experiencing fluctuations.",
              'inactive': isTr ? "Henüz yeterli etkinlik tamamlamamış." : "Has not yet completed enough activities.",
              'critical': isTr ? "Ciddi anlama zorlukları yaşıyor." : "Experiencing severe comprehension difficulties."
            };
            const evalText = evalTexts[sr.eval_code] || (isTr ? 'Veri yetersiz.' : 'Insufficient data.');
            return '<div style="background: var(--bg-secondary); border: 1px solid var(--border); padding: 15px; border-radius: 8px;"><div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;"><strong style="font-size: 15px;">' + esc(sr.name) + '</strong><span style="font-size: 13px; font-weight: 600; padding: 4px 8px; border-radius: 12px; background: ' + (sr.overall_mastery >= 0.75 ? 'var(--success-bg)' : (sr.overall_mastery < 0.5 ? 'var(--danger-bg)' : 'var(--warning-bg)')) + '; color: ' + (sr.overall_mastery >= 0.75 ? 'var(--success)' : (sr.overall_mastery < 0.5 ? 'var(--danger)' : 'var(--warning)')) + ';">' + Math.round(sr.overall_mastery * 100) + '%</span></div><p style="margin: 0; font-size: 14px; color: var(--text-secondary); line-height: 1.5;">' + evalText + '</p></div>';
          }).join('') || '<p style="color:var(--text-muted)">No enrolled students found.</p>'}
        </div>
      </div>
    </div>
  `;
}

async function initStudent() {
  document.getElementById('student-nav-username').textContent = currentUser.name;
  document.getElementById('student-greeting').textContent = '¡Hola, ' + currentUser.name + '!';
  await loadStudentStats();
  loadStudentHome();
  loadStudentPractice();
  loadQuizList();
  loadAssignmentList();
  loadStudentProgress();
}

async function loadStudentStats() {
  const stats = await api('/student/stats?student_id=' + currentUser.id);
  const container = document.getElementById('student-stats');
  if (!container) return;
  container.innerHTML = `<div class="stat-card"><div class="stat-label">Quizzes</div><div class="stat-value accent">${stats.quizzes||0}</div></div><div class="stat-card"><div class="stat-label">Practice</div><div class="stat-value success">${stats.practice||0}</div></div><div class="stat-card"><div class="stat-label">Assignments</div><div class="stat-value warning">${stats.assignments||0}</div></div>`;
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

  document.getElementById('student-current-chapter').innerHTML = curriculum.length ? `<h4 style="margin-bottom:12px">Unit ${curriculum[0].number}: ${curriculum[0].title}</h4>${(curriculum[0].topics||[]).map(tp => `<div class="topic-item"><div class="topic-info"><span class="topic-type-badge ${tp.type}">${tp.type}</span><span class="topic-name">${tp.title}</span></div></div>`).join('')}` : '';
}

function loadStudentPractice() {
  document.getElementById('practice-topics').innerHTML = curriculum.map(ch => (ch.topics||[]).map(tp =>
    `<div class="topic-practice-card" onclick="startPractice('${tp.id}','${esc(tp.title)}')">
      <div class="topic-type-badge ${tp.type}" style="margin-bottom:8px">${tp.type}</div>
      <div style="font-weight:600;margin-bottom:4px">${tp.title}</div>
      <div style="font-size:13px;color:var(--text-muted)">Unit ${ch.number} · ${tp.difficulty}</div>
    </div>`
  ).join('')).join('');
}

async function startPractice(tid, title) {
  const data = await api('/activity?topic_id=' + tid);
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
  }).join('') || `<p style="color:var(--text-muted)">Complete some activities to see your progress!</p>`;
}

async function loadAssignmentList() {
  const assignments = await api(`/assignments?course_id=${courseId}&student_id=${currentUser.id}`);
  const container = currentUser.role==='lecturer' ? document.getElementById('assignment-list') : document.getElementById('student-assignment-list');
  if (!container) return;
  container.innerHTML = assignments.map(a => `<div class="card" onclick="${currentUser.role==='student'&&!a.is_completed?`takeAssignment('${a.id}')`:''}"><div class="card-body flex-between"><div><strong>${a.title}</strong></div><span>${a.is_completed?'Done':'Go'}</span></div></div>`).join('');
}

async function createAssignment() {
  const title = document.getElementById('assignment-title').value;
  const chapterId = document.getElementById('assignment-chapter-select').value;
  const count = document.getElementById('assignment-count').value;
  await api('/assignment/create', { method: 'POST', body: { title, chapter_id: chapterId, count: parseInt(count), course_id: courseId }});
  location.reload();
}

async function takeAssignment(aid) {
  const data = await api('/assignment/take?assignment_id=' + aid);
  const area = document.getElementById('assignment-taking-area');
  area.classList.remove('hidden');
  area.dataset.assignmentId = aid;
  area.dataset.questions = JSON.stringify(data.questions);
  area.dataset.current = '0';
  area.dataset.answers = '{}';
  showAssignmentQuestion(area);
}

function showAssignmentQuestion(area) {
  const qs = JSON.parse(area.dataset.questions), idx = parseInt(area.dataset.current);
  if (idx >= qs.length) return submitAssignment(area);
  const q = qs[idx];
  area.innerHTML = `<h3>Q${idx+1}</h3><p>${translatePrompt(q.prompt)}</p>` + (q.type==='mcq' ? (q.distractors||[]).concat([q.answer]).sort(()=>Math.random()-0.5).map(o=>`<button class="option-btn" onclick="assignmentAnswer('${esc(o)}')">${translateOption(o)}</button>`).join('') : `<input id="as-inp"><button onclick="assignmentAnswer(document.getElementById('as-inp').value)">Sub</button>`);
}

function assignmentAnswer(ans) {
  const area = document.getElementById('assignment-taking-area'), answers = JSON.parse(area.dataset.answers), qs = JSON.parse(area.dataset.questions), idx = parseInt(area.dataset.current);
  answers[qs[idx].id] = ans;
  area.dataset.answers = JSON.stringify(answers);
  area.dataset.current = String(idx + 1);
  showAssignmentQuestion(area);
}

async function submitAssignment(area) {
  await api('/assignment/submit', { method: 'POST', body: { assignment_id: area.dataset.assignmentId, student_id: currentUser.id, answers: JSON.parse(area.dataset.answers) }});
  location.reload();
}
