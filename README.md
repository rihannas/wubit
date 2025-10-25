# wubit

# REVIEW FLOW: start with "/review <order_item_id>"

        if text.startswith('/review'):
            parts = text.split()
            if len(parts) < 2:
                send_telegram_message(chat_id, "Usage: /review <order_item_id>")
                return JsonResponse({'ok': True})
            order_item_id = parts[1]
            try:
                oi = OrderItem.objects.get(id=order_item_id, order__buyer=buyer)
            except OrderItem.DoesNotExist:
                send_telegram_message(chat_id, "Order item not found or not owned by you.")
                return JsonResponse({'ok': True})
            if oi.order.status != 'completed' and oi.order.status != 'paid' and oi.order.status != 'shipped':
                # only allow review if order at least paid/completed (adjust rule as needed)
                send_telegram_message(chat_id, "You can only review items that have been paid/completed.")
                return JsonResponse({'ok': True})
            # set buyer session to collect review text next
            bsess, _ = BuyerSession.objects.get_or_create(user=user)
            bsess.state = 'awaiting_review_text'
            bsess.metadata = {'order_item_id': str(oi.id)}
            bsess.save()
            send_telegram_message(chat_id, f"Please write your review for '{oi.product.name_en}':")
            return JsonResponse({'ok': True})

        # If buyer_session expecting review text or rating
        bsession = getattr(user, 'buyer_session', None)
        if bsession and bsession.state:
            if bsession.state == 'awaiting_review_text':
                # store review text then ask for rating
                text_review = text
                bsession.metadata['review_text'] = text_review
                bsession.state = 'awaiting_review_rating'
                bsession.save()
                send_telegram_message(chat_id, "Thanks. Now send a rating from 1 to 5.")
                return JsonResponse({'ok': True})
            if bsession.state == 'awaiting_review_rating':
                try:
                    rating = int(text)
                    if rating < 1 or rating > 5:
                        raise ValueError
                except:
                    send_telegram_message(chat_id, "Send a number between 1 and 5 for rating.")
                    return JsonResponse({'ok': True})
                order_item_id = bsession.metadata.get('order_item_id')
                review_text = bsession.metadata.get('review_text')
                oi = OrderItem.objects.get(id=order_item_id)
                Review.objects.create(buyer=buyer, product=oi.product, rating=rating, text=review_text)
                bsession.state = ''
                bsession.metadata = {}
                bsession.save()
                send_telegram_message(chat_id, "✅ Thank you for your review!")
                return JsonResponse({'ok': True})

---

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid
from decimal import Decimal

# -------------------- USER --------------------

class User(AbstractUser):
USER_TYPES = (
('seller', 'Seller'),
('buyer', 'Buyer'),
)
user_type = models.CharField(max_length=10, choices=USER_TYPES)
telegram_id = models.CharField(max_length=50, blank=True, null=True)
phone_number = models.CharField(max_length=20, blank=True, null=True)
national_id = models.CharField(max_length=10, blank=True, null=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='wubit_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='wubit_user_permissions_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )



    def __str__(self):
        return f"{self.username} ({self.user_type})"

# -------------------- STORE --------------------

class Store(models.Model):
id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
seller = models.OneToOneField(User, on_delete=models.CASCADE, related_name='store')
name = models.CharField(max_length=255)
bio = models.TextField(blank=True)
logo_url = models.URLField(blank=True, null=True)
phone = models.CharField(max_length=50, blank=True, null=True)
location = models.CharField(max_length=255, blank=True, null=True)
verified = models.BooleanField(default=False)
created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name_en

# -------------------- PRODUCT --------------------

class Product(models.Model):
id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
name = models.CharField(max_length=255)
description = models.TextField(blank=True, null=True)
price = models.DecimalField(max_digits=10, decimal_places=2)
image_url = models.URLField(blank=True, null=True)
stock_quantity = models.IntegerField(default=0)
created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name_en} ({self.store.name_en})"

# -------------------- BUYER --------------------

class Buyer(models.Model):
user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='buyer_profile')
saved_products = models.ManyToManyField(Product, blank=True, related_name='saved_by')

    def __str__(self):
        return self.user.username

# -------------------- CART --------------------

class Cart(models.Model):
id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
buyer = models.OneToOneField(Buyer, on_delete=models.CASCADE, related_name='cart')
created_at = models.DateTimeField(default=timezone.now)

class CartItem(models.Model):
cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
product = models.ForeignKey(Product, on_delete=models.CASCADE)
quantity = models.IntegerField(default=1)

# -------------------- WISHLIST --------------------

class Wishlist(models.Model):
buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name='wishlist')
product = models.ForeignKey(Product, on_delete=models.CASCADE)
created_at = models.DateTimeField(default=timezone.now)

# -------------------- ORDER --------------------

class Order(models.Model):
STATUS_CHOICES = [
('pending', 'Pending'),
('paid', 'Paid'),
('shipped', 'Shipped'),
('completed', 'Completed'),
]
id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name='orders')
total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='pending')
created_at = models.DateTimeField(default=timezone.now)
metadata = models.JSONField(blank=True, null=True)

class OrderItem(models.Model):
order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
product = models.ForeignKey(Product, on_delete=models.PROTECT)
quantity = models.IntegerField(default=1)

# -------------------- REVIEW --------------------

class Review(models.Model):
buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE)
product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
rating = models.IntegerField(default=5)
text = models.TextField()
created_at = models.DateTimeField(default=timezone.now)

# -------------------- SELLER SESSION --------------------

class SellerSession(models.Model):
user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seller_session')
state = models.CharField(max_length=100, blank=True, null=True)
metadata = models.JSONField(blank=True, null=True)
updated_at = models.DateTimeField(auto_now=True)

from django.conf import settings

class BuyerSession(models.Model):
buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name='buyer_sessions') # Fixed: Changed from settings.AUTH_USER_MODEL to Buyer
data = models.JSONField(default=dict, blank=True)
created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"BuyerSession({self.buyer.user.username})"

---

from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator

from django_countries.fields import CountryField

from phonenumber_field.modelfields import PhoneNumberField
from decimal import Decimal

class CustomUserManager(BaseUserManager):
def create_user(self, email, password=None, **extra_fields):
if not email:
raise ValueError('The Email field must be set')
email = self.normalize_email(email)
user = self.model(email=email, **extra_fields)
user.set_password(password)  
 user.save(using=self.\_db)
return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
email = models.EmailField(unique=True)
about = models.TextField()
phonenumber = PhoneNumberField(blank=False)
country = CountryField()
last_login = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'about', 'phonenumber', 'password']


    # Add unique related_name attributes to avoid clashes
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        related_name='customuser_set'  # Unique related_name
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        related_name='customuser_permissions'  # Unique related_name
    )

class Seller(models.Model):
user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='seller')
skills = models.TextField(blank=True, null=True)
portfolio = models.TextField(blank=True, null=True)
average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
number_of_reviews = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.user.username}'

    def save(self, *args, **kwargs):
        # Add the user to the Seller group
        seller_group, created = Group.objects.get_or_create(name='Seller')
        self.user.groups.add(seller_group)
        super().save(*args, **kwargs)

class Buyer(models.Model):
user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='buyer')
favorite_services = models.ManyToManyField('Service', related_name='favorited_by')

    def __str__(self):
        return f'{self.user.username}'

    def save(self, *args, **kwargs):
        # Add the user to the Seller group
        buyer_group, created = Group.objects.get_or_create(name='Buyer')
        self.user.groups.add(buyer_group)
        super().save(*args, **kwargs)

class Category(models.Model):
name = models.CharField(max_length=225)

    def __str__(self):
        return self.name

class Service(models.Model):
title = models.CharField(max_length=225, blank=False)
category_id = models.ForeignKey(Category, on_delete=models.PROTECT, blank=False)
description = models.TextField(blank=False)
price = models.DecimalField(decimal_places=2, max_digits=6, validators=[MinValueValidator(Decimal(0.00))], blank=False)
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
seller_id = models.ForeignKey(Seller, on_delete=models.CASCADE)
tags = models.ManyToManyField('Tag', related_name='services', blank=True)

    def __str__(self):
        return self.title

class Order(models.Model):
created_at = models.DateTimeField(auto_now_add=True)
buyer_id = models.ForeignKey(Buyer, on_delete=models.CASCADE)
seller_id = models.ForeignKey(Seller, on_delete=models.CASCADE)
#unit price

    #TODO:
    # Change the on_delete situation to be PROTECTED if an order is active.
    def __str__(self):
        return f"Order #{self.id}"

class OrderItem(models.Model):
ORDER_STATUS_PENDING = 'P'
ORDER_STATUS_COMPLETE = 'C'
ORDER_STATUS_DELIEVERED = 'D'
ORDER_STATUS_REVISION = 'R'
ORDER_STATUS_CHOICES = [
(ORDER_STATUS_PENDING, 'Pending'),
(ORDER_STATUS_COMPLETE, 'Completed'),
(ORDER_STATUS_DELIEVERED, 'Delievered'),
(ORDER_STATUS_REVISION, 'Revision')
]

    order_id = models.ForeignKey(Order, on_delete=models.PROTECT)
    service_id = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='orderitems')
    order_status = models.CharField(
        max_length=1, choices=ORDER_STATUS_CHOICES, default=ORDER_STATUS_PENDING)

    def __str__(self) -> str:
        return f"{self.service}"

class Tag(models.Model):
tag = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.tag

class Rating(models.Model):
service_id = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='reviews')
buyer_id = models.ForeignKey(Buyer, on_delete=models.CASCADE)
rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
comment = models.TextField(blank=True)
created_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Rating for {self.service.title} by {self.buyer.username}"

class Transaction(models.Model):
pass

#Servicevariations : basic, mid, premium

#Paymentsession instead of cart

---

# views.py (COMPLETE - with product addition flow)

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

def get*or_create_user(chat_id, first_name):
"""Get or create user with telegram ID"""
username = f"tg*{chat_id}"

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

def handle*start_command(chat_id, first_name):
"""Send welcome message and ask for user type"""
welcome_text = f"""
🎉 \_Welcome to Wubit, {first_name}!*

I'm your assistant for setting up your online store. Let's get your business online! 🛍️

_First, tell me: Are you a Seller or Buyer?_

Please reply with:
🔸 _Seller_ - If you want to sell products
🔸 _Buyer_ - If you want to shop (coming soon)

_For now, I'll help you set up as a Seller._ Just type _Seller_ to continue!
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

📱 _Seller Registration - Step 1_

Please send your _phone number_ (Ethiopian format):

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
try: # Get or create seller session
session, created = SellerSession.objects.get_or_create(user=user)

        # Handle based on current state
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

        # Handle product addition states
        elif session.state == 'adding_product_name':
            return handle_product_name_input(chat_id, user, session, text)

        elif session.state == 'adding_product_price':
            return handle_product_price_input(chat_id, user, session, text)

        elif session.state == 'adding_product_description':
            return handle_product_description_input(chat_id, user, session, text)

        elif session.state == 'adding_product_quantity':
            return handle_product_quantity_input(chat_id, user, session, text)

        else:
            # Default fallback
            session.state = 'seller_complete'
            session.save()
            return handle_seller_commands(chat_id, user, text)

    except Exception as e:
        print(f"❌ Seller flow error: {e}")
        send_telegram_message(chat_id, "Sorry, something went wrong. Let's start over with /start")
        return JsonResponse({'status': 'error'})

def handle_phone_input(chat_id, user, session, text):
"""Validate and save phone number""" # Simple phone validation
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

🆔 _Seller Registration - Step 2_

Please send your _National ID number FIN_:

This helps us verify your identity and build trust with customers.

_Privacy:_ Your ID is stored securely and only used for verification.
"""

    send_telegram_message(chat_id, ask_id_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_national_id_input(chat_id, user, session, text):
"""Validate and save national ID"""
national_id = text.strip()

    if len(national_id) < 4:
        send_telegram_message(chat_id, "❌ Please enter a valid National ID FIN. Try again:")
        return JsonResponse({'status': 'success'})

    # Save national ID
    user.national_id = national_id
    user.save()

    # Update session
    session.state = 'asking_store_name'
    session.save()

    ask_store_name_text = """

🏪 _Store Setup - Step 3_

What's your _store name_?

You can type in _Amharic_ or _English_. Examples:
• _የኔ ሱቅ_ (My Shop)
• _Traditional Crafts_
• _Ethiopian Coffee Corner_

_Tip:_ Choose a name that represents your products well!
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

📝 _Store Setup - Step 4_

Tell us about your store! _What do you sell?_

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

📍 _Store Setup - Step 5_

Where are you located? _City/Area_:

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

🎊 _Congratulations! Your Store is Live!_ 🎊

_Store Name:_ {store.name}
_Location:_ {store.location}
_Phone:_ {user.phone_number}

✅ _Registration Complete!_

Now you can start adding products and selling!

_Available Commands:_
/addproduct - Add your first product
/mystore - View your store info
/myproducts - See your products
/help - Get help

_Let's start!_ Use /addproduct to add your first product! 🛍️
"""

        send_telegram_message(chat_id, success_text, parse_mode='Markdown')

    except Exception as e:
        print(f"❌ Store creation error: {e}")
        send_telegram_message(chat_id, "❌ Sorry, there was an error creating your store. Please try /start again.")

    return JsonResponse({'status': 'success'})

def handle_seller_commands(chat_id, user, text):
"""Handle seller commands after registration"""
if text.lower() == '/addproduct': # Start product addition flow
session = SellerSession.objects.get(user=user)
session.state = 'adding_product_name'
session.metadata = {} # Reset for product
session.save()

        send_telegram_message(chat_id, "🆕 *Add Product - Step 1*\n\nWhat's the product name? (Amharic or English)", parse_mode='Markdown')

    elif text.lower() == '/mystore':
        # Show store info
        try:
            store = Store.objects.get(seller=user)
            store_info = f"""

🏪 _Your Store Info_

_Name:_ {store.name}
_Location:_ {store.location}
_Bio:_ {store.bio}
_Phone:_ {store.phone}
_Status:_ {'✅ Verified' if store.verified else '⏳ Pending'}
_Products:_ {store.products.count()} items

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

🛍️ _Seller Commands_

/addproduct - Add a new product
/mystore - View your store info  
/myproducts - List your products
/help - Show this help

_Need help?_ Contact support if you have questions!
"""
send_telegram_message(chat_id, help_text, parse_mode='Markdown')

    return JsonResponse({'status': 'success'})

# ---- Product Addition Flow ----

def handle_product_name_input(chat_id, user, session, text):
"""Handle product name input"""
if not text:
send_telegram_message(chat_id, "🆕 Please enter the product name:")
return JsonResponse({'status': 'success'})

    product_name = text.strip()

    if not product_name:
        send_telegram_message(chat_id, "❌ Please enter a product name:")
        return JsonResponse({'status': 'success'})

    # Save product name to session
    if not session.metadata:
        session.metadata = {}

    session.metadata['product_name'] = product_name
    session.state = 'adding_product_price'
    session.save()

    ask_price_text = """

💰 _Add Product - Step 2_

What's the price of _{product_name}_? (in ETB)

Examples:
• 150
• 299.99
• 1000

Please enter only the number.
""".format(product_name=product_name)

    send_telegram_message(chat_id, ask_price_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_product_price_input(chat_id, user, session, text):
"""Handle product price input"""
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

    # Save product price to session
    session.metadata['product_price'] = str(price)
    session.state = 'adding_product_description'
    session.save()

    ask_description_text = """

📝 _Add Product - Step 3_

Describe _{product_name}_:

Tell customers about:
• Features
• Quality
• Size/weight
• Any important details

This helps customers understand your product better!
""".format(product_name=session.metadata['product_name'])

    send_telegram_message(chat_id, ask_description_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_product_description_input(chat_id, user, session, text):
"""Handle product description input"""
if not text:
send_telegram_message(chat_id, "📝 Please enter the product description:")
return JsonResponse({'status': 'success'})

    description = text.strip()

    if not description:
        send_telegram_message(chat_id, "❌ Please enter a product description:")
        return JsonResponse({'status': 'success'})

    # Save product description to session
    session.metadata['product_description'] = description
    session.state = 'adding_product_quantity'
    session.save()

    ask_quantity_text = """

📦 _Add Product - Step 4_

How many units of _{product_name}_ do you have in stock?

Enter the quantity (whole number):

Examples:
• 10
• 50
• 100

Enter 0 if this is a service or digital product.
""".format(product_name=session.metadata['product_name'])

    send_telegram_message(chat_id, ask_quantity_text, parse_mode='Markdown')
    return JsonResponse({'status': 'success'})

def handle_product_quantity_input(chat_id, user, session, text):
"""Finalize product creation"""
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
        # Get user's store
        store = Store.objects.get(seller=user)

        # Create the product
        product = Product.objects.create(
            store=store,
            name=session.metadata['product_name'],
            price=Decimal(session.metadata['product_price']),
            description=session.metadata['product_description'],
            stock_quantity=quantity
        )

        # Reset session to seller_complete
        session.state = 'seller_complete'
        session.metadata = {}  # Clear product data
        session.save()

        # Send success message
        success_text = f"""

✅ _Product Added Successfully!_

_Product:_ {product.name}
_Price:_ {product.price} ETB
_Stock:_ {product.stock_quantity} units

Your product is now live in your store! Customers can see it and place orders.

_What's next?_
/addproduct - Add another product
/myproducts - View all your products
/mystore - See your store info
"""

        send_telegram_message(chat_id, success_text, parse_mode='Markdown')

    except Store.DoesNotExist:
        send_telegram_message(chat_id, "❌ You don't have a store yet. Please complete store setup with /start first.")
        session.state = 'seller_complete'
        session.save()
    except Exception as e:
        print(f"❌ Product creation error: {e}")
        send_telegram_message(chat_id, "❌ Sorry, there was an error adding your product. Please try /addproduct again.")
        session.state = 'seller_complete'
        session.save()

    return JsonResponse({'status': 'success'})

def handle_callback_query(callback_query):
"""Handle inline keyboard interactions""" # You can add this later for more interactive features
chat_id = callback_query['message']['chat']['id']
send_telegram_message(chat_id, "Interactive features coming soon!")
return JsonResponse({'status': 'success'})
