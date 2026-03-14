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
from prompts import ISSUE_EVENT_TEMPLATE, CORE_SAFETY_RULES

LOG_DIR = AGENT_ROOT / "packages" / "agent" / "hermes_data" / "on_call_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


# Removed local ensure_repo_cloned (now in reporter.py)


def handle_issue(
    issue_number: int,
    title: str = "",
    body: str = "",
    owner: Optional[str] = None,
    repo: Optional[str] = None,
    bot_token: Optional[str] = None,
):
    logging.info(f"📋 Dispatching Hermes for Issue #{issue_number} in {owner}/{repo}")

    # Ensure we are looking at the RIGHT codebase
    repo_path = ensure_repo_cloned(owner, repo)

    send_telegram_message(
        f"📋 *GitHub Issue #{issue_number}* at {owner}/{repo}\n*{title}*\n\n🔍 Hermes analyzing...",
        repo_full_name=f"{owner}/{repo}",
    )

    body_snippet = str(body or "")[:2000]
    prompt = (
        ISSUE_EVENT_TEMPLATE.format(
            issue_number=issue_number, repo=f"{owner}/{repo}", title=title
        )
        + f"\n\nDescription:\n{body_snippet}\n\nLocal Path: {repo_path}"
    )

    log_file = (
        LOG_DIR / f"issue_{issue_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    def log_step(msg: str):
        central_log_step(msg, prefix=f"ISSUE #{issue_number}")

    log_step(f"Cloned repo: {owner}/{repo}")
    log_step("Starting Hermes analysis...")

    try:
        # Diagnostic: Check API Keys
        active_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("NOUS_API_KEY")

        # Determine base_url and default model
        is_nous = active_key and active_key.startswith("sk-2yd")
        target_base_url = NOUS_API_BASE_URL if is_nous else OPENROUTER_BASE_URL
        fallback_model = DEFAULT_NOUS_MODEL if is_nous else DEFAULT_MODEL

        # Priority: Project-specific Model > Global Config Model > Fallback
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
                f"You are an autonomous GitHub Issue agent.\n{CORE_SAFETY_RULES}"
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
        logging.error(f"Issue agent failed: {e}")
        send_telegram_message(
            f"❌ Hermes analysis failed for Issue #{issue_number}: {e}",
            repo_full_name=f"{owner}/{repo}",
        )
        return

    # Log results
    log_step("Analysis complete.")

    # Extract analysis block using robust regex
    analysis: str = ""
    # Look for tags, allowing for some padding (like box characters | or spaces)
    blocks = re.findall(
        r"\[ANALYSIS_START\](.*?)\[ANALYSIS_END\]", output_text, re.DOTALL
    )
    if blocks:
        # Clean candidates from padding characters like '│' and strip
        candidates = []
        for b in blocks:
            cleaned = str(b).replace("│", "").strip()
            if cleaned:
                candidates.append(cleaned)

        if candidates:
            # Pick the longest block to avoid matching reflected instructions
            analysis = str(max(candidates, key=len))

    if not analysis:
        # Fallback: take the last 2000 chars if tags were missed, but clean it
        analysis_text = str(output_text or "").replace("│", "").strip()
        analysis = analysis_text[-2000:] if len(analysis_text) > 2000 else analysis_text
        logging.warning("Tags [ANALYSIS_START/END] not found or empty. Using fallback.")

    log_step("Waiting for user approval...")

    # Request Approval
    approval_text = f"Hermes has finished analyzing Issue #{issue_number}.\n\n*Proposed Comment:*\n{analysis[:3800]}..."
    approved = request_approval(
        approval_text,
        f"issue_{issue_number}_{int(time.time())}",
        repo_full_name=f"{owner}/{repo}",
    )

    if approved:
        if not analysis.strip():
            log_step("Approved, but analysis is empty. Skipping GitHub comment.")
            logging.warning(
                "⚠️ Analysis is empty after approval. Skipping gh issue comment."
            )
            send_telegram_message(
                f"ℹ️ Analysis for Issue #{issue_number} was approved but was empty. No comment posted.",
                repo_full_name=f"{owner}/{repo}",
            )
            return

        log_step("Approved! Posting to GitHub...")
        logging.info("🚀 Approved! Posting comment to GitHub.")
        try:
            cmd = [
                "gh",
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                f"{owner}/{repo}",
                "--body",
                analysis,
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            send_telegram_message(
                f"✅ Comment posted to Issue #{issue_number}.",
                repo_full_name=f"{owner}/{repo}",
            )
            log_step("Posted successfully.")
        except Exception as e:
            logging.error(f"Failed to post comment: {e}")
            send_telegram_message(
                f"❌ Failed to post comment to Issue #{issue_number}: {e}",
                repo_full_name=f"{owner}/{repo}",
            )
            log_step(f"Post FAILED: {e}")
    else:
        log_step("Rejected by user.")
        logging.info("🛑 Rejected by user. Skipping comment.")
        send_telegram_message(
            f"🛑 Analysis for Issue #{issue_number} was rejected. No comment posted.",
            repo_full_name=f"{owner}/{repo}",
        )

    logging.info(f"✅ Hermes done for issue #{issue_number}")
    log_step("Mission complete.")


if __name__ == "__main__":
    import sys, time

    if len(sys.argv) < 4:
        print("Usage: python github_issue_agent.py <issue_number> <owner> <repo>")
        sys.exit(1)
    handle_issue(int(sys.argv[1]), owner=sys.argv[2], repo=sys.argv[3])
