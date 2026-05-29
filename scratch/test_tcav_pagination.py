import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import Api

api = Api()

# Test TCAV Page 1
print("Calling get_tcav_home_videos for Page 1...")
res1 = api.get_tcav_home_videos("tcav")
videos1 = res1.get("videos", [])
print(f"Page 1 returned {len(videos1)} videos. First video code: {videos1[0]['code'] if videos1 else 'None'}")
print(f"Page 1 reported current_page: {res1.get('current_page')}")

# Test TCAV Page 2
print("\nCalling get_tcav_home_videos for Page 2 (with ?page=2)...")
res2 = api.get_tcav_home_videos("tcav?page=2")
videos2 = res2.get("videos", [])
print(f"Page 2 returned {len(videos2)} videos. First video code: {videos2[0]['code'] if videos2 else 'None'}")
print(f"Page 2 reported current_page: {res2.get('current_page')}")

# Check duplicates
codes1 = [v['code'] for v in videos1]
codes2 = [v['code'] for v in videos2]
overlap = set(codes1).intersection(set(codes2))
print(f"\nOverlap between Page 1 and Page 2: {len(overlap)} codes. Overlap codes: {overlap}")
