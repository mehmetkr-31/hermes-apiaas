#!/usr/bin/env python3
"""
GitHub Push Agent — thin Hermes wrapper.
Hermes handles everything: analyzing changed files, maybe running tests.
"""
import os, subprocess, pathlib, logging
from datetime import datetime
from dotenv import load_dotenv

try:
    from reporter import send_telegram_message
except ImportError:
    def send_telegram_message(msg):
        logging.info(f"Telegram MSG: {msg}")

load_dotenv()

HERMES_CMD  = os.getenv("HERMES_CMD", "/Users/alikar/.local/bin/hermes")
WORKING_DIR = pathlib.Path(__file__).parent.parent.parent.resolve()
LOG_DIR     = WORKING_DIR / "agent" / "on_call_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def handle_push(branch: str, pusher: str = "", head_commit_msg: str = "", head_commit_url: str = ""):
    logging.info(f"🚀 Dispatching Hermes for Push to {branch}")

    send_telegram_message(
        f"🚀 *GitHub Push to {branch}*\n*{head_commit_msg}*\nby {pusher}\n\n🔍 Hermes analyzing changes..."
    )

    prompt = f"""A new Push has been made to the branch `{branch}` in this repository.

Pusher: {pusher}
Commit Message: {head_commit_msg}
Diff URL: {head_commit_url}

YOUR TASKS (in order):
1. Use the terminal tool with git to investigate the recent changes if necessary:
   `git fetch`
   `git log -1`
   `git diff HEAD~1 HEAD`

2. Review the pushed code:
   - Identify any obvious linting or build errors.
   - You can try running `npx tsc --noEmit` or `npm run check` if it's a JS/TS project to see if the push broke anything.
   - Analyze the diff for potential bugs.

3. Send a brief summary of the changes and build/check status to Telegram via the messaging tool or just a simple summary if everything looks fine.
"""

    log_file = LOG_DIR / f"push_{branch.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    main_log = LOG_DIR / "monitoring.jsonl"
    
    proc = subprocess.Popen(
        [HERMES_CMD, "chat", "-q", prompt, "--toolsets", "terminal,file,web"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE, text=True,
        env=os.environ.copy(), bufsize=1, cwd=str(WORKING_DIR),
    )
    try:
        proc.stdin.write("s\n" * 10)
        proc.stdin.flush()
    except Exception:
        pass

    with open(log_file, "w", buffering=1) as f_private, open(main_log, "a", buffering=1) as f_main:
        f_main.write(f"\n🚀 [Hermes Push Agent] Analyzing branch: {branch} @ {datetime.now().isoformat()}\n")
        f_main.write(f"Commit: {head_commit_msg}\n{'─' * 40}\n")
        
        for line in proc.stdout:
            if line:
                f_private.write(line); f_private.flush()
                f_main.write(line); f_main.flush()
                
    proc.wait()

    send_telegram_message(f"✅ Push to {branch} analyzed.")
    logging.info(f"✅ Hermes done for Push to {branch}")
    with open(main_log, "a") as f_main:
        f_main.write(f"\n✅ Hermes analysis finished for {branch}.\n")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python github_push_agent.py <branch_name>")
        sys.exit(1)
    handle_push(sys.argv[1])
