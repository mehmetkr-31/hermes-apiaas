#!/usr/bin/env python3
"""
GitHub Action Agent — thin Hermes wrapper.
Hermes handles everything: reading logs, diagnosing, rollback via gh CLI.
"""

import os, subprocess, pathlib, logging, time, re
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from run_agent import AIAgent
from reporter import (
    send_telegram_message,
    get_project_config,
    request_approval,
    ensure_repo_cloned,
    DATA_DIR,
    get_standardized_model,
    log_step as central_log_step,
    NOUS_API_BASE_URL,
    OPENROUTER_BASE_URL,
)
from prompts import CORE_SAFETY_RULES

load_dotenv()
AGENT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
DATA_DIR = AGENT_ROOT.parent.parent.resolve() / ".tmp"
LOG_DIR = AGENT_ROOT / "hermes_data" / "on_call_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


# Removed local ensure_repo_cloned (now in reporter.py)


def handle_failed_action(
    run_id: int,
    workflow_name: str = "",
    branch: str = "",
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    bot_token: Optional[str] = None,
):
    logging.info(
        f"⚙️ Dispatching Hermes for failed Action run #{run_id} in {owner}/{repo}"
    )

    # Ensure we are looking at the RIGHT codebase
    repo_path = ensure_repo_cloned(owner, repo)

    send_telegram_message(
        f"⚙️ *GitHub Action Failed* in {owner}/{repo}\n"
        f"*{workflow_name}* on `{branch}`\n\n🔍 Hermes analyzing...",
        repo_full_name=f"{owner}/{repo}",
    )

    prompt = f"""A GitHub Actions workflow run has FAILED in the repository {owner}/{repo}.

Workflow: {workflow_name}
Branch: {branch}
Run ID: {run_id}
Local Path: {repo_path}

YOUR TASK:
1. Inspect the failure: Use `gh run view {run_id} --log-failed` to see logs.
2. Diagnose the root cause by searching the codebase.
3. Wrap your diagnosis with these exact tags: [DIAGNOSIS_START] and [DIAGNOSIS_END].
   (Do NOT use these tags in your earlier reasoning or thoughts).
   I will present this to the human for approval before rerunning.
   DO NOT use the terminal tool to rerun the jobs yourself.
"""

    log_file = (
        LOG_DIR / f"action_{run_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    def log_step(msg: str):
        central_log_step(msg, prefix=f"ACTION #{run_id}")

    log_step(f"Cloned repo: {owner}/{repo}")
    log_step("Starting Hermes diagnosis...")

    try:
        # Diagnostic: Check API Keys
        active_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("NOUS_API_KEY")

        # Determine base_url and default model
        is_nous = active_key and active_key.startswith("sk-2yd")
        target_base_url = NOUS_API_BASE_URL if is_nous else OPENROUTER_BASE_URL
        fallback_model = (
            "Hermes-3-Llama-3.1-405B" if is_nous else "anthropic/claude-3-5-sonnet"
        )

        # Priority: Project Model > Global Model > Fallback
        repo_full_name = f"{owner}/{repo}"
        project_model = get_project_config(repo_full_name, "llmModel")
        raw_model = project_model or fallback_model

        target_model = get_standardized_model(raw_model, active_key or "")

        # Initialize Agent
        agent = AIAgent(
            model=target_model,
            api_key=active_key or "",
            base_url=target_base_url,
            quiet_mode=True,
            enabled_toolsets=["terminal", "file", "web", "vision"],
            reasoning_config={"enabled": True, "effort": "high"},
            ephemeral_system_prompt=(
                f"You are an autonomous GitHub Action Failure agent.\n{CORE_SAFETY_RULES}"
            ),
        )

        # Execute natively
        result = agent.run_conversation(prompt)
        output_text = (
            str(result.get("final_response", ""))
            if result and result.get("final_response")
            else ""
        )

        # Log to private file
        with open(log_file, "w") as f:
            f.write(output_text)

    except Exception as e:
        log_step(f"Hermes FAILED: {e}")
        logging.error(f"Action agent failed: {e}")
        send_telegram_message(
            f"❌ Hermes analysis failed for Action #{run_id}: {e}",
            repo_full_name=f"{owner}/{repo}",
        )
        return

    # Log results
    log_step("Diagnosis complete.")

    # Extract diagnosis using robust regex
    diagnosis = ""
    blocks = re.findall(
        r"\[DIAGNOSIS_START\](.*?)\[DIAGNOSIS_END\]", output_text, re.DOTALL
    )
    if blocks:
        candidates = []
        for b in blocks:
            cleaned = b.replace("│", "").strip()
            if cleaned:
                candidates.append(cleaned)
        if candidates:
            diagnosis = max(candidates, key=len)

    if not diagnosis:
        # Fallback: take the last 1000 chars if tags were missed, but clean it
        diagnosis_text = (output_text or "").replace("│", "").strip()
        diagnosis = diagnosis_text[-2000:]
        logging.warning(
            "Tags [DIAGNOSIS_START/END] not found for Action failure. Using fallback."
        )

    log_step("Waiting for user approval...")

    # Request Approval
    approval_text = f"Hermes diagnosed a failure in *- {workflow_name} -*\n\n*Diagnosis:*\n{diagnosis[:3800]}...\n\n*Should I rerun the failed jobs?*"
    approved = request_approval(
        approval_text,
        f"action_{run_id}_{int(time.time())}",
        repo_full_name=f"{owner}/{repo}",
    )

    if approved:
        log_step("Approved! Rerunning jobs...")
        logging.info("🚀 Approved! Rerunning failed jobs.")
        result = do_rollback(run_id, owner, repo)
        send_telegram_message(f"🔄 {result}", repo_full_name=f"{owner}/{repo}")
        log_step(f"Result: {result}")
    else:
        log_step("Rejected by user.")
        logging.info("🛑 Rejected by user. Skipping rerun.")
        send_telegram_message(
            f"🛑 Rerun for Action #{run_id} was rejected by user.",
            repo_full_name=f"{owner}/{repo}",
        )

    logging.info(f"✅ Hermes done for Action run #{run_id}")
    log_step("Mission complete.")


def do_rollback(
    run_id: int, owner: Optional[str] = None, repo: Optional[str] = None
) -> str:
    """Triggered by approval or legacy command."""
    try:
        repo_arg = f"{owner}/{repo}" if owner and repo else None
        cmd = ["gh", "run", "rerun", str(run_id), "--failed"]
        if repo_arg:
            cmd.extend(["--repo", repo_arg])

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
