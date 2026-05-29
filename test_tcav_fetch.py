import urllib.request
import re
import sys
import urllib.parse

sys.stdout.reconfigure(encoding='utf-8')

# Mock the fetch_html_content from app.py
def fetch_html_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as r:
            return True, r.read().decode('utf-8')
    except Exception as e:
        return False, str(e)

# Extracting parsing logic from get_tcav_home_videos
def test_parse(url):
    success, html = fetch_html_content(url)
    if not success:
        print("Failed to fetch HTML:", html)
        return []
        
    try:
        img_matches = list(re.finditer(r'<img\s+post-id="(\d+)"[^>]*src="([^"]+)"[^>]*alt="([^"]+)"[^>]*>', html, re.IGNORECASE))
        print("Number of img matches found:", len(img_matches))
        
        results = []
        seen_codes = set()
        
        for m in img_matches:
            post_id, img_url, alt = m.groups()
            img_pos = m.start()
            context = html[max(0, img_pos - 400) : min(len(html), img_pos + 1200)]
            
            hrefs = re.findall(r'href="([^"]+)"', context)
            detail_url = ""
            for h in hrefs:
                if h.startswith("https://tcav.85xvideo.com/") and not any(x in h for x in ["/category/", "/tag/", "/feed/", "/page/", "wp-json", "xmlrpc"]):
                    if h != "https://tcav.85xvideo.com/":
                        detail_url = h
                        break
                        
            if not detail_url:
                print(f"Skipping post {post_id} - no detail URL found in context.")
                continue
                
            slug = detail_url.split('/')[-2] if detail_url.endswith('/') else detail_url.split('/')[-1]
            slug_decoded = urllib.parse.unquote(slug)
            
            code_match = re.search(r'([a-zA-Z0-9]+-[0-9]+)', slug_decoded)
            if code_match:
                code = code_match.group(1).upper()
            else:
                code_match = re.search(r'([a-zA-Z0-9]+-[0-9]+)', alt)
                if code_match:
                    code = code_match.group(1).upper()
                else:
                    code = slug_decoded.split('%')[0].split('-')[0].upper()
                    
            title = alt.replace(code, "").replace(code.lower(), "").replace("-", " ").strip()
            
            results.append({
                "code": code,
                "title": title,
                "cover": img_url,
                "url": detail_url
            })
        return results
    except Exception as e:
        print("Parsing error:", e)
        return []

res = test_parse("https://tcav.85xvideo.com/?s=3292343")
print("Parsed results:")
for r in res:
    print(r)
