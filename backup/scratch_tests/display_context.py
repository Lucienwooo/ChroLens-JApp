import sys

def display_context(filepath, lines_to_show):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for l in lines_to_show:
        print(f"=== Line {l} ===")
        start = max(0, l - 10)
        end = min(len(lines), l + 10)
        for i in range(start, end):
            print(f"{i+1}: {lines[i].strip()}")

if __name__ == '__main__':
    lines = [int(sys.argv[1])] if len(sys.argv) > 1 else [2500]
    display_context('main/japp.py', lines)
