# Weaver ⚡️

**Built for the Hackathon using the Nous Research Hermes Agent + Hermes-4-405B**

[![Demo](demo.gif)](demo.gif)

---

## The Problem

Web scrapers and third-party APIs are incredibly fragile. When a target website updates its UI or renames its CSS classes, traditional scrapers break immediately — causing data loss, downtime, and forcing engineers to manually inspect the new HTML and rewrite the code.

## The Solution

**Weaver** is an autonomous, self-healing API generation engine that runs as a **Hermes Agent Skill**. Point it at any URL and it will:

1. **Inspect** the live DOM using Hermes's own `browser_tool` (real Browserbase cloud browser — not just an LLM guess)
2. **Write** a production-ready FastAPI scraper with correct CSS selectors, based on what it actually sees
3. **Deploy** the API locally and verify it returns real data
4. **Monitor** it continuously — and if the site ever updates its HTML, autonomously rewrite the selectors and hot-swap the code into production without dropping a single request
5. **Notify** you on Telegram when something breaks and when it's been fixed

---

## Architecture — True Hermes Agent Skill

> ⚠️ **Important distinction:** Weaver is not just a wrapper around the Hermes LLM API.
> It is a **Hermes Agent Skill** — the agent uses its own built-in tools to do the work.

```
User (Telegram) → Hermes Agent
                      │
                      ├─ browser_tool    → Opens target URL, reads real DOM
                      ├─ terminal_tool   → Writes scraper.py, runs uvicorn, verifies output
                      ├─ web_extract     → Fetches robots.txt, quick DOM snapshots
                      └─ (no LLM API call needed — agent writes the code itself)
```

### vs. the old approach

| | Old Weaver (v1) | New Weaver (v2 — this) |
|---|---|---|
| DOM inspection | `httpx.get()` → sends raw HTML to LLM | `browser_tool` → agent sees live rendered page |
| Code generation | Calls Hermes-4-405B API | Agent writes code using its own reasoning |
| Deployment | Python subprocess | `terminal_tool` → agent runs uvicorn directly |
| Telegram | Not supported | Built into Hermes Gateway |
| Self-heal trigger | Standalone `health_check.py` | Hermes cron + agent re-runs skill |

---

## Two Core Workflows

### 1. Zero-to-One Generation

User sends: `/weave https://uni.edu/announcements`

```
Agent:  🕵️ Checking robots.txt... allowed
        🌐 browser_navigate → browser_snapshot(full=True)
        ✍️  Found .announcement-card (×6), writing scraper...
        🚀  uvicorn deployed on :8000
        ✅  API live! 6 items returned
        👁  Health monitor started (30s interval)
```

### 2. Zero-Downtime Self-Healing

Site updates CSS. API returns 503.

```
Monitor: ⚠️  /health → broken (0 results)
Agent:   🌐  browser_snapshot → .announcement-card gone, .ann-item found
         ✍️  Rewrote scrape_v2() with new selectors
         💾  Backup saved: backups/scraper_20250310T142233.py.bak
         🔄  Hot-swapped scraper.py → uvicorn restarted
         ✅  Verified: 6 items returned. Schema v1.0.0 preserved.

Telegram: "✅ Healed in 14s. .announcement-card → .ann-item. Downstream unaffected."
```

---

## Skill File

The core logic lives in a single Hermes Skill definition:

```
hermes-agent/skills/web/weaver/SKILL.md
```

This file tells Hermes Agent exactly how to:
- Check `robots.txt` before touching any site
- Use `browser_tool` to inspect real DOM (not guess from memory)
- Write FastAPI code with correct selectors
- Deploy, verify, and monitor
- Self-heal while preserving backward-compatible JSON schema

---

## How to Run

### Prerequisites

```bash
# 1. Clone both repos
git clone https://github.com/nousresearch/hermes-agent   ~/HERMES/hermes-agent
git clone https://github.com/nousresearch/hermes-apiaas  ~/HERMES/hermes-apiaas

# 2. Install Weaver dependencies
python3 -m venv ~/HERMES/hermes-apiaas/agent/.venv
~/HERMES/hermes-apiaas/agent/.venv/bin/pip install -r ~/HERMES/hermes-apiaas/agent/requirements.txt

# 3. Install hermes-agent
cd ~/HERMES/hermes-agent
pip install -e .
```

### Option A — Telegram Bot (Recommended)

The cleanest experience. You chat with Hermes on Telegram, it does everything for you.

**Step 1 — Get a bot token**

1. Open Telegram, search for `@BotFather`
2. Send `/newbot`, follow the prompts
3. Copy the token (looks like `110201543:AAHdqTcvCH1vGWJxfSeofSs4tAqZSPyT`)

**Step 2 — Get your Telegram user ID**

1. Search for `@userinfobot` on Telegram
2. Send `/start` — it replies with your numeric user ID (e.g. `123456789`)

**Step 3 — Configure hermes-agent**

```bash
# Edit ~/.hermes/.env  (create it if it doesn't exist)
cat >> ~/.hermes/.env << EOF

# Telegram
TELEGRAM_BOT_TOKEN=110201543:AAHdqTcvCH1vGWJxfSeofSs4tAqZSPyT
TELEGRAM_ALLOWED_USERS=123456789

# Nous API (for Hermes-4-405B model)
NOUS_API_KEY=your_nous_api_key_here

# Browserbase (for browser_tool DOM inspection)
BROWSERBASE_API_KEY=your_browserbase_key
BROWSERBASE_PROJECT_ID=your_project_id

# Firecrawl (for web_extract)
FIRECRAWL_API_KEY=your_firecrawl_key
EOF
```

**Step 4 — Set your model to Hermes-4-405B**

```bash
cat >> ~/.hermes/.env << EOF
LLM_MODEL=nousresearch/hermes-4-405b
EOF
```

Or via OpenRouter:
```bash
# OpenRouter also hosts Hermes models
LLM_MODEL=nousresearch/hermes-3-405b-instruct
OPENROUTER_API_KEY=your_openrouter_key
```

**Step 5 — Start the gateway**

```bash
cd ~/HERMES/hermes-agent
hermes gateway run
```

Or as a background service (macOS):
```bash
hermes gateway install   # installs as launchd service
hermes gateway start
hermes gateway status
```

**Step 6 — Chat on Telegram**

```
You:   /weave https://northbridge.edu/announcements
Bot:   🕵️ Checking robots.txt...
Bot:   🌐 Inspecting DOM with browser tool...
Bot:   ✍️ Found .announcement-card elements, writing scraper...
Bot:   🚀 Deploying API on localhost:8000...
Bot:   ✅ API is live!
       📡 http://localhost:8000/items  (6 items)
       🏥 http://localhost:8000/health
       👁 Monitoring every 30s
```

---

### Option B — CLI Demo (Self-Healing Demo)

To see the self-healing demo without Telegram:

```bash
cd ~/HERMES/hermes-apiaas

# Make sure your Nous API key is set
echo "NOUS_API_KEY=your_key_here" > .env

# Run the end-to-end demo
./agent/.venv/bin/python demo_heal.py
```

**What happens:**
1. A mock university site boots on `:8080`
2. The AI-generated API boots on `:8000`
3. We simulate a CSS rename: `.announcement-card` → `.ann-item`
4. The API returns `503 Service Unavailable`
5. The health monitor detects the DOM change
6. Hermes rewrites the scraper with new selectors
7. The API recovers — schema unchanged, zero data loss

---

### Option C — Generate a New API from Scratch (CLI)

```bash
cd ~/HERMES/hermes-apiaas

./agent/.venv/bin/python scripts/init_api.py \
    --url "https://news.ycombinator.com" \
    --schema "Extract post titles, URLs, points, and comment counts"
```

This uses the Hermes LLM API directly to generate `agent/scraper_generated.py`.

---

## Project Structure

```
hermes-apiaas/                          # Weaver standalone scripts
├── agent/
│   ├── scraper.py                      # Live FastAPI scraper (auto-generated + auto-healed)
│   ├── scraper_v1.py                   # Original selectors (demo baseline)
│   ├── scraper_v2.py                   # Healed selectors (post-DOM-change)
│   ├── backups/                        # Timestamped scraper backups
│   ├── state.json                      # Last successful scrape state
│   └── requirements.txt
├── scripts/
│   ├── init_api.py                     # Zero-to-One generator (calls Hermes LLM API)
│   └── health_check.py                 # Self-healing orchestrator
├── mock-site/
│   ├── index_working.html              # Original DOM (6 announcements)
│   ├── index_broken.html               # Broken DOM (CSS classes renamed)
│   └── server.py                       # Local HTTP server for demo
├── docs/
│   ├── SKILL.md                        # Legacy skill doc (v1)
│   └── WEAVER_SKILL.md                 # New Hermes Agent skill definition (v2)
├── demo_heal.py                        # End-to-end self-healing demo
└── docker-compose.yml                  # Docker deployment (3 services)

hermes-agent/skills/web/weaver/         # True Hermes Agent Skill
├── SKILL.md                            # Full skill definition (browser_tool + terminal_tool)
└── DESCRIPTION.md                      # Category description
```

---

## API Endpoints

Once deployed, your auto-generated API exposes:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/items` | GET | Returns all scraped items (Pydantic-typed JSON) |
| `/health` | GET | Health check — triggers self-heal if `status: broken` |
| `/state` | GET | Last successful scrape metadata + DOM fingerprint |

### Sample Response

```json
{
  "source": "https://uni.edu/announcements",
  "scraped_at": "2025-03-10T14:22:33.412Z",
  "schema_version": "1.0.0",
  "count": 6,
  "items": [
    {
      "title": "Spring 2025 Course Registration Closes",
      "category": "Deadline",
      "excerpt": "All students must complete registration by end of this week...",
      "date": "2025-03-10",
      "department": "Registrar's Office"
    }
  ]
}
```

---

## Self-Healing Guarantees

| Guarantee | Details |
|-----------|---------|
| **Zero data loss** | API keeps serving last-known-good data during heal |
| **Schema stability** | `schema_version: "1.0.0"` and all field names preserved forever |
| **Backup on every heal** | `agent/backups/scraper_{timestamp}.py.bak` |
| **Atomic hot-swap** | Write to `.tmp`, then `rename()` — never a half-written file |
| **Telegram alerts** | Break + heal events delivered to your chat |
| **Max 3 self-debug cycles** | Escalates to user if still failing after 3 attempts |

---

## Environment Variables

### `hermes-agent` (`~/.hermes/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | For Telegram | From `@BotFather` |
| `TELEGRAM_ALLOWED_USERS` | Recommended | Your Telegram user ID |
| `NOUS_API_KEY` | Yes | Nous Research inference API key |
| `OPENROUTER_API_KEY` | Alternative | OpenRouter (also hosts Hermes models) |
| `LLM_MODEL` | Yes | e.g. `nousresearch/hermes-3-405b-instruct` |
| `BROWSERBASE_API_KEY` | For browser_tool | Browserbase cloud browser |
| `BROWSERBASE_PROJECT_ID` | For browser_tool | Browserbase project ID |
| `FIRECRAWL_API_KEY` | For web_extract | Firecrawl web extraction |

### `hermes-apiaas` (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NOUS_API_KEY` | Yes | For `init_api.py` and `health_check.py` |
| `API_BASE` | No | FastAPI server URL (default: `http://localhost:8000`) |
| `TARGET_URL` | No | Target website URL (default: `http://localhost:8080`) |

---

## 🎬 Demo

Watch Weaver detect a broken site and autonomously heal itself:

![Weaver Self-Healing Demo](demo.gif)

---

## Hackathon Notes

This project demonstrates two complementary uses of the Hermes ecosystem:

1. **Hermes Agent Skill (`skills/web/weaver/SKILL.md`)** — The canonical implementation. The agent uses its own `browser_tool`, `terminal_tool`, and `web_extract` to inspect, generate, deploy, and heal scrapers. No external LLM calls. This is what "using Hermes Agent" actually means.

2. **Standalone scripts (`scripts/init_api.py`, `scripts/health_check.py`)** — For environments without the full agent stack, these scripts call the Hermes-4-405B inference API directly. Useful for CI/CD pipelines or minimal deployments.

Both share the same FastAPI structure, same Pydantic schemas, and the same self-healing guarantees.