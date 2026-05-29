import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://tcav.85xvideo.com/?s=3292343"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as r:
        html = r.read().decode('utf-8')
        
    print("Finding all matches of 3292343 in HTML:")
    for match in re.finditer("3292343", html):
        idx = match.start()
        print(f"\nMatch at index {idx}:")
        start = max(0, idx - 150)
        end = min(len(html), idx + 250)
        print(html[start:end])
except Exception as e:
    print("Error:", e)
