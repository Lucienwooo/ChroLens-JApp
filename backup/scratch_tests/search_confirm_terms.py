import sys
import re

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

with open("scratch/javbus.html", "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if any(w in line.lower() for w in ["18", "enter", "agree", "yes", "confirm", "over", "已滿", "進入"]):
            print(f"Line {line_num}: {line.strip()[:150]}")
