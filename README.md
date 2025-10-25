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
