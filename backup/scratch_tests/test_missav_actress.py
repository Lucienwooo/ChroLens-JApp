import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

def test_missav(code):
    url = f"https://missav.ws/zh/{code.lower()}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        'Referer': 'https://missav.ws/'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8', errors='ignore')
            
        print(f"--- MissAV {code} ---")
        
        # Find actress using the updated regex
        actress_matches = re.findall(r'href="[^"]*actresses/([^"]+)"[^>]*>([^<]+)</a>', html)
        actresses = []
        if actress_matches:
            # Get the unique text values from the captures
            actresses = list(set(name.strip() for url_part, name in actress_matches if name.strip() and name.strip() != "Actresses"))
            
        print(f"Actresses: {actresses}")
        print()
    except Exception as e:
        print(f"Error MissAV {code}: {e}")

if __name__ == '__main__':
    test_missav("MAZO-033")
    test_missav("HMN-446")
    test_missav("TCD-332")
    test_missav("MARA-041")
