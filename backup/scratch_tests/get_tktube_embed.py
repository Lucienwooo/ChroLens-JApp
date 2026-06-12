import urllib.request
import urllib.parse

url = 'https://tktube.com/zh/embed/401110/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Referer': 'https://tktube.com/'
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode('utf-8', errors='ignore')
        with open('tktube_embed.html', 'w', encoding='utf-8') as out:
            out.write(html)
        print("Fetched successfully. Saved to tktube_embed.html")
except Exception as e:
    print("Error:", e)
