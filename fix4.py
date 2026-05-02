f = open('public/index.html', 'r', encoding='utf-8')
content = f.read()
f.close()

# Find the start of tab-study-materials
start_idx = content.find('            <!-- AI Study Materials Tab (Lecturer) -->')
# Find the end of it
end_idx = content.find('            <section id="tab-s-home"', start_idx)

# Extract the block
block = content[start_idx:end_idx]

# Remove the block from its current location
content = content[:start_idx] + content[end_idx:]

# Find where to put it: right before the </main> of lecturer dashboard.
# The lecturer dashboard main ends right before student-dashboard starts.
put_idx = content.find('        </main>\n    </div>\n\n    <!-- Student Dashboard -->')

content = content[:put_idx] + block + content[put_idx:]

f = open('public/index.html', 'w', encoding='utf-8')
f.write(content)
f.close()
