import glob
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

for fpath in glob.glob("c:/Users/Lucien/Downloads/02_影片暫存區/jav_app/*.*"):
    if fpath.endswith((".py", ".js", ".html")):
        with open(fpath, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                if "loadHomeContent" in line:
                    safe = line.strip().encode('ascii', errors='replace').decode('ascii')
                    print(f"{fpath} L{idx}: {safe}")
