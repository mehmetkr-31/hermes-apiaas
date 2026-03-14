#!/usr/bin/env python3
import os, subprocess, pathlib, logging, time, re
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
from prompts import PR_EVENT_TEMPLATE, CORE_SAFETY_RULES

LOG_DIR = AGENT_ROOT / "packages" / "agent" / "hermes_data" / "on_call_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


# Removed local ensure_repo_cloned (now in reporter.py)


def handle_pr(
    pr_number: int,
    title: str = "",
    author: str = "",
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    bot_token: Optional[str] = None,
):
    logging.info(f"🔀 Dispatching Hermes for PR #{pr_number} in {owner}/{repo}")

    # Ensure we are looking at the RIGHT codebase
    repo_path = ensure_repo_cloned(owner, repo)

    send_telegram_message(
        f"🔀 *GitHub PR #{pr_number}* at {owner}/{repo}\n*{title}*\nby {author}\n\n🔍 Hermes reviewing...",
        repo_full_name=f"{owner}/{repo}",
    )

    prompt = (
        PR_EVENT_TEMPLATE.format(
            pr_number=pr_number, repo=f"{owner}/{repo}", title=title
        )
        + f"\n\nAuthor: {author}\nLocal Path: {repo_path}"
    )

    log_file = (
        LOG_DIR / f"pr_{pr_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    def log_step(msg: str):
        central_log_step(msg, prefix=f"PR #{pr_number}")

    log_step(f"Cloned repo: {owner}/{repo}")
    log_step("Starting Hermes review...")

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
                f"You are an autonomous GitHub PR Review agent.\n{CORE_SAFETY_RULES}"
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
        logging.error(f"PR agent failed: {e}")
        send_telegram_message(
            f"❌ Hermes analysis failed for PR #{pr_number}: {e}",
            repo_full_name=f"{owner}/{repo}",
        )
        return

    # Log results
    log_step("Analysis complete.")

    # Extract analysis block using robust regex
    analysis: str = ""
    blocks = re.findall(
        r"\[ANALYSIS_START\](.*?)\[ANALYSIS_END\]", output_text, re.DOTALL
    )
    if blocks:
        candidates = []
        for b in blocks:
            cleaned = str(b).replace("│", "").strip()
            if cleaned:
                candidates.append(cleaned)
        if candidates:
            analysis = str(max(candidates, key=len))

    # Extract verdict - use rpartition to get the latest one provided by the agent
    verdict = "comment"
    if "[VERDICT]:" in output_text:
        v_line = output_text.rpartition("[VERDICT]:")[2].split("\n")[0].strip().lower()
        if "approve" in v_line:
            verdict = "approve"
        elif "request-changes" in v_line:
            verdict = "request-changes"

    if not analysis:
        # Fallback: take the last 2000 chars if tags were missed, but clean it
        analysis_text = str(output_text or "").replace("│", "").strip()
        analysis = analysis_text[-2000:] if len(analysis_text) > 2000 else analysis_text
        logging.warning("Tags [ANALYSIS_START/END] not found for PR. Using fallback.")

    log_step(f"Verdict: {verdict}. Waiting for user approval...")

    # Request Approval
    approval_text = f"Hermes review for PR #{pr_number} is ready.\n\n*Verdict:* `{verdict.upper()}`\n\n*Review Preview:*\n{analysis[:3800]}..."
    approved = request_approval(
        approval_text,
        f"pr_{pr_number}_{int(time.time())}",
        repo_full_name=f"{owner}/{repo}",
    )

    if approved:
        if not analysis.strip():
            log_step("Approved, but review is empty. Skipping GitHub post.")
            logging.warning("⚠️ Review is empty after approval. Skipping gh pr review.")
            send_telegram_message(
                f"ℹ️ Review for PR #{pr_number} was approved but was empty. No review posted.",
                repo_full_name=f"{owner}/{repo}",
            )
            return

        log_step("Approved! Posting to GitHub...")
        logging.info("🚀 Approved! Posting PR review to GitHub.")
        try:
            flag = (
                "--approve"
                if verdict == "approve"
                else "--request-changes"
                if verdict == "request-changes"
                else "--comment"
            )
            process = subprocess.run(
                [
                    "gh",
                    "pr",
                    "review",
                    str(pr_number),
                    "--repo",
                    f"{owner}/{repo}",
                    flag,
                    "--body",
                    analysis,
                ],
                capture_output=True,
                text=True,
            )
            if process.returncode == 0:
                send_telegram_message(
                    f"✅ PR review posted to #{pr_number} ({verdict}).",
                    repo_full_name=f"{owner}/{repo}",
                )
                log_step("Posted successfully.")
            else:
                log_step(f"Post FAILED: {process.stderr[:100]}")
                send_telegram_message(
                    f"❌ Failed to post PR review: {process.stderr[:200]}",
                    repo_full_name=f"{owner}/{repo}",
                )
        except Exception as e:
            logging.error(f"Failed to post PR review: {e}")
            send_telegram_message(
                f"❌ Failed to post PR review to #{pr_number}: {e}",
                repo_full_name=f"{owner}/{repo}",
            )
            log_step(f"Post FAIL: {e}")
    else:
        log_step("Rejected by user.")
        logging.info("🛑 Rejected by user. Skipping evaluation.")
        send_telegram_message(
            f"🛑 Review for PR #{pr_number} was rejected by user.",
            repo_full_name=f"{owner}/{repo}",
        )

    logging.info(f"✅ Hermes done for PR #{pr_number}")
    log_step("Mission complete.")


if __name__ == "__main__":
    import sys, time

    if len(sys.argv) < 4:
        print("Usage: python github_pr_agent.py <pr_number> <owner> <repo>")
        sys.exit(1)
    handle_pr(int(sys.argv[1]), owner=sys.argv[2], repo=sys.argv[3])
