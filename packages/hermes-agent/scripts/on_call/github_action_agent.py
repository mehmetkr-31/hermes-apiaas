#!/usr/bin/env python3
"""
GitHub Action Agent — thin Hermes wrapper.
Hermes handles everything: reading logs, diagnosing, rollback via gh CLI.
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
3. OUTPUT YOUR DIAGNOSIS between `[DIAGNOSIS_START]` and `[DIAGNOSIS_END]` tags.
   I will present this to the human for approval before rerunning.
   DO NOT use the terminal tool to rerun the jobs yourself.
"""

    log_file = LOG_DIR / f"action_{run_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
        start_msg = f"\n⚙️ [Hermes Action Agent] Analyzing @ {datetime.now().isoformat()} for Run #{run_id}\n"
        f_private.write(start_msg); f_main.write(start_msg)
        
        for line in proc.stdout:
            if line:
                full_output.append(line)
                f_private.write(line); f_private.flush()
                f_main.write(line); f_main.flush()
                
    proc.wait()

    # Extract diagnosis
    output_text = "".join(full_output)
    diagnosis = ""
    if "[DIAGNOSIS_START]" in output_text and "[DIAGNOSIS_END]" in output_text:
        diagnosis = output_text.split("[DIAGNOSIS_START]")[1].split("[DIAGNOSIS_END]")[0].strip()
    
    if not diagnosis:
        diagnosis = output_text[-1000:]
        logging.warning("Tags [DIAGNOSIS_START/END] not found for Action failure. Using fallback.")

    # Request Approval
    approval_text = f"Hermes diagnosed a failure in *- {workflow_name} -*\n\n*Diagnosis:*\n{diagnosis[:1000]}...\n\n*Should I rerun the failed jobs?*"
    approved = request_approval(approval_text, f"action_{run_id}_{int(time.time())}")

    if approved:
        logging.info("🚀 Approved! Rerunning failed jobs.")
        result = do_rollback(run_id, owner, repo)
        send_telegram_message(f"🔄 {result}")
    else:
        logging.info("🛑 Rejected by user. Skipping rerun.")
        send_telegram_message(f"🛑 Rerun for Action #{run_id} was rejected by user.")

    logging.info(f"✅ Hermes done for Action run #{run_id}")


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
