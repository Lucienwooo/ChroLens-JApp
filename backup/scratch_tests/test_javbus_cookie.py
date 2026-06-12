import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Starting Playwright for JavBus verification redirect test...")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        # Go directly to verify page
        print("Navigating to verification URL...")
        page.goto("https://www.javbus.com/doc/driver-verify?referer=https%3A%2F%2Fwww.javbus.com%2FMAZO-033", timeout=15000)
        
        print("Final URL:", page.url)
        print("Final Page title:", page.title())
        html = page.content()
        print("Content length:", len(html))
        
        import re
        m_actresses = re.findall(r'<a href="https://www\.javbus\.com/star/[^"]+">([^<]+)</a>', html)
        print("Actresses found on JavBus:", m_actresses)
        m_title = re.search(r'<h3>(.*?)</h3>', html)
        if m_title:
            print("Title found:", m_title.group(1).strip())
            
        # Check cookies
        cookies = context.cookies()
        print("Cookies set in context:")
        for c in cookies:
            print(f"Name: {c['name']}, Value: {c['value']}, Domain: {c['domain']}")
            
        browser.close()
except Exception as e:
    print("Error:", e)
