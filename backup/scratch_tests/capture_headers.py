import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Starting Playwright to capture headers...")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        def handle_request(request):
            if "javbus.com" in request.url:
                print(f"[REQ] {request.method} {request.url}")
                headers = request.headers
                if "cookie" in headers:
                    print(f"  Cookie: {headers['cookie']}")
                    
        def handle_response(response):
            if "javbus.com" in response.url:
                print(f"[RESP] {response.status} {response.url}")
                headers = response.headers
                if "set-cookie" in headers:
                    print(f"  Set-Cookie: {headers['set-cookie']}")
                    
        page.on("request", handle_request)
        page.on("response", handle_response)
        
        print("Navigating to JavBus MAZO-033...")
        page.goto("https://www.javbus.com/MAZO-033", timeout=15000)
        
        chk = page.query_selector("input[type='checkbox']")
        btn = page.query_selector("input#submit")
        
        if chk and btn:
            print("Checking checkbox and clicking submit...")
            chk.check()
            page.wait_for_timeout(500)
            btn.click()
            page.wait_for_load_state("networkidle")
            
        print("Final page URL:", page.url)
        print("Final page title:", page.title())
        
        # Navigate to another code to see if it bypasses
        print("Navigating to HMN-446...")
        page.goto("https://www.javbus.com/HMN-446", timeout=15000)
        print("HMN-446 page title:", page.title())
        
        browser.close()
except Exception as e:
    print("Error:", e)
