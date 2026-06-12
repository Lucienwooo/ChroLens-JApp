import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Starting Playwright for JavBus with adc cookie test...")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        context.add_cookies([
            {
                'name': 'existmag',
                'value': 'all',
                'domain': '.javbus.com',
                'path': '/'
            },
            {
                'name': 'existmag',
                'value': 'all',
                'domain': 'www.javbus.com',
                'path': '/'
            },
            {
                'name': 'age',
                'value': 'verified',
                'domain': '.javbus.com',
                'path': '/'
            },
            {
                'name': 'age',
                'value': 'verified',
                'domain': 'www.javbus.com',
                'path': '/'
            },
            {
                'name': 'adc',
                'value': '1',
                'domain': '.javbus.com',
                'path': '/'
            },
            {
                'name': 'adc',
                'value': '1',
                'domain': 'www.javbus.com',
                'path': '/'
            }
        ])
        page = context.new_page()
        print("Navigating to JavBus MAZO-033...")
        page.goto("https://www.javbus.com/MAZO-033", timeout=15000)
        
        print("Final URL:", page.url)
        print("Page title:", page.title())
        html = page.content()
        print("Content length:", len(html))
        
        import re
        m_actresses = re.findall(r'<a href="https://www\.javbus\.com/star/[^"]+">([^<]+)</a>', html)
        print("Actresses found on JavBus:", m_actresses)
        m_title = re.search(r'<h3>(.*?)</h3>', html)
        if m_title:
            print("Title found:", m_title.group(1).strip())
            
        browser.close()
except Exception as e:
    print("Error:", e)
