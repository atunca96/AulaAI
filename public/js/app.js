// ── State & i18n ──
let currentUser = null;
let courseId = null;
let curriculum = [];
let currentLang = 'tr';
let aiStatus = null;
let _lastVersion = -1;
let _syncInterval = null;

// ── Keep Render alive (ping every 10 min) ──
setInterval(() => fetch('/api/courses').catch(() => {}), 10 * 60 * 1000);

// ── Live-sync: poll for data changes every 4 seconds ──
function startLiveSync() {
  if (_syncInterval) clearInterval(_syncInterval);
  _syncInterval = setInterval(async () => {
    if (!currentUser) return;
    try {
      const res = await fetch('/api/version');
      const data = await res.json();
      if (_lastVersion === -1) { _lastVersion = data.version; return; }
      if (data.version !== _lastVersion) {
        _lastVersion = data.version;
        console.log('[LiveSync] Data changed, refreshing...');
        
        // If data changed, ensure we weren't just kicked
        const statusCheck = await api('/user/status?user_id=' + currentUser.id);
        if (statusCheck && statusCheck.error === 'User not found') {
          alert(currentLang === 'tr' ? 'Hesabınız silindi veya oturumunuz kapatıldı.' : 'Your account has been removed or logged out.');
          logout();
          return;
        }

        refreshCurrentView();
      }
    } catch (e) { /* ignore network errors */ }
  }, 4000);
}

function stopLiveSync() {
  if (_syncInterval) { clearInterval(_syncInterval); _syncInterval = null; }
}

function refreshCurrentView() {
  if (!currentUser) return;
  if (document.getElementById('waiting-room-screen').classList.contains('active')) {
    window.location.reload();
    return;
  }
  if (currentUser.role === 'lecturer') {
    loadOverview();
    loadQuizList();
    loadAssignmentList();
    loadStudentRoster();
    api('/messages').then(messages => {
      if (messages && Array.isArray(messages)) {
        const unread = messages.filter(m => !m.is_read && m.sender === 'student').length;
        const badge = document.getElementById('inbox-badge');
        if (unread > 0) {
          badge.style.display = 'flex';
          badge.textContent = unread;
        } else {
          badge.style.display = 'none';
        }
        if (document.getElementById('tab-inbox') && document.getElementById('tab-inbox').classList.contains('active')) {
          if (currentChatStudentId) {
            const titleEl = document.getElementById('inbox-title');
            if (titleEl) {
              const nameText = titleEl.textContent;
              const name = nameText.includes('💬') ? nameText.split('💬 ')[1] : nameText;
              openChat(currentChatStudentId, name);
            }
          } else {
            loadInbox();
          }
        }
      }
    });
  } else {
    loadStudentHome();
    loadQuizList();
    loadAssignmentList();
    loadStudentProgress();
    api(`/messages?student_id=${currentUser.id}`).then(messages => {
      if (messages && Array.isArray(messages)) {
        const unread = messages.filter(m => !m.is_read && m.sender === 'lecturer').length;
        const badge = document.getElementById('message-badge');
        if (unread > 0) {
          badge.style.display = 'flex';
          badge.textContent = unread;
        } else {
          badge.style.display = 'none';
        }
        if (document.getElementById('tab-s-messages') && document.getElementById('tab-s-messages').classList.contains('active')) {
          loadStudentChat();
        }
      }
    });
  }
}

const i18n = {
  en: {
    langBtn: '🌐 TR',
    // Login screen
    signInTab: 'Sign In', registerTab: 'Register', welcomeBack: 'Welcome back', signInHint: 'Sign in to continue', emailLabel: 'Email', passwordLabel: 'Password', signInBtn: 'Sign In', joinClass: 'Join the Class', registerHint: 'Create a student account', nameLabel: 'Full Name', registerBtn: 'Create Account', lecturerAccess: 'Lecturer Access', signOut: 'Sign Out', rememberMe: 'Remember Me',
    'Lecturer Login': 'Lecturer Login', 'Sign in with your email and password': 'Sign in with your email and password',
    'Student Login': 'Student Login', 'Log in with your student number': 'Log in with your student number',
    'Student Number': 'Student Number', '(required)': '(required)',
    'Your Full Name': 'Your Full Name', 'e.g. 2021123456': 'e.g. 2021123456',
    Email: 'Email', Password: 'Password', 'Full Name': 'Full Name',
    'Sign In': 'Sign In', 'Remember Me': 'Remember Me',
    messageTeacher: 'Message Teacher', inbox: 'Inbox', book: 'Book',
    '👩‍🏫 Lecturer': '👩‍🏫 Lecturer', '🎓 Student': '🎓 Student',
    // Student dashboard
    home: 'Home', practice: 'Practice', quizzes: 'Quizzes', myProgress: 'My Progress',
    keepUp: 'Keep up the great work!', overallMastery: 'Overall Mastery', strongTopics: 'Strong Topics', needsWork: 'Needs Work', topicsStudied: 'Topics Studied', currentChapter: 'Current Chapter',
    selectPractice: 'Select a topic to practice', availableQuizzes: 'Available quizzes', trackMastery: 'Track your mastery across topics', noQuizzes: 'No quizzes yet.',
    takeQuiz: 'Take Quiz', view: 'View', close: 'Close', done: 'Done', submit: 'Submit', check: 'Check',
    yourScore: 'Your Score', questions: 'questions', correct: 'correct',
    incorrectAns: 'Incorrect. The answer is:', correctAns: 'The correct answer is:', correctMsg: '¡Correcto! ✓',
    takeQuizBtn: 'Take Quiz', viewBtn: 'View',
    // Lecturer nav & tabs
    Lecturer: 'Lecturer', Student: 'Student',
    Overview: 'Overview', Curriculum: 'Curriculum', Activities: 'Activities', Students: 'Students', Reports: 'Reports', Dashboard: 'Dashboard', Assignments: 'Assignments', Quizzes: 'Quizzes', 'My Stats': 'My Stats',
    // Overview stats
    STUDENTS: 'STUDENTS', 'CLASS MASTERY': 'CLASS MASTERY', 'AT RISK': 'AT RISK', 'TOP PERFORMERS': 'TOP PERFORMERS',
    'Class Mastery': 'Class Mastery', 'At Risk': 'At Risk', 'Top Performers': 'Top Performers',
    '⚠️ At-Risk Students': '⚠️ At-Risk Students', '📊 Topic Difficulty': '📊 Topic Difficulty',
    'active this week': 'active this week', 'Average across all topics': 'Average across all topics',
    'Students needing attention': 'Students needing attention', 'Mastery above 80%': 'Mastery above 80%',
    'No at-risk students 🎉': 'No at-risk students 🎉', mastery: 'mastery',
    'Welcome back,': 'Welcome back,',
    // Data Management
    'Data Management': 'Data Management', 'Erase All Data': 'Erase All Data',
    'Removes all students, quiz results, assignment submissions, and mastery scores. Curriculum and your lecturer account are preserved.': 'Removes all students, quiz results, assignment submissions, and mastery scores. Curriculum and your lecturer account are preserved.',
    // Activities
    'In-Class Activities': 'In-Class Activities', 'Generate and launch live activities': 'Generate and launch live activities',
    '🚀 Launch Activity': '🚀 Launch Activity', 'Select Chapter & Topic': 'Select Chapter & Topic',
    'Generate Activity': 'Generate Activity', 'Loading curriculum...': 'Loading curriculum...',
    // Quiz Management
    'Quiz Management': 'Quiz Management', 'Create and manage quizzes': 'Create and manage quizzes',
    '➕ Create New Quiz': '➕ Create New Quiz', 'Quiz Title': 'Quiz Title',
    Chapter: 'Chapter', 'All chapters': 'All chapters', Questions: 'Questions', 'Create Quiz': 'Create Quiz',
    completed: 'Completed',
    // Assignments
    'Assignment Management': 'Assignment Management', 'Assign homework to your students': 'Assign homework to your students',
    '➕ Create New Assignment': '➕ Create New Assignment', 'Assignment Title': 'Assignment Title',
    'Create Assignment': 'Create Assignment', 'Your homework tasks': 'Your homework tasks',
    // Students
    'Student Roster': 'Student Roster', 'Monitor individual student progress': 'Monitor individual student progress',
    Kick: 'Kick', 'Mastery:': 'Mastery:', responses: 'responses',
    // Reports
    'Weekly Report': 'Weekly Report', 'AI-generated class performance analysis': 'AI-generated class performance analysis',
    '🔄 Generate Report': '🔄 Generate Report',
    // Curriculum
    'Aula Internacional Plus 1 — Content Map': 'Aula Internacional Plus 1 — Content Map',
    // Waiting Room
    'Account Pending Approval': 'Account Pending Approval',
    'Please wait for your lecturer to approve your account. This screen will refresh automatically once approved.': 'Please wait for your lecturer to approve your account. This screen will refresh automatically once approved.',
    // Nav badge
    'AI ACTIVE': 'AI ACTIVE',
    // Student home
    '📖 Current Chapter': '📖 Current Chapter',
    Practice: 'Practice', Home: 'Home',
    // Settings
    'settings.title': 'Settings',
    'settings.appearance': 'Appearance',
    'settings.dark': 'Dark',
    'settings.light': 'Light',
    'settings.hud_size': 'HUD Size',
    'settings.normal': 'Normal',
    'settings.large': 'Large',
    'settings.done': 'Done',
    // Draft Modal
    'draft.review': 'Review Questions',
    'draft.publish': 'Publish',
    'draft.add_question': 'Add Question',
    'draft.prompt': 'Question Prompt',
    'draft.answer': 'Correct Answer',
    'draft.distractors': 'Distractors (comma separated)',
    'draft.save': 'Save',
    'draft.cancel': 'Cancel',
    'draft.remove': 'Remove',
    'draft.type': 'Question Type',
    'draft.fill_blank': 'Fill in the gap',
    'draft.mcq': 'Multiple Choice'
  },
  tr: {
    langBtn: '🌐 EN',
    loginTitle: 'Öğrenci Girişi', signInTab: 'Giriş Yap', registerTab: 'Kayıt Ol', welcomeBack: 'Tekrar Hoş Geldin', signInHint: 'Devam etmek için giriş yapın', emailLabel: 'E-posta', passwordLabel: 'Şifre', signInBtn: 'Giriş Yap', joinClass: 'Sınıfa Katıl', registerHint: 'Öğrenci hesabı oluştur', nameLabel: 'Ad Soyad', registerBtn: 'Hesap Oluştur', lecturerAccess: 'Öğretmen Girişi', signOut: 'Çıkış Yap', rememberMe: 'Beni Hatırla',
    'Lecturer Login': 'Öğretmen Girişi', 'Sign in with your email and password': 'E-posta ve şifrenizle giriş yapın',
    'Student Login': 'Öğrenci Girişi', 'Log in with your student number': 'Öğrenci numaranızla giriş yapın',
    'Student Number': 'Öğrenci Numarası', '(required)': '(ilk girişte gerekli)',
    'Your Full Name': 'Adınız Soyadınız', 'e.g. 2021123456': 'Örn: 2021123456',
    Email: 'E-posta', Password: 'Şifre', 'Full Name': 'Ad Soyad',
    'Sign In': 'Giriş Yap', 'Remember Me': 'Beni Hatırla', 'Sign Out': 'Çıkış Yap',
    messageTeacher: 'Öğretmene Mesaj', inbox: 'Gelen Kutusu', book: 'Kitap',
    '👩‍🏫 Lecturer': '👩‍🏫 Öğretmen', '🎓 Student': '🎓 Öğrenci',
    // Student dashboard
    home: 'Ana Sayfa', practice: 'Alıştırma', quizzes: 'Sınavlar', myProgress: 'Gelişimim',
    keepUp: 'Harika gidiyorsun, devam et!', overallMastery: 'Genel Başarı', strongTopics: 'İyi Olduğum Konular', needsWork: 'Eksiğim Olan Konular', topicsStudied: 'Çalışılan Konular', currentChapter: 'Mevcut Ünite',
    selectPractice: 'Alıştırma yapmak için bir konu seçin', availableQuizzes: 'Mevcut Sınavlar', trackMastery: 'Konulardaki başarı durumunuzu takip edin', noQuizzes: 'Henüz sınav yok.',
    takeQuiz: 'Sınava Başla', view: 'Görüntüle', close: 'Kapat', done: 'Bitti', submit: 'Gönder', check: 'Kontrol Et',
    yourScore: 'Puanınız', questions: 'soru', correct: 'doğru',
    incorrectAns: 'Yanlış. Doğru cevap:', correctAns: 'Doğru cevap:', correctMsg: 'Doğru! ✓',
    takeQuizBtn: 'Sınava Başla', viewBtn: 'Görüntüle',
    // Lecturer nav & tabs
    Lecturer: 'Öğretmen', Student: 'Öğrenci',
    Overview: 'Genel Bakış', Curriculum: 'Müfredat', Activities: 'Etkinlikler', Students: 'Öğrenciler', Reports: 'Raporlar', Dashboard: 'Kontrol Paneli', Assignments: 'Ödevler', Quizzes: 'Sınavlar', 'My Stats': 'İstatistiklerim',
    // Overview stats
    STUDENTS: 'ÖĞRENCİLER', 'CLASS MASTERY': 'SINIF BAŞARISI', 'AT RISK': 'RİSKLİ', 'TOP PERFORMERS': 'EN İYİLER',
    'Class Mastery': 'Sınıf Başarısı', 'At Risk': 'Riskli', 'Top Performers': 'En İyiler',
    '⚠️ At-Risk Students': '⚠️ Riskli Öğrenciler', '📊 Topic Difficulty': '📊 Konu Zorluğu',
    'active this week': 'bu hafta aktif', 'Average across all topics': 'Tüm konularda ortalama',
    'Students needing attention': 'Dikkat gerektiren öğrenciler', 'Mastery above 80%': '%80 üzeri başarı',
    'No at-risk students 🎉': 'Riskli öğrenci yok 🎉', mastery: 'başarı',
    'Welcome back,': 'Tekrar hoş geldin,',
    // Data Management
    'Data Management': 'Veri Yönetimi', 'Erase All Data': 'Tüm Verileri Sil',
    'Removes all students, quiz results, assignment submissions, and mastery scores. Curriculum and your lecturer account are preserved.': 'Tüm öğrencileri, sınav sonuçlarını, ödev teslimlerini ve başarı puanlarını siler. Müfredat ve öğretmen hesabınız korunur.',
    // Activities
    'In-Class Activities': 'Sınıf İçi Etkinlikler', 'Generate and launch live activities': 'Canlı etkinlikler oluştur ve başlat',
    '🚀 Launch Activity': '🚀 Etkinlik Başlat', 'Select Chapter & Topic': 'Ünite ve Konu Seç',
    'Generate Activity': 'Etkinlik Oluştur', 'Loading curriculum...': 'Müfredat yükleniyor...',
    // Quiz Management
    'Quiz Management': 'Sınav Yönetimi', 'Create and manage quizzes': 'Sınav oluştur ve yönet',
    '➕ Create New Quiz': '➕ Yeni Sınav Oluştur', 'Quiz Title': 'Sınav Başlığı',
    Chapter: 'Ünite', 'All chapters': 'Tüm üniteler', Questions: 'Soru Sayısı', 'Create Quiz': 'Sınav Oluştur',
    completed: 'Tamamlandı',
    // Assignments
    'Assignment Management': 'Ödev Yönetimi', 'Assign homework to your students': 'Öğrencilerinize ödev atayın',
    '➕ Create New Assignment': '➕ Yeni Ödev Oluştur', 'Assignment Title': 'Ödev Başlığı',
    'Create Assignment': 'Ödev Oluştur', 'Your homework tasks': 'Ödev görevleriniz',
    // Students
    'Student Roster': 'Öğrenci Listesi', 'Monitor individual student progress': 'Bireysel öğrenci gelişimini izle',
    Kick: 'At', 'Mastery:': 'Başarı:', responses: 'yanıt',
    // Reports
    'Weekly Report': 'Haftalık Rapor', 'AI-generated class performance analysis': 'Yapay zeka destekli sınıf performans analizi',
    '🔄 Generate Report': '🔄 Rapor Oluştur',
    // Curriculum
    'Aula Internacional Plus 1 — Content Map': 'Aula Internacional Plus 1 — İçerik Haritası',
    // Waiting Room
    'Account Pending Approval': 'Hesabınız Onay Bekliyor',
    'Please wait for your lecturer to approve your account. This screen will refresh automatically once approved.': 'Lütfen öğretmeninizin hesabınızı onaylamasını bekleyin. Onaylandıktan sonra bu ekran otomatik olarak yenilenecektir.',
    // Nav badge
    'AI ACTIVE': 'AI AKTİF',
    // Student home
    '📖 Current Chapter': '📖 Mevcut Ünite',
    Practice: 'Alıştırma', Home: 'Ana Sayfa',
    // Settings
    'settings.title': 'Ayarlar',
    'settings.appearance': 'Görünüm',
    'settings.dark': 'Karanlık',
    'settings.light': 'Aydınlık',
    'settings.hud_size': 'Arayüz Boyutu',
    'settings.normal': 'Normal',
    'settings.large': 'Büyük',
    'settings.done': 'Bitti',
    // Draft Modal
    'draft.review': 'Soruları Gözden Geçir',
    'draft.publish': 'Yayınla',
    'draft.add_question': 'Soru Ekle',
    'draft.prompt': 'Soru Metni',
    'draft.answer': 'Doğru Cevap',
    'draft.distractors': 'Yanlış Seçenekler (virgülle ayırın)',
    'draft.save': 'Kaydet',
    'draft.cancel': 'İptal',
    'draft.remove': 'Kaldır',
    'draft.type': 'Soru Tipi',
    'draft.fill_blank': 'Boşluk Doldurma',
    'draft.mcq': 'Çoktan Seçmeli'
  }
};

function t(key) { return i18n[currentLang][key] || key; }

function toggleLanguage() {
  currentLang = currentLang === 'en' ? 'tr' : 'en';
  localStorage.setItem('aula_lang', currentLang);
  document.getElementById('lang-btn').textContent = t('langBtn');

  const from = currentLang === 'en' ? i18n['tr'] : i18n['en'];
  const to = currentLang === 'en' ? i18n['en'] : i18n['tr'];

  const walkDOM = (node) => {
    if (node.nodeType === 3) {
      let txt = node.nodeValue.trim();
      if (txt) {
        let matchKey = Object.keys(from).find(k => from[k] === txt);
        if (matchKey) node.nodeValue = node.nodeValue.replace(txt, to[matchKey]);
      }
    } else if (node.nodeType === 1 && node.nodeName !== 'SCRIPT') {
      if (node.placeholder) {
        let matchKey = Object.keys(from).find(k => from[k] === node.placeholder);
        if (matchKey) node.placeholder = to[matchKey];
      }
      if (node.dataset && node.dataset.i18n) {
        const key = node.dataset.i18n;
        if (to[key]) node.textContent = to[key];
      }
      for (let child = node.firstChild; child; child = child.nextSibling) walkDOM(child);
    }
  };
  walkDOM(document.body);

  // Re-render all dynamic content in the correct language
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

function switchLoginTab(tab) {
  document.getElementById('tab-lecturer').classList.toggle('active', tab === 'lecturer');
  document.getElementById('tab-student').classList.toggle('active', tab === 'student');
  document.getElementById('lecturer-login-panel').style.display = tab === 'lecturer' ? 'block' : 'none';
  document.getElementById('student-login-panel').style.display = tab === 'student' ? 'block' : 'none';
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
  if (courses && courses.length) courseId = courses[0].id;
  const currData = await api('/curriculum?course_id=' + courseId);
  curriculum = Array.isArray(currData) ? currData : [];
  if (currentUser.status === 'pending') {
    // Re-check status from server in case lecturer already approved
    try {
      const check = await api('/user/status?user_id=' + currentUser.id);
      if (check && check.status === 'approved') {
        currentUser.status = 'approved';
        localStorage.setItem('aula_user', JSON.stringify(currentUser));
        sessionStorage.setItem('aula_user', JSON.stringify(currentUser));
      }
    } catch(e) {}
    
    if (currentUser.status === 'pending') {
      showScreen('waiting-room-screen');
      // Poll every 3 seconds until approved
      const waitingPoll = setInterval(async () => {
        try {
          const check = await api('/user/status?user_id=' + currentUser.id);
          if (check && check.status === 'approved') {
            clearInterval(waitingPoll);
            currentUser.status = 'approved';
            localStorage.setItem('aula_user', JSON.stringify(currentUser));
            sessionStorage.setItem('aula_user', JSON.stringify(currentUser));
            window.location.reload();
          } else if (check && check.error === 'User not found') {
            clearInterval(waitingPoll);
            alert(currentLang === 'tr' ? 'Hesabınız reddedildi ve silindi.' : 'Your account was rejected and removed.');
            logout();
          }
        } catch(e) {}
      }, 3000);
      return;
    }
  }
  
  showScreen(currentUser.role === 'lecturer' ? 'lecturer-dashboard' : 'student-dashboard');
  if (currentUser.role === 'lecturer') {
    initLecturer();
  } else {
    initStudent();
  }
  startLiveSync();
}

async function handleStudentLogin(e) {
  e.preventDefault();
  const number = document.getElementById('student-number').value.trim();
  const name = document.getElementById('student-name-input').value.trim();
  const errEl = document.getElementById('student-login-error');
  errEl.classList.add('hidden');

  const data = await api('/student/login', { method: 'POST', body: { student_number: number, name } });
  if (data.error) {
    const isTr = currentLang === 'tr';
    const errorMap = {
      'Name is required': isTr ? 'Ad Soyad alanı zorunludur.' : 'Full name is required.',
      'Name is required for first login': isTr ? 'İlk girişte ad soyad gereklidir.' : 'Full name is required for first login.',
      'Student number and name do not match': isTr ? 'Öğrenci numarası ve isim eşleşmiyor. Lütfen kayıtlı bilgilerinizi giriniz.' : 'Student number and name do not match. Please enter your registered information.',
      'Student number is required': isTr ? 'Öğrenci numarası gereklidir.' : 'Student number is required.'
    };
    errEl.textContent = errorMap[data.error] || data.error;
    errEl.classList.remove('hidden');
    return false;
  }
  // On subsequent logins, name field not needed
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
  _lastVersion = -1;
  stopLiveSync();
  localStorage.removeItem('aula_user');
  sessionStorage.removeItem('aula_user');
  showScreen('login-screen'); 
}

window.addEventListener('DOMContentLoaded', () => {
  const savedLang = localStorage.getItem('aula_lang');
  if (savedLang && savedLang !== currentLang) toggleLanguage();
  
  // Apply saved theme and HUD size
  const savedTheme = localStorage.getItem('aula_theme') || 'dark';
  setTheme(savedTheme);
  const savedHud = localStorage.getItem('aula_hud') || 'normal';
  setHudSize(savedHud);

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

function switchTab(btn, skipLoad = false) {
  const nav = btn.closest('.topnav') || btn.closest('nav');
  nav.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  const main = btn.closest('.screen').querySelector('main');
  main.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  
  if (!skipLoad) {
    if (btn.dataset.tab === 'inbox') loadInbox();
    if (btn.dataset.tab === 's-messages') loadStudentChat();
  }
}

function closeModal() { document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden')); }

// ── Messages ──
let currentChatStudentId = null;

async function loadStudentChat() {
  const messages = await api(`/messages?student_id=${currentUser.id}`);
  const container = document.getElementById('student-chat-history');
  
  if (!messages || messages.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted); text-align:center; padding:20px;">${currentLang==='tr'?'Henüz mesaj yok.':'No messages yet.'}</p>`;
    return;
  }
  
  container.innerHTML = messages.map(m => {
    const isMe = m.sender === 'student';
    return `
      <div style="display:flex; justify-content:${isMe ? 'flex-end' : 'flex-start'};">
        <div style="max-width:80%; background:${isMe ? 'var(--accent)' : 'var(--bg-secondary)'}; color:${isMe ? '#fff' : 'var(--text-primary)'}; border-radius:12px; padding:10px 14px; font-size:14px; box-shadow:0 2px 5px rgba(0,0,0,0.2);">
          ${esc(m.content)}
          <div style="font-size:10px; text-align:right; margin-top:4px; opacity:0.7;">${new Date(m.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
        </div>
      </div>
    `;
  }).join('');
  
  messages.filter(m => m.sender === 'lecturer' && !m.is_read).forEach(m => {
    api('/message/read', { method: 'POST', body: { message_id: m.id } });
  });
  
  container.scrollTop = container.scrollHeight;
}

async function sendMessage() {
  const text = document.getElementById('message-text').value.trim();
  if (!text) return;
  document.getElementById('message-text').value = '';
  await api('/message/send', { method: 'POST', body: { student_id: currentUser.id, sender: 'student', content: text } });
  await loadStudentChat();
}

async function loadInbox() {
  const messages = await api('/messages');
  const container = document.getElementById('inbox-messages');
  document.getElementById('inbox-back-btn').classList.add('hidden');
  document.getElementById('inbox-reply-area').classList.add('hidden');
  document.getElementById('inbox-title').innerHTML = `📥 <span data-i18n="inbox">Inbox</span>`;
  currentChatStudentId = null;
  
  const unreadCount = messages.filter(m => m.sender === 'student' && !m.is_read).length;
  const badge = document.getElementById('inbox-badge');
  if (unreadCount > 0) {
    badge.style.display = 'flex';
    badge.textContent = unreadCount;
  } else {
    badge.style.display = 'none';
  }
  
  if (!messages || messages.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted); text-align:center; padding:20px;">${currentLang==='tr'?'Mesaj yok.':'No messages.'}</p>`;
    return;
  }
  
  const threads = {};
  messages.forEach(m => {
    if (!threads[m.student_id]) {
      threads[m.student_id] = { student_name: m.student_name, latest: m, unread: 0 };
    } else {
      if (new Date(m.created_at) > new Date(threads[m.student_id].latest.created_at)) {
        threads[m.student_id].latest = m;
      }
    }
    if (m.sender === 'student' && !m.is_read) {
      threads[m.student_id].unread++;
    }
  });
  
  const threadList = Object.entries(threads).sort((a,b) => new Date(b[1].latest.created_at) - new Date(a[1].latest.created_at));
  
  container.innerHTML = threadList.map(([sId, data]) => `
    <div style="background:var(--bg-primary); border:1px solid var(--border); border-radius:8px; padding:12px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; transition:var(--transition);" onclick="openChat('${sId}', '${esc(data.student_name).replace(/'/g, "\\'")}')">
      <div style="flex:1; min-width:0; margin-right:12px;">
        <strong style="font-size:15px; color:var(--text-primary);">${esc(data.student_name)}</strong>
        <div style="font-size:13px; color:var(--text-muted); margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
          ${data.latest.sender === 'lecturer' ? 'You: ' : ''}${esc(data.latest.content)}
        </div>
      </div>
      <div style="display:flex; flex-direction:column; align-items:flex-end; gap:6px; flex-shrink:0;">
        <span style="font-size:11px; color:var(--text-muted);">${new Date(data.latest.created_at).toLocaleDateString()}</span>
        ${data.unread > 0 ? `<span style="background:var(--accent); color:#fff; border-radius:12px; padding:2px 8px; font-size:11px; font-weight:bold;">${data.unread}</span>` : ''}
      </div>
    </div>
  `).join('');
}

async function openChat(studentId, studentName) {
  currentChatStudentId = studentId;
  document.getElementById('inbox-back-btn').classList.remove('hidden');
  document.getElementById('inbox-reply-area').classList.remove('hidden');
  document.getElementById('inbox-title').innerHTML = `💬 ${esc(studentName)}`;
  
  const messages = await api(`/messages?student_id=${studentId}`);
  const container = document.getElementById('inbox-messages');
  
  container.innerHTML = messages.map(m => {
    const isMe = m.sender === 'lecturer';
    return `
      <div style="display:flex; justify-content:${isMe ? 'flex-end' : 'flex-start'};">
        <div style="max-width:80%; background:${isMe ? 'var(--accent)' : 'var(--bg-secondary)'}; color:${isMe ? '#fff' : 'var(--text-primary)'}; border-radius:12px; padding:10px 14px; font-size:14px; box-shadow:0 2px 5px rgba(0,0,0,0.2);">
          ${esc(m.content)}
          <div style="font-size:10px; text-align:right; margin-top:4px; opacity:0.7;">${new Date(m.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
        </div>
      </div>
    `;
  }).join('');
  
  messages.filter(m => m.sender === 'student' && !m.is_read).forEach(m => {
    api('/message/read', { method: 'POST', body: { message_id: m.id } });
  });
  
  const badge = document.getElementById('inbox-badge');
  const remaining = Math.max(0, parseInt(badge.textContent || '0') - messages.filter(m => m.sender === 'student' && !m.is_read).length);
  if (remaining > 0) {
    badge.textContent = remaining;
  } else {
    badge.style.display = 'none';
  }
  
  container.scrollTop = container.scrollHeight;
}

async function sendLecturerMessage() {
  const text = document.getElementById('inbox-reply-text').value.trim();
  if (!text || !currentChatStudentId) return;
  document.getElementById('inbox-reply-text').value = '';
  await api('/message/send', { method: 'POST', body: { student_id: currentChatStudentId, sender: 'lecturer', content: text } });
  
  const name = document.getElementById('inbox-title').textContent.replace('💬 ', '');
  await openChat(currentChatStudentId, name);
}

// ── Settings ──
function openSettingsModal() {
  document.getElementById('settings-modal').classList.remove('hidden');
}

function closeSettingsModal() {
  document.getElementById('settings-modal').classList.add('hidden');
}

function setTheme(theme) {
  if (theme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
    document.getElementById('theme-light-btn')?.classList.add('active', 'btn-primary');
    document.getElementById('theme-light-btn')?.classList.remove('btn-outline');
    document.getElementById('theme-dark-btn')?.classList.remove('active', 'btn-primary');
    document.getElementById('theme-dark-btn')?.classList.add('btn-outline');
  } else {
    document.documentElement.removeAttribute('data-theme');
    document.getElementById('theme-dark-btn')?.classList.add('active', 'btn-primary');
    document.getElementById('theme-dark-btn')?.classList.remove('btn-outline');
    document.getElementById('theme-light-btn')?.classList.remove('active', 'btn-primary');
    document.getElementById('theme-light-btn')?.classList.add('btn-outline');
  }
  localStorage.setItem('aula_theme', theme);
}

function setHudSize(size) {
  if (size === 'large') {
    document.body.style.zoom = '1.1';
    document.getElementById('hud-large-btn')?.classList.add('active', 'btn-primary');
    document.getElementById('hud-large-btn')?.classList.remove('btn-outline');
    document.getElementById('hud-normal-btn')?.classList.remove('active', 'btn-primary');
    document.getElementById('hud-normal-btn')?.classList.add('btn-outline');
  } else {
    document.body.style.zoom = '1.0';
    document.getElementById('hud-normal-btn')?.classList.add('active', 'btn-primary');
    document.getElementById('hud-normal-btn')?.classList.remove('btn-outline');
    document.getElementById('hud-large-btn')?.classList.remove('active', 'btn-primary');
    document.getElementById('hud-large-btn')?.classList.add('btn-outline');
  }
  localStorage.setItem('aula_hud', size);
}

function masteryColor(s) { return s >= 0.75 ? 'var(--success)' : s >= 0.4 ? 'var(--warning)' : 'var(--danger)'; }
function masteryClass(s) { return s >= 0.75 ? 'success' : s >= 0.4 ? 'warning' : 'danger'; }

async function initLecturer() {
  document.getElementById('nav-username').textContent = currentUser.name;
  document.getElementById('overview-greeting').textContent = t('welcomeBack') + ', ' + currentUser.name.split(' ').pop();
  
  // Check AI status
  try {
    aiStatus = await api('/ai-status');
    const badge = document.querySelector('.nav-badge');
    if (badge && aiStatus.ai_enabled) {
      if (!document.getElementById('ai-active-badge')) {
        badge.insertAdjacentHTML('afterend', '<span id="ai-active-badge" class="nav-badge" style="background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;margin-left:6px;animation:pulse-glow 2s ease-in-out infinite;padding:3px 6px;">🤖</span>');
      }
      if (!document.getElementById('ai-pulse-style')) {
        const style = document.createElement('style');
        style.id = 'ai-pulse-style';
        style.textContent = '@keyframes pulse-glow{0%,100%{box-shadow:0 0 4px rgba(99,102,241,0.4)}50%{box-shadow:0 0 12px rgba(139,92,246,0.7)}}';
        document.head.appendChild(style);
      }
    }
  } catch(e) { aiStatus = { ai_enabled: false }; }

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
  if (a.type === 'fill_blank') return `<div class="activity-card" id="${ctx}-${idx}"><div class="activity-type-label">${translateOption('Fill in the Blank')}</div><div class="activity-prompt">${p}</div><div style="display:flex;gap:10px;align-items:center;margin-top:12px"><input class="fill-blank-input" id="inp-${ctx}-${idx}" placeholder="Your answer..." style="flex:1" onkeydown="if(event.key==='Enter')checkFill('${ctx}-${idx}','${esc(a.answer)}','${esc(a.id)}')"><button class="btn btn-primary btn-sm" onclick="checkFill('${ctx}-${idx}','${esc(a.answer)}','${esc(a.id)}')">${t('check')}</button></div>${a.hint ? `<div style="margin-top:8px;font-size:13px;color:var(--text-muted)">💡 ${a.hint}</div>` : ''}<div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
  if (a.type === 'dialogue_order') {
    const lines = a.scrambled_lines || [];
    const speakers = a.speakers || {};
    return `<div class="activity-card" id="${ctx}-${idx}"><div class="activity-type-label">🗣️ ${a.title || 'Dialogue'}</div><div class="activity-prompt">${currentLang === 'tr' ? 'Diyaloğu doğru sıraya koyun:' : 'Arrange the dialogue in the correct order:'}</div><div id="dialogue-${ctx}-${idx}" style="display:flex;flex-direction:column;gap:8px;margin-top:12px">${lines.map((line, li) => `<div class="dialogue-row" style="display:flex;align-items:center;gap:8px" data-line="${esc(line)}"><button class="btn btn-ghost btn-sm" onclick="moveDialogueLine(this,-1)" style="min-width:36px">▲</button><button class="btn btn-ghost btn-sm" onclick="moveDialogueLine(this,1)" style="min-width:36px">▼</button><div style="flex:1;padding:10px 14px;background:var(--bg-input);border:2px solid var(--border);border-radius:var(--radius-sm);font-size:14px"><span style="font-weight:600;color:var(--accent-light);margin-right:8px">${speakers[line] || '?'}:</span>${line}</div></div>`).join('')}</div><button class="btn btn-primary btn-sm" style="margin-top:12px" onclick="checkDialogue('${ctx}-${idx}','${esc(JSON.stringify(a.correct_order))}')">✓ ${t('check')}</button><div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
  }
  return '';
}

function esc(s) { return (s||'').replace(/'/g, "\\'").replace(/"/g, '&quot;'); }

async function checkMCQ(btn, answer, cardId, qid) {
  const card = document.getElementById(cardId);
  if (card.classList.contains('correct') || card.classList.contains('incorrect')) return;
  
  // Fix for escaped apostrophes in data-original attribute
  const picked = (btn.dataset.original || btn.textContent.trim()).replace(/\\'/g, "'");
  const isCorrect = picked.toLowerCase() === answer.toLowerCase();
  
  card.querySelectorAll('.option-btn').forEach(b => {
    const bText = (b.dataset.original || b.textContent.trim()).replace(/\\'/g, "'");
    if (bText.toLowerCase() === answer.toLowerCase()) b.classList.add('correct-answer');
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

function moveDialogueLine(btn, direction) {
  const row = btn.closest('.dialogue-row');
  const container = row.parentElement;
  const rows = Array.from(container.children);
  const idx = rows.indexOf(row);
  if (direction === -1 && idx > 0) {
    container.insertBefore(row, rows[idx - 1]);
  } else if (direction === 1 && idx < rows.length - 1) {
    container.insertBefore(rows[idx + 1], row);
  }
}

function checkDialogue(cardId, correctOrderJson) {
  const card = document.getElementById(cardId);
  if (card.classList.contains('correct') || card.classList.contains('incorrect')) return;
  const correctOrder = JSON.parse(correctOrderJson.replace(/\\'/g, "'"));
  const container = document.getElementById('dialogue-' + cardId);
  const currentOrder = Array.from(container.querySelectorAll('.dialogue-row')).map(r => r.dataset.line.replace(/\\'/g, "'"));
  const isCorrect = JSON.stringify(currentOrder) === JSON.stringify(correctOrder);
  card.classList.add(isCorrect ? 'correct' : 'incorrect');
  const fb = document.getElementById('fb-' + cardId);
  fb.classList.remove('hidden');
  fb.className = 'feedback-msg ' + (isCorrect ? 'correct' : 'incorrect');
  fb.textContent = isCorrect ? t('correctMsg') : (currentLang === 'tr' ? 'Doğru sıra farklı. Tekrar deneyin!' : 'Not quite right. Try again!');
  if (!isCorrect) {
    setTimeout(() => { card.classList.remove('incorrect'); fb.classList.add('hidden'); }, 2000);
  }
}

let currentDraft = null;

async function createQuiz() {
  const btn = event.target;
  const originalText = btn.textContent;
  btn.textContent = '...';
  btn.disabled = true;

  const title = document.getElementById('quiz-title').value || 'Quiz';
  const chapterId = document.getElementById('quiz-chapter-select').value || null;
  const count = parseInt(document.getElementById('quiz-count').value) || 10;
  
  const res = await api('/draft/generate', { method: 'POST', body: { course_id: courseId, chapter_id: chapterId, count } });
  
  btn.textContent = originalText;
  btn.disabled = false;
  
  if(res && res.questions) {
    currentDraft = {
      type: 'quiz',
      title: title,
      chapter_id: chapterId,
      due_at: null,
      questions: res.questions
    };
    openDraftModal();
  }
}

async function loadQuizList() {
  const quizzes = await api(`/quizzes?course_id=${courseId}&student_id=${currentUser.id}`);
  const container = currentUser.role === 'lecturer' ? document.getElementById('quiz-list') : document.getElementById('student-quiz-list');
  if (!container) return;
  const isTr = currentLang === 'tr';
  container.innerHTML = quizzes.length === 0 ? `<p style="color:var(--text-muted);padding:20px">${t('noQuizzes')}</p>`
    : quizzes.map(q => {
        if (currentUser.role === 'lecturer') {
          return `<div class="card" style="margin-bottom:12px">
            <div class="card-body flex-between">
              <div style="flex:1;cursor:pointer" onclick="viewQuiz('${q.id}','${esc(q.title)}')">
                <strong>${q.title}</strong>
                <div style="font-size:13px;color:var(--text-muted);margin-top:4px">${isTr ? 'Oluşturulma' : 'Created'}: ${new Date(q.created_at).toLocaleDateString()}</div>
              </div>
              <div style="display:flex;gap:8px;align-items:center">
                <button class="btn btn-outline btn-sm" onclick="viewQuiz('${q.id}','${esc(q.title)}')">${t('viewBtn')}</button>
                <button class="btn btn-sm" style="background:var(--danger-bg,#fde8e8);color:var(--danger);border:1px solid var(--danger)" onclick="event.stopPropagation();deleteQuiz('${q.id}','${esc(q.title)}')">🗑️ ${isTr ? 'Sil' : 'Delete'}</button>
              </div>
            </div>
          </div>`;
        } else {
          const isCompleted = q.is_completed;
          return `<div class="card" style="cursor:${isCompleted?'default':'pointer'};opacity:${isCompleted?'0.6':'1'};margin-bottom:12px" onclick="${isCompleted?'':`takeQuiz('${q.id}')`}"><div class="card-body flex-between"><div><strong>${q.title}</strong><div style="font-size:13px;color:var(--text-muted);margin-top:4px">${isTr ? 'Oluşturulma' : 'Created'}: ${new Date(q.created_at).toLocaleDateString()} ${isCompleted?` · <span style="color:var(--success)">✓ ${t('completed')}</span>`:''}</div></div><span class="btn btn-sm ${isCompleted?'btn-ghost':'btn-outline'}">${isCompleted?t('completed'):t('takeQuizBtn')}</span></div></div>`;
        }
      }).join('');
}

async function deleteQuiz(quizId, title) {
  const isTr = currentLang === 'tr';
  const msg = isTr
    ? `"${title}" sınavını silmek istediğinize emin misiniz? Bu işlem geri alınamaz ve öğrenci sonuçları da silinir.`
    : `Are you sure you want to delete the quiz "${title}"? This cannot be undone and all student results will be removed.`;
  if (!confirm(msg)) return;
  const res = await api('/quiz/delete', { method: 'POST', body: { quiz_id: quizId } });
  if (res && !res.error) loadQuizList();
}

async function viewQuiz(quizId, title) {
  const modal = document.getElementById('student-detail-modal');
  modal.classList.remove('hidden');
  document.getElementById('student-detail-body').innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-muted)">Loading...</div>`;

  const [quizData, respData] = await Promise.all([
    api('/quiz/take?quiz_id=' + quizId),
    api('/quiz/responses?quiz_id=' + quizId)
  ]);

  const isTr = currentLang === 'tr';
  const L = {
    questions: isTr ? 'Sorular' : 'Questions',
    studentResponses: isTr ? 'Öğrenci Cevapları' : 'Student Responses',
    answerKey: isTr ? 'Cevap Anahtarı' : 'Answer Key',
    answer: isTr ? 'Cevap' : 'Answer',
    noResponses: isTr ? 'Henüz hiçbir öğrenci bu sınavı çözmedi.' : 'No students have taken this quiz yet.',
    studentCount: isTr ? 'öğrenci çözdü' : 'students completed',
    score: isTr ? 'Puan' : 'Score',
    studentAnswer: isTr ? 'Öğrenci Cevabı' : "Student's Answer",
    correctAnswer: isTr ? 'Doğru Cevap' : 'Correct Answer',
    correct: isTr ? 'Doğru' : 'Correct',
    incorrect: isTr ? 'Yanlış' : 'Incorrect',
    avgScore: isTr ? 'Ortalama' : 'Average'
  };

  const studentResults = respData.student_results || [];

  document.getElementById('student-detail-body').innerHTML = `
    <h2 style="margin-bottom:4px">${title}</h2>
    <div style="color:var(--text-muted); margin-bottom:20px; font-size:14px">${quizData.questions.length} ${L.questions.toLowerCase()} · ${studentResults.length} ${L.studentCount}</div>
    
    <div style="display:flex;gap:8px;margin-bottom:20px;border-bottom:1px solid var(--border)">
      <button class="nav-tab active" onclick="switchQuizViewTab(this,'qv-questions')" style="flex:1;padding:10px">📋 ${L.answerKey}</button>
      <button class="nav-tab" onclick="switchQuizViewTab(this,'qv-responses')" style="flex:1;padding:10px">👥 ${L.studentResponses} (${studentResults.length})</button>
    </div>

    <div id="qv-questions">
      ${quizData.questions.map((q, i) => `
        <div style="margin-bottom:10px; padding:12px; background:var(--bg-input); border:1px solid var(--border); border-radius:8px">
          <div style="font-weight:600; margin-bottom:6px; font-size:14px">Q${i+1}: ${q.prompt}</div>
          <div style="font-size:13px">${L.answer}: <strong style="color:var(--success)">${q.answer}</strong></div>
        </div>
      `).join('')}
    </div>

    <div id="qv-responses" style="display:none">
      ${studentResults.length === 0 
        ? `<p style="color:var(--text-muted);padding:20px;text-align:center">${L.noResponses}</p>`
        : studentResults.map(sr => {
            const avgPct = Math.round(sr.average_score * 100);
            const correctCount = sr.answers.filter(a => a.is_correct).length;
            return `
              <div style="margin-bottom:16px; border:1px solid var(--border); border-radius:8px; overflow:hidden">
                <div style="padding:14px 16px; background:var(--bg-secondary); display:flex; justify-content:space-between; align-items:center; cursor:pointer" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
                  <div>
                    <strong style="font-size:15px">${sr.student_name}</strong>
                    <span style="font-size:13px; color:var(--text-muted); margin-left:8px">${correctCount}/${sr.total_questions} ${L.correct.toLowerCase()}</span>
                  </div>
                  <div style="display:flex; align-items:center; gap:10px">
                    <span style="font-weight:700; font-size:16px; color:${masteryColor(sr.average_score)}">${avgPct}%</span>
                    <span style="color:var(--text-muted); font-size:18px">▾</span>
                  </div>
                </div>
                <div style="display:none; padding:12px 16px; background:var(--bg-card)">
                  ${sr.answers.map((a, i) => {
                    const isRight = a.is_correct;
                    return `
                      <div style="padding:10px 0; border-bottom:1px solid var(--border); font-size:13px; display:flex; gap:10px; align-items:flex-start">
                        <span style="min-width:20px; font-weight:700; color:${isRight ? 'var(--success)' : 'var(--danger)'}">${isRight ? '✓' : '✗'}</span>
                        <div style="flex:1">
                          <div style="margin-bottom:4px; font-weight:500">${a.prompt}</div>
                          <div style="display:flex; gap:16px; flex-wrap:wrap">
                            <span>${L.studentAnswer}: <strong style="color:${isRight ? 'var(--success)' : 'var(--danger)'}">${a.student_answer === '[STARTED]' ? (currentLang === 'tr' ? '[Boş Bırakıldı]' : '[Left Blank]') : esc(a.student_answer)}</strong></span>
                            ${!isRight ? `<span>${L.correctAnswer}: <strong style="color:var(--success)">${a.correct_answer}</strong></span>` : ''}
                          </div>
                        </div>
                      </div>`;
                  }).join('')}
                </div>
              </div>`;
          }).join('')
      }
    </div>
  `;
}

function switchQuizViewTab(btn, panelId) {
  btn.parentElement.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('qv-questions').style.display = panelId === 'qv-questions' ? 'block' : 'none';
  document.getElementById('qv-responses').style.display = panelId === 'qv-responses' ? 'block' : 'none';
}

async function takeQuiz(quizId) {
  const isTr = currentLang === 'tr';
  const title = isTr ? 'Sınava Başla' : 'Start Quiz';
  const msg = isTr ? 'Emin misiniz? Sınava başladıktan sonra soruları görüp geri dönemezsiniz, yarıda bırakmak 0 puan almanıza sebep olabilir.' : 'Are you sure? Once you start, you cannot go back or cancel without submitting.';
  const confirmed = await showConfirmModal(title, msg);
  if (!confirmed) return;

  const data = await api(`/quiz/take?quiz_id=${quizId}&student_id=${currentUser.id}`);
  if (data.error) {
    alert(data.error);
    loadQuizList();
    return;
  }
  
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
    (q.type==='mcq' ? `<div class="options-grid">${((q.distractors||[]).concat([q.answer]).sort(()=>Math.random()-0.5)).map(o=>`<button class="option-btn" onclick="quizAnswer(this,'${esc(q.id)}','${esc(o)}')">${translateOption(o)}</button>`).join('')}</div>` : `<div style="display:flex;gap:10px;align-items:center;margin-top:12px"><input class="fill-blank-input" id="q-inp" style="flex:1" placeholder="${currentLang==='tr'?'Cevabınızı yazın...':'Type your answer...'}" onkeydown="if(event.key==='Enter')quizAnswer(null,'${esc(q.id)}',this.value)"><button class="btn btn-primary" onclick="quizAnswer(null,'${esc(q.id)}',document.getElementById('q-inp').value)">${currentLang==='tr'?'Gönder':'Submit'}</button></div>`) + `</div>`;
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
  const pending = await api('/students/pending').catch(()=>[]);
  const isTr = currentLang === 'tr';
  
  // Render pending approvals into separate full-width container
  const pendingEl = document.getElementById('pending-roster');
  if (pendingEl) {
    if (pending && pending.length > 0) {
      pendingEl.innerHTML = `<div style="background:linear-gradient(135deg, rgba(139,92,246,0.1), rgba(139,92,246,0.05));padding:20px;border-radius:16px;border:1px solid rgba(139,92,246,0.3);margin-bottom:24px">
        <h3 style="color:#8b5cf6;margin:0 0 16px 0;font-size:1.1rem">⏳ ${isTr ? 'Bekleyen Onaylar' : 'Pending Approvals'} (${pending.length})</h3>
        ${pending.map(s => `
          <div style="display:flex;align-items:center;justify-content:space-between;background:var(--bg-card);padding:14px 20px;border-radius:10px;margin-bottom:8px;border:1px solid var(--border)">
            <div style="min-width:0;flex:1;overflow:hidden">
              <div style="font-weight:600;color:var(--text-primary);font-size:0.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${s.name}</div>
              <div style="color:var(--text-secondary);font-size:0.8rem;margin-top:2px">${s.email}</div>
            </div>
            <div style="display:flex;gap:8px;margin-left:16px;flex-shrink:0">
              <button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); approveStudent('${s.id}')">✅ ${isTr ? 'Onayla' : 'Approve'}</button>
              <button class="btn btn-outline btn-sm" onclick="event.stopPropagation(); deleteStudent('${s.id}','${esc(s.name)}')">❌ ${isTr ? 'Reddet' : 'Reject'}</button>
            </div>
          </div>
        `).join('')}
      </div>`;
    } else {
      pendingEl.innerHTML = '';
    }
  }
  
  // Render approved students into grid
  document.getElementById('student-roster').innerHTML = students.map(s => {
    const pct = Math.round(s.avg_mastery * 100);
    const schoolNum = s.email && s.email.includes('@student.aulaai') ? s.email.split('@')[0] : '';
    const schoolNumHtml = schoolNum ? `<span style="font-size:12px; color:var(--text-muted); margin-left:8px; font-weight:normal">#${schoolNum}</span>` : '';
    return `<div class="student-card" onclick="showStudentDetail('${s.id}','${esc(s.name)}')"><div class="flex-between" style="margin-bottom:8px"><div class="student-name" style="margin-bottom:0">${s.name}${schoolNumHtml}</div><div style="display:flex;gap:6px"><button class="btn btn-sm" style="background:var(--accent);color:#fff;border:none;padding:4px 8px;border-radius:6px;font-size:14px" onclick="event.stopPropagation();openChatFromRoster('${s.id}','${esc(s.name).replace(/'/g, "\\'")}')">💬 ${t('Message')}</button><button class="btn btn-sm" style="background:var(--danger-bg);color:var(--danger);border:1px solid var(--danger);padding:4px 8px;border-radius:6px" onclick="event.stopPropagation();deleteStudent('${s.id}','${esc(s.name).replace(/'/g, "\\'")}')">${t('Kick')}</button></div></div><div class="student-mastery-bar"><div class="student-mastery-fill" style="width:${pct}%;background:${masteryColor(s.avg_mastery)}"></div></div><div class="student-meta-row"><span>${t('Mastery:')} ${pct}%</span><span>${s.total_responses} ${t('responses')}</span></div></div>`;
  }).join('');
}

window.openChatFromRoster = async (studentId, studentName) => {
  const tabBtn = document.querySelector('button[data-tab="inbox"]');
  if (tabBtn) switchTab(tabBtn, true);
  await openChat(studentId, studentName);
};

window.approveStudent = async (id) => {
  await api('/students/approve', { method: 'POST', body: { student_id: id } });
  loadStudentRoster();
};

function showConfirmModal(title, message, isDanger = false, inputPlaceholder = null) {
  return new Promise(resolve => {
    const modal = document.getElementById('confirm-modal');
    document.getElementById('confirm-title').textContent = title;
    document.getElementById('confirm-message').textContent = message;
    
    const inputContainer = document.getElementById('confirm-input-container');
    const inputEl = document.getElementById('confirm-input');
    
    if (inputPlaceholder !== null) {
      inputContainer.classList.remove('hidden');
      inputEl.placeholder = inputPlaceholder;
      inputEl.value = '';
    } else {
      inputContainer.classList.add('hidden');
    }
    
    const okBtn = document.getElementById('confirm-ok-btn');
    const cancelBtn = document.getElementById('confirm-cancel-btn');
    
    if (isDanger) {
      okBtn.style.background = 'var(--danger)';
      okBtn.style.boxShadow = '0 0 10px rgba(239,68,68,0.4)';
    } else {
      okBtn.style.background = 'var(--primary)';
      okBtn.style.boxShadow = '0 0 10px rgba(99,102,241,0.4)';
    }
    
    const cleanup = () => {
      modal.classList.add('hidden');
      okBtn.removeEventListener('click', onOk);
      cancelBtn.removeEventListener('click', onCancel);
    };
    
    const onOk = () => { cleanup(); resolve(inputPlaceholder !== null ? inputEl.value : true); };
    const onCancel = () => { cleanup(); resolve(inputPlaceholder !== null ? null : false); };
    
    okBtn.addEventListener('click', onOk);
    cancelBtn.addEventListener('click', onCancel);
    
    modal.classList.remove('hidden');
    if (inputPlaceholder !== null) inputEl.focus();
  });
}

async function deleteStudent(sid, name) {
  const isTr = currentLang === 'tr';
  const title = isTr ? 'Öğrenciyi At' : 'Kick Student';
  const msg = isTr ? `${name} adlı öğrenciyi sınıftan atmak istediğinize emin misiniz? Bu işlem geri alınamaz.` : `Are you sure you want to kick ${name} from the class? This cannot be undone.`;
  
  const confirmed = await showConfirmModal(title, msg, true);
  if (confirmed) {
    const res = await api('/student/delete', { method: 'POST', body: { student_id: sid } });
    if (!res.error) loadStudentRoster();
  }
}

async function eraseAllData() {
  const isTr = currentLang === 'tr';
  const title = isTr ? 'Tüm Verileri Sil' : 'Erase All Data';
  const msg1 = isTr
    ? 'DİKKAT: Tüm öğrenci verileri, sınav sonuçları, ödev teslimleri ve başarı puanları silinecektir. Bu işlem geri alınamaz.'
    : 'WARNING: This will permanently delete ALL students, quiz results, assignment submissions, and mastery scores. This cannot be undone.';
  
  const confirmed1 = await showConfirmModal(title, msg1, true);
  if (!confirmed1) return;

  const msg2 = isTr
    ? 'Devam etmek için aşağıdaki kutuya "ERASE ALL DATA" yazın:'
    : 'Type "ERASE ALL DATA" to confirm:';
  
  const typed = await showConfirmModal(title, msg2, true, 'ERASE ALL DATA');
  if (typed !== 'ERASE ALL DATA') {
    return;
  }

  const res = await api('/data/reset', { method: 'POST', body: { confirm: 'ERASE ALL DATA' } });
  if (res.success) {
    alert(isTr ? 'Tüm veriler silindi.' : 'All data has been erased.');
    location.reload();
  } else {
    alert(res.error || 'Error');
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
  document.getElementById('report-content').innerHTML = '<p style="color:var(--text-muted)">' + (currentLang==='tr'?'Rapor oluşturuluyor...':'Generating report...') + '</p>';
  const r = await api('/report/generate', { method: 'POST', body: { course_id: courseId } });
  const isTr = currentLang === 'tr';
  const today = new Date().toLocaleDateString(isTr ? 'tr-TR' : 'en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  const avgPct = Math.round((r.summary?.class_avg_mastery||0)*100);

  const L = {
    title: isTr ? 'AulaAI Haftalık Özet' : 'AulaAI Weekly Digest',
    greeting: isTr ? 'Merhaba Profesör,' : 'Hi Professor,',
    intro: isTr ? '<strong>İspanyolca 101</strong> dersiniz için yapay zeka destekli haftalık performans raporunuz.' : 'Here is your AI-generated weekly performance breakdown for <strong>Spanish 101</strong>.',
    classSize: isTr ? 'Sınıf Mevcudu' : 'Class Size',
    classMastery: isTr ? 'Sınıf Başarısı' : 'Class Mastery',
    atRisk: isTr ? 'Riskli' : 'At Risk',
    aiInsights: isTr ? '🤖 Yapay Zeka Analizi' : '🤖 AI Insights',
    aiBody: isTr
      ? ('Sınıf ortalaması şu an %' + avgPct + ' seviyesinde. ' + ((r.review_topics||[]).length > 0 ? '<strong>' + r.review_topics[0].topic + '</strong> konusunda zorluk tespit edildi. Hızlı bir canlı etkinlik yapmanızı öneriyoruz.' : 'Harika! Şu an ciddi bir sorun tespit edilmedi.'))
      : ('The class is tracking an average mastery of ' + avgPct + '%. ' + ((r.review_topics||[]).length > 0 ? 'We noticed some difficulty with <strong>' + r.review_topics[0].topic + '</strong>. We recommend running a quick live activity.' : 'Great job! No major review topics detected right now.')),
    topicsReview: isTr ? '📊 Tekrar Gerektiren Konular' : '📊 Topics Needing Review',
    noTopics: isTr ? 'Zorlanılan konu tespit edilmedi.' : 'No challenging topics detected.',
    avgLabel: isTr ? 'ort' : 'avg',
    intervention: isTr ? '⚠️ Müdahale Gerektiren Öğrenciler' : '⚠️ Students Needing Intervention',
    noRisk: isTr ? 'Riskli öğrenci yok 🎉' : 'No at-risk students 🎉',
    overallLabel: isTr ? 'genel' : 'overall',
    evalTitle: isTr ? '👥 Bireysel Öğrenci Değerlendirmeleri' : '👥 Individual Student Evaluations',
    noStudents: isTr ? 'Kayıtlı öğrenci bulunmuyor.' : 'No enrolled students found.'
  };

  document.getElementById('report-content').innerHTML = `
    <div style="max-width: 800px; margin: 0 auto; background: var(--bg-card); border-radius: 8px; overflow: hidden; border: 1px solid var(--border);">
      <div style="background: var(--gradient-1); padding: 30px; text-align: center; color: white;">
        <div style="font-size: 32px; margin-bottom: 10px;">🇪🇸</div>
        <h2 style="margin: 0; font-size: 24px; font-weight: 600;">${L.title}</h2>
        <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 14px;">${today}</p>
      </div>
      <div style="padding: 40px 30px;">
        <p style="font-size: 16px; line-height: 1.6; margin-top: 0;">${L.greeting}</p>
        <p style="font-size: 16px; line-height: 1.6; color: var(--text-secondary);">${L.intro}</p>
        <div style="display: flex; gap: 20px; margin: 30px 0; flex-wrap: wrap;">
          <div style="flex: 1; min-width: 120px; background: var(--bg-input); border: 1px solid var(--border); padding: 20px; border-radius: 8px; text-align: center;">
            <div style="font-size: 12px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">${L.classSize}</div>
            <div style="font-size: 28px; font-weight: 700; margin-top: 5px;">${r.summary?.total_students||0}</div>
          </div>
          <div style="flex: 1; min-width: 120px; background: var(--bg-input); border: 1px solid var(--border); padding: 20px; border-radius: 8px; text-align: center;">
            <div style="font-size: 12px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">${L.classMastery}</div>
            <div style="font-size: 28px; font-weight: 700; margin-top: 5px;">${avgPct}%</div>
          </div>
          <div style="flex: 1; min-width: 120px; background: var(--danger-bg); border: 1px solid var(--danger); padding: 20px; border-radius: 8px; text-align: center;">
            <div style="font-size: 12px; text-transform: uppercase; color: var(--danger); font-weight: 600;">${L.atRisk}</div>
            <div style="font-size: 28px; font-weight: 700; color: var(--danger); margin-top: 5px;">${r.summary?.at_risk_count||0}</div>
          </div>
        </div>
        <h3 style="font-size: 18px; border-bottom: 2px solid var(--border); padding-bottom: 10px; margin-top: 40px;">${L.aiInsights}</h3>
        ${r.ai_insights ? `
          <div style="background: var(--bg-input); padding: 20px; border-left: 4px solid var(--accent); border-radius: 0 8px 8px 0; margin-bottom: 16px;">
            <p style="font-size: 15px; line-height: 1.7; margin: 0 0 12px 0;">${r.ai_insights.summary_text || ''}</p>
            ${r.ai_insights.key_insight ? `<p style="font-size: 14px; line-height: 1.6; margin: 0 0 8px 0; color: var(--warning);"><strong>💡 ${isTr ? 'Önemli' : 'Key Insight'}:</strong> ${r.ai_insights.key_insight}</p>` : ''}
            ${r.ai_insights.recommendation ? `<p style="font-size: 14px; line-height: 1.6; margin: 0 0 8px 0; color: var(--accent);"><strong>📌 ${isTr ? 'Öneri' : 'Recommendation'}:</strong> ${r.ai_insights.recommendation}</p>` : ''}
            ${r.ai_insights.praise_point ? `<p style="font-size: 14px; line-height: 1.6; margin: 0; color: var(--success);"><strong>🌟 ${isTr ? 'Olumlu' : 'Praise'}:</strong> ${r.ai_insights.praise_point}</p>` : ''}
          </div>
          <div style="font-size: 11px; color: var(--text-muted); text-align: right; margin-bottom: 8px;">Powered by Groq · Llama 3.3 70B</div>
        ` : `<p style="font-size: 15px; line-height: 1.6; background: var(--bg-input); padding: 15px; border-left: 4px solid var(--accent); border-radius: 0 8px 8px 0;">${L.aiBody}</p>`}
        <h3 style="font-size: 18px; border-bottom: 2px solid var(--border); padding-bottom: 10px; margin-top: 40px;">${L.topicsReview}</h3>
        <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
          ${(r.review_topics||[]).map(td => '<tr style="border-bottom: 1px solid var(--border);"><td style="padding: 12px 0; font-size: 15px; font-weight: 500;">' + td.topic + '</td><td style="padding: 12px 0; text-align: right;"><span style="background: var(--warning-bg); color: var(--warning); padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">' + Math.round(td.avg_mastery*100) + '% ' + L.avgLabel + '</span></td></tr>').join('') || '<tr><td style="padding: 12px 0; color: var(--text-muted);">' + L.noTopics + '</td></tr>'}
        </table>
        <h3 style="font-size: 18px; border-bottom: 2px solid var(--border); padding-bottom: 10px; margin-top: 40px;">${L.intervention}</h3>
        ${(r.at_risk_students||[]).length === 0 ? '<p style="color: var(--success); font-weight: 500;">' + L.noRisk + '</p>' :
          '<table style="width: 100%; border-collapse: collapse; margin-top: 15px;">' + r.at_risk_students.map(rs => '<tr style="border-bottom: 1px solid var(--border);"><td style="padding: 12px 0; font-size: 15px; font-weight: 600;">' + rs.name + '</td><td style="padding: 12px 0; text-align: right; color: var(--danger); font-weight: 600;">' + Math.round(rs.overall_mastery*100) + '% ' + L.overallLabel + '</td></tr>').join('') + '</table>'}
        <h3 style="font-size: 18px; border-bottom: 2px solid var(--border); padding-bottom: 10px; margin-top: 40px;">${L.evalTitle}</h3>
        <div style="margin-top: 15px; display: flex; flex-direction: column; gap: 15px;">
          ${(r.student_reports||[]).map(sr => {
            const evalTexts = {
              'excellent': isTr ? "Mükemmel ilerleme kaydediyor. Ders materyallerini kavraması çok yüksek seviyede." : "Making excellent progress. Comprehension of course materials is at a very high level.",
              'good': isTr ? "Genel performansı iyi durumda, ancak bazı konularda küçük pratik eksikleri var." : "General performance is good, but shows minor gaps in core topics.",
              'fluctuating': isTr ? "Öğrenme sürecinde dalgalanmalar yaşıyor. Eksik konularda tekrar yapması faydalı olacaktır." : "Experiencing fluctuations in learning. Would benefit from reviewing weaker topics.",
              'inactive': isTr ? "Henüz platformda yeterli etkinlik tamamlamamış. Katılımının teşvik edilmesi gerekiyor." : "Has not yet completed enough activities. Class participation needs encouragement.",
              'critical': isTr ? "Ciddi anlama zorlukları yaşıyor ve acil öğretmen desteğine ihtiyacı var." : "Experiencing severe comprehension difficulties and needs urgent teacher support."
            };
            const evalText = evalTexts[sr.eval_code] || (isTr ? 'Veri yetersiz.' : 'Insufficient data.');
            return '<div style="background: var(--bg-secondary); border: 1px solid var(--border); padding: 15px; border-radius: 8px;"><div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;"><strong style="font-size: 15px;">' + esc(sr.name) + '</strong><span style="font-size: 13px; font-weight: 600; padding: 4px 8px; border-radius: 12px; background: ' + (sr.overall_mastery >= 0.75 ? 'var(--success-bg)' : (sr.overall_mastery < 0.5 ? 'var(--danger-bg)' : 'var(--warning-bg)')) + '; color: ' + (sr.overall_mastery >= 0.75 ? 'var(--success)' : (sr.overall_mastery < 0.5 ? 'var(--danger)' : 'var(--warning)')) + ';">' + Math.round(sr.overall_mastery * 100) + '%</span></div><p style="margin: 0; font-size: 14px; color: var(--text-secondary); line-height: 1.5;">' + evalText + '</p></div>';
          }).join('') || '<p style="color:var(--text-muted)">' + L.noStudents + '</p>'}
        </div>
      </div>
    </div>
  `;
}

async function initStudent() {
  document.getElementById('student-nav-username').textContent = currentUser.name;
  document.getElementById('student-greeting').textContent = '¡Hola, ' + currentUser.name + '!';
  await loadStudentHome();
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
  const isTr = currentLang === 'tr';
  const url = currentUser.role === 'lecturer'
    ? `/assignments?course_id=${courseId}`
    : `/assignments?course_id=${courseId}&student_id=${currentUser.id}`;
  const assignments = await api(url);
  const container = currentUser.role === 'lecturer'
    ? document.getElementById('assignment-list')
    : document.getElementById('student-assignment-list');
  if (!container) return;

  if (!assignments || assignments.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted);padding:20px;text-align:center">${isTr ? 'Henüz ödev oluşturulmadı.' : 'No assignments yet.'}</p>`;
    return;
  }

  if (currentUser.role === 'lecturer') {
    container.innerHTML = assignments.map(a => `
      <div class="card" style="margin-bottom:12px">
        <div class="card-body flex-between">
          <div style="flex:1">
            <strong style="font-size:15px">${esc(a.title)}</strong>
            <div style="font-size:13px;color:var(--text-muted);margin-top:4px">
              ${isTr ? 'Oluşturulma' : 'Created'}: ${new Date(a.created_at).toLocaleDateString()}
              ${a.due_at ? ' · Due: ' + new Date(a.due_at).toLocaleDateString() : ''}
            </div>
          </div>
          <div style="display:flex;gap:8px;align-items:center;margin-left:12px">
            <button class="btn btn-outline btn-sm" onclick="previewAssignment('${a.id}','${esc(a.title)}')">
              👁️ ${isTr ? 'Önizle' : 'Preview'}
            </button>
            <button class="btn btn-outline btn-sm" onclick="viewAssignment('${a.id}','${esc(a.title)}')">
              📊 ${isTr ? 'Sonuçları Gör' : 'View Results'}
            </button>
            <button class="btn btn-sm" style="background:var(--danger-bg,#fde8e8);color:var(--danger);border:1px solid var(--danger)" onclick="deleteAssignment('${a.id}','${esc(a.title)}')">
              🗑️ ${isTr ? 'Sil' : 'Delete'}
            </button>
          </div>
        </div>
      </div>`).join('');
  } else {
    container.innerHTML = assignments.map(a => {
      const done = a.is_completed;
      return `
        <div class="card" style="margin-bottom:12px;cursor:${done ? 'default' : 'pointer'}" onclick="${done ? '' : `takeAssignment('${a.id}')`}">
          <div class="card-body flex-between">
            <div>
              <strong style="font-size:15px">${esc(a.title)}</strong>
              <div style="font-size:13px;color:var(--text-muted);margin-top:4px">
                ${done ? (isTr ? '✅ Tamamlandı' : '✅ Completed') : (isTr ? '📝 Başlamak için tıkla' : '📝 Click to start')}
              </div>
            </div>
            <span class="nav-badge" style="background:${done ? 'var(--success-bg)' : 'var(--warning-bg)'};color:${done ? 'var(--success)' : 'var(--warning)'}">${done ? (isTr ? 'Tamam' : 'Done') : (isTr ? 'Bekliyor' : 'Pending')}</span>
          </div>
        </div>`;
    }).join('');
  }
}

async function deleteAssignment(assignmentId, title) {
  const isTr = currentLang === 'tr';
  const msg = isTr
    ? `"${title}" ödevini silmek istediğinize emin misiniz? Bu işlem geri alınamaz ve öğrenci teslimleri de silinir.`
    : `Are you sure you want to delete the assignment "${title}"? This cannot be undone and all student submissions will be removed.`;
  if (!confirm(msg)) return;
  const res = await api('/assignment/delete', { method: 'POST', body: { assignment_id: assignmentId } });
  if (res && !res.error) loadAssignmentList();
}

async function viewAssignment(assignmentId, title) {
  const modal = document.getElementById('student-detail-modal');
  modal.classList.remove('hidden');
  document.getElementById('student-detail-body').innerHTML =
    `<div style="text-align:center;padding:40px;color:var(--text-muted)">Loading...</div>`;

  const data = await api('/assignment/responses?assignment_id=' + assignmentId);
  const isTr = currentLang === 'tr';
  const results = data.student_results || [];

  // Class average
  const classAvg = results.length
    ? Math.round(results.reduce((s, r) => s + r.average_score, 0) / results.length * 100)
    : 0;

  const L = {
    noResponses: isTr ? 'Henüz hiçbir öğrenci bu ödevi teslim etmedi.' : 'No students have submitted this assignment yet.',
    submitted: isTr ? 'teslim etti' : 'submitted',
    classAvg: isTr ? 'Sınıf Ort.' : 'Class Avg',
    correct: isTr ? 'Doğru' : 'Correct',
    studentAnswer: isTr ? 'Öğrenci Cevabı' : "Student's Answer",
    correctAnswer: isTr ? 'Doğru Cevap' : 'Correct Answer',
    expand: isTr ? 'Detayları gör' : 'View details'
  };

  document.getElementById('student-detail-body').innerHTML = `
    <h2 style="margin-bottom:4px">📋 ${title}</h2>
    <div style="color:var(--text-muted);font-size:14px;margin-bottom:20px">
      ${data.total_questions} ${isTr ? 'soru' : 'questions'} &nbsp;·&nbsp;
      ${results.length} ${L.submitted}
    </div>

    ${results.length > 0 ? `
    <!-- Summary bar -->
    <div style="display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap">
      <div style="flex:1;min-width:100px;background:var(--bg-input);border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center">
        <div style="font-size:11px;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin-bottom:4px">${isTr ? 'Teslim Eden' : 'Submitted'}</div>
        <div style="font-size:26px;font-weight:700">${results.length}</div>
      </div>
      <div style="flex:1;min-width:100px;background:var(--bg-input);border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center">
        <div style="font-size:11px;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin-bottom:4px">${L.classAvg}</div>
        <div style="font-size:26px;font-weight:700;color:${masteryColor(classAvg/100)}">${classAvg}%</div>
      </div>
      <div style="flex:1;min-width:100px;background:var(--bg-input);border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center">
        <div style="font-size:11px;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin-bottom:4px">${isTr ? 'En Yüksek' : 'Top Score'}</div>
        <div style="font-size:26px;font-weight:700;color:var(--success)">${Math.round(results[0].average_score * 100)}%</div>
      </div>
    </div>

    <!-- Score bar chart -->
    <div style="margin-bottom:24px">
      ${results.map((sr, i) => {
        const pct = Math.round(sr.average_score * 100);
        const correctCount = sr.answers.filter(a => a.is_correct).length;
        return `
        <div style="margin-bottom:6px">
          <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:3px">
            <span style="font-weight:500">
              ${i === 0 ? '🏆 ' : i === 1 ? '🥈 ' : i === 2 ? '🥉 ' : ''}
              ${esc(sr.student_name)}
            </span>
            <span style="color:${masteryColor(sr.average_score)};font-weight:700">${pct}%
              <span style="color:var(--text-muted);font-weight:400">(${correctCount}/${data.total_questions} ${L.correct.toLowerCase()})</span>
            </span>
          </div>
          <div style="background:var(--border);border-radius:4px;height:8px;cursor:pointer" onclick="this.parentElement.nextElementSibling.style.display=this.parentElement.nextElementSibling.style.display==='none'?'block':'none'">
            <div style="background:${masteryColor(sr.average_score)};height:8px;border-radius:4px;width:${pct}%;transition:width 0.6s ease"></div>
          </div>
        </div>
        <!-- Expandable detail -->
        <div style="display:none;margin-bottom:16px;border:1px solid var(--border);border-radius:8px;overflow:hidden">
          <div style="padding:12px 14px;background:var(--bg-secondary);font-size:12px;font-weight:600;text-transform:uppercase;color:var(--text-muted);letter-spacing:0.5px">
            ${esc(sr.student_name)} — ${isTr ? 'Detaylı Cevaplar' : 'Detailed Answers'}
          </div>
          ${sr.answers.map((a, qi) => `
            <div style="padding:10px 14px;border-bottom:1px solid var(--border);display:flex;gap:10px;align-items:flex-start;background:var(--bg-card)">
              <span style="min-width:22px;font-size:15px;font-weight:700;color:${a.is_correct ? 'var(--success)' : 'var(--danger)'};margin-top:1px">${a.is_correct ? '✓' : '✗'}</span>
              <div style="flex:1;font-size:13px">
                <div style="margin-bottom:5px;font-weight:500;line-height:1.4">${a.prompt}</div>
                <div style="display:flex;gap:16px;flex-wrap:wrap">
                  <span>${L.studentAnswer}: <strong style="color:${a.is_correct ? 'var(--success)' : 'var(--danger)'}">${a.student_answer === '[STARTED]' ? (currentLang === 'tr' ? '[Boş Bırakıldı]' : '[Left Blank]') : esc(a.student_answer)}</strong></span>
                  ${!a.is_correct ? `<span>${L.correctAnswer}: <strong style="color:var(--success)">${esc(a.correct_answer)}</strong></span>` : ''}
                </div>
              </div>
              <span style="font-size:12px;color:${a.is_correct ? 'var(--success)' : 'var(--danger)'};font-weight:600;white-space:nowrap">${Math.round(a.score*100)}%</span>
            </div>
          `).join('')}
        </div>`;
      }).join('')}
    </div>` : `<p style="color:var(--text-muted);padding:20px;text-align:center">${L.noResponses}</p>`}
  `;
}

async function previewAssignment(aid, title) {
  const modal = document.getElementById('student-detail-modal');
  modal.classList.remove('hidden');
  document.getElementById('student-detail-body').innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-muted)">Loading...</div>`;
  
  const data = await api('/assignment/take?assignment_id=' + aid);
  const isTr = currentLang === 'tr';
  const qs = data.questions || [];
  
  document.getElementById('student-detail-body').innerHTML = `
    <h2 style="margin-bottom:4px">👁️ ${title} - ${isTr ? 'Önizleme' : 'Preview'}</h2>
    <div style="color:var(--text-muted);font-size:14px;margin-bottom:20px">
      ${qs.length} ${isTr ? 'soru' : 'questions'}
    </div>
    <div style="display:flex;flex-direction:column;gap:12px">
      ${qs.map((q, i) => `
        <div style="padding:16px;border:1px solid var(--border);border-radius:8px;background:var(--bg-card)">
          <div style="font-size:12px;font-weight:600;color:var(--text-muted);margin-bottom:8px;text-transform:uppercase">
            ${isTr ? 'Soru' : 'Question'} ${i+1} • ${translateOption(q.type === 'mcq' ? 'Multiple Choice' : 'Fill in the Blank')}
          </div>
          <div style="font-size:15px;margin-bottom:12px">${translatePrompt(q.prompt)}</div>
          ${q.type === 'mcq' ? `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              ${(q.distractors||[]).concat([q.answer]).map(o => `
                <div style="padding:8px 12px;background:var(--bg-input);border-radius:4px;font-size:13px;border:1px solid ${o === q.answer ? 'var(--success)' : 'var(--border)'};color:${o === q.answer ? 'var(--success)' : 'inherit'};font-weight:${o === q.answer ? '600' : 'normal'}">
                  ${o === q.answer ? '✓ ' : ''}${translateOption(o)}
                </div>
              `).join('')}
            </div>
          ` : `
            <div style="padding:8px 12px;background:var(--bg-input);border-radius:4px;font-size:13px;border:1px solid var(--success);color:var(--success);font-weight:600;display:inline-block">
              ✓ ${q.answer}
            </div>
          `}
        </div>
      `).join('')}
    </div>
  `;
}

async function createAssignment() {
  const btn = event.target;
  const originalText = btn.textContent;
  btn.textContent = '...';
  btn.disabled = true;

  const title = document.getElementById('assignment-title').value || 'Assignment';
  const chapterId = document.getElementById('assignment-chapter-select').value || null;
  const count = parseInt(document.getElementById('assignment-count').value) || 10;
  
  const res = await api('/draft/generate', { method: 'POST', body: { course_id: courseId, chapter_id: chapterId, count } });
  
  btn.textContent = originalText;
  btn.disabled = false;
  
  if(res && res.questions) {
    currentDraft = {
      type: 'assignment',
      title: title,
      chapter_id: chapterId,
      due_at: null,
      questions: res.questions
    };
    openDraftModal();
  }
}

function openDraftModal() {
  const modal = document.getElementById('draft-modal');
  modal.classList.remove('hidden');
  renderDraftList();
}

function closeDraftModal() {
  document.getElementById('draft-modal').classList.add('hidden');
  currentDraft = null;
}

function renderDraftList() {
  const container = document.getElementById('draft-body');
  
  let html = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
      <h2 style="margin:0">${t('draft.review')} - ${esc(currentDraft.title)}</h2>
      <div>
        <button class="btn btn-outline btn-sm" onclick="showAddCustomQuestionForm()">➕ ${t('draft.add_question')}</button>
        <button class="btn btn-primary btn-sm" onclick="publishDraft()">✅ ${t('draft.publish')}</button>
      </div>
    </div>
    <div id="custom-question-form" class="card hidden" style="margin-bottom:16px; border:2px solid var(--primary);">
      <div class="card-body">
        <div class="form-group">
          <label>${t('draft.type')}</label>
          <select id="cq-type" class="select-input">
            <option value="mcq">${t('draft.mcq')}</option>
            <option value="fill_blank">${t('draft.fill_blank')}</option>
          </select>
        </div>
        <div class="form-group">
          <label>${t('draft.prompt')}</label>
          <input type="text" id="cq-prompt" class="text-input" placeholder="Ej: La capital de España es ___">
        </div>
        <div class="form-group">
          <label>${t('draft.answer')}</label>
          <input type="text" id="cq-answer" class="text-input" placeholder="Madrid">
        </div>
        <div class="form-group" id="cq-distractors-group">
          <label>${t('draft.distractors')}</label>
          <input type="text" id="cq-distractors" class="text-input" placeholder="Barcelona, Sevilla, Valencia">
        </div>
        <div style="display:flex; gap:8px; margin-top:12px;">
          <button class="btn btn-primary btn-sm" onclick="saveCustomQuestion()">${t('draft.save')}</button>
          <button class="btn btn-ghost btn-sm" onclick="document.getElementById('custom-question-form').classList.add('hidden')">${t('draft.cancel')}</button>
        </div>
      </div>
    </div>
    <div style="max-height: 60vh; overflow-y: auto; padding-right:8px;">
  `;
  
  currentDraft.questions.forEach((q, i) => {
    html += `
      <div class="card" style="margin-bottom:12px; position:relative;">
        <button class="btn btn-ghost btn-sm" style="position:absolute; top:8px; right:8px; color:var(--danger);" onclick="removeDraftQuestion(${i})">🗑️ ${t('draft.remove')}</button>
        <div class="card-body">
          <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">${i+1}. ${q.type === 'mcq' ? t('draft.mcq') : t('draft.fill_blank')}</div>
          <div style="font-weight:600; margin-bottom:8px;">${esc(q.prompt)}</div>
          <div style="color:var(--success); font-size:14px; margin-bottom:4px;">✓ ${esc(q.answer)}</div>
          ${q.type === 'mcq' && q.distractors && q.distractors.length > 0 ? `<div style="color:var(--danger); font-size:13px;">✗ ${q.distractors.join(', ')}</div>` : ''}
        </div>
      </div>
    `;
  });
  
  html += `</div>`;
  container.innerHTML = html;
  
  // Show/hide distractors based on type
  document.getElementById('cq-type')?.addEventListener('change', (e) => {
    if(e.target.value === 'fill_blank') {
      document.getElementById('cq-distractors-group').style.display = 'none';
    } else {
      document.getElementById('cq-distractors-group').style.display = 'block';
    }
  });
}

function showAddCustomQuestionForm() {
  const form = document.getElementById('custom-question-form');
  form.classList.remove('hidden');
  document.getElementById('cq-prompt').value = '';
  document.getElementById('cq-answer').value = '';
  document.getElementById('cq-distractors').value = '';
}

function saveCustomQuestion() {
  const type = document.getElementById('cq-type').value;
  const prompt = document.getElementById('cq-prompt').value.trim();
  const answer = document.getElementById('cq-answer').value.trim();
  const dist = document.getElementById('cq-distractors').value;
  
  if(!prompt || !answer) {
    alert('Prompt and Answer are required.');
    return;
  }
  
  const distArray = type === 'mcq' && dist ? dist.split(',').map(s => s.trim()).filter(Boolean) : [];
  
  currentDraft.questions.unshift({
    id: 'new_' + Date.now(),
    type: type,
    prompt: prompt,
    answer: answer,
    distractors: distArray
  });
  
  renderDraftList();
}

function removeDraftQuestion(index) {
  currentDraft.questions.splice(index, 1);
  renderDraftList();
}

async function publishDraft() {
  if(!currentDraft || currentDraft.questions.length === 0) {
    alert('You need at least 1 question to publish.');
    return;
  }
  
  const btn = event.target;
  const originalText = btn.textContent;
  btn.textContent = '...';
  btn.disabled = true;
  
  const res = await api('/draft/publish', {
    method: 'POST',
    body: currentDraft
  });
  
  btn.textContent = originalText;
  btn.disabled = false;
  
  if(!res.error) {
    closeDraftModal();
    if(currentDraft.type === 'quiz') {
      document.getElementById('quiz-title').value = '';
      loadQuizList();
    } else {
      document.getElementById('assignment-title').value = '';
      loadAssignmentList();
    }
  } else {
    alert(res.error);
  }
}

async function takeAssignment(aid) {
  const isTr = currentLang === 'tr';
  const title = isTr ? 'Ödeve Başla' : 'Start Assignment';
  const msg = isTr ? 'Emin misiniz? Ödeve başladıktan sonra geri dönemezsiniz, yarıda bırakmak yarım teslim yapmanıza sebep olabilir.' : 'Are you sure? Once you start, you cannot go back or cancel without submitting.';
  const confirmed = await showConfirmModal(title, msg);
  if (!confirmed) return;

  const data = await api(`/assignment/take?assignment_id=${aid}&student_id=${currentUser.id}`);
  if (data.error) {
    alert(data.error);
    loadAssignmentList();
    return;
  }
  
  const area = document.getElementById('assignment-taking-area');
  area.classList.remove('hidden');
  area.dataset.assignmentId = aid;
  area.dataset.questions = JSON.stringify(data.questions);
  area.dataset.current = '0';
  area.dataset.answers = '{}';
  showAssignmentQuestion(area);
}


function showAssignmentQuestion(area) {
  const qs = JSON.parse(area.dataset.questions);
  const idx = parseInt(area.dataset.current);
  const isTr = currentLang === 'tr';

  if (idx >= qs.length) return submitAssignment(area);

  const q = qs[idx];
  const total = qs.length;
  const pct = Math.round((idx / total) * 100);

  let answerHTML;
  if (q.type === 'mcq') {
    const options = (q.distractors || []).concat([q.answer]).sort(() => Math.random() - 0.5);
    answerHTML = `<div class="options-grid" style="margin-top:16px">
      ${options.map(o => `<button class="option-btn" onclick="assignmentAnswer('${esc(o)}')"
        style="text-align:left;padding:14px 18px;font-size:14px">${translateOption(o)}</button>`).join('')}
    </div>`;
  } else {
    answerHTML = `<div style="margin-top:16px;display:flex;gap:10px;align-items:center">
      <input id="as-inp" class="fill-blank-input" placeholder="${isTr ? 'Cevabınızı yazın...' : 'Type your answer...'}"
        style="flex:1;font-size:15px" onkeydown="if(event.key==='Enter')assignmentAnswer(this.value)">
      <button class="btn btn-primary" onclick="assignmentAnswer(document.getElementById('as-inp').value)">
        ${isTr ? 'Gönder' : 'Submit'} →
      </button>
    </div>
    ${q.hint ? `<div style="margin-top:8px;font-size:13px;color:var(--text-muted)">💡 ${q.hint}</div>` : ''}`;
  }

  area.innerHTML = `
    <div style="padding:20px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <span style="font-size:13px;color:var(--text-muted)">${isTr ? 'Soru' : 'Question'} ${idx + 1} / ${total}</span>
        <button class="btn btn-ghost btn-sm"
          onclick="if(confirm('${isTr ? 'Ödevi iptal et?' : 'Cancel assignment?'}'))document.getElementById('assignment-taking-area').classList.add('hidden')">
          ${isTr ? 'İptal' : 'Cancel'}
        </button>
      </div>
      <div style="background:var(--border);border-radius:4px;height:6px;margin-bottom:24px">
        <div style="background:var(--accent);height:6px;border-radius:4px;width:${pct}%;transition:width 0.3s"></div>
      </div>
      <div class="activity-type-label" style="margin-bottom:10px">
        ${translateOption(q.type === 'mcq' ? 'Multiple Choice' : 'Fill in the Blank')}
      </div>
      <div class="activity-prompt" style="font-size:16px;line-height:1.6">${translatePrompt(q.prompt)}</div>
      ${answerHTML}
    </div>`;

  if (q.type !== 'mcq') setTimeout(() => document.getElementById('as-inp')?.focus(), 100);
}

function assignmentAnswer(ans) {
  if (!ans || !ans.trim()) return;
  const area = document.getElementById('assignment-taking-area');
  const answers = JSON.parse(area.dataset.answers);
  const qs = JSON.parse(area.dataset.questions);
  const idx = parseInt(area.dataset.current);
  answers[qs[idx].id] = ans.trim();
  area.dataset.answers = JSON.stringify(answers);
  area.dataset.current = String(idx + 1);
  showAssignmentQuestion(area);
}

async function submitAssignment(area) {
  const isTr = currentLang === 'tr';
  const aid = area.dataset.assignmentId;
  const answers = JSON.parse(area.dataset.answers);

  area.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-muted)">
    ${isTr ? 'Gönderiliyor...' : 'Submitting...'}
  </div>`;

  try {
    const result = await api('/assignment/submit', {
      method: 'POST',
      body: { assignment_id: aid, student_id: currentUser.id, answers }
    });
    const pct = Math.round((result.average || 0) * 100);
    area.innerHTML = `
      <div style="padding:40px;text-align:center">
        <div style="font-size:48px;margin-bottom:16px">${pct >= 70 ? '🎉' : '📚'}</div>
        <h2 style="margin-bottom:8px">${isTr ? 'Ödev Tamamlandı!' : 'Assignment Complete!'}</h2>
        <div style="font-size:36px;font-weight:700;color:${pct >= 70 ? 'var(--success)' : 'var(--warning)'};margin:16px 0">${pct}%</div>
        <p style="color:var(--text-muted);margin-bottom:24px">${isTr ? 'Puanın kaydedildi.' : 'Your score has been recorded.'}</p>
        <button class="btn btn-primary"
          onclick="document.getElementById('assignment-taking-area').classList.add('hidden');loadAssignmentList()">
          ${isTr ? 'Ödevlere Dön' : 'Back to Assignments'}
        </button>
      </div>`;
  } catch(e) {
    area.innerHTML = `<div style="padding:20px;color:var(--danger);text-align:center">
      ${isTr ? 'Hata oluştu, tekrar deneyin.' : 'An error occurred. Please try again.'}
      <br><button class="btn btn-outline" style="margin-top:12px"
        onclick="document.getElementById('assignment-taking-area').classList.add('hidden')">
        ${isTr ? 'Geri Dön' : 'Go Back'}
      </button>
    </div>`;
  }
}

