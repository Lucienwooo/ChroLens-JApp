import sys
import os
import json
import time
import concurrent.futures

sys.stdout.reconfigure(encoding='utf-8')

# Add main directory to sys.path
sys.path.append(os.path.abspath('main'))

from japp import Api

def process_item(api, item, idx, total):
    code = item.get("code")
    raw = item.get("raw")
    url = item.get("url", "")
    actress = item.get("actress", "未知")
    jp_title = item.get("japanese_title", "")
    
    # Check if this item already has a clean URL, actress, and Japanese title
    is_clean = (
        url and 
        ("javxx.com" not in url) and 
        ("missav.ws" not in url) and 
        (actress and actress not in ("未知", "未知女優", "")) and 
        (jp_title and jp_title.strip() != "")
    )
    
    if is_clean:
        print(f"[{idx+1}/{total}] Skipping already clean item: {code}")
        return False, item
        
    print(f"[{idx+1}/{total}] Processing JAV code: {code} (Raw: {raw})")
    try:
        res = api.fetch_video_info(code or raw)
        if res and res.get("found"):
            item["url"] = res.get("url") or item.get("url")
            item["img"] = res.get("img") or item.get("img")
            item["preview"] = res.get("preview") or item.get("preview")
            item["actress"] = res.get("actress") or item.get("actress")
            item["japanese_title"] = res.get("japanese_title") or item.get("japanese_title")
            item["found"] = True
            
            if "missav.ws" in item["url"]:
                item["type"] = "正常版"
                
            print(f"    -> Success {code}: {item['url']} | Actress: {item['actress']} | Title: {item['japanese_title']}")
            return True, item
        else:
            print(f"    -> Scrape failed or not found for {code}.")
            return False, item
    except Exception as e:
        print(f"    -> Error processing {code}: {e}")
        return False, item

def migrate_parallel():
    print("Initializing Api and loading Favorites database...")
    api = Api()
    
    total = len(api.data)
    print(f"Loaded {total} favorites.")
    
    # We will use ThreadPoolExecutor to run tasks in parallel
    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for idx, item in enumerate(api.data):
            f = executor.submit(process_item, api, item, idx, total)
            futures.append(f)
            
        updated_count = 0
        for idx, f in enumerate(concurrent.futures.as_completed(futures)):
            success, updated_item = f.result()
            if success:
                updated_count += 1
            
            # Periodically save progress to DB files
            if (idx + 1) % 5 == 0 or (idx + 1) == total:
                print(f"Saving progress to database files (completed {idx+1}/{total})...")
                api.save_videos(api.data)
                
    print(f"\nMigration Complete! Total: {total}, Updated/Cleaned: {updated_count}")

if __name__ == '__main__':
    migrate_parallel()
