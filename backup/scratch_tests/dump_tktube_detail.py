import sys
import urllib.request
import re

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

url = "https://tktube.com/zh/videos/401344/timd-033-bl/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode('utf-8')
        
    print("HTML length:", len(html))
    
    # Print lines containing label or actresses
    for line in html.splitlines():
        if any(w in line.lower() for w in ["label", "actress", "女演員", "演員", "女優"]):
            print(line.strip()[:150])
            
except Exception as e:
    print("Error:", e)
