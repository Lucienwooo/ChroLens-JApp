import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

with open("hmn_446.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find all occurrences of "北野"
for m in re.finditer(r"北野", html):
    start = max(0, m.start() - 150)
    end = min(len(html), m.end() + 150)
    print(f"--- Match at index {m.start()} ---")
    print(html[start:end].strip().replace("\n", " "))
