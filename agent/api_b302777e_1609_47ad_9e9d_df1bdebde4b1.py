from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}


def scrape_data():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        
        # Load main page
        page.goto("https://www.kitapyurdu.com/", wait_until="load", timeout=60000)
        
        results = []
        
        # Strategy: Get all links and try to find book-like items
        all_links = page.locator("a")
        
        for i, link in enumerate(all_links.all()[:20]):  # Limit to first 20 links
            href = link.get_attribute("href")
            text = link.text_content()
            
            if href and text and len(text) > 3:  # Basic filtering
                # Try to extract price-like patterns
                price_text = "0.00"
                if "TL" in text:
                    price_text = text.split(" ")[-1] if " " in text else text
                
                results.append({
                    "title": text,
                    "price": price_text,
                    "url": href
                })
                
                if len(results) >= 5:  # Get at least 5 results
                    break
        
        browser.close()
        return results

@app.get("/data")
def get_data():
    return scrape_data()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)