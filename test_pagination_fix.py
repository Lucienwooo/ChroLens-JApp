import sys, os
sys.path.insert(0, '.')

from app import Api

api = Api()

# 測試1: 前端新格式 - 直接傳斜線格式 URL
url1 = "https://tktube.com/zh/categories/454545388bfe05b5b43cdc4fb9496ac6/2/"
print(f"=== 測試1: 斜線格式分頁 URL ===")
print(f"傳入 URL: {url1}")
res1 = api.get_tktube_home_videos(url1)
print(f"current_page: {res1.get('current_page')}")
print(f"total_pages: {res1.get('total_pages')}")
print(f"videos count: {len(res1.get('videos', []))}")
if res1.get('videos'):
    print(f"第一部影片代碼: {res1['videos'][0].get('code')}")

print()

# 測試2: 舊格式 (仍需相容)
url2 = "https://tktube.com/zh/categories/454545388bfe05b5b43cdc4fb9496ac6/?page=2"
print(f"=== 測試2: 查詢參數格式 URL ===")
print(f"傳入 URL: {url2}")
res2 = api.get_tktube_home_videos(url2)
print(f"current_page: {res2.get('current_page')}")
print(f"total_pages: {res2.get('total_pages')}")
print(f"videos count: {len(res2.get('videos', []))}")
if res2.get('videos'):
    print(f"第一部影片代碼: {res2['videos'][0].get('code')}")

print()
# 驗證兩個頁面返回不同內容
if res1.get('videos') and res2.get('videos'):
    codes1 = {v['code'] for v in res1['videos']}
    codes2 = {v['code'] for v in res2['videos']}
    same = codes1 & codes2
    print(f"=== 相同影片數: {len(same)} (應該高度重疊，確認兩個都是第2頁) ===")

print("測試完成！")
