#!/usr/bin/env python3
import os, subprocess, pathlib, logging, time, re, json
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Environment Setup
AGENT_ROOT = pathlib.Path(__file__).parent.parent.parent.parent.resolve()
_ENV_PATH = AGENT_ROOT / ".env"
load_dotenv(_ENV_PATH)

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
    DEFAULT_MODEL,
    DEFAULT_NOUS_MODEL,
)
from prompts import CORE_SAFETY_RULES

LOG_DIR = AGENT_ROOT / "packages" / "agent" / "hermes_data" / "on_call_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


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
        fallback_model = DEFAULT_NOUS_MODEL if is_nous else DEFAULT_MODEL

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

    # Find last successful run for rollback option
    last_success_id = None
    try:
        repo_full = f"{owner}/{repo}"
        # Get the workflow ID or name for the current run to filter by the SAME workflow
        workflow_res = subprocess.run(
            [
                "gh",
                "run",
                "view",
                str(run_id),
                "--repo",
                repo_full,
                "--json",
                "workflowDatabaseId",
            ],
            capture_output=True,
            text=True,
        )

        wf_data = json.loads(workflow_res.stdout)
        wf_id = wf_data.get("workflowDatabaseId")

        if wf_id:
            success_res = subprocess.run(
                [
                    "gh",
                    "run",
                    "list",
                    "--repo",
                    repo_full,
                    "--workflow",
                    str(wf_id),
                    "--status",
                    "success",
                    "--limit",
                    "1",
                    "--json",
                    "databaseId",
                ],
                capture_output=True,
                text=True,
            )
            success_data = json.loads(success_res.stdout)
            if success_data:
                last_success_id = success_data[0].get("databaseId")
    except Exception as e:
        logging.warning(f"Could not fetch last successful run: {e}")

    # Request Approval
    approval_text = f"Hermes diagnosed a failure in *- {workflow_name} -*\n\n*Diagnosis:*\n{diagnosis[:3500]}...\n\n"
    if last_success_id:
        approval_text += f"💡 *Rollback Option:* I found a previous successful run (#<code>{last_success_id}</code>). You can rollback to it or retry the current failed jobs."
    else:
        approval_text += "*Should I rerun the failed jobs?*"

    status = request_approval(
        approval_text,
        f"action_{run_id}_{int(time.time())}",
        repo_full_name=f"{owner}/{repo}",
        allow_rollback=bool(last_success_id),
    )

    if status == "approved":
        log_step("Approved! Rerunning jobs...")
        logging.info("🚀 Approved! Rerunning failed jobs.")
        res = do_retry(run_id, owner, repo)
        send_telegram_message(f"🔄 {res}", repo_full_name=f"{owner}/{repo}")
        log_step(f"Result: {res}")
    elif status == "rollback":
        if last_success_id is not None:
            log_step(f"Rollback requested to run #{last_success_id}")
            logging.info(f"🚀 Rollback triggered to run #{last_success_id}")
            res = do_rollback(int(last_success_id), owner, repo)
            send_telegram_message(f"⏪ {res}", repo_full_name=f"{owner}/{repo}")
            log_step(f"Result: {res}")
        else:
            log_step("Rollback requested but no successful run found.")
            send_telegram_message(
                "❌ Rollback failed: No previous successful run found.",
                repo_full_name=f"{owner}/{repo}",
            )
    else:
        log_step("Rejected by user.")
        logging.info("🛑 Rejected by user. Skipping action.")
        send_telegram_message(
            f"🛑 Action for run #{run_id} was rejected by user.",
            repo_full_name=f"{owner}/{repo}",
        )

    logging.info(f"✅ Hermes done for Action run #{run_id}")
    log_step("Mission complete.")


def do_retry(
    run_id: int, owner: Optional[str] = None, repo: Optional[str] = None
) -> str:
    """Reruns failed jobs of the current run."""
    try:
        repo_arg = f"{owner}/{repo}" if owner and repo else None
        cmd = ["gh", "run", "rerun", str(run_id), "--failed"]
        if repo_arg:
            cmd.extend(["--repo", repo_arg])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return f"Retry triggered for failed jobs in run #{run_id}"
        return f"❌ gh error: {result.stderr.strip()}"
    except Exception as e:
        return f"❌ Retry failed: {e}"


def do_rollback(
    success_run_id: int, owner: Optional[str] = None, repo: Optional[str] = None
) -> str:
    """Reruns all jobs of a PREVIOUS successful run to effectively 'rollback' deployment."""
    try:
        repo_arg = f"{owner}/{repo}" if owner and repo else None
        # Rerunning a successful run will rerun all its jobs
        cmd = ["gh", "run", "rerun", str(success_run_id)]
        if repo_arg:
            cmd.extend(["--repo", repo_arg])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return f"Rollback triggered: Rerunning successful run #{success_run_id}"
        return f"❌ gh error: {result.stderr.strip()}"
    except Exception as e:
        return f"❌ Rollback failed: {e}"


if __name__ == "__main__":
    import sys, time

    if len(sys.argv) < 4:
        print("Usage: python github_action_agent.py <run_id> <owner> <repo>")
        sys.exit(1)
    handle_failed_action(int(sys.argv[1]), owner=sys.argv[2], repo=sys.argv[3])
