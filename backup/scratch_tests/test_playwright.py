import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Starting Playwright...")
try:
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        print("Creating context...")
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        print("Navigating to av-wiki...")
        page.goto("https://av-wiki.net/mazo-033/", timeout=15000)
        print("Page title:", page.title())
        html = page.content()
        print("Content length:", len(html))
        # Look for the actress name in html
        import re
        m_body_actresses = re.search(r'AV女優名\s*：\s*(.*?)</li>', html, re.DOTALL)
        if m_body_actresses:
            actresses = re.findall(r'<a[^>]*>([^<]+)</a>', m_body_actresses.group(1))
            print("Parsed actresses:", actresses)
        else:
            print("No AV女優名 section found in body.")
        browser.close()
except Exception as e:
    print("Error:", e)
