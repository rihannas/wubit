import os, json, requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Product, Cart, CartItem, Wishlist, Store, Order, OrderItem, SellerSession
from .serializers import ProductSerializer, CartSerializer, WishlistSerializer
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from decimal import Decimal

User = get_user_model()

# ---- Helper functions (placeholders for translation + AI) ----
def translate_to_en(text):
    # Placeholder: call Google Translate or your translation API
    # Return tuple (en_text, am_text)
    # For now, naive return:
    return text, text

def translate_to_am(text):
    # Placeholder for English -> Amharic translation
    return text + " (Amharic translation)"

def openai_summarize(text):
    # Use OpenAI API to summarize, then return string
    # Placeholder implementation
    return "AI Summary: " + text[:300]

def send_telegram_message(chat_id, text):
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        print("No TELEGRAM_TOKEN set")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

# ---- Public API endpoints ----

@api_view(['GET'])
@permission_classes([AllowAny])
def products_list(request):
    q = request.GET.get('q')
    if q:
        qs = Product.objects.filter(name_en__icontains=q) | Product.objects.filter(name_am__icontains=q)
    else:
        qs = Product.objects.all()
    serializer = ProductSerializer(qs, many=True)
    return JsonResponse(serializer.data, safe=False)

@api_view(['POST'])
def add_to_cart(request):
    user = request.user
    data = request.data
    product_id = data.get('product_id')
    qty = int(data.get('quantity', 1))
    product = get_object_or_404(Product, id=product_id)
    cart, _ = Cart.objects.get_or_create(user=user)
    ci = CartItem.objects.create(cart=cart, product=product, quantity=qty, price_snapshot=product.price)
    return JsonResponse({'ok': True, 'cart_item_id': ci.id})

@api_view(['GET'])
def view_cart(request):
    user = request.user
    cart, _ = Cart.objects.get_or_create(user=user)
    serializer = CartSerializer(cart)
    return JsonResponse(serializer.data, safe=False)

@api_view(['POST'])
def cart_checkout(request):
    user = request.user
    cart, _ = Cart.objects.get_or_create(user=user)
    items = cart.items.all()
    if not items.exists():
        return JsonResponse({'error': 'Cart empty'}, status=400)
    total = sum([float(i.price_snapshot)*i.quantity for i in items])
    order = Order.objects.create(customer=user, total_amount=Decimal(total), status='pending')
    for i in items:
        OrderItem.objects.create(order=order, product=i.product, quantity=i.quantity, price_snapshot=i.price_snapshot)
    # Clear cart
    items.delete()
    # Create payment link with provider (placeholder)
    payment_link = f"https://example-payment-provider/pay?order_id={order.id}&amount={order.total_amount}"
    return JsonResponse({'ok': True, 'order_id': str(order.id), 'payment_link': payment_link})

@api_view(['POST'])
def add_to_wishlist(request):
    user = request.user
    pid = request.data.get('product_id')
    product = get_object_or_404(Product, id=pid)
    w, _ = Wishlist.objects.get_or_create(user=user, product=product)
    return JsonResponse({'ok': True})

# ---- Telegram webhook handler ----
@csrf_exempt
def telegram_webhook(request):
    """
    Receives Telegram updates (set webhook to /telegram/webhook/)
    Very simple command/state handler for MVP
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'ok'})
    body = json.loads(request.body.decode('utf-8'))
    if 'message' not in body:
        return JsonResponse({'status': 'ok'})
    msg = body['message']
    chat_id = msg['chat']['id']
    text = msg.get('text','').strip()
    # Find or create user by chat id (simple mapping; for production map phone with verification)
    user, _ = User.objects.get_or_create(username=f"tg_{chat_id}")
    # Initialize cart if needed
    Cart.objects.get_or_create(user=user)
    # Basic command handling
    # /start_store
    if text.startswith('/start_store'):
        # create store placeholder
        Store.objects.get_or_create(seller=user, defaults={'name_en': f"{user.username}'s store"})
        send_telegram_message(chat_id, "Store created. Send /add_product to add your first product.")
        return JsonResponse({'ok': True})
    if text.startswith('/add_product'):
        # set session state
        sess, _ = SellerSession.objects.get_or_create(user=user)
        sess.state = 'adding_product_name'
        sess.data = {}
        sess.save()
        send_telegram_message(chat_id, "Please send the product name (in Amharic or English).")
        return JsonResponse({'ok': True})
    # State machine for adding product
    sess = getattr(user, 'seller_session', None)
    if sess and sess.state:
        if sess.state == 'adding_product_name':
            name = text
            sess.data['name'] = name
            sess.state = 'adding_product_price'
            sess.save()
            send_telegram_message(chat_id, "Got it. Now send the price (number).")
            return JsonResponse({'ok': True})
        if sess.state == 'adding_product_price':
            try:
                price = float(text)
            except:
                send_telegram_message(chat_id, "Invalid price. Send a number like 250 or 250.00")
                return JsonResponse({'ok': True})
            sess.data['price'] = price
            sess.state = 'adding_product_image'
            sess.save()
            send_telegram_message(chat_id, "Great. Now send an image URL for the product (or type 'skip').")
            return JsonResponse({'ok': True})
        if sess.state == 'adding_product_image':
            image = text
            # finish: create product
            store = getattr(user, 'store', None)
            if not store:
                store = Store.objects.create(seller=user, name_en=f"{user.username}'s store")
            name = sess.data.get('name')
            price = sess.data.get('price')
            # translation placeholder
            name_en, name_am = translate_to_en(name)
            p = Product.objects.create(store=store, name_en=name_en, name_am=name_am, price=Decimal(price), image_url=image)
            sess.state = ''
            sess.data = {}
            sess.save()
            send_telegram_message(chat_id, f"Product '{name_en}' added successfully ✅")
            return JsonResponse({'ok': True})
    # Other commands
    if text.startswith('/show_products'):
        qs = Product.objects.all()[:10]
        for p in qs:
            txt = f"{p.name_en} - {p.price} ETB\nProduct ID: {p.id}"
            send_telegram_message(chat_id, txt)
        return JsonResponse({'ok': True})
    if text.startswith('/view_cart'):
        cart, _ = Cart.objects.get_or_create(user=user)
        items = cart.items.all()
        if not items:
            send_telegram_message(chat_id, "Your cart is empty.")
        else:
            lines = []
            total=0
            for it in items:
                lines.append(f"{it.product.name_en} - {it.quantity} x {it.price_snapshot} ETB")
                total += float(it.price_snapshot)*it.quantity
            lines.append(f"Total: {total} ETB")
            send_telegram_message(chat_id, "\n".join(lines))
        return JsonResponse({'ok': True})
    if text.startswith('/checkout'):
        cart, _ = Cart.objects.get_or_create(user=user)
        items = cart.items.all()
        if not items:
            send_telegram_message(chat_id, "Cart empty.")
            return JsonResponse({'ok': True})
        total = sum([float(i.price_snapshot)*i.quantity for i in items])
        order = Order.objects.create(customer=user, total_amount=Decimal(total), status='pending')
        for i in items:
            OrderItem.objects.create(order=order, product=i.product, quantity=i.quantity, price_snapshot=i.price_snapshot)
        items.delete()
        # Payment link placeholder
        payment_link = f"https://example-payment-provider/pay?order_id={order.id}&amount={order.total_amount}"
        send_telegram_message(chat_id, f"Checkout created. Pay here: {payment_link}")
        return JsonResponse({'ok': True})
    if text.startswith('/my_sales'):
        # simple sales aggregation for this seller's store
        store = getattr(user, 'store', None)
        if not store:
            send_telegram_message(chat_id, "You don't have a store yet. /start_store")
            return JsonResponse({'ok': True})
        orders = OrderItem.objects.filter(product__store=store)
        total_qty = sum([oi.quantity for oi in orders])
        summary = f"Total items sold (all time): {total_qty}"
        # AI summary placeholder
        ai_text = openai_summarize(summary)
        # translate to Amharic
        am = translate_to_am(ai_text)
        send_telegram_message(chat_id, am)
        return JsonResponse({'ok': True})
    # Default help
    send_telegram_message(chat_id, "Commands:\n/start_store\n/add_product\n/show_products\n/view_cart\n/checkout\n/my_sales")
    return JsonResponse({'ok': True})
