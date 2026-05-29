import urllib.request
import re

url = "https://tktube.com/zh/categories/454545388bfe05b5b43cdc4fb9496ac6/"
req = urllib.request.Request(
    url,
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
)
try:
    with urllib.request.urlopen(req, timeout=10) as response:
        html = response.read().decode('utf-8')
        
    print("HTML Length:", len(html))
    # Write the last 15000 characters of HTML to a local text file so we can view it safely
    with open("footer_debug.html", "w", encoding="utf-8") as f:
        f.write(html[-15000:])
    print("Wrote footer debug to footer_debug.html successfully.")
except Exception as e:
    print("Error:", e)
