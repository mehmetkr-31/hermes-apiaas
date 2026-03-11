#!/usr/bin/env python3
import time
import subprocess
import psutil
import httpx
import os
import logging
from pathlib import Path
from datetime import datetime

# --- Config ---
HERMES_CMD = os.getenv("HERMES_CMD", "hermes")
API_URL = os.getenv("API_URL", "http://localhost:8000/health")
CPU_THRESHOLD = int(os.getenv("CPU_THRESHOLD", 95))
MEM_THRESHOLD = int(os.getenv("MEM_THRESHOLD", 95))
LOG_FILE = Path("/Users/alikar/dev/hermes-apiaas/agent/on_call_logs/sentinel.log")

# Setup logging
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

def check_health():
    # 1. Check local API
    try:
        r = httpx.get(API_URL, timeout=5)
        if r.status_code >= 400:
            return f"API returned status {r.status_code}"
    except Exception as e:
        return f"API connection failed: {e}"

    # 2. Check System Stats
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent
    
    if cpu > CPU_THRESHOLD:
        return f"CPU usage is critical ({cpu}%)"
    if mem > MEM_THRESHOLD:
        return f"Memory usage is critical ({mem}%)"

    return None

def trigger_hermes(issue: str):
    logging.error(f"Issue detected: {issue}. Invoking Hermes On-Call Agent...")
    
    task_prompt = f"The following production issue was detected: {issue}. Investigate the root cause using vision/logs/web-search and attempt a fix. Report back on Telegram."
    
    try:
        # Run in background but log output
        proc = subprocess.run([HERMES_CMD, "task", task_prompt, "--skill", "on_call"], capture_output=True, text=True)
        logging.info(f"Hermes Task Output: {proc.stdout}")
        if proc.stderr:
            logging.error(f"Hermes Task Error: {proc.stderr}")
    except Exception as e:
        logging.error(f"Failed to trigger Hermes: {e}")

def main():
    logging.info("Sentinel Monitor Active. Watching for anomalies...")
    while True:
        try:
            issue = check_health()
            if issue:
                trigger_hermes(issue)
                # Avoid spamming triggers if it persists
                time.sleep(300) 
            else:
                logging.debug("System healthy.")
        except Exception as e:
            logging.error(f"Unexpected error in monitor loop: {e}")
        
        time.sleep(60)

if __name__ == "__main__":
    main()
