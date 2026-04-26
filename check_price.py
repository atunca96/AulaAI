import urllib.request, json
resp = urllib.request.urlopen('https://openrouter.ai/api/v1/models')
data = json.loads(resp.read())
for m in data['data']:
    if 'gemini-3.1-flash' in m['id']:
        print(f"{m['id']}: {m['pricing']}")
