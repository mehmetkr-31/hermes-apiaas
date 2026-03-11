#!/usr/bin/env python3
"""
GitHub Action Agent — thin Hermes wrapper.
Hermes handles everything: reading logs, diagnosing, rollback via gh CLI.
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

# Registry for Telegram /rollback command
PENDING_ROLLBACKS: dict[int, str] = {}


def handle_failed_action(run_id: int, workflow_name: str = "", branch: str = "", owner: str = None, repo: str = None):
    logging.info(f"⚙️ Dispatching Hermes for failed Action run #{run_id} in {owner}/{repo}")

    send_telegram_message(
        f"⚙️ *GitHub Action Failed* in {owner}/{repo}\n"
        f"*{workflow_name}* on `{branch}`\n\n"
        f"🔍 Hermes analyzing...\n"
        f"💡 To rollback after: `/rollback {run_id} {owner} {repo}`"
    )

    PENDING_ROLLBACKS[run_id] = {"workflow": workflow_name, "owner": owner, "repo": repo}

    prompt = f"""A GitHub Actions workflow run has FAILED in the repository {owner}/{repo}.

Workflow: {workflow_name}
Branch: {branch}
Run ID: {run_id}

YOUR TASKS (in order):
1. Inspect the failure using terminal tool (gh CLI is authenticated):
   `gh run view {run_id} --repo {owner}/{repo}`
   `gh run view {run_id} --repo {owner}/{repo} --log-failed`

2. Diagnose the root cause:
   - Read the failed job logs carefully
   - Search the codebase at {WORKING_DIR} for the failing code using file tools
   - Use web_search if the error is from an external library or service

3. Send a detailed Telegram report via the messaging tool:
   - What failed and why
   - Suggested fix
   - Whether a rerun is likely to succeed

4. If the fix is clear and low-risk, you MAY attempt a rerun using terminal tool:
   `gh run rerun {run_id} --repo {owner}/{repo} --failed`
   Only do this if you are confident it will succeed.

5. If a code fix is needed, create a GitHub issue documenting the problem:
   `gh issue create --repo {owner}/{repo} --title "Fix: <problem>" --body "<details>"`

Use github-repo-management and github-issues skills as needed.
Use `terminal_tool` for all `gh` commands.
"""

    log_file = LOG_DIR / f"action_{run_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

    with open(log_file, "w", buffering=1) as f:
        for line in proc.stdout:
            f.write(line); f.flush()
    proc.wait()

    logging.info(f"✅ Hermes done for action run #{run_id}")


def do_rollback(run_id: int, owner: str = None, repo: str = None) -> str:
    """Trigger by Telegram /rollback command — just runs gh CLI directly."""
    try:
        repo_arg = f"{owner}/{repo}" if owner and repo else None
        cmd = ["gh", "run", "rerun", str(run_id), "--failed"]
        if repo_arg:
            cmd.extend(["--repo", repo_arg])
            
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return f"✅ Rerun triggered for run #{run_id}"
        return f"❌ gh error: {result.stderr.strip()}"
    except Exception as e:
        return f"❌ Rollback failed: {e}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python github_action_agent.py <run_id> <owner> <repo>")
        sys.exit(1)
    handle_failed_action(int(sys.argv[1]), owner=sys.argv[2], repo=sys.argv[3])
