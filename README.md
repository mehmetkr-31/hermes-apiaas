<p align="center">
  <img src="agiaas_logo.svg" alt="AGIAAS Logo" width="200"/>
</p>

# 🦊 AGIAAS - Autonomous Agent Platform

> **Intelligent Incident Management & On-Call Agent System**

AGIAAS (Autonomous GitHub Incident Analysis & Automation System) is an **intelligent agent platform** that automatically monitors your software projects, detects errors, analyzes them, and notifies you via Telegram.

## 🚀 Purpose

AGIAAS is designed to automate developer "on-call" processes:

- **Proactive Monitoring:** Automatically monitors GitHub Issues, Pull Requests, and Workflow failures
- **Smart Analysis:** Uses AI to analyze the root cause of errors
- **Interactive Approval:** Requests your approval for changes via Telegram
- **Auto-Fix:** After approval, fixes the code and creates PRs
- **Cost Tracking:** Reports token usage and costs for each operation

## 🔄 How It Works?

```
┌─────────────┐     Webhook      ┌─────────────┐     AI Analysis     ┌─────────────┐
│   GitHub    │ ───────────────▶ │ AGIAAS Agent │ ────────────────▶ │   Claude    │
│  (Events)   │                  │  (Python)   │                  │ /Hermes-Llama│
└─────────────┘                  └──────────────┘                  └─────────────┘
                                        │
                                        │ Report & Approval
                                        ▼
                               ┌─────────────┐
                               │  Telegram  │ ◀── User Approval
                               │    Bot     │
                               └─────────────┘
```

### Flow Details:

1. **Event Trigger:**
   - New Issue opened
   - Pull Request created/modified
   - GitHub Workflow fails
   - Push notification

2. **Agent Actions:**
   - Analyzes the event via GitHub API
   - Reads relevant code files
   - Identifies root cause

3. **User Interaction:**
   - You receive detailed report on Telegram
   - Decide with "Approve/Reject" buttons

4. **Auto Action:**
   - Fixes the code
   - Creates branch
   - Opens PR

## 🛠️ Installation

### Requirements

- Node.js 18+
- Python 3.12+
- pnpm
- GitHub Account
- Telegram Bot Token

### Step 1: Clone the Project

```bash
git clone https://github.com/your-username/agiaas.git
cd agiaas
```

### Step 2: Install Dependencies

```bash
pnpm install
```

### Step 3: Setup Database

```bash
pnpm run db:push
```

### Step 4: Environment Variables

```bash
# Copy example file
cp packages/agent/.env.example .env

# Edit the file
nano .env
```

Required variables:
```bash
# Telegram Bot Token (get from @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# AI Provider (OpenRouter or Nous)
OPENROUTER_API_KEY=your_openrouter_key
# OR
NOUS_API_KEY=your_nous_key
```

### Step 5: Telegram Bot Setup

1. Go to @BotFather on Telegram
2. Create new bot with `/newbot` command
3. Copy the token and paste into .env file
4. Send start command to your bot

### Step 6: Run Dashboard

```bash
pnpm run dev
```

Dashboard: http://localhost:5173

### Step 7: Start Agent

**Local:**
```bash
cd packages/agent
pnpm server:standalone
```

**With Docker:**
```bash
docker-compose up --build
```

## 📦 Project Structure

```
hermes-apiaas/
├── apps/
│   └── web/                 # React Dashboard
├── packages/
│   ├── agent/               # Python Agent (AGIAAS)
│   │   ├── scripts/
│   │   │   └── on_call/  # Agent logic
│   │   ├── tools/          # Tool definitions
│   │   └── hermes_data/  # Dependencies
│   ├── ui/                  # Shadcn UI components
│   ├── db/                  # Drizzle schema
│   ├── api/                 # API layer
│   └── auth/               # Authentication
├── docker-compose.yml       # Docker configuration
└── local.db                 # SQLite database
```

## 🔌 Supported Platforms

### GitHub Events
- ✅ Issue Opened
- ✅ Pull Request Created
- ✅ Workflow Failure
- ✅ Push Notifications

### Notification Platforms
- ✅ Telegram Bot
- 🔄 Discord (Coming Soon)
- 🔄 Slack (Coming Soon)

## ⚙️ Configuration

### Adding a Project

Via Dashboard or directly to database:

```bash
sqlite3 local.db "INSERT INTO hermes_project (repo_full_name, is_active, telegram_chat_id) VALUES ('username/repo', 1, 'chat_id');"
```

### Changing the Model

In `packages/agent/scripts/on_call/reporter.py`:

```python
DEFAULT_MODEL = "anthropic/claude-3-5-sonnet"
# or
DEFAULT_MODEL = "Hermes-4-405B"
```

## 📊 Cost Tracking

AGIAAS automatically calculates the cost of each operation:

```
💰 Cost: $0.0234  |  ⚡ Tokens: 1,240
```

Costs are calculated based on the pricing of the model you use (via OpenRouter).

## 🐳 Running with Docker

```bash
# Build for production
docker-compose build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f hermes-agent

# Stop
docker-compose down
```

## 🤖 Security Rules

The agent follows these rules for safe and accurate operation:

1. **Approval Protocol:** Gets your approval before making code changes
2. **Local Filesystem:** Only uses the `.tmp` folder
3. **GitHub Native:** All operations via `gh` CLI
4. **Database Source:** Gets active projects from database

## 📝 License

MIT License


**Note:** This project is in active development. We welcome contributions!
