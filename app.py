import os
import sys
import time

# Disable web security to allow cross-origin iframe DOM access for Range Replay feature
os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--disable-web-security --disable-site-isolation-trials'

import json
import webview
import urllib.request
import re
import concurrent.futures
import threading
import datetime

VERSION = "1.1"

def get_resource_path():
    """ 取得打包在 exe 內的唯讀資源路徑 (HTML, CSS, JS 等) """
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def get_data_path():
    """ 取得持久化資料庫儲存路徑 (確保與打包後的 exe 同目錄，並優先相容本機 dist 目錄) """
    base_dir = os.path.dirname(sys.executable) if hasattr(sys, 'frozen') else os.path.dirname(os.path.abspath(__file__))
    dist_path = os.path.join(base_dir, 'dist')
    if os.path.exists(os.path.join(dist_path, 'Favorites.json')):
        return dist_path
    return base_dir

def clean_code(raw_code):
    if not raw_code:
        return ""
    c = raw_code.strip().lower()
    # Remove anything in brackets or parentheses (e.g. (無碼洩露) or （合演）)
    c = re.sub(r'[\(\uff08].*?[\)\uff09]', '', c)
    # Remove common garbage suffixes at the end
    c = re.sub(r'-(ub|uncensored|leaked|破解版|正常版)$', '', c)
    # Remove trailing 'v' if it is preceded by a number (e.g. start-423v -> start-423)
    c = re.sub(r'([0-9]+)v$', r'\1', c)
    
    # Extract the core JAV code: letters/numbers, dash, then numbers
    matches = re.findall(r'([a-z0-9]+-[0-9]+)', c)
    if matches:
        return matches[-1]
    
    # Fallback: clean all non-alphanumeric except dash
    c = re.sub(r'[^a-z0-9\-]', '', c)
    return c

GLOBAL_API = None

def fetch_html_content(url):
    import urllib.error
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        'Referer': 'https://tktube.com/' if 'tktube.com' in url else ('https://tcav.85xvideo.com/' if 'tcav.85xvideo.com' in url else 'https://google.com/')
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return True, r.read().decode('utf-8')
    except Exception as urllib_err:
        return False, ""

def fetch_url(url):
    success, html = fetch_html_content(url)
    if not success:
        return False, "", "未知"
    poster_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if not poster_match:
        poster_match = re.search(r'poster=["\']([^"\']+)["\']', html, re.IGNORECASE)
    img_url = poster_match.group(1) if poster_match else ""
    
    # Extract actress name from details page HTML if available
    actress_name = "未知"
    actress_sec = re.search(r'<div>\s*<label>(?:女演員|女演员|Actresses|女优|女優):?</label>\s*(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
    if actress_sec:
        actresses = re.findall(r'<a href="[^"]*/actresses/[^"]+">([^<]+)</a>', actress_sec.group(1))
        if actresses:
            actress_name = ", ".join(a.strip() for a in actresses)
            
    return True, img_url, actress_name

def parse_actress_from_title(title):
    if not title:
        return "未知"
    t = title.strip()
    t = re.sub(r'[\(\[（【].*?[\)\]）】]', '', t).strip()
    
    exclude_terms = {
        "中出", "巨乳", "美乳", "爆乳", "潮吹", "高清", "字幕", "破解", "流出", "合集", "下卷", "上卷", "精選",
        "中文字幕", "中文", "近親", "相姦", "亂倫", "強姦", "輪姦", "運動", "性感", "美女", "熟女", "人妻", 
        "主婦", "OL", "學生", "女僕", "教師", "醫生", "護士", "空姐", "痴漢", "野外", "溫泉", "旅館", "露出",
        "自慰", "潮吹", "噴水", "失禁", "榨汁", "乳交", "口交", "肛交", "內射", "高潮", "呻吟", "恍惚",
        "禁慾", "挑逗", "性愛", "進化", "拷貝", "複製", "修復", "洩露", "版本", "合演", "主演", "演出", "新人",
        "約會", "一日", "旅行", "溫泉", "旅館", "酒店", "飯店", "同居", "同床", "同房", "上司", "同事", "客戶",
        "老師", "學生", "同學", "班長", "會長", "校長", "護士", "醫生", "病人", "妹妹", "姐姐", "媽媽", "阿姨",
        "女演員", "女優", "小姐", "大嫂", "媳婦", "婆婆", "無碼", "破解", "字幕", "合集", "系列", "精選",
        "特輯", "推薦", "排行", "熱門", "最新", "經典", "超清", "高清", "完整版", "流出版", "破壞版", "解禁版",
        "未公開", "未發行", "未曝光", "幕後", "花絮", "紀錄", "採訪", "訪談", "對談", "談話", "聊天", "交流",
        "互動", "體驗", "嘗試", "挑戰", "冒險", "探索", "研究", "分析", "調查", "報告", "總結", "回顧", "展望",
        "計劃", "方案", "策略", "方法", "技巧", "秘訣", "指南", "教程", "課程", "培訓", "講座", "研討",
        "動漫", "遊戲", "影視", "音樂", "舞蹈", "戲劇", "曲藝", "書畫", "雕塑", "攝影", "設計", "手工",
        "制服", "黑絲", "網絲", "眼鏡", "美腿", "長腿", "可愛", "漂亮", "苗條", "豐滿", "骨感", "高挑",
        "順從", "調教", "綁架", "監禁", "虐待", "羞恥", "按摩", "自拍"
    }

    # First, try to match at the end
    match = re.search(r'([\u4e00-\u9fa5]{2,4})$', t)
    if match:
        actress = match.group(1)
        is_excluded = actress in exclude_terms or any(term in actress for term in exclude_terms)
        if not is_excluded:
            return actress
            
    # Search all 2-4 character Chinese sequences anywhere in the title
    candidates = re.findall(r'[\u4e00-\u9fa5]{2,4}', t)
    for cand in candidates:
        is_excluded = cand in exclude_terms or any(term in cand for term in exclude_terms)
        if not is_excluded:
            return cand
            
    return "未知"


# Pre-compiled regexes for maximum scraping speed
HOME_ITEM_RE = re.compile(
    r'<a href="(/tw/v/[^"]+)" class="poster">.*?<img[^>]*src="([^"]+)"[^>]*>.*?<a href="[^"]+" class="title">\s*<span class="code">([^<]+)</span>\s*<span>([^<]+)</span>',
    re.DOTALL | re.IGNORECASE
)
PREVIEW_URL_RE1 = re.compile(r'<d-tag\s+[^>]*?url=["\']([^"\']+)["\'][^>]*?src=["\']Preview["\']', re.IGNORECASE)
PREVIEW_URL_RE2 = re.compile(r'<d-tag\s+[^>]*?src=["\']Preview["\'][^>]*?url=["\']([^"\']+)["\']', re.IGNORECASE)

def parse_relative_time(relative_str):
    if not relative_str:
        return ""
    
    relative_str = relative_str.strip()
    now = datetime.datetime.now()
    days = 0
    hours = 0
    minutes = 0
    
    # Extract week, day, hour, minute, month, year
    week_match = re.search(r'(\d+)\s*週', relative_str)
    day_match = re.search(r'(\d+)\s*天', relative_str)
    hour_match = re.search(r'(\d+)\s*小時', relative_str)
    min_match = re.search(r'(\d+)\s*分鐘', relative_str)
    month_match = re.search(r'(\d+)\s*個月', relative_str)
    year_match = re.search(r'(\d+)\s*年', relative_str)
    
    if week_match:
        days += int(week_match.group(1)) * 7
    if day_match:
        days += int(day_match.group(1))
    if hour_match:
        hours += int(hour_match.group(1))
    if min_match:
        minutes += int(min_match.group(1))
    if month_match:
        days += int(month_match.group(1)) * 30
    if year_match:
        days += int(year_match.group(1)) * 365
        
    if days == 0 and hours == 0 and minutes == 0:
        # Check english fallback just in case
        eng_hour = re.search(r'(\d+)\s*hour', relative_str, re.IGNORECASE)
        eng_day = re.search(r'(\d+)\s*day', relative_str, re.IGNORECASE)
        eng_week = re.search(r'(\d+)\s*week', relative_str, re.IGNORECASE)
        eng_min = re.search(r'(\d+)\s*min', relative_str, re.IGNORECASE)
        eng_month = re.search(r'(\d+)\s*month', relative_str, re.IGNORECASE)
        eng_year = re.search(r'(\d+)\s*year', relative_str, re.IGNORECASE)
        
        if eng_week:
            days += int(eng_week.group(1)) * 7
        if eng_day:
            days += int(eng_day.group(1))
        if eng_hour:
            hours += int(eng_hour.group(1))
        if eng_min:
            minutes += int(eng_min.group(1))
        if eng_month:
            days += int(eng_month.group(1)) * 30
        if eng_year:
            days += int(eng_year.group(1)) * 365
            
    delta = datetime.timedelta(days=days, hours=hours, minutes=minutes)
    upload_time = now - delta
    return upload_time.strftime('%Y-%m-%d')

class PlatformRegistry:
    def __init__(self, api):
        self.api = api
        
    def _fetch_javxx_info(self, ccode):
        leaked_url = f"https://javxx.com/tw/v/{ccode}-uncensored-leaked"
        normal_url = f"https://javxx.com/tw/v/{ccode}"
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            f_leaked = ex.submit(fetch_url, leaked_url)
            f_normal = ex.submit(fetch_url, normal_url)
            concurrent.futures.wait([f_leaked, f_normal], timeout=5)
            try:
                leaked_found, leaked_img, leaked_actress = f_leaked.result()
            except:
                leaked_found, leaked_img, leaked_actress = False, "", "未知"
            if leaked_found:
                return {"url": leaked_url, "img": leaked_img, "preview": "", "type": "無碼破解版", "actress": leaked_actress}
            try:
                normal_found, normal_img, normal_actress = f_normal.result()
            except:
                normal_found, normal_img, normal_actress = False, "", "未知"
            if normal_found:
                return {"url": normal_url, "img": normal_img, "preview": "", "type": "正常版", "actress": normal_actress}
        return None

    def get_providers(self):
        return [
            {
                "name": "javxx",
                "fetch_info": lambda ccode: self._fetch_javxx_info(ccode),
                "get_home": lambda url: self.api.get_home_videos(url)
            },
            {
                "name": "tcav",
                "fetch_info": lambda ccode: self.api.fetch_tcav_info(ccode),
                "get_home": lambda url: self.api.get_tcav_home_videos(url)
            },
            {
                "name": "tktube",
                "fetch_info": lambda ccode: self.api.fetch_tktube_info(ccode),
                "get_home": lambda url: self.api.get_tktube_home_videos(url)
            }
        ]

class Api:
    def __init__(self):
        self.data = []
        self.data_path = os.path.join(get_data_path(), 'Favorites.json')
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except Exception as e:
                print("Error loading json:", e)
                # 備份損壞的 JSON 檔案，防止被覆寫
                import shutil
                bak_path = self.data_path + ".corrupted.bak"
                try:
                    shutil.copy2(self.data_path, bak_path)
                    print(f"Backed up corrupted Favorites.json to {bak_path}")
                except Exception as backup_err:
                    print("Failed to backup corrupted file:", backup_err)
                self.data = []
        # (Platform Registry is now instantiated locally to prevent circular reference recursion errors)
        # Start background healing thread for favorites
        threading.Thread(target=self.heal_favorites_background, daemon=True).start()
        
        # Initialize Version & Update Manager
        self.current_version = VERSION
        from version_manager import VersionManager
        self.version_manager = VersionManager(self.current_version, logger=print)
        self.update_progress = {"status": "idle", "percent": 0, "detail": "", "error": None}
        self._window = None
        
        # Initialize Playwright Browser State & Thread Worker Queue
        import queue
        self.playwright_queue = queue.Queue()
        self.browser_context = None
        self.playwright_err = None
        
        global GLOBAL_API
        GLOBAL_API = self
        
        # Start background lazy init for Playwright to keep GUI startup instantaneous!
        threading.Thread(target=self.init_playwright_background, daemon=True).start()
                
    def get_videos(self):
        return self.data

    def get_preview_data(self, url):
        if not url: return ""
        import base64
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            data = urllib.request.urlopen(req, timeout=10).read()
            encoded = base64.b64encode(data).decode('utf-8')
            return f"data:video/mp4;base64,{encoded}"
        except Exception as e:
            print("Preview fetch error:", e)
            return ""

    def save_videos(self, new_data):
        self.data = new_data
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print("Save error:", e)
            return False

    def fetch_video_info(self, raw_code):
        ccode = clean_code(raw_code)
        if not ccode:
            return {"raw": raw_code, "clean": "", "code": raw_code, "url": "", "img": "", "found": False, "type": "無", "actress": "未知"}
            
        providers = PlatformRegistry(self).get_providers()
        is_fc2_or_md = "fc2" in ccode.lower() or "md" in ccode.lower()
        
        # Concurrently check all registered platforms!
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(providers)) as executor:
            future_to_prov = {
                executor.submit(prov["fetch_info"], ccode): prov
                for prov in providers
            }
            
            # Wait for all to complete
            concurrent.futures.wait(future_to_prov.keys(), timeout=6)
            
            # Resolve results by priority
            results = {}
            for future, prov in future_to_prov.items():
                try:
                    res = future.result()
                    if res:
                        results[prov["name"]] = res
                except:
                    pass
            
            # Extract actress from results dynamically
            actress_name = "未知"
            if "javxx" in results and "actress" in results["javxx"] and results["javxx"]["actress"] != "未知":
                actress_name = results["javxx"]["actress"]
            else:
                # Fallback to other results if available
                for name in results:
                    if "actress" in results[name] and results[name]["actress"] != "未知":
                        actress_name = results[name]["actress"]
                        break
            
            # Adapt priority adaptive logic:
            # 1. If FC2 or Chinese premium: check TCAV (85xvideo) first
            is_tcav_priority = any(x in ccode.lower() for x in ["fc2", "md", "mdyd", "sht", "mianbar", "hs", "cc", "tw", "pk", "lu"])
            priority_list = ["tcav", "tktube", "javxx"] if is_tcav_priority else ["tktube", "javxx", "tcav"]
            
            best_res = None
            # Double priority lookup: 1. Try to find Uncensored Leaked or FC2 from any platform first
            for name in priority_list:
                if name in results:
                    r = results[name]
                    if r.get("type") in ["無碼破解版", "FC2"]:
                        best_res = (name, r)
                        break
                        
            # 2. Fallback to normal priority list order if no uncensored/FC2 premium version is found
            if not best_res:
                for name in priority_list:
                    if name in results:
                        best_res = (name, results[name])
                        break
                        
            if best_res:
                name, r = best_res
                return {
                    "raw": raw_code,
                    "clean": ccode,
                    "code": ccode.upper(),
                    "url": r["url"],
                    "img": r["img"],
                    "preview": r.get("preview") or "",
                    "found": True,
                    "type": r["type"],
                    "actress": actress_name
                }
                    
        # If absolutely nothing is found, check if it's a valid JAV code and fallback to MissAV!
        if ccode and re.search(r'[A-Z0-9]+-[0-9]+', ccode):
            parsed_actress = parse_actress_from_title(raw_code)
            return {
                "raw": raw_code,
                "clean": ccode,
                "code": ccode.upper(),
                "url": f"https://missav.ws/{ccode.lower()}",
                "img": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500&auto=format&fit=crop",
                "preview": "",
                "found": True,
                "type": "正常版",
                "actress": parsed_actress if parsed_actress != "未知" else "未知"
            }
            
        # If absolutely nothing is found
        return {
            "raw": raw_code,
            "clean": ccode,
            "code": ccode.upper(),
            "url": "",
            "img": "",
            "found": False,
            "type": "無",
            "actress": "未知"
        }

    def search_all_platforms(self, query):
        if not query:
            return {"videos": [], "total_pages": 1, "current_page": 1}
            
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        
        javxx_search_url = f"https://javxx.com/tw/search?q={encoded_query}"
        tcav_search_url = f"https://tcav.85xvideo.com/?s={encoded_query}"
        tktube_search_url = f"https://tktube.com/zh/search/{encoded_query}/"
        
        # Concurrently search all 3 platforms!
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_javxx = executor.submit(self.get_home_videos, javxx_search_url)
            future_tcav = executor.submit(self.get_tcav_home_videos, tcav_search_url)
            future_tktube = executor.submit(self.get_tktube_home_videos, tktube_search_url)
            
            # Wait for all to complete (max 8 seconds)
            concurrent.futures.wait([future_javxx, future_tcav, future_tktube], timeout=8)
            
            try:
                javxx_res = future_javxx.result()
                javxx_videos = javxx_res.get("videos") if isinstance(javxx_res, dict) else javxx_res
            except Exception as e:
                print("JAVxx search error:", e)
                javxx_videos = []
                
            try:
                tcav_res = future_tcav.result()
                tcav_videos = tcav_res.get("videos") if isinstance(tcav_res, dict) else tcav_res
            except Exception as e:
                print("TCAV search error:", e)
                tcav_videos = []
                
            try:
                tktube_res = future_tktube.result()
                tktube_videos = tktube_res.get("videos") if isinstance(tktube_res, dict) else tktube_res
            except Exception as e:
                print("TKTube search error:", e)
                tktube_videos = []
                
            # Merge results
            merged_videos = []
            seen_codes = set()
            
            # Combine them in a balanced order: first exact/highly matching results from each
            clean_q = clean_code(query).upper()
            
            def is_match(v):
                v_code = v.get("code", "").upper()
                return clean_q in v_code or v_code in clean_q or query.upper() in v_code
                
            matches = []
            others = []
            
            # Priority Sorting: If query contains 'fc2', prioritize 85xvideo (tcav_videos) first
            is_fc2_query = "fc2" in query.lower()
            platform_order = [tcav_videos, tktube_videos, javxx_videos] if is_fc2_query else [tktube_videos, javxx_videos, tcav_videos]
            
            for vlist in platform_order:
                if not vlist: continue
                for v in vlist:
                    code = v.get("code", "").upper()
                    if not code or code in seen_codes:
                        continue
                    seen_codes.add(code)
                    
                    if is_match(v):
                        matches.append(v)
                    else:
                        others.append(v)
                        
            # Automatically construct MissAV auxiliary cards if a JAV code is detected in query
            ccode = clean_code(query).upper()
            if ccode and re.search(r'[A-Z0-9]+-[0-9]+', ccode):
                cover_img = ""
                actress_name = "未知"
                preview_url = ""
                for v in matches + others:
                    if clean_code(v.get("code", "")).upper() == ccode:
                        if v.get("cover"):
                            cover_img = v["cover"]
                        if v.get("preview"):
                            preview_url = v["preview"]
                        if v.get("actress") and v["actress"] != "未知":
                            actress_name = v["actress"]
                        break
                
                # Check our local favorites database too!
                if not cover_img:
                    for item in self.data:
                        if clean_code(item.get("code", "")).upper() == ccode:
                            if item.get("img"):
                                cover_img = item["img"]
                            if item.get("preview"):
                                preview_url = item["preview"]
                            if item.get("actress") and item["actress"] != "未知":
                                actress_name = item["actress"]
                            break
                            
                # Fallback beautiful premium abstract poster image if still missing
                if not cover_img:
                    cover_img = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500&auto=format&fit=crop"
                
                missav_leaked = {
                    "code": ccode,
                    "title": f"[MissAV 無碼破解] {ccode}",
                    "cover": cover_img,
                    "preview": preview_url,
                    "url": f"https://missav.ws/{ccode.lower()}-uncensored-leak",
                    "type": "無碼破解版",
                    "actress": actress_name,
                    "relative_time": "加入日期: 2026-05-18",
                    "source": "missav"
                }
                
                missav_normal = {
                    "code": ccode,
                    "title": f"[MissAV 一般版] {ccode}",
                    "cover": cover_img,
                    "preview": preview_url,
                    "url": f"https://missav.ws/{ccode.lower()}",
                    "type": "正常版",
                    "actress": actress_name,
                    "relative_time": "加入日期: 2026-05-18",
                    "source": "missav"
                }
                
                # Insert MissAV cards as the top priority matches
                matches.insert(0, missav_leaked)
                matches.insert(1, missav_normal)
                        
            final_videos = matches + others
            
            return {
                "videos": final_videos[:60],
                "total_pages": 1,
                "current_page": 1
            }

    def fetch_tktube_info(self, ccode):
        # 1. Try standard path search
        tktube_url = f"https://tktube.com/zh/search/{ccode}/"
        success, html = fetch_html_content(tktube_url)
        if success:
            res = self.parse_tktube_html(html, ccode)
            if res: return res
            
        # 2. Try double-dash path search (TKTube redirects/index fallback)
        tktube_url_2 = f"https://tktube.com/zh/search/{ccode.replace('-', '--')}/"
        success, html = fetch_html_content(tktube_url_2)
        if success:
            res = self.parse_tktube_html(html, ccode)
            if res: return res
            
        # 3. Try query parameter search
        tktube_url_3 = f"https://tktube.com/zh/search/?q={ccode}"
        success, html = fetch_html_content(tktube_url_3)
        if success:
            res = self.parse_tktube_html(html, ccode)
            if res: return res
            
        return None

    def parse_tktube_html(self, html, ccode):
        best_uncensored = None
        best_normal = None
        uncensored_keywords = ["馬賽克破壞", "破除馬賽克", "馬賽克解除", "去馬賽克", "無修正", "無碼", "破解", "解除馬賽克", "破壞版"]
        
        # Split into blocks of items to optimize performance
        blocks = html.split('<div class="item')[1:]
        for block in blocks:
            href_m = re.search(r'href="([^"]+)"', block)
            if not href_m: continue
            video_url = href_m.group(1)
            
            title_m = re.search(r'alt="([^"]+)"', block)
            if not title_m:
                title_m = re.search(r'<strong class="title">\s*(.*?)\s*</strong>', block, re.DOTALL)
            title = title_m.group(1).strip() if title_m else ""
            
            img_m = re.search(r'src="([^"]+)"', block)
            if not img_m:
                img_m = re.search(r'data-src="([^"]+)"', block)
            img_url = img_m.group(1) if img_m else ""
            
            preview_m = re.search(r'data-preview="([^"]+)"', block)
            preview_url = preview_m.group(1) if preview_m else ""
            
            if video_url.startswith('/'):
                video_url = "https://tktube.com" + video_url
                
            lower_title = title.lower()
            lower_url = video_url.lower()
            
            # Match the video strictly to ensure we get correct matching code
            if ccode in lower_title or ccode.replace("-", "") in lower_title or ccode in lower_url or ccode.replace("-", "") in lower_url:
                is_uncensored = any(kw in lower_title for kw in uncensored_keywords)
                video_data = {
                    "url": video_url,
                    "img": img_url,
                    "preview": preview_url,
                    "type": "無碼破解版" if is_uncensored else "正常版"
                }
                if is_uncensored:
                    if not best_uncensored:
                        best_uncensored = video_data
                else:
                    if not best_normal:
                        best_normal = video_data
                        
        if best_uncensored:
            return best_uncensored
        if best_normal:
            return best_normal
        return None

    def parse_home_videos(self, html, url=""):
        if not html:
            return {"videos": [], "total_pages": 1, "current_page": 1}
        try:
            current_page = 1
            page_match = re.search(r'[?&]page=(\d+)', url)
            if page_match:
                current_page = int(page_match.group(1))
                
            total_pages = current_page
            page_nums = [int(p) for p in re.findall(r'page=(\d+)', html)]
            if page_nums:
                total_pages = max(max(page_nums), current_page)
                
            items = html.split('<div class="item">')[1:]
            results = []
            
            for item_html in items:
                m = HOME_ITEM_RE.search(item_html)
                if m:
                    link, img, code, title = m.groups()
                    preview_match = PREVIEW_URL_RE1.search(item_html)
                    if not preview_match:
                        preview_match = PREVIEW_URL_RE2.search(item_html)
                    preview_url = preview_match.group(1) if preview_match else ""
                    
                    meta_m = re.search(r'<div class="meta">\s*<div>([^<]+)</div>', item_html, re.IGNORECASE)
                    relative_time = meta_m.group(1).strip() if meta_m else ""
                    upload_date = parse_relative_time(relative_time)
                    
                    results.append({
                        "code": code.strip().upper(),
                        "title": title.strip(),
                        "cover": img.strip(),
                        "preview": preview_url.strip(),
                        "url": "https://javxx.com" + link.strip(),
                        "type": "normal",
                        "actress": parse_actress_from_title(title),
                        "relative_time": relative_time,
                        "upload_date": upload_date
                    })
            
            unique = []
            seen = set()
            for v in results:
                if v['code'] not in seen:
                    unique.append(v)
                    seen.add(v['code'])
            return {
                "videos": unique,
                "total_pages": total_pages,
                "current_page": current_page
            }
        except Exception as e:
            print("Home parse error:", e)
            return {"videos": [], "total_pages": 1, "current_page": 1}

    def get_home_videos(self, url=None):
        if not url:
            url = "https://javxx.com/tw"
        success, html = fetch_html_content(url)
        if not success:
            return {"videos": [], "total_pages": 1, "current_page": 1}
        return self.parse_home_videos(html, url)

    def fetch_page_and_parse_dates(self, base_url, page_num):
        if "tktube.com" in base_url:
            url = self.format_tktube_url(base_url, page_num)
        else:
            url = base_url
            if page_num > 1:
                if '?' in url:
                    url = f"{url}&page={page_num}"
                else:
                    url = f"{url}?page={page_num}"
                
        success, html = fetch_html_content(url)
        if not success:
            return []
            
        try:
            if "tktube.com" in base_url:
                blocks = html.split('<div class="item')[1:]
                results = []
                seen_codes = set()
                for block in blocks:
                    href_m = re.search(r'href="([^"]+)"', block)
                    if not href_m: continue
                    video_url = href_m.group(1)
                    
                    title_m = re.search(r'alt="([^"]+)"', block)
                    if not title_m:
                        title_m = re.search(r'<strong class="title">\s*(.*?)\s*</strong>', block, re.DOTALL)
                    title = title_m.group(1).strip() if title_m else ""
                    
                    # Optimized image extraction to support data-original, data-src, and raw src lazy-loads
                    img_url = ""
                    for attr in ["data-original", "data-src", "src"]:
                        img_m = re.search(attr + r'="([^"]+)"', block)
                        if img_m and img_m.group(1) and not any(x in img_m.group(1) for x in ["placeholder", "clear.gif", "transparent"]):
                            img_url = img_m.group(1)
                            break
                    if not img_url:
                        img_m = re.search(r'src="([^"]+)"', block)
                        img_url = img_m.group(1) if img_m else ""
                    
                    preview_m = re.search(r'data-preview="([^"]+)"', block)
                    preview_url = preview_m.group(1) if preview_m else ""
                    
                    if video_url.startswith('/'):
                        video_url = "https://tktube.com" + video_url
                        
                    # Optimized Advanced JAV / FC2 Code Matching
                    code_m = re.search(r'([a-zA-Z0-9]+-ppv-\d+|[a-zA-Z0-9]+-\d+(_\d+)?|fc2-ppv-\d+|fc2-\d+)', title.lower())
                    if not code_m:
                        code_m = re.search(r'([a-zA-Z0-9]+-ppv-\d+|[a-zA-Z0-9]+-\d+(_\d+)?|fc2-ppv-\d+|fc2-\d+)', video_url.lower())
                        
                    if code_m:
                        code = code_m.group(1).upper()
                    else:
                        continue
                        
                    if code in seen_codes:
                        continue
                    seen_codes.add(code)
                    
                    # Parse absolute upload date from block
                    date_m = re.search(r'<div class="added">\s*<em>([^<]+)</em>', block)
                    if not date_m:
                        date_m = re.search(r'<em>(\d{4}-\d{2}-\d{2})</em>', block)
                    upload_date = date_m.group(1).strip() if date_m else ""
                    
                    # Premium Clean Title Formatting
                    clean_title = title.replace(code, "").replace(code.lower(), "").strip()
                    clean_title = re.sub(r'[\[【\(（].*?[\]】\)）]', '', clean_title).strip()
                    clean_title = re.sub(r'^(hd|1080p|720p|高清|字幕|中字)\s*', '', clean_title, flags=re.IGNORECASE).strip()
                    if not clean_title:
                        clean_title = f"{code} 影片"
                    
                    results.append({
                        "code": code,
                        "title": clean_title,
                        "cover": img_url,
                        "url": video_url,
                        "preview": preview_url,
                        "type": "無碼破解版",  # Default all TKTube videos to Uncensored Leaked as requested
                        "actress": parse_actress_from_title(title),
                        "upload_date": upload_date,
                        "relative_time": f"加入日期: {upload_date}",
                        "source": "tktube"
                    })
                return results
            else:
                items = html.split('<div class="item">')[1:]
                results = []
                for item_html in items:
                    m = HOME_ITEM_RE.search(item_html)
                    if m:
                        link, img, code, title = m.groups()
                        preview_match = PREVIEW_URL_RE1.search(item_html)
                        if not preview_match:
                            preview_match = PREVIEW_URL_RE2.search(item_html)
                        preview_url = preview_match.group(1) if preview_match else ""
                        
                        meta_m = re.search(r'<div class="meta">\s*<div>([^<]+)</div>', item_html, re.IGNORECASE)
                        relative_time = meta_m.group(1).strip() if meta_m else ""
                        upload_date = parse_relative_time(relative_time)
                        
                        results.append({
                            "code": code.strip().upper(),
                            "title": title.strip(),
                            "cover": img.strip(),
                            "preview": preview_url.strip(),
                            "url": "https://javxx.com" + link.strip(),
                            "type": "normal",
                            "actress": parse_actress_from_title(title),
                            "relative_time": relative_time,
                            "upload_date": upload_date
                        })
                return results
        except Exception as e:
            return []

    def scan_pages_for_date(self, base_url, target_prefix):
        if not target_prefix:
            return []
            
        # Get total pages dynamically from the first page HTML
        success, html = fetch_html_content(base_url)
        total_pages = 100  # Default fallback
        if success:
            if "tktube.com" in base_url:
                total_match = re.search(r'Total:(\d+)', html)
                if total_match:
                    total_pages = min(int(total_match.group(1)), 500)
                else:
                    total_pages = 200
            else:
                page_nums = [int(p) for p in re.findall(r'page=(\d+)', html)]
                if page_nums:
                    total_pages = max(page_nums)
                
        # Perform logarithmic binary search to locate target date
        low = 1
        high = total_pages
        target_page = -1
        
        while low <= high:
            mid = (low + high) // 2
            time.sleep(0.05)  # Politeness delay
            videos = self.fetch_page_and_parse_dates(base_url, mid)
            if not videos:
                # If page is empty, shrink the search boundary
                high = mid - 1
                continue
                
            newest_date = videos[0].get('upload_date', '')
            oldest_date = videos[-1].get('upload_date', '')
            
            # Check for match on the current page
            has_match = any(v.get('upload_date', '').startswith(target_prefix) for v in videos)
            if has_match:
                target_page = mid
                break
                
            # If target prefix is older than the oldest date on page, it must be on a higher page number
            if oldest_date and oldest_date > target_prefix:
                low = mid + 1
            # If target prefix is newer than the newest date on page, it must be on a lower page number
            else:
                high = mid - 1
                
        if target_page == -1:
            # Fallback sequential search for the first 5 pages
            matching_pages = []
            for p in range(1, 6):
                time.sleep(0.05)
                videos = self.fetch_page_and_parse_dates(base_url, p)
                if any(v.get('upload_date', '').startswith(target_prefix) for v in videos):
                    matching_pages.append(p)
            return matching_pages
            
        # Contiguous range scan around target_page (capturing neighboring match pages)
        matching_pages = []
        for p in range(max(1, target_page - 3), min(total_pages + 1, target_page + 4)):
            time.sleep(0.05)
            videos = self.fetch_page_and_parse_dates(base_url, p)
            if videos and any(v.get('upload_date', '').startswith(target_prefix) for v in videos):
                matching_pages.append(p)
                
        return sorted(list(set(matching_pages)))

    def get_embed_url(self, url):
        if not url: return ""
        if "missav" in url:
            m = re.search(r'missav\.[a-z]+/(?:zh/|ja/|tw/|cn/|en/)?([^/?#]+)', url)
            if m:
                video_code = m.group(1)
                return f"https://missav.ws/play/{video_code}"
            return url
            
        if "tktube.com" in url:
            m = re.search(r'/videos/([0-9]+)/', url)
            if m:
                video_id = m.group(1)
                success, html = fetch_html_content(url)
                if success:
                    mp4_match = re.search(r'video_url:\s*[\'"]([^\'"]+\.mp4[^\'"]*)[\'"]', html)
                    if not mp4_match:
                        mp4_match = re.search(r'<source\s+src=[\'"]([^\'"]+\.mp4[^\'"]*)[\'"]', html)
                    if not mp4_match:
                        mp4_match = re.search(r'video_alt_url:\s*[\'"]([^\'"]+\.mp4[^\'"]*)[\'"]', html)
                    
                    if mp4_match:
                        mp4_url = mp4_match.group(1)
                        import urllib.parse
                        player_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>HTML5 Player</title>
    <style>
        body, html {{ margin:0; padding:0; width:100%; height:100%; background:#000; overflow:hidden; }}
        video {{ width:100%; height:100%; object-fit:contain; }}
    </style>
</head>
<body>
    <video id="video" src="{mp4_url}" controls autoplay playsinline></video>
</body>
</html>"""
                        encoded_html = urllib.parse.quote(player_html)
                        return f"data:text/html;charset=utf-8,{encoded_html}"
                return f"https://tktube.com/zh/embed/{video_id}/"
            return url
            
        if "tcav.85xvideo.com" in url:
            success, html = fetch_html_content(url)
            if success:
                m3u8_matches = re.findall(r'https?://[^"\']+\.m3u8', html)
                if m3u8_matches:
                    m3u8_url = m3u8_matches[0]
                    # Return premium, completely ad-free dynamic HLS.js data URI player!
                    import urllib.parse
                    player_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>HLS Player</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@1"></script>
    <style>
        body, html {{ margin:0; padding:0; width:100%; height:100%; background:#000; overflow:hidden; }}
        video {{ width:100%; height:100%; object-fit:contain; }}
    </style>
</head>
<body>
    <video id="video" controls autoplay playsinline></video>
    <script>
        var video = document.getElementById('video');
        var videoSrc = '{m3u8_url}';
        if (Hls.isSupported()) {{
            var hls = new Hls();
            hls.loadSource(videoSrc);
            hls.attachMedia(video);
        }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
            video.src = videoSrc;
        }}
    </script>
</body>
</html>"""
                    encoded_html = urllib.parse.quote(player_html)
                    return f"data:text/html;charset=utf-8,{encoded_html}"
            return url
            
        success, html = fetch_html_content(url)
        if not success:
            return url
            
        try:
            iframes = re.findall(r'<iframe\s+[^>]*?src=["\']([^"\']+)["\']', html, re.IGNORECASE)
            for src in iframes:
                lower_src = src.lower()
                if 'ad' in lower_src and 'load' not in lower_src:
                    continue
                if 'banner' in lower_src or 'pop' in lower_src:
                    continue
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = 'https://javxx.com' + src
                return src
            return url
        except Exception as e:
            print("Error fetching embed:", e)
            return url

    def fetch_tcav_info(self, ccode):
        url = f"https://tcav.85xvideo.com/?s={ccode}"
        success, html = fetch_html_content(url)
        if not success:
            return None
            
        try:
            img_matches = re.finditer(r'<img\s+post-id="(\d+)"[^>]*src="([^"]+)"[^>]*alt="([^"]+)"[^>]*>', html, re.IGNORECASE)
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
                            
                if detail_url:
                    # Match clean code to the slug/title
                    slug = detail_url.split('/')[-2] if detail_url.endswith('/') else detail_url.split('/')[-1]
                    slug_decoded = urllib.parse.unquote(slug).lower()
                    ccode_clean = ccode.lower()
                    
                    if ccode_clean in slug_decoded or ccode_clean.replace("-", "") in slug_decoded or ccode_clean in alt.lower():
                        return {
                            "url": detail_url,
                            "img": img_url,
                            "preview": "",
                            "type": "FC2" if "FC2" in ccode.upper() else "無碼破解版"
                        }
            return None
        except Exception as e:
            print("TCAV parse error:", e)
            return None

    def parse_tcav_home_videos(self, html, url=""):
        if not html:
            return {"videos": [], "total_pages": 1, "current_page": 1}
        current_page = 1
        page_match = re.search(r'[?&]paged?=(\d+)', url)
        if page_match:
            current_page = int(page_match.group(1))
        
        try:
            total_pages = current_page
            page_nums = [int(p) for p in re.findall(r'/page/(\d+)', html)]
            if page_nums:
                total_pages = max(max(page_nums), current_page)
                
            img_matches = re.finditer(r'<img\s+post-id="(\d+)"[^>]*src="([^"]+)"[^>]*alt="([^"]+)"[^>]*>', html, re.IGNORECASE)
            
            results = []
            seen_codes = set()
            import urllib.parse
            
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
                if not title:
                    title = slug_decoded.replace(code, "").replace("-", " ").strip()
                if not title:
                    title = alt
                    
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                
                results.append({
                    "code": code,
                    "title": title,
                    "cover": img_url,
                    "url": detail_url,
                    "preview": "",
                    "type": "FC2" if "FC2" in code else "正常版",
                    "actress": "未知女優",
                    "upload_date": "2026-05-18",
                    "relative_time": "最新",
                    "source": "tcav"
                })
                
            return {
                "videos": results,
                "total_pages": total_pages,
                "current_page": current_page
            }
        except Exception as e:
            print("TCAV parse error:", e)
            return {"videos": [], "total_pages": 1, "current_page": current_page}

    def get_tcav_home_videos(self, url=None):
        if not url or url == "tcav":
            url = "https://tcav.85xvideo.com/"
        elif url.startswith("tcav"):
            page_match = re.search(r'[?&]page=(\d+)', url)
            if page_match:
                url = f"https://tcav.85xvideo.com/?paged={page_match.group(1)}"
            else:
                url = "https://tcav.85xvideo.com/"
            
        current_page = 1
        page_match = re.search(r'[?&]paged?=(\d+)', url)
        if page_match:
            current_page = int(page_match.group(1))
            
        success, html = fetch_html_content(url)
        if not success:
            return {"videos": [], "total_pages": 1, "current_page": current_page}
            
        return self.parse_tcav_home_videos(html, url)

    def parse_tktube_home_videos(self, html, url=""):
        if not html:
            return {"videos": [], "total_pages": 1, "current_page": 1}
        current_page = 1
        page_match = re.search(r'[?&]page=(\d+)', url)
        if page_match:
            current_page = int(page_match.group(1))
        else:
            slash_match = re.search(r'/zh/(\d+)/?$', url)
            if not slash_match:
                slash_match = re.search(r'/(\d+)/?$', url)
            if slash_match:
                current_page = int(slash_match.group(1))
            
        try:
            total_pages = current_page
            total_match = re.search(r'Total:(\d+)', html)
            if total_match:
                total_pages = int(total_match.group(1))
            else:
                total_change_match = re.search(r'_pagechange\([^,]+,\s*(\d+)\)', html)
                if total_change_match:
                    total_pages = int(total_change_match.group(1))
                else:
                    page_nums = [int(p) for p in re.findall(r'page=(\d+)', html)]
                    if page_nums:
                        total_pages = max(max(page_nums), current_page)
                    else:
                        total_pages = max(current_page + 10, 50)
                
            blocks = html.split('<div class="item')[1:]
            results = []
            seen_codes = set()
            
            for block in blocks:
                href_m = re.search(r'href="([^"]+)"', block)
                if not href_m: continue
                video_url = href_m.group(1)
                
                title_m = re.search(r'alt="([^"]+)"', block)
                if not title_m:
                    title_m = re.search(r'<strong class="title">\s*(.*?)\s*</strong>', block, re.DOTALL)
                title = title_m.group(1).strip() if title_m else ""
                
                img_url = ""
                for attr in ["data-original", "data-src", "src"]:
                    img_m = re.search(attr + r'="([^"]+)"', block)
                    if img_m and img_m.group(1) and not any(x in img_m.group(1) for x in ["placeholder", "clear.gif", "transparent"]):
                        img_url = img_m.group(1)
                        break
                if not img_url:
                    img_m = re.search(r'src="([^"]+)"', block)
                    img_url = img_m.group(1) if img_m else ""
                
                preview_m = re.search(r'data-preview="([^"]+)"', block)
                preview_url = preview_m.group(1) if preview_m else ""
                
                if video_url.startswith('/'):
                    video_url = "https://tktube.com" + video_url
                    
                code_m = re.search(r'([a-zA-Z0-9]+-ppv-\d+|[a-zA-Z0-9]+-\d+(_\d+)?|fc2-ppv-\d+|fc2-\d+)', title.lower())
                if not code_m:
                    code_m = re.search(r'([a-zA-Z0-9]+-ppv-\d+|[a-zA-Z0-9]+-\d+(_\d+)?|fc2-ppv-\d+|fc2-\d+)', video_url.lower())
                
                if code_m:
                    code = code_m.group(1).upper()
                else:
                    continue
                    
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                
                date_m = re.search(r'<div class="added">\s*<em>([^<]+)</em>', block)
                if not date_m:
                    date_m = re.search(r'<em>(\d{4}-\d{2}-\d{2})</em>', block)
                upload_date = date_m.group(1).strip() if date_m else ""
                
                clean_title = title.replace(code, "").replace(code.lower(), "").strip()
                clean_title = re.sub(r'[\[【\(（].*?[\]】\)）]', '', clean_title).strip()
                clean_title = re.sub(r'^(hd|1080p|720p|高清|字幕|中字)\s*', '', clean_title, flags=re.IGNORECASE).strip()
                if not clean_title:
                    clean_title = f"{code} 影片"
                
                results.append({
                    "code": code,
                    "title": clean_title,
                    "cover": img_url,
                    "url": video_url,
                    "preview": preview_url,
                    "type": "無碼破解版",
                    "actress": parse_actress_from_title(title),
                    "upload_date": upload_date,
                    "relative_time": f"加入日期: {upload_date}",
                    "source": "tktube"
                })
                
            return {
                "videos": results,
                "total_pages": total_pages,
                "current_page": current_page
            }
        except Exception as e:
            print("TKTube parse error:", e)
            return {"videos": [], "total_pages": 1, "current_page": current_page}

    def format_tktube_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        
        # Strip any trailing page numbers or subpages
        clean_url = re.sub(r'([?&]page=\d+|\/zh\/\d+\/|\/\d+\/)$', '', base_url)
        if not clean_url.endswith('/'):
            clean_url += '/'
            
        # Home page pagination
        if clean_url in ['https://tktube.com/zh/', 'https://tktube.com/zh/latest-updates/']:
            return f"https://tktube.com/zh/latest-updates/{page_num}/"
            
        # Category page pagination (e.g. most-popular, top-rated, categories, etc.)
        if 'tktube.com/zh/' in clean_url:
            return f"{clean_url}{page_num}/"
            
        return f"{clean_url}?page={page_num}"

    def get_tktube_home_videos(self, url=None):
        log_file = "dist/debug_pagination.log"
        try:
            os.makedirs("dist", exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"\n--- TKTube Request: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                lf.write(f"Incoming URL: {url}\n")
        except Exception:
            pass

        if not url or url == "tktube":
            url = "https://tktube.com/zh/latest-updates/"
        elif url.startswith("tktube"):
            page_match = re.search(r'[?&]page=(\d+)', url)
            if page_match:
                url = f"https://tktube.com/zh/latest-updates/?page={page_match.group(1)}"
            else:
                url = "https://tktube.com/zh/latest-updates/"
            
        current_page = 1
        page_match = re.search(r'[?&]page=(\d+)', url)
        if page_match:
            current_page = int(page_match.group(1))
        else:
            # 解析斜線格式頁碼：.../categories/hash/2/
            slash_match = re.search(r'/(\d+)/?$', url)
            if slash_match:
                current_page = int(slash_match.group(1))
        
        # 建立干淨的基礎 URL（空頁碼段）
        base_url = re.sub(r'[?&]page=\d+', '', url)  # 移除 ?page=N
        base_url = re.sub(r'/\d+/?$', '/', base_url)  # 移除 /N/ 於結尾
        if not base_url.endswith('/'):
            base_url += '/'
        
        target_url = self.format_tktube_url(base_url, current_page)
        
        try:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"Parsed Page: {current_page}\n")
                lf.write(f"Formatted Base URL: {base_url}\n")
                lf.write(f"Target URL: {target_url}\n")
        except Exception:
            pass

        success, html = fetch_html_content(target_url)
        
        try:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"Fetch HTML Success: {success} (Length: {len(html) if success else 0})\n")
        except Exception:
            pass

        if not success:
            return {"videos": [], "total_pages": 1, "current_page": current_page}
            
        res = self.parse_tktube_home_videos(html, target_url)
        
        try:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"Parsed Videos Count: {len(res.get('videos', []))}\n")
                lf.write(f"Returned Current Page: {res.get('current_page')}\n")
                lf.write(f"Returned Total Pages: {res.get('total_pages')}\n")
        except Exception:
            pass

        return res

    def parse_tktube_html_client(self, html, url):
        try:
            return self.parse_tktube_home_videos(html, url)
        except Exception as e:
            print("Client HTML parse error:", e)
            return {"videos": [], "total_pages": 1, "current_page": 1}

    def parse_tktube_total_pages_client(self, html):
        try:
            total_pages = 1
            total_match = re.search(r'Total:(\d+)', html)
            if total_match:
                total_pages = int(total_match.group(1))
            else:
                total_change_match = re.search(r'_pagechange\([^,]+,\s*(\d+)\)', html)
                if total_change_match:
                    total_pages = int(total_change_match.group(1))
                else:
                    page_nums = [int(p) for p in re.findall(r'page=(\d+)', html)]
                    if page_nums:
                        total_pages = max(page_nums)
                    else:
                        total_pages = 50
            return total_pages
        except Exception as e:
            print("Client HTML parse total pages error:", e)
            return 50

    def parse_page_dates_client(self, html, target_prefix):
        try:
            blocks = html.split('<div class="item')[1:]
            if not blocks:
                return {"newest_date": "", "oldest_date": "", "has_match": False}
            
            dates = []
            for block in blocks:
                date_m = re.search(r'<div class="added">\s*<em>([^<]+)</em>', block)
                if not date_m:
                    date_m = re.search(r'<em>(\d{4}-\d{2}-\d{2})</em>', block)
                if date_m:
                    dates.append(date_m.group(1).strip())
            
            if not dates:
                return {"newest_date": "", "oldest_date": "", "has_match": False}
                
            newest = dates[0]
            oldest = dates[-1]
            has_match = any(d.startswith(target_prefix) for d in dates)
            
            return {
                "newest_date": newest,
                "oldest_date": oldest,
                "has_match": has_match
            }
        except Exception as e:
            print("Client HTML parse page dates error:", e)
            return {"newest_date": "", "oldest_date": "", "has_match": False}

    def init_playwright_background(self):
        try:
            from playwright.sync_api import sync_playwright
            print("Playwright: Initializing worker thread headless browser...")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-web-security',
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox'
                    ]
                )
                browser_context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1280, 'height': 720}
                )
                self.browser_context = browser_context
                print("Playwright: Headless Chromium worker thread active!")
                
                # 進入常駐工作佇列迴圈 (Thread Queue Loop)
                while True:
                    task = self.playwright_queue.get()
                    if task is None: # 退出訊號
                        break
                    
                    url, response_queue, timeout_ms = task
                    try:
                        page = browser_context.new_page()
                        
                        # 資源路由攔截器 (Adblocker & Media Blocker)
                        def block_ad_and_media(route):
                            request = route.request
                            resource_type = request.resource_type
                            req_url = request.url.lower()
                            
                            block_types = ["image", "media", "font", "stylesheet"]
                            ad_keywords = ["google-analytics", "doubleclick", "adservice", "popunder", "exoclick", "juicyads", "trafficjunky", "histats"]
                            
                            if resource_type in block_types or any(kw in req_url for kw in ad_keywords):
                                route.abort()
                            else:
                                route.continue_()
                                
                        page.route("**/*", block_ad_and_media)
                        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                        html = page.content()
                        page.close()
                        response_queue.put(html)
                    except Exception as e:
                        print(f"Playwright worker error for {url}: {e}")
                        try:
                            page.close()
                        except:
                            pass
                        response_queue.put(None)
                        
                # 關閉瀏覽器
                browser.close()
        except Exception as e:
            self.playwright_err = str(e)
            print("Playwright worker thread crash/error:", e)

    def playwright_fetch_html(self, url, timeout_ms=15000):
        # 如果背景執行緒尚未就緒或發生錯誤
        if not self.browser_context:
            print("Playwright: Worker not ready yet, falling back...")
            return None
            
        import queue
        response_queue = queue.Queue()
        
        # 發送工作給背景常駐執行緒
        self.playwright_queue.put((url, response_queue, timeout_ms))
        
        try:
            # 阻塞等待背景執行緒回傳結果
            html = response_queue.get(timeout=timeout_ms / 1000.0)
            return html
        except Exception as e:
            print(f"Playwright fetch timeout/error for {url}: {e}")
            return None

    def __del__(self):
        try:
            self.playwright_queue.put(None)
        except:
            pass

    def heal_favorites_background(self):
        # Auto-normalizes and heals favorites list links, previews, clean codes, and actress names silently
        import time
        # Small sleep on startup to let pywebview render first
        time.sleep(1.0)
        
        def is_invalid_actress(actress):
            if not actress:
                return True
            actress_clean = str(actress).replace('*', '').strip()
            return actress_clean in ("", "未知", "未知女優", "新加入", "女優", "None", "undefined")
            
        needs_healing = []
        for idx, item in enumerate(self.data):
            raw = item.get('raw') or item.get('code') or ""
            ccode = clean_code(raw)
            # Heal if code is not fully cleaned, or link is missing, or not found previously, or actress is unknown
            if (item.get('code') != ccode.upper()) or (not item.get('url')) or (not item.get('found')) or is_invalid_actress(item.get('actress')):
                needs_healing.append((idx, raw, ccode))
                
        if not needs_healing:
            return
            
        print(f"Healer: Automatically cleaning and healing {len(needs_healing)} favorites in background...")
        
        changed = False
        # Limit to max 5 workers to be friendly to servers
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_idx = {
                executor.submit(self.fetch_video_info, raw): idx 
                for idx, raw, ccode in needs_healing
            }
            
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    res = future.result()
                    if res and res.get('found'):
                        original_id = self.data[idx].get('id')
                        original_actress = self.data[idx].get('actress')
                        scraped_actress = res.get('actress')
                        
                        # Decide final actress
                        if is_invalid_actress(original_actress) and not is_invalid_actress(scraped_actress):
                            final_actress = scraped_actress
                        else:
                            final_actress = original_actress if not is_invalid_actress(original_actress) else scraped_actress
                            
                        self.data[idx] = {
                            "id": original_id,
                            "raw": self.data[idx].get('raw') or self.data[idx].get('code'),
                            "clean": res["clean"],
                            "code": res["code"],
                            "url": res["url"],
                            "img": res["img"],
                            "preview": res.get("preview") or self.data[idx].get("preview") or "",
                            "found": True,
                            "type": res["type"],
                            "actress": final_actress
                        }
                        changed = True
                except Exception as e:
                    print(f"Healer: Failed to heal favorite index {idx}: {e}")
                    
        if changed:
            print("Healer: Healing complete! Saving updated JSON and updating web interface...")
            self.save_videos(self.data)
            # Evaluate JS in webview to silently refresh favorites grid
            try:
                webview.windows[0].evaluate_js("if(typeof loadData === 'function') { loadData(); }")
            except Exception as e:
                pass

    def copy_to_clipboard(self, text):
        import ctypes
        try:
            if not ctypes.windll.user32.OpenClipboard(None):
                return False
            ctypes.windll.user32.EmptyClipboard()
            text_bytes = text.encode('utf-16le')
            h_mem = ctypes.windll.kernel32.GlobalAlloc(0x0002, len(text_bytes) + 2)
            if not h_mem:
                ctypes.windll.user32.CloseClipboard()
                return False
            p_mem = ctypes.windll.kernel32.GlobalLock(h_mem)
            if not p_mem:
                ctypes.windll.kernel32.GlobalFree(h_mem)
                ctypes.windll.user32.CloseClipboard()
                return False
            ctypes.memmove(p_mem, text_bytes, len(text_bytes))
            ctypes.memset(p_mem + len(text_bytes), 0, 2)
            ctypes.windll.kernel32.GlobalUnlock(h_mem)
            ctypes.windll.user32.SetClipboardData(13, h_mem)
            ctypes.windll.user32.CloseClipboard()
            return True
        except Exception as e:
            print(f"Clipboard Error: {e}")
            return False

    # JApp Update API Methods
    def get_version(self):
        """ 獲取當前版本號 """
        return self.current_version

    def check_for_updates(self):
        """ 檢查 GitHub Releases 以獲取更新資訊 """
        try:
            res = self.version_manager.check_for_updates()
            return res
        except Exception as e:
            print(f"check_for_updates error: {e}")
            return None

    def start_update(self, download_url):
        """ 啟動背景更新下載與應用流程 """
        if self.update_progress["status"] in ["downloading", "extracting", "applying"]:
            return {"success": False, "msg": "更新已在進行中"}
        
        self.update_progress = {
            "status": "downloading",
            "percent": 0,
            "detail": "準備下載更新檔案...",
            "error": None
        }
        self._notify_js_progress()
        threading.Thread(target=self._run_update_flow, args=(download_url,), daemon=True).start()
        return {"success": True, "msg": "更新流程已成功啟動"}

    def get_update_progress(self):
        """ 供前端輪詢更新進度 """
        return self.update_progress

    def _notify_js_progress(self):
        """ 主動推播進度到 Web 前端 """
        if self._window:
            try:
                status = self.update_progress["status"]
                percent = self.update_progress["percent"]
                detail = self.update_progress["detail"]
                error = self.update_progress["error"] or ""
                
                detail_esc = detail.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
                error_esc = error.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
                
                js = f"if (typeof onUpdateProgress === 'function') {{ onUpdateProgress('{status}', {percent}, '{detail_esc}', '{error_esc}'); }}"
                self._window.evaluate_js(js)
            except Exception as e:
                print(f"Failed to notify JS progress: {e}")

    def _run_update_flow(self, download_url):
        """ 背景更新執行緒 """
        try:
            # 1. 下載
            def progress_callback(downloaded, total):
                if total > 0:
                    percent = int((downloaded / total) * 40)  # 下載佔前 40% 進度
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    self.update_progress = {
                        "status": "downloading",
                        "percent": percent,
                        "detail": f"正在下載更新: {downloaded_mb:.2f}MB / {total_mb:.2f}MB ({int((downloaded/total)*100)}%)",
                        "error": None
                    }
                    self._notify_js_progress()
                    
            zip_path = self.version_manager.download_update(download_url, progress_callback)
            if not zip_path:
                raise Exception("下載更新檔案失敗，請檢查網路連線或稍後再試。")
                
            # 2. 解壓縮
            self.update_progress = {
                "status": "extracting",
                "percent": 40,
                "detail": "正在解壓縮更新檔案...",
                "error": None
            }
            self._notify_js_progress()
            
            # 模擬進度條動態跑一下
            for p in range(40, 70, 5):
                time.sleep(0.1)
                self.update_progress["percent"] = p
                self._notify_js_progress()
                
            extract_dir = self.version_manager.extract_update(zip_path)
            if not extract_dir:
                raise Exception("解壓縮更新檔案失敗，檔案可能已損壞。")
                
            self.update_progress["percent"] = 70
            self.update_progress["detail"] = "解壓縮完成，準備安裝更新..."
            self._notify_js_progress()
            time.sleep(0.3)
            
            # 3. 部署
            self.update_progress = {
                "status": "applying",
                "percent": 80,
                "detail": "正在創建並執行更新腳本...",
                "error": None
            }
            self._notify_js_progress()
            
            success = self.version_manager.apply_update(extract_dir, restart_after=True)
            if success:
                self.update_progress = {
                    "status": "completed",
                    "percent": 100,
                    "detail": "更新檔案佈署成功！程式將於 2 秒後重啟以套用更新...",
                    "error": None
                }
                self._notify_js_progress()
                time.sleep(2.0)
                os._exit(0)
            else:
                raise Exception("無法啟動更新批次腳本，請確認是否有系統權限。")
                
        except Exception as e:
            self.update_progress = {
                "status": "error",
                "percent": 0,
                "detail": f"更新失敗: {str(e)}",
                "error": str(e)
            }
            self._notify_js_progress()

if __name__ == '__main__':
    api = Api()
    html_path = os.path.join(get_resource_path(), 'index.html')
    window_title = f"JApp_{VERSION}"
    window = webview.create_window(window_title, html_path, js_api=api, width=1200, height=800)
    api._window = window
    webview.start(debug=False)
