import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Starting Playwright for Jable...")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        # Test code hmn-446 or ssis-054
        ccode = "hmn-446"
        url = f"https://jable.tv/videos/{ccode}/"
        print(f"Navigating to Jable: {url} ...")
        page.goto(url, timeout=15000)
        print("Page URL:", page.url)
        print("Page Title:", page.title())
        html = page.content()
        print("Content length:", len(html))
        
        import re
        m_title = re.search(r'<title>(.*?)</title>', html, re.I)
        if m_title:
            title_text = m_title.group(1).split(' - ')[0].strip()
            print("Title text from HTML:", title_text)
            models = re.findall(r'data-original-title="([^"]+)"', html)
            print("Models found in data-original-title:", models)
            
        browser.close()
except Exception as e:
    print("Error:", e)
