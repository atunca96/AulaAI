import base64
with open('public/img/marmara-logo.png', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode('utf-8')

svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <image href="data:image/png;base64,{b64}" x="0" y="0" width="100" height="100" preserveAspectRatio="xMidYMid meet" />
</svg>'''

with open('public/img/favicon.svg', 'w') as f:
    f.write(svg_content)
