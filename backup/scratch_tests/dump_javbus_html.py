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
        html = page.content()
        with open("scratch/javbus.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("HTML dumped successfully, length:", len(html))
        
        # Print all links or buttons in the page
        buttons = page.locator("a, button").all()
        print("Buttons found:")
        for idx, btn in enumerate(buttons):
            try:
                print(f"{idx}: text={btn.inner_text()}, href={btn.get_attribute('href')}, class={btn.get_attribute('class')}")
            except:
                pass
        browser.close()
except Exception as e:
    print("Error:", e)
