---
name: weaver
description: Autonomous web scraping API generator and self-healer. Given any URL, Weaver uses browser inspection to understand the DOM, generates a production-ready FastAPI scraper, deploys it locally, and continuously monitors it — autonomously rewriting CSS selectors if the target site changes its HTML structure.
version: 2.0.0
author: community
license: MIT
metadata:
  hermes:
    tags: [web-scraping, fastapi, self-healing, api-generation, DOM, automation]
    homepage: https://github.com/nousresearch/hermes-apiaas
---

# Weaver — Autonomous Self-Healing API Engine

Weaver turns any URL into a live, self-healing REST API — no manual code required.

---

## ⚡ GOLDEN RULE — ACT IMMEDIATELY, SINGLE FINAL MESSAGE

> **When the user gives you a URL, START WORKING SILENTLY. Do not ask questions. Do not send progress messages.**
>
> - Do NOT ask "is the site running?" — check it yourself with `terminal_tool` (`curl`)
> - Do NOT ask "what data do you want?" — inspect the DOM and figure it out
> - Do NOT ask "should I check robots.txt?" — always check it, silently
> - Do NOT ask permission before each step — execute the full workflow autonomously
> - Do NOT send intermediate messages like "Checking robots.txt...", "Writing scraper..." etc.
> - **Send ONLY ONE message at the very end** when everything is done (or failed)
>
> The only time you may ask a question is if you have exhausted all 3 self-debug
> attempts and still cannot get `count > 0`. In every other situation: **just do it.**
>
> **MESSAGING RULE: Complete ALL phases silently → send ONE final summary message.**
> The final message format is defined at the bottom of this skill under "Phase 4 — Reporting".

---

You use your own `browser_tool`, `web_extract`, and `terminal_tool` to:
1. Inspect the target site's real DOM
2. Write a FastAPI scraper with correct CSS selectors
3. Deploy and verify it
4. Monitor it and autonomously repair it when the site updates its HTML

> **Architecture note:** This is a true Hermes Agent skill. You do NOT call an external
> LLM API to write code — you write the code yourself using your own reasoning, informed
> by what you see with `browser_tool` and `web_extract`.

---

## Prerequisites

- Python 3.11+ with `pip` available (`python3 --version`)
- `uvicorn`, `fastapi`, `httpx`, `beautifulsoup4`, `pydantic` installed in the target venv
- Optional: Docker (for sandboxed deployment)
- The `hermes-apiaas` project cloned locally:
  ```
  git clone https://github.com/nousresearch/hermes-apiaas ~/hermes-apiaas
  ```
- Dependencies installed:
  ```
  python3 -m venv ~/hermes-apiaas/agent/.venv
  ~/hermes-apiaas/agent/.venv/bin/pip install -r ~/hermes-apiaas/agent/requirements.txt
  ```

---

## Activation

When a user says any of the following (or similar), activate this skill and **immediately begin Phase 1** without asking any questions first:

- `"weave <url>"` or `"/weave <url>"`
- `"Build an API for <url>"`
- `"Turn <url> into an API"`
- `"Scrape <url> and give me an endpoint"`
- `"My API is broken, heal it"`
- `"Watch my scraper and fix it if it breaks"`
- `"Start monitoring <url>"`

**Immediately upon activation, execute Phase 1 → Phase 2 → Phase 3 silently. Send NO messages until Phase 4.**

---

## Phase 1 — Ethical Reconnaissance

> Execute this phase silently and quickly. Do not stop to ask the user anything.

### Step 1.1 — robots.txt Check

Use `terminal_tool` with `curl` — do this first, automatically:

```bash
curl -s "{url}/robots.txt"
```

- If the relevant path has a `Disallow:` rule → **STOP. Inform the user. Do not proceed.**
- If allowed or no robots.txt exists → proceed silently to Step 1.2.

### Step 1.2 — DOM Inspection

**First try the fast path** — use `terminal_tool` with `curl` to fetch the raw HTML and find repeating elements:

```bash
curl -s "http://localhost:8080" | python3 -c "
from bs4 import BeautifulSoup, sys
soup = BeautifulSoup(sys.stdin.read(), 'html.parser')
for div in soup.find_all('div', class_=True):
    children = [c for c in div.children if hasattr(c,'name') and c.name]
    if len(children) >= 2:
        print(div.get('class'), '->', [c.name for c in children[:4]])
" | head -30
```

If the page is JavaScript-rendered (empty output), then use `browser_navigate` + `browser_snapshot`. This is critical — do NOT guess selectors from memory.

```
browser_navigate(url)
browser_snapshot(full=True)
```

Look for:
- Repeating card/list containers (3+ sibling divs with similar structure) → these are your data items
- CSS class names on: title, date, category, body, link, image elements
- Whether the page is a SPA (React/Vue/Angular) — wait for `networkidle`
- Pagination controls

If the page requires JavaScript rendering (blank snapshot), use `browser_vision`:
```
browser_vision("What are the CSS class names of the repeating article/card elements on this page?")
```

Store your findings as a structural fingerprint:
```
fingerprint = "cards={count_of_primary_container_selector}"
```

### Step 1.3 — Anti-Bot Risk Assessment

Check if the response headers contain `cf-ray` (Cloudflare) or `x-akamai-*`. If detected, use `browser_tool` stealth mode (already enabled by default via Browserbase). Add randomized delays if scraping in loops.

---

## Phase 2 — Code Generation & Deployment

### Step 2.1 — Write the FastAPI Scraper

Based on what you observed in Phase 1, write a complete FastAPI scraper. Save it to:
```
~/hermes-apiaas/agent/scraper.py
```

The file **must** follow this exact structure:

```python
"""
AutoAPI — Generated by Weaver Agent
Target: {url}
Generated: {iso_timestamp}
Selectors (v1):
  card:       .CLASSNAME
  title:      .CLASSNAME a
  date:       time.CLASSNAME [datetime attr]
  department: .CLASSNAME
  category:   .CLASSNAME
  excerpt:    .CLASSNAME
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup
import json
from datetime import datetime
from pathlib import Path

app = FastAPI(
    title="Weaver Auto-Scraper",
    description="Auto-generated by Weaver Agent · v1",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TARGET_URL = "{url}"
STATE_FILE = Path("state.json")

# ── Pydantic Schema (NEVER change field names across self-heals) ─────────────
class Item(BaseModel):
    title: str
    category: str
    excerpt: str
    date: str        # ISO 8601 string
    department: str  # or equivalent contextual field

class ItemsResponse(BaseModel):
    source: str
    scraped_at: str
    schema_version: str = "1.0.0"
    count: int
    items: List[Item]

class HealthResponse(BaseModel):
    status: str           # "ok" | "broken"
    last_successful_scrape: Optional[str]
    item_count: int
    dom_fingerprint: Optional[str]
    message: str

# ── Scraping Logic — V1 selectors ────────────────────────────────────────────
def scrape_v1(html: str) -> list[dict]:
    """
    Selectors for original DOM (v1):
      card:       .ACTUAL_CLASS_YOU_OBSERVED
      title:      .ACTUAL_CLASS a
      ...
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for card in soup.select(".YOUR_CARD_SELECTOR"):
        title_el = card.select_one(".YOUR_TITLE_SELECTOR a")
        if not title_el:
            continue
        results.append({
            "title":      title_el.get_text(strip=True),
            "category":   (card.select_one(".YOUR_CATEGORY_SELECTOR") or object()).get_text("") if card.select_one(".YOUR_CATEGORY_SELECTOR") else "Unknown",
            "excerpt":    card.select_one(".YOUR_EXCERPT_SELECTOR").get_text(strip=True) if card.select_one(".YOUR_EXCERPT_SELECTOR") else "",
            "date":       card.select_one("time.YOUR_DATE_SELECTOR").get("datetime", "") if card.select_one("time.YOUR_DATE_SELECTOR") else "",
            "department": card.select_one(".YOUR_DEPT_SELECTOR").get_text(strip=True) if card.select_one(".YOUR_DEPT_SELECTOR") else "",
        })
    return results

def compute_dom_fingerprint(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    count = len(soup.select(".YOUR_CARD_SELECTOR"))
    return f"cards={count}"

def save_state(data: dict):
    STATE_FILE.write_text(json.dumps(data, indent=2))

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/items", response_model=ItemsResponse)
async def get_items():
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(TARGET_URL)
            resp.raise_for_status()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Cannot reach target: {e}")

    items = scrape_v1(resp.text)
    if not items:
        raise HTTPException(status_code=503, detail="Scraper returned 0 results. DOM may have changed.")

    save_state({
        "last_successful_scrape": datetime.utcnow().isoformat(),
        "item_count": len(items),
        "dom_fingerprint": compute_dom_fingerprint(resp.text),
        "selector_version": "v1",
    })
    return ItemsResponse(source=TARGET_URL, scraped_at=datetime.utcnow().isoformat(), count=len(items), items=items)

@app.get("/health", response_model=HealthResponse)
async def health():
    state = load_state()
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(TARGET_URL)
            html = resp.text
        except Exception as e:
            return HealthResponse(status="broken", last_successful_scrape=state.get("last_successful_scrape"), item_count=0, dom_fingerprint=None, message=f"Target unreachable: {e}")

    items = scrape_v1(html)
    fp    = compute_dom_fingerprint(html)
    if not items:
        return HealthResponse(status="broken", last_successful_scrape=state.get("last_successful_scrape"), item_count=0, dom_fingerprint=fp, message="Scraper returned 0 results — DOM likely changed.")
    return HealthResponse(status="ok", last_successful_scrape=datetime.utcnow().isoformat(), item_count=len(items), dom_fingerprint=fp, message="All systems nominal.")

@app.get("/state")
async def get_state():
    return load_state()
```

**Fill in all `.YOUR_*_SELECTOR` placeholders with the actual CSS class names you observed in Phase 1. The template above is a scaffold — every selector must come from your real DOM inspection.**

### Step 2.2 — Write the File with terminal_tool

```bash
# Write scraper.py to the agent directory
cat > ~/hermes-apiaas/agent/scraper.py << 'PYEOF'
{your generated python code here}
PYEOF
```

Or use `file_write` if available, then verify:

```bash
python3 -c "import py_compile; py_compile.compile('~/hermes-apiaas/agent/scraper.py', doraise=True)" && echo "SYNTAX OK"
```

### Step 2.3 — Deploy with uvicorn

```bash
# Kill any existing instance on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Start the API server
cd ~/hermes-apiaas/agent
.venv/bin/uvicorn scraper:app --host 0.0.0.0 --port 8000 &
echo $! > api.pid
sleep 3
echo "API started with PID $(cat api.pid)"
```

### Step 2.4 — Verify the Deployment

```bash
curl -s http://localhost:8000/items | python3 -m json.tool
```

**Verification checklist — ALL must pass:**
- [ ] HTTP 200 response
- [ ] `count` > 0
- [ ] `items[0].title` is a real title string (not an HTML tag or CSS selector name)
- [ ] `items[0].date` is a recognizable date string
- [ ] `items[0].category` is a meaningful category word
- [ ] `schema_version` field is present in the response

**Semantic check:** Ask yourself — "Does `items[0].title` look like an actual article title? Does the data make sense for this website?" If not, go to Step 2.5.

### Step 2.5 — Self-Debug (if verification fails)

1. Re-run `browser_snapshot(full=True)` on the target URL
2. Use `browser_vision("What are the exact CSS class names of the repeating item containers and their child elements?")` if needed
3. Inspect the raw HTML of one card element directly:
   ```bash
   curl -s "{url}" | python3 -c "
   from bs4 import BeautifulSoup, sys
   soup = BeautifulSoup(sys.stdin.read(), 'html.parser')
   for div in soup.find_all('div', class_=True)[:30]:
       children = [c for c in div.children if hasattr(c,'name') and c.name]
       if len(children) >= 2:
           print(div.get('class'), '→', [c.name for c in children[:3]])
   "
   ```
4. Rewrite `scrape_v1()` with corrected selectors
5. Re-deploy and re-verify (maximum 3 attempts before asking the user for help)

---

## Phase 3 — Self-Healing Monitor

### Step 3.1 — Start the Health Monitor

```bash
cd ~/hermes-apiaas
agent/.venv/bin/python scripts/health_check.py --watch 30 >> health.log 2>&1 &
echo $! > health.pid
echo "Health monitor started (PID $(cat health.pid)), polling every 30s"
```

The monitor will:
- Poll `GET /health` every 30 seconds
- If `status == "broken"`: fetch the current DOM, diff it against `state.json`, rewrite selectors, hot-swap `scraper.py`, restart uvicorn
- Log all events to `agent/heal_log.jsonl`

### Step 3.2 — Self-Heal Protocol (when triggered automatically or by user request)

When health is `"broken"`:

**1. Fetch current DOM:**
```
web_extract(["{target_url}"], format="markdown")
```
Or if JavaScript rendering is needed:
```
browser_navigate("{target_url}")
browser_snapshot(full=True)
```

**2. Identify what changed:**
Compare the old selectors (from `scrape_v1()` docstring) against what you now see in the DOM. Identify renamed/replaced CSS classes.

**3. Rewrite selectors — write `scrape_v2()`:**
```python
def scrape_v2(html: str) -> list[dict]:
    """
    Selectors for updated DOM (v2):
      card:       .NEW_CLASS   (was .OLD_CLASS)
      title:      .NEW_TITLE a (was .OLD_TITLE a)
      ...
    """
    # ... corrected selector logic ...
```

**4. Backward compatibility rules (MANDATORY):**
- ✅ PRESERVE all Pydantic model field names (`title`, `category`, `excerpt`, `date`, `department`)
- ✅ PRESERVE all API route paths (`/items`, `/health`, `/state`)
- ✅ PRESERVE `schema_version: "1.0.0"`
- ❌ NEVER rename response fields — downstream consumers must remain unaffected

**5. Hot-swap atomically:**
```bash
# Backup
cp ~/hermes-apiaas/agent/scraper.py ~/hermes-apiaas/agent/backups/scraper_$(date +%Y%m%dT%H%M%S).py.bak

# Atomic replace
cat > ~/hermes-apiaas/agent/scraper.py << 'PYEOF'
{new scraper code with scrape_v2}
PYEOF

# Restart API
kill $(cat ~/hermes-apiaas/agent/api.pid) 2>/dev/null || true
sleep 1
cd ~/hermes-apiaas/agent
.venv/bin/uvicorn scraper:app --host 0.0.0.0 --port 8000 &
echo $! > api.pid
sleep 3
```

**6. Verify fix:**
```bash
curl -s http://localhost:8000/items | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('count:', d['count'])
print('title:', d['items'][0]['title'] if d['items'] else 'NO ITEMS')
"
```

### Step 3.3 — Report to User

After a successful self-heal, report:

```
🔧 Self-heal complete in {N}s

  DOM change detected:
    Old selector: .announcement-card → New: .ann-item
    Old title:    .ann-title a       → New: .ann-heading a

  ✅ API restored: http://localhost:8000/items
  📋 Schema v1.0.0 preserved — downstream unaffected
  💾 Backup saved: agent/backups/scraper_{timestamp}.py.bak
```

---

## Phase 4 — Reporting & Status

After successful deployment (Phase 2), always report:

```
✅ Weaver API is live!

  📡 Data:      http://localhost:8000/items
  🏥 Health:    http://localhost:8000/health
  📊 State:     http://localhost:8000/state
  📋 Schema:    v1.0.0 (stable — field names are locked)
  🔄 Monitoring: Active (30s interval via health_check.py)

Sample:
  { "count": 6, "items": [{"title": "...", "category": "...", ...}] }

The API will self-heal if the site updates its HTML structure.
Backup scrapers are saved in ~/hermes-apiaas/agent/backups/
```

---

## Telegram Workflow

When operating via the Hermes Telegram gateway, the full flow is:

**User → Telegram:**
```
/weave https://example.com/news
```

**Agent response sequence:**
1. `"🕵️ Checking robots.txt..."`
2. `"🌐 Inspecting DOM with browser tool..."`
3. `"✍️ Writing FastAPI scraper (found .article-card selectors)..."`
4. `"🚀 Deploying on :8000..."`
5. `"✅ API is live! http://localhost:8000/items — 12 items found"`
6. `"👁 Health monitor started (30s interval)"` 

**When site breaks (unprompted message from cron/monitor):**
```
⚠️ API BROKEN — http://localhost:8000/items returning 503

  Target: https://example.com/news
  Reason: Scraper returned 0 results
  DOM fingerprint changed: cards=12 → cards=0|items=12

  🔧 Self-healing now...
```

**After heal:**
```
✅ Healed in 18s

  .article-card → .news-card
  .article-title → .news-heading

  Schema v1.0.0 preserved. API restored.
```

---

## Tool Usage Reference

| Task | Tool | Notes |
|------|------|-------|
| Check robots.txt | `terminal_tool` (`curl -s {url}/robots.txt`) | Always do this first |
| Inspect DOM (static site) | `web_extract([url], format="markdown")` | Fast, no browser needed |
| Inspect DOM (SPA/React) | `browser_navigate` + `browser_snapshot(full=True)` | Required for JS-rendered pages |
| Visually confirm selectors | `browser_vision("What CSS classes are on the card elements?")` | Use when snapshot is ambiguous |
| Write scraper.py | `terminal_tool` (`cat > ... << 'EOF'`) | Atomic write |
| Syntax check code | `terminal_tool` (`python3 -c "import py_compile; ..."`) | Before deploying |
| Deploy API | `terminal_tool` (`uvicorn scraper:app ...`) | Background process |
| Verify API | `terminal_tool` (`curl -s http://localhost:8000/items`) | Check count > 0 |
| Start monitor | `terminal_tool` (`python scripts/health_check.py --watch 30 &`) | Background |
| Hot-swap scraper | `terminal_tool` (backup + write + restart) | Atomic sequence |

---

## Critical Constraints

- **NEVER** proceed if `robots.txt` disallows the target path
- **NEVER** guess CSS selectors — always inspect the real DOM with browser or web_extract
- **NEVER** rename Pydantic model fields between versions (backward compatibility)
- **NEVER** run uvicorn outside the `~/hermes-apiaas/agent/` directory
- **ALWAYS** document selectors in a docstring inside `scrape_v1()` / `scrape_v2()`
- **ALWAYS** save `state.json` after every successful scrape
- **ALWAYS** backup before hot-swapping (`agent/backups/scraper_{timestamp}.py.bak`)
- **LIMIT** self-debug to 3 attempts — escalate to user if still failing

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `count: 0` after deploy | Wrong CSS selector | Re-inspect DOM with `browser_snapshot(full=True)`, fix selector |
| `502 Bad Gateway` | Target URL unreachable | Check URL, robots.txt, anti-bot detection |
| `503 Service Unavailable` | DOM changed | Trigger self-heal: `python scripts/health_check.py` |
| `SyntaxError` on import | Code generation error | Run `python3 -c "import py_compile; py_compile.compile('scraper.py')"` |
| Port 8000 in use | Previous instance still running | `lsof -ti:8000 | xargs kill -9` |
| Selector returns HTML tag | Wrong element targeted | Use `browser_vision` to visually confirm which element holds the title |
| Anti-bot block (Cloudflare) | JS challenge | Use `browser_tool` with stealth (already enabled via Browserbase) |

---

## Demo Script (Hackathon / Live Presentation)

```
1. User: "/weave http://localhost:8080"
2. Agent: Checks robots.txt → allowed
3. Agent: browser_navigate → browser_snapshot → finds .announcement-card elements
4. Agent: Writes scraper.py with correct v1 selectors
5. Agent: uvicorn scraper:app deployed on :8000
6. Agent: curl /items → {"count": 6, "items": [...]} ✓
7. Agent: "✅ API live! Monitoring started."
--- [Demonstrator: cp index_broken.html index.html on mock server] ---
8. Health monitor: GET /health → {"status": "broken"} detected
9. Agent: browser_snapshot on target → sees .ann-item instead of .announcement-card
10. Agent: Writes scrape_v2() with new selectors
11. Agent: Backup + hot-swap scraper.py + restart uvicorn
12. Agent: curl /items → {"count": 6, ...} ✓
13. Agent (Telegram): "✅ Healed in 14s. .announcement-card → .ann-item. Schema preserved."
```
