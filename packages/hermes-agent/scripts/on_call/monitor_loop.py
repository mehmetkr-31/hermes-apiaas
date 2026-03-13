#!/usr/bin/env python3
"""
Hermes On-Call Monitor Loop
Autonomously checks system health and triggers diagnosis if needed.
"""
import time
import logging
import sqlite3
from reporter import send_telegram_message, DB_FILE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def check_health(repo_full_name: str):
    # Placeholder for actual health checking logic
    logging.info(f"🔍 Checking system health for {repo_full_name}...")
    return True

def main():
    logging.info("🚀 Hermes On-Call Monitor Loop started.")
    while True:
        try:
            if DB_FILE.exists():
                with sqlite3.connect(DB_FILE) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT repo_full_name FROM hermes_project WHERE is_active = 1")
                    repos = [row[0] for row in cur.fetchall()]
                    
                    for repo in repos:
                        if not check_health(repo):
                            send_telegram_message("⚠️ Health check failed! Starting autonomous diagnosis...", repo_full_name=repo)
            
            time.sleep(60) # Poll every minute
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(f"Error in monitor loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
