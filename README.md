<p align="center">
  <img src="agiaas_logo.svg" alt="AGIAAS Logo" width="180"/>
</p>

# 🦊 AGIAAS - Autonomous Agent Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Stack: TypeScript & Python](https://img.shields.io/badge/Stack-TS%20%2F%20Python-blue.svg)](#-tech-stack)
[![Status: Active Development](https://img.shields.io/badge/Status-Active-green.svg)](#)

> **Intelligent Incident Management & On-Call Agent System**

AGIAAS (Autonomous GitHub Incident Analysis & Automation System) is a powerful **intelligent agent platform** that monitors your GitHub infrastructure, analyzes anomalies using state-of-the-art AI, and facilitates automated fixes via a Telegram-integrated human-in-the-loop workflow.

---

## 🚀 Key Features

- **🎯 Proactive Monitoring:** Real-time tracking of GitHub Issues, PRs, and Workflow failures.
- **🧠 Brain Layer:** Leverage Claude-3.5-Sonnet or Hermes-Llama for deep root-cause analysis.
- **📱 Human-in-the-Loop:** Interactive approval flow via Telegram bots—you decide, AI executes.
- **🛠️ Autonomous Fixes:** Automated branch creation, code patching, and PR generation.
- **💰 Cost Transparency:** Real-time token usage and cost calculation for every operation.
- **📡 Webhook Automation:** Zero-config webhook synchronization using Cloudflare tunnels.

---

## 🔄 System Architecture

```mermaid
graph TD
    subgraph GitHub ["GitHub Infrastructure"]
        Events[Issues / PRs / Workflows]
        GH_API[GitHub API & CLI]
    end

    subgraph Core ["AGIAAS Core (Monorepo)"]
        WS[Webhook Server]
        Agent[Python Agent / AGIAAS]
        DB[(SQLite / Drizzle)]
        API[Backend API]
    end

    subgraph Interaction ["User Interface"]
        Web[React Dashboard]
        Bot[Telegram Bot]
    end

    Events -- "Webhooks" --> WS
    WS -- "Trigger" --> Agent
    Agent -- "Analysis" --> AI[AI Models / Claude / Hermes]
    Agent -- "Approval Request" --> Bot
    Bot -- "User Action" --> Agent
    Agent -- "Execute Fixed/PR" --> GH_API
    Web -- "Management" --> API
    API -- "Data" --> DB
```

---

## 🔌 Project Structure

This is a monorepo powered by **Turborepo** and **pnpm**.

| Package | Path | Description |
| :--- | :--- | :--- |
| **`@agiaas/agent`** | `packages/agent` | The core Python-based intelligent agent. |
| **`@agiaas/webhook-server`** | `packages/webhook-server` | Node.js bridge for Cloudflare tunnel & webhook ingestion. |
| **`@agiaas/web`** | `apps/web` | React-based monitoring & management dashboard. |
| **`@agiaas/docs`** | `apps/docs` | Documentation site powered by Fumadocs. |
| **`@agiaas/api`** | `packages/api` | Type-safe backend API powered by oRPC. |
| **`@agiaas/db`** | `packages/db` | Database schema & migrations using Drizzle ORM. |
| **`@agiaas/auth`** | `packages/auth` | Authentication logic & providers. |
| **`@agiaas/ui`** | `packages/ui` | Shared UI components built with Tailwind & Radix. |
| **`@agiaas/env`** | `packages/env` | Type-safe environment variable management. |
| **`@agiaas/config`** | `packages/config` | Shared ESLint, TypeScript, and Biome configurations. |

---

## 🛠️ Installation & Setup

### Prerequisites

- **Runtimes:** Node.js 18+, Python 3.12+
- **Tools:** `pnpm`, `gh` (GitHub CLI), `sqlite3`, `cloudflared`
- **Accounts:** GitHub access, Telegram Bot (via @BotFather)

### Quick Start

1. **Clone & Install**
   ```bash
   git clone https://github.com/mehmetkr-31/agiaas.git
   cd agiaas
   pnpm install
   ```

2. **Database Initialization**
   ```bash
   pnpm db:push
   ```

3. **Environment Setup**
   Copy the example environment file and fill in your keys:
   ```bash
   cp .env.example .env
   ```
   > [!IMPORTANT]
   > Ensure `TELEGRAM_BOT_TOKEN`, `GITHUB_TOKEN`, and your AI provider keys (OpenRouter/Nous) are correctly set.

4. **Launch Dashboard & API**
   ```bash
   pnpm dev
   ```
   Web Dashboard: `http://localhost:5173`

5. **Start Webhook Server & Tunnel**
   ```bash
   cd packages/webhook-server
   npm run dev
   ```
   *The webhook server will automatically open a Cloudflare tunnel and sync the URL to your GitHub repositories.*

---

## 🤖 Security & Principles

AGIAAS is built with safety as a first-class citizen:

1. **Explicit Approval:** No code is modified or pushed without a direct "Approve" from the Telegram bot.
2. **Minimal Footprint:** Agents operate in isolated `.tmp` directories.
3. **Encrypted Secrets:** Sensitive tokens and webhook secrets are stored with AES-256-GCM encryption.
4. **Audit Logs:** Every AI suggestion and token cost is logged for full accountability.

---

## 📊 Cost Tracking

AGIAAS provides real-time financial tracking for AI operations. Costs are calculated dynamically based on input/output tokens and the specific model pricing fetched via **OpenRouter**.

> [!TIP]
> Use lighter models for initial triage and switch to Claude-3.5-Sonnet for complex root-cause analysis to optimize costs.

---

## 📝 License

Distributed under the **MIT License**. See `LICENSE` for more information.

---

<p align="center">
  Built with ❤️ by the AGIAAS Team
</p>
