import sys
from playwright.sync_api import sync_playwright

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
            
        html = page.content()
        with open("scratch/after_click.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("After click HTML dumped successfully, length:", len(html))
        
        browser.close()
except Exception as e:
    print("Error:", e)
