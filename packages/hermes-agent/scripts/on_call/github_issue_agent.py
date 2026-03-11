#!/usr/bin/env python3
"""
GitHub Issue Agent — thin Hermes wrapper.
Hermes handles everything: gh CLI, web search, code analysis, GitHub comment.
"""
import os, subprocess, pathlib, logging
from datetime import datetime
from dotenv import load_dotenv
from reporter import send_telegram_message

load_dotenv()

HERMES_CMD  = os.getenv("HERMES_CMD", "/Users/alikar/.local/bin/hermes")
WORKING_DIR = pathlib.Path(__file__).parent.parent.parent.resolve()
LOG_DIR     = WORKING_DIR / "agent" / "on_call_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def handle_issue(issue_number: int, title: str = "", body: str = "", owner: str = None, repo: str = None):
    logging.info(f"📋 Dispatching Hermes for Issue #{issue_number} in {owner}/{repo}")

    send_telegram_message(
        f"📋 *GitHub Issue #{issue_number}* at {owner}/{repo}\n*{title}*\n\n🔍 Hermes analyzing..."
    )

    prompt = f"""GitHub Issue #{issue_number} has just been opened in the repository {owner}/{repo}.

Title: {title}
Body:
{body[:2000]}

YOUR TASKS (in order):
1. Use the github-issues skill and `gh` CLI to read the full issue:
   `gh issue view {issue_number} --repo {owner}/{repo}`

2. Research the problem:
   - Search the codebase (this project at {WORKING_DIR}) for related code using file tools
   - Use web_search to find solutions or similar issues online

3. Post your analysis directly as a GitHub comment — use the terminal tool:
   `gh issue comment {issue_number} --repo {owner}/{repo} --body "<your markdown analysis>"`
   Structure the comment as:
   ## 🤖 Hermes Analysis
   ### Root Cause Hypothesis
   ### Recommended Fix
   ### References

4. Send a summary to Telegram via the messaging tool.

Use `terminal_tool` for all `gh` commands. The `gh` CLI is already authenticated.
"""

    log_file = LOG_DIR / f"issue_{issue_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    main_log = LOG_DIR / "monitoring.jsonl"
    
    proc = subprocess.Popen(
        [HERMES_CMD, "chat", "--model", "Hermes-4-405B", "-q", prompt, "--toolsets", "terminal,file,web"],
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
        f_main.write(f"\n📋 [Hermes Issue Agent] Starting work on Issue #{issue_number} in {owner}/{repo} @ {datetime.now().isoformat()}\n")
        f_main.write(f"Title: {title}\n{'─' * 40}\n")
        
        for line in proc.stdout:
            if line:
                f_private.write(line); f_private.flush()
                f_main.write(line); f_main.flush()
                
    proc.wait()

    send_telegram_message(f"✅ Issue #{issue_number} ({owner}/{repo}) analysis done. Check GitHub for comment.")
    logging.info(f"✅ Hermes done for issue #{issue_number}")
    with open(main_log, "a") as f_main:
        f_main.write(f"\n✅ Hermes analysis finished for Issue #{issue_number}.\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python github_issue_agent.py <issue_number> <owner> <repo>")
        sys.exit(1)
    handle_issue(int(sys.argv[1]), owner=sys.argv[2], repo=sys.argv[3])
