import sys
import urllib.request

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
        
    pos = html.find("女優:")
    if pos != -1:
        print("Context around 女優:")
        print(html[pos:pos+400])
    else:
        print("女優: not found")
except Exception as e:
    print("Error:", e)
