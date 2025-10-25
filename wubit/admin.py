# admin.py (FIXED - for dual role system)
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Store, Product, Buyer, Cart, CartItem, Wishlist, Order, OrderItem, Review, SellerSession, BuyerSession

# Custom User Admin for dual roles
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'telegram_id', 'display_roles', 'phone_number', 'is_staff')
    list_filter = ('is_seller', 'is_buyer', 'is_staff', 'is_superuser')
    search_fields = ('username', 'telegram_id', 'phone_number', 'first_name', 'last_name')
    ordering = ('username',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Wubit Information', {
            'fields': ('telegram_id', 'phone_number', 'national_id', 'is_seller', 'is_buyer')
        }),
    )
    
    def display_roles(self, obj):
        roles = []
        if obj.is_seller:
            roles.append("Seller")
        if obj.is_buyer:
            roles.append("Buyer")
        return ", ".join(roles) if roles else "No Role"
    display_roles.short_description = 'Roles'

# Store Admin
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'seller', 'location', 'verified', 'created_at')
    list_filter = ('verified', 'created_at')
    search_fields = ('name', 'seller__username', 'location')
    readonly_fields = ('created_at',)

# Product Admin  
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'price', 'stock_quantity', 'views_count', 'orders_count', 'created_at')
    list_filter = ('store', 'created_at')
    search_fields = ('name', 'store__name')
    readonly_fields = ('created_at', 'views_count', 'saves_count', 'orders_count')

# Buyer Admin
class BuyerAdmin(admin.ModelAdmin):
    list_display = ('user', 'saved_products_count')
    filter_horizontal = ('saved_products',)
    
    def saved_products_count(self, obj):
        return obj.saved_products.count()
    saved_products_count.short_description = 'Saved Products'

# Cart Admin
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1

class CartAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'items_count', 'created_at')
    inlines = [CartItemInline]
    
    def items_count(self, obj):
        return obj.items.count()
    items_count.short_description = 'Items'

# Order Admin
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    inlines = [OrderItemInline]
    readonly_fields = ('created_at',)

# Review Admin
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'product', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('buyer__user__username', 'product__name')
    readonly_fields = ('created_at',)

# Seller Session Admin
class SellerSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'state', 'updated_at')
    list_filter = ('state', 'updated_at')
    readonly_fields = ('updated_at',)

# Buyer Session Admin
class BuyerSessionAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'created_at')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)

# Register all models
admin.site.register(User, CustomUserAdmin)
admin.site.register(Store, StoreAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Buyer, BuyerAdmin)
admin.site.register(Cart, CartAdmin)
admin.site.register(Wishlist)
admin.site.register(Order, OrderAdmin)
admin.site.register(Review, ReviewAdmin)
admin.site.register(SellerSession, SellerSessionAdmin)
admin.site.register(BuyerSession, BuyerSessionAdmin)

# Optional: Register tracking models if you want them in admin
from .models import ProductView, ProductSave, ProductOrder

class ProductViewAdmin(admin.ModelAdmin):
    list_display = ('product', 'buyer', 'viewed_at')
    list_filter = ('viewed_at',)
    readonly_fields = ('viewed_at',)

class ProductSaveAdmin(admin.ModelAdmin):
    list_display = ('product', 'buyer', 'saved_at')
    list_filter = ('saved_at',)
    readonly_fields = ('saved_at',)

class ProductOrderAdmin(admin.ModelAdmin):
    list_display = ('product', 'order', 'quantity', 'unit_price', 'ordered_at')
    list_filter = ('ordered_at',)
    readonly_fields = ('ordered_at',)

admin.site.register(ProductView, ProductViewAdmin)
admin.site.register(ProductSave, ProductSaveAdmin)
admin.site.register(ProductOrder, ProductOrderAdmin)