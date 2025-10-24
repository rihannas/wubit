import os, json, requests
from decimal import Decimal
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .models import (
    User, Store, Product, Buyer, Cart, CartItem, Wishlist,
    Order, OrderItem, Review, SellerSession, BuyerSession,
)

# ---- Helpers (placeholders: replace with real API calls) ----
def send_telegram_message(chat_id, text):
    token = os.getenv('TELEGRAM_TOKEN') or settings.TELEGRAM_TOKEN
    if not token:
        print("No TELEGRAM_TOKEN set")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def translate_to_en(text):
    # Placeholder: call Google Translate or your translation API
    # Return (en_text, am_text_or_none)
    return text, text

def translate_to_am(text):
    # Placeholder for english -> amharic
    return text + " (Translated to Amharic)"

def openai_summarize(text):
    # Placeholder: call OpenAI summarize
    return "AI Summary: " + (text[:300])

# ---- Telegram webhook handler ----
@csrf_exempt
def telegram_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'ok'})

    body = json.loads(request.body.decode('utf-8'))
    if 'message' not in body:
        return JsonResponse({'status': 'ok'})

    msg = body['message']
    chat_id = msg['chat']['id']
    text = msg.get('text', '').strip()

    # Get or create a local user mapped to this telegram chat id
    username = f"tg_{chat_id}"
    user, created = User.objects.get_or_create(username=username, defaults={'telegram_id': str(chat_id)})
    if created:
        # basic defaults
        user.telegram_id = str(chat_id)
        user.save()

    # Ensure buyer profile and cart exists if user_type==buyer
    if user.user_type == 'buyer':
        Buyer.objects.get_or_create(user=user)
        # initialize cart for buyer
        buyer = user.buyer_profile
        Cart.objects.get_or_create(buyer=buyer)

    # Ensure store exists if user_type==seller
    if user.user_type == 'seller':
        # store may not be created yet; do not auto-create here
        pass

    # 1) If user_type not set, ask to choose
    if not user.user_type:
        if text.lower() in ['buyer', 'seller']:
            user.user_type = text.lower()
            user.save()
            # Create profiles
            if user.user_type == 'buyer':
                Buyer.objects.get_or_create(user=user)
                send_telegram_message(chat_id, "Registered as Buyer. Use /browse to see products.")
            else:
                send_telegram_message(chat_id, "Registered as Seller. Use /start_store to create your store.")
            return JsonResponse({'ok': True})
        else:
            send_telegram_message(chat_id, "Welcome! Are you a Buyer or Seller? Reply with 'Buyer' or 'Seller'.")
            return JsonResponse({'ok': True})

    # ----- SELLER COMMANDS -----
    if user.user_type == 'seller':
        # create store
        if text.startswith('/start_store'):
            # Ask for shop name if none
            store, created = Store.objects.get_or_create(seller=user, defaults={'name_en': f"{user.username}'s store"})
            if created:
                send_telegram_message(chat_id, f"Store created with name: {store.name_en}. Use /addproduct to add items.")
            else:
                send_telegram_message(chat_id, f"You already have a store: {store.name_en}. Use /addproduct to add items.")
            return JsonResponse({'ok': True})

        # start adding product
        if text.startswith('/addproduct'):
            sess, _ = SellerSession.objects.get_or_create(user=user)
            sess.state = 'adding_product_name'
            sess.metadata = {}
            sess.save()
            send_telegram_message(chat_id, "Send the product name (Amharic or English).")
            return JsonResponse({'ok': True})

        # seller session FSM
        sess = getattr(user, 'seller_session', None)
        if sess and sess.state:
            # name
            if sess.state == 'adding_product_name':
                sess.metadata['name'] = text
                sess.state = 'adding_product_price'
                sess.save()
                send_telegram_message(chat_id, "Got it. Send the price (number).")
                return JsonResponse({'ok': True})
            # price
            if sess.state == 'adding_product_price':
                try:
                    price = float(text)
                except:
                    send_telegram_message(chat_id, "Invalid price. Send a number like 250 or 250.00")
                    return JsonResponse({'ok': True})
                sess.metadata['price'] = price
                sess.state = 'adding_product_image'
                sess.save()
                send_telegram_message(chat_id, "Send image URL for the product (or type 'skip').")
                return JsonResponse({'ok': True})
            # image & finalize
            if sess.state == 'adding_product_image':
                image = text if text.lower() != 'skip' else None
                store = getattr(user, 'store', None)
                if not store:
                    store = Store.objects.create(seller=user, name_en=f"{user.username}'s store")
                name = sess.metadata.get('name')
                price = sess.metadata.get('price', 0)
                name_en, name_am = translate_to_en(name)
                Product.objects.create(
                    store=store,
                    name_en=name_en,
                    name_am=name_am,
                    price=Decimal(price),
                    image_url=image
                )
                sess.state = ''
                sess.metadata = {}
                sess.save()
                send_telegram_message(chat_id, f"Product '{name_en}' added successfully ✅")
                return JsonResponse({'ok': True})

        # view seller's products
        if text.startswith('/myproducts'):
            store = getattr(user, 'store', None)
            if not store:
                send_telegram_message(chat_id, "You don't have a store. Use /start_store to create one.")
                return JsonResponse({'ok': True})
            products = store.products.all()
            if not products:
                send_telegram_message(chat_id, "No products yet. Use /addproduct to add.")
                return JsonResponse({'ok': True})
            for p in products:
                saved_count = p.saved_by.count()  # from Wishlist relation
                send_telegram_message(chat_id, f"{p.name_en} — {p.price} ETB — Saved by: {saved_count}")
            return JsonResponse({'ok': True})

        # how many saved per product (alias to /myproducts or separate)
        if text.startswith('/saves'):
            store = getattr(user, 'store', None)
            if not store:
                send_telegram_message(chat_id, "No store found. Use /start_store.")
                return JsonResponse({'ok': True})
            lines = []
            for p in store.products.all():
                lines.append(f"{p.name_en}: {p.saved_by.count()} saves")
            send_telegram_message(chat_id, "\n".join(lines) if lines else "No products.")
            return JsonResponse({'ok': True})

        # insights (AI summarization + translation)
        if text.startswith('/insights'):
            store = getattr(user, 'store', None)
            if not store:
                send_telegram_message(chat_id, "No store found. Use /start_store.")
                return JsonResponse({'ok': True})
            # aggregate data
            all_items = OrderItem.objects.filter(product__store=store)
            total_qty = sum([oi.quantity for oi in all_items])
            revenue = sum([float(oi.price_snapshot) * oi.quantity for oi in all_items])
            saves = sum([p.saved_by.count() for p in store.products.all()])
            # build text for AI
            raw = f"Store {store.name_en}: sold_items={total_qty}, revenue={revenue}, total_saves={saves}."
            ai = openai_summarize(raw)
            am = translate_to_am(ai)
            send_telegram_message(chat_id, am)
            return JsonResponse({'ok': True})

    # ----- BUYER COMMANDS -----
    if user.user_type == 'buyer':
        # ensure buyer & cart
        buyer, _ = Buyer.objects.get_or_create(user=user)
        Cart.objects.get_or_create(buyer=buyer)

        # browse products
        if text.startswith('/browse') or text.startswith('/show_products'):
            qs = Product.objects.order_by('-created_at')[:15]
            if not qs:
                send_telegram_message(chat_id, "No products available yet.")
            else:
                for p in qs:
                    send_telegram_message(chat_id, f"{p.id}\n{p.name_en} — {p.price} ETB\n{p.image_url or ''}")
            return JsonResponse({'ok': True})

        # save: "/save <product_uuid>"
        if text.startswith('/save'):
            parts = text.split()
            if len(parts) < 2:
                send_telegram_message(chat_id, "Usage: /save <product_id>")
                return JsonResponse({'ok': True})
            pid = parts[1]
            try:
                prod = Product.objects.get(id=pid)
            except Product.DoesNotExist:
                send_telegram_message(chat_id, "Product not found.")
                return JsonResponse({'ok': True})
            Wishlist.objects.get_or_create(buyer=buyer, product=prod)
            send_telegram_message(chat_id, f"Saved '{prod.name_en}' for later ✅")
            return JsonResponse({'ok': True})

        # add to cart: "/addtocart <product_id> <qty>"
        if text.startswith('/addtocart'):
            parts = text.split()
            if len(parts) < 3:
                send_telegram_message(chat_id, "Usage: /addtocart <product_id> <quantity>")
                return JsonResponse({'ok': True})
            pid = parts[1]
            qty = int(parts[2])
            try:
                prod = Product.objects.get(id=pid)
            except Product.DoesNotExist:
                send_telegram_message(chat_id, "Product not found.")
                return JsonResponse({'ok': True})
            cart, _ = Cart.objects.get_or_create(buyer=buyer)
            ci, created = CartItem.objects.get_or_create(cart=cart, product=prod, defaults={'quantity': qty, 'price_snapshot': prod.price})
            if not created:
                ci.quantity += qty
                ci.save()
            send_telegram_message(chat_id, f"Added {qty} x '{prod.name_en}' to cart ✅")
            return JsonResponse({'ok': True})

        # view cart
        if text.startswith('/cart') or text.startswith('/view_cart'):
            cart = buyer.cart
            items = cart.items.all()
            if not items:
                send_telegram_message(chat_id, "Your cart is empty.")
                return JsonResponse({'ok': True})
            lines = []
            total = 0
            for it in items:
                lines.append(f"{it.product.name_en} — {it.quantity} x {it.price_snapshot} ETB")
                total += float(it.price_snapshot) * it.quantity
            lines.append(f"Total: {total} ETB")
            send_telegram_message(chat_id, "\n".join(lines))
            return JsonResponse({'ok': True})

        # checkout -> create order and provide payment link placeholder
        if text.startswith('/checkout'):
            cart = buyer.cart
            items = cart.items.all()
            if not items:
                send_telegram_message(chat_id, "Cart is empty.")
                return JsonResponse({'ok': True})
            total = sum([float(i.price_snapshot) * i.quantity for i in items])
            order = Order.objects.create(buyer=buyer, total_amount=Decimal(total), status='pending')
            for it in items:
                OrderItem.objects.create(order=order, product=it.product, quantity=it.quantity, price_snapshot=it.price_snapshot)
            items.delete()
            # payment link placeholder (replace with Chapa/Flutterwave integration)
            payment_link = f"https://example-payment-provider/pay?order_id={order.id}&amount={order.total_amount}"
            send_telegram_message(chat_id, f"Order created. Pay here: {payment_link}")
            return JsonResponse({'ok': True})

        # orders list (delivered or all)
        if text.startswith('/orders') or text.startswith('/myorders'):
            orders = buyer.orders.all().order_by('-created_at')
            if not orders:
                send_telegram_message(chat_id, "You have no orders yet.")
                return JsonResponse({'ok': True})
            for o in orders:
                send_telegram_message(chat_id, f"Order {o.id} — {o.status} — {o.total_amount} ETB")
                for item in o.items.all():
                    send_telegram_message(chat_id, f"  • {item.product.name_en} x {item.quantity}")
            return JsonResponse({'ok': True})

        
    # Default help
    help_text = (
        "Commands:\n"
        "If new: reply 'Buyer' or 'Seller' to register your role.\n\n"
        "Buyer commands:\n"
        "/browse or /show_products\n"
        "/save <product_id>\n"
        "/addtocart <product_id> <qty>\n"
        "/cart\n"
        "/checkout\n"
        "/orders\n"
        "/review <order_item_id>\n\n"
        "Seller commands:\n"
        "/start_store\n"
        "/addproduct\n"
        "/myproducts\n"
        "/saves\n"
        "/insights\n"
    )
    send_telegram_message(chat_id, help_text)
    return JsonResponse({'ok': True})
