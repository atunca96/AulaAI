import urllib.request
import json

data = json.dumps({'title': 'All Chapters Test', 'count': 5}).encode()
req = urllib.request.Request('http://localhost:3000/api/assignment/create', data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        print(f"Status: {response.getcode()}")
        print(f"Body: {response.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        print(f"Error Body: {e.read().decode()}")
