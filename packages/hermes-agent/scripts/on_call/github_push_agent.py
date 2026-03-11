#!/usr/bin/env python3
"""
GitHub Push Agent — thin Hermes wrapper.
Hermes handles everything: analyzing changed files, maybe running tests.
"""
import os, subprocess, pathlib, logging
from datetime import datetime
from dotenv import load_dotenv
from run_agent import AIAgent

try:
    from reporter import send_telegram_message, get_global_config, NOUS_API_BASE_URL, OPENROUTER_BASE_URL
except ImportError:
    def send_telegram_message(msg):
        logging.info(f"Telegram MSG: {msg}")
    def get_global_config(key):
        return os.getenv(key, "")
    NOUS_API_BASE_URL = "https://inference-api.nousresearch.com/v1"
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

load_dotenv()

HERMES_CMD  = os.getenv("HERMES_CMD", "/Users/alikar/.local/bin/hermes")
AGENT_ROOT  = pathlib.Path(__file__).parent.parent.parent.resolve()
WORKING_DIR = AGENT_ROOT.parent.parent.resolve() # Monorepo Root
LOG_DIR     = AGENT_ROOT / "hermes_data" / "on_call_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def handle_push(branch: str, pusher: str = "", head_commit_msg: str = "", head_commit_url: str = "", owner: str = None, repo: str = None):
    project_slug = f"{owner}/{repo}" if owner and repo else branch
    logging.info(f"🚀 Dispatching Hermes for Push to {project_slug} ({branch})")

    send_telegram_message(
        f"🚀 *GitHub Push to {branch}* in {project_slug}\n*{head_commit_msg}*\nby {pusher}\n\n🔍 Hermes analyzing changes..."
    )

    prompt = f"""A new Push has been made to the branch `{branch}` in this repository ({project_slug}).

Pusher: {pusher}
Commit Message: {head_commit_msg}
Diff URL: {head_commit_url}

YOUR TASKS (in order):
1. Use the terminal tool with git to investigate the recent changes if necessary.
   - ⚡ CRITICAL PEFORMANCE RULE: The repository is ALREADY cloned to your local filesystem.
   - You MUST use fast local terminal commands like `ls -la`, `cat`, `grep`, or file tools to read the code.
   - Do NOT use slow `gh api` or network calls to read files or directory contents unless absolutely necessary.
2. Review the pushed code for linting, build errors, or potential bugs.
3. Send a brief summary of the changes and build/check status to Telegram via the messaging tool or just a simple summary.
"""

    log_file = LOG_DIR / f"push_{branch.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    main_log = LOG_DIR / "monitoring.jsonl"
    
    try:
        # Diagnostic: Check API Keys
        active_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("NOUS_API_KEY")
        
        # Determine base_url and default model
        is_nous = active_key and active_key.startswith("sk-2yd")
        target_base_url = NOUS_API_BASE_URL if is_nous else OPENROUTER_BASE_URL
        fallback_model   = "Hermes-4-405B" if is_nous else "anthropic/claude-3-5-sonnet"
        target_model     = get_global_config("MODEL") or fallback_model

        # Initialize Agent
        agent = AIAgent(
            model=target_model,
            api_key=active_key,
            base_url=target_base_url,
            quiet_mode=True, # No spinners for background agents
            enabled_toolsets=["terminal", "file", "web"],
        )
        
        # Execute natively
        response = agent.chat(prompt)
        
        # Log results
        with open(log_file, "w") as f, open(main_log, "a") as f_main:
            entry = f"\n🚀 [Push Agent] {project_slug} | Branch: {branch} | {datetime.now().isoformat()}\n"
            f.write(entry); f.write(str(response))
            f_main.write(entry); f_main.write(f"Result: {str(response)[:200]}...\n")

    except Exception as e:
        logging.error(f"Push agent failed: {e}")
        send_telegram_message(f"❌ Hermes analysis failed for {branch}: {e}")

    send_telegram_message(f"✅ Push to {branch} analyzed.")
    logging.info(f"✅ Hermes done for Push to {branch}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python github_push_agent.py <branch_name>")
        sys.exit(1)
    handle_push(sys.argv[1])
