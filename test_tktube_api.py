import json
from app import Api

api = Api()
url = "https://tktube.com/zh/categories/454545388bfe05b5b43cdc4fb9496ac6/?page=2"
print(f"Simulating frontend calling get_tktube_home_videos with: {url}")
res = api.get_tktube_home_videos(url)
print("\n--- Result Summary ---")
print(f"Type of res: {type(res)}")
if isinstance(res, dict):
    print(f"Keys: {list(res.keys())}")
    print(f"Current Page: {res.get('current_page')}")
    print(f"Total Pages: {res.get('total_pages')}")
    videos = res.get('videos', [])
    print(f"Videos count: {len(videos)}")
    if videos:
        print("First video example:")
        print(json.dumps(videos[0], indent=2, ensure_ascii=False))
else:
    print(res)
