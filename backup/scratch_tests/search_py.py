import re
import sys

def search_with_context(pattern, filepath, context_lines=10):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if re.search(pattern, line, re.IGNORECASE):
            print(f"Match at line {i+1}:")
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            for j in range(start, end):
                print(f"{j+1}: {lines[j]}", end="")
            print("-" * 40)
            
if __name__ == "__main__":
    search_with_context(sys.argv[1], sys.argv[2])
