import os
from datetime import datetime
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

def send_status_notification(total_companies: int) -> bool:
    """
    Sends a daily status heartbeat Telegram message when 0 new jobs are found.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")

    if not token or not chat_id:
        print("⚠️ Telegram token or Chat ID missing in environment. Skipping status heartbeat.")
        return False

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    message = (
        f"🤖 <b>Scout Scraper Status Update</b>\n\n"
        f"✅ Daily scrape completed successfully.\n"
        f"🏢 <b>Companies Scraped:</b> {total_companies}\n"
        f"🔍 <b>New Jobs Found:</b> 0\n"
        f"🕒 <i>Checked at {date_str}</i>"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Daily status heartbeat sent to Telegram.")
            return True
        else:
            print(f"❌ Failed to send status heartbeat ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending status heartbeat: {e}")
        return False
