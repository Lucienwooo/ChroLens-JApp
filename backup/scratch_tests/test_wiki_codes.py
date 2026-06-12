import urllib.request
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def _parse_avwiki_title_tag(title_text, ccode_upper):
    found_actress = "未知"
    found_jp_title = None
    
    m_actress = re.search(r'([^\s。！？、。\.]+)に出てるAV女優は誰？', title_text)
    if m_actress:
        candidate = m_actress.group(1).strip()
        candidate = re.sub(r'^[「」【】（）\(\)\[\]。、！？\s]+', '', candidate).strip()
        candidate = re.sub(r'に$', '', candidate).strip()
        
        def is_valid_parsed_actress(name):
            if not name or name == "未知":
                return False
            stop_words = ["無反應", "無反応", "出演", "監督", "企劃", "企畫", "企画", "解禁", "合集", "破解", "字幕", "正常版", "無修正", "感覺", "感觉", "感覺到", "感受到", "暴漢", "對策", "對付", "行為", "護身術"]
            if any(sw in name for sw in stop_words):
                return False
            if not (2 <= len(name) <= 8):
                return False
            if not re.match(r'^[一-龥぀-ゟ゠-ヿ]+$', name):
                return False
            return True
            
        if is_valid_parsed_actress(candidate):
            found_actress = candidate
            
    if found_actress != "未知":
        m_title = re.search(rf'{re.escape(ccode_upper)}：(.+?)\s*{re.escape(found_actress)}に?出てるAV女優は誰？', title_text)
        if m_title and m_title.group(1).strip():
            found_jp_title = m_title.group(1).strip()
        else:
            m_title2 = re.search(rf'：(.+?)\s*{re.escape(found_actress)}に', title_text)
            if m_title2:
                found_jp_title = m_title2.group(1).strip()
    else:
        m_title = re.search(rf'{re.escape(ccode_upper)}：(.+?)に出てるAV女優は誰？', title_text)
        if m_title and m_title.group(1).strip():
            found_jp_title = m_title.group(1).strip()
            
    return found_actress, found_jp_title

def scrape(code):
    url = f"https://av-wiki.net/{code.lower()}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            title_text = ""
            title_m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            if title_m:
                title_text = title_m.group(1)
            
            actress, jp_title = _parse_avwiki_title_tag(title_text, code.upper())
            
            # FALLBACK
            if actress == "未知":
                m_body_actresses = re.search(r'AV女優名\s*：\s*(.*?)</li>', html, re.DOTALL)
                if m_body_actresses:
                    actresses = re.findall(r'<a[^>]*>([^<]+)</a>', m_body_actresses.group(1))
                    if actresses:
                        actress = ", ".join(a.strip() for a in actresses)
            
            print(f"Code: {code} -> Actress: {actress}, Title: {jp_title}")
    except Exception as e:
        print(f"Code: {code} -> Error: {e}")

for c in ['MAZO-033', 'HMN-446', 'TCD-332', 'MARA-041', 'SGKI-090']:
    scrape(c)
