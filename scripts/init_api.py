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
    r = httpx.get(url, timeout=10)
    r.raise_for_status()
    # Strip scripts and styles to save tokens
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return str(soup)

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
    6. Ensure the code is production-ready, imports all needed libraries, handles basic exceptions, and adds CORSMiddleware.
    
    OUTPUT FORMAT:
    Output ONLY valid Python code. NO markdown formatting blocks like ```python. Just raw code.
    
    HTML DOM OF TARGET:
    <html_snippet>
    {html[:8000]}
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
