// ── State & i18n ──
let currentUser = null;
let courseId = null;
let curriculum = [];
let currentCourse = null;
let currentLang = localStorage.getItem('aula_lang') || 'en';
let aiStatus = null;
let _lastVersion = -1;
let _buildStartTime = 0;
let _syncInterval = null;
let _lastExtractedLanguage = null;
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
let _lastReportData = null;
let currentStudentEnrollments = [];
let currentStudentLessons = [];
let currentStudentQuizzes = [];
let currentStudentAssignments = [];

function toggleSidebar() {
  const sidebar = document.getElementById('mobile-sidebar');
  const content = document.getElementById('sidebar-content');
  const overlay = document.getElementById('sidebar-overlay');
  if (!sidebar || !content) return;

  const isOpen = content.style.transform === 'translateX(220px)';
  if (isOpen) {
    content.style.transform = 'translateX(0)';
    overlay.style.opacity = '0';
    overlay.style.pointerEvents = 'none';
    sidebar.style.pointerEvents = 'none';
    document.body.style.overflow = '';
    document.body.style.touchAction = '';
  } else {
    // Update user info before showing
    if (currentUser) {
      const nameEl = document.getElementById('sidebar-user-name');
      const roleEl = document.getElementById('sidebar-user-role');
      if (nameEl) nameEl.textContent = currentUser.name || 'Guest';
      if (roleEl) {
        const roleKey = currentUser.role === 'lecturer' ? 'Lecturer' : 'Student';
        roleEl.textContent = t(roleKey).toUpperCase();
        roleEl.setAttribute('data-i18n', roleKey);
      }

      // Show/Hide role-specific nav items in sidebar
      const lNav = sidebar.querySelector('.lecturer-only');
      const sNav = sidebar.querySelector('.student-only');
      if (lNav) lNav.style.display = currentUser.role === 'lecturer' ? 'flex' : 'none';
      if (sNav) sNav.style.display = currentUser.role === 'student' ? 'flex' : 'none';

      // Update course info
      if (currentCourse) {
        const sCourseName = document.getElementById('sidebar-course-name');
        const sCourseCode = document.getElementById('sidebar-course-code');
        if (sCourseName) sCourseName.textContent = currentCourse.name;
        if (sCourseCode) sCourseCode.textContent = '#' + currentCourse.code;
      }
    }

    // Update language text
    const langText = currentLang === 'tr' ? 'Turkish (TR)' : 'English (EN)';
    const sidebarLangText = document.getElementById('sidebar-lang-text');
    if (sidebarLangText) sidebarLangText.textContent = langText;

    // Apply translations to sidebar elements
    applyTranslations();

    content.style.transform = 'translateX(220px)';
    overlay.style.opacity = '1';
    overlay.style.pointerEvents = 'auto';
    sidebar.style.pointerEvents = 'auto';
    document.body.style.overflow = 'hidden';
    document.body.style.touchAction = 'none'; // Prevent background touch/scroll
  }
}

// ── Keep Render alive (ping every 10 min) ──
setInterval(() => fetch('/api/courses').catch(() => { }), 10 * 60 * 1000);

function confirmDeleteAccount() {
  showConfirmModal('student.delete_account_title', 'student.delete_account_msg', true, null, false, 'student.delete_confirm_btn').then(async confirmed => {
    if (confirmed) {
      const res = await api('/user/delete', { method: 'POST' });
      if (res && res.success) {
        logout();
      } else {
        showAlert('Error', res?.error || 'Failed to delete account');
      }
    }
  });
}

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
        // If enrollment was removed (teacher did a hard reset on the classroom)
        if (statusCheck && statusCheck.error === 'enrollment_removed' && currentUser.role === 'student') {
          await showAlert(t('alert.classroom_reset'), t('alert.classroom_reset_msg'), true);
          localStorage.removeItem('aula_last_course');
          localStorage.removeItem('aula_last_tab');
          showScreen('student-portal-screen');
          await refreshStudentEnrollments();
          return;
        }

        refreshCurrentView();
      }

      // Continuous progress polling while building (independent of data version)
      if (currentCourse && currentCourse.is_building) {
        api(`/classroom/progress?course_id=${currentCourse.id}&v=${Date.now()}`).then(prog => {
            if (prog) {
              if (prog.is_building && _buildStartTime === 0) _buildStartTime = Date.now();
              if (!prog.is_building) _buildStartTime = 0;

              const isLecturer = currentUser.role === 'lecturer';
            const bannerId = isLecturer ? 'lecturer-building-banner' : 'student-building-banner';
            const fillId = isLecturer ? 'lecturer-progress-fill' : 'student-progress-fill';
            const textId = isLecturer ? 'lecturer-progress-text' : 'student-progress-text';

            const buildBanner = document.getElementById(bannerId);
            const progressFill = document.getElementById(fillId);
            const progressText = document.getElementById(textId);

            const elapsed = Date.now() - _buildStartTime;
            let displayPct = prog.percentage;
            
            // 7-SECOND SMOOTHING HACK: Stay low while starting
            if (elapsed < 7000 && prog.is_building) {
                // Smoothly climb to 10% over 7 seconds regardless of actual speed
                const fakePct = Math.floor((elapsed / 7000) * 10);
                displayPct = Math.min(fakePct, prog.percentage);
            }

            if (buildBanner) buildBanner.classList.toggle('hidden', !prog.is_building);
            if (progressFill) progressFill.style.width = displayPct + '%';
            if (progressText) progressText.textContent = displayPct + '%';

            // Update local state if it finished building
            if (!prog.is_building && currentCourse.is_building) {
              currentCourse.is_building = 0;
              _buildStartTime = 0;
              refreshCurrentView();
            }
          }
        });
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
  api('/courses').then(async courses => {
    if (!courses || !Array.isArray(courses)) return;
    const currentlyBuilding = courses.filter(c => c.is_building === 1).map(c => c.id);

    // Auto-update building banner if we're inside a classroom
    if (currentCourse) {
      const updated = courses.find(c => c.id === currentCourse.id);
      if (updated) {
        currentCourse = updated;
        const isLecturer = currentUser.role === 'lecturer';
        const bannerId = isLecturer ? 'lecturer-building-banner' : 'student-building-banner';
        const fillId = isLecturer ? 'lecturer-progress-fill' : 'student-progress-fill';
        const textId = isLecturer ? 'lecturer-progress-text' : 'student-progress-text';
        const buildBanner = document.getElementById(bannerId);
        const progressFill = document.getElementById(fillId);
        const progressText = document.getElementById(textId);

        if (buildBanner) {
          if (currentCourse.is_building) {
            buildBanner.classList.remove('hidden');
          } else {
            buildBanner.classList.add('hidden');
          }
        }
      }
    }

    if (currentUser.role === 'lecturer') {
      for (const id of _buildingCourses) {
        if (!currentlyBuilding.includes(id)) {
          const course = courses.find(c => c.id === id);
          if (course) {
            await showAlert(t('Tebrikler!'), `"${course.name}" ${t('is ready!')}`);
            location.reload(); // Refresh to ensure everything is fresh
            return; // reload stops execution anyway
          }
        }
      }
    }
    if (currentUser.role === 'student') {
      if (currentCourse) {
        // Detect if our active course just finished building
        if (_buildingCourses.includes(currentCourse.id) && !currentlyBuilding.includes(currentCourse.id)) {
          showAlert(t('info'), t('class.ready_msg') || 'Classroom is ready! New content has been added.', false).then(() => {
            location.reload();
          });
          return;
        }

        const updated = courses.find(c => c.id === currentCourse.id);
        if (!updated || updated.enrollment_status === 'none') {
          // Kicked or course deleted
          currentCourse = null;
          showStudentPortal();
          showAlert(t('alert.classroom_reset'), t('alert.classroom_reset_msg'), true);
          return;
        }
      }
      if (document.getElementById('student-portal-screen').classList.contains('active')) {
        refreshStudentEnrollments();
      }
    }
    _buildingCourses = currentlyBuilding;
  });

  if (document.getElementById('waiting-room-screen').classList.contains('active')) {
    api('/user/status?user_id=' + currentUser.id + '&course_id=' + (currentUser.course_id || currentCourse?.id)).then(async status => {
      if (status && status.status === 'approved') {
        window.location.reload();
      } else if (status && (status.error === 'enrollment_removed' || status.error === 'course_deleted')) {
        if (window._waitingPoll) clearInterval(window._waitingPoll);
        await showAlert(t('alert.classroom_reset'), t('alert.classroom_reset_msg'), true);
        localStorage.removeItem('aula_last_course');
        localStorage.removeItem('aula_last_tab');
        window.location.reload();
      }
    });
    applyTranslations();
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
            if (currentChatStudentId && currentChatStudentName) {
              openChat(currentChatStudentId, currentChatStudentName, currentChatCourseId);
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
    // loadStudentProgress(); // Disabled until further notice
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
    langBtn: 'Language: EN',
    // Login screen
    signInTab: 'Sign In', registerTab: 'Register', signInHint: 'Sign in to continue', emailLabel: 'Email', passwordLabel: 'Password', signInBtn: 'Sign In', joinClass: 'Join the Class', registerHint: 'Create a student account', nameLabel: 'Full Name', registerBtn: 'Create Account', lecturerAccess: 'Lecturer Access', signOut: 'Sign Out', rememberMe: 'Remember Me',
    loginTitle: 'Student Login',
    'Lecturer Login': 'Lecturer Login', 'Sign in with your email and password': 'Sign in with your email and password',
    'Student Login': 'Student Login', 'Log in with your student number': 'Log in with your student number',
    'Student Number': 'Student Number', '(required)': '(required)',
    'Your Full Name': 'Your Full Name', 'e.g. 2021123456': 'e.g. 2021123456',
    'login.class_code': 'Classroom Code (5 digits)', 'login.class_code_placeholder': 'e.g. 12345',
    'login.student_number': 'Student Number',
    student_number: 'Student Number',
    full_name: 'Full Name',
    student_number_placeholder: 'e.g. 2021123456',
    full_name_placeholder: 'Your Full Name',
    Email: 'Email', Password: 'Password', 'Full Name': 'Full Name',
    'Sign In': 'Sign In', 'Remember Me': 'Remember Me',
    messageTeacher: 'Messages',
    messageStudent: 'Message Student',
    inbox: 'Messages', study: 'Study',
    newChat: 'New Chat',
    selectStudent: 'Select a Student',
    searchStudent: 'Search students...',
    noNewChats: 'No new students to message.',
    startChat: 'Start Chat',
    typeReply: 'Type a reply...',
    sendBtn: 'Send',
    Lecturer: 'Lecturer', Student: 'Student',
    '👩‍🏫 Lecturer': '👩‍🏫 Lecturer', '🎓 Student': '🎓 Student',
    select_study_topic: 'Select a topic to start studying',
    // Student dashboard
    home: 'Home', practice: 'Practice', quizzes: 'Quizzes', myProgress: 'My Progress',
    keepUp: 'Keep up the great work!', overallMastery: 'Overall Mastery', strongTopics: 'Strong Topics', needsWork: 'Needs Work', topicsStudied: 'Topics Studied', currentChapter: 'Current Chapter',
    selectPractice: 'Select a topic to practice', availableQuizzes: 'Available quizzes', trackMastery: 'Track your mastery across topics', noQuizzes: 'No quizzes yet.',
    takeQuiz: 'Take Quiz', view: 'View', close: 'Close', done: 'Done', submit: 'Submit', check: 'Check',
    yourScore: 'Your Score', questions: 'questions', correct: 'correct',
    incorrectAns: 'Incorrect. The answer is:', correctAns: 'The correct answer is:', correctMsg: 'Correct! ✓',
    takeQuizBtn: 'Take Quiz', viewBtn: 'View',
    noQuizzes: 'No quizzes yet.', noAssignments: 'No assignments yet.',
    // Lecturer nav & tabs
    Lecturer: 'Lecturer', Student: 'Student',
    settings: 'Settings', language: 'Language',
    signOut: 'Sign Out',
    Overview: 'Overview', Curriculum: 'Curriculum', Activities: 'Activities', Students: 'Students', Reports: 'Reports', Dashboard: 'Dashboard', Assignments: 'Assignments', Quizzes: 'Quizzes', 'My Stats': 'My Stats',
    // Overview stats
    STUDENTS: 'STUDENTS', 'CLASS_MASTERY': 'CLASS MASTERY', 'AT_RISK': 'AT RISK', 'TOP_PERFORMERS': 'TOP PERFORMERS',
    'Class Mastery': 'Class Mastery', 'At Risk': 'At Risk', 'Top Performers': 'Top Performers',
    at_risk_students: '⚠️ At-Risk Students', topic_difficulty: '📊 Topic Difficulty',
    'prac.dialogue_order': 'Reorder the dialogue correctly:',
    'prac.dialogue': 'Dialogue',
    'active_this_week': '{count} Active this week', 'avg_across_topics': 'Average across all topics',
    'students_needing_attention': 'Students needing attention', 'mastery_above_80': 'Mastery above 80%',
    no_at_risk: 'No at-risk students 🎉', mastery: 'mastery',
    'welcomeBack': 'Welcome back, {name}',
    'Welcome back,': 'Welcome back,',
    // Data Management
    data_mgmt: '🗑️ Data Management',
    erase_all_btn: 'Erase All Data',
    erase_all_desc: 'Removes all students, quiz results, assignment submissions, and mastery scores. Curriculum and your lecturer account are preserved.',
    // Activities
    'In-Class Activities': 'In-Class Activities', 'Generate and launch live activities': 'Generate and launch live activities',
    '🚀 Launch Activity': '🚀 Launch Activity', 'Select Chapter & Topic': 'Select Chapter & Topic',
    'Generate Activity': 'Generate Activity', 'Loading curriculum...': 'Loading curriculum...',
    // Quiz Management
    'Quiz Management': 'Quiz Management', 'Create and manage quizzes': 'Create and manage quizzes',
    '➕ Create New Quiz': '➕ Create New Quiz', 'Quiz Title': 'Quiz Title',
    Chapter: 'Select Topic', 'All chapters': 'All Topics', AllTopics: 'All Topics', Questions: 'Questions', 'Create Quiz': 'Create Quiz',
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
    'draft.no_auto_gen': 'No questions could be automatically generated.',
    'draft.click_add': 'Please click "➕ Add Question" to create them manually.',
    // Classroom Selection
    'class.selection': 'Classroom Selection',
    'class.subtitle': 'Select a classroom to manage or create a new one',
    'class.create': 'Create New Classroom from PDF',
    'class.create_generic': 'Create New Classroom',
    'class.create_title': '🛠️ Classroom Creation',
    'class.choose_method': 'Choose how you want to build your course',
    'class.magic_pdf': 'Magic PDF',
    'class.magic_pdf_desc': 'Upload a textbook PDF and let AI build the course from it.',
    'class.ai_architect': 'AI Architect',
    'class.ai_architect_desc': 'No PDF? Just tell AI the language and level, and it creates the course.',
    'ai.tell_teach': 'Tell AI what you want to teach',
    'ai.select_lang': '1. Select Language',
    'ai.target_level': '2. Target Level',
    'ai.course_name': '3. Course Name',
    'ai.name_placeholder': 'e.g. Intensive Language Course',
    'ai.gen_curriculum': 'Generate Curriculum ✨',
    'ai.clear_cache': 'Clear Cached Blueprints',
    'ai.regenerate': 'Regenerate',
    'ai.cache_cleared': 'All cached blueprints have been deleted. Next generation will create fresh curricula.',
    'ai.cache_cleared_title': 'Cache Cleared',
    'ai.review_title': 'Review Curriculum',
    'ai.review_desc': 'AI suggested these topics. You can edit or remove them.',
    'class.add_topic': 'Add Topic',
    'class.topic_name_placeholder': 'New Topic Name',
    'class.build_btn': 'Build Classroom 🚀',
    'ai.add_unit': 'Add Custom Unit',
    'ai.new_unit_title': 'New Unit Title',
    'class.enter': 'Enter Classroom',
    'class.delete_confirm': 'Are you sure you want to delete this classroom? All data including students, grades, and content will be permanently removed.',
    'class.upload_pdf': 'Upload PDF Textbook',
    'class.toc_range': 'Contents Page Range (e.g. 2-5)',
    'class.toc_placeholder': '1-25',
    'class.processing': 'Processing PDF & generating curriculum... This may take a minute.',
    'class.start_pipeline': 'Start Pipeline',
    'class.toc_manual': '2. Manual Curriculum / TOC (Paste here)',
    'class.toc_manual_hint': "Paste the book's contents or your syllabus. The AI will use this as a roadmap.",
    'class.toc_range_hint': 'If left empty, AI will use the Manual Syllabus above as the primary source.',

    // Student Portal
    'ai.select_lang': '1. Select Language',
    'ai.target_level': '2. Target Level',
    'ai.course_name': '3. Course Name',
    'ai.name_placeholder': 'e.g. Intensive Language Course',
    'ai.gen_curriculum': 'Generate Curriculum ✨',
    'loading': 'Loading...',
    'lang.Spanish': 'Spanish',
    'lang.German': 'German',
    'lang.French': 'French',
    'lang.Italian': 'Italian',
    'lang.Portuguese': 'Portuguese',
    'lang.Russian': 'Russian',
    'lang.Chinese': 'Chinese',
    'lang.Japanese': 'Japanese',
    'lang.Arabic': 'Arabic',
    'lang.Turkish': 'Turkish',
    'lang.Dutch': 'Dutch',
    'lang.Swedish': 'Swedish',
    'lang.Korean': 'Korean',
    'lang.Greek': 'Greek',
    'student.welcome': 'Welcome to AulaAI',
    'student.select_class': 'Select a classroom to continue learning',
    'student.join_new': 'Join New Classroom',
    'student.join_title': 'Join Classroom',
    'student.enter_code': 'Enter the 5-digit code provided by your teacher',
    'no_classrooms_found': 'No classrooms found',
    'student.join_btn': 'Join Classroom',
    'student.pin_required': 'Security PIN Required',
    'student.pin_desc': 'Please enter your 4-digit PIN for this classroom.',
    'student.pin_setup': 'First-time Setup',
    'student.pin_setup_desc': 'Set a 4-digit PIN for this classroom to use for future logins.',
    'student.waiting': 'Waiting for Approval',
    'student.waiting_desc': 'You will be able to enter once your teacher approves your request. Please refresh or check back later.',
    'student.invalid_pin': 'Invalid PIN. Please try again.',
    'student.pin': 'PIN',
    'student.leave': 'Leave',
    'student.leave_title': 'Leave Classroom',
    'student.leave_msg': 'Are you sure you want to leave "{name}"? All your progress, scores, and data for this classroom will be permanently deleted.',
    'alert.classroom_reset': 'Classroom Reset',
    'alert.classroom_reset_msg': 'Your teacher has reset this classroom. You have been returned to the classroom selection screen.',
    'class.create_success': 'Classroom created successfully!',
    'class.share_msg': 'Share the Join Code with your students to start the lesson.',
    'class.create_success_full': 'Classroom created successfully! \n\nJoin Code: {code}\n\nShare the Join Code with your students to start the lesson.',
    'class.building_msg_student': 'The lecturer is rebuilding the classroom structure...',
    'answer': 'Answer',
    'responses': 'Responses',
    'gen.loading': 'Questions are being generated...',
    'gen.time': 'This may take 5-10 seconds.',
    'Unit': 'Unit',
    'Material': 'Material',
    'study': 'Material',
    'book': 'Book',
    'study.units': 'Units',
    'study.vocabulary': 'Vocabulary Cheat Sheet',
    'study.grammar': 'Grammar & Key Rules',
    'study.usage': 'Practical Usage',
    'study.complete': 'Lesson Complete',
    'study.preview': 'Lesson Preview',
    'study.back': 'Back',
    'study.next': 'Next Page',
    'study.ready': "You're Ready to Practice!",
    'study.preview_end': 'End of Lesson Material',
    'study.preview_msg': 'This is how the lesson appears to your students.',
    'study.ready_msg': "Now it's time to test your knowledge.",
    'study.start_practice': '🚀 Start Practice Session',
    'SelectTopic': 'Select a topic...',
    'AllChapters': 'All chapters',
    'confirm.rebuild_title': 'Build Lessons?',
    'confirm.rebuild_msg': 'This will use AI to write all textbook pages and generate practice questions for every topic in this curriculum. This takes 2-3 minutes. Continue?',
    'confirm.rebuild_ok': 'Yes, Build Everything',
    'confirm.rebuild_cancel': 'Cancel',
    'confirm.rearchitect_title': 'Re-Architect Curriculum?',
    'confirm.rearchitect_msg': 'This will PERMANENTLY DELETE all current chapters, topics, and lesson materials. You will be taken back to the AI Architect to generate a new curriculum structure. Continue?',
    'confirm.rearchitect_ok': 'Yes, Wipe & Restart',
    'Re-Architect': 'Re-Architect',
    'ok': 'OK',
    'cancel': 'Cancel',
    'no_messages': 'No messages.',
    'tap_explain': '🧠 Tap to explain',
    'explain_ai': 'Explain with AI 🤖',
    'ai_error': 'AI was unable to explain this word right now.',
    'explain_more': 'Click \'Explain\' again for more details.',
    'ai_analyzing': 'AI is analyzing your answer...',
    'prac.dialogue': 'Dialogue',
    'confirm.delete_classroom': 'Delete Classroom',
    'confirm.delete_classroom_msg': 'Are you sure you want to delete the classroom "{name}"?',
    'confirm.delete_quiz': 'Delete Quiz',
    'confirm.delete_quiz_msg': 'Are you sure you want to delete the quiz "{title}"?',
    'confirm.cancel_creation_title': 'Cancel Creation?',
    'confirm.cancel_creation_msg': 'Are you sure? All extracted curriculum data and settings will be lost.',
    'confirm.delete_assignment': 'Delete Assignment',
    'confirm.delete_assignment_msg': 'Are you sure you want to delete the assignment "{title}"?',
    'confirm.kick_student_title': 'Kick Student',
    'confirm.kick_student_msg': 'Are you sure you want to kick {name} from the class?',
    'confirm.erase_all_title': 'ERASE ALL DATA',
    'confirm.erase_all_msg1': 'This will permanently remove all student accounts, results, and mastery data. The curriculum will stay. Are you sure?',
    'confirm.erase_all_msg2': 'LAST WARNING: Type "ERASE ALL DATA" to confirm absolute deletion.',
    'confirm.start_quiz_title': 'Start Quiz',
    'confirm.start_quiz_msg': 'Are you sure you want to start the quiz? Once started, you should finish it.',
    'confirm.start_assignment_title': 'Start Assignment',
    'confirm.start_assignment_msg': 'Are you sure? Once you start the assignment, you cannot go back, and leaving may cause partial submission.',
    'View Classrooms': 'View Classrooms',
    'Detecting...': 'Detecting...',
    'View': 'View',
    'alert.session_ended': 'Session Ended',
    'alert.account_removed': 'Your account has been removed or logged out.',
    'error': 'Error',
    'success': 'Success',
    'missing_info': 'Missing Info',
    'Tebrikler!': 'Congratulations!',
    'is ready!': 'is ready!',
    'gen.preparing': 'Preparing Classroom...',
    'gen.building': 'Building Lessons...',
    'gen.preparing_content': 'Preparing Content',
    'gen.preparing_desc': 'The AI is currently architecting this lesson. Please wait a few moments.',
    'gen.generating': 'Generating questions...',
    'gen.ai_architecting': 'Our AI is architecting your curriculum and generating study materials. Please wait a moment.',
    'gen.please_wait': 'Please Wait',
    'Build All Lessons': 'Build All Lessons',
    'Building...': 'Building...',
    'Go Back to Classrooms': 'Go Back to Classrooms',
    'alert.rebuild_title': 'Build Lessons?',
    'alert.rebuild_msg': 'This will use AI to write all textbook pages and generate practice questions for every topic in this curriculum. This takes 2-3 minutes. Continue?',
    'assign.no_responses': 'No students have submitted this assignment yet.',
    'assign.submitted': 'Submitted',
    'assign.class_avg': 'Class Avg',
    'assign.correct': 'Correct',
    'assign.student_answer': "Student's Answer",
    'assign.correct_answer': 'Correct Answer',
    'assign.view_details': 'View Details',
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
    'signIn': 'Sign In',
    'no_classrooms_found': 'No classrooms found',
    'approved': 'Approved',
    'pending': 'Pending',
    'class.name': 'Classroom Name',
    'class.name_placeholder': 'e.g. Spanish 101 — Fall 2026',
    'class.magic_pdf': 'Magic PDF',
    'class.magic_pdf_wizard_desc': 'Upload a textbook and let AI build your course automatically.',
    'class.drop_pdf': 'Click to select or drag & drop your PDF',
    'class.extract_step': 'Extract & Analyze',
    'class.extract_desc': 'AI will scan your PDF and extract the table of contents, chapters, and topics.',
    'class.deep_extract': 'Deep Extract',
    'class.extract_done': 'Extraction Complete',
    'class.advanced': 'Advanced Options',
    'class.start_pipeline': 'Launch Architect',
    'class.pdf_limit': 'Searchable text PDFs only. Scanned images are not supported.',
    'class.extracting': 'Extracting...',
    'class.analyzing': 'Analyzing your PDF...',
    'class.select_pdf_first': 'Please select a PDF file first.',
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
    'alert.select_pdf': 'Please select a PDF file',
    'message.placeholder': 'Write your message here...',
    'admin.hard_reset_title': 'Admin Hard Reset',
    'admin.hard_reset_desc': 'This will wipe EVERYTHING. Users, courses, data - gone forever.',
    'admin.hard_reset_btn': 'HARD RESET SYSTEM',
    'alert.hard_reset_success_title': 'System Reset',
    'alert.hard_reset_success_msg': 'The database has been completely wiped. You will be logged out now.',
    'alert.hard_reset_failed': 'Hard reset failed: {error}',
    'student.delete_account': 'Delete Account',
    'student.delete_account_title': 'Delete Account',
    'student.delete_account_msg': 'Are you sure you want to permanently delete your account? All your progress and data will be lost forever.',
    'student.delete_confirm_btn': 'Yes, Delete My Account',
  },
  tr: {
    'ai.select_lang': '1. Dil Seçin',
    'ai.target_level': '2. Hedef Seviye',
    'ai.course_name': '3. Kurs Adı',
    'ai.name_placeholder': 'ör. Yoğun İspanyolca Yaz Kursu',
    'ai.gen_curriculum': 'Müfredat Oluştur ✨',
    'loading': 'yükleniyor',
    'lang.Spanish': 'İspanyolca',
    'lang.German': 'Almanca',
    'lang.French': 'Fransızca',
    'lang.Italian': 'İtalyanca',
    'lang.Portuguese': 'Portekizce',
    'lang.Russian': 'Rusça',
    'lang.Chinese': 'Çince',
    'lang.Japanese': 'Japonca',
    'lang.Arabic': 'Arapça',
    'lang.Turkish': 'Türkçe',
    'lang.Dutch': 'Felemenkçe',
    'lang.Swedish': 'İsveççe',
    'lang.Korean': 'Korece',
    'lang.Greek': 'Yunanca',
    langBtn: 'Dil: TR',
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
    'class.extract_step': 'Ayrıştır ve Analiz Et',
    'class.extract_desc': 'Yapay zeka PDF\'nizi tarayacak ve içindekiler tablosunu, üniteleri ve konuları ayrıştıracaktır.',
    'class.extracting': 'Ayrıştırılıyor...',
    'class.analyzing': 'PDF\'niz analiz ediliyor...',
    'class.extract_done': 'Ayrıştırma Tamamlandı',
    'class.deep_extract': 'Derin Ayrıştırma',
    'class.select_pdf_first': 'Lütfen önce bir PDF dosyası seçin.',
    'gen.preparing': 'Hazırlanıyor...',
    'gen.building': 'İçerik Oluşturuluyor...',
    'gen.please_wait': 'Lütfen Bekleyin',
    'class.building_msg_student': 'Öğretmen sınıf yapısını yeniden oluşturuyor...',
    'Build All Lessons': 'Dersleri Oluştur',
    'Building...': 'Hazırlanıyor...',
    'Go Back to Classrooms': 'Sınıflara Geri Dön',
    'alert.rebuild_title': 'Dersleri Oluştur?',
    'alert.rebuild_msg': 'Bu işlem, müfredattaki her konu için yapay zeka kullanarak ders içerikleri ve alıştırma soruları oluşturacaktır. Bu işlem 2-3 dakika sürebilir. Devam edilsin mi?',
    'assign.no_responses': 'Henüz hiçbir öğrenci bu ödevi teslim etmedi.',
    'assign.submitted': 'Teslim Edildi',
    'assign.class_avg': 'Sınıf Ort.',
    'assign.correct': 'Doğru',
    'assign.student_answer': 'Öğrenci Cevabı',
    'assign.correct_answer': 'Doğru Cevap',
    'assign.view_details': 'Detayları Gör',
    'assign.top_score': 'En Yüksek Puan',
    'assign.detailed_answers': 'Detaylı Cevaplar',
    'assign.left_blank': '[Boş Bırakıldı]',
    'assign.preview': 'Önizleme',
    'assign.complete': 'Ödev Tamamlandı!',
    'assign.recorded': 'Puanın kaydedildi.',
    'assign.back': 'Ödevlere Dön',
    'assign.retry': 'Hata oluştu, tekrar deneyin.',
    'Material': 'Materyal',
    'study': 'Materyal',
    'book': 'Kitap',
    'study.units': 'Üniteler',
    'study.vocabulary': 'Kelime Rehberi',
    'study.grammar': 'Dilbilgisi ve Kurallar',
    'study.usage': 'Pratik Kullanım',
    'study.complete': 'Ders Tamamlandı',
    'study.preview': 'Ders Önizleme',
    'study.back': 'Geri',
    'study.next': 'Sonraki Sayfa',
    'study.ready': 'Alıştırma Yapmaya Hazırsın!',
    'study.preview_end': 'Ders Materyali Sonu',
    'study.preview_msg': 'Bu dersin öğrencileriniz için nasıl göründüğüdür.',
    'study.ready_msg': 'Şimdi bilgini test etme zamanı.',
    'study.start_practice': '🚀 Alıştırma Seansını Başlat',
    'confirm.rebuild_title': 'Dersleri Oluştur?',
    'confirm.rebuild_msg': 'Bu işlem müfredattaki her konu için yapay zeka kullanarak ders içerikleri ve alıştırma soruları oluşturacaktır. Bu işlem 2-3 dakika sürebilir. Devam edilsin mi?',
    'confirm.rebuild_ok': 'Evet, Her Şeyi Oluştur',
    'confirm.rebuild_cancel': 'İptal',
    'confirm.rearchitect_title': 'Müfredatı Yeniden Tasarla?',
    'confirm.rearchitect_msg': 'Bu işlem mevcut tüm üniteleri, konuları ve ders materyallerini KALICI OLARAK SİLECEKTİR. Yeni bir müfredat yapısı oluşturmak için Yapay Zeka Mimarı sayfasına yönlendirileceksiniz. Devam edilsin mi?',
    'confirm.rearchitect_ok': 'Evet, Sil ve Yeniden Başlat',
    'Re-Architect': 'Yeniden Tasarla',
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
    'no_classrooms_found': 'Sınıf bulunamadı',
    'student.enter_code': 'Öğretmeniniz tarafından verilen 5 haneli kodu girin',
    'signIn': 'Giriş Yap',
    'class.name': 'Sınıf Adı',
    'class.name_placeholder': 'örn. İspanyolca 101 — Güz 2026',
    'class.magic_pdf': 'Sihirli PDF',
    'class.magic_pdf_wizard_desc': 'Bir ders kitabı yükleyin ve yapay zeka dersinizi otomatik olarak oluştursun.',
    'class.drop_pdf': 'PDF dosyanızı seçmek için tıklayın veya sürükleyip bırakın',
    'class.extract_step': 'Çıkar & Analiz Et',
    'class.extract_desc': 'Yapay zeka PDF\'nizi tarayacak ve içindekileri, bölümleri ve konuları çıkaracaktır.',
    'class.deep_extract': 'Derin Çıkarım',
    'class.extract_done': 'Çıkarım Tamamlandı',
    'class.advanced': 'Gelişmiş Seçenekler',
    'class.start_pipeline': 'Mimarı Başlat',
    'class.pdf_limit': 'Yalnızca aranabilir metin içeren PDF\'ler. Taranmış resimler desteklenmez.',
    'class.toc_manual_hint': 'Kitabın içindekiler kısmını veya müfredatınızı buraya yapıştırın. Yapay zeka bunu yol haritası olarak kullanacaktır.',
    'class.building_msg': 'İçeriğiniz hala hazırlanıyor — kısa süre sonra tekrar kontrol edin.',
    'class.no_curriculum': 'Bu sınıf için müfredat verisi bulunamadı.',
    'low_mastery': 'Düşük Başarı',
    'low_engagement': 'Düşük Katılım',
    'critical_risk': 'Kritik Risk',
    'LOW_MASTERY': 'Düşük Başarı',
    'LOW_ENGAGEMENT': 'Düşük Katılım',
    'CRITICAL_RISK': 'Kritik Risk',
    'UNKNOWN': 'Bilinmiyor',
    loginTitle: 'Öğrenci Girişi', signInTab: 'Giriş Yap', registerTab: 'Kayıt Ol', signInHint: 'Devam etmek için giriş yapın', emailLabel: 'E-posta', passwordLabel: 'Şifre', signInBtn: 'Giriş Yap', joinClass: 'Sınıfa Katıl', registerHint: 'Öğrenci hesabı oluştur', nameLabel: 'Ad Soyad', registerBtn: 'Hesap Oluştur', lecturerAccess: 'Öğretmen Girişi', signOut: 'Çıkış Yap', rememberMe: 'Beni Hatırla',
    'Lecturer Login': 'Öğretmen Girişi', 'Sign in with your email and password': 'E-posta ve şifrenizle giriş yapın',
    'Student Login': 'Öğrenci Girişi', 'Log in with your student number': 'Öğrenci numaranızla giriş yapın',
    'Student Number': 'Öğrenci Numarası', '(required)': '(ilk girişte gerekli)',
    'Your Full Name': 'Adınız Soyadınız', 'e.g. 2021123456': 'Örn: 2021123456',
    'login.class_code': 'Sınıf Kodu (5 hane)', 'login.class_code_placeholder': 'Örn: 12345',
    'login.student_number': 'Öğrenci Numarası',
    student_number: 'Öğrenci Numarası',
    full_name: 'Ad Soyad',
    student_number_placeholder: 'Örn: 2021123456',
    full_name_placeholder: 'Adınız Soyadınız',
    Email: 'E-posta', Password: 'Şifre', 'Full Name': 'Ad Soyad',
    'Sign In': 'Giriş Yap', 'Remember Me': 'Beni Hatırla', 'Sign Out': 'Çıkış Yap',
    messageTeacher: 'Öğretmene Mesaj',
    messageStudent: 'Öğrenciye Mesaj',
    inbox: 'Mesajlar', study: 'Çalışma',
    newChat: 'Yeni Mesaj',
    selectStudent: 'Öğrenci Seç',
    searchStudent: 'Öğrenci ara...',
    noNewChats: 'Mesaj atılacak yeni öğrenci yok.',
    startChat: 'Mesaj Başlat',
    typeReply: 'Mesajınızı yazın...',
    sendBtn: 'Gönder',
    Lecturer: 'Öğretmen', Student: 'Öğrenci',
    '👩‍🏫 Lecturer': '👩‍🏫 Öğretmen', '🎓 Student': '🎓 Öğrenci',
    // Student dashboard
    home: 'Ana Sayfa', practice: 'Alıştırma', quizzes: 'Sınavlar', myProgress: 'Gelişimim',
    keepUp: 'Harika gidiyorsun, devam et!', overallMastery: 'Genel Başarı', strongTopics: 'İyi Olduğum Konular', needsWork: 'Eksiğim Olan Konular', topicsStudied: 'Çalışılan Konular', currentChapter: 'Mevcut Ünite',
    selectPractice: 'Alıştırma yapmak için bir konu seçin', availableQuizzes: 'Mevcut Sınavlar', trackMastery: 'Konulardaki başarı durumunuzu takip edin',
    takeQuiz: 'Sınava Başla', view: 'Görüntüle', close: 'Kapat', done: 'Bitti', submit: 'Gönder', check: 'Kontrol Et',
    yourScore: 'Puanınız', questions: 'soru', correct: 'doğru',
    incorrectAns: 'Yanlış. Doğru cevap:', correctAns: 'Doğru cevap:', correctMsg: 'Doğru! ✓',
    takeQuizBtn: 'Sınavı Başlat', viewBtn: 'Görüntüle',
    noQuizzes: 'Henüz sınav yok.', noAssignments: 'Henüz ödev yok.',
    // Lecturer nav & tabs
    Lecturer: 'Öğretmen', Student: 'Öğrenci',
    Overview: 'Genel Bakış', Curriculum: 'Müfredat', Activities: 'Etkinlikler', Students: 'Öğrenciler', Reports: 'Raporlar', Dashboard: 'Kontrol Paneli', Assignments: 'Ödevler', Quizzes: 'Sınavlar', 'My Stats': 'İstatistiklerim',
    // Overview stats
    STUDENTS: 'ÖĞRENCİLER', 'CLASS_MASTERY': 'SINIF BAŞARISI', 'AT_RISK': 'RİSKLİ', 'TOP_PERFORMERS': 'EN İYİLER',
    'Class Mastery': 'Sınıf Başarısı', 'At Risk': 'Riskli', 'Top Performers': 'En İyiler',
    at_risk_students: '⚠️ Riskli Öğrenciler', topic_difficulty: '📊 Konu Zorluğu',
    'active_this_week': '{count} Bu hafta aktif', 'avg_across_topics': 'Tüm konularda ortalama',
    'students_needing_attention': 'Dikkat gerektiren öğrenciler', 'mastery_above_80': '%80 üzeri başarı',
    no_at_risk: 'Riskli öğrenci yok 🎉', mastery: 'başarı',
    'welcomeBack': 'Tekrar Hoş Geldin, {name}',
    'Welcome back,': 'Tekrar Hoş Geldin,',
    // Data Management
    data_mgmt: 'Veri Yönetimi',
    erase_all_btn: 'Tüm Verileri Sil',
    erase_all_desc: 'Tüm öğrencileri, sınav sonuçlarını, ödev teslimlerini ve başarı puanlarını siler. Müfredat ve öğretmen hesabınız korunur.',
    // Activities
    'In-Class Activities': 'Sınıf İçi Etkinlikler', 'Generate and launch live activities': 'Canlı etkinlikler oluştur ve başlat',
    '🚀 Launch Activity': '🚀 Etkinlik Başlat', 'Select Chapter & Topic': 'Ünite ve Konu Seç',
    'Generate Activity': 'Etkinlik Oluştur', 'Loading curriculum...': 'Müfredat yükleniyor...',
    // Quiz Management
    'Quiz Management': 'Sınav Yönetimi', 'Create and manage quizzes': 'Sınav oluştur ve yönet',
    '➕ Create New Quiz': '➕ Yeni Sınav Oluştur', 'Quiz Title': 'Sınav Başlığı',
    Chapter: 'Konu Seçin', 'All chapters': 'Tüm Konular', AllTopics: 'Tüm Konular', Questions: 'Soru Sayısı', 'Create Quiz': 'Sınav Oluştur',
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
    Lecturer: 'Öğretmen', Student: 'Öğrenci',
    settings: 'Ayarlar', language: 'Dil',
    'signOut': 'Çıkış Yap',
    'signIn': 'Giriş Yap',
    'no_classrooms_found': 'Sınıf bulunamadı',
    'approved': 'Onaylandı',
    'pending': 'Bekliyor',
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
    'draft.no_auto_gen': 'Otomatik olarak soru oluşturulamadı.',
    'draft.click_add': 'Lütfen manuel olarak oluşturmak için "➕ Soru Ekle" butonuna tıklayın.',
    // Classroom Selection
    'class.selection': 'Sınıf Seçimi',
    'class.subtitle': 'Yönetmek için bir sınıf seçin veya yeni bir tane oluşturun',
    'class.create': 'PDF\'den Yeni Sınıf Oluştur',
    'class.create_generic': 'Yeni Sınıf Oluştur',
    'class.create_title': '🛠️ Yeni Sınıf Yöntemi',
    'class.choose_method': 'Kursunuzu nasıl oluşturmak istediğinizi seçin',
    'class.magic_pdf': 'Sihirli PDF',
    'class.magic_pdf_desc': 'Bir PDF ders kitabı yükleyin ve yapay zekanın kursu oluşturmasına izin verin.',
    'class.ai_architect': 'Yapay Zeka Mimarı',
    'class.ai_architect_desc': 'PDF yok mu? Yapay zekaya dili ve seviyeyi söyleyin, o kursu oluştursun.',
    'ai.tell_teach': 'Yapay zekaya ne öğretmek istediğinizi söyleyin',
    'ai.select_lang': '1. Dil Seçin',
    'ai.target_level': '2. Hedef Seviye',
    'ai.course_name': '3. Kurs Adı',
    'ai.name_placeholder': 'Örn: Yoğun İspanyolca Yaz Kursu',
    'ai.gen_curriculum': 'Müfredatı Oluştur ✨',
    'ai.clear_cache': 'Önbellekteki Taslakları Temizle',
    'ai.regenerate': 'Yeniden Oluştur',
    'ai.cache_cleared': 'Tüm önbellekteki müfredat taslakları silindi. Bir sonraki oluşturma yeni müfredat üretecektir.',
    'ai.cache_cleared_title': 'Önbellek Temizlendi',
    'ai.review_title': 'Müfredatı İncele',
    'ai.review_desc': 'Yapay zeka bu konuları önerdi. Bunları düzenleyebilir veya kaldırabilirsiniz.',
    'class.add_topic': 'Konu Ekle',
    'class.topic_name_placeholder': 'Yeni Konu Adı',
    'class.build_btn': 'Sınıfı Oluştur 🚀',
    'ai.add_unit': 'Yeni Ünite Ekle',
    'ai.new_unit_title': 'Yeni Ünite Başlığı',
    'class.enter': 'Sınıfa Gir',
    'class.delete_confirm': 'Bu sınıfı silmek istediğinizden emin misiniz? Öğrenciler, notlar ve içerik dahil tüm veriler kalıcı olarak silinecektir.',
    'class.upload_pdf': 'PDF Ders Kitabı Yükle',
    'class.toc_range': 'İçindekiler Sayfa Aralığı (örn. 1-25)',
    'class.toc_placeholder': '1-25',
    'class.processing': 'PDF işleniyor ve müfredat oluşturuluyor... Bu işlem bir dakika sürebilir.',
    'class.start_pipeline': 'İşlemi Başlat',
    'class.toc_manual': '2. Manuel Müfredat / İçindekiler (Buraya yapıştırın)',
    'class.toc_manual_hint': 'Kitabın içindekilerini veya müfredatınızı yapıştırın. Yapay zeka bunu yol haritası olarak kullanacaktır.',
    'class.toc_range_hint': 'Burayı boş bırakırsanız, yapay zeka yukarıdaki Manuel Müfredatı birincil kaynak olarak kullanacaktır.',

    'class.create_success': 'Sınıf başarıyla oluşturuldu!',
    'class.share_msg': 'Derse başlamak için Katılım Kodunu öğrencilerinizle paylaşın.',
    'class.create_success_full': 'Sınıf başarıyla oluşturuldu! \n\nKatılım Kodu: {code}\n\nDerse başlamak için Katılım Kodunu öğrencilerinizle paylaşın.',
    'answer': 'Cevaplar',
    'responses': 'Sonuçlar',
    'gen.loading': 'Sorular oluşturuluyor...',
    'gen.time': 'Bu işlem 5-10 saniye sürebilir.',
    'gen.preparing': 'Sınıf Hazırlanıyor...',
    'gen.building': 'Dersler Oluşturuluyor...',
    'gen.preparing_content': 'İçerik Hazırlanıyor',
    'gen.preparing_desc': 'Yapay zeka bu dersi kurguluyor. Lütfen birkaç dakika bekleyin.',
    'gen.generating': 'Sorular oluşturuluyor...',
    'gen.ai_architecting': 'Yapay zekamız müfredatınızı kurguluyor ve çalışma materyallerini oluşturuyor. Lütfen bekleyin.',
    'gen.please_wait': 'Lütfen Bekleyin',
    'Unit': 'Ünite',
    'SelectTopic': 'Bir konu seçin...',
    'AllChapters': 'Tüm üniteler',
    'ok': 'Tamam',
    'cancel': 'İptal',
    'no_classrooms_found': 'Sınıf bulunamadı. İlkini oluşturun!',
    'class.delete_building_msg': 'Oluşturma işlemini durdurmak ve bu sınıfı silmek istediğinize emin misiniz?',
    'confirm.start_quiz_title': 'Sınava Başla',
    'confirm.start_quiz_msg': 'Sınava başlamak istediğinize emin misiniz? Başladıktan sonra bitirmeniz gerekir.',
    'confirm.start_assignment_title': 'Ödeve Başla',
    'confirm.start_assignment_msg': 'Emin misiniz? Ödeve başladıktan sonra geri dönemezsiniz, yarıda bırakmak yarım teslim yapmanıza sebep olabilir.',
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
    'Tebrikler!': 'Tebrikler!',
    'is ready!': 'hazır!',
    'Detecting...': 'Algılanıyor...',
    'class.pdf_status_cancel': 'Hayır, kontrol edeceğim',
    'prac.dialogue_order': 'Diyaloğu doğru sıraya dizin:',
    'prac.dialogue': 'Diyalog',
    'no_messages': 'Mesaj yok.',
    'tap_explain': '🧠 Açıklamak için dokun',
    'explain_ai': 'Yapay Zeka ile Açıkla 🤖',
    'ai_error': 'Yapay zeka şu anda bu kelimeyi açıklayamadı.',
    'explain_more': 'Daha fazla detay için \'Açıkla\'ya tekrar tıklayın.',
    'ai_analyzing': 'Yapay zeka cevabınızı analiz ediyor...',
    'No assignments yet.': 'Henüz ödev yok.',
    'No quizzes yet.': 'Henüz sınav yok.',
    'prac.dialogue': 'Diyalog',
    'draft.lang_warning': 'Not: Soru içeriğinin dili oluşturma sırasında sabitlenir ve arayüz diliyle birlikte değişmez.',
    'message.placeholder': 'Mesajınızı buraya yazın...',
    'alert.select_pdf': 'Lütfen bir PDF dosyası seçin',
    // Student Portal
    'student.welcome': 'AulaAI\'ya Hoş Geldiniz',
    'admin.hard_reset_title': 'Yönetici Tam Sıfırlama',
    'admin.hard_reset_desc': 'Bu işlem HER ŞEYİ silecektir. Kullanıcılar, kurslar, veriler - sonsuza kadar yok olacak.',
    'admin.hard_reset_btn': 'SİSTEMİ TAMAMEN SIFIRLA',
    'alert.hard_reset_success_title': 'Sistem Sıfırlandı',
    'alert.hard_reset_success_msg': 'Veritabanı tamamen temizlendi. Şimdi çıkış yapacaksınız.',
    'alert.hard_reset_failed': 'Tam sıfırlama başarısız oldu: {error}',
    'student.select_class': 'Öğrenmeye devam etmek için bir sınıf seçin',
    'student.join_new': 'Yeni Sınıfa Katıl',
    'student.join_title': 'Sınıfa Katıl',
    'student.enter_code': 'Öğretmeniniz tarafından verilen 5 haneli kodu girin',
    'student.join_btn': 'Sınıfa Katıl',
    'student.pin_required': 'Güvenlik PIN\'i Gerekli',
    'student.pin_desc': 'Bu sınıf için 4 haneli PIN kodunuzu girin.',
    'student.pin_setup': 'İlk Kez Giriş',
    'student.pin_setup_desc': 'Gelecekteki girişleriniz için bu sınıfa özel 4 haneli bir PIN kodu belirleyin.',
    'student.waiting': 'Onay Bekleniyor',
    'student.waiting_desc': 'Öğretmeniniz başvurunuzu incelediğinde sınıfa girebileceksiniz. Lütfen bu sayfayı yenileyin veya daha sonra tekrar deneyin.',
    'student.invalid_pin': 'Geçersiz PIN. Lütfen tekrar deneyin.',
    'student.pin': 'PIN',
    'student.leave': 'Ayrıl',
    'student.leave_title': 'Sınıftan Ayrıl',
    'student.leave_msg': '"{name}" sınıfından ayrılmak istediğinize emin misiniz? Bu sınıftaki tüm ilerlemeniz, puanlarınız ve verileriniz kalıcı olarak silinecektir.',
    'alert.classroom_reset': 'Sınıf Sıfırlandı',
    'alert.classroom_reset_msg': 'Öğretmeniniz bu sınıfı sıfırladı. Sınıf seçim ekranına yönlendirildiniz.',
    select_study_topic: 'Çalışmak için bir konu seçin',
    'student.delete_account': 'Hesabı Sil',
    'student.delete_account_title': 'Hesabı Sil',
    'student.delete_account_msg': 'Hesabınızı kalıcı olarak silmek istediğinizden emin misiniz? Tüm ilerlemeniz ve verileriniz sonsuza dek kaybolacak.',
    'student.delete_confirm_btn': 'Evet, Hesabımı Sil',
  }
};

function t(key, data = {}) {
  try {
    const lang = localStorage.getItem('aula_lang') || 'en';
    let str = (i18n[lang] && i18n[lang][key]) || (i18n['en'] && i18n['en'][key]) || key;
    if (typeof str !== 'string') str = String(str || key);

    Object.keys(data).forEach(k => {
      str = str.replace(new RegExp(`{${k}}`, 'g'), String(data[k] || ''));
    });
    return str;
  } catch (e) {
    console.error('Translation error:', e);
    return String(key);
  }
}

function applyTranslations() {
  // Sync open modal FIRST
  const modal = document.getElementById('confirm-modal');
  if (modal && !modal.classList.contains('hidden')) {
    const titleKey = modal.getAttribute('data-title-key');
    const msgKey = modal.getAttribute('data-msg-key');
    const msgDataStr = modal.getAttribute('data-msg-data');
    let msgData = {};
    try { if (msgDataStr) msgData = JSON.parse(msgDataStr); } catch (e) { }

    const titleEl = document.getElementById('confirm-title');
    const msgEl = document.getElementById('confirm-message');
    const okEl = document.getElementById('confirm-ok-btn');
    const cancelEl = document.getElementById('confirm-cancel-btn');

    if (titleKey && titleEl) titleEl.textContent = t(titleKey);
    if (msgKey && msgEl) msgEl.textContent = t(msgKey, msgData);

    const okK = modal.getAttribute('data-ok-key');
    const canK = modal.getAttribute('data-cancel-key');
    if (okK && okEl) okEl.textContent = t(okK);
    if (canK && cancelEl) cancelEl.textContent = t(canK);
  }

  document.querySelectorAll('[data-i18n]').forEach(el => {
    try {
      const key = el.getAttribute('data-i18n');
      const dataStr = el.getAttribute('data-i18n-data');
      let data = {};
      try { if (dataStr) data = JSON.parse(dataStr); } catch (e) { }

      const translation = t(key, data);

      // Safety: Don't overwrite buttons that are currently showing a "loading" spinner
      if (el.tagName === 'BUTTON' && el.querySelector('.spinner-small')) return;
      if (el.disabled && el.innerHTML.includes('spinner')) return;

      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = translation;
      } else {
        el.textContent = translation;
      }
    } catch (e) { console.error('Loop error:', e); }
  });

  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    try { el.placeholder = t(el.getAttribute('data-i18n-placeholder')); } catch (e) { }
  });

  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    try { el.title = t(el.getAttribute('data-i18n-title')); } catch (e) { }
  });

  if (typeof currentUser !== 'undefined' && currentUser) {
    if (currentUser.role === 'lecturer') {
      const overviewGreeting = document.getElementById('overview-greeting');
      if (overviewGreeting) overviewGreeting.textContent = t('welcomeBack', { name: currentUser.name.split(' ').pop() });
    } else if (currentUser.role === 'student') {
      const studentGreeting = document.getElementById('student-greeting');
      if (studentGreeting) studentGreeting.textContent = t('welcomeBack', { name: currentUser.name }) + '!';
    }
  }

  const langBtn = document.getElementById('lang-btn');
  if (langBtn) {
    langBtn.setAttribute('data-i18n', 'langBtn');
    langBtn.textContent = t('langBtn');
  }
  const sidebarLangLabel = document.getElementById('sidebar-lang-label');
  if (sidebarLangLabel) {
    sidebarLangLabel.textContent = currentLang === 'en' ? 'TR' : 'EN';
  }

  if (_lastReportData && document.getElementById('tab-reports').classList.contains('active')) {
    renderReport(_lastReportData);
  }

  // Refresh dynamic components that don't use simple data-i18n
  if (document.getElementById('ai-architect-modal') && !document.getElementById('ai-architect-modal').classList.contains('hidden')) {
    renderAiLanguages();
  }
}

function toggleLanguage() {
  currentLang = currentLang === 'en' ? 'tr' : 'en';
  localStorage.setItem('aula_lang', currentLang);

  // Update state immediately
  applyTranslations();

  if (_lastReportData) renderReport(_lastReportData);

  // Re-render all dynamic content SYNCHRONOUSLY using cached data
  if (currentUser) {
    if (currentUser.role === 'lecturer') {
      if (currentCourse) renderLecturerSync();
      else if (_lastClassroomsData) renderClassroomSelection(_lastClassroomsData);
    } else {
      if (currentCourse) renderStudentSync();
      else renderStudentPortal();
    }
  }

  // Re-render activity preview if visible
  const preview = document.getElementById('activity-preview');
  if (preview && !preview.classList.contains('hidden') && _lastActivityData) {
    preview.innerHTML = '<h2 style="margin-bottom:20px">📋 ' + (_lastActivityData.topic?.title || '') + '</h2>' + (_lastActivityData.activities || []).map((a, i) => renderActivityCard(a, i, 'preview')).join('');
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

  const greetingEl = document.getElementById('overview-greeting');
  if (greetingEl) {
    greetingEl.setAttribute('data-i18n', 'welcomeBack');
    greetingEl.setAttribute('data-i18n-data', JSON.stringify({ name: currentUser.name.split(' ').pop() }));
  }

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
  document.getElementById('student-greeting').textContent = t('welcomeBack', { name: currentUser.name }) + '!';

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
  let match = t.match(/How do you say '(.*)' in (.*)\?/);
  if (match) {
    const wordTR = vocabTR[match[1]] || match[1];
    const langTR = vocabTR[match[2]] || match[2];
    t = `${langTR}'da '${wordTR}' nasıl denir?`;
  }
  return vocabTR[t] || t;
}

function translateOption(text) {
  if (currentLang !== 'tr') return text;
  return vocabTR[text] || text;
}

async function api(path, opts = {}) {
  let url = '/api' + path;

  // Auto-append user identity for role-aware endpoints
  if (currentUser && currentUser.id) {
    const parsedUrl = new URL(url, window.location.origin);
    // Only append if not already present to avoid duplicates
    if (!parsedUrl.searchParams.has('user_id')) {
      parsedUrl.searchParams.set('user_id', currentUser.id);
      parsedUrl.searchParams.set('role', currentUser.role || '');
      url = parsedUrl.pathname + parsedUrl.search + parsedUrl.hash;
    }
  }

  const res = await fetch(url, {
    method: opts.method || 'GET',
    headers: opts.body ? { 'Content-Type': 'application/json' } : {},
    body: opts.body ? JSON.stringify(opts.body) : undefined
  });

  if (res.status === 404 && currentUser && currentUser.role === 'student' && currentCourse) {
    // If we are in a course and get a 404, it might be deleted
    const data = await res.json();
    if (data.error === "Course not found" || data.error === "Not found") {
      localStorage.removeItem('aula_last_course');
      await showAlert("Classroom Deleted", "This classroom has been deleted by the lecturer. You are being redirected to your portal.");
      window.location.reload(); // Re-fetch portal state
      return { error: "Classroom Deleted" };
    }
    return data;
  }

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
  } else {
    document.getElementById('student-number').value = '2023001';
    document.getElementById('student-name-input').value = 'Alex Rivera';
  }
}

async function completeLogin(user, isFresh = false) {
  currentUser = user;
  if (user.course_id) courseId = user.course_id;

  if (isFresh) {
    localStorage.removeItem('aula_last_tab');
    localStorage.removeItem('aula_last_course');
  }

  // Session Storage is per-tab, so it's safer for multiple roles in different tabs
  sessionStorage.setItem('aula_user', JSON.stringify(user));

  const remember = document.getElementById('login-remember') ? document.getElementById('login-remember').checked : true;
  if (remember) {
    localStorage.setItem('aula_user', JSON.stringify(user));
  }

  localStorage.setItem('aula_lang', currentLang);

  // Show Admin Panel if applicable
  const adminPanel = document.getElementById('admin-panel');
  if (adminPanel) {
    if (user.email === 'atunca96@gmail.com') adminPanel.classList.remove('hidden');
    else adminPanel.classList.add('hidden');
  }

  if (currentUser.status === 'pending') {
    try {
      const check = await api('/user/status'); // api() helper will now append the ID correctly
      if (check && check.status === 'approved') {
        currentUser.status = 'approved';
        sessionStorage.setItem('aula_user', JSON.stringify(currentUser));
        if (remember) localStorage.setItem('aula_user', JSON.stringify(currentUser));
      }
    } catch (e) { }

    if (currentUser.status === 'pending') {
      showScreen('waiting-room-screen');
      if (window._waitingPoll) clearInterval(window._waitingPoll);
      window._waitingPoll = setInterval(async () => {
        try {
          const check = await api('/user/status?user_id=' + currentUser.id + (currentUser.course_id ? '&course_id=' + currentUser.course_id : ''));
          if (check && check.status === 'approved') {
            clearInterval(window._waitingPoll);
            currentUser.status = 'approved';
            localStorage.setItem('aula_user', JSON.stringify(currentUser));
            sessionStorage.setItem('aula_user', JSON.stringify(currentUser));
            window.location.reload();
          } else if (check && (check.error === 'User not found' || check.error === 'course_deleted')) {
            clearInterval(window._waitingPoll);
            localStorage.removeItem('aula_last_course');
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
    // Global Student Portal
    const savedCourse = localStorage.getItem('aula_last_course');
    if (savedCourse) {
      await selectClassroom(savedCourse, false);
    } else {
      showScreen('student-portal-screen');
      await refreshStudentEnrollments();
    }
  }
  startLiveSync();
}

async function showClassroomSelection() {
  localStorage.removeItem('aula_last_course');
  localStorage.removeItem('aula_last_tab');
  currentCourse = null; // Clear state
  showScreen('classroom-selection-screen');
  const courses = await api('/courses?t=' + Date.now());
  _lastClassroomsData = courses;
  renderClassroomSelection(courses);
  applyTranslations();
}

async function showStudentPortal() {
  localStorage.removeItem('aula_last_course');
  localStorage.removeItem('aula_last_tab');
  currentCourse = null; // Clear state
  showScreen('student-portal-screen');
  await refreshStudentEnrollments();
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
    const isBuilding = c.is_building === 1;
    const isPhase1 = c.language === "Detecting...";

    return `<div class="card classroom-card" style="position:relative; overflow:hidden; display:flex; flex-direction:column; justify-content:space-between; border:1px solid var(--border); opacity: ${isPhase1 ? '0.65' : '1'}; transition: opacity 0.3s ease;">
        ${isBuilding ? '<div style="position:absolute; top:0; left:0; right:0; height:4px; background:linear-gradient(90deg, #6366f1, #a855f7); animation: slide 2s linear infinite;"></div>' : ''}
        <div class="card-body">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                <span style="font-size:12px; font-weight:700; color:var(--accent); text-transform:uppercase; letter-spacing:1px;" ${c.language === 'Detecting...' ? 'data-i18n="gen.detecting"' : ''}>${c.language === 'Detecting...' ? t('gen.detecting') : (c.language || 'Unknown').toUpperCase()}</span>
                <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); deleteClassroom('${c.id}', '${esc(c.name)}')" style="color:var(--danger); padding:4px;">🗑️</button>
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
              <p style="color:var(--accent); font-size:12px; font-weight:500; margin-bottom:12px; text-align:center; animation: pulse 1.5s infinite; display:flex; align-items:center; justify-content:center; gap:6px;">
                ⏳ <span data-i18n="${isPhase1 ? 'gen.preparing' : 'gen.building'}">${isPhase1 ? t('gen.preparing') : t('gen.building')}</span>
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
  // Clear last topic if switching courses
  if (localStorage.getItem('aula_last_course') !== id) {
    localStorage.removeItem('aula_last_topic');
    localStorage.removeItem('aula_last_page');
  }

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
  currentChatStudentName = null;
  currentChatCourseId = null;
  const inboxBackBtn = document.getElementById('inbox-back-btn');
  if (inboxBackBtn) inboxBackBtn.classList.add('hidden');
  const inboxReplyArea = document.getElementById('inbox-reply-area');
  if (inboxReplyArea) inboxReplyArea.classList.add('hidden');
  const inboxTitle = document.getElementById('inbox-title');
  if (inboxTitle) inboxTitle.innerHTML = `💬 <span data-i18n="inbox">${t('inbox')}</span>`;

  // 2. Fetch course data
  const courses = await api('/courses');
  let course = courses.find(c => c.id === id);

  // Fallback if the course was deleted/consolidated
  if (!course && courses.length > 0) {
    course = courses[0];
    id = course.id;
  }

  courseId = id;
  if (course) {
    if (currentUser.role === 'student' && course.enrollment_status !== 'approved') {
      showScreen('waiting-room-screen');
      startWaitingRoomPoll(courseId);
      return;
    }

    const navName = document.getElementById(currentUser.role === 'lecturer' ? 'nav-course-name' : 'student-nav-course-name');
    const navCode = document.getElementById(currentUser.role === 'lecturer' ? 'nav-course-code' : 'student-nav-course-code');

    if (navName) navName.textContent = course.name;
    if (navCode) {
      navCode.textContent = '#' + (course.code || '00000');
      navCode.classList.remove('hidden');
    }
  }

  const buildBanner = document.getElementById(currentUser.role === 'lecturer' ? 'lecturer-building-banner' : 'student-building-banner');
  if (buildBanner) {
    if (course && course.is_building) {
      buildBanner.classList.remove('hidden');
    } else {
      buildBanner.classList.add('hidden');
    }
  }

  currentCourse = course;
  try {
    const currData = await api('/curriculum?course_id=' + courseId);
    curriculum = Array.isArray(currData) ? currData : [];
  } catch (e) {
    console.error("Failed to load curriculum:", e);
    curriculum = [];
  }

  let bookPath = course ? course.textbook : '';
  const isAiGenerated = course && (course.textbook === 'AI Generated' || (course.textbook || '').toUpperCase().includes('AI GENERATED'));

  const pdfViewerSrc = (!isAiGenerated && bookPath && bookPath.length > 7 && bookPath.startsWith('/books/')) ? bookPath : '';

  document.querySelectorAll('.pdf-viewer').forEach(el => {
    if (el.src !== pdfViewerSrc) el.src = pdfViewerSrc || 'about:blank';
  });
  document.querySelectorAll('a[data-tab="book"], a[data-tab="s-book"], .pdf-download-link').forEach(el => {
    if (el.tagName === 'A' && pdfViewerSrc) el.href = pdfViewerSrc;
  });

  document.querySelectorAll('.mobile-book-title').forEach(el => el.textContent = course ? course.name : 'Textbook');
  document.querySelectorAll('.mobile-book-title-thumb').forEach(el => el.textContent = course ? course.name : 'Textbook');
  document.querySelectorAll('.mobile-book-link').forEach(el => el.href = pdfViewerSrc || '#');

  document.querySelectorAll('.pdf-empty-state').forEach(el => {
    if (pdfViewerSrc) el.classList.add('hidden');
    else el.classList.remove('hidden');
  });

  document.querySelectorAll('.book-subtitle').forEach(el => el.textContent = course ? course.name : 'Textbook');

  document.querySelectorAll('.pdf-container').forEach(el => el.classList.toggle('hidden', isAiGenerated));

  const lectBookTab = document.getElementById('lecturer-book-tab');
  const lectStudyTab = document.getElementById('lecturer-study-tab');
  const sStudyTabBtn = document.getElementById('nav-s-study-tab');
  const sBookTabBtn = document.getElementById('nav-s-book-tab');

  if (currentUser.role === 'lecturer') {
    if (lectBookTab) {
      lectBookTab.style.display = pdfViewerSrc ? '' : 'none';
      const label = lectBookTab.querySelector('.tab-label');
      if (label) label.textContent = t('Read Textbook') || 'Read Textbook';
    }
    if (lectStudyTab) {
      lectStudyTab.style.display = '';
      const label = lectStudyTab.querySelector('.tab-label');
      if (label) label.textContent = t('Material') || 'Material';
    }
  }

  if (currentUser.role === 'student') {
    if (sStudyTabBtn) sStudyTabBtn.style.display = '';
    if (sBookTabBtn) sBookTabBtn.style.display = pdfViewerSrc ? '' : 'none';

    const sMainTitle = document.getElementById('s-study-tab-main-title');
    if (sMainTitle) {
      sMainTitle.textContent = t('study') || 'Study Lessons';
    }
  }

  if (currentUser.role === 'student') {
    renderStudyBook();
  } else if (currentUser.role === 'lecturer') {
    renderStudyBook();
  }

  if (currentUser.role === 'lecturer') {
    showScreen('lecturer-dashboard');
    const targetTab = localStorage.getItem('aula_last_tab') || 'overview';
    let finalTab = targetTab;

    const tabBtn = document.querySelector(`#lecturer-dashboard [data-tab="${finalTab}"]`);
    if (tabBtn) switchTab(tabBtn);
    await initLecturer();

    if (finalTab === 'book') {
      renderStudyBook();
      const lastTopic = localStorage.getItem('aula_last_topic');
      const lastPage = parseInt(localStorage.getItem('aula_last_page') || '0');
      if (lastTopic) setTimeout(() => showStudyTopic(lastTopic, lastPage), 100);
    }
  } else {
    showScreen('student-dashboard');
    let targetTab = localStorage.getItem('aula_last_tab') || 's-home';

    const tabBtn = document.querySelector(`#student-dashboard [data-tab="${targetTab}"]`);
    if (tabBtn) switchTab(tabBtn, true); // skipLoad=true since we call initStudent after
    else {
      const homeBtn = document.querySelector(`#student-dashboard [data-tab="s-home"]`);
      if (homeBtn) switchTab(homeBtn, true);
    }
    await initStudent();

    if (targetTab === 's-study-tab') {
      const lastTopic = localStorage.getItem('aula_last_topic');
      const lastPage = parseInt(localStorage.getItem('aula_last_page') || '0');
      if (lastTopic) setTimeout(() => showStudyTopic(lastTopic, lastPage), 100);
    }
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

let _currentAiStep = 1;
let _selectedAiLanguage = null;
let _selectedAiLevel = null;

function openClassroomMethodModal() {
  localStorage.removeItem('aula_rearchitecting_id');
  document.getElementById('classroom-method-modal').classList.remove('hidden');
}

function closeClassroomMethodModal() {
  document.getElementById('classroom-method-modal').classList.add('hidden');
}

function startPdfCreationFlow() {
  closeClassroomMethodModal();
  openCreateClassroomModal();
}

function startAiArchitectFlow() {
  closeClassroomMethodModal();
  document.getElementById('ai-architect-modal').classList.remove('hidden');
  renderAiLanguages();
  _currentAiStep = 1;
  showAiStep(1);
}

function closeAiArchitectModal() {
  document.getElementById('ai-architect-modal').classList.add('hidden');
}

function showAiStep(step) {
  document.querySelectorAll('[id^="ai-step-"]').forEach(el => el.classList.add('hidden'));
  document.getElementById(`ai-step-${step}`).classList.remove('hidden');
  _currentAiStep = step;
}

function nextAiStep() {
  if (_currentAiStep < 3) showAiStep(_currentAiStep + 1);
}

function prevAiStep() {
  if (_currentAiStep > 1) showAiStep(_currentAiStep - 1);
}

async function clearBlueprintCache() {
  const res = await api('/blueprint/delete-all', { method: 'POST', body: {} });
  if (res && res.success) {
    showAlert(t('ai.cache_cleared_title'), t('ai.cache_cleared'));
  } else {
    showAlert(t('error'), 'Failed to clear cache', true);
  }
}

async function regenerateAiCurriculum() {
  if (!_selectedAiLanguage || !_selectedAiLevel) return;

  // 1. Delete the cached blueprint for this language/level
  await api('/blueprint/delete', { method: 'POST', body: { language: _selectedAiLanguage, level: _selectedAiLevel } });

  // 2. Go back to step 1 and auto-trigger generation
  showAiStep(1);
  await generateAiCurriculum();
}

function renderAiLanguages() {
  const grid = document.getElementById('ai-language-grid');
  if (!grid) return;
  const langs = [
    { id: 'Spanish', icon: '🇪🇸' },
    { id: 'German', icon: '🇩🇪' },
    { id: 'French', icon: '🇫🇷' },
    { id: 'Italian', icon: '🇮🇹' },
    { id: 'Portuguese', icon: '🇵🇹' },
    { id: 'Russian', icon: '🇷🇺' },
    { id: 'Chinese', icon: '🇨🇳' },
    { id: 'Japanese', icon: '🇯🇵' },
    { id: 'Arabic', icon: '🇸🇦' },
    { id: 'Turkish', icon: '🇹🇷' },
    { id: 'Dutch', icon: '🇳🇱' },
    { id: 'Swedish', icon: '🇸🇪' },
    { id: 'Korean', icon: '🇰🇷' },
    { id: 'Greek', icon: '🇬🇷' }
  ];
  grid.innerHTML = langs.map(l => `
    <button class="btn btn-ghost lang-btn" onclick="selectAiLanguage('${l.id}', this)" style="display:flex; flex-direction:column; gap:8px; padding:16px; border:2px solid ${_selectedAiLanguage === l.id ? 'var(--accent)' : 'var(--border)'}; border-radius:12px; height:auto; min-width:0;">
      <span style="font-size:24px;">${l.icon}</span>
      <span style="font-size:12px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; width:100%;">${t('lang.' + l.id)}</span>
    </button>
  `).join('');
}

function selectAiLanguage(id, btn) {
  _selectedAiLanguage = id;
  document.querySelectorAll('.lang-btn').forEach(b => b.style.borderColor = 'var(--border)');
  btn.style.borderColor = 'var(--accent)';
}

function selectAiLevel(level) {
  _selectedAiLevel = level;
  document.querySelectorAll('.level-btn').forEach(b => {
    b.classList.remove('btn-primary');
    b.classList.add('btn-ghost');
  });
  const activeBtn = Array.from(document.querySelectorAll('.level-btn')).find(b => b.textContent === level);
  if (activeBtn) {
    activeBtn.classList.remove('btn-ghost');
    activeBtn.classList.add('btn-primary');
  }
}

async function generateAiCurriculum() {
  if (!_selectedAiLanguage || !_selectedAiLevel) return showAlert(t('error'), 'Please select language and level', true);
  const courseName = document.getElementById('ai-course-name').value;
  if (!courseName) return showAlert(t('error'), 'Please enter a course name', true);

  const btn = document.getElementById('ai-gen-btn');
  btn.disabled = true;
  const oldText = btn.innerHTML;
  btn.innerHTML = '<div class="spinner-small" style="display:inline-block"></div> ' + t('loading');

  try {
    const data = await api('/draft/curriculum', { method: 'POST', body: { language: _selectedAiLanguage, level: _selectedAiLevel } });
    if (data.syllabus) {
      renderAiSyllabusEditor(data.syllabus);
      nextAiStep();
    } else {
      showAlert(t('error'), 'Failed to generate syllabus', true);
    }
  } catch (e) {
    showAlert(t('error'), 'Generation failed', true);
  } finally {
    btn.disabled = false;
    btn.innerHTML = oldText;
  }
}

function renderAiSyllabusEditor(syllabus) {
  const container = document.getElementById('ai-curriculum-list');
  if (!container) return;
  container.innerHTML = syllabus.map((chapter, i) => `
    <div class="syllabus-chapter" style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); padding:16px; border-radius:12px; margin-bottom:12px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <h4 style="margin:0; color:var(--accent-light);">Unit ${i + 1}</h4>
        <button class="btn btn-ghost btn-sm" onclick="this.closest('.syllabus-chapter').remove()" style="color:var(--danger)">🗑️</button>
      </div>
      <input type="text" class="text-input syllabus-title" value="${esc(chapter.title)}" style="margin-bottom:12px; font-weight:700; background:rgba(0,0,0,0.2);">
      <div class="topics-list">
        ${chapter.topics.map(topic => {
    const title = typeof topic === 'string' ? topic : (topic.title || '');
    return `
            <div class="topic-item" data-type="${topic.type || 'vocabulary'}" style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
              <span style="font-size:12px; color:var(--accent); cursor:pointer;" onclick="toggleTopicType(this)" title="Toggle Grammar/Vocabulary">${(topic.type || 'vocabulary') === 'grammar' ? '⚙️' : '•'}</span>
              <input type="text" class="text-input topic-title" value="${esc(title)}" style="font-size:13px; padding:6px 10px; background:rgba(0,0,0,0.1); flex:1;">
              <button class="btn btn-ghost btn-xs" onclick="this.parentElement.remove()">×</button>
            </div>
          `;
  }).join('')}
        <button class="btn btn-ghost btn-xs" style="font-size:11px; margin-top:4px;" onclick="addTopicToSyllabus(this)">+ ${t('class.add_topic') || 'Add Topic'}</button>
      </div>
    </div>
  `).join('');
}

function addUnitToAiArchitect() {
  const container = document.getElementById('ai-curriculum-list');
  if (!container) return;

  const unitIdx = container.querySelectorAll('.syllabus-chapter').length;
  const unitHtml = `
    <div class="syllabus-chapter" style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); padding:16px; border-radius:12px; margin-bottom:12px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <h4 style="margin:0; color:var(--accent-light);">${t('Unit')} ${unitIdx + 1}</h4>
        <button class="btn btn-ghost btn-sm" onclick="this.closest('.syllabus-chapter').remove()" style="color:var(--danger)">🗑️</button>
      </div>
      <input type="text" class="text-input syllabus-title" placeholder="${t('ai.new_unit_title')}" style="margin-bottom:12px; font-weight:700; background:rgba(0,0,0,0.2);">
      <div class="topics-list">
        <button class="btn btn-ghost btn-xs" style="font-size:11px; margin-top:4px;" onclick="addTopicToSyllabus(this)">+ ${t('class.add_topic') || 'Add Topic'}</button>
      </div>
    </div>
  `;

  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = unitHtml;
  container.appendChild(tempDiv.firstElementChild);
  container.scrollTop = container.scrollHeight;
  const input = container.lastElementChild.querySelector('input');
  if (input) input.focus();
}

function addTopicToSyllabus(btn) {
  const div = document.createElement('div');
  div.className = 'topic-item';
  div.style.cssText = 'display:flex; align-items:center; gap:8px; margin-bottom:8px;';
  div.innerHTML = `
    <span style="font-size:12px; color:var(--accent); cursor:pointer;" onclick="toggleTopicType(this)" title="Toggle Grammar/Vocabulary">•</span>
    <input type="text" class="text-input topic-title" placeholder="${t('class.topic_name_placeholder') || 'New Topic Name'}" style="font-size:13px; padding:6px 10px; background:rgba(0,0,0,0.1); flex:1;">
    <button class="btn btn-ghost btn-xs" onclick="this.parentElement.remove()">×</button>
  `;
  div.setAttribute('data-type', 'vocabulary');
  btn.before(div);
  div.querySelector('input').focus();
}

function toggleTopicType(span) {
  const item = span.closest('.topic-item');
  const current = item.getAttribute('data-type') || 'vocabulary';
  const next = current === 'vocabulary' ? 'grammar' : 'vocabulary';
  item.setAttribute('data-type', next);
  span.textContent = next === 'grammar' ? '⚙️' : '•';
}

async function buildAiClassroom() {
  const courseName = document.getElementById('ai-course-name').value;
  const chapters = [];
  document.querySelectorAll('.syllabus-chapter').forEach(chapterEl => {
    const title = chapterEl.querySelector('.syllabus-title').value;
    const topics = [];
    chapterEl.querySelectorAll('.topic-item').forEach(topicItem => {
      const topicInp = topicItem.querySelector('.topic-title');
      const type = topicItem.getAttribute('data-type') || 'vocabulary';
      topics.push({ title: topicInp.value, type: type });
    });
    chapters.push({ title, topics });
  });

  const btn = document.getElementById('ai-build-btn');
  btn.disabled = true;
  const oldContent = btn.innerHTML;
  btn.innerHTML = '<div class="spinner-small" style="display:inline-block"></div> ' + t('loading');

  try {
    const res = await api('/classroom/create-from-scratch', {
      method: 'POST',
      body: {
        course_name: courseName,
        language: _selectedAiLanguage,
        level: _selectedAiLevel,
        chapters,
        lecturer_id: currentUser.id,
        course_id: localStorage.getItem('aula_rearchitecting_id')
      }
    });
    localStorage.removeItem('aula_rearchitecting_id');
    if (res.success) {
      closeAiArchitectModal();
      showClassroomSelection();
    } else {
      showAlert(t('error'), res.error || 'Failed to build classroom', true);
    }
  } catch (e) {
    showAlert(t('error'), 'Build failed', true);
  } finally {
    btn.disabled = false;
    btn.innerHTML = oldContent;
  }
}

async function openCreateClassroomModal() {
  document.getElementById('create-classroom-modal').classList.remove('hidden');
  document.getElementById('creation-status').classList.add('hidden');
  document.getElementById('extract-status').classList.add('hidden');
  document.getElementById('extract-success').classList.add('hidden');
  document.getElementById('submit-creation-btn').disabled = false;
  document.getElementById('submit-creation-btn').style.opacity = '1';
  
  // Setup drag & drop
  const dropZone = document.getElementById('pdf-drop-zone');
  if (dropZone && !dropZone._initialized) {
    dropZone._initialized = true;
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.style.borderColor = 'var(--accent)';
      dropZone.style.background = 'rgba(139,92,246,0.06)';
    });
    dropZone.addEventListener('dragleave', () => {
      dropZone.style.borderColor = 'var(--border)';
      dropZone.style.background = 'rgba(255,255,255,0.02)';
    });
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.style.borderColor = 'var(--border)';
      dropZone.style.background = 'rgba(255,255,255,0.02)';
      const file = e.dataTransfer.files[0];
      if (file && file.type === 'application/pdf') {
        const input = document.getElementById('pdf-upload');
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        onPdfFileSelected(input);
      } else {
        showAlert(t('error'), 'Please drop a PDF file.', true);
      }
    });
  }
}

function onPdfFileSelected(input) {
  const file = input.files[0];
  if (!file) return;
  
  const emptyState = document.getElementById('pdf-drop-empty');
  const filledState = document.getElementById('pdf-drop-filled');
  const nameEl = document.getElementById('pdf-file-name');
  const sizeEl = document.getElementById('pdf-file-size');
  
  nameEl.textContent = file.name;
  const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
  sizeEl.textContent = `${sizeMB} MB — PDF`;
  
  emptyState.classList.add('hidden');
  filledState.classList.remove('hidden');
  filledState.style.display = 'flex';
  
  // Auto-set course name from filename if empty
  const nameInput = document.getElementById('course-name-input');
  if (nameInput && !nameInput.value.trim()) {
    const cleanName = file.name.replace(/\.pdf$/i, '').replace(/[_-]/g, ' ');
    nameInput.value = cleanName;
  }
}

function clearPdfUpload() {
  const input = document.getElementById('pdf-upload');
  input.value = '';
  document.getElementById('pdf-drop-empty').classList.remove('hidden');
  const filled = document.getElementById('pdf-drop-filled');
  filled.classList.add('hidden');
  filled.style.display = 'none';
  document.getElementById('extract-success').classList.add('hidden');
  document.getElementById('markdown-analysis-input').value = '';
}

async function closeCreateClassroomModal(force = false) {
  const name = document.getElementById('course-name-input').value.trim();
  const md = document.getElementById('markdown-analysis-input').value.trim();
  const toc = document.getElementById('manual-toc-input').value.trim();

  if (!force && (name || md || toc)) {
    const confirmed = await showConfirmModal('confirm.cancel_creation_title', 'confirm.cancel_creation_msg', true);
    if (!confirmed) return;
  }
  document.getElementById('create-classroom-modal').classList.add('hidden');
}

async function triggerDeepExtract() {
  const fileInput = document.getElementById('pdf-upload');
  const mdInput = document.getElementById('markdown-analysis-input');
  const statusEl = document.getElementById('extract-status');
  const successEl = document.getElementById('extract-success');
  const btn = document.getElementById('deep-extract-btn');

  if (!fileInput.files[0]) {
    return showAlert(t('missing_info'), t('class.select_pdf_first') || 'Please select a PDF file first.', true);
  }

  statusEl.classList.remove('hidden');
  successEl.classList.add('hidden');
  btn.disabled = true;
  btn.style.opacity = '0.5';
  btn.textContent = '⏳ ' + (t('class.extracting') || 'Extracting...');

  const formData = new FormData();
  formData.append('pdf', fileInput.files[0]);
  formData.append('toc_range', document.getElementById('pdf-toc-range').value || '1-25');
  const pdfLang = document.getElementById('pdf-language-select') ? document.getElementById('pdf-language-select').value : 'Detecting...';
  formData.append('language', pdfLang);

  try {
    const res = await fetch('/api/marker/extract', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (!data.success) throw new Error(data.error);

    mdInput.value = data.markdown;
    _lastExtractedLanguage = data.language;
    
    // Auto-set course name if still empty
    const nameInput = document.getElementById('course-name-input');
    if (nameInput && !nameInput.value.trim() && data.language) {
      nameInput.value = `${data.language} Course`;
    }

    // Show success banner
    statusEl.classList.add('hidden');
    successEl.classList.remove('hidden');
    const summaryEl = document.getElementById('extract-summary');
    const lineCount = data.markdown.split('\n').filter(l => l.trim()).length;
    summaryEl.textContent = `${data.language || 'Unknown'} detected • ${lineCount} content lines extracted`;
    
    // Auto-expand advanced section so user can see/edit the content
    // document.getElementById('advanced-section').open = true;
    
  } catch (err) {
    console.error('Extraction Error:', err);
    statusEl.classList.add('hidden');
    showAlert(t('error'), 'Deep extraction failed: ' + err.message, true);
  } finally {
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.innerHTML = '⚡ ' + (t('class.deep_extract') || 'Deep Extract');
  }
}

async function handleCreateClassroom(e) {
  e.preventDefault();
  const nameInput = document.getElementById('course-name-input');
  const fileInput = document.getElementById('pdf-upload');
  const manualTocInput = document.getElementById('manual-toc-input');
  const markdownInput = document.getElementById('markdown-analysis-input');
  const statusEl = document.getElementById('creation-status');
  const btn = document.getElementById('submit-creation-btn');

  if (!fileInput.files[0] && !markdownInput.value.trim()) {
    return showAlert(t('missing_info'), t('class.select_pdf_first') || 'Please select a PDF file first.', true);
  }

  // Auto-extract if they skipped step 3
  if (fileInput.files[0] && !markdownInput.value.trim()) {
    const confirmed = await showConfirmModal('Extract PDF', 'You haven\'t extracted the PDF yet. Should we do that automatically before building?', true, null, false, 'Yes, extract it', 'Cancel');
    if (!confirmed) return;
    
    // Attempt auto extraction
    try {
      await triggerDeepExtract();
    } catch (e) {
      return; // Stop if extraction fails
    }
    
    if (!markdownInput.value.trim()) {
      return showAlert(t('error'), 'Auto-extraction failed to produce content.', true);
    }
  }

  const formData = new FormData();
  formData.append('course_name', nameInput.value.trim());
  
  // Send PDF if available (for textbook rendering/book tab)
  if (fileInput.files[0]) {
    formData.append('pdf', fileInput.files[0]);
  }
  
  formData.append('external_markdown', markdownInput.value.trim());
  formData.append('manual_toc', manualTocInput.value.trim());
  formData.append('lecturer_id', currentUser.id);
  if (_lastExtractedLanguage) {
    formData.append('language', _lastExtractedLanguage);
  }

  statusEl.classList.remove('hidden');
  btn.disabled = true;
  btn.style.opacity = '0.5';

  try {
    const res = await fetch('/api/classroom/create-from-pdf', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (!data.success) throw new Error(data.error);

    await showAlert('success', 'class.create_success_full', false, { code: data.code });
    closeCreateClassroomModal(true);
    if (typeof _buildingCourses !== 'undefined') _buildingCourses.push(data.course_id);
    await showClassroomSelection();
  } catch (err) {
    console.error('Creation Error:', err);
    statusEl.classList.add('hidden');
    btn.disabled = false;
    btn.style.opacity = '1';
    showAlert(t('error'), err.message || t('class.create_failed'), true);
  }
}

async function handleStudentLogin(e) {
  if (e) e.preventDefault();
  const btn = e ? e.target.querySelector('button[type="submit"]') : null;
  const num = document.getElementById('student-number').value.trim();
  const name = document.getElementById('student-name-input').value.trim();
  const errBox = document.getElementById('student-login-error');

  if (!num || !name) {
    errBox.textContent = t('missing_info');
    errBox.classList.remove('hidden');
    return;
  }

  if (btn) btn.disabled = true;
  errBox.classList.add('hidden');

  try {
    const res = await api('/student/login', {
      method: 'POST',
      body: { student_number: num, name: name }
    });

    if (res.error) {
      errBox.textContent = res.error;
      errBox.classList.remove('hidden');
      if (btn) btn.disabled = false;
    } else {
      await completeLogin(res.user, true);
      if (btn) btn.disabled = false;
    }
  } catch (err) {
    errBox.textContent = t('error');
    errBox.classList.remove('hidden');
    if (btn) btn.disabled = false;
  }
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
  localStorage.removeItem('aula_user');
  sessionStorage.removeItem('aula_user');
  localStorage.removeItem('aula_last_course');
  localStorage.removeItem('aula_last_tab');
  window.location.href = '/'; // Hard redirect to clear everything
}

// ── Visual Viewport Fix (Mobile Keyboard) ──
function initViewportFix() {
  // Simplified: No more viewport hacks needed for inline views.
  // We let the browser handle the keyboard natively.
}

window.addEventListener('DOMContentLoaded', () => {
  try {
    initViewportFix();

    // Apply translations based on saved preference
    applyTranslations();

    // Apply saved theme and HUD size
    const savedTheme = localStorage.getItem('aula_theme') || 'dark';
    setTheme(savedTheme);

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
  } catch (err) {
    console.error('INIT ERROR:', err);
    alert('Critical Initialization Error: ' + err.message);
    // Force show login screen as fallback
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const login = document.getElementById('login-screen');
    if (login) login.classList.add('active');
  }
});

function showScreen(id) {
  // Stop waiting room polling if we leave that screen
  if (id !== 'waiting-room-screen' && window._waitingPoll) {
    clearInterval(window._waitingPoll);
    window._waitingPoll = null;
  }
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const target = document.getElementById(id);
  if (target) target.classList.add('active');
}
document.addEventListener('focusin', (e) => {
  if (e.target.id === 'inbox-reply-text' || e.target.id === 'message-text') {
    setTimeout(() => {
      const cw = e.target.closest('.chat-wrapper');
      if (cw) {
        const msgList = cw.querySelector('#inbox-messages') || cw.querySelector('#student-chat-history');
        if (msgList && msgList.lastElementChild) {
          msgList.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }
      }
    }, 200);
  }
});

function switchTab(btn, skipLoad = false) {
  // Find which screen we are in (Lecturer or Student)
  const screen = btn.closest('.screen') || (currentUser.role === 'lecturer' ? document.getElementById('lecturer-dashboard') : document.getElementById('student-dashboard'));
  if (!screen) return;

  const tabId = btn.dataset.tab;
  if (!tabId) return;

  // LOCK: If building, prevent switching to non-essential tabs
  if (currentCourse && currentCourse.is_building === 1) {
    if (currentUser.role === 'lecturer') {
      const allowedTabs = ['overview', 'inbox', 'students-tab']; 
      if (!allowedTabs.includes(tabId)) {
        triggerBuildingFocus();
        return; 
      }
    } else if (currentUser.role === 'student') {
      const allowedTabs = ['s-home', 's-messages'];
      if (!allowedTabs.includes(tabId)) {
        triggerStudentBuildingFocus();
        return;
      }
    }
  }

  // Clean up any open chat overlays/locks when switching tabs
  closeMobileChat();
  document.body.style.overflow = '';

  // Update nav-tab active state (if top nav is visible)
  const nav = screen.querySelector('.topnav');
  if (nav) {
    nav.querySelectorAll('.nav-tab').forEach(t => {
      if (t.dataset.tab === tabId) t.classList.add('active');
      else t.classList.remove('active');
    });
  }

  // Update tab-panel active state
  const panels = screen.querySelectorAll('.tab-panel');
  panels.forEach(p => {
    if (p.id === 'tab-' + tabId) {
      p.classList.add('active');
      p.classList.remove('hidden');
      p.style.display = 'block';
      if (tabId === 'book' || tabId === 's-study-tab' || tabId === 'study-materials') renderStudyBook();
    } else {
      p.classList.remove('active');
      p.style.display = 'none';
    }
  });

  localStorage.setItem('aula_last_tab', tabId);

  if (!skipLoad) {
    if (tabId === 'inbox') loadInbox();
    if (tabId === 's-messages') loadStudentChat();
  }
}

function triggerBuildingFocus() {
  const banner = document.getElementById('lecturer-building-banner');
  const whisper = document.getElementById('architect-whisper');
  if (!banner) return;

  // Trigger animations
  banner.classList.add('shake-active', 'glow-active');
  if (whisper) whisper.classList.add('visible');

  // Clean up after 1s
  setTimeout(() => {
    banner.classList.remove('shake-active');
    setTimeout(() => {
      banner.classList.remove('glow-active');
      if (whisper) whisper.classList.remove('visible');
    }, 1000);
  }, 300);
}

function triggerStudentBuildingFocus() {
  const banner = document.getElementById('student-building-banner');
  if (!banner) return;

  // Trigger animations
  banner.classList.remove('hidden');
  banner.classList.add('shake-active', 'glow-active');

  // Clean up after 1s
  setTimeout(() => {
    banner.classList.remove('shake-active');
    setTimeout(() => {
      banner.classList.remove('glow-active');
    }, 1000);
  }, 300);
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

function closeMobileChat() {
  document.querySelectorAll('.chat-wrapper').forEach(w => w.classList.remove('is-active'));
  document.documentElement.classList.remove('chat-open');
  document.body.classList.remove('chat-open');

  // Show the lists again
  const inboxList = document.getElementById('inbox-list-container');
  if (inboxList) inboxList.style.display = '';
  const studentInboxList = document.querySelector('.student-messages-list');
  if (studentInboxList) studentInboxList.style.display = '';

  document.body.style.overflow = '';
  currentChatStudentId = null;
  currentChatStudentName = null;
  currentChatCourseId = null;
}

// ── Messages ──
let currentChatStudentId = null;
let currentChatStudentName = null;
let currentChatCourseId = null;

async function loadStudentChat() {
  if (!currentCourse) return;
  const wrapper = document.querySelector('#tab-s-messages .chat-wrapper');
  const isTabActive = document.getElementById('tab-s-messages')?.classList.contains('active');

  if (wrapper && window.innerWidth <= 768 && isTabActive) {
    // Small delay on refresh to ensure layout is ready
    setTimeout(() => {
      wrapper.classList.add('is-active');
      document.documentElement.classList.add('chat-open');

      // Hide the list to show chat inline
      if (window.innerWidth <= 768) {
        const inboxList = document.getElementById('inbox-list-container');
        if (inboxList && wrapper.id === 'inbox-chat-wrapper') inboxList.style.display = 'none';

        const studentInboxList = document.querySelector('.student-messages-list');
        if (studentInboxList && wrapper.id === 'student-chat-wrapper') studentInboxList.style.display = 'none';
      }

      document.body.classList.add('chat-open');
    }, 50);
  }

  const container = document.getElementById('student-chat-history');
  if (container) container.innerHTML = '<div style="display:flex; justify-content:center; padding:40px;"><div class="spinner"></div></div>';

  const messages = await api(`/messages?student_id=${currentUser.id}&course_id=${currentCourse.id}`);

  if (!messages || messages.length === 0) {
    if (container) container.innerHTML = `<p style="color:var(--text-muted); text-align:center; padding:20px;" data-i18n="no_messages">${t('no_messages')}</p>`;
    return;
  }

  if (container) {
    container.innerHTML = `<div class="chat-container" style="display:flex; flex-direction:column; gap:12px; padding:10px;">` + messages.map(m => {
      const isMe = m.sender === 'student';
      const dateObj = new Date(m.created_at.includes('Z') ? m.created_at : m.created_at.replace(' ', 'T') + 'Z');
      return `
        <div class="chat-bubble ${isMe ? 'sent' : 'received'}" 
             style="align-self:${isMe ? 'flex-end' : 'flex-start'}; background:${isMe ? 'var(--gradient-1)' : 'var(--bg-input)'}; color:${isMe ? 'white' : 'var(--text-main)'}; padding:12px 16px; border-radius:18px; max-width:85%; box-shadow:0 2px 4px rgba(0,0,0,0.1); border:${isMe ? 'none' : '1px solid var(--border)'}; ${isMe ? 'border-bottom-right-radius:4px' : 'border-bottom-left-radius:4px'};">
          ${!isMe ? `<div class="chat-sender" style="font-size:11px; font-weight:700; margin-bottom:4px; color:var(--accent-light);">${t('Lecturer')}</div>` : ''}
          ${esc(m.content)}
          <span class="chat-time" style="display:block; font-size:10px; opacity:0.7; margin-top:4px; text-align:${isMe ? 'right' : 'left'};">${dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      `;
    }).join('') + `</div>`;
  }
  container.scrollTop = container.scrollHeight;

  messages.filter(m => m.sender === 'lecturer' && !m.is_read).forEach(m => {
    api('/message/read', { method: 'POST', body: { message_id: m.id } });
  });

  container.scrollTop = container.scrollHeight;
}

async function sendMessage() {
  const text = document.getElementById('message-text').value.trim();
  if (!text || !currentCourse) return;
  document.getElementById('message-text').value = '';
  await api('/message/send', {
    method: 'POST', body: {
      student_id: currentUser.id,
      course_id: currentCourse.id,
      sender: 'student',
      content: text
    }
  });
  await loadStudentChat();
}

async function loadInbox() {
  if (!currentCourse) return;
  closeMobileChat();

  // Fetch all messages for lecturer (global inbox)
  const messages = await api('/messages');
  const container = document.getElementById('inbox-messages');
  document.getElementById('inbox-back-btn').classList.add('hidden');
  document.getElementById('inbox-reply-area').classList.add('hidden');
  document.getElementById('inbox-title').innerHTML = `💬 <span data-i18n="inbox">${t('inbox')}</span>`;

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
    // Group by student + course to keep context clear
    const threadKey = `${m.student_id}_${m.course_id}`;
    if (!threads[threadKey]) {
      threads[threadKey] = {
        student_id: m.student_id,
        course_id: m.course_id,
        student_name: m.student_name,
        course_name: m.course_name,
        latest: m,
        unread: 0
      };
    } else {
      if (new Date(m.created_at) > new Date(threads[threadKey].latest.created_at)) {
        threads[threadKey].latest = m;
      }
    }
    if (m.sender === 'student' && !m.is_read) {
      threads[threadKey].unread++;
    }
  });

  const threadList = Object.entries(threads).sort((a, b) => new Date(b[1].latest.created_at) - new Date(a[1].latest.created_at));

  container.innerHTML = threadList.map(([key, data]) => `
    <div style="background:var(--bg-input); border:1px solid var(--border); border-radius:16px; padding:16px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; transition:var(--transition); margin-bottom:8px; box-shadow:var(--shadow-sm);" onclick="openChat('${data.student_id}', '${esc(data.student_name).replace(/'/g, "\\'")}', '${data.course_id}')">
      <div style="flex:1; min-width:0; margin-right:12px;">
        <div style="display:flex; align-items:center; gap:8px;">
           <div style="width:10px; height:10px; border-radius:50%; background:${data.unread > 0 ? 'var(--accent)' : 'transparent'};"></div>
           <strong style="font-size:16px; color:var(--text-primary); font-weight:700;">${esc(data.student_name)}</strong>
           <span style="font-size:10px; font-weight:700; color:var(--accent); background:rgba(99,102,241,0.1); padding:2px 8px; border-radius:6px; border:1px solid rgba(99,102,241,0.2);">${esc(data.course_name)}</span>
        </div>
        <div style="font-size:13px; color:var(--text-muted); margin-top:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding-left:18px;">
          ${data.latest.sender === 'lecturer' ? '<span style="color:var(--accent-light); font-weight:600;">' + t('You') + ':</span> ' : ''}${esc(data.latest.content)}
        </div>
      </div>
      <div style="display:flex; flex-direction:column; align-items:flex-end; gap:6px; flex-shrink:0;">
        <span style="font-size:11px; color:var(--text-muted);">${new Date(data.latest.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}</span>
        ${data.unread > 0 ? `<span style="background:var(--accent); color:#fff; border-radius:10px; padding:2px 8px; font-size:11px; font-weight:800;">${data.unread}</span>` : ''}
      </div>
    </div>
  `).join('');
}

async function openChat(studentId, studentName, cid) {
  currentChatStudentId = studentId;
  currentChatStudentName = studentName;
  const activeCourseId = cid || currentCourse?.id;
  currentChatCourseId = activeCourseId;

  const wrapper = document.querySelector('#tab-inbox .chat-wrapper');
  const isTabActive = document.getElementById('tab-inbox')?.classList.contains('active');

  if (wrapper && isTabActive) {
    const mobileTitle = document.getElementById('mobile-inbox-title');
    if (mobileTitle) mobileTitle.textContent = studentName;

    if (window.innerWidth <= 768) {
      setTimeout(() => {
        wrapper.classList.add('is-active');
        document.documentElement.classList.add('chat-open');
        document.body.classList.add('chat-open');
      }, 50);
    } else {
      wrapper.classList.add('is-active');
    }
  }

  document.getElementById('inbox-back-btn').classList.remove('hidden');
  document.getElementById('inbox-reply-area').classList.remove('hidden');
  document.getElementById('inbox-title').innerHTML = `💬 ${esc(studentName)}`;

  const container = document.getElementById('inbox-messages');
  if (container) container.innerHTML = '<div style="display:flex; justify-content:center; padding:40px;"><div class="spinner"></div></div>';

  const messages = await api(`/messages?student_id=${studentId}&course_id=${activeCourseId}`);

  if (container) {
    container.innerHTML = `<div class="chat-container" style="display:flex; flex-direction:column; gap:12px; padding:10px;">` + messages.map(m => {
      const isMe = m.sender === 'lecturer';
      const dateObj = new Date(m.created_at.includes('Z') ? m.created_at : m.created_at.replace(' ', 'T') + 'Z');
      return `
        <div class="chat-bubble ${isMe ? 'sent' : 'received'}"
             style="align-self:${isMe ? 'flex-end' : 'flex-start'}; background:${isMe ? 'var(--gradient-1)' : 'var(--bg-input)'}; color:${isMe ? 'white' : 'var(--text-main)'}; padding:12px 16px; border-radius:18px; max-width:85%; box-shadow:0 2px 4px rgba(0,0,0,0.1); border:${isMe ? 'none' : '1px solid var(--border)'}; ${isMe ? 'border-bottom-right-radius:4px' : 'border-bottom-left-radius:4px'};">
          ${isMe ? `<div class="chat-sender" style="font-size:11px; font-weight:700; margin-bottom:4px; color:rgba(255,255,255,0.7);">${t('Lecturer')}</div>` : ''}
          ${esc(m.content)}
          <span class="chat-time" style="display:block; font-size:10px; opacity:0.7; margin-top:4px; text-align:${isMe ? 'right' : 'left'};">${dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      `;
    }).join('') + `</div>`;
    container.scrollTop = container.scrollHeight;
  }

  messages.filter(m => m.sender === 'student' && !m.is_read).forEach(m => {
    api('/message/read', { method: 'POST', body: { message_id: m.id } });
  });

  const badge = document.getElementById('inbox-badge');
  if (badge) {
    const remaining = Math.max(0, parseInt(badge.textContent || '0') - messages.filter(m => m.sender === 'student' && !m.is_read).length);
    if (remaining > 0) {
      badge.textContent = remaining;
    } else {
      badge.style.display = 'none';
    }
  }
}

async function sendLecturerMessage() {
  const text = document.getElementById('inbox-reply-text').value.trim();
  if (!text || !currentChatStudentId || !currentChatCourseId) return;
  document.getElementById('inbox-reply-text').value = '';
  await api('/message/send', {
    method: 'POST', body: {
      student_id: currentChatStudentId,
      course_id: currentChatCourseId,
      sender: 'lecturer',
      content: text
    }
  });

  await openChat(currentChatStudentId, currentChatStudentName, currentChatCourseId);
}

// ── New Chat Logic ──
let _allStudentsCache = [];
let _existingChatIds = new Set();

async function openNewChatModal() {
  if (!currentCourse) return;
  const modal = document.getElementById('new-chat-modal');
  modal.classList.remove('hidden');
  const list = document.getElementById('new-chat-student-list');
  list.innerHTML = '<div style="display:flex; justify-content:center; padding:20px;"><div class="spinner"></div></div>';

  try {
    const students = await api(`/students?course_id=${currentCourse.id}`);
    _allStudentsCache = students || [];
    const messages = await api(`/messages?course_id=${currentCourse.id}`);
    _existingChatIds = new Set(messages.map(m => m.student_id));
    renderNewChatStudents();
  } catch (e) {
    list.innerHTML = '<p style="text-align:center; color:var(--danger);">Error loading students.</p>';
  }
}

function renderNewChatStudents() {
  const list = document.getElementById('new-chat-student-list');
  const searchInput = document.getElementById('student-search-input');
  const search = searchInput ? searchInput.value.toLowerCase() : '';

  const filtered = _allStudentsCache.filter(s => {
    const matchesSearch = s.name.toLowerCase().includes(search);
    const hasNoChat = !_existingChatIds.has(s.id);
    return matchesSearch && hasNoChat;
  });

  if (filtered.length === 0) {
    list.innerHTML = `<p style="text-align:center; color:var(--text-muted); padding:20px;" data-i18n="noNewChats">${t('noNewChats')}</p>`;
    return;
  }

  list.innerHTML = filtered.map(s => `
        <div class="new-chat-item" style="display:flex; align-items:center; justify-content:space-between; padding:12px; border:1px solid var(--border); border-radius:12px; background:var(--bg-input); cursor:pointer; margin-bottom:8px; transition:var(--transition);" onclick="startNewChat('${s.id}', '${esc(s.name).replace(/'/g, "\\'")}')" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'">
            <div style="font-weight:600; color:var(--text-primary);">${esc(s.name)}</div>
            <button class="btn btn-ghost btn-sm" style="color:var(--accent); font-size:12px;" data-i18n="startChat">${t('startChat')}</button>
        </div>
    `).join('');
}

function filterNewChatStudents() {
  renderNewChatStudents();
}

function startNewChat(studentId, studentName) {
  closeModal();
  openChat(studentId, studentName);
}

// ── Theme Toggle ──
function toggleTheme() {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  const newTheme = isLight ? 'dark' : 'light';
  setTheme(newTheme);
}

function setTheme(theme) {
  const btns = [document.getElementById('theme-toggle-btn'), document.getElementById('student-theme-toggle-btn')];
  if (theme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
    btns.forEach(btn => { if (btn) btn.textContent = '☀️'; });
  } else {
    document.documentElement.removeAttribute('data-theme');
    btns.forEach(btn => { if (btn) btn.textContent = '🌙'; });
  }
  localStorage.setItem('aula_theme', theme);
}

// Initial theme check
document.addEventListener('DOMContentLoaded', () => {
  const savedTheme = localStorage.getItem('aula_theme');
  if (savedTheme) setTheme(savedTheme);
});

// HUD Size logic removed

function masteryColor(s) { return s >= 0.75 ? 'var(--success)' : s >= 0.4 ? 'var(--warning)' : 'var(--danger)'; }
function masteryClass(s) { return s >= 0.75 ? 'success' : s >= 0.4 ? 'warning' : 'danger'; }

async function initLecturer() {
  const navUser = document.getElementById('nav-username');
  if (navUser) navUser.textContent = currentUser.name;

  const greeting = document.getElementById('overview-greeting');
  if (greeting) greeting.textContent = t('welcomeBack', { name: currentUser.name.split(' ').pop() });

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
    <div class="stat-card"><div class="stat-label" data-i18n="STUDENTS">STUDENTS</div><div class="stat-value accent">${s.total_students || 0}</div><div class="stat-sub"><span data-i18n-data='{"count":${s.active_students || 0}}' data-i18n="active_this_week">${s.active_students || 0} Active this week</span></div></div>
    <div class="stat-card"><div class="stat-label" data-i18n="CLASS_MASTERY">CLASS MASTERY</div><div class="stat-value ${masteryClass(s.class_avg_mastery)}">${Math.round((s.class_avg_mastery || 0) * 100)}%</div><div class="stat-sub" data-i18n="avg_across_topics">Average across all topics</div></div>
    <div class="stat-card"><div class="stat-label" data-i18n="AT_RISK">AT RISK</div><div class="stat-value ${s.at_risk_count > 0 ? 'danger' : 'success'}">${s.at_risk_count || 0}</div><div class="stat-sub" data-i18n="students_needing_attention">Students needing attention</div></div>
    <div class="stat-card"><div class="stat-label" data-i18n="TOP_PERFORMERS">TOP PERFORMERS</div><div class="stat-value success">${s.top_performer_count || 0}</div><div class="stat-sub" data-i18n="mastery_above_80">Mastery above 80%</div></div>`;

  const atRisk = report.at_risk_students || [];
  const atRiskList = document.getElementById('at-risk-list');
  if (atRisk.length === 0) {
    atRiskList.innerHTML = `<p style="color:var(--text-muted)" data-i18n="no_at_risk">No at-risk students 🎉</p>`;
  } else {
    atRiskList.innerHTML = atRisk.map(s => `<div class="risk-item"><div><span class="risk-name">${s.name}</span></div><div class="risk-badges"><span class="risk-badge ${s.overall_mastery < 0.4 ? 'critical' : 'warning'}">${Math.round(s.overall_mastery * 100)}% <span data-i18n="mastery">mastery</span></span>${s.flags.map(f => `<span class="risk-badge low" data-i18n="${f}">${t(f)}</span>`).join('')}</div></div>`).join('');
  }
  const td = report.topic_difficulty || {};
  const chartEl = document.getElementById('topic-difficulty-chart');
  if (chartEl) {
    chartEl.innerHTML = Object.entries(td).slice(0, 8).map(([name, score]) =>
      `<div class="progress-item"><div class="progress-label"><span>${name}</span><span>${Math.round(score * 100)}%</span></div><div class="progress-bar"><div class="progress-fill" style="width:${score * 100}%;background:${masteryColor(score)}"></div></div></div>`
    ).join('');
  }

  applyTranslations(); // Unify everything!
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
    if (subtitleEl) subtitleEl.setAttribute('data-i18n-data', JSON.stringify({ name: currentCourse?.name || '' })); // Optional: for more complex templates

    if (!curriculum || !Array.isArray(curriculum)) {
      document.getElementById('curriculum-tree').innerHTML = `<p style="color:var(--text-muted); padding:20px;">${t('class.no_curriculum')}</p>`;
      return;
    }

    const isBuilding = currentCourse && currentCourse.is_building;
    const treeEl = document.getElementById('curriculum-tree');
    const rebuildBtn = document.getElementById('rebuild-curriculum-btn');

    if (rebuildBtn) {
      rebuildBtn.disabled = isBuilding;
      rebuildBtn.style.opacity = isBuilding ? '0.5' : '1';
      const btnText = rebuildBtn.querySelector('span[data-i18n="Build Lessons"]') || rebuildBtn.querySelector('span:last-child');
      if (btnText) btnText.textContent = isBuilding ? t('Building...') : t('Build All Lessons');
    }

    treeEl.innerHTML = curriculum.map((ch, i) => {
      const cleanTitle = (ch.title || "").replace(/^(unit|chapter|lektion|tema|c\.|l\.)\s*\d+\s*[:\-]\s*/i, "").trim();
      const displayNum = i + 1;
      return `
      <div class="chapter-block">
        <div class="chapter-header" onclick="this.nextElementSibling.classList.toggle('open');this.querySelector('.chapter-toggle').textContent=this.nextElementSibling.classList.contains('open')?'▾':'▸'">
          <div style="display:flex;align-items:center;gap:12px;">
            <span class="chapter-num">${displayNum}</span>
            <span class="chapter-title">${esc(cleanTitle)}</span>
            <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation(); deleteChapter('${ch.id}', '${esc(ch.title)}')" style="color:var(--danger); padding:2px; margin-left:8px; font-size:12px;">🗑️</button>
          </div>
          <span class="chapter-toggle">▸</span>
        </div>
        <div class="chapter-topics">${(ch.topics || []).map(t_obj => {
          const cleanTopicTitle = (t_obj.title || "").replace(/^(topic|tema|item)\s*\d+\s*[:\-]\s*/i, "").trim();
          return `
          <div class="topic-item">
            <div class="topic-info">
              <span class="topic-type-badge ${t_obj.type}">${t_obj.type}</span>
              <span class="topic-name">${esc(cleanTopicTitle)}</span>
            </div>
            <div style="display:flex; align-items:center; gap:12px;">
              ${t_obj.pdf_url ? `<button class="btn btn-sm" style="background:var(--info); color:#fff; border:none; padding:4px 8px; border-radius:6px; font-size:14px" onclick="event.stopPropagation(); window.open('${t_obj.pdf_url}', '_blank')">📖</button>` : ''}
              <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation(); deleteTopic('${t_obj.id}', '${esc(t_obj.title)}')" style="color:var(--danger); padding:4px;">🗑️</button>
              <div class="topic-meta">
                <span>${t_obj.difficulty}</span>
                <span>${t_obj.question_count || 0} ${t('questions')}</span>
              </div>
            </div>
          </div>`}).join('')}</div>
      </div>`}).join('');
  } catch (err) {
    console.error('Render Error:', err);
  }
}

async function deleteChapter(id, title) {
  const ok = await showConfirmModal('confirm.delete_chapter', `Are you sure you want to delete chapter: ${title}?`, true, null, false, "Delete", "Cancel");
  if (!ok) return;
  const res = await api('/curriculum/chapter/delete', { method: 'POST', body: { chapter_id: id } });
  if (res.success) {
    curriculum = curriculum.filter(ch => ch.id !== id);
    renderCurriculum();
  }
}

async function deleteTopic(id, title) {
  const ok = await showConfirmModal('confirm.delete_topic', `Are you sure you want to delete topic: ${title}?`, true, null, false, "Delete", "Cancel");
  if (!ok) return;
  const res = await api('/curriculum/topic/delete', { method: 'POST', body: { topic_id: id } });
  if (res.success) {
    curriculum.forEach(ch => {
      if (ch.topics) ch.topics = ch.topics.filter(t => t.id !== id);
    });
    renderCurriculum();
  }
}

async function rebuildClassroom(force = false) {
  if (!currentCourse) return;
  
  if (!force) {
    const ok = await showConfirmModal(
      'confirm.rebuild_title',
      "confirm.rebuild_msg",
      false, null, false, "confirm.rebuild_ok", "confirm.rebuild_cancel"
    );
    if (!ok) return;
  }

  try {
    const res = await api('/classroom/rebuild', {
      method: 'POST',
      body: { course_id: currentCourse.id, force: force }
    });
    if (res.status === 'success') {
      currentCourse.is_building = 1;
      // HARD UI RESET
      const bannerId = currentUser.role === 'lecturer' ? 'lecturer-building-banner' : 'student-building-banner';
      const fillId = currentUser.role === 'lecturer' ? 'lecturer-progress-fill' : 'student-progress-fill';
      const textId = currentUser.role === 'lecturer' ? 'lecturer-progress-text' : 'student-progress-text';
      const b = document.getElementById(bannerId);
      const f = document.getElementById(fillId);
      const t = document.getElementById(textId);
      if (b) b.classList.remove('hidden');
      if (f) f.style.width = '0%';
      if (t) t.textContent = '0%';
      
      _buildStartTime = Date.now();
      renderCurriculum();
    } else {
      showAlert("Error", res.error || "Failed to start build");
    }
  } catch (err) {
    showAlert("Error", "Network error starting build");
  }
}

async function reArchitectCurriculum() {
  if (!currentCourse) return;
  const ok = await showConfirmModal(
    'confirm.rearchitect_title',
    'confirm.rearchitect_msg',
    true, null, false, 'confirm.rearchitect_ok', 'confirm.rebuild_cancel'
  );
  if (!ok) return;

  try {
    const res = await api('/classroom/wipe-curriculum', {
      method: 'POST',
      body: { course_id: currentCourse.id }
    });
    if (res.status === 'success' || res.success) {
      curriculum = [];
      if (currentCourse) {
        currentCourse.is_building = 0;
        currentCourse.progress = 0;
      }
      localStorage.setItem('aula_rearchitecting_id', currentCourse.id);
      startAiArchitectFlow();
      // Optional: fill in the classroom name
      const nameInp = document.getElementById('ai-course-name');
      if (nameInp) nameInp.value = currentCourse.name;
      renderCurriculum();
    } else {
      showAlert("Error", res.error || "Failed to wipe curriculum");
    }
  } catch (err) {
    showAlert("Error", "Network error wiping curriculum");
  }
}

function populateSelects() {
  let topicOpts = '', chapterOpts = '';
  curriculum.forEach((ch, idx) => {
    let title = ch.title || "";
    // Remove redundant "Unit X:" or "Chapter X:" if it already exists in the title
    const cleanTitle = title.replace(/^(unit|chapter|lektion|tema|c\.|l\.)\s*\d+\s*[:\-]\s*/i, "").trim();
    
    // Always use the index + 1 for the unit number to ensure they start at 1 and are sequential
    const displayNum = idx + 1;
    const displayTitle = `${t('Unit')} ${displayNum}: ${cleanTitle}`;
    
    chapterOpts += `<option value="${ch.id}">${displayTitle}</option>`;
    (ch.topics || []).forEach(t => { 
      const cleanT = (t.title || "").replace(/^(topic|tema|item)\s*\d+\s*[:\-]\s*/i, "").trim();
      topicOpts += `<option value="${t.id}">U${displayNum} — ${cleanT} (${t.type})</option>`; 
    });
  });
  document.getElementById('activity-topic-select').innerHTML = `<option value="">${t('SelectTopic')}</option>` + topicOpts;
  document.getElementById('quiz-chapter-select').innerHTML = `<option value="">${t('AllTopics')}</option>` + topicOpts;
  const as = document.getElementById('assignment-chapter-select');
  if (as) as.innerHTML = `<option value="">${t('AllTopics')}</option>` + topicOpts;
}

let activityProgressInterval = null;

function showGenerationLoading(el) {
  if (activityProgressInterval) clearInterval(activityProgressInterval);
  el.innerHTML = `
    <div style="padding:40px; text-align:center; background:var(--bg-card); border-radius:16px; border:1px solid var(--border); box-shadow:var(--shadow-lg); margin-top: 24px;">
      <div class="bot-animation" style="font-size:32px; margin-bottom:16px;">🤖</div>
      <h3 style="margin-bottom:12px;" data-i18n="gen.loading">${t('gen.loading')}</h3>
      <div class="progress-container" style="background:rgba(255,255,255,0.05); height:10px; border-radius:5px; max-width:320px; margin:0 auto; overflow:hidden; position:relative; border:1px solid rgba(255,255,255,0.1);">
        <div id="activity-progress-fill" style="width: 0%; height: 100%; background: var(--accent); transition: width 0.3s ease;"></div>
      </div>
      <p style="color:var(--accent); font-size:14px; font-weight:700; margin-top:12px;" id="activity-progress-text">0%</p>
      <p style="color:var(--text-muted); font-size:13px; margin-top:16px;" data-i18n="gen.time">${t('gen.time')}</p>
    </div>
    <style>
      .bot-animation {
        animation: bot-bounce 2s infinite ease-in-out;
        display: inline-block;
      }
      @keyframes bot-bounce {
        0%, 100% { transform: translateY(0) scale(1); }
        50% { transform: translateY(-12px) scale(1.1); }
      }
    </style>
  `;
}

function startActivityPolling(targetId, title) {
  const el = document.getElementById(targetId);
  if (!el) return;
  const fill = el.querySelector('#activity-progress-fill');
  const text = el.querySelector('#activity-progress-text');

  if (activityProgressInterval) clearInterval(activityProgressInterval);

  activityProgressInterval = setInterval(async () => {
    try {
      const data = await api(`/activity/progress?course_id=${courseId}&v=${Date.now()}`);
      if (data && !data.error) {
        if (fill) fill.style.width = data.percentage + '%';
        if (text) text.textContent = data.percentage + '%';
        if (data.status === 'done') {
          if (data.results && data.results.length > 0) {
            clearInterval(activityProgressInterval);
            _lastActivityData = { activities: data.results };
            const isStudent = currentUser.role === 'student';
            const header = `<div class="page-header" style="margin-top:24px"><h2>${title}</h2><button class="btn btn-outline btn-sm" onclick="${isStudent ? 'cancelPractice()' : `this.closest('#${targetId}').classList.add('hidden')`}">${t('close')}</button></div>`;
            document.getElementById(targetId).innerHTML = header + data.results.map((a, i) => renderActivityCard(a, i, targetId)).join('');
          } else {
            // Done but no results - wait a few more polls or show error
            if (!window._retryEmptyPoll) window._retryEmptyPoll = 0;
            window._retryEmptyPoll++;
            if (window._retryEmptyPoll > 10) {
                clearInterval(activityProgressInterval);
                document.getElementById(targetId).innerHTML = `<div style="padding:40px; text-align:center; color:var(--text-muted);">
                    <div style="font-size:48px; margin-bottom:16px;">🔍</div>
                    <div style="font-weight:700; margin-bottom:8px;">No questions found</div>
                    <div style="font-size:14px;">The AI couldn't generate valid questions for this specific topic content. Try a different topic or build the curriculum again.</div>
                </div>`;
            }
          }
        } else if (data.status === 'error') {
          clearInterval(activityProgressInterval);
          document.getElementById(targetId).innerHTML = `<div style="padding:20px; color:var(--danger); text-align:center;">Error generating activities.</div>`;
        }
      }
    } catch (e) { console.error("Poll Error:", e); }
  }, 300);
}

let draftProgressInterval = null;

function startDraftPolling(type, btn, originalText, callback) {
  const container = document.getElementById(`${type}-gen-progress`);
  const fill = document.getElementById(`${type}-gen-fill`);
  const pctText = document.getElementById(`${type}-gen-pct`);

  if (container) container.classList.remove('hidden');
  if (fill) fill.style.width = '0%';
  if (pctText) pctText.textContent = '0%';

  if (draftProgressInterval) clearInterval(draftProgressInterval);

  draftProgressInterval = setInterval(async () => {
    try {
      const data = await api(`/draft/progress?course_id=${courseId}&v=${Date.now()}`);

      if (data.status === 'generating') {
        const pct = data.percentage || 0;
        if (fill) fill.style.width = pct + '%';
        if (pctText) pctText.textContent = pct + '%';
      } else if (data.status === 'done') {
        clearInterval(draftProgressInterval);
        if (fill) fill.style.width = '100%';
        if (pctText) pctText.textContent = '100%';

        setTimeout(() => {
          if (container) container.classList.add('hidden');
          btn.textContent = originalText;
          btn.disabled = false;
          if (data.questions) callback(data.questions);
        }, 500);
      } else if (data.status === 'error') {
        clearInterval(draftProgressInterval);
        if (container) container.classList.add('hidden');
        btn.textContent = originalText;
        btn.disabled = false;
        showAlert(t('error'), 'Generation failed', true);
      }
    } catch (err) {
      console.error("Draft Polling Error:", err);
    }
  }, 300);
}

async function launchActivity() {
  const topicId = document.getElementById('activity-topic-select').value;
  if (!topicId) return showAlert(t('missing_info'), t('class.select_topic_msg') || (currentLang === 'tr' ? 'Lütfen bir konu seçin' : 'Please select a topic'), true);

  const preview = document.getElementById('activity-preview');
  preview.classList.remove('hidden');

  // Show Loading State
  showGenerationLoading(preview);

  const btn = document.getElementById('generate-activity-btn');
  if (btn) btn.disabled = true;

  try {
    // 1. Kick off the background task
    await api('/activity/start', {
      method: 'POST',
      body: { topic_id: topicId, course_id: courseId, count: 10 }
    });
    // 2. Start polling AFTER the task is successfully initiated
    startActivityPolling('activity-preview', '📋 ' + (t('Content Map') || 'Content Map'));
  } catch (err) {
    preview.innerHTML = `<div style="padding:20px; color:var(--danger); text-align:center; background:var(--danger-bg); border-radius:12px; border:1px solid var(--danger);">
      ${t('assign.retry')}
    </div>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderPromptHTML(a, isQuiz = false) {
  let p = formatActivityData(a.prompt);
  p = translatePrompt(p); // Preserve existing localization mechanism
  
  if (a.translation) {
    return `<div class="activity-prompt-wrapper" style="position:relative; display:inline-block; margin-bottom:8px; cursor:help;" 
      onmouseenter="this.querySelector('.activity-translation').style.display='block'" 
      onmouseleave="this.querySelector('.activity-translation').style.display='none'">
      <div class="activity-prompt" style="display:inline; border-bottom:1px dashed var(--text-muted); padding-bottom:2px;">${p}</div>
      <div class="activity-translation" style="font-size:13px; color:var(--text-muted); margin-top:8px; display:none; padding:10px 14px; background:var(--bg-card); border:1px solid var(--border); border-radius:8px; border-left:3px solid var(--accent); position:absolute; z-index:100; box-shadow:0 4px 12px rgba(0,0,0,0.5); width:max-content; max-width:400px; left:0; top:100%;"><i>${esc(a.translation)}</i></div>
    </div>`;
  }
  return `<div class="activity-prompt">${p}</div>`;
}

function renderActivityCard(a, idx, ctx) {
  const promptHTML = renderPromptHTML(a);
  const isLecturer = currentUser && currentUser.role === 'lecturer';
  const editBtns = isLecturer ? `
    <div style="position:absolute; top:12px; right:12px; display:flex; gap:6px; z-index:10;">
        <button class="btn btn-ghost btn-xs" onclick="editActivityQuestion('${esc(a.id)}', '${ctx}-${idx}', '${esc(a.type)}')" style="background:rgba(255,255,255,0.1); padding:4px;">✏️</button>
        <button class="btn btn-ghost btn-xs" onclick="deleteActivityQuestion('${esc(a.id)}', '${ctx}-${idx}')" style="background:rgba(255,59,48,0.1); color:var(--danger); padding:4px;">🗑️</button>
    </div>
  ` : '';

  if (a.type === 'mcq') return `<div class="activity-card" id="${ctx}-${idx}" style="position:relative">${editBtns}<div class="activity-type-label"><span data-i18n="draft.mcq">${t('draft.mcq')}</span></div>${promptHTML}<div class="options-grid">${(a.options || []).map(o => `<button class="option-btn" data-original="${esc(o)}" onclick="checkMCQ(this,'${escJS(a.answer)}','${ctx}-${idx}','${escJS(a.id)}')">${translateOption(o)}</button>`).join('')}</div><div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
  if (a.type === 'fill_blank') return `<div class="activity-card" id="${ctx}-${idx}" style="position:relative">${editBtns}<div class="activity-type-label"><span data-i18n="draft.fill_blank">${t('draft.fill_blank')}</span></div>${promptHTML}<div style="display:flex;gap:10px;align-items:center;margin-top:12px"><input class="fill-blank-input" id="inp-${ctx}-${idx}" data-i18n-placeholder="assign.type_answer" placeholder="${t('assign.type_answer')}" style="flex:1" onkeydown="if(event.key==='Enter')checkFill('${ctx}-${idx}','${escJS(a.answer)}','${escJS(a.id)}')"><button class="btn btn-primary btn-sm" onclick="checkFill('${ctx}-${idx}','${escJS(a.answer)}','${escJS(a.id)}')" data-i18n="check">${t('check')}</button></div>${a.hint ? `<div style="margin-top:8px;font-size:13px;color:var(--text-muted)">💡 ${a.hint}</div>` : ''}<div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
  if (a.type === 'dialogue_order') {
    const lines = a.scrambled_lines || [];
    const speakers = a.speakers || {};
    return `<div class="activity-card" id="${ctx}-${idx}" style="position:relative">${editBtns}<div class="activity-type-label">🗣️ <span data-i18n="prac.dialogue">${t('prac.dialogue')}</span></div><div class="activity-prompt" data-i18n="prac.dialogue_order">${t('prac.dialogue_order')}</div><div id="dialogue-${ctx}-${idx}" style="display:flex;flex-direction:column;gap:8px;margin-top:12px">${lines.map((line, li) => `<div class="dialogue-row" style="display:flex;align-items:center;gap:8px" data-line="${esc(line)}"><button class="btn btn-ghost btn-sm" onclick="moveDialogueLine(this,-1)" style="min-width:36px">▲</button><button class="btn btn-ghost btn-sm" onclick="moveDialogueLine(this,1)" style="min-width:36px">▼</button><div style="flex:1;padding:10px 14px;background:var(--bg-input);border:2px solid var(--border);border-radius:var(--radius-sm);font-size:14px"><span style="font-weight:600;color:var(--accent-light);margin-right:8px">${speakers[line] || '?'}:</span>${line}</div></div>`).join('')}</div><button class="btn btn-primary btn-sm" style="margin-top:12px" onclick="checkDialogue('${ctx}-${idx}','${esc(JSON.stringify(a.correct_order))}')">✓ <span data-i18n="check">${t('check')}</span></button><div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
  }
  return '';
}

async function editActivityQuestion(qid, cardId, type) {
  const card = document.getElementById(cardId);
  if (!card) return;

  // Find the original data from _lastActivityData
  const qData = (_lastActivityData?.activities || []).find(q => q.id === qid);
  if (!qData) return;

  // Switch to edit mode by replacing card innerHTML
  const originalContent = card.innerHTML;
  card.dataset.original = originalContent;

  card.innerHTML = `
        <div style="padding:10px;">
            <label style="display:block; font-size:11px; color:var(--accent); font-weight:700; text-transform:uppercase; margin-bottom:4px;">Edit Question</label>
            <input type="text" id="edit-prompt-${qid}" class="text-input" value="${esc(qData.prompt)}" style="margin-bottom:12px; background:rgba(0,0,0,0.2);" placeholder="Prompt">
            <input type="text" id="edit-answer-${qid}" class="text-input" value="${esc(qData.answer)}" style="margin-bottom:12px; background:rgba(0,0,0,0.2);" placeholder="Answer">
            ${type === 'mcq' ? `<input type="text" id="edit-distractors-${qid}" class="text-input" value="${esc((qData.distractors || []).join(', '))}" style="margin-bottom:12px; background:rgba(0,0,0,0.2);" placeholder="Distractors (comma separated)">` : ''}
            <div style="display:flex; gap:8px;">
                <button class="btn btn-primary btn-sm" onclick="saveEditedQuestion('${qid}', '${cardId}', '${type}')">Save</button>
                <button class="btn btn-outline btn-sm" onclick="cancelEditQuestion('${cardId}')">Cancel</button>
            </div>
        </div>
    `;
}

function cancelEditQuestion(cardId) {
  const card = document.getElementById(cardId);
  if (card && card.dataset.original) {
    card.innerHTML = card.dataset.original;
    delete card.dataset.original;
  }
}

async function saveEditedQuestion(qid, cardId, type) {
  const prompt = document.getElementById(`edit-prompt-${qid}`).value.trim();
  const answer = document.getElementById(`edit-answer-${qid}`).value.trim();
  let distractors = [];
  if (type === 'mcq') {
    distractors = document.getElementById(`edit-distractors-${qid}`).value.split(',').map(s => s.trim()).filter(s => s);
  }

  if (!prompt || !answer) return showAlert('error', 'Prompt and Answer are required', true);

  const res = await api('/question/update', {
    method: 'POST',
    body: { id: qid, prompt, answer, distractors }
  });

  if (res.success) {
    // Update local data so re-render works
    const qIdx = _lastActivityData.activities.findIndex(q => q.id === qid);
    if (qIdx !== -1) {
      _lastActivityData.activities[qIdx].prompt = prompt;
      _lastActivityData.activities[qIdx].answer = answer;
      if (type === 'mcq') {
        _lastActivityData.activities[qIdx].distractors = distractors;
        _lastActivityData.activities[qIdx].options = [answer, ...distractors].sort(() => Math.random() - 0.5);
      }
      const updatedCardHtml = renderActivityCard(_lastActivityData.activities[qIdx], qIdx, cardId.split('-')[0]);
      document.getElementById(cardId).outerHTML = updatedCardHtml;
    }
  } else {
    showAlert('error', 'Failed to save question', true);
  }
}

async function deleteActivityQuestion(qid, cardId) {
  if (!confirm('Are you sure you want to delete this question?')) return;

  const res = await api('/question/delete', {
    method: 'POST',
    body: { id: qid }
  });

  if (res.success) {
    const card = document.getElementById(cardId);
    if (card) {
      card.style.opacity = '0';
      card.style.transform = 'scale(0.9)';
      card.style.transition = 'all 0.3s ease';
      setTimeout(() => card.remove(), 300);
    }
  } else {
    showAlert('error', 'Failed to delete question', true);
  }
}

function esc(s) { 
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escJS(s) {
  if (!s) return "";
  return String(s).replace(/'/g, "\\'");
}

function formatActivityData(val) {
  if (!val) return '';
  let data = val;
  // If it's a string that looks like JSON, try to parse it
  if (typeof data === 'string' && (data.trim().startsWith('[') || data.trim().startsWith('{'))) {
    try {
      data = JSON.parse(data);
    } catch (e) {
      // Not valid JSON, keep as string
    }
  }
  // If it's an array, join with clean comma-space
  if (Array.isArray(data)) {
    return data.map(item => String(item)).join(', ');
  }
  return String(data);
}

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
  const fb = document.getElementById('fb-' + cardId);
  fb.classList.remove('hidden');
  fb.className = 'feedback-msg ' + (isCorrect ? 'correct' : 'incorrect clickable-feedback');
  if (isCorrect) {
    fb.textContent = t('correctMsg');
    fb.onclick = null;
  } else {
    fb.innerHTML = `<span>${t('incorrectAns')} ${answer}</span> <span style="float:right; opacity:0.8; font-size:12px;">${t('tap_explain')}</span>`;
    fb.onclick = () => explainMistake(cardId, answer, picked);
  }
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
  const fb = document.getElementById('fb-' + id);
  fb.classList.remove('hidden');
  fb.className = 'feedback-msg ' + (isCorrect ? 'correct' : 'incorrect clickable-feedback');
  if (isCorrect) {
    fb.textContent = t('correctMsg');
    fb.onclick = null;
  } else {
    fb.innerHTML = `<span>${t('incorrectAns')} ${answer}</span> <span style="float:right; opacity:0.8; font-size:12px;">${t('tap_explain')}</span>`;
    fb.onclick = () => explainMistake(id, answer, val);
  }
  if (id.startsWith('prac')) await api('/activity/respond', { method: 'POST', body: { student_id: currentUser.id, question_id: qid, answer: val, correct_answer: answer, question_type: 'fill_blank' } });
}

async function explainMistake(cardId, correct_answer, student_answer) {
  const fb = document.getElementById('fb-' + cardId);
  if (fb.dataset.explaining) return;
  fb.dataset.explaining = "true";
  
  const originalHtml = fb.innerHTML;
  fb.innerHTML = `<div style="display:flex; align-items:center; gap:8px;"><span>🧠</span> <span style="font-size:12px; animation:pulse 1.5s infinite;">${t('ai_analyzing')}</span></div>`;
  
  const card = document.getElementById(cardId);
  const prompt = card.querySelector('.activity-prompt').innerText;
  const language = (currentCourse && currentCourse.language) ? currentCourse.language : 'English';
  
  try {
    const res = await api('/activity/explain', {
      method: 'POST',
      body: { prompt, correct_answer, student_answer, language }
    });
    
    if (res.explanation) {
      fb.innerHTML = `
        <div style="font-weight:600; margin-bottom:6px;">${t('incorrectAns')} ${correct_answer}</div>
        <div style="background:rgba(255,255,255,0.1); padding:10px; border-radius:8px; font-size:13.5px; line-height:1.45;">
          <span style="font-size:16px; margin-right:4px;">🤖</span> ${res.explanation}
        </div>
      `;
      fb.onclick = null;
      fb.classList.remove('clickable-feedback');
      fb.style.cursor = 'default';
    } else {
      fb.innerHTML = originalHtml;
      fb.dataset.explaining = "";
    }
  } catch (e) {
    console.error("AI Explanation error:", e);
    fb.innerHTML = originalHtml;
    fb.dataset.explaining = "";
  }
}

function moveDialogueLine(btn, direction) {
  const row = btn.closest('.dialogue-row');
  const container = row.parentElement;
  const rows = Array.from(container.children);
  const idx = rows.indexOf(row);

  // Add CSS transition class if not already there
  if (!row.style.transition) {
    rows.forEach(r => r.style.transition = 'transform 0.2s ease');
  }

  if (direction === -1 && idx > 0) {
    const prev = rows[idx - 1];
    row.style.transform = 'translateY(-40px)';
    prev.style.transform = 'translateY(40px)';
    setTimeout(() => {
      row.style.transform = '';
      prev.style.transform = '';
      container.insertBefore(row, prev);
    }, 200);
  } else if (direction === 1 && idx < rows.length - 1) {
    const next = rows[idx + 1];
    row.style.transform = 'translateY(40px)';
    next.style.transform = 'translateY(-40px)';
    setTimeout(() => {
      row.style.transform = '';
      next.style.transform = '';
      container.insertBefore(next, row);
    }, 200);
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

  try {
    const res = await api('/draft/generate', { method: 'POST', body: { course_id: courseId, chapter_id: chapterId, count } });
    if (res.error) throw new Error(res.error);

    startDraftPolling('quiz', btn, originalText, (questions) => {
      currentDraft = {
        type: 'quiz',
        title: title,
        course_id: courseId,
        chapter_id: chapterId,
        questions: questions
      };
      openDraftModal();
    });
  } catch (err) {
    btn.textContent = originalText;
    btn.disabled = false;
    showAlert(t('error'), err.message, true);
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
  container.innerHTML = quizzes.length === 0 ? `<p style="color:var(--text-muted);padding:20px" data-i18n="noQuizzes">${t('noQuizzes')}</p>`
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
                <button class="btn btn-sm" style="background:var(--danger-bg,#fde8e8);color:var(--danger);border:1px solid var(--danger)" onclick="event.stopPropagation();deleteQuiz('${q.id}','${esc(q.title)}')">🗑️ ${t('confirm.delete_quiz')}</button>
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
    correctAns: t('assign.correct_answer')
  };

  document.getElementById('student-detail-body').innerHTML = `
    <h2 style="margin-bottom:4px">${title}</h2>
    <div style="color:var(--text-muted); margin-bottom:20px; font-size:14px">
      <span data-i18n="assign.class_avg">${L.classAvg}</span>: <strong style="color:var(--accent)">${classAvg}%</strong> · 
      ${studentResults.length} <span data-i18n="assign.submitted">${L.submitted}</span>
    </div>
    
    <div style="display:flex;gap:8px;margin-bottom:20px;border-bottom:1px solid var(--border)">
      <button class="nav-tab active" onclick="switchQuizViewTab(this,'qv-questions')" style="flex:1;padding:10px">📄 <span data-i18n="answer">${t('answer')}</span></button>
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
                            ${!isRight ? `<span><span data-i18n="assign.correct_answer">${L.correctAns}</span>: <strong style="color:var(--success)">${a.correct_answer}</strong></span>` : ''}
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
  area.innerHTML = `<div class="quiz-header"><span class="quiz-progress-text">Q${idx + 1}/${qs.length}</span></div><div class="activity-card">${renderPromptHTML(q, true)}` +
    (q.type === 'mcq' ? `<div class="options-grid">${((q.distractors || []).concat([q.answer]).sort(() => Math.random() - 0.5)).map(o => `<button class="option-btn" onclick="quizAnswer(this,'${escJS(q.id)}','${escJS(o)}')">${translateOption(o)}</button>`).join('')}</div>` : `<div style="display:flex;gap:10px;align-items:center;margin-top:12px"><input class="fill-blank-input" id="q-inp" style="flex:1" placeholder="..." onkeydown="if(event.key==='Enter')quizAnswer(null,'${escJS(q.id)}',this.value)"><button class="btn btn-primary" onclick="quizAnswer(null,'${escJS(q.id)}',document.getElementById('q-inp').value)" data-i18n="submit">${t('submit')}</button></div>`) + `</div>`;
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
        <h3 style="color:#8b5cf6;margin:0 0 16px 0;font-size:1.1rem">⏳ <span data-i18n="Account Pending Approval">${t('Account Pending Approval')}</span> (${pending.length})</h3>
        ${pending.map(s => `
          <div style="display:flex;align-items:center;justify-content:space-between;background:var(--bg-card);padding:14px 20px;border-radius:10px;margin-bottom:8px;border:1px solid var(--border)">
            <div style="min-width:0;flex:1;overflow:hidden">
              <div style="font-weight:600;color:var(--text-primary);font-size:0.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${s.name}</div>
              <div style="color:var(--text-secondary);font-size:0.8rem;margin-top:2px">${s.email}</div>
            </div>
            <div style="display:flex;gap:8px;margin-left:16px;flex-shrink:0">
              <button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); approveStudent('${s.id}')">✅ <span data-i18n="ok">${t('ok')}</span></button>
              <button class="btn btn-outline btn-sm" onclick="event.stopPropagation(); deleteStudent('${s.id}','${esc(s.name)}')">❌ <span data-i18n="cancel">${t('cancel')}</span></button>
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
          <button class="btn btn-sm" style="background:var(--accent); color:#fff; border:none; padding:4px 8px; border-radius:6px; font-size:14px" onclick="event.stopPropagation(); openChatFromRoster('${s.id}','${esc(s.name).replace(/'/g, "\\'")}')">💬 <span data-i18n="messageStudent">${t('messageStudent')}</span></button>
          <button class="btn btn-sm" style="background:var(--danger-bg); color:var(--danger); border:1px solid var(--danger); padding:4px 8px; border-radius:6px" onclick="event.stopPropagation(); deleteStudent('${s.id}','${esc(s.name).replace(/'/g, "\\'")}')"><span data-i18n="Kick">${t('Kick')}</span></button>
        </div>
      </div>
      <div class="student-mastery-bar">
        <div class="student-mastery-fill" style="width:${pct}%; background:${masteryColor(s.avg_mastery)}"></div>
      </div>
      <div class="student-meta-row">
        <span><span data-i18n="Mastery:">${t('Mastery:')}</span> ${pct}%</span>
        <span>${s.total_responses} <span data-i18n="responses">${t('responses')}</span></span>
        <span style="color:var(--accent-light); font-weight:700;">PIN: ${s.pin || '---'}</span>
      </div>
    </div>`;
  }).join('');
  applyTranslations();
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
    else cancelBtn.style.display = '';

    if (isDanger) {
      okBtn.style.background = 'var(--danger)';
      okBtn.style.boxShadow = '0 0 10px rgba(239,68,68,0.4)';
    } else {
      okBtn.style.background = '';
      okBtn.style.boxShadow = '';
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

async function showAlert(titleKey, messageKey, isDanger = false, messageData = {}) {
  return showConfirmModal(titleKey, messageKey, isDanger, null, true, 'ok', null, messageData);
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
        <button class="btn btn-primary btn-sm" onclick="openChatFromRoster('${sid}','${esc(name).replace(/'/g, "\\'")}')">💬 <span data-i18n="messageStudent">${t('messageStudent')}</span></button>
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
  const content = document.getElementById('report-content');
  if (!content) return;

  showGenerationLoading(content);

  try {
    const r = await api('/report/generate', { method: 'POST', body: { course_id: courseId } });
    _lastReportData = r;
    renderReport(r);
  } catch (err) {
    content.innerHTML = `<div style="padding:20px; color:var(--danger); text-align:center; background:var(--danger-bg); border-radius:12px; border:1px solid var(--danger);">
      ${t('assign.retry')}
    </div>`;
  }
}

function renderReport(report) {
  const content = document.getElementById('report-content');
  if (!content || !report) return;

  const lang = currentLang;
  // Pick the appropriate language from AI insights, or use a default if it's the old format
  let data = null;
  if (report.ai_insights) {
    if (report.ai_insights[lang]) {
      data = report.ai_insights[lang];
    } else if (report.ai_insights.summary) {
      // Legacy format fallback
      data = {
        summary: report.ai_insights.summary,
        topic_breakdown: (report.review_topics || []).map(t => ({ topic: t.topic, analysis: "N/A", recommendation: "N/A" })),
        at_risk_commentaries: (report.at_risk_students || []).map(s => ({ name: s.name, commentary: "N/A" })),
        general_advice: "N/A"
      };
    }
  }

  if (!data) {
    content.innerHTML = `<div style="text-align:center; padding:40px; color:var(--text-muted);">${t('report.no_data')}</div>`;
    return;
  }

  const s = report.summary || {};
  const avgPct = Math.round((s.class_avg_mastery || 0) * 100);

  content.innerHTML = `
    <div class="report-card animate-slide-up" style="background:var(--bg-card); border-radius:24px; border:1px solid var(--border); overflow:hidden; box-shadow:var(--shadow-xl); max-width:800px; margin:0 auto;">
      <div style="background:var(--gradient-1); padding:40px; text-align:center; color:white; position:relative; overflow:hidden;">
        <h2 style="margin:0; font-size:28px; font-weight:800; letter-spacing:-0.5px;">${t('report.title')}</h2>
        <p style="margin:8px 0 0; opacity:0.8; font-size:14px;">${new Date(report.generated_at).toLocaleDateString(lang === 'tr' ? 'tr-TR' : 'en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>
      </div>
      
      <div style="padding:32px;">
        <!-- Stats Row -->
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:16px; margin-bottom:32px;">
          <div style="background:var(--bg-input); padding:16px; border-radius:16px; border:1px solid var(--border); text-align:center;">
            <div style="font-size:11px; text-transform:uppercase; color:var(--text-muted); font-weight:800; margin-bottom:4px;">${t('STUDENTS')}</div>
            <div style="font-size:24px; font-weight:800; color:var(--accent-light);">${s.total_students || 0}</div>
          </div>
          <div style="background:var(--bg-input); padding:16px; border-radius:16px; border:1px solid var(--border); text-align:center;">
            <div style="font-size:11px; text-transform:uppercase; color:var(--text-muted); font-weight:800; margin-bottom:4px;">${t('CLASS_MASTERY')}</div>
            <div style="font-size:24px; font-weight:800; color:var(--success);">${avgPct}%</div>
          </div>
          <div style="background:rgba(239,68,68,0.05); padding:16px; border-radius:16px; border:1px solid rgba(239,68,68,0.2); text-align:center;">
            <div style="font-size:11px; text-transform:uppercase; color:var(--danger); font-weight:800; margin-bottom:4px;">${t('AT_RISK')}</div>
            <div style="font-size:24px; font-weight:800; color:var(--danger);">${s.at_risk_count || 0}</div>
          </div>
        </div>

        <div style="margin-bottom:32px; padding:24px; background:var(--bg-input); border-radius:20px; border:1px solid var(--border);">
          <h3 style="margin:0 0 12px; font-size:18px; font-weight:700; display:flex; align-items:center; gap:10px;"><span>📝</span> ${lang === 'tr' ? 'Yönetici Özeti' : 'Executive Summary'}</h3>
          <div style="font-size:14.5px; line-height:1.7; color:var(--text-secondary);">${data.summary}</div>
        </div>

        <div style="margin-bottom:32px;">
          <h3 style="margin:0 0 16px; font-size:18px; font-weight:700; display:flex; align-items:center; gap:10px;"><span>📉</span> ${lang === 'tr' ? 'Hatalı Konular ve Analiz' : 'Flawed Topics & Analysis'}</h3>
          <div style="display:flex; flex-direction:column; gap:12px;">
            ${(data.topic_breakdown || []).map(topic => `
              <div style="background:var(--bg-input); border:1px solid var(--border); padding:20px; border-radius:20px;">
                <div style="font-weight:700; color:var(--accent-light); margin-bottom:8px; font-size:15px;">${topic.topic}</div>
                <div style="font-size:13.5px; line-height:1.6; color:var(--text-secondary); margin-bottom:12px;">${topic.analysis}</div>
                <div style="background:rgba(16,185,129,0.05); border:1px dashed rgba(16,185,129,0.3); padding:12px; border-radius:12px;">
                  <div style="font-size:11px; font-weight:800; color:var(--success); text-transform:uppercase; margin-bottom:4px;">${lang === 'tr' ? 'Tavsiye' : 'Recommendation'}</div>
                  <div style="font-size:13px; color:var(--text-secondary);">${topic.recommendation}</div>
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <div style="margin-bottom:32px;">
          <h3 style="margin:0 0 16px; font-size:18px; font-weight:700; display:flex; align-items:center; gap:10px;"><span>👤</span> ${lang === 'tr' ? 'Öğrenci Spotlight' : 'Student Spotlights'}</h3>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:12px;">
            ${(data.at_risk_commentaries || []).map(sc => `
              <div style="background:var(--bg-input); border:1px solid var(--border); padding:16px; border-radius:16px; border-left:4px solid var(--danger);">
                <div style="font-weight:700; margin-bottom:6px; font-size:14px;">${sc.name}</div>
                <div style="font-size:13px; line-height:1.5; font-style:italic; color:var(--text-muted);">"${sc.commentary}"</div>
              </div>
            `).join('')}
          </div>
        </div>

        <div style="padding:24px; background:var(--gradient-2); border-radius:20px; color:white;">
          <h3 style="margin:0 0 10px; font-size:18px; font-weight:700;">💡 ${lang === 'tr' ? 'Genel Tavsiye' : 'General Advice'}</h3>
          <div style="font-size:14px; line-height:1.6; opacity:0.9;">${data.general_advice}</div>
        </div>
      </div>
    </div>
  `;
}

async function initStudent() {
  const navUser = document.getElementById('student-nav-username');
  if (navUser) navUser.textContent = currentUser.name;

  const greeting = document.getElementById('student-greeting');
  if (greeting) greeting.textContent = t('welcomeBack', { name: currentUser.name }) + '!';

  // Background poller to check if classroom still exists (Safety/Immediate Notification)
  if (window._studentPoll) clearInterval(window._studentPoll);
  window._studentPoll = setInterval(async () => {
    if (currentCourse && currentUser && currentUser.role === 'student') {
      const check = await api('/courses');
      if (check && Array.isArray(check)) {
        const stillExists = check.some(c => c.id === currentCourse.id);
        if (!stillExists) {
          clearInterval(window._studentPoll);
          await showAlert("Classroom Deleted", "The lecturer has deleted this classroom. Redirecting to your portal...");
          window.location.reload();
        }
      }
    }
  }, 15000);

  try {
    await Promise.all([
      loadCurriculumAsync(),
      loadStudentHome(),
      loadQuizList(),
      loadAssignmentList(),
      loadStudentProgress(),
      loadStudentChat()
    ]);
  } catch (e) {
    console.error("Error initializing student dashboard:", e);
  }
  loadStudentPractice();
  applyTranslations();
}

async function loadStudentStats() {
  const stats = await api(`/student/stats?student_id=${currentUser.id}&course_id=${courseId}`);
  const container = document.getElementById('student-stats');
  if (!container) return;
  container.innerHTML = `<div class="stat-card"><div class="stat-label">${t('Quizzes')}</div><div class="stat-value accent">${stats.quizzes || 0}</div></div><div class="stat-card"><div class="stat-label">${t('practice')}</div><div class="stat-value success">${stats.practice || 0}</div></div><div class="stat-card"><div class="stat-label">${t('Assignments')}</div><div class="stat-value warning">${stats.assignments || 0}</div></div>`;
}

async function loadStudentHome() {
  const progress = await api(`/student/progress?student_id=${currentUser.id}&course_id=${courseId}`);
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
    chapterEl.innerHTML = curriculum.length ? `<h4 style="margin-bottom:12px">📖 ${t('currentChapter')}: ${curriculum[0].title}</h4>${(curriculum[0].topics || []).map(tp => `<div class="topic-item" style="cursor:pointer" onclick="startStudyFirst('${tp.id}')"><div class="topic-info"><span class="topic-type-badge ${tp.type}">${tp.type}</span><span class="topic-name">${tp.title}</span></div></div>`).join('')}` : '';
  }
}

function loadStudentPractice() {
  document.getElementById('practice-topics').innerHTML = curriculum.map(ch => (ch.topics || []).map(tp =>
    `<div class="topic-practice-card" onclick="startStudyFirst('${tp.id}')">
      <div style="display:flex; justify-content:space-between; align-items:flex-start">
        <div class="topic-type-badge ${tp.type}" style="margin-bottom:8px">${tp.type}</div>
      </div>
      <div style="font-weight:600;margin-bottom:4px">${tp.title}</div>
      <div style="font-size:13px;color:var(--text-muted)"><span data-i18n="Unit">${t('Unit')}</span> ${ch.number} · ${tp.difficulty}</div>
    </div>`
  ).join('')).join('');
}

function startStudyFirst(topicId) {
  // 1. Find the Study tab button and switch to it
  const studyTabBtn = document.getElementById('nav-s-study-tab') || document.querySelector('button[data-tab="s-book"]');
  if (studyTabBtn) {
    switchTab(studyTabBtn);
    // 2. Load the study content for this topic
    setTimeout(() => showStudyTopic(topicId), 50);
  }
}

async function startPractice(tid, title) {
  const isLecturer = currentUser.role === 'lecturer';
  const targetId = isLecturer ? 'activity-preview' : 'practice-area';
  const topicsGrid = isLecturer ? null : document.getElementById('practice-topics');
  const area = document.getElementById(targetId);

  if (topicsGrid) topicsGrid.classList.add('hidden');
  if (area) {
    area.innerHTML = '';
    area.classList.remove('hidden');
    area.style.display = 'block';
    showGenerationLoading(area);
  }

  try {
    // 1. Kick off the background task
    const res = await api('/activity/start', {
      method: 'POST',
      body: { topic_id: tid, course_id: courseId, count: 10 }
    });
    if (res.error) throw new Error(res.error);

    // 2. Start polling
    startActivityPolling(targetId, `${t('practice')}: ${title}`);
  } catch (err) {
    console.error("Practice Start Error:", err);
    if (area) {
      area.innerHTML = `<div style="padding:40px; color:var(--danger); text-align:center; background:var(--bg-card); border-radius:16px; border:1px solid var(--border);">
          <div style="font-size:48px; margin-bottom:16px;">⚠️</div>
          <h3 style="margin-bottom:8px;">${t('assign.retry')}</h3>
          <p style="color:var(--text-muted); margin-bottom:24px;">${err.message || 'Generation failed'}</p>
          <button class="btn btn-primary" onclick="cancelPractice()">Back to Topics</button>
        </div>`;
    }
  }
}

function cancelPractice() {
  const topicsGrid = document.getElementById('practice-topics');
  const area = document.getElementById('practice-area');
  if (topicsGrid) topicsGrid.classList.remove('hidden');
  if (area) {
    area.classList.add('hidden');
    area.innerHTML = '';
  }
}

async function loadStudentProgress() {
  const data = await api(`/student/progress?student_id=${currentUser.id}&course_id=${courseId}`);
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
    container.innerHTML = `<p style="color:var(--text-muted);padding:20px;text-align:center" data-i18n="noAssignments">${t('noAssignments')}</p>`;
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
              🗑️ ${t('confirm.delete_assignment')}
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

  try {
    const res = await api('/draft/generate', { method: 'POST', body: { course_id: courseId, chapter_id: chapterId, count } });
    if (res.error) throw new Error(res.error);

    startDraftPolling('assignment', btn, originalText, (questions) => {
      currentDraft = {
        type: 'assignment',
        title: title,
        course_id: courseId,
        chapter_id: chapterId,
        due_at: null,
        questions: questions
      };
      openDraftModal();
    });
  } catch (err) {
    btn.textContent = originalText;
    btn.disabled = false;
    showAlert(t('error'), err.message, true);
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
          <input type="text" id="cq-prompt" class="text-input" placeholder="e.g. The capital of Germany is ___">
        </div>
        <div class="form-group">
          <label data-i18n="draft.answer">${t('draft.answer')}</label>
          <input type="text" id="cq-answer" class="text-input" placeholder="e.g. Berlin">
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

  if (!currentDraft.questions || currentDraft.questions.length === 0) {
    html += `
      <div style="text-align:center; padding:20px; color:var(--text-muted);">
        <p data-i18n="draft.no_auto_gen">${t('draft.no_auto_gen')}</p>
        <p data-i18n="draft.click_add">${t('draft.click_add')}</p>
      </div>
    `;
  }

  currentDraft.questions.forEach((q, i) => {
    let typeLabel = q.type === 'mcq' ? t('draft.mcq') : (q.type === 'dialogue_order' || q.type === 'dialogue' ? (t('prac.dialogue') || 'Dialogue') : t('draft.fill_blank'));

    let formattedPrompt = formatActivityData(q.prompt);
    let formattedAnswer = formatActivityData(q.answer);

    html += `
      <div class="card" style="margin-bottom:12px; position:relative;">
        <button class="btn btn-ghost btn-sm" style="position:absolute; top:8px; right:8px; color:var(--danger);" onclick="removeDraftQuestion(${i})">🗑️ <span data-i18n="draft.remove">${t('draft.remove')}</span></button>
        <div class="card-body">
          <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">${i + 1}. ${typeLabel}</div>
          <div style="font-weight:600; margin-bottom:8px;">${esc(formattedPrompt)}</div>
          <div style="color:var(--success); font-size:14px; margin-bottom:4px;">✓ ${esc(formattedAnswer)}</div>
          ${q.type === 'mcq' && q.distractors && q.distractors.length > 0 ? q.distractors.map(d => `<div style="color:var(--danger); font-size:13px;">✗ ${esc(d)}</div>`).join('') : ''}
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
      ${options.map(o => `<button class="option-btn" onclick="assignmentAnswer('${escJS(o)}')"
        style="text-align:left;padding:14px 18px;font-size:14px">${translateOption(o)}</button>`).join('')}
    </div>`;
  } else {
    answerHTML = `<div style="margin-top:16px;display:flex;gap:10px;align-items:center">
      <input id="as-inp" class="fill-blank-input" placeholder="${t('assign.type_answer')}"
        style="flex:1;font-size:15px" onkeydown="if(event.key==='Enter')assignmentAnswer(this.value)">
      <button class="btn btn-primary" onclick="assignmentAnswer(document.getElementById('as-inp').value)" data-i18n="submit">
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
      <div style="font-size:16px;line-height:1.6">${renderPromptHTML(q)}</div>
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
    ${t('loading')}
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

// ── Digital Study Book (AI Architect) ──
function renderStudyBook() {
  const isStudent = currentUser.role === 'student';
  const containerId = isStudent ? 's-ai-book-container' : 'ai-book-container';
  const container = document.getElementById(containerId);
  const fallback = document.getElementById('s-ai-book-fallback');

  if (container) container.classList.remove('hidden');
  if (isStudent && fallback) fallback.classList.add('hidden');

  const tocId = currentUser.role === 'lecturer' ? 'ai-book-toc' : 's-ai-book-toc';
  const toc = document.getElementById(tocId);
  if (!toc) return;

  if (!curriculum || curriculum.length === 0) {
    toc.innerHTML = `<p style="color:var(--text-muted); font-size:13px; padding:10px;">${t('class.no_curriculum') || 'No curriculum loaded.'}</p>`;
    return;
  }

  // Clear existing content and render
  toc.innerHTML = curriculum.map((ch, i) => `
    <div class="study-ch-group" style="margin-bottom:16px;">
      <div style="font-size:11px; font-weight:800; color:var(--accent); text-transform:uppercase; letter-spacing:1px; margin-bottom:8px; opacity:0.7;">${t('Unit')} ${ch.number || (i + 1)}</div>
      <div style="display:flex; flex-direction:column; gap:4px;">
        ${(ch.topics || []).map(t => `
          <button class="btn btn-ghost study-topic-btn" onclick="showStudyTopic('${t.id}')" style="justify-content:flex-start; text-align:left; font-size:13px; padding:10px 14px; border-radius:10px; line-height:1.3; height:auto; transition:0.2s ease;">
            ${esc(t.title)}
          </button>
        `).join('')}
      </div>
    </div>
  `).join('');
}

function showStudyTopic(topicId, pageIdx = 0) {
  const isStudent = currentUser.role === 'student';
  const contentId = isStudent ? 's-ai-book-content-area' : 'ai-book-content';
  const container = document.getElementById(contentId);
  if (!container) return;

  container.innerHTML = `<div style="height:400px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:16px;"><div class="spinner"></div></div>`;

  // Save for refresh
  localStorage.setItem('aula_last_topic', topicId);
  localStorage.setItem('aula_last_page', pageIdx);

  let topic = null;
  for (const ch of curriculum) {
    topic = ch.topics.find(t => t.id === topicId);
    if (topic) break;
  }
  if (!topic) return;

  // Save topic title for dictionary context (prevents AI contradicting lesson material)
  localStorage.setItem('aula_last_topic_title', topic.title || '');

  // Highlight active sidebar item
  document.querySelectorAll('.study-topic-btn').forEach(b => {
    const isActive = b.textContent.trim() === topic.title;
    b.classList.toggle('active', isActive);
    b.style.background = isActive ? 'var(--accent-glow)' : '';
  });

  // Define pages
  let pages = [];

  try {
    const content = typeof topic.content === 'string' ? JSON.parse(topic.content || '{}') : (topic.content || {});

    const fixDiacritics = (txt) => {
      if (typeof txt !== 'string') return txt;
      let res = txt.replace(/(^|[\s\(\[“"'‘])([\u064B-\u065F\u0670])/g, '$1◌$2');
      return '\u200E' + res;
    };

    if (content.pages && Array.isArray(content.pages)) {
      content.pages.forEach(p => {
        const type = (p.type || '').toLowerCase();
        let icon = "📄";
        if (type.includes('vocab')) icon = "📙";
        else if (type.includes('gramm') || type.includes('intro') || type.includes('expla')) icon = "⚙️";
        else if (type.includes('examp') || type.includes('dialog') || type.includes('conv')) icon = "💬";

        pages.push({
          title: p.title || (topic.title || t('Material')),
          icon: icon,
          render: () => {
            // 1. DYNAMIC CONTENT DETECTION (Including 'content' as a data source)
            let rawData = p.items || p.vocabulary || p.words || p.list || p.phrases || p.examples || p.dialogue || p.content || [];
            
            // CATCH-ALL: If rawData is empty, look for any array in the object
            if (!Array.isArray(rawData) || rawData.length === 0) {
              for (const key in p) {
                if (Array.isArray(p[key]) && p[key].length > 0) {
                  rawData = p[key];
                  break;
                }
              }
            }

            // A. If it's an array of strings (Alphabet/Simple Lists)
            if (Array.isArray(rawData) && rawData.length > 0 && typeof rawData[0] === 'string') {
              return `<div style="display:flex; flex-direction:column; gap:16px; font-size:20px; line-height:1.8; color:#e2e8f0;">
                ${rawData.map(str => `<div dir="auto" class="foreign-word" style="cursor:pointer; display:inline-block;">${fixDiacritics(str)}</div>`).join('')}
              </div>`;
            }

            // B. If it's an array of objects (Vocabulary, Examples, or mislabeled content)
            if (Array.isArray(rawData) && rawData.length > 0 && typeof rawData[0] === 'object') {
              return `<div style="display:flex; flex-direction:column; gap:12px;">
                ${rawData.map(it => {
                // Agnostic Key Detection
                const k = it.term || it.word || it.phrase || it.speaker || it.sentence || it.turkish || it.arabic || it.spanish || it.key || Object.values(it)[0] || "";
                const v = it.translation || it.meaning || it.text || it.content || it.english || it.value || Object.values(it)[1] || "";

                // Smarter Example Detection: Only hide the 'term' side if 'v' is empty or speaker exists
                const isExplicitExample = !!it.speaker;
                const isLongSentence = typeof k === 'string' && k.length > 40 && (!v || v === k);

                if (isExplicitExample || isLongSentence) {
                  return `<div dir="auto" style="background:rgba(255,255,255,0.02); padding:18px; border-radius:16px; border-left:4px solid var(--accent);">
                      ${(it.speaker && k) ? `<div style="font-weight:800; color:var(--accent-light); font-size:11px; text-transform:uppercase; margin-bottom:4px;">${k}</div>` : ''}
                      <div class="foreign-word" style="font-style:italic; font-size:20px; color:#ffffff; cursor:pointer; display:inline-block;">"${fixDiacritics(v || k)}"</div>
                    </div>`;
                }

                // Regular Vocab/Phrase Card
                return `<div style="background:rgba(255,255,255,0.03); padding:16px 20px; border-radius:14px; border:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; gap:16px;">
                    <div style="flex:1; display:flex; justify-content:flex-start;">
                        <div dir="auto" class="foreign-word" style="font-size:22px; font-weight:800; color:#ffffff; cursor:pointer;">${fixDiacritics(k)}</div>
                    </div>
                    <div class="english-translation" style="color:var(--accent-light); font-weight:500; font-size:15px; text-align:right; flex:1;">${v}</div>
                  </div>`;
              }).join('')}</div>`;
            }

            // C. If it's a string (Grammar or Intro)
            let text = p.text || p.content || p.description || p.explanation || p.rule || p.intro || "";
            
            // CATCH-ALL: If text is empty, look for any long string in the object
            if (!text) {
              for (const key in p) {
                if (typeof p[key] === 'string' && p[key].length > 15 && key !== 'title' && key !== 'type') {
                  text = p[key];
                  break;
                }
              }
            }

            if (text) {
              if (typeof text !== 'string') text = JSON.stringify(text, null, 2);
              
              // SMARTBOARD AUTO-FORMATTER: Convert paragraphs to bullet points
              const fixDiacriticsText = fixDiacritics(text);
              const lines = fixDiacriticsText.split(/\n|(?<=[.!?])\s+(?=[A-Z])/).filter(l => l.trim().length > 0);
              
              if (lines.length > 1) {
                return `<ul class="ai-explanation" style="font-size:22px; line-height:1.6; color:#ffffff; list-style-type: disc; padding-left: 24px; margin: 0;">
                  ${lines.map(line => `<li style="margin-bottom: 16px;">${line.trim().replace(/^[•\-\*]\s*/, "")}</li>`).join('')}
                </ul>`;
              }
              
              return `<div dir="auto" class="ai-explanation" style="font-size:22px; line-height:1.8; color:#ffffff; white-space:pre-wrap;">${fixDiacriticsText}</div>`;
            }

            return `<div style="color:var(--text-muted); font-style:italic; text-align:center; padding:40px;">No content found for this section.</div>`;
          }
        });
      });
    }
  } catch (e) { console.error("Renderer Failure:", e); }

  if (pages.length === 0) {
    pages.push({
      title: t('gen.preparing_content') || 'Under Construction',
      icon: "🚧",
      render: () => `<div style="text-align:center; padding:60px 20px; color:var(--text-muted);">
        <div style="font-size:60px; margin-bottom:24px;">🚧</div>
        <h2 style="color:var(--text-main);">${t('gen.preparing_content') || 'Content Still Building'}</h2>
        <p>${t('gen.preparing_desc') || 'The AI is currently architecting this lesson. Please wait a few moments.'}</p>
        <button class="btn btn-primary" style="margin-top:24px;" onclick="location.reload()">Refresh Page</button>
        ${!isStudent ? `<button class="btn btn-outline" style="margin-top:12px; border-color:var(--accent); color:var(--accent-light);" onclick="rebuildClassroom(true)">🔄 Rebuild All Lessons (Force)</button>` : ''}
      </div>`
    });
  }

  pages.push({
    title: isStudent ? t('study.complete') : t('study.preview'),
    icon: "🏁",
    render: () => `<div style="text-align:center; padding:60px 20px;">
      <div style="font-size:64px; margin-bottom:24px;">🎯</div>
      <h2 style="font-size:28px;">${isStudent ? t('study.ready') : t('study.preview_end')}</h2>
      <p style="color:var(--text-muted); font-size:18px; margin:20px 0 40px;">${isStudent ? t('study.ready_msg') : t('study.preview_msg')}</p>
      ${isStudent ? `<button class="btn btn-primary btn-lg" onclick="launchStudyActivity('${topic.id}', '${esc(topic.title)}')">${t('study.start_practice')}</button>` : ''}
    </div>`
  });

  const page = pages[pageIdx] || pages[0];

  container.innerHTML = `
    <div style="max-width:850px; margin:0 auto; animation:fadeIn 0.4s ease-out;">
      <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:32px; border-bottom:1px solid var(--border); padding-bottom:24px;">
        <div>
          <div style="font-size:11px; color:var(--accent); font-weight:900; text-transform:uppercase; letter-spacing:2px; margin-bottom:8px;">${topic.title} • PAGE ${pageIdx + 1}/${pages.length}</div>
          <h1 style="font-size:36px; font-weight:800; letter-spacing:-1px;">${page.icon} ${page.title}</h1>
        </div>
        <div style="display:flex; gap:12px;">
          ${pageIdx > 0 ? `<button class="btn btn-outline" onclick="showStudyTopic('${topicId}', ${pageIdx - 1})">← ${t('study.back')}</button>` : ''}
          ${pageIdx < pages.length - 1 ? `<button class="btn btn-primary" onclick="showStudyTopic('${topicId}', ${pageIdx + 1})">${t('study.next')} →</button>` : ''}
        </div>
      </div>
      <div class="study-card" style="background:var(--bg-card); border:1px solid var(--border); border-radius:24px; padding:40px; min-height:500px; box-shadow:0 10px 30px rgba(0,0,0,0.2);">
        ${page.render()}
      </div>
      <div style="margin-top:24px; display:flex; justify-content:center; gap:8px;">
        ${pages.map((_, i) => `<div style="width:${i === pageIdx ? '24px' : '8px'}; height:8px; border-radius:4px; background:${i === pageIdx ? 'var(--accent)' : 'var(--border)'}; transition:0.3s ease;"></div>`).join('')}
      </div>
    </div>
  `;
}

function launchStudyActivity(topicId, topicTitle) {
  const selector = currentUser.role === 'lecturer' ? 'button[data-tab="activities"]' : 'button[data-tab="s-practice"]';
  const tabBtn = document.querySelector(selector);
  if (tabBtn) {
    switchTab(tabBtn);
    // Start practice after a small delay to ensure DOM is ready
    setTimeout(() => startPractice(topicId, topicTitle), 100);
  } else {
    // Fallback if button not found
    startPractice(topicId, topicTitle);
  }
}

// ── Student Portal Functions ──

async function refreshStudentEnrollments() {
  if (!currentUser) return;
  const res = await api('/student/login', {
    method: 'POST',
    body: { student_number: currentUser.email.split('@')[0], name: currentUser.name }
  });
  if (!res.error) {
    currentStudentEnrollments = res.enrollments || [];
    renderStudentPortal();
  }
}

function renderStudentPortal() {
  const grid = document.getElementById('student-classrooms-grid');
  if (!grid) return;

  if (currentStudentEnrollments.length === 0) {
    grid.innerHTML = `
      <div style="grid-column:1/-1; text-align:center; padding:60px; background:var(--bg-card); border-radius:16px; border:1px dashed var(--border);">
        <div style="font-size:48px; margin-bottom:16px;">🏫</div>
        <h2 data-i18n="no_classrooms_found">${t('no_classrooms_found')}</h2>
        <p style="color:var(--text-muted); margin-top:8px;">${t('student.enter_code')}</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = currentStudentEnrollments.map(enr => `
    <div class="classroom-card" style="position:relative">
      <div onclick="enterStudentClassroom('${enr.course_id}')" style="cursor:pointer">
        <div class="classroom-card-header">
          <div class="classroom-icon">🎓</div>
          <div class="classroom-status ${enr.status}">${enr.status === 'approved' ? '✓ ' + t('approved') : '⏳ ' + t('pending')}</div>
        </div>
        <div class="classroom-card-body">
          <h3 class="classroom-name">${esc(enr.course_name)}</h3>
          <div class="classroom-meta">${enr.language || 'Language'} • ${enr.level || 'Level'}</div>
        </div>
        <div class="classroom-card-footer">
          <div class="classroom-code">#${enr.course_code}</div>
          <div style="display:flex; gap:8px; align-items:center">
             <button class="btn btn-sm" onclick="event.stopPropagation(); leaveClassroom('${enr.course_id}', '${esc(enr.course_name)}')" style="background:#ff3b30; color:white; border:none; font-size:11px; padding:4px 12px; border-radius:6px; opacity:1; font-weight:700; box-shadow: 0 2px 8px rgba(255,59,48,0.3);" data-i18n="student.leave">${t('student.leave')}</button>
             <div class="classroom-arrow">→</div>
          </div>
        </div>
      </div>
    </div>
  `).join('');
  applyTranslations(grid);
}

function openJoinClassroomModal() {
  document.getElementById('join-classroom-modal').classList.remove('hidden');
  document.getElementById('join-class-code').value = '';
  document.getElementById('join-class-code').focus();
}

function closeJoinClassroomModal() {
  document.getElementById('join-classroom-modal').classList.add('hidden');
}

async function handleJoinClassroom() {
  const code = document.getElementById('join-class-code').value.trim();
  if (code.length < 5) return;

  const res = await api('/student/join', {
    method: 'POST',
    body: { student_id: currentUser.id, code: code }
  });

  if (res.error) {
    showAlert(t('error'), res.error, true);
  } else {
    closeJoinClassroomModal();
    await refreshStudentEnrollments();
  }
}

async function enterStudentClassroom(courseId) {
  const enr = currentStudentEnrollments.find(e => e.course_id === courseId);
  if (!enr) return;

  if (enr.status === 'pending') {
    showScreen('waiting-room-screen');
    startWaitingRoomPoll(courseId);
    return;
  }

  if (!enr.pin) {
    showPinModal('setup', courseId);
  } else {
    showPinModal('verify', courseId);
  }
}

function showPinModal(mode, courseId) {
  const modal = document.getElementById('pin-entry-modal');
  const title = document.getElementById('pin-modal-title');
  const desc = document.getElementById('pin-modal-desc');
  const pinInput = document.getElementById('student-pin-input');
  const submitBtn = document.getElementById('pin-submit-btn');
  const errBox = document.getElementById('pin-error');

  modal.classList.remove('hidden');
  pinInput.value = '';
  pinInput.focus();
  errBox.classList.add('hidden');

  // Support Enter key for PIN submission
  pinInput.onkeydown = (e) => {
    if (e.key === 'Enter') submitBtn.click();
  };

  if (mode === 'setup') {
    title.textContent = t('student.pin_setup');
    desc.textContent = t('student.pin_setup_desc');
    submitBtn.textContent = t('submit');
    submitBtn.onclick = () => handleSetPin(courseId, pinInput.value);
  } else {
    title.textContent = t('student.pin_required');
    desc.textContent = t('student.pin_desc');
    submitBtn.textContent = t('class.enter');
    submitBtn.onclick = () => handleVerifyPin(courseId, pinInput.value);
  }
}

function closePinModal() {
  document.getElementById('pin-entry-modal').classList.add('hidden');
}

async function handleSetPin(courseId, pin) {
  if (pin.length !== 4) return;
  const res = await api('/student/set-pin', {
    method: 'POST',
    body: { student_id: currentUser.id, course_id: courseId, pin: pin }
  });
  if (res.error) {
    document.getElementById('pin-error').textContent = res.error;
    document.getElementById('pin-error').classList.remove('hidden');
  } else {
    closePinModal();
    await selectClassroom(courseId, false);
  }
}

async function handleVerifyPin(courseId, pin) {
  if (pin.length !== 4) return;
  const res = await api('/student/access', {
    method: 'POST',
    body: { student_id: currentUser.id, course_id: courseId, pin: pin }
  });
  if (res.error) {
    document.getElementById('pin-error').textContent = t('student.invalid_pin');
    document.getElementById('pin-error').classList.remove('hidden');
  } else {
    closePinModal();
    stopLiveSync();
    currentUser.role = 'student';
    await selectClassroom(courseId, false);
  }
}

function startWaitingRoomPoll(courseId) {
  if (window._waitingPoll) clearInterval(window._waitingPoll);
  window._waitingPoll = setInterval(async () => {
    const check = await api('/user/status?user_id=' + currentUser.id + '&course_id=' + courseId);
    if (check && check.status === 'approved') {
      clearInterval(window._waitingPoll);
      currentUser.status = 'approved';
      localStorage.setItem('aula_user', JSON.stringify(currentUser));
      sessionStorage.setItem('aula_user', JSON.stringify(currentUser));
      window.location.reload();
    }
  }, 2000);
}

async function leaveClassroom(courseId, courseName) {
  const confirmed = await showConfirmModal('student.leave_title', 'student.leave_msg', true, null, false, 'ok', 'cancel', { name: courseName });
  if (!confirmed) return;

  const res = await api('/student/leave', {
    method: 'POST',
    body: { student_id: currentUser.id, course_id: courseId }
  });

  if (res && res.success) {
    // If the student was inside this classroom, go back to portal
    if (typeof courseId !== 'undefined' && localStorage.getItem('aula_last_course') === courseId) {
      localStorage.removeItem('aula_last_course');
      localStorage.removeItem('aula_last_tab');
    }
    await refreshStudentEnrollments();
  } else {
    showAlert(t('error'), (res && res.error) || 'Failed to leave classroom.', true);
  }
}

async function adminHardReset() {
  const email = currentUser ? currentUser.email : '';
  if (!email) return;

  const confirmed = await showConfirmModal('confirm.erase_all_title', 'confirm.erase_all_msg2', true, 'HARD DELETE EVERYTHING');
  if (confirmed !== 'HARD DELETE EVERYTHING') return;

  const btn = document.querySelector('#admin-panel button');
  if (btn) btn.disabled = true;

  try {
    const res = await api('/admin/hard-reset', {
      method: 'POST',
      body: { email, confirm: 'HARD DELETE EVERYTHING' }
    });

    if (res.success) {
      await showAlert('success', 'System has been completely wiped. You will be logged out now.');
      logout();
    } else {
      showAlert(t('error'), res.error || 'Hard reset failed.', true);
    }
  } catch (e) {
    showAlert(t('error'), 'Network error during reset.', true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ── AulaAI Global Dictionary Logic ──

let activeDictWord = "";

// 3. Single-Click Trigger for Dictionary
window.addEventListener('click', async (e) => {
  // English Guard: Ignore if clicking English text
  if (e.target.closest('.english-translation') || e.target.closest('.ai-explanation')) {
    return;
  }

  let trigger = e.target.closest('.foreign-word');
  if (!trigger) return;

  let word = trigger.innerText.trim();

  // Smart Phrase Expansion (e.g., teşekkür -> teşekkür ederim)
  if (word.toLowerCase() === 'teşekkür' || word.toLowerCase() === 'ederim') {
    const fullText = trigger.parentElement.innerText || "";
    if (fullText.toLowerCase().includes('teşekkür ederim')) {
      word = "teşekkür ederim";
    }
  }

  // Only trigger if we are inside a study area
  const isStudyArea = e.target.closest('.study-card') || e.target.closest('#ai-book-content') || e.target.closest('#s-ai-book-content-area');

  if (word && isStudyArea && word.length > 1 && word.length < 600) {
    showDict(word, e);
  }
});

async function showDict(word, e) {
  const popup = document.getElementById('aula-dict-popup');
  const content = document.getElementById('dict-content');
  const loading = document.getElementById('dict-loading');

  activeDictWord = word;

  // Position popup using page coordinates so it scrolls with content
  popup.style.display = 'block';
  // Support dynamic width calculation up to 520px max, with 16px margins
  const popupWidth = Math.min(520, window.innerWidth - 32);

  let left = e.pageX - popupWidth / 2;
  let top = e.pageY + 20;

  if (left < 16) left = 16;
  if (left + popupWidth > window.innerWidth - 16) left = window.innerWidth - popupWidth - 16;

  popup.style.left = `${left}px`;
  popup.style.top = `${top}px`;

  content.style.display = 'none';
  loading.style.display = 'block';

  try {
    const lang = (currentCourse && currentCourse.language) ? currentCourse.language : 'English';
    // Pass the current study topic as context so the AI doesn't contradict lesson material
    const topicTitle = localStorage.getItem('aula_last_topic_title') || '';
    let dictUrl = `/dictionary?word=${encodeURIComponent(word)}&lang=${lang}`;
    if (topicTitle) dictUrl += `&context=${encodeURIComponent(topicTitle)}`;
    const res = await api(dictUrl);

    loading.style.display = 'none';
    content.style.display = 'block';

    // Unified AI-First Display
    const explanation = res.explanation || (res.definitions ? res.definitions[0].definition : "No definition found.");
    const usage = res.usage || "Use it in daily conversation.";
    const tip = res.tip || t('explain_more');
    const source = res.source || "AulaAI Brain";

    content.innerHTML = `
            <div style="margin-bottom:16px;">
                <div id="dict-word-title" style="font-size:${word.length > 40 ? '16px' : '24px'}; color:#fff; font-weight:800; letter-spacing:-0.5px; line-height:1.4; margin-bottom:8px; word-break:break-word;">${word}</div>
                <div style="font-size:12px; color:var(--accent-light); text-transform:uppercase; letter-spacing:1px; font-weight:700;">(${lang.split('(')[0].trim()})</div>
            </div>
            
            <div class="ai-card">
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
                    <span style="font-size:18px;">🤖</span>
                    <span style="font-size:11px; font-weight:800; color:var(--accent-light); text-transform:uppercase; letter-spacing:1px;">Linguistic Intelligence</span>
                </div>
                <div class="ai-explanation" style="font-size:16px; color:#ffffff; line-height:1.6; margin-bottom:14px;">${explanation}</div>
                
                <div style="font-size:11px; font-weight:700; color:var(--accent-light); text-transform:uppercase; margin-bottom:6px;">Usage</div>
                <div class="english-translation" style="font-style:italic; font-size:15px; color:rgba(255,255,255,0.7); margin-bottom:14px;">"${usage}"</div>
                
                <div style="background:rgba(255,255,255,0.05); padding:12px; border-radius:12px; font-size:13px; color:rgba(255,255,255,0.6); line-height:1.4;">
                    <span style="font-weight:700; color:var(--accent-light);">PRO-TIP:</span> ${tip}
                </div>
            </div>
            
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:10px; color:var(--text-muted); opacity:0.6;">
                <span>POWERED BY ${source.toUpperCase()}</span>
                <span style="cursor:pointer;" onclick="activeDictWord=''; document.getElementById('aula-dict-popup').style.display='none';">CLOSE</span>
            </div>
        `;
  } catch (err) {
    console.error("Dict error:", err);
    // Show silent error in popup
    loading.style.display = 'none';
    content.style.display = 'block';
    document.getElementById('dict-word').textContent = word;
    document.getElementById('dict-meanings').innerHTML = `<div style="color:var(--danger); font-size:12px;">Dictionary service unavailable.</div>`;
  }
}

function closeDict() {
  const popup = document.getElementById('aula-dict-popup');
  if (popup) popup.style.display = 'none';
}

// Close on click outside
window.addEventListener('mousedown', (e) => {
  const popup = document.getElementById('aula-dict-popup');
  if (popup && popup.style.display === 'block' && !popup.contains(e.target)) {
    closeDict();
  }
});

async function askAiAboutWord() {
  if (!activeDictWord) return;
  const wordToAsk = activeDictWord;

  const content = document.getElementById('dict-content');
  const loading = document.getElementById('dict-loading');
  const meanings = document.getElementById('dict-meanings');

  // Show AI Loading State in the popup
  meanings.innerHTML = `
        <div style="text-align:center; padding:20px; animation:pulse 1.5s infinite;">
            <div style="font-size:32px; margin-bottom:12px;">🧠</div>
            <div style="font-size:10px; color:var(--accent-light); text-transform:uppercase; letter-spacing:2px; font-weight:800;">AI is thinking...</div>
        </div>
    `;

  try {
    const lang = (currentCourse && currentCourse.language) ? currentCourse.language : 'English';
    const res = await api(`/dictionary/ai-explain?word=${encodeURIComponent(wordToAsk)}&lang=${lang}`);

    if (res.explanation) {
      meanings.innerHTML = `
                <div style="background:rgba(99,102,241,0.1); padding:16px; border-radius:16px; border:1px solid rgba(99,102,241,0.2);">
                    <div style="font-size:11px; font-weight:800; color:var(--accent-light); text-transform:uppercase; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
                        <span>🤖</span> AI Explanation
                    </div>
                    <div style="font-size:14px; color:#fff; line-height:1.5; margin-bottom:12px;">${res.explanation}</div>
                    
                    <div style="font-size:11px; font-weight:800; color:var(--accent-light); text-transform:uppercase; margin-bottom:4px; opacity:0.7;">Usage</div>
                    <div style="font-size:13px; color:#e2e8f0; line-height:1.4; margin-bottom:12px; font-style:italic;">"${res.usage}"</div>
                    
                    <div style="background:rgba(255,255,255,0.05); padding:8px 12px; border-radius:10px; font-size:12px; color:var(--text-muted);">
                        <span style="color:var(--accent-light); font-weight:700;">PRO-TIP:</span> ${res.tip}
                    </div>
                </div>
            `;
    } else {
      meanings.innerHTML = `<div style="color:var(--danger); font-size:12px;">${t('ai_error')}</div>`;
    }
  } catch (err) {
    console.error("AI Dict error:", err);
    meanings.innerHTML = `<div style="color:var(--danger); font-size:12px;">AI connection lost.</div>`;
  }
}





