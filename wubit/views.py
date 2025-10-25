# views.py (FINAL - Dual Role System)
import os, json, requests
from decimal import Decimal
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from .models import User, Store, Product, SellerSession, Buyer, ProductView, ProductSave, ProductOrder

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
        
        # Handle role selection commands
        if text.lower() in ['seller', 'buyer', 'both', 'ነጋዴ', 'ሻጭ', 'ደንበኛ', 'ኩሉ']:
            return handle_role_selection(chat_id, user, text)
        
        # Handle switch commands
        if text.lower() in ['/seller', '/switch seller']:
            return handle_role_selection(chat_id, user, 'seller')
        elif text.lower() in ['/buyer', '/switch buyer']:
            return handle_role_selection(chat_id, user, 'buyer')
        elif text.lower() == '/switch both':
            return handle_role_selection(chat_id, user, 'both')
        
        # Route commands based on context
        if text.lower().startswith('/'):
            # Seller commands
            if any(cmd in text.lower() for cmd in ['/addproduct', '/mystore', '/myproducts', '/insights']):
                return handle_seller_commands(chat_id, user, text)
            # Buyer commands
            elif any(cmd in text.lower() for cmd in ['/browse', '/mycart', '/myorders', '/wishlist']):
                return handle_buyer_commands(chat_id, user, text)
            # Help command
            elif text.lower() == '/help':
                return handle_help_command(chat_id, user)
        
        # Route regular messages based on active roles
        if user.is_seller and not user.is_buyer:
            # Only seller active - go to seller flow
            return handle_seller_flow(chat_id, user, text)
        elif user.is_buyer and not user.is_seller:
            # Only buyer active - go to buyer flow
            return handle_buyer_commands(chat_id, user, text)
        elif user.is_seller and user.is_buyer:
            # Both roles active - check context or show help
            if any(word in text.lower() for word in ['store', 'product', 'sell', 'price']):
                return handle_seller_flow(chat_id, user, text)
            elif any(word in text.lower() for word in ['buy', 'shop', 'cart', 'order']):
                return handle_buyer_commands(chat_id, user, text)
            else:
                return handle_help_command(chat_id, user)
        else:
            # No roles active - show role selection
            return handle_role_selection(chat_id, user, '')

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
        )
        print(f"✅ Created new user: {user.username}")
    
    return user

def handle_start_command(chat_id, first_name):
    """Send welcome message for dual-role system"""
    welcome_text = f"""
🎉 *Welcome to Wubit, {first_name}!* 

I'm your assistant for our multi-role marketplace! You can be both a *Seller* and *Buyer*.

*Choose your role:*
🛍️ *Seller* - Create store, add products, track sales
🛒 *Buyer* - Browse products, save items, make purchases

*You can switch between roles anytime!*

Just type:
• *Seller* - for seller commands  
• *Buyer* - for buyer commands
• *Both* - to activate both roles

What would you like to do first?
    """
    
    send_telegram_message(chat_id, welcome_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_role_selection(chat_id, user, text):
    """Handle role selection - users can have multiple roles"""
    text_lower = text.lower()
    
    if text_lower in ['seller', 'ነጋዴ', 'ሻጭ']:
        user.activate_seller()
        
        if user.has_store():
            # Already has store - show seller commands
            seller_commands = """
🛍️ *Seller Mode Activated!*

*Your Store Commands:*
/addproduct - Add new products
/mystore - View store info  
/myproducts - See your products
/insights - Product analytics
/switch buyer - Switch to buyer mode

Your store is ready! 🚀
            """
            send_telegram_message(chat_id, seller_commands, parse_mode='Markdown')
        else:
            # Start seller registration
            session, created = SellerSession.objects.get_or_create(
                user=user,
                defaults={'state': 'asking_phone', 'metadata': {}}
            )
            
            ask_phone_text = """
🛍️ *Seller Registration - Step 1*

Let's set up your seller account!

Please send your *phone number* (Ethiopian format):

Examples:
• 0912345678  
• +251912345678

This will be used for order notifications.
            """
            send_telegram_message(chat_id, ask_phone_text, parse_mode='Markdown')
    
    elif text_lower in ['buyer', 'ደንበኛ']:
        user.activate_buyer()
        
        # Ensure buyer profile exists
        buyer_profile, created = Buyer.objects.get_or_create(user=user)
        
        buyer_commands = """
🛒 *Buyer Mode Activated!*

*Buyer Commands:*
/browse - Browse products
/mycart - View cart 
/myorders - Order history
/wishlist - Saved items
/switch seller - Switch to seller mode

Happy shopping! 🛍️
        """
        send_telegram_message(chat_id, buyer_commands, parse_mode='Markdown')
    
    elif text_lower in ['both', 'all', 'ኩሉ']:
        user.activate_seller()
        user.activate_buyer()
        Buyer.objects.get_or_create(user=user)
        
        both_roles_text = """
🎭 *Dual Roles Activated!*

You're now both a *Seller* and *Buyer*!

*Switch between modes:*
• Type *seller* for seller commands
• Type *buyer* for buyer commands  
• Or use /switch command

What would you like to do first?
/seller - Seller features
/buyer - Buyer features
        """
        send_telegram_message(chat_id, both_roles_text, parse_mode='Markdown')
    
    else:
        help_text = """
Please choose a role:
• *Seller* - To sell products  
• *Buyer* - To shop products
• *Both* - To activate both roles

You can switch anytime! 🔄
        """
        send_telegram_message(chat_id, help_text, parse_mode='Markdown')
    
    return JsonResponse({'status': 'success'})

def handle_help_command(chat_id, user):
    """Show help based on active roles"""
    if user.is_seller and user.is_buyer:
        help_text = """
🔄 *Dual Role Help*

*Seller Commands:*
/addproduct - Add new products
/mystore - View store info  
/myproducts - See your products
/insights - Product analytics

*Buyer Commands:*
/browse - Browse products
/mycart - View cart
/myorders - Order history  
/wishlist - Saved items

*Switch Commands:*
/seller - Switch to seller mode
/buyer - Switch to buyer mode

Type any command to get started!
        """
    elif user.is_seller:
        help_text = """
🛍️ *Seller Help*

*Available Commands:*
/addproduct - Add new products
/mystore - View store info  
/myproducts - See your products
/insights - Product analytics
/switch buyer - Switch to buyer mode

Type any command to continue!
        """
    elif user.is_buyer:
        help_text = """
🛒 *Buyer Help*

*Available Commands:*
/browse - Browse products
/mycart - View cart
/myorders - Order history  
/wishlist - Saved items
/switch seller - Switch to seller mode

Type any command to continue!
        """
    else:
        help_text = """
🤔 *Get Started*

Choose a role to begin:
• Type *seller* - To sell products
• Type *buyer* - To shop products  
• Type *both* - For both roles

Each role has different commands and features!
        """
    
    send_telegram_message(chat_id, help_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

# ---- Seller Flow ----
def handle_seller_flow(chat_id, user, text):
    """Handle seller interactions"""
    if not user.is_seller:
        activate_seller_text = """
🛍️ *Seller Mode Required*

You need to activate seller mode first!

Type *seller* to switch to seller mode and access:
• Store management
• Product addition  
• Sales analytics

Or type *both* to activate both seller and buyer roles.
        """
        send_telegram_message(chat_id, activate_seller_text, parse_mode='Markdown')
        return JsonResponse({'status': 'success'})
    
    try:
        session, created = SellerSession.objects.get_or_create(user=user)
        
        if not session.state:
            session.state = 'asking_phone'
            session.save()
        
        print(f"🔧 Seller {user.username} state: {session.state}")
        
        # Handle store setup states
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
        elif session.state == 'adding_product_name':
            return handle_product_name_input(chat_id, user, session, text)
        elif session.state == 'adding_product_price':
            return handle_product_price_input(chat_id, user, session, text)
        elif session.state == 'adding_product_description':
            return handle_product_description_input(chat_id, user, session, text)
        elif session.state == 'adding_product_quantity':
            return handle_product_quantity_input(chat_id, user, session, text)
        else:
            session.state = 'seller_complete'
            session.save()
            return handle_seller_commands(chat_id, user, text)
            
    except Exception as e:
        print(f"❌ Seller flow error: {e}")
        send_telegram_message(chat_id, "Sorry, something went wrong. Type *seller* to try again.")
        return JsonResponse({'status': 'error'})

def handle_seller_commands(chat_id, user, text):
    """Handle seller commands"""
    if not user.is_seller:
        return handle_role_selection(chat_id, user, 'seller')
    
    if text.lower() == '/addproduct':
        session = SellerSession.objects.get(user=user)
        session.state = 'adding_product_name'
        session.metadata = {}
        session.save()
        send_telegram_message(chat_id, "🆕 *Add Product - Step 1*\n\nWhat's the product name? (Amharic or English)", parse_mode='Markdown')
        
    elif text.lower() == '/mystore':
        try:
            store = Store.objects.get(seller=user)
            total_products = store.products.count()
            total_views = store.products.aggregate(total_views=Sum('views_count'))['total_views'] or 0
            total_orders = store.products.aggregate(total_orders=Sum('orders_count'))['total_orders'] or 0
            
            store_info = f"""
🏪 *Your Store Info*

*Name:* {store.name}
*Location:* {store.location}
*Bio:* {store.bio}
*Phone:* {store.phone}
*Status:* {'✅ Verified' if store.verified else '⏳ Pending'}

📊 *Store Performance*
• Products: {total_products} items
• Total Views: {total_views}
• Total Orders: {total_orders}

Use /addproduct to add more items!
            """
            send_telegram_message(chat_id, store_info, parse_mode='Markdown')
        except Store.DoesNotExist:
            send_telegram_message(chat_id, "❌ You don't have a store yet. Continue with seller setup to create one.")
            
    elif text.lower() == '/myproducts':
        try:
            store = Store.objects.get(seller=user)
            products = store.products.all()
            
            if not products:
                send_telegram_message(chat_id, "📦 You don't have any products yet. Use /addproduct to add your first product!")
            else:
                message = "📦 *Your Products:*\n\n"
                for i, product in enumerate(products, 1):
                    conversion_rate = (product.orders_count / product.views_count * 100) if product.views_count > 0 else 0
                    message += f"*{i}. {product.name}*\n"
                    message += f"   Price: {product.price} ETB\n"
                    message += f"   Stock: {product.stock_quantity}\n"
                    message += f"   Views: {product.views_count} | Orders: {product.orders_count}\n"
                    message += f"   Conversion: {conversion_rate:.1f}%\n"
                    message += f"   ID: `{product.id}`\n\n"
                
                message += "📊 *To see detailed insights:*\nUse /insights followed by the product ID\nExample: `/insights PRODUCT_ID`"
                send_telegram_message(chat_id, message, parse_mode='Markdown')
        except Store.DoesNotExist:
            send_telegram_message(chat_id, "❌ You don't have a store yet.")
            
    elif text.lower().startswith('/insights'):
        return handle_insights_command(chat_id, user, text)
    else:
        return handle_help_command(chat_id, user)
    
    return JsonResponse({'status': 'success'})

# ---- Buyer Commands ----
def handle_buyer_commands(chat_id, user, text):
    """Handle buyer interactions"""
    if not user.is_buyer:
        return handle_role_selection(chat_id, user, 'buyer')
    
    # Ensure buyer profile exists
    buyer_profile, created = Buyer.objects.get_or_create(user=user)
    
    if text.lower() == '/browse':
        # Show available products
        products = Product.objects.filter(stock_quantity__gt=0)[:10]
        if products:
            message = "🛍️ *Available Products:*\n\n"
            for product in products:
                message += f"*{product.name}*\n"
                message += f"Price: {product.price} ETB\n"
                message += f"Store: {product.store.name}\n"
                message += f"Stock: {product.stock_quantity}\n\n"
            message += "More features coming soon! 🚀"
        else:
            message = "📭 No products available yet. Check back soon!"
        send_telegram_message(chat_id, message, parse_mode='Markdown')
        
    elif text.lower() == '/mycart':
        send_telegram_message(chat_id, "🛒 *Your Cart*\n\nCart features are coming soon! You'll be able to add products and checkout easily.")
        
    elif text.lower() == '/myorders':
        send_telegram_message(chat_id, "📦 *Your Orders*\n\nOrder history features are coming soon! You'll be able to track all your purchases.")
        
    elif text.lower() == '/wishlist':
        saved_products = buyer_profile.saved_products.all()
        if saved_products:
            message = "❤️ *Your Wishlist:*\n\n"
            for product in saved_products:
                message += f"• {product.name} - {product.price} ETB\n"
            message += "\nMore wishlist features coming soon!"
        else:
            message = "📝 *Your Wishlist is Empty*\n\nSave products you like to see them here!"
        send_telegram_message(chat_id, message, parse_mode='Markdown')
        
    elif text.lower() == '/switch seller':
        user.activate_seller()
        send_telegram_message(chat_id, "🛍️ Switched to Seller mode!")
    else:
        return handle_help_command(chat_id, user)
    
    return JsonResponse({'status': 'success'})

# ---- Store Setup Flow (Keep all existing functions) ----
def handle_phone_input(chat_id, user, session, text):
    phone = text.strip().replace(' ', '').replace('-', '')
    if len(phone) < 9:
        send_telegram_message(chat_id, "❌ Please enter a valid phone number (at least 9 digits). Try again:")
        return JsonResponse({'status': 'success'})
    
    user.phone_number = phone
    user.save()
    session.state = 'asking_national_id'
    session.save()
    
    ask_id_text = """
🆔 *Seller Registration - Step 2*

Please send your *National ID number* (12 digits):

This helps us verify your identity and build trust with customers.
    """
    send_telegram_message(chat_id, ask_id_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_national_id_input(chat_id, user, session, text):
    national_id = text.strip()
    if len(national_id) != 12 or not national_id.isdigit():
        send_telegram_message(chat_id, "❌ Please enter a valid 12-digit National ID. Try again:")
        return JsonResponse({'status': 'success'})
    
    user.national_id = national_id
    user.save()
    session.state = 'asking_store_name'
    session.save()
    
    ask_store_name_text = """
🏪 *Store Setup - Step 3*

What's your *store name*?

You can type in *Amharic* or *English*. Examples:
• *የኔ ሱቅ* (My Shop)
• *Traditional Crafts*
• *Ethiopian Coffee Corner*
    """
    send_telegram_message(chat_id, ask_store_name_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_store_name_input(chat_id, user, session, text):
    store_name = text.strip()
    if not store_name:
        send_telegram_message(chat_id, "❌ Please enter a store name:")
        return JsonResponse({'status': 'success'})
    
    detected_lang = TranslationService.detect_language(store_name)
    if detected_lang == 'am':
        store_name_en = TranslationService.translate_text(store_name, 'en')
        message = f"🌍 Detected Amharic: '{store_name}'\n🔤 English: '{store_name_en}'"
        send_telegram_message(chat_id, message)
    else:
        store_name_en = store_name
    
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
• "Fresh Ethiopian coffee and spices"
    """
    send_telegram_message(chat_id, ask_bio_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_store_bio_input(chat_id, user, session, text):
    store_bio = text.strip()
    if not store_bio:
        send_telegram_message(chat_id, "❌ Please tell us about your store:")
        return JsonResponse({'status': 'success'})
    
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
    """
    send_telegram_message(chat_id, ask_location_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_store_location_input(chat_id, user, session, text):
    location = text.strip()
    if not location:
        send_telegram_message(chat_id, "❌ Please enter your location:")
        return JsonResponse({'status': 'success'})
    
    try:
        store = Store.objects.create(
            seller=user,
            name=session.metadata.get('store_name_en', 'My Store'),
            bio=session.metadata.get('store_bio', ''),
            location=location,
            phone=user.phone_number
        )
        
        session.state = 'seller_complete'
        session.metadata['store_id'] = str(store.id)
        session.save()
        
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
/insights - Get product analytics

*Let's start!* Use /addproduct to add your first product! 🛍️
        """
        send_telegram_message(chat_id, success_text, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Store creation error: {e}")
        send_telegram_message(chat_id, "❌ Sorry, there was an error creating your store. Please try /start again.")
    
    return JsonResponse({'status': 'success'})

# ---- Product Addition Flow (Keep all existing functions) ----
def handle_product_name_input(chat_id, user, session, text):
    if not text:
        send_telegram_message(chat_id, "🆕 Please enter the product name:")
        return JsonResponse({'status': 'success'})
    
    product_name = text.strip()
    if not product_name:
        send_telegram_message(chat_id, "❌ Please enter a product name:")
        return JsonResponse({'status': 'success'})
    
    if not session.metadata:
        session.metadata = {}
    session.metadata['product_name'] = product_name
    session.state = 'adding_product_price'
    session.save()
    
    ask_price_text = """
💰 *Add Product - Step 2*

What's the price of *{product_name}*? (in ETB)

Examples:
• 150
• 299.99
• 1000
    """.format(product_name=product_name)
    send_telegram_message(chat_id, ask_price_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_product_price_input(chat_id, user, session, text):
    if not text:
        send_telegram_message(chat_id, "💰 Please enter the product price:")
        return JsonResponse({'status': 'success'})
    
    price_text = text.strip()
    try:
        price = Decimal(price_text)
        if price <= 0:
            raise ValueError("Price must be positive")
    except:
        send_telegram_message(chat_id, "❌ Please enter a valid price (numbers only, positive value). Try again:")
        return JsonResponse({'status': 'success'})
    
    session.metadata['product_price'] = str(price)
    session.state = 'adding_product_description'
    session.save()
    
    ask_description_text = """
📝 *Add Product - Step 3*

Describe *{product_name}*:

Tell customers about features, quality, size, etc.
    """.format(product_name=session.metadata['product_name'])
    send_telegram_message(chat_id, ask_description_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_product_description_input(chat_id, user, session, text):
    if not text:
        send_telegram_message(chat_id, "📝 Please enter the product description:")
        return JsonResponse({'status': 'success'})
    
    description = text.strip()
    if not description:
        send_telegram_message(chat_id, "❌ Please enter a product description:")
        return JsonResponse({'status': 'success'})
    
    session.metadata['product_description'] = description
    session.state = 'adding_product_quantity'
    session.save()
    
    ask_quantity_text = """
📦 *Add Product - Step 4*

How many units of *{product_name}* do you have in stock?

Enter the quantity (whole number):
    """.format(product_name=session.metadata['product_name'])
    send_telegram_message(chat_id, ask_quantity_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_product_quantity_input(chat_id, user, session, text):
    if not text:
        send_telegram_message(chat_id, "📦 Please enter the stock quantity:")
        return JsonResponse({'status': 'success'})
    
    quantity_text = text.strip()
    try:
        quantity = int(quantity_text)
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")
    except:
        send_telegram_message(chat_id, "❌ Please enter a valid quantity (whole number, 0 or more). Try again:")
        return JsonResponse({'status': 'success'})
    
    try:
        store = Store.objects.get(seller=user)
        product = Product.objects.create(
            store=store,
            name=session.metadata['product_name'],
            price=Decimal(session.metadata['product_price']),
            description=session.metadata['product_description'],
            stock_quantity=quantity
        )
        
        session.state = 'seller_complete'
        session.metadata = {}
        session.save()
        
        success_text = f"""
✅ *Product Added Successfully!*

*Product:* {product.name}
*Price:* {product.price} ETB
*Stock:* {product.stock_quantity} units

Your product is now live in your store!
        """
        send_telegram_message(chat_id, success_text, parse_mode='Markdown')
        
    except Store.DoesNotExist:
        send_telegram_message(chat_id, "❌ You don't have a store yet. Please complete store setup first.")
        session.state = 'seller_complete'
        session.save()
    except Exception as e:
        print(f"❌ Product creation error: {e}")
        send_telegram_message(chat_id, "❌ Sorry, there was an error adding your product. Please try /addproduct again.")
        session.state = 'seller_complete'
        session.save()
    
    return JsonResponse({'status': 'success'})

# ---- Insights Command ----
def handle_insights_command(chat_id, user, text):
    """Handle product insights"""
    try:
        parts = text.split()
        if len(parts) < 2:
            store = Store.objects.get(seller=user)
            products = store.products.all()
            
            if not products:
                send_telegram_message(chat_id, "📊 You don't have any products yet. Use /addproduct to add your first product!")
                return JsonResponse({'status': 'success'})
            
            message = "📊 *Select a product for insights:*\n\n"
            for i, product in enumerate(products, 1):
                conversion_rate = (product.orders_count / product.views_count * 100) if product.views_count > 0 else 0
                message += f"*{i}. {product.name}*\n"
                message += f"   Price: {product.price} ETB\n"
                message += f"   Stock: {product.stock_quantity}\n"
                message += f"   Performance: {product.orders_count} orders ({conversion_rate:.1f}%)\n"
                message += f"   ID: `{product.id}`\n\n"
            
            message += "To see detailed insights, use:\n`/insights PRODUCT_ID`"
            send_telegram_message(chat_id, message, parse_mode='Markdown')
            return JsonResponse({'status': 'success'})
        
        product_id = parts[1].strip()
        store = Store.objects.get(seller=user)
        product = Product.objects.get(id=product_id, store=store)
        
        # Generate insights
        total_revenue = product.price * product.orders_count
        conversion_rate = (product.orders_count / product.views_count * 100) if product.views_count > 0 else 0
        
        insights_text = f"""
📊 *Product Insights: {product.name}*

📈 *Performance Overview*
• Total Views: {product.views_count}
• Times Saved: {product.saves_count}
• Orders Placed: {product.orders_count}

💰 *Sales & Revenue*
• Price: {product.price} ETB
• Total Revenue: {total_revenue} ETB
• Conversion Rate: {conversion_rate:.1f}%

📦 *Inventory*
• Current Stock: {product.stock_quantity}
• Stock Health: {'🟢 Good' if product.stock_quantity > 10 else '🟡 Low' if product.stock_quantity > 0 else '🔴 Out'}

*Product Details*
• Added: {product.created_at.strftime('%Y-%m-%d')}
        """
        send_telegram_message(chat_id, insights_text, parse_mode='Markdown')
        
    except Product.DoesNotExist:
        send_telegram_message(chat_id, "❌ Product not found. Use /myproducts to see your products.")
    except Store.DoesNotExist:
        send_telegram_message(chat_id, "❌ You don't have a store yet.")
    except Exception as e:
        print(f"❌ Insights error: {e}")
        send_telegram_message(chat_id, "❌ Error getting insights. Please try again.")
    
    return JsonResponse({'status': 'success'})

def handle_callback_query(callback_query):
    """Handle inline keyboard interactions"""
    chat_id = callback_query['message']['chat']['id']
    send_telegram_message(chat_id, "Interactive features coming soon!")
    return JsonResponse({'status': 'success'})