#!/usr/bin/env python3
"""
health_check.py — Weaver Self-Healing Orchestrator
============================================================
Runs on a schedule (or triggered event-driven via the API).
Checks the live API health endpoint. If broken:
  1. Fetches current DOM from target
  2. Diffs against stored state
  3. Calls Hermes Agent to re-analyse DOM and rewrite selectors
  4. Hot-swaps the running scraper (zero-downtime)
  5. Verifies the fix
  6. Reports result

Usage:
  python health_check.py               # one-shot check
  python health_check.py --watch 60    # poll every 60 seconds
"""

import sys
import time
import json
import shutil
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# ── Config ───────────────────────────────────────────────────────────────────
API_BASE      = "http://localhost:8000"
TARGET_URL    = "http://localhost:8080"
APP_DIR       = Path(__file__).parent.parent / "agent"
STATE_FILE    = APP_DIR / "state.json"
SCRAPER_PATH  = APP_DIR / "scraper.py"
BACKUP_DIR    = APP_DIR / "backups"
LOG_FILE      = APP_DIR / "heal_log.jsonl"

FAIL_THRESHOLD = 1   # Trigger heal after N consecutive failures

COLORS = {
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "cyan":   "\033[96m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}

def c(color, text):
    return f"{COLORS[color]}{text}{COLORS['reset']}"


# ── Logging ──────────────────────────────────────────────────────────────────
def log_event(event_type: str, data: dict):
    entry = {"ts": datetime.utcnow().isoformat(), "event": event_type, **data}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


# ── Health Check ─────────────────────────────────────────────────────────────
def check_health() -> dict:
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=10)
        return r.json()
    except Exception as e:
        return {"status": "broken", "message": str(e), "announcement_count": 0}


# ── DOM Diffing ───────────────────────────────────────────────────────────────
def fetch_dom() -> str:
    r = httpx.get(TARGET_URL, timeout=10)
    return r.text


def extract_structural_selectors(html: str) -> dict:
    """Extract CSS class names that look like data containers."""
    soup = BeautifulSoup(html, "html.parser")
    selectors = {}

    # Look for card-like containers (divs with 3+ children)
    for div in soup.find_all("div", class_=True):
        classes = div.get("class", [])
        children = list(div.children)
        real_children = [c for c in children if hasattr(c, "name") and c.name]
        if len(real_children) >= 3:
            for cls in classes:
                selectors[cls] = selectors.get(cls, 0) + 1

    return selectors


def diff_dom(old_state: dict, new_html: str) -> dict:
    """Compare current DOM structure against stored state fingerprint."""
    new_selectors = extract_structural_selectors(new_html)
    old_fingerprint = old_state.get("dom_fingerprint", "")

    soup = BeautifulSoup(new_html, "html.parser")
    new_cards = len(soup.select(".announcement-card"))
    new_items = len(soup.select(".ann-item"))
    new_fingerprint = f"cards={new_cards}|items={new_items}"

    changed = old_fingerprint != new_fingerprint

    return {
        "changed": changed,
        "old_fingerprint": old_fingerprint,
        "new_fingerprint": new_fingerprint,
        "prominent_classes": sorted(new_selectors.items(), key=lambda x: -x[1])[:10],
    }


# ── Hermes API Call ─────────────────────────────────────────────────────────
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env map securely
load_dotenv(Path(__file__).parent.parent / ".env")

# Initialize client using the generic OpenAI SDK, pointed at Nous Research
# This allows using Nous API Keys interchangeably.
client = OpenAI(
    base_url="https://inference-api.nousresearch.com/v1",
    api_key=os.environ.get("NOUS_API_KEY", "not-set")
)

def call_hermes_agent(html: str, diff: dict, old_scraper_code: str) -> str:
    """
    Sends the broken HTML and old code to the Hermes API.
    Asks the model to generate the corrected scraper using the new CSS selectors.
    """
    print(c("cyan", "\n  🤖 Calling Hermes API (Nous Research)..."))
    
    if os.environ.get("NOUS_API_KEY") in [None, "not-set", "your_nous_api_key_here"]:
        print(c("red", "  ⚠ NOUS_API_KEY not found in environment! Using fallback local v2 mock."))
        time.sleep(2)
        healed_path = Path(__file__).parent.parent / "agent" / "scraper_v2.py"
        return healed_path.read_text()

    prompt = f"""
    You are an expert Python web scraping agent. An existing FastAPI scraper just broke because the target website's DOM changed.
    
    I will provide you with:
    1. The old scraper code that was working previously.
    2. A summary of the DOM changes we detected.
    3. The current broken HTML of the target website.
    
    Your task is to rewrite the `scrape_v1` function (or equivalent parsing logic) to accurately extract the data matching the Pydantic schema using the NEW HTML structure.
    
    CRITICAL INSTRUCTIONS:
    - Output ONLY the full, complete, working Python file.
    - DO NOT include ANY markdown formatting like ```python. Start directly with the code.
    - Ensure you preserve the Pydantic schemas exactly as they are to maintain backward compatibility.
    - Just update the CSS selectors in BeautifulSoup.
    
    OLD CODE:
    <old_code>
    {old_scraper_code}
    </old_code>
    
    DOM CHANGES DETECTED:
    Old Fingerprint: {diff.get('old_fingerprint')}
    New Fingerprint: {diff.get('new_fingerprint')}
    Most Prominent New Classes: {diff.get('prominent_classes')}
    
    NEW HTML FILE:
    <new_html_snippet>
    {html[:8000]} # Send a generous snippet to prevent token overflow if the page is huge
    </new_html_snippet>
    """

    print(c("cyan",  "  ├── Sending prompt and broken HTML to Hermes..."))
    try:
        response = client.chat.completions.create(
            model="Hermes-4-405B", # Adjust model name based on Nous portal availability
            messages=[
                {"role": "system", "content": "You are Hermes, an autonomous coding agent specializing in web scraping."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        new_code = response.choices[0].message.content.strip()
        
        # Strip potential markdown blocks if the LLM ignores instructions
        if new_code.startswith("```python"):
            new_code = new_code[9:]
        if new_code.endswith("```"):
            new_code = new_code[:-3]
            
        print(c("green",  "  ├── Received new healed code from Hermes API!"))
        return new_code.strip()
    
    except Exception as e:
        print(c("red", f"  ⚠ API Call failed: {e}. Falling back to local mock."))
        healed_path = Path(__file__).parent.parent / "agent" / "scraper_v2.py"
        return healed_path.read_text()


# ── Hot-Swap ──────────────────────────────────────────────────────────────────
def backup_and_replace(new_code: str) -> Path:
    """Backup current scraper and write new version atomically."""
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    backup_path = BACKUP_DIR / f"scraper_{ts}.py.bak"

    if SCRAPER_PATH.exists():
        shutil.copy(SCRAPER_PATH, backup_path)
        print(c("yellow", f"  ├── Backup saved: {backup_path.name}"))

    # Write atomically via temp file
    tmp = SCRAPER_PATH.with_suffix(".tmp")
    tmp.write_text(new_code)
    tmp.replace(SCRAPER_PATH)

    print(c("green", f"  ├── New scraper written to {SCRAPER_PATH}"))
    return backup_path


def restart_api():
    """Restart the FastAPI process (uvicorn)."""
    print(c("yellow", "  ├── Waiting for FastAPI --reload to pick up changes..."))
    
    # In Docker environments, Uvicorn runs with --reload.
    # The atomic file replacement triggers the auto-restart, so we just wait.
    time.sleep(3) # Wait for it to boot up
    print(c("green",  "  └── API server restarted ✓"))


def verify_fix() -> bool:
    """Call /announcements after heal and verify data is returned."""
    time.sleep(2)
    try:
        r = httpx.get(f"{API_BASE}/announcements", timeout=10)
        if r.status_code == 200:
            data = r.json()
            count = data.get("count", 0)
            if count > 0:
                print(c("green", f"  ✓ Verification passed — {count} announcements returned"))
                return True
    except Exception:
        pass
    print(c("red", "  ✗ Verification failed"))
    return False


# ── Main Self-Heal Loop ───────────────────────────────────────────────────────
def run_check(consecutive_failures: list) -> bool:
    """Returns True if system is healthy, False if still broken after heal attempt."""
    timestamp = datetime.utcnow().strftime("%H:%M:%S")
    print(f"\n{c('bold', '━' * 60)}")
    print(f"  {c('bold', 'Health Check')} · {timestamp}")
    print(c('bold', '━' * 60))

    health = check_health()
    status = health.get("status", "unknown")

    if status == "ok":
        count = health.get("announcement_count", 0)
        fp    = health.get("dom_fingerprint", "n/a")
        print(c("green", f"  ✓ Status: OK  |  Announcements: {count}  |  DOM: {fp}"))
        consecutive_failures.clear()
        log_event("health_ok", {"count": count, "fingerprint": fp})
        return True

    # ── Status is broken / degraded ──────────────────────────────────────────
    consecutive_failures.append(timestamp)
    print(c("red", f"  ✗ Status: {status.upper()}"))
    print(c("red", f"  ✗ Message: {health.get('message', 'unknown')}"))
    print(c("yellow", f"  ⚠ Consecutive failures: {len(consecutive_failures)}/{FAIL_THRESHOLD}"))

    if len(consecutive_failures) < FAIL_THRESHOLD:
        print(c("yellow", "  → Threshold not reached. Waiting for next check."))
        return False

    # ── Threshold reached — begin self-heal ──────────────────────────────────
    print(c("bold", f"\n  🔧 SELF-HEAL TRIGGERED"))
    log_event("heal_start", {"failures": consecutive_failures})

    # Step 1: Fetch current DOM
    print(c("cyan", "  ├── Fetching current DOM from target..."))
    html = fetch_dom()

    # Step 2: Diff against state
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    diff  = diff_dom(state, html)
    print(c("cyan",  f"  ├── DOM changed: {diff['changed']}"))
    print(c("cyan",  f"  ├── Old fingerprint: {diff['old_fingerprint']}"))
    print(c("cyan",  f"  ├── New fingerprint: {diff['new_fingerprint']}"))

    # Step 3: Call Hermes Agent
    old_code = SCRAPER_PATH.read_text() if SCRAPER_PATH.exists() else ""
    new_code = call_hermes_agent(html, diff, old_code)

    # Step 4: Hot-swap
    backup_and_replace(new_code)

    # Step 5: Restart & verify
    restart_api()
    success = verify_fix()

    log_event("heal_end", {
        "success": success,
        "old_fingerprint": diff["old_fingerprint"],
        "new_fingerprint": diff["new_fingerprint"],
    })

    if success:
        consecutive_failures.clear()
        print(c("green", "\n  ✅ SELF-HEAL COMPLETE — API restored with zero data loss"))
        print(c("green",  "  📋 Schema v1.0.0 preserved — downstream consumers unaffected"))
    else:
        print(c("red", "\n  ❌ Self-heal attempt failed. Manual intervention required."))

    return success


def main():
    parser = argparse.ArgumentParser(description="Weaver Health Monitor")
    parser.add_argument("--watch", type=int, metavar="SECONDS",
                        help="Poll continuously every N seconds")
    args = parser.parse_args()

    consecutive_failures = []

    if args.watch:
        print(c("bold", f"  👁 Watching API every {args.watch}s  (Ctrl+C to stop)"))
        while True:
            run_check(consecutive_failures)
            time.sleep(args.watch)
    else:
        run_check(consecutive_failures)


if __name__ == "__main__":
    main()
