#!/usr/bin/env python3
"""
Hermes Telegram Reporter + Interactive Bot (SDK Version)

Modes:
  1. send_telegram_message(text)    → one-shot message
  2. request_approval(text, id)      → blocks until user clicks Approve/Reject/Rollback
  3. start_bot()                    → long-poll bot with command & callback handlers

Database:
  Uses the 'approvals' table (curated by Drizzle) in local.db to sync between
  one-shot agent calls and the long-running bot.
"""

import os
import pathlib
import threading
import subprocess
import time
import logging
import sqlite3
import asyncio
import json
import re
from typing import Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from run_agent import AIAgent
from encryption_utils import decrypt
from ui_utils import (
    calculate_cost,
    format_telegram_card,
    escape_html,
)
from agent.model_metadata import fetch_model_metadata
from prompts import get_commander_system_prompt, CORE_SAFETY_RULES

# Import local tools to override default library tools
try:
    import sys
    import os

    # Add the packages/agent directory to sys.path so we can import tools.*
    agent_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if agent_root not in sys.path:
        sys.path.insert(0, agent_root)
    import custom_tools.send_message_tool

    logging.info("🚀 Local send_message_tool (Modern UI) loaded successfully.")
except Exception as e:
    logging.warning(f"⚠️ Failed to load local tools: {e}")


# Static Configuration Defaults (User requested static models)
DEFAULT_MODEL = "anthropic/claude-3-5-sonnet"
DEFAULT_NOUS_MODEL = "Hermes-4-405B"

## Load environment from project root
_SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
# We are in packages/agent/scripts/on_call/ -> Root is 4 levels up
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent.parent.parent.resolve()
_ENV_PATH = _PROJECT_ROOT / ".env"

if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)
    logging.info(f"✅ Loaded .env from: {_ENV_PATH}")
else:
    # Fallback to current dir or environment
    load_dotenv()
    logging.warning(f"⚠️ .env NOT FOUND at {_ENV_PATH}. Using current environment.")

logger = logging.getLogger(__name__)

# Constants for default models/urls
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
NOUS_API_BASE_URL = os.getenv(
    "NOUS_API_BASE_URL", "https://inference-api.nousresearch.com/v1"
)


# Dynamic Path Configuration (Docker & Local Compatible)
# Priority: 1. Environment Variable, 2. Auto-detect from file location, 3. Default
def _get_project_root():
    """Get project root dynamically for Docker/Local compatibility."""
    env_root = os.getenv("HERMES_PROJECT_ROOT")
    if env_root:
        return pathlib.Path(env_root)
    # Fallback: detect from current file location
    return pathlib.Path(__file__).resolve().parent.parent.parent


PROJECT_ROOT = _get_project_root()

# Data directory for cloned repositories
DEFAULT_DATA_DIR = ".tmp"
DATA_DIR = PROJECT_ROOT / os.getenv("HERMES_DATA_DIR", DEFAULT_DATA_DIR)

# Database file
DEFAULT_DB_FILE = "local.db"
DB_FILE = PROJECT_ROOT / os.getenv("HERMES_DB_FILE", DEFAULT_DB_FILE)

# Logging
WORKING_DIR = PROJECT_ROOT / "packages" / "agent"
LOG_FILE_PATH = WORKING_DIR / "agent" / "on_call_logs" / "monitoring.jsonl"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.info(f"📁 Project Root: {PROJECT_ROOT}")
logging.info(f"📁 Data Directory: {DATA_DIR}")
logging.info(f"📁 Database: {DB_FILE}")


def get_standardized_model(model_name: str, api_key: str = "") -> str:
    """Map human model names to API-specific IDs and handle prefixes."""
    key_prefix = str(api_key)[:10] if api_key else "none"
    logging.info(f"🔍 Standardizing: '{model_name}' (Key: {key_prefix}...)")
    if not model_name:
        logging.warning("⚠️ Empty model name! Using default fallback.")
        return "anthropic/claude-3-5-sonnet"

    # 1. Map human names to API internal names (case-insensitive)
    mapping = {
        "HERMES-4-405B": "Hermes-4-405B",
        "HERMES-4-70B": "Hermes-4-70B",
        "HERMES-3-LLAMA-3.1-405B": "Hermes-4-405B",  # Upgrade deprecated model
        "CLAUDE-3-5-SONNET": "anthropic/claude-3-5-sonnet",
    }

    standardized = mapping.get(model_name.upper(), model_name)

    is_nous = bool(api_key and api_key.startswith("sk-2yd"))

    # 2. Add provider prefix for OpenRouter, but NOT for direct Nous API
    # Direct Nous API expects exactly the model name like 'Hermes-3-Llama-3.1-405B'
    if "/" not in standardized:
        if not is_nous:
            standardized = f"openrouter/{standardized}"

    # 3. Strip redundant NousResearch/ if using direct Nous API
    if is_nous:
        if "NousResearch/" in standardized:
            standardized = standardized.replace("NousResearch/", "")
        if "nous/" in standardized:
            standardized = standardized.replace("nous/", "")

    logging.info(f"🎯 Standardized result: '{standardized}' (is_nous={is_nous})")
    return standardized


def log_step(msg: str, prefix: str = "AGENT"):
    """Append a structured log line to the central monitoring file."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] 🧩 {prefix} | {msg}\n"
    try:
        if not LOG_FILE_PATH.parent.exists():
            LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE_PATH, "a") as f:
            f.write(line)
    except Exception as e:
        logging.warning(f"Failed to write to monitoring log: {e}")
    logging.info(f"Steplog: {msg}")


def get_project_config(repo_full_name: str, key: str) -> str:
    """Read a project-specific value (like llm_model) from hermes_project table."""
    active_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("NOUS_API_KEY")
    is_nous = bool(active_key and active_key.startswith("sk-2yd"))
    fallback_model = DEFAULT_NOUS_MODEL if is_nous else DEFAULT_MODEL

    try:
        if DB_FILE.exists():
            with sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True) as conn:
                cur = conn.cursor()
                column_map = {
                    "llmModel": "llm_model",
                    "webhookSecret": "webhook_secret",
                    "telegramChatId": "telegram_chat_id",
                }
                column = column_map.get(key, key)
                cur.execute(
                    f"SELECT {column} FROM hermes_project WHERE repo_full_name = ?",
                    (repo_full_name,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    val = row[0]
                    if key == "webhookSecret" and val:
                        return decrypt(val)
                    if key == "llmModel" and val and val.startswith("NousResearch/"):
                        if os.getenv("NOUS_API_KEY"):
                            return val.replace("NousResearch/", "")
                    return val or ""
    except Exception as e:
        logging.error(
            f"❌ Failed to read project config {key} for {repo_full_name}: {e}"
        )

    return fallback_model if key == "llmModel" else ""


def get_primary_bot_token() -> str:
    """Read the primary bot token from hermes_bots table."""
    try:
        if DB_FILE.exists():
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT token FROM hermes_bots WHERE is_primary = 1 LIMIT 1"
                )
                row = cur.fetchone()
                if row:
                    return decrypt(row[0])
    except Exception as e:
        logging.error(f"Failed to read primary bot from DB: {e}")
    return ""


def get_telegram_context(repo_full_name: str) -> tuple[str, str]:
    """Returns (bot_token, chat_id) for a specific repo."""
    try:
        if DB_FILE.exists():
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT telegram_chat_id, bot_id FROM hermes_project WHERE repo_full_name = ?",
                    (repo_full_name,),
                )
                row = cur.fetchone()
                if not row:
                    logging.warning(f"Project {repo_full_name} not found in DB.")
                    return "", ""

                chat_id, bot_id = row
                bot_token = ""

                if bot_id:
                    cur.execute("SELECT token FROM hermes_bots WHERE id = ?", (bot_id,))
                    bot_row = cur.fetchone()
                    if bot_row:
                        bot_token = decrypt(bot_row[0])

                if not bot_token:
                    bot_token = get_primary_bot_token()

                return bot_token, chat_id
    except Exception as e:
        logging.error(f"Failed to get telegram context: {e}")
    return "", ""


def ensure_repo_cloned(owner: Optional[str], repo: Optional[str]) -> pathlib.Path:
    """Clone or pull the target repository into .tmp/owner/repo"""
    import shutil

    if not owner or not repo:
        raise ValueError("Owner and repo must be provided")
    repo_dir = DATA_DIR / str(owner) / str(repo)
    repo_git_dir = repo_dir / ".git"

    repo_dir.parent.mkdir(parents=True, exist_ok=True)

    if not repo_git_dir.exists():
        if repo_dir.exists():
            logging.warning(
                f"🧹 Removing corrupted or empty repository directory: {repo_dir}"
            )
            shutil.rmtree(repo_dir)
        logging.info(f"🚚 Cloning {owner}/{repo} into {repo_dir}")
        subprocess.run(
            ["git", "clone", f"https://github.com/{owner}/{repo}.git", str(repo_dir)],
            check=True,
        )
    else:
        logging.info(f"🔄 Updating {owner}/{repo} in {repo_dir}")
        # Robust update: fetch and then pull/reset on current branch
        try:
            # Get current branch
            branch_res = subprocess.run(
                ["git", "-C", str(repo_dir), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            current_branch = branch_res.stdout.strip()

            # Fetch specifically from origin
            subprocess.run(["git", "-C", str(repo_dir), "fetch", "origin"], check=True)

            # Reset to origin/branch to avoid merge conflicts and tracking issues for an agent
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_dir),
                    "reset",
                    "--hard",
                    f"origin/{current_branch}",
                ],
                check=True,
            )
        except Exception as e:
            logging.warning(
                f"⚠️ Robust update failed for {owner}/{repo}: {e}. Falling back to standard pull."
            )
            subprocess.run(["git", "-C", str(repo_dir), "pull"], check=True)
    return repo_dir


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

# ── Session Management ──────────────────────────────────────────────────────


class SessionManager:
    """Manages conversation history for Telegram users."""

    def __init__(self):
        self.histories: Dict[str, list] = {}

    def get_history(self, chat_id: str) -> list:
        return self.histories.get(chat_id, [])

    def update_history(self, chat_id: str, history: list):
        # Keep history manageable
        if len(history) > 40:
            history = history[:1] + history[-39:]  # Keep system prompt + last turns
        self.histories[chat_id] = history

    def clear_history(self, chat_id: str):
        if chat_id in self.histories:
            del self.histories[chat_id]
            return True
        return False


# Global instance
sessions = SessionManager()

# ── Approval Database Interface ─────────────────────────────────────────────


def set_approval_status(
    approval_id: str,
    status: str,
    message_id: Optional[str] = None,
    chat_id: Optional[str] = None,
):
    """Update or insert approval status in the DB."""
    try:
        with sqlite3.connect(DB_FILE, timeout=20) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO approvals (id, status, message_id, chat_id) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "status=excluded.status, "
                "message_id=COALESCE(excluded.message_id, message_id), "
                "chat_id=COALESCE(excluded.chat_id, chat_id)",
                (approval_id, status, message_id, chat_id),
            )
            logging.info(f"💾 DB Update: {approval_id} -> {status}")
    except Exception as e:
        logging.error(f"DB Error (set_approval): {e}")


def get_approval_status(approval_id: str) -> str:
    """Query current status of an approval request."""
    try:
        with sqlite3.connect(DB_FILE, timeout=20) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.cursor()
            cur.execute("SELECT status FROM approvals WHERE id = ?", (approval_id,))
            row = cur.fetchone()
            return row[0] if row else "pending"
    except Exception as e:
        logging.error(f"DB Read Error (get_approval): {e}")
        return "pending"


# ── Blocking Approval Mechanism ─────────────────────────────────────────────


async def _request_approval_async(
    text: str,
    approval_id: str,
    repo_full_name: str,
    timeout: int = 300,
    allow_rollback: bool = False,
) -> str:
    """Internal async logic to send a message with buttons and poll the DB."""
    bot_token, chat_id = get_telegram_context(repo_full_name)
    if not bot_token or not chat_id:
        logging.warning(
            f"Telegram not configured for {repo_full_name}. Auto-approving for development."
        )
        return "approved"

    bot = telegram.Bot(token=bot_token)

    buttons = [
        InlineKeyboardButton("✅ Approve", callback_data=f"appr_{approval_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"rejc_{approval_id}"),
    ]

    if allow_rollback:
        buttons.insert(
            1, InlineKeyboardButton("🚀 Rollback", callback_data=f"roll_{approval_id}")
        )

    keyboard = [buttons]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Use UI Card for approval request
    formatted_text = format_telegram_card(
        title="Permission Required",
        content=text,
        repo_name=repo_full_name,
        level="incident",
    )

    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=formatted_text,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
        set_approval_status(
            approval_id,
            "pending",
            message_id=str(msg.message_id),
            chat_id=str(msg.chat_id),
        )

        logging.info(f"🕒 Polling DB for approval {approval_id}...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = get_approval_status(approval_id)
            if status in ("approved", "rejected", "rollback"):
                logging.info(f"✅ Approval {approval_id} resolved as {status} via DB.")
                return status
            await asyncio.sleep(2)

        # Timeout handling
        logging.warning(f"⏰ Approval {approval_id} timed out.")
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg.message_id,
            text=escape_html(
                f"⏰ TIMEOUT\n\n{text}\n\nAuto-rejected after {timeout}s by system."
            ),
            parse_mode="HTML",
        )
        set_approval_status(approval_id, "rejected")
        return "rejected"
    except Exception as e:
        logging.error(f"Approval request failed for {approval_id}: {e}")
        return "rejected"


def request_approval(
    text: str,
    approval_id: str,
    repo_full_name: str,
    timeout: int = 300,
    allow_rollback: bool = False,
) -> str:
    """
    Synchronous blocking call for agents.
    Sends message with buttons and waits for user interaction in Telegram.
    Returns status: "approved", "rejected", or "rollback".
    """
    logging.info(f"⏳ Waiting for user approval on {approval_id} via Telegram...")
    try:
        # Create a new loop for this sync call if none exists
        return asyncio.run(
            _request_approval_async(
                text, approval_id, repo_full_name, timeout, allow_rollback
            )
        )
    except Exception as e:
        logging.error(f"Error in request_approval sync wrapper: {e}")
        return "rejected"


# ── Message Utilities ──────────────────────────────────────────────────────


def send_telegram_message(text: str, repo_full_name: str, level: str = "info") -> bool:
    """Simplified one-shot SDK message sender with UI Card support."""
    bot_token, chat_id = get_telegram_context(repo_full_name)
    if not bot_token or not chat_id:
        return False

    async def _send():
        bot = telegram.Bot(token=bot_token)
        # Convert to UI Card
        formatted_text = format_telegram_card(
            title="System Notification",
            content=text,
            repo_name=repo_full_name,
            level=level,
        )
        await bot.send_message(chat_id=chat_id, text=formatted_text, parse_mode="HTML")

    try:
        asyncio.run(_send())
        return True
    except Exception as e:
        logging.error(f"Telegram send error: {e}")
        return False


# ── Bot Loop & Command Handlers ─────────────────────────────────────────────


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(
        escape_html(
            "🤖 Hermes Interactive Bot\n\n"
            "/new — Clear conversation history\n"
            "/status — System health & pending actions\n"
            "/logs [n] — Last N log lines (default 30)\n"
            "/help — This message\n\n"
            "I will also send you approval requests with buttons for sensitive actions."
        ),
        parse_mode="HTML",
    )


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    chat_id = str(update.effective_chat.id)
    if sessions.clear_history(chat_id):
        await update.message.reply_text(
            f"🧼 <b>Memory cleared.</b> Starting fresh!", parse_mode="HTML"
        )
    else:
        await update.message.reply_text("Memory was already empty.", parse_mode="HTML")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    msg = "🏢 Hermes Status\n✅ All systems operational.\n"
    # Show last 3 approvals
    try:
        if DB_FILE.exists():
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, status FROM approvals ORDER BY id DESC LIMIT 3")
                rows = cur.fetchall()
                if rows:
                    msg += "\nRecent Approvals:\n"
                    for r in rows:
                        status_emoji = (
                            "✅"
                            if r[1] == "approved"
                            else "❌"
                            if r[1] == "rejected"
                            else "⏳"
                        )
                        aid = str(r[0])
                        short_aid = aid[-8:]
                        msg += f"{status_emoji} <code>{short_aid}</code>: {r[1]}\n"
    except Exception:
        pass
    await update.message.reply_text(escape_html(msg), parse_mode="HTML")


async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    n = 30
    if context.args and context.args[0].isdigit():
        n = int(context.args[0])

    if not LOG_FILE_PATH.exists():
        await update.message.reply_text(
            "📭 No monitoring logs found.", parse_mode="HTML"
        )
        return

    with open(LOG_FILE_PATH, "r") as f:
        lines = f.readlines()
    snippet = "".join(lines[-n:])[-3500:]
    msg = f"📄 <b>Last {n} log lines:</b>\n<pre>{escape_html(snippet)}</pre>"
    await update.message.reply_text(msg, parse_mode="HTML")


async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """General chat interaction with Hermes."""
    if not update.message:
        return

    message_text = update.message.text or update.message.caption or ""

    if update.message.photo:
        photo = update.message.photo[-1]
        photo_file = await context.bot.get_file(photo.file_id)

        images_dir = os.path.expanduser("~/.hermes/images")
        os.makedirs(images_dir, exist_ok=True)
        filename = f"telegram_photo_{photo.file_id}.jpg"
        filepath = os.path.join(images_dir, filename)

        await photo_file.download_to_drive(filepath)

        if not message_text.strip():
            message_text = "What is in this image?"

        message_text += f"\n\n[Attached Photo: {filepath}]"

    if not message_text.strip():
        return

    # Security: Check allowlist from db
    if not update.effective_user or not update.effective_chat:
        return
    user_id = str(update.effective_user.id)

    is_allowed = False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM hermes_project WHERE telegram_chat_id = ?", (user_id,)
            )
            if cur.fetchone():
                is_allowed = True
    except:
        pass

    if not is_allowed:
        logging.warning(f"🚫 Unauthorized chat attempt from {user_id}")
        await update.message.reply_text(
            "⛔️ You are not authorized to use this commander."
        )
        return

    if message_text.startswith("/"):
        return  # Skip commands already handled

    logging.info(f"💬 Telegram Chat: {message_text}")

    # Send "typing..." action
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING
    )

    try:
        # Diagnostic: Check API Keys
        active_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("NOUS_API_KEY")
        if not active_key:
            logging.error("❌ NO API KEY FOUND in environment!")
            await update.message.reply_text(
                "❌ API Key missing. Check server environment."
            )
            return

        # Determine base_url and default model
        is_nous = active_key and active_key.startswith("sk-2yd")
        target_base_url = NOUS_API_BASE_URL if is_nous else OPENROUTER_BASE_URL
        fallback_model = DEFAULT_NOUS_MODEL if is_nous else DEFAULT_MODEL
        target_model = get_standardized_model(fallback_model, active_key)

        # Fetch projects to provide context
        projects = []
        try:
            if DB_FILE.exists():
                with sqlite3.connect(DB_FILE) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT repo_full_name FROM hermes_project WHERE is_active = 1"
                    )
                    projects = [row[0] for row in cur.fetchall()]
        except Exception as projects_err:
            logging.warning(
                f"Failed to fetch projects for Telegram context: {projects_err}"
            )

        project_context = ""
        if projects:
            project_context = (
                "\n\nRegistered repositories you can manage:\n- "
                + "\n- ".join(projects)
            )

        logging.info(
            f"Loaded {len(projects)} projects for Telegram context: {projects}"
        )

        system_prompt = get_commander_system_prompt(project_context, str(DATA_DIR))

        # Get history
        chat_id_str = str(update.effective_chat.id)
        history = sessions.get_history(chat_id_str)

        # Log the incoming message
        log_step(f"Inbound TG: {message_text[:100]}...", prefix="TG-CHAT")

        # Ensure Homebrew path is available for 'gh'
        env = os.environ.copy()
        if "/opt/homebrew/bin" not in env.get("PATH", ""):
            env["PATH"] = f"/opt/homebrew/bin:{env.get('PATH', '')}"

        # Initialize Agent
        agent = AIAgent(
            model=target_model,
            api_key=active_key,
            base_url=target_base_url,
            quiet_mode=True,
            enabled_toolsets=["terminal", "file", "web", "vision"],
            skip_memory=False,  # Enable memory for proactive flows
            skip_context_files=True,  # STRICTLY ignore default SOUL.md/AGENTS.md to enforce Commander persona
            session_id=f"tg-{chat_id_str}",
            ephemeral_system_prompt=system_prompt,
            platform="telegram",
            reasoning_config={"enabled": True, "effort": "high"},
            tool_progress_callback=lambda name, preview, args=None: log_step(
                f"Tool: {name} | {preview}", prefix="TG-TOOL"
            ),
        )

        # Use .run_conversation for multi-turn
        result = agent.run_conversation(message_text, conversation_history=history)

        response = result.get("final_response")
        new_history = result.get("messages", [])

        # Update session memory
        sessions.update_history(chat_id_str, new_history)

        # Calculate cost and tokens
        prompt_tokens = getattr(agent, "session_prompt_tokens", 0)
        completion_tokens = getattr(agent, "session_completion_tokens", 0)
        total_tokens = getattr(agent, "session_total_tokens", 0)

        metadata = fetch_model_metadata()
        cost = calculate_cost(prompt_tokens, completion_tokens, agent.model, metadata)

        log_step(
            f"Outbound TG: {str(response)[:100]}... (Cost: ${cost:.4f})",
            prefix="TG-CHAT",
        )

        if not response or not str(response).strip():
            response_text = "Hermes did not provide a message response."
        else:
            response_text = str(response)

        # Format as UI Card
        repo_info = ", ".join(projects) if projects else None
        formatted_msg = format_telegram_card(
            title="Hermes Commander",
            content=response_text,
            repo_name=repo_info,
            cost=cost,
            tokens=total_tokens,
            level="agent",
        )

        await update.message.reply_text(formatted_msg, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Chat error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes button clicks from approval messages."""
    query = update.callback_query
    if query is None or query.data is None:
        return

    data = str(query.data)
    logging.info(f"🖱 Button clicked: {data}")

    try:
        await query.answer()

        if data.startswith("appr_"):
            aid = data[len("appr_") :]
            logging.info(f"👍 Approving action: {aid}")
            set_approval_status(aid, "approved")
            # Update original message to show decision
            if query.message:
                # Use getattr because it could be InaccessibleMessage which doesn't have .text
                msg_text = getattr(query.message, "text", "") or ""
                # Use MarkdownV2 for consistency and escape the replacement text
                new_text = str(msg_text).replace(
                    format_telegram_card(
                        title="Permission Required", content="", level="incident"
                    )
                    .split("────────────────────")[0]
                    .strip(),
                    format_telegram_card(
                        title="Action Approved", content="", level="success"
                    )
                    .split("────────────────────")[0]
                    .strip(),
                )
                await query.edit_message_text(text=new_text, parse_mode="HTML")

        elif data.startswith("roll_"):
            aid = data[len("roll_") :]
            logging.info(f"🚀 Rolling back action: {aid}")
            set_approval_status(aid, "rollback")
            if query.message:
                msg_text = getattr(query.message, "text", "") or ""
                new_text = str(msg_text).replace(
                    format_telegram_card(
                        title="Permission Required", content="", level="incident"
                    )
                    .split("────────────────────")[0]
                    .strip(),
                    format_telegram_card(
                        title="Rollback Triggered", content="", level="info"
                    )
                    .split("────────────────────")[0]
                    .strip(),
                )
                await query.edit_message_text(text=new_text, parse_mode="HTML")

        elif data.startswith("rejc_"):
            aid = data[len("rejc_") :]
            logging.info(f"👎 Rejecting action: {aid}")
            set_approval_status(aid, "rejected")
            if query.message:
                msg_text = getattr(query.message, "text", "") or ""
                new_text = str(msg_text).replace(
                    format_telegram_card(
                        title="Permission Required", content="", level="incident"
                    )
                    .split("────────────────────")[0]
                    .strip(),
                    format_telegram_card(
                        title="Action Rejected", content="", level="error"
                    )
                    .split("────────────────────")[0]
                    .strip(),
                )
                await query.edit_message_text(text=new_text, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Error in callback_handler: {e}", exc_info=True)
        # Fallback to answer if not answered yet
        try:
            await query.answer("An error occurred.")
        except:
            pass


# ── Service Entry Point ────────────────────────────────────────────────────


def start_bot():
    """Main entry point for the long-running bot service."""
    primary_token = get_primary_bot_token()
    if not primary_token:
        logging.warning("Primary Bot Token not set in DB. Interactive bot disabled.")
        return

    # PTB v20+ requires an event loop in the thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = Application.builder().token(primary_token).build()

    application.add_handler(CommandHandler("start", help_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    # Handle everything else as chat
    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO) & (~filters.COMMAND), chat_handler
        )
    )

    logging.info("🤖 Interactive Telegram Bot initializing...")
    try:
        # Explicitly allow both messages and callback queries
        # stop_signals=None is CRITICAL when running in a background thread to avoid signal handling errors
        application.run_polling(
            allowed_updates=["message", "callback_query"],
            stop_signals=None,
            close_loop=False,
        )
        logging.info("🤖 run_polling has exited.")
    except telegram.error.InvalidToken as token_err:
        logging.warning(
            f"⚠️ Telegram token rejected: {token_err}. Interactive features disabled."
        )
    except Exception as poll_err:
        logging.error(f"❌ Critical error in run_polling: {poll_err}", exc_info=True)


def start_bot_thread() -> threading.Thread:
    """Call this from webhook_receiver.py to start the bot without blocking the server."""
    t = threading.Thread(target=start_bot, daemon=True, name="telegram-interactive-bot")
    t.start()
    return t


if __name__ == "__main__":
    start_bot()
