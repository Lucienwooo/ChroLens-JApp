import sys
from playwright.sync_api import sync_playwright

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        print("Navigating to av-wiki homepage...")
        page.goto("https://av-wiki.net", timeout=10000)
        print("Homepage title:", page.title())
        browser.close()
except Exception as e:
    print("Error:", e)
