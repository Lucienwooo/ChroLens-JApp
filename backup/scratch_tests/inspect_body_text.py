import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Starting Playwright to inspect body text...")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        page.goto("https://www.javbus.com/MAZO-033", timeout=15000)
        
        print("Page URL:", page.url)
        print("Page Title:", page.title())
        print("Body text:")
        print(page.locator("body").inner_text())
        
        browser.close()
except Exception as e:
    print("Error:", e)
