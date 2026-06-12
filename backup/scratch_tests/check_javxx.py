import json

with open("main/Favorites.json", "r", encoding="utf-8") as f:
    data = json.load(f)

javxx_count = sum(1 for item in data if item.get("url") and "javxx.com" in item["url"])
empty_url_count = sum(1 for item in data if not item.get("url"))
total = len(data)

print(f"Total entries: {total}")
print(f"javxx.com URLs: {javxx_count}")
print(f"Empty/No URLs: {empty_url_count}")
