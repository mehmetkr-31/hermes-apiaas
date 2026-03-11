#!/usr/bin/env python3
"""
GitHub Action Agent — thin Hermes wrapper.
Hermes handles everything: reading logs, diagnosing, rollback via gh CLI.
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


def handle_failed_action(run_id: int, workflow_name: str = "", branch: str = "", owner: str = None, repo: str = None):
    logging.info(f"⚙️ Dispatching Hermes for failed Action run #{run_id} in {owner}/{repo}")

    # Ensure we are looking at the RIGHT codebase
    repo_path = ensure_repo_cloned(owner, repo)

    send_telegram_message(
        f"⚙️ *GitHub Action Failed* in {owner}/{repo}\n"
        f"*{workflow_name}* on `{branch}`\n\n🔍 Hermes analyzing..."
    )

    prompt = f"""A GitHub Actions workflow run has FAILED in the repository {owner}/{repo}.

Workflow: {workflow_name}
Branch: {branch}
Run ID: {run_id}

YOUR TASK:
1. Inspect the failure: Use `gh run view {run_id} --log-failed` to see logs.
2. Diagnose the root cause by searching the codebase at {repo_path}.
   - ⚡ CRITICAL PEFORMANCE RULE: The repository is ALREADY cloned to your local filesystem.
   - You MUST use fast local terminal commands like `ls -la {repo_path}`, `cat`, `grep`, or file tools to read the code.
   - Do NOT use slow `gh api` or network calls to read files or directory contents unless absolutely necessary.
3. Wrap your diagnosis with these exact tags: [DIAGNOSIS_START] and [DIAGNOSIS_END].
   (Do NOT use these tags in your earlier reasoning or thoughts).
   I will present this to the human for approval before rerunning.
   DO NOT use the terminal tool to rerun the jobs yourself.
"""

    log_file = LOG_DIR / f"action_{run_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    main_log = LOG_DIR / "monitoring.jsonl"
    
    def log_step(msg: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        with open(main_log, "a") as f:
            f.write(f"[{timestamp}] 🧩 ACTION #{run_id}  | {msg}\n")
        logging.info(f"Steplog: {msg}")

    log_step(f"Cloned repo: {owner}/{repo}")
    log_step("Starting Hermes diagnosis...")
    
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
                "You are an autonomous on-call bot. Your goal is to diagnose failed CI/CD Action runs and propose fixes.\n"
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
        logging.error(f"Action agent failed: {e}")
        send_telegram_message(f"❌ Hermes analysis failed for Action #{run_id}: {e}")
        return

    # Log results
    log_step("Diagnosis complete.")

    # Extract diagnosis using robust regex
    diagnosis = ""
    blocks = re.findall(r'\[DIAGNOSIS_START\](.*?)\[DIAGNOSIS_END\]', output_text, re.DOTALL)
    if blocks:
        candidates = []
        for b in blocks:
            cleaned = b.replace('│', '').strip()
            if cleaned: candidates.append(cleaned)
        if candidates:
            diagnosis = max(candidates, key=len)
    
    if not diagnosis:
        # Fallback: take the last 1000 chars if tags were missed, but clean it
        diagnosis = output_text.replace('│', '').strip()[-1000:]
        logging.warning("Tags [DIAGNOSIS_START/END] not found for Action failure. Using fallback.")
    
    log_step("Waiting for user approval...")

    # Request Approval
    approval_text = f"Hermes diagnosed a failure in *- {workflow_name} -*\n\n*Diagnosis:*\n{diagnosis[:1000]}...\n\n*Should I rerun the failed jobs?*"
    approved = request_approval(approval_text, f"action_{run_id}_{int(time.time())}")

    if approved:
        log_step("Approved! Rerunning jobs...")
        logging.info("🚀 Approved! Rerunning failed jobs.")
        result = do_rollback(run_id, owner, repo)
        send_telegram_message(f"🔄 {result}")
        log_step(f"Result: {result}")
    else:
        log_step("Rejected by user.")
        logging.info("🛑 Rejected by user. Skipping rerun.")
        send_telegram_message(f"🛑 Rerun for Action #{run_id} was rejected by user.")

    logging.info(f"✅ Hermes done for Action run #{run_id}")
    log_step("Mission complete.")


def do_rollback(run_id: int, owner: str = None, repo: str = None) -> str:
    """Triggered by approval or legacy command."""
    try:
        repo_arg = f"{owner}/{repo}" if owner and repo else None
        cmd = ["gh", "run", "rerun", str(run_id), "--failed"]
        if repo_arg: cmd.extend(["--repo", repo_arg])
            
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return f"✅ Rerun triggered for run #{run_id}"
        return f"❌ gh error: {result.stderr.strip()}"
    except Exception as e:
        return f"❌ Rollback failed: {e}"


if __name__ == "__main__":
    import sys, time
    if len(sys.argv) < 4:
        print("Usage: python github_action_agent.py <run_id> <owner> <repo>")
        sys.exit(1)
    handle_failed_action(int(sys.argv[1]), owner=sys.argv[2], repo=sys.argv[3])
