import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Starting Playwright for JavBus.org...")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        print("Navigating to JavBus.org MAZO-033...")
        page.goto("https://www.javbus.org/MAZO-033", timeout=15000)
        print("Page URL:", page.url)
        print("Page Title:", page.title())
        html = page.content()
        print("Content length:", len(html))
        
        import re
        m_actresses = re.findall(r'<a href="https://www\.javbus\.org/star/[^"]+">([^<]+)</a>', html)
        if not m_actresses:
            m_actresses = re.findall(r'<a href="https://www\.javbus\.com/star/[^"]+">([^<]+)</a>', html)
        print("Actresses found on JavBus.org:", m_actresses)
        browser.close()
except Exception as e:
    print("Error:", e)
