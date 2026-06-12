import sys
import os

# Add main directory to sys.path
sys.path.append(os.path.abspath('main'))

from japp import Api

if __name__ == '__main__':
    api = Api()
    codes = ["MAZO-033", "HMN-446", "TCD-332", "MARA-041"]
    for code in codes:
        print(f"--- Fetching {code} ---")
        res = api.fetch_video_info(code)
        print(f"Found: {res.get('found')}")
        print(f"Type: {res.get('type')}")
        print(f"Actress: {res.get('actress')}")
        print(f"Title: {res.get('japanese_title') or res.get('raw')}")
        print(f"URL: {res.get('url')}")
        print()
