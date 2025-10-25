# views.py (updated)
import os, json, requests
from decimal import Decimal
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import User, Store, Product, SellerSession

# ---- Translation Service ----
class TranslationService:
    @staticmethod
    def detect_language(text):
        """Simple Amharic detection"""
        amharic_range = range(0x1200, 0x137F)
        for char in text:
            if ord(char) in amharic_range:
                return 'am'
        return 'en'
    
    @staticmethod
    def translate_text(text, target_language='en'):
        """Simple translation - replace with real API in production"""
        # Basic Amharic to English mapping for demo
        amharic_to_english = {
            'ሰላም': 'Hello',
            'እንኳን ደህና መጣህ': 'Welcome',
            'እንኳን ደህና መጡ': 'Welcome',
            'ስለዚህ': 'About this',
            'ሻጭ': 'Seller',
            'ደንበኛ': 'Buyer',
            'ስራ': 'Work',
            'ንግድ': 'Business',
            'ሱቅ': 'Shop',
            'የኔ ሱቅ': 'My Shop',
            'እቃ': 'Product',
            'ዋጋ': 'Price',
            'ቁጥር': 'Number',
            'ስልክ': 'Phone',
            'መለያ': 'ID',
        }
        
        english_to_amharic = {v: k for k, v in amharic_to_english.items()}
        
        if target_language == 'en':
            return amharic_to_english.get(text, text)
        else:
            return english_to_amharic.get(text, text)

# ---- Telegram Message Helper ----
def send_telegram_message(chat_id, text, parse_mode=None):
    token = os.getenv('TELEGRAM_TOKEN') or getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        print("❌ No TELEGRAM_TOKEN set")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": text
    }
    
    if parse_mode:
        payload["parse_mode"] = parse_mode
        
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"❌ Telegram API error: {response.text}")
    except Exception as e:
        print(f"❌ Error sending message: {e}")

# ---- Main Webhook Handler ----
@csrf_exempt
def telegram_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'ok'})

    try:
        body = json.loads(request.body.decode('utf-8'))
        
        # Handle callback queries (inline keyboard)
        if 'callback_query' in body:
            return handle_callback_query(body['callback_query'])
            
        if 'message' not in body:
            return JsonResponse({'status': 'ok'})

        msg = body['message']
        chat_id = msg['chat']['id']
        text = msg.get('text', '').strip()
        first_name = msg['from'].get('first_name', 'User')

        print(f"📨 Message from {first_name} ({chat_id}): {text}")

        # Handle /start command
        if text == '/start':
            return handle_start_command(chat_id, first_name)
        
        # Get or create user
        user = get_or_create_user(chat_id, first_name)
        
        # Handle user registration flow
        if not user.user_type:
            return handle_user_type_selection(chat_id, user, text)
        
        # Handle seller flow
        if user.user_type == 'seller':
            return handle_seller_flow(chat_id, user, text)
        
        # Default response
        send_telegram_message(chat_id, "I'm focused on seller features right now. Use /start to begin.")
        return JsonResponse({'status': 'success'})

    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# ---- Helper Functions ----
def get_or_create_user(chat_id, first_name):
    """Get or create user with telegram ID"""
    username = f"tg_{chat_id}"
    
    try:
        user = User.objects.get(telegram_id=str(chat_id))
    except User.DoesNotExist:
        user = User.objects.create(
            username=username,
            telegram_id=str(chat_id),
            first_name=first_name,
            user_type='',  # Empty until they choose
        )
        print(f"✅ Created new user: {user.username}")
    
    return user

def handle_start_command(chat_id, first_name):
    """Send welcome message and ask for user type"""
    welcome_text = f"""
🎉 *Welcome to Wubit, {first_name}!* 

I'm your assistant for setting up your online store. Let's get your business online! 🛍️

*First, tell me: Are you a Seller or Buyer?*

Please reply with:
🔸 *Seller* - If you want to sell products
🔸 *Buyer* - If you want to shop (coming soon)

*For now, I'll help you set up as a Seller.* Just type *Seller* to continue!
    """
    
    send_telegram_message(chat_id, welcome_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_user_type_selection(chat_id, user, text):
    """Handle user type selection"""
    text_lower = text.lower()
    
    if text_lower in ['seller', 'ነጋዴ', 'ሻጭ']:
        user.user_type = 'seller'
        user.save()
        
        # Start seller registration flow
        session, created = SellerSession.objects.get_or_create(
            user=user,
            defaults={'state': 'asking_phone', 'metadata': {}}
        )
        
        ask_phone_text = """
📱 *Seller Registration - Step 1*

Please send your *phone number* (Ethiopian format):

Examples:
• 0912345678
• +251912345678

This will be used for order notifications and verification.
        """
        
        send_telegram_message(chat_id, ask_phone_text, parse_mode='Markdown')
        return JsonResponse({'status': 'success'})
    
    elif text_lower in ['buyer', 'ደንበኛ']:
        user.user_type = 'buyer'
        user.save()
        send_telegram_message(chat_id, "👋 Buyer features are coming soon! For now, let's set you up as a seller. Type *Seller* to continue.", parse_mode='Markdown')
        return JsonResponse({'status': 'success'})
    else:
        send_telegram_message(chat_id, "Please type *Seller* or *Buyer* to continue. I recommend *Seller* to set up your store now! 🛍️", parse_mode='Markdown')
        return JsonResponse({'status': 'success'})

def handle_seller_flow(chat_id, user, text):
    """Handle all seller interactions"""
    try:
        # Get or create seller session
        session, created = SellerSession.objects.get_or_create(user=user)
        
        # Handle based on current state
        if not session.state:
            session.state = 'asking_phone'
            session.save()
        
        print(f"🔧 Seller {user.username} state: {session.state}")
        
        if session.state == 'asking_phone':
            return handle_phone_input(chat_id, user, session, text)
        
        elif session.state == 'asking_national_id':
            return handle_national_id_input(chat_id, user, session, text)
            
        elif session.state == 'asking_store_name':
            return handle_store_name_input(chat_id, user, session, text)
            
        elif session.state == 'asking_store_bio':
            return handle_store_bio_input(chat_id, user, session, text)
            
        elif session.state == 'asking_store_location':
            return handle_store_location_input(chat_id, user, session, text)
            
        elif session.state == 'seller_complete':
            return handle_seller_commands(chat_id, user, text)
            
        else:
            # Default fallback
            session.state = 'asking_phone'
            session.save()
            send_telegram_message(chat_id, "Let's start with your phone number. Please send your phone number:")
            return JsonResponse({'status': 'success'})
            
    except Exception as e:
        print(f"❌ Seller flow error: {e}")
        send_telegram_message(chat_id, "Sorry, something went wrong. Let's start over with /start")
        return JsonResponse({'status': 'error'})

def handle_phone_input(chat_id, user, session, text):
    """Validate and save phone number"""
    # Simple phone validation
    phone = text.strip().replace(' ', '').replace('-', '')
    
    if len(phone) < 9:
        send_telegram_message(chat_id, "❌ Please enter a valid phone number (at least 9 digits). Try again:")
        return JsonResponse({'status': 'success'})
    
    # Save phone
    user.phone_number = phone
    user.save()
    
    # Update session
    session.state = 'asking_national_id'
    session.save()
    
    ask_id_text = """
🆔 *Seller Registration - Step 2*

Please send your *National ID number*:

This helps us verify your identity and build trust with customers.

*Privacy:* Your ID is stored securely and only used for verification.
    """
    
    send_telegram_message(chat_id, ask_id_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_national_id_input(chat_id, user, session, text):
    """Validate and save national ID"""
    national_id = text.strip()
    
    if len(national_id) < 4:
        send_telegram_message(chat_id, "❌ Please enter a valid National ID. Try again:")
        return JsonResponse({'status': 'success'})
    
    # Save national ID
    user.national_id = national_id
    user.save()
    
    # Update session
    session.state = 'asking_store_name'
    session.save()
    
    ask_store_name_text = """
🏪 *Store Setup - Step 3*

What's your *store name*?

You can type in *Amharic* or *English*. Examples:
• *የኔ ሱቅ* (My Shop)
• *Traditional Crafts*
• *Ethiopian Coffee Corner*

*Tip:* Choose a name that represents your products well!
    """
    
    send_telegram_message(chat_id, ask_store_name_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_store_name_input(chat_id, user, session, text):
    """Handle store name input with translation"""
    store_name = text.strip()
    
    if not store_name:
        send_telegram_message(chat_id, "❌ Please enter a store name:")
        return JsonResponse({'status': 'success'})
    
    # Detect language and translate if needed
    detected_lang = TranslationService.detect_language(store_name)
    
    if detected_lang == 'am':
        store_name_en = TranslationService.translate_text(store_name, 'en')
        message = f"🌍 Detected Amharic: '{store_name}'\n🔤 English: '{store_name_en}'"
        send_telegram_message(chat_id, message)
    else:
        store_name_en = store_name
    
    # Save to session metadata
    if not session.metadata:
        session.metadata = {}
    
    session.metadata['store_name'] = store_name
    session.metadata['store_name_en'] = store_name_en
    session.state = 'asking_store_bio'
    session.save()
    
    ask_bio_text = """
📝 *Store Setup - Step 4*

Tell us about your store! *What do you sell?*

Examples:
• "I sell handmade traditional Ethiopian scarves and crafts"
• "የእጅ የተሠራ አልባሳት እና የባህል እቃዎች እሸጣለሁ"
• "Fresh Ethiopian coffee and spices"

This helps customers understand your products!
    """
    
    send_telegram_message(chat_id, ask_bio_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_store_bio_input(chat_id, user, session, text):
    """Handle store bio input"""
    store_bio = text.strip()
    
    if not store_bio:
        send_telegram_message(chat_id, "❌ Please tell us about your store:")
        return JsonResponse({'status': 'success'})
    
    # Save to session
    session.metadata['store_bio'] = store_bio
    session.state = 'asking_store_location'
    session.save()
    
    ask_location_text = """
📍 *Store Setup - Step 5*

Where are you located? *City/Area*:

Examples:
• Addis Ababa, Bole
• Hawassa
• Bahir Dar
• "Online only"

This helps with delivery and local customers.
    """
    
    send_telegram_message(chat_id, ask_location_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_store_location_input(chat_id, user, session, text):
    """Finalize store creation"""
    location = text.strip()
    
    if not location:
        send_telegram_message(chat_id, "❌ Please enter your location:")
        return JsonResponse({'status': 'success'})
    
    try:
        # Create the store
        store = Store.objects.create(
            seller=user,
            name=session.metadata.get('store_name_en', 'My Store'),
            bio=session.metadata.get('store_bio', ''),
            location=location,
            phone=user.phone_number
        )
        
        # Update user session
        session.state = 'seller_complete'
        session.metadata['store_id'] = str(store.id)
        session.save()
        
        # Send success message
        success_text = f"""
🎊 *Congratulations! Your Store is Live!* 🎊

*Store Name:* {store.name}
*Location:* {store.location}
*Phone:* {user.phone_number}

✅ *Registration Complete!*

Now you can start adding products and selling!

*Available Commands:*
/addproduct - Add your first product
/mystore - View your store info
/myproducts - See your products
/help - Get help

*Let's start!* Use /addproduct to add your first product! 🛍️
        """
        
        send_telegram_message(chat_id, success_text, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Store creation error: {e}")
        send_telegram_message(chat_id, "❌ Sorry, there was an error creating your store. Please try /start again.")
    
    return JsonResponse({'status': 'success'})

def handle_seller_commands(chat_id, user, text):
    """Handle seller commands after registration"""
    if text.lower() == '/addproduct':
        # Start product addition flow
        session = SellerSession.objects.get(user=user)
        session.state = 'adding_product_name'
        session.metadata = {}  # Reset for product
        session.save()
        
        send_telegram_message(chat_id, "🆕 *Add Product - Step 1*\n\nWhat's the product name? (Amharic or English)", parse_mode='Markdown')
        
    elif text.lower() == '/mystore':
        # Show store info
        try:
            store = Store.objects.get(seller=user)
            store_info = f"""
🏪 *Your Store Info*

*Name:* {store.name}
*Location:* {store.location}
*Bio:* {store.bio}
*Phone:* {store.phone}
*Status:* {'✅ Verified' if store.verified else '⏳ Pending'}
*Products:* {store.products.count()} items

Use /addproduct to add more items!
            """
            send_telegram_message(chat_id, store_info, parse_mode='Markdown')
        except Store.DoesNotExist:
            send_telegram_message(chat_id, "❌ You don't have a store yet. Use /start to create one.")
            
    elif text.lower() == '/myproducts':
        # Show products
        try:
            store = Store.objects.get(seller=user)
            products = store.products.all()
            
            if not products:
                send_telegram_message(chat_id, "📦 You don't have any products yet. Use /addproduct to add your first product!")
            else:
                message = "📦 *Your Products:*\n\n"
                for product in products:
                    message += f"• {product.name} - {product.price} ETB\n"
                    message += f"  Stock: {product.stock_quantity}\n\n"
                
                send_telegram_message(chat_id, message, parse_mode='Markdown')
        except Store.DoesNotExist:
            send_telegram_message(chat_id, "❌ You don't have a store yet.")
            
    else:
        # Show available commands
        help_text = """
🛍️ *Seller Commands*

/addproduct - Add a new product
/mystore - View your store info  
/myproducts - List your products
/help - Show this help

*Need help?* Contact support if you have questions!
        """
        send_telegram_message(chat_id, help_text, parse_mode='Markdown')
    
    return JsonResponse({'status': 'success'})

def handle_callback_query(callback_query):
    """Handle inline keyboard interactions"""
    # You can add this later for more interactive features
    chat_id = callback_query['message']['chat']['id']
    send_telegram_message(chat_id, "Interactive features coming soon!")
    return JsonResponse({'status': 'success'})