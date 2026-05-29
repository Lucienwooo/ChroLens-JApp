import urllib.request
import re

url = "https://tktube.com/zh/categories/454545388bfe05b5b43cdc4fb9496ac6/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8'
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode('utf-8')
        blocks = html.split('<div class="item')[1:]
        if blocks:
            print("--- RAW BLOCK 1 ---")
            print(blocks[0][:2000])
        else:
            print("No items found!")
except Exception as e:
    print("Fetch error:", e)
