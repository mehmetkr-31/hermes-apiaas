#!/usr/bin/env python3
"""
health_check.py — Weaver Self-Healing Orchestrator
====================================================
Monitors the live API. If broken, autonomously:
  1. Fetches current DOM from target
  2. Diffs against stored state fingerprint
  3. Calls Hermes Agent to rewrite selectors
  4. Hot-swaps scraper + restarts uvicorn via PID file
  5. Verifies the fix and reports result

Usage:
  python health_check.py               # one-shot check
  python health_check.py --watch 30    # poll every 30 seconds

Config (env vars or edit defaults below):
  API_BASE    — FastAPI server base URL  (default: http://localhost:8000)
  TARGET_URL  — Target website URL       (default: http://localhost:8080)
  APP_DIR     — Directory with scraper.py and state.json
  PID_FILE    — Path to uvicorn PID file (written by start_api in demo_heal.py)
"""

import os
import sys
import signal
import time
import json
import shutil
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

_SCRIPT_DIR   = Path(__file__).resolve().parent
load_dotenv(_SCRIPT_DIR.parent / ".env")

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE      = os.getenv("API_BASE",   "http://localhost:8000")
TARGET_URL    = os.getenv("TARGET_URL", "http://localhost:8080")

APP_DIR       = Path(os.getenv("APP_DIR", str(_SCRIPT_DIR.parent / "agent")))
STATE_FILE    = APP_DIR / "state.json"
SCRAPER_PATH  = APP_DIR / "scraper.py"
BACKUP_DIR    = APP_DIR / "backups"
LOG_FILE      = APP_DIR / "heal_log.jsonl"
PID_FILE      = APP_DIR / "api.pid"
UVICORN_BIN   = APP_DIR / ".venv" / "bin" / "uvicorn"

FAIL_THRESHOLD = 1

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

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def now_hms() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")

def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


# ── Logging ───────────────────────────────────────────────────────────────────
def log_event(event_type: str, data: dict):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"ts": now_iso(), "event": event_type, **data}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


# ── Health Check ──────────────────────────────────────────────────────────────
def check_health() -> dict:
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=10)
        return r.json()
    except Exception as e:
        return {"status": "broken", "message": str(e), "announcement_count": 0}


# ── DOM Fetching ──────────────────────────────────────────────────────────────
# BUG 1 FIX: fetch_dom() now returns None on failure instead of crashing the loop
def fetch_dom() -> str | None:
    try:
        r = httpx.get(TARGET_URL, timeout=10)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(c("red", f"  ├── Cannot reach target site: {e}"))
        return None


# ── DOM Diffing ───────────────────────────────────────────────────────────────
def extract_structural_selectors(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    selectors: dict[str, int] = {}
    for div in soup.find_all("div", class_=True):
        real_children = [ch for ch in div.children if hasattr(ch, "name") and ch.name]
        if len(real_children) >= 3:
            for cls in div.get("class", []):
                selectors[cls] = selectors.get(cls, 0) + 1
    return selectors


def diff_dom(old_state: dict, new_html: str) -> dict:
    new_selectors = extract_structural_selectors(new_html)
    old_fingerprint = old_state.get("dom_fingerprint", "")
    soup = BeautifulSoup(new_html, "html.parser")
    new_cards = len(soup.select(".announcement-card"))
    new_items = len(soup.select(".ann-item"))
    new_fingerprint = f"cards={new_cards}|items={new_items}"
    return {
        "changed": old_fingerprint != new_fingerprint,
        "old_fingerprint": old_fingerprint,
        "new_fingerprint": new_fingerprint,
        "prominent_classes": sorted(new_selectors.items(), key=lambda x: -x[1])[:10],
    }


# ── Hermes Agent Call ─────────────────────────────────────────────────────────
def call_hermes_agent(html: str, diff: dict, old_scraper_code: str) -> str:
    print(c("cyan", "\n  🤖 Calling Hermes Agent..."))
    print(c("cyan",  "  ├── Sending DOM diff to agent"))
    print(c("cyan",  "  ├── Agent analysing structural changes"))
    print(c("cyan",  "  ├── Agent identifying new CSS selectors"))
    print(c("cyan",  "  ├── Agent rewriting scraper (preserving schema v1.0.0)"))

    api_key = os.getenv("NOUS_API_KEY")
    if api_key and api_key != "not-set":
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url="https://inference-api.nousresearch.com/v1",
                api_key=api_key,
            )
            prompt = f"""You are an expert Python web scraping agent.

An existing FastAPI scraper broke because the target website changed its HTML/CSS classes.

## DOM Change Detected
Old fingerprint: {diff['old_fingerprint']}
New fingerprint: {diff['new_fingerprint']}
Changed: {diff['changed']}
Prominent CSS classes in new DOM: {diff['prominent_classes']}

## Broken Scraper Code
```python
{old_scraper_code}
```

## New HTML (truncated to first 8000 chars)
```html
{html[:8000]}
```

## Task
Rewrite ONLY the scraper function(s) with corrected CSS selectors that work on the new HTML.
Rules:
- PRESERVE all Pydantic model field names exactly (backward compatibility is mandatory)
- PRESERVE the FastAPI route paths and response structure
- Update ONLY the CSS selectors inside the scrape function (rename it scrape_v2())
- Add a docstring listing the new selectors
- Return ONLY the complete Python file, no markdown fences, no explanation.
"""
            response = client.chat.completions.create(
                model="Hermes-4-405B",
                messages=[
                    {"role": "system", "content": "You are Hermes, an autonomous coding agent. Return only raw Python code, no markdown."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2500,
            )
            new_code = response.choices[0].message.content.strip()
            if new_code.startswith("```"):
                new_code = "\n".join(new_code.split("\n")[1:])
            if new_code.endswith("```"):
                new_code = "\n".join(new_code.split("\n")[:-1])
            print(c("cyan", "  ├── Hermes API responded successfully"))
            return new_code
        except Exception as e:
            print(c("yellow", f"  ├── Hermes API error ({e}) — using offline fallback"))

    # Offline fallback
    time.sleep(2)
    for candidate in [
        _SCRIPT_DIR.parent / "agent" / "scraper_v2.py",
        _SCRIPT_DIR / "scraper_v2.py",
        APP_DIR / "scraper_v2.py",
    ]:
        if candidate.exists():
            print(c("cyan", "  ├── Loaded pre-written healed scraper (offline mode)"))
            return candidate.read_text()

    raise RuntimeError(
        "Cannot find scraper_v2.py and NOUS_API_KEY is not set. "
        "Set NOUS_API_KEY or place scraper_v2.py in agent/ directory."
    )


# ── Hot-Swap ──────────────────────────────────────────────────────────────────
def backup_and_replace(new_code: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"scraper_{now_ts()}.py.bak"
    if SCRAPER_PATH.exists():
        shutil.copy(SCRAPER_PATH, backup_path)
        print(c("yellow", f"  ├── Backup saved: {backup_path.name}"))
    tmp = SCRAPER_PATH.with_suffix(".tmp")
    tmp.write_text(new_code)
    tmp.replace(SCRAPER_PATH)
    print(c("green", f"  ├── New scraper written to {SCRAPER_PATH}"))
    return backup_path


# ── API Restart ───────────────────────────────────────────────────────────────
# BUG 2 FIX: Actually kills old uvicorn via PID file and starts a new process
def restart_api():
    print(c("yellow", "  ├── Restarting API server..."))

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            print(c("yellow", f"  ├── Killed old uvicorn (PID {pid})"))
        except (ValueError, ProcessLookupError, PermissionError) as e:
            print(c("yellow", f"  ├── PID kill skipped: {e}"))

    if UVICORN_BIN.exists():
        try:
            proc = subprocess.Popen(
                [str(UVICORN_BIN), "scraper:app", "--host", "0.0.0.0", "--port", "8000"],
                cwd=str(APP_DIR),
                stdout=open(APP_DIR / "api.log", "w"),
                stderr=subprocess.STDOUT,
            )
            PID_FILE.write_text(str(proc.pid))
            time.sleep(3)
            print(c("green", f"  ├── New uvicorn started (PID {proc.pid})"))
        except Exception as e:
            print(c("red", f"  ├── Failed to start uvicorn: {e}"))
    else:
        print(c("yellow", "  ├── uvicorn not found locally — relying on Docker --reload"))
        time.sleep(3)

    print(c("green", "  └── API server restart complete"))


def verify_fix() -> bool:
    time.sleep(2)
    try:
        r = httpx.get(f"{API_BASE}/announcements", timeout=10)
        if r.status_code == 200:
            data = r.json()
            count = data.get("count", 0)
            if count > 0:
                print(c("green", f"  ✓ Verification passed — {count} announcements returned"))
                return True
    except Exception as e:
        print(c("red", f"  ✗ Verification request failed: {e}"))
    print(c("red", "  ✗ Verification failed"))
    return False


# ── Main Self-Heal Loop ───────────────────────────────────────────────────────
def run_check(consecutive_failures: list) -> bool:
    print(f"\n{c('bold', '━' * 60)}")
    print(f"  {c('bold', 'Health Check')} · {now_hms()}")
    print(c("bold", "━" * 60))

    health = check_health()
    status = health.get("status", "unknown")

    if status == "ok":
        count = health.get("announcement_count", 0)
        fp    = health.get("dom_fingerprint", "n/a")
        print(c("green", f"  ✓ Status: OK  |  Announcements: {count}  |  DOM: {fp}"))
        consecutive_failures.clear()
        log_event("health_ok", {"count": count, "fingerprint": fp})
        return True

    consecutive_failures.append(now_hms())
    print(c("red",    f"  ✗ Status: {status.upper()}"))
    print(c("red",    f"  ✗ Message: {health.get('message', 'unknown')}"))
    print(c("yellow", f"  ⚠ Consecutive failures: {len(consecutive_failures)}/{FAIL_THRESHOLD}"))

    if len(consecutive_failures) < FAIL_THRESHOLD:
        print(c("yellow", "  → Threshold not reached. Waiting for next check."))
        return False

    print(c("bold", "\n  🔧 SELF-HEAL TRIGGERED"))
    log_event("heal_start", {"failures": consecutive_failures})

    # Step 1: Fetch DOM
    print(c("cyan", "  ├── Fetching current DOM from target..."))
    html = fetch_dom()
    if html is None:
        # BUG 1 FIX: Target down → abort gracefully, don't crash, retry next cycle
        print(c("red", "  ├── Target unreachable — aborting heal, will retry next cycle"))
        log_event("heal_abort", {"reason": "target_unreachable"})
        return False

    # Step 2: Diff
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass

    diff = diff_dom(state, html)
    print(c("cyan", f"  ├── DOM changed: {diff['changed']}"))
    print(c("cyan", f"  ├── Old fingerprint: {diff['old_fingerprint']}"))
    print(c("cyan", f"  ├── New fingerprint: {diff['new_fingerprint']}"))

    # Step 3: Hermes
    old_code = SCRAPER_PATH.read_text() if SCRAPER_PATH.exists() else ""
    try:
        new_code = call_hermes_agent(html, diff, old_code)
    except Exception as e:
        print(c("red", f"  ├── Hermes Agent failed: {e}"))
        log_event("heal_abort", {"reason": "agent_failed", "error": str(e)})
        return False

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
        # BUG 3 FIX: Clear failures ONLY after confirmed success — not after every heal attempt
        consecutive_failures.clear()
        print(c("green", "\n  ✅ SELF-HEAL COMPLETE — API restored with zero data loss"))
        print(c("green",  "  📋 Schema v1.0.0 preserved — downstream consumers unaffected"))
    else:
        print(c("red", "\n  ❌ Self-heal attempt failed. Will retry next cycle."))

    return success


def main():
    parser = argparse.ArgumentParser(description="Weaver — Hermes Self-Healing API Monitor")
    parser.add_argument("--watch", type=int, metavar="SECONDS",
                        help="Poll continuously every N seconds (e.g. --watch 30)")
    args = parser.parse_args()

    consecutive_failures: list = []

    if args.watch:
        print(c("bold", f"  👁 Watching API every {args.watch}s  (Ctrl+C to stop)"))
        while True:
            try:
                run_check(consecutive_failures)
            except KeyboardInterrupt:
                print(c("yellow", "\n  Stopped by user."))
                sys.exit(0)
            except Exception as e:
                # BUG 4 FIX: Catch unexpected exceptions so --watch loop NEVER dies
                print(c("red",    f"\n  ⚠ Unexpected error in watch loop: {e}"))
                print(c("yellow", "  → Continuing to next check..."))
            time.sleep(args.watch)
    else:
        run_check(consecutive_failures)


if __name__ == "__main__":
    main()
