import os
import re
import json
import concurrent.futures
import urllib.request
from urllib.error import HTTPError, URLError

MD_PATH = r"C:\Users\Lucien\Downloads\02_影片暫存區\影片清單.md"
OUT_MD_PATH = r"C:\Users\Lucien\Downloads\02_影片暫存區\影片清單.md"
OUT_JSON_PATH = r"C:\Users\Lucien\Downloads\02_影片暫存區\videos_data.json"

def clean_code(raw_code):
    c = raw_code
    for p in ['A-MOSAIC-ARCHIVE-', 'MOSAIC-ARCHIVE-', 'ARCHIVE-MOSAIC-', 'AV女優で筆下ろしフォルダ']:
        c = c.replace(p, '')
    c = c.replace('-UB', '').replace('_MOSAIC', '').replace(' (1)', '').replace('V', '')
    c = c.replace('（合演）', '')
    c = c.strip()
    return c.lower()

def fetch_url(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=headers)
    try:
        html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
        poster_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
        if not poster_match:
            poster_match = re.search(r'poster=["\']([^"\']+)["\']', html)
        img_url = poster_match.group(1) if poster_match else ""
        return True, img_url
    except:
        return False, ""

def fetch_info(raw_code):
    ccode = clean_code(raw_code)
    
    # 1. 優先檢查無碼破解版
    leaked_url = f"https://javxx.com/tw/v/{ccode}-uncensored-leaked"
    found, img = fetch_url(leaked_url)
    
    if found:
        return {"raw": raw_code, "clean": ccode, "url": leaked_url, "img": img, "found": True, "type": "無碼破解版"}
    
    # 2. 檢查正常版
    normal_url = f"https://javxx.com/tw/v/{ccode}"
    found, img = fetch_url(normal_url)
    
    if found:
        return {"raw": raw_code, "clean": ccode, "url": normal_url, "img": img, "found": True, "type": "正常版"}
    
    # 3. 找不到
    return {"raw": raw_code, "clean": ccode, "url": "", "img": "", "found": False, "type": "無"}

def main():
    with open(MD_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    codes_to_fetch = []
    
    for line in lines:
        if line.startswith('|') and not line.startswith('|---') and not line.startswith('| #'):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 4:
                # 判斷番號所在欄位
                if len(parts) == 6 and parts[1] != '番號':
                    # | 番號 | 女優 | 備註 | 預覽 | 連結 |
                    # parts = ['', '200GANA...', '素人', '根目錄', '', '', '']
                    code = parts[1]
                elif len(parts) >= 5 and parts[1] == '#':
                    continue
                elif len(parts) >= 6:
                    # | 1 | 女優 | 番號 | 預覽 | 連結 |
                    code = parts[3]
                else:
                    code = parts[1]
                
                if code and code not in ['番號', '備註', '說明']:
                    codes_to_fetch.append(code)
                    
    print(f"Total codes to fetch: {len(codes_to_fetch)}")
    
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_code = {executor.submit(fetch_info, code): code for code in set(codes_to_fetch)}
        for future in concurrent.futures.as_completed(future_to_code):
            res = future.result()
            results[res['raw']] = res
            print(f"Done: {res['raw']} -> {res['type']}")
            
    # 產生 JSON 與更新 MD
    new_lines = []
    videos_data = []
    
    for line in lines:
        if line.startswith('|') and not line.startswith('|---'):
            parts = [p.strip() for p in line.split('|')]
            
            if line.startswith('| # | 女優 | 番號 |'):
                new_lines.append("| # | 女優 | 番號 | 版本 | 預覽 | 連結 |\n")
                new_lines.append("|---|------|------|------|------|------|\n")
                continue
            elif line.startswith('| 番號 | 女優 |') or line.startswith('| 番號 | 備註 |') or line.startswith('| 番號 | 說明 |'):
                new_lines.append(f"| 番號 | {parts[2]} | {parts[3] if len(parts)>3 and parts[3] not in ['預覽', '連結'] else '備註'} | 版本 | 預覽 | 連結 |\n")
                new_lines.append("|------|------|------|------|------|------|\n")
                continue
            
            if len(parts) >= 4 and parts[1] != '#':
                # Parse depending on table format
                if len(parts) >= 6 and parts[1].isdigit():
                    num, actress, code = parts[1], parts[2], parts[3]
                    res = results.get(code)
                    if res:
                        videos_data.append({"id": num, "actress": actress, "code": code, **res})
                        link_str = f"[觀看影片]({res['url']})" if res['found'] else "(無連結)"
                        img_str = f"<img src='{res['img']}' width='200'>" if res['img'] else ""
                        new_lines.append(f"| {num} | {actress} | {code} | {res['type']} | {img_str} | {link_str} |\n")
                    else:
                        new_lines.append(line)
                elif len(parts) >= 5:
                    code, info1, info2 = parts[1], parts[2], parts[3] if len(parts) > 4 else ""
                    # handle unclassified tables
                    res = results.get(code)
                    if res:
                        videos_data.append({"id": code, "actress": info1, "code": code, "note": info2, **res})
                        link_str = f"[觀看影片]({res['url']})" if res['found'] else "(無連結)"
                        img_str = f"<img src='{res['img']}' width='200'>" if res['img'] else ""
                        new_lines.append(f"| {code} | {info1} | {info2} | {res['type']} | {img_str} | {link_str} |\n")
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            else:
                pass
        elif line.startswith('|---'):
            pass
        else:
            new_lines.append(line)
            
    with open(OUT_MD_PATH, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
        
    with open(OUT_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(videos_data, f, ensure_ascii=False, indent=2)
        
    print("Update complete!")

if __name__ == '__main__':
    main()
