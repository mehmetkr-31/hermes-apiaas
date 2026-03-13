#!/usr/bin/env python3
"""
Hermes Telegram Reporter + Interactive Bot (SDK Version)

Modes:
  1. send_telegram_message(text)    → one-shot message
  2. request_approval(text, id)      → blocks until user clicks Approve/Reject
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
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from run_agent import AIAgent
from encryption_utils import decrypt

load_dotenv()

# Static Configuration Defaults (User requested static models)
DEFAULT_MODEL = "anthropic/claude-3-5-sonnet"
DEFAULT_NOUS_MODEL = "Hermes-4-405B" # Reverting to the old fallback that worked

# Pathing setup
PROJECT_ROOT = pathlib.Path("/Users/alikar/dev/hermes-apiaas")
WORKING_DIR  = PROJECT_ROOT / "packages" / "hermes-agent"
DB_FILE      = PROJECT_ROOT / "local.db"
LOG_FILE_PATH = WORKING_DIR / "agent" / "on_call_logs" / "monitoring.jsonl"
DATA_DIR     = PROJECT_ROOT / ".tmp"

# Log the discovery for debugging
logging.info(f"📍 Database Discovery: Using {DB_FILE} (Project Root: {PROJECT_ROOT})")

# Load root .env
root_env = PROJECT_ROOT / ".env"
if root_env.exists():
    load_dotenv(dotenv_path=root_env)
    # AIAgent looks for OPENROUTER_API_KEY. If NOUS_API_KEY is present, map it as priority.
    if os.getenv("NOUS_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = os.environ["NOUS_API_KEY"]
        logging.info("🔑 Mapped NOUS_API_KEY to OPENROUTER_API_KEY for agent initialization.")
else:
    load_dotenv() # Fallback to local

# Constants for default models/urls
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
NOUS_API_BASE_URL = "https://inference-api.nousresearch.com/v1"


def get_standardized_model(model_name: str, api_key: str = "") -> str:
    """Map human model names to API-specific IDs and handle prefixes."""
    key_prefix = str(api_key)[:10] if api_key else "none"
    logging.info(f"🔍 Standardizing: '{model_name}' (Key: {key_prefix}...)")
    if not model_name: 
        logging.warning("⚠️ Empty model name! Using default fallback.")
        return "anthropic/claude-3-5-sonnet"
    
    # 1. Map human names to API internal names
    mapping = {
        "Hermes-4-405B": "Hermes-4-405B",
        "Hermes-3-Llama-3.1-405B": "Hermes-3-Llama-3.1-405B",
    }
    
    standardized = mapping.get(model_name, model_name)
    
    # 2. Strip NousResearch/ prefix if using direct Nous API
    is_nous = bool(api_key and api_key.startswith("sk-2yd"))
    if is_nous and standardized.startswith("NousResearch/"):
        standardized = standardized.replace("NousResearch/", "")
    
    logging.info(f"🎯 Standardized result: '{standardized}'")
    return standardized

def log_step(msg: str, prefix: str = "AGENT"):
    """Append a structured log line to the central monitoring file."""
    timestamp = datetime.now().strftime('%H:%M:%S')
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
    # HARDCODED STATIC FALLBACKS
    if key == "llmModel":
        active_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("NOUS_API_KEY")
        is_nous = bool(active_key and active_key.startswith("sk-2yd"))
        return DEFAULT_NOUS_MODEL if is_nous else DEFAULT_MODEL

    try:
        if DB_FILE.exists():
            with sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True) as conn:
                cur = conn.cursor()
                column_map = {
                    "llmModel": "llm_model",
                    "webhookSecret": "webhook_secret",
                    "telegramChatId": "telegram_chat_id"
                }
                column = column_map.get(key, key)
                cur.execute(f"SELECT {column} FROM hermes_project WHERE repo_full_name = ?", (repo_full_name,))
                row = cur.fetchone()
                if row:
                    val = row[0]
                    if key == "webhookSecret" and val:
                        return decrypt(val)
                    if key == "llmModel" and val and val.startswith("NousResearch/"):
                        if os.getenv("NOUS_API_KEY"):
                            return val.replace("NousResearch/", "")
                    return val or ""
    except Exception as e:
        logging.error(f"❌ Failed to read project config {key} for {repo_full_name}: {e}")
    
    return ""

def get_primary_bot_token() -> str:
    """Read the primary bot token from hermes_bots table."""
    try:
        if DB_FILE.exists():
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute("SELECT token FROM hermes_bots WHERE is_primary = 1 LIMIT 1")
                row = cur.fetchone()
                if row: return decrypt(row[0])
    except Exception as e:
        logging.error(f"Failed to read primary bot from DB: {e}")
    return ""

def get_telegram_context(repo_full_name: str) -> tuple[str, str]:
    """Returns (bot_token, chat_id) for a specific repo."""
    try:
        if DB_FILE.exists():
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute("SELECT telegram_chat_id, bot_id FROM hermes_project WHERE repo_full_name = ?", (repo_full_name,))
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
            logging.warning(f"🧹 Removing corrupted or empty repository directory: {repo_dir}")
            shutil.rmtree(repo_dir)
        logging.info(f"🚚 Cloning {owner}/{repo} into {repo_dir}")
        subprocess.run(["git", "clone", f"https://github.com/{owner}/{repo}.git", str(repo_dir)], check=True)
    else:
        logging.info(f"🔄 Updating {owner}/{repo} in {repo_dir}")
        subprocess.run(["git", "-C", str(repo_dir), "pull"], check=True)
    return repo_dir


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

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
            history = history[:1] + history[-39:] # Keep system prompt + last turns
        self.histories[chat_id] = history

    def clear_history(self, chat_id: str):
        if chat_id in self.histories:
            del self.histories[chat_id]
            return True
        return False

# Global instance
sessions = SessionManager()

# ── Approval Database Interface ─────────────────────────────────────────────

def set_approval_status(approval_id: str, status: str, message_id: Optional[str] = None, chat_id: Optional[str] = None):
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
                (approval_id, status, message_id, chat_id)
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

async def _request_approval_async(text: str, approval_id: str, repo_full_name: str, timeout: int = 300) -> bool:
    """Internal async logic to send a message with buttons and poll the DB."""
    bot_token, chat_id = get_telegram_context(repo_full_name)
    if not bot_token or not chat_id:
        logging.warning(f"Telegram not configured for {repo_full_name}. Auto-approving for development.")
        return True

    bot = telegram.Bot(token=bot_token)
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"appr_{approval_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"rejc_{approval_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=f"🛡 *HERMES NEEDS YOUR PERMISSION*\n\n{text}",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        set_approval_status(approval_id, "pending", message_id=str(msg.message_id), chat_id=str(msg.chat_id))
        
        logging.info(f"🕒 Polling DB for approval {approval_id}...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = get_approval_status(approval_id)
            if status == "approved": 
                logging.info(f"✅ Approval {approval_id} granted via DB.")
                return True
            if status == "rejected": 
                logging.info(f"❌ Approval {approval_id} rejected via DB.")
                return False
            await asyncio.sleep(2)
            
        # Timeout handling
        logging.warning(f"⏰ Approval {approval_id} timed out.")
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg.message_id,
            text=f"⏰ *TIMEOUT*\n\n{text}\n\n_Auto-rejected after {timeout}s by system._"
        )
        set_approval_status(approval_id, "rejected")
        return False
    except Exception as e:
        logging.error(f"Approval request failed for {approval_id}: {e}")
        return False

def request_approval(text: str, approval_id: str, repo_full_name: str, timeout: int = 300) -> bool:
    """
    Synchronous blocking call for agents. 
    Sends message with buttons and waits for user interaction in Telegram.
    """
    logging.info(f"⏳ Waiting for user approval on {approval_id} via Telegram...")
    try:
        # Create a new loop for this sync call if none exists
        return asyncio.run(_request_approval_async(text, approval_id, repo_full_name, timeout))
    except Exception as e:
        logging.error(f"Error in request_approval sync wrapper: {e}")
        return False

# ── Message Utilities ──────────────────────────────────────────────────────

def send_telegram_message(text: str, repo_full_name: str) -> bool:
    """Simplified one-shot SDK message sender."""
    bot_token, chat_id = get_telegram_context(repo_full_name)
    if not bot_token or not chat_id:
        return False
    async def _send():
        bot = telegram.Bot(token=bot_token)
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    try:
        asyncio.run(_send())
        return True
    except Exception as e:
        logging.error(f"Telegram send error: {e}")
        return False

# ── Bot Loop & Command Handlers ─────────────────────────────────────────────

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    await update.message.reply_text(
        "🤖 *Hermes Interactive Bot*\n\n"
        "/new — Clear conversation history\n"
        "/status — System health & pending actions\n"
        "/logs [n] — Last N log lines (default 30)\n"
        "/help — This message\n\n"
        "I will also send you approval requests with buttons for sensitive actions.",
        parse_mode="Markdown"
    )

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat: return
    chat_id = str(update.effective_chat.id)
    if sessions.clear_history(chat_id):
        await update.message.reply_text("🧼 *Memory cleared.* Starting fresh!", parse_mode="Markdown")
    else:
        await update.message.reply_text("Memory was already empty.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    msg = "🏢 *Hermes Status*\n✅ All systems operational.\n"
    # Show last 3 approvals
    try:
        if DB_FILE.exists():
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, status FROM approvals ORDER BY id DESC LIMIT 3")
                rows = cur.fetchall()
                if rows:
                    msg += "\n*Recent Approvals:*\n"
                    for r in rows:
                        status_emoji = "✅" if r[1] == "approved" else "❌" if r[1] == "rejected" else "⏳"
                        aid = str(r[0])
                        short_aid = aid[-8:]
                        msg += f"{status_emoji} `{short_aid}`: {r[1]}\n"
    except Exception: pass
    await update.message.reply_text(msg, parse_mode="Markdown")

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    n = 30
    if context.args and context.args[0].isdigit():
        n = int(context.args[0])
    
    if not LOG_FILE_PATH.exists():
        await update.message.reply_text("📭 No monitoring logs found.")
        return
    
    with open(LOG_FILE_PATH, "r") as f:
        lines = f.readlines()
    snippet = "".join(lines[-n:])[-3500:]
    await update.message.reply_text(f"📄 *Last {n} log lines:*\n```\n{snippet}\n```", parse_mode="Markdown")

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
    if not update.effective_user or not update.effective_chat: return
    user_id = str(update.effective_user.id)
    
    is_allowed = False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM hermes_project WHERE telegram_chat_id = ?", (user_id,))
            if cur.fetchone():
                is_allowed = True
    except:
        pass
        
    if not is_allowed:
        logging.warning(f"🚫 Unauthorized chat attempt from {user_id}")
        await update.message.reply_text("⛔️ You are not authorized to use this commander.")
        return

    if message_text.startswith("/"):
        return # Skip commands already handled

    logging.info(f"💬 Telegram Chat: {message_text}")
    
    # Send "typing..." action
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.constants.ChatAction.TYPING)

    try:
        # Diagnostic: Check API Keys
        active_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("NOUS_API_KEY")
        if not active_key:
            logging.error("❌ NO API KEY FOUND in environment!")
            await update.message.reply_text("❌ API Key missing. Check server environment.")
            return

        # Determine base_url and default model
        is_nous = active_key and active_key.startswith("sk-2yd")
        target_base_url = NOUS_API_BASE_URL if is_nous else OPENROUTER_BASE_URL
        fallback_model   = "NousResearch/Hermes-3-Llama-3.1-405B" if is_nous else "anthropic/claude-3-5-sonnet"
        target_model = fallback_model
        
        # Fetch projects to provide context
        projects = []
        try:
            if DB_FILE.exists():
                with sqlite3.connect(DB_FILE) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT repo_full_name FROM hermes_project WHERE is_active = 1")
                    projects = [row[0] for row in cur.fetchall()]
        except Exception as projects_err:
            logging.warning(f"Failed to fetch projects for Telegram context: {projects_err}")

        project_context = ""
        if projects:
            project_context = f"\n\nRegistered repositories you can manage (located in {DATA_DIR}):\n- " + "\n- ".join(projects)
        
        logging.info(f"Loaded {len(projects)} projects for Telegram context: {projects}")

        system_prompt = f"""# HERMES COMMANDER: GITHUB-NATIVE OPERATIONAL DIRECTIVE

You are Hermes Commander, a high-level autonomous agent responsible for maintaining and fixing remote software systems via GitHub.

## MISSION CONTEXT
You manage the following registered repositories: {project_context}

## OPERATIONAL DIRECTIVE: "GITHUB-NATIVE RESEARCH"
1. **ISOLATION**: You are FORBIDDEN from exploring the local filesystem (e.g., `packages/`, `apps/`, `node_modules/`). The local codebase is your OWN dashboard; do NOT confuse it with the projects you manage.
2. **RESEARCH**: Use the `terminal` tool to investigate target repositories strictly via `gh` CLI or GitHub API:
   - Use `gh repo view [owner]/[repo] --web` to see repo info.
   - Use `gh api repos/[owner]/[repo]/contents/[path]` to read files.
   - Use `gh issue list` and `gh pr list` to understand current state.
3. **ONLY** if you are tasked with a code fix and need to modify files, clone the repository to a temporary path under `{DATA_DIR}`:
   - `gh repo clone [owner]/[repo] {DATA_DIR}/[owner]/[repo]`

## ACTION WORKFLOWS
- **Incident reporting**: Research via `gh api`, then ask: "I've analyzed the bug in [repo]. Should I open an issue?"
- **Remediation**: If approved, clone to `{DATA_DIR}`, fix the code, run tests, then ask: "Fix implemented in [repo]. Should I create a Pull Request?"

## SAFETY & APPROVAL PROTOCOL (STRICT)
- **ZERO MUTATION WITHOUT CONSENT**: You are FORBIDDEN from running `gh issue create`, `gh pr create`, `git push`, or any command that commit/pushes code without an explicit "yes", "proceed", or "approve" from the user in the *current* conversation turn.
- **CLEAR PROPOSALS**: State the Target Repository and a summary of the change before asking for confirmation.

You are decisive, proactive, and strictly adhere to GitHub-native investigation tools.
"""

        # Get history
        chat_id_str = str(update.effective_chat.id)
        history = sessions.get_history(chat_id_str)

        # Initialize Agent
        agent = AIAgent(
            model=target_model,
            api_key=active_key,
            base_url=target_base_url,
            quiet_mode=True,
            enabled_toolsets=["terminal", "file", "web", "vision"],
            skip_memory=False, # Enable memory for proactive flows
            session_id=f"tg-{chat_id_str}",
            ephemeral_system_prompt=system_prompt,
            platform="telegram"
        )
        
        # Use .run_conversation for multi-turn
        result = agent.run_conversation(
            message_text,
            conversation_history=history
        )
        
        response = result.get("final_response")
        new_history = result.get("messages", [])
        
        # Update session memory
        sessions.update_history(chat_id_str, new_history)
        
        if not response or not str(response).strip():
            response = "Hermes did not provide a message response."
        else:
            response = str(response)

        # Telegram message limit is ~4096. Split if needed.
        if len(response) > 4000:
            response = response[:3900] + "\n\n... (trimmed)"

        await update.message.reply_text(response)
        
    except Exception as e:
        logging.error(f"Chat error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes button clicks from approval messages."""
    query = update.callback_query
    if query is None or query.data is None: return
    
    data = str(query.data)
    logging.info(f"🖱 Button clicked: {data}")
    
    try:
        await query.answer()
        
        if data.startswith("appr_"):
            aid = data[len("appr_"):]
            logging.info(f"👍 Approving action: {aid}")
            set_approval_status(aid, "approved")
            # Update original message to show decision
            if query.message:
            # Use getattr because it could be InaccessibleMessage which doesn't have .text
                msg_text = getattr(query.message, "text", "") or ""
                new_text = str(msg_text).replace("🛡 *HERMES NEEDS YOUR PERMISSION*", "✅ *ACTION APPROVED*")
                await query.edit_message_text(text=new_text, parse_mode="Markdown")
            
        elif data.startswith("rejc_"):
            aid = data[len("rejc_"):]
            logging.info(f"👎 Rejecting action: {aid}")
            set_approval_status(aid, "rejected")
            if query.message:
                msg_text = getattr(query.message, "text", "") or ""
                new_text = str(msg_text).replace("🛡 *HERMES NEEDS YOUR PERMISSION*", "❌ *ACTION REJECTED*")
                await query.edit_message_text(text=new_text, parse_mode="Markdown")
            
    except Exception as e:
        logging.error(f"Error in callback_handler: {e}", exc_info=True)
        # Fallback to answer if not answered yet
        try: await query.answer("An error occurred.")
        except: pass

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
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & (~filters.COMMAND), chat_handler))

    logging.info("🤖 Interactive Telegram Bot initializing...")
    try:
        # Explicitly allow both messages and callback queries
        # stop_signals=None is CRITICAL when running in a background thread to avoid signal handling errors
        application.run_polling(
            allowed_updates=["message", "callback_query"], 
            stop_signals=None, 
            close_loop=False
        )
        logging.info("🤖 run_polling has exited.")
    except telegram.error.InvalidToken as token_err:
        logging.warning(f"⚠️ Telegram token rejected: {token_err}. Interactive features disabled.")
    except Exception as poll_err:
        logging.error(f"❌ Critical error in run_polling: {poll_err}", exc_info=True)

def start_bot_thread() -> threading.Thread:
    """Call this from webhook_receiver.py to start the bot without blocking the server."""
    t = threading.Thread(target=start_bot, daemon=True, name="telegram-interactive-bot")
    t.start()
    return t

if __name__ == "__main__":
    start_bot()
