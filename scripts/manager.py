#!/usr/bin/env python3
"""
manager.py — Weaver Manager API
=================================
A persistent FastAPI service (port 9000) that orchestrates all
Weaver API generation, lifecycle management, and health monitoring.

Usage:
    python scripts/manager.py
"""

import os
import sys
import uuid
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

import uvicorn
import httpx
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import threading

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
AGENT_DIR = ROOT / "agent"
SCRIPTS_DIR = ROOT / "scripts"
VENV_PYTHON = AGENT_DIR / ".venv" / "bin" / "python3"

load_dotenv(ROOT / ".env")

# ── State ──────────────────────────────────────────────────────────────────
# {api_id: ApiRecord}
apis: Dict[str, Any] = {}
generation_logs: Dict[str, List[str]] = {}  # {api_id: [log_lines]}
next_port = [8010]  # Mutable counter

def get_next_port() -> int:
    port = next_port[0]
    next_port[0] += 1
    return port

# ── Models ─────────────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    url: str
    schema: str

class ApiRecord(BaseModel):
    id: str
    url: str
    schema: str
    port: int
    status: str  # "generating" | "running" | "failed" | "stopped"
    created_at: str
    error: Optional[str] = None

# ── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(title="Weaver Manager API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health/Orphan Check ───────────────────────────────────────────────────
# TUI spawns this process. If TUI crashes, we shouldn't stay alive forever
# and hold port 9000 hostage.
def orphan_check_loop():
    import time
    while True:
        time.sleep(5)
        # On macOS/Unix, if parent dies, PPID becomes 1
        if os.getppid() == 1:
            print("[MANAGER] Parent process died. Exiting to avoid zombie state.")
            # Kill any active apis
            for record in list(apis.values()):
                proc = record.get("process")
                if proc and proc.poll() is None:
                    proc.kill()
            os._exit(0)

threading.Thread(target=orphan_check_loop, daemon=True).start()

# ── Background: Generate API ────────────────────────────────────────────────
HERMES_CLI = Path.home() / ".local" / "bin" / "hermes"
HERMES_HOME = Path.home() / ".hermes" / "hermes-agent"

def _run_generation(api_id: str, url: str, schema: str, port: int):
    """
    Uses Hermes Agent (with browser+terminal+file tools) to autonomously:
    1. Navigate to the target URL in a real headless browser
    2. Wait for JS to load, scroll to reveal lazy-loaded content
    3. Extract real data matching the user's schema
    4. Write a self-contained FastAPI scraper to agent/scraper_generated.py
    5. Start the scraper on the assigned port
    """
    import time
    logs = generation_logs[api_id]
    
    try:
        logs.append(f"[+] Starting Hermes Agent for {url}")
        logs.append(f"[+] Port assigned: {port}")
        logs.append("[+] Hermes Agent is opening a real browser — this may take 30-60 seconds...")

        safe_id = api_id.replace("-", "_")
        scraper_filename = f"api_{safe_id}.py"
        verify_filename = f"verify_{safe_id}.py"
        output_file = str(AGENT_DIR / scraper_filename)
        verify_file = str(AGENT_DIR / verify_filename)

        # Ensure agent directory exists
        AGENT_DIR.mkdir(exist_ok=True)

        # Build a detailed, non-ambiguous task prompt for the agent
        task_prompt = f"""You are a web scraping engineer. Your task is to create a FastAPI data service.

TARGET URL: {url}
DATA SCHEMA: {schema}
OUTPUT FILE: {output_file}
PORT: {port}

Follow these exact steps IN ORDER:

STEP 1 - BROWSE THE SITE (MANDATORY):
You MUST use your `browser_navigate` and `browser_snapshot` tools to navigate to {url}. Wait for the page to fully load including any JavaScript-rendered content. Scroll down to trigger lazy loading if needed. Wait until you can see actual data on the page.

STEP 2 - ANALYZE THE DATA:
Look at the actual rendered page content and identify the real HTML selectors or JSON data that matches the schema: "{schema}". Take note of exact CSS class names or JSON keys.
CRITICAL DATA EXTRACTION RULE: You MUST observe the ACTUAL CSS classes and tags used on the page. Use strict CSS locators like `page.locator(".product-card")`. DO NOT blindly invent or hallucinate `.get_by_role("group")` unless you strictly verify the site uses ARIA roles. Most sites do NOT use `role="group"`. Extract data using `await locator.text_content()` and `await locator.get_attribute("href")`.

STEP 3 - WRITE THE SCRAPER (MUST USE PLAYWRIGHT):
Write a complete Python FastAPI file to {output_file}.
CRITICAL: The site uses client-side rendering (SPA). You MUST use `playwright` (sync_playwright) inside the generated code to fetch the fully-rendered HTML!
Do NOT use `httpx` or `requests` for fetching HTML. Use Playwright!
CRITICAL PLAYWRIGHT REQUIREMENT: You MUST use `sync_playwright` instead of `async_playwright`. DO NOT use `async_playwright`. You MUST run the scraping logic inside a standard synchronous `def` endpoint (DO NOT use `async def`). FastAPI will automatically run it in a threadpool to prevent event loop blocking.

IMPORTANT ANTI-PATTERN WARNING: DO NOT use accessibility roles (like "group", "link", "heading", "button") as CSS selectors in `page.locator()`.
- WRONG: `page.locator("group")` or `page.locator("link")`
- RIGHT: `page.locator(".product-card")` or `page.locator("div.item")`
Always prioritize ACTUAL CSS classes observed in the `browser_snapshot`.
Example pattern:
```python
from playwright.sync_api import sync_playwright

def scrape_data():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        # Use 'load' or 'domcontentloaded' to ensure document.body exists
        page.goto("{url}", wait_until="load", timeout=60000)
        
        # Safe scroll helper
        for _ in range(3):
            page.evaluate("window.scrollTo(0, document.body ? document.body.scrollHeight : 0)")
            page.wait_for_timeout(2000)
            
        # Use your discovered CSS selectors here
        # TIP: Look for stable product card classes (e.g., .sgf-dr-card, .dotd-product, .product-item)
        # TIP: Do NOT use .is_visible() guards unless necessary, as they often skip valid off-screen data.
        # Use page.locator(".candidate1, .candidate2") to try multiple patterns.
        items = page.locator(".sgf-dr-card, .dotd-product, .product-item").all()
        for item in items:
            # Extract list of dicts matching {schema}
            # Use item.locator(".title, .product-name") type selectors
        browser.close()
        return data

@app.get("/data")
def get_data():
    return scrape_data()
```

The file MUST:
- Import fastapi, pydantic, and playwright.sync_api
- Have CORS middleware (IMPORTANT: import it via `from fastapi.middleware.cors import CORSMiddleware`)
- Have GET /health returning {{"status": "ok"}}
- Have GET /data endpoint which is a `def` (NOT `async def`) calling your scrape function.
- Return a list matching the {schema} structure.

STEP 4 - VERIFY IT (CRITICAL):
You MUST verify that your scraper actually works and returns data.
1. Create a file `{verify_file}`:
```python
from {scraper_filename[:-3]} import scrape_data
data = scrape_data()
print(f'DATA_COUNT: {{len(data)}}')
assert len(data) > 0, "No data extracted! Check your selectors."
```
2. Run it: `cd {str(AGENT_DIR)} && .venv/bin/python {verify_filename}`
- If the count is 0 or it fails, your selectors are WRONG. Go back to Step 2, re-analyze the `browser_snapshot`, and fix the selectors in `{scraper_filename}`.
- Repeat until the verification command passes.

STEP 5 - CONFIRM:
Print "GENERATION_COMPLETE" ONLY when the Step 4 verification command passes.

DO NOT ask clarifying questions. Just complete all 5 steps autonomously.
"""

        # Use hermes chat non-interactively with browser + terminal + file tools
        hermes_env = {
            **os.environ,
            "NOUS_API_KEY": os.environ.get("NOUS_API_KEY", ""),
        }

        proc = subprocess.Popen(
            [str(HERMES_CLI), "chat",
             "--query", task_prompt,
             "--toolsets", "browser,terminal,file,web",
             "--model", "Hermes-4-405B",
             ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,  # Enable stdin for auto-approving prompts
            text=True,
            env=hermes_env,
            bufsize=1,
        )

        # Auto-approve prompts by sending 's\n' (session approval)
        # We write this multiple times to handle any unexpected prompts
        try:
            proc.stdin.write("s\n" * 10)
            proc.stdin.flush()
        except:
            pass

        # Stream Hermes Agent output to logs in real time
        generation_successful = False
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                logs.append(f"[AGENT] {line}")
                if "GENERATION_COMPLETE" in line:
                    generation_successful = True
                elif "GENERATION_FAILED" in line:
                    logs.append(f"[!] Agent reported failure: {line}")
                    apis[api_id]["status"] = "failed"
                    apis[api_id]["error"] = line
                    return

        proc.wait()

        # Check that the file was written
        generated_file = AGENT_DIR / scraper_filename
        if not generated_file.exists():
            logs.append(f"[!] {scraper_filename} not found after agent run")
            apis[api_id]["status"] = "failed"
            apis[api_id]["error"] = f"{scraper_filename} was not created"
            return

        logs.append(f"[✓] Scraper generated! Starting API on port {port}...")

        # Kill any existing process on this port
        try:
            pids = subprocess.check_output(["lsof", "-ti", f":{port}"], text=True).strip()
            if pids:
                for pid in pids.split():
                    subprocess.run(["kill", "-9", pid], capture_output=True)
        except Exception:
            pass

        # Start uvicorn with the generated scraper
        uvicorn_log_path = AGENT_DIR / f"uvicorn_{api_id}.log"
        log_file = open(str(uvicorn_log_path), "w")
        uvicorn_proc = subprocess.Popen(
            [str(VENV_PYTHON), "-m", "uvicorn",
             f"{scraper_filename[:-3]}:app",
             "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(AGENT_DIR),
            stdout=log_file,
            stderr=log_file,
        )

        apis[api_id]["process"] = uvicorn_proc

        # Poll until ready (max 60s)
        for attempt in range(30):
            time.sleep(2)
            if uvicorn_proc.poll() is not None:
                log_content = ""
                try:
                    log_content = open(str(uvicorn_log_path)).read()[-500:]
                except Exception:
                    pass
                logs.append(f"[!] uvicorn exited early. Log: {log_content or 'empty'}")
                apis[api_id]["status"] = "failed"
                apis[api_id]["error"] = "uvicorn exited prematurely"
                return
            for endpoint in ["/health", "/"]:
                try:
                    r = httpx.get(f"http://127.0.0.1:{port}{endpoint}", timeout=3)
                    logs.append(f"[✓] API is LIVE at http://127.0.0.1:{port} (status {r.status_code})")
                    apis[api_id]["status"] = "running"
                    return
                except httpx.ConnectError:
                    pass
                except Exception:
                    pass
            logs.append(f"[~] Waiting for server on port {port}... ({attempt+1}/30)")

        logs.append("[!] API failed to respond in time.")
        apis[api_id]["status"] = "failed"
        apis[api_id]["error"] = "API did not start within timeout"

    except Exception as e:
        import traceback
        logs.append(f"[!] EXCEPTION: {str(e)}")
        logs.append(traceback.format_exc())
        apis[api_id]["status"] = "failed"
        apis[api_id]["error"] = str(e)


# ── API Endpoints ─────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"service": "Weaver Manager API", "version": "1.0.0", "uptime": True}


@app.get("/apis", response_model=List[ApiRecord])
def list_apis():
    """List all known APIs and their status."""
    result = []
    for api_id, record in apis.items():
        result.append(ApiRecord(
            id=api_id,
            url=record["url"],
            schema=record["schema"],
            port=record["port"],
            status=record["status"],
            created_at=record["created_at"],
            error=record.get("error"),
        ))
    return result


@app.post("/apis/generate", response_model=ApiRecord, status_code=202)
def generate_api(req: GenerateRequest, background_tasks: BackgroundTasks):
    """Start generating a new API. Returns immediately with api_id. Use /apis/{id}/logs to stream progress."""
    api_id = str(uuid.uuid4())
    port = get_next_port()
    
    apis[api_id] = {
        "id": api_id,
        "url": req.url,
        "schema": req.schema,
        "port": port,
        "status": "generating",
        "created_at": datetime.now().isoformat(),
        "process": None,
        "error": None,
    }
    generation_logs[api_id] = []
    
    background_tasks.add_task(_run_generation, api_id, req.url, req.schema, port)
    
    return ApiRecord(
        id=api_id,
        url=req.url,
        schema=req.schema,
        port=port,
        status="generating",
        created_at=apis[api_id]["created_at"],
    )


@app.get("/apis/{api_id}/status", response_model=ApiRecord)
def get_api_status(api_id: str):
    """Get the current status of a specific API."""
    if api_id not in apis:
        raise HTTPException(status_code=404, detail="API not found")
    record = apis[api_id]
    return ApiRecord(
        id=api_id,
        url=record["url"],
        schema=record["schema"],
        port=record["port"],
        status=record["status"],
        created_at=record["created_at"],
        error=record.get("error"),
    )


@app.get("/apis/{api_id}/logs")
def stream_logs(api_id: str):
    """Stream generation logs as plain text (SSE-compatible polling)."""
    if api_id not in generation_logs:
        raise HTTPException(status_code=404, detail="API not found")
    
    def generate():
        for line in generation_logs[api_id]:
            yield f"data: {line}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/apis/{api_id}/logs/all")
def get_all_logs(api_id: str):
    """Return all generation logs as JSON array (for polling)."""
    if api_id not in generation_logs:
        raise HTTPException(status_code=404, detail="API not found")
    return {"logs": generation_logs[api_id]}


@app.get("/apis/{api_id}/data")
async def get_api_data(api_id: str):
    """Proxy request to the running API and return its data."""
    if api_id not in apis:
        raise HTTPException(status_code=404, detail="API not found")
    
    record = apis[api_id]
    if record["status"] != "running":
        raise HTTPException(status_code=425, detail=f"API is not running yet (status: {record['status']})")
    
    port = record["port"]
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"http://127.0.0.1:{port}/data", timeout=45)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {"_raw": r.text}
        except httpx.HTTPStatusError as e:
            error_data = {"_error": f"HTTP {e.response.status_code}", "_raw": e.response.text}
            if api_id in generation_logs:
                # Append last 15 lines of server logs to help debug 500s
                error_data["_traceback"] = "\n".join(generation_logs[api_id][-15:])
            return error_data
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Could not reach API on port {port}: {str(e)}")


@app.delete("/apis/{api_id}")
def delete_api(api_id: str):
    """Stop and remove an API."""
    if api_id not in apis:
        raise HTTPException(status_code=404, detail="API not found")
    
    record = apis[api_id]
    # Process kill
    proc = record.get("process")
    if proc and proc.poll() is None:
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception as e:
            print(f"Warning: Could not kill process for {api_id}: {e}")
    
    del apis[api_id]

    if api_id in generation_logs:
        del generation_logs[api_id]
    
    return {"deleted": api_id}


# ── Entry Point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("╔══════════════════════════════════════╗")
    print("║    Weaver Manager API  — Port 9000   ║")
    print("╚══════════════════════════════════════╝")
    print(f"  NOUS_API_KEY: {'✓ Set' if os.environ.get('NOUS_API_KEY') else '✗ NOT SET'}")
    print()
    uvicorn.run(app, host="127.0.0.1", port=9000, log_level="warning")
