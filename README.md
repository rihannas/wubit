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
