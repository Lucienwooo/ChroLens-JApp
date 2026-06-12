import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Starting Playwright to inspect form elements...")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        page.goto("https://www.javbus.com/MAZO-033", timeout=15000)
        
        # Initial form state
        print("Initial form HTML:")
        print(page.locator("form#form1").evaluate("el => el.outerHTML"))
        
        # Check checkbox
        chk = page.query_selector("input[type='checkbox']")
        if chk:
            print("Checking checkbox...")
            chk.check()
            page.wait_for_timeout(500)
            
        # Form state after check
        print("Form HTML after checking:")
        print(page.locator("form#form1").evaluate("el => el.outerHTML"))
        
        browser.close()
except Exception as e:
    print("Error:", e)
