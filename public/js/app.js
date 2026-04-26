// ── State & i18n ──
let currentUser = null;
let courseId = null;
let curriculum = [];
let currentCourse = null;
let currentLang = localStorage.getItem('aula_lang') || 'en';
window.currentLang = currentLang;
let aiStatus = null;
let _lastVersion = -1;
let _syncInterval = null;
let _buildingCourses = [];
let _lastActivityData = null;
let _lastOverviewData = null;
let _lastCurriculumData = null;
let _lastQuizListData = null;
let _lastAssignmentListData = null;
let _lastStudentRosterData = null;
let _lastStudentHomeData = null;
let _lastClassroomsData = null;
let _lastStudentDetailData = null;

// ── Keep Render alive (ping every 10 min) ──
setInterval(() => fetch('/api/courses').catch(() => { }), 10 * 60 * 1000);

// ── Live-sync: poll for data changes every 1 second ──
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
        const statusCheck = await api('/user/status?user_id=' + currentUser.id + (currentUser.course_id ? '&course_id=' + currentUser.course_id : ''));
        if (statusCheck && statusCheck.error === 'User not found') {
          await showAlert(t('alert.session_ended'), t('alert.account_removed'), true);
          logout();
          return;
        }

        refreshCurrentView();
      }
    } catch (e) { /* ignore network errors */ }
  }, 1000);
}

function stopLiveSync() {
  if (_syncInterval) { clearInterval(_syncInterval); _syncInterval = null; }
}

function refreshCurrentView() {
  if (!currentUser) return;

  // Track building status for notifications and UI updates
  api('/courses').then(courses => {
    if (!courses || !Array.isArray(courses)) return;
    const currentlyBuilding = courses.filter(c => c.is_building === 1).map(c => c.id);

    // Auto-update building banner if we're inside a classroom
    if (currentCourse) {
      const updated = courses.find(c => c.id === currentCourse.id);
      if (updated) {
        currentCourse = updated;
        const buildBanner = document.getElementById(currentUser.role === 'lecturer' ? 'lecturer-building-banner' : 'student-building-banner');
        if (buildBanner) {
          if (currentCourse.is_building) buildBanner.classList.remove('hidden');
          else buildBanner.classList.add('hidden');
        }
      }
    }

    _buildingCourses.forEach(id => {
      if (!currentlyBuilding.includes(id)) {
        const course = courses.find(c => c.id === id);
        if (course) {
          showAlert(t('Tebrikler!'), `"${course.name}" ${t('is ready!')}`);
          // Force a list refresh to show the "Enter" button
          if (document.getElementById('classroom-selection-screen').classList.contains('active')) {
            showClassroomSelection();
          }
        }
      }
    });
    _buildingCourses = currentlyBuilding;
  });

  if (document.getElementById('waiting-room-screen').classList.contains('active')) {
    window.location.reload();
    return;
  }
  if (currentUser.role === 'lecturer') {
    if (document.getElementById('classroom-selection-screen').classList.contains('active')) {
      showClassroomSelection();
    }
    loadOverview();
    loadQuizList();
    loadAssignmentList();
    loadStudentRoster();
    if (currentCourse) {
      api('/messages?course_id=' + currentCourse.id).then(messages => {
        if (messages && Array.isArray(messages)) {
          const unread = messages.filter(m => !m.is_read && m.sender === 'student').length;
          const badge = document.getElementById('inbox-badge');
          if (badge) {
            if (unread > 0) {
              badge.style.display = 'flex';
              badge.textContent = unread;
            } else {
              badge.style.display = 'none';
            }
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
    }
  } else {
    loadStudentHome();
    loadQuizList();
    loadAssignmentList();
    loadStudentProgress();
    if (currentCourse) {
      api(`/messages?student_id=${currentUser.id}&course_id=${currentCourse.id}`).then(messages => {
        if (messages && Array.isArray(messages)) {
          const unread = messages.filter(m => !m.is_read && m.sender === 'lecturer').length;
          const badge = document.getElementById('message-badge');
          if (badge) {
            if (unread > 0) {
              badge.style.display = 'flex';
              badge.textContent = unread;
            } else {
              badge.style.display = 'none';
            }
          }
          if (document.getElementById('tab-s-messages') && document.getElementById('tab-s-messages').classList.contains('active')) {
            loadStudentChat();
          }
        }
      });
    }
  }
}

const i18n = {
  en: {
    langBtn: '🌐 TR',
    // Login screen
    signInTab: 'Sign In', registerTab: 'Register', welcomeBack: 'Welcome back', signInHint: 'Sign in to continue', emailLabel: 'Email', passwordLabel: 'Password', signInBtn: 'Sign In', joinClass: 'Join the Class', registerHint: 'Create a student account', nameLabel: 'Full Name', registerBtn: 'Create Account', lecturerAccess: 'Lecturer Access', signOut: 'Sign Out', rememberMe: 'Remember Me',
    loginTitle: 'Student Login',
    'Lecturer Login': 'Lecturer Login', 'Sign in with your email and password': 'Sign in with your email and password',
    'Student Login': 'Student Login', 'Log in with your student number': 'Log in with your student number',
    'Student Number': 'Student Number', '(required)': '(required)',
    'Your Full Name': 'Your Full Name', 'e.g. 2021123456': 'e.g. 2021123456',
    'login.class_code': 'Classroom Code (5 digits)', 'login.class_code_placeholder': 'e.g. 12345',
    'login.student_number': 'Student Number',
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
    completed: 'Completed', 'Created': 'Created',
    // Assignments
    'Assignment Management': 'Assignment Management', 'Assign homework to your students': 'Assign homework to your students',
    '➕ Create New Assignment': '➕ Create New Assignment', 'Assignment Title': 'Assignment Title',
    'Create Assignment': 'Create Assignment', 'Your homework tasks': 'Your homework tasks',
    // Students
    'Student Roster': 'Student Roster', 'Monitor individual student progress': 'Monitor individual student progress',
    Kick: 'Kick', 'Mastery:': 'Mastery:', responses: 'responses',
    // Reports
    'report.title': 'Weekly Report', 'report.subtitle': 'AI-generated class performance analysis', 'report.generate': '🔄 Report',
    'Content Map': 'Content Map', 'You': 'You',
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
    'draft.mcq': 'Multiple Choice',
    // Classroom Selection
    'class.selection': 'Classroom Selection',
    'class.subtitle': 'Select a classroom to manage or create a new one',
    'class.create': 'Create New Classroom from PDF',
    'class.enter': 'Enter Classroom',
    'class.delete_confirm': 'Are you sure you want to delete this classroom? All data including students, grades, and content will be permanently removed.',
    'class.upload_pdf': 'Upload PDF Textbook',
    'class.toc_range': 'Contents Page Range (e.g. 2-5)',
    'class.toc_placeholder': '2-5',
    'class.processing': 'Processing PDF & generating curriculum... This may take a minute.',
    'class.start_pipeline': 'Start Pipeline',
    'class.toc_manual': '2. Manual Curriculum / TOC (Paste here)',
    'class.toc_manual_hint': "Paste the book's contents or your syllabus. The AI will use this as a roadmap.",
    'class.toc_range_hint': 'If you leave this blank, the AI will use the Manual Curriculum above as the primary source.',
    'class.toc_range': '3. PDF Context Range (Optional)',
    'answer': 'answer',
    'responses': 'responses',
    'gen.loading': 'Questions are being generated...',
    'gen.time': 'This may take 5-10 seconds.',
    'Unit': 'Unit',
    'SelectTopic': 'Select a topic...',
    'AllChapters': 'All chapters',
    'ok': 'OK',
    'cancel': 'Cancel',
    'no_messages': 'No messages.',
    'prac.dialogue': 'Dialogue',
    'confirm.delete_classroom': 'Delete Classroom',
    'confirm.delete_classroom_msg': 'Are you sure you want to delete the classroom "{name}"?',
    'confirm.delete_quiz': 'Delete Quiz',
    'confirm.delete_quiz_msg': 'Are you sure you want to delete the quiz "{title}"?',
    'confirm.delete_assignment': 'Delete Assignment',
    'confirm.delete_assignment_msg': 'Are you sure you want to delete the assignment "{title}"?',
    'confirm.kick_student_title': 'Kick Student',
    'confirm.kick_student_msg': 'Are you sure you want to kick {name} from the class?',
    'confirm.erase_all_title': 'ERASE ALL DATA',
    'confirm.erase_all_msg1': 'This will permanently remove all student accounts, results, and mastery data. The curriculum will stay. Are you sure?',
    'confirm.erase_all_msg2': 'LAST WARNING: Type "ERASE ALL DATA" to confirm absolute deletion.',
    'View Classrooms': 'View Classrooms',
    'View': 'View',
    'alert.session_ended': 'Session Ended',
    'alert.account_removed': 'Your account has been removed or logged out.',
    'error': 'Error',
    'success': 'Success',
    'missing_info': 'Missing Info',
    'gen.preparing': 'Preparing Classroom...',
    'gen.building': 'Building Lessons...',
    'gen.please_wait': 'Please Wait',
    'assign.no_responses': 'No students have submitted this assignment yet.',
    'assign.submitted': 'submitted',
    'assign.class_avg': 'Class Avg',
    'assign.correct': 'Correct',
    'assign.student_answer': "Student's Answer",
    'assign.correct_answer': 'Correct Answer',
    'assign.view_details': 'View details',
    'assign.top_score': 'Top Score',
    'assign.detailed_answers': 'Detailed Answers',
    'assign.left_blank': '[Left Blank]',
    'assign.preview': 'Preview',
    'assign.complete': 'Assignment Complete!',
    'assign.recorded': 'Your score has been recorded.',
    'assign.back': 'Back to Assignments',
    'assign.retry': 'An error occurred. Please try again.',
    'assign.type_answer': 'Type your answer...',
    'question': 'Question',
    'questions': 'questions',
    'unit': 'Unit',
    'submitting': 'Submitting...',
    'go_back': 'Go Back',
    'Dashboard': 'Dashboard',
    'Overview': 'Overview',
    'Curriculum': 'Curriculum',
    'Activities': 'Activities',
    'Quizzes': 'Quizzes',
    'Assignments': 'Assignments',
    'Students': 'Students',
    'Reports': 'Reports',
    'signOut': 'Sign Out',
    'class.name': 'Classroom Name',
    'class.building_msg': 'Your content is still being built from the textbook — check back soon.',
    'class.no_curriculum': 'No curriculum data available for this classroom.',
    'low_mastery': 'Low Mastery',
    'low_engagement': 'Low Engagement',
    'critical_risk': 'Critical Risk',
    'LOW_MASTERY': 'Low Mastery',
    'LOW_ENGAGEMENT': 'Low Engagement',
    'CRITICAL_RISK': 'Critical Risk',
    'UNKNOWN': 'Unknown',
    'class.join_code': 'Join Code',
    'class.unknown': 'Unknown',
    'class.pdf_status_title': '📄 PDF Status Confirmation',
    'class.pdf_status_msg': 'Is the PDF you are about to upload a digital file with selectable text, or a flat scan (scanned image)? Flat scans can lead to distorted outcomes. Are you sure your file has selectable/searchable text?',
    'class.pdf_status_ok': 'Yes, it is searchable',
    'class.pdf_status_cancel': 'No, let me check',
    'draft.lang_warning': 'Note: Question content language is fixed upon generation and will not change with the UI toggle.',
    'message.placeholder': 'Write your message here...',
  },
  tr: {
    langBtn: '🌐 EN',
    ok: 'Tamam',
    cancel: 'İptal',
    'confirm.delete_classroom': 'Sınıfı Sil',
    'confirm.delete_classroom_msg': '"{name}" sınıfını silmek istediğinize emin misiniz?',
    'confirm.delete_quiz': 'Sınavı Sil',
    'confirm.delete_quiz_msg': '"{title}" sınavını silmek istediğinize emin misiniz?',
    'confirm.delete_assignment': 'Ödevi Sil',
    'confirm.delete_assignment_msg': '"{title}" ödevini silmek istediğinize emin misiniz?',
    'confirm.start_assignment_title': 'Ödeve Başla',
    'confirm.start_assignment_msg': 'Emin misiniz? Ödeve başladıktan sonra geri dönemezsiniz, yarıda bırakmak yarım teslim yapmanıza sebep olabilir.',
    'confirm.kick_student_title': 'Öğrenciyi At',
    'confirm.kick_student_msg': '{name} adlı öğrenciyi sınıftan atmak istediğinize emin misiniz?',
    'confirm.erase_all_title': 'TÜM VERİLERİ SİL',
    'confirm.erase_all_msg1': 'Bu işlem tüm öğrenci hesaplarını, sonuçlarını ve başarı verilerini kalıcı olarak silecektir. Müfredat kalacaktır. Emin misiniz?',
    'confirm.erase_all_msg2': 'SON UYARI: Kesin silme işlemini onaylamak için "ERASE ALL DATA" yazın.',
    'View Classrooms': 'Sınıfları Gör',
    'View': 'Görüntüle',
    'alert.session_ended': 'Oturum Kapatıldı',
    'alert.account_removed': 'Hesabınız silindi veya oturumunuz kapatıldı.',
    'error': 'Hata',
    'success': 'Başarılı',
    'missing_info': 'Eksik Bilgi',
    'gen.preparing': 'Hazırlanıyor...',
    'gen.building': 'İçerik Oluşturuluyor...',
    'gen.please_wait': 'Lütfen Bekleyin',
    'assign.no_responses': 'Henüz hiçbir öğrenci bu ödevi teslim etmedi.',
    'assign.submitted': 'teslim etti',
    'assign.class_avg': 'Sınıf Ort.',
    'assign.correct': 'Doğru',
    'assign.student_answer': 'Öğrenci Cevabı',
    'assign.correct_answer': 'Doğru Cevap',
    'assign.view_details': 'Detayları gör',
    'assign.top_score': 'En Yüksek',
    'assign.detailed_answers': 'Detaylı Cevaplar',
    'assign.left_blank': '[Boş Bırakıldı]',
    'assign.preview': 'Önizleme',
    'assign.complete': 'Ödev Tamamlandı!',
    'assign.recorded': 'Puanın kaydedildi.',
    'assign.back': 'Ödevlere Dön',
    'assign.retry': 'Hata oluştu, tekrar deneyin.',
    'assign.type_answer': 'Cevabınızı yazın...',
    'question': 'Soru',
    'questions': 'soru',
    'unit': 'Ünite',
    'submitting': 'Gönderiliyor...',
    'go_back': 'Geri Dön',
    'Dashboard': 'Kontrol Paneli',
    'Overview': 'Genel Bakış',
    'Curriculum': 'Müfredat',
    'Activities': 'Etkinlikler',
    'Quizzes': 'Sınavlar',
    'Assignments': 'Ödevler',
    'Students': 'Öğrenciler',
    'Reports': 'Raporlar',
    'signOut': 'Çıkış Yap',
    'class.name': 'Sınıf Adı',
    'class.building_msg': 'İçeriğiniz hala hazırlanıyor — kısa süre sonra tekrar kontrol edin.',
    'class.no_curriculum': 'Bu sınıf için müfredat verisi bulunamadı.',
    'low_mastery': 'Düşük Başarı',
    'low_engagement': 'Düşük Katılım',
    'critical_risk': 'Kritik Risk',
    'LOW_MASTERY': 'Düşük Başarı',
    'LOW_ENGAGEMENT': 'Düşük Katılım',
    'CRITICAL_RISK': 'Kritik Risk',
    'UNKNOWN': 'Bilinmiyor',
    loginTitle: 'Öğrenci Girişi', signInTab: 'Giriş Yap', registerTab: 'Kayıt Ol', welcomeBack: 'Tekrar Hoş Geldin', signInHint: 'Devam etmek için giriş yapın', emailLabel: 'E-posta', passwordLabel: 'Şifre', signInBtn: 'Giriş Yap', joinClass: 'Sınıfa Katıl', registerHint: 'Öğrenci hesabı oluştur', nameLabel: 'Ad Soyad', registerBtn: 'Hesap Oluştur', lecturerAccess: 'Öğretmen Girişi', signOut: 'Çıkış Yap', rememberMe: 'Beni Hatırla',
    'Lecturer Login': 'Öğretmen Girişi', 'Sign in with your email and password': 'E-posta ve şifrenizle giriş yapın',
    'Student Login': 'Öğrenci Girişi', 'Log in with your student number': 'Öğrenci numaranızla giriş yapın',
    'Student Number': 'Öğrenci Numarası', '(required)': '(ilk girişte gerekli)',
    'Your Full Name': 'Adınız Soyadınız', 'e.g. 2021123456': 'Örn: 2021123456',
    'login.class_code': 'Sınıf Kodu (5 hane)', 'login.class_code_placeholder': 'Örn: 12345',
    'login.student_number': 'Öğrenci Numarası',
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
    completed: 'Tamamlandı', 'Created': 'Oluşturulma',
    // Assignments
    'Assignment Management': 'Ödev Yönetimi', 'Assign homework to your students': 'Öğrencilerinize ödev atayın',
    '➕ Create New Assignment': '➕ Yeni Ödev Oluştur', 'Assignment Title': 'Ödev Başlığı',
    'Create Assignment': 'Ödev Oluştur', 'Your homework tasks': 'Ödev görevleriniz',
    // Students
    'Student Roster': 'Öğrenci Listesi', 'Monitor individual student progress': 'Bireysel öğrenci gelişimini izle',
    Kick: 'At', 'Mastery:': 'Başarı:', responses: 'yanıt',
    // Reports
    'report.title': 'Haftalık Rapor', 'report.subtitle': 'Yapay zeka destekli sınıf performans analizi',
    'report.generate': '🔄 Rapor Oluştur',
    'Content Map': 'İçerik Haritası', 'You': 'Siz', 'Curriculum': 'Müfredat',
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
    'draft.mcq': 'Çoktan Seçmeli',
    // Classroom Selection
    'class.selection': 'Sınıf Seçimi',
    'class.subtitle': 'Yönetmek için bir sınıf seçin veya yeni bir tane oluşturun',
    'class.create': 'PDF\'den Yeni Sınıf Oluştur',
    'class.enter': 'Sınıfa Gir',
    'class.delete_confirm': 'Bu sınıfı silmek istediğinizden emin misiniz? Öğrenciler, notlar ve içerik dahil tüm veriler kalıcı olarak silinecektir.',
    'class.upload_pdf': 'PDF Ders Kitabı Yükle',
    'class.toc_range': 'İçindekiler Sayfa Aralığı (örn. 2-5)',
    'class.toc_placeholder': '2-5',
    'class.processing': 'PDF işleniyor ve müfredat oluşturuluyor... Bu işlem bir dakika sürebilir.',
    'class.start_pipeline': 'İşlemi Başlat',
    'class.toc_manual': '2. Manuel Müfredat / İçindekiler (Buraya yapıştırın)',
    'class.toc_manual_hint': 'Kitabın içindekilerini veya müfredatınızı yapıştırın. Yapay zeka bunu yol haritası olarak kullanacaktır.',
    'class.toc_range_hint': 'Burayı boş bırakırsanız, yapay zeka yukarıdaki Manuel Müfredatı birincil kaynak olarak kullanacaktır.',
    'class.toc_range': '3. PDF İçindekiler Sayfa Aralığı (Opsiyonel)',
    'answer': 'cevaplar',
    'responses': 'sonuçlar',
    'gen.loading': 'Sorular oluşturuluyor...',
    'gen.time': 'Bu işlem 5-10 saniye sürebilir.',
    'Unit': 'Ünite',
    'SelectTopic': 'Bir konu seçin...',
    'AllChapters': 'Tüm üniteler',
    'ok': 'Tamam',
    'cancel': 'İptal',
    'no_classrooms_found': 'Sınıf bulunamadı. İlkini oluşturun!',
    'class.delete_building_msg': 'Oluşturma işlemini durdurmak ve bu sınıfı silmek istediğinize emin misiniz?',
    'You': 'Siz',
    'class.select_topic_msg': 'Lütfen bir konu seçin',
    'draft.required_msg': 'Soru metni ve cevap zorunludur.',
    'draft.no_questions_msg': 'Yayınlamak için en az 1 soru gereklidir.',
    'message.placeholder': 'Mesajınızı buraya yazın...',
    'Read Textbook': 'Kitabı Oku',
    'class.join_code': 'Sınıf Kodu',
    'class.unknown': 'Bilinmiyor',
    'class.pdf_status_title': '📄 PDF Durumu Onayı',
    'class.pdf_status_msg': 'Yükleyeceğeniz PDF dosyası taranmış bir resim (flat scan) mi yoksa seçilebilir metin içeren dijital bir dosya mı? Taranmış resimler hatalı sonuçlara neden olabilir. Dosyanızın metin araması yapılabilir/seçilebilir olduğundan emin misiniz?',
    'class.pdf_status_ok': 'Evet, metin seçilebiliyor',
    'class.pdf_status_cancel': 'Hayır, kontrol edeceğim',
    'no_messages': 'Mesaj yok.',
    'No assignments yet.': 'Henüz ödev yok.',
    'No quizzes yet.': 'Henüz sınav yok.',
    'prac.dialogue': 'Diyalog',
    'draft.lang_warning': 'Not: Soru içeriğinin dili oluşturma sırasında sabitlenir ve arayüz diliyle birlikte değişmez.',
    'message.placeholder': 'Mesajınızı buraya yazın...',
  }
};

function t(key, data = {}) {
  const lang = window.currentLang || 'en';
  let str = (i18n[lang] && i18n[lang][key]) || (i18n['en'] && i18n['en'][key]) || key;
  Object.keys(data).forEach(k => {
    str = str.replace(new RegExp(`{${k}}`, 'g'), data[k]);
  });
  return str;
}

function applyTranslations() {
  // Sync open modal FIRST
  const modal = document.getElementById('confirm-modal');
  if (modal) {
    const titleKey = modal.getAttribute('data-title-key');
    const msgKey = modal.getAttribute('data-msg-key');
    const msgDataStr = modal.getAttribute('data-msg-data');
    let msgData = {};
    try { if (msgDataStr) msgData = JSON.parse(msgDataStr); } catch(e) {}
    
    if (titleKey) document.getElementById('confirm-title').textContent = t(titleKey);
    if (msgKey) document.getElementById('confirm-message').textContent = t(msgKey, msgData);
    
    const okK = modal.getAttribute('data-ok-key');
    const canK = modal.getAttribute('data-cancel-key');
    if (okK) document.getElementById('confirm-ok-btn').textContent = t(okK);
    if (canK) document.getElementById('confirm-cancel-btn').textContent = t(canK);
  }

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const dataStr = el.getAttribute('data-i18n-data');
    let data = {};
    try { if (dataStr) data = JSON.parse(dataStr); } catch(e) {}
    
    const translation = t(key, data);
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      el.placeholder = translation;
    } else {
      el.textContent = translation;
    }
  });

  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.getAttribute('data-i18n-placeholder'));
  });

  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    el.title = t(el.getAttribute('data-i18n-title'));
  });

  const langBtn = document.getElementById('lang-btn');
  if (langBtn) {
    langBtn.setAttribute('data-i18n', 'langBtn');
    langBtn.textContent = t('langBtn');
  }
}

function toggleLanguage() {
  window.currentLang = window.currentLang === 'en' ? 'tr' : 'en';
  localStorage.setItem('aula_lang', window.currentLang);
  applyTranslations();

  // Re-render all dynamic content SYNCHRONOUSLY using cached data
  if (currentUser) {
    if (currentUser.role === 'lecturer') {
      if (currentCourse) {
        renderLecturerSync();
      } else {
        if (_lastClassroomsData) renderClassroomSelection(_lastClassroomsData);
      }
    } else {
      if (currentCourse) {
        renderStudentSync();
      } else {
        if (_lastClassroomsData) renderClassroomSelection(_lastClassroomsData);
      }
    }
  }

  // Re-render activity preview if visible
  const preview = document.getElementById('activity-preview');
  if (preview && !preview.classList.contains('hidden') && _lastActivityData) {
    preview.innerHTML = '<h2 style="margin-bottom:20px">📋 ' + (_lastActivityData.topic?.title||'') + '</h2>' + (_lastActivityData.activities||[]).map((a, i) => renderActivityCard(a, i, 'preview')).join('');
  }

  // Sync the Draft Review modal if open
  renderDraftListSync();
}

function renderDraftListSync() {
  const modal = document.getElementById('draft-modal');
  if (modal && !modal.classList.contains('hidden') && window.currentDraft) {
    renderDraftList();
  }
}

function renderLecturerSync() {
  if (!currentUser) return;
  document.getElementById('nav-username').textContent = currentUser.name;
  document.getElementById('overview-greeting').textContent = t('welcomeBack') + ', ' + currentUser.name.split(' ').pop();
  
  if (_lastOverviewData) renderOverview(_lastOverviewData);
  if (curriculum) renderCurriculum();
  populateSelects();
  if (_lastQuizListData) renderQuizList(_lastQuizListData);
  if (_lastAssignmentListData) renderAssignmentList(_lastAssignmentListData);
  if (_lastStudentRosterData) renderStudentRoster(_lastStudentRosterData);
}

function renderStudentSync() {
  if (!currentUser) return;
  document.getElementById('student-nav-username').textContent = currentUser.name;
  document.getElementById('student-greeting').textContent = t('welcomeBack') + ', ' + currentUser.name + '!';
  
  if (_lastStudentHomeData) renderStudentHome(_lastStudentHomeData);
  if (_lastQuizListData) renderQuizList(_lastQuizListData);
  if (_lastAssignmentListData) renderAssignmentList(_lastAssignmentListData);
  if (_lastStudentHomeData) renderStudentProgress(_lastStudentHomeData);
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

async function completeLogin(user, isFresh = false) {
  currentUser = user;
  if (user.course_id) courseId = user.course_id;
  if (isFresh) {
    localStorage.removeItem('aula_last_tab');
    localStorage.removeItem('aula_last_course');
  }
  const remember = document.getElementById('login-remember') ? document.getElementById('login-remember').checked : true;
  if (remember) localStorage.setItem('aula_user', JSON.stringify(user));
  else sessionStorage.setItem('aula_user', JSON.stringify(user));
  localStorage.setItem('aula_lang', currentLang);

  if (currentUser.status === 'pending') {
    try {
      const check = await api('/user/status?user_id=' + currentUser.id + (currentUser.course_id ? '&course_id=' + currentUser.course_id : ''));
      if (check && check.status === 'approved') {
        currentUser.status = 'approved';
        localStorage.setItem('aula_user', JSON.stringify(currentUser));
        sessionStorage.setItem('aula_user', JSON.stringify(currentUser));
      }
    } catch (e) { }

    if (currentUser.status === 'pending') {
      showScreen('waiting-room-screen');
      const waitingPoll = setInterval(async () => {
        try {
          const check = await api('/user/status?user_id=' + currentUser.id + (currentUser.course_id ? '&course_id=' + currentUser.course_id : ''));
          if (check && check.status === 'approved') {
            clearInterval(waitingPoll);
            currentUser.status = 'approved';
            localStorage.setItem('aula_user', JSON.stringify(currentUser));
            sessionStorage.setItem('aula_user', JSON.stringify(currentUser));
            window.location.reload();
          } else if (check && check.error === 'User not found') {
            clearInterval(waitingPoll);
            await showAlert(t('alert.session_ended'), t('alert.account_removed'), true);
            logout();
          }
        } catch (e) { }
      }, 1000);
      startLiveSync();
      return;
    }
  }

  if (currentUser.role === 'lecturer') {
    const savedCourse = localStorage.getItem('aula_last_course');
    if (savedCourse) {
      await selectClassroom(savedCourse);
    } else {
      showClassroomSelection();
    }
  } else {
    if (currentUser.course_id) {
      await selectClassroom(currentUser.course_id, false);
    } else {
      const savedCourse = localStorage.getItem('aula_last_course');
      if (savedCourse) {
        await selectClassroom(savedCourse, false);
      } else {
        const courses = await api('/courses');
        if (courses && courses.length) {
          await selectClassroom(courses[0].id, false);
        } else {
          showScreen('student-dashboard');
          initStudent();
        }
      }
    }
  }
  startLiveSync();
}

async function showClassroomSelection() {
  localStorage.removeItem('aula_last_course');
  localStorage.removeItem('aula_last_tab');
  showScreen('classroom-selection-screen');
  const courses = await api('/courses?t=' + Date.now());
  _lastClassroomsData = courses;
  renderClassroomSelection(courses);
  applyTranslations();
}

function renderClassroomSelection(courses) {
  const container = document.getElementById('classroom-list');
  if (!container) return;
  if (!courses || courses.length === 0) {
    container.innerHTML = `<p style="grid-column: 1/-1; text-align:center; padding:40px; color:var(--text-muted);">${t('no_classrooms_found')}</p>`;
    return;
  }

  container.innerHTML = courses.map(c => {
    const isSpanish = c.id === 'spanish-101' || c.name === "Spanish 101";
    const isBuilding = c.is_building === 1;
    const isPhase1 = c.language === "Detecting...";

    return `<div class="card classroom-card" style="position:relative; overflow:hidden; display:flex; flex-direction:column; justify-content:space-between; border:1px solid var(--border); opacity: ${isPhase1 ? '0.65' : '1'}; transition: opacity 0.3s ease;">
        ${isBuilding ? '<div style="position:absolute; top:0; left:0; right:0; height:4px; background:linear-gradient(90deg, #6366f1, #a855f7); animation: slide 2s linear infinite;"></div>' : ''}
        <div class="card-body">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                <span style="font-size:12px; font-weight:700; color:var(--accent); text-transform:uppercase; letter-spacing:1px;" data-i18n="${c.language || 'class.unknown'}">${t(c.language) || t('class.unknown')}</span>
                ${!isSpanish ? `<button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); deleteClassroom('${c.id}', '${esc(c.name)}')" style="color:var(--danger); padding:4px;">🗑️</button>` : ''}
            </div>
            <h3 style="font-size:20px; margin-bottom:8px;">${esc(c.name)}</h3>
            <p style="color:var(--text-muted); font-size:14px; margin-bottom:12px;">${esc(c.semester)}</p>
            <div style="background:rgba(255,255,255,0.05); border-radius:8px; padding:8px 12px; margin-bottom:16px; border:1px dashed var(--border); display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:10px; color:var(--text-muted); font-weight:700; text-transform:uppercase;" data-i18n="class.join_code">${t('class.join_code')}</span>
                <span style="font-family:monospace; font-size:16px; color:var(--accent); font-weight:700; letter-spacing:2px;">${c.code}</span>
            </div>
            
            ${isBuilding ? `
              <div class="flex-center" style="margin: 10px 0;">
                <div class="spinner-small" style="border-top-color:var(--accent);"></div>
              </div>
              <p style="color:var(--accent); font-size:12px; font-weight:500; margin-bottom:12px; text-align:center; animation: pulse 1.5s infinite;">
                <span data-i18n="${isPhase1 ? 'gen.preparing' : 'gen.building'}">${isPhase1 ? '⏳ ' + t('gen.preparing') : '⏳ ' + t('gen.building')}</span>
              </p>
            ` : ''}
        </div>
        <button class="btn ${isPhase1 ? 'btn-ghost' : 'btn-outline'} btn-full" ${isPhase1 ? 'disabled' : ''} onclick="selectClassroom('${c.id}')">
            <span data-i18n="${isPhase1 ? 'gen.please_wait' : 'class.enter'}">${isPhase1 ? t('gen.please_wait') : t('class.enter')}</span>
        </button>
    </div>`;
  }).join('');

  if (!document.getElementById('slide-anim')) {
    const style = document.createElement('style');
    style.id = 'slide-anim';
    style.innerHTML = `@keyframes slide { from { transform: translateX(-100%); } to { transform: translateX(100%); } }`;
    document.head.appendChild(style);
  }
  applyTranslations();
}

async function selectClassroom(id, isLecturer = true) {
  // 1. Immediate UI Cleanup to prevent ghosting/flicker
  const activityPreview = document.getElementById('activity-preview');
  if (activityPreview) { activityPreview.classList.add('hidden'); activityPreview.innerHTML = ''; }
  const activitySelect = document.getElementById('activity-topic-select');
  if (activitySelect) activitySelect.value = '';

  ['student-roster', 'pending-roster', 'overview-stats', 'at-risk-list', 'quiz-list', 'student-quiz-list', 'assignment-list', 'student-assignment-list', 'inbox-messages', 'student-chat-history', 'topic-difficulty-chart', 'report-content', 'practice-topics', 'progress-chart'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '';
  });

  // Reset chat/inbox state
  currentChatStudentId = null;
  const inboxBackBtn = document.getElementById('inbox-back-btn');
  if (inboxBackBtn) inboxBackBtn.classList.add('hidden');
  const inboxReplyArea = document.getElementById('inbox-reply-area');
  if (inboxReplyArea) inboxReplyArea.classList.add('hidden');
  const inboxTitle = document.getElementById('inbox-title');
  if (inboxTitle) inboxTitle.innerHTML = `📥 <span data-i18n="inbox">${t('inbox')}</span>`;

  // 2. Fetch course data
  const courses = await api('/courses');
  let course = courses.find(c => c.id === id);

  // Fallback if the course was deleted/consolidated
  if (!course && courses.length > 0) {
    course = courses[0];
    id = course.id;
  }

  courseId = id;
  if (course && document.getElementById('nav-course-name')) {
    document.getElementById('nav-course-name').textContent = course.name;
    const codeEl = document.getElementById('nav-course-code');
    if (codeEl) codeEl.textContent = '#' + course.code;
  }

  // Show building banner if needed
  const buildBanner = document.getElementById(currentUser.role === 'lecturer' ? 'lecturer-building-banner' : 'student-building-banner');
  if (buildBanner) {
    if (course && course.is_building) {
      buildBanner.classList.remove('hidden');
    } else {
      buildBanner.classList.add('hidden');
    }
  }

  currentCourse = course;
  const currData = await api('/curriculum?course_id=' + courseId);
  curriculum = Array.isArray(currData) ? currData : [];

  // Update Book Tab
  let bookPath = course ? course.textbook : '';
  if (course && (course.id === 'spanish-101' || course.name === 'Spanish' || course.name === 'Spanish 101')) {
    bookPath = '/books/textbook.pdf';
  }
  const pdfViewerSrc = (bookPath && bookPath !== '/books/' && bookPath !== '/books/undefined') ? bookPath : '';
  document.querySelectorAll('.pdf-viewer').forEach(el => { el.src = pdfViewerSrc || 'about:blank'; });
  document.querySelectorAll('a[data-tab="book"], a[data-tab="s-book"], .pdf-download-link').forEach(el => {
    if (el.tagName === 'A' && pdfViewerSrc) el.href = pdfViewerSrc;
  });

  if (currentUser.role === 'lecturer') {
    showScreen('lecturer-dashboard');
    const targetTab = localStorage.getItem('aula_last_tab') || 'overview';
    const tabBtn = document.querySelector(`#lecturer-dashboard [data-tab="${targetTab}"]`);
    if (tabBtn) switchTab(tabBtn, true);
    await initLecturer();
  } else {
    showScreen('student-dashboard');
    const targetTab = localStorage.getItem('aula_last_tab') || 's-home';
    const tabBtn = document.querySelector(`#student-dashboard [data-tab="${targetTab}"]`);
    if (tabBtn) switchTab(tabBtn, true);
    await initStudent();
  }

  localStorage.setItem('aula_last_course', id);
}

async function deleteClassroom(id, name) {
  const course = (window.allCourses) ? window.allCourses.find(c => c.id === id) : null;
  const isBuilding = course && course.is_building === 1;
  const msgKey = isBuilding ? 'class.delete_building_msg' : 'confirm.delete_classroom_msg';
  const msgData = isBuilding ? {} : { name };
  
  if (!(await showConfirmModal('confirm.delete_classroom', msgKey, true, null, false, 'ok', 'cancel', msgData))) return;

  const res = await api('/classroom/delete', { method: 'POST', body: { course_id: id } });
  if (res.success) {
    showClassroomSelection();
  } else {
    showAlert(t('error'), res.error || 'Failed to delete classroom', true);
  }
}

async function openCreateClassroomModal() {
  if (await showConfirmModal('class.pdf_status_title', 'class.pdf_status_msg', false, null, false, 'class.pdf_status_ok', 'class.pdf_status_cancel')) {
    document.getElementById('create-classroom-modal').classList.remove('hidden');
  }
  document.getElementById('creation-status').classList.add('hidden');
  document.getElementById('submit-creation-btn').disabled = false;
}

function closeCreateClassroomModal() {
  document.getElementById('create-classroom-modal').classList.add('hidden');
}

async function handleCreateClassroom(e) {
  e.preventDefault();
  const nameInput = document.getElementById('course-name-input');
  const fileInput = document.getElementById('pdf-upload');
  const rangeInput = document.getElementById('toc-range');
  const manualTocInput = document.getElementById('manual-toc-input');
  const statusEl = document.getElementById('creation-status');
  const btn = document.getElementById('submit-creation-btn');

  if (!fileInput.files[0]) return showAlert(t('missing_info'), 'Please select a PDF file', true);

  const formData = new FormData();
  formData.append('course_name', nameInput.value.trim());
  formData.append('pdf', fileInput.files[0]);
  formData.append('toc_range', rangeInput.value);
  formData.append('manual_toc', manualTocInput.value.trim());
  formData.append('lecturer_id', currentUser.id);

  statusEl.classList.remove('hidden');
  btn.disabled = true;
  btn.style.opacity = '0.5';
  btn.style.cursor = 'default';

  try {
    const res = await fetch('/api/classroom/create-from-pdf', {
      method: 'POST',
      body: formData
    });
    data = await res.json();
  } catch (err) {
    console.error('Creation Error:', err);
    stopLiveSync();
    return showAlert(t('error'), t('class.create_failed'), true);
  }
  
  await showAlert(t('success'), `${t('class.create_success')} \n\n${t('class.join_code')}: ${data.code}\n\n${t('class.share_msg')}`);
  statusEl.classList.remove('hidden');
  btn.disabled = false;
  btn.style.opacity = '1';
  btn.style.cursor = 'pointer';

  if (!data.success) {
    return showAlert(t('error'), data.error || (currentLang === 'tr' ? 'Sınıf oluşturulamadı.' : 'Failed to create classroom.'), true);
  }

  // Success path logic (wrapped in a separate try-catch so UI refresh errors don't look like creation errors)
  try {
    await showAlert(t('success'), `${currentLang === 'tr' ? 'Sınıf başarıyla oluşturuldu!' : 'Classroom created successfully!'} \n\n${currentLang === 'tr' ? 'Sınıf Kodu' : 'Classroom Code'}: ${data.code}\n\n${currentLang === 'tr' ? 'Bu kodu öğrencilerinizle paylaşın.' : 'Share this code with your students.'}`);
    closeCreateClassroomModal();

    // Register for completion notification
    if (typeof _buildingCourses !== 'undefined') {
      _buildingCourses.push(data.course_id);
    }

    await showClassroomSelection();

    // If it's still missing from global list (race condition), manually inject it
    if (!Array.isArray(window.allCourses)) { window.allCourses = []; }
    if (!window.allCourses.find(c => c.id === data.course_id)) {
      const ghost = { id: data.course_id, name: data.name, code: data.code, semester: 'Fall 2026', is_building: 1, language: 'Detecting...' };
      window.allCourses.unshift(ghost);
      // Refresh local UI using global state
      const container = document.getElementById('classroom-list');
      if (container) {
        container.innerHTML = window.allCourses.map(c => {
          const isSpanish = c.id === 'spanish-101' || c.name === "Spanish 101";
          const isBuilding = c.is_building === 1;
          return `<div class="card classroom-card" style="position:relative; overflow:hidden; display:flex; flex-direction:column; justify-content:space-between; border:1px solid var(--border); opacity: ${isBuilding ? '0.65' : '1'}; transition: opacity 0.3s ease;">
              ${isBuilding ? '<div style="position:absolute; top:0; left:0; right:0; height:4px; background:linear-gradient(90deg, #6366f1, #a855f7); animation: slide 2s linear infinite;"></div>' : ''}
              <div class="card-body">
                  <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                      <span style="font-size:12px; font-weight:700; color:var(--accent); text-transform:uppercase; letter-spacing:1px;">${t(c.language) || t('class.unknown')}</span>
                      ${(!isSpanish && !isBuilding) ? `<button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); deleteClassroom('${c.id}', '${esc(c.name)}')" style="color:var(--danger); padding:4px;">🗑️</button>` : ''}
                  </div>
                  <h3 style="font-size:20px; margin-bottom:8px;">${esc(c.name)}</h3>
                  <p style="color:var(--text-muted); font-size:14px; margin-bottom:16px;">${esc(c.semester)}</p>
                  
                  ${isBuilding ? `
                    <div class="flex-center" style="margin: 20px 0;">
                      <div class="spinner-small" style="border-top-color:var(--accent);"></div>
                    </div>
                    <p style="color:var(--accent); font-size:12px; font-weight:500; margin-bottom:12px; text-align:center; animation: pulse 1.5s infinite;">⏳ ${t('gen.building')}</p>
                    <button class="btn btn-sm" style="width:100%; color:var(--danger); border:1px solid var(--danger); background:transparent; margin-bottom:8px;" onclick="event.stopPropagation(); deleteClassroom('${c.id}', '${esc(c.name)}')">
                      ✕ ${t('cancel')}
                    </button>
                  ` : ''}
              </div>
              <button class="btn ${isBuilding ? 'btn-ghost' : 'btn-outline'} btn-full" ${isBuilding ? 'disabled' : ''} onclick="selectClassroom('${c.id}')">
                  ${isBuilding ? t('gen.please_wait') : t('class.enter')}
              </button>
          </div>`;
        }).join('');
      }
    }
  } catch (err) {
    console.warn('[CLASSROOM] Post-creation UI refresh failed, but classroom was created:', err);
  }
}

async function handleStudentLogin(e) {
  e.preventDefault();
  const number = document.getElementById('student-number').value.trim();
  const name = document.getElementById('student-name-input').value.trim();
  const code = document.getElementById('classroom-code').value.trim();
  const errEl = document.getElementById('student-login-error');
  errEl.classList.add('hidden');

  const data = await api('/student/login', { method: 'POST', body: { student_number: number, name, classroom_code: code } });
  if (data.error) {
    const isTr = currentLang === 'tr';
    const errorMap = {
      'Name is required': isTr ? 'Ad Soyad alanı zorunludur.' : 'Full name is required.',
      'Name is required for first login': isTr ? 'İlk girişte ad soyad gereklidir.' : 'Full name is required for first login.',
      'Student number and name do not match': isTr ? 'Öğrenci numarası ve isim eşleşmiyor. Lütfen kayıtlı bilgilerinizi giriniz.' : 'Student number and name do not match. Please enter your registered information.',
      'Student number is required': isTr ? 'Öğrenci numarası gereklidir.' : 'Student number is required.',
      'Classroom code is required': isTr ? 'Sınıf kodu gereklidir.' : 'Classroom code is required.',
      'Invalid classroom code': isTr ? 'Geçersiz sınıf kodu.' : 'Invalid classroom code.'
    };
    errEl.textContent = errorMap[data.error] || data.error;
    errEl.classList.remove('hidden');
    return false;
  }
  // On subsequent logins, name field not needed
  await completeLogin(data.user, true);
  return false;
}

async function handleLogin(e) {
  e.preventDefault();
  const data = await api('/login', {
    method: 'POST', body: {
      email: document.getElementById('login-email').value,
      password: document.getElementById('login-password').value
    }
  });
  if (data.error) { document.getElementById('login-error').textContent = data.error; document.getElementById('login-error').classList.remove('hidden'); return false; }
  await completeLogin(data.user, true);
  return false;
}

function logout() {
  currentUser = null;
  _lastVersion = -1;
  stopLiveSync();
  localStorage.removeItem('aula_user');
  sessionStorage.removeItem('aula_user');
  localStorage.removeItem('aula_last_course');
  localStorage.removeItem('aula_last_tab');
  showScreen('login-screen');
}

window.addEventListener('DOMContentLoaded', () => {
  // Force English on refresh per user request
  window.currentLang = 'en';
  applyTranslations();

  // Apply saved theme and HUD size
  const savedTheme = localStorage.getItem('aula_theme') || 'dark';
  setTheme(savedTheme);
  const savedHud = localStorage.getItem('aula_hud') || 'normal';
  setHudSize(savedHud);

  const savedUser = localStorage.getItem('aula_user') || sessionStorage.getItem('aula_user');
  if (savedUser) {
    try { completeLogin(JSON.parse(savedUser)).catch(() => showScreen('login-screen')); }
    catch (e) { showScreen('login-screen'); }
  } else showScreen('login-screen');

  // Add language warnings to creation forms
  const activityBtn = document.querySelector('button[onclick="launchActivity()"]');
  if (activityBtn) {
    const warn = document.createElement('div');
    warn.style.fontSize = '11px'; warn.style.color = 'var(--text-muted)'; warn.style.marginTop = '8px';
    warn.setAttribute('data-i18n', 'draft.lang_warning');
    warn.textContent = t('draft.lang_warning');
    activityBtn.parentNode.appendChild(warn);
  }
  const quizBtn = document.querySelector('button[onclick="createQuiz()"]');
  if (quizBtn) {
    const warn = document.createElement('div');
    warn.style.fontSize = '11px'; warn.style.color = 'var(--text-muted)'; warn.style.marginTop = '8px';
    warn.setAttribute('data-i18n', 'draft.lang_warning');
    warn.textContent = t('draft.lang_warning');
    quizBtn.parentNode.appendChild(warn);
  }
  const assignBtn = document.querySelector('button[onclick="createAssignment()"]');
  if (assignBtn) {
    const warn = document.createElement('div');
    warn.style.fontSize = '11px'; warn.style.color = 'var(--text-muted)'; warn.style.marginTop = '8px';
    warn.setAttribute('data-i18n', 'draft.lang_warning');
    warn.textContent = t('draft.lang_warning');
    assignBtn.parentNode.appendChild(warn);
  }
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

  localStorage.setItem('aula_last_tab', btn.dataset.tab);

  if (!skipLoad) {
    if (btn.dataset.tab === 'inbox') loadInbox();
    if (btn.dataset.tab === 's-messages') loadStudentChat();
  }
}

function goToHome() {
  if (!currentUser) return;
  if (currentUser.role === 'lecturer') {
    const tabBtn = document.querySelector('button[data-tab="overview"]');
    if (tabBtn) switchTab(tabBtn);
  } else {
    const tabBtn = document.querySelector('button[data-tab="s-home"]');
    if (tabBtn) switchTab(tabBtn);
  }
}

function closeModal() { document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden')); }

// ── Messages ──
let currentChatStudentId = null;

async function loadStudentChat() {
  if (!currentCourse) return;
  const messages = await api(`/messages?student_id=${currentUser.id}&course_id=${currentCourse.id}`);
  const container = document.getElementById('student-chat-history');

  if (!messages || messages.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted); text-align:center; padding:20px;" data-i18n="no_messages">${t('no_messages')}</p>`;
    return;
  }

  container.innerHTML = messages.map(m => {
    const isMe = m.sender === 'student';
    // Ensure timestamp is treated as UTC
    const dateObj = new Date(m.created_at.includes('Z') ? m.created_at : m.created_at.replace(' ', 'T') + 'Z');
    return `
      <div style="display:flex; justify-content:${isMe ? 'flex-end' : 'flex-start'};">
        <div style="max-width:80%; background:${isMe ? 'var(--accent)' : 'var(--bg-secondary)'}; color:${isMe ? '#fff' : 'var(--text-primary)'}; border-radius:12px; padding:10px 14px; font-size:14px; box-shadow:0 2px 5px rgba(0,0,0,0.2);">
          ${esc(m.content)}
          <div style="font-size:10px; text-align:right; margin-top:4px; opacity:0.7;">${dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
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
  if (!text || !currentCourse) return;
  document.getElementById('message-text').value = '';
  await api('/message/send', { method: 'POST', body: { 
    student_id: currentUser.id, 
    course_id: currentCourse.id,
    sender: 'student', 
    content: text 
  } });
  await loadStudentChat();
}

async function loadInbox() {
  if (!currentCourse) return;
  const messages = await api(`/messages?course_id=${currentCourse.id}`);
  const container = document.getElementById('inbox-messages');
  document.getElementById('inbox-back-btn').classList.add('hidden');
  document.getElementById('inbox-reply-area').classList.add('hidden');
  document.getElementById('inbox-title').innerHTML = `📥 <span data-i18n="inbox">${t('inbox')}</span>`;
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
    container.innerHTML = `<p style="color:var(--text-muted); text-align:center; padding:20px;" data-i18n="no_messages">${t('no_messages')}</p>`;
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

  const threadList = Object.entries(threads).sort((a, b) => new Date(b[1].latest.created_at) - new Date(a[1].latest.created_at));

  container.innerHTML = threadList.map(([sId, data]) => `
    <div style="background:var(--bg-primary); border:1px solid var(--border); border-radius:8px; padding:12px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; transition:var(--transition);" onclick="openChat('${sId}', '${esc(data.student_name).replace(/'/g, "\\'")}')">
      <div style="flex:1; min-width:0; margin-right:12px;">
        <strong style="font-size:15px; color:var(--text-primary);">${esc(data.student_name)}</strong>
        <div style="font-size:13px; color:var(--text-muted); margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
          ${data.latest.sender === 'lecturer' ? '<span data-i18n="You">' + t('You') + '</span>: ' : ''}${esc(data.latest.content)}
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

  const messages = await api(`/messages?student_id=${studentId}&course_id=${currentCourse.id}`);
  const container = document.getElementById('inbox-messages');

  container.innerHTML = messages.map(m => {
    const isMe = m.sender === 'lecturer';
    const dateObj = new Date(m.created_at.includes('Z') ? m.created_at : m.created_at.replace(' ', 'T') + 'Z');
    return `
      <div style="display:flex; justify-content:${isMe ? 'flex-end' : 'flex-start'};">
        <div style="max-width:80%; background:${isMe ? 'var(--accent)' : 'var(--bg-secondary)'}; color:${isMe ? '#fff' : 'var(--text-primary)'}; border-radius:12px; padding:10px 14px; font-size:14px; box-shadow:0 2px 5px rgba(0,0,0,0.2);">
          ${esc(m.content)}
          <div style="font-size:10px; text-align:right; margin-top:4px; opacity:0.7;">${dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
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
  if (!text || !currentChatStudentId || !currentCourse) return;
  document.getElementById('inbox-reply-text').value = '';
  await api('/message/send', { method: 'POST', body: { 
    student_id: currentChatStudentId, 
    course_id: currentCourse.id,
    sender: 'lecturer', 
    content: text 
  } });

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
  } catch (e) { aiStatus = { ai_enabled: false }; }

  await Promise.all([
    loadOverview(),
    loadCurriculumAsync(),
    loadQuizList(),
    loadAssignmentList(),
    loadStudentRoster()
  ]);
  populateSelects();
}

async function loadOverview() {
  const report = await api('/report?course_id=' + courseId);
  _lastOverviewData = report;
  renderOverview(report);
}

function renderOverview(report) {
  const s = report.summary || {};
  document.getElementById('overview-stats').innerHTML = `
    <div class="stat-card"><div class="stat-label">${t('STUDENTS')}</div><div class="stat-value accent">${s.total_students || 0}</div><div class="stat-sub">${s.active_students || 0} ${t('active this week')}</div></div>
    <div class="stat-card"><div class="stat-label">${t('CLASS MASTERY')}</div><div class="stat-value ${masteryClass(s.class_avg_mastery)}">${Math.round((s.class_avg_mastery || 0) * 100)}%</div><div class="stat-sub">${t('Average across all topics')}</div></div>
    <div class="stat-card"><div class="stat-label">${t('AT RISK')}</div><div class="stat-value ${s.at_risk_count > 0 ? 'danger' : 'success'}">${s.at_risk_count || 0}</div><div class="stat-sub">${t('Students needing attention')}</div></div>
    <div class="stat-card"><div class="stat-label">${t('TOP PERFORMERS')}</div><div class="stat-value success">${s.top_performer_count || 0}</div><div class="stat-sub">${t('Mastery above 80%')}</div></div>`;
  const atRisk = report.at_risk_students || [];
  document.getElementById('at-risk-list').innerHTML = atRisk.length === 0 ? `<p style="color:var(--text-muted)">${t('No at-risk students 🎉')}</p>`
    : atRisk.map(s => `<div class="risk-item"><div><span class="risk-name">${s.name}</span></div><div class="risk-badges"><span class="risk-badge ${s.overall_mastery < 0.4 ? 'critical' : 'warning'}">${Math.round(s.overall_mastery * 100)}% ${t('mastery')}</span>${s.flags.map(f => `<span class="risk-badge low">${t(f)}</span>`).join('')}</div></div>`).join('');
  const td = report.topic_difficulty || {};
  document.getElementById('topic-difficulty-chart').innerHTML = Object.entries(td).slice(0, 8).map(([name, score]) =>
    `<div class="progress-item"><div class="progress-label"><span>${name}</span><span>${Math.round(score * 100)}%</span></div><div class="progress-bar"><div class="progress-fill" style="width:${score * 100}%;background:${masteryColor(score)}"></div></div></div>`
  ).join('');
}

async function loadCurriculumAsync() {
  const currData = await api('/curriculum?course_id=' + courseId);
  curriculum = Array.isArray(currData) ? currData : [];
  renderCurriculum();
}

function renderCurriculum() {
  try {
    const subtitleEl = document.getElementById('curriculum-subtitle');
    if (subtitleEl && currentCourse) subtitleEl.textContent = `${currentCourse.name} — ${t('Content Map')}`;
    if (subtitleEl) subtitleEl.setAttribute('data-i18n-data', JSON.stringify({name: currentCourse?.name||''})); // Optional: for more complex templates

    if (!curriculum || !Array.isArray(curriculum)) {
      document.getElementById('curriculum-tree').innerHTML = `<p style="color:var(--text-muted); padding:20px;">${t('class.no_curriculum')}</p>`;
      return;
    }

    document.getElementById('curriculum-tree').innerHTML = curriculum.map((ch, i) => `
      <div class="chapter-block">
        <div class="chapter-header" onclick="this.nextElementSibling.classList.toggle('open');this.querySelector('.chapter-toggle').textContent=this.nextElementSibling.classList.contains('open')?'▾':'▸'">
          <div style="display:flex;align-items:center"><span class="chapter-num">${ch.number}</span><span class="chapter-title">${esc(ch.title)}</span></div>
          <span class="chapter-toggle">▸</span>
        </div>
        <div class="chapter-topics">${(ch.topics || []).map(t_obj => `<div class="topic-item"><div class="topic-info"><span class="topic-type-badge ${t_obj.type}">${t_obj.type}</span><span class="topic-name">${esc(t_obj.title)}</span></div><div class="topic-meta"><span>${t_obj.difficulty}</span><span>${t_obj.question_count || 0} ${t('questions')}</span></div></div>`).join('')}</div>
      </div>`).join('');
  } catch (err) {
    console.error('Render Error:', err);
  }
}

function populateSelects() {
  let topicOpts = '', chapterOpts = '';
  curriculum.forEach(ch => {
    chapterOpts += `<option value="${ch.id}">${t('Unit')} ${ch.number}: ${ch.title}</option>`;
    (ch.topics || []).forEach(t => { topicOpts += `<option value="${t.id}">U${ch.number} — ${t.title} (${t.type})</option>`; });
  });
  document.getElementById('activity-topic-select').innerHTML = `<option value="">${t('SelectTopic')}</option>` + topicOpts;
  document.getElementById('quiz-chapter-select').innerHTML = `<option value="">${t('AllChapters')}</option>` + chapterOpts;
  const as = document.getElementById('assignment-chapter-select');
  if (as) as.innerHTML = `<option value="">${t('AllChapters')}</option>` + chapterOpts;
}

function showGenerationLoading(el) {
  el.innerHTML = `
    <div style="padding:40px; text-align:center; background:var(--bg-card); border-radius:16px; border:1px solid var(--border); box-shadow:var(--shadow-lg); margin-top: 24px;">
      <div class="bot-animation" style="font-size:32px; margin-bottom:16px;">🤖</div>
      <h3 style="margin-bottom:12px;" data-i18n="gen.loading">${t('gen.loading')}</h3>
      <div class="progress-container" style="background:rgba(255,255,255,0.05); height:8px; border-radius:4px; max-width:320px; margin:0 auto; overflow:hidden; position:relative; border:1px solid rgba(255,255,255,0.1);">
        <div class="progress-bar-shimmer"></div>
      </div>
      <p style="color:var(--text-muted); font-size:13px; margin-top:16px;" data-i18n="gen.time">${t('gen.time')}</p>
    </div>
    <style>
      .bot-animation {
        animation: bot-bounce 2s infinite ease-in-out;
        display: inline-block;
      }
      .progress-bar-shimmer {
        position: absolute;
        top: 0;
        left: -100%;
        height: 100%;
        width: 100%;
        background: linear-gradient(90deg, 
          transparent 0%, 
          rgba(99, 102, 241, 0.8) 40%, 
          rgba(168, 85, 247, 0.8) 50%, 
          rgba(99, 102, 241, 0.8) 60%, 
          transparent 100%
        );
        animation: shimmer-slide 1.5s infinite linear;
        box-shadow: 0 0 15px rgba(168, 85, 247, 0.4);
      }
      @keyframes bot-bounce {
        0%, 100% { transform: translateY(0) scale(1); }
        50% { transform: translateY(-12px) scale(1.1); }
      }
      @keyframes shimmer-slide {
        0% { left: -100%; }
        100% { left: 100%; }
      }
    </style>
  `;
}

async function launchActivity() {
  const topicId = document.getElementById('activity-topic-select').value;
  if (!topicId) return showAlert(t('missing_info'), t('class.select_topic_msg') || (currentLang === 'tr' ? 'Lütfen bir konu seçin' : 'Please select a topic'), true);
  
  const preview = document.getElementById('activity-preview');
  preview.classList.remove('hidden');
  
  // Show Loading State
  showGenerationLoading(preview);

  try {
    const data = await api('/activity?topic_id=' + topicId);
    _lastActivityData = data;
    preview.innerHTML = '<h2 style="margin-bottom:20px">📋 ' + (data.topic?.title||'') + '</h2>' + (data.activities||[]).map((a, i) => renderActivityCard(a, i, 'preview')).join('');
  } catch (err) {
    preview.innerHTML = `<div style="padding:20px; color:var(--danger); text-align:center; background:var(--danger-bg); border-radius:12px; border:1px solid var(--danger);">
      ${t('assign.retry')}
    </div>`;
  }
}

function renderActivityCard(a, idx, ctx) {
  const p = translatePrompt(a.prompt);
  if (a.type === 'mcq') return `<div class="activity-card" id="${ctx}-${idx}"><div class="activity-type-label">${t('draft.mcq').toUpperCase()}</div><div class="activity-prompt">${p}</div><div class="options-grid">${(a.options || []).map(o => `<button class="option-btn" data-original="${esc(o)}" onclick="checkMCQ(this,'${esc(a.answer)}','${ctx}-${idx}','${esc(a.id)}')">${translateOption(o)}</button>`).join('')}</div><div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
  if (a.type === 'fill_blank') return `<div class="activity-card" id="${ctx}-${idx}"><div class="activity-type-label">${t('draft.fill_blank').toUpperCase()}</div><div class="activity-prompt">${p}</div><div style="display:flex;gap:10px;align-items:center;margin-top:12px"><input class="fill-blank-input" id="inp-${ctx}-${idx}" data-i18n-placeholder="assign.type_answer" placeholder="${t('assign.type_answer')}" style="flex:1" onkeydown="if(event.key==='Enter')checkFill('${ctx}-${idx}','${esc(a.answer)}','${esc(a.id)}')"><button class="btn btn-primary btn-sm" onclick="checkFill('${ctx}-${idx}','${esc(a.answer)}','${esc(a.id)}')">${t('check')}</button></div>${a.hint ? `<div style="margin-top:8px;font-size:13px;color:var(--text-muted)">💡 ${a.hint}</div>` : ''}<div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
  if (a.type === 'dialogue_order') {
    const lines = a.scrambled_lines || [];
    const speakers = a.speakers || {};
    return `<div class="activity-card" id="${ctx}-${idx}"><div class="activity-type-label">🗣️ ${t('prac.dialogue').toUpperCase()}</div><div class="activity-prompt">${t('prac.dialogue_order')}</div><div id="dialogue-${ctx}-${idx}" style="display:flex;flex-direction:column;gap:8px;margin-top:12px">${lines.map((line, li) => `<div class="dialogue-row" style="display:flex;align-items:center;gap:8px" data-line="${esc(line)}"><button class="btn btn-ghost btn-sm" onclick="moveDialogueLine(this,-1)" style="min-width:36px">▲</button><button class="btn btn-ghost btn-sm" onclick="moveDialogueLine(this,1)" style="min-width:36px">▼</button><div style="flex:1;padding:10px 14px;background:var(--bg-input);border:2px solid var(--border);border-radius:var(--radius-sm);font-size:14px"><span style="font-weight:600;color:var(--accent-light);margin-right:8px">${speakers[line] || '?'}:</span>${line}</div></div>`).join('')}</div><button class="btn btn-primary btn-sm" style="margin-top:12px" onclick="checkDialogue('${ctx}-${idx}','${esc(JSON.stringify(a.correct_order))}')">✓ ${t('check')}</button><div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
  }
  return '';
}

function esc(s) { return (s || '').replace(/'/g, "\\'").replace(/"/g, '&quot;'); }

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
  if (cardId.startsWith('prac')) await api('/activity/respond', { method: 'POST', body: { student_id: currentUser.id, question_id: qid, answer: picked, correct_answer: answer, question_type: 'mcq' } });
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
  if (id.startsWith('prac')) await api('/activity/respond', { method: 'POST', body: { student_id: currentUser.id, question_id: qid, answer: val, correct_answer: answer, question_type: 'fill_blank' } });
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
  fb.textContent = isCorrect ? t('correctMsg') : t('prac.not_quite_right');
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

  if (res && res.questions) {
    currentDraft = {
      type: 'quiz',
      title: title,
      course_id: courseId,
      chapter_id: chapterId,
      questions: res.questions
    };
    openDraftModal();
  }
}

async function loadQuizList() {
  const quizzes = await api(`/quizzes?course_id=${courseId}&student_id=${currentUser.id}`);
  _lastQuizListData = quizzes;
  renderQuizList(quizzes);
}

function renderQuizList(quizzes) {
  const container = currentUser.role === 'lecturer' ? document.getElementById('quiz-list') : document.getElementById('student-quiz-list');
  if (!container) return;
  container.innerHTML = quizzes.length === 0 ? `<p style="color:var(--text-muted);padding:20px">${t('noQuizzes')}</p>`
    : quizzes.map(q => {
      if (currentUser.role === 'lecturer') {
        return `<div class="card" style="margin-bottom:12px">
            <div class="card-body flex-between">
              <div style="flex:1;cursor:pointer" onclick="viewQuiz('${q.id}','${esc(q.title)}')">
                <strong>${q.title}</strong>
                <div style="font-size:13px;color:var(--text-muted);margin-top:4px">${t('Created')}: ${new Date(q.created_at).toLocaleDateString()}</div>
              </div>
              <div style="display:flex;gap:8px;align-items:center">
                <button class="btn btn-outline btn-sm" onclick="previewQuiz('${q.id}','${esc(q.title)}')">👁️ ${t('viewBtn')}</button>
                <button class="btn btn-outline btn-sm" onclick="viewQuiz('${q.id}','${esc(q.title)}')">📊 ${t('view')}</button>
                <button class="btn btn-sm" style="background:var(--danger-bg,#fde8e8);color:var(--danger);border:1px solid var(--danger)" onclick="event.stopPropagation();deleteQuiz('${q.id}','${esc(q.title)}')">🗑️ ${t('close')}</button>
              </div>
            </div>
          </div>`;
      } else {
        const isCompleted = q.is_completed;
        return `<div class="card" style="cursor:${isCompleted ? 'default' : 'pointer'};opacity:${isCompleted ? '0.6' : '1'};margin-bottom:12px" onclick="${isCompleted ? '' : `takeQuiz('${q.id}')`}"><div class="card-body flex-between"><div><strong>${q.title}</strong><div style="font-size:13px;color:var(--text-muted);margin-top:4px">${t('Created')}: ${new Date(q.created_at).toLocaleDateString()} ${isCompleted ? ` · <span style="color:var(--success)">✓ ${t('completed')}</span>` : ''}</div></div><span class="btn btn-sm ${isCompleted ? 'btn-ghost' : 'btn-outline'}">${isCompleted ? t('completed') : t('takeQuizBtn')}</span></div></div>`;
      }
    }).join('');
}

async function deleteQuiz(quizId, title) {
  if (!(await showConfirmModal('confirm.delete_quiz', 'confirm.delete_quiz_msg', true, null, false, 'ok', 'cancel', { title }))) return;
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

  const studentResults = respData.student_results || [];
  const classAvg = respData.average_score ? Math.round(respData.average_score * 100) : 0;
  
  const L = {
    noResponses: t('assign.no_responses'),
    submitted: t('assign.submitted'),
    classAvg: t('assign.class_avg'),
    correct: t('assign.correct'),
    studentAnswer: t('assign.student_answer'),
    correctAns: t('assign.correct_ans')
  };

  document.getElementById('student-detail-body').innerHTML = `
    <h2 style="margin-bottom:4px">${title}</h2>
    <div style="color:var(--text-muted); margin-bottom:20px; font-size:14px">${L.classAvg}: <strong style="color:var(--accent)">${classAvg}%</strong> · ${studentResults.length} ${L.submitted}</div>
    
    <div style="display:flex;gap:8px;margin-bottom:20px;border-bottom:1px solid var(--border)">
      <button class="nav-tab active" onclick="switchQuizViewTab(this,'qv-questions')" style="flex:1;padding:10px">📋 <span data-i18n="answer">${t('answer')}</span></button>
      <button class="nav-tab" onclick="switchQuizViewTab(this,'qv-responses')" style="flex:1;padding:10px">👥 <span data-i18n="responses">${t('responses')}</span> (${studentResults.length})</button>
    </div>

    <div id="qv-questions">
      ${quizData.questions.map((q, i) => `
        <div style="margin-bottom:10px; padding:12px; background:var(--bg-input); border:1px solid var(--border); border-radius:8px">
          <div style="font-weight:600; margin-bottom:6px; font-size:14px">Q${i + 1}: ${translatePrompt(q.prompt)}</div>
          <div style="font-size:13px"><span data-i18n="answer">${t('answer')}</span>: <strong style="color:var(--success)">${q.answer}</strong></div>
        </div>
      `).join('')}
    </div>

    <div id="qv-responses" style="display:none">
      ${studentResults.length === 0
      ? `<p style="color:var(--text-muted);padding:20px;text-align:center" data-i18n="assign.no_responses">${L.noResponses}</p>`
      : studentResults.map(sr => {
        const avgPct = Math.round(sr.average_score * 100);
        const correctCount = sr.answers.filter(a => a.is_correct).length;
        return `
              <div style="margin-bottom:16px; border:1px solid var(--border); border-radius:8px; overflow:hidden">
                <div style="padding:14px 16px; background:var(--bg-secondary); display:flex; justify-content:space-between; align-items:center; cursor:pointer" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
                  <div>
                    <strong style="font-size:15px">${sr.student_name}</strong>
                    <span style="font-size:13px; color:var(--text-muted); margin-left:8px">${correctCount}/${sr.total_questions} <span data-i18n="assign.correct">${L.correct}</span></span>
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
                          <div style="margin-bottom:4px; font-weight:500">${translatePrompt(a.prompt)}</div>
                          <div style="display:flex; gap:16px; flex-wrap:wrap">
                            <span><span data-i18n="assign.student_answer">${L.studentAnswer}</span>: <strong style="color:${isRight ? 'var(--success)' : 'var(--danger)'}">${a.student_answer === '[STARTED]' ? '[Blank]' : esc(a.student_answer)}</strong></span>
                            ${!isRight ? `<span><span data-i18n="assign.correct_ans">${L.correctAns}</span>: <strong style="color:var(--success)">${a.correct_answer}</strong></span>` : ''}
                          </div>
                        </div>
                      </div>`;
        }).join('')}
                </div>
              </div>`;
      }).join('')}
    </div>
  `;
  applyTranslations(document.getElementById('student-detail-body'));
}

function switchQuizViewTab(btn, panelId) {
  btn.parentElement.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('qv-questions').style.display = panelId === 'qv-questions' ? 'block' : 'none';
  document.getElementById('qv-responses').style.display = panelId === 'qv-responses' ? 'block' : 'none';
}

async function takeQuiz(quizId) {
  const confirmed = await showConfirmModal('confirm.start_quiz_title', 'confirm.start_quiz_msg');
  if (!confirmed) return;

  const data = await api(`/quiz/take?quiz_id=${quizId}&student_id=${currentUser.id}`);
  if (data.error) {
    showAlert(t('error'), data.error, true);
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
  area.innerHTML = `<div class="quiz-header"><span class="quiz-progress-text">Q${idx + 1}/${qs.length}</span></div><div class="activity-card"><div class="activity-prompt">${translatePrompt(q.prompt)}</div>` +
    (q.type === 'mcq' ? `<div class="options-grid">${((q.distractors || []).concat([q.answer]).sort(() => Math.random() - 0.5)).map(o => `<button class="option-btn" onclick="quizAnswer(this,'${esc(q.id)}','${esc(o)}')">${translateOption(o)}</button>`).join('')}</div>` : `<div style="display:flex;gap:10px;align-items:center;margin-top:12px"><input class="fill-blank-input" id="q-inp" style="flex:1" placeholder="..." onkeydown="if(event.key==='Enter')quizAnswer(null,'${esc(q.id)}',this.value)"><button class="btn btn-primary" onclick="quizAnswer(null,'${esc(q.id)}',document.getElementById('q-inp').value)">${t('submit')}</button></div>`) + `</div>`;
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
  await api('/quiz/submit', { method: 'POST', body: { quiz_id: area.dataset.quizId, student_id: currentUser.id, answers: JSON.parse(area.dataset.answers) } });
  location.reload();
}

async function loadStudentRoster() {
  const students = await api('/students?course_id=' + courseId);
  const pending = await api('/students/pending?course_id=' + courseId).catch(() => []);

  // Render pending approvals into separate full-width container
  const pendingEl = document.getElementById('pending-roster');
  if (pendingEl) {
    if (pending && pending.length > 0) {
      pendingEl.innerHTML = `<div style="background:linear-gradient(135deg, rgba(139,92,246,0.1), rgba(139,92,246,0.05));padding:20px;border-radius:16px;border:1px solid rgba(139,92,246,0.3);margin-bottom:24px">
        <h3 style="color:#8b5cf6;margin:0 0 16px 0;font-size:1.1rem">⏳ ${t('Account Pending Approval')} (${pending.length})</h3>
        ${pending.map(s => `
          <div style="display:flex;align-items:center;justify-content:space-between;background:var(--bg-card);padding:14px 20px;border-radius:10px;margin-bottom:8px;border:1px solid var(--border)">
            <div style="min-width:0;flex:1;overflow:hidden">
              <div style="font-weight:600;color:var(--text-primary);font-size:0.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${s.name}</div>
              <div style="color:var(--text-secondary);font-size:0.8rem;margin-top:2px">${s.email}</div>
            </div>
            <div style="display:flex;gap:8px;margin-left:16px;flex-shrink:0">
              <button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); approveStudent('${s.id}')">✅ ${t('ok')}</button>
              <button class="btn btn-outline btn-sm" onclick="event.stopPropagation(); deleteStudent('${s.id}','${esc(s.name)}')">❌ ${t('cancel')}</button>
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
    return `<div class="student-card" onclick="showStudentDetail('${s.id}','${esc(s.name)}', '${schoolNum}')">
      <div class="flex-between" style="margin-bottom:8px; gap:12px">
        <div class="student-name" style="margin-bottom:0; flex:1; min-width:0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis">
          ${s.name}${schoolNumHtml}
        </div>
        <div style="display:flex; gap:6px; flex-shrink:0">
          <button class="btn btn-sm" style="background:var(--accent); color:#fff; border:none; padding:4px 8px; border-radius:6px; font-size:14px" onclick="event.stopPropagation(); openChatFromRoster('${s.id}','${esc(s.name).replace(/'/g, "\\'")}')">💬 <span data-i18n="messageTeacher">${t('messageTeacher')}</span></button>
          <button class="btn btn-sm" style="background:var(--danger-bg); color:var(--danger); border:1px solid var(--danger); padding:4px 8px; border-radius:6px" onclick="event.stopPropagation(); deleteStudent('${s.id}','${esc(s.name).replace(/'/g, "\\'")}')"><span data-i18n="Kick">${t('Kick')}</span></button>
        </div>
      </div>
      <div class="student-mastery-bar">
        <div class="student-mastery-fill" style="width:${pct}%; background:${masteryColor(s.avg_mastery)}"></div>
      </div>
      <div class="student-meta-row">
        <span><span data-i18n="Mastery:">${t('Mastery:')}</span> ${pct}%</span>
        <span>${s.total_responses} <span data-i18n="responses">${t('responses')}</span></span>
      </div>
    </div>`;
  }).join('');
}

window.openChatFromRoster = async (studentId, studentName) => {
  const tabBtn = document.querySelector('button[data-tab="inbox"]');
  if (tabBtn) switchTab(tabBtn, true);
  await openChat(studentId, studentName);
};

window.approveStudent = async (id) => {
  await api('/students/approve', { method: 'POST', body: { student_id: id, course_id: courseId } });
  loadStudentRoster();
};

function showConfirmModal(titleKey, messageKey, isDanger = false, inputPlaceholder = null, hideCancel = false, okKey = null, cancelKey = null, messageData = {}) {
  return new Promise(resolve => {
    const modal = document.getElementById('confirm-modal');
    modal.setAttribute('data-title-key', titleKey);
    modal.setAttribute('data-msg-key', messageKey);
    modal.setAttribute('data-msg-data', JSON.stringify(messageData));
    modal.setAttribute('data-ok-key', okKey || 'ok');
    modal.setAttribute('data-cancel-key', cancelKey || 'cancel');

    const titleEl = document.getElementById('confirm-title');
    const msgEl = document.getElementById('confirm-message');
    
    titleEl.setAttribute('data-i18n', titleKey);
    titleEl.textContent = t(titleKey);
    
    msgEl.setAttribute('data-i18n', messageKey);
    msgEl.setAttribute('data-i18n-data', JSON.stringify(messageData));
    msgEl.textContent = t(messageKey, messageData);

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

    const okKeyFinal = okKey || 'ok';
    const cancelKeyFinal = cancelKey || 'cancel';

    okBtn.setAttribute('data-i18n', okKeyFinal);
    okBtn.textContent = t(okKeyFinal);
    
    cancelBtn.setAttribute('data-i18n', cancelKeyFinal);
    cancelBtn.textContent = t(cancelKeyFinal);

    if (hideCancel) cancelBtn.style.display = 'none';
    else cancelBtn.style.display = 'block';

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

async function showAlert(titleKey, messageKey, isDanger = false) {
  return showConfirmModal(titleKey, messageKey, isDanger, null, true);
}

async function confirmCancelAssignment() {
  if (await showConfirmModal('cancel', 'confirm.start_assignment_msg', true)) {
    document.getElementById('assignment-taking-area').classList.add('hidden');
  }
}

async function deleteStudent(sid, name) {
  const confirmed = await showConfirmModal('confirm.kick_student_title', 'confirm.kick_student_msg', true, null, false, 'ok', 'cancel', { name });
  if (confirmed) {
    const res = await api('/student/delete', { method: 'POST', body: { student_id: sid } });
    if (!res.error) loadStudentRoster();
  }
}

async function resetData(targetCourseId = null) {
  // If targetCourseId is not explicitly null (Global), use current courseId if available
  // Wait! If called from selection screen with (null), we WANT targetCourseId to stay null.
  // If called from Overview with (), targetCourseId is null by default.
  // So we need to distinguish between "Global" and "Current Classroom".
  
  // Revised logic:
  // resetData() -> Current Classroom (if courseId exists)
  // resetData(null) -> Global Reset
  
  let finalCourseId = targetCourseId;
  if (arguments.length === 0 && typeof courseId !== 'undefined') {
    finalCourseId = courseId;
  }

  const confirmed1 = await showConfirmModal('confirm.erase_all_title', 'confirm.erase_all_msg1', true);
  if (!confirmed1) return;

  const typed = await showConfirmModal('confirm.erase_all_title', 'confirm.erase_all_msg2', true, 'ERASE ALL DATA');
  if (typed !== 'ERASE ALL DATA') return;

  const res = await api('/data/reset', { 
    method: 'POST', 
    body: { 
      confirm: 'ERASE ALL DATA',
      course_id: finalCourseId
    } 
  });
  
  if (res.success) {
    location.reload();
  } else {
    showAlert('cancel', res.error || 'Error', true);
  }
}

async function showStudentDetail(sid, name, studentId = '') {
  const data = await api('/student/progress?student_id=' + sid);
  const modal = document.getElementById('student-detail-modal');
  modal.classList.remove('hidden');
  
  const idHtml = studentId ? `<span style="font-size:16px; color:var(--text-muted); margin-left:12px; font-weight:normal">#${studentId}</span>` : '';

  document.getElementById('student-detail-body').innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:24px">
      <h2 style="margin:0">${name}${idHtml}</h2>
      <div style="display:flex; gap:8px">
        <button class="btn btn-primary btn-sm" onclick="openChatFromRoster('${sid}','${esc(name).replace(/'/g, "\\'")}')">💬 <span data-i18n="messageTeacher">${t('messageTeacher')}</span></button>
        <button class="btn btn-sm" style="background:var(--danger-bg); color:var(--danger); border:1px solid var(--danger)" onclick="deleteStudent('${sid}','${esc(name).replace(/'/g, "\\'")}')">🚫 <span data-i18n="Kick">${t('Kick')}</span></button>
      </div>
    </div>

    <h3 style="margin-bottom:16px" data-i18n="Mastery:">${t('Mastery:')}</h3>
    ${(data.masteries || []).map(m => {
      const pct = Math.round(m.score * 100);
      return `<div class="progress-item"><div class="progress-label"><span>${m.title}</span><span>${pct}%</span></div><div class="progress-bar"><div class="progress-fill" style="width:${pct}%;background:${masteryColor(m.score)}"></div></div></div>`;
    }).join('')}

    <h3 style="margin:24px 0 16px" data-i18n="Activities">${t('Activities')}</h3>
    ${(data.recent_responses || []).slice(0, 10).map(r => `<div style="padding:8px 0;border-bottom:1px solid var(--border);font-size:14px"><span style="color:${r.score >= 0.8 ? 'var(--success)' : 'var(--danger)'};font-weight:600">${Math.round(r.score * 100)}%</span> — ${r.prompt?.substring(0, 60) || 'Question'}</div>`).join('')}
  `;
  applyTranslations(document.getElementById('student-detail-body'));
}

async function generateReport() {
  document.getElementById('report-content').innerHTML = '<p style="color:var(--text-muted)">' + t('Loading curriculum...') + '</p>';
  const r = await api('/report/generate', { method: 'POST', body: { course_id: courseId } });
  const avgPct = Math.round((r.summary?.class_avg_mastery || 0) * 100);

  document.getElementById('report-content').innerHTML = `
    <div style="max-width: 800px; margin: 0 auto; background: var(--bg-card); border-radius: 8px; overflow: hidden; border: 1px solid var(--border);">
      <div style="background: var(--gradient-1); padding: 30px; text-align: center; color: white;">
        <h2 style="margin: 0; font-size: 24px; font-weight: 600;" data-i18n="report.title">${t('Weekly Report')}</h2>
      </div>
      <div style="padding: 40px 30px;">
        <div style="display: flex; gap: 20px; margin: 30px 0; flex-wrap: wrap;">
          <div style="flex: 1; min-width: 120px; background: var(--bg-input); border: 1px solid var(--border); padding: 20px; border-radius: 8px; text-align: center;">
            <div style="font-size: 12px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;" data-i18n="STUDENTS">${t('STUDENTS')}</div>
            <div style="font-size: 28px; font-weight: 700; margin-top: 5px;">${r.summary?.total_students || 0}</div>
          </div>
          <div style="flex: 1; min-width: 120px; background: var(--bg-input); border: 1px solid var(--border); padding: 20px; border-radius: 8px; text-align: center;">
            <div style="font-size: 12px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;" data-i18n="CLASS MASTERY">${t('CLASS MASTERY')}</div>
            <div style="font-size: 28px; font-weight: 700; margin-top: 5px;">${avgPct}%</div>
          </div>
          <div style="flex: 1; min-width: 120px; background: var(--danger-bg); border: 1px solid var(--danger); padding: 20px; border-radius: 8px; text-align: center;">
            <div style="font-size: 12px; text-transform: uppercase; color: var(--danger); font-weight: 600;" data-i18n="AT RISK">${t('AT RISK')}</div>
            <div style="font-size: 28px; font-weight: 700; color: var(--danger); margin-top: 5px;">${r.summary?.at_risk_count || 0}</div>
          </div>
        </div>
      </div>
    </div>
  `;
  applyTranslations(document.getElementById('report-content'));
}

async function initStudent() {
  document.getElementById('student-nav-username').textContent = currentUser.name;
  document.getElementById('student-greeting').textContent = t('welcomeBack') + ', ' + currentUser.name + '!';

  await Promise.all([
    loadCurriculumAsync(),
    loadStudentHome(),
    loadQuizList(),
    loadAssignmentList(),
    loadStudentProgress()
  ]);
  loadStudentPractice();
}

async function loadStudentStats() {
  const stats = await api('/student/stats?student_id=' + currentUser.id);
  const container = document.getElementById('student-stats');
  if (!container) return;
  container.innerHTML = `<div class="stat-card"><div class="stat-label">${t('Quizzes')}</div><div class="stat-value accent">${stats.quizzes || 0}</div></div><div class="stat-card"><div class="stat-label">${t('practice')}</div><div class="stat-value success">${stats.practice || 0}</div></div><div class="stat-card"><div class="stat-label">${t('Assignments')}</div><div class="stat-value warning">${stats.assignments || 0}</div></div>`;
}

async function loadStudentHome() {
  const progress = await api('/student/progress?student_id=' + currentUser.id);
  _lastStudentHomeData = progress;
  renderStudentHome(progress);
}

function renderStudentHome(data) {
  const masteries = data.masteries || [];
  const avg = masteries.length ? masteries.reduce((a, m) => a + m.score, 0) / masteries.length : 0;
  const strong = masteries.filter(m => m.score >= 0.75).length;
  const weak = masteries.filter(m => m.score < 0.4).length;

  const statsEl = document.getElementById('student-stats');
  if (statsEl) {
    statsEl.innerHTML = `
      <div class="stat-card"><div class="stat-label">${t('overallMastery')}</div><div class="stat-value ${masteryClass(avg)}">${Math.round(avg * 100)}%</div></div>
      <div class="stat-card"><div class="stat-label">${t('strongTopics')}</div><div class="stat-value success">${strong}</div></div>
      <div class="stat-card"><div class="stat-label">${t('needsWork')}</div><div class="stat-value ${weak > 0 ? 'danger' : 'success'}">${weak}</div></div>
      <div class="stat-card"><div class="stat-label">${t('topicsStudied')}</div><div class="stat-value accent">${masteries.length}</div></div>`;
  }

  const chapterEl = document.getElementById('student-current-chapter');
  if (chapterEl) {
    chapterEl.innerHTML = curriculum.length ? `<h4 style="margin-bottom:12px">${t('📖 Current Chapter')}: ${curriculum[0].title}</h4>${(curriculum[0].topics || []).map(tp => `<div class="topic-item"><div class="topic-info"><span class="topic-type-badge ${tp.type}">${tp.type}</span><span class="topic-name">${tp.title}</span></div></div>`).join('')}` : '';
  }
}

function loadStudentPractice() {
  document.getElementById('practice-topics').innerHTML = curriculum.map(ch => (ch.topics || []).map(tp =>
    `<div class="topic-practice-card" onclick="startPractice('${tp.id}','${esc(tp.title)}')">
      <div class="topic-type-badge ${tp.type}" style="margin-bottom:8px">${tp.type}</div>
      <div style="font-weight:600;margin-bottom:4px">${tp.title}</div>
      <div style="font-size:13px;color:var(--text-muted)"><span data-i18n="Unit">${t('Unit')}</span> ${ch.number} · ${tp.difficulty}</div>
    </div>`
  ).join('')).join('');
}

async function startPractice(tid, title) {
  const area = document.getElementById('practice-area');
  area.classList.remove('hidden');
  area.scrollIntoView({ behavior: 'smooth' });
  
  // Show Loading State
  showGenerationLoading(area);
  
  const data = await api('/activity?topic_id=' + tid);
  
  area.innerHTML = `<div class="page-header" style="margin-top:24px"><h2>${t('practice')}: ${title}</h2><button class="btn btn-outline btn-sm" onclick="this.closest('#practice-area').classList.add('hidden')">${t('close')}</button></div>` +
    (data.activities || []).map((a, i) => renderActivityCard(a, i, 'prac')).join('');
}

async function loadStudentProgress() {
  const data = await api('/student/progress?student_id=' + currentUser.id);
  _lastStudentHomeData = data;
  renderStudentProgress(data);
}

function renderStudentProgress(data) {
  const chart = document.getElementById('progress-chart');
  if (!chart) return;
  chart.innerHTML = (data.masteries || []).map(m => {
    const pct = Math.round(m.score * 100);
    return `<div class="progress-item"><div class="progress-label"><span>${m.title} <span class="topic-type-badge ${m.type}" style="margin-left:8px">${m.type}</span></span><span>${pct}%</span></div><div class="progress-bar"><div class="progress-fill" style="width:${pct}%;background:${masteryColor(m.score)}"></div></div></div>`;
  }).join('') || `<p style="color:var(--text-muted)">${t('No quizzes yet.')}</p>`;
}

async function loadAssignmentList() {
  const url = currentUser.role === 'lecturer'
    ? `/assignments?course_id=${courseId}`
    : `/assignments?course_id=${courseId}&student_id=${currentUser.id}`;
  const assignments = await api(url);
  _lastAssignmentListData = assignments;
  renderAssignmentList(assignments);
}

function renderAssignmentList(assignments) {
  const container = currentUser.role === 'lecturer'
    ? document.getElementById('assignment-list')
    : document.getElementById('student-assignment-list');
  if (!container) return;

  if (!assignments || assignments.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted);padding:20px;text-align:center" data-i18n="No assignments yet.">${t('No assignments yet.')}</p>`;
    return;
  }

  if (currentUser.role === 'lecturer') {
    container.innerHTML = assignments.map(a => `
      <div class="card" style="margin-bottom:12px">
        <div class="card-body flex-between">
          <div style="flex:1">
            <strong style="font-size:15px">${esc(a.title)}</strong>
            <div style="font-size:13px;color:var(--text-muted);margin-top:4px">
              ${t('Created')}: ${new Date(a.created_at).toLocaleDateString()}
            </div>
          </div>
          <div style="display:flex;gap:8px;align-items:center;margin-left:12px">
            <button class="btn btn-outline btn-sm" onclick="previewAssignment('${a.id}','${esc(a.title)}')">
              👁️ ${t('viewBtn')}
            </button>
            <button class="btn btn-outline btn-sm" onclick="viewAssignment('${a.id}','${esc(a.title)}')">
              📊 ${t('view')}
            </button>
            <button class="btn btn-sm" style="background:var(--danger-bg,#fde8e8);color:var(--danger);border:1px solid var(--danger)" onclick="deleteAssignment('${a.id}','${esc(a.title)}')">
              🗑️ ${t('close')}
            </button>
          </div>
        </div>
      </div>`).join('');
  } else {
    container.innerHTML = assignments.map(a => {
      const done = a.is_completed;
      return `
        <div class="card" style="margin-bottom:12px;cursor:${done ? 'default' : 'pointer'};opacity:${done ? '0.6' : '1'}" onclick="${done ? '' : `takeAssignment('${a.id}')`}">
          <div class="card-body flex-between">
            <div>
              <strong style="font-size:15px">${esc(a.title)}</strong>
              <div style="font-size:13px;color:var(--text-muted);margin-top:4px">
                ${t('Created')}: ${new Date(a.created_at).toLocaleDateString()} ${done ? ` · <span style="color:var(--success)">✓ ${t('completed')}</span>` : ''}
              </div>
            </div>
            <span class="btn btn-sm ${done ? 'btn-ghost' : 'btn-outline'}">${done ? t('completed') : t('takeQuizBtn')}</span>
          </div>
        </div>`;
    }).join('');
  }
}

async function deleteAssignment(assignmentId, title) {
  if (!(await showConfirmModal('confirm.delete_assignment', 'confirm.delete_assignment_msg', true, null, false, 'ok', 'cancel', { title }))) return;
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
    noResponses: t('assign.no_responses'),
    submitted: t('assign.submitted'),
    classAvg: t('assign.class_avg'),
    correct: t('assign.correct'),
    studentAnswer: t('assign.student_answer'),
    correctAnswer: t('assign.correct_answer'),
    expand: t('assign.view_details')
  };

  document.getElementById('student-detail-body').innerHTML = `
    <h2 style="margin-bottom:4px">📋 ${title}</h2>
    <div style="color:var(--text-muted);font-size:14px;margin-bottom:20px">
      ${data.total_questions} <span data-i18n="questions">${t('questions')}</span> &nbsp;·&nbsp;
      ${results.length} <span data-i18n="assign.submitted">${L.submitted}</span>
    </div>

    ${results.length > 0 ? `
    <!-- Summary bar -->
    <div style="display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap">
      <div style="flex:1;min-width:100px;background:var(--bg-input);border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center">
        <div style="font-size:11px;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin-bottom:4px" data-i18n="assign.submitted">${t('assign.submitted')}</div>
        <div style="font-size:26px;font-weight:700">${results.length}</div>
      </div>
      <div style="flex:1;min-width:100px;background:var(--bg-input);border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center">
        <div style="font-size:11px;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin-bottom:4px" data-i18n="CLASS MASTERY">${t('CLASS MASTERY')}</div>
        <div style="font-size:26px;font-weight:700;color:${masteryColor(classAvg / 100)}">${classAvg}%</div>
      </div>
      <div style="flex:1;min-width:100px;background:var(--bg-input);border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center">
        <div style="font-size:11px;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin-bottom:4px" data-i18n="assign.top_score">${t('assign.top_score')}</div>
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
              <span style="color:var(--text-muted);font-weight:400">(${correctCount}/${data.total_questions} <span data-i18n="correct">${L.correct.toLowerCase()}</span>)</span>
            </span>
          </div>
          <div style="background:var(--border);border-radius:4px;height:8px;cursor:pointer" onclick="this.parentElement.nextElementSibling.style.display=this.parentElement.nextElementSibling.style.display==='none'?'block':'none'">
            <div style="background:${masteryColor(sr.average_score)};height:8px;border-radius:4px;width:${pct}%;transition:width 0.6s ease"></div>
          </div>
        </div>
        <!-- Expandable detail -->
        <div style="display:none;margin-bottom:16px;border:1px solid var(--border);border-radius:8px;overflow:hidden">
          <div style="padding:12px 14px;background:var(--bg-secondary);font-size:12px;font-weight:600;text-transform:uppercase;color:var(--text-muted);letter-spacing:0.5px">
            ${esc(sr.student_name)} — <span data-i18n="assign.detailed_answers">${t('assign.detailed_answers')}</span>
          </div>
          ${sr.answers.map((a, qi) => `
            <div style="padding:10px 14px;border-bottom:1px solid var(--border);display:flex;gap:10px;align-items:flex-start;background:var(--bg-card)">
              <span style="min-width:22px;font-size:15px;font-weight:700;color:${a.is_correct ? 'var(--success)' : 'var(--danger)'};margin-top:1px">${a.is_correct ? '✓' : '✗'}</span>
              <div style="flex:1;font-size:13px">
                <div style="margin-bottom:5px;font-weight:500;line-height:1.4">${a.prompt}</div>
                <div style="display:flex;gap:16px;flex-wrap:wrap">
                  <span><span data-i18n="assign.student_answer">${L.studentAnswer}</span>: <strong style="color:${a.is_correct ? 'var(--success)' : 'var(--danger)'}">${a.student_answer === '[STARTED]' ? (currentLang === 'tr' ? '[Boş Bırakıldı]' : '[Left Blank]') : esc(a.student_answer)}</strong></span>
                  ${!a.is_correct ? `<span><span data-i18n="assign.correct_answer">${L.correctAnswer}</span>: <strong style="color:var(--success)">${esc(a.correct_answer)}</strong></span>` : ''}
                </div>
              </div>
              <span style="font-size:12px;color:${a.is_correct ? 'var(--success)' : 'var(--danger)'};font-weight:600;white-space:nowrap">${Math.round(a.score * 100)}%</span>
            </div>
          `).join('')}
        </div>`;
  }).join('')}
    </div>` : `<p style="color:var(--text-muted);padding:20px;text-align:center" data-i18n="assign.no_responses">${L.noResponses}</p>`}
  `;
  applyTranslations(document.getElementById('student-detail-body'));
}
}

async function previewAssignment(aid, title) {
  const modal = document.getElementById('student-detail-modal');
  modal.classList.remove('hidden');
  document.getElementById('student-detail-body').innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-muted)">Loading...</div>`;

  const data = await api('/assignment/take?assignment_id=' + aid);
  const isTr = currentLang === 'tr';
  const qs = data.questions || [];

  document.getElementById('student-detail-body').innerHTML = `
    <h2 style="margin-bottom:4px">👁️ ${title} - ${t('Preview')}</h2>
    <div style="color:var(--text-muted);font-size:14px;margin-bottom:20px">
      ${qs.length} ${t('questions')}
    </div>
    <div style="display:flex;flex-direction:column;gap:12px">
      ${qs.map((q, i) => `
        <div style="padding:16px;border:1px solid var(--border);border-radius:8px;background:var(--bg-card)">
          <div style="font-size:12px;font-weight:600;color:var(--text-muted);margin-bottom:8px;text-transform:uppercase">
            ${isTr ? 'Soru' : 'Question'} ${i + 1} • ${translateOption(q.type === 'mcq' ? 'Multiple Choice' : 'Fill in the Blank')}
          </div>
          <div style="font-size:15px;margin-bottom:12px">${translatePrompt(q.prompt)}</div>
          ${q.type === 'mcq' ? `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              ${(q.distractors || []).concat([q.answer]).map(o => `
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

async function previewQuiz(qid, title) {
  const modal = document.getElementById('student-detail-modal');
  modal.classList.remove('hidden');
  document.getElementById('student-detail-body').innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-muted)">Loading...</div>`;

  const data = await api('/quiz/take?quiz_id=' + qid);
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
            ${isTr ? 'Soru' : 'Question'} ${i + 1} • ${translateOption(q.type === 'mcq' ? 'Multiple Choice' : 'Fill in the Blank')}
          </div>
          <div style="font-size:15px;margin-bottom:12px">${translatePrompt(q.prompt)}</div>
          ${q.type === 'mcq' ? `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
              ${(q.distractors || []).concat([q.answer]).map(o => `
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

  if (res && res.questions) {
    currentDraft = {
      type: 'assignment',
      title: title,
      course_id: courseId,
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
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
      <h2 style="margin:0"><span data-i18n="draft.review">${t('draft.review')}</span> - ${esc(currentDraft.title)}</h2>
      <div>
        <button class="btn btn-outline btn-sm" onclick="showAddCustomQuestionForm()">➕ <span data-i18n="draft.add_question">${t('draft.add_question')}</span></button>
        <button class="btn btn-primary btn-sm" onclick="publishDraft()">✅ <span data-i18n="draft.publish">${t('draft.publish')}</span></button>
      </div>
    </div>
    <div style="font-size:12px; color:var(--text-muted); margin-bottom:16px;" data-i18n="draft.lang_warning">${t('draft.lang_warning')}</div>
    <div id="custom-question-form" class="card hidden" style="margin-bottom:16px; border:2px solid var(--primary);">
      <div class="card-body">
        <div class="form-group">
          <label data-i18n="draft.type">${t('draft.type')}</label>
          <select id="cq-type" class="select-input">
            <option value="mcq" data-i18n="draft.mcq">${t('draft.mcq')}</option>
            <option value="fill_blank" data-i18n="draft.fill_blank">${t('draft.fill_blank')}</option>
          </select>
        </div>
        <div class="form-group">
          <label data-i18n="draft.prompt">${t('draft.prompt')}</label>
          <input type="text" id="cq-prompt" class="text-input" placeholder="Ej: La capital de España es ___">
        </div>
        <div class="form-group">
          <label data-i18n="draft.answer">${t('draft.answer')}</label>
          <input type="text" id="cq-answer" class="text-input" placeholder="Madrid">
        </div>
        <div class="form-group" id="cq-distractors-group">
          <label data-i18n="draft.distractors">${t('draft.distractors')}</label>
          <input type="text" id="cq-distractors" class="text-input" placeholder="Barcelona, Sevilla, Valencia">
        </div>
        <div style="display:flex; gap:8px; margin-top:12px;">
          <button class="btn btn-primary btn-sm" onclick="saveCustomQuestion()" data-i18n="draft.save">${t('draft.save')}</button>
          <button class="btn btn-ghost btn-sm" onclick="document.getElementById('custom-question-form').classList.add('hidden')" data-i18n="draft.cancel">${t('draft.cancel')}</button>
        </div>
      </div>
    </div>
    <div style="max-height: 60vh; overflow-y: auto; padding-right:8px;">
  `;

  currentDraft.questions.forEach((q, i) => {
    html += `
      <div class="card" style="margin-bottom:12px; position:relative;">
        <button class="btn btn-ghost btn-sm" style="position:absolute; top:8px; right:8px; color:var(--danger);" onclick="removeDraftQuestion(${i})">🗑️ <span data-i18n="draft.remove">${t('draft.remove')}</span></button>
        <div class="card-body">
          <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">${i + 1}. <span data-i18n="${q.type === 'mcq' ? 'draft.mcq' : 'draft.fill_blank'}">${q.type === 'mcq' ? t('draft.mcq') : t('draft.fill_blank')}</span></div>
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
    if (e.target.value === 'fill_blank') {
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

  if (!prompt || !answer) {
    showAlert(t('missing_info'), t('draft.required_msg') || 'Prompt and Answer are required.', true);
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
  if (!currentDraft || currentDraft.questions.length === 0) {
    showAlert(t('missing_info'), t('draft.no_questions_msg') || 'You need at least 1 question to publish.', true);
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

  if (!res.error) {
    closeDraftModal();
    if (currentDraft.type === 'quiz') {
      document.getElementById('quiz-title').value = '';
      loadQuizList();
    } else {
      document.getElementById('assignment-title').value = '';
      loadAssignmentList();
    }
  } else {
    showAlert(t('error'), res.error, true);
  }
}

async function takeAssignment(aid) {
  const confirmed = await showConfirmModal('confirm.start_assignment_title', 'confirm.start_assignment_msg');
  if (!confirmed) return;

  const data = await api(`/assignment/take?assignment_id=${aid}&student_id=${currentUser.id}`);
  if (data.error) {
    showAlert(t('error'), data.error, true);
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
      <input id="as-inp" class="fill-blank-input" placeholder="${t('assign.type_answer')}"
        style="flex:1;font-size:15px" onkeydown="if(event.key==='Enter')assignmentAnswer(this.value)">
      <button class="btn btn-primary" onclick="assignmentAnswer(document.getElementById('as-inp').value)">
        ${t('submit')} →
      </button>
    </div>
    ${q.hint ? `<div style="margin-top:8px;font-size:13px;color:var(--text-muted)">💡 ${q.hint}</div>` : ''}`;
  }

  area.innerHTML = `
    <div style="padding:20px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <span style="font-size:13px;color:var(--text-muted)">${t('question')} ${idx + 1} / ${total}</span>
        <button class="btn btn-ghost btn-sm"
          onclick="confirmCancelAssignment()">
          ${t('cancel')}
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
    ${t('loading')}...
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
        <h2 style="margin-bottom:8px">${t('assign.complete')}</h2>
        <div style="font-size:36px;font-weight:700;color:${pct >= 70 ? 'var(--success)' : 'var(--warning)'};margin:16px 0">${pct}%</div>
        <p style="color:var(--text-muted);margin-bottom:24px">${t('assign.recorded')}</p>
        <button class="btn btn-primary"
          onclick="document.getElementById('assignment-taking-area').classList.add('hidden');loadAssignmentList()">
          ${t('assign.back')}
        </button>
      </div>`;
  } catch (e) {
    area.innerHTML = `<div style="padding:20px;color:var(--danger);text-align:center">
      ${t('assign.retry')}
      <br><button class="btn btn-outline" style="margin-top:12px"
        onclick="document.getElementById('assignment-taking-area').classList.add('hidden')">
        ${t('cancel')}
      </button>
    </div>`;
  }
}

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

  if (res && res.questions) {
    currentDraft = {
      type: 'quiz',
      title: title,
      course_id: courseId,
      chapter_id: chapterId,
      questions: res.questions
    };
    openDraftModal();
  }
}

