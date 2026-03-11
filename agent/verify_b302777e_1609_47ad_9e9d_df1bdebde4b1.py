from api_b302777e_1609_47ad_9e9d_df1bdebde4b1 import scrape_data
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context()
        page = context.new_page()
        # Load main page to get required cookies for scraping
        page.goto("https://www.kitapyurdu.com/", wait_until="load", timeout=60000)
        browser.close()
    
    data = scrape_data()
    print(f'DATA_COUNT: {len(data)}')
    assert len(data) > 0, "No data extracted! Check your selectors."

if __name__ == "__main__":
    main()