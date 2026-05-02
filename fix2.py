f = open('public/index.html', 'r', encoding='utf-8')
content = f.read()
f.close()

start_marker = '                <!-- Digital Study Container -->'
end_marker = '                <div class="mobile-preview mobile-only">'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

ai_book_html = content[start_idx:end_idx]

content = content[:start_idx] + content[end_idx:]

tab_book_end = content.find('            <section id="tab-s-home"')

new_section = '''
            <!-- AI Study Materials Tab (Lecturer) -->
            <section id="tab-study-materials" class="tab-panel">
                <div class="page-header">
                    <h1>📑 <span data-i18n="Material">Material</span></h1>
                    <p class="subtitle book-subtitle">Course Materials</p>
                </div>
''' + ai_book_html + '''            </section>
'''

content = content[:tab_book_end] + new_section + content[tab_book_end:]

# Update the lecturer tab data-tab properly
content = content.replace('id="lecturer-study-tab" data-tab="s-study-tab"', 'id="lecturer-study-tab" data-tab="study-materials"')

f = open('public/index.html', 'w', encoding='utf-8')
f.write(content)
f.close()
