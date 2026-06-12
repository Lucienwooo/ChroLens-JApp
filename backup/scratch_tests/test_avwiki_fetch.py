import urllib.request
import re

def test_code(code):
    url = f"https://av-wiki.net/{code.lower()}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8', errors='ignore')
            print(f"--- SUCCESS FOR {code} ---")
            print("URL:", url)
            
            # Title tag
            title_tag = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
            if title_tag:
                print("Title:", title_tag.group(1).strip())
                
            # Try parsing using the current regex
            m_body_actresses = re.search(r'AV女優名\s*：\s*(.*?)</li>', html, re.DOTALL)
            if m_body_actresses:
                print("Body Actress section found:")
                actresses = re.findall(r'<a[^>]*>([^<]+)</a>', m_body_actresses.group(1))
                print("Parsed actresses:", actresses)
            else:
                print("Body Actress section NOT found!")
                # Print a chunk of HTML to see what's there
                # search for Actress or 女優 in html
                pos = html.find("女優名")
                if pos != -1:
                    print("Context around 女優名:")
                    print(html[max(0, pos-100):min(len(html), pos+300)])
                else:
                    print("No 女優名 found in HTML!")
    except Exception as e:
        print(f"--- FAILED FOR {code}: {e} ---")

for code in ["mazo-033", "hmn-446", "mara-041", "tcd-332"]:
    test_code(code)
