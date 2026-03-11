#!/usr/bin/env python3
"""
GitHub PR Agent — thin Hermes wrapper.
Hermes handles everything: reading diff, code review, posting gh pr review.
"""
import os, subprocess, pathlib, logging, time
from datetime import datetime
from dotenv import load_dotenv
from reporter import send_telegram_message, request_approval

load_dotenv()

HERMES_CMD  = os.getenv("HERMES_CMD", "/Users/alikar/.local/bin/hermes")
AGENT_ROOT  = pathlib.Path(__file__).parent.parent.parent.resolve()
DATA_DIR    = AGENT_ROOT.parent.parent.resolve() / ".tmp"
LOG_DIR     = AGENT_ROOT / "agent" / "on_call_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def ensure_repo_cloned(owner: str, repo: str) -> pathlib.Path:
    """Clone or pull the target repository into .tmp/owner/repo"""
    repo_dir = DATA_DIR / owner / repo
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    
    if not repo_dir.exists():
        logging.info(f"🚚 Cloning {owner}/{repo} into {repo_dir}")
        subprocess.run(["git", "clone", f"https://github.com/{owner}/{repo}.git", str(repo_dir)], check=True)
    else:
        logging.info(f"🔄 Updating {owner}/{repo} in {repo_dir}")
        subprocess.run(["git", "-C", str(repo_dir), "pull"], check=True)
    return repo_dir


def handle_pr(pr_number: int, title: str = "", author: str = "", owner: str = None, repo: str = None):
    logging.info(f"🔀 Dispatching Hermes for PR #{pr_number} in {owner}/{repo}")

    # Ensure we are looking at the RIGHT codebase
    repo_path = ensure_repo_cloned(owner, repo)

    send_telegram_message(
        f"🔀 *GitHub PR #{pr_number}* at {owner}/{repo}\n*{title}*\nby {author}\n\n🔍 Hermes reviewing..."
    )

    prompt = f"""A new Pull Request #{pr_number} has been opened in the repository {owner}/{repo}.

Title: {title}
Author: {author}

YOUR TASK:
1. Review the PR:
   - Use `gh pr view {pr_number}` and `gh pr diff {pr_number}` to inspect changes.
   - Look for bugs, security issues, or missing tests.
   - Inspect the local codebase at {repo_path} using file tools.
2. Formulate your review.
3. OUTPUT YOUR PROPOSED REVIEW in this format:
   [VERDICT]: <approve|comment|request-changes>
   [ANALYSIS_START]
   <markdown review body>
   [ANALYSIS_END]

I will present this to the human for approval. DO NOT use the terminal tool to post the review yourself.
"""

    log_file = LOG_DIR / f"pr_{pr_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    main_log = LOG_DIR / "monitoring.jsonl"
    
    full_output = []
    # Set WORKING_DIR to the TARGET repository, not the Hermes project
    proc = subprocess.Popen(
        [HERMES_CMD, "chat", "--model", "Hermes-4-405B", "-q", prompt, "--toolsets", "terminal,file,web"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE, text=True,
        env=os.environ.copy(), bufsize=1, cwd=str(repo_path),
    )
    try:
        proc.stdin.write("s\n" * 10)
        proc.stdin.flush()
    except Exception:
        pass

    with open(log_file, "w", buffering=1) as f_private, open(main_log, "a", buffering=1) as f_main:
        start_msg = f"\n🔀 [Hermes PR Agent] Reviewing @ {datetime.now().isoformat()} for PR #{pr_number}\n"
        f_private.write(start_msg); f_main.write(start_msg)
        
        for line in proc.stdout:
            if line:
                full_output.append(line)
                f_private.write(line); f_private.flush()
                f_main.write(line); f_main.flush()
                
    proc.wait()

    # Extract analysis and verdict
    output_text = "".join(full_output)
    analysis = ""
    verdict = "comment"

    if "[ANALYSIS_START]" in output_text and "[ANALYSIS_END]" in output_text:
        analysis = output_text.split("[ANALYSIS_START]")[1].split("[ANALYSIS_END]")[0].strip()
    
    if "[VERDICT]:" in output_text:
        v_line = output_text.split("[VERDICT]:")[1].split("\n")[0].strip().lower()
        if "approve" in v_line: verdict = "approve"
        elif "request-changes" in v_line: verdict = "request-changes"
    
    if not analysis:
        analysis = output_text[-2000:]
        logging.warning("Tags [ANALYSIS_START/END] not found for PR. Using fallback.")

    # Request Approval
    approval_text = f"Hermes review for PR #{pr_number} is ready.\n\n*Verdict:* `{verdict.upper()}`\n\n*Review Preview:*\n{analysis[:1000]}..."
    approved = request_approval(approval_text, f"pr_{pr_number}_{int(time.time())}")

    if approved:
        logging.info("🚀 Approved! Posting PR review to GitHub.")
        try:
            flag = "--approve" if verdict == "approve" else "--request-changes" if verdict == "request-changes" else "--comment"
            cmd = ["gh", "pr", "review", str(pr_number), "--repo", f"{owner}/{repo}", flag, "--body", analysis]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            send_telegram_message(f"✅ PR review posted to #{pr_number} ({verdict}).")
        except Exception as e:
            logging.error(f"Failed to post PR review: {e}")
            send_telegram_message(f"❌ Failed to post PR review to #{pr_number}: {e}")
    else:
        logging.info("🛑 Rejected by user. Skipping evaluation.")
        send_telegram_message(f"🛑 Review for PR #{pr_number} was rejected by user.")

    logging.info(f"✅ Hermes done for PR #{pr_number}")


if __name__ == "__main__":
    import sys, time
    if len(sys.argv) < 4:
        print("Usage: python github_pr_agent.py <pr_number> <owner> <repo>")
        sys.exit(1)
    handle_pr(int(sys.argv[1]), owner=sys.argv[2], repo=sys.argv[3])
