import sys
import re

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

with open("scratch/javbus.html", "r", encoding="utf-8") as f:
    content = f.read()

# Find all a and button elements with regex
matches = re.findall(r'<(?:a|button)[^>]*>.*?</(?:a|button)>', content, re.DOTALL | re.IGNORECASE)
for idx, match in enumerate(matches):
    clean = re.sub(r'\s+', ' ', match).strip()
    if 'trigger-overlay' in clean or 'back()' in clean or 'warning' in clean or 'alert' in clean or 'verify' in clean or 'confirm' in clean or 'button' in clean:
        print(f"{idx}: {clean[:200]}")
