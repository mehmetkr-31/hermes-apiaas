#!/usr/bin/env python3
import os
import subprocess
import time

def run_demo():
    print("🚀 Starting On-Call Agent Demo Scenario (60s)...")
    
    # 1. Simulating a 'Prod Down' event
    issue = "CRITICAL: API service on port 8000 is down. HTTP 503."
    print(f"\n[DEMO] Triggering event: {issue}")
    
    # 2. Invoke Hermes On-Call Agent
    # We use 'hermes chat' for the demo to show the dialogue
    cmd = [
        "hermes", "chat",
        "--skill", "on_call",
        "--query", f"ALERT: {issue}. Investigate the dashboard, find the error fix, and restart the service. Report to Telegram."
    ]
    
    print(f"[DEMO] Running Hermes natively...")
    try:
        # We run this in the foreground so the user sees the 'agent at work'
        subprocess.run(cmd)
    except Exception as e:
        print(f"Demo failed: {e}")

if __name__ == "__main__":
    run_demo()
