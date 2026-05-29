import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

def find_in_file(filepath, pattern):
    print(f"--- Searching in {filepath} for pattern ---")
    with open(filepath, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f, 1):
            if re.search(pattern, line, re.IGNORECASE):
                safe_line = line.strip().encode('ascii', errors='replace').decode('ascii')
                print(f"{idx}: {safe_line}")

find_in_file(r"c:\Users\Lucien\Downloads\02_影片暫存區\jav_app\script.js", r"saveHomeUrlBtn|homeUrlInput")
