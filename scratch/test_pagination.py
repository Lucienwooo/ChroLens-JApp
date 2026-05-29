import urllib.request
import re

def fetch(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode('utf-8')
    except Exception as e:
        print("Fetch error for url:", url, e)
        return ""

url1 = "https://tktube.com/zh/categories/454545388bfe05b5b43cdc4fb9496ac6/"
url2 = "https://tktube.com/zh/categories/454545388bfe05b5b43cdc4fb9496ac6/2/"

html1 = fetch(url1)
html2 = fetch(url2)

def get_first_video_title(html):
    blocks = html.split('<div class="item')[1:]
    if not blocks:
        return "No blocks"
    title_m = re.search(r'alt="([^"]+)"', blocks[0])
    if not title_m:
        title_m = re.search(r'<strong class="title">\s*(.*?)\s*</strong>', blocks[0], re.DOTALL)
    title = title_m.group(1).strip() if title_m else "No title"
    return title

print("Page 1 first video:", get_first_video_title(html1))
print("Page 2 first video:", get_first_video_title(html2))

print("Is Page 1 HTML identical to Page 2 HTML?", html1 == html2)
print("Page 1 length:", len(html1), "Page 2 length:", len(html2))
