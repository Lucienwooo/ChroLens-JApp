import sys
import os
import json
import random
import concurrent.futures

sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.abspath('main'))

from japp import Api, fetch_metadata_info, PlatformRegistry

def compare_platforms():
    api = Api()
    favorites_path = os.path.join('main', 'Favorites.json')
    with open(favorites_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    codes = [item.get("code") or item.get("raw") for item in data if item.get("code") or item.get("raw")]
    # Randomly pick 5 unique codes that look like standard JAV codes
    valid_codes = [c for c in codes if "-" in c]
    if len(valid_codes) >= 5:
        sample_codes = random.sample(valid_codes, 5)
    else:
        sample_codes = random.sample(codes, min(5, len(codes)))
        
    print(f"Randomly selected 5 codes: {sample_codes}")
    print("-" * 120)
    print(f"{'Code':<15} | {'Platform':<12} | {'Actress':<25} | {'Title'}")
    print("-" * 120)
    
    registry = PlatformRegistry(api)
    providers = registry.get_providers()
    
    for code in sample_codes:
        print(f"Testing {code}...")
        results = []
        
        # 1. MissAV (via fetch_metadata_info)
        try:
            meta = fetch_metadata_info(code, api)
            if meta:
                results.append(("MissAV", meta.get("actress", "未知"), meta.get("japanese_title") or meta.get("title") or "未找到"))
        except:
            results.append(("MissAV", "Error", "Error"))
            
        # 2. Providers (TKTube, JavHDPorn, Supjav, TCAV)
        def fetch_prov(prov):
            try:
                res = prov["fetch_info"](code)
                if res:
                    return (prov["name"], res.get("actress", "未知"), res.get("japanese_title") or res.get("title") or "未找到")
            except:
                pass
            return (prov["name"], "未找到", "未找到")
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(providers)) as executor:
            future_to_prov = {executor.submit(fetch_prov, p): p for p in providers}
            for future in concurrent.futures.as_completed(future_to_prov):
                results.append(future.result())
                
        # 3. JavBus directly if possible
        javbus_res = ("JavBus", "未找到", "未找到")
        try:
            import re
            url = f"https://www.javbus.com/{code.upper()}"
            html = api.playwright_fetch_html(url, timeout_ms=6000)
            if html and "Age Verification" not in html and "你是否已經成年" not in html:
                m_actresses = re.findall(r'<a href="https://www\.javbus\.com/star/[^"]+">([^<]+)</a>', html)
                actress = ", ".join(m_actresses) if m_actresses else "未知"
                m_title = re.search(r'<h3>(.*?)</h3>', html)
                title = m_title.group(1).strip() if m_title else "未找到"
                javbus_res = ("JavBus", actress, title)
            elif html:
                javbus_res = ("JavBus", "Blocked", "Blocked")
        except:
            pass
        results.append(javbus_res)
        
        for name, actress, title in results:
            if len(title) > 60:
                title = title[:57] + "..."
            # Adjust padding for CJK characters loosely
            a_len = len(actress.encode('gbk', 'ignore')) if actress else 0
            pad_a = 25 - (a_len - len(actress))
            print(f"{code:<15} | {name:<12} | {actress:<{pad_a}} | {title}")
        print("-" * 120)

if __name__ == '__main__':
    compare_platforms()
