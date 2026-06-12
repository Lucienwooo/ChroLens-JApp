import re
import sys

# Reconfigure stdout to use utf-8
sys.stdout.reconfigure(encoding='utf-8')

def search_in_file(filepath, pattern):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for idx, line in enumerate(lines):
        if re.search(pattern, line, re.IGNORECASE):
            print(f"{idx+1}: {line.strip()}")

if __name__ == '__main__':
    pattern = sys.argv[1] if len(sys.argv) > 1 else 'syncPanesData'
    search_in_file('main/script.js', pattern)
