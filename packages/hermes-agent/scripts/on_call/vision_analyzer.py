import os
import base64
from playwright.sync_api import sync_playwright
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def capture_screenshot(url: str, output_path: str):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        page.wait_for_timeout(5000) # Wait for charts to load
        page.screenshot(path=output_path, full_page=True)
        browser.close()

def analyze_dashboard(image_path: str, prompt: str):
    client = OpenAI(
        base_url="https://inference-api.nousresearch.com/v1",
        api_key=os.getenv("NOUS_API_KEY")
    )

    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    response = client.chat.completions.create(
        model="Hermes-4-405B", # Assuming Hermes-4 supports vision or proxy to a vision model
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    },
                ],
            }
        ],
        max_tokens=500,
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    # Mock usage
    img_path = "dashboard_snap.png"
    # capture_screenshot("https://grafana.example.com", img_path)
    # print(analyze_dashboard(img_path, "Detect any anomalies or spikes in this dashboard screenshot."))
    print("Vision Analyzer Script loaded.")
