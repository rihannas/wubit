
from django.contrib import admin
from .models import Store, Product, Cart, CartItem, Wishlist, Order, OrderItem, SellerSession

admin.site.register(Store)
admin.site.register(Product)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Wishlist)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(SellerSession)
