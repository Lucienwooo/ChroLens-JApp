import json
from urllib.parse import urlparse
from collections import Counter

with open("main/Favorites.json", "r", encoding="utf-8") as f:
    data = json.load(f)

domains = []
for item in data:
    url = item.get("url")
    if url:
        parsed = urlparse(url)
        domains.append(parsed.netloc)
    else:
        domains.append("None")

print("Domain Distribution in main/Favorites.json:")
print(Counter(domains))
