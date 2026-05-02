f = open('public/js/app.js', 'r', encoding='utf-8')
lines = f.readlines()
f.close()
start = -1
end = -1
for i, l in enumerate(lines):
    if 'const lectBookTab = document.getElementById' in l:
        start = i
        break
for i in range(start, len(lines)):
    if 'if (currentUser.role === \'student\') {' in lines[i]:
        end = i
        break

new_code = '''  const lectBookTab = document.getElementById('lecturer-book-tab');
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

'''
lines[start:end] = [new_code]
f = open('public/js/app.js', 'w', encoding='utf-8')
f.writelines(lines)
f.close()
