import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Starting Playwright for JavBus age verification detailed click test...")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        print("Navigating to JavBus MAZO-033...")
        page.goto("https://www.javbus.com/MAZO-033", timeout=15000)
        
        # Check checkbox state
        chk = page.query_selector("input[type='checkbox']")
        btn = page.query_selector("input#submit")
        
        print("Checkbox found:", chk is not None)
        print("Submit button found:", btn is not None)
        if btn:
            print("Submit button disabled attribute initially:", btn.get_attribute("disabled"))
            
        if chk:
            print("Checking the checkbox...")
            chk.check()
            page.wait_for_timeout(1000)
            print("Submit button disabled attribute after check:", btn.get_attribute("disabled") if btn else "N/A")
            
        if btn and not btn.get_attribute("disabled"):
            print("Clicking submit button...")
            with page.expect_navigation(timeout=10000) as nav:
                btn.click()
            print("Navigation done!")
            
        print("Final URL:", page.url)
        print("Final Page title:", page.title())
        html = page.content()
        print("Content length:", len(html))
        
        import re
        m_actresses = re.findall(r'<a href="https://www\.javbus\.com/star/[^"]+">([^<]+)</a>', html)
        print("Actresses found on JavBus:", m_actresses)
        
        browser.close()
except Exception as e:
    print("Error:", e)
