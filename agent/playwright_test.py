from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://www.dr.com.tr/")
    title = page.title()
    browser.close()
    print(f"PAGE_TITLE: {title}")