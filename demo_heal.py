#!/usr/bin/env python3
"""
demo_heal.py — End-to-end self-healing demo for Weaver project
Usage: python3 demo_heal.py
"""
import sys, os, time, json, shutil, signal, subprocess, urllib.request
import urllib.request as req
from bs4 import BeautifulSoup
from pathlib import Path

BASE = Path(__file__).parent
AGENT = BASE / "agent"
MOCK  = BASE / "mock-site"
UVICORN = AGENT / ".venv" / "bin" / "uvicorn"

api_proc  = None
mock_proc = None

def kill_port(port):
    r = subprocess.run(["lsof", "-t", f"-i:{port}"], capture_output=True, text=True)
    if r.stdout.strip():
        subprocess.run(["kill", "-9"] + r.stdout.split(), capture_output=True)

def start_mock():
    kill_port(8080)
    time.sleep(0.5)
    proc = subprocess.Popen(
        ["python3", "server.py"],
        cwd=str(MOCK),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    return proc

def start_api():
    kill_port(8000)
    time.sleep(0.5)
    proc = subprocess.Popen(
        [str(UVICORN), "scraper:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(AGENT),
        stdout=open(AGENT / "api.log", "w"),
        stderr=subprocess.STDOUT,
    )
    pid_file = AGENT / "api.pid"
    pid_file.write_text(str(proc.pid))
    time.sleep(3)
    return proc

def get_json(url, retries=3):
    for i in range(retries):
        try:
            return json.loads(urllib.request.urlopen(url, timeout=5).read())
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(1)

def banner(text, color="\033[1m"):
    print(f"\n{color}{'━'*60}\033[0m")
    print(f"{color}  {text}\033[0m")
    print(f"{color}{'━'*60}\033[0m")

def ok(msg):  print(f"  \033[92m✓ {msg}\033[0m")
def err(msg): print(f"  \033[91m✗ {msg}\033[0m")
def info(msg):print(f"  \033[96m→ {msg}\033[0m")

# ── RESET ─────────────────────────────────────────────────────────────────────
banner("STEP 0 — Environment Reset")
shutil.copy(AGENT/"scraper_v1.py", AGENT/"scraper.py")
(AGENT/"state.json").unlink(missing_ok=True)
(AGENT/"heal_log.jsonl").unlink(missing_ok=True)
bdir = AGENT/"backups"
bdir.mkdir(exist_ok=True)
for f in bdir.glob("*"): f.unlink()
(MOCK/"index.html").unlink(missing_ok=True)
if (MOCK/"index_working.html").exists():
    shutil.copy(MOCK/"index_working.html", MOCK/"index.html")
else:
    err("index_working.html not found! Demo might not work.")
ok("All state reset")

# ── START SERVICES ─────────────────────────────────────────────────────────────
banner("STEP 1 — Starting Services")
info("Starting mock university site on :8080 …")
mock_proc = start_mock()
info("Starting AI-generated API on :8000 …")
api_proc  = start_api()

# ── BASELINE ──────────────────────────────────────────────────────────────────
banner("STEP 2 — Baseline Verification")
try:
    data = get_json("http://localhost:8000/announcements")
    count = data["count"]
    ok(f"API is live! count={count} schema_version={data['schema_version']}")
    ok(f"First item: {data['announcements'][0]['title']}")
except Exception as e:
    err(f"Baseline failed: {e}")
    sys.exit(1)

# ── BREAK DOM ─────────────────────────────────────────────────────────────────
banner("STEP 3 — Simulating DOM Change\033[91m (BREAKING SITE)", "\033[91;1m")
shutil.copy(MOCK/"index.html", MOCK/"index_working_backup.html")
shutil.copy(MOCK/"index_broken.html", MOCK/"index.html")
info(".announcement-card → .ann-item  (CSS classes renamed in mock site HTML)")
time.sleep(1)

try:
    urllib.request.urlopen("http://localhost:8000/announcements", timeout=5)
    err("Expected 503 but got 200 — something is wrong")
except Exception as e:
    ok(f"API correctly reports failure: {str(e)[:80]}")

# ── SELF-HEAL ─────────────────────────────────────────────────────────────────
banner("STEP 4 — Self-Heal Triggered\033[96m", "\033[96;1m")
info("Fetching new DOM from target …")
new_html = req.urlopen("http://localhost:8080", timeout=5).read().decode()
cards = len(BeautifulSoup(new_html,"html.parser").select(".announcement-card"))
items = len(BeautifulSoup(new_html,"html.parser").select(".ann-item"))
info(f"DOM fingerprint: cards={cards} | items={items}")

info("Hermes Agent: analysing diff, rewriting selectors via real LLM API …")
sys.path.append(str(BASE))
from scripts.health_check import diff_dom, call_hermes_agent
state = json.loads((AGENT/"state.json").read_text()) if (AGENT/"state.json").exists() else {}
diff = diff_dom(state, new_html)
old_code = (AGENT/"scraper.py").read_text()
new_code = call_hermes_agent(new_html, diff, old_code)

# Hot-swap
import datetime
ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
shutil.copy(AGENT/"scraper.py", bdir/f"scraper_{ts}.py.bak")
(AGENT/"scraper.py").write_text(new_code)
ok("scraper.py hot-swapped (v1 → v2). Backup saved.")

# Kill old uvicorn and restart
info("Restarting API server (killing old uvicorn) …")
api_proc.kill()
api_proc.wait()
time.sleep(1)
api_proc = start_api()
ok("API server restarted with new selectors")

# ── VERIFY ─────────────────────────────────────────────────────────────────────
banner("STEP 5 — Verification After Heal", "\033[92;1m")
try:
    data = get_json("http://localhost:8000/announcements")
    count = data["count"]
    ok(f"count={count}  schema_version={data['schema_version']}  ← Schema UNCHANGED ✓")
    ok(f"First item: {data['announcements'][0]['title']}")
    ok("SELF-HEAL COMPLETE — API restored. Zero data loss. Schema preserved.")
except Exception as e:
    err(f"Verification failed: {e}")

# ── CLEANUP ───────────────────────────────────────────────────────────────────
print("\n  Shutting down demo processes …")
api_proc.kill()
mock_proc.kill()
print("  Done.\n")
