#!/usr/bin/env python3
"""
GitHub Issue Agent — thin Hermes wrapper.
Hermes handles everything: gh CLI, web search, code analysis, GitHub comment.
"""
import os, subprocess, pathlib, logging, time, re
from datetime import datetime
from dotenv import load_dotenv
from run_agent import AIAgent
from reporter import send_telegram_message, request_approval, get_global_config, NOUS_API_BASE_URL, OPENROUTER_BASE_URL

load_dotenv()
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
   - ⚠️ IMPORTANT: If you find {repo_path} is empty (only has .git), do NOT hallucinate code. Instead, use your terminal tool (e.g. `gh repo view {owner}/{repo}` or `git remote`) to verify if the repository is actually empty on GitHub or if there was a cloning issue.
   - Use web_search if needed.
2. Formulate a detailed analysis.
3. Wrap your final analysis with these exact tags: [ANALYSIS_START] and [ANALYSIS_END].
   (Do NOT use these tags in your earlier reasoning or thoughts).
   I will present this analysis to the human for approval before posting it.
   DO NOT use the terminal tool to post the comment yourself.

Structure the final analysis block as:
## 🤖 Hermes Analysis
### Root Cause Hypothesis
### Recommended Fix
### References
"""

    log_file = LOG_DIR / f"issue_{issue_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    main_log = LOG_DIR / "monitoring.jsonl"
    
    def log_step(msg: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        with open(main_log, "a") as f:
            f.write(f"[{timestamp}] 🧩 ISSUE #{issue_number} | {msg}\n")
        logging.info(f"Steplog: {msg}")

    log_step(f"Cloned repo: {owner}/{repo}")
    log_step("Starting Hermes analysis...")
    
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
                "You are an autonomous on-call bot. Your goal is to research issues and provide a structured analysis.\n"
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
        logging.error(f"Issue agent failed: {e}")
        send_telegram_message(f"❌ Hermes analysis failed for Issue #{issue_number}: {e}")
        return

    # Log results
    log_step("Analysis complete.")

    # Extract analysis block using robust regex
    analysis = ""
    # Look for tags, allowing for some padding (like box characters | or spaces)
    blocks = re.findall(r'\[ANALYSIS_START\](.*?)\[ANALYSIS_END\]', output_text, re.DOTALL)
    if blocks:
        # Clean candidates from padding characters like '│' and strip
        candidates = []
        for b in blocks:
            cleaned = b.replace('│', '').strip()
            if cleaned: candidates.append(cleaned)
        
        if candidates:
            # Pick the longest block to avoid matching reflected instructions
            analysis = max(candidates, key=len)
    
    if not analysis:
        # Fallback: take the last 2000 chars if tags were missed, but clean it
        analysis = output_text.replace('│', '').strip()[-2000:]
        logging.warning("Tags [ANALYSIS_START/END] not found or empty. Using fallback.")
    
    log_step("Waiting for user approval...")

    # Request Approval
    approval_text = f"Hermes has finished analyzing Issue #{issue_number}.\n\n*Proposed Comment:*\n{analysis[:1000]}..."
    approved = request_approval(approval_text, f"issue_{issue_number}_{int(time.time())}")

    if approved:
        log_step("Approved! Posting to GitHub...")
        logging.info("🚀 Approved! Posting comment to GitHub.")
        try:
            cmd = ["gh", "issue", "comment", str(issue_number), "--repo", f"{owner}/{repo}", "--body", analysis]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            send_telegram_message(f"✅ Comment posted to Issue #{issue_number}.")
            log_step("Posted successfully.")
        except Exception as e:
            logging.error(f"Failed to post comment: {e}")
            send_telegram_message(f"❌ Failed to post comment to Issue #{issue_number}: {e}")
            log_step(f"Post FAILED: {e}")
    else:
        log_step("Rejected by user.")
        logging.info("🛑 Rejected by user. Skipping comment.")
        send_telegram_message(f"🛑 Analysis for Issue #{issue_number} was rejected. No comment posted.")

    logging.info(f"✅ Hermes done for issue #{issue_number}")
    log_step("Mission complete.")


if __name__ == "__main__":
    import sys, time
    if len(sys.argv) < 4:
        print("Usage: python github_issue_agent.py <issue_number> <owner> <repo>")
        sys.exit(1)
    handle_issue(int(sys.argv[1]), owner=sys.argv[2], repo=sys.argv[3])
