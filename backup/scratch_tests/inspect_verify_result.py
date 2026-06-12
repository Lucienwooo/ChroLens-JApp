import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Starting Playwright to inspect verify result...")
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
            
        print("Final URL:", page.url)
        # Select specifically the ageVerify modal body
        age_modal = page.query_selector("#ageVerify .modal-body")
        if age_modal:
            print("Modal body text:")
            print(age_modal.inner_text())
        else:
            print("Age verification modal NOT found on page! Checking other content...")
            h3 = page.query_selector("h3")
            if h3:
                print("H3 tag text:", h3.inner_text())
            else:
                print("No h3 found.")
        
        browser.close()
except Exception as e:
    print("Error:", e)
