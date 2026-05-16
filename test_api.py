import sys, os, urllib.request, json, base64

api_key = ''
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f:
            if '=' in line:
                k, v = line.strip().split('=', 1)
                if k == 'OPENROUTER_API_KEY': api_key = v

pdf_path = 'dummy.pdf'
with open(pdf_path, 'wb') as f:
    f.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Count 1\n/Kids [ 3 0 R ]\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/F1 4 0 R\n>>\n>>\n/MediaBox [0 0 612 792]\n/Contents 5 0 R\n>>\nendobj\n4 0 obj\n<<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\nendobj\n5 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 24 Tf\n100 700 Td\n(Hello World) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000224 00000 n \n0000000312 00000 n \ntrailer\n<<\n/Size 6\n/Root 1 0 R\n>>\nstartxref\n405\n%%EOF')

with open(pdf_path, 'rb') as f:
    pdf_b64 = base64.b64encode(f.read()).decode('utf-8')

payload = {
    'model': 'openai/gpt-4o-mini',
    'messages': [
        {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': 'What does this document say? Output strictly JSON with key "text".'},
                {'type': 'file', 'file': {'filename': 'doc.pdf', 'file_data': f'data:application/pdf;base64,{pdf_b64}'}}
            ]
        }
    ],
    'plugins': [{'id': 'file-parser', 'pdf': {'engine': 'mistral-ocr'}}]
}

url = 'https://openrouter.ai/api/v1/chat/completions'
req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as r:
        print('SUCCESS:', r.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print('ERROR:', e.code, e.read().decode('utf-8'))
except Exception as e:
    print('EXCEPTION:', e)
