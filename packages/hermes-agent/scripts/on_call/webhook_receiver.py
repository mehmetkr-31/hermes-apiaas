#!/usr/bin/env python3
import os
import subprocess
import logging
from fastapi import FastAPI, BackgroundTasks, Request
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = FastAPI(title="Hermes Webhook Receiver")
HERMES_CMD = os.getenv("HERMES_CMD", "hermes")

def trigger_hermes(payload: dict):
    logging.info(f"🚨 Webhook received! Triggering Hermes for incident...")
    
    # Format the payload into a prompt for Hermes
    issue_details = str(payload)[:1000] # Limit size to avoid max token issues
    task_prompt = f"Production issue triggered via Webhook. Incident details: {issue_details}. Investigate the root cause, check related systems, and attempt a fix. Report back via Telegram."
    
    try:
        proc = subprocess.run(
            [HERMES_CMD, "task", task_prompt, "--skill", "on_call"],
            capture_output=True,
            text=True
        )
        logging.info(f"✅ Hermes Task Finished. Output: {proc.stdout[:500]}...")
        if proc.stderr:
            logging.error(f"⚠️ Hermes Task Error: {proc.stderr[:500]}")
    except Exception as e:
        logging.error(f"❌ Failed to trigger Hermes: {e}")

@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        # Try to parse JSON, fallback to text
        payload = await request.json()
    except:
        payload = {"raw_body": (await request.body()).decode('utf-8')}
    
    # Add to background tasks so the webhook returns 200 OK immediately to the sender
    background_tasks.add_task(trigger_hermes, payload)
    
    return {"status": "accepted", "message": "Hermes incident response triggered in background."}

@app.get("/logs")
async def get_logs():
    # Simplified mock for now
    log_file = "agent/on_call_logs/monitoring.jsonl"
    logs = []
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            logs = f.readlines()
    return {"logs": logs}

if __name__ == "__main__":
    port = int(os.getenv("WEBHOOK_PORT", 8090))
    logging.info(f"Starting Hermes Webhook Receiver on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
