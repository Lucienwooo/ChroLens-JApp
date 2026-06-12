import re

with open("hmn_446.html", "r", encoding="utf-8") as f:
    html = f.read()

lines = html.splitlines()
for idx, line in enumerate(lines):
    if "北野" in line:
        print(f"Line {idx+1}: {line.strip()[:200]}")
