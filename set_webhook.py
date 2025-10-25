# set_webhook.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()
# Your actual values - KEEP THESE SECRET!
BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')  
WEBHOOK_URL = "https://wubit-4.onrender.com/telegram/webhook/"

def set_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    
    response = requests.post(url, json={
        "url": WEBHOOK_URL,
        "drop_pending_updates": True
    })
    
    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            print("✅ Webhook set successfully!")
            print(f"📱 Bot URL: {WEBHOOK_URL}")
        else:
            print(f"❌ Failed: {result.get('description')}")
    else:
        print("❌ Failed to connect to Telegram API")

if __name__ == "__main__":
    set_webhook()