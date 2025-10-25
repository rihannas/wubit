from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Buyer, Store, Product, Cart, CartItem,
    Wishlist, Order, OrderItem, Review, SellerSession, BuyerSession
)

# -------------------------------
# Custom User Admin
# -------------------------------
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'user_type', 'telegram_id', 'is_staff', 'is_active')
    list_filter = ('user_type', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('email', 'phone_number', 'national_id', 'telegram_id')}),
        ('Permissions', {'fields': ('user_type', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'user_type', 'email', 'password1', 'password2')}
        ),
    )
    search_fields = ('username', 'email', 'telegram_id')
    ordering = ('username',)
    filter_horizontal = ('groups', 'user_permissions',)

admin.site.register(User, UserAdmin)

# -------------------------------
# Buyer Admin
# -------------------------------
class BuyerAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user__username',)
    filter_horizontal = ('saved_products',)

admin.site.register(Buyer, BuyerAdmin)

# -------------------------------
# Store & Product Admin
# -------------------------------
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'seller', 'verified', 'created_at')
    search_fields = ('name', 'seller__username')
    list_filter = ('verified',)

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'price', 'stock_quantity', 'created_at')
    search_fields = ('name', 'store__name')
    list_filter = ('store',)

admin.site.register(Store, StoreAdmin)
admin.site.register(Product, ProductAdmin)

# -------------------------------
# Cart & Orders Admin
# -------------------------------
class CartAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'created_at')

class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'quantity', )

admin.site.register(Cart, CartAdmin)
admin.site.register(CartItem, CartItemAdmin)

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'total_amount', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('buyer__user__username',)

class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', )

admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)

# -------------------------------
# Wishlist & Reviews
# -------------------------------
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'product', 'created_at')

class ReviewAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'product', 'rating', 'text')

admin.site.register(Wishlist, WishlistAdmin)
admin.site.register(Review, ReviewAdmin)

# -------------------------------
# Seller & Buyer Sessions
# -------------------------------
class SellerSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'state', 'updated_at')

class BuyerSessionAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'created_at')

admin.site.register(SellerSession, SellerSessionAdmin)
admin.site.register(BuyerSession, BuyerSessionAdmin)
