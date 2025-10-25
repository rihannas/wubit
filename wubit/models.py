# models.py (FINAL - Dual Role System)
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid
from decimal import Decimal
from django.core.validators import RegexValidator


# -------------------- USER --------------------
class User(AbstractUser):
    telegram_id = models.CharField(
        max_length=50, 
        unique=True,
        blank=True,
        null=True
    )
    phone_number = models.CharField(
        max_length=20, 
        blank=True,
        null=True
    )
    national_id = models.CharField(
        max_length=12,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r'^\d{12}$',
                message='National ID must be exactly 12 digits.'
            )
        ]
    )

    # Dual role tracking
    is_seller = models.BooleanField(default=False)
    is_buyer = models.BooleanField(default=False)

    def activate_seller(self):
        """Activate seller role"""
        self.is_seller = True
        self.save()

    def activate_buyer(self):
        """Activate buyer role"""
        self.is_buyer = True
        self.save()

    def has_store(self):
        """Check if user has a store"""
        return hasattr(self, 'store')

    def has_buyer_profile(self):
        """Check if user has buyer profile"""
        return hasattr(self, 'buyer_profile')

    def clean(self):
        if not self.telegram_id and self.username.startswith('tg_'):
            self.telegram_id = self.username.replace('tg_', '')

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
        roles = []
        if self.is_seller:
            roles.append("Seller")
        if self.is_buyer:
            roles.append("Buyer")
        roles_str = " + ".join(roles) if roles else "No Role"
        return f"{self.username} ({roles_str})"


# -------------------- STORE --------------------
class Store(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='store'
    )
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
    
    # Performance tracking
    views_count = models.IntegerField(default=0)
    saves_count = models.IntegerField(default=0)
    orders_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} ({self.store})"


# -------------------- BUYER --------------------
class Buyer(models.Model):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='buyer_profile'
    )
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

    class Meta:
        unique_together = ['buyer', 'product']


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
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='seller_session'
    )
    state = models.CharField(max_length=100, blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SellerSession({self.user.username})"


# -------------------- BUYER SESSION --------------------
class BuyerSession(models.Model):
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, related_name='buyer_sessions')
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"BuyerSession({self.buyer.user.username})"


# -------------------- PERFORMANCE TRACKING --------------------
class ProductView(models.Model):
    """Track individual product views"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='view_events')
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE, null=True, blank=True)
    viewed_at = models.DateTimeField(default=timezone.now)
    user_identifier = models.CharField(max_length=100, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['product', 'viewed_at']),
        ]


class ProductSave(models.Model):
    """Track when users save products to wishlist"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='save_events')
    buyer = models.ForeignKey(Buyer, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['product', 'buyer']


class ProductOrder(models.Model):
    """Track product orders"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='order_events')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='product_orders')
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    ordered_at = models.DateTimeField(default=timezone.now)