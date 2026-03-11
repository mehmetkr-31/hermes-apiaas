# hermes-on-call

An autonomous incident management and on-call agent system built with [Better-T-Stack](https://github.com/AmanVarshney01/create-better-t-stack).

## Features

- **Autonomous On-Call Agent** - Monitoring, diagnosing, and reporting incidents.
- **Telegram Integration** - Interactive reporting and approval flow.
- **GitHub Integration** - Handles Issues, PRs, and Workflow failures.
- **Fullstack Dashboard** - Real-time monitoring and log visualization.

## Getting Started

First, install the dependencies:

```bash
pnpm install
```

## Database Setup

This project uses SQLite with Drizzle ORM.

1. Apply the schema to your database:

```bash
pnpm run db:push
```

2. Start the development server:

```bash
pnpm run dev
```

## Project Structure

```
hermes-on-call/
├── apps/
│   └── web/            # Dashboard application
├── packages/
│   ├── hermes-agent/   # Python logic, agents, and monitoring loop
│   ├── ui/             # Shared shadcn/ui components
│   ├── api/            # API layer
│   ├── auth/           # Better-Auth config
│   └── db/             # Drizzle schema
```

## Running the Agent

To start the webhook receiver (listens for GitHub events):
```bash
cd packages/hermes-agent
pnpm server:standalone
```
