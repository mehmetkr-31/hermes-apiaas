#!/usr/bin/env python3
"""
GitHub PR Agent — thin Hermes wrapper.
Hermes handles everything: reading diff, code review, posting gh pr review.
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


def handle_pr(pr_number: int, title: str = "", author: str = "", owner: str = None, repo: str = None):
    logging.info(f"🔀 Dispatching Hermes for PR #{pr_number} in {owner}/{repo}")

    send_telegram_message(
        f"🔀 *GitHub PR #{pr_number}* at {owner}/{repo}\n*{title}*\nby {author}\n\n🔍 Hermes reviewing..."
    )

    prompt = f"""A new Pull Request #{pr_number} has been opened in the repository {owner}/{repo}.

Title: {title}
Author: {author}

YOUR TASKS (in order):
1. Use the github-pr-workflow and github-code-review skills. First inspect the PR:
   `gh pr view {pr_number} --repo {owner}/{repo}`
   `gh pr diff {pr_number} --repo {owner}/{repo}`
   `gh pr checks {pr_number} --repo {owner}/{repo}`

2. Review the diff carefully:
   - Look for bugs, security issues, missing error handling
   - Scan for TODO/FIXME/HACK comments in the changed lines
   - Check if tests are missing for new functionality
   - Review for breaking changes

3. Search the codebase at {WORKING_DIR} using file tools for related patterns if needed.

4. Post your review directly using the terminal tool:
   - If everything looks good: `gh pr review {pr_number} --repo {owner}/{repo} --approve --body "<your review>"`
   - If changes needed:        `gh pr review {pr_number} --repo {owner}/{repo} --request-changes --body "<your review>"`
   - If just commenting:       `gh pr review {pr_number} --repo {owner}/{repo} --comment --body "<your review>"`
   
   Format the body as:
   ## 🤖 Hermes Code Review
   ### Summary
   ### Issues Found (if any)
   ### TODO/FIXME Items (if any)
   ### Verdict

5. Send a brief summary to Telegram via the messaging tool.

Use `terminal_tool` for all `gh` commands. The `gh` CLI is already authenticated.
"""

    log_file = LOG_DIR / f"pr_{pr_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
        f_main.write(f"\n🔀 [Hermes PR Agent] Reviewing PR #{pr_number} in {owner}/{repo} @ {datetime.now().isoformat()}\n")
        f_main.write(f"Title: {title}\n{'─' * 40}\n")
        
        for line in proc.stdout:
            if line:
                f_private.write(line); f_private.flush()
                f_main.write(line); f_main.flush()
                
    proc.wait()

    send_telegram_message(f"✅ PR #{pr_number} ({owner}/{repo}) review posted. Check GitHub.")
    logging.info(f"✅ Hermes done for PR #{pr_number}")
    with open(main_log, "a") as f_main:
        f_main.write(f"\n✅ Hermes review finished for PR #{pr_number}.\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python github_pr_agent.py <pr_number> <owner> <repo>")
        sys.exit(1)
    handle_pr(int(sys.argv[1]), owner=sys.argv[2], repo=sys.argv[3])
