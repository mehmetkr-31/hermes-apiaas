# SKILL: AutoAPI — Autonomous Web Scraping API Generator
**Version:** 1.0.0  
**For:** Hermes Agent (NousResearch)  
**Purpose:** Given a URL, autonomously generate, deploy, test, and self-heal a REST API that exposes the site's structured data.

---

## Overview

When a user provides a URL, you will autonomously:
1. Audit the site for ethical/legal scraping permission
2. Analyse its DOM structure using browser tools
3. Generate a FastAPI scraper with correct CSS selectors
4. Deploy it inside a Docker sandbox
5. Verify it returns valid, semantically correct data
6. Install a self-healing health monitor
7. Report the live API endpoint to the user

You operate in three phases. **Never skip Phase 1.** Always preserve backward-compatible JSON schema across self-heals.

---

## Phase 1 — Ethical Reconnaissance

### Step 1.1 — robots.txt Check
```
GET {url}/robots.txt
```
- Parse `Disallow:` rules for the target path.
- If the path is disallowed → **STOP.** Inform user. Do not proceed.
- If allowed or no robots.txt → proceed to Step 1.2.
- Log result: `{ "robots_check": "allowed" | "denied", "rule": "..." }`

### Step 1.2 — Browser Inspection (Browserbase / browser_tool)
- Navigate to the target URL with stealth mode enabled (avoid bot detection).
- Wait for full DOM render (handle SPA/React: wait for `networkidle`).
- Extract:
  - Page title and meta description
  - All repeating card/list container elements (look for 3+ sibling divs with similar structure)
  - CSS class names on title, date, category, body, and link elements
  - Whether pagination exists (`next` button or page numbers)
- Store the raw HTML snapshot and a structural fingerprint:
  ```
  fingerprint = f"cards={count_of_primary_container}"
  ```

### Step 1.3 — Anti-Bot Risk Assessment
- Check response headers for `cf-ray` (Cloudflare) or `x-akamai-*`.
- If detected, activate Browserbase stealth/human-simulation mode.
- Add randomized 1–3 second delays between requests.

---

## Phase 2 — Code Generation & Sandboxed Testing

### Step 2.1 — Generate FastAPI Scraper
Write a complete Python FastAPI file with:

**Required endpoints:**
- `GET /announcements` (or appropriate resource name) → returns `AnnouncementsResponse`
- `GET /health` → returns `HealthResponse`
- `GET /state` → returns last persisted state JSON

**Required JSON schema (must never break across versions):**
```python
class Item(BaseModel):
    title: str
    category: str
    excerpt: str
    date: str        # ISO 8601 datetime string
    department: str  # or equivalent contextual field

class Response(BaseModel):
    source: str
    scraped_at: str
    schema_version: str   # e.g. "1.0.0" — NEVER change field names
    count: int
    items: list[Item]
```

**Required implementation details:**
- Use `httpx` for async HTTP requests (not `requests`)
- Use `beautifulsoup4` for HTML parsing
- Save state to `/app/state.json` after every successful scrape
- Include `compute_dom_fingerprint(html)` function for diff detection
- If scraper returns 0 results → raise `HTTP 503` (triggers health monitor)

**Selector documentation:** Inside `scrape_v1()`, add a docstring listing every selector used:
```python
def scrape_v1(html: str) -> list[dict]:
    """
    Selectors (v1):
      card:       .CLASSNAME
      title:      .CLASSNAME a
      date:       time.CLASSNAME [datetime attr]
      department: .CLASSNAME
    """
```

### Step 2.2 — Docker Sandbox Deployment
```bash
# terminal_tool commands:
docker build -t autoapi ./agent
docker run -d \
  --name hermes-autoapi \
  -p 8000:8000 \
  -v autoapi-state:/app \
  autoapi
```
- Confirm container is running: `docker ps | grep hermes-autoapi`
- Wait 3 seconds for startup, then proceed to verification.

### Step 2.3 — Automated Self-Verification
```bash
curl -s http://localhost:8000/announcements | python3 -m json.tool
```

**Verification checklist (all must pass):**
- [ ] HTTP 200 response
- [ ] `count` > 0
- [ ] `items[0].title` is a non-empty string (not a CSS selector or HTML tag)
- [ ] `items[0].date` matches ISO format OR is a recognizable date string
- [ ] `items[0].category` is one of the expected categorical values
- [ ] `schema_version` field is present

**Semantic validation** — ask yourself:
> "Does `items[0].title` look like an actual announcement title? Does the date make sense for this year? Is the category meaningful?"

If any check fails → go to Step 2.4.

### Step 2.4 — Self-Debugging (if verification fails)
1. Re-open browser_tool and inspect the live DOM again
2. Print all class names of the repeating container
3. Rewrite `scrape_v1()` with corrected selectors
4. Increment debug attempt counter (max 3 attempts before escalating to user)
5. Rebuild Docker image and restart container
6. Re-run verification checklist

---

## Phase 3 — Deployment & Self-Healing

### Step 3.1 — Install Health Monitor
Deploy `health_check.py --watch 30` as a background process or second container.

The health monitor must:
- Poll `GET /health` every 30 seconds
- Count consecutive failures
- Trigger self-heal after `FAIL_THRESHOLD` consecutive failures (default: 1 for demo, 3 for production)

### Step 3.2 — Self-Heal Protocol (triggered automatically)
When health is `"broken"`:

```
1. Fetch current DOM from target URL
2. Compute new DOM fingerprint
3. Diff against stored state.json fingerprint
4. If changed:
   a. Identify renamed/replaced CSS classes
   b. Generate new scraper code (scraper_v2.py) with updated selectors
   c. PRESERVE schema_version and all field names — backward compatibility is mandatory
   d. Backup current scraper: cp scraper.py backups/scraper_{timestamp}.py.bak
   e. Atomically replace: mv scraper_new.py scraper.py
   f. Restart uvicorn (SIGHUP or supervisor reload)
   g. Wait 3s, call /announcements, verify count > 0
5. Log heal event to heal_log.jsonl
6. Report: "DOM change detected. Classes renamed: X→Y. Healed in {N}s. Schema preserved."
```

### Step 3.3 — Report to User
After successful deployment, output:
```
✅ AutoAPI is live!

  📡 Endpoint:  http://localhost:8000/announcements
  🏥 Health:    http://localhost:8000/health
  📋 Schema:    v1.0.0 (stable)
  🔄 Monitoring: Active (30s interval)

Sample response:
  { "count": 6, "items": [...] }

The API will self-heal if the site's DOM changes.
Backup scrapers are stored in /app/backups/.
```

---

## Tool Usage Reference

| Task | Tool |
|------|------|
| Fetch robots.txt | `web_search` or `terminal_tool` (curl) |
| Inspect DOM | `browser_tool` (Browserbase, stealth mode) |
| Run Docker commands | `terminal_tool` |
| Write Python files | `terminal_tool` (write to /app/) |
| Verify API response | `terminal_tool` (curl + jq) |
| Self-heal code update | `terminal_tool` (atomic file swap) |

---

## Critical Constraints

- **NEVER** scrape a URL that is `Disallow`ed in robots.txt
- **NEVER** change JSON field names between scraper versions (backward compatibility)
- **NEVER** run untrusted scraper code outside Docker sandbox
- **ALWAYS** save `state.json` after every successful scrape
- **ALWAYS** include `schema_version` in every API response
- **ALWAYS** document selectors in the scraper function docstring
- **LIMIT** to 3 self-debug attempts before escalating to user

---

## Demo Script (Hackathon Video)

```
1. User: "Build an API for http://localhost:8080"
2. Hermes: Checks robots.txt → allowed
3. Hermes: Opens browser, inspects DOM → finds .announcement-card
4. Hermes: Writes scraper_v1.py with correct selectors
5. Hermes: docker build && docker run
6. Hermes: curl /announcements → 6 results ✓
7. Hermes: "API is live at :8000/announcements"
--- [Demonstrator swaps index.html with index_broken.html on mock server] ---
8. Health monitor: detects HTTP 503
9. Health monitor: triggers self-heal
10. Hermes: fetches DOM, computes diff (cards=0|items=6)
11. Hermes: rewrites selectors (.announcement-card→.ann-item, etc.)
12. Hermes: hot-swaps scraper, restarts uvicorn
13. Hermes: curl /announcements → 6 results ✓
14. Hermes: "DOM change detected & repaired. Schema preserved. Zero downtime."
```
