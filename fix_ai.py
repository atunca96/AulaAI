import re

with open('services/ai_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update signature
content = content.replace(
    "def ai_generate_questions(topic_title, topic_type, topic_content, language, count=10, level='A1', use_quality=True, existing_questions=None, is_pdf_source=False):",
    "def ai_generate_questions(topic_title, topic_type, topic_content, language, count=10, level='A1', use_quality=True, existing_questions=None, is_pdf_source=False, is_quiz=False):"
)

# 2. Update instruction_lang logic
old_lang = '''    if is_pdf_source:
        instruction_lang = language
    else:
        instruction_lang = "English" if is_beginner else language'''

new_lang = '''    if is_pdf_source or is_quiz:
        instruction_lang = language
    else:
        instruction_lang = "English" if is_beginner else language'''

content = content.replace(old_lang, new_lang)

# 3. Update translation_rule
old_trans = '''    translation_rule = '12. TRANSLATION: Add a "translation" field containing the English translation of the prompt.' if is_beginner else ""
    translation_field = '"translation": "...", ' if is_beginner else ""'''

new_trans = '''    translation_rule = '12. TRANSLATION: Add a "translation" field containing the English translation of the prompt.' if (is_beginner and not is_quiz) else ""
    translation_field = '"translation": "...", ' if (is_beginner and not is_quiz) else ""'''

content = content.replace(old_trans, new_trans)

with open('services/ai_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)
