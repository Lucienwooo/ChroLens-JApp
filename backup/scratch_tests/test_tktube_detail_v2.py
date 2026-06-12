import urllib.request
import re
import sys
import html as html_module

sys.stdout.reconfigure(encoding='utf-8')

def test_code(code, url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        'Referer': 'https://tktube.com/'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8', errors='ignore')
        
        # Parse actress
        actress_name = "未知"
        actress_sec = re.search(r'(?:女優|女演員|女优|女演员|Actresses|Models)\s*[:：]\s*(.*?)(?:</div>|</td>|</li>)', html, re.DOTALL | re.IGNORECASE)
        if actress_sec:
            content = actress_sec.group(1)
            actresses = re.findall(r'<a[^>]*href="[^"]*(?:models|actresses|star|model|actress)/[^"]+">([^<]+)</a>', content)
            if not actresses:
                actresses = re.findall(r'<a[^>]*>([^<]+)</a>', content)
            if actresses:
                actress_name = ", ".join(a.strip() for a in actresses if a.strip())
            else:
                plain = re.sub(r'<[^>]+>', '', content).strip()
                if plain:
                    actress_name = plain
                    
        title = None
        title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if not title_match:
            title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
            title = html_module.unescape(title)
            
        print(f"Code: {code}")
        print(f"Actress: {actress_name}")
        print(f"Title: {title}")
        
        # Clean title
        clean_t = title
        clean_t = re.sub(rf'\b{re.escape(code)}\b', '', clean_t, flags=re.IGNORECASE).strip()
        # Remove common site prefixes
        clean_t = re.sub(r'^(hd|1080p|720p|高清|字幕|中字|無碼破解|一般版)\s*', '', clean_t, flags=re.IGNORECASE).strip()
        # Remove brackets contents
        clean_t = re.sub(r'^[\[【\(（].*?[\]】\)）]', '', clean_t).strip()
        clean_t = re.sub(r'\s*-\s*TKTube.*$', '', clean_t, flags=re.IGNORECASE).strip()
        print(f"Cleaned Japanese Title: {clean_t}")
        print()
        
    except Exception as e:
        print(f"Error {code}: {e}")

if __name__ == '__main__':
    test_code("MAZO-033", "https://tktube.com/zh/videos/401315/mazo-033-ol24-sex-0-12/")
    test_code("HMN-446", "https://tktube.com/zh/videos/401330/hmn-446c-u-100cm-5/")
    test_code("TCD-332", "https://tktube.com/zh/videos/401342/tcd-332-4/")
    test_code("MARA-041", "https://tktube.com/zh/videos/401311/mara-041-pcup-128cm2/")
