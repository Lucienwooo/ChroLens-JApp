import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Starting Playwright to check cookies detailed attributes...")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        page.goto("https://www.javbus.com/MAZO-033", timeout=15000)
        
        chk = page.query_selector("input[type='checkbox']")
        btn = page.query_selector("input#submit")
        if chk and btn:
            chk.check()
            page.wait_for_timeout(500)
            btn.click()
            page.wait_for_load_state("networkidle")
            
        cookies = context.cookies()
        print("Cookies attributes:")
        for c in cookies:
            print(f"Name: {c['name']}")
            print(f"  Value: {c['value']}")
            print(f"  Domain: {c['domain']}")
            print(f"  Path: {c['path']}")
            print(f"  Expires: {c.get('expires')}")
            print(f"  Secure: {c.get('secure')}")
            print(f"  HTTPOnly: {c.get('httpOnly')}")
            
        browser.close()
except Exception as e:
    print("Error:", e)
