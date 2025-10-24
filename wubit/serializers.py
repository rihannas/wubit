from rest_framework import serializers
from .models import Product, CartItem, Cart, Wishlist, Order, OrderItem, Store

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    class Meta:
        model = CartItem
        fields = ['id','product','quantity','price_snapshot']

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()
    class Meta:
        model = Cart
        fields = ['id','user','items','total_price']
    def get_total_price(self, obj):
        total = 0
        for it in obj.items.all():
            total += float(it.price_snapshot) * it.quantity
        return total

class WishlistSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    class Meta:
        model = Wishlist
        fields = ['id','product','created_at']
