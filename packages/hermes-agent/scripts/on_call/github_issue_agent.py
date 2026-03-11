#!/usr/bin/env python3
"""
GitHub Issue Agent — thin Hermes wrapper.
Hermes handles everything: gh CLI, web search, code analysis, GitHub comment.
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


def handle_issue(issue_number: int, title: str = "", body: str = "", owner: str = None, repo: str = None):
    logging.info(f"📋 Dispatching Hermes for Issue #{issue_number} in {owner}/{repo}")

    # Ensure we are looking at the RIGHT codebase
    repo_path = ensure_repo_cloned(owner, repo)

    send_telegram_message(
        f"📋 *GitHub Issue #{issue_number}* at {owner}/{repo}\n*{title}*\n\n🔍 Hermes analyzing..."
    )

    prompt = f"""GitHub Issue #{issue_number} has just been opened in the repository {owner}/{repo}.

Title: {title}
Body:
{body[:2000]}

YOUR TASK:
1. Research the problem:
   - Search the codebase (THIS TARGET PROJECT at {repo_path}) for related code using file tools.
   - Use web_search if needed.
2. Formulate a detailed analysis.
3. OUTPUT YOUR FINAL ANALYSIS between `[ANALYSIS_START]` and `[ANALYSIS_END]` tags.
   I will present this analysis to the human for approval before posting it.
   DO NOT use the terminal tool to post the comment yourself.

Structure the analysis as:
## 🤖 Hermes Analysis
### Root Cause Hypothesis
### Recommended Fix
### References
"""

    log_file = LOG_DIR / f"issue_{issue_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
        start_msg = f"\n📋 [Hermes Issue Agent] Tasking @ {datetime.now().isoformat()} for Issue #{issue_number}\n"
        f_private.write(start_msg); f_main.write(start_msg)
        
        for line in proc.stdout:
            if line:
                full_output.append(line)
                f_private.write(line); f_private.flush()
                f_main.write(line); f_main.flush()
                
    proc.wait()

    # Extract analysis block
    output_text = "".join(full_output)
    analysis = ""
    if "[ANALYSIS_START]" in output_text and "[ANALYSIS_END]" in output_text:
        analysis = output_text.split("[ANALYSIS_START]")[1].split("[ANALYSIS_END]")[0].strip()
    
    if not analysis:
        # Fallback: take the last 2000 chars if tags were missed
        analysis = output_text[-2000:]
        logging.warning("Tags [ANALYSIS_START/END] not found. Using fallback.")

    # Request Approval
    approval_text = f"Hermes has finished analyzing Issue #{issue_number}.\n\n*Proposed Comment:*\n{analysis[:1000]}..."
    approved = request_approval(approval_text, f"issue_{issue_number}_{int(time.time())}")

    if approved:
        logging.info("🚀 Approved! Posting comment to GitHub.")
        try:
            cmd = ["gh", "issue", "comment", str(issue_number), "--repo", f"{owner}/{repo}", "--body", analysis]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            send_telegram_message(f"✅ Comment posted to Issue #{issue_number}.")
        except Exception as e:
            logging.error(f"Failed to post comment: {e}")
            send_telegram_message(f"❌ Failed to post comment to Issue #{issue_number}: {e}")
    else:
        logging.info("🛑 Rejected by user. Skipping comment.")
        send_telegram_message(f"🛑 Analysis for Issue #{issue_number} was rejected. No comment posted.")

    logging.info(f"✅ Hermes done for issue #{issue_number}")


if __name__ == "__main__":
    import sys, time
    if len(sys.argv) < 4:
        print("Usage: python github_issue_agent.py <issue_number> <owner> <repo>")
        sys.exit(1)
    handle_issue(int(sys.argv[1]), owner=sys.argv[2], repo=sys.argv[3])
