import urllib.request
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

url = "https://av-wiki.net/sgki-090/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        # Print lines/context around "女優名"
        for m in re.finditer(r"女優名", html):
            start = max(0, m.start() - 100)
            end = min(len(html), m.end() + 250)
            print(f"Match context: {html[start:end].strip().replace('\n', ' ')}")
except Exception as e:
    print(f"Error: {e}")
