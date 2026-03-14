#!/usr/bin/env python3
"""
Vercel Agent — Receives Vercel deployment webhooks, reads deployment logs if failed, and reports via Telegram.
"""

import os, pathlib, logging, re
from typing import Optional
from datetime import datetime
from run_agent import AIAgent
from dotenv import load_dotenv
from reporter import (
    send_telegram_message,
    get_project_config,
    ensure_repo_cloned,
    get_standardized_model,
    log_step as central_log_step,
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


def handle_vercel_deployment(
    deployment_id: str,
    deployment_url: str,
    project_name: str,
    status: str,
    owner: str,
    repo: str,
    bot_token: Optional[str] = None,
):
    repo_full_name = f"{owner}/{repo}"
    logging.info(
        f"🚀 Dispatching Hermes for Vercel {status} deployment {deployment_id} in {repo_full_name}"
    )

    if status == "error" or status == "canceled":
        level = "error"
        status_emoji = "❌"
    elif status == "ready":
        level = "success"
        status_emoji = "✅"
    else:
        level = "info"
        status_emoji = "⏳"

    repo_path = ensure_repo_cloned(owner, repo)

    send_telegram_message(
        f"{status_emoji} *Vercel Deployment {status.upper()}*\n"
        f"Project: `{project_name}`\n"
        f"Repo: {repo_full_name}\n"
        f"[View Deployment]({deployment_url})",
        repo_full_name=repo_full_name,
        level=level,
    )

    if status not in ["error", "failed"]:
        logging.info("Deployment was not an error. Analysis skipped.")
        return

    send_telegram_message(
        f"🔍 Hermes is analyzing the Vercel deployment failure for `{project_name}`...",
        repo_full_name=repo_full_name,
        level="incident",
    )

    prompt = f"""A Vercel deployment has FAILED for the repository {repo_full_name}.

Vercel Project: {project_name}
Deployment Status: {status}
Deployment URL: {deployment_url}
Local Codebase Path: {repo_path}

YOUR TASK:
1. Since we don't have direct access to Vercel logs here, review the recent commits (`git log -3 --stat`) or package.json changes.
2. Search for common build errors in the repo (e.g., missing dependencies, TypeScript errors with `npx tsc --noEmit` or ESLint).
3. Attempt to find the root cause of why a build might have failed.
4. Write a concise diagnosis.
5. Wrap your final diagnosis with these exact tags: [DIAGNOSIS_START] and [DIAGNOSIS_END].
"""

    log_file = (
        LOG_DIR
        / f"vercel_{deployment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    def log_step(msg: str):
        central_log_step(msg, prefix=f"VERCEL {deployment_id}")

    log_step(f"Cloned repo: {repo_full_name}")
    log_step("Starting Hermes Vercel diagnosis...")

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
                f"You are an autonomous Vercel build diagnostic agent.\n{CORE_SAFETY_RULES}"
            ),
        )

        result = agent.run_conversation(prompt)
        output_text = str(result.get("final_response", ""))

        with open(log_file, "w") as f:
            f.write(output_text)

    except Exception as e:
        log_step(f"Hermes FAILED: {e}")
        logging.error(f"Vercel agent failed: {e}")
        send_telegram_message(
            f"❌ Hermes analysis failed for Vercel deployment: {e}",
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

    report = f"🔬 *Build Failure Diagnosis for {project_name}*\n\n{diagnosis[:3500]}\n"

    send_telegram_message(report, repo_full_name=repo_full_name, level="success")
    logging.info(f"✅ Hermes done for Vercel {deployment_id}")
    log_step("Mission complete.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 7:
        print(
            "Usage: python vercel_agent.py <dep_id> <url> <project> <status> <owner> <repo>"
        )
        sys.exit(1)
    handle_vercel_deployment(
        sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
    )
