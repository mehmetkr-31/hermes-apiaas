#!/usr/bin/env python3
"""
Cloudflare Agent — Receives Cloudflare Pages/Workers deployment webhooks and reports via Telegram.
"""

import os, pathlib, logging, re
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from run_agent import AIAgent
from reporter import (
    send_telegram_message,
    get_project_config,
    request_approval,
    ensure_repo_cloned,
    get_standardized_model,
    log_step as central_log_step,
)

AGENT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
_ENV_PATH = AGENT_ROOT / ".env"
load_dotenv(_ENV_PATH)

from reporter import (
    NOUS_API_BASE_URL,
    OPENROUTER_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_NOUS_MODEL,
)
from prompts import CORE_SAFETY_RULES

AGENT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
LOG_DIR = AGENT_ROOT / "hermes_data" / "on_call_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


def handle_cloudflare_deployment(
    project_name: str,
    status: str,
    environment: str,
    owner: str,
    repo: str,
    bot_token: Optional[str] = None,
):
    repo_full_name = f"{owner}/{repo}"
    logging.info(
        f"☁️ Dispatching Hermes for Cloudflare {status} deployment in {repo_full_name}"
    )

    if status == "failure" or status == "failed":
        level = "error"
        status_emoji = "❌"
    elif status == "success" or status == "ready":
        level = "success"
        status_emoji = "✅"
    else:
        level = "info"
        status_emoji = "⏳"

    repo_path = ensure_repo_cloned(owner, repo)

    send_telegram_message(
        f"{status_emoji} *Cloudflare Deployment {status.upper()}*\n"
        f"Project: `{project_name}`\n"
        f"Env: `{environment}`\n"
        f"Repo: {repo_full_name}\n",
        repo_full_name=repo_full_name,
        level=level,
    )

    if status not in ["error", "failure", "failed"]:
        logging.info("Deployment was not an error. Analysis skipped.")
        return

    send_telegram_message(
        f"🔍 Hermes is analyzing the Cloudflare build failure for `{project_name}`...",
        repo_full_name=repo_full_name,
        level="incident",
    )

    prompt = f"""A Cloudflare deployment has FAILED for the repository {repo_full_name}.

Cloudflare Project: {project_name}
Deployment Status: {status}
Environment: {environment}
Local Codebase Path: {repo_path}

YOUR TASK:
1. Search for common build errors in the repo (e.g., missing dependencies, Wrangler/Cloudflare Pages issues).
2. Attempt to find the root cause of why a build might have failed.
3. Write a concise diagnosis.
4. Wrap your final diagnosis with these exact tags: [DIAGNOSIS_START] and [DIAGNOSIS_END].
"""

    log_file = (
        LOG_DIR / f"cf_{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    def log_step(msg: str):
        central_log_step(msg, prefix=f"CLOUDFLARE {project_name}")

    log_step(f"Cloned repo: {repo_full_name}")
    log_step("Starting Hermes Cloudflare diagnosis...")

    try:
        active_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("NOUS_API_KEY")
        is_nous = active_key and active_key.startswith("sk-2yd")
        target_base_url = NOUS_API_BASE_URL if is_nous else OPENROUTER_BASE_URL
        fallback_model = DEFAULT_NOUS_MODEL if is_nous else DEFAULT_MODEL

        project_model = get_project_config(repo_full_name, "llmModel")
        target_model = get_standardized_model(
            project_model or fallback_model, active_key or ""
        )

        agent = AIAgent(
            model=target_model,
            api_key=active_key or "",
            base_url=target_base_url,
            quiet_mode=True,
            enabled_toolsets=["terminal", "file", "web"],
            reasoning_config={"enabled": True, "effort": "high"},
            ephemeral_system_prompt=(
                f"You are an autonomous Cloudflare build diagnostic agent.\n{CORE_SAFETY_RULES}"
            ),
        )

        result = agent.run_conversation(prompt)
        output_text = str(result.get("final_response", ""))

        with open(log_file, "w") as f:
            f.write(output_text)

    except Exception as e:
        log_step(f"Hermes FAILED: {e}")
        logging.error(f"Cloudflare agent failed: {e}")
        send_telegram_message(
            f"❌ Hermes analysis failed for Cloudflare deployment: {e}",
            repo_full_name=repo_full_name,
            level="error",
        )
        return

    log_step("Diagnosis complete.")

    diagnosis = ""
    blocks = re.findall(
        r"\[DIAGNOSIS_START\](.*?)\[DIAGNOSIS_END\]", output_text, re.DOTALL
    )
    if blocks:
        diagnosis = max([b.strip() for b in blocks if b.strip()], key=len, default="")

    if not diagnosis:
        diagnosis = output_text[-2000:].strip()

    report = (
        f"🔬 *Cloudflare Failure Diagnosis for {project_name}*\n\n{diagnosis[:3500]}\n"
    )

    send_telegram_message(report, repo_full_name=repo_full_name, level="success")
    logging.info(f"✅ Hermes done for Cloudflare {project_name}")

    # Proactive Step: Ask to open GitHub Issue
    log_step("Waiting for user approval to open GitHub issue...")
    approval_msg = f"🔬 <b>Cloudflare Failure Diagnosis Ready</b>\n\nShould I open a GitHub issue in <code>{repo_full_name}</code> with this diagnosis?"
    
    import time
    approved = request_approval(
        approval_msg,
        f"cf_issue_{project_name}_{int(time.time())}",
        repo_full_name=repo_full_name
    )

    if approved:
        log_step("Approved! Creating GitHub issue...")
        try:
            import subprocess
            issue_title = f"Cloudflare: Build {status.upper()} in {project_name}"
            issue_body = f"## Cloudflare Build Diagnosis\n\n{diagnosis}\n\nProject: {project_name}\nEnv: {environment}\n\n---\n*Created automatically by Hermes*"
            
            cmd = [
                "gh", "issue", "create",
                "--title", issue_title,
                "--body", issue_body,
                "--repo", repo_full_name
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            new_issue_url = result.stdout.strip()
            
            send_telegram_message(
                f"✅ <b>GitHub Issue Created</b>\n{new_issue_url}",
                repo_full_name=repo_full_name,
                level="success"
            )
            log_step("GitHub issue created successfully.")
        except Exception as e:
            logging.error(f"Failed to create GitHub issue: {e}")
            send_telegram_message(
                f"❌ Failed to create GitHub issue: {e}",
                repo_full_name=repo_full_name,
                level="error"
            )
            log_step(f"Issue creation FAILED: {e}")
    else:
        log_step("Issue creation skipped by user.")

    log_step("Mission complete.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 6:
        print(
            "Usage: python cloudflare_agent.py <project> <status> <env> <owner> <repo>"
        )
        sys.exit(1)
    handle_cloudflare_deployment(
        sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
    )
