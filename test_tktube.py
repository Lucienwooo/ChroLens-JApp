import urllib.request
import re

url1 = "https://tktube.com/zh/categories/454545388bfe05b5b43cdc4fb9496ac6/"
url2 = "https://tktube.com/zh/categories/454545388bfe05b5b43cdc4fb9496ac6/2/"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8'
}

def fetch(url):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8')
            print(f"URL: {url} - SUCCESS, length: {len(html)}")
            # 看看有沒有找到 <div class="item
            blocks = html.split('<div class="item')
            print(f"Number of item blocks: {len(blocks) - 1}")
            # 尋找頁碼
            total_match = re.search(r'Total:(\d+)', html)
            print(f"Total: {total_match.group(1) if total_match else 'None'}")
            return html
    except Exception as e:
        print(f"URL: {url} - FAILED: {e}")
        return None

print("Fetching Page 1...")
html1 = fetch(url1)
print("\nFetching Page 2...")
html2 = fetch(url2)
