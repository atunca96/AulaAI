import re

def fix():
    with open('app.js', 'r', encoding='utf-8') as f:
        txt = f.read()
    
    # Fix opening tags: < div -> <div
    txt = re.sub(r'<\s+(div|span|h[1-6]|button|a|strong)\b', r'<\1', txt)
    
    # Fix closing tags: </ div > -> </div>
    txt = re.sub(r'</\s*(div|span|h[1-6]|button|a|strong)\s*>', r'</\1>', txt)
    
    with open('app.js', 'w', encoding='utf-8') as f:
        f.write(txt)

if __name__ == '__main__':
    fix()
