import urllib.request

url = "https://www.javbus.com/js/focus.js?v=8.7"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        js = r.read().decode('utf-8')
        print("focus.js length:", len(js))
        for line in js.splitlines():
            if "cookie" in line.lower() or "age" in line.lower() or "verify" in line.lower() or "submit" in line.lower():
                print(line.strip()[:150])
except Exception as e:
    print("Error:", e)
