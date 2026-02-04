import time
from playwright.sync_api import sync_playwright

# User provided session ID
COOKIE_VALUE = "nbizz42kdrbabk9r80e5a9q7z7gnlutx"
CHART_URL = "https://cn.tradingview.com/chart/PP8uCQUu/"

print("Starting verification script...")

with sync_playwright() as p:
    # 1. Launch Browser (Visible Mode)
    print("Launching Chrome (Headless=False)...")
    # Force window size and position, and start maximized
    browser = p.chromium.launch(headless=False, channel="chrome", args=["--window-position=0,0", "--window-size=1920,1080", "--start-maximized"]) 
    
    # 2. Creating Context
    # Set viewport to None (match window) and device_scale_factor to 0.75 (Zoom Out 75%)
    context = browser.new_context(viewport=None, device_scale_factor=0.75)
    
    # 3. Injecting Cookie (The "Master Key")
    print(f"Injecting Cookie: {COOKIE_VALUE[:5]}...*****")
    context.add_cookies([{
        "name": "sessionid",
        "value": COOKIE_VALUE,
        "domain": ".tradingview.com",
        "path": "/"
    }])
    
    # 4. Open Page
    print(f"Navigating to {CHART_URL}")
    page = context.new_page()
    page.goto(CHART_URL)
    
    print("Page loaded. Please check if you are logged in (look for your avatar).")
    print("If you see the 'Indicator Limit' error effectively GONE, then it worked.")
    
    # 5. Keep open for user review
    print("Browser will close in 300 seconds or press Ctrl+C in terminal...")
    time.sleep(300)
    
    browser.close()
