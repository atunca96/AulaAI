// ── State & i18n ──
let currentUser = null;
let courseId = null;
let curriculum = [];
let currentCourse = null;
let currentLang = localStorage.getItem('aula_lang') || 'tr';
let aiStatus = null;
let _lastVersion = -1;
let _buildStartTime = 0;
let _syncInterval = null;
let _lastExtractedLanguage = null;
let _buildingCourses = [];
let _lastActivityData = null;
const _answeredQuestionsState = {};
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

// ── TTS Audio Engine (Google Translate TTS — Direct, no server proxy) ──
const _ttsAudioCache = new Map();
let _ttsPlaying = false;
const PERMANENT_STUDENT_NUMBERS = ['176724049', '176725007', '176725019', '176725005', '176725038', '176725853', '176725029', '176725004'];

// Language name → ISO code for Google TTS
const _langCodes = {
  'german': 'de', 'deutsch': 'de', 'spanish': 'es', 'español': 'es',
  'french': 'fr', 'français': 'fr', 'turkish': 'tr', 'türkçe': 'tr',
  'italian': 'it', 'italiano': 'it', 'portuguese': 'pt', 'português': 'pt',
  'arabic': 'ar', 'japanese': 'ja', 'chinese': 'zh', 'korean': 'ko',
  'russian': 'ru', 'english': 'en', 'dutch': 'nl', 'polish': 'pl',
  'swedish': 'sv', 'norwegian': 'no', 'danish': 'da', 'finnish': 'fi',
  'greek': 'el', 'czech': 'cs', 'hungarian': 'hu', 'romanian': 'ro',
  'hindi': 'hi', 'thai': 'th', 'vietnamese': 'vi', 'indonesian': 'id',
  'hebrew': 'he', 'persian': 'fa', 'ukrainian': 'uk', 'croatian': 'hr',
  'serbian': 'sr', 'bulgarian': 'bg', 'malay': 'ms', 'swahili': 'sw'
};

function _getLangCode(lang) {
  if (!lang) return 'en';
  const key = lang.split('(')[0].trim().toLowerCase();
  return _langCodes[key] || key.substring(0, 2).toLowerCase();
}

function _getTTSUrl(text, lang) {
  const tl = _getLangCode(lang);
  return `/api/tts?text=${encodeURIComponent(text)}&lang=${tl}`;
}

// Preload: create Audio objects that start buffering immediately
function preloadTTS(words, lang) {
  if (!lang && currentCourse && currentCourse.language) {
    lang = currentCourse.language.split('(')[0].trim();
  }
  lang = lang || 'English';
  
  const unique = [...new Set(words.map(w => w.trim()).filter(w => w.length > 0 && w.length < 100))];
  unique.forEach(word => {
    const cacheKey = `${lang}_${word.toLowerCase()}`;
    if (_ttsAudioCache.has(cacheKey)) return;
    
    const audio = new Audio(_getTTSUrl(word, lang));
    audio.preload = 'auto';
    audio.load();
    _ttsAudioCache.set(cacheKey, audio);
  });
}

let _ttsCurrentAudio = null;

async function speakText(text, lang) {
  if (!text) return;
  
  // Stop current audio if playing
  if (_ttsCurrentAudio) {
    _ttsCurrentAudio.pause();
    _ttsCurrentAudio.currentTime = 0;
    _ttsCurrentAudio = null;
  }
  
  if (!lang && currentCourse && currentCourse.language) {
    lang = currentCourse.language.split('(')[0].trim();
  }
  lang = lang || 'English';

  const cacheKey = `${lang}_${text.toLowerCase()}`;
  
  try {
    _ttsPlaying = true;

    let audio;
    if (_ttsAudioCache.has(cacheKey)) {
      audio = _ttsAudioCache.get(cacheKey);
    } else {
      audio = new Audio(_getTTSUrl(text, lang));
      _ttsAudioCache.set(cacheKey, audio);
    }

    audio.onended = () => { _ttsPlaying = false; _ttsCurrentAudio = null; };
    audio.onerror = () => { _ttsPlaying = false; _ttsCurrentAudio = null; };
    audio.currentTime = 0;
    _ttsCurrentAudio = audio;
    await audio.play();
  } catch (e) {
    console.error('TTS Error:', e);
    _ttsPlaying = false;
  }
}

// Inject TTS pulse animation CSS
(function() {
  const style = document.createElement('style');
  style.textContent = `
    @keyframes ttsPulse {
      0% { background: transparent; }
      50% { background: var(--accent-glow); }
      100% { background: transparent; }
    }
    .tts-speaking {
      animation: ttsPulse 1s ease-out;
    }
    .tts-btn {
      background: none;
      border: none;
      cursor: pointer;
      padding: 6px;
      border-radius: var(--radius-sm);
      color: var(--accent);
      font-size: 18px;
      transition: all 0.2s ease;
      flex-shrink: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
    }
    .tts-btn:hover {
      background: var(--accent-glow);
    }
    .tts-btn:active {
      transform: scale(0.95);
    }
    .tts-btn.playing {
      background: var(--accent-glow);
      color: var(--accent);
    }
  `;
  document.head.appendChild(style);
})();

const TTS_SVG_IDLE = '<svg style="width:16px;height:16px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>';
const TTS_SVG_PLAYING = '<svg style="width:16px;height:16px;display:inline-block;vertical-align:middle;color:var(--accent);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path></svg>';
const SVG_TRASH = '<svg style="width:14px;height:14px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>';
const SVG_EDIT = '<svg style="width:14px;height:14px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';
const SVG_GEAR = '<svg style="width:14px;height:14px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>';
const SVG_BOOK = '<svg style="width:14px;height:14px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>';
const SVG_SUN = '<svg style="width:18px;height:18px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
const SVG_MOON = '<svg style="width:18px;height:18px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
const SVG_EYE = '<svg style="width:14px;height:14px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
const SVG_KEY = '<svg style="width:14px;height:14px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2l-2 2m-1.5 1.5L14 9m-4-4l-6.5 6.5a4.95 4.95 0 0 0 7 7L17 12V9h-3V6h-3V3z"/></svg>';
const SVG_CHAT = '<svg style="width:14px;height:14px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
const SVG_BAN = '<svg style="width:14px;height:14px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>';
const SVG_PLUS = '<svg style="width:14px;height:14px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>';
const SVG_CHECK = '<svg style="width:14px;height:14px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
const SVG_CROSS = '<svg style="width:14px;height:14px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
const SVG_ACADEMIC = '<svg style="width:18px;height:18px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 2 3 3 6 3s6-1 6-3v-5"/></svg>';
const SVG_SEARCH = '<svg style="width:40px;height:40px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>';
const SVG_SCHOOL = '<svg style="width:48px;height:48px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3"/></svg>';
const SVG_WARNING = '<svg style="width:36px;height:36px;display:inline-block;vertical-align:middle;" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';

function handleTTSClick(btn, text, lang, event) {
  if (event) { event.stopPropagation(); event.preventDefault(); }
  
  // Reset all other playing buttons
  document.querySelectorAll('.tts-btn.playing').forEach(b => {
    b.classList.remove('playing');
    b.innerHTML = TTS_SVG_IDLE;
  });
  document.querySelectorAll('.tts-speaking').forEach(c => c.classList.remove('tts-speaking'));
  
  btn.classList.add('playing');
  btn.innerHTML = TTS_SVG_PLAYING;
  
  const card = btn.closest('[style*="border-radius"]');
  if (card) card.classList.add('tts-speaking');
  
  speakText(text, lang).then(() => {
    const checkDone = setInterval(() => {
      if (!_ttsPlaying) {
        clearInterval(checkDone);
        btn.classList.remove('playing');
        btn.innerHTML = TTS_SVG_IDLE;
        if (card) card.classList.remove('tts-speaking');
      }
    }, 200);
  });
}

function toggleDialogueTrans(id, btn) {
  const el = document.getElementById(id);
  if (!el) return;
  const isHidden = el.classList.contains('hidden-trans') || el.style.display === 'none';
  if (isHidden) {
    el.classList.remove('hidden-trans');
    el.style.display = 'block';
    if (btn) {
      btn.classList.add('active');
      btn.setAttribute('aria-expanded', 'true');
    }
  } else {
    el.classList.add('hidden-trans');
    el.style.display = 'none';
    if (btn) {
      btn.classList.remove('active');
      btn.setAttribute('aria-expanded', 'false');
    }
  }
}

// ── Message Sync Engine ──
let messagePollingInterval = null;

function startMessagePolling() {
  if (messagePollingInterval) return;
  messagePollingInterval = setInterval(() => {
    // 1. If student is on message tab, refresh chat
    const sMessageTab = document.getElementById('tab-s-messages');
    if (sMessageTab && sMessageTab.classList.contains('active')) {
       syncStudentChat();
    }
    
    // 2. If lecturer is on inbox tab, refresh inbox or open chat
    const lInboxTab = document.getElementById('tab-inbox');
    if (lInboxTab && lInboxTab.classList.contains('active')) {
       if (currentChatStudentId) {
         syncLecturerChat();
       } else {
         loadInbox();
       }
    }
  }, 8000);
}

async function syncStudentChat() {
  if (!currentCourse || !currentUser) return;
  const messages = await api(`/messages?student_id=${currentUser.id}&course_id=${currentCourse.id}`);
  renderStudentChat(messages);
}

async function syncLecturerChat() {
  if (!currentChatStudentId || !currentChatCourseId) return;
  const messages = await api(`/messages?student_id=${currentChatStudentId}&course_id=${currentChatCourseId}`);
  renderLecturerChat(messages);
}

function renderStudentChat(messages) {
  const container = document.getElementById('student-chat-history');
  if (!container) return;
  const currentCount = container.querySelectorAll('.chat-bubble').length;
  if (messages.length === currentCount && currentCount > 0) return;

  container.innerHTML = `<div class="chat-container" style="display:flex; flex-direction:column; gap:12px; padding:10px;">` + messages.map(m => {
    const isMe = m.sender === 'student';
    const dateObj = new Date(m.created_at.includes('Z') ? m.created_at : m.created_at.replace(' ', 'T') + 'Z');
    return `
        <div class="chat-bubble ${isMe ? 'sent' : 'received'}" 
             style="align-self:${isMe ? 'flex-end' : 'flex-start'}; background:${isMe ? 'var(--gradient-1)' : 'var(--bg-input)'}; color:${isMe ? 'white' : 'var(--text-main)'}; padding:12px 16px; border-radius:18px; max-width:85%; box-shadow:0 2px 4px rgba(0,0,0,0.1); border:${isMe ? 'none' : '1px solid var(--border)'}; ${isMe ? 'border-bottom-right-radius:4px' : 'border-bottom-left-radius:4px'};">
          ${!isMe ? `<div class="chat-sender" data-i18n="Lecturer" style="font-size:11px; font-weight:700; margin-bottom:4px; color:var(--accent-light);">${t('Lecturer')}</div>` : ''}
          ${esc(m.content)}
          <span class="chat-time" style="display:block; font-size:10px; opacity:0.7; margin-top:4px; text-align:${isMe ? 'right' : 'left'};">${dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      `;
  }).join('') + `</div>`;
  container.scrollTop = container.scrollHeight;
}

function renderLecturerChat(messages) {
  const container = document.getElementById('inbox-messages');
  if (!container) return;
  const currentCount = container.querySelectorAll('.chat-bubble').length;
  if (messages.length === currentCount && currentCount > 0) return;

  container.innerHTML = `<div class="chat-container" style="display:flex; flex-direction:column; gap:12px; padding:10px;">` + messages.map(m => {
    const isMe = m.sender === 'lecturer';
    const dateObj = new Date(m.created_at.includes('Z') ? m.created_at : m.created_at.replace(' ', 'T') + 'Z');
    return `
        <div class="chat-bubble ${isMe ? 'sent' : 'received'}" 
             style="align-self:${isMe ? 'flex-end' : 'flex-start'}; background:${isMe ? 'var(--gradient-1)' : 'var(--bg-input)'}; color:${isMe ? 'white' : 'var(--text-main)'}; padding:12px 16px; border-radius:18px; max-width:85%; box-shadow:0 2px 4px rgba(0,0,0,0.1); border:${isMe ? 'none' : '1px solid var(--border)'}; ${isMe ? 'border-bottom-right-radius:4px' : 'border-bottom-left-radius:4px'};">
          ${isMe ? `<div class="chat-sender" data-i18n="Lecturer" style="font-size:11px; font-weight:700; margin-bottom:4px; color:rgba(255,255,255,0.7);">${t('Lecturer')}</div>` : ''}
          ${esc(m.content)}
          <span class="chat-time" style="display:block; font-size:10px; opacity:0.7; margin-top:4px; text-align:${isMe ? 'right' : 'left'};">${dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      `;
  }).join('') + `</div>`;
  container.scrollTop = container.scrollHeight;
}

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
let _syncTick = 0;
let _heartbeatInterval = null;

function startUserHeartbeat() {
  if (_heartbeatInterval) clearInterval(_heartbeatInterval);
  const sendPing = () => {
    if (!currentUser || !currentUser.id) return;
    fetch('/api/user/heartbeat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: currentUser.id })
    }).catch(() => {});
  };
  sendPing();
  _heartbeatInterval = setInterval(sendPing, 3000);
}

// Immediately notify server when student closes tab or leaves
window.addEventListener('beforeunload', () => {
  if (currentUser && currentUser.id && currentUser.role === 'student') {
    try {
      const payload = JSON.stringify({ user_id: currentUser.id });
      if (navigator.sendBeacon) {
        const blob = new Blob([payload], { type: 'application/json' });
        navigator.sendBeacon('/api/user/logout', blob);
      } else {
        fetch('/api/user/logout', { method: 'POST', body: payload, keepalive: true });
      }
    } catch (e) {}
  }
});

function startLiveSync() {
  if (_syncInterval) clearInterval(_syncInterval);
  startUserHeartbeat();
  _syncInterval = setInterval(async () => {
    if (!currentUser) return;
    try {
      _syncTick++;
      // Continuous heartbeat ping every 3 seconds for active user
      if (currentUser && currentUser.id && (_syncTick % 3 === 0)) {
        fetch('/api/user/heartbeat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: currentUser.id })
        }).catch(() => {});
      }

      const res = await fetch('/api/version');
      const data = await res.json();
      if (_lastVersion === -1) { _lastVersion = data.version; return; }
      if (data.version !== _lastVersion) {
        _lastVersion = data.version;
        console.log('[LiveSync] Data changed, refreshing...');

        // If admin panel is open, refresh students list immediately
        if (currentUser && (currentUser.role === 'lecturer' || currentUser.email === 'atunca96@gmail.com') && document.getElementById('classroom-selection-screen')?.classList.contains('active')) {
          loadAdminStudentPanel(true);
        }

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
            const isLecturer = currentUser.role === 'lecturer';
            const bannerId = isLecturer ? 'lecturer-building-banner' : 'student-building-banner';
            const fillId = isLecturer ? 'lecturer-progress-fill' : 'student-progress-fill';
            const textId = isLecturer ? 'lecturer-progress-text' : 'student-progress-text';
            const detailId = isLecturer ? 'lecturer-progress-detail' : 'student-progress-detail';
            const badgeId = isLecturer ? 'lecturer-stage-badge' : 'student-stage-badge';

            const buildBanner = document.getElementById(bannerId);
            const progressFill = document.getElementById(fillId);
            const progressText = document.getElementById(textId);
            const progressDetail = document.getElementById(detailId);
            const stageBadge = document.getElementById(badgeId);

            if (buildBanner) {
              buildBanner.classList.toggle('hidden', !prog.is_building);
              if (prog.stage === 'failed' || prog.stage === 'timeout') {
                buildBanner.classList.add('build-failed');
              } else {
                buildBanner.classList.remove('build-failed');
              }
            }

            const pct = prog.is_building 
              ? Math.max(0, Math.min(100, Math.round(prog.percentage || 0)))
              : Math.max(0, Math.min(100, Math.round(prog.percentage || 0)));
            if (progressFill) progressFill.style.width = pct + '%';
            if (progressText) progressText.textContent = pct + '%';

            if (stageBadge && prog.stage) {
              stageBadge.textContent = translateBuildStage(prog.stage);
            }

            if (progressDetail && prog.message) {
              progressDetail.textContent = translateBuildMessage(prog.message);
            }

            // Update step nodes on lecturer banner
            if (isLecturer) {
              const stepsTrack = document.getElementById('lecturer-steps-track');
              if (stepsTrack) {
                const stageOrder = ['analyzing', 'structuring', 'enriching', 'finalizing'];
                const currentStageIdx = stageOrder.indexOf(prog.stage);
                stepsTrack.querySelectorAll('.build-step-node').forEach(node => {
                  const nodeStep = node.getAttribute('data-step');
                  const nodeIdx = stageOrder.indexOf(nodeStep);
                  node.classList.remove('active', 'done');
                  if (nodeIdx !== -1) {
                    if (nodeIdx < currentStageIdx) {
                      node.classList.add('done');
                    } else if (nodeIdx === currentStageIdx) {
                      node.classList.add('active');
                    }
                  }
                });
              }
            }

            // Update local state if it finished building
            if (!prog.is_building && currentCourse.is_building) {
              currentCourse.is_building = 0;
              showToast(t('Classroom is ready!'), "success");
              refreshCurrentView();
            }
          }
        });
      }

      // Continuous background polling for Admin Students Panel to update status LIVE without refreshing
      if (currentUser && (currentUser.role === 'lecturer' || currentUser.email === 'atunca96@gmail.com') && document.getElementById('classroom-selection-screen')?.classList.contains('active')) {
        const pnl = document.getElementById('admin-students-panel');
        if (pnl && !pnl.classList.contains('hidden')) {
          loadAdminStudentPanel(true);
        }
      }
    } catch (e) { /* ignore network errors */ }
  }, 1000);
}

function stopLiveSync() {
  if (_syncInterval) { clearInterval(_syncInterval); _syncInterval = null; }
  if (_heartbeatInterval) { clearInterval(_heartbeatInterval); _heartbeatInterval = null; }
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
            const pct = Math.max(0, Math.min(100, Math.round(currentCourse.percentage || 0)));
            if (progressFill) progressFill.style.width = pct + '%';
            if (progressText) progressText.textContent = pct + '%';
            const detailEl = document.getElementById(isLecturer ? 'lecturer-progress-detail' : 'student-progress-detail');
            if (detailEl && currentCourse.build_message) detailEl.textContent = translateBuildMessage(currentCourse.build_message);
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
    // Only check status when we know which course the student is waiting for.
    // Omitting course_id would fall back to user-level status which is always
    // 'approved' (set at registration), causing a spurious reload loop.
    const waitCourseId = localStorage.getItem('aula_last_course');
    if (waitCourseId) {
      api('/user/status?user_id=' + currentUser.id + '&course_id=' + waitCourseId).then(async status => {
        if (status && status.status === 'approved') {
          if (window._waitingPoll) clearInterval(window._waitingPoll);
          window.location.reload();
        } else if (status && (status.error === 'enrollment_removed' || status.error === 'course_deleted')) {
          if (window._waitingPoll) clearInterval(window._waitingPoll);
          await showAlert(t('alert.classroom_reset'), t('alert.classroom_reset_msg'), true);
          localStorage.removeItem('aula_last_course');
          localStorage.removeItem('aula_last_tab');
          window.location.reload();
        }
      });
    }
    applyTranslations();
    return;
  }
  if (currentUser.role === 'lecturer') {
    if (document.getElementById('classroom-selection-screen').classList.contains('active')) {
      showClassroomSelection();
    }

    // Only refresh the ACTIVE tab's data to prevent UI flicker
    const activeTab = document.querySelector('.nav-tab.active');
    const tabId = activeTab ? activeTab.dataset.tab : '';
    
    if (tabId === 'overview') loadOverview();
    if (tabId === 'curriculum') { loadCurriculumAsync(); renderStudyBook(); }
    if (tabId === 'quizzes-mgmt') loadQuizList();
    if (tabId === 'assignments-mgmt') loadAssignmentList();
    if (tabId === 'students') loadStudentRoster();
    if (tabId === 'book' || tabId === 'study-materials') renderStudyBook();

    // Always refresh roster + inbox badge in background
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
              openChat(currentChatStudentId, currentChatStudentName, currentChatCourseId, true);
            } else {
              loadInbox();
            }
          }
        }
      });
    }
  } else {
    loadStudentHome();
    loadStudentStats();
    
    // Only refresh active tab's data
    const activeTab = document.querySelector('.nav-tab.active');
    const tabId = activeTab ? activeTab.dataset.tab : '';
    if (tabId === 'book' || tabId === 's-study-tab' || tabId === 'study-materials') renderStudyBook();
    if (tabId === 'quizzes') loadQuizList();
    if (tabId === 'assignments') loadAssignmentList();
    
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
            loadStudentChat(true);
          }
        }
      });
    }
  }
}

const i18n = {
  en: {
    langBtn: 'Language: EN',
    // New login showcase translations
    'hero.value_title': 'Marmara University Language Portal',
    'hero.value_subtitle': 'Curriculum-based interactive practices and resource management system for the School of Foreign Languages.',
    'hero.widget_title': 'INTERACTIVE STUDY MATERIAL',
    'hero.demo_es_trans': 'Hello, how are you today?',
    'hero.demo_de_trans': 'Hello, how are you today?',
    'hero.demo_fr_trans': 'Hello, how are you today?',
    'hero.demo_tip': 'Note: Click any word for instant dictionary translation',
    Translation: 'Translation',
    // Privacy policy
    'login.agree_prefix': 'By signing in, you agree to our ',
    'login.privacy_policy': 'Privacy Policy',
    'login.agree_suffix': '.',
    'privacy.title': 'Privacy Policy',
    'privacy.intro': 'AulaAI processes minimal student and lecturer data solely to provide customized language learning materials.',
    'privacy.h1': '1. Data Collection',
    'privacy.p1': 'We collect student names, school numbers, classroom join codes, dialogue audio files, and uploaded educational PDFs. This data is used by AI models to generate personalized worksheets and flashcards.',
    'privacy.h2': '2. Local Processing & Security',
    'privacy.p2': 'All records are stored securely on local database servers. We comply with standard KVKK and GDPR data minimization requirements. Your data is never sold or used for advertisement targeting.',
    'privacy.h3': '3. Your Rights',
    'privacy.p3': 'Students and lecturers have full rights to request PIN resets, retrieve their overall curriculum history, or request permanent deletion of their account databases. For inquiries, email rkahraman@marmara.edu.tr.',
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
    'Lecturer': 'Lecturer', 'Student': 'Student',
    select_study_topic: 'Select a topic to start studying',
    page: 'PAGE',
    // Student dashboard
    home: 'Home', practice: 'Practice', quizzes: 'Quizzes', myProgress: 'My Progress',
    keepUp: 'Keep up the great work!', overallMastery: 'Overall Mastery', strongTopics: 'Strong Topics', needsWork: 'Needs Work', topicsStudied: 'Topics Studied', currentChapter: 'Current Chapter',
    selectPractice: 'Select a topic to practice', availableQuizzes: 'Available quizzes', trackMastery: 'Track your mastery across topics', noQuizzes: 'No quizzes yet.',
    takeQuiz: 'Take Quiz', view: 'View', close: 'Close', done: 'Done', submit: 'Submit', check: 'Check',
    yourScore: 'Your Score', questions: 'questions', correct: 'correct',
    incorrectAns: 'Incorrect. The answer is:', correctAns: 'The correct answer is:', correctMsg: 'Correct!',
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
    at_risk_students: 'At-Risk Students', topic_difficulty: 'Topic Difficulty',
    'prac.dialogue_order': 'Reorder the dialogue correctly:',
    'prac.dialogue': 'Dialogue',
    'active_this_week': '{count} Active this week', 'avg_across_topics': 'Average across all topics',
    'students_needing_attention': 'Students needing attention', 'mastery_above_80': 'Mastery above 80%',
    no_at_risk: 'No at-risk students', mastery: 'mastery',
    'welcomeBack': 'Welcome back, {name}',
    'Welcome back,': 'Welcome back,',
    // Data Management
    data_mgmt: 'Data Management',
    erase_all_btn: 'Erase All Data',
    reset_class_data_btn: 'Reset Classroom',
    erase_all_desc: 'Resets student responses and mastery progress for this classroom.',
    // Activities
    'In-Class Activities': 'In-Class Activities', 'Generate and launch live activities': 'Generate and launch live activities',
    'Launch Activity': 'Launch Activity', 'Select Chapter & Topic': 'Select Chapter & Topic',
    'Generate Activity': 'Generate Activity', 'Loading curriculum...': 'Loading curriculum...',
    // Quiz Management
    'Quiz Management': 'Quiz Management', 'Create and manage quizzes': 'Create and manage quizzes',
    '\u2795 Create New Quiz': '\u2795 Create New Quiz', 'Create New Quiz': 'Create New Quiz', 'Quiz Title': 'Quiz Title',
    Chapter: 'Select Topic', 'All chapters': 'All Topics', AllTopics: 'All Topics', Questions: 'Questions', 'Create Quiz': 'Create Quiz',
    completed: 'Completed', 'Created': 'Created',
    // Assignments
    'Assignment Management': 'Assignment Management', 'Assign homework to your students': 'Assign homework to your students',
    '\u2795 Create New Assignment': '\u2795 Create New Assignment', 'Create New Assignment': 'Create New Assignment', 'Assignment Title': 'Assignment Title',
    'Create Assignment': 'Create Assignment', 'Your homework tasks': 'Your homework tasks',
    // Students
    'Student Roster': 'Student Roster', 'Monitor individual student progress': 'Monitor individual student progress',
    Kick: 'Kick', 'Mastery:': 'Mastery:', responses: 'responses',
    // Reports
    'report.title': 'Weekly Report', 'report.subtitle': 'AI-generated class performance analysis', 'report.generate': 'Report',
    'Content Map': 'Content Map', 'You': 'You',
    // Curriculum
    'Aula Internacional Plus 1 — Content Map': 'Aula Internacional Plus 1 — Content Map',
    // Waiting Room
    'Account Pending Approval': 'Account Pending Approval',
    'Please wait for your lecturer to approve your account. This screen will refresh automatically once approved.': 'Please wait for your lecturer to approve your account. This screen will refresh automatically once approved.',
    // Nav badge
    'AI ACTIVE': 'AI ACTIVE',
    // Student home
    'Current Chapter': 'Current Chapter',
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
    'draft.click_add': 'Please click "\u2795 Add Question" to create them manually.',
    // Classroom Selection
    'class.selection': 'Classroom Selection',
    'class.subtitle': 'Select a classroom to manage or create a new one',
    'class.create': 'Create New Classroom from PDF',
    'class.create_generic': 'Create New Classroom',
    'class.create_title': 'Classroom Creation',
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
    'ai.gen_curriculum': 'Generate Curriculum',
    'ai.clear_cache': 'Clear Cached Blueprints',
    'ai.regenerate': 'Regenerate',
    'ai.cache_cleared': 'All cached blueprints have been deleted. Next generation will create fresh curricula.',
    'ai.cache_cleared_title': 'Cache Cleared',
    'ai.review_title': 'Review Curriculum',
    'ai.review_desc': 'AI suggested these topics. You can edit or remove them.',
    'class.add_topic': 'Add Topic',
    'class.topic_name_placeholder': 'New Topic Name',
    'class.build_btn': 'Build Classroom',
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
    'ai.gen_curriculum': 'Generate Curriculum',
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
    'student_login_hint': 'Sign in with your student number and password',
    'Invalid student number or password': 'Invalid student number or password',
    'Invalid credentials': 'Invalid email or password',
    'Student number is required': 'Student number is required',
    'Password is required': 'Password is required',
    'Please enter student number and password.': 'Please enter student number and password.',
    'Invalid classroom code. Please verify the code with your teacher.': 'Invalid classroom code. Please verify the code with your teacher.',
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
    'class.building_title': 'Classroom Content Generation',
    'class.building_title_student': 'Course Content Update in Progress',
    'class.force_restart': 'Force Restart',
    'step.analysis': '1. Analysis',
    'step.curriculum': '2. Curriculum',
    'step.lessons': '3. Lessons',
    'step.finalize': '4. Finalize',
    'answer': 'Answer',
    'responses': 'Responses',
    'gen.generating': 'Generating Practice Activities...',
    'gen.loading': 'Questions are being generated...',
    'gen.time': 'The AI is generating custom practice exercises and test questions for this topic. Please wait...',
    'Explanation': 'Explanation',
    'explanation': 'Explanation',
    'Unit': 'Unit',
    'Units': 'Units',
    'units': 'Units',
    'Material': 'Material',
    'study': 'Material',
    'book': 'Book',
    'study.units': 'Units',
    'study.sidebar_guide': 'Use the sidebar on the left to navigate through units.',
    'study.vocabulary': 'Vocabulary Cheat Sheet',
    'study.grammar': 'Grammar & Key Rules',
    'study.usage': 'Practical Usage',
    'study.complete': 'Lesson Complete',
    'study.preview': 'Lesson Preview',
    'study.back': 'Back',
    'study.next': 'Next Page',
    'study.quick_check': 'Quick Check',
    'study.ready': "You're Ready to Practice!",
    'study.preview_end': 'End of Lesson Material',
    'study.preview_msg': 'This is how the lesson appears to your students.',
    'study.ready_msg': "Now it's time to test your knowledge.",
    'study.start_practice': 'Start Practice Session',
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
    'tap_explain': 'Tap to explain',
    'explain_ai': 'Explain with Assistant',
    'ai_error': 'Assistant was unable to explain this word right now.',
    'explain_more': 'Click \'Explain\' again for more details.',
    'ai_analyzing': 'Analyzing your answer...',
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
    'confirm.hard_delete_msg': 'LAST WARNING: Type "HARD DELETE EVERYTHING" to confirm absolute deletion.',
    'theme.dark': 'Theme: Dark',
    'theme.light': 'Theme: Light',
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
    'class.pdf_status_title': 'PDF Status Confirmation',
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
    // Admin Student Panel
    'student_login_hint': 'Sign in with your student number and password',
    'admin.add_student': 'Add Student',
    'admin.set_password': 'Set Password',
    'admin.enter_new_password_for': 'Enter new password for {name}:',
    'admin.enter_student_number': 'Enter the student number:',
    'admin.enter_student_name': 'Enter full name for #{number}:',
    'admin.enter_student_pwd': 'Enter password for {name}:',
    'admin.password_set_success': 'Password updated successfully.',
    'admin.student_created_success': 'Student account created successfully.',
    'admin.all_students': 'All Students',
    'admin.reset_all_students': 'Reset All Students',
    'admin.reset_students_confirm': 'This will delete ALL student accounts and their data across ALL classrooms. This cannot be undone.',
    'admin.reset_students_type': 'Type RESET ALL STUDENTS to confirm:',
    'admin.no_students': 'No student accounts found.',
    'admin.student_name': 'Name',
    'admin.student_id': 'ID / Email',
    'admin.enrolled_in': 'Enrolled In',
    'admin.responses': 'Responses',
    'admin.status': 'Status',
    'admin.action': 'Action',
    'admin.remove': 'Remove',
    'admin.active': 'Active',
    'admin.pending': 'Pending',
    'admin.inactive': 'Inactive',
    'admin.students_removed': '{count} student account(s) have been removed.',
    'admin.reset_pin': 'Reset PIN',
    'admin.reset_progress': 'Reset Progress',
    'confirm.reset_pin_title': 'Reset Student PIN',
    'confirm.reset_pin_msg': 'Are you sure you want to reset the PIN for {name}? They will be asked to set a new PIN when they next access their classrooms.',
    'confirm.reset_progress_title': 'Reset Student Progress',
    'confirm.reset_progress_msg': 'Are you sure you want to wipe ALL quiz and assignment history for {name}? This cannot be undone.',
    'alert.pin_reset_success': 'Student PIN has been reset.',
    'alert.progress_reset_success': 'Student progress has been wiped.',
    'student.pin_must_be_4': 'PIN must be exactly 4 digits',
    'class.stop_build': 'Stop Generation',
    'class.confirm_stop_build': 'Are you sure you want to stop generating lesson materials? The background process will be terminated.',
    'class.build_stopped': 'Lesson generation stopped.',
    'architect.busy': 'The Architect is busy...',
    'stage.starting': 'STARTING',
    'stage.analyzing': 'ANALYZING',
    'stage.structuring': 'STRUCTURING',
    'stage.enriching': 'LESSONS',
    'stage.finalizing': 'FINALIZING',
    'stage.completed': 'COMPLETED',
  },
  tr: {
    // New login showcase translations
    'hero.value_title': 'Marmara Üniversitesi Dil Eğitim Portalı',
    'hero.value_subtitle': 'Yabancı Diller Yüksekokulu müfredatına dayalı interaktif dil alıştırmaları ve kaynak yönetim sistemi.',
    'hero.widget_title': 'ETKİLEŞİMLİ ÇALIŞMA MATERYALİ',
    'hero.demo_es_trans': 'Merhaba, bugün nasılsın?',
    'hero.demo_de_trans': 'Merhaba, bugün nasılsın?',
    'hero.demo_fr_trans': 'Merhaba, bugün nasılsın?',
    'hero.demo_tip': 'Not: Anında sözlük çevirisi için kelimelerin üzerine tıklayabilirsiniz.',
    Translation: 'Çeviri',
    // Privacy policy
    'login.agree_prefix': 'Giriş yaparak ',
    'login.privacy_policy': 'Gizlilik Politikası',
    'login.agree_suffix': '\'mızı kabul etmiş olursunuz.',
    'privacy.title': 'Gizlilik Politikası',
    'privacy.intro': 'AulaAI, öğrencilere ve öğretmenlere kişiselleştirilmiş dil öğrenim materyalleri sunabilmek amacıyla yalnızca asgari düzeyde veri işlemektedir.',
    'privacy.h1': '1. Veri Toplama',
    'privacy.p1': 'Öğrenci isimlerini, okul numaralarını, sınıf katılım kodlarını, diyalog ses dosyalarını ve yüklenen eğitim PDF\'lerini topluyoruz. Bu veriler yapay zeka modelleri tarafından kişiselleştirilmiş çalışma sayfaları ve kelime kartları oluşturmak için kullanılır.',
    'privacy.h2': '2. Yerel İşleme ve Güvenlik',
    'privacy.p2': 'Tüm kayıtlar yerel veri tabanı sunucularında güvenli bir şekilde saklanır. Standart KVKK ve GDPR veri minimizasyonu gerekliliklerine uyuyoruz. Verileriniz asla satılmaz veya reklam hedeflemesi amacıyla kullanılmaz.',
    'privacy.h3': '3. Haklarınız',
    'privacy.p3': 'Öğrenciler ve öğretim elemanları, PIN kodlarının sıfırlanmasını talep etme, müfredat geçmişlerini görüntüleme veya hesap veri tabanlarının kalıcı olarak silinmesini isteme hakkına sahiptir. Sorularınız için rkahraman@marmara.edu.tr adresine e-posta gönderebilirsiniz.',
    page: 'SAYFA',
    'ai.select_lang': '1. Dil Seçin',
    'ai.target_level': '2. Hedef Seviye',
    'ai.course_name': '3. Kurs Adı',
    'ai.name_placeholder': 'ör. Yoğun İspanyolca Yaz Kursu',
    'ai.gen_curriculum': 'Müfredat Oluştur',
    'loading': 'Yükleniyor...',
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
    'confirm.hard_delete_msg': 'SON UYARI: Kesin silme işlemini onaylamak için "HARD DELETE EVERYTHING" yazın.',
    'theme.dark': 'Tema: Karanlık',
    'theme.light': 'Tema: Aydınlık',
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
    'class.building_title': 'Sınıf İçeriği Hazırlanıyor',
    'class.building_title_student': 'Ders İçerikleri Güncelleniyor',
    'class.force_restart': 'Yeniden Başlat',
    'step.analysis': '1. Analiz',
    'step.curriculum': '2. Müfredat',
    'step.lessons': '3. Dersler',
    'step.finalize': '4. Tamamlama',
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
    'gen.generating': 'Alıştırmalar Hazırlanıyor...',
    'gen.loading': 'Sorular hazırlanıyor...',
    'gen.time': 'Yapay zeka bu konuya özel alıştırmalar ve test soruları üretiyor. Lütfen bekleyin...',
    'Explanation': 'Açıklama',
    'explanation': 'Açıklama',
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
    'study.quick_check': 'Hızlı Kontrol',
    'study.ready': 'Alıştırma Yapmaya Hazırsın!',
    'study.preview_end': 'Ders Materyali Sonu',
    'study.preview_msg': 'Bu dersin öğrencileriniz için nasıl göründüğüdür.',
    'study.ready_msg': 'Şimdi bilgini test etme zamanı.',
    'study.start_practice': 'Alıştırma Seansını Başlat',
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
    'student_login_hint': 'Öğrenci numaranız ve şifrenizle giriş yapın',
    'Invalid student number or password': 'Geçersiz öğrenci numarası veya şifre',
    'Invalid credentials': 'Geçersiz e-posta veya şifre',
    'Student number is required': 'Öğrenci numarası gereklidir',
    'Password is required': 'Şifre gereklidir',
    'Please enter student number and password.': 'Lütfen öğrenci numarası ve şifrenizi girin.',
    'missing_info': 'Lütfen öğrenci numarası ve şifrenizi girin.',
    'Invalid classroom code. Please verify the code with your teacher.': 'Geçersiz sınıf kodu. Lütfen öğretmeninizle teyit edin.',
    'Invalid classroom code': 'Geçersiz sınıf kodu',
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
    'study.sidebar_guide': 'Üniteler arasında gezinmek için soldaki kenar çubuğunu kullanın.',
    'Lecturer': 'Öğretmen', 'Student': 'Öğrenci',
    // Student dashboard
    home: 'Ana Sayfa', practice: 'Alıştırma', quizzes: 'Sınavlar', myProgress: 'Gelişimim',
    keepUp: 'Harika gidiyorsun, devam et!', overallMastery: 'Genel Başarı', strongTopics: 'İyi Olduğum Konular', needsWork: 'Eksiğim Olan Konular', topicsStudied: 'Çalışılan Konular', currentChapter: 'Mevcut Ünite',
    selectPractice: 'Alıştırma yapmak için bir konu seçin', availableQuizzes: 'Mevcut Sınavlar', trackMastery: 'Konulardaki başarı durumunuzu takip edin',
    takeQuiz: 'Sınava Başla', view: 'Görüntüle', close: 'Kapat', done: 'Bitti', submit: 'Gönder', check: 'Kontrol Et',
    yourScore: 'Puanınız', questions: 'soru', correct: 'doğru',
    incorrectAns: 'Yanlış. Doğru cevap:', correctAns: 'Doğru cevap:', correctMsg: 'Doğru!',
    takeQuizBtn: 'Sınavı Başlat', viewBtn: 'Görüntüle',
    noQuizzes: 'Henüz sınav yok.', noAssignments: 'Henüz ödev yok.',
    // Lecturer nav & tabs
    Lecturer: 'Öğretmen', Student: 'Öğrenci',
    Overview: 'Genel Bakış', Curriculum: 'Müfredat', Activities: 'Etkinlikler', Students: 'Öğrenciler', Reports: 'Raporlar', Dashboard: 'Kontrol Paneli', Assignments: 'Ödevler', Quizzes: 'Sınavlar', 'My Stats': 'İstatistiklerim',
    // Overview stats
    STUDENTS: 'ÖĞRENCİLER', 'CLASS_MASTERY': 'SINIF BAŞARISI', 'AT_RISK': 'RİSKLİ', 'TOP_PERFORMERS': 'EN İYİLER',
    'Class Mastery': 'Sınıf Başarısı', 'At Risk': 'Riskli', 'Top Performers': 'En İyiler',
    at_risk_students: 'Riskli Öğrenciler', topic_difficulty: 'Konu Zorluğu',
    'active_this_week': '{count} Bu hafta aktif', 'avg_across_topics': 'Tüm konularda ortalama',
    'students_needing_attention': 'Dikkat gerektiren öğrenciler', 'mastery_above_80': '%80 üzeri başarı',
    no_at_risk: 'Riskli öğrenci yok', mastery: 'başarı',
    'welcomeBack': 'Tekrar Hoş Geldin, {name}',
    'Welcome back,': 'Tekrar Hoş Geldin,',
    // Data Management
    data_mgmt: 'Veri Yönetimi',
    erase_all_btn: 'Tüm Verileri Sil',
    reset_class_data_btn: 'Sınıfı Sıfırla',
    erase_all_desc: 'Bu sınıftaki öğrenci yanıtlarını ve başarı verilerini sıfırlar.',
    // Activities
    'In-Class Activities': 'Sınıf İçi Etkinlikler', 'Generate and launch live activities': 'Canlı etkinlikler oluştur ve başlat',
    'Launch Activity': 'Etkinlik Başlat', 'Select Chapter & Topic': 'Ünite ve Konu Seç',
    'Generate Activity': 'Etkinlik Oluştur', 'Loading curriculum...': 'Müfredat yükleniyor...',
    // Quiz Management
    'Quiz Management': 'Sınav Yönetimi', 'Create and manage quizzes': 'Sınav oluştur ve yönet',
    '\u2795 Create New Quiz': '\u2795 Yeni Sınav Oluştur', 'Create New Quiz': 'Yeni Sınav Oluştur', 'Quiz Title': 'Sınav Başlığı',
    Chapter: 'Konu Seçin', 'All chapters': 'Tüm Konular', AllTopics: 'Tüm Konular', Questions: 'Soru Sayısı', 'Create Quiz': 'Sınav Oluştur',
    completed: 'Tamamlandı', 'Created': 'Oluşturuldu',
    // Assignments
    'Assignment Management': 'Ödev Yönetimi', 'Assign homework to your students': 'Öğrencilerinize ödev atayın',
    '\u2795 Create New Assignment': '\u2795 Yeni Ödev Oluştur', 'Create New Assignment': 'Yeni Ödev Oluştur', 'Assignment Title': 'Ödev Başlığı',
    'Create Assignment': 'Ödev Oluştur', 'Your homework tasks': 'Ödev görevleriniz',
    // Students
    'Student Roster': 'Öğrenci Listesi', 'Monitor individual student progress': 'Bireysel öğrenci gelişimini izle',
    Kick: 'At', 'Mastery:': 'Başarı:', responses: 'yanıt',
    // Reports
    'report.title': 'Haftalık Rapor', 'report.subtitle': 'Yapay zeka destekli sınıf performans analizi',
    'report.generate': 'Rapor Oluştur',
    'Content Map': 'İçerik Haritası', 'You': 'Siz', 'Curriculum': 'Müfredat',
    // Curriculum
    'Aula Internacional Plus 1 — Content Map': 'Aula Internacional Plus 1 — İçerik Haritası',
    // Waiting Room
    'Account Pending Approval': 'Hesabınız Onay Bekliyor',
    'Please wait for your lecturer to approve your account. This screen will refresh automatically once approved.': 'Lütfen öğretmeninizin hesabınızı onaylamasını bekleyin. Onaylandıktan sonra bu ekran otomatik olarak yenilenecektir.',
    // Nav badge
    'AI ACTIVE': 'AI AKTİF',
    // Student home
    'Current Chapter': 'Mevcut Ünite',
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
    'draft.click_add': 'Lütfen manuel olarak oluşturmak için "\u2795 Soru Ekle" butonuna tıklayın.',
    // Classroom Selection
    'class.selection': 'Sınıf Seçimi',
    'class.subtitle': 'Yönetmek için bir sınıf seçin veya yeni bir tane oluşturun',
    'class.create': 'PDF\'den Yeni Sınıf Oluştur',
    'class.create_generic': 'Yeni Sınıf Oluştur',
    'class.create_title': 'Yeni Sınıf Yöntemi',
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
    'ai.gen_curriculum': 'Müfredatı Oluştur',
    'ai.clear_cache': 'Önbellekteki Taslakları Temizle',
    'ai.regenerate': 'Yeniden Oluştur',
    'ai.cache_cleared': 'Tüm önbellekteki müfredat taslakları silindi. Bir sonraki oluşturma yeni müfredat üretecektir.',
    'ai.cache_cleared_title': 'Önbellek Temizlendi',
    'ai.review_title': 'Müfredatı İncele',
    'ai.review_desc': 'Yapay zeka bu konuları önerdi. Bunları düzenleyebilir veya kaldırabilirsiniz.',
    'class.add_topic': 'Konu Ekle',
    'class.topic_name_placeholder': 'Yeni Konu Adı',
    'class.build_btn': 'Sınıfı Oluştur',
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
    'Units': 'Üniteler',
    'units': 'Üniteler',
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
    'class.pdf_status_title': 'PDF Durumu Onayı',
    'class.pdf_status_msg': 'Yükleyeceğeniz PDF dosyası taranmış bir resim (flat scan) mi yoksa seçilebilir metin içeren dijital bir dosya mı? Taranmış resimler hatalı sonuçlara neden olabilir. Dosyanızın metin araması yapılabilir/seçilebilir olduğundan emin misiniz?',
    'class.pdf_status_ok': 'Evet, metin seçilebiliyor',
    'Tebrikler!': 'Tebrikler!',
    'is ready!': 'hazır!',
    'Detecting...': 'Algılanıyor...',
    'class.pdf_status_cancel': 'Hayır, kontrol edeceğim',
    'prac.dialogue_order': 'Diyaloğu doğru sıraya dizin:',
    'prac.dialogue': 'Diyalog',
    'no_messages': 'Mesaj yok.',
    'tap_explain': 'Açıklamak için dokun',
    'explain_ai': 'Asistan ile Açıkla',
    'ai_error': 'Asistan şu anda bu kelimeyi açıklayamadı.',
    'explain_more': 'Daha fazla detay için \'Açıkla\'ya tekrar tıklayın.',
    'ai_analyzing': 'Cevabınız analiz ediliyor...',
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
    // Admin Student Panel
    'student_login_hint': 'Öğrenci numaranız ve şifrenizle giriş yapın',
    'admin.add_student': 'Öğrenci Ekle',
    'admin.set_password': 'Şifre Belirle',
    'admin.enter_new_password_for': '{name} için yeni şifre belirleyin:',
    'admin.enter_student_number': 'Öğrenci numarasını girin:',
    'admin.enter_student_name': '#{number} için ad soyad girin:',
    'admin.enter_student_pwd': '{name} için şifre belirleyin:',
    'admin.password_set_success': 'Şifre başarıyla güncellendi.',
    'admin.student_created_success': 'Öğrenci hesabı başarıyla oluşturuldu.',
    'admin.all_students': 'Tüm Öğrenciler',
    'admin.reset_all_students': 'Tüm Öğrencileri Sıfırla',
    'admin.reset_students_confirm': 'Bu işlem TÜM sınıflardaki TÜM öğrenci hesaplarını ve verilerini silecektir. Bu işlem geri alınamaz.',
    'admin.reset_students_type': 'Onaylamak için RESET ALL STUDENTS yazın:',
    'admin.no_students': 'Öğrenci hesabı bulunamadı.',
    'admin.student_name': 'İsim',
    'admin.student_id': 'Numara / E-posta',
    'admin.enrolled_in': 'Kayıtlı Sınıf',
    'admin.responses': 'Yanıtlar',
    'admin.status': 'Durum',
    'admin.action': 'İşlem',
    'admin.remove': 'Kaldır',
    'admin.active': 'Aktif',
    'admin.pending': 'Bekliyor',
    'admin.inactive': 'İnaktif',
    'admin.students_removed': '{count} öğrenci hesabı silindi.',
    'admin.reset_pin': 'PIN Sıfırla',
    'admin.reset_progress': 'İlerlemeyi Sıfırla',
    'confirm.reset_pin_title': 'Öğrenci PIN\'ini Sıfırla',
    'confirm.reset_pin_msg': '{name} isimli öğrencinin PIN kodunu sıfırlamak istediğinize emin misiniz? Bir sonraki girişlerinde yeni bir PIN belirlemeleri istenecektir.',
    'confirm.reset_progress_title': 'Öğrenci İlerlemesini Sıfırla',
    'confirm.reset_progress_msg': '{name} isimli öğrencinin TÜM sınav ve ödev geçmişini silmek istediğinize emin misiniz? Bu işlem geri alınamaz.',
    'alert.pin_reset_success': 'Öğrenci PIN\'i sıfırlandı.',
    'alert.progress_reset_success': 'Öğrenci ilerlemesi silindi.',
    'student.pin_must_be_4': 'PIN tam olarak 4 rakam olmalıdır',
    'class.stop_build': 'Oluşturmayı Durdur',
    'class.confirm_stop_build': 'Ders materyali oluşturmayı durdurmak istediğinize emin misiniz? Arka plan işlemi sonlandırılacaktır.',
    'class.build_stopped': 'Ders üretimi durduruldu.',
    'architect.busy': 'Mimar dersleri inşa ediyor...',
    'stage.starting': 'BAŞLATILIYOR',
    'stage.analyzing': 'ANALİZ EDİLİYOR',
    'stage.structuring': 'MÜFREDAT',
    'stage.enriching': 'DERSLER',
    'stage.finalizing': 'TAMAMLANIYOR',
    'stage.completed': 'TAMAMLANDI',
  }
};

function t(key, data = {}) {
  try {
    const lang = currentLang || localStorage.getItem('aula_lang') || 'tr';
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

function translateBuildStage(stage) {
  if (!stage) return '';
  const s = String(stage).toLowerCase();
  const stages = {
    'starting': { tr: 'BAŞLATILIYOR', en: 'STARTING' },
    'analyzing': { tr: 'ANALİZ EDİLİYOR', en: 'ANALYZING' },
    'structuring': { tr: 'MÜFREDAT', en: 'STRUCTURING' },
    'enriching': { tr: 'DERSLER', en: 'LESSONS' },
    'finalizing': { tr: 'TAMAMLANIYOR', en: 'FINALIZING' },
    'completed': { tr: 'TAMAMLANDI', en: 'COMPLETED' },
    'failed': { tr: 'HATA', en: 'FAILED' },
    'timeout': { tr: 'ZAMAN AŞIMI', en: 'TIMEOUT' },
    'stopped': { tr: 'DURDURULDU', en: 'STOPPED' },
    'updating': { tr: 'GÜNCELLENİYOR', en: 'UPDATING' }
  };
  const lang = currentLang || localStorage.getItem('aula_lang') || 'tr';
  return (stages[s] && stages[s][lang]) || stage.toUpperCase();
}

function translateBuildMessage(msg) {
  if (!msg) return t('gen.building') || 'Building...';
  const lang = currentLang || localStorage.getItem('aula_lang') || 'tr';

  const mCount = msg.match(/(?:Dersler üretilmeye başlandı|Generating lesson materials|Ders içerikleri hazırlanıyor)\s*\((\d+)(?:\/(\d+))?(?:\s*ders)?\)/i);
  if (mCount) {
    const done = mCount[1];
    const total = mCount[2];
    if (total) {
      return lang === 'tr' ? `Ders içerikleri hazırlanıyor (${done}/${total})...` : `Generating lesson materials (${done}/${total})...`;
    }
    return lang === 'tr' ? `Dersler üretilmeye başlandı (${done} ders)...` : `Generating lessons (${done} lessons)...`;
  }

  const mTopic = msg.match(/(?:Ders üretiliyor|Generating lesson):\s*(.+)/i);
  if (mTopic) {
    const title = mTopic[1];
    return lang === 'tr' ? `Ders üretiliyor: ${title}` : `Generating lesson: ${title}`;
  }

  const dict = {
    'Classroom is ready!': { tr: 'Sınıf hazır!', en: 'Classroom is ready!' },
    'Starting lesson rebuild...': { tr: 'Dersler yeniden oluşturuluyor...', en: 'Starting lesson rebuild...' },
    'Starting build process...': { tr: 'Oluşturma işlemi başlatılıyor...', en: 'Starting build process...' },
    'Analyzing syllabus and chapters...': { tr: 'Ders programı analiz ediliyor...', en: 'Analyzing syllabus and chapters...' },
    'Analyzing textbook syllabus...': { tr: 'Ders kitabı analiz ediliyor...', en: 'Analyzing textbook syllabus...' },
    'Ders programı analiz ediliyor...': { tr: 'Ders programı analiz ediliyor...', en: 'Analyzing syllabus and chapters...' },
    'Structuring chapters and topics...': { tr: 'Müfredat yapısı oluşturuluyor...', en: 'Structuring chapters and topics...' },
    'Structuring course chapters and topics...': { tr: 'Müfredat yapısı oluşturuluyor...', en: 'Structuring course chapters and topics...' },
    'Müfredat yapısı oluşturuluyor...': { tr: 'Müfredat yapısı oluşturuluyor...', en: 'Structuring chapters and topics...' },
    'Ders içerikleri hazırlanıyor...': { tr: 'Ders içerikleri hazırlanıyor...', en: 'Preparing lesson materials...' },
    'Curriculum ready. Preparing lesson generation...': { tr: 'Müfredat hazır. Ders içerikleri hazırlanıyor...', en: 'Curriculum ready. Preparing lesson generation...' },
    'Finalizing bilingual translations...': { tr: 'İki dilli çeviriler tamamlanıyor...', en: 'Finalizing bilingual translations...' },
    'Build timed out. Please click Force Restart.': { tr: 'İşlem zaman aşımına uğradı. Lütfen Yeniden Başlat\'a tıklayın.', en: 'Build timed out. Please click Force Restart.' },
    'Ders üretimi kullanıcı tarafından durduruldu.': { tr: 'Ders üretimi kullanıcı tarafından durduruldu.', en: 'Lesson generation stopped by user.' },
    'Build interrupted by server restart': { tr: 'Sunucu yeniden başlatıldığı için işlem kesildi.', en: 'Build interrupted by server restart.' },
    'Building classroom content...': { tr: 'Sınıf içeriği hazırlanıyor...', en: 'Building classroom content...' },
    'Your content is being built from the textbook...': { tr: 'Ders içeriğiniz kitaptan hazırlanıyor...', en: 'Your content is being built from the textbook...' },
    'The Architect is busy...': { tr: 'Mimar dersleri inşa ediyor...', en: 'The Architect is busy...' }
  };

  if (dict[msg] && dict[msg][lang]) return dict[msg][lang];
  return msg;
}

function applyTranslations(root = document) {
  const rootEl = root || document;
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

  rootEl.querySelectorAll('[data-i18n]').forEach(el => {
    try {
      const key = el.getAttribute('data-i18n');
      const dataStr = el.getAttribute('data-i18n-data');
      let data = {};
      try { if (dataStr) data = JSON.parse(dataStr); } catch (e) { }

      const translation = t(key, data);

      // Safety: Don't overwrite buttons that are currently in generating/loading state
      if (el.tagName === 'BUTTON' && (
        el.disabled || 
        el.getAttribute('data-generating') === 'true' ||
        el.querySelector('.spinner-small') || 
        (el.innerHTML && el.innerHTML.includes('spinner'))
      )) return;

      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = translation;
      } else {
        el.textContent = translation;
      }
    } catch (e) { console.error('Loop error:', e); }
  });

  rootEl.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    try { el.placeholder = t(el.getAttribute('data-i18n-placeholder')); } catch (e) { }
  });

  rootEl.querySelectorAll('[data-i18n-title]').forEach(el => {
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
    langBtn.textContent = currentLang === 'en' ? 'EN' : 'TR';
  }
  const studentLangBtn = document.getElementById('student-lang-btn');
  if (studentLangBtn) {
    studentLangBtn.textContent = currentLang === 'en' ? 'EN' : 'TR';
  }
  const sidebarLangLabel = document.getElementById('sidebar-lang-label');
  if (sidebarLangLabel) {
    sidebarLangLabel.textContent = currentLang === 'en' ? 'EN' : 'TR';
  }

  // Photo 1: Curriculum Subtitle (Course Name — Content Map / İçerik Haritası)
  const subtitleEl = document.getElementById('curriculum-subtitle');
  if (subtitleEl && currentCourse) {
    const cName = translateCourseName(currentCourse.name, currentLang);
    subtitleEl.textContent = `${cName} — ${t('Content Map')}`;
  }

  // Messaging chat-sender headers
  rootEl.querySelectorAll('.chat-sender').forEach(el => {
    el.textContent = t('Lecturer');
  });

  // Dynamic Quiz and Assignment Cards in DOM
  rootEl.querySelectorAll('.quiz-item-title').forEach(el => {
    const raw = el.getAttribute('data-raw-title');
    if (raw) el.textContent = translateQuizTitle(raw, currentLang);
  });
  rootEl.querySelectorAll('.quiz-item-date').forEach(el => {
    const d = el.getAttribute('data-created-at');
    if (d) el.textContent = new Date(d).toLocaleDateString(currentLang === 'tr' ? 'tr-TR' : 'en-US');
  });
  rootEl.querySelectorAll('.assignment-item-title').forEach(el => {
    const raw = el.getAttribute('data-raw-title');
    if (raw) el.textContent = translateQuizTitle(raw, currentLang);
  });
  rootEl.querySelectorAll('.assignment-item-date').forEach(el => {
    const d = el.getAttribute('data-created-at');
    if (d) el.textContent = new Date(d).toLocaleDateString(currentLang === 'tr' ? 'tr-TR' : 'en-US');
  });

  if (_lastReportData && document.getElementById('tab-reports')?.classList.contains('active')) {
    renderReport(_lastReportData);
  }

  // Refresh dynamic components that don't use simple data-i18n
  if (document.getElementById('ai-architect-modal') && !document.getElementById('ai-architect-modal').classList.contains('hidden')) {
    renderAiLanguages();
  }

  if (curriculum && Array.isArray(curriculum) && curriculum.length > 0) {
    populateSelects();
    if (document.getElementById('curriculum-tree')) renderCurriculum();
    if (document.getElementById('ai-book-toc') || document.getElementById('s-ai-book-toc')) renderStudyBook();
    if (currentUser && currentUser.role === 'student') {
      if (_lastStudentHomeData) renderStudentHome(_lastStudentHomeData);
      loadStudentPractice();
    }
  }
}

function toggleLanguage() {
  // 1. Freeze dimensions to eliminate DOM height collapse, scroll jumping, and visual vibration
  const docEl = document.documentElement;
  const currentScrollY = window.scrollY || window.pageYOffset || 0;
  const currentScrollX = window.scrollX || window.pageXOffset || 0;
  const savedScroll = {
    windowX: currentScrollX,
    windowY: currentScrollY,
    docScrollTop: docEl.scrollTop || document.body.scrollTop || 0,
    studyCard: document.querySelector('.study-card')?.scrollTop || 0,
    studyCardLeft: document.querySelector('.study-card')?.scrollLeft || 0,
    contentArea: document.querySelector('#ai-book-content-area, #s-ai-book-content-area')?.scrollTop || 0,
    main: document.querySelector('main')?.scrollTop || 0,
    activeTab: document.querySelector('.tab-panel.active')?.scrollTop || 0
  };

  const activePanel = document.querySelector('.tab-panel.active');
  const frozenHeight = Math.max(docEl.scrollHeight, document.body.scrollHeight);
  docEl.style.minHeight = frozenHeight + 'px';
  document.body.style.minHeight = frozenHeight + 'px';
  if (activePanel && activePanel.offsetHeight > 0) {
    activePanel.style.minHeight = activePanel.offsetHeight + 'px';
  }

  currentLang = currentLang === 'en' ? 'tr' : 'en';
  localStorage.setItem('aula_lang', currentLang);

  // 1. Update all static and dynamic UI elements immediately
  try { applyTranslations(); } catch (e) { console.warn(e); }

  // 2. Re-render curriculum tree if loaded
  try {
    if (curriculum && document.getElementById('curriculum-tree')) {
      renderCurriculum();
    }
    populateSelects();
  } catch (e) { console.warn(e); }

  // 3. Re-render Study Material book & topic
  try {
    renderStudyBook();
    let lastTopic = localStorage.getItem('aula_last_topic');
    let lastPage = parseInt(localStorage.getItem('aula_last_page') || '0');
    if (!lastTopic && curriculum && curriculum[0] && curriculum[0].topics && curriculum[0].topics[0]) {
      lastTopic = curriculum[0].topics[0].id;
      lastPage = 0;
    }
    if (lastTopic) {
      showStudyTopic(lastTopic, lastPage, { preserveScroll: true });
    }
  } catch (e) { console.warn(e); }

  // 4. Re-render role dashboard synchronously
  try {
    if (currentUser) {
      if (currentUser.role === 'lecturer') {
        renderLecturerSync();
        if (_lastClassroomsData) {
          renderClassroomSelection(_lastClassroomsData);
          if (_lastAdminStudentsData) {
            renderAdminStudentPanelSync(_lastAdminStudentsData);
          } else {
            loadAdminStudentPanel();
          }
        }
      } else {
        renderStudentSync();
        if (!_lastStudentHomeData) renderStudentPortal();
        if (curriculum) loadStudentPractice();
      }
    }
  } catch (e) { console.warn(e); }

  // 5. Explicitly sync Quiz and Assignment lists
  try {
    if (_lastQuizListData) renderQuizList(_lastQuizListData);
    else if (courseId || currentCourse) loadQuizList();
  } catch (e) { console.warn(e); }
  try {
    if (_lastAssignmentListData) renderAssignmentList(_lastAssignmentListData);
    else if (courseId || currentCourse) loadAssignmentList();
  } catch (e) { console.warn(e); }

  // 6. Reports
  try { if (_lastReportData) renderReport(_lastReportData); } catch (e) { console.warn(e); }

  // 7. Practice preview or active student practice if visible (never overwrite during active generation!)
  try {
    const isActGenerating = window._isGeneratingActivities || !!document.querySelector('#activity-progress-bar');
    if (!isActGenerating) {
      const preview = document.getElementById('activity-preview');
      if (preview && !preview.classList.contains('hidden') && _lastActivityData) {
        preview.innerHTML = '<h2 style="margin-bottom:20px">' + (translateCurriculumTitle(_lastActivityData.topic?.title) || '') + '</h2>' + (_lastActivityData.activities || []).map((a, i) => renderActivityCard(a, i, 'preview')).join('');
      }
      const practiceArea = document.getElementById('practice-area');
      if (practiceArea && !practiceArea.classList.contains('hidden') && _lastActivityData) {
        const isStudent = currentUser && currentUser.role === 'student';
        const actSelect = document.getElementById('activity-topic-select');
        const curTid = actSelect ? actSelect.value : null;
        let currentTopic = _lastActivityData.topic || null;
        if (!currentTopic && curTid && (window.curriculum || curriculum)) {
          for (const ch of (window.curriculum || curriculum)) {
            const tp = ch.topics ? ch.topics.find(t => t.id === curTid) : null;
            if (tp) { currentTopic = tp; break; }
          }
        }
        const displayTitle = currentTopic ? (getLocalizedCurriculumTitle(currentTopic, currentLang) || currentTopic.title) : (_lastActivityData.topic?.title || (currentLang === 'tr' ? 'Alıştırma' : 'Practice'));
        const header = `<div class="page-header" style="margin-top:24px; display:flex; justify-content:space-between; align-items:center;"><h2>${displayTitle}</h2><button class="btn btn-outline btn-sm" onclick="${isStudent ? 'cancelPractice()' : "this.closest('#practice-area').classList.add('hidden')"}">${t('close')}</button></div>`;
        practiceArea.innerHTML = header + (_lastActivityData.activities || []).map((a, i) => renderActivityCard(a, i, 'practice-area')).join('');
      }
    }
  } catch (e) { console.warn(e); }

  // 8. Active quiz or assignment if in progress
  try {
    const quizArea = document.getElementById('quiz-taking-area');
    if (quizArea && !quizArea.classList.contains('hidden') && quizArea.dataset.questions) {
      showQuizQuestion(quizArea);
    }
    const assignArea = document.getElementById('assignment-taking-area');
    if (assignArea && !assignArea.classList.contains('hidden') && assignArea.dataset.questions) {
      showAssignmentQuestion(assignArea);
    }
  } catch (e) { console.warn(e); }

  // 9. Re-render active dictionary popup if open
  try {
    const dictPopup = document.getElementById('aula-dict-popup');
    if (dictPopup && dictPopup.style.display !== 'none' && window._lastDictWord && window._lastDictRes) {
      renderDictContent(window._lastDictWord, window._lastDictLang || 'English', window._lastDictRes);
    } else if (dictPopup && dictPopup.style.display !== 'none' && activeDictWord) {
      showDict(activeDictWord, { pageX: parseInt(dictPopup.style.left) || 200, pageY: parseInt(dictPopup.style.top) || 200 });
    }
  } catch (e) { console.warn(e); }

  // 10. Sync the Draft Review modal if open
  try { renderDraftListSync(); } catch (e) { console.warn(e); }

  // 11. Sync student detail modal if open (viewQuiz / viewAssignment)
  try {
    const detailModal = document.getElementById('student-detail-modal');
    if (detailModal && !detailModal.classList.contains('hidden')) {
      if (window._currentViewingQuiz) {
        viewQuiz(window._currentViewingQuiz.id, window._currentViewingQuiz.title);
      } else if (window._currentViewingAssignment) {
        viewAssignment(window._currentViewingAssignment.id, window._currentViewingAssignment.title);
      }
    }
  } catch (e) { console.warn(e); }

  // 12. Synchronous scroll restoration — instant, zero frame jitter
  if (savedScroll.studyCard) {
    const card = document.querySelector('.study-card');
    if (card) {
      card.scrollTop = savedScroll.studyCard;
      card.scrollLeft = savedScroll.studyCardLeft;
    }
  }
  if (savedScroll.contentArea) {
    const ca = document.querySelector('#ai-book-content-area, #s-ai-book-content-area');
    if (ca) ca.scrollTop = savedScroll.contentArea;
  }
  if (savedScroll.main) {
    const main = document.querySelector('main');
    if (main) main.scrollTop = savedScroll.main;
  }
  if (savedScroll.activeTab) {
    const tab = document.querySelector('.tab-panel.active');
    if (tab) tab.scrollTop = savedScroll.activeTab;
  }
  window.scrollTo({
    left: savedScroll.windowX,
    top: savedScroll.windowY || savedScroll.docScrollTop,
    behavior: 'instant'
  });

  // 13. Safely release frozen minHeights after paint
  requestAnimationFrame(() => {
    docEl.style.minHeight = '';
    document.body.style.minHeight = '';
    if (activePanel) activePanel.style.minHeight = '';
  });
}

function renderDraftListSync() {
  const modal = document.getElementById('draft-modal');
  if (modal && !modal.classList.contains('hidden') && window.currentDraft) {
    renderDraftList();
  }
}

function renderLecturerSync() {
  if (!currentUser) return;
  const navUser = document.getElementById('nav-username');
  if (navUser) navUser.textContent = currentUser.name;

  const greetingEl = document.getElementById('overview-greeting');
  if (greetingEl) {
    greetingEl.setAttribute('data-i18n', 'welcomeBack');
    greetingEl.setAttribute('data-i18n-data', JSON.stringify({ name: currentUser.name.split(' ').pop() }));
  }

  try { if (_lastOverviewData) renderOverview(_lastOverviewData); } catch (e) { console.warn(e); }
  try { if (curriculum) renderCurriculum(); } catch (e) { console.warn(e); }
  try { populateSelects(); } catch (e) { console.warn(e); }
  try {
    if (_lastQuizListData) renderQuizList(_lastQuizListData);
    else if (currentCourse || courseId) loadQuizList();
  } catch (e) { console.warn(e); }
  try {
    if (_lastAssignmentListData) renderAssignmentList(_lastAssignmentListData);
    else if (currentCourse || courseId) loadAssignmentList();
  } catch (e) { console.warn(e); }
  try { if (_lastStudentRosterData) renderStudentRoster(_lastStudentRosterData); } catch (e) { console.warn(e); }
}

function renderStudentSync() {
  if (!currentUser) return;
  const navUser = document.getElementById('student-nav-username');
  if (navUser) navUser.textContent = currentUser.name;
  const greeting = document.getElementById('student-greeting');
  if (greeting) greeting.textContent = t('welcomeBack', { name: currentUser.name }) + '!';

  try { renderStudentHome(_lastStudentHomeData || { masteries: [] }); } catch (e) { console.warn(e); }
  try {
    if (_lastQuizListData) renderQuizList(_lastQuizListData);
    else if (currentCourse || courseId) loadQuizList();
  } catch (e) { console.warn(e); }
  try {
    if (_lastAssignmentListData) renderAssignmentList(_lastAssignmentListData);
    else if (currentCourse || courseId) loadAssignmentList();
  } catch (e) { console.warn(e); }
  try { if (_lastStudentHomeData) renderStudentProgress(_lastStudentHomeData); } catch (e) { console.warn(e); }
  try { if (curriculum) loadStudentPractice(); } catch (e) { console.warn(e); }
}

// ── Comprehensive Bidirectional Translation Engine ──

const COURSE_LANG_PAIRS = [
  ['Spanish', 'İspanyolca'],
  ['German', 'Almanca'],
  ['French', 'Fransızca'],
  ['Italian', 'İtalyanca'],
  ['Portuguese', 'Portekizce'],
  ['Russian', 'Rusça'],
  ['Chinese', 'Çince'],
  ['Japanese', 'Japonca'],
  ['Arabic', 'Arapça'],
  ['Turkish', 'Türkçe'],
  ['Dutch', 'Felemenkçe'],
  ['Swedish', 'İsveççe'],
  ['Korean', 'Korece'],
  ['Greek', 'Yunanca'],
  ['English', 'İngilizce']
];

function translateCourseName(name, lang = currentLang) {
  if (!name) return '';
  const trimmed = name.trim();
  for (const [en, tr] of COURSE_LANG_PAIRS) {
    if (trimmed.toLowerCase() === en.toLowerCase() || trimmed.toLowerCase() === tr.toLowerCase()) {
      return lang === 'tr' ? tr : en;
    }
  }
  return name;
}

const BADGE_PAIRS = [
  ['PHONETICS', 'FONETİK'],
  ['GRAMMAR', 'DİLBİLGİSİ'],
  ['VOCABULARY', 'KELİME BİLGİSİ'],
  ['FUNCTIONAL LANGUAGE', 'İŞLEVSEL DİL'],
  ['FUNCTIONAL', 'İŞLEVSEL'],
  ['CULTURAL CONTEXT', 'KÜLTÜREL BAĞLAM'],
  ['CULTURAL', 'KÜLTÜREL'],
  ['COMMUNICATION', 'İLETİŞİM'],
  ['PRONUNCIATION', 'TELAFFUZ'],
  ['EXAMPLES', 'ÖRNEKLER'],
  ['DIALOGUE', 'DİYALOG'],
  ['CONVERSATION', 'SOHBET'],
  ['MCQ', 'ÇOKTAN SEÇMELİ'],
  ['MULTIPLE CHOICE', 'ÇOKTAN SEÇMELİ'],
  ['FILL IN THE BLANK', 'BOŞLUK DOLDURMA'],
  ['FILL_BLANK', 'BOŞLUK DOLDURMA'],
  ['PRACTICE', 'ALIŞTIRMA'],
  ['LISTENING', 'DİNLEME'],
  ['READING', 'OKUMA'],
  ['WRITING', 'YAZMA'],
  ['SPEAKING', 'KONUŞMA'],
  ['FUNCTIONAL_LANGUAGE', 'İŞLEVSEL DİL'],
  ['FUNCTIONAL LANGUAGE', 'İŞLEVSEL DİL']
];

function translateBadge(type, lang = currentLang) {
  if (!type) return '';
  const raw = String(type).trim();
  const normalized = raw.replace(/[_-]+/g, ' ').toUpperCase();
  for (const [en, tr] of BADGE_PAIRS) {
    const enNorm = en.replace(/[_-]+/g, ' ').toUpperCase();
    const trNorm = tr.replace(/[_-]+/g, ' ').toUpperCase();
    if (normalized === enNorm || normalized === trNorm) {
      return lang === 'tr' ? tr : en;
    }
  }
  return raw.replace(/[_-]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function translateDifficulty(diff, lang = currentLang) {
  if (!diff) return '';
  const d = String(diff).toLowerCase();
  if (lang === 'tr') {
    if (d === 'beginner') return 'Başlangıç';
    if (d === 'intermediate') return 'Orta';
    if (d === 'advanced') return 'İleri';
  } else {
    if (d === 'başlangıç' || d === 'baslangic') return 'Beginner';
    if (d === 'orta') return 'Intermediate';
    if (d === 'ileri') return 'Advanced';
  }
  return diff;
}

const CURRICULUM_PAIRS = [
  ["All Topics", "Tüm Konular"],
  ["All topics", "Tüm konular"],
  ["All chapters", "Tüm Konular"],
  ["All Chapters", "Tüm Bölümler"],
  ["All lessons", "Tüm Dersler"],
  ["Essential Vocabulary for Daily Life", "Günlük Yaşam İçin Temel Kelimeler"],
  ["Daily Life", "Günlük Yaşam"],
  ["Everyday Life", "Günlük Yaşam"],
  ["Common Objects at Home", "Evde Yaygın Nesneler"],
  ["Common Objects", "Yaygın Nesneler"],
  ["Objects at Home", "Evdeki Nesneler"],
  ["Food and Drink Words", "Yiyecek ve İçecek Kelimeleri"],
  ["Places in Society", "Toplumdaki Yerler"],
  ["Places in the Community", "Toplumdaki Yerler"],
  ["Places in Community", "Toplumdaki Yerler"],
  ["Alphabet and Foundations", "Alfabe ve Temeller"],
  ["The Alphabet", "Alfabe"],
  ["Vowels and Consonants", "Sesli Harfler ve Sessiz Harfler"],
  ["Pronunciation and Phonetics", "Telaffuz ve Fonetik"],
  ["Greetings and Introductions", "Selamlaşmalar ve Tanıtımlar"],
  ["How to Say Hello and Goodbye", "Merhaba ve Hoşça Kal Deme"],
  ["Introducing Yourself: Basic Phrases", "Kendini Tanıtma: Temel Kalıplar"],
  ["Cultural Nuances in Greetings: A Spanish Perspective", "Selamlaşmalardaki Kültürel İncelikler: İspanyol Perspektifi"],
  ["Numbers and Basic Math", "Sayilar ve Temel Matematik"],
  ["Counting from 1 to 100: Basic Numbers", "1'den 100'e Sayma: Temel Sayılar"],
  ["Using Numbers in Everyday Contexts", "Günlük Yaşamda Sayıları Kullanma"],
  ["Simple Math Operations in Spanish", "İspanyolca Basit Matematik İşlemleri"],
  ["Days, Months, and Time", "Günler, Aylar ve Zaman"],
  ["Days of the Week: A Weekly Routine", "Haftanın Günleri: Haftalık Rutin"],
  ["Months of the Year and Seasons", "Yılın Ayları ve Mevsimler"],
  ["Telling Time: Basic Expressions", "Saati Söyleme: Temel İfadeler"],
  ["Essential Survival Vocabulary", "Temel Hayatta Kalma Kelimeleri"],
  ["At the Airport: Key Phrases and Vocabulary", "Havaalanında: Önemli Kalıplar ve Kelimeler"],
  ["Navigating a Restaurant: Ordering Food", "Restoranda: Yemek Siparişi Verme"],
  ["Shopping Basics: Common Phrases", "Alışveriş Temelleri: Yaygın Kalıplar"],
  ["Describing Yourself and Others", "Kendini ve Başkalarını Tanımlama"],
  ["Talking About Age and Nationality", "Yaş ve Milliyet Hakkında Konuşma"],
  ["Describing Physical Appearance: Adjectives", "Fiziksel Görünüşü Tanımlama: Sıfatlar"],
  ["Expressing Likes and Dislikes: Using 'gustar'", "Beğenileri ve Sevmediklerini Belirtme: 'gustar' Kullanımı"],
  ["Forming Basic Sentences", "Temel Cümleler Oluşturma"],
  ["Constructing Simple Sentences: Subject-Verb Agreement", "Basit Cümleler Oluşturma: Özne-Yüklem Uyumu"],
  ["Using Common Verbs in Present Tense", "Geniş Zamanda Yaygın Fiilleri Kullanma"],
  ["Asking Questions: Wh- Questions", "Soru Sorma: Soru Kalıpları"],
  ["Daily Activities and Routines", "Günlük Aktiviteler ve Rutinler"],
  ["Talking About Your Day: Daily Routines", "Gününüz Hakkında Konuşma: Günlük Rutinler"],
  ["Using Time Expressions with Activities", "Aktivitelerle Zaman İfadelerini Kullanma"],
  ["Cultural Context: Spanish Daily Life and Routines", "Kültürel Bağlam: İspanya'da Günlük Yaşam ve Rutinler"],
  ["Family and Relationships", "Aile ve İlişkiler"],
  ["Introducing Family Members: Vocabulary", "Aile Üyelerini Tanıtma: Kelime Bilgisi"],
  ["Describing Relationships: Simple Phrases", "İlişkileri Tanımlama: Basit Kalıplar"],
  ["Cultural Insights: The Importance of Family in Spanish-speaking Cultures", "Kültürel Bakış: İspanyolca Konuşulan Kültürlerde Ailenin Önemi"],
  ["Hobbies and Interests", "Hobiler ve İlgi Alanları"],
  ["Discussing Hobbies: Common Activities", "Hobiler Hakkında Konuşma: Yaygın Aktiviteler"],
  ["Expressing What You Like to Do: Sentence Structures", "Neler Yapmaktan Hoşlandığını Belirtme: Cümle Yapıları"],
  ["Cultural Perspectives on Leisure Activities in Spain and Latin America", "İspanya ve Latin Amerika'da Boş Zaman Aktivitelerine Kültürel Bakış"],
  ["Everyday Routines", "Günlük Rutinler"],
  ["Exploring the Past", "Geçmişi Keşfetmek"],
  ["Describing Your Surroundings", "Çevrenizi Tanımlama"],
  ["Social Exchanges and Interactions", "Sosyal İletişim ve Etkileşimler"],
  ["Shopping Essentials", "Alışveriş Esasları"],
  ["Workplace Communication", "İş Yeri İletişimi"],
  ["Cultural Insights", "Kültürel Bilgiler"],
  ["Traveling in Greece", "Yunanistan'da Seyahat"],
  ["Describing Daily Activities", "Günlük Aktiviteleri Tanımlama"],
  ["Telling Time and Scheduling", "Zamanı Söyleme ve Planlama"],
  ["Expressing Frequency and Habits", "Sıklık ve Alışkanlıkları Belirtme"],
  ["Introduction to the Simple Past Tense", "Geçmiş Zamana Giriş"],
  ["Narrating Past Events in Context", "Geçmiş Olayları Bağlamında Anlatma"],
  ["Common Verbs in the Past Tense", "Geçmiş Zamanda Yaygın Fiiller"],
  ["Talking About Your Home", "Eviniz Hakkında Konuşma"],
  ["Describing Places and Locations", "Yerleri ve Konumları Tanımlama"],
  ["Using Prepositions of Place", "Yer Edatlarını Kullanma"],
  ["Making Small Talk", "Kısa Sohbetler Yapma"],
  ["Polite Requests and Offers", "Kibar İstekler ve Teklifler"],
  ["Expressing Likes and Dislikes", "Beğenileri ve Sevmediklerini Belirtme"],
  ["Navigating a Grocery Store", "Markette Alışveriş Yapma"],
  ["Asking for Prices and Discounts", "Fiyat ve İndirim Sorma"],
  ["Making Purchases and Returns", "Satın Alma ve İadeler"],
  ["Talking About Your Job", "İşiniz Hakkında Konuşma"],
  ["Describing Work Tasks and Responsibilities", "İş Görevlerini ve Sorumlulukları Tanımlama"],
  ["Interacting with Colleagues and Clients", "İş Arkadaşları ve Müşterilerle İletişim"],
  ["Understanding Greek Customs and Etiquette", "Yunan Gelenek ve Görgü Kurallarını Anlama"],
  ["Celebrations and Traditions in Greece", "Yunanistan'da Kutlamalar ve Gelenekler"],
  ["Regional Dialects and Variations", "Bölgesel Lehçeler ve Farklılıklar"],
  ["Asking for Directions", "Yol Tarifi Sorma"],
  ["Using Public Transportation", "Toplu Taşımayı Kullanma"],
  ["Booking Accommodations and Services", "Konaklama ve Hizmet Rezervasyonu"],
  ["Alfabeto Master List", "Alfabe Ana Listesi"],
  ["Phonetic Sounds of the Alphabet", "Alfabenin Fonetik Sesleri"],
  ["Using the Alphabet in Context", "Alfabeyi Bağlam İçinde Kullanma"],
  ["Quick Check", "Hızlı Kontrol"],
  ["Practical Usage", "Pratik Kullanım"],
  ["Vocabulary Cheat Sheet", "Kelime İpucu Listesi"],
  ["Grammar & Key Rules", "Dilbilgisi ve Temel Kurallar"],
  ["Describing Your Environment", "Çevrenizi Tanımlamak"],
  ["Social Interactions and Small Talk", "Sosyal Etkileşimler ve Küçük Sohbet"],
  ["Exploring the Past: Introduction to Past Tenses", "Geçmişi Keşfetmek: Geçmiş Zamanlara Giriş"],
  ["Shopping Scenarios", "Alışveriş Senaryoları"],
  ["Workplace Basics", "İş Yeri Temelleri"],
  ["Traveling in Spanish-Speaking Countries", "İspanyolca Konuşan Ülkelerde Seyahat"],
  ["Culinary Adventures", "Gastronomik Maceralar"],
  ["Morning Rituals and Daily Activities", "Sabah Ritüelleri ve Günlük Aktiviteler"],
  ["Using Reflexive Verbs in Daily Contexts", "Günlük Bağlamlarda Refleksif Fiiller Kullanmak"],
  ["Common Expressions for Daily Routines", "Günlük Rutinler için Yaygın İfadeler"],
  ["Adjectives to Describe Your Home", "Evinizi Tanımlamak İçin Sıfatlar"],
  ["Prepositions of Place: Where Things Are", "Yer Prepozisyonları: Eşyaların Nerede Olduğu"],
  ["Talking About Your Neighborhood", "Mahalleniz Hakkında Konuşmak"],
  ["Engaging in Simple Conversations", "Basit Konuşmalara Katılma"],
  ["Asking and Answering Personal Questions", "Kişisel Sorular Sorma ve Cevaplama"],
  ["Cultural Nuances in Greetings", "Selamlaşmalardaki Kültürel İncelikler"],
  ["Understanding the Preterite Tense", "Geçmiş Zamanı Anlamak"],
  ["Using the Imperfect Tense for Background Descriptions", "Arka Plan Tanımlamaları için Geçmiş Zaman Kullanımı"],
  ["Simple Narratives: Telling a Story from the Past", "Basit Anlatılar: Geçmişten Bir Hikaye Anlatmak"],
  ["At the Market: Buying Food and Goods", "Pazarda: Gıda ve Eşya Satın Alma"],
  ["Expressing Preferences and Needs", "Tercihleri ve İhtiyaçları İfade Etmek"],
  ["Understanding Prices and Bargaining", "Fiyatları Anlama ve Pazarlık"],
  ["Describing Your Job and Responsibilities", "İşinizi ve Sorumluluklarınızı Tanımlama"],
  ["Common Workplace Interactions", "Yaygın İş Yeri Etkileşimleri"],
  ["Using the Future Tense: Discussing Plans", "Gelecek Zaman Kullanımı: Planları Tartışma"],
  ["Asking for Directions and Transportation", "Yol Tarifi ve Ulaşım İsteme"],
  ["Describing Travel Experiences", "Seyahat Deneyimlerini Tanımlama"],
  ["Cultural Etiquette When Traveling", "Seyahat Ederken Kültürel Görgü Kuralları"],
  ["Talking About Food Preferences and Dietary Restrictions", "Yiyecek Tercihleri ve Diyet Kısıtlamaları Hakkında Konuşmak"],
  ["Ordering at a Restaurant: Key Phrases", "Bir Restoranda Sipariş Verme: Anahtar İfadeler"],
  ["Cultural Insights into Spanish Cuisine", "İspanyol Mutfağına Kültürel Bakışlar"],
  ["The Alphabet and Foundations", "Alfabe ve Temeller"],
  ["Formal and Informal Greetings", "Resmi ve Gayriresmi Selamlaşmalar"],
  ["Introducing Yourself and Others", "Kendini ve Başkalarını Tanıtma"],
  ["Asking and Answering Basic Questions", "Temel Sorular Sorma ve Cevaplama"],
  ["Numbers and Basic Quantities", "Sayılara ve Temel Miktarlara"],
  ["Numbers and Quantities", "Sayılar ve Miktarlar"],
  ["Counting from 0 to 100", "0'dan 100'e Sayma"],
  ["Counting from 1 to 100", "1'den 100'e Sayma"],
  ["Using Numbers in Daily Life: Age, Phone Numbers, and Prices", "Günlük Yaşamda Sayıları Kullanma: Yaş, Telefon Numaraları ve Fiyatlar"],
  ["Basic Math Operations: Addition and Subtraction", "Basit Matematik İşlemleri: Toplama ve Çıkarma"],
  ["Days, Months, and Basic Time Management", "Günler, Aylar ve Temel Zaman Yönetimi"],
  ["The Days of the Week: Planning Your Schedule", "Haftanın Günleri: Programınızı Planlama"],
  ["The Days of the Week: Planning and Routines", "Haftanın Günleri: Planlama ve Rutinler"],
  ["The Days of the Week: Planning Activities", "Haftanın Günleri: Aktiviteleri Planlama"],
  ["The Days of the Week", "Haftanın Günleri"],
  ["Months of the Year and the Four Seasons", "Yılın Ayları ve Dört Mevsim"],
  ["Telling Time and Daily Schedules", "Saati Söyleme ve Günlük Planlar"],
  ["Survival Vocabulary", "Hayatta Kalma Kelimeleri"],
  ["Ordering Food and Drinks", "Yiyecek ve İçecek Siparişi Verme"],
  ["Describing People: Personality and Physical Appearance", "İnsanları Tanımlama: Kişilik ve Fiziksel Görünüş"],
  ["Describing Physical Appearance", "Fiziksel Görünüşü Tanımlama"],
  ["Subject Pronouns and Basic Sentence Structure", "Özne Zamirleri ve Temel Cümle Yapısı"],
  ["Reflexive Verbs and Daily Routine", "Dönüşlü Fiiller ve Günlük Rutin"],
  ["Introducing Family Members", "Aile Üyelerini Tanıtma"],
  ["Saying Hello: Formal vs. Informal Greetings", "Selamlaşma: Resmi ve Samimi Selamlaşmalar"],
  ["Saying Hello", "Selamlaşma"],
  ["Formal vs. Informal Greetings", "Resmi ve Samimi Selamlaşmalar"],
  ["Formal vs Informal Greetings", "Resmi ve Samimi Selamlaşmalar"],
  ["Polite Farewells and Their Contexts", "Kibar Vedalaşmalar ve Bağlamları"],
  ["Polite Farewells", "Kibar Vedalaşmalar"],
  ["Numbers and Basic Counting", "Sayılar ve Temel Sayma"],
  ["NUMBERS AND BASIC COUNTING", "Sayılar ve Temel Sayma"],
  ["Building Blocks of Numbers", "Sayıların Temel Yapı Taşları"],
  ["Building Blocks", "Temel Yapı Taşları"],
  ["Using Numbers in Everyday Situations: Prices and Time", "Sayıları Günlük Durumlarda Kullanma: Fiyatlar ve Zaman"],
  ["Using Numbers in Everyday Situations", "Sayıları Günlük Durumlarda Kullanma"],
  ["Prices and Time", "Fiyatlar ve Zaman"],
  ["Basic Math Operations in Spanish", "İspanyolcada Temel Matematik İşlemleri"],
  ["Basic Math Operations", "Temel Matematik İşlemleri"],
  ["Personal Information and Descriptive Basics", "Kişisel Bilgiler ve Temel Tanımlamalar"],
  ["PERSONAL INFORMATION AND DESCRIPTIVE BASICS", "Kişisel Bilgiler ve Temel Tanımlamalar"],
  ["Asking and Answering Questions About Yourself", "Kendiniz Hakkında Soru Sorma ve Cevaplama"],
  ["Asking and Answering Questions", "Soru Sorma ve Cevaplama"],
  ["Describing Yourself: Age, Nationality, and Occupation", "Kendini Tanımlama: Yaş, Milliyet ve Meslek"],
  ["Describing Yourself", "Kendini Tanımlama"],
  ["Age, Nationality, and Occupation", "Yaş, Milliyet ve Meslek"],
  ["Talking About Your Family: Basic Vocabulary and Structures", "Aileniz Hakkında Konuşma: Temel Kelimeler ve Yapılar"],
  ["Talking About Your Family", "Aileniz Hakkında Konuşma"],
  ["Basic Vocabulary and Structures", "Temel Kelimeler ve Yapılar"],
  ["Essential Greetings and Introductions", "Temel Selamlaşmalar ve Tanıtımlar"],
  ["Cardinal Numbers: Counting from One to Ten", "Asıl Sayılar: Birden Ona Sayma"],
  ["Cardinal Numbers", "Asıl Sayılar"],
  ["Ordinal Numbers: Describing Order and Sequence", "Sıra Sayıları: Sıra ve Dizilimi Tanımlama"],
  ["Ordinal Numbers", "Sıra Sayıları"],
  ["Describing Your Daily Life", "Günlük Hayatınızı Tanımlama"],
  ["Basic Present Tense: Talking About Routines", "Temel Geniş Zaman: Rutinler Hakkında Konuşma"],
  ["Basic Present Tense", "Temel Geniş Zaman"],
  ["Daily Activities Vocabulary: Common Verbs and Expressions", "Günlük Aktiviteler Kelimeleri: Yaygın Fiiller ve İfadeler"],
  ["Constructing Simple Sentences: Subject-Object-Verb Structure", "Basit Cümleler Kurma: Özne-Nesne-Yüklem Yapısı"],
  ["Survival Vocabulary for Travelers", "Gezginler İçin Hayatta Kalma Kelimeleri"],
  ["Essential Phrases for Navigating Public Transport", "Toplu Taşımada Yol Bulma İçin Temel İfadeler"],
  ["Asking for Directions: Key Questions and Responses", "Yol Tarifi Sorma: Temel Sorular ve Yanıtlar"],
  ["Dining Out: Ordering Food and Understanding Menus", "Dışarıda Yemek Yeme: Yemek Siparişi ve Menüleri Anlama"],
  ["Dining Out", "Dışarıda Yemek Yeme"],
  ["Ordering Food and Understanding Menus", "Yemek Siparişi ve Menüleri Anlama"],
  ["Family and Personal Information", "Aile ve Kişisel Bilgiler"],
  ["Family Vocabulary: Identifying Family Members", "Aile Kelimeleri: Aile Üyelerini Tanıma"],
  ["Describing Relationships: Simple Adjectives and Phrases", "İlişkileri Tanımlama: Basit Sıfatlar ve İfadeler"],
  ["Sharing Personal Information: Where You Live and Work", "Kişisel Bilgi Paylaşma: Nerede Yaşadığınız ve Çalıştığınız"],
  ["Exploring Common Places", "Yaygın Yerleri Keşfetme"],
  ["Identifying Places in Your Community: Vocabulary and Usage", "Topluluğunuzdaki Yerleri Tanıma: Kelimeler ve Kullanım"],
  ["Simple Conversations About Places: Asking and Answering Questions", "Yerler Hakkında Basit Konuşmalar: Soru Sorma ve Cevaplama"],
  ["Common Hobbies and Interests Vocabulary", "Yaygın Hobiler ve İlgi Alanları Kelimeleri"],
  ["Constructing Preference Statements: I Like, I Don't Like", "Tercih İfadeleri Kurma: Severim, Sevmem"],
  ["Engaging in Small Talk: Discussing Interests with Others", "Kısa Sohbet Yapma: Başkalarıyla İlgi Alanlarını Tartışma"],
  ["Weather and Seasons", "Hava Durumu ve Mevsimler"],
  ["Describing the Weather: Common Terms and Expressions", "Hava Durumunu Tanımlama: Yaygın Terimler ve İfadeler"],
  ["Talking About Seasons: Activities and Preferences", "Mevsimler Hakkında Konuşma: Aktiviteler ve Tercihler"],
  ["Basic Shopping Skills", "Temel Alışveriş Becerileri"],
  ["Shopping Vocabulary: Common Items and Shopping Expressions", "Alışveriş Kelimeleri: Yaygın Eşyalar ve İfadeler"],
  ["Asking About Prices: Useful Questions and Responses", "Fiyatları Sorma: Yararlı Sorular ve Yanıtlar"],
  ["Everyday Survival Vocabulary", "Günlük Hayatta Kalma Kelimeleri"],
  ["EVERYDAY SURVIVAL VOCABULARY", "Günlük Hayatta Kalma Kelimeleri"],
  ["Navigating Public Places: Directions and Transportation", "Kamusal Alanlarda Yol Bulma: Yol Tarifi ve Ulaşım"],
  ["Navigating Public Places", "Kamusal Alanlarda Yol Bulma"],
  ["Directions and Transportation", "Yol Tarifi ve Ulaşım"],
  ["Essential Phrases for Shopping and Eating Out", "Alışveriş ve Dışarıda Yemek İçin Temel İfadeler"],
  ["Shopping and Eating Out", "Alışveriş ve Dışarıda Yemek"],
  ["Eating Out", "Dışarıda Yemek"],
  ["Emergency Situations: Key Vocabulary and Phrases", "Acil Durumlar: Temel Kelimeler ve İfadeler"],
  ["Emergency Situations", "Acil Durumlar"],
  ["Key Vocabulary and Phrases", "Temel Kelimeler ve İfadeler"],
  ["Basic Present Tense Conjugation", "Temel Geniş Zaman Çekimi"],
  ["BASIC PRESENT TENSE CONJUGATION", "Temel Geniş Zaman Çekimi"],
  ["Present Tense Conjugation", "Geniş Zaman Çekimi"],
  ["Basic Present Tense", "Temel Geniş Zaman"],
  ["Introduction to Regular Verbs: -ar, -er, -ir", "Düzenli Fiillere Giriş: -ar, -er, -ir"],
  ["Introduction to Regular Verbs", "Düzenli Fiillere Giriş"],
  ["Regular Verbs", "Düzenli Fiiller"],
  ["Using Common Irregular Verbs in Present Tense", "Geniş Zamanda Yaygın Düzensiz Fiillerin Kullanımı"],
  ["Using Common Irregular Verbs", "Yaygın Düzensiz Fiillerin Kullanımı"],
  ["Common Irregular Verbs in Present Tense", "Geniş Zamanda Yaygın Düzensiz Fiiller"],
  ["Common Irregular Verbs", "Yaygın Düzensiz Fiiller"],
  ["Stem-Changing Verbs in the Present Tense", "Geniş Zamanda Kök Değiştiren Fiiller"],
  ["Stem-Changing Verbs", "Kök Değiştiren Fiiller"],
  ["Forming Questions and Negations", "Soru ve Olumsuz Cümle Kurma"],
  ["Daily Activities and Routines", "Günlük Aktiviteler ve Rutinler"],
  ["Daily Routines: Reflexive Verbs and Time Expressions", "Günlük Rutinler: Dönüşlü Fiiller ve Zaman İfadeleri"],
  ["Daily Routines", "Günlük Rutinler"],
  ["Talking About Your Daily Routine", "Günlük Rutininiz Hakkında Konuşma"],
  ["Parts of the Day and Time Expressions", "Günün Bölümleri ve Zaman İfadeleri"],
  ["Parts of the Day", "Günün Bölümleri"],
  ["Time Expressions", "Zaman İfadeleri"],
  ["Food, Dining, and Ordering Meals", "Yiyecek, Yemek ve Sipariş Verme"],
  ["At the Restaurant: Ordering Food and Drinks", "Restoranda: Yiyecek ve İçecek Siparişi"],
  ["Ordering Food and Drinks", "Yiyecek ve İçecek Siparişi Verme"],
  ["Expressing Preferences: Me Gusta and Other Verbs", "Tercihleri İfade Etme: Me Gusta ve Diğer Fiiller"],
  ["Around the Town: Places and Directions", "Şehirde: Yerler ve Yol Tarifi"],
  ["Around the Town", "Şehirde"],
  ["Asking for and Giving Directions", "Yol Tarifi Sorma ve Verme"],
  ["Public Transportation and Getting Around", "Toplu Taşıma ve Şehir İçi Ulaşım"],
  ["Getting Around", "Şehir İçi Ulaşım"],
  ["Weather, Seasons, and Free Time Activities", "Hava Durumu, Mevsimler ve Boş Zaman Aktiviteleri"],
  ["Describing the Weather and Temperature", "Hava Durumu ve Sıcaklığı Tanımlama"],
  ["Free Time Activities and Hobbies", "Boş Zaman Aktiviteleri ve Hobiler"],
  ["Free Time Activities", "Boş Zaman Aktiviteleri"],
  ["Making Plans with 'Ir a' + Infinitive", "'Ir a' + Mastar ile Plan Yapma"],
  ["Shopping, Clothes, and Colors", "Alışveriş, Kıyafetler ve Renkler"],
  ["At the Clothing Store: Colors, Sizes, and Prices", "Giyim Mağazasında: Renkler, Bedenler ve Fiyatlar"],
  ["Health, Body Parts, and Visiting the Doctor", "Sağlık, Vücut Bölümleri ve Doktora Gitme"],
  ["Body Parts and Expressing Pain with 'Doler'", "Vücut Bölümleri ve 'Doler' ile Ağrı İfade Etme"],
  ["Past Tense: Introduction to the Preterite", "Geçmiş Zaman: Preterite Zamanına Giriş"],
  ["Travel, Holidays, and Transportation", "Seyahat, Tatiller ve Ulaşım"],

  // ── V3: AI-generated titles observed on production ──
  ["Constructing Simple Sentences in Present Tense", "Geniş Zamanda Basit Cümleler Kurma"],
  ["Constructing Simple Sentences in the Present Tense", "Geniş Zamanda Basit Cümleler Kurma"],
  ["Constructing Simple Sentences", "Basit Cümleler Kurma"],
  ["Simple Sentences in Present Tense", "Geniş Zamanda Basit Cümleler"],
  ["Asking Questions and Seeking Clarifications", "Soru Sorma ve Açıklama İsteme"],
  ["Asking Questions and Seeking Clarification", "Soru Sorma ve Açıklama İsteme"],
  ["Asking Questions", "Soru Sorma"],
  ["Seeking Clarifications", "Açıklama İsteme"],
  ["Seeking Clarification", "Açıklama İsteme"],
  ["Formulating Yes/No Questions", "Evet/Hayır Soruları Oluşturma"],
  ["Formulating Yes or No Questions", "Evet/Hayır Soruları Oluşturma"],
  ["Formulating Questions", "Soru Cümleleri Oluşturma"],
  ["Question Words", "Soru Kelimeleri"],
  ["Question Words Kullanımı", "Soru Kelimeleri Kullanımı"],
  ["Question Words Kullanımı: Who, What, Where, When, Why", "Soru Kelimeleri Kullanımı: Kim, Ne, Nerede, Ne Zaman, Neden"],
  ["Question Words: Who, What, Where, When, Why", "Soru Kelimeleri: Kim, Ne, Nerede, Ne Zaman, Neden"],
  ["Using Question Words: Who, What, Where, When, Why", "Soru Kelimeleri Kullanımı: Kim, Ne, Nerede, Ne Zaman, Neden"],
  ["Who, What, Where, When, Why", "Kim, Ne, Nerede, Ne Zaman, Neden"],
  ["Polite Ways to Ask for Help or Information", "Yardım veya Bilgi İstemek İçin Nezaket İfadeleri"],
  ["Polite Ways to Ask for Help", "Yardım İstemek İçin Nezaket İfadeleri"],
  ["Polite Expressions", "Nezaket İfadeleri"],
  ["Polite Requests and Expressions", "Nezaket İstekleri ve İfadeleri"],
  ["Cultural Contexts: Spanish-Speaking Countries", "Kültürel Bağlamlar: İspanyolca Konuşulan Ülkeler"],
  ["Cultural Contexts", "Kültürel Bağlamlar"],
  ["Spanish-Speaking Countries", "İspanyolca Konuşulan Ülkeler"],
  ["Spanish-Speaking World", "İspanyolca Konuşulan Dünya"],
  ["The Spanish-Speaking World", "İspanyolca Konuşulan Dünya"],
  ["Geography and Major Cities of the Spanish-Speaking World", "İspanyolca Konuşulan Dünyanın Coğrafyası ve Başlıca Şehirleri"],
  ["Geography and Major Cities", "Coğrafya ve Başlıca Şehirler"],
  ["Major Cities", "Başlıca Şehirler"],
  ["Celebrations and Traditions in Spanish-Speaking Countries", "İspanyolca Konuşulan Ülkelerde Kutlamalar ve Gelenekler"],
  ["Celebrations and Traditions in the Spanish-Speaking World", "İspanyolca Konuşulan Dünyada Kutlamalar ve Gelenekler"],
  ["Celebrations and Traditions in Spain and Latin America", "İspanya ve Latin Amerika'da Kutlamalar ve Gelenekler"],
  ["Celebrations and Traditions", "Kutlamalar ve Gelenekler"],
  ["Traditional Festivals and Holidays", "Geleneksel Festivaller ve Tatiller"],
  ["Festivals and Holidays", "Festivaller ve Tatiller"],
  ["Cultural Insights", "Kültürel İçgörüler"],
  ["Cultural Context", "Kültürel Bağlam"],

  // ── Common AI-generated verb/grammar titles ──
  ["Stem-Changing Verbs", "Kök Değiştiren Fiiller"],
  ["Regular Verbs", "Düzenli Fiiller"],
  ["Irregular Verbs", "Düzensiz Fiiller"],
  ["Common Irregular Verbs", "Yaygın Düzensiz Fiiller"],
  ["Regular and Irregular Verbs", "Düzenli ve Düzensiz Fiiller"],
  ["Subject-Verb Agreement", "Özne-Yüklem Uyumu"],
  ["Verb Conjugation", "Fiil Çekimi"],
  ["Present Tense", "Geniş Zaman"],
  ["Present Tense Conjugation", "Geniş Zaman Çekimi"],
  ["Past Tense", "Geçmiş Zaman"],
  ["Future Tense", "Gelecek Zaman"],
  ["Forming Negative Sentences", "Olumsuz Cümle Kurma"],
  ["Forming Questions", "Soru Cümleleri Kurma"],
  ["Forming Questions and Negations", "Soru ve Olumsuz Cümle Kurma"],
  ["Negation", "Olumsuzluk"],
  ["Negations", "Olumsuz Cümleler"],

  // ── Common AI-generated everyday/situational titles ──
  ["At the Airport", "Havaalanında"],
  ["At the Restaurant", "Restoranda"],
  ["At the Hotel", "Otelde"],
  ["At the Market", "Pazarda"],
  ["At the Doctor", "Doktorda"],
  ["At the Hospital", "Hastanede"],
  ["At the Pharmacy", "Eczanede"],
  ["At the Bank", "Bankada"],
  ["At the Post Office", "Postanede"],
  ["Making Reservations", "Rezervasyon Yapma"],
  ["Making Appointments", "Randevu Alma"],
  ["Asking for Directions", "Yol Tarifi Sorma"],
  ["Giving Directions", "Yol Tarifi Verme"],
  ["Ordering at a Restaurant", "Restoranda Sipariş Verme"],
  ["Shopping for Groceries", "Market Alışverişi"],
  ["Buying Clothes", "Kıyafet Satın Alma"],
  ["Renting an Apartment", "Ev Kiralama"],
  ["Making Phone Calls", "Telefon Konuşmaları"],

  // ── Common AI-generated descriptive/personal titles ──
  ["Describing People", "İnsanları Tanımlama"],
  ["Describing Places", "Yerleri Tanımlama"],
  ["Describing Objects", "Nesneleri Tanımlama"],
  ["Physical Appearance", "Fiziksel Görünüm"],
  ["Personality Traits", "Kişilik Özellikleri"],
  ["Expressing Feelings and Emotions", "Duyguları İfade Etme"],
  ["Feelings and Emotions", "Duygular ve Hisler"],
  ["Expressing Opinions", "Fikir Belirtme"],
  ["Expressing Preferences", "Tercihleri İfade Etme"],
  ["Expressing Agreement and Disagreement", "Katılma ve Katılmama İfade Etme"],
  ["Comparing Things", "Karşılaştırmalar Yapma"],
  ["Comparatives and Superlatives", "Karşılaştırma ve Üstünlük Dereceleri"],

  // ── Common AI-generated misc curriculum titles ──
  ["Review and Practice", "Tekrar ve Pratik"],
  ["Comprehensive Review", "Kapsamlı Tekrar"],
  ["Putting It All Together", "Hepsini Bir Araya Getirme"],
  ["Real-World Application", "Gerçek Dünya Uygulaması"],
  ["Practical Exercises", "Pratik Alıştırmalar"],
  ["Writing Practice", "Yazma Pratiği"],
  ["Reading Comprehension", "Okuduğunu Anlama"],
  ["Listening Practice", "Dinleme Pratiği"],
  ["Conversation Practice", "Konuşma Pratiği"],
  ["Dialogue Practice", "Diyalog Pratiği"],
  ["Role Play Scenarios", "Rol Yapma Senaryoları"]
];

const CURRICULUM_LANG_MAP_TR = {
  spanish: "İspanyolcada",
  english: "İngilizcede",
  german: "Almancada",
  french: "Fransızcada",
  italian: "İtalyancada",
  portuguese: "Portekizcede",
  russian: "Rusçada",
  chinese: "Çincede",
  japanese: "Japoncada",
  korean: "Korecede",
  arabic: "Arapçada",
  turkish: "Türkçede",
  greek: "Yunancada",
  dutch: "Felemenkçede",
  swedish: "İsveççede",
};

const UniversalCurriculumTranslator = {
  LANGUAGES: {
    "german": ["Almanca", "Alman", "Almancada"],
    "spanish": ["İspanyolca", "İspanyol", "İspanyolcada"],
    "french": ["Fransızca", "Fransız", "Fransızcada"],
    "italian": ["İtalyanca", "İtalyan", "İtalyancada"],
    "english": ["İngilizce", "İngiliz", "İngilizcede"],
    "russian": ["Rusça", "Rus", "Rusçada"],
    "chinese": ["Çince", "Çin", "Çincede"],
    "japanese": ["Japonca", "Japon", "Japoncada"],
    "korean": ["Korece", "Kore", "Korecede"],
    "arabic": ["Arapça", "Arap", "Arapçada"],
    "portuguese": ["Portekizce", "Portekiz", "Portekizcede"],
    "dutch": ["Felemenkçe", "Felemenk", "Felemenkçede"],
    "greek": ["Yunanca", "Yunan", "Yunancada"],
    "swedish": ["İsveççe", "İsveç", "İsveççede"],
    "turkish": ["Türkçe", "Türk", "Türkçede"],
  },

  QUOTED_EXPRESSIONS: {
    "who are you": "Sen Kimsin",
    "who are you?": "Sen Kimsin?",
    "what is your name": "Adın Ne",
    "what is your name?": "Adın Ne?",
    "where are you from": "Nerelisin",
    "where are you from?": "Nerelisin?",
    "how are you": "Nasılsın",
    "how are you?": "Nasılsın?",
    "hello": "Merhaba",
    "goodbye": "Hoşça Kal",
    "please": "Lütfen",
    "thank you": "Teşekkür Ederim",
    "yes": "Evet",
    "no": "Hayır",
    "doler": "Doler",
    "gustar": "Gustar",
    "ser": "Ser",
    "estar": "Estar",
    "haben": "Haben",
    "sein": "Sein",
    "avoir": "Avoir",
    "être": "Être",
  },

  PHRASES: {
    "getting acquainted with the german language": "Almanca ile Tanışma",
    "getting acquainted with the spanish language": "İspanyolca ile Tanışma",
    "getting acquainted with the french language": "Fransızca ile Tanışma",
    "getting acquainted with the italian language": "İtalyanca ile Tanışma",
    "getting acquainted with the english language": "İngilizce ile Tanışma",
    "getting acquainted": "Tanışma",
    "basic greetings and farewells": "Temel Selamlaşmalar ve Vedalaşmalar",
    "greetings and farewells": "Selamlaşmalar ve Vedalaşmalar",
    "greetings and introductions": "Selamlaşmalar ve Tanıtımlar",
    "basic greetings": "Temel Selamlaşmalar",
    "farewells": "Vedalaşmalar",
    "saying hello and goodbye": "Merhaba ve Hoşça Kal Deme",
    "polite expressions and requests": "Nazik İfadeler ve İstekler",
    "polite expressions": "Nazik İfadeler",
    "sharing personal information": "Kişisel Bilgileri Paylaşma",
    "personal information": "Kişisel Bilgiler",
    "personal info": "Kişisel Bilgiler",
    "introducing yourself and others": "Kendinizi ve Başkalarını Tanıtmak",
    "introducing yourself": "Kendini Tanıtma",
    "introducing others": "Başkalarını Tanıtma",
    "name, age, and origin": "İsim, Yaş ve Memleket",
    "name, age and origin": "İsim, Yaş ve Memleket",
    "age and origin": "Yaş ve Memleket",
    "name and age": "İsim ve Yaş",
    "numbers and essential quantities": "Sayılar ve Temel Miktarlar",
    "numbers and basic math": "Sayılar ve Temel Matematik",
    "numbers and quantities": "Sayılar ve Miktarlar",
    "essential quantities": "Temel Miktarlar",
    "basic quantities": "Temel Miktarlar",
    "counting and numbers": "Sayma ve Sayılar",
    "telling time": "Zamanı Söyleme",
    "prices and time": "Fiyatlar ve Zaman",
    "days, months, and seasons": "Günler, Aylar ve Mevsimler",
    "days of the week": "Haftanın Günleri",
    "months of the year": "Yılın Ayları",
    "formulating simple questions": "Basit Sorular Oluşturma",
    "formulating questions": "Soru Cümleleri Oluşturma",
    "formulating yes/no questions": "Evet/Hayır Soruları Oluşturma",
    "yes/no and wh- questions": "Evet/Hayır ve Soru Kelimeleri ile Sorular",
    "yes/no questions": "Evet/Hayır Soruları",
    "wh- questions": "Soru Kelimeleri ile Sorular",
    "wh- questions: who, what, where": "Soru Kelimeleri: Kim, Ne, Nerede",
    "wh- questions: who, what, where, when, why": "Soru Kelimeleri: Kim, Ne, Nerede, Ne Zaman, Neden",
    "asking questions: wh- questions": "Soru Sorma: Soru Kelimeleri",
    "asking questions: question words": "Soru Sorma: Soru Kelimeleri",
    "asking questions and seeking clarifications": "Soru Sorma ve Açıklama İsteme",
    "asking questions": "Soru Sorma",
    "seeking clarifications": "Açıklama İsteme",
    "question words": "Soru Kelimeleri",
    "question words: who, what, where": "Soru Kelimeleri: Kim, Ne, Nerede",
    "who, what, where": "Kim, Ne, Nerede",
    "who, what, where, when": "Kim, Ne, Nerede, Ne Zaman",
    "who, what, where, when, why": "Kim, Ne, Nerede, Ne Zaman, Neden",
    "constructing simple sentences": "Basit Cümleler Kurma",
    "simple sentences": "Basit Cümleler",
    "polite ways to ask for help or information": "Yardım veya Bilgi İstemek İçin Nezaket İfadeleri",
    "polite ways to ask for help": "Yardım İstemek İçin Nezaket İfadeleri",
    "ask for help or information": "Yardım veya Bilgi İsteme",
    "asking for help": "Yardım İsteme",
    "polite expressions": "Nezaket İfadeleri",
    "cultural contexts": "Kültürel Bağlamlar",
    "cultural insights": "Kültürel İçgörüler",
    "cultural perspective": "Kültürel Bakış Açısı",
    "cultural perspectives": "Kültürel Bakış Açıları",
    "spanish-speaking countries": "İspanyolca Konuşulan Ülkeler",
    "spanish-speaking world": "İspanyolca Konuşulan Dünya",
    "german-speaking countries": "Almanca Konuşulan Ülkeler",
    "german-speaking world": "Almanca Konuşulan Dünya",
    "french-speaking countries": "Fransızca Konuşulan Ülkeler",
    "geography and major cities": "Coğrafya ve Başlıca Şehirler",
    "celebrations and traditions": "Kutlamalar ve Gelenekler",
    "traditions and customs": "Gelenekler ve Görenekler",
    "festivals and holidays": "Festivaller ve Tatiller",
    "alphabet and foundations": "Alfabe ve Temeller",
    "the alphabet and foundations": "Alfabe ve Temeller",
    "the alphabet": "Alfabe",
    "vowels and consonants": "Sesli ve Sessiz Harfler",
    "pronunciation and phonetics": "Telaffuz ve Fonetik",
    "present tense": "Geniş Zaman",
    "present tense conjugation": "Geniş Zaman Çekimi",
    "past tense": "Geçmiş Zaman",
    "future tense": "Gelecek Zaman",
    "regular verbs": "Düzenli Fiiller",
    "irregular verbs": "Düzensiz Fiiller",
    "common irregular verbs": "Yaygın Düzensiz Fiiller",
    "stem-changing verbs": "Kök Değiştiren Fiiller",
    "reflexive verbs": "Dönüşlü Fiiller",
    "subject-verb agreement": "Özne-Yüklem Uyumu",
    "everyday survival vocabulary": "Günlük Hayatta Kalma Kelimeleri",
    "everyday survival": "Günlük Hayatta Kalma",
    "survival vocabulary": "Hayatta Kalma Kelimeleri",
    "essential vocabulary for traveling": "Seyahat İçin Temel Kelimeler",
    "essential vocabulary for travel": "Seyahat İçin Temel Kelimeler",
    "essential vocabulary for daily life": "Günlük Yaşam İçin Temel Kelimeler",
    "essential vocabulary for everyday life": "Günlük Yaşam İçin Temel Kelimeler",
    "vocabulary for daily life": "Günlük Yaşam İçin Kelimeler",
    "vocabulary for everyday life": "Günlük Yaşam İçin Kelimeler",
    "daily life": "Günlük Yaşam",
    "everyday life": "Günlük Yaşam",
    "daily life and routines": "Günlük Yaşam ve Rutinler",
    "common objects at home": "Evde Yaygın Nesneler",
    "common objects": "Yaygın Nesneler",
    "objects at home": "Evdeki Nesneler",
    "food and drink words": "Yiyecek ve İçecek Kelimeleri",
    "places in society": "Toplumdaki Yerler",
    "places in the community": "Toplumdaki Yerler",
    "places in community": "Toplumdaki Yerler",
    "vocabulary for traveling": "Seyahat İçin Kelimeler",
    "vocabulary for travel": "Seyahat İçin Kelimeler",
    "essential vocabulary": "Temel Kelimeler",
    "navigating public transportation": "Toplu Taşımada Yol Bulma",
    "navigating public transport": "Toplu Taşımada Yol Bulma",
    "public transportation": "Toplu Taşıma",
    "public transport": "Toplu Taşıma",
    "basic food and drink vocabulary": "Temel Yiyecek ve İçecek Kelimeleri",
    "food and drink vocabulary": "Yiyecek ve İçecek Kelimeleri",
    "food and drink": "Yiyecek ve İçecek",
    "basic food and drinks": "Temel Yiyecek ve İçecekler",
    "seeking help: phrases for emergencies": "Yardım İsteme: Acil Durum İfadeleri",
    "seeking help": "Yardım İsteme",
    "phrases for emergencies": "Acil Durum İfadeleri",
    "basic phrases for celebratory situations": "Kutlama Durumları İçin Temel İfadeler",
    "celebratory situations": "Kutlama Durumları",
    "daily routines": "Günlük Rutinler",
    "food and dining": "Yiyecek ve Yemek",
    "shopping essentials": "Alışveriş Temelleri",
    "emergency situations": "Acil Durumlar",
    "directions and transportation": "Yol Tarifi ve Ulaşım",
    "weather and seasons": "Hava Durumu ve Mevsimler",
    "describing yourself and others": "Kendinizi ve Başkalarını Tanımlama",
    "describing yourself": "Kendinizi Tanımlama",
    "describing others": "Başkalarını Tanımlama",
    "basic adjectives for personal description": "Kişisel Tanım İçin Temel Sıfatlar",
    "adjectives for personal description": "Kişisel Tanım İçin Sıfatlar",
    "basic adjectives": "Temel Sıfatlar",
    "personal description": "Kişisel Tanım",
    "personal descriptions": "Kişisel Tanımlar",
    "using 'ser' to describe identity": "'Ser' Kullanarak Kimliği Tanımlama",
    "using ser to describe identity": "'Ser' Kullanarak Kimliği Tanımlama",
    "talking about age and nationality": "Yaş ve Milliyet Hakkında Konuşma",
    "age and nationality": "Yaş ve Milliyet"
  },

  VOCABULARY: {
    "alphabet": "Alfabe",
    "vowels": "Sesli Harfler",
    "consonants": "Sessiz Harfler",
    "pronunciation": "Telaffuz",
    "phonetics": "Fonetik",
    "numbers": "Sayılar",
    "quantities": "Miktarlar",
    "quantity": "Miktar",
    "greetings": "Selamlaşmalar",
    "farewells": "Vedalaşmalar",
    "introductions": "Tanıtımlar",
    "information": "Bilgiler",
    "name": "İsim",
    "age": "Yaş",
    "origin": "Memleket / Köken",
    "nationality": "Milliyet",
    "questions": "Sorular",
    "question": "Soru",
    "answers": "Cevaplar",
    "answer": "Cevap",
    "sentences": "Cümleler",
    "sentence": "Cümle",
    "words": "Kelimeler",
    "word": "Kelime",
    "vocabulary": "Kelime Bilgisi",
    "phrases": "İfadeler",
    "phrase": "İfade",
    "expressions": "İfadeler",
    "expression": "İfade",
    "requests": "İstekler",
    "request": "İstek",
    "description": "Tanım",
    "descriptions": "Tanımlar",
    "identity": "Kimlik",
    "identities": "Kimlikler",
    "survival": "Hayatta Kalma",
    "travel": "Seyahat",
    "traveling": "Seyahat",
    "travelling": "Seyahat",
    "transport": "Ulaşım",
    "transportation": "Ulaşım",
    "basics": "Temeller",
    "foundations": "Temeller",
    "celebratory": "Kutlama",
    "celebration": "Kutlama",
    "celebrations": "Kutlamalar",
    "seeking": "İsteme",
    "others": "Başkaları",
    "yourself": "Kendiniz",
    "grammar": "Dilbilgisi",
    "verbs": "Fiiller",
    "verb": "Fiil",
    "nouns": "İsimler",
    "noun": "İsim",
    "adjectives": "Sıfatlar",
    "adjective": "Sıfat",
    "adverbs": "Zarflar",
    "pronouns": "Zamirler",
    "prepositions": "Edatlar",
    "tenses": "Zamanlar",
    "tense": "Zaman",
    "conjugation": "Çekim",
    "days": "Günler",
    "months": "Aylar",
    "seasons": "Mevsimler",
    "weather": "Hava Durumu",
    "time": "Zaman",
    "prices": "Fiyatlar",
    "price": "Fiyat",
    "family": "Aile",
    "routines": "Rutinler",
    "routine": "Rutin",
    "activities": "Aktiviteler",
    "food": "Yiyecek",
    "drinks": "İçecekler",
    "meals": "Öğünler",
    "restaurant": "Restoran",
    "shopping": "Alışveriş",
    "clothes": "Kıyafetler",
    "clothing": "Giyim",
    "colors": "Renkler",
    "places": "Yerler",
    "cities": "Şehirler",
    "city": "Şehir",
    "countries": "Ülkeler",
    "country": "Ülke",
    "world": "Dünya",
    "geography": "Coğrafya",
    "traditions": "Gelenekler",
    "celebrations": "Kutlamalar",
    "customs": "Görenekler",
    "culture": "Kültür",
    "contexts": "Bağlamlar",
    "context": "Bağlam",
    "health": "Sağlık",
    "doctor": "Doktor",
    "body": "Vücut",
    "emergency": "Acil Durum",
    "emergencies": "Acil Durumlar",
    "directions": "Yol Tarifi",
    "transportation": "Ulaşım",
    "travel": "Seyahat",
    "hotel": "Otel",
    "airport": "Havalimanı",
    "hobbies": "Hobiler",
    "work": "İş",
    "jobs": "Meslekler",
    "basic": "Temel",
    "essential": "Temel",
    "simple": "Basit",
    "common": "Yaygın",
    "regular": "Düzenli",
    "irregular": "Düzensiz",
    "polite": "Nazik",
    "personal": "Kişisel",
    "daily": "Günlük",
    "life": "Yaşam",
    "cultural": "Kültürel",
    "practical": "Pratik",
    "structural": "Yapısal",
    "major": "Başlıca",
    "traditional": "Geleneksel",
    "new": "Yeni",
    "important": "Önemli",
    "useful": "Yararlı",
    "key": "Temel / Anahtar",
    "everyday": "Günlük",
    "general": "Genel",
    "elementary": "Başlangıç",
    "advanced": "İleri",
    "intermediate": "Orta Düzey",
    "occupation": "Meslek",
    "occupations": "Meslekler",
    "profession": "Meslek",
    "professions": "Meslekler",
    "festivals": "Festivaller",
    "festival": "Festival",
    "case": "İsmin Hâli",
    "cases": "İsmin Halleri",
    "nominative": "Yalın Hâl (Nominativ)",
    "accusative": "Belirtme Hâli (Akkusativ)",
    "dative": "Yönelme Hâli (Dativ)",
    "genitive": "Tamlayan Hâli (Genitiv)",
    "asking": "Sorma",
    "answering": "Cevaplama",
    "sharing": "Paylaşma",
    "formulating": "Oluşturma",
    "constructing": "Kurma",
    "building": "Oluşturma",
    "introducing": "Tanıtma",
    "describing": "Tanımlama",
    "expressing": "İfade Etme",
    "navigating": "Yol Bulma",
    "ordering": "Sipariş Verme",
    "shopping": "Alışveriş Yapma",
    "talking": "Konuşma",
    "using": "Kullanma",
    "exploring": "Keşfetme",
    "mastering": "Uzmanlaşma",
    "understanding": "Anlama",
    "practicing": "Pratik Yapma",
    "reviewing": "Tekrar Etme",
    "counting": "Sayma",
    "making": "Yapma",
    "giving": "Verme",
  },

  cleanStutter: function(text) {
    if (!text) return '';
    let t = String(text).trim();
    t = t.replace(/\bGünlük\s+Hayatta\s+Hayatta\s+Kalma\b/gi, 'Günlük Hayatta Kalma')
         .replace(/\bHayatta\s+Hayatta\b/gi, 'Hayatta')
         .replace(/\bve\s+ve\b/gi, 've')
         .replace(/\bveya\s+veya\b/gi, 'veya')
         .replace(/\biçin\s+için\b/gi, 'için')
         .replace(/\bde\s+de\b/gi, 'de')
         .replace(/\bda\s+da\b/gi, 'da')
         .replace(/\bile\s+ile\b/gi, 'ile')
         .replace(/Wh-\s*Sorular[ıi](?:n[ıi]n?)?/gi, 'Soru Kelimeleri')
         .replace(/Wh-\s*Sorusu/gi, 'Soru Kelimesi')
         .replace(/Wh-\s*Questions?/gi, 'Soru Kelimeleri')
         .replace(/Wh-/gi, 'Soru Kelimeleri');
    t = t.replace(/\b([a-zA-ZçğıöşüÇĞİÖŞÜâîû]+)\s+\1\b/gi, (m, w) => {
      if (['yavaş', 'adım', 'tek', 'ayrı', 'az'].includes(w.toLowerCase())) return m;
      return w;
    });
    t = t.replace(/,\s*ve\b/gi, ' ve').replace(/\s{2,}/g, ' ').trim();
    return t;
  },

  cleanHybrids: function(text) {
    if (!text) return '';
    let t = String(text).trim();
    const hybrids = [
      [/Wh-\s*Sorular[ıi](?:n[ıi]n?)?/gi, 'Soru Kelimeleri'],
      [/Wh-\s*Sorusu/gi, 'Soru Kelimesi'],
      [/Wh-\s*Questions?/gi, 'Soru Kelimeleri'],
      [/Wh-/gi, 'Soru Kelimeleri'],
      [/Personal\s+Description\s+İçin/gi, 'Kişisel Tanım İçin'],
      [/Personal\s+Description/gi, 'Kişisel Tanım'],
      [/Traveling\s+İçin/gi, 'Seyahat İçin'],
      [/Travel\s+İçin/gi, 'Seyahat İçin'],
      [/Günlük\s+Hayatta\s+Hayatta\s+Kalma/gi, 'Günlük Hayatta Kalma'],
      [/Hayatta\s+Hayatta/gi, 'Hayatta'],
      [/Dünya\s+Around\s+Us/gi, 'Çevremizdeki Dünya'],
      [/the\s+world\s+around\s+us/gi, 'Çevremizdeki Dünya'],
      [/world\s+around\s+us/gi, 'Çevremizdeki Dünya'],
      [/around\s+us/gi, 'Çevremizdeki'],
      [/\bDaily\s+Objects\b/gi, 'Günlük Eşyalar'],
      [/\bGünlük\s+Objects\b/gi, 'Günlük Eşyalar'],
      [/\bobjects\b/gi, 'Eşyalar'],
      [/\bAile\s+ve\s+Friends\s+ve\s+(?:ve\s+)?Relationships\b/gi, 'Aile, Arkadaşlar ve İlişkiler'],
      [/\bFamily[,\s]+Friends[,\s]+(?:and\s+)?Relationships\b/gi, 'Aile, Arkadaşlar ve İlişkiler'],
      [/\bfriends\b/gi, 'Arkadaşlar'],
      [/\brelationships\b/gi, 'İlişkiler'],
      [/Temel\s+Social\s+Situations['’]?de\s+Yol\s+Bulma/gi, 'Temel Sosyal Durumlarda İletişim'],
      [/Social\s+Situations['’]?de\s+Yol\s+Bulma/gi, 'Sosyal Durumlarda İletişim'],
      [/\bNavigating\s+Basic\s+Social\s+Situations\b/gi, 'Temel Sosyal Durumlarda İletişim'],
      [/\bBasic\s+Social\s+Situations\b/gi, 'Temel Sosyal Durumlar'],
      [/\bSocial\s+Situations\b/gi, 'Sosyal Durumlar'],
      [/\bTraveling\s+Basics\b/gi, 'Seyahat Temelleri'],
      [/\bTravel\s+Basics\b/gi, 'Seyahat Temelleri'],
      [/Dışarıda\s+Yemek\s+Yeme/gi, 'Dışarıda Yemek'],
      [/\bDining\s+Out\b/gi, 'Dışarıda Yemek'],
      [/\bEating\s+Out\b/gi, 'Dışarıda Yemek'],
      [/Celebratory\s+Situations/gi, 'Kutlama Durumları'],
      [/Seeking\s+Help/gi, 'Yardım İsteme'],
      [/Phrases\s+for\s+Emergencies/gi, 'Acil Durum İfadeleri'],
      [/Visiting\s+a\s+Doctor/gi, 'Doktora Gitmek'],
      [/Key\s+Questions/gi, 'Anahtar Sorular'],
      [/Functional[_\s]+Language/gi, 'İşlevsel Dil'],
      [/Cultural[_\s]+Context/gi, 'Kültürel Bağlam']
    ];
    for (const [pat, repl] of hybrids) {
      t = t.replace(pat, repl);
    }
    return this.cleanStutter(t);
  },

  translate: function(title) {
    if (!title) return '';
    const t = String(title).trim();
    let clean = t.replace(/^(unit|chapter|topic|tema|lektion|item|ünite|unite|bölüm|bolum|c\.|l\.)\s*\d+\s*[:\-]\s*/i, '').trim();
    clean = this.cleanHybrids(clean);
    const low = clean.toLowerCase();

    // Check if already Turkish without English leftovers or stutter
    if (this.isCleanTurkish(clean) && !this.isHybridOrEnglish(clean)) {
      const mHalf = clean.match(/^(\d+)'den\s+(\d+)'(?:ye|e)\s+sayma\s*[:\-]\s*(.*)$/i);
      if (mHalf) {
        return this.cleanStutter(`${mHalf[1]}'den ${mHalf[2]}'e Sayma: ${this.translate(mHalf[3].trim())}`);
      }
      return this.cleanStutter(clean);
    }

    // Direct match in PHRASES first
    if (this.PHRASES[low]) return this.cleanStutter(this.PHRASES[low]);

    // 1. Direct dictionary lookup in EDUCATIONAL_SENTENCE_MAP if available
    if (window.EDUCATIONAL_SENTENCE_MAP_EN_TR) {
      const v = window.EDUCATIONAL_SENTENCE_MAP_EN_TR[t] || window.EDUCATIONAL_SENTENCE_MAP_EN_TR[clean];
      if (v && this.isCleanTurkish(v) && !this.isHybridOrEnglish(v)) return this.cleanStutter(v);
    }

    // 2. Check window.PAGE_TITLE_PAIRS
    if (Array.isArray(window.PAGE_TITLE_PAIRS)) {
      for (const [en, tr] of window.PAGE_TITLE_PAIRS) {
        if (!en || !tr) continue;
        if (t.toLowerCase() === en.toLowerCase() || low === en.toLowerCase()) {
          if (this.isCleanTurkish(tr) && !this.isHybridOrEnglish(tr)) return this.cleanStutter(tr);
        }
      }
    }

    // 3. Check CURRICULUM_PAIRS
    if (Array.isArray(CURRICULUM_PAIRS)) {
      for (const [en, tr] of CURRICULUM_PAIRS) {
        if (!en || !tr) continue;
        if (t.toLowerCase() === en.toLowerCase() || low === en.toLowerCase()) {
          if (this.isCleanTurkish(tr) && !this.isHybridOrEnglish(tr)) return this.cleanStutter(tr);
        }
      }
    }

    // Colon compound "A: B"
    if (clean.includes(':')) {
      const parts = clean.split(':');
      if (parts.length === 2) {
        const s1 = this.translate(parts[0].trim());
        const s2 = this.translate(parts[1].trim());
        if (this.isCleanTurkish(s1) && this.isCleanTurkish(s2)) {
          return this.cleanStutter(`${s1}: ${s2}`);
        }
      }
    }

    // A vs B
    const mVs = clean.match(/^(.*?)\s+(?:vs\.?|versus)\s+(.*)$/i);
    if (mVs) {
      return this.cleanStutter(`${this.translate(mVs[1].trim())} ve ${this.translate(mVs[2].trim())} Karşılaştırması`);
    }

    // Getting Acquainted with X
    const mAcq = clean.match(/^getting\s+acquainted\s+with\s+(the\s+)?(.*)$/i);
    if (mAcq) {
      let sub = mAcq[2].trim();
      const subClean = sub.replace(/\s+language$/i, '').trim().toLowerCase();
      if (this.LANGUAGES[subClean]) {
        return this.cleanStutter(`${this.LANGUAGES[subClean][0]} ile Tanışma`);
      }
      return this.cleanStutter(`${this.translate(sub)} ile Tanışma`);
    }

    // How to Ask and Answer 'X'
    const mAskAns = clean.match(/^how\s+to\s+ask\s+and\s+answer\s+['"]?(.*?)['"]?$/i);
    if (mAskAns) {
      const sub = mAskAns[1].trim();
      const subLow = sub.toLowerCase();
      if (this.QUOTED_EXPRESSIONS[subLow]) {
        return this.cleanStutter(`'${this.QUOTED_EXPRESSIONS[subLow]}' Diye Sorma ve Cevaplama`);
      }
      return this.cleanStutter(`'${sub}' Diye Sorma ve Cevaplama`);
    }

    // How to (Verb) (X)
    const mHowto = clean.match(/^how\s+to\s+(.*?)\s+(.*)$/i);
    if (mHowto) {
      const verb = mHowto[1].trim();
      const rest = mHowto[2].trim();
      const verbTr = this.VOCABULARY[verb.toLowerCase()] || verb;
      return this.cleanStutter(`${this.translate(rest)} ${verbTr} Yolları`);
    }

    // Sharing X
    const mSharing = clean.match(/^sharing\s+(.*)$/i);
    if (mSharing) {
      return this.cleanStutter(`${this.translate(mSharing[1].trim())} Paylaşma`);
    }

    // Exploring X
    const mExp = clean.match(/^exploring\s+(.*)$/i);
    if (mExp) {
      return this.cleanStutter(`${this.translate(mExp[1].trim())} Keşfetme`);
    }

    // Mastering X
    const mMas = clean.match(/^mastering\s+(.*)$/i);
    if (mMas) {
      return this.cleanStutter(`${this.translate(mMas[1].trim())} Konusunda Uzmanlaşma`);
    }

    // Formulating (X) Questions
    const mFormQ = clean.match(/^formulating\s+(.*?)\s+questions$/i);
    if (mFormQ) {
      return this.cleanStutter(`${this.translate(mFormQ[1].trim())} Soruları Oluşturma`);
    }

    // Formulating X
    const mForm = clean.match(/^formulating\s+(.*)$/i);
    if (mForm) {
      return this.cleanStutter(`${this.translate(mForm[1].trim())} Oluşturma`);
    }

    // Using 'X' to (Y) or Using X to (Y)
    const mUsingTo = clean.match(/^using\s+(.*?)\s+to\s+(.*)$/i);
    if (mUsingTo) {
      const actTr = this.translate(mUsingTo[2].trim());
      if (this.isCleanTurkish(actTr) && !this.isHybridOrEnglish(actTr)) {
        const cleanedTarget = mUsingTo[1].replace(/['"]/g, '').trim();
        const capitalized = cleanedTarget.charAt(0).toUpperCase() + cleanedTarget.slice(1);
        return this.cleanStutter(`'${capitalized}' Kullanarak ${actTr}`);
      }
    }

    // Constructing (X) in (the)? (Y)
    const mConstIn = clean.match(/^constructing\s+(.*?)\s+in\s+(the\s+)?(.*)$/i);
    if (mConstIn) {
      const s1 = this.translate(mConstIn[1].trim());
      const s2 = this.translate(mConstIn[3].trim());
      if (this.isCleanTurkish(s1) && this.isCleanTurkish(s2) && !this.isHybridOrEnglish(s1) && !this.isHybridOrEnglish(s2)) {
        return this.cleanStutter(`${s2}'de ${s1} Kurma`);
      }
    }

    // Constructing X
    const mConst = clean.match(/^constructing\s+(.*)$/i);
    if (mConst) {
      const sub = this.translate(mConst[1].trim());
      if (this.isCleanTurkish(sub) && !this.isHybridOrEnglish(sub)) {
        return this.cleanStutter(`${sub} Kurma`);
      }
    }

    // Polite Ways to X
    const mPolite = clean.match(/^polite\s+ways\s+to\s+(.*)$/i);
    if (mPolite) {
      const sub = this.translate(mPolite[1].trim());
      if (this.isCleanTurkish(sub) && !this.isHybridOrEnglish(sub)) {
        return this.cleanStutter(`${sub} İçin Nezaket İfadeleri`);
      }
    }

    // Geography and Major Cities of (the)? X
    const mGeo = clean.match(/^geography\s+and\s+major\s+cities\s+of\s+(the\s+)?(.*)$/i);
    if (mGeo) {
      return this.cleanStutter(`${this.translate(mGeo[2].trim())} Coğrafyası ve Başlıca Şehirleri`);
    }

    // Celebrations and Traditions in (the)? X
    const mCel = clean.match(/^celebrations\s+and\s+traditions\s+in\s+(the\s+)?(.*)$/i);
    if (mCel) {
      return this.cleanStutter(`${this.translate(mCel[2].trim())}'de Kutlamalar ve Gelenekler`);
    }

    // Cultural Contexts of / in X
    const mCult = clean.match(/^cultural\s+contexts?\s*(?:of|in)?\s*(.*)$/i);
    if (mCult && mCult[1].trim()) {
      return this.cleanStutter(`Kültürel Bağlamlar: ${this.translate(mCult[1].trim())}`);
    }

    // Counting from N1 to N2
    const mCount = clean.match(/^counting\s+from\s+(\d+)\s+to\s+(\d+)(.*)$/i);
    if (mCount) {
      const n1 = mCount[1];
      const n2 = mCount[2];
      const suffix = (n2.endsWith("00") || ["1", "3", "4", "5", "8", "70", "80"].includes(n2)) ? "e" : "a";
      let res = `${n1}'den ${n2}'${suffix} Sayma`;
      const extra = mCount[3].replace(/^[:\s\-]+/, '').trim();
      if (extra) res += `: ${this.translate(extra)}`;
      return this.cleanStutter(res);
    }

    // Introduction to X
    const mIntro = clean.match(/^introduction\s+to\s+(.*)$/i);
    if (mIntro) {
      const sub = this.translate(mIntro[1].trim());
      return this.cleanStutter(sub.endsWith("Giriş") ? sub : `${sub}'e Giriş`);
    }

    // Using X in Y
    const mUsingIn = clean.match(/^using\s+(.*?)\s+in\s+(.*)$/i);
    if (mUsingIn) {
      const s1 = this.translate(mUsingIn[1].trim());
      const s2 = this.translate(mUsingIn[2].trim());
      if (this.isCleanTurkish(s1) && this.isCleanTurkish(s2) && !this.isHybridOrEnglish(s1) && !this.isHybridOrEnglish(s2)) {
        return this.cleanStutter(`${s2}'de ${s1} Kullanımı`);
      }
    }

    // Using X
    const mUsing = clean.match(/^using\s+(.*)$/i);
    if (mUsing) {
      const sub = this.translate(mUsing[1].trim());
      if (this.isCleanTurkish(sub) && !this.isHybridOrEnglish(sub)) {
        return this.cleanStutter(`${sub} Kullanımı`);
      }
    }

    // Talking About X
    const mTalking = clean.match(/^talking\s+about\s+(.*)$/i);
    if (mTalking) {
      const sub = this.translate(mTalking[1].trim());
      if (this.isCleanTurkish(sub) && !this.isHybridOrEnglish(sub)) {
        return this.cleanStutter(`${sub} Hakkında Konuşma`);
      }
    }

    // Navigating X
    const mNav = clean.match(/^navigating\s+(.*)$/i);
    if (mNav) {
      const sub = this.translate(mNav[1].trim());
      if (this.isCleanTurkish(sub) && !this.isHybridOrEnglish(sub)) {
        if (sub.toLowerCase().includes('taşıma')) return this.cleanStutter(`${sub}da Yol Bulma`);
        return this.cleanStutter(`${sub}'de Yol Bulma`);
      }
    }

    // X for Y - SAFETY INVARIANT: both parts MUST be clean Turkish
    const mFor = clean.match(/^(.*?)\s+for\s+(.*)$/i);
    if (mFor) {
      const s1 = this.translate(mFor[1].trim());
      const s2 = this.translate(mFor[2].trim());
      if (this.isCleanTurkish(s1) && this.isCleanTurkish(s2) && !this.isHybridOrEnglish(s1) && !this.isHybridOrEnglish(s2)) {
        return this.cleanStutter(`${s2} İçin ${s1}`);
      }
    }

    // X in [Language]
    for (const [langEn, [langNom, langAdj, langLoc]] of Object.entries(this.LANGUAGES)) {
      const regex = new RegExp(`^(.*?)\\s+in\\s+${langEn}$`, 'i');
      const lm = clean.match(regex);
      if (lm) {
        const subTr = this.translate(lm[1].trim());
        if (this.isCleanTurkish(subTr) && !this.isHybridOrEnglish(subTr)) {
          return this.cleanStutter(`${langLoc} ${subTr}`);
        }
      }
    }

    // X and Y - SAFETY INVARIANT: both parts MUST be clean Turkish
    if (/\s+and\s+/i.test(clean)) {
      const parts = clean.split(/\s+and\s+/i);
      if (parts.length === 2) {
        const s1 = this.translate(parts[0].trim());
        const s2 = this.translate(parts[1].trim());
        if (this.isCleanTurkish(s1) && this.isCleanTurkish(s2) && !this.isHybridOrEnglish(s1) && !this.isHybridOrEnglish(s2)) {
          return this.cleanStutter(`${s1} ve ${s2}`);
        }
      }
    }

    // Comma-separated list "A, B, and C" or "A, B, C"
    if (clean.includes(',')) {
      const rawItems = clean.split(/,\s*(?:and\s+)?/i);
      if (rawItems.length > 1) {
        const trItems = rawItems.map(item => this.translate(item.trim()));
        if (trItems.every(it => this.isCleanTurkish(it) && !this.isHybridOrEnglish(it))) {
          if (trItems.length === 2) {
            return this.cleanStutter(`${trItems[0]} ve ${trItems[1]}`);
          }
          return this.cleanStutter(trItems.slice(0, -1).join(', ') + ` ve ${trItems[trItems.length - 1]}`);
        }
      }
    }

    // Language + Noun
    for (const [langEn, [langNom, langAdj, langLoc]] of Object.entries(this.LANGUAGES)) {
      if (low === `the ${langEn} language` || low === `${langEn} language`) {
        return `${langNom} Dili`;
      }
      const regex = new RegExp(`^${langEn}\\s+(.*)$`, 'i');
      const lm = clean.match(regex);
      if (lm) {
        const subTr = this.translate(lm[1].trim());
        return this.cleanStutter(`${langAdj} ${subTr}`);
      }
    }

    // Adjective + Noun
    const words = clean.split(/\s+/);
    if (words.length === 2) {
      const w1 = words[0].toLowerCase();
      const w2 = words[1].toLowerCase();
      if (this.VOCABULARY[w1] && this.VOCABULARY[w2]) {
        return this.cleanStutter(`${this.VOCABULARY[w1]} ${this.VOCABULARY[w2]}`);
      }
    }

    // Word-by-word fallback — SAFE: only translate if ALL tokens are recognized vocabulary
    // (Never produce Frankenstein hybrids like 'Nazik İfadeler for Conversation')
    let allTranslated = true;
    const translatedWords = [];
    for (const w of words) {
      const wLow = w.toLowerCase().replace(/[.,!?:;]/g, '');
      if (this.VOCABULARY[wLow]) {
        translatedWords.push(this.VOCABULARY[wLow]);
      } else if (this.LANGUAGES[wLow]) {
        translatedWords.push(this.LANGUAGES[wLow][0]);
      } else if (wLow === 'and') {
        translatedWords.push('ve');
      } else if (wLow === 'or') {
        translatedWords.push('veya');
      } else if (wLow === 'the') {
        continue; // skip article
      } else if (wLow === 'with') {
        translatedWords.push('ile');
      } else {
        allTranslated = false;
        break; // Unknown token — abort rather than produce a hybrid
      }
    }

    if (allTranslated && translatedWords.length > 0) {
      const res = translatedWords.join(' ');
      if (this.isCleanTurkish(res) && !this.isHybridOrEnglish(res)) {
        return this.cleanStutter(res);
      }
    }

    // Return the original clean English title — the server AI will translate properly
    return clean;
  },

  isHybridOrEnglish: function(text) {
    if (!text || typeof text !== 'string') return false;
    const t = text.trim();
    if (!t) return false;
    const low = t.toLowerCase();
    if (/\bve\s+ve\b/i.test(low) || /\bhayatta\s+hayatta\b/i.test(low) || low.includes('pratik application') || low.includes('around us') || /\bwh[- ]/i.test(low)) return true;

    // Strip target language foreign words inside quotes (e.g. 'ser', 'estar') so they are allowed
    const unquoted = t.replace(/['"][^'"]+['"]/g, '');

    const enPattern = /(?<![\p{L}\p{N}])(the|and|of|to|in|for|with|on|at|from|by|about|your|our|their|my|his|her|its|you|we|they|describing|talking|using|navigating|understanding|introducing|asking|making|expressing|telling|visiting|seeking|review|practice|practical|application|foundations|basics|intermediate|advanced|grammar|vocabulary|words|phrases|sentences|daily|activities|routines|food|dining|shopping|environment|travel|traveling|travelling|questions|answers|math|operations|culture|insights|context|customs|survival|numbers|counting|alphabet|vowels|consonants|pronunciation|phonetics|rules|check|guide|overview|summary|world|around|us|functional|language|situations|celebratory|emergencies|emergency|health|traditions|festivals|leisure|sports|hobbies|community|recommendations|transactions|menus|accessories|sizes|colors|transport|transportation|places|personal|description|identity|adjectives|adjective|nouns|noun|verbs|verb|conversation|dialogues|dialogue|objects|friends|friendship|free|time|interests|ordering|buying|giving|directions|family|members|feelings|emotions|workplace|office|home|school|weather|seasons|calendar|dates|essential|everyday|simple|who|what|where|when|why|how|which|whose|whom)(?![\p{L}\p{N}])/iu;

    const hasTr = /[çğıöşüÇĞİÖŞÜâîû]/.test(t) || /\b(ve|veya|ile|için|göre|kadar|temel|pratik|uygulama|tekrar|alfabe|selamlaşma|tanıtım|tanıtımlar|günlük|rutinler|sayılar|zaman|saat|aile|ilişkiler|hobiler|yiyecek|yemek|alışveriş|kıyafet|şehir|ulaşım|seyahat|tatil|kültür|kültürel|bilgiler|bağlam|dilbilgisi|kelimeler|kelime|kelimeleri|cümleler|cümle|cümleleri|ifadeler|ifade|ifadeleri|fiiller|fiil|sıfatlar|sıfat|zamirler|zamir|sorular|soru|soruları|sorusu|çevremizdeki|dünya|doğa|sağlık|iş|okul|ev|yerler|yol|tarifi|hava|durumu|mevsimler|doktora|gitmek|kutlama|durumları|işlevsel|topluluk|hediyeler|kutlamalar|tanım|tanımlama|kimlik|kim|ne|nerede|nereli|nasıl|neden|yanıt|yanıtlar|cevap|cevaplar|kurma|oluşturma|kullanma|kullanımı|anlatma|sorma|konuşma)\b/i.test(t);

    const hasEn = enPattern.test(unquoted);
    return (hasTr && hasEn) || (hasEn && !/[çğıöşüÇĞİÖŞÜâîû]/.test(t));
  },

  isCleanTurkish: function(text) {
    if (!text || typeof text !== 'string') return false;
    const t = text.trim();
    if (!t) return false;
    if (/\bHayatta\s+Hayatta\b/i.test(t) || /\bve\s+ve\b/i.test(t)) return false;
    if (this.isHybridOrEnglish(t)) return false;
    const hasTrChars = /[çğıöşüÇĞİÖŞÜâîû]/.test(t);
    const hasTrWords = /\b(ve|veya|ile|için|göre|kadar|temel|pratik|uygulama|tekrar|alfabe|selamlaşma|tanıtım|tanıtımlar|günlük|rutinler|sayılar|zaman|saat|aile|ilişkiler|hobiler|yiyecek|yemek|alışveriş|kıyafet|şehir|ulaşım|seyahat|tatil|kültür|kültürel|bilgiler|bağlam|dilbilgisi|kelimeler|kelime|kelimeleri|cümleler|cümle|cümleleri|ifadeler|ifade|ifadeleri|fiiller|fiil|sıfatlar|sıfat|zamirler|zamir|sorular|soru|soruları|sorusu|çevremizdeki|dünya|doğa|sağlık|iş|okul|ev|yerler|yol|tarifi|hava|durumu|mevsimler|doktora|gitmek|kutlama|durumları|işlevsel|topluluk|hediyeler|kutlamalar|tanım|tanımlama|kimlik|kim|ne|nerede|nereli|nasıl|neden|yanıt|yanıtlar|cevap|cevaplar|kurma|oluşturma|kullanma|kullanımı|anlatma|sorma|konuşma)\b/i.test(t);
    return hasTrChars || hasTrWords;
  }
};
window.UniversalCurriculumTranslator = UniversalCurriculumTranslator;

function translateCurriculumTitle(title, lang = currentLang) {
  if (!title) return '';
  const trimmed = title.trim();
  const clean = trimmed.replace(/^(unit|chapter|topic|tema|lektion|item|ünite|unite|bölüm|bolum|c\.|l\.)\s*\d+\s*[:\-]\s*/i, "").trim();
  const lowerTrimmed = trimmed.toLowerCase();
  const lowerClean = clean.toLowerCase();

  if (lang === 'tr') {
    // Check precompiled bundles first
    if (Array.isArray(window.PAGE_TITLE_PAIRS)) {
      for (const [en, tr] of window.PAGE_TITLE_PAIRS) {
        if (!en || !tr) continue;
        if (lowerClean === en.toLowerCase() || lowerTrimmed === en.toLowerCase()) return tr;
      }
    }
    if (window.EDUCATIONAL_SENTENCE_MAP_EN_TR) {
      if (window.EDUCATIONAL_SENTENCE_MAP_EN_TR[trimmed]) return window.EDUCATIONAL_SENTENCE_MAP_EN_TR[trimmed];
      if (window.EDUCATIONAL_SENTENCE_MAP_EN_TR[clean]) return window.EDUCATIONAL_SENTENCE_MAP_EN_TR[clean];
    }
    return UniversalCurriculumTranslator.translate(title);
  }

  // English lookup
  if (window.EDUCATIONAL_SENTENCE_MAP_TR_EN) {
    if (window.EDUCATIONAL_SENTENCE_MAP_TR_EN[trimmed]) return window.EDUCATIONAL_SENTENCE_MAP_TR_EN[trimmed];
    if (window.EDUCATIONAL_SENTENCE_MAP_TR_EN[clean]) return window.EDUCATIONAL_SENTENCE_MAP_TR_EN[clean];
  }

  if (Array.isArray(window.PAGE_TITLE_PAIRS)) {
    for (const [en, tr] of window.PAGE_TITLE_PAIRS) {
      if (!en || !tr) continue;
      if (lowerTrimmed === tr.toLowerCase() || lowerClean === tr.toLowerCase()) return en;
    }
  }

  if (Array.isArray(CURRICULUM_PAIRS)) {
    for (const [en, tr] of CURRICULUM_PAIRS) {
      if (!en || !tr) continue;
      if (lowerTrimmed === tr.toLowerCase() || lowerClean === tr.toLowerCase()) return en;
    }
  }

  if (/^temel\s+(kelimeler|kelime\s+bilgisi|kelime\s+dağarcığı|fiiller)$/i.test(trimmed) || /^temel\s+(kelimeler|kelime\s+bilgisi|kelime\s+dağarcığı|fiiller)$/i.test(clean)) return 'Essential Vocabulary';
  if (/^yapısal\s+odak$/i.test(trimmed) || /^yapısal\s+odak$/i.test(clean)) return 'Structural Focus';
  if (/^pratik\s+uygulama$/i.test(trimmed) || /^pratik\s+uygulama$/i.test(clean)) return 'Practical Application';
  if (/^hızlı\s+kontrol$/i.test(trimmed) || /^hızlı\s+kontrol$/i.test(clean)) return 'Quick Check';

  return clean || trimmed;
}

function translateQuizTitle(title, lang = currentLang) {
  if (!title) return '';
  const trimmed = title.trim();

  // 1. Exact match for All Topics / All Chapters variations
  if (/^(tüm\s+konular|tüm\s+bölümler|tüm\s+dersler)$/i.test(trimmed)) {
    return lang === 'tr' ? 'Tüm Konular' : 'All Topics';
  }
  if (/^(all\s+topics|all\s+chapters|all\s+lessons)$/i.test(trimmed)) {
    return lang === 'tr' ? 'Tüm Konular' : 'All Topics';
  }

  // 2. Generic Quiz / Assignment
  if (/^quiz$/i.test(trimmed)) {
    return lang === 'tr' ? 'Sınav' : 'Quiz';
  }
  if (/^assignment$/i.test(trimmed)) {
    return lang === 'tr' ? 'Ödev' : 'Assignment';
  }

  // 3. Chapter / Unit Quiz: "Chapter 3 Quiz", "Ünite 3 Sınavı", etc.
  const mChQuiz = trimmed.match(/^(chapter|bölüm|ünite|unit)\s*(\d+)\s*(quiz|sınavı?)$/i);
  if (mChQuiz) {
    const num = mChQuiz[2];
    return lang === 'tr' ? `Ünite ${num} Sınavı` : `Unit ${num} Quiz`;
  }

  // 4. Chapter / Unit Assignment: "Chapter 3 Assignment", "Ünite 3 Ödevi"
  const mChAssign = trimmed.match(/^(chapter|bölüm|ünite|unit)\s*(\d+)\s*(assignment|ödevi?)$/i);
  if (mChAssign) {
    const num = mChAssign[2];
    return lang === 'tr' ? `Ünite ${num} Ödevi` : `Unit ${num} Assignment`;
  }

  // 5. Topic with Quiz suffix: e.g. "Vowels and Consonants Quiz" or "Sesli Harfler ve Sessiz Harfler Sınavı"
  const mSuffixQuiz = trimmed.match(/^(.*?)\s+(quiz|sınavı?)$/i);
  if (mSuffixQuiz) {
    const baseTopic = mSuffixQuiz[1].trim();
    const translatedBase = translateCurriculumTitle(baseTopic, lang);
    return lang === 'tr' ? `${translatedBase} Sınavı` : `${translatedBase} Quiz`;
  }

  // 6. Topic with Assignment suffix: e.g. "Vowels and Consonants Assignment" or "Sesli Harfler ve Sessiz Harfler Ödevi"
  const mSuffixAssign = trimmed.match(/^(.*?)\s+(assignment|ödevi?)$/i);
  if (mSuffixAssign) {
    const baseTopic = mSuffixAssign[1].trim();
    const translatedBase = translateCurriculumTitle(baseTopic, lang);
    return lang === 'tr' ? `${translatedBase} Ödevi` : `${translatedBase} Assignment`;
  }

  // 7. Topic itself as title
  const translatedCurriculum = translateCurriculumTitle(trimmed, lang);
  if (translatedCurriculum) {
    return translatedCurriculum;
  }

  return trimmed;
}
window.translateQuizTitle = translateQuizTitle;

function getLocalizedCurriculumTitle(item, lang = currentLang) {
  if (!item) return '';
  if (typeof item === 'string') {
    return translateCurriculumTitle(item, lang);
  }
  if (lang === 'tr') {
    if (item.title_tr && typeof item.title_tr === 'string') {
      const trVal = item.title_tr.trim();
      if (trVal && !UniversalCurriculumTranslator.isHybridOrEnglish(trVal)) {
        return trVal;
      }
    }
    const source = item.title || item.title_tr || '';
    return translateCurriculumTitle(source, 'tr');
  } else {
    if (item.title && typeof item.title === 'string') {
      const enVal = item.title.trim();
      if (enVal && !UniversalCurriculumTranslator.isCleanTurkish(enVal)) {
        return enVal;
      }
    }
    const source = item.title_tr || item.title || '';
    return translateCurriculumTitle(source, 'en');
  }
}

const VOCAB_PAIRS = [
  ["hello", "merhaba"],
  ["hi", "selam"],
  ["good morning", "günaydın"],
  ["good afternoon", "iyi günler"],
  ["good evening", "iyi akşamlar"],
  ["good night", "iyi geceler"],
  ["What's your name?", "Adın ne?"],
  ["My name is...", "Benim adım..."],
  ["Where are you from?", "Nerelisin?"],
  ["I'm from...", "Ben ...'lıyım"],
  ["nice to meet you", "memnun oldum"],
  ["goodbye", "hoşça kal"],
  ["bye", "hoşça kal"],
  ["see you later", "görüşürüz"],
  ["see you soon", "yakında görüşürüz"],
  ["please", "lütfen"],
  ["thank you", "teşekkür ederim"],
  ["thanks", "teşekkürler"],
  ["you're welcome", "rica ederim"],
  ["yes", "evet"],
  ["no", "hayır"],
  ["excuse me", "afedersiniz"],
  ["sorry", "özür dilerim"],
  ["friend", "arkadaş"],
  ["family", "aile"],
  ["mother", "anne"],
  ["father", "baba"],
  ["brother", "erkek kardeş"],
  ["sister", "kız kardeş"],
  ["son", "oğul"],
  ["daughter", "kız çocuk"],
  ["house", "ev"],
  ["home", "ev"],
  ["water", "su"],
  ["bread", "ekmek"],
  ["coffee", "kahve"],
  ["tea", "çay"],
  ["food", "yemek"],
  ["book", "kitap"],
  ["school", "okul"],
  ["teacher", "öğretmen"],
  ["student", "öğrenci"],
  ["cat", "kedi"],
  ["dog", "köpek"],
  ["car", "araba"],
  ["city", "şehir"],
  ["country", "ülke"],
  ["time", "zaman"],
  ["day", "gün"],
  ["night", "gece"],
  ["week", "hafta"],
  ["month", "ay"],
  ["year", "yıl"],
  ["today", "bugün"],
  ["tomorrow", "yarın"],
  ["yesterday", "dün"],
  ["Monday", "Pazartesi"],
  ["Tuesday", "Salı"],
  ["Wednesday", "Çarşamba"],
  ["Thursday", "Perşembe"],
  ["Friday", "Cuma"],
  ["Saturday", "Cumartesi"],
  ["Sunday", "Pazar"],
  ["one", "bir"],
  ["two", "iki"],
  ["three", "üç"],
  ["four", "dört"],
  ["five", "beş"],
  ["six", "altı"],
  ["seven", "yedi"],
  ["eight", "sekiz"],
  ["nine", "dokuz"],
  ["ten", "on"],
  ["I", "ben"],
  ["you", "sen"],
  ["he", "o (erkek)"],
  ["she", "o (kadın)"],
  ["we", "biz"],
  ["they", "onlar"],
  ["Spanish", "İspanyol"],
  ["Mexican", "Meksikalı"],
  ["American", "Amerikalı"],
  ["French", "Fransız"],
  ["German", "Alman"],
  ["Italian", "İtalyan"],
  ["Brazilian", "Brezilyalı"],
  ["Chinese", "Çinli"],
  ["Japanese", "Japon"],
  ["English/British", "İngiliz"],
  ["Argentine", "Arjantinli"],
  ["Colombian", "Kolombiyalı"],
  ["Greek", "Yunan"],
  ["Turkish", "Türk"],
  ["Multiple Choice", "Çoktan Seçmeli"],
  ["Fill in the Blank", "Boşluk Doldurma"],
  ["Arrange the dialogue in the correct order:", "Diyaloğu doğru sıraya koyun:"]
];

const SPANISH_LETTER_SPELLINGS = new Set([
  'a','be','ce','de','e','efe','ge','hache','i','jota','ka','ele','eme','ene','eñe','o','pe','cu','ere','erre','ese','te','u','uve','uve doble','equis','i griega','zeta'
]);

const TAUTOLOGY_REGEX = /(?:\beylemini\s+ifade\s+eder|\betkinliğini\s+ifade\s+eder|\bifade\s+etmek\s+için\s+kullanılır|\beylemidir|\bveya\s+spor\s+etkinliklerini|\bresim\s+yaratmayı|\biçerir\.|\büretme\s+eylemidir|\brefers?\s+to\s+the\s+act\s+of|\bmeans?\s+the\s+act\s+of|\bis\s+the\s+act\s+of|\bused\s+to\s+express\s+the\s+action\s+of)/i;

const ALPHABET_PHONETICS_MAP = {
  "spanish": {
    "A": { "name": "A", "phonetic_en": "[ah]", "phonetic_tr": "[a]", "example": "Amigo", "example_en": "Friend", "example_tr": "Arkadaş", "explanation_en": "Open and bright vowel sound, pronounced cleanly like the 'a' in 'father'; never slurred or weakened.", "explanation_tr": "Türkçedeki 'a' sesi gibi açık ve net okunur; asla yuvarlanmaz veya zayıflatılmaz." },
    "B": { "name": "Be", "phonetic_en": "[beh]", "phonetic_tr": "[be]", "example": "Bueno", "example_en": "Good", "example_tr": "İyi", "explanation_en": "Pronounced as a soft bilabial stop [b] at the start of a phrase, and a gentle approximant [β] between vowels.", "explanation_tr": "Kelime başında Türkçedeki 'b' gibidir; iki ünlü arasında dudaklar birbirine tam değmeden yumuşakça çıkar." },
    "C": { "name": "Ce", "phonetic_en": "[seh / theh] (e/i) / [kah] (a/o/u)", "phonetic_tr": "[se / peltek s] (e/i) / [k] (a/o/u)", "example": "Casa", "example_en": "House", "example_tr": "Ev", "explanation_en": "Hard [k] before a, o, u (casa, coche, cuna); soft [s] or [θ] before e, i (cero, cine).", "explanation_tr": "a, o, u önünde 'k' sesi verir (casa, coche); e ve i önünde ise 's' veya peltek 's' olarak okunur (cero, cine)." },
    "CH": { "name": "Che", "phonetic_en": "[cheh]", "phonetic_tr": "[çe]", "example": "Chico", "example_en": "Boy", "example_tr": "Çocuk", "explanation_en": "Voiceless postalveolar affricate, pronounced crisply like 'ch' in 'chocolate' or 'cheese'.", "explanation_tr": "Türkçedeki 'ç' sesi gibi net ve sert bir sestir (chico, chocolate)." },
    "D": { "name": "De", "phonetic_en": "[deh]", "phonetic_tr": "[de]", "example": "Día", "example_en": "Day", "example_tr": "Gün", "explanation_en": "Dental stop [d] at word start; softens to a gentle approximant [ð] (like 'th' in 'this') between vowels.", "explanation_tr": "Kelime başında net 'd' sesi verir; ünlüler arasında ise yumuşayarak peltek bir ton alır." },
    "E": { "name": "E", "phonetic_en": "[eh]", "phonetic_tr": "[e]", "example": "Elefante", "example_en": "Elephant", "example_tr": "Fil", "explanation_en": "Mid-front invariant vowel, pronounced cleanly like 'e' in 'bed'; never gliding into an 'ee' sound.", "explanation_tr": "Türkçedeki 'e' sesi gibi sabit ve nettir; asla diftonglaşmaz veya uzatılmaz." },
    "F": { "name": "Efe", "phonetic_en": "[EH-feh]", "phonetic_tr": "[efe]", "example": "Familia", "example_en": "Family", "example_tr": "Aile", "explanation_en": "Voiceless labiodental fricative, pronounced exactly like 'f' in 'father' or 'fine'.", "explanation_tr": "Türkçedeki 'f' sesiyle aynıdır; üst dişler alt dudağa hafifçe değer." },
    "G": { "name": "Ge", "phonetic_en": "[heh] (e/i) / [geh] (a/o/u)", "phonetic_tr": "[he] (boğazdan h, e/i) / [ge] (a/o/u)", "example": "Gato", "example_en": "Cat", "example_tr": "Kedi", "explanation_en": "Hard [g] before a, o, u (gato, gusto); raspy fricative [x] from the throat before e, i (gente, girasol).", "explanation_tr": "a, o, u önünde sert 'g' (gato); e ve i önünde ise boğazdan hırıltılı 'h' sesi verir (gente)." },
    "H": { "name": "Hache", "phonetic_en": "[AH-cheh] (always silent)", "phonetic_tr": "[açe] (daima sessiz, okunmaz)", "example": "Hola", "example_en": "Hello", "example_tr": "Merhaba", "explanation_en": "Always completely silent in Spanish; never pronounced under any circumstances (hola sounds like 'ola').", "explanation_tr": "İspanyolcada daima sessizdir, asla okunmaz (hola sözcüğü 'ola' şeklinde okunur)." },
    "I": { "name": "I", "phonetic_en": "[ee]", "phonetic_tr": "[i]", "example": "Isla", "example_en": "Island", "example_tr": "Ada", "explanation_en": "Close front vowel, pronounced like 'ee' in 'see' or 'machine'; crisp and distinct.", "explanation_tr": "Türkçedeki 'i' sesi gibi net ve kısadır; asla yuvarlanmaz veya zayıflatılmaz." },
    "J": { "name": "Jota", "phonetic_en": "[HOH-tah] (raspy h)", "phonetic_tr": "[hota] (boğazdan h sesi)", "example": "Jardín", "example_en": "Garden", "example_tr": "Bahçe", "explanation_en": "Voiceless velar/uvular fricative from the throat, like the Scottish 'ch' in 'loch' or strong 'h' in 'hotel'.", "explanation_tr": "Boğazın arkasından gelen hırıltılı bir 'h' sesidir (Almanca 'ach' gibi)." },
    "K": { "name": "Ka", "phonetic_en": "[kah]", "phonetic_tr": "[ka]", "example": "Kilo", "example_en": "Kilo", "example_tr": "Kilo", "explanation_en": "Found only in foreign loanwords; pronounced as a crisp [k] as in 'kite'.", "explanation_tr": "Yabancı kökenli sözcüklerde bulunur; sert ve net 'k' sesi verir." },
    "L": { "name": "Ele", "phonetic_en": "[EH-leh]", "phonetic_tr": "[ele]", "example": "Libro", "example_en": "Book", "example_tr": "Kitap", "explanation_en": "Voiced alveolar lateral, pronounced with the tongue tip against the upper gum ridge like 'l' in 'light'.", "explanation_tr": "Türkçedeki ince 'l' sesi gibi dil ucu üst damağa değerek berrak çıkar." },
    "LL": { "name": "Elle", "phonetic_en": "[YEH / EH-lyeh]", "phonetic_tr": "[ye / elye]", "example": "Lluvia", "example_en": "Rain", "example_tr": "Yağmur", "explanation_en": "Pronounced like the 'y' in 'yes' across most Hispanic dialects; historically a palatal lateral [ʎ].", "explanation_tr": "Günümüz İspanyolcasında çoğunlukla 'y' sesi (yağmur gibi) olarak telaffuz edilir." },
    "M": { "name": "Eme", "phonetic_en": "[EH-meh]", "phonetic_tr": "[eme]", "example": "Madre", "example_en": "Mother", "example_tr": "Anne", "explanation_en": "Bilabial nasal, pronounced cleanly like the 'm' in 'mother'.", "explanation_tr": "Türkçedeki 'm' sesi ile tamamen aynıdır; dudaklar kapatılarak çıkarılır." },
    "N": { "name": "Ene", "phonetic_en": "[EH-neh]", "phonetic_tr": "[ene]", "example": "Noche", "example_en": "Night", "example_tr": "Gece", "explanation_en": "Alveolar nasal, pronounced cleanly like the 'n' in 'night'.", "explanation_tr": "Türkçedeki 'n' sesi ile tamamen aynıdır; dil ucu üst damağa değer." },
    "Ñ": { "name": "Eñe", "phonetic_en": "[EH-nyeh] (like canyon)", "phonetic_tr": "[enye] (n+y sesi)", "example": "Niño", "example_en": "Child", "example_tr": "Çocuk", "explanation_en": "Voiced palatal nasal, pronounced like the 'ny' in 'canyon' or 'onion'.", "explanation_tr": "Damaktan çıkan 'n+y' birleşik sesidir (kanyon sözcüğündeki 'ny' gibi)." },
    "O": { "name": "O", "phonetic_en": "[oh]", "phonetic_tr": "[o]", "example": "Ojo", "example_en": "Eye", "example_tr": "Göz", "explanation_en": "Back mid rounded vowel, pronounced cleanly like the 'o' in 'for' or 'order'; never diphthongized.", "explanation_tr": "Türkçedeki 'o' sesi gibi yuvarlak ve nettir; asla diftonglaşmaz." },
    "P": { "name": "Pe", "phonetic_en": "[peh]", "phonetic_tr": "[pe]", "example": "Padre", "example_en": "Father", "example_tr": "Baba", "explanation_en": "Voiceless bilabial stop, pronounced crisply like 'p' in 'spot' without heavy aspiration.", "explanation_tr": "Türkçedeki 'p' sesi gibi nefes patlaması olmadan net çıkar." },
    "Q": { "name": "Cu", "phonetic_en": "[koo] (qu = k)", "phonetic_tr": "[ku] (qu = k sesi)", "example": "Queso", "example_en": "Cheese", "example_tr": "Peynir", "explanation_en": "Always followed by silent 'u' (qu) before e or i, pronounced as [k] (queso sounds like 'keso').", "explanation_tr": "Daima 'qu' şeklinde e veya i önünde gelir; 'u' okunmaz, sert 'k' sesi verir (queso -> keso)." },
    "R": { "name": "Ere", "phonetic_en": "[EH-reh] (soft tap)", "phonetic_tr": "[ere] (yumuşak r)", "example": "Pero", "example_en": "But", "example_tr": "Ama", "explanation_en": "A single alveolar tap, like the rapid 'tt' in American English 'butter' or 'city'.", "explanation_tr": "Hafif ve tek bir dil vuruşuyla çıkan yumuşak 'r' sesidir." },
    "RR": { "name": "Erre", "phonetic_en": "[EH-rreh] (trilled r)", "phonetic_tr": "[erre] (kuvvetli titrek r)", "example": "Perro", "example_en": "Dog", "example_tr": "Köpek", "explanation_en": "A multi-tap vibrant trill produced by vibrating the tip of the tongue against the alveolar ridge.", "explanation_tr": "Dil ucunun üst damakta hızla titretilmesiyle oluşan kuvvetli, çift 'r' sesidir." },
    "S": { "name": "Ese", "phonetic_en": "[EH-seh]", "phonetic_tr": "[ese]", "example": "Sol", "example_en": "Sun", "example_tr": "Güneş", "explanation_en": "Voiceless alveolar sibilant, pronounced cleanly like the 's' in 'sun'.", "explanation_tr": "Türkçedeki 's' sesi gibi temiz ve nettir." },
    "T": { "name": "Te", "phonetic_en": "[teh]", "phonetic_tr": "[te]", "example": "Tiempo", "example_en": "Time", "example_tr": "Zaman", "explanation_en": "Dental stop, pronounced with the tongue directly against the back of the upper front teeth, like 't' in 'stop'.", "explanation_tr": "Dil ucu üst dişlerin arkasına basılarak çıkan sert 't' sesidir." },
    "U": { "name": "U", "phonetic_en": "[oo]", "phonetic_tr": "[u]", "example": "Uva", "example_en": "Grape", "example_tr": "Üzüm", "explanation_en": "Close back rounded vowel, pronounced cleanly like the 'oo' in 'moon' or 'lunar'.", "explanation_tr": "Türkçedeki 'u' sesi gibi dudaklar öne uzatılarak net çıkarılır." },
    "V": { "name": "Uve", "phonetic_en": "[OO-beh] (b/v sound)", "phonetic_tr": "[uve] (b-v arası ses)", "example": "Vino", "example_en": "Wine", "example_tr": "Şarap", "explanation_en": "Phonetically identical to 'b' in Spanish; pronounced with both lips, without biting the lower lip.", "explanation_tr": "İspanyolcada 'b' ile tamamen aynıdır; alt dudak ısırılmadan yumuşakça telaffuz edilir." },
    "W": { "name": "Uve doble", "phonetic_en": "[OO-beh DOH-bleh]", "phonetic_tr": "[uve doble] (çift v)", "example": "Web", "example_en": "Web", "example_tr": "Web", "explanation_en": "Appears exclusively in loanwords; pronounced like English [w] in 'water' or [b].", "explanation_tr": "Yalnızca yabancı sözcüklerde bulunur; İngilizce 'w' sesi gibi okunur." },
    "X": { "name": "Equis", "phonetic_en": "[EH-kees]", "phonetic_tr": "[ekis]", "example": "Éxito", "example_en": "Success", "example_tr": "Başarı", "explanation_en": "Pronounced as [ks] between vowels (éxito) and often as [s] before consonants (extra).", "explanation_tr": "İki ünlü arasında 'ks' (éxito), sessiz harflerden önce ise genellikle 's' okunur." },
    "Y": { "name": "I griega / Ye", "phonetic_en": "[ee gryeh-gah / yeh]", "phonetic_tr": "[i griyega / ye]", "example": "Yo", "example_en": "I", "example_tr": "Ben", "explanation_en": "Pronounced like the 'y' in 'yes' before vowels; sounds like 'ee' in 'see' at word ends (hoy, rey).", "explanation_tr": "Ünlü önünde 'y' sesi, tek başına veya kelime sonunda ise 'i' gibi okunur." },
    "Z": { "name": "Zeta", "phonetic_en": "[SEH-tah / THEH-tah]", "phonetic_tr": "[seta / peltek s]", "example": "Zapato", "example_en": "Shoe", "example_tr": "Ayakkabı", "explanation_en": "Pronounced as voiceless [θ] ('th' in 'thin') in Spain, and as [s] in Latin America.", "explanation_tr": "İspanya'da peltek 's' (İngilizce 'think' gibi), Latin Amerika'da ise düz 's' okunur." }
  },
  "german": {
    "A": { "name": "A", "phonetic_en": "[ah]", "phonetic_tr": "[a]", "example": "Apfel" },
    "Ä": { "name": "Ä", "phonetic_en": "[eh] (open e)", "phonetic_tr": "[açık e]", "example": "Äpfel" },
    "B": { "name": "Be", "phonetic_en": "[beh]", "phonetic_tr": "[be]", "example": "Buch" },
    "C": { "name": "Ce", "phonetic_en": "[tseh]", "phonetic_tr": "[tse]", "example": "Computer" },
    "D": { "name": "De", "phonetic_en": "[deh]", "phonetic_tr": "[de]", "example": "Danke" },
    "E": { "name": "E", "phonetic_en": "[eh]", "phonetic_tr": "[e]", "example": "Essen" },
    "F": { "name": "Ef", "phonetic_en": "[eff]", "phonetic_tr": "[ef]", "example": "Freund" },
    "G": { "name": "Ge", "phonetic_en": "[geh]", "phonetic_tr": "[ge]", "example": "Gut" },
    "H": { "name": "Ha", "phonetic_en": "[hah] (aspirated)", "phonetic_tr": "[ha] (vurgulu)", "example": "Haus" },
    "I": { "name": "I", "phonetic_en": "[ee]", "phonetic_tr": "[i]", "example": "Insel" },
    "J": { "name": "Jott", "phonetic_en": "[yot] (y-sound)", "phonetic_tr": "[yot] (y sesi)", "example": "Ja" },
    "K": { "name": "Ka", "phonetic_en": "[kah]", "phonetic_tr": "[ka]", "example": "Katze" },
    "L": { "name": "El", "phonetic_en": "[ell]", "phonetic_tr": "[el]", "example": "Liebe" },
    "M": { "name": "Em", "phonetic_en": "[emm]", "phonetic_tr": "[em]", "example": "Mutter" },
    "N": { "name": "En", "phonetic_en": "[enn]", "phonetic_tr": "[en]", "example": "Nacht" },
    "O": { "name": "O", "phonetic_en": "[oh]", "phonetic_tr": "[o]", "example": "Ohr" },
    "Ö": { "name": "Ö", "phonetic_en": "[oe] (rounded lips)", "phonetic_tr": "[ö]", "example": "Öl" },
    "P": { "name": "Pe", "phonetic_en": "[peh]", "phonetic_tr": "[pe]", "example": "Park" },
    "Q": { "name": "Ku", "phonetic_en": "[koo] (qu = kv)", "phonetic_tr": "[ku] (qu = kv sesi)", "example": "Quelle" },
    "R": { "name": "Er", "phonetic_en": "[err] (uvular r)", "phonetic_tr": "[er] (boğazdan r)", "example": "Rot" },
    "S": { "name": "Es", "phonetic_en": "[ess] (z-sound at start)", "phonetic_tr": "[es] (başta z)", "example": "Sonne" },
    "ß": { "name": "Eszett", "phonetic_en": "[es-TSET] (sharp double s)", "phonetic_tr": "[esset] (keskin çift s)", "example": "Straße" },
    "T": { "name": "Te", "phonetic_en": "[teh]", "phonetic_tr": "[te]", "example": "Tag" },
    "U": { "name": "U", "phonetic_en": "[oo]", "phonetic_tr": "[u]", "example": "Uhr" },
    "Ü": { "name": "Ü", "phonetic_en": "[ue] (rounded lips)", "phonetic_tr": "[ü]", "example": "Über" },
    "V": { "name": "Vau", "phonetic_en": "[fow] (f-sound)", "phonetic_tr": "[fau] (f sesi)", "example": "Vater" },
    "W": { "name": "We", "phonetic_en": "[veh] (v-sound)", "phonetic_tr": "[ve] (v sesi)", "example": "Wasser" },
    "X": { "name": "Iks", "phonetic_en": "[iks]", "phonetic_tr": "[iks]", "example": "Taxi" },
    "Y": { "name": "Ypsilon", "phonetic_en": "[UP-si-lon] (ü-sound)", "phonetic_tr": "[ipsilon] (ü sesi)", "example": "Typ" },
    "Z": { "name": "Zett", "phonetic_en": "[tset] (ts-sound)", "phonetic_tr": "[tset] (ts sesi)", "example": "Zeit" }
  },
  "french": {
    "A": { "name": "A", "phonetic_en": "[ah]", "phonetic_tr": "[a]", "example": "Ami" },
    "B": { "name": "Bé", "phonetic_en": "[beh]", "phonetic_tr": "[be]", "example": "Bonjour" },
    "C": { "name": "Cé", "phonetic_en": "[seh]", "phonetic_tr": "[se]", "example": "Ciel" },
    "Ç": { "name": "C cédille", "phonetic_en": "[seh sey-dee] (always s)", "phonetic_tr": "[se sediy] (daima s)", "example": "Français" },
    "D": { "name": "Dé", "phonetic_en": "[deh]", "phonetic_tr": "[de]", "example": "Demain" },
    "E": { "name": "E", "phonetic_en": "[uh]", "phonetic_tr": "[kapalı ö/e]", "example": "Enfant" },
    "É": { "name": "E accent aigu", "phonetic_en": "[ay] (closed e)", "phonetic_tr": "[kapalı e]", "example": "Été" },
    "È": { "name": "E accent grave", "phonetic_en": "[eh] (open e)", "phonetic_tr": "[açık e]", "example": "Père" },
    "F": { "name": "Eff", "phonetic_en": "[eff]", "phonetic_tr": "[ef]", "example": "Femme" },
    "G": { "name": "Gé", "phonetic_en": "[zheh]", "phonetic_tr": "[je]", "example": "Gare" },
    "H": { "name": "Hache", "phonetic_en": "[AHSH] (silent)", "phonetic_tr": "[aş] (sessiz harf)", "example": "Homme" },
    "I": { "name": "I", "phonetic_en": "[ee]", "phonetic_tr": "[i]", "example": "Île" },
    "J": { "name": "Ji", "phonetic_en": "[zhee]", "phonetic_tr": "[ji]", "example": "Jour" },
    "K": { "name": "Ka", "phonetic_en": "[kah]", "phonetic_tr": "[ka]", "example": "Kilo" },
    "L": { "name": "Elle", "phonetic_en": "[ell]", "phonetic_tr": "[el]", "example": "Livre" },
    "M": { "name": "Emme", "phonetic_en": "[emm]", "phonetic_tr": "[em]", "example": "Maison" },
    "N": { "name": "Enne", "phonetic_en": "[enn]", "phonetic_tr": "[en]", "example": "Nuit" },
    "O": { "name": "O", "phonetic_en": "[oh]", "phonetic_tr": "[o]", "example": "Oui" },
    "P": { "name": "Pé", "phonetic_en": "[peh]", "phonetic_tr": "[pe]", "example": "Pain" },
    "Q": { "name": "Ku", "phonetic_en": "[kew]", "phonetic_tr": "[kü]", "example": "Quatre" },
    "R": { "name": "Erre", "phonetic_en": "[AIR] (french uvular r)", "phonetic_tr": "[er] (boğazdan g-r)", "example": "Rouge" },
    "S": { "name": "Esse", "phonetic_en": "[ess]", "phonetic_tr": "[es]", "example": "Soleil" },
    "T": { "name": "Té", "phonetic_en": "[teh]", "phonetic_tr": "[te]", "example": "Temps" },
    "U": { "name": "U", "phonetic_en": "[ew] (french rounded u)", "phonetic_tr": "[ü]", "example": "Un" },
    "V": { "name": "Vé", "phonetic_en": "[veh]", "phonetic_tr": "[ve]", "example": "Vin" },
    "W": { "name": "Double vé", "phonetic_en": "[DOO-bluh veh]", "phonetic_tr": "[dubl ve]", "example": "Weekend" },
    "X": { "name": "Iks", "phonetic_en": "[eeks]", "phonetic_tr": "[iks]", "example": "Yeux" },
    "Y": { "name": "I grec", "phonetic_en": "[ee GREK]", "phonetic_tr": "[i grek]", "example": "Yeux" },
    "Z": { "name": "Zède", "phonetic_en": "[zed]", "phonetic_tr": "[zed]", "example": "Zéro" }
  },
  "italian": {
    "A": { "name": "A", "phonetic_en": "[ah]", "phonetic_tr": "[a]", "example": "Amore" },
    "B": { "name": "Bi", "phonetic_en": "[bee]", "phonetic_tr": "[bi]", "example": "Bello" },
    "C": { "name": "Ci", "phonetic_en": "[chee] (e/i) / [k] (a/o/u)", "phonetic_tr": "[çi] (e/i) / [k] (a/o/u)", "example": "Ciao / Casa" },
    "D": { "name": "Di", "phonetic_en": "[dee]", "phonetic_tr": "[di]", "example": "Donna" },
    "E": { "name": "E", "phonetic_en": "[eh]", "phonetic_tr": "[e]", "example": "Estate" },
    "F": { "name": "Effe", "phonetic_en": "[EF-feh]", "phonetic_tr": "[effe]", "example": "Famiglia" },
    "G": { "name": "Gi", "phonetic_en": "[jee] (e/i) / [g] (a/o/u)", "phonetic_tr": "[ci] (e/i) / [g] (a/o/u)", "example": "Giorno / Gatto" },
    "H": { "name": "Acca", "phonetic_en": "[AHK-kah] (silent)", "phonetic_tr": "[akka] (sessiz harf)", "example": "Hotel" },
    "I": { "name": "I", "phonetic_en": "[ee]", "phonetic_tr": "[i]", "example": "Isola" },
    "L": { "name": "Elle", "phonetic_en": "[EL-leh]", "phonetic_tr": "[elle]", "example": "Libro" },
    "M": { "name": "Emme", "phonetic_en": "[EM-meh]", "phonetic_tr": "[emme]", "example": "Madre" },
    "N": { "name": "Enne", "phonetic_en": "[EN-neh]", "phonetic_tr": "[enne]", "example": "Notte" },
    "O": { "name": "O", "phonetic_en": "[oh]", "phonetic_tr": "[o]", "example": "Oggi" },
    "P": { "name": "Pi", "phonetic_en": "[pee]", "phonetic_tr": "[pi]", "example": "Pane" },
    "Q": { "name": "Qu", "phonetic_en": "[koo]", "phonetic_tr": "[ku]", "example": "Questo" },
    "R": { "name": "Erre", "phonetic_en": "[ER-reh] (rolled r)", "phonetic_tr": "[erre] (titrek r)", "example": "Roma" },
    "S": { "name": "Esse", "phonetic_en": "[ES-seh]", "phonetic_tr": "[esse]", "example": "Sole" },
    "T": { "name": "Ti", "phonetic_en": "[tee]", "phonetic_tr": "[ti]", "example": "Tempo" },
    "U": { "name": "U", "phonetic_en": "[oo]", "phonetic_tr": "[u]", "example": "Uomo" },
    "V": { "name": "Vu / Vi", "phonetic_en": "[voo / vee]", "phonetic_tr": "[vu / vi]", "example": "Vino" },
    "Z": { "name": "Zeta", "phonetic_en": "[DZEH-tah / TSEH-tah]", "phonetic_tr": "[dzeta / tseta]", "example": "Pizza" }
  },
  "russian": {
    "А": { "name": "А", "phonetic_en": "[ah]", "phonetic_tr": "[a]", "example": "Анна" },
    "Б": { "name": "Бэ", "phonetic_en": "[beh]", "phonetic_tr": "[be]", "example": "Брат" },
    "В": { "name": "Вэ", "phonetic_en": "[veh]", "phonetic_tr": "[ve]", "example": "Вода" },
    "Г": { "name": "Гэ", "phonetic_en": "[geh]", "phonetic_tr": "[ge]", "example": "Город" },
    "Д": { "name": "Дэ", "phonetic_en": "[deh]", "phonetic_tr": "[de]", "example": "Дом" },
    "Е": { "name": "Е", "phonetic_en": "[yeh]", "phonetic_tr": "[ye]", "example": "Еда" },
    "Ё": { "name": "Ё", "phonetic_en": "[yoh]", "phonetic_tr": "[yo]", "example": "Ёлка" },
    "Ж": { "name": "Жэ", "phonetic_en": "[zheh]", "phonetic_tr": "[je]", "example": "Жизнь" },
    "З": { "name": "Зэ", "phonetic_en": "[zeh]", "phonetic_tr": "[ze]", "example": "Зима" },
    "И": { "name": "И", "phonetic_en": "[ee]", "phonetic_tr": "[i]", "example": "Имя" },
    "Й": { "name": "И краткое", "phonetic_en": "[ee KRAHT-koy-eh]", "phonetic_tr": "[kısa i]", "example": "Чай" },
    "К": { "name": "Ка", "phonetic_en": "[kah]", "phonetic_tr": "[ka]", "example": "Книга" },
    "Л": { "name": "Эль", "phonetic_en": "[el]", "phonetic_tr": "[el]", "example": "Любовь" },
    "М": { "name": "Эм", "phonetic_en": "[em]", "phonetic_tr": "[em]", "example": "Мама" },
    "Н": { "name": "Эн", "phonetic_en": "[en]", "phonetic_tr": "[en]", "example": "Ночь" },
    "О": { "name": "О", "phonetic_en": "[oh]", "phonetic_tr": "[o]", "example": "Окно" },
    "П": { "name": "Пэ", "phonetic_en": "[peh]", "phonetic_tr": "[pe]", "example": "Папа" },
    "Р": { "name": "Эр", "phonetic_en": "[er]", "phonetic_tr": "[er]", "example": "Россия" },
    "С": { "name": "Эс", "phonetic_en": "[es]", "phonetic_tr": "[es]", "example": "Солнце" },
    "Т": { "name": "Тэ", "phonetic_en": "[teh]", "phonetic_tr": "[te]", "example": "Театр" },
    "У": { "name": "У", "phonetic_en": "[oo]", "phonetic_tr": "[u]", "example": "Утро" },
    "Ф": { "name": "Эф", "phonetic_en": "[ef]", "phonetic_tr": "[ef]", "example": "Фото" },
    "Х": { "name": "Ха", "phonetic_en": "[khah]", "phonetic_tr": "[ha]", "example": "Хлеб" },
    "Ц": { "name": "Цэ", "phonetic_en": "[tseh]", "phonetic_tr": "[tse]", "example": "Центр" },
    "Ч": { "name": "Че", "phonetic_en": "[cheh]", "phonetic_tr": "[çe]", "example": "Час" },
    "Ш": { "name": "Ша", "phonetic_en": "[shah]", "phonetic_tr": "[şa]", "example": "Школа" },
    "Щ": { "name": "Ща", "phonetic_en": "[shchah]", "phonetic_tr": "[şça]", "example": "Щи" },
    "Ъ": { "name": "Твёрдый знак", "phonetic_en": "[hard sign]", "phonetic_tr": "[sert işaret]", "example": "Объект" },
    "Ы": { "name": "Ы", "phonetic_en": "[ih / uh]", "phonetic_tr": "[ı]", "example": "Мы" },
    "Ь": { "name": "Мягкий знак", "phonetic_en": "[soft sign]", "phonetic_tr": "[yumuşatma]", "example": "День" },
    "Э": { "name": "Э", "phonetic_en": "[eh]", "phonetic_tr": "[e]", "example": "Это" },
    "Ю": { "name": "Ю", "phonetic_en": "[yoo]", "phonetic_tr": "[yu]", "example": "Юг" },
    "Я": { "name": "Я", "phonetic_en": "[yah]", "phonetic_tr": "[ya]", "example": "Яблоко" }
  },
  "turkish": {
    "A": { "name": "A", "phonetic_en": "[ah]", "phonetic_tr": "[a]", "example": "Anne" },
    "B": { "name": "Be", "phonetic_en": "[beh]", "phonetic_tr": "[be]", "example": "Baba" },
    "C": { "name": "Ce", "phonetic_en": "[jeh]", "phonetic_tr": "[ce]", "example": "Cam" },
    "Ç": { "name": "Çe", "phonetic_en": "[cheh]", "phonetic_tr": "[çe]", "example": "Çay" },
    "D": { "name": "De", "phonetic_en": "[deh]", "phonetic_tr": "[de]", "example": "Dede" },
    "E": { "name": "E", "phonetic_en": "[eh]", "phonetic_tr": "[e]", "example": "Elma" },
    "F": { "name": "Fe", "phonetic_en": "[feh]", "phonetic_tr": "[fe]", "example": "Fincan" },
    "G": { "name": "Ge", "phonetic_en": "[geh]", "phonetic_tr": "[ge]", "example": "Güneş" },
    "Ğ": { "name": "Yumuşak Ge", "phonetic_en": "[lengthens vowel]", "phonetic_tr": "[yumuşak ge] (uzatır)", "example": "Ağaç" },
    "H": { "name": "He", "phonetic_en": "[heh]", "phonetic_tr": "[he]", "example": "Halı" },
    "I": { "name": "I", "phonetic_en": "[uh] (dotless i)", "phonetic_tr": "[ı] (noktasız ı)", "example": "Işık" },
    "İ": { "name": "İ", "phonetic_en": "[ee] (dotted i)", "phonetic_tr": "[i] (noktalı i)", "example": "İncir" },
    "J": { "name": "Je", "phonetic_en": "[zheh]", "phonetic_tr": "[je]", "example": "Jeton" },
    "K": { "name": "Ke", "phonetic_en": "[keh]", "phonetic_tr": "[ke]", "example": "Kitap" },
    "L": { "name": "Le", "phonetic_en": "[leh]", "phonetic_tr": "[le]", "example": "Limon" },
    "M": { "name": "Me", "phonetic_en": "[meh]", "phonetic_tr": "[me]", "example": "Masa" },
    "N": { "name": "Ne", "phonetic_en": "[neh]", "phonetic_tr": "[ne]", "example": "Nane" },
    "O": { "name": "O", "phonetic_en": "[oh]", "phonetic_tr": "[o]", "example": "Okul" },
    "Ö": { "name": "Ö", "phonetic_en": "[oe]", "phonetic_tr": "[ö]", "example": "Ördek" },
    "P": { "name": "Pe", "phonetic_en": "[peh]", "phonetic_tr": "[pe]", "example": "Para" },
    "R": { "name": "Re", "phonetic_en": "[reh]", "phonetic_tr": "[re]", "example": "Radyo" },
    "S": { "name": "Se", "phonetic_en": "[seh]", "phonetic_tr": "[se]", "example": "Su" },
    "Ş": { "name": "Şe", "phonetic_en": "[sheh]", "phonetic_tr": "[şe]", "example": "Şeker" },
    "T": { "name": "Te", "phonetic_en": "[teh]", "phonetic_tr": "[te]", "example": "Top" },
    "U": { "name": "U", "phonetic_en": "[oo]", "phonetic_tr": "[u]", "example": "Uçak" },
    "Ü": { "name": "Ü", "phonetic_en": "[ew]", "phonetic_tr": "[ü]", "example": "Üzüm" },
    "V": { "name": "Ve", "phonetic_en": "[veh]", "phonetic_tr": "[ve]", "example": "Vazo" },
    "Y": { "name": "Ye", "phonetic_en": "[yeh]", "phonetic_tr": "[ye]", "example": "Yol" },
    "Z": { "name": "Ze", "phonetic_en": "[zeh]", "phonetic_tr": "[ze]", "example": "Zeytin" }
  },
  "english": {
    "A": { "name": "A", "phonetic_en": "[ay]", "phonetic_tr": "[ey]", "example": "Apple" },
    "B": { "name": "B", "phonetic_en": "[bee]", "phonetic_tr": "[bi]", "example": "Book" },
    "C": { "name": "C", "phonetic_en": "[see]", "phonetic_tr": "[si]", "example": "Cat" },
    "D": { "name": "D", "phonetic_en": "[dee]", "phonetic_tr": "[di]", "example": "Door" },
    "E": { "name": "E", "phonetic_en": "[ee]", "phonetic_tr": "[i]", "example": "Elephant" },
    "F": { "name": "F", "phonetic_en": "[eff]", "phonetic_tr": "[ef]", "example": "Fish" },
    "G": { "name": "G", "phonetic_en": "[jee]", "phonetic_tr": "[ci]", "example": "Green" },
    "H": { "name": "H", "phonetic_en": "[aych]", "phonetic_tr": "[eyç]", "example": "House" },
    "I": { "name": "I", "phonetic_en": "[eye]", "phonetic_tr": "[ay]", "example": "Island" },
    "J": { "name": "J", "phonetic_en": "[jay]", "phonetic_tr": "[cey]", "example": "Juice" },
    "K": { "name": "K", "phonetic_en": "[kay]", "phonetic_tr": "[key]", "example": "Key" },
    "L": { "name": "L", "phonetic_en": "[ell]", "phonetic_tr": "[el]", "example": "Lion" },
    "M": { "name": "M", "phonetic_en": "[emm]", "phonetic_tr": "[em]", "example": "Moon" },
    "N": { "name": "N", "phonetic_en": "[enn]", "phonetic_tr": "[en]", "example": "Night" },
    "O": { "name": "O", "phonetic_en": "[oh]", "phonetic_tr": "[o]", "example": "Orange" },
    "P": { "name": "P", "phonetic_en": "[pee]", "phonetic_tr": "[pi]", "example": "Pen" },
    "Q": { "name": "Q", "phonetic_en": "[kyoo]", "phonetic_tr": "[kyu]", "example": "Queen" },
    "R": { "name": "R", "phonetic_en": "[ahr]", "phonetic_tr": "[ar]", "example": "Rain" },
    "S": { "name": "S", "phonetic_en": "[ess]", "phonetic_tr": "[es]", "example": "Sun" },
    "T": { "name": "T", "phonetic_en": "[tee]", "phonetic_tr": "[ti]", "example": "Table" },
    "U": { "name": "U", "phonetic_en": "[yoo]", "phonetic_tr": "[yu]", "example": "Umbrella" },
    "V": { "name": "V", "phonetic_en": "[vee]", "phonetic_tr": "[vi]", "example": "Voice" },
    "W": { "name": "W", "phonetic_en": "[DUB-uhl-yoo]", "phonetic_tr": "[dabılyu]", "example": "Water" },
    "X": { "name": "X", "phonetic_en": "[eks]", "phonetic_tr": "[eks]", "example": "Box" },
    "Y": { "name": "Y", "phonetic_en": "[wye]", "phonetic_tr": "[vay]", "example": "Yellow" },
    "Z": { "name": "Z", "phonetic_en": "[zee / zed]", "phonetic_tr": "[zi / zed]", "example": "Zoo" }
  }
};

function extractBaseLetter(str) {
  if (!str || typeof str !== 'string') return '';
  const s = str.trim();
  const letters = s.replace(/[^a-zA-ZñÑáéíóúüÁÉÍÓÚÜ]/g, '');
  if (!letters) return '';
  const u = letters.toUpperCase();
  if (u === 'CH' || u === 'CHCH') return 'CH';
  if (u === 'LL' || u === 'LLLL') return 'LL';
  if (u === 'RR' || u === 'RRRR') return 'RR';
  if (new Set(u).size === 1 && u.length <= 4) return u[0];
  const firstPart = s.split(/[\s,/-]+/)[0].toUpperCase();
  const cleanP = firstPart.replace(/[^a-zA-ZñÑáéíóúüÁÉÍÓÚÜ]/g, '');
  if (cleanP === 'CH' || cleanP === 'LL' || cleanP === 'RR' || (cleanP.length === 1 && cleanP in (ALPHABET_PHONETICS_MAP['spanish'] || {}))) {
    return cleanP;
  }
  return u.slice(0, 2);
}

function isLetterLike(str) {
  if (!str || typeof str !== 'string') return false;
  const s = str.trim();
  if (s.length === 1 && !/[\u4e00-\u9fff]/.test(s)) return true;
  const clean = s.replace(/[^a-zA-ZñÑáéíóúüÁÉÍÓÚÜ]/g, '');
  if (!clean) return false;
  const u = clean.toUpperCase();
  if (u === 'CH' || u === 'CHCH' || u === 'LL' || u === 'LLLL' || u === 'RR' || u === 'RRRR') return true;
  if (clean.length <= 4 && new Set(clean.toLowerCase()).size === 1) return true;
  if (/^(ch|ll|rr)$/i.test(s)) return true;
  return false;
}

function sanitizeEnglishExplanation(text, term = '') {
  if (!text || typeof text !== 'string') return text;
  let s = text.trim();

  // If term is an alphabet letter, check canonical explanation
  if (term && isLetterLike(term)) {
    const baseL = extractBaseLetter(term);
    const phon = getClientLetterPhonetics('spanish', baseL);
    if (phon && phon.explanation_en) {
      if (/[çğıöşüÇĞİÖŞÜ]/.test(s) || /\b(turkish|türkçe|türkçedeki|turkcedeki)\b/i.test(s)) {
        return phon.explanation_en;
      }
    }
  }

  // Regex replacements for English explanations that refer to Turkish:
  s = s.replace(/like\s+(?:the\s+)?(?:sound\s+of\s+)?(?:['"]?([a-zA-Z])['"]?\s+)?(?:sound\s+)?in\s+Turkish/gi, (m, char) => {
    if (char) {
      const c = char.toLowerCase();
      if (c === 'a') return "like the 'a' in 'father'";
      if (c === 'b') return "like the 'b' in 'boy'";
      if (c === 'e') return "like the 'e' in 'bed'";
      if (c === 'i') return "like the 'ee' in 'see'";
      if (c === 'o') return "like the 'o' in 'for'";
      if (c === 'u') return "like the 'oo' in 'moon'";
      if (c === 'r') return "like a soft tap";
      return `like '${char}' in English`;
    }
    return "clearly and distinctly";
  });

  s = s.replace(/similar\s+to\s+(?:the\s+)?(?:Turkish\s+)?['"]?([a-zA-Z])['"]?(?:\s+sound)?(?:\s+in\s+Turkish)?/gi, (m, char) => {
    const c = (char || '').toLowerCase();
    if (c === 'a') return "similar to the 'a' in 'father'";
    if (c === 'b') return "similar to the 'b' in 'boy'";
    if (c === 'e') return "similar to the 'e' in 'bed'";
    if (c === 'i') return "similar to the 'ee' in 'see'";
    if (c === 'o') return "similar to the 'o' in 'for'";
    if (c === 'u') return "similar to the 'oo' in 'moon'";
    return "clear and distinct";
  });

  s = s.replace(/\b(?:as|just\s+like|like)\s+in\s+Turkish\b/gi, "clean and distinct");
  s = s.replace(/\bin\s+Turkish\b/gi, "in standard pronunciation");
  s = s.replace(/\bTurkish\s+sound\b/gi, "clear phonetic sound");

  return s;
}

function getClientLetterPhonetics(lang, letter) {
  if (!letter) return null;
  const lKey = (lang || '').toLowerCase().trim();
  const rawTarget = letter.trim().toUpperCase();
  const baseTarget = extractBaseLetter(letter);
  const targets = Array.from(new Set([rawTarget, baseTarget])).filter(Boolean);

  for (const [k, dict] of Object.entries(ALPHABET_PHONETICS_MAP)) {
    if (lKey.includes(k)) {
      for (const t of targets) {
        if (dict[t]) return dict[t];
      }
    }
  }
  // Fallback: check Spanish or default
  for (const t of targets) {
    if (ALPHABET_PHONETICS_MAP['spanish'] && ALPHABET_PHONETICS_MAP['spanish'][t]) {
      return ALPHABET_PHONETICS_MAP['spanish'][t];
    }
  }
  return null;
}

const FRONTEND_VOCAB_EXAMPLE_BANK = {
  "spanish": {
    "leer": {
      "example": "Leo un libro fascinante cada noche.",
      "example_en": "I read a fascinating book every night.",
      "example_tr": "Her gece sürükleyici bir kitap okurum.",
      "tip_en": "Irregular gerund: 'leyendo'. Common phrase: 'leer en voz alta' (read aloud).",
      "tip_tr": "Ulaç hali kuralsızdır: 'leyendo'. Sık kullanılan kalıp: 'leer en voz alta' (sesli okumak)."
    },
    "escribir": {
      "example": "Ella escribe un diario todos los días.",
      "example_en": "She writes in a diary every day.",
      "example_tr": "O her gün günlük yazar.",
      "tip_en": "Past participle is irregular: 'escrito' (written).",
      "tip_tr": "Geçmiş zaman sıfat-fiili kuralsızdır: 'escrito' (yazılmış)."
    },
    "jugar": {
      "example": "Jugamos al fútbol los fines de semana.",
      "example_en": "We play soccer on weekends.",
      "example_tr": "Hafta sonları futbol oynarız.",
      "tip_en": "Stem-changing verb (u -> ue). Always takes preposition 'a': 'jugar al fútbol'.",
      "tip_tr": "Kök değişimi yapar (u -> ue). Sporlarda mutlaka 'a' edatı alır: 'jugar al fútbol'."
    },
    "nadar": {
      "example": "Nado en la piscina olímpica cada sábado.",
      "example_en": "I swim in the Olympic pool every Saturday.",
      "example_tr": "Her cumartesi olimpik havuzda yüzerim.",
      "tip_en": "Regular -ar verb. Pair with 'en': 'nadar en el mar' (swim in the sea).",
      "tip_tr": "Düzenli -ar fiilidir. 'en' edatıyla kullanılır: 'nadar en el mar' (denizde yüzmek)."
    },
    "dibujar": {
      "example": "Me gusta dibujar paisajes a lápiz.",
      "example_en": "I like drawing landscapes in pencil.",
      "example_tr": "Karakalemle manzara çizmeyi severim.",
      "tip_en": "The noun form is 'el dibujo' (drawing/sketch).",
      "tip_tr": "İsim formu 'el dibujo' (çizim/resim) şeklindedir."
    },
    "cocinar": {
      "example": "Mi padre cocina una paella deliciosa.",
      "example_en": "My father cooks a delicious paella.",
      "example_tr": "Babam çok lezzetli bir paella pişirir.",
      "tip_en": "Related to 'la cocina' (the kitchen).",
      "tip_tr": "'La cocina' (mutfak) sözcüğüyle aynı köktendir."
    },
    "viajar": {
      "example": "Quiero viajar por todo el mundo.",
      "example_en": "I want to travel all over the world.",
      "example_tr": "Bütün dünyayı gezmek istiyorum.",
      "tip_en": "Transport requires 'en': 'viajar en tren / en avión'.",
      "tip_tr": "Ulaşım araçlarında 'en' edatı kullanılır: 'viajar en tren / en avión'."
    },
    "bailar": {
      "example": "Ellos bailan salsa los viernes por la noche.",
      "example_en": "They dance salsa on Friday nights.",
      "example_tr": "Cuma geceleri salsa dansı yaparlar.",
      "tip_en": "Common phrase: 'bailar con' (dance with someone).",
      "tip_tr": "'Bailar con' (biriyle dans etmek) yapısıyla sık kullanılır."
    },
    "cantar": {
      "example": "Ella canta muy bien en el coro de la escuela.",
      "example_en": "She sings very well in the school choir.",
      "example_tr": "Okul korosunda çok güzel şarkı söyler.",
      "tip_en": "The noun is 'la canción' (the song).",
      "tip_tr": "İsim formu 'la canción' (şarkı) şeklindedir."
    },
    "escuchar musica": {
      "example": "Escucho música relajante mientras estudio.",
      "example_en": "I listen to relaxing music while studying.",
      "example_tr": "Ders çalışırken dinlendirici müzik dinlerim.",
      "tip_en": "No preposition needed for object: 'escuchar música'.",
      "tip_tr": "Nesne alırken araya edat almaz: 'escuchar música'."
    },
    "ver peliculas": {
      "example": "Los domingos vemos películas en casa.",
      "example_en": "On Sundays we watch movies at home.",
      "example_tr": "Pazar günleri evde film izleriz.",
      "tip_en": "Irregular first-person present: 'yo veo'.",
      "tip_tr": "'Ver' fiilinin ben çekimi kuralsızdır: 'yo veo'."
    },
    "hacer ejercicio": {
      "example": "Hago ejercicio en el parque todas las mañanas.",
      "example_en": "I exercise in the park every morning.",
      "example_tr": "Her sabah parkta egzersiz yaparım.",
      "tip_en": "First-person present is irregular: 'yo hago'.",
      "tip_tr": "'Hacer' fiilinin şimdiki zaman 1. şahsı kuralsızdır: 'yo hago'."
    },
    "correr": {
      "example": "Corro cinco kilómetros cada mañana.",
      "example_en": "I run five kilometers every morning.",
      "example_tr": "Her sabah beş kilometre koşarım.",
      "tip_en": "Regular -er verb.",
      "tip_tr": "Düzenli -er fiilidir."
    },
    "hobi": {
      "example": "¿Cuál es tu pasatiempo favorito?",
      "example_en": "What is your favorite hobby?",
      "example_tr": "En sevdiğin hobi nedir?",
      "tip_en": "Native Spanish term is 'el pasatiempo' (pasar + tiempo).",
      "tip_tr": "İspanyolcada özgün karşılığı 'el pasatiempo' (vakit geçirme) sözcüğüdür."
    },
    "pasatiempo": {
      "example": "La fotografía es mi pasatiempo principal.",
      "example_en": "Photography is my main hobby.",
      "example_tr": "Fotoğrafçılık benim başlıca hobimdir.",
      "tip_en": "Compound word: 'pasar' (spend) + 'tiempo' (time). Plural: 'los pasatiempos'.",
      "tip_tr": "'Pasar' (geçirmek) ve 'tiempo' (zaman) birleşimidir. Çoğulu: 'los pasatiempos'."
    }
  }
};

function getClientVocabExample(lang, term) {
  if (!term) return null;
  const lKey = (lang || '').toLowerCase().trim();
  const norm = normalizeConceptStr(term);
  for (const [k, dict] of Object.entries(FRONTEND_VOCAB_EXAMPLE_BANK)) {
    if (lKey.includes(k)) {
      if (dict[norm]) return dict[norm];
      for (const [w, entry] of Object.entries(dict)) {
        if (normalizeConceptStr(w) === norm) return entry;
      }
    }
  }
  // Global fallback in Spanish if term matches
  if (FRONTEND_VOCAB_EXAMPLE_BANK['spanish'][norm]) return FRONTEND_VOCAB_EXAMPLE_BANK['spanish'][norm];
  return null;
}



function healTurkishSyntax(s) {
  if (!s || typeof s !== 'string') return s;
  
  // 1. Concessive clause healing:
  // Transforms unnatural machine calques like "Her ne kadar çok meşguldü, yine de..."
  // into natural authentic Turkish "Her ne kadar çok meşgul olsa da, yine de..."
  const concessivePat = /\b(her\s+ne\s+kadar\s+(?:.*?\s+)?)([\p{L}]+?)(?:y(?:dı|di|du|dü)|dı|di|du|dü|tı|ti|tu|tü)(,)?(?=\s+(?:yine\s+de|ancak|fakat|hâlâ|hala|ama)|\s+[\p{L}])/giu;
  s = s.replace(concessivePat, (match, prefix, stem, comma) => {
    return prefix + stem + ' olsa da' + (comma || '');
  });

  // Clean missing 'da/de' after 'olsa' in 'Her ne kadar ... olsa,'
  s = s.replace(/\b(her\s+ne\s+kadar\s+.*?)\s+olsa(?!\s+da|\s+de)(,)?/giu, '$1 olsa da$2');

  // 2. Idiomatic collocations & anti-calques
  const calques = [
    [/\bzaman\s+yapmak\b/giu, 'vakit ayırmak'],
    [/\bzaman\s+yaptı\b/giu, 'vakit ayırdı'],
    [/\bzaman\s+yapıyor\b/giu, 'vakit ayırıyor'],
    [/\bzaman\s+yapacağız\b/giu, 'vakit ayıracağız'],
    [/\banlam\s+yapmak\b/giu, 'mantıklı gelmek'],
    [/\banlam\s+yapmıyor\b/giu, 'mantıklı gelmiyor'],
    [/\banlam\s+yapıyor\b/giu, 'mantıklı geliyor'],
    [/\bdikkat\s+ödemek\b/giu, 'dikkat etmek'],
    [/\bdikkat\s+ödeyin\b/giu, 'dikkat edin'],
    [/\bbir\s+bakış\s+almak\b/giu, 'göz atmak'],
    [/\bbir\s+duş\s+almak\b/giu, 'duş almak'],
    [/\bbanyo\s+almak\b/giu, 'banyo yapmak'],
    [/\bbir\s+karar\s+yapmak\b/giu, 'karar vermek'],
    [/\bkarar\s+yapmak\b/giu, 'karar vermek'],
    [/\biyi\s+öğleden\s+sonralar\b/giu, 'Tünaydın'],
    [/\biyi\s+öğleden\s+sonra\b/giu, 'Tünaydın'],
    [/\böğleden\s+sonralar\b/giu, 'Tünaydın']
  ];
  for (const [re, repl] of calques) {
    s = s.replace(re, repl);
  }

  // 3. Typo & calque healer: doktar -> doktor with vowel harmony
  s = s.replace(/\bdoktar(sınız|siniz|sın|sin|ım|im|ız|iz|dır|dir|lar|ler|[a-zçğıöşü]+)?\b/giu, (match, suffix) => {
    const isCap = match[0] === match[0].toUpperCase() && match[0] !== match[0].toLowerCase();
    const prefix = isCap ? 'Doktor' : 'doktor';
    if (!suffix) return prefix;
    const sLow = suffix.toLowerCase();
    const map = {
      'sın': 'sun', 'sin': 'sun',
      'sınız': 'sunuz', 'siniz': 'sunuz',
      'ım': 'um', 'im': 'um',
      'ız': 'uz', 'iz': 'uz',
      'dır': 'dur', 'dir': 'dur',
      'lar': 'lar', 'ler': 'lar',
      'a': 'a', 'e': 'a',
      'dan': 'dan', 'den': 'dan',
      'ı': 'u', 'i': 'u',
      'un': 'un', 'in': 'un'
    };
    return prefix + (map[sLow] || sLow);
  });

  s = humanizeTurkishExplanation(s);
  return s;
}

function humanizeTurkishExplanation(s) {
  if (!s || typeof s !== 'string') return s;

  let res = s;

  // 1. "X terimini/kelimesini/sözcüğünü ... ifade etmek için kullanın" -> "... tanımlar;"
  res = res.replace(/(?:'[^']+'|"[^"]+"|[a-zçğıöşüA-ZÇĞİÖŞÜ0-9\s'-]+?)\s+(?:terimini|kelimesini|sözcüğünü|ifadesini)\s*,?\s*(.+?)\s+(?:ifade\s+etmek\s+için\s+kullanın|ifade\s+ederken\s+kullanın|için\s+kullanın)\.?/giu, (match, topic) => {
    let clean = topic.trim().replace(/^,\s*/, '');
    clean = clean.charAt(0).toUpperCase() + clean.slice(1);
    return `${clean} tanımlar;`;
  });

  // 2. "Bu terimleri / Bu kelimeleri / Bu sıfatları / Bunları ... ifade etmek için kullanın"
  res = res.replace(/\b(?:bu\s+(?:terimleri|kelimeleri|sıfatları|ifadeleri)|bunları)\s*,?\s*(.+?)\s+(?:ifade\s+etmek\s+için\s+kullanın|için\s+kullanın)\.?/giu, (match, topic) => {
    let clean = topic.trim().replace(/^,\s*/, '');
    clean = clean.charAt(0).toUpperCase() + clean.slice(1);
    return `${clean} belirtirken kullanılır.`;
  });

  // 3. Standalone "... ifade etmek için kullanın" -> "... belirtirken kullanılır."
  res = res.replace(/([^.]+?)\s+ifade\s+etmek\s+için\s+kullanın\.?/giu, (match, topic) => {
    let clean = topic.trim().replace(/^,\s*/, '');
    clean = clean.charAt(0).toUpperCase() + clean.slice(1);
    return `${clean} belirtirken kullanılır.`;
  });

  // 4. "Bu terim/kelime/sözcük, ... ifade eder. Günlük konuşmalarda sıkça kullanılır."
  res = res.replace(/\bbu\s+(?:terim|kelime|sözcük),?\s+([^.]+?)\s+ifade\s+eder\.?\s*(?:günlük\s+konuşmalarda\s+sıkça\s+kullanılır\.?)?/giu, (match, topic) => {
    let clean = topic.trim().replace(/^,\s*/, '');
    clean = clean.charAt(0).toUpperCase() + clean.slice(1);
    return `${clean} tanımlar; günlük dilde ve pratik iletişimde yaygın olarak kullanılır. `;
  });

  // 5. "Bu terim/kelime, ... ifade etmek için kullanılır."
  res = res.replace(/\bbu\s+(?:terim|kelime|sözcük),?\s+([^.]+?)\s+ifade\s+etmek\s+için\s+kullanılır\.?/giu, (match, topic) => {
    let clean = topic.trim().replace(/^,\s*/, '');
    clean = clean.charAt(0).toUpperCase() + clean.slice(1);
    return `${clean} tanımlar;`;
  });

  // 6. "... kuralları ve düzenlemeleri anlamak için önemlidir"
  res = res.replace(/\bkuralları\s+ve\s+düzenlemeleri\s+anlamak\s+için\s+önemlidir\.?/giu, 'seyahat ve günlük iletişim kuralları açısından temel bir kavramdır.');

  // 7. "... için temel bir terimdir / ... için önemli bir terimdir"
  res = res.replace(/([^.]+?)\s+için\s+(?:temel|önemli)\s+bir\s+terimdir\.?/giu, (match, topic) => {
    let clean = topic.trim();
    return `${clean} açısından temel bir kavramdır.`;
  });

  // 8. "Toplu taşımada yaygın bir terimdir."
  res = res.replace(/\btoplu\s+taşımada\s+yaygın\s+bir\s+terimdir\.?/giu, 'Ulaşım ağlarında ve bilet işlemlerinde sıkça kullanılır.');

  // 9. "... durumunu ifade eder" / "... eylemini ifade eder" -> "... tanımlar."
  res = res.replace(/([a-zçğıöşüA-ZÇĞİÖŞÜ]+(leri|ları|i|ı|u|ü))\s+ifade\s+eder\.?/giu, '$1 tanımlar.');

  // Clean formatting artifacts
  res = res
    .replace(/;\s*;/g, ';')
    .replace(/;\s*\./g, '.')
    .replace(/\.\s*\./g, '.')
    .replace(/\s{2,}/g, ' ')
    .replace(/([.!?])(?=[a-zçğıöşüA-ZÇĞİÖŞÜ])/g, '$1 ')
    .replace(/;\s*(?=[A-ZÇĞİÖŞÜ])/g, '; ')
    .trim();

  return res;
}

let SANITY_EN_TO_TR = null;
let SANITY_TR_TO_EN = null;

const SANITY_TR_CHARS = /[çğıöşüÇĞİÖŞÜ]/;

const SANITY_CORE_EN_WORDS = new Set([
  'the', 'a', 'an', 'to', 'in', 'on', 'at', 'for', 'of', 'with', 'from',
  'stop', 'train', 'ticket', 'timetable', 'bus', 'passenger', 'station',
  'subway', 'airport', 'hotel', 'restaurant', 'car', 'street', 'city',
  'day', 'night', 'morning', 'afternoon', 'evening', 'hello', 'goodbye',
  'please', 'thank', 'thanks', 'welcome', 'yes', 'no', 'what', 'where',
  'how', 'who', 'why', 'when', 'my', 'your', 'his', 'her', 'our', 'their',
  'nice', 'meet', 'pleased', 'friend', 'family', 'brother', 'sister',
  'mother', 'father', 'son', 'daughter', 'water', 'bread', 'food',
  'drink', 'eat', 'see', 'go', 'come', 'have', 'do', 'make', 'take',
  'good', 'bad', 'big', 'small', 'new', 'old', 'cheap', 'expensive',
  'open', 'closed', 'left', 'right', 'near', 'far', 'help', 'time',
  'discussion', 'logic', 'conclusion', 'result', 'schedule', 'journey', 'platform',
  'doctor', 'physician', 'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh',
  'eighth', 'ninth', 'tenth', 'eleventh', 'twelfth', 'twentieth', 'thirtieth', 'hundredth',
  'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
  'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen',
  'nineteen', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety', 'hundred'
]);

const SANITY_CORE_TR_WORDS = new Set([
  'durak', 'tren', 'bilet', 'sefer', 'tablosu', 'otobüs', 'yolcu', 'istasyon',
  'metro', 'havalimanı', 'otel', 'restoran', 'araba', 'cadde', 'şehir',
  'gün', 'gece', 'sabah', 'öğleden', 'akşam', 'merhaba', 'hoşça', 'kal',
  'lütfen', 'teşekkür', 'teşekkürler', 'rica', 'ederim', 'evet', 'hayır',
  'ne', 'nerede', 'nasıl', 'kim', 'neden', 'ne zaman', 'benim', 'senin',
  'onun', 'bizim', 'sizin', 'onların', 'memnun', 'oldum', 'arkadaş',
  'aile', 'kardeş', 'kız', 'erkek', 'anne', 'baba', 'oğul', 'su', 'ekmek',
  'yemek', 'içmek', 'görmek', 'gitmek', 'gelmek', 'sahip', 'olmak',
  'yapmak', 'almak', 'iyi', 'kötü', 'büyük', 'küçük', 'yeni', 'eski', 'ucuz',
  'pahalı', 'açık', 'kapalı', 'sol', 'sağ', 'yakın', 'uzak', 'yardım', 'zaman',
  'vakit', 'tartışma', 'mantık', 'sonuç', 'görüşme', 'tarife', 'çizelge', 'peron',
  'doktor', 'hekim', 'birinci', 'ikinci', 'üçüncü', 'dördüncü', 'beşinci', 'altıncı',
  'yedinci', 'sekizinci', 'dokuzuncu', 'onuncu', 'yirminci', 'otuzuncu', 'yüzüncü',
  'sıfır', 'bir', 'iki', 'üç', 'dört', 'beş', 'altı', 'yedi', 'sekiz', 'dokuz', 'on',
  'on bir', 'on iki', 'on üç', 'on dört', 'on beş', 'on altı', 'on yedi', 'on sekiz',
  'on dokuz', 'yirmi', 'otuz', 'kırk', 'elli', 'altmış', 'yetmiş', 'seksen', 'doksan', 'yüz'
]);

function isSanityTR(s) {
  if (!s || typeof s !== 'string') return false;
  if (SANITY_TR_CHARS.test(s)) return true;
  const words = s.toLowerCase().trim().split(/\s+/);
  for (const w of words) {
    if (SANITY_CORE_TR_WORDS.has(w)) return true;
    if (SANITY_CORE_EN_WORDS.has(w)) return false;
  }
  return false;
}

function isSanityEN(s) {
  if (!s || typeof s !== 'string') return false;
  if (SANITY_TR_CHARS.test(s)) return false;
  const sLower = s.toLowerCase().trim();
  if (/\bharf(i)?\b/.test(sLower)) return false;
  const words = sLower.split(/\s+/);
  for (const w of words) {
    if (w === 'a' && words.length > 1) continue;
    if (SANITY_CORE_EN_WORDS.has(w)) return true;
    if (SANITY_CORE_TR_WORDS.has(w)) return false;
  }
  return false;
}

function registerSanityPair(a, b) {
  if (!a || !b) return;
  const strA = String(a).trim();
  const strB = String(b).trim();
  if (!strA || !strB || strA.toLowerCase() === strB.toLowerCase()) return;
  // Strictly block 'on' -> 'üzerinde' collision
  if (strA.toLowerCase() === 'on' && strB.toLowerCase() === 'üzerinde') return;
  if (strB.toLowerCase() === 'on' && strA.toLowerCase() === 'üzerinde') return;

  let en = '', tr = '';
  if (isSanityTR(strA) && !isSanityTR(strB)) {
    tr = strA; en = strB;
  } else if (isSanityTR(strB) && !isSanityTR(strA)) {
    en = strA; tr = strB;
  } else if (isSanityEN(strA) && !isSanityEN(strB)) {
    en = strA; tr = strB;
  } else if (isSanityEN(strB) && !isSanityEN(strA)) {
    tr = strA; en = strB;
  }

  if (en && tr) {
    SANITY_EN_TO_TR[en.toLowerCase()] = tr;
    SANITY_TR_TO_EN[tr.toLowerCase()] = en;
  }
}

function deinflectTurkishNoun(w) {
  if (!w || typeof w !== 'string') return '';
  let s = w.toLowerCase().trim();
  if (s.endsWith('ler') || s.endsWith('lar')) s = s.slice(0, -3);
  s = s.replace(/ğ([ıiuüae])$/, 'k');
  s = s.replace(/[ys]?([ıiuüae])$/, '');
  s = s.replace(/(?:d[ae]|d[ae]n|t[ae]|t[ae]n)$/, '');
  return s;
}

function initSanitizedBilingualDictionaries() {
  if (SANITY_EN_TO_TR && SANITY_TR_TO_EN) return;
  SANITY_EN_TO_TR = Object.create(null);
  SANITY_TR_TO_EN = Object.create(null);

  // 1. Foundational transport and core vocabulary pairs
  const FOUNDATIONAL_PAIRS = [
    ["stop", "durak"],
    ["bus stop", "otobüs durağı"],
    ["train", "tren"],
    ["ticket", "bilet"],
    ["timetable", "sefer tablosu"],
    ["schedule", "tarife"],
    ["bus", "otobüs"],
    ["passenger", "yolcu"],
    ["station", "istasyon"],
    ["subway", "metro"],
    ["airport", "havalimanı"],
    ["platform", "peron"],
    ["discussion", "tartışma"],
    ["logic", "mantık"],
    ["conclusion", "sonuç"],
    ["argument", "argüman"],
    ["pleased to meet you", "tanıştığıma memnun oldum"],
    ["nice to meet you", "memnun oldum"],
    ["doctor", "doktor"],
    ["physician", "hekim"],
    ["first", "birinci"],
    ["second", "ikinci"],
    ["third", "üçüncü"],
    ["fourth", "dördüncü"],
    ["fifth", "beşinci"],
    ["sixth", "altıncı"],
    ["seventh", "yedinci"],
    ["eighth", "sekizinci"],
    ["ninth", "dokuzuncu"],
    ["tenth", "onuncu"],
    ["eleventh", "on birinci"],
    ["twelfth", "on ikinci"],
    ["thirteenth", "on üçüncü"],
    ["fourteenth", "on dördüncü"],
    ["fifteenth", "on beşinci"],
    ["sixteenth", "on altıncı"],
    ["seventeenth", "on yedinci"],
    ["eighteenth", "on sekizinci"],
    ["nineteenth", "on dokuzuncu"],
    ["twentieth", "yirminci"],
    ["thirtieth", "otuzuncu"],
    ["fortieth", "kırkıncı"],
    ["fiftieth", "ellinci"],
    ["hundredth", "yüzüncü"],
    ["zero", "sıfır"], ["cero", "sıfır"],
    ["one", "bir"], ["uno", "bir"],
    ["two", "iki"], ["dos", "iki"],
    ["three", "üç"], ["tres", "üç"],
    ["four", "dört"], ["cuatro", "dört"],
    ["five", "beş"], ["cinco", "beş"],
    ["six", "altı"], ["seis", "altı"],
    ["seven", "yedi"], ["siete", "yedi"],
    ["eight", "sekiz"], ["ocho", "sekiz"],
    ["nine", "dokuz"], ["nueve", "dokuz"],
    ["ten", "on"], ["diez", "on"],
    ["eleven", "on bir"], ["once", "on bir"],
    ["twelve", "on iki"], ["doce", "on iki"],
    ["thirteen", "on üç"], ["trece", "on üç"],
    ["fourteen", "on dört"], ["catorce", "on dört"],
    ["fifteen", "on beş"], ["quince", "on beş"],
    ["sixteen", "on altı"], ["dieciséis", "on altı"],
    ["seventeen", "on yedi"], ["diecisiete", "on yedi"],
    ["eighteen", "on sekiz"], ["dieciocho", "on sekiz"],
    ["nineteen", "on dokuz"], ["diecinueve", "on dokuz"],
    ["twenty", "yirmi"], ["veinte", "yirmi"],
    ["thirty", "otuz"], ["treinta", "otuz"],
    ["forty", "kırk"], ["cuarenta", "kırk"],
    ["fifty", "elli"], ["cincuenta", "elli"],
    ["sixty", "altmış"], ["sesenta", "altmış"],
    ["seventy", "yetmiş"], ["setenta", "yetmiş"],
    ["eighty", "seksen"], ["ochenta", "seksen"],
    ["ninety", "doksan"], ["noventa", "doksan"],
    ["hundred", "yüz"], ["cien", "yüz"]
  ];
  for (const [e, t] of FOUNDATIONAL_PAIRS) registerSanityPair(e, t);

  // 2. Register VOCAB_PAIRS
  if (typeof VOCAB_PAIRS !== 'undefined' && Array.isArray(VOCAB_PAIRS)) {
    for (const [e, t] of VOCAB_PAIRS) registerSanityPair(e, t);
  }

  // 3. Register and sanitize VOCAB_MAP_EN_TR and VOCAB_MAP_TR_EN (re-routing polluted entries)
  const enTr = (typeof window !== 'undefined' && window.VOCAB_MAP_EN_TR) || {};
  const trEn = (typeof window !== 'undefined' && window.VOCAB_MAP_TR_EN) || {};
  for (const [k, v] of Object.entries(enTr)) registerSanityPair(k, v);
  for (const [k, v] of Object.entries(trEn)) registerSanityPair(k, v);
}

function translateOption(text, lang = currentLang) {
  if (!text) return '';
  const trimmed = text.trim();
  const lower = trimmed.toLowerCase();
  const isTr = (lang === 'tr');

  // Single characters / letters must NEVER be translated into pronouns (e.g. 'I' -> 'Ben' or 'o' -> 'she')
  if (trimmed.length <= 1) {
    return trimmed;
  }
  if (typeof SPANISH_LETTER_SPELLINGS !== 'undefined' && SPANISH_LETTER_SPELLINGS.has(lower)) {
    return trimmed;
  }

  // Absolute cardinal number & foundational protection (never allow 'on' -> 'üzerinde' or 'diez' -> 'üzerinde')
  const CARDINAL_NUM_MAP_TR = {
    'zero': 'sıfır', 'cero': 'sıfır', 'sıfır': 'sıfır',
    'one': 'bir', 'uno': 'bir', 'bir': 'bir',
    'two': 'iki', 'dos': 'iki', 'iki': 'iki',
    'three': 'üç', 'tres': 'üç', 'üç': 'üç',
    'four': 'dört', 'cuatro': 'dört', 'dört': 'dört',
    'five': 'beş', 'cinco': 'beş', 'beş': 'beş',
    'six': 'altı', 'seis': 'altı', 'altı': 'altı',
    'seven': 'yedi', 'siete': 'yedi', 'yedi': 'yedi',
    'eight': 'sekiz', 'ocho': 'sekiz', 'sekiz': 'sekiz',
    'nine': 'dokuz', 'nueve': 'dokuz', 'dokuz': 'dokuz',
    'ten': 'on', 'diez': 'on', 'on': 'on',
    'eleven': 'on bir', 'once': 'on bir', 'on bir': 'on bir',
    'twelve': 'on iki', 'doce': 'on iki', 'on iki': 'on iki',
    'thirteen': 'on üç', 'trece': 'on üç', 'on üç': 'on üç',
    'fourteen': 'on dört', 'catorce': 'on dört', 'on dört': 'on dört',
    'fifteen': 'on beş', 'quince': 'on beş', 'on beş': 'on beş',
    'sixteen': 'on altı', 'dieciséis': 'on altı', 'on altı': 'on altı',
    'seventeen': 'on yedi', 'diecisiete': 'on yedi', 'on yedi': 'on yedi',
    'eighteen': 'on sekiz', 'dieciocho': 'on sekiz', 'on sekiz': 'on sekiz',
    'nineteen': 'on dokuz', 'diecinueve': 'on dokuz', 'on dokuz': 'on dokuz',
    'twenty': 'yirmi', 'veinte': 'yirmi', 'yirmi': 'yirmi'
  };
  const CARDINAL_NUM_MAP_EN = {
    'cero': 'zero', 'sıfır': 'zero', 'zero': 'zero',
    'uno': 'one', 'bir': 'one', 'one': 'one',
    'dos': 'two', 'iki': 'two', 'two': 'two',
    'tres': 'three', 'üç': 'three', 'three': 'three',
    'cuatro': 'four', 'dört': 'four', 'four': 'four',
    'cinco': 'five', 'beş': 'five', 'five': 'five',
    'seis': 'six', 'altı': 'six', 'six': 'six',
    'siete': 'seven', 'yedi': 'seven', 'seven': 'seven',
    'ocho': 'eight', 'sekiz': 'eight', 'eight': 'eight',
    'nueve': 'nine', 'dokuz': 'nine', 'nine': 'nine',
    'diez': 'ten', 'on': 'ten', 'ten': 'ten',
    'once': 'eleven', 'on bir': 'eleven', 'eleven': 'eleven',
    'doce': 'twelve', 'on iki': 'twelve', 'twelve': 'twelve',
    'trece': 'thirteen', 'on üç': 'thirteen', 'thirteen': 'thirteen',
    'catorce': 'fourteen', 'on dört': 'fourteen', 'fourteen': 'fourteen',
    'quince': 'fifteen', 'on beş': 'fifteen', 'fifteen': 'fifteen',
    'dieciséis': 'sixteen', 'on altı': 'sixteen', 'sixteen': 'sixteen',
    'diecisiete': 'seventeen', 'on yedi': 'seventeen', 'seventeen': 'seventeen',
    'dieciocho': 'eighteen', 'on sekiz': 'eighteen', 'eighteen': 'eighteen',
    'diecinueve': 'nineteen', 'on dokuz': 'nineteen', 'nineteen': 'nineteen',
    'veinte': 'twenty', 'yirmi': 'twenty', 'twenty': 'twenty'
  };
  if (isTr && CARDINAL_NUM_MAP_TR[lower]) {
    const r = CARDINAL_NUM_MAP_TR[lower];
    return text.charAt(0) === text.charAt(0).toUpperCase() ? r.charAt(0).toUpperCase() + r.slice(1) : r;
  }
  if (!isTr && CARDINAL_NUM_MAP_EN[lower]) {
    const r = CARDINAL_NUM_MAP_EN[lower];
    return text.charAt(0) === text.charAt(0).toUpperCase() ? r.charAt(0).toUpperCase() + r.slice(1) : r;
  }

  // Pragmatic greetings & natural Turkish overrides
  if (lower === 'good afternoon' || lower === 'good afternoon.') {
    return isTr ? 'Tünaydın' : 'Good afternoon';
  }
  if (lower.includes('öğleden sonra') || lower.includes('ogleden sonra')) {
    return isTr ? 'Tünaydın' : 'Good afternoon';
  }
  if (lower === 'good morning' || lower === 'good morning.') {
    return isTr ? 'Günaydın' : 'Good morning';
  }
  if (lower === 'good evening' || lower === 'good evening.') {
    return isTr ? 'İyi akşamlar' : 'Good evening';
  }
  if (lower === 'good night' || lower === 'good night.') {
    return isTr ? 'İyi geceler' : 'Good night';
  }
  if (lower === 'nice to meet you' || lower === 'pleased to meet you') {
    return isTr ? 'Memnun oldum' : 'Nice to meet you';
  }

  initSanitizedBilingualDictionaries();

  if (isTr) {
    // Target is Turkish: STRICT DIRECTION ISOLATION (NEVER return English!)
    // Check if it is an inflected noun needing base lemma (e.g. durağı -> Durak)
    const deinflected = deinflectTurkishNoun(lower);
    if (deinflected && deinflected !== lower && SANITY_TR_TO_EN[deinflected]) {
      return deinflected.charAt(0).toUpperCase() + deinflected.slice(1);
    }
    // If text is already Turkish, return it
    if (SANITY_TR_CHARS.test(lower) || SANITY_TR_TO_EN[lower]) {
      return text;
    }
    // Translate from English
    if (SANITY_EN_TO_TR[lower]) return SANITY_EN_TO_TR[lower];
    // Check unambiguous VOCAB_PAIRS array
    if (typeof VOCAB_PAIRS !== 'undefined' && Array.isArray(VOCAB_PAIRS)) {
      for (const [en, tr] of VOCAB_PAIRS) {
        if (lower === en.toLowerCase()) return tr;
        if (lower === tr.toLowerCase()) return tr;
      }
    }
    return text;
  } else {
    // Target is English: STRICT DIRECTION ISOLATION (NEVER return Turkish!)
    // If text is already English, return it directly
    if (SANITY_EN_TO_TR[lower] && !SANITY_TR_CHARS.test(lower)) {
      return text;
    }
    // Translate from Turkish
    if (SANITY_TR_TO_EN[lower]) return SANITY_TR_TO_EN[lower];
    // Check Turkish noun case endings: -ı/-i/-u/-ü, -yı/-yi/-yu/-yü, -a/-e (e.g. durağı -> durak -> stop)
    const deinflected = deinflectTurkishNoun(lower);
    if (deinflected && SANITY_TR_TO_EN[deinflected]) {
      return SANITY_TR_TO_EN[deinflected];
    }
    // Check unambiguous VOCAB_PAIRS array
    if (typeof VOCAB_PAIRS !== 'undefined' && Array.isArray(VOCAB_PAIRS)) {
      for (const [en, tr] of VOCAB_PAIRS) {
        if (lower === tr.toLowerCase()) return en;
        if (lower === en.toLowerCase()) return en;
      }
    }
    return text;
  }
}

const PEDAGOGICAL_CONCEPT_EXPLANATIONS = {
  // Phonetics & Pronunciation
  "vowel": {
    en: "A core speech sound produced with an open vocal tract without air obstruction (A, E, I, O, U).",
    tr: "Ses yolunda bir engelle karşılaşmadan serbestçe çıkan temel sesler (A, E, I, İ, O, Ö, U, Ü)."
  },
  "consonant": {
    en: "A speech sound formed by obstructing or restricting airflow with lips, tongue, or teeth.",
    tr: "Dudak, dil veya dişlerin hava akımını kısmen veya tamamen engellemesiyle oluşan sesler."
  },
  "umlaut": {
    en: "A vowel sound modification marked by two dots (ä, ö, ü) that alters pronunciation.",
    tr: "Almancada ses değişimini gösteren iki noktalı özel harfler (ä, ö, ü)."
  },
  "sound": {
    en: "An individual spoken phonetic unit or letter pronunciation value.",
    tr: "Bir dildeki her bir işitilebilir ses veya fonetik konuşma birimi."
  },
  "syllable": {
    en: "A unit of spoken pronunciation formed by a single vowel sound, with or without consonants.",
    tr: "Ağzın tek bir nefes ve ses hamlesiyle çıkardığı ses veya ses öbeği."
  },
  "word": {
    en: "A single distinct, meaningful linguistic element used to form phrases and sentences.",
    tr: "Cümle kurmaya yarayan bağımsız ve anlamlı temel dil birimi."
  },
  "letter": {
    en: "A written character or symbol representing one or more speech sounds in an alphabet.",
    tr: "Dildeki bir sesi gösteren ve alfabeyi oluşturan yazılı işaret."
  },
  "alphabet": {
    en: "The complete standardized set of letters representing the sounds of a language.",
    tr: "Bir dildeki sesleri gösteren, belli bir sıraya göre dizilmiş harflerin tamamı."
  },
  "sentence": {
    en: "A grammatically complete set of words expressing a statement, question, or thought.",
    tr: "Bir duyguyu, düşünceyi veya durumu bildiren sözcük dizisi."
  },
  "language": {
    en: "A structured system of communication used by a community to express thoughts and ideas.",
    tr: "İnsanların duygu ve düşüncelerini aktarmak için kullandığı kurallı iletişim sistemi."
  },
  "accent": {
    en: "The vocal emphasis or pitch placed on a specific syllable within a word.",
    tr: "Bir kelimede belirli bir hecenin diğerlerine göre daha baskılı ve belirgin söylenmesi."
  },
  "stress": {
    en: "The prominent acoustic emphasis given to a syllable in spoken words.",
    tr: "Konuşurken bir heceye verilen belirgin ses vurgusu."
  },
  "intonation": {
    en: "The melodic rise and fall of vocal pitch across phrases and sentences.",
    tr: "Konuşurken ses perdesinin cümlenin anlamına göre alçalıp yükselmesi."
  },
  "pronunciation": {
    en: "The conventional articulation and audible speech production of words and sounds.",
    tr: "Bir dildeki ses ve kelimelerin ağızdan doğru ve anlaşılır biçimde sesletimi."
  },
  "diphthong": {
    en: "Two adjacent vowel sounds gliding together within the same syllable (e.g., ei, au, eu).",
    tr: "Tek bir hecede kesintisiz bir kaymayla birleşen iki sesli harf (ör. ei, au, eu)."
  },
  "hiatus": {
    en: "Two consecutive vowel sounds pronounced in separate, distinct syllables.",
    tr: "Yan yana gelen iki sesli harfin iki ayrı hecede bölünerek okunması."
  },
  "silent": {
    en: "A letter written in spelling but omitted from verbal pronunciation.",
    tr: "Yazıda yer alan fakat telaffuz edilirken sesletilmeyen harf."
  },
  "weak vowel": {
    en: "In Spanish, the closed vowels (I, U) that readily combine into diphthongs.",
    tr: "İspanyolcada diftong oluşturan dar sesli harfler (I, U)."
  },
  "strong vowel": {
    en: "In Spanish, open vowels (A, E, O) that form independent, separated syllables.",
    tr: "İspanyolcada bağımsız hece oluşturan açık sesli harfler (A, E, O)."
  },
  "accentuation": {
    en: "The rules governing where vocal stress and written accent marks fall in words.",
    tr: "Kelimelerdeki vurgu ve aksan işaretlerinin yerini belirleyen kurallar bütünü."
  },
  "rhythm": {
    en: "The beat, cadence, and timing pattern of spoken syllables in a language.",
    tr: "Konuşmadaki hecelerin ve vurguların oluşturduğu ahenkli ritim."
  },

  // Grammar & Parts of Speech
  "noun": {
    en: "A word identifying a person, place, physical object, or abstract concept.",
    tr: "Canlı veya cansız varlıkları, nesneleri ve kavramları adlandıran sözcük türü."
  },
  "verb": {
    en: "A word expressing an action, event, occurrence, or state of being.",
    tr: "Bir işi, oluşu, hareketi veya durumu zaman ve kişiye bağlayarak bildiren sözcük."
  },
  "adjective": {
    en: "A word describing or qualifying the qualities, state, or traits of a noun.",
    tr: "İsimlerin niteliklerini, durumlarını veya özelliklerini belirten sözcük."
  },
  "adverb": {
    en: "A word modifying a verb, adjective, or phrase (describing manner, time, or place).",
    tr: "Fiilleri, sıfatları veya diğer zarfları durum, zaman veya miktar yönünden niteleyen sözcük."
  },
  "pronoun": {
    en: "A word that substitutes for a noun or noun phrase (e.g., I, you, he, she, they).",
    tr: "İsmin yerini tutan ve onun yerine kullanılan sözcük (ben, sen, o, biz, siz, onlar)."
  },
  "article": {
    en: "A grammatical marker accompanying a noun to signal definiteness or grammatical gender.",
    tr: "İsmin önüne gelerek onun belirli mi yoksa belirsiz mi olduğunu gösteren dilbilgisi birimi."
  },
  "definite article": {
    en: "Specifies a particular, identifiable person or object (e.g., 'the', German 'der/die/das').",
    tr: "Bilinen veya belirli bir varlığı niteleyen tanımlık (Almanca 'der/die/das', İspanyolca 'el/la')."
  },
  "indefinite article": {
    en: "Refers to a non-specific or newly introduced person or object (e.g., 'a/an', 'ein/eine').",
    tr: "Herhangi bir varlığı genel olarak niteleyen tanımlık (Almanca 'ein/eine', İspanyolca 'un/una')."
  },
  "preposition": {
    en: "A word showing spatial, directional, temporal, or logical relationships (in, on, at).",
    tr: "Kelimeler arasında yön, yer, zaman veya ilgi ilişkisi kuran ilgeç."
  },
  "conjunction": {
    en: "A connecting word linking phrases, clauses, or coordinating elements (and, but, because).",
    tr: "Kelimeleri veya cümleleri birbirine bağlayan sözcük (ve, ama, çünkü)."
  },
  "gender": {
    en: "Grammatical categorization of nouns into classes such as masculine, feminine, or neuter.",
    tr: "Pek çok dilde isimlerin eril, dişil veya nötr olarak sınıflandırılması."
  },
  "masculine": {
    en: "Grammatical gender category marked with masculine articles (e.g., German 'der', Spanish 'el').",
    tr: "Eril cinsiyetteki isimler (Almanca 'der', İspanyolca 'el' artikeliyle kullanılır)."
  },
  "feminine": {
    en: "Grammatical gender category marked with feminine articles (e.g., German 'die', Spanish 'la').",
    tr: "Dişil cinsiyetteki isimler (Almanca 'die', İspanyolca 'la' artikeliyle kullanılır)."
  },
  "neuter": {
    en: "Grammatical gender category that is neither masculine nor feminine (e.g., German 'das').",
    tr: "Ne eril ne de dişil olan cinsiyet kategorisi (Almanca 'das' artikeliyle kullanılır)."
  },
  "singular": {
    en: "Grammatical form designating a single person, item, or concept.",
    tr: "Sadece tek bir varlığı veya kişiyi belirten sözcük biçimi."
  },
  "plural": {
    en: "Grammatical form designating more than one person, item, or concept.",
    tr: "Birden fazla varlığı veya kişiyi belirten sözcük biçimi."
  },
  "subject": {
    en: "The actor, person, or entity performing the verb or being described in a sentence.",
    tr: "Cümlede bildirilen işi yapan veya hakkında bilgi verilen temel öge."
  },
  "object": {
    en: "The person, item, or entity affected by or receiving the action of a verb.",
    tr: "Cümlede öznenin yaptığı işten etkilenen varlık veya öge."
  },
  "infinitive": {
    en: "The base, uninflected dictionary form of a verb before conjugation.",
    tr: "Fiilin kişi ve zaman eki almamış yalın sözlük hali (mastar)."
  },
  "conjugation": {
    en: "The inflection and ending changes of a verb corresponding to person, number, and tense.",
    tr: "Fiilin kişi, zaman ve kipe göre ek alarak değişmesi (fiil çekimi)."
  },
  "regular verb": {
    en: "A verb that adheres strictly to standard, predictable conjugation patterns.",
    tr: "Standart kurallara ve kalıplara uygun olarak çekimlenen düzenli fiil."
  },
  "irregular verb": {
    en: "A verb with idiosyncratic stem changes or non-standard conjugation endings.",
    tr: "Çekimlenirken kökü veya ekleri standart kuralların dışına çıkan düzensiz fiil."
  },
  "reflexive verb": {
    en: "A verb where the subject and the direct object are the same entity (acting on oneself).",
    tr: "Öznenin yaptığı işin yine özneye döndüğü dönüşlü fiil."
  },
  "modal verb": {
    en: "An auxiliary verb indicating permission, ability, obligation, or necessity.",
    tr: "Zorunluluk, izin, yetenek veya olasılık bildiren kip yardımcı fiili."
  },
  "cognate": {
    en: "A word sharing common ancestral origin, meaning, and spelling across languages.",
    tr: "Farklı dillerde ortak kökenden gelen, yazılışı ve anlamı birbirine çok benzeyen sözcük."
  },
  "false friend": {
    en: "A deceptive word that looks or sounds like a familiar word but carries a different meaning.",
    tr: "Yazılışı veya okunuşu tanıdık gelen ancak tamamen farklı anlama sahip yanıltıcı sözcük."
  },
  // Cases & Tenses
  "case": {
    en: "A grammatical category determining the grammatical role of a noun in a sentence.",
    tr: "İsmin cümlede üstlendiği dilbilgisel görevi belirleyen çekim hali."
  },
  "nominative": {
    en: "The base grammatical case identifying the subject of a sentence.",
    tr: "Cümlenin öznesi olan ismin ek almamış yalın hali."
  },
  "accusative": {
    en: "The case marking the direct object directly receiving the action of a transitive verb.",
    tr: "Geçişli fiilin doğrudan etkilediği nesneyi belirten -i hali."
  },
  "dative": {
    en: "The case marking the indirect recipient, beneficiary, or directional target of an action.",
    tr: "Eylemin yöneldiği veya yararlandığı dolaylı tümleci belirten -e hali."
  },
  "genitive": {
    en: "The case expressing possession, belonging, origin, or close relationship between nouns.",
    tr: "Aitlik, iyelik veya tamlama ilişkisi bildiren ilgi / tamlayan hali (-in)."
  },
  "tense": {
    en: "The grammatical inflection of a verb showing the time of an action relative to speaking.",
    tr: "Eylemin gerçekleştiği zaman dilimini belirten fiil çekim kategorisi."
  },
  "present tense": {
    en: "The verb tense used for present actions, habitual facts, and general truths.",
    tr: "Şu anda gerçekleşen veya genel geçer durumları bildiren şimdiki/geniş zaman."
  },
  "past tense": {
    en: "The verb tense expressing actions that occurred and completed before the present moment.",
    tr: "Geçmişte tamamlanmış veya yaşanmış olayları bildiren geçmiş zaman."
  },
  "future tense": {
    en: "The verb tense expressing actions that are expected to happen after the present time.",
    tr: "Gelecekte gerçekleşmesi beklenen veya planlanan eylemleri bildiren gelecek zaman."
  },
  "imperative": {
    en: "The grammatical mood used to express direct commands, instructions, or requests.",
    tr: "Doğrudan emir, talimat veya rica bildiren fiil kipi."
  },
  "subjunctive": {
    en: "The grammatical mood expressing wishes, doubts, hypotheticals, or possibilities.",
    tr: "Dilek, istek, şüphe, varsayım veya temenni bildiren kip biçimi."
  },
  "synonym": {
    en: "A word with identical or very similar meaning to another word in the same language.",
    tr: "Yazılışları farklı ancak anlamları aynı veya birbirine çok yakın olan sözcük."
  },
  "antonym": {
    en: "A word with opposite meaning to another word in the same language.",
    tr: "Anlamca birbiriyle çelişen ve karşıt anlam taşıyan sözcük."
  }
};

const CANONICAL_CONCEPT_NAMES = {
  vowel: { en: "Vowel", tr: "Ünlü" },
  consonant: { en: "Consonant", tr: "Ünsüz" },
  umlaut: { en: "Umlaut", tr: "İki Noktalı Ünlü (Umlaut)" },
  sound: { en: "Sound", tr: "Ses" },
  syllable: { en: "Syllable", tr: "Hece" },
  word: { en: "Word", tr: "Kelime" },
  letter: { en: "Letter", tr: "Harf" },
  alphabet: { en: "Alphabet", tr: "Alfabe" },
  sentence: { en: "Sentence", tr: "Cümle" },
  language: { en: "Language", tr: "Dil" },
  accent: { en: "Accent", tr: "Vurgu" },
  stress: { en: "Stress", tr: "Vurgu" },
  intonation: { en: "Intonation", tr: "Tonlama" },
  pronunciation: { en: "Pronunciation", tr: "Telaffuz" },
  diphthong: { en: "Diphthong", tr: "Diftong (Çift Ünlü)" },
  hiatus: { en: "Hiatus", tr: "Hiyat (Ayrı Ünlüler)" },
  silent: { en: "Silent Letter", tr: "Okunmayan Harf" },
  "weak vowel": { en: "Weak Vowel", tr: "Dar Ünlü" },
  "strong vowel": { en: "Strong Vowel", tr: "Açık Ünlü" },
  accentuation: { en: "Accentuation", tr: "Aksan Kuralları" },
  rhythm: { en: "Rhythm", tr: "Ritim" },
  noun: { en: "Noun", tr: "İsim" },
  verb: { en: "Verb", tr: "Fiil" },
  adjective: { en: "Adjective", tr: "Sıfat" },
  adverb: { en: "Adverb", tr: "Zarf" },
  pronoun: { en: "Pronoun", tr: "Zamir" },
  article: { en: "Article", tr: "Tanımlık (Artikel)" },
  "definite article": { en: "Definite Article", tr: "Belirli Tanımlık" },
  "indefinite article": { en: "Indefinite Article", tr: "Belirsiz Tanımlık" },
  preposition: { en: "Preposition", tr: "Edat" },
  conjunction: { en: "Conjunction", tr: "Bağlaç" },
  gender: { en: "Gender", tr: "Dilbilgisel Cinsiyet" },
  masculine: { en: "Masculine", tr: "Eril" },
  feminine: { en: "Feminine", tr: "Dişil" },
  neuter: { en: "Neuter", tr: "Nötr" },
  singular: { en: "Singular", tr: "Tekil" },
  plural: { en: "Plural", tr: "Çoğul" },
  subject: { en: "Subject", tr: "Özne" },
  object: { en: "Object", tr: "Nesne" },
  infinitive: { en: "Infinitive", tr: "Mastar" },
  conjugation: { en: "Conjugation", tr: "Fiil Çekimi" },
  "regular verb": { en: "Regular Verb", tr: "Düzenli Fiil" },
  "irregular verb": { en: "Irregular Verb", tr: "Düzensiz Fiil" },
  "reflexive verb": { en: "Reflexive Verb", tr: "Dönüşlü Fiil" },
  "modal verb": { en: "Modal Verb", tr: "Modal Yardımcı Fiil" },
  cognate: { en: "Cognate", tr: "Ortak Kökenli Sözcük" },
  "false friend": { en: "False Friend", tr: "Yanıltıcı Benzer" },
  case: { en: "Grammatical Case", tr: "İsmin Hali" },
  nominative: { en: "Nominative Case", tr: "Yalın Hal" },
  accusative: { en: "Accusative Case", tr: "Belirtme Hali (-i)" },
  dative: { en: "Dative Case", tr: "Yönelme Hali (-e)" },
  genitive: { en: "Genitive Case", tr: "İlgi / Tamlayan Hali (-in)" },
  tense: { en: "Tense", tr: "Zaman" },
  "present tense": { en: "Present Tense", tr: "Geniş / Şimdiki Zaman" },
  "past tense": { en: "Past Tense", tr: "Geçmiş Zaman" },
  "future tense": { en: "Future Tense", tr: "Gelecek Zaman" },
  imperative: { en: "Imperative", tr: "Emir Kipi" },
  subjunctive: { en: "Subjunctive", tr: "Dilek / İstek Kipi" },
  synonym: { en: "Synonym", tr: "Eş Anlamlı" },
  antonym: { en: "Antonym", tr: "Zıt Anlamlı" }
};

const INCOMPATIBLE_CONCEPT_CLUSTERS = [
  new Set(["vowel", "consonant", "silent"]),
  new Set(["weak vowel", "strong vowel"]),
  new Set(["diphthong", "hiatus"]),
  new Set(["masculine", "feminine", "neuter"]),
  new Set(["singular", "plural"]),
  new Set(["noun", "verb", "adjective", "adverb", "preposition", "conjunction", "article", "pronoun"]),
  new Set(["nominative", "accusative", "dative", "genitive"]),
  new Set(["present tense", "past tense", "future tense"]),
  new Set(["synonym", "antonym"])
];

function areConceptsIncompatible(k1, k2) {
  if (!k1 || !k2 || k1 === k2) return false;
  for (const cluster of INCOMPATIBLE_CONCEPT_CLUSTERS) {
    if (cluster.has(k1) && cluster.has(k2)) return true;
  }
  return false;
}

const CONCEPT_ALIASES = {
  // German
  "vokal": "vowel", "vokale": "vowel",
  "konsonant": "consonant", "konsonanten": "consonant",
  "laut": "sound", "laute": "sound",
  "silbe": "syllable", "silben": "syllable",
  "wort": "word", "worter": "word",
  "buchstabe": "letter", "buchstaben": "letter",
  "satz": "sentence", "satze": "sentence",
  "sprache": "language", "sprachen": "language",
  "akzent": "accent", "betonung": "stress", "aussprache": "pronunciation",
  "substantiv": "noun", "nomen": "noun",
  "verb": "verb", "verben": "verb",
  "adjektiv": "adjective", "adjektive": "adjective",
  "adverb": "adverb", "adverbien": "adverb",
  "praposition": "preposition", "prapositionen": "preposition",
  "pronomen": "pronoun", "artikel": "article",
  "genus": "gender", "maskulin": "masculine", "feminin": "feminine", "neutrum": "neuter",
  "einzahl": "singular", "mehrzahl": "plural", "singular": "singular", "plural": "plural",
  "kognat": "cognate", "falscher freund": "false friend", "stumm": "silent",
  "fall": "case", "kasus": "case",
  "nominativ": "nominative", "akkusativ": "accusative", "dativ": "dative", "genitiv": "genitive",
  "zeitform": "tense", "tempus": "tense",
  "prasens": "present tense", "prateritum": "past tense", "perfekt": "past tense", "futur": "future tense",
  "imperativ": "imperative", "konjunktiv": "subjunctive",
  "synonym": "synonym", "antonym": "antonym",

  // Spanish
  "vocal": "vowel", "vocales": "vowel",
  "consonante": "consonant", "consonantes": "consonant",
  "silaba": "syllable", "silabas": "syllable",
  "sonido": "sound", "sonidos": "sound",
  "palabra": "word", "palabras": "word",
  "letra": "letter", "letras": "letter",
  "abecedario": "alphabet", "alfabeto": "alphabet",
  "acento": "accent", "acentos": "accent",
  "tonica": "stress", "diptongo": "diphthong", "hiato": "hiatus",
  "silencio": "silent", "silencioso": "silent", "mudo": "silent",
  "entonacion": "intonation", "pronunciacion": "pronunciation",
  "acentuacion": "accentuation", "debil": "weak vowel", "vocal debil": "weak vowel",
  "fuerte": "strong vowel", "vocal fuerte": "strong vowel",
  "sustantivo": "noun", "sustantivos": "noun", "nombre": "noun",
  "verbo": "verb", "verbos": "verb",
  "adjetivo": "adjective", "adjetivos": "adjective",
  "adverbio": "adverb", "adverbios": "adverb",
  "pronombre": "pronoun", "pronombres": "pronoun",
  "articulo": "article", "articulos": "article",
  "preposicion": "preposition", "preposiciones": "preposition",
  "conjuncion": "conjunction", "conjunciones": "conjunction",
  "genero": "gender", "masculino": "masculine", "femenino": "feminine", "neutro": "neuter",
  "singular": "singular", "plural": "plural",
  "sujeto": "subject", "objeto": "object", "infinitivo": "infinitive", "conjugacion": "conjugation",
  "cognado": "cognate", "falso amigo": "false friend",
  "caso": "case", "nominativo": "nominative", "acusativo": "accusative", "dativo": "dative", "genitivo": "genitive",
  "tiempo verbal": "tense", "presente": "present tense", "pasado": "past tense", "preterito": "past tense", "imperfecto": "past tense", "futuro": "future tense",
  "imperativo": "imperative", "subjuntivo": "subjunctive",
  "sinonimo": "synonym", "antonimo": "antonym",

  // Turkish
  "sesli harf": "vowel", "unlu": "vowel", "unluler": "vowel", "sesli": "vowel",
  "sessiz harf": "consonant", "unsuz": "consonant", "unsuzler": "consonant", "sessiz": "consonant",
  "iki noktali unlu": "umlaut", "ses": "sound", "fonetik ses": "sound",
  "hece": "syllable", "heceler": "syllable", "kelime": "word", "sozcuk": "word",
  "harf": "letter", "harfler": "letter", "alfabe": "alphabet", "cumle": "sentence",
  "dil": "language", "vurgu": "accent", "aksan": "accent", "diftong": "diphthong",
  "cift unlu": "diphthong", "hiat": "hiatus", "ayri unluler": "hiatus",
  "okunmayan harf": "silent", "tonlama": "intonation", "ezgi": "intonation",
  "telaffuz": "pronunciation", "sesletim": "pronunciation",
  "isim": "noun", "ad": "noun",
  "fiil": "verb", "eylem": "verb",
  "sifat": "adjective", "onad": "adjective",
  "zarf": "adverb", "belirtec": "adverb",
  "zamir": "pronoun", "adıl": "pronoun",
  "tanimlik": "article", "artikel": "article",
  "edat": "preposition", "ilgec": "preposition", "baglac": "conjunction",
  "cinsiyet": "gender", "eril": "masculine", "disil": "feminine", "notr": "neuter",
  "tekil": "singular", "cogul": "plural", "ozne": "subject", "nesne": "object", "tumlec": "object",
  "mastar": "infinitive", "fiil cekimi": "conjugation", "cekim": "conjugation",
  "ortak kokenli": "cognate", "yaniltici benzer": "false friend",
  "hal": "case", "ismin hali": "case", "durum": "case",
  "yalin hal": "nominative", "belirtme hali": "accusative", "yonelme hali": "dative", "tamlayan hali": "genitive",
  "zaman": "tense", "simdiki zaman": "present tense", "genis zaman": "present tense",
  "gecmis zaman": "past tense", "gelecek zaman": "future tense",
  "emir kipi": "imperative", "istek kipi": "subjunctive",
  "es anlamli": "synonym", "anlamdas": "synonym", "zit anlamli": "antonym", "karsit": "antonym",

  // French
  "voyelle": "vowel", "voyelles": "vowel", "consonne": "consonant", "consonnes": "consonant",
  "syllabe": "syllable", "mot": "word", "lettre": "letter", "nom": "noun", "verbe": "verb",
  "adjectif": "adjective", "adverbe": "adverb", "pronom": "pronoun", "article": "article",
  "preposition": "preposition", "genre": "gender", "masculin": "masculine", "feminin": "feminine",
  "singulier": "singular", "pluriel": "plural",

  // Italian
  "vocale": "vowel", "vocali": "vowel", "consonante": "consonant", "consonanti": "consonant",
  "sillaba": "syllable", "parola": "word", "lettera": "letter", "sostantivo": "noun",
  "nome": "noun", "verbo": "verb", "aggettivo": "adjective", "avverbio": "adverb",
  "pronome": "pronoun", "articolo": "article", "preposizione": "preposition",
  "genere": "gender", "maschile": "masculine", "femminile": "feminine",
  "singolare": "singular", "plurale": "plural"
};

function normalizeConceptStr(str) {
  if (!str || typeof str !== 'string') return '';
  let s = str.toLowerCase().trim();
  const prefixes = ['der ', 'die ', 'das ', 'el ', 'la ', 'los ', 'las ', 'the ', 'a ', 'an ', 'ein ', 'eine ', 'un ', 'una ', 'le ', 'les ', 'il ', 'lo ', 'gli '];
  for (const p of prefixes) {
    if (s.startsWith(p)) { s = s.slice(p.length).trim(); break; }
  }
  return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9\s]/g, '').trim();
}

function resolveConceptKey(str) {
  if (!str || typeof str !== 'string') return '';
  const norm = normalizeConceptStr(str);
  if (!norm) return '';
  if (PEDAGOGICAL_CONCEPT_EXPLANATIONS[norm]) return norm;
  if (CONCEPT_ALIASES[norm]) return CONCEPT_ALIASES[norm];
  const words = norm.split(/\s+/);
  // Word-level fallback ONLY for very short phrases (<= 3 words), NEVER for sentences
  if (words.length <= 3) {
    for (const w of words) {
      if (PEDAGOGICAL_CONCEPT_EXPLANATIONS[w]) return w;
      if (CONCEPT_ALIASES[w]) return CONCEPT_ALIASES[w];
    }
  }
  return '';
}

const FRONTEND_PRAGMATIC_MAP = {
  "buenas tardes": {
    en: "Good afternoon",
    tr: "Tünaydın",
    desc_en: "Standard polite greeting used from midday until dusk.",
    desc_tr: "Öğleden gün batımına kadar kullanılan kibar ve doğal selamlaşma ifadesi."
  },
  "buenos dias": {
    en: "Good morning",
    tr: "Günaydın",
    desc_en: "Standard greeting used in the morning until noon.",
    desc_tr: "Sabah saatlerinde öğleye kadar kullanılan standart karşılama ifadesi."
  },
  "buenas noches": {
    en: "Good evening / Good night",
    tr: "İyi akşamlar / İyi geceler",
    desc_en: "Greeting used in the evening, also used as farewell at night.",
    desc_tr: "Akşam saatlerinde selamlaşırken veya gece ayrılırken kullanılır."
  },
  "hola": {
    en: "Hello / Hi",
    tr: "Merhaba",
    desc_en: "Universal, all-purpose greeting suitable for any time of day.",
    desc_tr: "Günün her saatinde kullanılabilen genel ve samimi selamlaşma sözcüğü."
  },
  "adios": {
    en: "Goodbye",
    tr: "Hoşça kal",
    desc_en: "Standard farewell expression.",
    desc_tr: "Ayrılırken söylenen temel veda sözü."
  },
  "hasta luego": {
    en: "See you later",
    tr: "Sonra görüşürüz",
    desc_en: "Common parting phrase: until later / see you later.",
    desc_tr: "Ayrılırken 'sonra görüşmek üzere' anlamında kullanılan yaygın veda ifadesi."
  },
  "hasta pronto": {
    en: "See you soon",
    tr: "Yakında görüşürüz",
    desc_en: "Parting phrase used when expecting to see someone again soon.",
    desc_tr: "Kısa bir süre içinde yeniden bir araya gelineceğini bildiren veda ifadesi."
  },
  "nos vemos": {
    en: "See you",
    tr: "Görüşmek üzere",
    desc_en: "Friendly parting expression: we will see each other.",
    desc_tr: "Samimi ve günlük vedalaşmalarda kullanılan 'görüşmek üzere' ifadesi."
  },
  "hasta manana": {
    en: "See you tomorrow",
    tr: "Yarın görüşürüz",
    desc_en: "Parting phrase specifically for the following day.",
    desc_tr: "Ertesi gün yeniden bir araya gelineceğini bildiren veda ifadesi."
  },
  "primero": { en: "First", tr: "Birinci", desc_en: "Precedes all others in order or position.", desc_tr: "Bir dizideki ilk pozisyonu veya sırayı belirtir." },
  "primera": { en: "First", tr: "Birinci", desc_en: "Feminine form: precedes all others in order.", desc_tr: "Bir dizideki ilk sırayı veya konumu belirtir." },
  "segundo": { en: "Second", tr: "İkinci", desc_en: "Coming next after the first in order.", desc_tr: "Bir dizideki ikinci konumu veya sırayı belirtir." },
  "segunda": { en: "Second", tr: "İkinci", desc_en: "Feminine form: coming next after the first.", desc_tr: "Bir dizideki ikinci sırayı veya konumu belirtir." },
  "tercero": { en: "Third", tr: "Üçüncü", desc_en: "Coming next after the second in order.", desc_tr: "Bir dizideki üçüncü konumu veya sırayı belirtir." },
  "tercera": { en: "Third", tr: "Üçüncü", desc_en: "Feminine form: coming next after the second.", desc_tr: "Bir dizideki üçüncü sırayı veya konumu belirtir." },
  "cuarto": { en: "Fourth", tr: "Dördüncü", desc_en: "Coming next after the third in order.", desc_tr: "Bir dizideki dördüncü konumu veya sırayı belirtir." },
  "cuarta": { en: "Fourth", tr: "Dördüncü", desc_en: "Feminine form: fourth in order.", desc_tr: "Bir dizideki dördüncü konumu veya sırayı belirtir." },
  "quinto": { en: "Fifth", tr: "Beşinci", desc_en: "Coming next after the fourth in order.", desc_tr: "Beşinci sırayı veya konumu belirtmek için kullanılır." },
  "quinta": { en: "Fifth", tr: "Beşinci", desc_en: "Feminine form: fifth in order.", desc_tr: "Beşinci sırayı veya konumu belirtmek için kullanılır." },
  "sexto": { en: "Sixth", tr: "Altıncı", desc_en: "Coming next after the fifth in order.", desc_tr: "Altıncı sırayı veya konumu belirtir." },
  "sexta": { en: "Sixth", tr: "Altıncı", desc_en: "Feminine form: sixth in order.", desc_tr: "Altıncı sırayı veya konumu belirtir." },
  "septimo": { en: "Seventh", tr: "Yedinci", desc_en: "Coming next after the sixth in order.", desc_tr: "Yedinci sırayı veya konumu belirtir." },
  "séptimo": { en: "Seventh", tr: "Yedinci", desc_en: "Coming next after the sixth in order.", desc_tr: "Yedinci sırayı veya konumu belirtir." },
  "octavo": { en: "Eighth", tr: "Sekizinci", desc_en: "Coming next after the seventh in order.", desc_tr: "Sekizinci sırayı veya konumu belirtir." },
  "noveno": { en: "Ninth", tr: "Dokuzuncu", desc_en: "Coming next after the eighth in order.", desc_tr: "Dokuzuncu sırayı veya konumu belirtir." },
  "decimo": { en: "Tenth", tr: "Onuncu", desc_en: "Coming next after the ninth in order.", desc_tr: "Onuncu sırayı veya konumu belirtir." },
  "décimo": { en: "Tenth", tr: "Onuncu", desc_en: "Coming next after the ninth in order.", desc_tr: "Onuncu sırayı veya konumu belirtir." },
  "mucho gusto": {
    en: "Nice to meet you",
    tr: "Tanıştığımıza memnun oldum",
    desc_en: "Polite formula when introduced to someone for the first time.",
    desc_tr: "Biriyle ilk kez tanışıldığında nezaket gereği söylenen kalıp."
  },
  "me llamo": {
    en: "My name is",
    tr: "Benim adım...",
    desc_en: "Reflexive verb phrase used to state one's own name.",
    desc_tr: "Kendi ismini söylerken kullanılan dönüşlü kalıp (Adım...)."
  },
  "como estas": {
    en: "How are you?",
    tr: "Nasılsın?",
    desc_en: "Informal inquiry about someone's well-being.",
    desc_tr: "Yakınlara ve akranlara yöneltilen samimi hal hatır sorusu."
  },
  "como esta usted": {
    en: "How are you? (formal)",
    tr: "Nasılsınız?",
    desc_en: "Formal, respectful inquiry about well-being.",
    desc_tr: "Resmi veya saygı gerektiren durumlarda sorulan hal hatır kalıbı."
  },
  "yo": {
    en: "I",
    tr: "Ben",
    desc_en: "First-person singular subject pronoun.",
    desc_tr: "1. tekil şahıs zamiri (eylemi yapan konuşan kişi)."
  },
  "soy": {
    en: "I am",
    tr: "(Ben) ...yim / ...yım",
    desc_en: "First-person singular present of 'ser' (to be: identity, origin, traits).",
    desc_tr: "'Ser' (olmak) fiilinin 1. tekil şahıs çekimi (kimlik, milliyet, meslek bildirir)."
  },
  "tu": {
    en: "You",
    tr: "Sen",
    desc_en: "Second-person informal singular subject pronoun.",
    desc_tr: "2. tekil şahıs zamiri (samimi hitap)."
  },
  "eres": {
    en: "You are",
    tr: "(Sen) ...sin / ...sın",
    desc_en: "Second-person singular present of 'ser'.",
    desc_tr: "'Ser' fiilinin 2. tekil şahıs çekimi."
  },
  "el": {
    en: "He",
    tr: "O (erkek)",
    desc_en: "Third-person singular masculine pronoun.",
    desc_tr: "3. tekil şahıs eril zamiri."
  },
  "ella": {
    en: "She",
    tr: "O (kadın)",
    desc_en: "Third-person singular feminine pronoun.",
    desc_tr: "3. tekil şahıs dişil zamiri."
  },
  "usted": {
    en: "You (formal)",
    tr: "Siz (resmi)",
    desc_en: "Second-person formal singular pronoun (conjugates with 3rd person).",
    desc_tr: "Nezaket ve resmiyet bildiren 2. tekil şahıs hitabı."
  },
  "es": {
    en: "He/she/it is",
    tr: "(O) ...dir / ...dır",
    desc_en: "Third-person singular present of 'ser'.",
    desc_tr: "'Ser' fiilinin 3. tekil şahıs çekimi."
  },
  "nosotros": {
    en: "We",
    tr: "Biz",
    desc_en: "First-person plural subject pronoun.",
    desc_tr: "1. çoğul şahıs zamiri."
  },
  "nosotras": {
    en: "We (feminine)",
    tr: "Biz (kadınlar)",
    desc_en: "First-person plural feminine subject pronoun.",
    desc_tr: "1. çoğul şahıs dişil zamiri."
  },
  "somos": {
    en: "We are",
    tr: "(Biz) ...yiz / ...yız",
    desc_en: "First-person plural present of 'ser'.",
    desc_tr: "'Ser' fiilinin 1. çoğul şahıs çekimi."
  },
  "vosotros": {
    en: "You all (informal)",
    tr: "Sizler (samimi)",
    desc_en: "Second-person plural informal pronoun (used in Spain).",
    desc_tr: "İspanya'da kullanılan 2. çoğul şahıs zamiri."
  },
  "vosotras": {
    en: "You all (feminine)",
    tr: "Sizler (kadınlar)",
    desc_en: "Second-person plural feminine informal pronoun (Spain).",
    desc_tr: "İspanya'da kullanılan 2. çoğul şahıs dişil zamiri."
  },
  "sois": {
    en: "You all are",
    tr: "(Sizler) ...siniz / ...sınız",
    desc_en: "Second-person plural present of 'ser'.",
    desc_tr: "'Ser' fiilinin 2. çoğul şahıs çekimi (İspanya)."
  },
  "ellos": {
    en: "They (masculine / mixed)",
    tr: "Onlar (eril)",
    desc_en: "Third-person plural masculine pronoun.",
    desc_tr: "3. çoğul şahıs eril / genel zamiri."
  },
  "ellas": {
    en: "They (feminine)",
    tr: "Onlar (dişil)",
    desc_en: "Third-person plural feminine pronoun.",
    desc_tr: "3. çoğul şahıs dişil zamiri."
  },
  "ustedes": {
    en: "You all",
    tr: "Sizler",
    desc_en: "Second-person plural pronoun (universal in Latin America).",
    desc_tr: "2. çoğul şahıs hitabı (Latin Amerika'da genel, İspanya'da resmi)."
  },
  "son": {
    en: "They are / You all are",
    tr: "(Onlar) ...dirler / ...dırlar",
    desc_en: "Third-person plural present of 'ser'.",
    desc_tr: "'Ser' fiilinin 3. çoğul şahıs çekimi."
  },
  "guten morgen": {
    en: "Good morning",
    tr: "Günaydın",
    desc_en: "Standard German morning greeting used until midday.",
    desc_tr: "Almancada sabah saatlerinde öğleye kadar kullanılan standart karşılama."
  },
  "guten tag": {
    en: "Good day / Hello",
    tr: "İyi günler / Merhaba",
    desc_en: "Standard polite daytime greeting in German.",
    desc_tr: "Almancada gün içinde yaygın olarak kullanılan resmi ve genel selamlaşma."
  },
  "guten abend": {
    en: "Good evening",
    tr: "İyi akşamlar",
    desc_en: "Polite German greeting used in the evening hours.",
    desc_tr: "Almancada akşam saatlerinde kullanılan kibar selamlaşma."
  },
  "gute nacht": {
    en: "Good night",
    tr: "İyi geceler",
    desc_en: "German parting expression specifically used before bedtime.",
    desc_tr: "Almancada uyumadan önce veya gece ayrılırken söylenen veda ifadesi."
  },
  "auf wiedersehen": {
    en: "Goodbye",
    tr: "Görüşmek üzere / Hoşça kalın",
    desc_en: "Formal German farewell expression.",
    desc_tr: "Almancada resmi ve kibar veda sözü."
  },
  "tschuss": {
    en: "Bye",
    tr: "Hoşça kal",
    desc_en: "Informal German farewell among friends and peers.",
    desc_tr: "Almancada arkadaşlar arasında kullanılan samimi veda ifadesi."
  },
  "ich": {
    en: "I",
    tr: "Ben",
    desc_en: "German first-person singular subject pronoun.",
    desc_tr: "Almanca 1. tekil şahıs zamiri."
  },
  "bin": {
    en: "I am",
    tr: "(Ben) ...yim / ...yım",
    desc_en: "First-person singular present of German 'sein' (to be).",
    desc_tr: "Almancada 'sein' (olmak) fiilinin 1. tekil şahıs çekimi (asla sadece zamir değil)."
  },
  "du": {
    en: "You",
    tr: "Sen",
    desc_en: "German second-person informal singular subject pronoun.",
    desc_tr: "Almanca 2. tekil şahıs zamiri (samimi hitap)."
  },
  "bist": {
    en: "You are",
    tr: "(Sen) ...sin / ...sın",
    desc_en: "Second-person singular present of German 'sein'.",
    desc_tr: "Almancada 'sein' (olmak) fiilinin 2. tekil şahıs çekimi."
  },
  "er": {
    en: "He",
    tr: "O (erkek)",
    desc_en: "German third-person singular masculine pronoun.",
    desc_tr: "Almanca 3. tekil şahıs eril zamiri."
  },
  "sie": {
    en: "She / They / You (formal)",
    tr: "O (kadın) / Onlar / Siz",
    desc_en: "German third-person feminine pronoun, plural pronoun, or formal 'You'.",
    desc_tr: "Almancada dişil 'O', çoğul 'Onlar' veya büyük harfle resmi 'Siz'."
  },
  "ist": {
    en: "He/she/it is",
    tr: "(O) ...dir / ...dır",
    desc_en: "Third-person singular present of German 'sein'.",
    desc_tr: "Almancada 'sein' (olmak) fiilinin 3. tekil şahıs çekimi."
  },
  "wir": {
    en: "We",
    tr: "Biz",
    desc_en: "German first-person plural subject pronoun.",
    desc_tr: "Almanca 1. çoğul şahıs zamiri."
  },
  "sind": {
    en: "We are / They are",
    tr: "(Biz) ...yiz / ...yız",
    desc_en: "First and third person plural present of German 'sein'.",
    desc_tr: "Almancada 'sein' fiilinin çoğul çekimi."
  },
  "bonjour": {
    en: "Hello / Good morning",
    tr: "Günaydın / Merhaba",
    desc_en: "Universal French daytime greeting.",
    desc_tr: "Fransızcada gün boyu kullanılan standart selamlaşma."
  },
  "bonsoir": {
    en: "Good evening",
    tr: "İyi akşamlar",
    desc_en: "French greeting used from late afternoon through the evening.",
    desc_tr: "Fransızcada akşam saatlerinde kullanılan selamlaşma."
  },
  "bonne nuit": {
    en: "Good night",
    tr: "İyi geceler",
    desc_en: "French parting wish before sleeping.",
    desc_tr: "Fransızcada gece yatarken veya ayrılırken söylenen iyi geceler dileği."
  },
  "au revoir": {
    en: "Goodbye",
    tr: "Görüşmek üzere / Hoşça kalın",
    desc_en: "Standard French farewell expression.",
    desc_tr: "Fransızcada temel ve saygılı veda ifadesi."
  },
  "salut": {
    en: "Hi / Bye",
    tr: "Selam / Hoşça kal",
    desc_en: "Informal French greeting and parting phrase among friends.",
    desc_tr: "Fransızcada hem merhaba hem hoşça kal anlamında samimi hitap."
  },
  "je": {
    en: "I",
    tr: "Ben",
    desc_en: "French first-person singular subject pronoun.",
    desc_tr: "Fransızca 1. tekil şahıs zamiri."
  },
  "suis": {
    en: "I am",
    tr: "(Ben) ...yim / ...yım",
    desc_en: "First-person singular present of French 'être' (to be).",
    desc_tr: "Fransızcada 'être' (olmak) fiilinin 1. tekil şahıs çekimi (asla sadece zamir değil)."
  },
  "il": {
    en: "He",
    tr: "O (erkek)",
    desc_en: "French third-person singular masculine pronoun.",
    desc_tr: "Fransızca 3. tekil şahıs eril zamiri."
  },
  "elle": {
    en: "She",
    tr: "O (kadın)",
    desc_en: "French third-person singular feminine pronoun.",
    desc_tr: "Fransızca 3. tekil şahıs dişil zamiri."
  },
  "est": {
    en: "He/she is",
    tr: "(O) ...dir / ...dır",
    desc_en: "Third-person singular present of French 'être'.",
    desc_tr: "Fransızcada 'être' (olmak) fiilinin 3. tekil şahıs çekimi."
  },
  "nous": {
    en: "We",
    tr: "Biz",
    desc_en: "French first-person plural subject pronoun.",
    desc_tr: "Fransızca 1. çoğul şahıs zamiri."
  },
  "sommes": {
    en: "We are",
    tr: "(Biz) ...yiz / ...yız",
    desc_en: "First-person plural present of French 'être'.",
    desc_tr: "Fransızcada 'être' fiilinin 1. çoğul şahıs çekimi."
  },
  "vous": {
    en: "You (formal/plural)",
    tr: "Siz / Sizler",
    desc_en: "French polite singular or general plural second-person pronoun.",
    desc_tr: "Fransızcada kibar tekil veya genel çoğul hitap zamiri."
  },
  "buongiorno": {
    en: "Good morning / Good day",
    tr: "Günaydın / İyi günler",
    desc_en: "Standard Italian polite daytime greeting.",
    desc_tr: "İtalyancada sabah ve gündüz kullanılan kibar karşılama."
  },
  "buonasera": {
    en: "Good evening",
    tr: "İyi akşamlar",
    desc_en: "Italian greeting used in the late afternoon and evening.",
    desc_tr: "İtalyancada akşam saatlerinde söylenen selamlaşma."
  },
  "buonanotte": {
    en: "Good night",
    tr: "İyi geceler",
    desc_en: "Italian parting expression before sleeping.",
    desc_tr: "İtalyancada uyumadan önce söylenen veda kalıbı."
  },
  "arrivederci": {
    en: "Goodbye",
    tr: "Görüşmek üzere",
    desc_en: "Standard Italian polite farewell expression.",
    desc_tr: "İtalyancada kibar ve yaygın veda sözü."
  },
  "ciao": {
    en: "Hello / Bye",
    tr: "Merhaba / Hoşça kal",
    desc_en: "Universal informal Italian greeting and parting word.",
    desc_tr: "İtalyancada hem karşılama hem veda için kullanılan samimi sözcük."
  },
  "io": {
    en: "I",
    tr: "Ben",
    desc_en: "Italian first-person singular subject pronoun.",
    desc_tr: "İtalyanca 1. tekil şahıs zamiri."
  },
  "sono": {
    en: "I am / They are",
    tr: "(Ben) ...yim / ...yım",
    desc_en: "First-person singular (or 3rd-plural) present of Italian 'essere' (to be).",
    desc_tr: "İtalyancada 'essere' (olmak) fiilinin 1. tekil şahıs çekimi."
  },
  "lui": {
    en: "He",
    tr: "O (erkek)",
    desc_en: "Italian third-person singular masculine pronoun.",
    desc_tr: "İtalyanca 3. tekil şahıs eril zamiri."
  },
  "lei": {
    en: "She / You (formal)",
    tr: "O (kadın) / Siz (resmi)",
    desc_en: "Italian third-person feminine pronoun or formal 'You'.",
    desc_tr: "İtalyancada 3. tekil şahıs dişil zamiri veya resmi 'Siz'."
  },
  "noi": {
    en: "We",
    tr: "Biz",
    desc_en: "Italian first-person plural subject pronoun.",
    desc_tr: "İtalyanca 1. çoğul şahıs zamiri."
  },
  "siamo": {
    en: "We are",
    tr: "(Biz) ...yiz / ...yız",
    desc_en: "First-person plural present of Italian 'essere'.",
    desc_tr: "İtalyancada 'essere' fiilinin 1. çoğul şahıs çekimi."
  },
  "good morning": {
    en: "Good morning",
    tr: "Günaydın",
    desc_en: "Standard morning greeting used from dawn until noon.",
    desc_tr: "Sabah saatlerinde öğleye kadar kullanılan standart karşılama."
  },
  "good afternoon": {
    en: "Good afternoon",
    tr: "Tünaydın",
    desc_en: "Polite greeting used from midday until evening.",
    desc_tr: "Öğleden akşama kadar kullanılan kibar ve doğal selamlaşma."
  },
  "good evening": {
    en: "Good evening",
    tr: "İyi akşamlar",
    desc_en: "Polite greeting used during evening hours.",
    desc_tr: "Akşam saatlerinde kullanılan kibar karşılama."
  },
  "good night": {
    en: "Good night",
    tr: "İyi geceler",
    desc_en: "Parting wish spoken before bed or upon leaving late at night.",
    desc_tr: "Yatmadan önce veya gece ayrılırken söylenen veda ifadesi."
  },
  "i am": {
    en: "I am",
    tr: "(Ben) ...yim / ...yım",
    desc_en: "First-person singular present of 'to be'.",
    desc_tr: "'To be' (olmak) fiilinin 1. tekil şahıs çekimi."
  },
  "you are": {
    en: "You are",
    tr: "(Sen) ...sin / ...sın",
    desc_en: "Second-person present of 'to be'.",
    desc_tr: "'To be' fiilinin 2. şahıs çekimi."
  },
  "we are": {
    en: "We are",
    tr: "(Biz) ...yiz / ...yız",
    desc_en: "First-person plural present of 'to be'.",
    desc_tr: "'To be' fiilinin 1. çoğul şahıs çekimi."
  },
  "they are": {
    en: "They are",
    tr: "(Onlar) ...dirler / ...dırlar",
    desc_en: "Third-person plural present of 'to be'.",
    desc_tr: "'To be' fiilinin 3. çoğul şahıs çekimi."
  }
};

function safeStr(val) {
  if (val === null || val === undefined) return "";
  if (typeof val === "string") return val;
  if (typeof val === "number" || typeof val === "boolean") return String(val);
  if (Array.isArray(val)) return val.map(v => safeStr(v)).filter(Boolean).join(", ");
  if (typeof val === "object") {
    const displayKeys = ['text','name','value','label','character','hiragana','katakana','letter','symbol','word','term','phrase','romaji','pinyin','reading'];
    for (const dk of displayKeys) {
      if (val[dk] && typeof val[dk] === "string") return val[dk];
    }
    const vals = Object.values(val);
    for (const v of vals) {
      if (typeof v === "string" && v.length > 0) return v;
    }
    const strs = vals.filter(v => typeof v === "string" && v.length > 0);
    if (strs.length > 0) return strs.join(" — ");
    return JSON.stringify(val);
  }
  return String(val);
}

function fixDiacritics(txt) {
  if (typeof txt !== 'string') return txt;
  let res = txt.replace(/(^|[\s\(\[“"'‘])([\u064B-\u065F\u0670])/g, '$1◌$2');
  if (typeof currentLang !== 'undefined' && currentLang === 'tr' && typeof healTurkishSyntax === 'function') {
    res = healTurkishSyntax(res);
  }
  return res;
}

function resolveDualLanguage(enVal, trVal, targetLang = currentLang, defaultVal = "") {
  let enStr = safeStr(enVal).trim();
  let trStr = safeStr(trVal).trim();
  
  const hasTurkishMarkers = (txt) => {
    if (!txt || typeof txt !== 'string') return false;
    return /[çğıöşüÇĞİÖŞÜ]/.test(txt) || /\b(ve|bir|bu|ile|için|olarak|anlatırken|edin|edilmelidir|olmalıdır|göre|kullanılır|ifade|eden|edilir|tartışma|açık|karşı|diyalogu|teşvik|argümanlara|dinleyin|sonuç|mantık|tanışırken|öğleden|günaydın|tünaydın|sesi|gibi|okunur)\b/i.test(txt);
  };
  
  const hasEnglishMarkers = (txt) => {
    if (!txt || typeof txt !== 'string') return false;
    return /\b(the|and|is|are|in|for|with|of|to|these|this|should|must|have|has|be|discussion|open|dialogue|arguments|listen|encourage|conclusion|logic|result|meeting|someone|used|when|first|time)\b/i.test(txt);
  };

  if (targetLang === 'tr') {
    let res = defaultVal;
    // We want Turkish
    if (trStr && !hasEnglishMarkers(trStr) && (hasTurkishMarkers(trStr) || trStr.length > 0)) {
      // Check if trStr needs deinflection to base lemma or is an English word masquerading in trStr
      const autoTr = translateOption(trStr, 'tr');
      res = (autoTr && autoTr.toLowerCase() !== trStr.toLowerCase()) ? autoTr : trStr;
    } else {
      // If trStr is missing or English, try translating enStr or trStr to Turkish
      const src = (enStr && !hasTurkishMarkers(enStr)) ? enStr : (trStr || defaultVal);
      if (src) {
        const optTr = translateOption(src, 'tr');
        if (optTr && optTr.toLowerCase() !== src.toLowerCase()) res = optTr;
        else {
          const trRes = translateEducationalText(src, 'tr');
          res = (trRes && trRes.toLowerCase() !== src.toLowerCase()) ? trRes : src;
        }
      }
    }
    return healTurkishSyntax(humanizeTurkishExplanation(res));
  } else {
    // We want English
    if (enStr && !hasTurkishMarkers(enStr) && (hasEnglishMarkers(enStr) || enStr.length > 0)) {
      // Confirmed English string without Turkish markers
      const autoEn = translateOption(enStr, 'en');
      const cand = (autoEn && autoEn.toLowerCase() !== enStr.toLowerCase() && !hasTurkishMarkers(autoEn)) ? autoEn : enStr;
      return sanitizeEnglishExplanation(cand);
    }
    // If enStr is contaminated with Turkish, or missing, translate to English
    const src = (trStr && trStr.trim()) ? trStr : ((enStr && enStr.trim()) ? enStr : defaultVal);
    if (src) {
      const optEn = translateOption(src, 'en');
      if (optEn && optEn.toLowerCase() !== src.toLowerCase() && !hasTurkishMarkers(optEn)) return sanitizeEnglishExplanation(optEn);
      const enRes = translateEducationalText(src, 'en');
      if (enRes && enRes.toLowerCase() !== src.toLowerCase() && !hasTurkishMarkers(enRes)) return sanitizeEnglishExplanation(enRes);
      return sanitizeEnglishExplanation(enRes || src);
    }
    return sanitizeEnglishExplanation(defaultVal);
  }
}

function resolveItemExplanation(it, term, translation, lang = currentLang) {
  const cleanTerm = safeStr(term).trim();
  const cLang = (currentCourse && currentCourse.language) || 'Spanish';

  // 1. Alphabet letter / phonetics check (handles "A", "a", "A, a", "B, b", "Ch, ch", etc.)
  if (isLetterLike(cleanTerm) || (it && (it.letter || it.character))) {
    const baseL = extractBaseLetter(cleanTerm);
    const phon = getClientLetterPhonetics(cLang, baseL) || {};
    if (lang === 'tr') {
      const rawTr = it && (it.explanation_tr || it.turkish_explanation);
      if (rawTr && typeof rawTr === 'string' && rawTr.trim().length > 2 && !TAUTOLOGY_REGEX.test(rawTr)) {
        return healTurkishSyntax(humanizeTurkishExplanation(rawTr.trim()));
      }
      if (phon.explanation_tr) return phon.explanation_tr;
    } else {
      const rawEn = it && (it.explanation_en || it.english_explanation);
      if (rawEn && typeof rawEn === 'string' && rawEn.trim().length > 2 && !TAUTOLOGY_REGEX.test(rawEn)) {
        const isTrText = /[çğıöşüÇĞİÖŞÜ]/.test(rawEn) || /\b(sesi|gibi|açık|net|okunur|asla|harfi)\b/i.test(rawEn);
        if (!isTrText) {
          return sanitizeEnglishExplanation(rawEn.trim(), cleanTerm);
        }
      }
      if (phon.explanation_en) return phon.explanation_en;
    }
  }

  // Single letters or alphabet character cards must NEVER match pronouns or pragmatic greetings
  if (cleanTerm.length <= 1 || (it && (it.letter || it.character))) {
    return '';
  }

  // Pragmatic check first (for multi-word greetings/phrases)
  const normTerm = normalizeConceptStr(term);
  if (normTerm && FRONTEND_PRAGMATIC_MAP[normTerm]) {
    const prag = FRONTEND_PRAGMATIC_MAP[normTerm];
    return lang === 'tr' ? prag.desc_tr : prag.desc_en;
  }

  const termKey = resolveConceptKey(term);
  const transKey = resolveConceptKey(translation);

  // If item already has explicit language-specific explanation, verify it is not tautological
  if (it && typeof it === 'object') {
    const rawLangExpl = (lang === 'tr')
      ? (it.explanation_tr || it.turkish_explanation || it.desc_tr)
      : (it.explanation_en || it.english_explanation || it.desc_en);
    if (rawLangExpl && typeof rawLangExpl === 'string' && rawLangExpl.trim().length > 2) {
      if (!TAUTOLOGY_REGEX.test(rawLangExpl)) {
        if (lang === 'tr') {
          return healTurkishSyntax(humanizeTurkishExplanation(rawLangExpl.trim()));
        } else {
          const isTr = /[çğıöşüÇĞİÖŞÜ]/.test(rawLangExpl) || /\b(ve|bir|bu|ile|için|olarak|anlatırken|edin|edilmelidir|olmalıdır|göre|kullanılır|ifade|eden|edilir|sesi|gibi|okunur|açık|net)\b/i.test(rawLangExpl);
          if (!isTr) {
            return sanitizeEnglishExplanation(rawLangExpl.trim(), cleanTerm);
          }
        }
      }
    }
  }

  // Check vocab practical tips bank before generic fallback
  const bankHit = getClientVocabExample(cLang, cleanTerm);
  if (bankHit) {
    const tip = (lang === 'tr') ? bankHit.tip_tr : bankHit.tip_en;
    if (tip && !TAUTOLOGY_REGEX.test(tip)) return (lang === 'tr') ? healTurkishSyntax(humanizeTurkishExplanation(tip)) : sanitizeEnglishExplanation(tip, cleanTerm);
  }

  // Bidirectional fallback if one language is missing
  if (it && typeof it === 'object') {
    if (lang === 'en' && it.explanation_tr && typeof it.explanation_tr === 'string' && it.explanation_tr.trim().length > 2) {
      if (!TAUTOLOGY_REGEX.test(it.explanation_tr)) {
        const dual = resolveDualLanguage('', it.explanation_tr.trim(), 'en');
        if (dual && !/[çğıöşüÇĞİÖŞÜ]/.test(dual)) {
          return sanitizeEnglishExplanation(dual, cleanTerm);
        }
      }
    } else if (lang === 'tr' && (it.explanation_en || it.explanation) && typeof (it.explanation_en || it.explanation) === 'string') {
      const enVal = (it.explanation_en || it.explanation).trim();
      if (enVal.length > 2 && !TAUTOLOGY_REGEX.test(enVal)) {
        return resolveDualLanguage(enVal, '', 'tr');
      }
    }
  }

  // GROUND TRUTH: termKey (authentic foreign word being studied) ALWAYS takes precedence over transKey!
  let key = termKey;
  if (termKey && transKey && areConceptsIncompatible(termKey, transKey)) {
    key = termKey;
  } else if (!key) {
    key = transKey;
  }

  if (key && PEDAGOGICAL_CONCEPT_EXPLANATIONS[key]) {
    const entry = PEDAGOGICAL_CONCEPT_EXPLANATIONS[key];
    const val = lang === 'tr' ? (entry.tr || entry.en) : (entry.en || entry.tr);
    if (val && !TAUTOLOGY_REGEX.test(val)) return (lang === 'tr') ? healTurkishSyntax(humanizeTurkishExplanation(val)) : sanitizeEnglishExplanation(val, cleanTerm);
  }

  // Fallback to generic item explanation if not tautological
  if (it && typeof it === 'object') {
    const rawExpl = it.explanation || it.description || it.desc || it.note || it.usage;
    if (rawExpl && typeof rawExpl === 'string' && rawExpl.trim().length > 2) {
      if (!TAUTOLOGY_REGEX.test(rawExpl)) {
        const resolved = resolveDualLanguage(rawExpl.trim(), rawExpl.trim(), lang, rawExpl.trim());
        return (lang === 'tr') ? healTurkishSyntax(humanizeTurkishExplanation(resolved)) : sanitizeEnglishExplanation(resolved, cleanTerm);
      }
    }
  }

  return '';
}

function translatePrompt(text, lang = currentLang) {
  if (!text) return '';
  let str = text.trim();
  if (lang === 'tr') {
    str = str.replace(/What is the phonetic sound of the letter '(.*)' in Spanish\?/i, "İspanyolcada '$1' harfinin fonetik sesi nedir?");
    str = str.replace(/What is the phonetic sound of the letter '(.*)' in (.*)\?/i, "$2'de '$1' harfinin fonetik sesi nedir?");
    str = str.replace(/What does '(.*)' mean\?/i, "'$1' ne anlama gelir?");
    str = str.replace(/How do you say '(.*)' in Spanish\?/i, (m, w) => {
      const wordTR = translateOption(w, 'tr');
      return `İspanyolca'da '${wordTR}' nasıl denir?`;
    });
    str = str.replace(/How do you say '(.*)' in (.*)\?/i, (m, w, l) => {
      const wordTR = translateOption(w, 'tr');
      const langTR = translateCourseName(l, 'tr');
      return `${langTR}'da '${wordTR}' nasıl denir?`;
    });
    str = str.replace(/Identify the correct option:?/i, "Doğru seçeneği belirleyin:");
    str = str.replace(/Identify the correct answer:?/i, "Doğru cevabı belirleyin:");
    str = str.replace(/Select the correct answer:?/i, "Doğru cevabı seçin:");
    str = str.replace(/Choose the correct translation:?/i, "Doğru çeviriyi seçin:");
    str = str.replace(/Choose the correct option:?/i, "Doğru seçeneği seçin:");
    str = str.replace(/Fill in the blank:?/i, "Boşluğu doldurun:");
    str = str.replace(/Reorder the dialogue correctly:?/i, "Diyaloğu doğru sıraya koyun:");
    str = str.replace(/Arrange the dialogue in the correct order:?/i, "Diyaloğu doğru sıraya koyun:");
    str = str.replace(/Which word best completes the sentence\?/i, "Cümleyi en iyi hangi kelime tamamlar?");
    str = str.replace(/Which of the following means '(.*)'\?/i, "Aşağıdakilerden hangisi '$1' anlamına gelir?");
    str = str.replace(/Translate the following sentence:?/i, "Aşağıdaki cümleyi çevirin:");
    str = str.replace(/Translate the following:?/i, "Aşağıdakini çevirin:");
    str = str.replace(/^Completa la frase:?/i, "Cümleyi tamamlayınız:");
    str = str.replace(/^Completa el espacio en blanco:?/i, "Boşluğu doldurun:");
    str = str.replace(/^Selecciona la opción correcta:?/i, "Doğru seçeneği seçin:");
    str = str.replace(/^Elige la opción correcta:?/i, "Doğru seçeneği seçin:");
    str = str.replace(/^Elige la frase gramaticalmente correcta:?/i, "Dilbilgisel olarak doğru cümleyi seçin:");
  } else {
    if (typeof getEnglishStudyPrompt === 'function') {
      str = getEnglishStudyPrompt(str);
    }
    str = str.replace(/İspanyolcada '(.*)' harfinin fonetik sesi nedir\?/i, "What is the phonetic sound of the letter '$1' in Spanish?");
    str = str.replace(/(.*)'de '(.*)' harfinin fonetik sesi nedir\?/i, (m, l, w) => {
      const langEN = translateCourseName(l, 'en');
      return `What is the phonetic sound of the letter '${w}' in ${langEN}?`;
    });
    str = str.replace(/'(.*)' ne anlama gelir\?/i, "What does '$1' mean?");
    str = str.replace(/İspanyolca'da '(.*)' nasıl denir\?/i, (m, w) => {
      const wordEN = translateOption(w, 'en');
      return `How do you say '${wordEN}' in Spanish?`;
    });
    str = str.replace(/(.*)'da '(.*)' nasıl denir\?/i, (m, l, w) => {
      const wordEN = translateOption(w, 'en');
      const langEN = translateCourseName(l, 'en');
      return `How do you say '${wordEN}' in ${langEN}?`;
    });
    str = str.replace(/Doğru seçeneği belirleyin:?/i, "Identify the correct option:");
    str = str.replace(/Doğru cevabı belirleyin:?/i, "Identify the correct answer:");
    str = str.replace(/Doğru cevabı seçin:?/i, "Select the correct answer:");
    str = str.replace(/Doğru çeviriyi seçin:?/i, "Choose the correct translation:");
    str = str.replace(/Doğru seçeneği seçin:?/i, "Choose the correct option:");
    str = str.replace(/Boşluğu doldurun:?/i, "Fill in the blank:");
    str = str.replace(/Diyaloğu doğru sıraya koyun:?/i, "Reorder the dialogue correctly:");
    str = str.replace(/Cümleyi en iyi hangi kelime tamamlar\?/i, "Which word best completes the sentence?");
    str = str.replace(/Aşağıdakilerden hangisi '(.*)' anlamına gelir\?/i, "Which of the following means '$1'?");
    str = str.replace(/Aşağıdaki cümleyi çevirin:?/i, "Translate the following sentence:");
    str = str.replace(/Aşağıdakini çevirin:?/i, "Translate the following:");
  }
  return str;
}

const EDUCATIONAL_SENTENCE_PAIRS = [
  ["This is the complete list of the Spanish alphabet.", "Bu, İspanyol alfabesinin tam listesidir."],
  ["Each letter has a unique sound that is important for pronunciation.", "Her harfin telaffuz için önemli olan benzersiz bir sesi vardır."],
  ["Familiarity with these letters helps in spelling and reading.", "Bu harflere aşina olmak heceleme ve okumaya yardımcı olur."],
  ["Understanding the alphabet is foundational for language learning.", "Alfabeyi anlamak dil öğrenimi için temeldir."],
  ["Each letter has a specific sound in Spanish.", "İspanyolcada her harfin belirli bir sesi vardır."],
  ["Vowels (A, E, I, O, U) have clear, distinct sounds.", "Ünlüler (A, E, I, O, U) net ve belirgin seslere sahiptir."],
  ["Consonants can vary in sound depending on their placement.", "Ünsüzlerin sesleri konumlarına göre değişiklik gösterebilir."],
  ["Practice saying each letter out loud to master pronunciation.", "Telaffuzda ustalaşmak için her harfi sesli olarak telaffuz edin."],
  ["Listening to native speakers helps improve your phonetic skills.", "Anadili konuşanları dinlemek fonetik becerilerinizi geliştirmeye yardımcı olur."],
  ["These examples show how to use letters in everyday situations.", "Bu örnekler harflerin günlük durumlarda nasıl kullanılacağını gösterir."],
  ["Recognizing letters helps in spelling names and places.", "Harfleri tanımak isimleri ve yerleri hecelemeye yardımcı olur."],
  ["Practice with these sentences to improve fluency.", "Akıcılığı artırmak için bu cümlelerle pratik yapın."],
  ["The letter 'G' has a hard sound like 'g' in 'go' when followed by 'a', 'o', or 'u'.", "'G' harfi 'a', 'o' veya 'u'dan önce geldiğinde 'go'daki 'g' gibi sert bir sese sahiptir."],
  ["When followed by 'e' or 'i', it has a softer sound, similar to 'h' in 'hello'.", "'e' veya 'i'den önce geldiğinde 'hello'daki 'h'ye benzer daha yumuşak bir sese sahiptir."],
  ["Understanding this helps in accurate pronunciation.", "Bunu anlamak doğru telaffuz için yardımcı olur."],
  ["Common greetings in Spanish include hola, buenos días, and buenas tardes.", "İspanyolcada yaygın selamlaşmalar arasında hola, buenos días ve buenas tardes yer alır."],
  ["Use 'tú' for informal situations and 'usted' for formal situations.", "Resmi olmayan durumlar için 'tú', resmi durumlar için 'usted' kullanın."],
  ["Numbers from 1 to 20 have unique names in Spanish.", "1'den 20'ye kadar olan sayıların İspanyolcada benzersiz adları vardır."],
  ["Days of the week are not capitalized in Spanish.", "İspanyolcada haftanın günleri büyük harfle başlamaz."],
  ["Months and seasons are essential for discussing plans and dates.", "Aylar ve mevsimler planları ve tarihleri konuşmak için gereklidir."]
];

function translateFormulaBrackets(formulaStr, targetLang = currentLang) {
  if (!formulaStr || typeof formulaStr !== 'string') return formulaStr;
  const isTr = (targetLang === 'tr');
  const termMap = {
    'sujeto': isTr ? 'Özne' : 'Subject',
    'subject': isTr ? 'Özne' : 'Subject',
    'özne': isTr ? 'Özne' : 'Subject',
    'verbo en presente': isTr ? 'Şimdiki / Geniş Zaman Fiili' : 'Present Tense Verb',
    'present tense verb': isTr ? 'Şimdiki / Geniş Zaman Fiili' : 'Present Tense Verb',
    'verbo en pasado': isTr ? 'Geçmiş Zaman Fiili' : 'Past Tense Verb',
    'past tense verb': isTr ? 'Geçmiş Zaman Fiili' : 'Past Tense Verb',
    'verbo en futuro': isTr ? 'Gelecek Zaman Fiili' : 'Future Tense Verb',
    'future tense verb': isTr ? 'Gelecek Zaman Fiili' : 'Future Tense Verb',
    'verbo principal': isTr ? 'Ana Eylem / Fiil' : 'Main Verb',
    'main verb': isTr ? 'Ana Eylem / Fiil' : 'Main Verb',
    'verbo': isTr ? 'Fiil' : 'Verb',
    'verb': isTr ? 'Fiil' : 'Verb',
    'fiil': isTr ? 'Fiil' : 'Verb',
    'verbo conjugado': isTr ? 'Çekimli Fiil' : 'Conjugated Verb',
    'conjugated verb': isTr ? 'Çekimli Fiil' : 'Conjugated Verb',
    'çekimli fiil': isTr ? 'Çekimli Fiil' : 'Conjugated Verb',
    'verbo auxiliar': isTr ? 'Yardımcı Fiil' : 'Auxiliary Verb',
    'auxiliary verb': isTr ? 'Yardımcı Fiil' : 'Auxiliary Verb',
    'yardımcı fiil': isTr ? 'Yardımcı Fiil' : 'Auxiliary Verb',
    'şimdiki zaman fiili': isTr ? 'Şimdiki Zaman Fiili' : 'Present Tense Verb',
    'geniş zaman fiili': isTr ? 'Geniş Zaman Fiili' : 'Present / Simple Tense Verb',
    'ana eylem': isTr ? 'Ana Eylem' : 'Main Verb',
    'ana cümle': isTr ? 'Ana Cümle' : 'Main Clause',
    'main clause': isTr ? 'Ana Cümle' : 'Main Clause',
    'cláusula principal': isTr ? 'Ana Cümle' : 'Main Clause',
    'yan cümle': isTr ? 'Yan Cümle' : 'Subordinate Clause',
    'subordinate clause': isTr ? 'Yan Cümle' : 'Subordinate Clause',
    'cláusula subordinada': isTr ? 'Yan Cümle' : 'Subordinate Clause',
    'cláusula': isTr ? 'Cümlecik' : 'Clause',
    'clause': isTr ? 'Cümlecik' : 'Clause',
    'cümlecik': isTr ? 'Cümlecik' : 'Clause',
    'objeto directo': isTr ? 'Belirtili Nesne' : 'Direct Object',
    'direct object': isTr ? 'Belirtili Nesne' : 'Direct Object',
    'objeto indirecto': isTr ? 'Dolaylı Tümleç' : 'Indirect Object',
    'indirect object': isTr ? 'Dolaylı Tümleç' : 'Indirect Object',
    'objeto': isTr ? 'Nesne' : 'Object',
    'object': isTr ? 'Nesne' : 'Object',
    'nesne': isTr ? 'Nesne' : 'Object',
    'complemento': isTr ? 'Tümleç' : 'Complement',
    'complement': isTr ? 'Tümleç' : 'Complement',
    'tümleç': isTr ? 'Tümleç' : 'Complement',
    'sustantivo': isTr ? 'İsim' : 'Noun',
    'noun': isTr ? 'İsim' : 'Noun',
    'isim': isTr ? 'İsim' : 'Noun',
    'ad': isTr ? 'Ad' : 'Noun',
    'adjetivo': isTr ? 'Sıfat' : 'Adjective',
    'adjective': isTr ? 'Sıfat' : 'Adjective',
    'sıfat': isTr ? 'Sıfat' : 'Adjective',
    'adverbio': isTr ? 'Zarf' : 'Adverb',
    'adverb': isTr ? 'Zarf' : 'Adverb',
    'zarf': isTr ? 'Zarf' : 'Adverb',
    'preposición': isTr ? 'Edat' : 'Preposition',
    'preposition': isTr ? 'Edat' : 'Preposition',
    'edat': isTr ? 'Edat' : 'Preposition',
    'pronombre': isTr ? 'Zamir' : 'Pronoun',
    'pronoun': isTr ? 'Zamir' : 'Pronoun',
    'zamir': isTr ? 'Zamir' : 'Pronoun',
    'infinitivo': isTr ? 'Mastar' : 'Infinitive',
    'infinitive': isTr ? 'Mastar' : 'Infinitive',
    'mastar': isTr ? 'Mastar' : 'Infinitive',
    'gerundio': isTr ? 'Ulaç (Gerund)' : 'Gerund',
    'gerund': isTr ? 'Ulaç (Gerund)' : 'Gerund',
    'ulaç': isTr ? 'Ulaç' : 'Gerund',
    'participio': isTr ? 'Sıfat-Fiil (Participle)' : 'Participle',
    'participle': isTr ? 'Sıfat-Fiil' : 'Participle',
    'sıfat-fiil': isTr ? 'Sıfat-Fiil' : 'Participle',
    'participio pasado': isTr ? 'Geçmiş Zaman Sıfat-Fiili' : 'Past Participle',
    'past participle': isTr ? 'Geçmiş Zaman Sıfat-Fiili' : 'Past Participle',
    'conjunción': isTr ? 'Bağlaç' : 'Conjunction',
    'conjunction': isTr ? 'Bağlaç' : 'Conjunction',
    'bağlaç': isTr ? 'Bağlaç' : 'Conjunction',
    'negación': isTr ? 'Olumsuzluk' : 'Negation',
    'negation': isTr ? 'Olumsuzluk' : 'Negation',
    'olumsuzluk': isTr ? 'Olumsuzluk' : 'Negation',
    'subyuntivo': isTr ? 'Dilek-Şart Kipi (Subjunctive)' : 'Subjunctive Mood',
    'subjuntivo': isTr ? 'Dilek-Şart Kipi (Subjunctive)' : 'Subjunctive Mood',
    'subjunctive': isTr ? 'Dilek-Şart Kipi' : 'Subjunctive Mood',
    'dilek-şart kipi': isTr ? 'Dilek-Şart Kipi' : 'Subjunctive Mood',
    'zarf-fiil': isTr ? 'Zarf-Fiil' : 'Adverbial Suffix / Converb',
    'converb': isTr ? 'Zarf-Fiil' : 'Converb / Adverbial',
    'kök': isTr ? 'Kök' : 'Stem',
    'gövde': isTr ? 'Gövde' : 'Stem / Base',
    'stem': isTr ? 'Gövde' : 'Stem',
    'suffix': isTr ? 'Ek' : 'Suffix',
    'ek': isTr ? 'Ek' : 'Suffix'
  };

  return formulaStr.replace(/\[(.*?)\]/g, (match, inner) => {
    const cleanKey = inner.trim().toLowerCase();
    if (termMap[cleanKey]) {
      return `[${termMap[cleanKey]}]`;
    }
    return match;
  });
}

function translateEducationalText(text, lang = currentLang) {
  if (!text || typeof text !== 'string') return text;
  
  const isTr = (lang === 'tr');
  const enTrMap = window.EDUCATIONAL_SENTENCE_MAP_EN_TR || {};
  const trEnMap = window.EDUCATIONAL_SENTENCE_MAP_TR_EN || {};
  
  // Split by newline to preserve paragraph and bullet structure
  const lines = text.split('\n');
  const translatedLines = lines.map(line => {
    const rawLine = line;
    const bulletMatch = rawLine.match(/^([•\-\*\s]+)(.*)$/);
    const bullet = bulletMatch ? bulletMatch[1] : '';
    const cleanContent = (bulletMatch ? bulletMatch[2] : rawLine).trim();
    if (!cleanContent) return rawLine;

    // 1. Direct dictionary lookup
    if (isTr) {
      if (enTrMap[cleanContent]) return bullet + enTrMap[cleanContent];
      const noDot = cleanContent.replace(/\.+$/, '');
      if (enTrMap[noDot]) return bullet + enTrMap[noDot] + (cleanContent.endsWith('.') ? '.' : '');
    } else {
      if (trEnMap[cleanContent]) return bullet + trEnMap[cleanContent];
      const noDot = cleanContent.replace(/\.+$/, '');
      if (trEnMap[noDot]) return bullet + trEnMap[noDot] + (cleanContent.endsWith('.') ? '.' : '');
    }

    // 2. Legacy sentence pair lookup
    if (Array.isArray(window.EDUCATIONAL_SENTENCE_PAIRS)) {
      for (const [en, tr] of window.EDUCATIONAL_SENTENCE_PAIRS) {
        if (isTr && cleanContent === en) return bullet + tr;
        if (!isTr && cleanContent === tr) return bullet + en;
      }
    }

    // 3. Dynamic Pedagogical Template Regex Engine (covers future / AI-generated lessons)
    let processed = cleanContent;
    if (isTr) {
      // Comparison Context Tags & Contrast Labels
      processed = processed.replace(/^Colloquial$/i, "Günlük / Samimi");
      processed = processed.replace(/^Formal$/i, "Resmi / Saygılı");
      processed = processed.replace(/^Informal$/i, "Samimi / Günlük");
      processed = processed.replace(/^Standard$/i, "Standart / Genel");
      processed = processed.replace(/^Slang$/i, "Argo / Sokak Dili");
      processed = processed.replace(/^Literary$/i, "Edebi / Sanatsal");
      processed = processed.replace(/^Polite$/i, "Kibar / Nezaket");
      processed = processed.replace(/^Conversational$/i, "Günlük Konuşma");
      processed = processed.replace(/^Direct\s*\/\s*Conversational$/i, "Doğrudan / Günlük Konuşma");
      processed = processed.replace(/^Elevated\s*\/\s*Nuanced$/i, "İleri Düzey / Edebi Nüans");
      processed = processed.replace(/^Formal\s*\/\s*Academic$/i, "Resmi / Akademik");
      processed = processed.replace(/^Standard\s*\/\s*Neutral$/i, "Standart / Nötr");
      processed = processed.replace(/^Common Error\s*\/\s*Incorrect$/i, "Sık Yapılan Hata / Yanlış");
      processed = processed.replace(/^Authentic\s*\/\s*Correct$/i, "Doğal / Doğru Kullanım");
      // Phonetic/contextual variation labels
      processed = processed.replace(/^Standard Pronunciation$/i, "Normal Telaffuz");
      processed = processed.replace(/^Contextual Variation$/i, "Bağlama Göre Değişen Telaffuz");
      processed = processed.replace(/^Contextual Pronunciation$/i, "Bağlamsal Telaffuz");
      processed = processed.replace(/^Natural Pronunciation$/i, "Doğal Telaffuz");
      processed = processed.replace(/^Regional Variation$/i, "Bölgesel Farklılık");
      processed = processed.replace(/^Emphatic Pronunciation$/i, "Vurgulu Telaffuz");

      // Contrast Notes & Descriptions (Image 1)
      processed = processed.replace(/^Standard informal greeting\.?$/i, "Standart samimi / günlük selamlama.");
      processed = processed.replace(/^Standard formal greeting\.?$/i, "Standart resmi selamlama.");
      processed = processed.replace(/^Standard greeting\.?$/i, "Standart selamlama ifadesi.");
      processed = processed.replace(/^Informal greeting\.?$/i, "Samimi selamlama ifadesi.");
      processed = processed.replace(/^Formal greeting\.?$/i, "Resmi selamlama ifadesi.");
      processed = processed.replace(/^Casual conversational style\.?$/i, "Günlük ve samimi konuşma üslubu.");
      processed = processed.replace(/^Polite and respectful address\.?$/i, "Kibar ve saygılı hitap biçimi.");
      processed = processed.replace(/^Common spoken phrasing\.?$/i, "Konuşma dilinde yaygın kullanım.");
      processed = processed.replace(/^Everyday conversational phrasing\.?$/i, "Günlük konuşma dili kalıbı.");
      processed = processed.replace(/^Everyday conversational formulation\.?$/i, "Günlük konuşma dili kalıbı.");
      processed = processed.replace(/^Standard conversational formulation\.?$/i, "Standart günlük konuşma kalıbı.");
      processed = processed.replace(/^Formal written expression\.?$/i, "Resmi yazı dili ifadesi.");
      processed = processed.replace(/^Sophisticated formal or literary expression\.?$/i, "Zengin ve incelikli edebi veya resmi anlatım.");
      processed = processed.replace(/^Sophisticated formal\/literary expression\.?$/i, "Zengin ve incelikli edebi/resmi anlatım.");
      processed = processed.replace(/^Everyday colloquial sentence in (.*)\.?$/i, "$1 dilinde günlük samimi cümle.");
      processed = processed.replace(/^Advanced nuanced sentence in (.*)\.?$/i, "$1 dilinde ileri düzey nüanslı cümle.");
      // Phonetic notes
      processed = processed.replace(/^Normal pronunciation\.?$/i, "Normal telaffuz.");
      processed = processed.replace(/^Standard pronunciation\.?$/i, "Normal telaffuz.");
      processed = processed.replace(/^Contextual variation\.?$/i, "Bağlama göre değişen telaffuz.");
      processed = processed.replace(/^Context-dependent pronunciation\.?$/i, "Bağlama göre değişen telaffuz.");
      processed = processed.replace(/^Pronunciation varies by context\.?$/i, "Telaffuz bağlama göre değişir.");
      processed = processed.replace(/^The (.*) sound is softened before (.*)\./i, "$1 sesi $2 harfinden önce yumuşatılır.");
      processed = processed.replace(/^The (.*) sound is typically (.*) before (.*)\./i, "$1 sesi genellikle $3 harfinden önce $2 olarak telaffuz edilir.");
      processed = processed.replace(/^Used (.*) before (.*)\./i, "$2 harfinden önce $1 kullanılır.");
      processed = processed.replace(/^Used in most contexts\./i, "Çoğu bağlamda kullanılır.");
      processed = processed.replace(/^Used before (.*) sounds\./i, "$1 sesleri öncesinde kullanılır.");
      processed = processed.replace(/^Used before the vowels? (.*)\./i, "$1 sesli harfi\/harfleri öncesinde kullanılır.");

      // Syntactic & Phonetic Formula Sentences
      processed = processed.replace(/^Each letter has its own sound\.?$/i, "Her harfin kendine özgü bir sesi vardır.");
      processed = processed.replace(/^Every letter has its own sound\.?$/i, "Her harfin kendine özgü bir sesi vardır.");
      processed = processed.replace(/^Every letter has a unique sound\.?$/i, "Her harfin kendine özgü bir sesi vardır.");
      processed = processed.replace(/^Each letter has a specific sound in (.*)\.?$/i, "$1 dilinde her harfin belirli bir sesi vardır.");
      processed = processed.replace(/^Each letter has a specific sound\.?$/i, "Her harfin belirli bir sesi vardır.");
      processed = processed.replace(/^Cada letra tiene un sonido único\.?$/i, "Her harfin kendine özgü bir sesi vardır.");
      processed = processed.replace(/^Cada letra tiene un sonido particular\.?$/i, "Her harfin kendine özgü bir sesi vardır.");


      // Grammatical Analysis & Breakdown Patterns (Image 3)
      processed = processed.replace(/^The verb '(.*)' changes according to the subject pronoun\.?$/i, "'$1' fiili özne zamirine göre çekimlenir.");
      processed = processed.replace(/^The verb '(.*)' conjugates based on the subject pronoun\.?$/i, "'$1' fiili özne zamirine göre çekimlenir.");
      processed = processed.replace(/^The verb '(.*)' conjugates based on the subject\.?$/i, "'$1' fiili özneye göre çekimlenir.");
      processed = processed.replace(/^The verb '(.*)' changes according to (.*)\.?$/i, "'$1' fiili $2 durumuna göre değişir.");
      processed = processed.replace(/changes according to the subject pronoun/i, "özne zamirine göre çekimlenir");
      processed = processed.replace(/changes according to the subject/i, "özneye göre çekimlenir");
      processed = processed.replace(/^Breakdown of the (.*) in the example\.?$/i, "Örnekteki $1 yapısının analizi.");
      processed = processed.replace(/^The vowels (.*) are pronounced distinctly\.?$/i, "$1 sesli harfleri belirgin ve net şekilde telaffuz edilir.");
      processed = processed.replace(/^The vowels (.*) are pronounced (.*)\.?$/i, "$1 sesli harfleri $2 şekilde telaffuz edilir.");
      processed = processed.replace(/^The '([^']+)' in '([^']+)' is pronounced as '([^']+)' while in '([^']+)' it is pronounced as '([^']+)'\.?$/i, 
        "'$2' içindeki '$1', '$3' olarak; '$4' içindeki ise '$5' olarak telaffuz edilir.");
      processed = processed.replace(/^Consonants can have different sounds depending on their position in a word\.?$/i, 
        "Sessiz harfler kelimedeki konumlarına göre farklı sesler çıkarabilir.");
      processed = processed.replace(/^Consonant Variability$/i, "Sessiz Harf Değişkenliği");
      processed = processed.replace(/^Syllable Structure$/i, "Hece Yapısı");
      processed = processed.replace(/^Vowel Clarity$/i, "Sesli Harf Netliği");
      processed = processed.replace(/^Pronunciation Rules$/i, "Telaffuz Kuralları");
      processed = processed.replace(/^Stress and Accentuation$/i, "Vurgu ve Tonlama");
      processed = processed.replace(/^Sound-Symbol Association$/i, "Ses-Harf Eşleşmesi");
      processed = processed.replace(/^Suffix Mechanics & Morphological Trigger$/i, "Biçimbirimsel Tetikleyici ve Ek Mekaniği");
      processed = processed.replace(/^Syntactic Subordination & Meaning Dependency$/i, "Yan Cümle Bağımlılığı ve Anlamsal İlişki");
      processed = processed.replace(/^Register Modulation & Stylistic Nuance$/i, "Üslup ve İleri Düzey Nüans");

      processed = processed.replace(/^These terms are (crucial|essential|fundamental|important) for understanding (.*) in (.*)\.?$/i, 
        "$3 dilinde $2 konusunu anlamak için bu terimler çok önemlidir.");
      processed = processed.replace(/^These terms are (crucial|essential|fundamental|important) for (.*)\.?$/i, 
        "Bu terimler $2 için çok önemlidir.");
      processed = processed.replace(/^Understanding these (terms|words|phrases) helps with (.*)\.?$/i, 
        "Bu $1'i anlamak $2 konusunda yardımcı olur.");
      processed = processed.replace(/^These examples show how to use (.*) in everyday situations\.?$/i, 
        "Bu örnekler $1 konusunun günlük durumlarda nasıl kullanılacağını gösterir.");
      processed = processed.replace(/^These phrases are (crucial|essential) for (.*)\.?$/i, 
        "Bu ifadeler $2 için çok önemlidir.");
      processed = processed.replace(/^These sentences illustrate (.*)\.?$/i, 
        "Bu cümleler $1 konusunu açıklar.");
      processed = processed.replace(/^Example:\s*(.*)\s*\((.*)\)/i, (m, phrase, paren) => {
        const trParen = translateOption(paren, 'tr');
        return `Örnek: ${phrase} (${trParen})`;
      });
      processed = processed.replace(/'(.*)' is used to express (.*)\.?/i, "'$1', $2 ifade etmek için kullanılır.");
      processed = processed.replace(/'(.*)' specifically refers to (.*)\.?/i, "'$1' özellikle $2 anlamına gelir.");
      processed = processed.replace(/The correct answer is '(.*)'/i, "Doğru cevap: '$1'");
      processed = processed.replace(/Other options do not fit the context\.?/i, "Diğer seçenekler bağlama uymaz.");
      processed = processed.replace(/^(The\s+)?discussion should be constructive and respectful\.?$/i, "Tartışma yapıcı ve saygılı olmalıdır.");
      processed = processed.replace(/^Encourage open dialogue;? actively listen to counterarguments\.?$/i, "Açık bir diyalogu teşvik edin; karşı argümanlara aktif olarak dinleyin.");
    } else {
      // Reverse TR -> EN
      processed = processed.replace(/^Günlük\s*\/\s*Samimi$/i, "Colloquial");
      processed = processed.replace(/^Resmi\s*\/\s*Saygılı$/i, "Formal");
      processed = processed.replace(/^Samimi\s*\/\s*Günlük$/i, "Informal");
      processed = processed.replace(/^Standart\s*\/\s*Genel$/i, "Standard");
      processed = processed.replace(/^Standart samimi\s*\/\s*günlük selamlama\.?$/i, "Standard informal greeting.");
      processed = processed.replace(/^Standart resmi selamlama\.?$/i, "Standard formal greeting.");
      processed = processed.replace(/^Standart selamlama ifadesi\.?$/i, "Standard greeting.");
      processed = processed.replace(/^Samimi selamlama ifadesi\.?$/i, "Informal greeting.");
      processed = processed.replace(/^Resmi selamlama ifadesi\.?$/i, "Formal greeting.");
      processed = processed.replace(/^Günlük ve samimi konuşma üslubu\.?$/i, "Casual conversational style.");
      processed = processed.replace(/^Kibar ve saygılı hitap biçimi\.?$/i, "Polite and respectful address.");
      // Phonetic TR→EN reverses
      processed = processed.replace(/^Normal [Tt]elaffuz\.?$/i, "Standard pronunciation.");
      processed = processed.replace(/^Bağlama [Gg]öre [Dd]eğişen [Tt]elaffuz\.?$/i, "Contextual variation.");
      processed = processed.replace(/^Bağlamsal [Tt]elaffuz\.?$/i, "Contextual pronunciation.");
      processed = processed.replace(/^Doğal [Tt]elaffuz\.?$/i, "Natural pronunciation.");
      processed = processed.replace(/^Bölgesel [Ff]arklılık\.?$/i, "Regional variation.");
      processed = processed.replace(/^Vurgulu [Tt]elaffuz\.?$/i, "Emphatic pronunciation.");
      processed = processed.replace(/^Çoğu bağlamda kullanılır\.?$/i, "Used in most contexts.");
      processed = processed.replace(/^Telaffuz bağlama göre değişir\.?$/i, "Pronunciation varies by context.");
      processed = processed.replace(/^Doğrudan\s*\/\s*Günlük Konuşma$/i, "Direct / Conversational");
      processed = processed.replace(/^Sessiz Harf Değişkenliği$/i, "Consonant Variability");
      processed = processed.replace(/^Hece Yapısı$/i, "Syllable Structure");
      processed = processed.replace(/^Sesli Harf Netliği$/i, "Vowel Clarity");
      processed = processed.replace(/^Telaffuz Kuralları$/i, "Pronunciation Rules");
      processed = processed.replace(/^Vurgu ve Tonlama$/i, "Stress and Accentuation");
      processed = processed.replace(/^Biçimbirimsel Tetikleyici ve Ek Mekaniği$/i, "Suffix Mechanics & Morphological Trigger");
      processed = processed.replace(/^Yan Cümle Bağımlılığı ve Anlamsal İlişki$/i, "Syntactic Subordination & Meaning Dependency");
      processed = processed.replace(/^Üslup ve İleri Düzey Nüans$/i, "Register Modulation & Stylistic Nuance");
      processed = processed.replace(/^(.*) sesli harfleri belirgin ve net şekilde telaffuz edilir\.?$/i, "The vowels $1 are pronounced distinctly.");
      processed = processed.replace(/^Sessiz harfler kelimedeki konumlarına göre farklı sesler çıkarabilir\.?$/i, "Consonants can have different sounds depending on their position in a word.");
      processed = processed.replace(/^'(.*)' fiili özne zamirine göre çekimlenir\.?$/i, "The verb '$1' changes according to the subject pronoun.");
      processed = processed.replace(/^Doğrudan\s*\/\s*Günlük Konuşma$/i, "Direct / Conversational");
      processed = processed.replace(/^İleri Düzey\s*\/\s*Edebi Nüans$/i, "Elevated / Nuanced");
      processed = processed.replace(/^Standart günlük konuşma kalıbı\.?$/i, "Standard conversational formulation.");
      processed = processed.replace(/^Zengin ve incelikli edebi\/resmi anlatım\.?$/i, "Sophisticated formal/literary expression.");
      processed = processed.replace(/^Zengin ve incelikli edebi veya resmi anlatım\.?$/i, "Sophisticated formal or literary expression.");
      processed = processed.replace(/^Bu terimler (.*) için çok önemlidir\.?$/i, "These terms are essential for $1.");
      processed = processed.replace(/^Bu terimler günlük yaşamda sıkça kullanılır\.?$/i, "These terms are frequently used in daily life.");
      processed = processed.replace(/^Bu cümleler günlük hayatta nasıl kullanılır\.?$/i, "How these sentences are used in everyday life.");
      processed = processed.replace(/^Bu cümleler günlük hayatta nasıl kullanılabilir\.?$/i, "How these sentences can be used in everyday life.");
      // Syntactic & Phonetic Formula Sentences
      processed = processed.replace(/^Her harfin kendine özgü bir sesi vardır\.?$/i, "Each letter has its own sound.");
      processed = processed.replace(/^Her harfin, telaffuz için önemli olan benzersiz bir sesi vardır\.?$/i, "Each letter has a unique sound that is important for pronunciation.");
      processed = processed.replace(/^Her harfin, konuşma ve yazım için önemli olan benzersiz bir telaffuzu vardır\.?$/i, "Each letter has a unique pronunciation that is important for speaking and spelling.");
      processed = processed.replace(/^Her harfin belirli bir sesi vardır\.?$/i, "Each letter has a specific sound.");
      processed = processed.replace(/^Cada letra tiene un sonido único\.?$/i, "Each letter has its own sound.");
      processed = processed.replace(/^Cada letra tiene un sonido particular\.?$/i, "Each letter has a specific sound.");

      // Pragmatic & Lexical Example Sentences / Advice
      processed = processed.replace(/^Tartışma yapıcı ve saygılı olmalıdır\.?$/i, "A discussion should be constructive and respectful.");
      processed = processed.replace(/^Açık bir diyalogu teşvik edin;? karşı argümanlara aktif olarak dinleyin\.?$/i, "Encourage open dialogue; actively listen to counterarguments.");
      processed = processed.replace(/^Açık bir diyalog teşvik edin;? karşı argümanları aktif olarak dinleyin\.?$/i, "Encourage open dialogue; actively listen to counterarguments.");
      processed = processed.replace(/^(.*) yapıcı ve saygılı olmalıdır\.?$/i, "$1 should be constructive and respectful.");
      processed = processed.replace(/^(.*) olmalıdır\.?$/i, "$1 should be.");
      processed = processed.replace(/^Açık bir diyalogu teşvik edin\.?$/i, "Encourage open dialogue.");
      processed = processed.replace(/^Karşı argümanlara aktif olarak dinleyin\.?$/i, "Actively listen to counterarguments.");

      processed = processed.replace(/^Örnek:\s*(.*)\s*\((.*)\)/i, (m, phrase, paren) => {
        const enParen = translateOption(paren, 'en');
        return `Example: ${phrase} (${enParen})`;
      });
      processed = processed.replace(/'(.*)' kelimesi (.*) ifade eder\.?/i, "The word '$1' expresses $2.");
      processed = processed.replace(/'(.*)' ifadesi (.*) için kullanılır\.?/i, "The phrase '$1' is used for $2.");
      processed = processed.replace(/Diğer seçenekler (.*) uygun değildir\.?/i, "Other options are not suitable in this context.");
      processed = processed.replace(/Doğru cevap (.*)\.?/i, "The correct answer $1.");
      processed = sanitizeEnglishExplanation(processed);
    }

    if (processed !== cleanContent) {
      return bullet + processed;
    }

    // 4. Substring fallback for embedded phrases
    let subStr = cleanContent;
    if (isTr) {
      for (const [en, tr] of (window.EDUCATIONAL_SENTENCE_PAIRS || [])) {
        if (subStr.includes(en)) subStr = subStr.split(en).join(tr);
      }
    } else {
      for (const [en, tr] of (window.EDUCATIONAL_SENTENCE_PAIRS || [])) {
        if (subStr.includes(tr)) subStr = subStr.split(tr).join(en);
      }
      subStr = sanitizeEnglishExplanation(subStr);
    }

    // 5. On-Demand Background Translation for brand new future classrooms
    if (subStr === cleanContent && cleanContent.length > 5 && !cleanContent.startsWith('http')) {
      const isEnglishSource = !/[çğıöşüÇĞİÖŞÜ]/.test(cleanContent) && /\b(the|and|is|are|in|for|with|of|to|these|this|vowels|consonants)\b/i.test(cleanContent);
      const isTurkishSource = /[çğıöşüÇĞİÖŞÜ]/.test(cleanContent) || /\b(ve|ile|bir|bu|için|nasıl|olarak|kullanılır|anlatırken|tanımlar)\b/i.test(cleanContent);
      const needsTranslation = (isTr && isEnglishSource) || (!isTr && isTurkishSource);
      
      if (needsTranslation) {
        if (!window._pendingMaterialTranslations) window._pendingMaterialTranslations = new Set();
        const cacheKey = `${lang}:${cleanContent}`;
        if (!window._pendingMaterialTranslations.has(cacheKey)) {
          window._pendingMaterialTranslations.add(cacheKey);
          fetch('/api/translate/material', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: cleanContent, target_lang: lang })
          }).then(r => r.json()).then(data => {
            if (data && data.translated && data.translated !== cleanContent && data.translated !== 'None') {
              if (isTr) {
                if (!window.EDUCATIONAL_SENTENCE_MAP_EN_TR) window.EDUCATIONAL_SENTENCE_MAP_EN_TR = {};
                window.EDUCATIONAL_SENTENCE_MAP_EN_TR[cleanContent] = data.translated;
              } else {
                if (!window.EDUCATIONAL_SENTENCE_MAP_TR_EN) window.EDUCATIONAL_SENTENCE_MAP_TR_EN = {};
                window.EDUCATIONAL_SENTENCE_MAP_TR_EN[cleanContent] = data.translated;
              }
            }
          }).catch(() => {});
        }
      }
    }

    return bullet + subStr;
  });

  return translatedLines.join('\n');
}

function translateDictExplanation(explanation, isTr) {
  if (!explanation) return '';
  if (!isTr) return explanation;
  let res = explanation;
  res = res.replace(/The phrase '(.*)' translates to '(.*)' in English\. It is a common greeting in Spanish-speaking countries\./i, (m, phrase, eng) => {
    const tr = translateOption(eng, 'tr') || 'merhaba, nasılsın?';
    return `'${phrase}' ifadesi '${tr}' anlamına gelir. İspanyolca konuşulan ülkelerde yaygın bir selamlaşmadır.`;
  });
  res = res.replace(/The phrase '(.*)' translates to '(.*)' in English\./i, (m, phrase, eng) => {
    const tr = translateOption(eng, 'tr');
    return `'${phrase}' ifadesi '${tr}' anlamına gelir.`;
  });
  res = res.replace(/The term '(.*)' translates to '(.*)' in English\./i, (m, term, eng) => {
    const tr = translateOption(eng, 'tr');
    return `'${term}' terimi '${tr}' anlamına gelir.`;
  });
  res = res.replace(/'(.*)' means '(.*)'\./i, (m, word, meaning) => {
    const meaningTR = translateOption(meaning, 'tr');
    return `'${word}', '${meaningTR}' anlamına gelir.`;
  });
  res = res.replace(/Commonly used in daily interaction\./i, "Günlük iletişimde yaygın olarak kullanılır.");
  res = res.replace(/This is a high-frequency word we've pre-verified for you!/i, "Bu, sizin için önceden doğruladığımız yüksek frekanslı bir kelimedir!");
  return res;
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

  const headers = Object.assign({}, opts.headers || {});
  if (opts.body) {
    headers['Content-Type'] = 'application/json';
  }
  if (currentUser && currentUser.id) {
    headers['X-User-Id'] = currentUser.id;
    headers['X-User-Role'] = currentUser.role || '';
  }

  const res = await fetch(url, {
    method: opts.method || 'GET',
    headers: headers,
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
    document.getElementById('login-email').value = 'atunca96@gmail.com';
    document.getElementById('login-password').value = 'ALper2002@';
  } else {
    document.getElementById('student-number').value = '176725004';
    const pwdEl = document.getElementById('student-password');
    if (pwdEl) pwdEl.value = '1234';
  }
}

// ── SPA Router & Route Definitions ──
const _ROUTE_MAP = {
  '/': { screen: 'login-screen' },
  '/login': { screen: 'login-screen' },
  '/classrooms': { screen: 'classroom-selection-screen' },
  '/portal': { screen: 'student-portal-screen' },
  '/waiting': { screen: 'waiting-room-screen' },
  '/overview': { screen: 'lecturer-dashboard', tab: 'overview' },
  '/curriculum': { screen: 'lecturer-dashboard', tab: 'curriculum' },
  '/activities': { screen: 'lecturer-dashboard', tab: 'activities' },
  '/quizzes': { screen: 'lecturer-dashboard', tab: 'quizzes-mgmt' },
  '/assignments': { screen: 'lecturer-dashboard', tab: 'assignments-mgmt' },
  '/students': { screen: 'lecturer-dashboard', tab: 'students-tab' },
  '/materials': { screen: 'lecturer-dashboard', tab: 'study-materials' },
  '/textbook': { screen: 'lecturer-dashboard', tab: 'book' },
  '/messages': { screen: 'lecturer-dashboard', tab: 'inbox' },
  '/home': { screen: 'student-dashboard', tab: 's-home' },
  '/practice': { screen: 'student-dashboard', tab: 's-practice' },
  '/my-quizzes': { screen: 'student-dashboard', tab: 's-quizzes' },
  '/my-assignments': { screen: 'student-dashboard', tab: 's-assignments' },
  '/my-materials': { screen: 'student-dashboard', tab: 's-study-tab' },
  '/my-textbook': { screen: 'student-dashboard', tab: 's-book' },
  '/my-messages': { screen: 'student-dashboard', tab: 's-messages' }
};

const _TAB_TO_PATH = {
  'overview': '/overview',
  'curriculum': '/curriculum',
  'activities': '/activities',
  'quizzes-mgmt': '/quizzes',
  'assignments-mgmt': '/assignments',
  'students-tab': '/students',
  'study-materials': '/materials',
  'book': '/textbook',
  'inbox': '/messages',
  's-home': '/home',
  's-practice': '/practice',
  's-quizzes': '/my-quizzes',
  's-assignments': '/my-assignments',
  's-study-tab': '/my-materials',
  's-book': '/my-textbook',
  's-messages': '/my-messages'
};

const _TAB_TO_PATH_VALUES = new Set(Object.values(_TAB_TO_PATH));

const _SCREEN_TO_PATH = {
  'login-screen': '/login',
  'classroom-selection-screen': '/classrooms',
  'student-portal-screen': '/portal',
  'waiting-room-screen': '/waiting'
};

let _isNavigatingFromPopState = false;

function parseRouteUrl(pathname = window.location.pathname, search = window.location.search) {
  let rawPath = pathname || '/';
  let rawSearch = search || '';
  if (rawPath.includes('?')) {
    const qIdx = rawPath.indexOf('?');
    rawSearch = rawPath.slice(qIdx) + (rawSearch ? '&' + rawSearch.replace(/^\?/, '') : '');
    rawPath = rawPath.slice(0, qIdx);
  }

  let classroomRef = null;
  if (rawSearch) {
    try {
      const params = new URLSearchParams(rawSearch);
      classroomRef = params.get('c') || params.get('course') || params.get('code') || params.get('id') || params.get('classroom');
    } catch (e) {}

    // Support bare ?248258, ?=248258, overview=?248258
    if (!classroomRef) {
      const clean = rawSearch.replace(/^\?/, '').trim();
      if (clean) {
        if (!clean.includes('&') && !clean.includes('=')) {
          classroomRef = clean;
        } else if (clean.startsWith('=')) {
          classroomRef = clean.replace(/^=+/, '').trim();
        }
      }
    }
  }

  let cleanPath = rawPath.replace(/\/+$/, '') || '/';
  const parts = cleanPath.split('/').filter(Boolean);

  if (parts.length >= 2 && parts[0] === 'c') {
    classroomRef = classroomRef || parts[1];
    cleanPath = '/' + (parts[2] || 'overview');
  } else if (parts.length === 2 && _ROUTE_MAP['/' + parts[0]]) {
    classroomRef = classroomRef || parts[1];
    cleanPath = '/' + parts[0];
  }

  const route = _ROUTE_MAP[cleanPath] || null;
  return {
    path: cleanPath,
    route: route,
    screen: route ? route.screen : null,
    tab: route ? route.tab : null,
    classroomRef: classroomRef
  };
}

function updateUrlPath(path, replace = false) {
  if (!path) return;
  let fullUrl = path;
  if (!fullUrl.includes('?') && _TAB_TO_PATH_VALUES.has(fullUrl) && currentCourse) {
    const code = currentCourse.code || currentCourse.id;
    if (code) {
      fullUrl = `${path}?c=${encodeURIComponent(code)}`;
    }
  }

  const currentFull = window.location.pathname + window.location.search;
  if (currentFull === fullUrl) return;

  try {
    if (replace) {
      window.history.replaceState({ path: fullUrl }, '', fullUrl);
    } else {
      window.history.pushState({ path: fullUrl }, '', fullUrl);
    }
  } catch (e) {
    console.warn('Router updateUrlPath error:', e);
  }
}

function handlePopState(e) {
  const fullUrl = window.location.pathname + window.location.search;
  applyRoute(fullUrl, true);
}

async function applyRoute(urlOrPath, fromPopState = false) {
  _isNavigatingFromPopState = fromPopState;
  try {
    const parsed = parseRouteUrl(urlOrPath);
    const { route, screen, tab, classroomRef, path } = parsed;

    if (!currentUser) {
      if (path !== '/' && path !== '/login') {
        sessionStorage.setItem('aula_redirect_path', urlOrPath);
      }
      showScreen('login-screen', false);
      return;
    }

    if (!route) {
      if (currentUser.role === 'lecturer') {
        if (currentCourse) {
          showScreen('lecturer-dashboard', false);
          const btn = document.querySelector('#lecturer-dashboard [data-tab="overview"]');
          if (btn) switchTab(btn, false, false);
        } else {
          showClassroomSelection();
        }
      } else {
        if (currentCourse) {
          showScreen('student-dashboard', false);
          const btn = document.querySelector('#student-dashboard [data-tab="s-home"]');
          if (btn) switchTab(btn, false, false);
        } else {
          showStudentPortal();
        }
      }
      return;
    }

    if (screen === 'login-screen') {
      showScreen('login-screen', false);
    } else if (screen === 'classroom-selection-screen') {
      if (currentUser.role !== 'lecturer') {
        showScreen('login-screen');
      } else {
        showClassroomSelection();
      }
    } else if (screen === 'student-portal-screen') {
      if (currentUser.role !== 'student') {
        showScreen('login-screen');
      } else {
        showStudentPortal();
      }
    } else if (screen === 'waiting-room-screen') {
      showScreen('waiting-room-screen', false);
    } else if (screen === 'lecturer-dashboard') {
      if (currentUser.role !== 'lecturer') {
        sessionStorage.setItem('aula_redirect_path', urlOrPath);
        showScreen('login-screen');
      } else {
        if (classroomRef && (!currentCourse || (currentCourse.code !== classroomRef && currentCourse.id !== classroomRef))) {
          try {
            const courses = await api('/courses');
            const found = courses.find(c => c.code === classroomRef || c.id === classroomRef);
            if (found) {
              if (tab) localStorage.setItem('aula_last_tab', tab);
              await selectClassroom(found.id, true);
              return;
            }
          } catch (e) {
            console.error('Error switching classroom in route:', e);
          }
        }
        showScreen('lecturer-dashboard', false);
        if (tab) {
          const btn = document.querySelector(`#lecturer-dashboard [data-tab="${tab}"]`);
          if (btn) switchTab(btn, false, false);
        }
      }
    } else if (screen === 'student-dashboard') {
      if (currentUser.role !== 'student') {
        sessionStorage.setItem('aula_redirect_path', urlOrPath);
        showScreen('login-screen');
      } else {
        if (classroomRef && (!currentCourse || (currentCourse.code !== classroomRef && currentCourse.id !== classroomRef))) {
          try {
            const courses = await api('/courses');
            const found = courses.find(c => c.code === classroomRef || c.id === classroomRef);
            if (found) {
              if (tab) localStorage.setItem('aula_last_tab', tab);
              await selectClassroom(found.id, false);
              return;
            }
          } catch (e) {
            console.error('Error switching classroom in route:', e);
          }
        }
        showScreen('student-dashboard', false);
        if (tab) {
          const btn = document.querySelector(`#student-dashboard [data-tab="${tab}"]`);
          if (btn) switchTab(btn, false, false);
        }
      }
    }
  } finally {
    _isNavigatingFromPopState = false;
  }
}

function initRouter() {
  window.addEventListener('popstate', handlePopState);
}

function sanitizeStudentDom() {
  if (!currentUser || currentUser.role !== 'student') return;
  const teacherElementIds = [
    'classroom-method-modal',
    'ai-architect-modal',
    'create-classroom-modal',
    'draft-modal',
    'student-detail-modal',
    'classroom-selection-screen',
    'lecturer-dashboard',
    'admin-panel',
    'admin-student-panel',
    'admin-curriculum-panel',
    'admin-students-panel',
    'new-chat-modal'
  ];
  teacherElementIds.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.remove();
  });
}

async function completeLogin(user, isFresh = false) {
  currentUser = user;
  if (user && user.role === 'student') {
    sanitizeStudentDom();
  }
  if (user.course_id) courseId = user.course_id;
  startUserHeartbeat();

  if (isFresh) {
    localStorage.removeItem('aula_last_tab');
    localStorage.removeItem('aula_last_course');
  }

  // Session Storage is per-tab, so it's safer for multiple roles in different tabs
  sessionStorage.setItem('aula_user', JSON.stringify(user));

  let remember = true;
  if (user && user.role === 'student') {
    const studentRememberEl = document.getElementById('student-login-remember');
    remember = studentRememberEl ? studentRememberEl.checked : true;
  } else {
    const lecturerRememberEl = document.getElementById('login-remember');
    remember = lecturerRememberEl ? lecturerRememberEl.checked : true;
  }

  // Preserve existing persistent login if restoring session on page reload
  if (!isFresh && localStorage.getItem('aula_user')) {
    remember = true;
  }

  if (remember) {
    localStorage.setItem('aula_user', JSON.stringify(user));
  } else if (isFresh) {
    localStorage.removeItem('aula_user');
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
            if (remember) localStorage.setItem('aula_user', JSON.stringify(currentUser));
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

  const currentFullUrl = window.location.pathname + window.location.search;
  const redirectPath = sessionStorage.getItem('aula_redirect_path');
  const targetUrl = redirectPath || (window.location.pathname !== '/login' && window.location.pathname !== '/' ? currentFullUrl : null);
  if (redirectPath) sessionStorage.removeItem('aula_redirect_path');

  const parsed = parseRouteUrl(targetUrl || window.location.pathname, targetUrl ? '' : window.location.search);
  const targetTab = parsed.tab;
  const targetClassroomRef = parsed.classroomRef;
  const targetPath = parsed.path;

  if (targetTab) {
    localStorage.setItem('aula_last_tab', targetTab);
  }

  if (currentUser.role === 'lecturer') {
    if (targetPath === '/classrooms') {
      showClassroomSelection();
    } else {
      let courseIdToSelect = null;
      if (targetClassroomRef) {
        try {
          const courses = await api('/courses');
          const found = courses.find(c => c.code === targetClassroomRef || c.id === targetClassroomRef);
          if (found) courseIdToSelect = found.id;
        } catch (e) {
          console.error("Failed fetching courses for URL resolution:", e);
        }
      }
      if (!courseIdToSelect) {
        courseIdToSelect = localStorage.getItem('aula_last_course');
      }
      if (courseIdToSelect) {
        await selectClassroom(courseIdToSelect);
      } else {
        showClassroomSelection();
      }
    }
  } else {
    // Global Student Portal
    if (targetPath === '/portal') {
      showStudentPortal();
    } else {
      let courseIdToSelect = null;
      if (targetClassroomRef) {
        try {
          const courses = await api('/courses');
          const found = courses.find(c => c.code === targetClassroomRef || c.id === targetClassroomRef);
          if (found) courseIdToSelect = found.id;
        } catch (e) {
          console.error("Failed fetching courses for student URL resolution:", e);
        }
      }
      if (!courseIdToSelect) {
        courseIdToSelect = localStorage.getItem('aula_last_course');
      }
      if (courseIdToSelect) {
        await selectClassroom(courseIdToSelect, false);
      } else {
        showStudentPortal();
      }
    }
  }
  startLiveSync();
}

async function showClassroomSelection() {
  if (!currentUser || currentUser.role !== 'lecturer') {
    showStudentPortal();
    return;
  }
  localStorage.removeItem('aula_last_course');
  localStorage.removeItem('aula_last_tab');
  currentCourse = null; // Clear state
  showScreen('classroom-selection-screen');
  const courses = await api('/courses?t=' + Date.now());
  _lastClassroomsData = courses;
  renderClassroomSelection(courses);
  
  // Load admin student panel if admin
  if (currentUser && currentUser.email === 'atunca96@gmail.com') {
    loadAdminStudentPanel();
  }
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
        ${isBuilding ? '<div style="position:absolute; top:0; left:0; right:0; height:3px; background:var(--gradient-2); animation: slide 2s linear infinite;"></div>' : ''}
        <div class="card-body">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                <span style="font-size:12px; font-weight:700; color:var(--accent); text-transform:uppercase; letter-spacing:1px;" ${c.language === 'Detecting...' ? 'data-i18n="gen.detecting"' : ''}>${c.language === 'Detecting...' ? t('gen.detecting') : (c.language || 'Unknown').toUpperCase()}</span>
                <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); deleteClassroom('${c.id}', ${escJS(c.name)})" style="color:var(--danger); padding:4px;">${SVG_TRASH}</button>
            </div>
            <h3 style="font-size:20px; margin-bottom:8px;">${esc(c.name)}</h3>
            <p style="color:var(--text-muted); font-size:14px; margin-bottom:12px;">${esc(c.semester)}</p>
            <div style="background:rgba(255,255,255,0.05); border-radius:8px; padding:8px 12px; margin-bottom:16px; border:1px dashed var(--border); display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:10px; color:var(--text-muted); font-weight:700; text-transform:uppercase;" data-i18n="class.join_code">${t('class.join_code')}</span>
                <span style="font-family:monospace; font-size:16px; color:var(--accent); font-weight:700; letter-spacing:2px;">${c.code}</span>
            </div>
            
            ${isBuilding ? `
              <div style="margin: 12px 0; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                  <span style="font-size:11px; font-weight:600; color:var(--accent); display:flex; align-items:center; gap:6px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:80%;">
                    <div class="spinner-small" style="width:12px; height:12px; border-top-color:var(--accent); flex-shrink:0;"></div>
                    <span id="card-msg-${c.id}">${esc(translateBuildMessage(c.build_message))}</span>
                  </span>
                  <span style="font-size:11px; font-weight:700; color:#fff; font-family:monospace;" id="card-pct-${c.id}">
                    ${Math.max(0, Math.min(100, Math.round(c.percentage || 0)))}%
                  </span>
                </div>
                <div style="width:100%; height:5px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden; margin-bottom:8px;">
                  <div id="card-bar-${c.id}" style="height:100%; width:${Math.max(0, Math.min(100, Math.round(c.percentage || 0)))}%; background:var(--gradient-2); transition:width 0.3s ease;"></div>
                </div>
                <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation(); stopClassroomBuild('${c.id}')" style="width:100%; color:var(--danger); border:1px solid rgba(239,68,68,0.3); font-size:11px; padding:4px 8px; border-radius:6px; background:rgba(239,68,68,0.05); cursor:pointer;">
                  🛑 <span data-i18n="class.stop_build">${t('class.stop_build')}</span>
                </button>
              </div>
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
  checkClassroomBuildingPoll();
}

let _classroomPollTimer = null;
let _currentBuildingCourseId = null;

function checkClassroomBuildingPoll() {
  if (_classroomPollTimer) { clearInterval(_classroomPollTimer); _classroomPollTimer = null; }
  const screen = document.getElementById('classroom-selection-screen');
  if (!screen || !screen.classList.contains('active')) return;
  const buildingCourses = (_lastClassroomsData || []).filter(c => c.is_building === 1);
  if (buildingCourses.length === 0) return;

  _classroomPollTimer = setInterval(async () => {
    const activeScreen = document.getElementById('classroom-selection-screen');
    if (!activeScreen || !activeScreen.classList.contains('active')) {
      clearInterval(_classroomPollTimer);
      _classroomPollTimer = null;
      return;
    }
    let anyStillBuilding = false;
    for (const c of buildingCourses) {
      try {
        const prog = await api(`/classroom/progress?course_id=${c.id}&v=${Date.now()}`);
        if (prog) {
          if (prog.is_building) anyStillBuilding = true;
          const pct = prog.is_building
            ? Math.max(0, Math.min(100, Math.round(prog.percentage || 0)))
            : Math.max(0, Math.min(100, Math.round(prog.percentage || 0)));
          const msgEl = document.getElementById(`card-msg-${c.id}`);
          const pctEl = document.getElementById(`card-pct-${c.id}`);
          const barEl = document.getElementById(`card-bar-${c.id}`);
          if (msgEl && prog.message) msgEl.textContent = translateBuildMessage(prog.message);
          if (pctEl) pctEl.textContent = `${pct}%`;
          if (barEl) barEl.style.width = `${pct}%`;

          // Also update building-screen overlay if open
          const bScreen = document.getElementById('building-screen');
          if (bScreen && !bScreen.classList.contains('hidden') && _currentBuildingCourseId === c.id) {
            const bPct = document.getElementById('building-screen-pct');
            const bMsg = document.getElementById('building-screen-status');
            const bBar = document.getElementById('building-screen-bar');
            if (bPct) bPct.textContent = `${pct}%`;
            if (bMsg && prog.message) bMsg.textContent = translateBuildMessage(prog.message);
            if (bBar) bBar.style.width = `${pct}%`;
            if (!prog.is_building) {
              bScreen.classList.add('hidden');
            }
          }
        }
      } catch (e) {}
    }
    if (!anyStillBuilding) {
      clearInterval(_classroomPollTimer);
      _classroomPollTimer = null;
      showClassroomSelection();
    }
  }, 2000);
}

async function stopClassroomBuild(cid) {
  if (!cid) return;
  const confirmed = confirm(t('class.confirm_stop_build') || 'Ders oluşturmayı durdurmak istediğinize emin misiniz?');
  if (!confirmed) return;
  
  try {
    const res = await api('/classroom/stop-build', {
      method: 'POST',
      body: { course_id: cid }
    });
    if (res && res.success) {
      showAlert(t('success'), t('class.build_stopped') || 'Ders üretimi durduruldu.', false);
      const bScreen = document.getElementById('building-screen');
      if (bScreen) bScreen.classList.add('hidden');
      _currentBuildingCourseId = null;
      if (currentCourse && currentCourse.id === cid) {
        currentCourse.is_building = 0;
        const banner = document.getElementById('lecturer-building-banner');
        if (banner) banner.classList.add('hidden');
      }
      showClassroomSelection();
    } else {
      showAlert(t('error'), res?.error || 'Durdurulamadı', true);
    }
  } catch (e) {
    showAlert(t('error'), 'İşlem başarısız oldu.', true);
  }
}

async function stopCurrentActiveBuilding() {
  if (_currentBuildingCourseId) {
    await stopClassroomBuild(_currentBuildingCourseId);
  } else {
    // Look up any building course
    const building = (_lastClassroomsData || []).find(c => c.is_building === 1);
    if (building) {
      await stopClassroomBuild(building.id);
    } else {
      const bScreen = document.getElementById('building-screen');
      if (bScreen) bScreen.classList.add('hidden');
    }
  }
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
  if (inboxTitle) inboxTitle.innerHTML = `<span data-i18n="inbox">${t('inbox')}</span>`;

  // 2. Resolve course from memory immediately if available, fallback to api
  let course = (_lastClassroomsData && Array.isArray(_lastClassroomsData)) 
    ? _lastClassroomsData.find(c => c.id === id || c.code === id) 
    : null;
    
  if (!course) {
    const courses = await api('/courses');
    _lastClassroomsData = courses;
    course = courses.find(c => c.id === id || c.code === id);
    if (!course && courses.length > 0) course = courses[0];
  }
  if (course) id = course.id;

  courseId = id;
  currentCourse = course;

  if (course) {
    if (currentUser.role === 'student' && course.enrollment_status !== 'approved') {
      localStorage.setItem('aula_last_course', courseId);
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
      const textId = currentUser.role === 'lecturer' ? 'lecturer-progress-text' : 'student-progress-text';
      const fillId = currentUser.role === 'lecturer' ? 'lecturer-progress-fill' : 'student-progress-fill';
      const detailId = currentUser.role === 'lecturer' ? 'lecturer-progress-detail' : 'student-progress-detail';
      const initPct = Math.max(0, Math.min(100, Math.round(course.percentage || 0)));
      const textEl = document.getElementById(textId);
      const fillEl = document.getElementById(fillId);
      const detailEl = document.getElementById(detailId);
      if (textEl) textEl.textContent = initPct + '%';
      if (fillEl) fillEl.style.width = initPct + '%';
      if (detailEl && course.build_message) detailEl.textContent = translateBuildMessage(course.build_message);
    } else {
      buildBanner.classList.add('hidden');
    }
  }

  // 1. Determine destination tab immediately before showing any screen
  const parsed = parseRouteUrl(window.location.pathname, window.location.search);
  const defaultTab = (currentUser.role === 'lecturer') ? 'overview' : 's-home';
  let targetTab = (parsed.screen === (currentUser.role === 'lecturer' ? 'lecturer-dashboard' : 'student-dashboard') && parsed.tab) 
    ? parsed.tab 
    : (parsed.tab || localStorage.getItem('aula_last_tab') || defaultTab);

  // 2. Pre-activate target tab and panel in DOM synchronously (prevents flashing 'overview' / 'home')
  const screenId = (currentUser.role === 'lecturer') ? 'lecturer-dashboard' : 'student-dashboard';
  const targetScreenEl = document.getElementById(screenId);
  if (targetScreenEl) {
    const tabBtn = targetScreenEl.querySelector(`[data-tab="${targetTab}"]`);
    if (tabBtn) {
      switchTab(tabBtn, true, false);
    }
  }

  // 3. Load curriculum before revealing dashboard
  try {
    const currData = await api('/curriculum?course_id=' + courseId);
    curriculum = Array.isArray(currData) ? currData : [];
  } catch (e) {
    console.error("Failed to load curriculum:", e);
    curriculum = [];
  }

  let bookPath = course ? course.textbook : '';
  const isAiGenerated = course && (
    course.textbook === 'AI Generated' || 
    course.textbook === 'AI Architect' ||
    (course.textbook || '').toUpperCase().includes('AI GENERATED') ||
    (course.textbook || '').toUpperCase().includes('AI ARCHITECT')
  );

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
  
  // Select all potential textbook triggers
  const textbookElements = document.querySelectorAll(`
    #l-sidebar-book-tab, 
    #s-sidebar-book-tab, 
    #lecturer-book-tab, 
    [data-tab="book"], 
    [data-tab="s-book"],
    .mobile-book-link,
    #s-ai-book-fallback
  `);

  textbookElements.forEach(el => {
    if (isAiGenerated) el.classList.add('hidden');
    else el.classList.remove('hidden');
  });

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

  renderStudyBook();

  // 4. Restore exact study topic synchronously if on study materials or book
  const isStudyTab = (targetTab === 'study-materials' || targetTab === 'book' || targetTab === 's-study-tab' || targetTab === 's-book');
  const lastTopic = localStorage.getItem('aula_last_topic');
  const lastPage = parseInt(localStorage.getItem('aula_last_page') || '0');
  if (isStudyTab && lastTopic) {
    showStudyTopic(lastTopic, lastPage);
  }

  // 5. Reveal dashboard ONCE in single paint — directly on user's active tab and topic!
  showScreen(screenId, false);

  const activeTab = (currentUser.role === 'lecturer') 
    ? (targetTab || 'overview') 
    : (targetTab || 's-home');

  if (currentUser.role === 'lecturer') {
    const tabBtn = document.querySelector(`#lecturer-dashboard [data-tab="${activeTab}"]`);
    if (tabBtn) {
      switchTab(tabBtn, false, !_isNavigatingFromPopState);
    } else {
      const overviewBtn = document.querySelector('#lecturer-dashboard [data-tab="overview"]');
      if (overviewBtn) switchTab(overviewBtn, false, !_isNavigatingFromPopState);
      else if (!_isNavigatingFromPopState) updateUrlPath('/overview');
    }
    await initLecturer();
  } else {
    const tabBtn = document.querySelector(`#student-dashboard [data-tab="${activeTab}"]`);
    if (tabBtn) {
      switchTab(tabBtn, true, !_isNavigatingFromPopState);
    } else {
      const homeBtn = document.querySelector('#student-dashboard [data-tab="s-home"]');
      if (homeBtn) switchTab(homeBtn, true, !_isNavigatingFromPopState);
      else if (!_isNavigatingFromPopState) updateUrlPath('/home');
    }
    await initStudent();
  }

  // Ensure the route URL is updated to the active tab + course code when entering classroom
  if (!_isNavigatingFromPopState) {
    const activePath = _TAB_TO_PATH[activeTab] || (currentUser.role === 'lecturer' ? '/overview' : '/home');
    updateUrlPath(activePath);
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
  if (!currentUser || currentUser.role !== 'lecturer') return;
  const modal = document.getElementById('classroom-method-modal');
  if (!modal) return;
  localStorage.removeItem('aula_rearchitecting_id');
  modal.classList.remove('hidden');
}

function closeClassroomMethodModal() {
  const modal = document.getElementById('classroom-method-modal');
  if (modal) modal.classList.add('hidden');
}

function startPdfCreationFlow() {
  if (!currentUser || currentUser.role !== 'lecturer') return;
  closeClassroomMethodModal();
  openCreateClassroomModal();
}

function startAiArchitectFlow() {
  if (!currentUser || currentUser.role !== 'lecturer') return;
  const modal = document.getElementById('ai-architect-modal');
  if (!modal) return;
  closeClassroomMethodModal();
  modal.classList.remove('hidden');
  renderAiLanguages();
  _currentAiStep = 1;
  showAiStep(1);
}

function closeAiArchitectModal() {
  const modal = document.getElementById('ai-architect-modal');
  if (modal) modal.classList.add('hidden');
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
  if (!currentUser || currentUser.email !== 'atunca96@gmail.com') return;
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
    { id: 'Spanish', code: 'ES' },
    { id: 'German', code: 'DE' },
    { id: 'French', code: 'FR' },
    { id: 'Italian', code: 'IT' },
    { id: 'Portuguese', code: 'PT' },
    { id: 'Russian', code: 'RU' },
    { id: 'Chinese', code: 'ZH' },
    { id: 'Japanese', code: 'JA' },
    { id: 'Arabic', code: 'AR' },
    { id: 'Turkish', code: 'TR' },
    { id: 'Dutch', code: 'NL' },
    { id: 'Swedish', code: 'SV' },
    { id: 'Korean', code: 'KO' },
    { id: 'Greek', code: 'EL' }
  ];
  grid.innerHTML = langs.map(l => `
    <button class="btn btn-ghost lang-btn" onclick="selectAiLanguage('${l.id}', this)" style="display:flex; flex-direction:column; gap:8px; padding:14px; border:2px solid ${_selectedAiLanguage === l.id ? 'var(--accent)' : 'var(--border)'}; border-radius:12px; height:auto; min-width:0; align-items:center;">
      <span style="font-size:13px; font-weight:800; letter-spacing:0.5px; padding:4px 8px; border-radius:6px; background:rgba(99,102,241,0.12); color:var(--accent);">${l.code}</span>
      <span style="font-size:12px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; width:100%; text-align:center;">${t('lang.' + l.id)}</span>
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
    const data = await api('/draft/curriculum', { method: 'POST', body: { language: _selectedAiLanguage, level: _selectedAiLevel, course_name: courseName } });
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
  container.innerHTML = syllabus.map((chapter, i) => {
    let titleEn = chapter.title || '';
    let titleTr = chapter.title_tr || '';
    // Trust server-provided title_tr. Only clear it if it's a known hybrid or identical to English.
    // Do NOT call local translate() here — that produces English for unknown phrases.
    if (titleTr && (titleTr.trim().toLowerCase() === titleEn.trim().toLowerCase() || UniversalCurriculumTranslator.isHybridOrEnglish(titleTr))) {
      titleTr = ''; // clear bad value; placeholder will show; AI debounce will fill it
    }
    return `
    <div class="syllabus-chapter" data-title-en="${esc(titleEn)}" data-title-tr="${esc(titleTr)}" data-last-auto-tr="${esc(titleTr)}" style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); padding:16px; border-radius:12px; margin-bottom:12px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <h4 style="margin:0; color:var(--accent-light);"><span data-i18n="Unit">${t('Unit')}</span> ${i + 1}</h4>
        <button class="btn btn-ghost btn-sm" onclick="this.closest('.syllabus-chapter').remove()" style="color:var(--danger);">${SVG_TRASH}</button>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:12px;">
        <div>
          <label style="display:block; font-size:11px; font-weight:700; color:var(--accent); text-transform:uppercase; margin-bottom:4px; letter-spacing:0.5px;">English Unit Name</label>
          <input type="text" class="text-input syllabus-title-en" placeholder="e.g. Health and Emergencies" value="${esc(titleEn)}" oninput="onAiChapterEnInput(this)" style="font-weight:600; background:rgba(0,0,0,0.25);">
        </div>
        <div>
          <label style="display:block; font-size:11px; font-weight:700; color:var(--accent-light); text-transform:uppercase; margin-bottom:4px; letter-spacing:0.5px;">Türkçe Ünite Adı</label>
          <input type="text" class="text-input syllabus-title-tr" placeholder="örn. Sağlık ve Acil Durumlar" value="${esc(titleTr)}" oninput="onAiChapterTrInput(this)" style="font-weight:600; background:rgba(0,0,0,0.25);">
        </div>
      </div>
      <div class="topics-list">
        ${(chapter.topics || []).map(topic => {
          let tEn = typeof topic === 'string' ? topic : (topic.title || '');
          let tTr = typeof topic === 'string' ? '' : (topic.title_tr || '');
          // Trust server-provided title_tr. Clear only if it's a hybrid/identical-to-English.
          if (tTr && (tTr.trim().toLowerCase() === tEn.trim().toLowerCase() || UniversalCurriculumTranslator.isHybridOrEnglish(tTr))) {
            tTr = ''; // clear bad value; AI debounce will fill it
          }
          const type = typeof topic === 'string' ? 'vocabulary' : (topic.type || 'vocabulary');
          return `
            <div class="topic-item" data-type="${type}" data-title-en="${esc(tEn)}" data-title-tr="${esc(tTr)}" data-last-auto-tr="${esc(tTr)}" style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
              <span style="font-size:12px; color:var(--accent); cursor:pointer;" onclick="toggleTopicType(this)" title="Toggle Grammar/Vocabulary">${type === 'grammar' ? SVG_GEAR : '•'}</span>
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; flex:1;">
                <input type="text" class="text-input topic-title-en" placeholder="English Topic Title" value="${esc(tEn)}" oninput="onAiTopicEnInput(this)" style="font-size:13px; padding:6px 10px; background:rgba(0,0,0,0.15);">
                <input type="text" class="text-input topic-title-tr" placeholder="Türkçe Konu Başlığı" value="${esc(tTr)}" oninput="onAiTopicTrInput(this)" style="font-size:13px; padding:6px 10px; background:rgba(0,0,0,0.15);">
              </div>
              <button class="btn btn-ghost btn-xs" onclick="this.parentElement.remove()">×</button>
            </div>
          `;
        }).join('')}
        <button class="btn btn-ghost btn-xs" style="font-size:11px; margin-top:4px;" onclick="addTopicToSyllabus(this)">+ ${t('class.add_topic') || 'Add Topic'}</button>
      </div>
    </div>
  `;}).join('');
  // After rendering, fire AI translation for any fields that are still empty or need filling
  _fillMissingTurkishTranslations(container);
}

// Post-render: scan syllabus editor and AI-translate any empty Turkish fields
async function _fillMissingTurkishTranslations(container) {
  if (!container) return;
  // Collect all (enInput, trInput) pairs where Turkish is empty
  const pairs = [];
  container.querySelectorAll('.syllabus-chapter').forEach(chapter => {
    const enInp = chapter.querySelector('.syllabus-title-en');
    const trInp = chapter.querySelector('.syllabus-title-tr');
    if (enInp && trInp && enInp.value.trim() && !trInp.value.trim()) {
      pairs.push({ enInp, trInp, container: chapter });
    }
    chapter.querySelectorAll('.topic-item').forEach(item => {
      const tEnInp = item.querySelector('.topic-title-en');
      const tTrInp = item.querySelector('.topic-title-tr');
      if (tEnInp && tTrInp && tEnInp.value.trim() && !tTrInp.value.trim()) {
        pairs.push({ enInp: tEnInp, trInp: tTrInp, container: item });
      }
    });
  });
  if (!pairs.length) return;

  // Fire AI translations concurrently (batched naturally by the browser)
  await Promise.all(pairs.map(async ({ enInp, trInp, container: el }) => {
    const englishText = enInp.value.trim();
    if (!englishText) return;
    try {
      const res = await api('/translate/material', {
        method: 'POST',
        body: { text: englishText, target_lang: 'tr' }
      });
      if (res && res.translated && typeof res.translated === 'string' && res.translated !== englishText) {
        trInp.value = res.translated;
        el.dataset.titleTr = res.translated;
        el.dataset.lastAutoTr = res.translated;
      }
    } catch (_e) { /* silently ignore — user can fill manually */ }
  }));
}

// Debounce helper for AI title translation calls
const _aiTitleTranslateTimers = new WeakMap();
function _debounceAiTitleTranslation(targetEl, englishText, onResult) {
  if (_aiTitleTranslateTimers.has(targetEl)) {
    clearTimeout(_aiTitleTranslateTimers.get(targetEl));
  }
  const tid = setTimeout(async () => {
    _aiTitleTranslateTimers.delete(targetEl);
    if (!englishText || !englishText.trim()) return;
    try {
      const res = await api('/translate/material', {
        method: 'POST',
        body: { text: englishText.trim(), target_lang: 'tr' }
      });
      if (res && res.translated && typeof res.translated === 'string') {
        onResult(res.translated);
      }
    } catch (_e) { /* silently fail — user can type Turkish manually */ }
  }, 650); // 650 ms debounce
  _aiTitleTranslateTimers.set(targetEl, tid);
}

function onAiChapterEnInput(input) {
  const chapter = input.closest('.syllabus-chapter');
  if (!chapter) return;
  const val = input.value;
  chapter.dataset.titleEn = val;
  const trInp = chapter.querySelector('.syllabus-title-tr');
  if (trInp) {
    const curTr = trInp.value.trim();
    if (!curTr || curTr === (chapter.dataset.lastAutoTr || '') || curTr.toLowerCase() === val.trim().toLowerCase()) {
      // Immediate optimistic fill with local dictionary (safe: returns English if unknown)
      const optimistic = UniversalCurriculumTranslator.translate(val);
      if (optimistic && optimistic !== val && UniversalCurriculumTranslator.isCleanTurkish(optimistic)) {
        trInp.value = optimistic;
        chapter.dataset.titleTr = optimistic;
        chapter.dataset.lastAutoTr = optimistic;
      }
      // Debounced AI call for accurate translation
      _debounceAiTitleTranslation(trInp, val, (translated) => {
        const stillAutoTr = trInp.value.trim() === '' || trInp.value.trim() === (chapter.dataset.lastAutoTr || '') || trInp.value.trim().toLowerCase() === val.trim().toLowerCase();
        if (stillAutoTr || UniversalCurriculumTranslator.isHybridOrEnglish(trInp.value)) {
          trInp.value = translated;
          chapter.dataset.titleTr = translated;
          chapter.dataset.lastAutoTr = translated;
        }
      });
    }
  }
}

function onAiChapterTrInput(input) {
  const chapter = input.closest('.syllabus-chapter');
  if (chapter) {
    chapter.dataset.titleTr = input.value;
    chapter.dataset.lastAutoTr = '';
  }
}

function onAiTopicEnInput(input) {
  const item = input.closest('.topic-item');
  if (!item) return;
  const val = input.value;
  item.dataset.titleEn = val;
  const trInp = item.querySelector('.topic-title-tr');
  if (trInp) {
    const curTr = trInp.value.trim();
    if (!curTr || curTr === (item.dataset.lastAutoTr || '') || curTr.toLowerCase() === val.trim().toLowerCase()) {
      // Immediate optimistic fill with local dictionary (safe: returns English if unknown)
      const optimistic = UniversalCurriculumTranslator.translate(val);
      if (optimistic && optimistic !== val && UniversalCurriculumTranslator.isCleanTurkish(optimistic)) {
        trInp.value = optimistic;
        item.dataset.titleTr = optimistic;
        item.dataset.lastAutoTr = optimistic;
      }
      // Debounced AI call for accurate translation
      _debounceAiTitleTranslation(trInp, val, (translated) => {
        const stillAutoTr = trInp.value.trim() === '' || trInp.value.trim() === (item.dataset.lastAutoTr || '') || trInp.value.trim().toLowerCase() === val.trim().toLowerCase();
        if (stillAutoTr || UniversalCurriculumTranslator.isHybridOrEnglish(trInp.value)) {
          trInp.value = translated;
          item.dataset.titleTr = translated;
          item.dataset.lastAutoTr = translated;
        }
      });
    }
  }
}

function onAiTopicTrInput(input) {
  const item = input.closest('.topic-item');
  if (item) {
    item.dataset.titleTr = input.value;
    item.dataset.lastAutoTr = '';
  }
}

function addUnitToAiArchitect() {
  const container = document.getElementById('ai-curriculum-list');
  if (!container) return;

  const unitIdx = container.querySelectorAll('.syllabus-chapter').length;
  const unitHtml = `
    <div class="syllabus-chapter" data-title-en="" data-title-tr="" data-last-auto-tr="" style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); padding:16px; border-radius:12px; margin-bottom:12px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <h4 style="margin:0; color:var(--accent-light);"><span data-i18n="Unit">${t('Unit')}</span> ${unitIdx + 1}</h4>
        <button class="btn btn-ghost btn-sm" onclick="this.closest('.syllabus-chapter').remove()" style="color:var(--danger)">${SVG_TRASH}</button>
      </div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:12px;">
        <div>
          <label style="display:block; font-size:11px; font-weight:700; color:var(--accent); text-transform:uppercase; margin-bottom:4px; letter-spacing:0.5px;">English Unit Name</label>
          <input type="text" class="text-input syllabus-title-en" placeholder="Unit title in English" oninput="onAiChapterEnInput(this)" style="font-weight:600; background:rgba(0,0,0,0.25);">
        </div>
        <div>
          <label style="display:block; font-size:11px; font-weight:700; color:var(--accent-light); text-transform:uppercase; margin-bottom:4px; letter-spacing:0.5px;">Türkçe Ünite Adı</label>
          <input type="text" class="text-input syllabus-title-tr" placeholder="Türkçe ünite başlığı" oninput="onAiChapterTrInput(this)" style="font-weight:600; background:rgba(0,0,0,0.25);">
        </div>
      </div>
      <div class="topics-list">
        <button class="btn btn-ghost btn-xs" style="font-size:11px; margin-top:4px;" onclick="addTopicToSyllabus(this)">+ ${t('class.add_topic') || 'Add Topic'}</button>
      </div>
    </div>
  `;

  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = unitHtml;
  container.appendChild(tempDiv.firstElementChild);
  container.scrollTop = container.scrollHeight;
  const input = container.lastElementChild.querySelector('.syllabus-title-en') || container.lastElementChild.querySelector('input');
  if (input) input.focus();
}

function addTopicToSyllabus(btn) {
  const div = document.createElement('div');
  div.className = 'topic-item';
  div.setAttribute('data-type', 'vocabulary');
  div.setAttribute('data-title-en', '');
  div.setAttribute('data-title-tr', '');
  div.setAttribute('data-last-auto-tr', '');
  div.style.cssText = 'display:flex; align-items:center; gap:8px; margin-bottom:8px;';
  div.innerHTML = `
    <span style="font-size:12px; color:var(--accent); cursor:pointer;" onclick="toggleTopicType(this)" title="Toggle Grammar/Vocabulary">•</span>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; flex:1;">
      <input type="text" class="text-input topic-title-en" placeholder="English Topic Title" oninput="onAiTopicEnInput(this)" style="font-size:13px; padding:6px 10px; background:rgba(0,0,0,0.15);">
      <input type="text" class="text-input topic-title-tr" placeholder="Türkçe Konu Başlığı" oninput="onAiTopicTrInput(this)" style="font-size:13px; padding:6px 10px; background:rgba(0,0,0,0.15);">
    </div>
    <button class="btn btn-ghost btn-xs" onclick="this.parentElement.remove()">×</button>
  `;
  btn.before(div);
  const inp = div.querySelector('.topic-title-en');
  if (inp) inp.focus();
}

function toggleTopicType(span) {
  const item = span.closest('.topic-item');
  const current = item.getAttribute('data-type') || 'vocabulary';
  const next = current === 'vocabulary' ? 'grammar' : 'vocabulary';
  item.setAttribute('data-type', next);
  span.innerHTML = next === 'grammar' ? SVG_GEAR : '•';
}

async function buildAiClassroom() {
  if (!currentUser || currentUser.role !== 'lecturer') return;
  const courseName = document.getElementById('ai-course-name').value;
  const chapters = [];
  document.querySelectorAll('.syllabus-chapter').forEach(chapterEl => {
    const enInp = chapterEl.querySelector('.syllabus-title-en');
    const trInp = chapterEl.querySelector('.syllabus-title-tr');
    const legacyInp = chapterEl.querySelector('.syllabus-title');
    let title_en = (enInp ? enInp.value : (chapterEl.dataset.titleEn || (legacyInp ? legacyInp.value : ''))).trim();
    let title_tr = (trInp ? trInp.value : (chapterEl.dataset.titleTr || (legacyInp ? legacyInp.value : ''))).trim();
    if (!title_en && title_tr) title_en = title_tr;
    // Do NOT call local translate() — server's ensure_bilingual_curriculum handles gaps

    const topics = [];
    chapterEl.querySelectorAll('.topic-item').forEach(topicItem => {
      const tEnInp = topicItem.querySelector('.topic-title-en');
      const tTrInp = topicItem.querySelector('.topic-title-tr');
      const tLegacyInp = topicItem.querySelector('.topic-title');
      let t_en = (tEnInp ? tEnInp.value : (topicItem.dataset.titleEn || (tLegacyInp ? tLegacyInp.value : ''))).trim();
      let t_tr = (tTrInp ? tTrInp.value : (topicItem.dataset.titleTr || (tLegacyInp ? tLegacyInp.value : ''))).trim();
      if (!t_en && t_tr) t_en = t_tr;
      // Do NOT call local translate() — server's ensure_bilingual_curriculum handles gaps
      const type = topicItem.getAttribute('data-type') || 'vocabulary';
      topics.push({ title: t_en, title_tr: t_tr, type: type });
    });
    chapters.push({ title: title_en, title_tr: title_tr, topics: topics });
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
      if (res.course_id) _currentBuildingCourseId = res.course_id;
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
  if (!currentUser || currentUser.role !== 'lecturer') return;
  const modal = document.getElementById('create-classroom-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
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
      dropZone.style.background = 'var(--accent-glow)';
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
  const nameEl = document.getElementById('course-name-input');
  const mdEl = document.getElementById('markdown-analysis-input');
  const tocEl = document.getElementById('manual-toc-input');
  const name = nameEl ? nameEl.value.trim() : '';
  const md = mdEl ? mdEl.value.trim() : '';
  const toc = tocEl ? tocEl.value.trim() : '';

  if (!force && (name || md || toc)) {
    const confirmed = await showConfirmModal('confirm.cancel_creation_title', 'confirm.cancel_creation_msg', true);
    if (!confirmed) return;
  }
  const modal = document.getElementById('create-classroom-modal');
  if (modal) modal.classList.add('hidden');
}

async function triggerDeepExtract() {
  if (!currentUser || currentUser.role !== 'lecturer') return;
  const fileInput = document.getElementById('pdf-upload');
  const mdInput = document.getElementById('markdown-analysis-input');
  const statusEl = document.getElementById('extract-status');
  const successEl = document.getElementById('extract-success');
  const btn = document.getElementById('deep-extract-btn');

  if (!fileInput || !fileInput.files[0]) {
    return showAlert(t('missing_info'), t('class.select_pdf_first') || 'Please select a PDF file first.', true);
  }

  statusEl.classList.remove('hidden');
  successEl.classList.add('hidden');
  btn.disabled = true;
  btn.style.opacity = '0.5';
  btn.textContent = (t('class.extracting') || 'Extracting...');

  const formData = new FormData();
  formData.append('pdf', fileInput.files[0]);
  formData.append('toc_range', document.getElementById('pdf-toc-range').value || '1-25');
  const pdfLang = document.getElementById('pdf-language-select') ? document.getElementById('pdf-language-select').value : 'Detecting...';
  formData.append('language', pdfLang);
  if (currentUser && currentUser.id) {
    formData.append('lecturer_id', currentUser.id);
  }

  try {
    const extractUrl = currentUser && currentUser.id ? `/api/marker/extract?user_id=${encodeURIComponent(currentUser.id)}` : '/api/marker/extract';
    const res = await fetch(extractUrl, {
      method: 'POST',
      headers: currentUser && currentUser.id ? { 'X-User-Id': currentUser.id, 'X-User-Role': currentUser.role || '' } : {},
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
    
    // Render extracted curriculum preview
    const previewEl = document.getElementById('extract-preview');
    if (previewEl && data.markdown) {
      const lines = data.markdown.split('\n');
      let html = '';
      const tagColors = {
        'grammar': 'var(--accent)', 'vocabulary': 'var(--accent-light)', 'mixed': '#d97706',
        'communication': '#059669', 'functional': '#b89047', 'phonetics': '#c5a059'
      };
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        if (trimmed.startsWith('##')) {
          const title = trimmed.replace(/^#+\s*/, '');
          html += `<div style="font-weight:700; font-size:14px; color:var(--accent-light); margin-top:14px; margin-bottom:6px; padding-bottom:4px; border-bottom:1px solid rgba(255,255,255,0.06);">${title}</div>`;
        } else if (trimmed.startsWith('- ')) {
          const tagMatch = trimmed.match(/\[(\w+)\]\s*$/);
          const tag = tagMatch ? tagMatch[1] : '';
          const topicText = trimmed.replace(/^-\s*/, '').replace(/\s*\[\w+\]\s*$/, '');
          const tagColor = tagColors[tag] || '#94a3b8';
          const tagBadge = tag ? `<span style="display:inline-block; font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px; padding:2px 6px; border-radius:var(--radius-sm); background:${tagColor}22; color:${tagColor}; margin-left:8px;">${tag}</span>` : '';
          html += `<div style="padding:3px 0 3px 12px; color:var(--text-secondary, #cbd5e1);">• ${topicText}${tagBadge}</div>`;
        }
      }
      previewEl.innerHTML = html || '<div style="color:var(--text-muted);">No structured content found.</div>';
      previewEl.classList.remove('hidden');
    }
    
  } catch (err) {
    console.error('Extraction Error:', err);
    statusEl.classList.add('hidden');
    showAlert(t('error'), 'Deep extraction failed: ' + err.message, true);
  } finally {
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.innerHTML = '\u26a1 ' + (t('class.deep_extract') || 'Deep Extract');
  }
}

async function handleCreateClassroom(e) {
  e.preventDefault();
  if (!currentUser || currentUser.role !== 'lecturer') return;
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
    const createUrl = currentUser && currentUser.id ? `/api/classroom/create-from-pdf?user_id=${encodeURIComponent(currentUser.id)}` : '/api/classroom/create-from-pdf';
    const res = await fetch(createUrl, {
      method: 'POST',
      headers: currentUser && currentUser.id ? { 'X-User-Id': currentUser.id, 'X-User-Role': currentUser.role || '' } : {},
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
  const pwdEl = document.getElementById('student-password');
  const password = pwdEl ? pwdEl.value : '';
  const errBox = document.getElementById('student-login-error');

  if (!num || !password) {
    errBox.textContent = t('missing_info') || 'Please enter student number and password.';
    errBox.classList.remove('hidden');
    return;
  }

  if (btn) btn.disabled = true;
  errBox.classList.add('hidden');

  try {
    const res = await api('/student/login', {
      method: 'POST',
      body: { student_number: num, password: password }
    });

    if (res.error) {
      errBox.textContent = t(res.error) || res.error;
      errBox.classList.remove('hidden');
      if (btn) btn.disabled = false;
    } else {
      await completeLogin(res.user, true);
      if (btn) btn.disabled = false;
    }
  } catch (err) {
    errBox.textContent = t('error') || 'Bir hata oluştu.';
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
  if (data.error) {
    const errEl = document.getElementById('login-error');
    if (errEl) {
      errEl.textContent = t(data.error) || data.error;
      errEl.classList.remove('hidden');
    }
    return false;
  }
  await completeLogin(data.user, true);
  return false;
}

async function logout() {
  if (currentUser && currentUser.id) {
    try {
      // Notify server to clear 'last_seen' timestamp immediately
      await api('/user/logout', { method: 'POST', body: { user_id: currentUser.id } });
    } catch (e) { console.error('Logout error:', e); }
  }
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

    // Check if a quiz was interrupted by page reload
    const abandonedQuiz = localStorage.getItem('aula_taking_quiz');
    if (abandonedQuiz) {
      localStorage.removeItem('aula_taking_quiz');
      setTimeout(() => {
        showAlert(
          currentLang === 'tr' ? 'Sınav Sonlandırıldı' : 'Quiz Terminated',
          currentLang === 'tr'
            ? 'Sınav sırasında sayfa yenilendiği için quiz sonlandırıldı ve tekrar giriş hakkınız kapatıldı.'
            : 'The quiz was ended because the page was refreshed, and retaking is not permitted.',
          true
        );
      }, 1000);
    }

    const savedUser = localStorage.getItem('aula_user') || sessionStorage.getItem('aula_user');
    if (savedUser) {
      try { completeLogin(JSON.parse(savedUser)).catch(() => showScreen('login-screen')); }
      catch (e) { showScreen('login-screen'); }
    } else {
      const p = window.location.pathname + window.location.search;
      if (p && p !== '/' && p !== '/login') {
        sessionStorage.setItem('aula_redirect_path', p);
      }
      showScreen('login-screen');
    }


    // Start Real-time Messaging Sync
    startMessagePolling();

    // Initialize SPA Router
    initRouter();
  } catch (err) {
    console.error('INIT ERROR:', err);
    alert('Critical Initialization Error: ' + err.message);
    // Force show login screen as fallback
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const login = document.getElementById('login-screen');
    if (login) login.classList.add('active');
  }
});

function showScreen(id, updateRoute = true) {
  if (currentUser && currentUser.role === 'student' && (id === 'lecturer-dashboard' || id === 'classroom-selection-screen')) {
    console.warn('Unauthorized screen switch blocked for student:', id);
    return;
  }
  // Stop waiting room polling if we leave that screen
  if (id !== 'waiting-room-screen' && window._waitingPoll) {
    clearInterval(window._waitingPoll);
    window._waitingPoll = null;
  }
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const target = document.getElementById(id);
  if (target) target.classList.add('active');

  if (updateRoute && !_isNavigatingFromPopState) {
    const p = _SCREEN_TO_PATH[id];
    if (p) updateUrlPath(p);
  }
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

function switchTab(btn, skipLoad = false, updateRoute = true) {
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
  const sidebarNav = document.getElementById('sidebar-nav');
  if (sidebarNav) {
    sidebarNav.querySelectorAll('.sidebar-item').forEach(t => {
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

  if (updateRoute && !_isNavigatingFromPopState) {
    const p = _TAB_TO_PATH[tabId];
    if (p) updateUrlPath(p);
  }

  if (!skipLoad) {
    if (tabId === 'inbox') loadInbox();
    if (tabId === 's-messages') loadStudentChat();
    if (tabId === 'quizzes-mgmt' || tabId === 'quizzes' || tabId === 's-quizzes') loadQuizList();
    if (tabId === 'assignments-mgmt' || tabId === 'assignments' || tabId === 's-assignments') loadAssignmentList();
    if (tabId === 'activities') {
      const actSelect = document.getElementById('activity-topic-select');
      if (actSelect) {
        if (!actSelect.value && actSelect.options.length > 1) {
          actSelect.selectedIndex = 1;
        }
        if (actSelect.value) {
          handleActivityTopicChange();
        }
      }
    }
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

function closeModal() {
  window._currentViewingQuiz = null;
  window._currentViewingAssignment = null;
  document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
}

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

async function loadStudentChat(isRefresh = false) {
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
  if (container && !isRefresh) container.innerHTML = '<div style="display:flex; justify-content:center; padding:40px;"><div class="spinner"></div></div>';

  const messages = await api(`/messages?student_id=${currentUser.id}&course_id=${currentCourse.id}`);
  
  // Only re-render if message count changed (basic check)
  const existingCount = container ? container.querySelectorAll('.chat-bubble').length : 0;
  if (messages && messages.length !== existingCount) {
    renderStudentChat(messages);
  }
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
  document.getElementById('inbox-title').innerHTML = `<span data-i18n="inbox">${t('inbox')}</span>`;

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
    <div style="background:var(--bg-input); border:1px solid var(--border); border-radius:var(--radius-lg); padding:16px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; transition:var(--transition); margin-bottom:8px; box-shadow:none;" onclick="openChat('${data.student_id}', ${escJS(data.student_name).replace(/'/g, "\\'")}, '${data.course_id}')">
      <div style="flex:1; min-width:0; margin-right:12px;">
        <div style="display:flex; align-items:center; gap:8px;">
           <div style="width:10px; height:10px; border-radius:50%; background:${data.unread > 0 ? 'var(--accent)' : 'transparent'};"></div>
           <strong style="font-size:16px; color:var(--text-primary); font-weight:700;">${esc(data.student_name)}</strong>
           <span style="font-size:10px; font-weight:700; color:var(--accent); background:var(--accent-glow); padding:2px 8px; border-radius:var(--radius-sm); border:1px solid var(--border);">${esc(data.course_name)}</span>
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

async function openChat(studentId, studentName, cid, isRefresh = false) {
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
  document.getElementById('inbox-title').innerHTML = `${esc(studentName)}`;

  const container = document.getElementById('inbox-messages');
  if (container && !isRefresh) container.innerHTML = '<div style="display:flex; justify-content:center; padding:40px;"><div class="spinner"></div></div>';

  const messages = await api(`/messages?student_id=${studentId}&course_id=${activeCourseId}`);
  
  const existingCount = container ? container.querySelectorAll('.chat-bubble').length : 0;
  if (messages && messages.length !== existingCount) {
    renderLecturerChat(messages);
  }

  messages.filter(m => m.sender === 'student' && !m.is_read).forEach(m => {
    api('/message/read', { method: 'POST', body: { message_id: m.id } });
  });
}

async function sendReply() {
  const text = document.getElementById('reply-text').value.trim();
  if (!text || !currentChatStudentId) return;
  document.getElementById('reply-text').value = '';
  await api('/message/send', {
    method: 'POST', body: {
      student_id: currentChatStudentId,
      course_id: currentChatCourseId,
      sender: 'lecturer',
      content: text
    }
  });
  syncLecturerChat();
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
        <div class="new-chat-item" style="display:flex; align-items:center; justify-content:space-between; padding:12px; border:1px solid var(--border); border-radius:12px; background:var(--bg-input); cursor:pointer; margin-bottom:8px; transition:var(--transition);" onclick="startNewChat('${s.id}', ${escJS(s.name).replace(/'/g, "\\'")})" onmouseover="this.style.borderColor='var(--accent)'" onmouseout="this.style.borderColor='var(--border)'">
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
  const globalIcon = document.getElementById('global-theme-toggle-icon');
  const globalText = document.getElementById('global-theme-toggle-text');

  if (theme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
    btns.forEach(btn => { if (btn) btn.innerHTML = SVG_SUN; });
    if (globalIcon) globalIcon.innerHTML = SVG_SUN;
    if (globalText) {
      globalText.setAttribute('data-i18n', 'theme.light');
      globalText.textContent = t('theme.light');
    }
  } else {
    document.documentElement.removeAttribute('data-theme');
    btns.forEach(btn => { if (btn) btn.innerHTML = SVG_MOON; });
    if (globalIcon) globalIcon.innerHTML = SVG_MOON;
    if (globalText) {
      globalText.setAttribute('data-i18n', 'theme.dark');
      globalText.textContent = t('theme.dark');
    }
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
    atRiskList.innerHTML = `<p style="color:var(--text-muted)" data-i18n="no_at_risk">No at-risk students</p>`;
  } else {
    atRiskList.innerHTML = atRisk.map(s => `<div class="risk-item"><div><span class="risk-name">${s.name}</span></div><div class="risk-badges"><span class="risk-badge ${s.overall_mastery < 0.4 ? 'critical' : 'warning'}">${Math.round(s.overall_mastery * 100)}% <span data-i18n="mastery">mastery</span></span>${s.flags.map(f => `<span class="risk-badge low" data-i18n="${f}">${t(f)}</span>`).join('')}</div></div>`).join('');
  }
  const td = report.topic_difficulty || {};
  const chartEl = document.getElementById('topic-difficulty-chart');
  if (chartEl) {
    chartEl.innerHTML = Object.entries(td).slice(0, 8).map(([name, score]) =>
      `<div class="progress-item"><div class="progress-label"><span>${translateCurriculumTitle(name, currentLang)}</span><span>${Math.round(score * 100)}%</span></div><div class="progress-bar"><div class="progress-fill" style="width:${score * 100}%;background:${masteryColor(score)}"></div></div></div>`
    ).join('');
  }

  applyTranslations(); // Unify everything!
}

async function loadCurriculumAsync() {
  const currData = await api('/curriculum?course_id=' + courseId);
  curriculum = Array.isArray(currData) ? currData : [];
  renderCurriculum();
  renderStudyBook();
  populateSelects();
  if (currentUser && currentUser.role === 'student') {
    if (_lastStudentHomeData) renderStudentHome(_lastStudentHomeData);
    loadStudentPractice();
  }
}

function renderCurriculum() {
  try {
    const subtitleEl = document.getElementById('curriculum-subtitle');
    if (subtitleEl && currentCourse) {
      const cName = translateCourseName(currentCourse.name, currentLang);
      subtitleEl.textContent = `${cName} — ${t('Content Map')}`;
    }

    if (!curriculum || !Array.isArray(curriculum)) {
      document.getElementById('curriculum-tree').innerHTML = `<p style="color:var(--text-muted); padding:20px;">${t('class.no_curriculum')}</p>`;
      return;
    }

    const treeEl = document.getElementById('curriculum-tree');
    treeEl.innerHTML = curriculum.map((ch, i) => {
      const displayNum = i + 1;
      const translatedChTitle = getLocalizedCurriculumTitle(ch, currentLang);
      return `
      <div class="chapter-block">
        <div class="chapter-header" onclick="this.nextElementSibling.classList.toggle('open');this.querySelector('.chapter-toggle').textContent=this.nextElementSibling.classList.contains('open')?'▾':'▸'">
          <div style="display:flex;align-items:center;gap:12px;">
            <span class="chapter-num">${displayNum}</span>
            <span class="chapter-title">${esc(translatedChTitle)}</span>
            <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation(); deleteChapter('${ch.id}', ${escJS(ch.title)})" style="color:var(--danger); padding:2px; margin-left:8px; font-size:12px;">${SVG_TRASH}</button>
          </div>
          <span class="chapter-toggle">▸</span>
        </div>
        <div class="chapter-topics">${(ch.topics || []).map(t_obj => {
          const translatedTTitle = getLocalizedCurriculumTitle(t_obj, currentLang);
          return `
          <div class="topic-item">
            <div class="topic-info">
              <span class="topic-type-badge ${t_obj.type}">${translateBadge(t_obj.type)}</span>
              <span class="topic-name">${esc(translatedTTitle)}</span>
            </div>
            <div style="display:flex; align-items:center; gap:12px;">
              <button class="btn btn-sm" style="background:var(--info); color:#fff; border:none; padding:4px 8px; border-radius:6px; font-size:14px; cursor:pointer;" title="${t('Material') || 'Study Material'}" onclick="event.stopPropagation(); openTopicMaterial('${t_obj.id}', '${t_obj.pdf_url || ''}')">${SVG_BOOK}</button>
              <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation(); deleteTopic('${t_obj.id}', ${escJS(t_obj.title)})" style="color:var(--danger); padding:4px;">${SVG_TRASH}</button>
              <div class="topic-meta">
                <span>${translateDifficulty(t_obj.difficulty)}</span>
                <span>${t_obj.question_count || 0} ${t('questions')}</span>
              </div>
            </div>
          </div>`}).join('')}</div>
      </div>`}).join('');
  } catch (err) {
    console.error('Render Error:', err);
  }
}

function openTopicMaterial(topicId, pdfUrl) {
  if (pdfUrl && !pdfUrl.toLowerCase().includes('none')) {
    let topic = null;
    if (curriculum) {
      for (const ch of curriculum) {
        topic = (ch.topics || []).find(t => t.id === topicId);
        if (topic) break;
      }
    }
    if (!topic || !topic.content || topic.content === '{}') {
      window.open(pdfUrl, '_blank');
      return;
    }
  }

  const isStudent = currentUser && currentUser.role === 'student';
  const studyTabBtn = isStudent 
    ? (document.getElementById('nav-s-study-tab') || document.querySelector('button[data-tab="s-study-tab"]'))
    : (document.getElementById('lecturer-study-tab') || document.querySelector('button[data-tab="study-materials"]'));
    
  if (studyTabBtn) {
    switchTab(studyTabBtn);
  } else {
    const targetPanelId = isStudent ? 'tab-s-study-tab' : 'tab-study-materials';
    document.querySelectorAll('.tab-panel').forEach(p => {
      if (p.id === targetPanelId) {
        p.classList.add('active');
        p.classList.remove('hidden');
        p.style.display = 'block';
      } else {
        p.classList.remove('active');
        p.style.display = 'none';
      }
    });
  }
  
  renderStudyBook();
  setTimeout(() => {
    showStudyTopic(topicId);
  }, 100);
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
      'confirm.rebuild_msg',
      true,
      null,
      false,
      'confirm.rebuild_ok',
      'confirm.rebuild_cancel'
    );
    if (!ok) return;
  }

  const rebuildBtn = document.getElementById('rebuild-curriculum-btn');
  const forceRestartBtn = document.getElementById('lecturer-force-restart-btn');
  if (rebuildBtn) {
    rebuildBtn.disabled = true;
    rebuildBtn.style.opacity = '0.5';
    const btnText = rebuildBtn.querySelector('span[data-i18n="Build Lessons"]') || rebuildBtn.querySelector('span:last-child');
    if (btnText) btnText.textContent = t('Building...');
  }
  if (forceRestartBtn) {
    forceRestartBtn.disabled = true;
    forceRestartBtn.style.opacity = '0.5';
    forceRestartBtn.textContent = '...';
  }

  showToast(t('gen.preparing_content'), "info");
  
  try {
    const res = await api('/classroom/rebuild', {
      method: 'POST',
      body: { course_id: currentCourse.id, force: true }
    });
    if (res.status === 'success' || res.success) {
      currentCourse.is_building = 1;
      showToast(t('gen.building'), "success");
      const banner = document.getElementById('lecturer-building-banner');
      if (banner) {
        banner.classList.remove('hidden');
        banner.classList.remove('build-failed');
      }
      pollRebuildProgress(currentCourse.id);
    } else {
      showToast(res.error || "Failed to start lesson building", "error");
      if (rebuildBtn) {
        rebuildBtn.disabled = false;
        rebuildBtn.style.opacity = '1';
        const btnText = rebuildBtn.querySelector('span[data-i18n="Build Lessons"]') || rebuildBtn.querySelector('span:last-child');
        if (btnText) btnText.textContent = t('Build All Lessons');
      }
    }
  } catch (err) {
    console.error("Rebuild trigger error:", err);
    showToast("Network error triggering rebuild", "error");
    if (rebuildBtn) {
      rebuildBtn.disabled = false;
      rebuildBtn.style.opacity = '1';
      const btnText = rebuildBtn.querySelector('span[data-i18n="Build Lessons"]') || rebuildBtn.querySelector('span:last-child');
      if (btnText) btnText.textContent = t('Build All Lessons');
    }
  } finally {
    if (forceRestartBtn) {
      forceRestartBtn.disabled = false;
      forceRestartBtn.style.opacity = '1';
      const forceTxt = forceRestartBtn.querySelector('span');
      if (forceTxt) forceTxt.textContent = t('class.force_restart') || 'Force Restart';
      else forceRestartBtn.textContent = t('class.force_restart') || 'Force Restart';
    }
  }
}

function pollRebuildProgress(cid) {
  const banner = document.getElementById('lecturer-building-banner');
  const fill = document.getElementById('lecturer-progress-fill');
  const txt = document.getElementById('lecturer-progress-text');
  const detail = document.getElementById('lecturer-progress-detail');
  const badge = document.getElementById('lecturer-stage-badge');
  const stepsTrack = document.getElementById('lecturer-steps-track');
  if (banner) banner.classList.remove('hidden');

  const timer = setInterval(async () => {
    try {
      const st = await api(`/classroom/progress?course_id=${cid}&v=${Date.now()}`);
      if (!st.is_building) {
        clearInterval(timer);
        if (banner) banner.classList.add('hidden');
        if (currentCourse) currentCourse.is_building = 0;
        const rebuildBtn = document.getElementById('rebuild-curriculum-btn');
        if (rebuildBtn) {
          rebuildBtn.disabled = false;
          rebuildBtn.style.opacity = '1';
          const btnText = rebuildBtn.querySelector('span[data-i18n="Build Lessons"]') || rebuildBtn.querySelector('span:last-child');
          if (btnText) btnText.textContent = t('Build All Lessons');
        }
        showToast(t('Classroom is ready!'), "success");
        await loadCurriculumAsync();
      } else {
        const pct = Math.max(0, Math.min(100, Math.round(st.percentage || 0)));
        if (fill) fill.style.width = pct + '%';
        if (txt) txt.textContent = pct + '%';
        if (detail && st.message) detail.textContent = translateBuildMessage(st.message);
        if (badge && st.stage) badge.textContent = translateBuildStage(st.stage);
        if (stepsTrack && st.stage) {
          const stageOrder = ['analyzing', 'structuring', 'enriching', 'finalizing'];
          const currentStageIdx = stageOrder.indexOf(st.stage);
          stepsTrack.querySelectorAll('.build-step-node').forEach(node => {
            const nodeStep = node.getAttribute('data-step');
            const nodeIdx = stageOrder.indexOf(nodeStep);
            node.classList.remove('active', 'done');
            if (nodeIdx !== -1) {
              if (nodeIdx < currentStageIdx) node.classList.add('done');
              else if (nodeIdx === currentStageIdx) node.classList.add('active');
            }
          });
        }
      }
    } catch(e) {
      console.warn("Poll status error:", e);
    }
  }, 1000);
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
  if (!curriculum || !Array.isArray(curriculum)) return;
  let topicOpts = '', chapterOpts = '';
  curriculum.forEach((ch, idx) => {
    // Always use the index + 1 for the unit number to ensure they start at 1 and are sequential
    const displayNum = idx + 1;
    const trTitle = getLocalizedCurriculumTitle(ch, currentLang);
    const displayTitle = `${t('Unit')} ${displayNum}: ${trTitle}`;
    
    chapterOpts += `<option value="${ch.id}">${displayTitle}</option>`;
    (ch.topics || []).forEach(tp => { 
      const trTopic = getLocalizedCurriculumTitle(tp, currentLang);
      const badgeText = translateBadge(tp.type);
      topicOpts += `<option value="${tp.id}">U${displayNum} — ${trTopic} (${badgeText})</option>`; 
    });
  });
  const actSelect = document.getElementById('activity-topic-select');
  if (actSelect) {
    const prevActVal = actSelect.value;
    actSelect.innerHTML = `<option value="">${t('SelectTopic')}</option>` + topicOpts;
    if (prevActVal) actSelect.value = prevActVal;
    actSelect.onchange = () => handleActivityTopicChange();
  }
  const quizSelect = document.getElementById('quiz-chapter-select');
  if (quizSelect) {
    const prevQuizVal = quizSelect.value;
    quizSelect.innerHTML = `<option value="">${t('AllTopics')}</option>` + topicOpts;
    if (prevQuizVal) quizSelect.value = prevQuizVal;
  }
  const as = document.getElementById('assignment-chapter-select');
  if (as) {
    const prevAsVal = as.value;
    as.innerHTML = `<option value="">${t('AllTopics')}</option>` + topicOpts;
    if (prevAsVal) as.value = prevAsVal;
  }
}

function clearActivityAnsweredState() {
  for (const k of Object.keys(_answeredQuestionsState)) {
    if (k.startsWith('act_')) {
      delete _answeredQuestionsState[k];
    }
  }
}

function handleActivityTopicChange() {
  clearActivityAnsweredState();
  const select = document.getElementById('activity-topic-select');
  const topicId = select ? select.value : '';
  const preview = document.getElementById('activity-preview');
  const btn = document.getElementById('generate-activity-btn');
  if (!topicId || !preview) {
    if (preview) { preview.classList.add('hidden'); preview.innerHTML = ''; }
    if (btn) btn.textContent = t('Generate Activity') || 'Generate Activity';
    return;
  }

  let topic = null;
  for (const ch of (window.curriculum || curriculum || [])) {
    topic = ch.topics ? ch.topics.find(t => t.id === topicId) : null;
    if (topic) break;
  }
  if (!topic) return;

  let content = typeof topic.content === 'string' ? JSON.parse(topic.content || '{}') : (topic.content || {});
  if (content && Array.isArray(content.activities) && content.activities.length > 0) {
    preview.classList.remove('hidden');
    _lastActivityData = { activities: content.activities, topic: topic, topicId: topicId };
    registerSeenQuestions(topicId, content.activities);
    const title = getLocalizedCurriculumTitle(topic, currentLang);
    const isStudent = currentUser && currentUser.role === 'student';
    const header = `<div class="page-header" style="margin-top:24px; display:flex; justify-content:space-between; align-items:center;">
      <h2>${title}</h2>
      <button class="btn btn-outline btn-sm" onclick="${isStudent ? 'cancelPractice()' : `this.closest('#activity-preview').classList.add('hidden')`}">${t('close')}</button>
    </div>`;
    preview.innerHTML = header + content.activities.map((a, i) => renderActivityCard(a, i, 'activity-preview')).join('');
    if (btn) btn.textContent = currentLang === 'tr' ? 'Etkinlikleri Yenile' : 'Regenerate Activity';
  } else {
    preview.classList.add('hidden');
    preview.innerHTML = '';
    if (btn) btn.textContent = currentLang === 'tr' ? 'Aktivite Oluştur' : 'Generate Activity';
  }
}

window._topicSeenQuestions = window._topicSeenQuestions || {};

window._draftSeenQuestions = window._draftSeenQuestions || {};

function _normalizeKey(str) {
  if (!str) return '';
  return String(str)
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^\w\s]/g, '')
    .trim();
}

function registerSeenQuestions(topicId, questions) {
  if (!topicId || !Array.isArray(questions)) return;
  const tid = String(topicId);
  if (!window._topicSeenQuestions[tid]) {
    window._topicSeenQuestions[tid] = [];
  }
  for (const q of questions) {
    if (q && (q.prompt || q.answer)) {
      const pKey = _normalizeKey(q.prompt);
      const aKey = _normalizeKey(q.answer);
      const exists = window._topicSeenQuestions[tid].some(
        sq => (pKey && _normalizeKey(sq.prompt) === pKey) || (aKey && _normalizeKey(sq.answer) === aKey)
      );
      if (!exists) {
        window._topicSeenQuestions[tid].push({
          prompt: q.prompt || '',
          answer: q.answer || ''
        });
      }
    }
  }
}

function getSeenQuestions(topicId) {
  if (!topicId) return [];
  const list = window._topicSeenQuestions[String(topicId)] || [];
  return list.slice(-50); // Pass last 50 seen questions for rich cross-test diversity
}

function registerDraftSeenQuestions(courseId, questions) {
  if (!Array.isArray(questions)) return;
  const cid = String(courseId || (currentCourse && currentCourse.id) || 'default');
  if (!window._draftSeenQuestions[cid]) {
    try {
      const stored = localStorage.getItem(`aula_draft_seen_${cid}`);
      window._draftSeenQuestions[cid] = stored ? JSON.parse(stored) : [];
    } catch(e) {
      window._draftSeenQuestions[cid] = [];
    }
  }
  for (const q of questions) {
    if (q && (q.prompt || q.answer)) {
      const pKey = _normalizeKey(q.prompt);
      const aKey = _normalizeKey(q.answer);
      const exists = window._draftSeenQuestions[cid].some(
        sq => (pKey && _normalizeKey(sq.prompt) === pKey) || (aKey && _normalizeKey(sq.answer) === aKey)
      );
      if (!exists) {
        window._draftSeenQuestions[cid].push({
          prompt: q.prompt || '',
          answer: q.answer || ''
        });
      }
    }
  }
  window._draftSeenQuestions[cid] = window._draftSeenQuestions[cid].slice(-100);
  try {
    localStorage.setItem(`aula_draft_seen_${cid}`, JSON.stringify(window._draftSeenQuestions[cid]));
  } catch(e) {}
}

function getDraftSeenQuestions(courseId) {
  const cid = String(courseId || (currentCourse && currentCourse.id) || 'default');
  if (!window._draftSeenQuestions[cid]) {
    try {
      const stored = localStorage.getItem(`aula_draft_seen_${cid}`);
      window._draftSeenQuestions[cid] = stored ? JSON.parse(stored) : [];
    } catch(e) {
      window._draftSeenQuestions[cid] = [];
    }
  }
  return window._draftSeenQuestions[cid].slice(-100);
}

let activityProgressInterval = null;

function showGenerationLoading(el) {
  if (activityProgressInterval) clearInterval(activityProgressInterval);
  window._isGeneratingActivities = true;
  _lastActivityData = null;
  const isTr = currentLang === 'tr';
  el.innerHTML = `
    <div style="padding:36px 24px; text-align:center; background:var(--bg-card); border-radius:16px; border:1px solid var(--border); box-shadow:var(--shadow-lg); margin-top:24px;">
      <div class="loader-container" style="margin:0 auto 20px; position:relative; width:56px; height:56px;">
        <div class="loader-ring" style="width:56px; height:56px; border-radius:50%; border:3px solid rgba(255,255,255,0.06); border-top-color:var(--accent); animation:spin 1s linear infinite;"></div>
        <div class="loader-glow" style="position:absolute; inset:0; background:var(--accent); filter:blur(20px); opacity:0.25; border-radius:50%;"></div>
        <div style="position:absolute; inset:0; display:flex; align-items:center; justify-content:center;">
          <svg style="width:24px;height:24px;color:var(--accent);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path>
          </svg>
        </div>
      </div>
      <h3 style="font-size:20px; font-weight:700; margin-bottom:6px; color:var(--text-primary);">${isTr ? 'Sorular Hazırlanıyor...' : 'Generating Questions...'}</h3>
      <p style="color:var(--text-secondary); font-size:13px; margin-bottom:20px; max-width:380px; margin-left:auto; margin-right:auto;">
        ${isTr ? 'Yapay zekâ ders içeriğine göre özgün soruları ve seçenekleri yapılandırıyor.' : 'AI is structuring authentic questions and distractors for this topic.'}
      </p>

      <div id="activity-progress-box" style="width:100%; max-width:380px; margin:0 auto 16px;">
        <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px; margin-bottom:8px;">
          <span id="activity-progress-status" style="color:var(--accent); font-weight:600;">${isTr ? 'Ders içeriği taranıyor...' : 'Scanning lesson content...'}</span>
          <span id="activity-progress-text" style="font-family:monospace; font-weight:700; color:#fff;">15%</span>
        </div>
        <div style="width:100%; height:6px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
          <div id="activity-progress-fill" style="height:100%; width:15%; background:var(--gradient-2); transition:width 0.3s ease;"></div>
        </div>
      </div>
      <p style="color:var(--text-muted); font-size:12px; margin:0;" data-i18n="gen.time">${t('gen.time')}</p>
    </div>
  `;
}

function startActivityPolling(targetId, title, taskId = null, topicId = null) {
  const el = document.getElementById(targetId);
  if (!el) return;
  const fill = el.querySelector('#activity-progress-fill');
  const text = el.querySelector('#activity-progress-text');
  const statusEl = el.querySelector('#activity-progress-status');

  window._retryEmptyPoll = 0;
  window._actPollErrors = 0;
  window._actTotalPolls = 0;
  if (activityProgressInterval) clearInterval(activityProgressInterval);

  const activeCourseId = courseId || (currentCourse && currentCourse.id) || localStorage.getItem('aula_last_course');
  const uid = currentUser ? currentUser.id : null;

  activityProgressInterval = setInterval(async () => {
    window._actTotalPolls = (window._actTotalPolls || 0) + 1;
    try {
      let pollUrl = `/activity/progress?course_id=${activeCourseId}&v=${Date.now()}`;
      if (taskId) pollUrl += `&task_id=${encodeURIComponent(taskId)}`;
      if (uid) pollUrl += `&user_id=${encodeURIComponent(uid)}`;
      if (topicId) pollUrl += `&topic_id=${encodeURIComponent(topicId)}`;

      const data = await api(pollUrl);
      if (data && !data.error) {
        window._actPollErrors = 0;
        const pct = Math.max(0, Math.min(100, Math.round(data.percentage || 0)));
        if (fill) fill.style.width = pct + '%';
        if (text) text.textContent = pct + '%';
        if (statusEl && data.message) statusEl.textContent = translateBuildMessage(data.message);

        if (data.status === 'done') {
          if (data.results && data.results.length > 0) {
            clearInterval(activityProgressInterval);
            window._isGeneratingActivities = false;
            if (fill) fill.style.width = '100%';
            if (text) text.textContent = '100%';
            if (statusEl) statusEl.textContent = currentLang === 'tr' ? 'Sorular hazır!' : 'Questions ready!';
            clearActivityAnsweredState();

            // Retrieve current topic title if available (without polluting content.activities cache)
            const actSelect = document.getElementById('activity-topic-select');
            const curTid = topicId || (actSelect ? actSelect.value : null);
            registerSeenQuestions(curTid, data.results);

            let currentTopic = null;
            if (curTid && (window.curriculum || curriculum)) {
              for (const ch of (window.curriculum || curriculum)) {
                const tp = ch.topics ? ch.topics.find(t => t.id === curTid) : null;
                if (tp) {
                  currentTopic = tp;
                  break;
                }
              }
            }
            _lastActivityData = { activities: data.results, topic: currentTopic, topicId: curTid };
            const isStudent = currentUser && currentUser.role === 'student';
            const displayTitle = currentTopic ? (getLocalizedCurriculumTitle(currentTopic, currentLang) || currentTopic.title) : title;
            const header = `<div class="page-header" style="margin-top:24px; display:flex; justify-content:space-between; align-items:center;"><h2>${displayTitle}</h2><button class="btn btn-outline btn-sm" onclick="${isStudent ? 'cancelPractice()' : `this.closest('#${targetId}').classList.add('hidden')`}">${t('close')}</button></div>`;
            
            setTimeout(() => {
              document.getElementById(targetId).innerHTML = header + data.results.map((a, i) => renderActivityCard(a, i, targetId)).join('');
              const genBtn = document.getElementById('generate-activity-btn');
              if (genBtn) {
                genBtn.textContent = currentLang === 'tr' ? 'Etkinlikleri Yenile' : 'Regenerate Activity';
                genBtn.disabled = false;
                genBtn.removeAttribute('data-generating');
              }
            }, 300);
            return;
          } else {
            // Done but no results - wait a few more polls or show error
            if (!window._retryEmptyPoll) window._retryEmptyPoll = 0;
            window._retryEmptyPoll++;
            if (window._retryEmptyPoll > 10) {
              clearInterval(activityProgressInterval);
              window._isGeneratingActivities = false;
              const genBtn = document.getElementById('generate-activity-btn');
              if (genBtn) {
                genBtn.textContent = currentLang === 'tr' ? 'Aktivite Oluştur' : 'Generate Activity';
                genBtn.disabled = false;
                genBtn.removeAttribute('data-generating');
              }
              document.getElementById(targetId).innerHTML = `<div style="padding:40px; text-align:center; color:var(--text-muted);">
                  <div style="margin-bottom:16px;">${SVG_SEARCH}</div>
                  <div style="font-weight:700; margin-bottom:8px;">${currentLang === 'tr' ? 'Soru bulunamadı' : 'No questions found'}</div>
                  <div style="font-size:14px; margin-bottom:16px;">${currentLang === 'tr' ? 'Bu konu içeriği için sorular henüz üretilemedi. Lütfen tekrar deneyin.' : 'Questions could not be generated for this topic content. Please try again.'}</div>
                  <button class="btn btn-primary btn-sm" onclick="launchActivity()">${currentLang === 'tr' ? 'Tekrar Dene' : 'Try Again'}</button>
              </div>`;
              return;
            }
          }
        } else if (data.status === 'error') {
          clearInterval(activityProgressInterval);
          window._isGeneratingActivities = false;
          const genBtn = document.getElementById('generate-activity-btn');
          if (genBtn) {
            genBtn.textContent = currentLang === 'tr' ? 'Aktivite Oluştur' : 'Generate Activity';
            genBtn.disabled = false;
            genBtn.removeAttribute('data-generating');
          }
          document.getElementById(targetId).innerHTML = `<div style="padding:30px; color:var(--danger); text-align:center; background:var(--bg-card); border-radius:12px; border:1px solid var(--border);">
            <div style="margin-bottom:12px; font-weight:700;">${currentLang === 'tr' ? 'Aktivite oluşturulurken bir hata oluştu.' : 'Error generating activities.'}</div>
            <button class="btn btn-primary btn-sm" onclick="launchActivity()">${currentLang === 'tr' ? 'Tekrar Dene' : 'Try Again'}</button>
          </div>`;
          return;
        }
      } else {
        window._actPollErrors = (window._actPollErrors || 0) + 1;
      }

      // Hard timeout fallback after ~30s (100 polls): don't freeze indefinitely
      if (window._actTotalPolls > 100) {
        clearInterval(activityProgressInterval);
        window._isGeneratingActivities = false;
        const genBtn = document.getElementById('generate-activity-btn');
        if (genBtn) {
          genBtn.textContent = currentLang === 'tr' ? 'Aktivite Oluştur' : 'Generate Activity';
          genBtn.disabled = false;
          genBtn.removeAttribute('data-generating');
        }
        document.getElementById(targetId).innerHTML = `<div style="padding:30px; text-align:center; background:var(--bg-card); border-radius:12px; border:1px solid var(--border);">
          <p style="color:var(--text-muted); margin-bottom:16px;">${currentLang === 'tr' ? 'Aktivite oluşturma zaman aşımına uğradı.' : 'Activity generation timed out.'}</p>
          <button class="btn btn-primary btn-sm" onclick="launchActivity()">${currentLang === 'tr' ? 'Yeniden Dene' : 'Retry'}</button>
        </div>`;
      }
    } catch (e) {
      console.error("Poll Error:", e);
      window._actPollErrors = (window._actPollErrors || 0) + 1;
    }
  }, 300);
}

let draftProgressInterval = null;

function startDraftPolling(type, btn, originalText, callback, targetCid) {
  const container = document.getElementById(`${type}-gen-progress`);
  const fill = document.getElementById(`${type}-gen-fill`);
  const pctText = document.getElementById(`${type}-gen-pct`);

  const cidToUse = targetCid || courseId || (currentCourse && currentCourse.id) || 'default';

  if (container) {
    container.classList.remove('hidden');
    const span = container.querySelector('span[data-i18n]') || container.querySelector('span');
    if (span) span.textContent = t('gen.generating');
  }
  if (fill) fill.style.width = '0%';
  if (pctText) pctText.textContent = '0%';

  if (draftProgressInterval) clearInterval(draftProgressInterval);

  draftProgressInterval = setInterval(async () => {
    try {
      const data = await api(`/draft/progress?course_id=${cidToUse}&v=${Date.now()}`);

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
          if (btn) {
            btn.textContent = originalText;
            btn.disabled = false;
            btn.removeAttribute('data-generating');
          }
          if (data.questions) callback(data.questions);
        }, 500);
      } else if (data.status === 'error') {
        clearInterval(draftProgressInterval);
        if (container) container.classList.add('hidden');
        if (btn) {
          btn.textContent = originalText;
          btn.disabled = false;
          btn.removeAttribute('data-generating');
        }
        showAlert(t('error'), 'Generation failed', true);
      }
    } catch (err) {
      console.error("Draft Polling Error:", err);
    }
  }, 300);
}

async function launchActivity() {
  clearActivityAnsweredState();
  const topicId = document.getElementById('activity-topic-select').value;
  if (!topicId) return showAlert(t('missing_info'), t('class.select_topic_msg') || (currentLang === 'tr' ? 'Lütfen bir konu seçin' : 'Please select a topic'), true);

  const preview = document.getElementById('activity-preview');
  preview.classList.remove('hidden');

  // Show Loading State
  showGenerationLoading(preview);

  const btn = document.getElementById('generate-activity-btn');
  if (btn) {
    btn.disabled = true;
    btn.setAttribute('data-generating', 'true');
    btn.textContent = currentLang === 'tr' ? 'Oluşturuluyor...' : 'Generating...';
  }

  const activeCourseId = courseId || (currentCourse && currentCourse.id) || localStorage.getItem('aula_last_course');

  try {
    if (_lastActivityData && Array.isArray(_lastActivityData.activities)) {
      registerSeenQuestions(topicId, _lastActivityData.activities);
    }
    const existingQuestions = getSeenQuestions(topicId);

    // 1. Kick off the background task
    const res = await api('/activity/start', {
      method: 'POST',
      body: { 
        topic_id: topicId, 
        course_id: activeCourseId, 
        count: 10, 
        ui_lang: currentLang, 
        user_id: currentUser ? currentUser.id : null,
        existing_questions: existingQuestions
      }
    });
    // 2. Start polling AFTER the task is successfully initiated
    startActivityPolling('activity-preview', (t('Content Map') || 'Content Map'), res ? res.task_id : null, topicId);
  } catch (err) {
    if (btn) {
      btn.disabled = false;
      btn.removeAttribute('data-generating');
      btn.textContent = currentLang === 'tr' ? 'Aktivite Oluştur' : 'Generate Activity';
    }
    preview.innerHTML = `<div style="padding:20px; color:var(--danger); text-align:center; background:var(--danger-bg); border-radius:12px; border:1px solid var(--danger);">
      ${t('assign.retry')}
    </div>`;
  }
}

function maskBlankTranslation(promptText, transText, answer) {
  if (!promptText || !transText) return transText || '';
  if (!/_{2,}/.test(promptText)) return transText;
  if (/_{2,}/.test(transText)) return transText;

  let res = String(transText);
  const ans = String(answer || '').trim();
  if (ans) {
    const regAns = new RegExp('\\b' + ans.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'i');
    if (regAns.test(res)) {
      return res.replace(regAns, '_____');
    }
    const NUMS = {
      'cero': ['zero', 'sıfır'], 'uno': ['one', 'bir'], 'un': ['one', 'bir'], 'una': ['one', 'bir'],
      'dos': ['two', 'iki'], 'tres': ['three', 'üç'], 'cuatro': ['four', 'dört'], 'cinco': ['five', 'beş'],
      'seis': ['six', 'altı'], 'siete': ['seven', 'yedi'], 'ocho': ['eight', 'sekiz'], 'nueve': ['nine', 'dokuz'],
      'diez': ['ten', 'on'], 'once': ['eleven', 'on bir'], 'doce': ['twelve', 'on iki'], 'trece': ['thirteen', 'on üç'],
      'catorce': ['fourteen', 'on dört'], 'quince': ['fifteen', 'on beş'], 'dieciséis': ['sixteen', 'on altı'],
      'diecisiete': ['seventeen', 'on yedi'], 'dieciocho': ['eighteen', 'on sekiz'], 'diecinueve': ['nineteen', 'on dokuz'],
      'veinte': ['twenty', 'yirmi'], 'veintiuno': ['twenty-one', 'yirmi bir'], 'veintidós': ['twenty-two', 'yirmi iki'],
      'veintitrés': ['twenty-three', 'yirmi üç'], 'veinticuatro': ['twenty-four', 'yirmi dört'], 'veinticinco': ['twenty-five', 'yirmi beş'],
      'veintiséis': ['twenty-six', 'yirmi altı'], 'veintisiete': ['twenty-seven', 'yirmi yedi'], 'veintiocho': ['twenty-eight', 'yirmi sekiz'],
      'veintinueve': ['twenty-nine', 'yirmi dokuz'], 'treinta': ['thirty', 'otuz'], 'cuarenta': ['forty', 'kırk'],
      'cincuenta': ['fifty', 'elli'], 'sesenta': ['sixty', 'altmış'], 'setenta': ['seventy', 'yetmiş'],
      'ochenta': ['eighty', 'seksen'], 'noventa': ['ninety', 'doksan'], 'cien': ['hundred', 'yüz'], 'ciento': ['hundred', 'yüz']
    };
    const mapped = NUMS[ans.toLowerCase()];
    if (mapped) {
      for (const mWord of mapped) {
        const regWord = new RegExp('\\b' + mWord.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'i');
        if (regWord.test(res)) {
          return res.replace(regWord, '_____');
        }
      }
    }
  }
  return res;
}

function renderPromptHTML(a, isQuiz = false) {
  let p = formatActivityData(a.prompt);
  
  if (isQuiz) {
    return `<div class="activity-prompt">${esc(p)}</div>`;
  }
  
  let transTr = a.translation_tr || a.turkish || translateEducationalText(a.translation || '') || a.translation || '';
  let transEn = a.translation_en || a.english || a.translation || '';
  transTr = maskBlankTranslation(p, transTr, a.answer);
  transEn = maskBlankTranslation(p, transEn, a.answer);

  if (transTr || transEn) {
    return `<div class="activity-prompt-wrapper" style="position:relative; display:inline-block; margin-bottom:8px; cursor:help;" 
      data-trans-tr="${esc(transTr)}" data-trans-en="${esc(transEn)}"
      onmouseenter="showActivityTooltip(this)" 
      onmouseleave="hideActivityTooltip(this)">
      <div class="activity-prompt" style="display:inline; border-bottom:1px dashed var(--text-muted); padding-bottom:2px;">${esc(p)}</div>
      <div class="activity-translation" style="font-size:13px; color:var(--text-muted); margin-top:8px; display:none; padding:10px 14px; background:var(--bg-card); border:1px solid var(--border); border-radius:8px; border-left:3px solid var(--accent); position:absolute; z-index:100; box-shadow:0 4px 12px rgba(0,0,0,0.5); width:max-content; max-width:420px; left:0; top:100%;"></div>
    </div>`;
  }
  return `<div class="activity-prompt">${esc(p)}</div>`;
}

function showActivityTooltip(wrapper) {
  const tip = wrapper.querySelector('.activity-translation');
  if (!tip) return;
  const tr = wrapper.getAttribute('data-trans-tr') || '';
  const en = wrapper.getAttribute('data-trans-en') || '';
  const text = (currentLang === 'tr' ? (tr || en) : (en || tr));
  if (!text) return;
  tip.innerHTML = `<i>${esc(text)}</i>`;
  tip.style.display = 'block';
}

function hideActivityTooltip(wrapper) {
  const tip = wrapper.querySelector('.activity-translation');
  if (tip) tip.style.display = 'none';
}

function renderActivityCard(a, idx, ctx) {
  const promptHTML = renderPromptHTML(a);
  const isLecturer = currentUser && currentUser.role === 'lecturer';
  const explText = (currentLang === 'tr' ? (a.why_tr || a.explanation_tr || a.why || a.explanation) : (a.why || a.explanation || a.why_tr || a.explanation_tr)) || '';
  const editBtns = isLecturer ? `
    <div style="position:absolute; top:12px; right:12px; display:flex; gap:6px; z-index:10;">
        <button class="btn btn-ghost btn-xs" onclick="editActivityQuestion(${escJS(a.id)}, '${ctx}-${idx}', ${escJS(a.type)})" style="background:rgba(255,255,255,0.1); padding:4px;">${SVG_EDIT}</button>
        <button class="btn btn-ghost btn-xs" onclick="deleteActivityQuestion(${escJS(a.id)}, '${ctx}-${idx}')" style="background:rgba(255,59,48,0.1); color:var(--danger); padding:4px;">${SVG_TRASH}</button>
    </div>
  ` : '';

  // Look up saved state strictly by question identity, NEVER by generic DOM slot index
  const qKey = a.id ? `act_q_${a.id}` : (a.prompt ? `act_p_${encodeURIComponent(a.prompt.trim())}` : null);
  const savedState = qKey ? _answeredQuestionsState[qKey] : null;

  const explLabel = currentLang === 'tr' ? 'Açıklama' : 'Explanation';
  const isAlreadyTr = (currentLang === 'tr') && (/[çğıöşüÇĞİÖŞÜ]/.test(explText) || explText.includes('doğru') || explText.includes('çünkü') || explText.includes('ifade'));
  const displayExpl = (currentLang === 'tr') ? (isAlreadyTr ? explText : (typeof translateEducationalText === 'function' ? translateEducationalText(explText) : explText)) : explText;

  const explBoxHTML = (explText) ? `
    <div class="activity-explanation-box" style="margin-top:16px; padding:16px 20px; background:rgba(255,255,255,0.04); border-radius:12px; border:1px solid var(--border); font-size:15px; line-height:1.6; color:var(--text-primary); text-align:left;">
      <div style="font-weight:700; color:var(--accent-light); margin-bottom:6px; display:flex; align-items:center; gap:6px;"><span>${explLabel}</span></div>
      <div>${fixDiacritics(displayExpl)}</div>
    </div>
  ` : '';

  if (a.type === 'mcq') {
    // Guarantee 4 options: if an activity only has 3 options, borrow a 4th option from sibling activities
    if (Array.isArray(a.options) && a.options.length === 3 && Array.isArray(_lastActivityData?.activities)) {
      for (const otherAct of _lastActivityData.activities) {
        if (otherAct && Array.isArray(otherAct.options)) {
          const cand = otherAct.options.find(opt => opt && !a.options.some(co => String(co).trim().toLowerCase() === String(opt).trim().toLowerCase()));
          if (cand) {
            a.options.push(cand);
            if (Array.isArray(a.distractors) && !a.distractors.includes(cand) && String(cand).toLowerCase() !== String(a.answer || '').toLowerCase()) {
              a.distractors.push(cand);
            }
            break;
          }
        }
      }
    }

    let cardClass = "activity-card";
    let fbClass = "feedback-msg hidden";
    let fbContent = "";
    let optionsHTML = "";
    let showExpl = false;

    if (savedState && savedState.type === 'mcq') {
      cardClass += savedState.isCorrect ? " correct" : " incorrect";
      fbClass = "feedback-msg " + (savedState.isCorrect ? "correct" : "incorrect");
      fbContent = savedState.isCorrect ? t('correctMsg') : `<span>${t('incorrectAns')} ${a.answer}</span>`;
      showExpl = true;

      optionsHTML = (a.options || []).map(o => {
        const isOptAnswer = (o.toLowerCase() === String(a.answer || '').toLowerCase());
        const isOptPicked = (o === savedState.picked);
        let btnCls = "option-btn";
        let icon = "";
        let opStyle = "opacity:0.75;";

        if (isOptAnswer) {
          btnCls += " correct-answer";
          icon = ' ' + SVG_CHECK;
          opStyle = "opacity:1;";
        } else if (isOptPicked && !savedState.isCorrect) {
          btnCls += " wrong-answer";
          icon = ' ' + SVG_CROSS;
          opStyle = "opacity:1;";
        }
        return `<button class="${btnCls}" disabled style="${opStyle}" data-original="${esc(o)}">${fixDiacritics(safeStr(o))}${icon}</button>`;
      }).join('');
    } else {
      optionsHTML = (a.options || []).map(o => `<button class="option-btn" data-original="${esc(o)}" onclick="checkMCQ(this, ${escJS(a.answer)}, '${ctx}-${idx}', ${escJS(a.id)})">${fixDiacritics(safeStr(o))}</button>`).join('');
    }

    return `<div class="${cardClass}" id="${ctx}-${idx}" data-explanation="${esc(explText)}" style="position:relative">${editBtns}<div class="activity-type-label"><span data-i18n="draft.mcq">${t('draft.mcq')}</span></div>${promptHTML}<div class="options-grid">${optionsHTML}</div><div class="${fbClass}" id="fb-${ctx}-${idx}">${fbContent}</div>${showExpl ? explBoxHTML : ''}</div>`;
  }

  if (a.type === 'fill_blank') {
    let cardClass = "activity-card";
    let fbClass = "feedback-msg hidden";
    let fbContent = "";
    let showExpl = false;
    let inputAttr = "";

    if (savedState && savedState.type === 'fill_blank') {
      cardClass += savedState.isCorrect ? " correct" : " incorrect";
      fbClass = "feedback-msg " + (savedState.isCorrect ? "correct" : "incorrect");
      fbContent = savedState.isCorrect ? t('correctMsg') : `<span>${t('incorrectAns')} ${a.answer}</span>`;
      showExpl = true;
      inputAttr = `value="${esc(savedState.val || '')}" disabled`;
    }

    return `<div class="${cardClass}" id="${ctx}-${idx}" data-explanation="${esc(explText)}" style="position:relative">${editBtns}<div class="activity-type-label"><span data-i18n="draft.fill_blank">${t('draft.fill_blank')}</span></div>${promptHTML}<div style="display:flex;gap:10px;align-items:center;margin-top:12px"><input class="fill-blank-input" id="inp-${ctx}-${idx}" ${inputAttr} data-i18n-placeholder="assign.type_answer" placeholder="${t('assign.type_answer')}" style="flex:1" onkeydown="if(event.key==='Enter')checkFill('${ctx}-${idx}',${escJS(a.answer)},${escJS(a.id)})"><button class="btn btn-primary btn-sm" ${savedState ? 'disabled' : ''} onclick="checkFill('${ctx}-${idx}',${escJS(a.answer)},${escJS(a.id)})" data-i18n="check">${t('check')}</button></div>${a.hint ? `<div style="margin-top:8px;font-size:13px;color:var(--text-muted)"><span style="font-weight:600;color:var(--accent);">Hint:</span> ${a.hint}</div>` : ''}<div class="${fbClass}" id="fb-${ctx}-${idx}">${fbContent}</div>${showExpl ? explBoxHTML : ''}</div>`;
  }

  if (a.type === 'dialogue_order') {
    const lines = a.scrambled_lines || [];
    const speakers = a.speakers || {};
    return `<div class="activity-card" id="${ctx}-${idx}" data-explanation="${esc(explText)}" style="position:relative">${editBtns}<div class="activity-type-label"><span data-i18n="prac.dialogue">${t('prac.dialogue')}</span></div><div class="activity-prompt" data-i18n="prac.dialogue_order">${t('prac.dialogue_order')}</div><div id="dialogue-${ctx}-${idx}" style="display:flex;flex-direction:column;gap:8px;margin-top:12px">${lines.map((line, li) => `<div class="dialogue-row" style="display:flex;align-items:center;gap:8px" data-line="${esc(line)}"><button class="btn btn-ghost btn-sm" onclick="moveDialogueLine(this,-1)" style="min-width:36px">▲</button><button class="btn btn-ghost btn-sm" onclick="moveDialogueLine(this,1)" style="min-width:36px">▼</button><div style="flex:1;padding:10px 14px;background:var(--bg-input);border:2px solid var(--border);border-radius:var(--radius-sm);font-size:14px"><span style="font-weight:600;color:var(--accent-light);margin-right:8px">${speakers[line] || '?'}:</span>${line}</div></div>`).join('')}</div><button class="btn btn-primary btn-sm" style="margin-top:12px" onclick="checkDialogue('${ctx}-${idx}',${escJS(JSON.stringify(a.correct_order))})"><span data-i18n="check">${t('check')}</span></button><div class="feedback-msg hidden" id="fb-${ctx}-${idx}"></div></div>`;
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
  if (s === null || s === undefined) return "''";
  const json = JSON.stringify(String(s));
  // Replace double quotes with HTML entities so it can live inside onclick="..."
  return json.replace(/"/g, '&quot;');
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
  const explanation = card.getAttribute('data-explanation') || '';

  const stateObj = {
    type: 'mcq',
    picked,
    answer,
    isCorrect,
    explanation,
    qid
  };
  const promptEl = card.querySelector('.activity-prompt');
  const promptTxt = promptEl ? promptEl.textContent.trim() : '';
  const qKey = qid ? `act_q_${qid}` : (promptTxt ? `act_p_${encodeURIComponent(promptTxt)}` : null);
  if (qKey) _answeredQuestionsState[qKey] = stateObj;

  card.querySelectorAll('.option-btn').forEach(b => {
    b.disabled = true;
    b.style.opacity = '0.75';
    const bText = (b.dataset.original || b.textContent.trim()).replace(/\\'/g, "'");
    if (bText.toLowerCase() === answer.toLowerCase()) {
      b.classList.add('correct-answer');
      b.style.opacity = '1';
      if (!b.querySelector('svg')) b.innerHTML += ' ' + SVG_CHECK;
    } else if (b === btn && !isCorrect) {
      b.classList.add('wrong-answer');
      b.style.opacity = '1';
      if (!b.querySelector('svg')) b.innerHTML += ' ' + SVG_CROSS;
    }
  });

  card.classList.add(isCorrect ? 'correct' : 'incorrect');
  const fb = document.getElementById('fb-' + cardId);
  fb.classList.remove('hidden');
  fb.className = 'feedback-msg ' + (isCorrect ? 'correct' : 'incorrect');
  if (isCorrect) {
    fb.textContent = t('correctMsg');
  } else {
    fb.innerHTML = `<span>${t('incorrectAns')} ${answer}</span>`;
  }
  fb.onclick = null;

  // Instant explanation box matching study material (Photo 5 style, zero extra AI usage)
  if (explanation && !card.querySelector('.activity-explanation-box')) {
    const expDiv = document.createElement('div');
    expDiv.className = 'activity-explanation-box';
    expDiv.style.cssText = 'margin-top:16px; padding:16px 20px; background:rgba(255,255,255,0.04); border-radius:12px; border:1px solid var(--border); font-size:15px; line-height:1.6; color:var(--text-primary); text-align:left; animation:fadeIn 0.25s ease;';
    const explLabel = currentLang === 'tr' ? 'Açıklama' : 'Explanation';
    const isAlreadyTr = (currentLang === 'tr') && (/[çğıöşüÇĞİÖŞÜ]/.test(explanation) || explanation.includes('doğru') || explanation.includes('çünkü') || explanation.includes('ifade'));
    const displayExplanation = (currentLang === 'tr') ? (isAlreadyTr ? explanation : (typeof translateEducationalText === 'function' ? translateEducationalText(explanation) : explanation)) : explanation;
    expDiv.innerHTML = `<div style="font-weight:700; color:var(--accent-light); margin-bottom:6px; display:flex; align-items:center; gap:6px;"><span>${explLabel}</span></div><div>${fixDiacritics(displayExplanation)}</div>`;
    card.appendChild(expDiv);
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

  const explanation = card.getAttribute('data-explanation') || '';
  const stateObj = {
    type: 'fill_blank',
    val,
    answer,
    isCorrect,
    explanation,
    qid
  };
  const promptEl = card.querySelector('.activity-prompt');
  const promptTxt = promptEl ? promptEl.textContent.trim() : '';
  const qKey = qid ? `act_q_${qid}` : (promptTxt ? `act_p_${encodeURIComponent(promptTxt)}` : null);
  if (qKey) _answeredQuestionsState[qKey] = stateObj;

  const fb = document.getElementById('fb-' + id);
  fb.classList.remove('hidden');
  fb.className = 'feedback-msg ' + (isCorrect ? 'correct' : 'incorrect');
  if (isCorrect) {
    fb.textContent = t('correctMsg');
  } else {
    fb.innerHTML = `<span>${t('incorrectAns')} ${answer}</span>`;
  }
  fb.onclick = null;

  // Instant explanation box matching study material (Photo 5 style, zero extra AI usage)
  if (explanation && !card.querySelector('.activity-explanation-box')) {
    const expDiv = document.createElement('div');
    expDiv.className = 'activity-explanation-box';
    expDiv.style.cssText = 'margin-top:16px; padding:16px 20px; background:rgba(255,255,255,0.04); border-radius:12px; border:1px solid var(--border); font-size:15px; line-height:1.6; color:var(--text-primary); text-align:left; animation:fadeIn 0.25s ease;';
    const explLabel = currentLang === 'tr' ? 'Açıklama' : 'Explanation';
    const isAlreadyTr = (currentLang === 'tr') && (/[çğıöşüÇĞİÖŞÜ]/.test(explanation) || explanation.includes('doğru') || explanation.includes('çünkü') || explanation.includes('ifade'));
    const displayExplanation = (currentLang === 'tr') ? (isAlreadyTr ? explanation : (typeof translateEducationalText === 'function' ? translateEducationalText(explanation) : explanation)) : explanation;
    expDiv.innerHTML = `<div style="font-weight:700; color:var(--accent-light); margin-bottom:6px; display:flex; align-items:center; gap:6px;"><span>${explLabel}</span></div><div>${fixDiacritics(displayExplanation)}</div>`;
    card.appendChild(expDiv);
  }

  if (id.startsWith('prac')) await api('/activity/respond', { method: 'POST', body: { student_id: currentUser.id, question_id: qid, answer: val, correct_answer: answer, question_type: 'fill_blank' } });
}

async function explainMistake(cardId, correct_answer, student_answer) {
  const fb = document.getElementById('fb-' + cardId);
  if (fb.dataset.explaining) return;
  fb.dataset.explaining = "true";
  
  const originalHtml = fb.innerHTML;
  fb.innerHTML = `<div style="display:flex; align-items:center; gap:8px;"><span class="ai-badge">AI</span> <span style="font-size:12px; animation:pulse 1.5s infinite;">${t('ai_analyzing')}</span></div>`;
  
  const card = document.getElementById(cardId);
  const prompt = card.querySelector('.activity-prompt').innerText;
  const language = (currentCourse && currentCourse.language) ? currentCourse.language : 'English';
  
  try {
    const courseId = currentCourse ? currentCourse.id : '';
    const res = await api('/activity/explain', {
      method: 'POST',
      body: { prompt, correct_answer, student_answer, language, course_id: courseId, ui_lang: currentLang }
    });
    
    if (res.explanation) {
      fb.innerHTML = `
        <div style="font-weight:600; margin-bottom:6px;">${t('incorrectAns')} ${correct_answer}</div>
        <div style="background:rgba(255,255,255,0.1); padding:10px; border-radius:8px; font-size:13.5px; line-height:1.45;">
          <span class="ai-badge" style="margin-right:6px;">AI</span> ${res.explanation}
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
  btn.textContent = currentLang === 'tr' ? 'Oluşturuluyor...' : 'Generating...';
  btn.disabled = true;
  btn.setAttribute('data-generating', 'true');

  const title = document.getElementById('quiz-title').value || 'Quiz';
  const chapterId = document.getElementById('quiz-chapter-select').value || null;
  const count = parseInt(document.getElementById('quiz-count').value) || 10;

  const targetCourseId = courseId || (currentCourse && currentCourse.id) || localStorage.getItem('aula_last_course');

  if (currentDraft && Array.isArray(currentDraft.questions)) {
    registerDraftSeenQuestions(targetCourseId, currentDraft.questions);
  }
  const existingQuestions = getDraftSeenQuestions(targetCourseId);

  try {
    const res = await api('/draft/generate', { 
      method: 'POST', 
      body: { 
        course_id: targetCourseId, 
        chapter_id: chapterId, 
        count, 
        ui_lang: currentLang,
        existing_questions: existingQuestions
      } 
    });
    if (res.error) throw new Error(res.error);

    startDraftPolling('quiz', btn, originalText, (questions) => {
      registerDraftSeenQuestions(targetCourseId, questions);
      currentDraft = {
        type: 'quiz',
        title: title,
        course_id: targetCourseId,
        chapter_id: chapterId,
        questions: questions
      };
      openDraftModal();
    }, targetCourseId);
  } catch (err) {
    btn.textContent = originalText;
    btn.disabled = false;
    btn.removeAttribute('data-generating');
    showAlert(t('error'), err.message, true);
  }
}

async function loadQuizList() {
  const quizzes = await api(`/quizzes?course_id=${courseId}&student_id=${currentUser.id}`);
  _lastQuizListData = quizzes;
  renderQuizList(quizzes);
}

function renderQuizList(quizzes) {
  const isLecturer = currentUser && currentUser.role === 'lecturer';
  const container = isLecturer ? document.getElementById('quiz-list') : document.getElementById('student-quiz-list');
  if (!container) return;
  container.innerHTML = (!quizzes || quizzes.length === 0) ? `<p style="color:var(--text-muted);padding:20px" data-i18n="noQuizzes">${t('noQuizzes')}</p>`
    : quizzes.map(q => {
      const displayTitle = esc(translateQuizTitle(q.title, currentLang));
      const createdLabel = t('Created');
      const formattedDate = new Date(q.created_at).toLocaleDateString(currentLang === 'tr' ? 'tr-TR' : 'en-US');
      if (isLecturer) {
        return `<div class="card" style="margin-bottom:12px">
            <div class="card-body flex-between">
              <div style="flex:1;cursor:pointer" onclick="viewQuiz('${q.id}',${escJS(q.title)})">
                <strong class="quiz-item-title" data-raw-title="${esc(q.title)}">${displayTitle}</strong>
                <div style="font-size:13px;color:var(--text-muted);margin-top:4px"><span data-i18n="Created">${createdLabel}</span>: <span class="quiz-item-date" data-created-at="${q.created_at}">${formattedDate}</span></div>
              </div>
              <div style="display:flex;gap:8px;align-items:center">
                <button class="btn btn-outline btn-sm" onclick="viewQuiz('${q.id}',${escJS(q.title)})">${SVG_EYE} <span data-i18n="viewBtn">${t('viewBtn')}</span></button>
                <button class="btn btn-sm" style="background:var(--danger-bg,#fde8e8);color:var(--danger);border:1px solid var(--danger)" onclick="event.stopPropagation();deleteQuiz('${q.id}',${escJS(q.title)})">${SVG_TRASH} <span data-i18n="confirm.delete_quiz">${t('confirm.delete_quiz')}</span></button>
              </div>
            </div>
          </div>`;
      } else {
        const isCompleted = q.is_completed;
        return `<div class="card" style="cursor:${isCompleted ? 'default' : 'pointer'};opacity:${isCompleted ? '0.6' : '1'};margin-bottom:12px" onclick="${isCompleted ? '' : `takeQuiz('${q.id}')`}">
          <div class="card-body flex-between">
            <div>
              <strong class="quiz-item-title" data-raw-title="${esc(q.title)}">${displayTitle}</strong>
              <div style="font-size:13px;color:var(--text-muted);margin-top:4px"><span data-i18n="Created">${createdLabel}</span>: <span class="quiz-item-date" data-created-at="${q.created_at}">${formattedDate}</span> ${isCompleted ? ` · <span style="color:var(--success)">${SVG_CHECK} <span data-i18n="completed">${t('completed')}</span></span>` : ''}</div>
            </div>
            <span class="btn btn-sm ${isCompleted ? 'btn-ghost' : 'btn-outline'}">${isCompleted ? `<span data-i18n="completed">${t('completed')}</span>` : `<span data-i18n="takeQuizBtn">${t('takeQuizBtn')}</span>`}</span>
          </div>
        </div>`;
      }
    }).join('');
}

async function deleteQuiz(quizId, title) {
  if (!(await showConfirmModal('confirm.delete_quiz', 'confirm.delete_quiz_msg', true, null, false, 'ok', 'cancel', { title }))) return;
  const res = await api('/quiz/delete', { method: 'POST', body: { quiz_id: quizId } });
  if (res && !res.error) loadQuizList();
}

async function viewQuiz(quizId, title) {
  window._currentViewingQuiz = { id: quizId, title: title };
  window._currentViewingAssignment = null;
  const modal = document.getElementById('student-detail-modal');
  modal.classList.remove('hidden');
  document.getElementById('student-detail-body').innerHTML = `<div style="text-align:center;padding:48px 20px;color:var(--text-muted);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;"><div class="spinner-small"></div><span style="font-size:14px;">${t('loading') || (currentLang === 'tr' ? 'Yükleniyor...' : 'Loading...')}</span></div>`;

  const [quizData, respData] = await Promise.all([
    api('/quiz/take?quiz_id=' + quizId),
    api('/quiz/responses?quiz_id=' + quizId)
  ]);

  const studentResults = (respData && respData.student_results) || [];
  const classAvg = (respData && respData.average_score) ? Math.round(respData.average_score * 100) : 0;
  const isTr = currentLang === 'tr';
  const displayTitle = translateQuizTitle(title, currentLang);
  const qs = (quizData && quizData.questions) || [];

  const L = {
    noResponses: t('assign.no_responses') || (isTr ? 'Henüz yanıt gönderilmedi.' : 'No responses submitted yet.'),
    submitted: t('assign.submitted') || (isTr ? 'gönderildi' : 'submitted'),
    classAvg: t('assign.class_avg') || (isTr ? 'Sınıf Ortalaması' : 'Class Average'),
    correct: t('assign.correct') || (isTr ? 'Doğru' : 'Correct'),
    studentAnswer: t('assign.student_answer') || (isTr ? 'Öğrenci Yanıtı' : 'Student Answer'),
    correctAns: t('assign.correct_answer') || (isTr ? 'Doğru Cevap' : 'Correct Answer'),
    questionsTab: isTr ? 'Sorular' : 'Questions',
    responsesTab: isTr ? 'Yanıtlar' : 'Responses'
  };

  const completedList = studentResults.filter(sr => sr.status === 'completed' || (!sr.has_unsubmitted && !sr.answers.some(a => a.student_answer === '[STARTED]')));
  const inProgressList = studentResults.filter(sr => sr.status === 'in_progress' || sr.has_unsubmitted || sr.answers.some(a => a.student_answer === '[STARTED]'));

  document.getElementById('student-detail-body').innerHTML = `
    <h2 style="margin-bottom:4px">${displayTitle}</h2>
    <div style="color:var(--text-muted); margin-bottom:20px; font-size:14px">
      <span>${L.classAvg}</span>: <strong style="color:var(--accent)">${classAvg}%</strong> · 
      ${completedList.length} <span>${L.submitted}</span>${inProgressList.length > 0 ? ` · <span style="color:#f59e0b;font-weight:600">${inProgressList.length} ${isTr ? 'devam ediyor' : 'in progress'}</span>` : ''}
    </div>
    
    <div style="display:flex;gap:8px;margin-bottom:20px;border-bottom:1px solid var(--border)">
      <button class="nav-tab active" onclick="switchQuizViewTab(this,'qv-questions')" style="flex:1;padding:10px"><span>${L.questionsTab}</span> (${qs.length})</button>
      <button class="nav-tab" onclick="switchQuizViewTab(this,'qv-responses')" style="flex:1;padding:10px"><span>${L.responsesTab}</span> (${studentResults.length})</button>
    </div>

    <div id="qv-questions">
      <div style="display:flex;flex-direction:column;gap:12px">
        ${qs.map((q, i) => `
          <div style="padding:16px;border:1px solid var(--border);border-radius:8px;background:var(--bg-card)">
            <div style="font-size:12px;font-weight:600;color:var(--text-muted);margin-bottom:8px;text-transform:uppercase">
              ${isTr ? 'Soru' : 'Question'} ${i + 1} • ${translateOption(q.type === 'mcq' ? (isTr ? 'Çoktan Seçmeli' : 'Multiple Choice') : (isTr ? 'Boşluk Doldurma' : 'Fill in the Blank'))}
            </div>
            <div style="font-size:15px;margin-bottom:12px">${fixDiacritics(safeStr(q.prompt))}</div>
            ${q.type === 'mcq' ? `
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                ${(q.distractors || []).concat([q.answer]).map(o => `
                    <div style="padding:8px 12px;background:var(--bg-input);border-radius:4px;font-size:13px;border:1px solid ${o === q.answer ? 'var(--success)' : 'var(--border)'};color:${o === q.answer ? 'var(--success)' : 'inherit'};font-weight:${o === q.answer ? '600' : 'normal'}">
                    ${o === q.answer ? SVG_CHECK + ' ' : ''}${fixDiacritics(safeStr(o))}
                  </div>
                `).join('')}
              </div>
            ` : `
              <div style="padding:8px 12px;background:var(--bg-input);border-radius:4px;font-size:13px;border:1px solid var(--success);color:var(--success);font-weight:600;display:inline-block">
                ${SVG_CHECK} ${q.answer}
              </div>
            `}
          </div>
        `).join('')}
      </div>
    </div>

    <div id="qv-responses" style="display:none">
      ${studentResults.length === 0
      ? `<p style="color:var(--text-muted);padding:20px;text-align:center">${L.noResponses}</p>`
      : studentResults.map(sr => {
        const isInProgress = (sr.status === 'in_progress' || sr.has_unsubmitted || sr.answers.some(a => a.student_answer === '[STARTED]'));
        const avgPct = Math.round(sr.average_score * 100);
        const answeredCount = sr.answered_count || sr.answers.filter(a => a.student_answer !== '[STARTED]').length;
        const correctCount = sr.answers.filter(a => a.is_correct && a.student_answer !== '[STARTED]').length;
        return `
              <div style="margin-bottom:16px; border:1px solid var(--border); border-radius:8px; overflow:hidden">
                <div style="padding:14px 16px; background:var(--bg-secondary); display:flex; justify-content:space-between; align-items:center; cursor:pointer" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
                  <div>
                    <strong style="font-size:15px">${sr.student_name}</strong>
                    ${isInProgress
                      ? `<span style="font-size:12px; background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.4); padding:2px 8px; border-radius:12px; margin-left:8px; font-weight:600">${isTr ? 'Sınav Devam Ediyor' : 'In Progress'}</span>
                         <span style="font-size:13px; color:var(--text-muted); margin-left:8px">(${answeredCount}/${sr.total_questions} ${isTr ? 'yanıtlandı' : 'answered'})</span>`
                      : `<span style="font-size:13px; color:var(--text-muted); margin-left:8px">${correctCount}/${sr.total_questions} <span>${L.correct}</span></span>`
                    }
                  </div>
                  <div style="display:flex; align-items:center; gap:10px">
                    ${isInProgress
                      ? `<span style="font-weight:600; font-size:14px; color:#f59e0b;">—</span>`
                      : `<span style="font-weight:700; font-size:16px; color:${masteryColor(sr.average_score)}">${avgPct}%</span>`
                    }
                    <span style="color:var(--text-muted); font-size:18px">▾</span>
                  </div>
                </div>
                <div style="display:none; padding:12px 16px; background:var(--bg-card)">
                  ${sr.answers.map((a, i) => {
                    const isStarted = (a.student_answer === '[STARTED]');
                    const isRight = a.is_correct && !isStarted;
                    return `
                      <div style="padding:10px 0; border-bottom:1px solid var(--border); font-size:13px; display:flex; gap:10px; align-items:flex-start">
                        <span style="min-width:20px; font-weight:700; color:${isStarted ? 'var(--text-muted)' : (isRight ? 'var(--success)' : 'var(--danger)')}">
                          ${isStarted ? '⏳' : (isRight ? SVG_CHECK : SVG_CROSS)}
                        </span>
                        <div style="flex:1">
                          <div style="margin-bottom:4px; font-weight:500">${fixDiacritics(safeStr(a.prompt))}</div>
                          <div style="display:flex; gap:16px; flex-wrap:wrap">
                            ${isStarted
                              ? `<span style="color:var(--text-muted);font-style:italic;">${isTr ? 'Henüz yanıtlanmadı (Sınav devam ediyor)' : 'Not answered yet (In progress)'}</span>`
                              : `<span><span>${L.studentAnswer}</span>: <strong style="color:${isRight ? 'var(--success)' : 'var(--danger)'}">${esc(a.student_answer)}</strong></span>
                                 ${!isRight ? `<span><span>${L.correctAns}</span>: <strong style="color:var(--success)">${a.correct_answer}</strong></span>` : ''}`
                            }
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
  const modalBody = btn.closest('#student-detail-body') || document.getElementById('student-detail-body');
  if (modalBody) {
    ['qv-questions', 'qv-responses', 'av-questions', 'av-responses'].forEach(id => {
      const p = modalBody.querySelector('#' + id);
      if (p) p.style.display = (id === panelId) ? 'block' : 'none';
    });
  }
}

function _quizBeforeUnloadHandler(e) {
  e.preventDefault();
  e.returnValue = '';
  return '';
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

  // Pre-shuffle options ONCE so language switching NEVER shuffles or changes option order!
  if (Array.isArray(data.questions)) {
    data.questions.forEach(q => {
      if (q.type === 'mcq' && !q._shuffledOptions) {
        const rawOpts = (Array.isArray(q.options) && q.options.length > 1)
          ? q.options
          : (q.distractors || []).concat([q.answer]);
        q._shuffledOptions = rawOpts.slice().sort(() => Math.random() - 0.5);
      }
    });
  }

  // Register browser beforeunload reload warning & track in localStorage
  window.addEventListener('beforeunload', _quizBeforeUnloadHandler);
  localStorage.setItem('aula_taking_quiz', quizId);

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
  // Stable option list - never re-shuffles on render or language toggle
  let qMcqOpts = q._shuffledOptions || ((Array.isArray(q.options) && q.options.length > 1) ? q.options : (q.distractors || []).concat([q.answer]));
  if (Array.isArray(qMcqOpts) && qMcqOpts.length === 3 && Array.isArray(qs)) {
    for (const otherQ of qs) {
      const otherOpts = otherQ.options || (otherQ.distractors || []).concat([otherQ.answer]);
      if (Array.isArray(otherOpts)) {
        const cand = otherOpts.find(opt => opt && !qMcqOpts.some(co => String(co).trim().toLowerCase() === String(opt).trim().toLowerCase()));
        if (cand) {
          qMcqOpts.push(cand);
          q._shuffledOptions = qMcqOpts;
          break;
        }
      }
    }
  }
  area.innerHTML = `<div class="quiz-header"><span class="quiz-progress-text">Q${idx + 1}/${qs.length}</span></div><div class="activity-card">${renderPromptHTML(q, true)}` +
    (q.type === 'mcq' ? `<div class="options-grid">${qMcqOpts.map(o => `<button class="option-btn" onclick="quizAnswer(this,${escJS(q.id)},${escJS(o)})">${fixDiacritics(safeStr(o))}</button>`).join('')}</div>` : `<div style="display:flex;gap:10px;align-items:center;margin-top:12px"><input class="fill-blank-input" id="q-inp" style="flex:1" placeholder="..." onkeydown="if(event.key==='Enter')quizAnswer(null,${escJS(q.id)},this.value)"><button class="btn btn-primary" onclick="quizAnswer(null,${escJS(q.id)},document.getElementById('q-inp').value)" data-i18n="submit">${t('submit')}</button></div>`) + `</div>`;
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
  window.removeEventListener('beforeunload', _quizBeforeUnloadHandler);
  localStorage.removeItem('aula_taking_quiz');
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
      pendingEl.innerHTML = `<div style="background:var(--accent-glow);padding:20px;border-radius:var(--radius-lg);border:1px solid var(--border);margin-bottom:24px">
        <h3 style="color:var(--accent);margin:0 0 16px 0;font-size:1.1rem"><span data-i18n="Account Pending Approval">${t('Account Pending Approval')}</span> (${pending.length})</h3>
        ${pending.map(s => `
          <div style="display:flex;align-items:center;justify-content:space-between;background:var(--bg-card);padding:14px 20px;border-radius:var(--radius);margin-bottom:8px;border:1px solid var(--border)">
            <div style="min-width:0;flex:1;overflow:hidden">
              <div style="font-weight:600;color:var(--text-primary);font-size:0.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${s.name}</div>
              <div style="color:var(--text-secondary);font-size:0.8rem;margin-top:2px">${s.email}</div>
            </div>
            <div style="display:flex;gap:8px;margin-left:16px;flex-shrink:0">
              <button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); approveStudent('${s.id}')"><span data-i18n="ok">${t('ok')}</span></button>
              <button class="btn btn-outline btn-sm" onclick="event.stopPropagation(); deleteStudent('${s.id}',${escJS(s.name)})"><span data-i18n="cancel">${t('cancel')}</span></button>
            </div>
          </div>
        `).join('')}
      </div>`;
    } else {
      pendingEl.innerHTML = '';
    }
  }

  // Save cache and render approved students into grid
  _lastStudentRosterData = students;
  renderStudentRoster(students);
}

function getStudentInitials(name) {
  if (!name) return 'S';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

const STUDENT_AVATAR_GRADIENTS = [
  'linear-gradient(135deg, #6366f1, #8b5cf6)',
  'linear-gradient(135deg, #3b82f6, #06b6d4)',
  'linear-gradient(135deg, #10b981, #059669)',
  'linear-gradient(135deg, #f59e0b, #d97706)',
  'linear-gradient(135deg, #ec4899, #8b5cf6)',
  'linear-gradient(135deg, #8b5cf6, #d946ef)',
  'linear-gradient(135deg, #14b8a6, #0284c7)',
  'linear-gradient(135deg, #f43f5e, #fb7185)'
];

function getStudentAvatarBg(name) {
  let hash = 0;
  for (let i = 0; i < (name || '').length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return STUDENT_AVATAR_GRADIENTS[Math.abs(hash) % STUDENT_AVATAR_GRADIENTS.length];
}

function renderStudentRoster(students) {
  const container = document.getElementById('student-roster');
  if (!container) return;
  if (!Array.isArray(students) || students.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding:32px; color:var(--text-muted); background:var(--bg-card); border:1px solid var(--border); border-radius:12px;">${t('admin.no_students') || 'No students enrolled yet.'}</div>`;
    return;
  }

  container.innerHTML = students.map(s => {
    const pct = Math.round((s.avg_mastery || 0) * 100);
    const schoolNum = s.email && s.email.includes('@student.aulaai') ? s.email.split('@')[0] : '';
    const isPermanent = Boolean(s.is_permanent || PERMANENT_STUDENT_NUMBERS.includes(schoolNum) || PERMANENT_STUDENT_NUMBERS.includes(String(s.id || '').replace('student-', '')));
    const kickBtn = !isPermanent
      ? `<button class="student-btn-kick" onclick="event.stopPropagation(); deleteStudent('${s.id}',${escJS(s.name).replace(/'/g, "\\'")})" title="${t('Kick')}"><span data-i18n="Kick">${t('Kick')}</span></button>`
      : '';
    const avatarBg = getStudentAvatarBg(s.name);
    const initials = getStudentInitials(s.name);
    const color = masteryColor(s.avg_mastery || 0);

    // Real-time Online Status Logic
    let isOnline = false;
    if (s.is_active !== undefined) {
      isOnline = Boolean(s.is_active);
    } else if (s.last_seen) {
      const lastSeen = new Date(s.last_seen.replace(' ', 'T') + 'Z').getTime();
      const now = new Date().getTime();
      if (now - lastSeen < 12 * 1000) isOnline = true;
    }

    const statusBadge = isOnline
      ? `<span class="student-status-indicator" style="background:rgba(34,197,94,0.12); color:#22c55e; border:1px solid rgba(34,197,94,0.25); display:inline-flex; align-items:center; gap:4px;"><span style="width:5px; height:5px; border-radius:50%; background:#22c55e; box-shadow:0 0 6px #22c55e; display:inline-block;"></span>${t('admin.active')}</span>`
      : `<span class="student-status-indicator" style="background:rgba(156,163,175,0.1); color:#9ca3af; border:1px solid rgba(156,163,175,0.2);">${t('admin.inactive')}</span>`;

    return `<div class="student-card" onclick="showStudentDetail('${s.id}',${escJS(s.name)}, '${schoolNum}', ${isPermanent})">
      <!-- Top Row: Avatar + Name & ID -->
      <div class="student-card-header">
        <div class="student-avatar" style="background: ${avatarBg};">
          ${initials}
        </div>
        <div class="student-info-block">
          <div class="student-name-title" title="${esc(s.name)}">${esc(s.name)}</div>
          <div class="student-id-row">
            ${schoolNum ? `<span class="student-school-num">#${esc(schoolNum)}</span>` : ''}
            ${statusBadge}
          </div>
        </div>
      </div>

      <!-- Middle: Mastery Progress & Metrics -->
      <div class="student-metrics-box">
        <div class="student-metrics-header">
          <span class="metric-badge">
            <span class="metric-indicator" style="background: ${color};"></span>
            <span data-i18n="Mastery:">${t('Mastery:')}</span> <strong style="color: var(--text-primary); margin-left: 2px;">${pct}%</strong>
          </span>
          <span class="metric-count">
            <strong>${s.total_responses || 0}</strong> <span data-i18n="responses">${t('responses')}</span>
          </span>
        </div>
        <div class="student-mastery-bar">
          <div class="student-mastery-fill" style="width:${pct}%; background:${color}"></div>
        </div>
      </div>

      <!-- Bottom: Action Buttons -->
      <div class="student-card-actions">
        <button class="student-btn-action student-btn-pw" onclick="event.stopPropagation(); lecturerSetStudentPassword('${s.id}', ${escJS(s.name).replace(/'/g, "\\'")})" title="${t('admin.set_password')}">
          ${SVG_KEY} <span data-i18n="admin.set_password">${t('admin.set_password')}</span>
        </button>
        <button class="student-btn-action student-btn-msg" onclick="event.stopPropagation(); openChatFromRoster('${s.id}',${escJS(s.name).replace(/'/g, "\\'")})" title="${t('messageStudent')}">
          ${SVG_CHAT} <span data-i18n="messageStudent">${t('messageStudent')}</span>
        </button>
        ${kickBtn}
      </div>
    </div>`;
  }).join('');
  applyTranslations();
}
window.renderStudentRoster = renderStudentRoster;

window.openChatFromRoster = async (studentId, studentName) => {
  const tabBtn = document.querySelector('button[data-tab="inbox"]');
  if (tabBtn) switchTab(tabBtn, true);
  await openChat(studentId, studentName);
};

window.approveStudent = async (id) => {
  await api('/students/approve', { method: 'POST', body: { student_id: id, course_id: courseId } });
  loadStudentRoster();
};

window.lecturerSetStudentPassword = async function(sid, name) {
  const newPassword = await showConfirmModal(
    'admin.set_password',
    'admin.enter_new_password_for',
    false,
    '••••••••',
    false,
    'ok',
    'cancel',
    { name }
  );
  if (newPassword && newPassword.trim()) {
    try {
      const res = await api('/admin/set-student-password', {
        method: 'POST',
        body: { student_id: sid, password: newPassword.trim() }
      });
      if (res && res.success) {
        await showAlert('success', 'admin.password_set_success', false);
      } else {
        await showAlert(t('error'), res.error || 'Failed to update password', true);
      }
    } catch (err) {
      await showAlert(t('error'), err.message || 'Error updating password', true);
    }
  }
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
  const isPerm = PERMANENT_STUDENT_NUMBERS.includes(String(sid || '').replace('student-', ''));
  if (isPerm) {
    showAlert('cancel', 'Permanent students cannot be removed.', true);
    return;
  }
  const confirmed = await showConfirmModal('confirm.kick_student_title', 'confirm.kick_student_msg', true, null, false, 'ok', 'cancel', { name });
  if (confirmed) {
    const res = await api('/student/delete', { method: 'POST', body: { student_id: sid, course_id: courseId } });
    if (res && res.error) {
      showAlert('cancel', res.error, true);
    } else {
      loadStudentRoster();
    }
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

async function showStudentDetail(sid, name, studentId = '', isPermanent = false) {
  const isPerm = Boolean(isPermanent || PERMANENT_STUDENT_NUMBERS.includes(studentId) || PERMANENT_STUDENT_NUMBERS.includes(String(sid || '').replace('student-', '')));
  const kickBtn = !isPerm
    ? `<button class="btn btn-sm" style="background:var(--danger-bg); color:var(--danger); border:1px solid var(--danger)" onclick="deleteStudent('${sid}',${escJS(name).replace(/'/g, "\\'")})">${SVG_BAN} <span data-i18n="Kick">${t('Kick')}</span></button>`
    : '';

  const data = await api('/student/progress?student_id=' + sid);
  const modal = document.getElementById('student-detail-modal');
  modal.classList.remove('hidden');

  const idHtml = studentId ? `<span style="font-size:16px; color:var(--text-muted); margin-left:12px; font-weight:normal">#${studentId}</span>` : '';

  document.getElementById('student-detail-body').innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:24px">
      <h2 style="margin:0">${name}${idHtml}</h2>
      <div style="display:flex; gap:8px">
        <button class="btn btn-primary btn-sm" onclick="openChatFromRoster('${sid}',${escJS(name).replace(/'/g, "\\'")})">${SVG_CHAT} <span data-i18n="messageStudent">${t('messageStudent')}</span></button>
        ${kickBtn}
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
          <h3 style="margin:0 0 12px; font-size:18px; font-weight:700; display:flex; align-items:center; gap:10px;">${lang === 'tr' ? 'Yönetici Özeti' : 'Executive Summary'}</h3>
          <div style="font-size:14.5px; line-height:1.7; color:var(--text-secondary);">${data.summary}</div>
        </div>

        <div style="margin-bottom:32px;">
          <h3 style="margin:0 0 16px; font-size:18px; font-weight:700; display:flex; align-items:center; gap:10px;">${lang === 'tr' ? 'Hatalı Konular ve Analiz' : 'Flawed Topics & Analysis'}</h3>
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
          <h3 style="margin:0 0 16px; font-size:18px; font-weight:700; display:flex; align-items:center; gap:10px;">${lang === 'tr' ? 'Öğrenci Spotlight' : 'Student Spotlights'}</h3>
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
          <h3 style="margin:0 0 10px; font-size:18px; font-weight:700;">${lang === 'tr' ? 'Genel Tavsiye' : 'General Advice'}</h3>
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
      <div class="stat-card"><div class="stat-label" data-i18n="overallMastery">${t('overallMastery')}</div><div class="stat-value ${masteryClass(avg)}">${Math.round(avg * 100)}%</div></div>
      <div class="stat-card"><div class="stat-label" data-i18n="strongTopics">${t('strongTopics')}</div><div class="stat-value success">${strong}</div></div>
      <div class="stat-card"><div class="stat-label" data-i18n="needsWork">${t('needsWork')}</div><div class="stat-value ${weak > 0 ? 'danger' : 'success'}">${weak}</div></div>
      <div class="stat-card"><div class="stat-label" data-i18n="topicsStudied">${t('topicsStudied')}</div><div class="stat-value accent">${masteries.length}</div></div>`;
  }

  const chapterEl = document.getElementById('student-current-chapter');
  if (chapterEl) {
    if (curriculum && curriculum.length > 0) {
      let targetChapter = null;
      const lastTopicId = (courseId ? localStorage.getItem('aula_last_topic_' + courseId) : null) || localStorage.getItem('aula_last_topic');
      if (lastTopicId) {
        targetChapter = curriculum.find(ch => (ch.topics || []).some(t => t.id === lastTopicId));
      }
      if (!targetChapter && masteries && masteries.length > 0) {
        for (let i = masteries.length - 1; i >= 0; i--) {
          const mid = masteries[i].topic_id;
          const found = curriculum.find(ch => (ch.topics || []).some(t => t.id === mid));
          if (found) { targetChapter = found; break; }
        }
      }
      const chCurrent = targetChapter || curriculum[0];
      const chTitle = getLocalizedCurriculumTitle(chCurrent, currentLang);
      chapterEl.innerHTML = `<h4 style="margin-bottom:12px"><span data-i18n="currentChapter">${t('currentChapter')}</span>: ${esc(chTitle)}</h4>${(chCurrent.topics || []).map(tp => {
        const tpTitle = getLocalizedCurriculumTitle(tp, currentLang);
        return `<div class="topic-item" style="cursor:pointer" onclick="startStudyFirst('${tp.id}')"><div class="topic-info"><span class="topic-type-badge ${tp.type}">${translateBadge(tp.type)}</span><span class="topic-name">${esc(tpTitle)}</span></div></div>`;
      }).join('')}`;
    } else {
      chapterEl.innerHTML = '';
    }
  }
}

function loadStudentPractice() {
  const practiceEl = document.getElementById('practice-topics');
  if (!practiceEl) return;
  if (!curriculum || !Array.isArray(curriculum)) {
    practiceEl.innerHTML = '';
    return;
  }
  practiceEl.innerHTML = curriculum.map((ch, idx) => (ch.topics || []).map(tp => {
    const tpTitle = getLocalizedCurriculumTitle(tp, currentLang);
    const unitNum = ch.number || (idx + 1);
    return `<div class="topic-practice-card" onclick="startStudyFirst('${tp.id}')">
      <div style="display:flex; justify-content:space-between; align-items:flex-start">
        <div class="topic-type-badge ${tp.type}" style="margin-bottom:8px">${translateBadge(tp.type)}</div>
      </div>
      <div style="font-weight:600;margin-bottom:4px">${esc(tpTitle)}</div>
      <div style="font-size:13px;color:var(--text-muted)"><span data-i18n="Unit">${t('Unit')}</span> ${unitNum} · ${translateDifficulty(tp.difficulty)}</div>
    </div>`;
  }).join('')).join('');
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
  clearActivityAnsweredState();
  const isLecturer = currentUser && currentUser.role === 'lecturer';
  const targetId = isLecturer ? 'activity-preview' : 'practice-area';
  const topicsGrid = isLecturer ? null : document.getElementById('practice-topics');
  const area = document.getElementById(targetId);

  if (isLecturer) {
    const actSelect = document.getElementById('activity-topic-select');
    if (actSelect) actSelect.value = tid;
  }

  if (topicsGrid) topicsGrid.classList.add('hidden');
  if (area) {
    area.innerHTML = '';
    area.classList.remove('hidden');
    area.style.display = 'block';
    showGenerationLoading(area);
  }

  try {
    if (_lastActivityData && Array.isArray(_lastActivityData.activities)) {
      registerSeenQuestions(tid, _lastActivityData.activities);
    }
    const existingQuestions = getSeenQuestions(tid);

    // 1. Kick off the background task
    const res = await api('/activity/start', {
      method: 'POST',
      body: { 
        topic_id: tid, 
        course_id: courseId, 
        count: 10, 
        ui_lang: currentLang,
        user_id: currentUser ? currentUser.id : null,
        existing_questions: existingQuestions
      }
    });
    if (res && res.error) throw new Error(res.error);

    // 2. Start polling
    startActivityPolling(targetId, `${t('practice')}: ${title}`, res ? res.task_id : null, tid);
  } catch (err) {
    console.error("Practice Start Error:", err);
    if (area) {
      area.innerHTML = `<div style="padding:40px; color:var(--danger); text-align:center; background:var(--bg-card); border-radius:16px; border:1px solid var(--border);">
          <div style="font-size:48px; margin-bottom:16px;">⚠️</div>
          <h3 style="margin-bottom:8px;">${t('assign.retry')}</h3>
          <p style="color:var(--text-muted); margin-bottom:24px;">${err.message || 'Generation failed'}</p>
          <button class="btn btn-primary" onclick="cancelPractice()">${currentLang === 'tr' ? 'Konulara Geri Dön' : 'Back to Topics'}</button>
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
    return `<div class="progress-item"><div class="progress-label"><span>${translateCurriculumTitle(m.title)} <span class="topic-type-badge ${m.type}" style="margin-left:8px">${translateBadge(m.type)}</span></span><span>${pct}%</span></div><div class="progress-bar"><div class="progress-fill" style="width:${pct}%;background:${masteryColor(m.score)}"></div></div></div>`;
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
  const isLecturer = currentUser && currentUser.role === 'lecturer';
  const container = isLecturer
    ? document.getElementById('assignment-list')
    : document.getElementById('student-assignment-list');
  if (!container) return;

  if (!assignments || assignments.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted);padding:20px;text-align:center" data-i18n="noAssignments">${t('noAssignments')}</p>`;
    return;
  }

  if (isLecturer) {
    container.innerHTML = assignments.map(a => {
      const displayTitle = esc(translateQuizTitle(a.title, currentLang));
      const createdLabel = t('Created');
      const formattedDate = new Date(a.created_at).toLocaleDateString(currentLang === 'tr' ? 'tr-TR' : 'en-US');
      return `
      <div class="card" style="margin-bottom:12px">
        <div class="card-body flex-between">
          <div style="flex:1;cursor:pointer" onclick="viewAssignment('${a.id}',${escJS(a.title)})">
            <strong class="assignment-item-title" data-raw-title="${esc(a.title)}" style="font-size:15px">${displayTitle}</strong>
            <div style="font-size:13px;color:var(--text-muted);margin-top:4px">
              <span data-i18n="Created">${createdLabel}</span>: <span class="assignment-item-date" data-created-at="${a.created_at}">${formattedDate}</span>
            </div>
          </div>
          <div style="display:flex;gap:8px;align-items:center;margin-left:12px">
            <button class="btn btn-outline btn-sm" onclick="viewAssignment('${a.id}',${escJS(a.title)})">${SVG_EYE} <span data-i18n="viewBtn">${t('viewBtn')}</span></button>
            <button class="btn btn-sm" style="background:var(--danger-bg,#fde8e8);color:var(--danger);border:1px solid var(--danger)" onclick="deleteAssignment('${a.id}',${escJS(a.title)})">${SVG_TRASH} <span data-i18n="confirm.delete_assignment">${t('confirm.delete_assignment')}</span></button>
          </div>
        </div>
      </div>`;
    }).join('');
  } else {
    container.innerHTML = assignments.map(a => {
      const done = a.is_completed;
      const displayTitle = esc(translateQuizTitle(a.title, currentLang));
      const createdLabel = t('Created');
      const formattedDate = new Date(a.created_at).toLocaleDateString(currentLang === 'tr' ? 'tr-TR' : 'en-US');
      return `
        <div class="card" style="margin-bottom:12px;cursor:${done ? 'default' : 'pointer'};opacity:${done ? '0.6' : '1'}" onclick="${done ? '' : `takeAssignment('${a.id}')`}">
          <div class="card-body flex-between">
            <div>
              <strong class="assignment-item-title" data-raw-title="${esc(a.title)}" style="font-size:15px">${displayTitle}</strong>
              <div style="font-size:13px;color:var(--text-muted);margin-top:4px">
                <span data-i18n="Created">${createdLabel}</span>: <span class="assignment-item-date" data-created-at="${a.created_at}">${formattedDate}</span> ${done ? ` · <span style="color:var(--success)">${SVG_CHECK} <span data-i18n="completed">${t('completed')}</span></span>` : ''}
              </div>
            </div>
            <span class="btn btn-sm ${done ? 'btn-ghost' : 'btn-outline'}">${done ? `<span data-i18n="completed">${t('completed')}</span>` : `<span data-i18n="takeQuizBtn">${t('takeQuizBtn')}</span>`}</span>
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
  window._currentViewingAssignment = { id: assignmentId, title: title };
  window._currentViewingQuiz = null;
  const modal = document.getElementById('student-detail-modal');
  modal.classList.remove('hidden');
  document.getElementById('student-detail-body').innerHTML = `<div style="text-align:center;padding:48px 20px;color:var(--text-muted);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;"><div class="spinner-small"></div><span style="font-size:14px;">${t('loading') || (currentLang === 'tr' ? 'Yükleniyor...' : 'Loading...')}</span></div>`;

  const [assignData, respData] = await Promise.all([
    api('/assignment/take?assignment_id=' + assignmentId),
    api('/assignment/responses?assignment_id=' + assignmentId)
  ]);
  const isTr = currentLang === 'tr';
  const displayTitle = translateQuizTitle(title, currentLang);
  const results = (respData && respData.student_results) || [];
  const qs = (assignData && assignData.questions) || [];

  // Class average and status split
  const completedList = results.filter(sr => sr.status === 'completed' || (!sr.has_unsubmitted && !sr.answers.some(a => a.student_answer === '[STARTED]')));
  const inProgressList = results.filter(sr => sr.status === 'in_progress' || sr.has_unsubmitted || sr.answers.some(a => a.student_answer === '[STARTED]'));
  const classAvg = (respData && typeof respData.average_score === 'number') ? Math.round(respData.average_score * 100) : (
    completedList.length
      ? Math.round(completedList.reduce((s, r) => s + (r.average_score || 0), 0) / completedList.length * 100)
      : 0
  );

  const L = {
    noResponses: t('assign.no_responses') || (isTr ? 'Henüz yanıt gönderilmedi.' : 'No responses submitted yet.'),
    submitted: t('assign.submitted') || (isTr ? 'gönderildi' : 'submitted'),
    classAvg: t('assign.class_avg') || (isTr ? 'Sınıf Ortalaması' : 'Class Average'),
    correct: t('assign.correct') || (isTr ? 'Doğru' : 'Correct'),
    studentAnswer: t('assign.student_answer') || (isTr ? 'Öğrenci Yanıtı' : 'Student Answer'),
    correctAnswer: t('assign.correct_answer') || (isTr ? 'Doğru Cevap' : 'Correct Answer'),
    expand: t('assign.view_details') || (isTr ? 'Detayları Gör' : 'View Details'),
    questionsTab: isTr ? 'Sorular' : 'Questions',
    responsesTab: isTr ? 'Yanıtlar' : 'Responses'
  };

  document.getElementById('student-detail-body').innerHTML = `
    <h2 style="margin-bottom:4px">${displayTitle}</h2>
    <div style="color:var(--text-muted);font-size:14px;margin-bottom:20px">
      <span>${L.classAvg}</span>: <strong style="color:var(--accent)">${classAvg}%</strong> · 
      ${completedList.length} <span>${L.submitted}</span>${inProgressList.length > 0 ? ` · <span style="color:#f59e0b;font-weight:600">${inProgressList.length} ${isTr ? 'devam ediyor' : 'in progress'}</span>` : ''}
    </div>

    <div style="display:flex;gap:8px;margin-bottom:20px;border-bottom:1px solid var(--border)">
      <button class="nav-tab active" onclick="switchQuizViewTab(this,'av-questions')" style="flex:1;padding:10px"><span>${L.questionsTab}</span> (${qs.length})</button>
      <button class="nav-tab" onclick="switchQuizViewTab(this,'av-responses')" style="flex:1;padding:10px"><span>${L.responsesTab}</span> (${results.length})</button>
    </div>

    <div id="av-questions">
      <div style="display:flex;flex-direction:column;gap:12px">
        ${qs.map((q, i) => `
          <div style="padding:16px;border:1px solid var(--border);border-radius:8px;background:var(--bg-card)">
            <div style="font-size:12px;font-weight:600;color:var(--text-muted);margin-bottom:8px;text-transform:uppercase">
              ${isTr ? 'Soru' : 'Question'} ${i + 1} • ${translateOption(q.type === 'mcq' ? (isTr ? 'Çoktan Seçmeli' : 'Multiple Choice') : (isTr ? 'Boşluk Doldurma' : 'Fill in the Blank'))}
            </div>
            <div style="font-size:15px;margin-bottom:12px">${translatePrompt(q.prompt)}</div>
            ${q.type === 'mcq' ? `
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                ${(q.distractors || []).concat([q.answer]).map(o => `
                  <div style="padding:8px 12px;background:var(--bg-input);border-radius:4px;font-size:13px;border:1px solid ${o === q.answer ? 'var(--success)' : 'var(--border)'};color:${o === q.answer ? 'var(--success)' : 'inherit'};font-weight:${o === q.answer ? '600' : 'normal'}">
                    ${o === q.answer ? SVG_CHECK + ' ' : ''}${fixDiacritics(safeStr(o))}
                  </div>
                `).join('')}
              </div>
            ` : `
              <div style="padding:8px 12px;background:var(--bg-input);border-radius:4px;font-size:13px;border:1px solid var(--success);color:var(--success);font-weight:600;display:inline-block">
                ${SVG_CHECK} ${q.answer}
              </div>
            `}
          </div>
        `).join('')}
      </div>
    </div>

    <div id="av-responses" style="display:none">
      ${results.length > 0 ? `
      <!-- Summary bar -->
      <div style="display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap">
        <div style="flex:1;min-width:100px;background:var(--bg-input);border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:11px;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin-bottom:4px">${L.submitted}</div>
          <div style="font-size:26px;font-weight:700">${completedList.length}</div>
        </div>
        <div style="flex:1;min-width:100px;background:var(--bg-input);border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:11px;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin-bottom:4px">${t('CLASS MASTERY') || (isTr ? 'Sınıf Başarısı' : 'Class Mastery')}</div>
          <div style="font-size:26px;font-weight:700;color:${masteryColor(classAvg / 100)}">${classAvg}%</div>
        </div>
        <div style="flex:1;min-width:100px;background:var(--bg-input);border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center">
          <div style="font-size:11px;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin-bottom:4px">${t('assign.top_score') || (isTr ? 'En Yüksek Skor' : 'Top Score')}</div>
          <div style="font-size:26px;font-weight:700;color:var(--success)">${completedList.length > 0 ? Math.round(completedList[0].average_score * 100) + '%' : '—'}</div>
        </div>
      </div>

      <!-- Score bar chart -->
      <div style="margin-bottom:24px">
        ${results.map((sr, i) => {
          const isInProgress = (sr.status === 'in_progress' || sr.has_unsubmitted || sr.answers.some(a => a.student_answer === '[STARTED]'));
          const pct = Math.round(sr.average_score * 100);
          const answeredCount = sr.answered_count || sr.answers.filter(a => a.student_answer !== '[STARTED]').length;
          const correctCount = sr.answers.filter(a => a.is_correct && a.student_answer !== '[STARTED]').length;
          const totalQ = sr.total_questions || qs.length || sr.answers.length;
          return `
          <div style="margin-bottom:6px">
            <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:3px">
              <span style="font-weight:500">
                ${i < 3 && !isInProgress ? `<span class="rank-badge rank-${i+1}">#${i+1}</span> ` : ''}
                ${esc(sr.student_name)}
                ${isInProgress ? `<span style="font-size:12px; background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.4); padding:2px 8px; border-radius:12px; margin-left:8px; font-weight:600">${isTr ? 'Ödev Devam Ediyor' : 'In Progress'}</span>` : ''}
              </span>
              ${isInProgress ? `
                <span style="color:#f59e0b;font-weight:600">—
                  <span style="color:var(--text-muted);font-weight:400">(${answeredCount}/${totalQ} ${isTr ? 'yanıtlandı' : 'answered'})</span>
                </span>
              ` : `
                <span style="color:${masteryColor(sr.average_score)};font-weight:700">${pct}%
                  <span style="color:var(--text-muted);font-weight:400">(${correctCount}/${totalQ} <span>${L.correct.toLowerCase()}</span>)</span>
                </span>
              `}
            </div>
            <div style="background:var(--border);border-radius:4px;height:8px;cursor:pointer" onclick="this.parentElement.nextElementSibling.style.display=this.parentElement.nextElementSibling.style.display==='none'?'block':'none'">
              <div style="background:${isInProgress ? '#f59e0b' : masteryColor(sr.average_score)};height:8px;border-radius:4px;width:${isInProgress ? Math.round((answeredCount/totalQ)*100) : pct}%;transition:width 0.6s ease"></div>
            </div>
          </div>
          <!-- Expandable detail -->
          <div style="display:none;margin-bottom:16px;border:1px solid var(--border);border-radius:8px;overflow:hidden">
            <div style="padding:12px 14px;background:var(--bg-secondary);font-size:12px;font-weight:600;text-transform:uppercase;color:var(--text-muted);letter-spacing:0.5px">
              ${esc(sr.student_name)} — <span>${t('assign.detailed_answers') || (isTr ? 'Ayrıntılı Cevaplar' : 'Detailed Answers')}</span>
            </div>
            ${sr.answers.map((a, qi) => {
              const isStarted = (a.student_answer === '[STARTED]');
              const isRight = a.is_correct && !isStarted;
              return `
              <div style="padding:10px 14px;border-bottom:1px solid var(--border);display:flex;gap:10px;align-items:flex-start;background:var(--bg-card)">
                <span style="min-width:22px;font-size:15px;font-weight:700;color:${isStarted ? 'var(--text-muted)' : (isRight ? 'var(--success)' : 'var(--danger)')};margin-top:1px">${isStarted ? '⏳' : (isRight ? SVG_CHECK : SVG_CROSS)}</span>
                <div style="flex:1;font-size:13px">
                  <div style="margin-bottom:5px;font-weight:500;line-height:1.4">${translatePrompt(a.prompt)}</div>
                  <div style="display:flex;gap:16px;flex-wrap:wrap">
                    ${isStarted
                      ? `<span style="color:var(--text-muted);font-style:italic;">${isTr ? 'Henüz yanıtlanmadı (Ödev devam ediyor)' : 'Not answered yet (In progress)'}</span>`
                      : `<span><span>${L.studentAnswer}</span>: <strong style="color:${isRight ? 'var(--success)' : 'var(--danger)'}">${esc(a.student_answer)}</strong></span>
                         ${!isRight ? `<span><span>${L.correctAnswer}: <strong style="color:var(--success)">${esc(a.correct_answer)}</strong></span>` : ''}`
                    }
                  </div>
                </div>
                <span style="font-size:12px;color:${isStarted ? 'var(--text-muted)' : (isRight ? 'var(--success)' : 'var(--danger)')};font-weight:600;white-space:nowrap">${isStarted ? '—' : Math.round(a.score * 100) + '%'}</span>
              </div>
            `;}).join('')}
          </div>`;
        }).join('')}
      </div>` : `<p style="color:var(--text-muted);padding:20px;text-align:center">${L.noResponses}</p>`}
    </div>
  `;
  applyTranslations(document.getElementById('student-detail-body'));
}

async function previewAssignment(aid, title) {
  return viewAssignment(aid, title);
}

async function previewQuiz(qid, title) {
  return viewQuiz(qid, title);
}

async function createAssignment() {
  const btn = event.target;
  const originalText = btn.textContent;
  btn.textContent = currentLang === 'tr' ? 'Oluşturuluyor...' : 'Generating...';
  btn.disabled = true;
  btn.setAttribute('data-generating', 'true');

  const title = document.getElementById('assignment-title').value || 'Assignment';
  const chapterId = document.getElementById('assignment-chapter-select').value || null;
  const count = parseInt(document.getElementById('assignment-count').value) || 10;

  const targetCourseId = courseId || (currentCourse && currentCourse.id) || localStorage.getItem('aula_last_course');

  if (currentDraft && Array.isArray(currentDraft.questions)) {
    registerDraftSeenQuestions(targetCourseId, currentDraft.questions);
  }
  const existingQuestions = getDraftSeenQuestions(targetCourseId);

  try {
    const res = await api('/draft/generate', { 
      method: 'POST', 
      body: { 
        course_id: targetCourseId, 
        chapter_id: chapterId, 
        count, 
        ui_lang: currentLang,
        existing_questions: existingQuestions
      } 
    });
    if (res.error) throw new Error(res.error);

    startDraftPolling('assignment', btn, originalText, (questions) => {
      registerDraftSeenQuestions(targetCourseId, questions);
      currentDraft = {
        type: 'assignment',
        title: title,
        course_id: targetCourseId,
        chapter_id: chapterId,
        due_at: null,
        questions: questions
      };
      openDraftModal();
    }, targetCourseId);
  } catch (err) {
    btn.textContent = originalText;
    btn.disabled = false;
    btn.removeAttribute('data-generating');
    showAlert(t('error'), err.message, true);
  }
}

function openDraftModal() {
  const modal = document.getElementById('draft-modal');
  modal.classList.remove('hidden');
  renderDraftList();
}

function closeDraftModal() {
  if (currentDraft && Array.isArray(currentDraft.questions)) {
    const cid = currentDraft.course_id || courseId || (currentCourse && currentCourse.id);
    registerDraftSeenQuestions(cid, currentDraft.questions);
  }
  document.getElementById('draft-modal').classList.add('hidden');
  currentDraft = null;
}

function renderDraftList() {
  const container = document.getElementById('draft-body');

  let html = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
      <h2 style="margin:0"><span data-i18n="draft.review">${t('draft.review')}</span> - ${esc(currentDraft.title)}</h2>
      <div>
        <button class="btn btn-outline btn-sm" onclick="showAddCustomQuestionForm()">${SVG_PLUS} <span data-i18n="draft.add_question">${t('draft.add_question')}</span></button>
        <button class="btn btn-primary btn-sm" onclick="publishDraft()"><span data-i18n="draft.publish">${t('draft.publish')}</span></button>
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
        <button class="btn btn-ghost btn-sm" style="position:absolute; top:8px; right:8px; color:var(--danger);" onclick="removeDraftQuestion(${i})">${SVG_TRASH} <span data-i18n="draft.remove">${t('draft.remove')}</span></button>
        <div class="card-body">
          <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">${i + 1}. ${typeLabel}</div>
          <div style="font-weight:600; margin-bottom:8px;">${esc(formattedPrompt)}</div>
          <div style="color:var(--success); font-size:14px; margin-bottom:4px;">${SVG_CHECK} ${esc(formattedAnswer)}</div>
          ${q.type === 'mcq' && q.distractors && q.distractors.length > 0 ? q.distractors.map(d => `<div style="color:var(--danger); font-size:13px;">${SVG_CROSS} ${esc(d)}</div>`).join('') : ''}
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

  // Pre-shuffle options ONCE so language switching never changes assignment option positions
  if (Array.isArray(data.questions)) {
    data.questions.forEach(q => {
      if (q.type === 'mcq' && !q._shuffledOptions) {
        const rawOpts = (Array.isArray(q.options) && q.options.length > 1) ? q.options : (q.distractors || []).concat([q.answer]);
        q._shuffledOptions = rawOpts.slice().sort(() => Math.random() - 0.5);
      }
    });
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
    const options = q._shuffledOptions || (Array.isArray(q.options) && q.options.length > 1 ? q.options : (q.distractors || []).concat([q.answer]));
    answerHTML = `<div class="options-grid" style="margin-top:16px">
      ${options.map(o => `<button class="option-btn" onclick="assignmentAnswer(${escJS(o)})"
        style="text-align:left;padding:14px 18px;font-size:14px">${fixDiacritics(safeStr(o))}</button>`).join('')}
    </div>`;
  } else {
    answerHTML = `<div style="margin-top:16px;display:flex;gap:10px;align-items:center">
      <input id="as-inp" class="fill-blank-input" placeholder="${t('assign.type_answer')}"
        style="flex:1;font-size:15px" onkeydown="if(event.key==='Enter')assignmentAnswer(this.value)">
      <button class="btn btn-primary" onclick="assignmentAnswer(document.getElementById('as-inp').value)" data-i18n="submit">
        ${t('submit')} →
      </button>
    </div>
    ${q.hint ? `<div style="margin-top:8px;font-size:13px;color:var(--text-muted)"><span style="font-weight:600;color:var(--accent);">Hint:</span> ${q.hint}</div>` : ''}`;
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
        <div style="margin-bottom:16px">${pct >= 70 ? SVG_CHECK : SVG_BOOK}</div>
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
  toc.innerHTML = curriculum.map((ch, i) => {
    const chTitle = getLocalizedCurriculumTitle(ch, currentLang);
    return `
    <div class="study-ch-group" style="margin-bottom:16px;">
      <div style="font-size:11px; font-weight:800; color:var(--accent); text-transform:uppercase; letter-spacing:1px; margin-bottom:8px; opacity:0.7;"><span data-i18n="Unit">${t('Unit')}</span> ${ch.number || (i + 1)}: ${esc(chTitle)}</div>
      <div style="display:flex; flex-direction:column; gap:4px;">
        ${(ch.topics || []).map(topicObj => {
          const tTitle = getLocalizedCurriculumTitle(topicObj, currentLang);
          return `
          <button class="btn btn-ghost study-topic-btn" data-topic-id="${topicObj.id}" onclick="showStudyTopic('${topicObj.id}')" title="${esc(tTitle)}" style="justify-content:flex-start; text-align:left; font-size:13px; padding:10px 14px; border-radius:var(--radius-sm); line-height:1.3; height:auto; transition:0.2s ease;">
            ${esc(tTitle)}
          </button>
        `;}).join('')}
      </div>
    </div>
  `;}).join('');
}

function highlightPedagogicalTerms(text) {
  if (!text || typeof text !== 'string') return '';
  // Match single quotes only when they are genuine pedagogical token quotes (not Turkish apostrophes / kesme işareti like İspanyolca'da)
  // Must be preceded by start of line or non-letter/non-digit, and followed by non-letter/non-digit or end of line
  let res = text.replace(/(?<=^|[^\p{L}\p{N}])'([^\s'][^'\n\r]*?)'(?=[^\p{L}\p{N}]|$)/gu, '<code class="study-term-chip">$1</code>');
  res = res.replace(/(?<!<[^>]*)\(([^)\n\r]{1,70})\)(?![^<]*>)/g, (m, inner) => {
    if (inner.includes('<')) return m;
    return `<span class="study-term-paren">(<span class="study-term-highlight">${inner}</span>)</span>`;
  });
  return res;
}

const CEFR_LEVEL_METAS = {
  'A1': {
    name: 'A1 · Breakthrough',
    name_tr: 'A1 · Başlangıç',
    focus: 'Foundations, Phonetics & Immediate Survival Chunks',
    focus_tr: 'Temel Bilgiler, Fonetik ve Günlük Hayatta Kalma Kalıpları',
    color: '#10b981'
  },
  'A2': {
    name: 'A2 · Waystage',
    name_tr: 'A2 · Temel Seviye',
    focus: 'Routine Exchanges, Timeframes & Everyday Collocations',
    focus_tr: 'Rutin İletişim, Zaman Kipleri ve Günlük Kalıplar',
    color: '#06b6d4'
  },
  'B1': {
    name: 'B1 · Threshold',
    name_tr: 'B1 · Orta Seviye',
    focus: 'Independence, Aspectual Contrast & Connective Discourse',
    focus_tr: 'Bağımsız İfade, Görünüş Karşıtlıkları ve Bağlaçlar',
    color: '#3b82f6'
  },
  'B2': {
    name: 'B2 · Vantage',
    name_tr: 'B2 · İleri-Orta Seviye',
    focus: 'Fluency, Subjunctive Nuances & Register Flexibility',
    focus_tr: 'Akıcılık, Dilek-Şart Nüansları ve Üslup Esnekliği',
    color: '#6366f1'
  },
  'C1': {
    name: 'C1 · Effective Proficiency',
    name_tr: 'C1 · İleri Seviye',
    focus: 'Implicit Meaning, Pragmatic Nuance & Stylistic Elevation',
    focus_tr: 'Örtük Anlam, Edimbilimsel Nüans ve Üslup Yükseltimi',
    color: '#8b5cf6'
  },
  'C2': {
    name: 'C2 · Mastery',
    name_tr: 'C2 · Üstün Ustalık',
    focus: 'Near-Native Precision, Rhetorical Trope & Sociolinguistic Subtlety',
    focus_tr: 'Anadili Düzeyinde Kesinlik, Retorik ve Toplumbilimsel İncelik',
    color: '#f59e0b'
  }
};

function isLevelB1OrAbove(topic) {
  let lvl = '';
  if (topic && topic.difficulty) {
    lvl = String(topic.difficulty).toUpperCase();
  } else if (currentCourse && currentCourse.level) {
    lvl = String(currentCourse.level).toUpperCase();
  }
  return lvl.includes('B1') || lvl.includes('B2') || lvl.includes('C1') || lvl.includes('C2');
}

function getSpanishStudyPrompt(basePrompt, promptTr) {
  if (basePrompt) {
    let s = basePrompt.trim();
    // Common instruction replacements to natural Spanish if basePrompt was authored in English or Turkish
    s = s.replace(/^Identify the correct option:?/i, 'Identifica la opción correcta:');
    s = s.replace(/^Identify the correct answer:?/i, 'Identifica la respuesta correcta:');
    s = s.replace(/^Select the correct answer:?/i, 'Selecciona la respuesta correcta:');
    s = s.replace(/^Choose the correct answer:?/i, 'Elige la respuesta correcta:');
    s = s.replace(/^Choose the correct option:?/i, 'Selecciona la opción correcta:');
    s = s.replace(/^Fill in the blank:?/i, 'Completa el espacio en blanco:');
    s = s.replace(/^Choose the correct translation:?/i, 'Elige la traducción correcta:');
    s = s.replace(/^Which word best completes the sentence\?/i, '¿Qué palabra completa mejor la frase?');
    s = s.replace(/^Choose the grammatically correct sentence:?/i, 'Elige la frase gramaticalmente correcta:');
    s = s.replace(/^What does '(.*)' mean\?/i, "¿Qué significa '$1'?");
    s = s.replace(/^How do you say '(.*)' in Spanish\?/i, "¿Cómo se dice '$1' en español?");
    s = s.replace(/^Doğru seçeneği belirleyin:?/i, 'Identifica la opción correcta:');
    s = s.replace(/^Doğru cevabı belirleyin:?/i, 'Identifica la respuesta correcta:');
    s = s.replace(/^Doğru cevabı seçin:?/i, 'Selecciona la respuesta correcta:');
    s = s.replace(/^Doğru seçeneği seçin:?/i, 'Selecciona la opción correcta:');
    s = s.replace(/^Boşluğu doldurun:?/i, 'Completa el espacio en blanco:');
    s = s.replace(/^Cümleyi tamamlayınız:?/i, 'Completa la frase:');
    s = s.replace(/^Cümleyi tamamlayın:?/i, 'Completa la frase:');
    return s;
  }
  return 'Selecciona la opción correcta:';
}

function getEnglishStudyPrompt(basePrompt, promptTr) {
  let s = (basePrompt || '').trim();
  if (!s && promptTr) s = String(promptTr).trim();
  if (!s) return 'Identify the correct option:';

  // If already an English carrier instruction, return as is
  const enStarters = ['Choose ', 'Select ', 'Complete ', 'Which ', 'What ', 'How ', 'Why ', 'You ', 'If '];
  if (enStarters.some(w => s.startsWith(w))) {
    return s;
  }

  // Spanish instruction stem replacements to natural English
  s = s.replace(/^Completa la frase con el posesivo adecuado:?/i, 'Complete the sentence with the appropriate possessive:');
  s = s.replace(/^Completa la frase con el verbo y adjetivo correctos:?/i, 'Complete the sentence with the correct verb and adjective:');
  s = s.replace(/^Completa la frase con la forma correcta:?/i, 'Complete the sentence with the correct form:');
  s = s.replace(/^Completa la frase con la opci[oó]n correcta:?/i, 'Complete the sentence with the correct option:');
  s = s.replace(/^Completa la frase con la preposici[oó]n correcta:?/i, 'Complete the sentence with the correct preposition:');
  s = s.replace(/^Completa la frase seg[uú]n la distancia:?/i, 'Complete the sentence according to the distance:');
  s = s.replace(/^Completa la frase:?/i, 'Complete the sentence:');
  s = s.replace(/^Completa el espacio en blanco:?/i, 'Fill in the blank:');
  s = s.replace(/^Elige la opci[oó]n gramaticalmente correcta para se[nñ]alar unos zapatos cerca de la persona con la que hablas:?/i, 'Choose the grammatically correct option to point out shoes near the person you are speaking with:');
  s = s.replace(/^Elige la opci[oó]n gramaticalmente correcta:?/i, 'Choose the grammatically correct option:');
  s = s.replace(/^Elige la frase gramaticalmente correcta:?/i, 'Choose the grammatically correct sentence:');
  s = s.replace(/^Elige la respuesta correcta:?/i, 'Choose the correct answer:');
  s = s.replace(/^Selecciona la opci[oó]n correcta para completar la descripci[oó]n espacial:?/i, 'Select the correct option to complete the spatial description:');
  s = s.replace(/^Selecciona la opci[oó]n correcta:?/i, 'Select the correct option:');
  s = s.replace(/^Selecciona la respuesta correcta:?/i, 'Select the correct answer:');
  s = s.replace(/^Identifica la opci[oó]n correcta:?/i, 'Identify the correct option:');
  s = s.replace(/^Identifica la respuesta correcta:?/i, 'Identify the correct answer:');
  s = s.replace(/^Est[aá]s en clase de espa[nñ]ol y no conoces la palabra en espa[nñ]ol para ['"]?(.*?)['"]?\.?\s*¿?Qu[eé] pregunta es la correcta\??/i, "You are in Spanish class and do not know the Spanish word for '$1'. Which question is correct?");
  s = s.replace(/^Llegas a la recepci[oó]n del hotel para hacer el registro de entrada\.?\s*¿?Cu[aá]l es la frase m[aá]s adecuada y educada para comenzar\??/i, 'You arrive at the hotel reception to check in. Which is the most appropriate and polite phrase to start with?');
  s = s.replace(/^Quieres saber si hay una farmacia en los alrededores del hotel\.?\s*¿?C[oó]mo se lo preguntas al recepcionista\??/i, 'You want to know if there is a pharmacy around the hotel. How do you ask the receptionist?');
  s = s.replace(/^Si tu amigo dice:\s*[«"'](.*?)[»"'],\s*y t[uú] tampoco lo tomas con agrado,\s*¿?qu[eé] respondes\??/i, 'If your friend says: "$1", and you do not like it either, what do you reply?');
  s = s.replace(/^Si unos pantalones son demasiado peque[nñ]os para ti,\s*¿?qu[eé] le dices al dependiente\??/i, 'If a pair of trousers is too small for you, what do you say to the shop assistant?');
  s = s.replace(/^¿?Cu[aá]l de las siguientes frases es gramaticalmente CORRECTA para decir que a ti te gustan los museos\??/i, 'Which of the following sentences is grammatically CORRECT to state that you like museums?');
  s = s.replace(/^¿?Cu[aá]l de las siguientes frases es gramaticalmente CORRECTA para expresar que alguien no come carne jam[aá]s\??/i, 'Which of the following sentences is grammatically CORRECT to state that someone never eats meat?');
  s = s.replace(/^¿?Cu[aá]l de las siguientes frases es gramaticalmente CORRECTA\??/i, 'Which of the following sentences is grammatically CORRECT?');
  s = s.replace(/^¿?Cu[aá]l de las siguientes oraciones es INCORRECTA\??/i, 'Which of the following sentences is INCORRECT?');
  s = s.replace(/^¿?Cu[aá]l es la forma correcta con la contracci[oó]n obligatoria\?:?/i, 'What is the correct form with the mandatory contraction?:');
  s = s.replace(/^¿?Cu[aá]l es la forma correcta para\s*/i, 'What is the correct form for ');
  s = s.replace(/\s+con el verbo regular\s+/i, ' with the regular verb ');
  s = s.replace(/^¿?Cu[aá]l es la forma correcta para preguntar por un objeto desconocido que tienes en la mano\??/i, 'What is the correct form to ask about an unknown object you are holding in your hand?');
  s = s.replace(/^¿?Cu[aá]l es la forma plural correcta de\s*/i, 'What is the correct plural form of ');
  s = s.replace(/^¿?Cu[aá]l es la frase correcta para describir una prenda femenina plural\??/i, 'What is the correct phrase to describe a feminine plural garment?');
  s = s.replace(/^¿?C[oó]mo pides cort[eé]smente un billete para ir y volver de (.*?) en el mismo d[ií]a\??/i, 'How do you politely ask for a same-day return ticket to $1?');
  s = s.replace(/^¿?C[oó]mo se dice\s*/i, 'How do you say ');
  s = s.replace(/\s*en espa[nñ]ol de forma natural\??/i, ' in Spanish naturally?');
  s = s.replace(/^How do you say en espa[nñ]ol:\s*/i, 'How do you say in Spanish: ');
  s = s.replace(/^¿?Por qu[eé] es incorrecto decir:\s*/i, 'Why is it incorrect to say: ');
  s = s.replace(/^¿?Qu[eé] significa\s*/i, 'What does ');
  s = s.replace(/^¿?Qu[eé] expresi[oó]n se utiliza habitualmente para pedir la cuenta en un restaurante\??/i, 'Which expression is usually used to ask for the bill in a restaurant?');

  // German instruction stem replacements to natural English
  s = s.replace(/^Vervollst[aä]ndige den Satz:?/i, 'Complete the sentence:');
  s = s.replace(/^W[aä]hle die grammatikalisch richtige Option:?/i, 'Choose the grammatically correct option:');
  s = s.replace(/^W[aä]hle die richtige Option:?/i, 'Choose the correct option:');
  s = s.replace(/^W[aä]hlen Sie die richtige Option:?/i, 'Select the correct option:');
  s = s.replace(/^Welcher Satz ist grammatikalisch KORREKT\??/i, 'Which sentence is grammatically CORRECT?');
  s = s.replace(/^Welche der folgenden Aussagen ist richtig\??/i, 'Which of the following statements is correct?');

  // Turkish carrier replacements to natural English (if basePrompt was TR or promptTr was used)
  s = s.replace(/^Cümleyi tamamlayınız:?/i, 'Complete the sentence:');
  s = s.replace(/^Cümleyi tamamlayın:?/i, 'Complete the sentence:');
  s = s.replace(/^Cümleyi doğru şekilde tamamlayınız:?/i, 'Complete the sentence correctly:');
  s = s.replace(/^Cümleyi doğru fiil ve sıfat çekimiyle tamamlayınız:?/i, 'Complete the sentence with the correct verb and adjective:');
  s = s.replace(/^Aşağıdaki cümlelerden hangisi dilbilgisel olarak DOĞRUDUR\??/i, 'Which of the following sentences is grammatically CORRECT?');
  s = s.replace(/^Aşağıdaki sorulardan hangisi dilbilgisi kurallarına uygun ve doğal bir kullanımdır\??/i, 'Which of the following questions is grammatically correct and naturally phrased?');
  s = s.replace(/^Aşağıdakilerden hangisi doğrudur\??/i, 'Which of the following is correct?');
  s = s.replace(/^Boşluğu doldurun:?/i, 'Fill in the blank:');
  s = s.replace(/^Doğru seçeneği belirleyin:?/i, 'Identify the correct option:');
  s = s.replace(/^Doğru seçeneği seçin:?/i, 'Choose the correct option:');
  s = s.replace(/^Doğru cevabı seçin:?/i, 'Select the correct answer:');
  s = s.replace(/^Doğru cevabı belirleyin:?/i, 'Identify the correct answer:');
  s = s.replace(/^Diyaloğu doğru sıraya koyun:?/i, 'Reorder the dialogue correctly:');
  s = s.replace(/^Cümleyi en iyi hangi kelime tamamlar\??/i, 'Which word best completes the sentence?');
  s = s.replace(/^Aşağıdakini çevirin:?/i, 'Translate the following:');
  s = s.replace(/^Aşağıdaki cümleyi çevirin:?/i, 'Translate the following sentence:');
  s = s.replace(/^'(.*)' ifadesinin doğru çoğul hali hangisidir\??/i, "What is the correct plural form of '$1'?");
  s = s.replace(/^'(.*)' ne anlama gelir\??/i, "What does '$1' mean?");
  s = s.replace(/^İspanyolca'da '(.*)' nasıl denir\??/i, "How do you say '$1' in Spanish?");
  s = s.replace(/(.*)'da '(.*)' nasıl denir\??/i, "How do you say '$2' in $1?");

  return s;
}

function resolveStudyPrompt(p, topic) {
  if (currentLang === 'tr') {
    if (p.prompt_tr) return p.prompt_tr;
    return translatePrompt(p.prompt || p.question || "Doğru seçeneği belirleyin:", 'tr');
  }
  // English mode (default)
  if (p.prompt_en) return p.prompt_en;
  return getEnglishStudyPrompt(p.prompt || p.question || '', p.prompt_tr);
}

function showStudyTopic(topicId, pageIdx = 0, options = {}) {
  const isStudent = currentUser && currentUser.role === 'student';
  const contentId = isStudent ? 's-ai-book-content-area' : 'ai-book-content-area';
  const container = document.getElementById(contentId) || document.getElementById('ai-book-content');
  if (!container) return;

  // Save for refresh
  if (courseId) {
    localStorage.setItem('aula_last_topic_' + courseId, topicId);
  }
  localStorage.setItem('aula_last_topic', topicId);
  localStorage.setItem('aula_last_page', pageIdx);

  let topic = null;
  const currList = window.curriculum || curriculum || [];
  for (const ch of currList) {
    topic = ch.topics ? ch.topics.find(t => t.id === topicId) : null;
    if (topic) break;
  }
  if (!topic) return;

  // Save topic title for dictionary context (prevents AI contradicting lesson material)
  localStorage.setItem('aula_last_topic_title', topic.title || '');

  // Highlight active sidebar item strictly by unique topic ID
  document.querySelectorAll('.study-topic-btn').forEach(b => {
    const isActive = b.getAttribute('data-topic-id') === topicId;
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
      if (currentLang === 'tr') {
        res = healTurkishSyntax(res);
      }
      return '\u200E' + res;
    };

    if (content.pages && Array.isArray(content.pages)) {
      content.pages.forEach((p, pIdx) => {
        const isMcq = (p.type === 'mcq' || p.prompt);
        let pageTitle = "";
        if (currentLang === 'tr') {
          const rawTitle = p.title || topic.title || '';
          pageTitle = (p.title_tr && p.title_tr !== p.title) ? p.title_tr : translateCurriculumTitle(rawTitle);
          if (!pageTitle && isMcq) pageTitle = t('study.quick_check') || 'Hızlı Kontrol';
        } else {
          pageTitle = p.title ? translateCurriculumTitle(p.title) : (isMcq ? (t('study.quick_check') || 'Quick Check') : (translateCurriculumTitle(topic.title) || t('Material')));
        }
        pages.push({
          title: pageTitle,
          icon: "",
          render: () => {
            let html = "";
            
            // Communicative Scene Context (for dialogues/examples)
            const sceneContext = (currentLang === 'tr' && p.context_tr) ? p.context_tr : (p.context || p.scene || "");
            if (sceneContext && typeof sceneContext === "string" && sceneContext.trim().length > 0 && !isMcq) {
              const sceneLabel = currentLang === 'tr' ? 'İletişimsel Bağlam ve Sahne' : 'Communicative Scenario & Setting';
              html += `
                <div class="pedagogy-scene-banner">
                  <div style="font-size:10.5px; font-weight:800; text-transform:uppercase; letter-spacing:0.7px; color:var(--accent); display:flex; align-items:center; gap:6px;">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                    <span>${sceneLabel}</span>
                  </div>
                  <div style="font-size:14px; line-height:1.5; color:var(--text-secondary);">${fixDiacritics(sceneContext)}</div>
                </div>
              `;
            }

            // 1. Text/Explanation Detection
            // For MCQs, NEVER display the answer explanation beforehand; only display explicit intro or instructions if present.
            let text = "";
            if (isMcq) {
              text = (currentLang === 'tr' && p.intro_tr) ? p.intro_tr : (p.intro || p.context || p.instructions || "");
            } else {
              if (currentLang === 'tr') {
                text = p.text_tr || p.explanation_tr || p.content_tr || p.description_tr;
              } else {
                text = p.text || p.explanation || p.content || p.description || p.rule || p.intro || "";
              }
              if (!text || (typeof text === "object" && !Array.isArray(text))) {
                 for(let key in p) {
                   if(typeof p[key] === "string" && p[key].length > 20 && key !== "title" && key !== "title_tr" && key !== "type" && key !== "explanation" && key !== "answer" && key !== "formula" && key !== "formula_tr" && key !== "pitfall" && key !== "pitfall_tr" && key !== "context" && key !== "context_tr" && key !== "scene" && key !== "setting") {
                     text = p[key]; break;
                   }
                 }
              }
            }

            // Prevent duplicate rendering if text matches sceneContext already displayed in banner
            if (text && typeof text === "string" && sceneContext && typeof sceneContext === "string") {
              if (text.trim() === sceneContext.trim() || text.trim() === (p.context || "").trim() || text.trim() === (p.context_tr || "").trim()) {
                text = "";
              }
            }

            let linesArr = [];
            if (text && typeof text === "string") {
              const translatedText = (currentLang === 'tr')
                ? ((p.text_tr || p.explanation_tr) ? text : translateEducationalText(text))
                : (p.text || p.explanation || text);
              const fixDiacriticsText = fixDiacritics(translatedText);
              if (fixDiacriticsText.includes('\n')) {
                linesArr = fixDiacriticsText.split(/\r?\n+/).map(l => l.trim()).filter(Boolean);
              } else {
                linesArr = fixDiacriticsText.split(/(?<=[.!?])\s+(?=[A-Z\u00C0-\u017F])/).map(l => l.trim()).filter(Boolean);
              }
              
              // Merge orphaned fragments (e.g. "şeklindedir.", "kullanılır.", or lowercase continuations) back into the previous line
              const mergedLines = [];
              for (const rawLine of linesArr) {
                const trimmed = rawLine.trim();
                if (!trimmed) continue;
                const isOrphan = mergedLines.length > 0 && (
                  /^[a-zçğıöşü]/.test(trimmed) ||
                  /^(şeklindedir|kullanılır|denir|diye\s|olarak|anlamına\s|gibi\s)/i.test(trimmed) ||
                  trimmed.length < 15
                );
                if (isOrphan) {
                  mergedLines[mergedLines.length - 1] += ' ' + trimmed;
                } else {
                  mergedLines.push(trimmed);
                }
              }
              linesArr = mergedLines;

              const badgeLabel = currentLang === 'tr' ? 'Pedagojik Rehber ve Kurallar' : 'Pedagogical Guidelines & Structure';
              if (linesArr.length > 1) {
                html += `
                  <div class="pedagogy-guide-block">
                    <div class="pedagogy-guide-badge">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
                      <span>${badgeLabel}</span>
                    </div>
                    <div class="pedagogy-rules-list">
                      ${linesArr.map(line => {
                        let cleanLine = line.trim().replace(/^[^a-zA-Z0-9\u00C0-\u017F\u0400-\u04FF\u0600-\u06FF\u4e00-\u9fa5\u3040-\u30ff\u3130-\u318f¿¡"'\(\[]+\s*/, "").trim();
                        if (cleanLine.length > 0) {
                          const firstChar = cleanLine.charAt(0);
                          if ((firstChar >= 'a' && firstChar <= 'z') || 'çğıöşü'.includes(firstChar)) {
                            cleanLine = firstChar.toLocaleUpperCase(currentLang === 'tr' ? 'tr-TR' : 'en-US') + cleanLine.slice(1);
                          }
                        }
                        return `<div class="pedagogy-rule-item">
                          <div class="pedagogy-rule-bullet"></div>
                          <div class="pedagogy-rule-content">${highlightPedagogicalTerms(cleanLine)}</div>
                        </div>`;
                      }).join("")}
                    </div>
                  </div>
                `;
              } else {
                html += `<div dir="auto" class="pedagogy-single-note">${highlightPedagogicalTerms(fixDiacriticsText)}</div>`;
              }
            }

            // Structured Rules Detection (Interactive Rule Cards)
            let hasRenderedStructuredRules = false;
            const rawRules = (currentLang === 'tr' && p.rules_tr && Array.isArray(p.rules_tr) && typeof p.rules_tr[0] === 'object') ? p.rules_tr : p.rules;
            if (Array.isArray(rawRules) && rawRules.length > 0 && typeof rawRules[0] === 'object') {
              hasRenderedStructuredRules = true;
              html += `<div class="pedagogy-rules-container">`;
              rawRules.forEach((rObj, rIdx) => {
                const rTitle = (currentLang === 'tr' && rObj.rule_tr) ? rObj.rule_tr : (rObj.rule || rObj.name || `Rule ${rIdx + 1}`);
                const rExpl = (currentLang === 'tr' && rObj.explanation_tr) ? rObj.explanation_tr : (rObj.explanation || rObj.desc || "");
                const rEx = rObj.example || rObj.target || "";
                const rExEn = rObj.example_en || rObj.translation || "";
                const rExTr = rObj.example_tr || (rObj.translation_tr || rObj.turkish || "");
                let rAnalysis = "";
                if (currentLang === 'tr') {
                  const rawA = rObj.analysis_tr || rObj.analysis || rObj.breakdown || "";
                  rAnalysis = rObj.analysis_tr || (rawA ? translateEducationalText(rawA, 'tr') : "");
                } else {
                  const rawA = rObj.analysis || rObj.analysis_tr || rObj.breakdown || "";
                  rAnalysis = rObj.analysis || (rawA ? translateEducationalText(rawA, 'en') : "");
                }
                const resolvedTrans = (currentLang === 'tr') ? (rExTr || (rExEn ? translateEducationalText(rExEn) : "")) : (rExEn || rExTr);

                html += `
                  <div class="pedagogy-rule-card">
                    <div class="pedagogy-rule-title">
                      <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--accent);"></span>
                      <span>${fixDiacritics(rTitle)}</span>
                    </div>
                    ${rExpl ? `<div class="pedagogy-rule-explanation">${highlightPedagogicalTerms(fixDiacritics(rExpl))}</div>` : ''}
                    ${rEx ? `
                      <div class="pedagogy-rule-example-box">
                        <div class="pedagogy-rule-example-top">
                          <span class="pedagogy-rule-example-label">${currentLang === 'tr' ? 'Örnek Kullanım' : 'Example Usage'}</span>
                          <button class="tts-btn" onclick="handleTTSClick(this, ${escJS(rEx)}, null, event)" title="Listen">${TTS_SVG_IDLE}</button>
                        </div>
                        <div class="foreign-word" role="button" tabindex="0" style="font-style:italic; font-size:16px; font-weight:600; line-height:1.55; color:var(--text-primary); cursor:pointer; display:inline;">&ldquo;${fixDiacritics(rEx)}&rdquo;</div>
                        ${resolvedTrans ? `<div style="font-size:13.5px; color:var(--text-secondary); margin-top:5px; line-height:1.45;">${fixDiacritics(resolvedTrans)}</div>` : ''}
                        ${rAnalysis ? `<div style="font-size:12px; color:var(--accent-light); margin-top:6px; padding-top:6px; border-top:1px dashed var(--border); line-height:1.4;"><strong style="text-transform:uppercase; font-size:10px; letter-spacing:0.5px;">${currentLang === 'tr' ? 'Dilbilgisi Analizi' : 'Structural Breakdown'}:</strong> ${fixDiacritics(rAnalysis)}</div>` : ''}
                      </div>
                    ` : ''}
                  </div>
                `;
              });
              html += `</div>`;
            }

            // Register / Nuance Contrast Section
            const compList = (currentLang === 'tr' && p.comparisons_tr) ? p.comparisons_tr : (p.comparisons || p.contrasts || []);
            if (Array.isArray(compList) && compList.length > 0) {
              const compHeader = currentLang === 'tr' ? 'Üslup ve Nüans Karşılaştırması' : 'Register & Nuance Contrast';
              html += `
                <div class="pedagogy-contrast-section">
                  <div class="pedagogy-formula-badge" style="color:var(--accent-light); margin-bottom:8px;">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 3 21 3 21 8"></polyline><line x1="4" y1="20" x2="21" y2="3"></line><polyline points="21 16 21 21 16 21"></polyline><line x1="15" y1="15" x2="21" y2="21"></line><line x1="4" y1="4" x2="9" y2="9"></line></svg>
                    <span>${compHeader}</span>
                  </div>
                  <div class="pedagogy-contrast-grid">
                    ${compList.map(c => {
                      let cContext = "";
                      if (currentLang === 'tr') {
                        cContext = c.context_tr || (c.context ? translateEducationalText(c.context, 'tr') : (c.label ? translateEducationalText(c.label, 'tr') : "Karşılaştırma"));
                      } else {
                        // Always translate — c.context may be stored in Turkish for older materials
                        const rawCtx = c.context || c.context_tr || c.label || "";
                        cContext = rawCtx ? translateEducationalText(rawCtx, 'en') : "Contrast";
                      }
                      const cTarget = c.target || c.sentence || c.text || "";
                      let cTrans = "";
                      if (currentLang === 'tr') {
                        cTrans = c.translation_tr || (c.translation ? translateEducationalText(c.translation, 'tr') : (c.meaning ? translateEducationalText(c.meaning, 'tr') : ""));
                      } else {
                        // c.translation may be stored in Turkish — always run through EN translation
                        const rawTrans = c.translation_en || c.translation || c.translation_tr || c.meaning || "";
                        cTrans = rawTrans ? translateEducationalText(rawTrans, 'en') : "";
                      }
                      let cNote = "";
                      if (currentLang === 'tr') {
                        cNote = c.note_tr || (c.note ? translateEducationalText(c.note, 'tr') : (c.explanation ? translateEducationalText(c.explanation, 'tr') : ""));
                      } else {
                        // c.note may be stored in Turkish — always run through EN translation
                        const rawNote = c.note_en || c.note || c.note_tr || c.explanation || "";
                        cNote = rawNote ? translateEducationalText(rawNote, 'en') : "";
                      }
                      return `
                        <div class="pedagogy-contrast-card">
                          <div class="pedagogy-contrast-tag">${fixDiacritics(cContext)}</div>
                          ${cTarget ? `
                            <div style="display:flex; align-items:center; justify-content:space-between; gap:6px;">
                              <div class="foreign-word pedagogy-contrast-target" role="button" tabindex="0" style="cursor:pointer; display:inline;">&ldquo;${fixDiacritics(cTarget)}&rdquo;</div>
                              <button class="tts-btn" onclick="handleTTSClick(this, ${escJS(cTarget)}, null, event)" title="Listen">${TTS_SVG_IDLE}</button>
                            </div>
                          ` : ''}
                          ${cTrans ? `<div class="pedagogy-contrast-trans">${fixDiacritics(cTrans)}</div>` : ''}
                          ${cNote ? `<div class="pedagogy-contrast-note">${fixDiacritics(cNote)}</div>` : ''}
                        </div>
                      `;
                    }).join('')}
                  </div>
                </div>
              `;
            }

            // Teacher's Pitfall & Caution Box
            const pitfallVal = (currentLang === 'tr' && p.pitfall_tr) ? p.pitfall_tr : (p.pitfall || p.caution || p.teacher_note || "");
            if (pitfallVal && typeof pitfallVal === "string" && pitfallVal.trim().length > 0) {
              const pitfallTitle = currentLang === 'tr' ? 'Öğretmenin Notu & Sık Yapılan Hatalar' : 'Teacher’s Caution & Common Pitfalls';
              html += `
                <div class="pedagogy-pitfall-card">
                  <div class="pedagogy-pitfall-header">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                    <span>${pitfallTitle}</span>
                  </div>
                  <div class="pedagogy-pitfall-body">${highlightPedagogicalTerms(fixDiacritics(pitfallVal))}</div>
                </div>
              `;
            }

            // 2. Data List Detection
            let rawData = [];
            if (currentLang === 'tr') {
              rawData = p.items_tr || p.list_tr || p.examples_tr || p.dialogue_tr || (hasRenderedStructuredRules ? null : p.rules_tr);
            }
            if (!Array.isArray(rawData) || rawData.length === 0) {
              rawData = p.items || p.vocabulary || p.words || p.list || p.phrases || p.examples || p.dialogue || p.conversation || p.turns || p.lines || (hasRenderedStructuredRules ? [] : (p.rules || []));
            }
            if (!Array.isArray(rawData) || rawData.length === 0) {
              for (const key in p) {
                if (Array.isArray(p[key]) && p[key].length > 0 && key !== 'pages' && key !== 'options' && key !== 'choices' && key !== 'distractors' && key !== 'answer' && key !== 'rules' && key !== 'comparisons') {
                  rawData = p[key]; break;
                }
              }
            }

            // Fallback for dialogue / practical application pages if list is empty
            const isExampleOrDialoguePage = (p.type === 'examples' || p.type === 'dialogue' || (p.title && /practical|application|pratik|uygulama|dialogue|diyalog/i.test(p.title || '')));
            if (isExampleOrDialoguePage && (!Array.isArray(rawData) || rawData.length === 0) && !isMcq) {
              const tTitleLower = ((topic && topic.title) || '').toLowerCase();
              if (tTitleLower.includes('vowel') || tTitleLower.includes('consonant') || tTitleLower.includes('sesli') || tTitleLower.includes('sessiz') || tTitleLower.includes('alphabet') || tTitleLower.includes('pronunciation')) {
                rawData = [
                  { speaker: "A", text: "¡Hola! ¿Cómo se escribe tu nombre?", translation: "Hello! How do you spell your name?", translation_tr: "Merhaba! Adın nasıl yazılıyor?" },
                  { speaker: "B", text: "Se escribe con 'e', 'l', 'e', 'n', 'a': Elena.", translation: "It is spelled with 'e', 'l', 'e', 'n', 'a': Elena.", translation_tr: "'e', 'l', 'e', 'n', 'a' harfleriyle yazılır: Elena." },
                  { speaker: "A", text: "¿Todas las vocales suenan claras en español?", translation: "Do all vowels sound clear in Spanish?", translation_tr: "İspanyolcada tüm sesli harfler net mi okunur?" },
                  { speaker: "B", text: "Sí, exactamente. Cada vocal tiene un sonido único.", translation: "Yes, exactly. Each vowel has a unique sound.", translation_tr: "Evet, aynen öyle. Her sesli harfin tek ve net bir sesi vardır." }
                ];
              } else {
                rawData = [
                  { speaker: "A", text: "Buenos días, ¿podemos repasar la lección?", translation: "Good morning, can we review the lesson?", translation_tr: "Günaydın, dersi gözden geçirebilir miyiz?" },
                  { speaker: "B", text: "Por supuesto, practiquemos estos conceptos juntos.", translation: "Of course, let's practice these concepts together.", translation_tr: "Elbette, bu kavramları birlikte pratik edelim." },
                  { speaker: "A", text: "¿Es común usar estas frases a diario?", translation: "Is it common to use these phrases daily?", translation_tr: "Bu ifadeleri günlük hayatta kullanmak yaygın mıdır?" },
                  { speaker: "B", text: "Sí, son expresiones fundamentales en la conversación.", translation: "Yes, they are fundamental expressions in conversation.", translation_tr: "Evet, konuşma dilinde temel ifadelerdir." }
                ];
              }
            }

            // Safe string extractor: drills into nested objects to find a displayable string
            const safeStr = (val) => {
              if (val === null || val === undefined) return "";
              if (typeof val === "string") return val;
              if (typeof val === "number" || typeof val === "boolean") return String(val);
              if (Array.isArray(val)) return val.map(v => safeStr(v)).filter(Boolean).join(", ");
              if (typeof val === "object") {
                // Try common display keys first
                const displayKeys = ['text','name','value','label','character','hiragana','katakana','letter','symbol','word','term','phrase','romaji','pinyin','reading'];
                for (const dk of displayKeys) {
                  if (val[dk] && typeof val[dk] === "string") return val[dk];
                }
                // Fallback: grab first string value
                const vals = Object.values(val);
                for (const v of vals) {
                  if (typeof v === "string" && v.length > 0) return v;
                }
                // Last resort: concatenate all string values
                const strs = vals.filter(v => typeof v === "string" && v.length > 0);
                if (strs.length > 0) return strs.join(" — ");
                return JSON.stringify(val);
              }
              return String(val);
            };

            // Prevent MCQs from double-rendering their options as vocab cards
            if (Array.isArray(rawData) && rawData.length > 0 && !isMcq) {
              html += `<div style="display:flex; flex-direction:column; gap:10px; margin-top:10px;">`;
              rawData.forEach((it, itIdx) => {
                if (typeof it === "string") {
                  const sTrimmed = it.trim();
                  // 1. Dialogue line formatted as string, e.g. "A: ¿Cómo te llamas?" or "Carlos: Me llamo Carlos."
                  const speakerMatch = sTrimmed.match(/^([A-Za-z0-9\u00C0-\u017F\s]{1,12})\s*[:\-]\s*(.+)$/);
                  if (speakerMatch && !sTrimmed.startsWith('•') && !sTrimmed.startsWith('*')) {
                    const speaker = speakerMatch[1].trim();
                    const targetLine = speakerMatch[2].trim();
                    const rawSpeaker = safeStr(speaker).trim();
                    const isSpeakerB = (rawSpeaker.toUpperCase() === 'B' || rawSpeaker.toLowerCase().includes('2') || rawSpeaker.toLowerCase().startsWith('b:'));
                    const speakerClass = isSpeakerB ? 'speaker-b' : 'speaker-a';
                    const avatarLetter = (rawSpeaker.charAt(0) || (isSpeakerB ? 'B' : 'A')).toUpperCase();
                    const isSingleLetterSpeaker = (rawSpeaker.toUpperCase() === avatarLetter || /^(speaker|konuşmacı|hablante)\s*[a-z0-9]$/i.test(rawSpeaker));
                    const speakerDisplayName = isSingleLetterSpeaker
                      ? (currentLang === 'tr' ? `Konuşmacı ${avatarLetter}` : `Speaker ${avatarLetter}`)
                      : rawSpeaker;

                    html += `
                      <div class="study-dialogue-card ${speakerClass}" dir="auto">
                        <div class="dialogue-card-header">
                          <div class="dialogue-speaker-badge">
                            <div class="dialogue-speaker-avatar">${avatarLetter}</div>
                            <div class="dialogue-speaker-name">${speakerDisplayName}</div>
                          </div>
                          <div class="dialogue-card-actions">
                            <button class="tts-btn" onclick="handleTTSClick(this, ${escJS(targetLine)}, null, event)" title="Listen">${TTS_SVG_IDLE}</button>
                          </div>
                        </div>
                        <div class="foreign-word dialogue-phrase" role="button" tabindex="0">&ldquo;${fixDiacritics(safeStr(targetLine))}&rdquo;</div>
                      </div>`;
                  } else {
                    const isExampleOrDialoguePage = (p.type === 'examples' || p.type === 'dialogue' || (p.title && /practical|application|pratik|uygulama|dialogue|diyalog/i.test(p.title)));
                    const isExplicitRule = sTrimmed.startsWith('•') || sTrimmed.startsWith('-') || sTrimmed.startsWith('*');

                    if (isExplicitRule || (!isExampleOrDialoguePage && (sTrimmed.split(/\s+/).length > 4 || sTrimmed.length > 35))) {
                      // Guideline rule / sentence — render as pedagogical guideline card, NOT as a vocab flashcard with TTS
                      const cleanLine = sTrimmed.replace(/^[•\-\*\s]+/, '').trim();
                      let translatedLine = cleanLine;
                      if (currentLang === 'tr') {
                        if (p.rules_tr && Array.isArray(p.rules_tr) && p.rules_tr[itIdx]) {
                          translatedLine = p.rules_tr[itIdx].replace(/^[•\-\*\s]+/, '').trim();
                        } else {
                          translatedLine = translateEducationalText(cleanLine);
                        }
                      }
                      if (translatedLine.length > 0) {
                        const firstChar = translatedLine.charAt(0);
                        if ((firstChar >= 'a' && firstChar <= 'z') || 'çğıöşü'.includes(firstChar)) {
                          translatedLine = firstChar.toLocaleUpperCase(currentLang === 'tr' ? 'tr-TR' : 'en-US') + translatedLine.slice(1);
                        }
                      }
                      html += `
                        <div class="pedagogy-guide-block" style="margin-top:4px; margin-bottom:4px;">
                          <div class="pedagogy-rules-list">
                            <div class="pedagogy-rule-item">
                              <div class="pedagogy-rule-bullet"></div>
                              <div class="pedagogy-rule-content">${highlightPedagogicalTerms(fixDiacritics(translatedLine))}</div>
                            </div>
                          </div>
                        </div>`;
                    } else if (isExampleOrDialoguePage && (sTrimmed.split(/\s+/).length > 2 || sTrimmed.length > 15)) {
                      // Standalone target language example sentence
                      html += `
                        <div class="study-dialogue-card speaker-a" dir="auto">
                          <div class="dialogue-card-header">
                            <div class="dialogue-speaker-badge">
                              <div class="dialogue-speaker-avatar"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg></div>
                              <div class="dialogue-speaker-name">${currentLang === 'tr' ? 'Örnek Cümle' : 'Example'}</div>
                            </div>
                            <div class="dialogue-card-actions">
                              <button class="tts-btn" onclick="handleTTSClick(this, ${escJS(sTrimmed)}, null, event)" title="Listen">${TTS_SVG_IDLE}</button>
                            </div>
                          </div>
                          <div class="foreign-word dialogue-phrase" role="button" tabindex="0">&ldquo;${fixDiacritics(sTrimmed)}&rdquo;</div>
                        </div>`;
                    } else {
                      const normStr = normalizeConceptStr(sTrimmed);
                      const isCJK = /[\u4e00-\u9fff]/.test(sTrimmed);
                      const courseLang = (currentCourse && currentCourse.language) ? currentCourse.language : 'Spanish';
                      const isLetter = !isCJK && (sTrimmed.length === 1 || SPANISH_LETTER_SPELLINGS.has(normStr));
                      if (isLetter) {
                        // Single letter with authentic phonetics guide
                        const phonData = getClientLetterPhonetics(courseLang, sTrimmed) || {};
                        const letterName = phonData.name || (SPANISH_LETTER_SPELLINGS.has(normStr) ? sTrimmed : '');
                        const phoneticGuide = (currentLang === 'tr') ? (phonData.phonetic_tr || '') : (phonData.phonetic_en || '');
                        const exampleWord = phonData.example || '';
                        const exampleTrans = (currentLang === 'tr') ? (phonData.example_tr || '') : (phonData.example_en || '');
                        html += `<div class="study-vocab-card alphabet-card">
                            <div class="vocab-card-header">
                              <div class="vocab-term-wrapper">
                                <button class="tts-btn" onclick="handleTTSClick(this, ${escJS(it)}, null, event)">${TTS_SVG_IDLE}</button>
                                <div class="vocab-term-text"><div dir="auto" style="font-size:18px; font-weight:700; color:var(--text-primary);">${fixDiacritics(it)}</div></div>
                              </div>
                              <div class="vocab-header-actions">
                                ${letterName ? `<div class="letter-name" style="font-style:italic; font-size:15px; font-weight:600; color:var(--accent-light);">${fixDiacritics(letterName)}</div>` : ''}
                                ${phoneticGuide ? `<div class="phonetic-badge">${fixDiacritics(phoneticGuide)}</div>` : ''}
                              </div>
                            </div>
                            ${exampleWord ? `
                              <div class="vocab-pedagogy-section" style="border-left-color: #a5b4fc;">
                                <div style="font-size:13px; color:var(--text-secondary);">${currentLang === 'tr' ? 'Örnek Sözcük' : 'Example Word'}: <span style="color:var(--text-primary); font-weight:600;">${fixDiacritics(exampleWord)}</span>${exampleTrans ? ` <span style="opacity:0.85;">(${fixDiacritics(exampleTrans)})</span>` : ''}</div>
                              </div>` : ''}
                          </div>`;
                      } else {
                        // Multi-char word — dict-clickable, but only over the word text itself
                        const briefExpl = resolveItemExplanation(null, it, '', currentLang);
                        html += `<div class="study-vocab-card">
                            <div class="vocab-card-header">
                              <div class="vocab-term-wrapper">
                                <button class="tts-btn" onclick="handleTTSClick(this, ${escJS(it)}, null, event)">${TTS_SVG_IDLE}</button>
                                <div class="vocab-term-text"><div class="foreign-word" role="button" tabindex="0" style="cursor:pointer; font-size:16px; font-weight:600; color:var(--text-primary); display:inline;">${fixDiacritics(it)}</div></div>
                              </div>
                              ${briefExpl ? `<span class="vocab-meaning-pill">${fixDiacritics(safeStr(briefExpl))}</span>` : ''}
                            </div>
                          </div>`;
                      }
                    }
                  }
                } else if (typeof it === "object" && it !== null) {
                  // Check if it is a dialogue item
                  if (it.speaker || it.role || it.actor || it.person) {
                    const speaker = safeStr(it.speaker || it.role || it.actor || it.person || "A");
                    const targetText = safeStr(
                      it.text || it.sentence || it.phrase || it.line || it.dialogue ||
                      it.target || it.spanish || it.german || it.french || it.italian ||
                      it.japanese || it.chinese || it.korean || it.term || it.word ||
                      Object.values(it).find(val => typeof val === 'string' && val !== it.speaker && val !== it.role && val !== it.translation && val !== it.translation_tr && val !== it.translation_en) || ""
                    );
                    const rawTransEn = safeStr(it.translation_en || it.english || it.meaning_en || it.translation || it.meaning);
                    const rawTransTr = safeStr(it.translation_tr || it.turkish || it.meaning_tr);
                    let transText = resolveDualLanguage(rawTransEn, rawTransTr, currentLang, (currentLang === 'tr' ? rawTransTr : rawTransEn));
                    if (transText && transText.trim().toLowerCase() === targetText.trim().toLowerCase()) {
                      transText = "";
                    }

                    const rawSpeaker = safeStr(speaker).trim();
                    const isSpeakerB = (rawSpeaker.toUpperCase() === 'B' || rawSpeaker.toLowerCase().includes('2') || rawSpeaker.toLowerCase().startsWith('b:'));
                    const speakerClass = isSpeakerB ? 'speaker-b' : 'speaker-a';
                    const avatarLetter = (rawSpeaker.charAt(0) || (isSpeakerB ? 'B' : 'A')).toUpperCase();
                    const isSingleLetterSpeaker = (rawSpeaker.toUpperCase() === avatarLetter || /^(speaker|konuşmacı|hablante)\s*[a-z0-9]$/i.test(rawSpeaker));
                    const speakerDisplayName = isSingleLetterSpeaker
                      ? (currentLang === 'tr' ? `Konuşmacı ${avatarLetter}` : `Speaker ${avatarLetter}`)
                      : rawSpeaker;
                    const diagId = `diag-bubble-${p.type || 'p'}-${itIdx}`;

                    html += `
                      <div class="study-dialogue-card ${speakerClass}" dir="auto">
                        <div class="dialogue-card-header">
                          <div class="dialogue-speaker-badge">
                            <div class="dialogue-speaker-avatar">${avatarLetter}</div>
                            <div class="dialogue-speaker-name">${speakerDisplayName}</div>
                          </div>
                          <div class="dialogue-card-actions">
                            ${transText ? `
                              <button class="dialogue-trans-toggle-btn active" onclick="toggleDialogueTrans('${diagId}', this)" title="${currentLang === 'tr' ? 'Çeviriyi Göster / Gizle' : 'Toggle Meaning'}" aria-expanded="true">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                                <span>${currentLang === 'tr' ? 'Çeviri' : 'Meaning'}</span>
                              </button>` : ''}
                            ${targetText ? `<button class="tts-btn" onclick="handleTTSClick(this, ${escJS(targetText)}, null, event)" title="Listen">${TTS_SVG_IDLE}</button>` : ''}
                          </div>
                        </div>
                        <div class="foreign-word dialogue-phrase" role="button" tabindex="0">&ldquo;${fixDiacritics(safeStr(targetText))}&rdquo;</div>
                        ${transText ? `<div id="${diagId}" class="dialogue-translation-box">${fixDiacritics(safeStr(transText))}</div>` : ''}
                      </div>`;
                  } else {
                    const k = safeStr(it.term || it.word || it.phrase || it.sentence || it.text || it.character || it.letter || it.symbol || it.spanish || it.japanese || it.chinese || it.korean || it.key || Object.values(it)[0]);
                    const enRawV = safeStr(it.translation_en || it.english || it.meaning_en || it.translation || it.meaning || '');
                    const trRawV = safeStr(it.translation_tr || it.turkish || it.meaning_tr || it.tr || '');

                    let v = '';
                    if (currentLang === 'tr') {
                      if (trRawV && trRawV.trim()) {
                        v = trRawV.trim();
                      } else {
                        v = resolveDualLanguage(enRawV, trRawV, 'tr', enRawV);
                        if (v) v = translateOption(v, 'tr');
                        if (v && enRawV && v.toLowerCase() === enRawV.toLowerCase()) {
                          const fallbackTr = translateEducationalText(enRawV, 'tr');
                          if (fallbackTr && fallbackTr.toLowerCase() !== enRawV.toLowerCase()) v = fallbackTr;
                        }
                      }
                    } else {
                      if (enRawV && enRawV.trim()) {
                        v = enRawV.trim();
                      } else {
                        v = resolveDualLanguage(enRawV, trRawV, 'en', trRawV);
                        if (v) v = translateOption(v, 'en');
                      }
                    }
                    if (v) {
                      v = v.charAt(0).toUpperCase() + v.slice(1);
                    }

                    // --- PRAGMATIC GREETINGS, PRONOUNS & AUXILIARIES SELF-HEALING ---
                    const kStr = safeStr(k).trim();
                    const isSingleChar = (kStr.length === 1 && !/[\u4e00-\u9fff]/.test(kStr));
                    const courseLang = (currentCourse && currentCourse.language) ? currentCourse.language : 'Spanish';
                    const normK = normalizeConceptStr(kStr);

                    // Only match pragmatic map for multi-character phrases (never corrupt single letters like 'I')
                    if (!isSingleChar && normK && FRONTEND_PRAGMATIC_MAP[normK]) {
                      const prag = FRONTEND_PRAGMATIC_MAP[normK];
                      v = (currentLang === 'tr') ? prag.tr : prag.en;
                    }

                    // Letter self-healing for meaning pill badge (never show example sentence in pill)
                    const isLetterCard = isLetterLike(kStr) || Boolean(it.letter || it.character);
                    if (isLetterCard) {
                      const baseL = extractBaseLetter(kStr);
                      const phon = getClientLetterPhonetics(courseLang, baseL) || {};
                      const isVEmptyOrEcho = !v || v.toLowerCase() === kStr.toLowerCase() || (normK && normK === normalizeConceptStr(v));
                      if (isVEmptyOrEcho) {
                        const hasDistinctName = phon.name && phon.name.trim().toUpperCase() !== baseL.toUpperCase();
                        const lName = hasDistinctName ? ` (${phon.name})` : '';
                        v = (currentLang === 'tr')
                          ? `${baseL} harfi${lName}`
                          : `Letter ${baseL}${lName}`;
                      }
                    }

                    // Eliminate calque 'öğleden sonra' if present in v
                    if (typeof v === 'string' && (v.toLowerCase().includes('öğleden sonra') || v.toLowerCase().includes('ogleden sonra'))) {
                      v = (currentLang === 'tr') ? 'Tünaydın' : 'Good afternoon';
                    }

                    // --- SEMANTIC CONCEPT SELF-HEALING ---
                    const termConceptKey = (!isSingleChar) ? resolveConceptKey(kStr) : '';
                    if (termConceptKey) {
                      const transConceptKey = resolveConceptKey(safeStr(v));
                      if ((transConceptKey && areConceptsIncompatible(termConceptKey, transConceptKey)) || !v || v.toLowerCase() === kStr.toLowerCase()) {
                        const canonicalTitle = CANONICAL_CONCEPT_NAMES[termConceptKey] ? CANONICAL_CONCEPT_NAMES[termConceptKey][currentLang] : null;
                        if (canonicalTitle) {
                          v = canonicalTitle;
                        }
                      }
                    }

                    const isCJKChar = /[\u4e00-\u9fff]/.test(kStr);
                    const isLetter = !isCJKChar && (
                      isLetterLike(kStr) ||
                      SPANISH_LETTER_SPELLINGS.has(normK) ||
                      Boolean(it.letter || it.character)
                    );

                    const isSentenceCard = Boolean(it.sentence || (it.text && !it.term && !it.word) || (typeof k === "string" && k.length > 50) || p.type === 'examples');

                    if (isSentenceCard && !isLetter) {
                      const exTransId = `diag-ex-${Math.random().toString(36).slice(2, 9)}`;
                      html += `
                        <div class="study-dialogue-card speaker-a" dir="auto">
                          <div class="dialogue-card-header">
                            <div class="dialogue-speaker-badge">
                              <div class="dialogue-speaker-avatar"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg></div>
                              <div class="dialogue-speaker-name">${currentLang === 'tr' ? 'Örnek Cümle' : 'Example'}</div>
                            </div>
                            <div class="dialogue-card-actions">
                              ${(v && v.toLowerCase() !== kStr.toLowerCase()) ? `
                                <button class="dialogue-trans-toggle-btn" onclick="toggleDialogueTrans('${exTransId}', this)" title="${currentLang === 'tr' ? 'Çeviriyi Göster / Gizle' : 'Toggle Meaning'}">
                                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                                  <span>${currentLang === 'tr' ? 'Çeviri' : 'Meaning'}</span>
                                </button>` : ''}
                              ${kStr ? `<button class="tts-btn" onclick="handleTTSClick(this, ${escJS(kStr)}, null, event)" title="Listen">${TTS_SVG_IDLE}</button>` : ''}
                            </div>
                          </div>
                          <div class="foreign-word dialogue-phrase" role="button" tabindex="0">&ldquo;${fixDiacritics(safeStr(kStr))}&rdquo;</div>
                          ${(v && v.toLowerCase() !== kStr.toLowerCase()) ? `<div id="${exTransId}" class="dialogue-translation-box">${fixDiacritics(safeStr(v))}</div>` : ''}
                        </div>`;
                    } else if (isLetter && !it.explanation && !it.explanation_en && !it.explanation_tr && !it.example) {
                    // Minimal single letter — render compact card
                    const phonData = getClientLetterPhonetics(courseLang, kStr) || {};
                    let letterName = it.name || phonData.name || (SPANISH_LETTER_SPELLINGS.has(normK) ? kStr : '') || safeStr(v);
                    if (['she', 'he', 'ben', 'i'].includes(letterName.toLowerCase()) && letterName.length > 1) {
                      letterName = phonData.name || kStr;
                    }
                    const phoneticGuide = (currentLang === 'tr')
                      ? (it.phonetic_tr || phonData.phonetic_tr || '')
                      : (it.phonetic_en || phonData.phonetic_en || '');
                    const exampleWord = it.example || phonData.example || '';
                    const rawExEn = it.example_en || phonData.example_en || it.translation_en || '';
                    const rawExTr = it.example_tr || phonData.example_tr || it.translation_tr || '';
                    const exampleTrans = (currentLang === 'tr') ? (rawExTr || (rawExEn ? translateEducationalText(rawExEn, 'tr') : '')) : (rawExEn || rawExTr);

                    html += `<div class="study-vocab-card alphabet-card">
                        <div class="vocab-term-wrapper">
                          <button class="tts-btn" onclick="handleTTSClick(this, ${escJS(kStr)}, null, event)">${TTS_SVG_IDLE}</button>
                          <div class="vocab-term-text"><div dir="auto" style="font-size:18px; font-weight:700; color:var(--text-primary);">${fixDiacritics(kStr)}</div></div>
                        </div>
                        <div class="alphabet-pronunciation-block" style="text-align:right;">
                          ${letterName ? `<div class="letter-name" style="font-style:italic; font-size:15px; font-weight:600; color:var(--accent-light);">${fixDiacritics(letterName)}</div>` : ''}
                          ${phoneticGuide ? `<div class="phonetic-badge" style="display:inline-block; margin-top:3px; padding:2px 8px; border-radius:6px; background:rgba(99,102,241,0.15); color:#a5b4fc; font-family:monospace; font-size:12px; font-weight:600; letter-spacing:0.3px;">${fixDiacritics(phoneticGuide)}</div>` : ''}
                          ${exampleWord ? `<div style="font-size:12px; color:var(--text-secondary); margin-top:3px;">${currentLang === 'tr' ? 'Örnek' : 'Example'}: <span style="color:var(--text-primary); font-weight:600;">${fixDiacritics(exampleWord)}</span>${exampleTrans ? ` <span style="opacity:0.8;">(${fixDiacritics(exampleTrans)})</span>` : ''}</div>` : ''}
                        </div>
                      </div>`;
                  } else {
                    // Regular vocabulary item or enriched pronunciation card with authentic pedagogy tip and example sentence
                    const briefExpl = resolveItemExplanation(it, kStr, safeStr(v), currentLang);
                    const bankHit = getClientVocabExample(courseLang, kStr) || {};
                    const exampleTarget = it.example || bankHit.example || '';
                    const rawExEn = it.example_en || bankHit.example_en || '';
                    const rawExTr = it.example_tr || bankHit.example_tr || '';
                    let exampleTrans = '';
                    if (currentLang === 'tr') {
                      if (rawExTr && rawExTr.trim()) {
                        exampleTrans = rawExTr.trim();
                      } else if (rawExEn && rawExEn.trim()) {
                        exampleTrans = translateEducationalText(rawExEn, 'tr');
                      }
                    } else {
                      if (rawExEn && rawExEn.trim()) {
                        exampleTrans = rawExEn.trim();
                      } else if (rawExTr && rawExTr.trim()) {
                        exampleTrans = translateEducationalText(rawExTr, 'en');
                      }
                    }

                    // --- STRICT ENGLISH LEAK HEALER FOR TURKISH MODE ---
                    if (currentLang === 'tr') {
                      if (isSanityEN(v) || /^(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|stop|train|ticket|doctor)$/i.test(v)) {
                        const trTrans = translateOption(v, 'tr');
                        if (trTrans && trTrans.toLowerCase() !== v.toLowerCase()) {
                          v = trTrans.charAt(0).toUpperCase() + trTrans.slice(1);
                        }
                      }
                    }

                    // Part of speech / grammatical category badge if available
                    const posBadge = safeStr(it.pos || it.part_of_speech || it.type || it.category || '').trim();

                    html += `<div class="study-vocab-card">
                        <div class="vocab-card-header">
                          <div class="vocab-term-wrapper">
                            <button class="tts-btn" onclick="handleTTSClick(this, ${escJS(kStr)}, null, event)" title="Listen">${TTS_SVG_IDLE}</button>
                            <div class="vocab-term-text"><div dir="auto" class="foreign-word" role="button" tabindex="0" style="cursor:pointer; display:inline;">${fixDiacritics(kStr)}</div></div>
                          </div>
                          <div class="vocab-header-actions">
                            ${posBadge ? `<span class="vocab-pos-badge">${esc(posBadge)}</span>` : ''}
                            <span class="vocab-meaning-pill">${fixDiacritics(safeStr(v))}</span>
                          </div>
                        </div>
                        ${briefExpl ? `
                          <div class="vocab-pedagogy-section">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                            <div class="vocab-pedagogy-text">${fixDiacritics((currentLang === 'tr') ? humanizeTurkishExplanation(safeStr(briefExpl)) : sanitizeEnglishExplanation(safeStr(briefExpl), kStr))}</div>
                          </div>` : ''}
                        ${exampleTarget ? `
                          <div class="vocab-example-card">
                            <div class="vocab-example-target-row">
                              <div class="foreign-word vocab-example-target" role="button" tabindex="0">&ldquo;${fixDiacritics(safeStr(exampleTarget))}&rdquo;</div>
                              <button class="tts-btn" onclick="handleTTSClick(this, ${escJS(exampleTarget)}, null, event)" title="Listen">${TTS_SVG_IDLE}</button>
                            </div>
                            ${exampleTrans ? `<div class="vocab-example-trans">${fixDiacritics(safeStr(exampleTrans))}</div>` : ''}
                          </div>` : ''}
                      </div>`;
                  }
                }
              }
            });
              html += `</div>`;
            }

             // 3. MCQ Support
            if (p.type === 'mcq' || p.prompt) {
               const rawOptions = (Array.isArray(p.options) && p.options.length > 1)
                 ? p.options
                 : (p.distractors || []).concat(p.answer);
               const allOptions = Array.from(new Set(rawOptions)).filter(Boolean);
               if (!Array.isArray(p.options) || p.options.length <= 1) {
                 allOptions.sort();
               }
               const translatedPrompt = resolveStudyPrompt(p, topic);
               const mcqExpl = (currentLang === 'tr' && (p.explanation_tr || p.text_tr)) ? (p.explanation_tr || p.text_tr) : (p.explanation || p.text || "");
               const studyKey = 'study_' + (topic ? topic.id : 'unknown') + '_' + pIdx;
               const savedAnswer = _answeredQuestionsState[studyKey];

               let restoredExplBox = '';
               if (savedAnswer && (mcqExpl || savedAnswer.explanation)) {
                 const explToUse = mcqExpl || savedAnswer.explanation;
                 const explLabel = currentLang === 'tr' ? 'Açıklama' : 'Explanation';
                 const isAlreadyTr = (currentLang === 'tr') && (/[çğıöşüÇĞİÖŞÜ]/.test(explToUse) || explToUse.includes('doğru') || explToUse.includes('çünkü') || explToUse.includes('ifade'));
                 const translatedExplanation = (currentLang === 'tr') ? (isAlreadyTr ? explToUse : (typeof translateEducationalText === 'function' ? translateEducationalText(explToUse) : explToUse)) : explToUse;
                 restoredExplBox = `<div class="study-explanation-box" style="margin-top:20px; padding:16px 20px; background:rgba(255,255,255,0.04); border-radius:12px; border:1px solid var(--border); font-size:15px; line-height:1.6; white-space:pre-wrap; color:var(--text-primary);"><div style="font-weight:700; color:var(--accent-light); margin-bottom:6px; display:flex; align-items:center; gap:6px;"><span>${explLabel}</span></div>${fixDiacritics(translatedExplanation)}</div>`;
               }

               html += `<div style="margin-top:${html ? '24px' : '0'}; background:var(--bg-input); padding:24px; border-radius:12px; border:1px solid var(--border);">
                 <div dir="auto" style="font-size:16px; font-weight:700; margin-bottom:16px; color:var(--text-primary); line-height:1.5;">${fixDiacritics(translatedPrompt)}</div>
                 <div style="display:flex; flex-direction:column; gap:10px;">
                   ${allOptions.map(opt => {
                     if (savedAnswer) {
                       const isPicked = (opt === savedAnswer.selected);
                       const isTargetCorrect = (opt === savedAnswer.correct);
                       let btnStyle = "justify-content:flex-start; text-align:left; padding:14px 18px; font-size:15px; border-radius:8px; opacity:0.75;";
                       let badgeIcon = "";
                       if (isPicked && savedAnswer.isCorrect) {
                         btnStyle += " background:rgba(34, 197, 94, 0.2); border-color:#22c55e; opacity:1;";
                         badgeIcon = ' ' + SVG_CHECK;
                       } else if (isPicked && !savedAnswer.isCorrect) {
                         btnStyle += " background:rgba(239, 68, 68, 0.2); border-color:#ef4444; opacity:1;";
                         badgeIcon = ' ' + SVG_CROSS;
                       } else if (isTargetCorrect && !savedAnswer.isCorrect) {
                         btnStyle += " background:rgba(34, 197, 129, 0.15); border-color:#10b981; opacity:1;";
                       }
                       return `<button class="btn btn-outline" disabled data-opt="${esc(opt)}" style="${btnStyle}">${fixDiacritics(safeStr(opt))}${badgeIcon}</button>`;
                     }
                     return `<button class="btn btn-outline" data-opt="${esc(opt)}" style="justify-content:flex-start; text-align:left; padding:14px 18px; font-size:15px; border-radius:8px;" onclick="checkStudyMCQ(this, ${escJS(opt)}, ${escJS(p.answer)}, ${escJS(mcqExpl)}, '${studyKey}')">${fixDiacritics(safeStr(opt))}</button>`;
                   }).join('')}
                 </div>
                 ${restoredExplBox}
               </div>`;
            }
            return html || `<div style="text-align:center; padding:40px; color:var(--text-muted);">No detailed material provided for this page.</div>`;
          }
        });
      });
    }

    pages.push({
      title: isStudent ? t('study.complete') : t('study.preview'),
      icon: "",
      render: () => `<div style="text-align:center; padding:60px 20px;">
      <h2 style="font-size:24px; font-weight:700;">${isStudent ? t('study.ready') : t('study.preview_end')}</h2>
      <p style="color:var(--text-muted); font-size:15px; margin:16px 0 32px;">${isStudent ? t('study.ready_msg') : t('study.preview_msg')}</p>
      ${isStudent ? `<button class="btn btn-primary btn-lg" onclick="launchStudyActivity('${topic.id}', ${escJS(topic.title)})">${t('study.start_practice')}</button>` : ''}
    </div>`
    });

  } catch (e) {
    console.error("Lesson Render Error:", e);
    pages.push({ title: "Error", icon: "", render: () => `<p>Failed to parse lesson content.</p>` });
  }

  const page = pages[pageIdx] || pages[0];
  let pageContentHtml = "";
  try {
    pageContentHtml = page && typeof page.render === 'function' ? page.render() : `<div style="text-align:center; padding:40px; color:var(--text-muted);">No material content found.</div>`;
  } catch (err) {
    console.error("Page Render Execution Error:", err);
    pageContentHtml = `<div style="text-align:center; padding:40px; color:var(--danger);"><p>Failed to render this lesson page.</p></div>`;
  }

  const headerTopicTitle = getLocalizedCurriculumTitle(topic, currentLang);
  const courseLevel = (currentCourse && currentCourse.level) ? currentCourse.level.toUpperCase() : (topic.difficulty ? String(topic.difficulty).toUpperCase() : 'A1');
  let lvlKey = 'A1';
  for (const k of ['C2', 'C1', 'B2', 'B1', 'A2', 'A1']) {
    if (courseLevel.includes(k)) { lvlKey = k; break; }
  }
  const lvlMeta = CEFR_LEVEL_METAS[lvlKey] || CEFR_LEVEL_METAS['A1'];

  container.innerHTML = `
    <div class="study-topic-wrapper">
      <div class="study-topic-header">
        <div>
          <div class="study-breadcrumb-pill">
            <span class="cefr-level-badge" style="background:${lvlMeta.color}22; color:${lvlMeta.color}; border:1px solid ${lvlMeta.color}55;">${currentLang === 'tr' ? lvlMeta.name_tr : lvlMeta.name}</span>
            <span class="study-badge-divider">•</span>
            <span class="study-badge-tag">${esc(headerTopicTitle)}</span>
            <span class="study-badge-divider">•</span>
            <span class="study-badge-page"><span data-i18n="page">${currentLang === 'tr' ? 'SAYFA' : 'PAGE'}</span> ${pageIdx + 1}/${pages.length}</span>
          </div>
          <h1 class="study-page-heading">${page.icon ? page.icon + ' ' : ''}${page.title}</h1>
          <div class="cefr-level-subtitle">${currentLang === 'tr' ? lvlMeta.focus_tr : lvlMeta.focus}</div>
        </div>
        <div style="display:flex; gap:10px; flex-shrink:0; align-items:center;">
          ${pageIdx > 0 ? `<button class="btn btn-outline btn-sm" onclick="showStudyTopic('${topicId}', ${pageIdx - 1})">← ${t('study.back')}</button>` : ''}
          ${pageIdx < pages.length - 1 ? `<button class="btn btn-primary btn-sm" onclick="showStudyTopic('${topicId}', ${pageIdx + 1})">${t('study.next')} →</button>` : ''}
        </div>
      </div>
      <div class="study-card">
        ${pageContentHtml}
      </div>
      <div class="study-pills-footer">
        ${pages.map((p, i) => `
          <button 
            type="button"
            class="study-pill-btn"
            onclick="showStudyTopic('${topicId}', ${i})"
            title="${esc(p.title || ((t('page') || 'Page') + ' ' + (i + 1)))}"
            aria-label="Go to page ${i + 1}"
          >
            <span class="study-pill ${i === pageIdx ? 'active' : ''}"></span>
          </button>
        `).join('')}
      </div>
    </div>
  `;

  // Reset scroll to top of the study card on page navigation, unless preserving scroll
  if (!options || !options.preserveScroll) {
    const studyCardEl = container.querySelector('.study-card');
    if (studyCardEl) {
      studyCardEl.scrollTop = 0;
    }
  }

  // Preload TTS immediately for all foreign words on this page
  const _ttsWords = [];
  container.querySelectorAll('.foreign-word').forEach(el => {
    const w = el.textContent.trim().replace(/^"|"$/g, '');
    if (w.length > 0 && w.length < 80) _ttsWords.push(w);
  });
  if (_ttsWords.length > 0) preloadTTS(_ttsWords);
}


function checkStudyMCQ(btn, selected, correct, explanation, pageKey) {
    const parent = btn.parentElement;
    const buttons = parent.querySelectorAll('button');
    buttons.forEach(b => {
        b.disabled = true;
        b.style.opacity = '0.75';
    });

    const isCorrect = (selected === correct);
    if (pageKey) {
      _answeredQuestionsState[pageKey] = {
        type: 'study_mcq',
        selected,
        correct,
        explanation,
        isCorrect
      };
    } else {
      const tId = localStorage.getItem('aula_last_topic') || 'unknown';
      const pIdx = localStorage.getItem('aula_last_page') || '0';
      _answeredQuestionsState[`study_${tId}_${pIdx}`] = {
        type: 'study_mcq',
        selected,
        correct,
        explanation,
        isCorrect
      };
    }

    if (isCorrect) {
        btn.style.background = 'rgba(34, 197, 94, 0.2)';
        btn.style.borderColor = '#22c55e';
        btn.style.opacity = '1';
        btn.innerHTML += ' ' + SVG_CHECK;
    } else {
        btn.style.background = 'rgba(239, 68, 68, 0.2)';
        btn.style.borderColor = '#ef4444';
        btn.style.opacity = '1';
        btn.innerHTML += ' ' + SVG_CROSS;
        
        // Highlight correct one
        buttons.forEach(b => {
            if (b.getAttribute('data-opt') === correct) {
                b.style.background = 'rgba(34, 197, 129, 0.15)';
                b.style.borderColor = '#10b981';
                b.style.opacity = '1';
            }
        });
    }
    
    if (explanation) {
        const expDiv = document.createElement('div');
        expDiv.className = 'study-explanation-box';
        expDiv.style.marginTop = '20px';
        expDiv.style.padding = '16px 20px';
        expDiv.style.background = 'rgba(255,255,255,0.04)';
        expDiv.style.borderRadius = '12px';
        expDiv.style.border = '1px solid var(--border)';
        expDiv.style.fontSize = '15px';
        expDiv.style.lineHeight = '1.6';
        expDiv.style.whiteSpace = 'pre-wrap';
        expDiv.style.color = 'var(--text-primary)';
        const explLabel = currentLang === 'tr' ? 'Açıklama' : 'Explanation';
        const isAlreadyTr = (currentLang === 'tr') && (/[çğıöşüÇĞİÖŞÜ]/.test(explanation) || explanation.includes('doğru') || explanation.includes('çünkü') || explanation.includes('ifade'));
        const translatedExplanation = (currentLang === 'tr') ? (isAlreadyTr ? explanation : (typeof translateEducationalText === 'function' ? translateEducationalText(explanation) : explanation)) : explanation;
        expDiv.innerHTML = `<div style="font-weight:700; color:var(--accent-light); margin-bottom:6px; display:flex; align-items:center; gap:6px;"><span>${explLabel}</span></div>${fixDiacritics(translatedExplanation)}`;
        (parent.parentElement || parent).appendChild(expDiv);
    }
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
  if (!currentUser || !currentUser.id) return;
  const res = await api(`/student/enrollments?student_id=${currentUser.id}`);
  if (res && !res.error) {
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
        <div style="margin-bottom:16px;">${SVG_SCHOOL}</div>
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
          <div class="classroom-icon">${SVG_ACADEMIC}</div>
          <div class="classroom-status ${enr.status}">${enr.status === 'approved' ? t('approved') : t('pending')}</div>
        </div>
        <div class="classroom-card-body">
          <h3 class="classroom-name">${esc(enr.course_name)}</h3>
          <div class="classroom-meta">${enr.language || 'Language'} • ${enr.level || 'Level'}</div>
        </div>
        <div class="classroom-card-footer">
          <div class="classroom-code">#${enr.course_code}</div>
          <div class="classroom-arrow">→</div>
        </div>
      </div>
    </div>
  `).join('');
  applyTranslations(grid);
}

function openJoinClassroomModal() {
  document.getElementById('join-classroom-modal').classList.remove('hidden');
  const input = document.getElementById('join-class-code');
  if (input) {
    input.value = '';
    setTimeout(() => input.focus(), 50);
  }
}

function closeJoinClassroomModal() {
  document.getElementById('join-classroom-modal').classList.add('hidden');
}

async function handleJoinClassroom() {
  const codeInput = document.getElementById('join-class-code');
  const code = codeInput ? codeInput.value.trim() : '';
  if (!code || code.length < 5) {
    showAlert(t('missing_info'), t('student.enter_code'), true);
    return;
  }

  const submitBtn = document.querySelector('#join-classroom-modal button.btn-primary');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = '...';
  }

  try {
    const res = await api('/student/join', {
      method: 'POST',
      body: { student_id: currentUser.id, code: code }
    });

    if (res.error) {
      showAlert(t('error'), res.error, true);
    } else {
      closeJoinClassroomModal();
      if (res.enrollments) {
        currentStudentEnrollments = res.enrollments;
        renderStudentPortal();
      } else {
        await refreshStudentEnrollments();
      }

      if (res.status === 'pending' && res.course_id) {
        showScreen('waiting-room-screen');
        startWaitingRoomPoll(res.course_id);
      } else if (res.status === 'approved' && res.course_id) {
        await enterStudentClassroom(res.course_id);
      }
    }
  } catch (err) {
    showAlert(t('error'), err.message || 'Failed to join classroom', true);
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.setAttribute('data-i18n', 'student.join_btn');
      submitBtn.textContent = t('student.join_btn') || 'Join Classroom';
    }
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

  stopLiveSync();
  currentUser.role = 'student';
  await selectClassroom(courseId, false);
}

function showPinModal(mode, courseId) {
  // Deprecated: PIN system removed
  selectClassroom(courseId, false);
}

function closePinModal() {
  const modal = document.getElementById('pin-entry-modal');
  if (modal) modal.classList.add('hidden');
}

async function handleSetPin(courseId, pin) {
  closePinModal();
  await selectClassroom(courseId, false);
}

async function handleVerifyPin(courseId, pin) {
  closePinModal();
  stopLiveSync();
  currentUser.role = 'student';
  await selectClassroom(courseId, false);
}

function startWaitingRoomPoll(courseId) {
  if (window._waitingPoll) clearInterval(window._waitingPoll);
  // Persist the target course so that after the approval-triggered reload the
  // student is automatically taken into the classroom (not left at the portal).
  if (courseId) localStorage.setItem('aula_last_course', courseId);
  window._waitingPoll = setInterval(async () => {
    try {
      const check = await api('/user/status?user_id=' + currentUser.id + '&course_id=' + courseId);
      if (check && check.status === 'approved') {
        clearInterval(window._waitingPoll);
        window._waitingPoll = null;
        currentUser.status = 'approved';
        localStorage.setItem('aula_user', JSON.stringify(currentUser));
        sessionStorage.setItem('aula_user', JSON.stringify(currentUser));
        // aula_last_course already set above — reload will send the student
        // straight into the classroom via selectClassroom().
        window.location.reload();
      } else if (check && (check.error === 'enrollment_removed' || check.error === 'course_deleted')) {
        clearInterval(window._waitingPoll);
        window._waitingPoll = null;
        localStorage.removeItem('aula_last_course');
        await showAlert(t('alert.classroom_reset'), t('alert.classroom_reset_msg'), true);
        showScreen('student-portal-screen');
        refreshStudentEnrollments();
      }
    } catch (e) { /* ignore network errors */ }
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
  if (!currentUser || currentUser.email !== 'atunca96@gmail.com') return;
  const email = currentUser ? currentUser.email : '';
  if (!email) return;

  const confirmed = await showConfirmModal('confirm.erase_all_title', 'confirm.hard_delete_msg', true, 'HARD DELETE EVERYTHING');
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

// ── Admin: All Students Panel ──

let _lastAdminStudentsData = null;

function renderAdminStudentPanelSync(students) {
  const panel = document.getElementById('admin-students-panel');
  if (!panel || !students) return;
  panel.classList.remove('hidden');

  const lang = currentLang || localStorage.getItem('aula_lang') || 'tr';
  const stateSignature = (students || []).map(s => `${s.id}:${s.is_active}:${s.status}:${s.course_count}:${s.total_responses}`).join('|') + lang;
  if (panel.dataset.hash === stateSignature) return; // Skip re-render if nothing changed
  panel.dataset.hash = stateSignature;

  if (students.length === 0) {
    panel.innerHTML = `
      <div style="padding:24px; border:1px solid var(--border); border-radius:16px; background:rgba(255,255,255,0.02);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
          <h3 style="margin:0; font-size:18px; display:inline-flex; align-items:center; gap:6px;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width:18px; height:18px; stroke-width:2px;"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>${t('admin.all_students')}</h3>
        </div>
        <p style="color:var(--text-muted); text-align:center; padding:20px;">${t('admin.no_students')}</p>
      </div>`;
    return;
  }

  const rows = students.map(s => {
    const schoolNum = s.email && s.email.includes('@student.aulaai') ? s.email.split('@')[0] : s.email;
    const isPermanent = Boolean(s.is_permanent || PERMANENT_STUDENT_NUMBERS.includes(schoolNum) || PERMANENT_STUDENT_NUMBERS.includes(String(s.id || '').replace('student-', '')));

    let isOnline = false;
    if (s.is_active !== undefined) {
      isOnline = Boolean(s.is_active);
    } else if (s.last_seen) {
      const lastSeen = new Date(s.last_seen.replace(' ', 'T') + 'Z').getTime();
      const now = new Date().getTime();
      if (now - lastSeen < 12 * 1000) isOnline = true;
    }

    const statusBadge = isOnline 
      ? `<span style="background:rgba(34,197,94,0.15); color:#22c55e; padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600; display:inline-flex; align-items:center; gap:5px;"><span style="width:6px; height:6px; border-radius:50%; background:#22c55e; display:inline-block; box-shadow:0 0 8px #22c55e;"></span>${t('admin.active')}</span>`
      : (s.status === 'pending'
         ? `<span style="background:rgba(234,179,8,0.15); color:#eab308; padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;">${t('admin.pending')}</span>`
         : `<span style="background:rgba(156,163,175,0.1); color:#9ca3af; padding:2px 8px; border-radius:6px; font-size:11px; font-weight:600;">${t('admin.inactive')}</span>`);

    const enrollmentList = s.enrolled_in ? s.enrolled_in.split(',').join(', ') : '—';

    const removeBtn = !isPermanent
      ? `<button class="btn btn-sm" style="background:var(--danger-bg); color:var(--danger); border:1px solid var(--danger); padding:4px 10px; border-radius:var(--radius-sm); font-size:11px;" onclick="event.stopPropagation(); adminKickStudent('${s.id}', ${escJS(s.name)})">${t('admin.remove')}</button>`
      : '';

    return `
      <tr style="border-bottom:1px solid var(--border);">
        <td style="padding:12px 16px; font-weight:600; color:var(--text-primary);">${esc(s.name)}</td>
        <td style="padding:12px 16px; color:var(--text-muted); font-family:monospace; font-size:13px;">${esc(schoolNum)}</td>
        <td style="padding:12px 16px; color:var(--text-muted); font-size:13px; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${esc(enrollmentList)}</td>
        <td style="padding:12px 16px; text-align:center; font-weight:600; color:var(--accent-light);">${s.total_responses || 0}</td>
        <td style="padding:12px 16px; text-align:center;">${statusBadge}</td>
        <td style="padding:12px 16px; text-align:right; display:flex; gap:6px; justify-content:flex-end; align-items:center;">
          <button class="btn btn-sm" style="background:var(--accent-glow); color:var(--accent); border:1px solid var(--accent); padding:4px 10px; border-radius:var(--radius-sm); font-size:11px;" onclick="event.stopPropagation(); adminSetStudentPassword('${s.id}', ${escJS(s.name)}, '${schoolNum}')">${t('admin.set_password')}</button>
          <button class="btn btn-sm" style="background:var(--warning-bg); color:var(--warning); border:1px solid var(--warning); padding:4px 10px; border-radius:var(--radius-sm); font-size:11px;" onclick="event.stopPropagation(); adminResetStudentProgress('${s.id}', ${escJS(s.name)})">${t('admin.reset_progress')}</button>
          ${removeBtn}
        </td>
      </tr>`;
  }).join('');

  panel.innerHTML = `
    <div style="padding:24px; border:1px solid var(--border); border-radius:16px; background:rgba(255,255,255,0.02);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:12px;">
        <h3 style="margin:0; font-size:18px; display:inline-flex; align-items:center; gap:6px;"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width:18px; height:18px; stroke-width:2px;"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>${t('admin.all_students')} <span style="font-size:14px; color:var(--text-muted); font-weight:400;">(${students.length})</span></h3>
        <div style="display:flex; gap:8px; align-items:center;">
          <button class="btn btn-sm btn-primary" style="padding:6px 14px; border-radius:8px; font-size:12px; font-weight:600; display:inline-flex; align-items:center; gap:4px;" onclick="adminOpenCreateStudentModal()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width:14px; height:14px; stroke-width:2px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>${t('admin.add_student')}</button>
        </div>
      </div>
      <div style="overflow-x:auto; border-radius:12px; border:1px solid var(--border);">
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
          <thead>
            <tr style="background:rgba(255,255,255,0.03); border-bottom:2px solid var(--border);">
              <th style="padding:10px 16px; text-align:left; font-weight:700; color:var(--text-muted); font-size:11px; text-transform:uppercase; letter-spacing:1px;">${t('admin.student_name')}</th>
              <th style="padding:10px 16px; text-align:left; font-weight:700; color:var(--text-muted); font-size:11px; text-transform:uppercase; letter-spacing:1px;">${t('admin.student_id')}</th>
              <th style="padding:10px 16px; text-align:left; font-weight:700; color:var(--text-muted); font-size:11px; text-transform:uppercase; letter-spacing:1px;">${t('admin.enrolled_in')}</th>
              <th style="padding:10px 16px; text-align:center; font-weight:700; color:var(--text-muted); font-size:11px; text-transform:uppercase; letter-spacing:1px;">${t('admin.responses')}</th>
              <th style="padding:10px 16px; text-align:center; font-weight:700; color:var(--text-muted); font-size:11px; text-transform:uppercase; letter-spacing:1px;">${t('admin.status')}</th>
              <th style="padding:10px 16px; text-align:right; font-weight:700; color:var(--text-muted); font-size:11px; text-transform:uppercase; letter-spacing:1px;">${t('admin.action')}</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

async function loadAdminStudentPanel(isRefresh = false) {
  const panel = document.getElementById('admin-students-panel');
  if (!panel) return;
  panel.classList.remove('hidden');

  // Immediately render cached data without network lag
  if (_lastAdminStudentsData) {
    renderAdminStudentPanelSync(_lastAdminStudentsData);
  } else if (!isRefresh && !panel.innerHTML.trim()) {
    panel.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-muted);">${t('loading')}</div>`;
  }

  try {
    const students = await api('/admin/all-students');
    _lastAdminStudentsData = students;
    renderAdminStudentPanelSync(students);
  } catch (e) {
    console.error("Admin Panel Error:", e);
    if (!panel.innerHTML.trim()) {
      panel.innerHTML = `<div style="padding:20px; color:var(--danger); text-align:center;">${t('error')}</div>`;
    }
  }
}

async function adminResetStudentPIN(sid, name) {
  const confirmed = await showConfirmModal('confirm.reset_pin_title', 'confirm.reset_pin_msg', true, null, false, 'ok', 'cancel', { name });
  if (confirmed) {
    await api('/admin/reset-student-pin', { method: 'POST', body: { student_id: sid } });
    showAlert('success', 'alert.pin_reset_success', false);
    loadAdminStudentPanel(true);
  }
}

async function adminResetStudentProgress(sid, name) {
  const confirmed = await showConfirmModal('confirm.reset_progress_title', 'confirm.reset_progress_msg', true, null, false, 'ok', 'cancel', { name });
  if (confirmed) {
    await api('/admin/reset-student-progress', { method: 'POST', body: { student_id: sid } });
    showAlert('success', 'alert.progress_reset_success', false);
    loadAdminStudentPanel(true);
  }
}

async function adminKickStudent(sid, name) {
  const isPerm = PERMANENT_STUDENT_NUMBERS.includes(String(sid || '').replace('student-', ''));
  if (isPerm) {
    showAlert('cancel', 'Permanent students cannot be removed.', true);
    return;
  }
  const confirmed = await showConfirmModal('confirm.kick_student_title', 'confirm.kick_student_msg', true, null, false, 'ok', 'cancel', { name });
  if (confirmed) {
    const res = await api('/student/delete', { method: 'POST', body: { student_id: sid } });
    if (res && res.error) {
      showAlert('cancel', res.error, true);
    } else {
      loadAdminStudentPanel(true);
    }
  }
}

async function adminResetStudents() {
  const confirmed1 = await showConfirmModal('confirm.erase_all_title', 'admin.reset_students_confirm', true);
  if (!confirmed1) return;

  const typed = await showConfirmModal('confirm.erase_all_title', 'admin.reset_students_type', true, 'RESET ALL STUDENTS');
  if (typed !== 'RESET ALL STUDENTS') return;

  try {
    const res = await api('/admin/reset-students', {
      method: 'POST',
      body: { confirm: 'RESET ALL STUDENTS' }
    });

    if (res.success) {
      await showAlert('success', t('admin.students_removed', { count: res.deleted }));
      loadAdminStudentPanel();
    } else {
      showAlert(t('error'), res.error || 'Reset failed.', true);
    }
  } catch (e) {
    showAlert(t('error'), 'Network error during reset.', true);
  }
}

async function adminSetStudentPassword(sid, name, studentNum) {
  const newPassword = await showConfirmModal(
    'admin.set_password',
    'admin.enter_new_password_for',
    false,
    '••••••••',
    false,
    'ok',
    'cancel',
    { name: name || studentNum }
  );
  if (newPassword && newPassword.trim()) {
    try {
      const res = await api('/admin/set-student-password', {
        method: 'POST',
        body: { student_id: sid, student_number: studentNum, password: newPassword.trim() }
      });
      if (res && res.success) {
        await showAlert('success', 'admin.password_set_success', false);
      } else {
        await showAlert(t('error'), res.error || 'Failed to update password', true);
      }
    } catch (err) {
      await showAlert(t('error'), err.message || 'Error updating password', true);
    }
  }
}

async function adminOpenCreateStudentModal() {
  const studentNum = await showConfirmModal(
    'admin.add_student',
    'admin.enter_student_number',
    false,
    'e.g. 2023002',
    false
  );
  if (!studentNum || !studentNum.trim()) return;

  const studentName = await showConfirmModal(
    'admin.add_student',
    'admin.enter_student_name',
    false,
    'e.g. Maria Gonzalez',
    false,
    'ok',
    'cancel',
    { number: studentNum.trim() }
  );
  if (!studentName || !studentName.trim()) return;

  const password = await showConfirmModal(
    'admin.add_student',
    'admin.enter_student_pwd',
    false,
    'e.g. student123',
    false,
    'ok',
    'cancel',
    { name: studentName.trim() }
  );
  if (!password || !password.trim()) return;

  try {
    const res = await api('/admin/create-student', {
      method: 'POST',
      body: {
        student_number: studentNum.trim(),
        name: studentName.trim(),
        password: password.trim()
      }
    });
    if (res && res.success) {
      await showAlert('success', 'admin.student_created_success', false);
      loadAdminStudentPanel(true);
    } else {
      await showAlert(t('error'), res.error || 'Failed to create student', true);
    }
  } catch (err) {
    await showAlert(t('error'), err.message || 'Error creating student', true);
  }
}

// ── AulaAI Global Dictionary Logic ──

let activeDictWord = "";

// 3. Single-Click Trigger for Dictionary (Disabled per user request)
const handleDictTrigger = async (e) => {
  return; // Tap to translate disabled
};

window.addEventListener('click', handleDictTrigger);

// Tap-Detector to distinguish between scrolling and tapping
let touchStartX = 0;
let touchStartY = 0;

window.addEventListener('touchstart', (e) => {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
    
    // Instant Open for words (but NOT for TTS buttons)
    if (!e.target.closest('.tts-btn') && (e.target.closest('.foreign-word') || e.target.closest('#aula-dict-popup'))) {
        handleDictTrigger(e);
    }
}, { passive: true });

window.addEventListener('touchend', (e) => {
    const touchEndX = e.changedTouches[0].clientX;
    const touchEndY = e.changedTouches[0].clientY;
    
    // Calculate distance to determine if it was a scroll or a tap
    const distance = Math.sqrt(Math.pow(touchEndX - touchStartX, 2) + Math.pow(touchEndY - touchStartY, 2));
    
    const popup = document.getElementById('aula-dict-popup');
    const isOpen = popup && popup.style.display === 'block';

    // If it was a stationary tap (distance < 10px) outside the popup and not on the trigger word, close it
    if (isOpen && distance < 10 && !popup.contains(e.target) && !e.target.closest('.foreign-word')) {
        closeDict();
    }
}, { passive: true });

async function showDict(word, e) {
  const popup = document.getElementById('aula-dict-popup');
  const content = document.getElementById('dict-content');
  const loading = document.getElementById('dict-loading');

  activeDictWord = word;
  const isMobile = window.innerWidth <= 768;

  // Show and prepare for positioning
  popup.style.display = 'block';
  popup.style.position = isMobile ? 'fixed' : 'absolute';
  
  const popupWidth = Math.min(520, window.innerWidth - 32);

  let left, top;
  if (isMobile) {
    // Center on mobile
    left = (window.innerWidth - popupWidth) / 2;
    top = Math.max(80, window.innerHeight / 2 - 200); // Higher than center for better thumb access
  } else {
    // Position near click on PC
    left = e.pageX - popupWidth / 2;
    top = e.pageY + 20;
    
    // Bounds check
    if (left < 16) left = 16;
    if (left + popupWidth > window.innerWidth - 16) left = window.innerWidth - popupWidth - 16;
  }

  popup.style.left = `${left}px`;
  popup.style.top = `${top}px`;

  content.style.display = 'none';
  loading.style.display = 'block';

  try {
    let lang = 'English';
    if (currentCourse && currentCourse.language) {
      lang = currentCourse.language;
    } else {
      const loginScreen = document.getElementById('login-screen');
      if (loginScreen && !loginScreen.classList.contains('hidden')) {
        lang = window.currentDemoLang || 'Spanish';
      }
    }
    // Pass the current study topic as context so the AI doesn't contradict lesson material
    const topicTitle = localStorage.getItem('aula_last_topic_title') || '';
    let dictUrl = `/dictionary?word=${encodeURIComponent(word)}&lang=${lang}&ui_lang=${currentLang}`;
    if (topicTitle) dictUrl += `&context=${encodeURIComponent(topicTitle)}`;
    const res = await api(dictUrl);

    window._lastDictRes = res;
    window._lastDictWord = word;
    window._lastDictLang = lang;

    loading.style.display = 'none';
    content.style.display = 'block';
    renderDictContent(word, lang, res);
  } catch (err) {
    console.error("Dict error:", err);
    // Show silent error in popup
    loading.style.display = 'none';
    content.style.display = 'block';
    content.innerHTML = `
        <div style="position:relative; text-align:center; padding:20px;">
            <button onclick="closeDict()" style="position:absolute; top:-10px; right:-10px; background:rgba(255,255,255,0.1); border:none; color:#fff; width:32px; height:32px; border-radius:50%; cursor:pointer; font-size:20px; display:flex; align-items:center; justify-content:center;">&times;</button>
            <div style="margin-bottom:12px;">${SVG_WARNING}</div>
            <div style="color:var(--danger); font-size:14px;">${currentLang === 'tr' ? 'Sözlük servisine erişilemiyor.' : 'Dictionary service unavailable.'}</div>
            <button class="btn btn-sm btn-ghost" style="margin-top:12px;" onclick="closeDict()">${currentLang === 'tr' ? 'Kapat' : 'Close'}</button>
        </div>
    `;
  }
}

function renderDictContent(word, lang, res) {
  const content = document.getElementById('dict-content');
  if (!content || !res) return;
  const isTr = currentLang === 'tr';
  const rawExplanation = (isTr && res.explanation_tr) ? res.explanation_tr : (res.explanation || (res.definitions ? res.definitions[0].definition : (isTr ? "Tanım bulunamadı." : "No definition found.")));
  const explanation = translateDictExplanation(rawExplanation, isTr);
  const rawUsage = (isTr && res.usage_tr) ? res.usage_tr : (res.usage || (isTr ? "Günlük konuşmada kullanın." : "Use it in daily conversation."));
  const usage = translateEducationalText(rawUsage);
  const rawTip = (isTr && res.tip_tr) ? res.tip_tr : (res.tip || (isTr ? 'Ayrıntılı bilgi için sınıftaki ders materyallerine başvurun.' : 'Refer to classroom materials for more context.'));
  const tip = translateEducationalText(rawTip);
  const displayLang = translateCourseName(lang.split('(')[0].trim(), currentLang);
  const cleanLang = lang.split('(')[0].trim();
  const fontSize = word.length > 16 ? (word.length > 28 ? '18px' : '22px') : '28px';

  content.innerHTML = `
    <div style="position:relative;">

      <!-- Header: Word + Close -->
      <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:10px; margin-bottom:16px;">
        <div style="flex:1; min-width:0;">
          <div style="font-size:${fontSize}; font-weight:900; letter-spacing:-0.5px; line-height:1.2; word-break:break-word;
            background:linear-gradient(135deg, #ffffff 0%, var(--accent-light) 100%);
            -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;">
            ${word}
          </div>
          <div style="display:flex; align-items:center; gap:8px; margin-top:6px;">
            <span style="display:inline-flex; align-items:center; gap:4px; padding:2px 8px; border-radius:20px;
              background:rgba(99,102,241,0.15); border:1px solid rgba(99,102,241,0.3);
              font-size:10px; font-weight:700; color:var(--accent-light); text-transform:uppercase; letter-spacing:0.8px;">
              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
              ${displayLang}
            </span>
            <button class="tts-btn" onclick="handleTTSClick(this, ${escJS(word)}, '${cleanLang}', event)" title="${isTr ? 'Dinle' : 'Listen'}" style="flex-shrink:0;">${TTS_SVG_IDLE}</button>
          </div>
        </div>
        <button onclick="closeDict()" style="flex-shrink:0; background:rgba(255,255,255,0.07); border:1px solid rgba(255,255,255,0.1); color:rgba(255,255,255,0.6); width:28px; height:28px; border-radius:50%; cursor:pointer; font-size:16px; display:flex; align-items:center; justify-content:center; transition:all 0.15s;" onmouseover="this.style.background='rgba(255,255,255,0.12)'" onmouseout="this.style.background='rgba(255,255,255,0.07)'">&times;</button>
      </div>

      <!-- Divider -->
      <div style="height:1px; background:linear-gradient(90deg, var(--accent) 0%, transparent 100%); margin-bottom:16px; opacity:0.3;"></div>

      <!-- Explanation -->
      <div style="margin-bottom:14px;">
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:7px;">
          <span style="width:3px; height:12px; background:var(--accent); border-radius:2px; display:inline-block;"></span>
          <span style="font-size:9px; font-weight:800; color:var(--accent-light); text-transform:uppercase; letter-spacing:1.2px;">${isTr ? 'Anlam & Açıklama' : 'Meaning & Explanation'}</span>
        </div>
        <div class="ai-explanation" style="font-size:15px; color:var(--text-primary); line-height:1.65;">${explanation}</div>
      </div>

      <!-- Usage -->
      <div style="margin-bottom:14px; padding:12px 14px; border-radius:10px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06);">
        <div style="font-size:9px; font-weight:800; color:var(--accent-light); text-transform:uppercase; letter-spacing:1.2px; margin-bottom:6px;">${isTr ? 'Kullanım Örneği' : 'Usage Example'}</div>
        <div class="english-translation" style="font-style:italic; font-size:14px; color:rgba(255,255,255,0.75); line-height:1.5;">&ldquo;${usage}&rdquo;</div>
      </div>

      <!-- Pro-Tip -->
      <div style="padding:10px 14px; border-radius:10px; background:rgba(99,102,241,0.07); border:1px solid rgba(99,102,241,0.18); margin-bottom:16px;">
        <span style="font-size:9px; font-weight:800; color:var(--accent-light); text-transform:uppercase; letter-spacing:1px;">${isTr ? '💡 İpucu' : '💡 Pro-Tip'}</span>
        <div style="font-size:12px; color:rgba(255,255,255,0.55); line-height:1.5; margin-top:4px;">${tip}</div>
      </div>

      <!-- Footer -->
      <div style="display:flex; justify-content:space-between; align-items:center; padding-top:12px; border-top:1px solid rgba(255,255,255,0.06);">
        <button class="btn btn-ghost btn-sm" style="font-size:10px; padding:5px 11px; border-radius:var(--radius-sm); background:var(--accent-glow); border:1px solid rgba(99,102,241,0.3); color:var(--accent); cursor:pointer; font-weight:700; letter-spacing:0.3px;" onclick="askAiAboutWord()">
          ${isTr ? '✦ Asistan ile Açıkla' : '✦ Explain with Assistant'}
        </button>
        <span style="font-size:9px; color:var(--text-muted); cursor:pointer; font-weight:700; text-transform:uppercase; letter-spacing:1px;" onclick="closeDict()">${isTr ? 'Kapat' : 'Dismiss'}</span>
      </div>

    </div>
  `;
}

function closeDict() {
  const popup = document.getElementById('aula-dict-popup');
  if (popup) {
    popup.style.display = 'none';
    activeDictWord = "";
    window._lastDictWord = null;
    window._lastDictRes = null;
    // Remove highlights
    document.querySelectorAll('.tap-highlight').forEach(el => el.classList.remove('tap-highlight'));
  }
}

// Global click/touch listener handles everything now
async function askAiAboutWord() {
  if (!activeDictWord) return;
  const wordToAsk = activeDictWord;

  const content = document.getElementById('dict-content');
  const loading = document.getElementById('dict-loading');
  const meanings = document.getElementById('dict-meanings');

  // Show Assistant Loading State in the popup
  meanings.innerHTML = `
        <div style="text-align:center; padding:20px;">
            <div class="spinner-small" style="margin:0 auto 12px; border-top-color:var(--accent);"></div>
            <div style="font-size:10px; color:var(--accent); text-transform:uppercase; letter-spacing:2px; font-weight:800;">Searching explanation...</div>
        </div>
    `;

  try {
    const lang = (currentCourse && currentCourse.language) ? currentCourse.language : 'English';
    const courseId = currentCourse ? currentCourse.id : '';
    const res = await api(`/dictionary/ai-explain?word=${encodeURIComponent(wordToAsk)}&lang=${lang}&course_id=${courseId}&ui_lang=${currentLang}`);

    if (res.explanation) {
      meanings.innerHTML = `
                <div style="background:var(--accent-glow); padding:16px; border-radius:var(--radius); border:1px solid var(--border);">
                    <div style="font-size:11px; font-weight:800; color:var(--accent); text-transform:uppercase; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
                        <span>${currentLang === 'tr' ? 'Açıklama' : 'Explanation'}</span>
                    </div>
                    <div style="font-size:14px; color:var(--text-primary); line-height:1.5; margin-bottom:12px;">${res.explanation}</div>
                    
                    <div style="font-size:11px; font-weight:800; color:var(--accent-light); text-transform:uppercase; margin-bottom:4px; opacity:0.7;">Usage</div>
                    <div style="font-size:13px; color:var(--text-secondary); line-height:1.4; margin-bottom:12px; font-style:italic;">"${res.usage}"</div>
                    
                    <div style="background:rgba(255,255,255,0.05); padding:8px 12px; border-radius:var(--radius-sm); font-size:12px; color:var(--text-muted);">
                        <span style="color:var(--accent); font-weight:700;">Academic Note:</span> ${res.tip}
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

// ── Interactive Demo Card Switcher and TTS handler ─────────────────
window.currentDemoLang = 'Spanish';

window.switchDemoLang = function(lang) {
  window.currentDemoLang = lang;
  
  document.querySelectorAll('.sheet-toggle-btn').forEach(btn => {
    btn.classList.remove('active');
    const i18nKey = btn.getAttribute('data-i18n');
    if (i18nKey === 'lang.' + lang) {
      btn.classList.add('active');
    }
  });

  const sentenceEl = document.getElementById('demo-spanish-sentence');
  const transEl = document.getElementById('demo-translated-text');
  
  if (!sentenceEl || !transEl) return;

  if (lang === 'Spanish') {
    sentenceEl.innerHTML = `<span class="foreign-word">Hola</span>, ¿<span class="foreign-word">cómo</span> <span class="foreign-word">estás</span> <span class="foreign-word">hoy</span>?`;
    transEl.setAttribute('data-i18n', 'hero.demo_es_trans');
    transEl.textContent = t('hero.demo_es_trans');
  } else if (lang === 'German') {
    sentenceEl.innerHTML = `<span class="foreign-word">Hallo</span>, <span class="foreign-word">wie</span> <span class="foreign-word">geht</span> <span class="foreign-word">es</span> <span class="foreign-word">dir</span> <span class="foreign-word">heute</span>?`;
    transEl.setAttribute('data-i18n', 'hero.demo_de_trans');
    transEl.textContent = t('hero.demo_de_trans');
  } else if (lang === 'French') {
    sentenceEl.innerHTML = `<span class="foreign-word">Bonjour</span>, <span class="foreign-word">comment</span> <span class="foreign-word">ça</span> <span class="foreign-word">va</span> <span class="foreign-word">aujourd'hui</span>?`;
    transEl.setAttribute('data-i18n', 'hero.demo_fr_trans');
    transEl.textContent = t('hero.demo_fr_trans');
  }
};

window.handleDemoTTS = function(btn) {
  const sentenceEl = document.getElementById('demo-spanish-sentence');
  if (!sentenceEl) return;
  const text = sentenceEl.innerText.trim();
  const lang = window.currentDemoLang || 'Spanish';
  handleTTSClick(btn, text, lang);
};
