from django.urls import path
from . import views

# urlpatterns = [
#     # path('products/', views.products_list),
#     # path('cart/add/', views.add_to_cart),
#     # path('cart/', views.view_cart),
#     # path('cart/checkout/', views.cart_checkout),
#     # path('wishlist/add/', views.add_to_wishlist),
#     path('telegram/webhook/', views.telegram_webhook),
# ]

urlpatterns = [
    path('telegram/webhook/', views.telegram_webhook, name='telegram_webhook'),
]