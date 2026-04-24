import os

file_path = r"c:\Users\atunc\.gemini\antigravity\scratch\spanish-ai-system\server.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Exact match from repr()
bad_block = '# ALWAYS TRY AI FIRST FOR VARIETY (Skip instant DB fetch)\n            topic = db.execute("""\n\n            topic = db.execute("""\n'
good_block = '# ALWAYS TRY AI FIRST FOR VARIETY (Skip instant DB fetch)\n            topic = db.execute("""\n'

if bad_block in content:
    new_content = content.replace(bad_block, good_block)
    with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)
    print("Success: Fixed server.py")
else:
    print("Error: Could not find bad block")
