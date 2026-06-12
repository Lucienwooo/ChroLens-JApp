import urllib.request
import sys

url = "https://av-wiki.net/hmn-446/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        with open("hmn_446.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Successfully saved to hmn_446.html")
except Exception as e:
    print(f"Error: {e}")
