#!/usr/bin/env python3
"""
DEPRECATED: init_api.py
========================
This file is no longer used. As of the Hermes Agent integration, API generation
is handled directly by Hermes Agent via manager.py:

  hermes chat --query "<task>" --toolsets "browser,terminal,file,web"

Hermes Agent uses its built-in browser tool to navigate real websites (solving
the SPA/CSR rendering problem), then writes and verifies scraper_generated.py
autonomously using its terminal and file tools.

Kept here for reference only. Safe to delete.
"""

#!/usr/bin/env python3
"""
init_api.py — Zero-to-One API Generator for Weaver
===========================================================
Takes a Target URL and a description of the desired data.
Calls the Hermes LLM to generate a FastAPI scraper from scratch.
Saves it as agent/scraper.py ready for deployment.

Usage:
  python scripts/init_api.py --url "http://localhost:8080" --schema "News headlines, categories, short excerpts, dates, and departments"
"""

import os
import sys
import time
import argparse
from pathlib import Path
import httpx
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

APP_DIR = Path(__file__).parent.parent / "agent"
load_dotenv(Path(__file__).parent.parent / ".env")

client = OpenAI(
    base_url="https://inference-api.nousresearch.com/v1",
    api_key=os.environ.get("NOUS_API_KEY", "not-set")
)

def fetch_dom(url: str) -> str:
    print(f"  [+] Fetching DOM from {url}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,tr-TR;q=0.8,tr;q=0.7",
    }
    r = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
    
    if r.status_code != 200:
        print(f"  [~] Warning: Got HTTP {r.status_code}, but proceeding to parse HTML anyway.")
        
    soup = BeautifulSoup(r.text, "html.parser")
    
    # Strip non-content bloat to keep it reasonable
    for tag in soup(["script", "style", "svg", "path", "meta", "noscript"]):
        tag.decompose()
        
    # User requested to send the ENTIRE HTML rather than trying to guess containers
    text = str(soup)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

def build_prompt(url: str, schema_desc: str, html: str) -> str:
    return f"""
    You are an expert Python backend engineer and web scraper.
    Your task is to build a robust POST/GET FastAPI web scraper from scratch.
    
    Target URL: {url}
    Desired Data Schema: {schema_desc}
    
    INSTRUCTIONS:
    1. Create a fully functioning `FastAPI` application called `app`.
    2. Define Pydantic models that match the user's requested data schema.
    3. Include two endpoints:
       - `GET /` or `GET /data` that scrapes the target live using `httpx` and `BeautifulSoup`.
       - `GET /health` that checks if the scraping logic still returns > 0 results.
    4. Write a function named `scrape_data(html: str) -> list[dict]` that holds the core Beautifulsoup selector logic.
    5. The DOM structure provided below is a minified representation of the target URL.
    6. CRITICAL: Ignore navigation menus, header dropdowns, and category links. Focus ONLY on the primary product/item grid or list in the main content area.
        7. Ensure the code is production-ready, imports all needed libraries, handles basic exceptions, and adds CORSMiddleware.
    8. VERY IMPORTANT: If the HTML appears to be a Single Page Application (SPA) where data is missing, hidden, lazy-loaded, or represented by skeleton placeholders (like `placeholder__item`), DO NOT generate a scraper that returns an array of nulls. Instead, the endpoint MUST return a single JSON object with an `error` field explaining: "This website uses Client-Side Rendering (SPA) or anti-bot protection. The HTML only contains empty placeholders, so the products cannot be extracted from static HTML." 
    7. IMPORTANT: The code MUST be compatible with Python 3.9.6. Do NOT use 3.10+ features like the `|` union operator for types (use `Optional` or `Union` from `typing` instead).
    8. CRITICAL: ALL httpx.get() calls MUST use `follow_redirects=True` AND a generic browser `User-Agent` header to avoid 403 Forbidden errors. DO NOT use `response.raise_for_status()`, instead check `response.is_success` and if False, return an empty list `[]`.
    9. CRITICAL: Handle parsing exceptions gracefully PER-FIELD. Use `try-except` around int/float cast conversions (e.g., points, comments). If a specific element is missing or fails to parse, default to 0 or "" and continue scraping the rest of the list. DO NOT crash the entire endpoint.
    
    OUTPUT FORMAT:
    Output ONLY valid Python code. NO markdown formatting blocks like ```python. Just raw code.
    
    HTML DOM OF TARGET:
    <html_snippet>
    {html}
    </html_snippet>
    """

def inspect_and_fix(code: str, prompt: str, max_retries: int = 3) -> str:
    """The Inspector Agent: tests the code in a subprocess and asks Hermes to fix it if it crashes."""
    current_code = code
    for attempt in range(max_retries):
        # Save temp file
        tmp_file = APP_DIR / "scraper_generated.py"
        tmp_file.write_text(current_code)
        
        # Test imports and syntax
        print(f"  [🔍] Inspector Agent: Compiling and verifying imports (Attempt {attempt+1})...")
        import subprocess
        result = subprocess.run(
            [sys.executable, "-c", "import scraper_generated"],
            cwd=str(APP_DIR),
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print("  [✓] Inspector Agent: Code is valid!")
            return current_code
            
        error_msg = result.stderr.strip()
        print(f"  [!] Inspector Agent found an error:\n{error_msg}")
        print("  [+] Sending error traceback back to Coder Agent for fixing...")
        
        fix_prompt = f"""
        You previously generated a FastApi scraper, but it failed when executing `import scraper_generated`.
        
        This is the error Python threw:
        ```
        {error_msg}
        ```
        
        Here is the code you previously wrote:
        ```python
        {current_code}
        ```
        
        Please rewrite the full file to fix this error. 
        Usually this happens because you forgot an import (like `from fastapi.middleware.cors import CORSMiddleware`) or have a syntax error.
        
        Output ONLY the fully fixed Python code. No markdown formatting.
        """
        
        try:
            response = client.chat.completions.create(
                model="Hermes-4-405B",
                messages=[
                    {"role": "system", "content": "You are Hermes, an autonomous infrastructure agent."},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": current_code},
                    {"role": "user", "content": fix_prompt}
                ],
                temperature=0.1,
                max_tokens=2500
            )
            current_code = response.choices[0].message.content.strip()
            if current_code.startswith("```python"):
                current_code = current_code[9:]
            if current_code.endswith("```"):
                current_code = current_code[:-3]
        except Exception as e:
            print(f"  [!] Fix generation failed: {e}")
            break
            
    return current_code

def generate_api(url: str, schema_desc: str):
    print(f"\n{'-'*60}")
    print(f"  🚀 Weaver — Zero-to-One Generator")
    print(f"{'-'*60}")
    
    html = fetch_dom(url)
    prompt = build_prompt(url, schema_desc, html)
    
    print("  [+] Calling Hermes LLM Coder Agent...")
    try:
        response = client.chat.completions.create(
            model="Hermes-4-405B",
            messages=[
                {"role": "system", "content": "You are Hermes, an autonomous infrastructure agent."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=2500
        )
        new_code = response.choices[0].message.content.strip()
        
        if new_code.startswith("```python"):
            new_code = new_code[9:]
        if new_code.endswith("```"):
            new_code = new_code[:-3]
            
        # Send to inspector
        final_code = inspect_and_fix(new_code.strip(), prompt)
        return final_code
        
    except Exception as e:
        print(f"  [!] LLM Generation failed: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Generate an API via LLM")
    parser.add_argument("--url", required=True, help="Target Website URL")
    parser.add_argument("--schema", required=True, help="Description of data to extract")
    args = parser.parse_args()
    
    if os.environ.get("NOUS_API_KEY") in [None, "not-set", "your_nous_api_key_here"]:
        print("  [!] Error: NOUS_API_KEY environment variable is not set correctly in .env.")
        sys.exit(1)
        
    code = generate_api(args.url, args.schema)
    
    out_file = APP_DIR / "scraper_generated.py"
    out_file.write_text(code)
    
    print(f"  [✓] Success! Generated FastAPI scraper saved to {out_file}.")
    print("\n  To test the new API run:")
    print(f"  cd agent && ./venv/bin/uvicorn scraper_generated:app --reload")

if __name__ == "__main__":
    main()
