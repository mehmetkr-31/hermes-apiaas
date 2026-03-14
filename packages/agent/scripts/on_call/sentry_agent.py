#!/usr/bin/env python3
"""
Sentry Agent — Receives Sentry webhooks, investigates the codebase, and reports via Telegram.
"""

import os, pathlib, logging, re
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv # Added load_dotenv import
from run_agent import AIAgent
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


def handle_sentry_issue(
    issue_id: str,
    title: str,
    permalink: str,
    culprit: str,
    project_slug: str,
    owner: str,
    repo: str,
    bot_token: Optional[str] = None,
):
    repo_full_name = f"{owner}/{repo}"
    logging.info(
        f"🚨 Dispatching Hermes for Sentry Issue {issue_id} in {repo_full_name}"
    )

    repo_path = ensure_repo_cloned(owner, repo)

    send_telegram_message(
        f"🚨 *New Sentry Issue* in {repo_full_name}\n"
        f"*{title}*\n"
        f"Culprit: `{culprit}`\n\n"
        f"🔍 Hermes analyzing codebase to find the root cause...",
        repo_full_name=repo_full_name,
        level="incident",
    )

    prompt = f"""A new error has been reported by Sentry in the repository {repo_full_name}.

Sentry Project: {project_slug}
Issue Title: {title}
Culprit (Location): {culprit}
Sentry Link: {permalink}
Local Codebase Path: {repo_path}

YOUR TASK:
1. Search the codebase for the culprit file/function ({culprit}) or related terms from the title.
2. Read the surrounding code to understand why this error might be happening.
3. Write a concise, technical diagnosis of the root cause.
4. Wrap your final diagnosis with these exact tags: [DIAGNOSIS_START] and [DIAGNOSIS_END].
"""

    log_file = (
        LOG_DIR / f"sentry_{issue_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    def log_step(msg: str):
        central_log_step(msg, prefix=f"SENTRY {issue_id}")

    log_step(f"Cloned repo: {repo_full_name}")
    log_step("Starting Hermes Sentry diagnosis...")

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
                f"You are an autonomous Sentry Issue diagnostic agent.\n{CORE_SAFETY_RULES}"
            ),
        )

        result = agent.run_conversation(prompt)
        output_text = str(result.get("final_response", ""))

        with open(log_file, "w") as f:
            f.write(output_text)

    except Exception as e:
        log_step(f"Hermes FAILED: {e}")
        logging.error(f"Sentry agent failed: {e}")
        send_telegram_message(
            f"❌ Hermes analysis failed for Sentry Issue {issue_id}: {e}",
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
        f"🔬 *Sentry Diagnosis for {title}*\n\n"
        f"{diagnosis[:3500]}\n\n"
        f"[View Issue on Sentry]({permalink})"
    )

    send_telegram_message(report, repo_full_name=repo_full_name, level="success")
    logging.info(f"✅ Hermes done for Sentry Issue {issue_id}")
    log_step("Mission complete.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 8:
        print(
            "Usage: python sentry_agent.py <id> <title> <link> <culprit> <slug> <owner> <repo>"
        )
        sys.exit(1)
    handle_sentry_issue(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        sys.argv[5],
        sys.argv[6],
        sys.argv[7],
    )
