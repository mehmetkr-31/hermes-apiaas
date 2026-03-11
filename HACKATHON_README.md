# ⬡ Weaver — Agentic Data-as-a-Service
### Hermes Agent Hackathon Submission

> **Turn any website into a live REST API — powered by Hermes Agent's browser, terminal, and code tools.**

---

## 🎯 What Is Weaver?

Weaver is a terminal-native platform that lets you generate a fully working REST API from any website in under 60 seconds — **without writing a single line of code**.

You give Weaver a URL and a plain-English data schema:
```
URL:    https://www.dr.com.tr/kategori/Kitap
Schema: book title, author, price, rating
```

Weaver delegates the entire job to **Hermes Agent**, which:
1. Opens a real **headless Chrome browser** and navigates to the URL
2. Waits for JavaScript / SPA content to fully render (solving the CSR problem!)
3. **Visually identifies** where the data lives on the page
4. Writes a **self-contained FastAPI scraper** — complete with Playwright, CORS, and error handling
5. Verifies the code compiles, fixes bugs autonomously
6. **Starts the API on a port** — ready for HTTP requests

## 🤖 Why Hermes Agent?

Traditional "scraping as a service" tools use static HTTP requests. They fail on 80% of modern websites that use JavaScript frameworks (Next.js, Nuxt, React SPA) because the HTML they receive is just empty skeleton placeholders.

Hermes Agent solves this with its **browser tool** — a real Chromium instance it can navigate, scroll, wait, and visually inspect. Combined with its **code execution** and **file tools**, it can write, test, and deploy a working scraper all by itself.

**That's why Weaver is not just a scraper — it's an Agentic Data Service.**

---

## 🏗️ Architecture

```
╔══════════════════════════════════════════════════════════════╗
║                    WEAVER CONTROL CENTER                    ║
║                 (Terminal UI — OpenTUI/React)                ║
╚══════════════════↓═══════════════════════════════════════════╝
                   │ POST /apis/generate
╔══════════════════↓═══════════════════════════════════════════╗
║                 WEAVER MANAGER API  (port 9000)             ║
║                        FastAPI + uvicorn                     ║
╚══════════════════↓═══════════════════════════════════════════╝
                   │ hermes chat --query "<5-step task>"
╔══════════════════↓═══════════════════════════════════════════╗
║              HERMES AGENT  (hermes-3-llama-3.1-405b)        ║
║  Tools: browser | terminal | file | web                      ║
║  ┌─────────────────────────────────────────────────────┐    ║
║  │  1. browser_navigate(url)                           │    ║
║  │  2. browser_scroll() — trigger lazy loading         │    ║
║  │  3. browser_snapshot() — see real rendered HTML     │    ║
║  │  4. write_file(scraper_generated.py)                │    ║
║  │  5. terminal("python -c 'import scraper_generated'")│    ║
║  └─────────────────────────────────────────────────────┘    ║
╚══════════════════↓═══════════════════════════════════════════╝
                   │ uvicorn scraper_generated:app --port N
╔══════════════════↓═══════════════════════════════════════════╗
║           LIVE DATA API  (port 8010, 8011, 8012…)           ║
║                  GET /data  →  [{…}, {…}, {…}]              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Bun (`curl -fsSL https://bun.sh/install | bash`)
- Nous API Key (get one at [portal.nousresearch.com](https://portal.nousresearch.com))

### 1. Install Hermes Agent
```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

### 2. Clone & Configure Weaver
```bash
git clone https://github.com/your-username/hermes-apiaas
cd hermes-apiaas
echo "NOUS_API_KEY=your_key_here" > .env
```

### 3. Install Python Dependencies
```bash
python -m venv agent/.venv
source agent/.venv/bin/activate
pip install fastapi uvicorn httpx beautifulsoup4 playwright python-dotenv
playwright install chromium
```

### 4. Install TUI Dependencies
```bash
cd examples/hn-tui && bun install
```

### 5. Launch!
```bash
cd examples/hn-tui
bun run src/index.tsx
```

The TUI will automatically start the Manager API in the background.

---

## 🎮 Usage

1. Press **N** to open the `[ NEW API ]` form
2. Enter any website URL (including SPA sites!)
3. Describe the data you want in plain English
4. Press **TAB → Generate API Now → ENTER**
5. Watch Hermes Agent navigate, analyze, code, verify — live!
6. Press **ENTER** on the running API to view the data

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **AI Agent** | NousResearch Hermes Agent + Hermes-3-405B |
| **Browser Automation** | Playwright (via Hermes browser tool) |
| **Manager API** | FastAPI + uvicorn |
| **Terminal UI** | OpenTUI + React reconciler |
| **Generated APIs** | FastAPI + Playwright/BeautifulSoup |
| **Runtime** | Bun (TUI) + Python venv (APIs) |

---

## 💡 What Makes This Unique

| Feature | Traditional Scrapers | Weaver + Hermes Agent |
|---------|--------------------|-----------------------|
| SPA/CSR sites | ❌ Empty HTML | ✅ Real browser |
| Bot detection | ❌ Blocked | ✅ Real Chrome fingerprint |
| Code generation | ❌ Manual | ✅ Fully autonomous |
| Bug fixing | ❌ Manual | ✅ Agent self-repairs |
| Zero-config | ❌ Write selectors manually | ✅ Agent finds them |
| Any site | ❌ Static HTML only | ✅ Any modern website |

---

## 📁 Project Structure

```
hermes-apiaas/
├── scripts/
│   └── manager.py          ← Weaver Manager API (orchestrates Hermes Agent)
├── agent/
│   ├── scraper_generated.py ← Auto-written by Hermes Agent
│   └── .venv/              ← Python environment for generated scrapers
└── examples/
    └── hn-tui/
        └── src/index.tsx   ← Terminal UI (OpenTUI + React)
```

---

## 🏆 Hackathon

Built for the **Hermes Agent Hackathon** by NousResearch.
Submissions due: EOD Sunday 03/16 · [Submit via @NousResearch on Twitter]