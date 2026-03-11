#!/usr/bin/env python3
import os
import time
import json
import psutil
import httpx
import argparse
from datetime import datetime, timezone
from pathlib import Path

# --- Config ---
LOG_DIR = Path("/Users/alikar/dev/hermes-apiaas/agent/on_call_logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
HEALTH_LOG = LOG_DIR / "monitoring.jsonl"

ENDPOINTS = [
    {"name": "API", "url": "http://localhost:8000/health"},
    {"name": "Frontend", "url": "http://localhost:3000"},
]

def get_system_stats():
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
    }

def check_endpoints():
    results = []
    with httpx.Client(timeout=5.0) as client:
        for ep in ENDPOINTS:
            try:
                r = client.get(ep["url"])
                results.append({
                    "name": ep["name"],
                    "status": "up" if r.status_code < 400 else "down",
                    "code": r.status_code,
                    "latency": r.elapsed.total_seconds()
                })
            except Exception as e:
                results.append({
                    "name": ep["name"],
                    "status": "down",
                    "error": str(e)
                })
    return results

def log_stats(stats, endpoint_results):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": stats,
        "endpoints": endpoint_results
    }
    with open(HEALTH_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry

def main():
    parser = argparse.ArgumentParser(description="On-Call Agent Sentinel")
    parser.add_argument("--test", action="store_true", help="Run once and print output")
    args = parser.parse_args()

    if args.test:
        stats = get_system_stats()
        endpoints = check_endpoints()
        entry = log_stats(stats, endpoints)
        print(json.dumps(entry, indent=2))
    else:
        print(f"Monitoring started. Logging to {HEALTH_LOG}")
        while True:
            stats = get_system_stats()
            endpoints = check_endpoints()
            log_stats(stats, endpoints)
            time.sleep(120) # 2 minutes

if __name__ == "__main__":
    main()
