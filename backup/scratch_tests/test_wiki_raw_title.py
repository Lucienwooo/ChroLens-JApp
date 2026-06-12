import urllib.request
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def print_raw_title(code):
    url = f"https://av-wiki.net/{code.lower()}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            title_m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            if title_m:
                print(f"Code: {code} -> Raw Title Tag: {title_m.group(1)}")
            else:
                print(f"Code: {code} -> Title tag not found")
    except Exception as e:
        print(f"Code: {code} -> Error: {e}")

for c in ['MAZO-033', 'HMN-446', 'MARA-041']:
    print_raw_title(c)
