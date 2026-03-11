#!/usr/bin/env python3
"""
Hermes Telegram Reporter + Bidirectional Bot

Modes:
  1. send_telegram_message(text)    → one-shot message (used by agents)
  2. start_bot()                    → long-poll bot that accepts commands

Commands supported:
  /status              → show active incidents / pending rollbacks
  /logs [n]            → last N lines from monitoring.jsonl (default 30)
  /rollback <run_id>   → re-run failed GitHub Action jobs
  /issue <number>      → show GitHub issue title + URL
  /approve             → acknowledge latest pending action
  /help                → list commands
"""
import os
import pathlib
import threading
import time
import logging
import httpx
import sqlite3
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

WORKING_DIR  = pathlib.Path(__file__).parent.parent.parent.resolve()
DB_FILE      = WORKING_DIR.parent.parent / "local.db"
LOG_FILE     = WORKING_DIR / "agent" / "on_call_logs" / "monitoring.jsonl"

def get_global_config(key: str) -> str:
    """Read a value from the global_config table in SQLite."""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        if DB_FILE.exists():
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute("SELECT value FROM global_config WHERE key = ?", (key,))
                row = cur.fetchone()
                if row:
                    return row[0]
    except Exception as e:
        logging.error(f"Failed to read {key} from DB: {e}")
    return ""

TELEGRAM_TOKEN = get_global_config("TELEGRAM_BOT_TOKEN")
CHAT_ID        = get_global_config("TELEGRAM_CHAT_ID")

_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ── One-shot send ──────────────────────────────────────────────────────────────

def send_telegram_message(text: str, chat_id: Optional[str] = None) -> bool:
    """Send a Markdown message to Telegram. Returns True on success."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logging.warning(f"[Telegram not configured] token={bool(TELEGRAM_TOKEN)} chat={bool(CHAT_ID)} msg={text}")
        return False

    cid = chat_id or CHAT_ID
    try:
        r = httpx.post(
            f"{_BASE}/sendMessage",
            json={"chat_id": cid, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        logging.error(f"Telegram send error: {e}")
        return False


def format_incident_report(event_data: dict) -> str:
    return (
        f"🚨 *PRODUCTION INCIDENT DETECTED*\n"
        f"📅 *Time:* {event_data.get('timestamp')}\n\n"
        f"🔍 *Status:* {event_data.get('summary')}\n\n"
        f"🛠 *Actions Taken:*\n{event_data.get('actions')}\n\n"
        f"✅ *Result:* {event_data.get('result')}"
    ).strip()


# ── Command handlers ───────────────────────────────────────────────────────────

def _cmd_status(args: list, chat_id: str):
    try:
        from github_action_agent import PENDING_ROLLBACKS
        if PENDING_ROLLBACKS:
            lines = []
            for run_id, info in list(PENDING_ROLLBACKS.items())[-5:]:
                name = info["run"].get("name", "?")
                lines.append(f"• Run #{run_id}: *{name}* → `/rollback {run_id}`")
            msg = "⚙️ *Pending Rollbacks:*\n" + "\n".join(lines)
        else:
            msg = "✅ No pending rollbacks or active incidents."
    except Exception as e:
        msg = f"⚠️ Status error: {e}"
    send_telegram_message(msg, chat_id)


def _cmd_logs(args: list, chat_id: str):
    n = int(args[0]) if args and args[0].isdigit() else 30
    if not LOG_FILE.exists():
        send_telegram_message("📭 No logs found yet.", chat_id)
        return
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()
    last = lines[-n:]
    snippet = "".join(last)[-3500:]  # Telegram limit ~4096
    send_telegram_message(f"📄 *Last {n} log lines:*\n```\n{snippet}\n```", chat_id)


def _cmd_rollback(args: list, chat_id: str):
    if not args:
        send_telegram_message("Usage: `/rollback <run_id>`", chat_id)
        return
    try:
        run_id = int(args[0])
    except ValueError:
        send_telegram_message("❌ Invalid run_id — must be a number.", chat_id)
        return

    send_telegram_message(f"🔄 Triggering rollback for run #{run_id}...", chat_id)
    try:
        from github_action_agent import do_rollback
        result = do_rollback(run_id)
        send_telegram_message(f"{result}", chat_id)
    except Exception as e:
        send_telegram_message(f"❌ Rollback error: {e}", chat_id)


def _cmd_issue(args: list, chat_id: str):
    if not args:
        send_telegram_message("Usage: `/issue <number>`", chat_id)
        return
    try:
        from github_api import get_issue
        issue = get_issue(int(args[0]))
        msg = (
            f"📋 *Issue #{issue['number']}*\n"
            f"*{issue['title']}*\n"
            f"State: `{issue['state']}`\n"
            f"[Open in GitHub]({issue['html_url']})"
        )
        send_telegram_message(msg, chat_id)
    except Exception as e:
        send_telegram_message(f"❌ Could not fetch issue: {e}", chat_id)


def _cmd_approve(args: list, chat_id: str):
    send_telegram_message(
        "✅ Approval acknowledged. (Automatic remediation not queued in this session — "
        "use `/rollback <run_id>` for specific actions.)",
        chat_id,
    )


def _cmd_help(args: list, chat_id: str):
    send_telegram_message(
        "🤖 *Hermes Bot Commands*\n\n"
        "`/status` — Active incidents & pending rollbacks\n"
        "`/logs [n]` — Last N log lines (default 30)\n"
        "`/rollback <run_id>` — Re-run failed GitHub Action jobs\n"
        "`/issue <number>` — Show GitHub issue details\n"
        "`/approve` — Acknowledge pending action\n"
        "`/help` — This message",
        chat_id,
    )


COMMANDS = {
    "status":   _cmd_status,
    "logs":     _cmd_logs,
    "rollback": _cmd_rollback,
    "issue":    _cmd_issue,
    "approve":  _cmd_approve,
    "help":     _cmd_help,
}


# ── Long-poll bot loop ─────────────────────────────────────────────────────────

def _process_update(update: dict):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    text    = message.get("text", "")
    chat_id = str(message.get("chat", {}).get("id", ""))

    if not text.startswith("/"):
        return  # ignore non-commands

    parts   = text.lstrip("/").split()
    cmd     = parts[0].lower().split("@")[0]  # strip @BotName suffix
    args    = parts[1:]

    handler = COMMANDS.get(cmd)
    if handler:
        try:
            handler(args, chat_id)
        except Exception as e:
            send_telegram_message(f"❌ Command error: {e}", chat_id)
    else:
        send_telegram_message(
            f"❓ Unknown command: `/{cmd}`\nSend `/help` for a list of commands.",
            chat_id,
        )


def start_bot():
    """Start the Telegram long-polling bot loop (blocking)."""
    if not TELEGRAM_TOKEN:
        logging.warning("TELEGRAM_BOT_TOKEN not set — bot polling disabled.")
        return

    logging.info("🤖 Telegram bot polling started...")
    offset = 0

    while True:
        try:
            r = httpx.get(
                f"{_BASE}/getUpdates",
                params={"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
                timeout=35,
            )
            r.raise_for_status()
            updates = r.json().get("result", [])
            for upd in updates:
                offset = upd["update_id"] + 1
                _process_update(upd)
        except httpx.ReadTimeout:
            pass  # normal for long-poll
        except Exception as e:
            logging.error(f"Bot loop error: {e}")
            time.sleep(5)


def start_bot_thread() -> threading.Thread:
    """Start bot polling in a background daemon thread."""
    t = threading.Thread(target=start_bot, daemon=True, name="telegram-bot")
    t.start()
    return t


if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN in .env first.")
    else:
        send_telegram_message("🤖 Hermes Bot is online. Send /help for commands.")
        start_bot()
