import os
import requests
from dotenv import load_dotenv

load_dotenv()

def send_telegram_notification(job: dict) -> bool:
    """
    Sends a Telegram alert for a newly discovered job listing.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")

    if not token or not chat_id:
        print("⚠️ Telegram token or Chat ID missing in environment. Skipping Telegram alert.")
        return False

    message = (
        f"🚀 <b>New Job Found!</b>\n\n"
        f"🏢 <b>Company:</b> {job.get('company', 'Unknown')}\n"
        f"💼 <b>Title:</b> {job.get('title', 'N/A')}\n"
        f"🔍 <b>Match Reason:</b> {job.get('reason', 'N/A')}\n"
        f"🔗 <b>Link:</b> <a href=\"{job.get('url', '#')}\">View Job Opening</a>"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Telegram notification sent for: {job.get('title')}")
            return True
        else:
            print(f"❌ Failed to send Telegram alert ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending Telegram alert: {e}")
        return False
