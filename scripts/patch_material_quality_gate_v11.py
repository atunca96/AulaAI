from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
ai_path = root / 'services' / 'ai_engine.py'
bi_path = root / 'services' / 'bilingual_finisher.py'
app_path = root / 'public' / 'js' / 'app.js'
pdf_path = root / 'services' / 'pdf_renderer_v12.py'


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 anchor, found {count}')
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 1) Generation quality gate: self-contained MCQs + strict bilingual UI data
# ---------------------------------------------------------------------------
ai = ai_path.read_text(encoding='utf-8')
anchor = '''   - Do NOT systematically put the correct answer first. Vary the correct option position across questions; post-processing may also reorder options while preserving index alignment.\n'''
insert = anchor + '''   - SELF-CONTAINED QUESTION RULE: every MCQ must contain ALL information needed to answer it inside the prompt and options. Never emit a stem such as "Complete the sentence", "Choose the correct conjugation", "Choose the reflexive pronoun", etc. without the actual sentence, subject, blank, or scenario. A student must be able to solve the question when seeing that MCQ alone.\n   - ANSWER CONSISTENCY RULE: `answer`, `correct_index`, and `explanation` must identify the SAME option. Before returning JSON, verify `options[correct_index] == answer`, exactly one option is defensibly correct, and the explanation explicitly supports that same answer without contradicting it.\n   - UI LOCALIZATION COMPLETENESS: all learner-facing explanatory/meta-language strings must be complete in English and Turkish before the lesson is returned. This includes page titles, intros/text/explanations, rule titles and rule explanations, analyses/notes, vocabulary explanations, dialogue translations, MCQ prompts/explanations, and meta-language option labels. Never leave an English instructional explanation as the Turkish display value or vice versa. Target-language words/sentences being taught must remain unchanged.\n'''
ai = replace_once(ai, anchor, insert, 'generation quality rules')

# Strengthen beginner pedagogy beyond the previous CEFR convergence rule.
cefr_anchor = '''- For A1-A2, use short concrete learner-facing explanations, one main idea at a time, and everyday examples. Avoid specialist linguistic metalanguage beyond the learner's level; if a technical term is necessary, explain it immediately in plain language. For B1-B2, use moderate terminology with plain-language support. C1-C2 may use advanced metalanguage when it genuinely improves precision.\n'''
cefr_new = '''- For A1-A2, use short concrete learner-facing explanations, one main idea at a time, and everyday examples. Avoid specialist linguistic metalanguage beyond the learner's level; if a technical term is necessary, explain it immediately in plain language. For A1 specifically, prefer plain descriptions such as "the vowel changes" or "the word shortens before a masculine noun" instead of labels such as apocope, oxytone/aguda, null-subject/pro-drop, univerbation, phoneme, allomorph, morphophonology, or similar specialist terminology. Never make A1 depth depend on jargon. For B1-B2, use moderate terminology with plain-language support. C1-C2 may use advanced metalanguage when it genuinely improves precision.\n'''
ai = replace_once(ai, cefr_anchor, cefr_new, 'A1 plain-language rule')
ai_path.write_text(ai, encoding='utf-8')


# ---------------------------------------------------------------------------
# 2) Bilingual finalizer: recursively fill UI-language fields in one pass
# ---------------------------------------------------------------------------
bi = bi_path.read_text(encoding='utf-8')
collect_anchor = '''    # 2. Batch translate everything missing\n'''
helper = r'''    # Complete nested learner-facing UI strings too. This closes the historical
    # gap where page text was translated but rule/analysis/note fields could remain English.
    UI_LOCALIZABLE_KEYS = {
        'title', 'text', 'explanation', 'intro', 'description', 'instructions',
        'rule', 'analysis', 'note', 'context', 'breakdown', 'label', 'hint'
    }

    def _collect_nested_ui_strings(node):
        if isinstance(node, list):
            for child in node:
                _collect_nested_ui_strings(child)
            return
        if not isinstance(node, dict):
            return
        for key, value in list(node.items()):
            if key in UI_LOCALIZABLE_KEYS and isinstance(value, str) and value.strip():
                tr_key = key + '_tr'
                existing = node.get(tr_key)
                if not existing or str(existing).strip() == value.strip():
                    to_translate_to_tr.append(value.strip())
            if isinstance(value, (dict, list)):
                _collect_nested_ui_strings(value)

    for _tid, _ttitle, _content in topic_data_list:
        _collect_nested_ui_strings(_content)

'''
bi = replace_once(bi, collect_anchor, helper + collect_anchor, 'nested bilingual collection')

apply_anchor = '''            # Save enriched bilingual content\n'''
apply_helper = r'''            # Apply any still-missing nested UI translations. Never touch target-language
            # content such as term/example/answer/options; only explanatory/meta-language keys.
            def _apply_nested_ui_strings(node):
                if isinstance(node, list):
                    for child in node:
                        _apply_nested_ui_strings(child)
                    return
                if not isinstance(node, dict):
                    return
                for key, value in list(node.items()):
                    if key in UI_LOCALIZABLE_KEYS and isinstance(value, str) and value.strip():
                        tr_key = key + '_tr'
                        existing = node.get(tr_key)
                        if not existing or str(existing).strip() == value.strip():
                            translated = trans_map.get(value.strip())
                            if translated and translated.strip() and translated.strip() != value.strip():
                                node[tr_key] = translated.strip()
                    if isinstance(value, (dict, list)):
                        _apply_nested_ui_strings(value)

            _apply_nested_ui_strings(content)

            # Deterministic MCQ integrity repair. If the explanation quotes exactly one
            # canonical option, that quoted option is authoritative. This fixes stale
            # answer/correct_index disagreements without a second AI verifier call.
            for _page in content.get('pages', []) if isinstance(content.get('pages', []), list) else []:
                if not isinstance(_page, dict):
                    continue
                _opts = _page.get('options') if isinstance(_page.get('options'), list) else []
                if len(_opts) < 2:
                    continue
                _opts = [str(x).strip() for x in _opts]
                _ans = str(_page.get('answer') or '').strip()
                _expl = str(_page.get('explanation') or _page.get('explanation_tr') or '').strip()
                _quoted = []
                if _expl:
                    for _opt in _opts:
                        if not _opt:
                            continue
                        _patterns = [f"'{_opt}'", f'"{_opt}"', f'«{_opt}»', f'“{_opt}”']
                        if any(_pat in _expl for _pat in _patterns):
                            _quoted.append(_opt)
                if len(_quoted) == 1 and _quoted[0] != _ans:
                    _ans = _quoted[0]
                    _page['answer'] = _ans
                if _ans in _opts:
                    _page['correct_index'] = _opts.index(_ans)
                    _page['distractors'] = [x for x in _opts if x != _ans]

'''
bi = replace_once(bi, apply_anchor, apply_helper + apply_anchor, 'nested bilingual apply and MCQ integrity')
bi_path.write_text(bi, encoding='utf-8')


# ---------------------------------------------------------------------------
# 3) Frontend: Turkish UI never falls back visibly to English pedagogy text
# ---------------------------------------------------------------------------
app = app_path.read_text(encoding='utf-8')
strict_helper_anchor = '''function resolveItemExplanation(it, term, translation, lang = currentLang) {\n'''
strict_helper = r'''function _looksLikeEnglishInstructionalText(value) {
  if (!value || typeof value !== 'string') return false;
  const s = value.trim();
  if (!s) return false;
  if (/[çğıöşüÇĞİÖŞÜ]/.test(s)) return false;
  const words = s.toLowerCase().match(/[a-z]+/g) || [];
  if (words.length < 3) return false;
  const markers = new Set(['the','a','an','is','are','to','of','and','or','like','with','before','after','pronounced','sound','letter','word','used','means','identical','voiced','voiceless','vowel','consonant','stop','fricative','choose','select','complete']);
  return words.filter(w => markers.has(w)).length >= 2;
}

function _strictTurkishDisplay(value) {
  if (!value || typeof value !== 'string') return value || '';
  const raw = value.trim();
  if (!raw) return '';
  if (!_looksLikeEnglishInstructionalText(raw)) return raw;
  const translated = (typeof translateEducationalText === 'function') ? translateEducationalText(raw, 'tr') : raw;
  if (translated && translated.trim() && translated.trim() !== raw && !_looksLikeEnglishInstructionalText(translated)) {
    return translated.trim();
  }
  // Missing localization should never leak English into a Turkish lesson.
  return '';
}

'''
app = replace_once(app, strict_helper_anchor, strict_helper + strict_helper_anchor, 'strict Turkish display helpers')

# Replace the last English-only fallback in resolveItemExplanation.
fallback_old = '''        const res = resolveDualLanguage(enVal, '', 'tr');\n        it._resolved_tr = res;\n        return res;\n'''
fallback_new = '''        const res = _strictTurkishDisplay(resolveDualLanguage(enVal, '', 'tr') || enVal);\n        if (res) it._resolved_tr = res;\n        return res;\n'''
app = replace_once(app, fallback_old, fallback_new, 'vocab Turkish explanation fallback')

# Any generic explanation that still resolves to English is hidden rather than leaked.
generic_old = '''        const resolved = resolveDualLanguage(rawExpl.trim(), rawExpl.trim(), lang, rawExpl.trim());\n        return (lang === 'tr') ? healTurkishSyntax(humanizeTurkishExplanation(resolved)) : sanitizeEnglishExplanation(resolved, cleanTerm);\n'''
generic_new = '''        const resolved = resolveDualLanguage(rawExpl.trim(), rawExpl.trim(), lang, rawExpl.trim());\n        if (lang === 'tr') {\n          const strictResolved = _strictTurkishDisplay(resolved);\n          return strictResolved ? healTurkishSyntax(humanizeTurkishExplanation(strictResolved)) : '';\n        }\n        return sanitizeEnglishExplanation(resolved, cleanTerm);\n'''
app = replace_once(app, generic_old, generic_new, 'generic Turkish explanation leak guard')

# Page prose: use stored Turkish first; if fallback translation is still English, do not display it.
page_old = '''              const translatedText = (currentLang === 'tr')\n                ? ((p.text_tr || p.explanation_tr) ? text : translateEducationalText(text))\n                : (p.text || p.explanation || text);\n'''
page_new = '''              const translatedText = (currentLang === 'tr')\n                ? ((p.text_tr || p.explanation_tr) ? text : _strictTurkishDisplay(translateEducationalText(text, 'tr') || text))\n                : (p.text || p.explanation || text);\n'''
app = replace_once(app, page_old, page_new, 'page prose Turkish leak guard')

# Runtime MCQ answer reconciliation for existing stored lessons.
resolver_anchor = '''function resolveStudyOptionLabel(p, canonicalOption) {\n'''
resolver_helper = r'''function resolveStudyCorrectAnswer(p, options) {
  const canonical = Array.isArray(options) ? options.map(x => String(x).trim()) : [];
  let answer = String((p && p.answer) || '').trim();
  const expl = String((p && (p.explanation || p.explanation_tr)) || '').trim();
  if (expl && canonical.length > 1) {
    const quoted = canonical.filter(opt => opt && ["'" + opt + "'", '"' + opt + '"', '«' + opt + '»', '“' + opt + '”'].some(q => expl.includes(q)));
    if (quoted.length === 1) answer = quoted[0];
  }
  if (!canonical.includes(answer) && Number.isInteger(p && p.correct_index) && p.correct_index >= 0 && p.correct_index < canonical.length) {
    answer = canonical[p.correct_index];
  }
  return answer;
}

'''
app = replace_once(app, resolver_anchor, resolver_helper + resolver_anchor, 'frontend MCQ answer resolver')

# In study renderer, calculate correctedAnswer once and use it for grading.
options_anchor = '''               const allOptions = Array.from(new Set(rawOptions)).filter(Boolean);\n               if (!Array.isArray(p.options) || p.options.length <= 1) {\n                 allOptions.sort();\n               }\n               const translatedPrompt = resolveStudyPrompt(p, topic);\n'''
options_new = '''               const allOptions = Array.from(new Set(rawOptions)).filter(Boolean);\n               if (!Array.isArray(p.options) || p.options.length <= 1) {\n                 allOptions.sort();\n               }\n               const correctedAnswer = resolveStudyCorrectAnswer(p, allOptions);\n               const translatedPrompt = resolveStudyPrompt(p, topic);\n'''
app = replace_once(app, options_anchor, options_new, 'study corrected answer')
app = app.replace("escJS(p.answer), ${escJS(mcqExpl)}", "escJS(correctedAnswer), ${escJS(mcqExpl)}", 1)

# Do not display English-only vocabulary meaning pills in Turkish mode when translation is absent.
meaning_old = '''                      } else {\n                        v = resolveDualLanguage(enRawV, trRawV, 'tr', enRawV);\n'''
meaning_new = '''                      } else {\n                        v = _strictTurkishDisplay(resolveDualLanguage(enRawV, trRawV, 'tr', enRawV) || enRawV);\n'''
app = replace_once(app, meaning_old, meaning_new, 'vocab meaning Turkish leak guard')

# Cache bust changed frontend.
app_path.write_text(app, encoding='utf-8')
for html_path in (root / 'public').glob('*.html'):
    h = html_path.read_text(encoding='utf-8')
    h2 = re.sub(r'app\.js\?v=[^\"\']+', 'app.js?v=20260913_quality_v11', h)
    if h2 != h:
        html_path.write_text(h2, encoding='utf-8')


# ---------------------------------------------------------------------------
# 4) PDF: Unicode-safe header + answer repair + reject unusable MCQs
# ---------------------------------------------------------------------------
pdf = pdf_path.read_text(encoding='utf-8')

header_old = '''        for idx, page in enumerate(doc):\n            if idx > 0:\n                page.insert_text(fitz.Point(38, 27), f'AulaAI · {self.course_name}', fontsize=7, color=(0.42,0.42,0.42))\n            page.insert_text(fitz.Point(38, 823), 'AulaAI Educational System · Self-Contained Course Material', fontsize=6.7, color=(0.42,0.42,0.42))\n            page.insert_text(fitz.Point(493, 823), f'{page_word} {idx+1} / {total}', fontsize=6.7, color=(0.42,0.42,0.42))\n'''
header_new = '''        for idx, page in enumerate(doc):\n            # insert_text with Helvetica drops characters such as Turkish capital İ.\n            # HTML boxes use PyMuPDF's Unicode fallback fonts and preserve course names.\n            if idx > 0:\n                page.insert_htmlbox(fitz.Rect(38, 17, 557, 34), f'<span style="font-family:sans-serif;font-size:7pt;color:#6b7280">AulaAI · {_e(self.course_name)}</span>')\n            page.insert_htmlbox(fitz.Rect(38, 814, 430, 829), '<span style="font-family:sans-serif;font-size:6.7pt;color:#6b7280">AulaAI Educational System · Self-Contained Course Material</span>')\n            page.insert_htmlbox(fitz.Rect(470, 814, 557, 829), f'<div style="text-align:right;font-family:sans-serif;font-size:6.7pt;color:#6b7280">{_e(page_word)} {idx+1} / {total}</div>')\n'''
pdf = replace_once(pdf, header_old, header_new, 'Unicode PDF header/footer')

# Add local MCQ helpers before render_course_pdf.
render_anchor = '''def render_course_pdf(course_id: str, lang: str = 'en') -> Tuple[bytes, str]:\n'''
pdf_helpers = r'''def _repair_mcq_answer(page: dict, raw_options: Sequence) -> str:
    opts = [str(x).strip() for x in raw_options]
    answer = str(page.get('answer') or '').strip()
    explanation = str(page.get('explanation') or page.get('explanation_tr') or '').strip()
    if explanation and len(opts) > 1:
        quoted = []
        for opt in opts:
            if opt and any(q in explanation for q in (f"'{opt}'", f'"{opt}"', f'«{opt}»', f'“{opt}”')):
                quoted.append(opt)
        if len(quoted) == 1:
            answer = quoted[0]
    if answer not in opts:
        idx = page.get('correct_index')
        if isinstance(idx, int) and 0 <= idx < len(opts):
            answer = opts[idx]
    return answer


def _mcq_has_required_context(prompt: str) -> bool:
    s = str(prompt or '').strip()
    if len(s) < 8:
        return False
    low = s.casefold()
    # A generic instruction ending at a colon has lost the actual sentence/subject.
    ambiguous_markers = (
        'cümleyi tamam', 'doğru çekimi seç', 'dönüşlü zamiri seç',
        'complete the sentence', 'choose the correct conjugation',
        'choose the reflexive pronoun', 'select the correct conjugation'
    )
    if s.endswith(':') and any(m in low for m in ambiguous_markers):
        # Explicit blank/scenario after the instruction would make it self-contained.
        if not re.search(r'_{2,}|\.{3,}|…|«[^»]+»|"[^"]{4,}"', s):
            return False
    return True


'''
pdf = replace_once(pdf, render_anchor, pdf_helpers + render_anchor, 'PDF MCQ integrity helpers')

mcq_old = '''                    elif ptype == 'mcq':\n                        prompt = _mcq_prompt(page, is_tr)\n                        if not prompt:\n                            continue\n'''
mcq_new = '''                    elif ptype == 'mcq':\n                        prompt = _mcq_prompt(page, is_tr)\n                        if not prompt or not _mcq_has_required_context(prompt):\n                            # Never print an objectively unanswerable MCQ. New generation rules\n                            # prevent these; this guard protects historical stored material.\n                            continue\n'''
pdf = replace_once(pdf, mcq_old, mcq_new, 'PDF unusable MCQ guard')

answer_old = '''                        answer = page.get('answer') or ''\n                        explanation = _pick(page, 'explanation', 'explanation_tr', is_tr) or ''\n'''
answer_new = '''                        answer = _repair_mcq_answer(page, raw_options)\n                        explanation = _pick(page, 'explanation', 'explanation_tr', is_tr) or ''\n'''
pdf = replace_once(pdf, answer_old, answer_new, 'PDF answer consistency repair')
pdf_path.write_text(pdf, encoding='utf-8')

print('Applied material quality/localization gate v11')
