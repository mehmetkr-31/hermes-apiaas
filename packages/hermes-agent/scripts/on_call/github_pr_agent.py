#!/usr/bin/env python3
"""
GitHub PR Agent — thin Hermes wrapper.
Hermes handles everything: reading diff, code review, posting gh pr review.
"""
import os, subprocess, pathlib, logging, time, re
from datetime import datetime
from dotenv import load_dotenv
from run_agent import AIAgent
from reporter import send_telegram_message, request_approval, get_global_config, NOUS_API_BASE_URL, OPENROUTER_BASE_URL

load_dotenv()
AGENT_ROOT  = pathlib.Path(__file__).parent.parent.parent.resolve()
DATA_DIR    = AGENT_ROOT.parent.parent.resolve() / ".tmp"
LOG_DIR     = AGENT_ROOT / "hermes_data" / "on_call_logs"
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

    prompt = f"""Review the following GitHub Pull Request #{pr_number} in {owner}/{repo}:

Title: {title}
Author: {author}

YOUR TASK:
1. Research the changes:
   - ⚡ CRITICAL PEFORMANCE RULE: The repository is ALREADY cloned to your local filesystem at `{repo_path}`.
   - You MUST use fast local terminal commands like `ls -la {repo_path}`, `cat`, `grep`, or file tools to read the code.
   - Do NOT use slow `gh api` or network calls to read files or directory contents unless absolutely necessary.
   - Check the PR diff using terminal commands if needed.
   - Search the codebase at {repo_path} to understand the impact.
2. Formulate a detailed review.
3. Wrap your final review with these exact tags: [ANALYSIS_START] and [ANALYSIS_END].
   (Do NOT use these tags in your earlier reasoning or thoughts).
4. Provide a [VERDICT]: either "approve" or "request-changes" or "comment".

I will present this to the human for approval.
DO NOT use the terminal tool to post the review yourself.

Structure the review block as:
## 🤖 Hermes Review
### Summary
### Findings & Suggestions
### Verdict
"""

    log_file = LOG_DIR / f"pr_{pr_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    main_log = LOG_DIR / "monitoring.jsonl"
    
    def log_step(msg: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        with open(main_log, "a") as f:
            f.write(f"[{timestamp}] 🧩 PR #{pr_number}    | {msg}\n")
        logging.info(f"Steplog: {msg}")

    log_step(f"Cloned repo: {owner}/{repo}")
    log_step("Starting Hermes review...")
    
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
            quiet_mode=True,
            enabled_toolsets=["terminal", "file", "web"],
            ephemeral_system_prompt=(
                "You are an autonomous on-call bot. Your goal is to review Pull Requests and provide structured feedback.\n"
                "STRICT RULES:\n"
                "- NO DIRECT COMMITS TO MAIN/MASTER: You are ABSOLUTELY FORBIDDEN from pushing commits directly to main or master branches.\n"
                "- MANDATORY PULL REQUESTS: All codebase changes MUST be done by creating a new branch, committing your changes, pushing the branch, and then creating a Pull Request (gh pr create).\n"
                "- PULL REQUEST MERGING: If the user explicitly asks you to merge a Pull Request, you may run `gh pr merge <pr_number> --merge --admin` or `gh pr merge <pr_number> --merge`. ONLY do this if they specifically request a merge."
            )
        )
        
        # Execute natively
        result = agent.run_conversation(prompt)
        output_text = result.get("final_response", "")
        
        # Log to private file
        with open(log_file, "w") as f:
            f.write(output_text)

    except Exception as e:
        log_step(f"Hermes FAILED: {e}")
        logging.error(f"PR agent failed: {e}")
        send_telegram_message(f"❌ Hermes analysis failed for PR #{pr_number}: {e}")
        return

    # Log results
    log_step("Analysis complete.")

    # Extract analysis block using robust regex
    analysis = ""
    blocks = re.findall(r'\[ANALYSIS_START\](.*?)\[ANALYSIS_END\]', output_text, re.DOTALL)
    if blocks:
        candidates = []
        for b in blocks:
            cleaned = b.replace('│', '').strip()
            if cleaned: candidates.append(cleaned)
        if candidates:
            analysis = max(candidates, key=len)
    
    # Extract verdict - use rpartition to get the latest one provided by the agent
    verdict = "comment"
    if "[VERDICT]:" in output_text:
        v_line = output_text.rpartition("[VERDICT]:")[2].split("\n")[0].strip().lower()
        if "approve" in v_line: verdict = "approve"
        elif "request-changes" in v_line: verdict = "request-changes"
    
    if not analysis:
        # Fallback: take the last 2000 chars if tags were missed, but clean it
        analysis = output_text.replace('│', '').strip()[-2000:]
        logging.warning("Tags [ANALYSIS_START/END] not found for PR. Using fallback.")
    
    log_step(f"Verdict: {verdict}. Waiting for user approval...")

    # Request Approval
    approval_text = f"Hermes review for PR #{pr_number} is ready.\n\n*Verdict:* `{verdict.upper()}`\n\n*Review Preview:*\n{analysis[:1000]}..."
    approved = request_approval(approval_text, f"pr_{pr_number}_{int(time.time())}")

    if approved:
        log_step("Approved! Posting to GitHub...")
        logging.info("🚀 Approved! Posting PR review to GitHub.")
        try:
            flag = "--approve" if verdict == "approve" else "--request-changes" if verdict == "request-changes" else "--comment"
            process = subprocess.run(
                ["gh", "pr", "review", str(pr_number), "--repo", f"{owner}/{repo}", flag, "--body", analysis],
                capture_output=True, text=True
            )
            if process.returncode == 0:
                send_telegram_message(f"✅ PR review posted to #{pr_number} ({verdict}).")
                log_step("Posted successfully.")
            else:
                log_step(f"Post FAILED: {process.stderr[:100]}")
                send_telegram_message(f"❌ Failed to post PR review: {process.stderr[:200]}")
        except Exception as e:
            logging.error(f"Failed to post PR review: {e}")
            send_telegram_message(f"❌ Failed to post PR review to #{pr_number}: {e}")
            log_step(f"Post FAIL: {e}")
    else:
        log_step("Rejected by user.")
        logging.info("🛑 Rejected by user. Skipping evaluation.")
        send_telegram_message(f"🛑 Review for PR #{pr_number} was rejected by user.")

    logging.info(f"✅ Hermes done for PR #{pr_number}")
    log_step("Mission complete.")


if __name__ == "__main__":
    import sys, time
    if len(sys.argv) < 4:
        print("Usage: python github_pr_agent.py <pr_number> <owner> <repo>")
        sys.exit(1)
    handle_pr(int(sys.argv[1]), owner=sys.argv[2], repo=sys.argv[3])
