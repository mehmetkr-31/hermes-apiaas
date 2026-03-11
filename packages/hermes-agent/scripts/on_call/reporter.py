import os
import httpx
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(f"Telegram not configured. Log: {text}")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        httpx.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def format_incident_report(event_data: dict):
    report = f"""
🚨 *PRODUCTION INCIDENT DETECTED*
📅 *Time:* {event_data.get('timestamp')}

🔍 *Status:* {event_data.get('summary')}

🛠 *Actions Taken:*
{event_data.get('actions')}

✅ *Result:* {event_data.get('result')}
    """
    return report.strip()

if __name__ == "__main__":
    # send_telegram_message("Test message from On-Call Agent")
    print("Telegram Reporter Module loaded.")
