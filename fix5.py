f = open('public/js/app.js', 'r', encoding='utf-8')
content = f.read()
f.close()

# Update renderPromptHTML signature and logic
old_func = '''function renderPromptHTML(a) {
  let p = formatActivityData(a.prompt);
  p = translatePrompt(p); // Preserve existing localization mechanism
  
  if (a.translation) {'''

new_func = '''function renderPromptHTML(a, isQuiz = false) {
  let p = formatActivityData(a.prompt);
  p = translatePrompt(p); // Preserve existing localization mechanism
  
  if (a.translation && !isQuiz) {'''

content = content.replace(old_func, new_func)

# Update showQuizQuestion caller
old_caller = '''  area.innerHTML = `<div class="quiz-header"><span class="quiz-progress-text">Q${idx + 1}/${qs.length}</span></div><div class="activity-card">${renderPromptHTML(q)}` +'''
new_caller = '''  area.innerHTML = `<div class="quiz-header"><span class="quiz-progress-text">Q${idx + 1}/${qs.length}</span></div><div class="activity-card">${renderPromptHTML(q, true)}` +'''

content = content.replace(old_caller, new_caller)

f = open('public/js/app.js', 'w', encoding='utf-8')
f.write(content)
f.close()
