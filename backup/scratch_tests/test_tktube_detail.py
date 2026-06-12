import urllib.request
import re

url = "https://tktube.com/zh/videos/401315/mazo-033-ol24-sex-0-12/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Referer': 'https://tktube.com/'
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode('utf-8', errors='ignore')
    
    # Save a snippet of the html around models/actresses/star/etc. for inspection
    with open("scratch/tktube_snippet.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    print("Fetched successfully. Let's see some snippets:")
    # Find all links containing 'models' or similar
    links = re.findall(r'<a[^>]+href="[^"]*(?:models|actresses|star|model|actress)/[^"]+"[^>]*>.*?</a>', html, re.IGNORECASE)
    print("Found links with models/actresses/star/model/actress:")
    for l in links[:10]:
        print(l)
        
    # Search for actress keywords
    keywords = ["女優", "女演員", "女优", "女演员", "Actresses", "Models", "モデル"]
    for kw in keywords:
        matches = [m.start() for m in re.finditer(kw, html)]
        print(f"Keyword '{kw}' matches count: {len(matches)}")
        for m in matches[:3]:
            print(f"Context around match: {html[max(0, m-100):min(len(html), m+200)]}\n")
            
except Exception as e:
    print(f"Error: {e}")
