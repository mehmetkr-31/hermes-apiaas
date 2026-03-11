import os
from pathlib import Path
from datetime import datetime

RUNBOOK_DIR = Path("/Users/alikar/dev/hermes-apiaas/.hermes/knowledge/runbooks")
RUNBOOK_DIR.mkdir(parents=True, exist_ok=True)

def generate_runbook(incident_data: dict):
    filename = f"runbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    filepath = RUNBOOK_DIR / filename
    
    content = f"""# Runbook: {incident_data.get('title', 'System Recovery')}

## Incident Overview
- **Date:** {datetime.now().isoformat()}
- **Root Cause:** {incident_data.get('root_cause')}

## Symptoms
{incident_data.get('symptoms')}

## Resolution Steps
{incident_data.get('resolution')}

## Lessons Learned
{incident_data.get('lessons')}
"""
    with open(filepath, "w") as f:
        f.write(content)
    return str(filepath)

if __name__ == "__main__":
    # generate_runbook({"title": "OOM Error", "root_cause": "Memory leak in scraper", "symptoms": "High RAM", "resolution": "Restarted", "lessons": "Check memory usage weekly"})
    print("Runbook Generator Module loaded.")
