import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://missav.ws/zh/hmn-446"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Referer': 'https://missav.ws/'
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode('utf-8', errors='ignore')
        
    print("All links containing actress or star or similar:")
    # Find all hrefs
    links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html)
    for href, text in links:
        if any(x in href for x in ['actress', 'star', 'search', 'model']) or any(x in text for x in ['北野', '未奈']):
            print(f"Href: {href} | Text: {text.strip()}")
            
except Exception as e:
    print(f"Error: {e}")
