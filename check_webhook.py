"""
Test your bot locally with polling instead of webhook
This helps verify your bot logic works before debugging webhook issues
"""
import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')

def send_message(chat_id, text, parse_mode=None):
    """Send a message to Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    
    if parse_mode:
        payload["parse_mode"] = parse_mode
    
    response = requests.post(url, json=payload)
    return response.json()

def handle_message(message):
    """Handle incoming messages - same logic as your webhook"""
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()
    first_name = message['from'].get('first_name', 'User')
    
    print(f"\n📨 Message from {first_name} ({chat_id}): {text}")
    
    if text == '/start':
        welcome_text = f"""
🎉 *Welcome to Wubit, {first_name}!* 

I'm your assistant for setting up your online store. Let's get your business online! 🛍️

*First, tell me: Are you a Seller or Buyer?*

Please reply with:
🔸 *Seller* - If you want to sell products
🔸 *Buyer* - If you want to shop (coming soon)

*For now, I'll help you set up as a Seller.* Just type *Seller* to continue!
        """
        
        result = send_message(chat_id, welcome_text, parse_mode='Markdown')
        print(f"✅ Sent welcome message: {result.get('ok')}")
    
    elif text.lower() in ['seller', 'buyer']:
        response = f"Great! You chose: {text}\n\nThis is a test. Your bot logic is working! ✅"
        send_message(chat_id, response)
    
    else:
        send_message(chat_id, "Send /start to begin!")

def main():
    """Main polling loop"""
    print("🤖 Starting bot in POLLING mode...")
    print("💡 This is for testing. Press Ctrl+C to stop.\n")
    
    # First, delete webhook so polling works
    delete_webhook_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    requests.post(delete_webhook_url)
    print("✅ Webhook removed (temporary, for testing)")
    
    offset = None
    
    try:
        while True:
            # Get updates
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {"timeout": 30}
            
            if offset:
                params["offset"] = offset
            
            response = requests.get(url, params=params, timeout=35)
            
            if response.status_code != 200:
                print(f"❌ Error: {response.text}")
                time.sleep(5)
                continue
            
            updates = response.json().get('result', [])
            
            for update in updates:
                offset = update['update_id'] + 1
                
                if 'message' in update:
                    handle_message(update['message'])
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping bot...")
        print("\n⚠️  REMEMBER: Set your webhook again with:")
        print("   python set_webhook.py")
        print("\nBot stopped.")

if __name__ == "__main__":
    main()