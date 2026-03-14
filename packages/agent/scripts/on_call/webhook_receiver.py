#!/usr/bin/env python3
"""
Hermes Webhook Receiver — GitHub events listener.

Endpoints:
  POST /github/webhook   → GitHub events (Issues, PRs, Workflow runs)
  GET  /logs             → stream logs
  GET  /health           → healthcheck

GitHub events handled:
  issues         (action: opened)           → github_issue_agent
  pull_request   (action: opened / sync)    → github_pr_agent
  workflow_run   (action: completed, conclusion: failure) → github_action_agent
"""

import os
import hmac
import hashlib
import logging
import pathlib
import sqlite3
import sys, json
import traceback
from dotenv import load_dotenv
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from typing import Optional
import uvicorn

# Ensure agent scripts can be imported BEFORE anything else from this directory
script_dir = pathlib.Path(__file__).parent.resolve()
parent_dir = script_dir.parent.resolve()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from run_agent import AIAgent
from encryption_utils import decrypt
from reporter import (
    sessions,
    send_telegram_message,
    get_project_config,
    ensure_repo_cloned,
    DATA_DIR,
    get_standardized_model,
    NOUS_API_BASE_URL,
    OPENROUTER_BASE_URL,
    request_approval,
    DB_FILE,
    WORKING_DIR,
    PROJECT_ROOT,
    LOG_FILE_PATH as MAIN_LOG_FILE,
)
from prompts import get_commander_system_prompt, CORE_SAFETY_RULES

# ── Environment Setup ────────────────────────
AGENT_ROOT = pathlib.Path(__file__).parent.parent.parent.parent.resolve()
_ENV_PATH = AGENT_ROOT / ".env"
load_dotenv(_ENV_PATH)

# ── Logging Setup ────────────────────────────
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
# Silence noisy library logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

HERMES_CMD = os.getenv("HERMES_CMD", "hermes")

# Common paths and config logic now imported from reporter.py
# Ensure directories exist
LOG_DIR = WORKING_DIR / "hermes_data" / "on_call_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.info(f"📁 Webhook Receiver - Project Root: {PROJECT_ROOT}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the Telegram bot thread when the server starts and cleanup on shutdown."""
    try:
        from reporter import start_bot_thread

        start_bot_thread()
        logging.info("🤖 Telegram bot thread started.")
        yield
    except Exception as e:
        logging.error(f"❌ Lifespan error: {e}")
        yield


app = FastAPI(title="Hermes Webhook Receiver", lifespan=lifespan)


# ── Signature verification ─────────────────────────────────────────────────────


def _get_webhook_secret_for_repo(repo_full_name: str) -> str:
    """Fetch the webhook secret for a specific repo from the database."""
    try:
        if DB_FILE.exists():
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT webhook_secret FROM hermes_project WHERE repo_full_name = ?",
                    (repo_full_name,),
                )
                row = cur.fetchone()
                if row:
                    logging.info(f"🔑 Secret found for {repo_full_name} in DB.")
                    return decrypt(row[0])
        logging.warning(f"⚠️ No secret found for {repo_full_name} in DB.")
    except Exception as e:
        logging.error(
            f"Failed to read webhook_secret from DB for {repo_full_name}: {e}"
        )
    return ""


def _get_bot_token_for_repo(repo_full_name: str) -> Optional[str]:
    """Fetch and decrypt the project-specific bot token if it exists."""
    try:
        if DB_FILE.exists():
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT telegram_bot_token FROM hermes_project WHERE repo_full_name = ?",
                    (repo_full_name,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    logging.info(f"🤖 Bot token found for {repo_full_name} in DB.")
                    return decrypt(row[0])
    except Exception as e:
        logging.error(
            f"Failed to read telegram_bot_token from DB for {repo_full_name}: {e}"
        )
    return None


def _verify_github_signature(body: bytes, sig_header: str, payload: dict) -> bool:
    """HMAC-SHA256 verification for GitHub webhooks."""
    repo_full_name = payload.get("repository", {}).get("full_name")
    if not repo_full_name:
        logging.warning(
            "No repository found in webhook payload — skipping signature check!"
        )
        return True  # Or False if we want to be strict

    secret = _get_webhook_secret_for_repo(repo_full_name)

    if not secret:
        logging.warning(
            f"Webhook secret not found for {repo_full_name} in DB — skipping signature check!"
        )
        return True

    if not sig_header or not sig_header.startswith("sha256="):
        logging.warning("❌ Missing or invalid X-Hub-Signature-256 header.")
        return False

    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    match = hmac.compare_digest(expected, sig_header)
    if not match:
        logging.error(f"❌ Signature MISMATCH for {repo_full_name}!")
        logging.debug(f"Expected: {expected}")
        logging.debug(f"Received: {sig_header}")
    else:
        logging.info(f"✅ Signature verified for {repo_full_name}")

    return match


# ── GitHub event handlers ──────────────────────────────────────────────────────


def _handle_github_issue(
    payload: dict, owner: Optional[str] = None, repo: Optional[str] = None
):
    issue = payload.get("issue", {})
    number = issue.get("number")
    if not number:
        return
    title = issue.get("title", "")
    body = issue.get("body", "") or ""
    logging.info(
        f"📋 GitHub Issue #{number} opened in {owner}/{repo} — dispatching Issue Agent"
    )
    _log_github_event("issue", number, payload)

    bot_token = _get_bot_token_for_repo(f"{owner}/{repo}")

    try:
        from github_issue_agent import handle_issue

        handle_issue(
            number, title=title, body=body, owner=owner, repo=repo, bot_token=bot_token
        )
    except Exception as e:
        logging.error(f"Issue agent failed: {e}\n{traceback.format_exc()}")


def _handle_github_pr(
    payload: dict, owner: Optional[str] = None, repo: Optional[str] = None
):
    pr = payload.get("pull_request", {})
    number = pr.get("number")
    if not number:
        return
    title = pr.get("title", "")
    author = pr.get("user", {}).get("login", "")
    logging.info(f"🔀 GitHub PR #{number} in {owner}/{repo} — dispatching PR Agent")
    _log_github_event("pr", number, payload)

    bot_token = _get_bot_token_for_repo(f"{owner}/{repo}")

    try:
        from github_pr_agent import handle_pr

        handle_pr(
            number,
            title=title,
            author=author,
            owner=owner,
            repo=repo,
            bot_token=bot_token,
        )
    except Exception as e:
        logging.error(f"PR agent failed: {e}\n{traceback.format_exc()}")


def _handle_github_action(
    payload: dict, owner: Optional[str] = None, repo: Optional[str] = None
):
    run = payload.get("workflow_run", {})
    run_id = run.get("id")
    conclusion = run.get("conclusion")
    if not run_id or conclusion != "failure":
        return
    workflow_name = run.get("name", "Workflow")
    branch = run.get("head_branch", "?")
    logging.info(
        f"⚙️ GitHub Action run #{run_id} failed in {owner}/{repo} — dispatching Action Agent"
    )
    _log_github_event("action", run_id, payload)

    bot_token = _get_bot_token_for_repo(f"{owner}/{repo}")

    try:
        from github_action_agent import handle_failed_action

        handle_failed_action(
            run_id,
            workflow_name=workflow_name,
            branch=branch,
            owner=owner,
            repo=repo,
            bot_token=bot_token,
        )
    except Exception as e:
        logging.error(f"Action agent failed: {e}\n{traceback.format_exc()}")


def _log_github_event(event_type: str, number: int, payload: dict):
    """Append a structured log line for the dashboard to display."""
    action = payload.get("action", "")
    title = (
        payload.get("issue", {}).get("title")
        or payload.get("pull_request", {}).get("title")
        or payload.get("workflow_run", {}).get("name")
        or payload.get("push", {}).get("title")
        or "?"
    )
    html_url = (
        payload.get("issue", {}).get("html_url")
        or payload.get("pull_request", {}).get("html_url")
        or payload.get("workflow_run", {}).get("html_url")
        or ""
    )

    timestamp = datetime.now().strftime("%H:%M:%S")
    icon = "📋" if event_type == "issue" else "🔀" if event_type == "pr" else "🚀"

    # Simple, high-contrast log line for the dashboard
    line = f"[{timestamp}] {icon} {event_type.upper():<8} | {action:<12} | {title}\n"

    with open(MAIN_LOG_FILE, "a") as f:
        f.write(line)


# ── Routes ─────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/github/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """GitHub webhook receiver with HMAC validation."""
    body = await request.body()
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    event_type = request.headers.get("X-GitHub-Event", "")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if not _verify_github_signature(body, sig_header, payload):
        raise HTTPException(status_code=401, detail="Invalid signature")

    action = payload.get("action", "")
    logging.info(f"📥 GitHub event: {event_type} / action: {action}")

    # Route to the correct agent
    repo_info = payload.get("repository", {})
    full_name = repo_info.get("full_name", "")

    if "/" in full_name:
        owner, repo_name = full_name.split("/", 1)
    else:
        owner = repo_info.get("owner", {}).get("login")
        repo_name = repo_info.get("name")

    logging.info(
        f"📍 Extracted Repository: {owner}/{repo_name} (from full_name: {full_name})"
    )

    if event_type == "issues" and action == "opened":
        background_tasks.add_task(_handle_github_issue, payload, owner, repo_name)

    elif event_type == "pull_request" and action in ("opened", "synchronize"):
        background_tasks.add_task(_handle_github_pr, payload, owner, repo_name)

    elif event_type == "workflow_run" and action == "completed":
        background_tasks.add_task(_handle_github_action, payload, owner, repo_name)

    elif event_type == "push":
        branch = payload.get("ref", "").replace("refs/heads/", "")
        pusher = payload.get("pusher", {}).get("name", "Someone")

        commits = payload.get("commits", [])
        if commits:
            head_commit = commits[-1]
            head_commit_msg = head_commit.get("message", "No commit message")
            head_commit_url = head_commit.get("url", "")
        else:
            head_commit = payload.get("head_commit") or {}
            head_commit_msg = head_commit.get("message", "No commit message")
            head_commit_url = head_commit.get("url", "")

        title = f"Push to {branch}: {head_commit_msg}"

        logging.info(
            f"🚀 Detected {event_type} event to branch {branch} in {owner}/{repo_name}. Dispatching Push Agent."
        )

        # Override payload temporarily just for the logger so it looks nice
        payload_for_logger = {"push": {"title": title, "html_url": head_commit_url}}
        _log_github_event(event_type, 0, payload_for_logger)

        bot_token = _get_bot_token_for_repo(f"{owner}/{repo_name}")

        try:
            from github_push_agent import handle_push

            background_tasks.add_task(
                handle_push,
                branch,
                pusher,
                head_commit_msg,
                head_commit_url,
                owner,
                repo_name,
                bot_token=bot_token,
            )
        except Exception as e:
            logging.error(f"Push agent failed: {e}\n{traceback.format_exc()}")

    elif event_type == "create":
        ref_type = payload.get("ref_type")
        ref = payload.get("ref")
        msg = f"New {ref_type} created: {ref}"
        logging.info(f"🚀 {msg}")
        _log_github_event(event_type, 0, {"push": {"title": msg, "html_url": ""}})

    elif event_type == "delete":
        ref_type = payload.get("ref_type")
        ref = payload.get("ref")
        msg = f"{ref_type.capitalize()} deleted: {ref}"
        logging.info(f"🗑️ {msg}")
        _log_github_event(event_type, 0, {"push": {"title": msg, "html_url": ""}})

    else:
        logging.info(f"ℹ️ Unhandled GitHub event: {event_type}/{action} — ignoring.")

    return {"status": "accepted", "event": event_type, "action": action}


@app.post("/sentry/webhook/{owner}/{repo_name}")
async def sentry_webhook(
    owner: str, repo_name: str, request: Request, background_tasks: BackgroundTasks
):
    """Sentry webhook receiver."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    action = payload.get("action", "")
    logging.info(f"📥 Sentry event received: {action} for {owner}/{repo_name}")

    # We only care about newly created issues for now
    if action == "created":
        data = payload.get("data", {}).get("issue", {})
        issue_id = str(data.get("id", ""))
        title = data.get("title", "Unknown Sentry Issue")
        permalink = data.get("permalink", "")
        culprit = data.get("culprit", "")
        project_slug = data.get("project", {}).get("slug", "")

        bot_token = _get_bot_token_for_repo(f"{owner}/{repo_name}")

        try:
            from sentry_agent import handle_sentry_issue

            background_tasks.add_task(
                handle_sentry_issue,
                issue_id,
                title,
                permalink,
                culprit,
                project_slug,
                owner,
                repo_name,
                bot_token=bot_token,
            )
        except Exception as e:
            logging.error(
                f"Failed to dispatch Sentry agent: {e}\n{traceback.format_exc()}"
            )

    return {"status": "accepted"}


@app.post("/vercel/webhook/{owner}/{repo_name}")
async def vercel_webhook(
    owner: str, repo_name: str, request: Request, background_tasks: BackgroundTasks
):
    """Vercel webhook receiver."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Vercel sends different payload formats depending on hook type,
    # but normally has type, payload.deployment...
    event_type = payload.get("type", "")
    data = payload.get("payload", {})

    deployment = data.get("deployment", {})
    project = data.get("project", {})

    dep_id = deployment.get("id", "")
    url = deployment.get("url", "")
    status = ""

    if "error" in event_type or "failed" in event_type:
        status = "error"
    elif "succeeded" in event_type or "ready" in event_type:
        status = "ready"
    elif "created" in event_type:
        status = "building"
    else:
        status = event_type

    project_name = project.get("name", "Unknown Vercel Project")
    logging.info(f"📥 Vercel event received: {event_type} for {owner}/{repo_name}")

    bot_token = _get_bot_token_for_repo(f"{owner}/{repo_name}")

    try:
        from vercel_agent import handle_vercel_deployment

        background_tasks.add_task(
            handle_vercel_deployment,
            dep_id,
            url,
            project_name,
            status,
            owner,
            repo_name,
            bot_token=bot_token,
        )
    except Exception as e:
        logging.error(f"Failed to dispatch Vercel agent: {e}\n{traceback.format_exc()}")

    return {"status": "accepted"}


@app.post("/cloudflare/webhook/{owner}/{repo_name}")
async def cloudflare_webhook(
    owner: str, repo_name: str, request: Request, background_tasks: BackgroundTasks
):
    """Cloudflare Pages/Workers webhook receiver."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Cloudflare payloads vary heavily based on Pages vs generic worker alerts.
    # Assuming standard CF Pages webhook format
    project_name = payload.get("project_name", "Unknown CF Project")
    status = payload.get("status", "unknown").lower()
    environment = payload.get("environment", "production")

    logging.info(f"📥 Cloudflare event received: {status} for {owner}/{repo_name}")

    bot_token = _get_bot_token_for_repo(f"{owner}/{repo_name}")

    try:
        from cloudflare_agent import handle_cloudflare_deployment

        background_tasks.add_task(
            handle_cloudflare_deployment,
            project_name,
            status,
            environment,
            owner,
            repo_name,
            bot_token=bot_token,
        )
    except Exception as e:
        logging.error(
            f"Failed to dispatch Cloudflare agent: {e}\n{traceback.format_exc()}"
        )

    return {"status": "accepted"}


@app.get("/logs")
async def get_logs():
    if not MAIN_LOG_FILE.exists():
        return "No logs found."

    with open(MAIN_LOG_FILE, "r") as f:
        return {"logs": f.readlines()}
    return {"logs": []}


@app.post("/chat")
async def chat_with_hermes(request: Request):
    """Direct chat with Hermes via library."""
    data = await request.json()
    message = data.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="Missing message")

    logging.info(f"💬 Chat request (API): {message[:50]}...")
    try:
        # Diagnostic: Check API Keys
        active_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("NOUS_API_KEY")

        # Determine base_url and default model
        is_nous = active_key and active_key.startswith("sk-2yd")
        target_base_url = NOUS_API_BASE_URL if is_nous else OPENROUTER_BASE_URL
        fallback_model = (
            "hermes-3-llama-3.1-405b" if is_nous else "anthropic/claude-3-5-sonnet"
        )

        # Priority: Global Model > Fallback
        raw_model = fallback_model
        target_model = get_standardized_model(raw_model, active_key or "")

        # Log the request
        msg = f"💬 Chat request (API): {message[:50]}..."
        try:
            with open(MAIN_LOG_FILE, mode="a") as f:
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO",
                    "message": msg,
                }
                f.write(json.dumps(entry) + "\n")
        except Exception as log_err:
            logging.warning(f"Failed to log chat request: {log_err}")

        # Fetch projects to provide context
        projects = []
        try:
            if DB_FILE.exists():
                import sqlite3

                with sqlite3.connect(DB_FILE) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT repo_full_name FROM hermes_project WHERE is_active = 1"
                    )
                    projects = [row[0] for row in cur.fetchall()]
        except Exception as projects_err:
            logging.warning(
                f"Failed to fetch projects for chat context: {projects_err}"
            )

        project_context = ""
        if projects:
            project_context = (
                f"\n\nRegistered repositories you can manage (located in {DATA_DIR}):\n- "
                + "\n- ".join(projects)
            )

        logging.info(f"Loaded {len(projects)} projects for chat context: {projects}")

        system_prompt = get_commander_system_prompt(project_context, str(DATA_DIR))

        # Session ID based on user or just a generic 'web-commander'

        # Session ID based on user or just a generic 'web-commander'
        session_id = data.get("session_id", "web-commander")

        # Initialize Agent
        agent = AIAgent(
            model=target_model,
            api_key=active_key or "",  # Handle potential None values for api_key
            base_url=target_base_url,
            quiet_mode=True,
            enabled_toolsets=["terminal", "file", "web", "vision"],
            skip_memory=False,  # Enable memory for multi-turn proactive flows
            session_id=session_id,
            ephemeral_system_prompt=system_prompt,
            platform="web-commander",
        )

        # We use run_conversation to handle memory automatically
        result = agent.run_conversation(message)
        response = result.get("final_response", "") if result else ""

        if not response or not str(response).strip():
            response = "Hermes did not provide a response."
        else:
            response = str(response)

        return {"response": response}
    except Exception as e:
        logging.error(f"Chat error: {e}")
        return {"response": f"Error: {str(e)}"}


if __name__ == "__main__":
    port = int(os.getenv("WEBHOOK_PORT", 8090))
    logging.info(f"Starting Hermes Webhook Receiver on port {port}...")
    # Bot startup is handled via @app.on_event("startup")
    uvicorn.run(app, host="0.0.0.0", port=port)
