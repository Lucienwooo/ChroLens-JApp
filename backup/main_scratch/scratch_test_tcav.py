import urllib.request
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def test_tcav_search(query):
    url = f"https://tcav.85xvideo.com/?s={urllib.parse.quote(query)}"
    print(f"\nSearching '{query}' on tcav: {url}")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8', errors='ignore')
        
        # Look for img post-id matches
        img_matches = re.finditer(r'<img\s+post-id="(\d+)"([^>]*?)>', html, re.I)
        count = 0
        for m in img_matches:
            post_id, img_attrs = m.groups()
            alt_m = re.search(r'alt=["\']([^"\']+)["\']', img_attrs)
            alt = alt_m.group(1).strip() if alt_m else ""
            print(f"Match {count}: post-id={post_id}, alt='{alt}'")
            count += 1
        if count == 0:
            print("No matches found in HTML.")
    except Exception as e:
        print(f"Failed: {e}")

test_tcav_search("200GANA-3268")
test_tcav_search("200GANA3268")
test_tcav_search("GANA-3268")
test_tcav_search("3268")
