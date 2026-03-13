#!/usr/bin/env python3
"""
GitHub Push Agent — thin Hermes wrapper.
Hermes handles everything: analyzing changed files, maybe running tests.
"""
import os, subprocess, pathlib, logging
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from run_agent import AIAgent

from reporter import (
    send_telegram_message, get_project_config, 
    request_approval, ensure_repo_cloned, DATA_DIR,
    get_standardized_model, log_step as central_log_step,
    NOUS_API_BASE_URL, OPENROUTER_BASE_URL
)

load_dotenv()

HERMES_CMD  = os.getenv("HERMES_CMD", "/Users/alikar/.local/bin/hermes")
AGENT_ROOT  = pathlib.Path(__file__).parent.parent.parent.resolve()
WORKING_DIR = AGENT_ROOT.parent.parent.resolve() # Monorepo Root
LOG_DIR     = AGENT_ROOT / "hermes_data" / "on_call_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

def log_step(msg: str, project_slug: str):
    central_log_step(msg, prefix=f"PUSH {project_slug}")

def handle_push(branch: str, pusher: str = "", head_commit_msg: str = "", head_commit_url: str = "", owner: Optional[str] = None, repo: Optional[str] = None, bot_token: Optional[str] = None):
    project_slug = f"{owner}/{repo}" if owner and repo else branch
    logging.info(f"🚀 Dispatching Hermes for Push to {project_slug} ({branch})")

    def local_log_step(msg: str):
        log_step(msg, project_slug)

    # Ensure we are looking at the RIGHT codebase
    repo_path = ensure_repo_cloned(owner, repo) if owner and repo else None

    send_telegram_message(
        f"🚀 *GitHub Push to {branch}* in {project_slug}\n*{head_commit_msg}*\nby {pusher}\n\n🔍 Hermes analyzing changes...", repo_full_name=f"{owner}/{repo}"
    )

    prompt = f"""A new Push has been made to the branch `{branch}` in this repository ({project_slug}).

Pusher: {pusher}
Commit Message: {head_commit_msg}
Diff URL: {head_commit_url}

YOUR TASKS (in order):
1. Use the terminal tool with git to investigate the recent changes if necessary.
   - ⚡ CRITICAL PEFORMANCE RULE: The repository is ALREADY cloned to your local filesystem at `{repo_path}`.
   - You MUST use fast local terminal commands like `ls -la {repo_path}`, `cat`, `grep`, or file tools to read the code.
   - Do NOT use slow `gh api` or network calls to read files or directory contents unless absolutely necessary.
   - ⚠️ IMPORTANT: If you find {repo_path} is empty or missing, do NOT hallucinate code. Use `gh repo view {project_slug}` to investigate.
2. Review the pushed code for linting, build errors, or potential bugs.
3. Send a brief summary of the changes and build/check status to Telegram via the messaging tool or just a simple summary.
"""

    log_file = LOG_DIR / f"push_{branch.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    local_log_step(f"Cloned repo: {project_slug}")
    local_log_step("Starting Hermes push analysis...")

    try:
        # Diagnostic: Check API Keys
        active_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("NOUS_API_KEY")
        
        # Determine base_url and default model
        is_nous = active_key and active_key.startswith("sk-2yd")
        target_base_url = NOUS_API_BASE_URL if is_nous else OPENROUTER_BASE_URL
        fallback_model   = "Hermes-3-Llama-3.1-405B" if is_nous else "anthropic/claude-3-5-sonnet"
        
        # Priority: Project Model > Global Model > Fallback
        repo_full_name = f"{owner}/{repo}" if owner and repo else None
        raw_model = (get_project_config(repo_full_name, "llmModel") if repo_full_name else None) or fallback_model
        target_model = get_standardized_model(raw_model, active_key or "")

        # Initialize Agent
        agent = AIAgent(
            model=target_model,
            api_key=active_key or "",
            base_url=target_base_url,
            quiet_mode=True, # No spinners for background agents
            enabled_toolsets=["terminal", "file", "web"],
        )
        
        # Execute natively
        result = agent.run_conversation(prompt)
        response = str(result.get("final_response", "")) if result and result.get("final_response") else ""
        
        # Log results
        with open(log_file, "w") as f:
            f.write(response)
        
        local_log_step("Analysis complete.")
        send_telegram_message(f"✅ Hermes analysis for Push to {branch} complete.\n\n{response[:1000]}", repo_full_name=f"{owner}/{repo}")

    except Exception as e:
        local_log_step(f"Hermes FAILED: {e}")
        logging.error(f"Push agent failed: {e}")
        send_telegram_message(f"❌ Hermes analysis failed for {branch}: {e}", repo_full_name=f"{owner}/{repo}")

    logging.info(f"✅ Hermes done for Push to {branch}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python github_push_agent.py <branch_name>")
        sys.exit(1)
    handle_push(sys.argv[1])
