from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid
from decimal import Decimal
from django.core.validators import RegexValidator


# -------------------- USER --------------------
class User(AbstractUser):
    USER_TYPES = (
        ('seller', 'Seller'),
        ('buyer', 'Buyer'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPES)
    telegram_id = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=20)
    national_id = models.CharField( max_length=12,
        validators=[
            RegexValidator(
                regex=r'^\d{12}$',
                message='National ID must be exactly 12 digits.'
            )
        ],)

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
    limage = models.ImageField(upload_to='logo_images/', blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


# -------------------- PRODUCT --------------------
class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    stock_quantity = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} ({self.store})"


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
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name='buyer_sessions')  # Fixed: Changed from settings.AUTH_USER_MODEL to Buyer
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"BuyerSession({self.buyer.user.username})"