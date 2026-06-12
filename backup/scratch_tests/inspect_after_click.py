import sys
import re

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

with open("scratch/after_click.html", "r", encoding="utf-8") as f:
    content = f.read()

# Print lines containing modal-body or ageVerify or error or alert
for line_num, line in enumerate(content.splitlines(), 1):
    if any(w in line.lower() for w in ["modal-body", "ageverify", "error", "alert", "warn", "fail", "success"]):
        print(f"Line {line_num}: {line.strip()[:150]}")
