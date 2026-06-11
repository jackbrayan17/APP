from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.restaurants.models import Restaurant, Dish
from apps.promotions.models import PromoCode, PromoCodeRedemption
from .models import Order, OrderItem, Review


# ---------------- Panier (session) ----------------
def _get_cart(request):
    return request.session.get("cart", {})


def _save_cart(request, cart):
    request.session["cart"] = cart
    request.session.modified = True


def _cart_count(request):
    return sum(i.get("qty", 0) for i in _get_cart(request).values())


@require_POST
def cart_add(request, dish_id):
    dish = get_object_or_404(Dish, id=dish_id, is_available=True)
    cart = _get_cart(request)
    key = str(dish_id)
    if key in cart:
        cart[key]["qty"] += 1
    else:
        cart[key] = {
            "qty": 1,
            "name": dish.name,
            "price": dish.current_price,
            "restaurant_id": dish.restaurant_id,
            "restaurant_name": dish.restaurant.name,
            "image": dish.image.url if dish.image else "",
        }
    _save_cart(request, cart)
    return JsonResponse({"ok": True, "count": _cart_count(request)})


@require_POST
def cart_update(request, dish_id):
    cart = _get_cart(request)
    key = str(dish_id)
    qty = int(request.POST.get("qty") or 0)
    if key in cart:
        if qty <= 0:
            del cart[key]
        else:
            cart[key]["qty"] = qty
        _save_cart(request, cart)
    return JsonResponse({"ok": True, "count": _cart_count(request)})


def cart_view(request):
    cart = _get_cart(request)
    groups = defaultdict(lambda: {"items": [], "subtotal": 0, "name": ""})
    total = 0
    for key, item in cart.items():
        rid = item["restaurant_id"]
        line = item["price"] * item["qty"]
        groups[rid]["items"].append({"id": key, **item, "line": line})
        groups[rid]["subtotal"] += line
        groups[rid]["name"] = item["restaurant_name"]
        total += line
    return render(request, "client/cart.html", {
        "groups": dict(groups), "total": total, "cart_count": _cart_count(request)})


@login_required
@require_POST
def checkout(request):
    cart = _get_cart(request)
    if not cart:
        messages.error(request, "Votre panier est vide.")
        return redirect("orders:cart")

    address = request.POST.get("address") or request.user.address
    lat = request.POST.get("lat") or request.user.lat
    lng = request.POST.get("lng") or request.user.lng
    payment = request.POST.get("payment_method", "cash")
    promo_code_str = request.POST.get("promo_code", "").strip().upper()

    # Grouper par restaurant -> une commande par restaurant
    by_resto = defaultdict(list)
    for key, item in cart.items():
        by_resto[item["restaurant_id"]].append((key, item))

    created = []
    for rid, items in by_resto.items():
        resto = Restaurant.objects.get(id=rid)
        order = Order.objects.create(
            customer=request.user, restaurant=resto,
            delivery_address=address or "", payment_method=payment,
            delivery_fee=resto.delivery_fee,
            delivery_lat=float(lat) if lat else None,
            delivery_lng=float(lng) if lng else None,
        )
        for key, item in items:
            OrderItem.objects.create(
                order=order, dish_id=int(key), name=item["name"],
                unit_price=item["price"], quantity=item["qty"])
            Dish.objects.filter(id=int(key)).update(orders_count=models_F_inc())
        order.recompute_totals()

        # Code promo influenceur
        if promo_code_str:
            code = PromoCode.objects.filter(code=promo_code_str, restaurant=resto).first()
            if code and code.is_valid:
                disc = code.discount_for(order.items_total)
                order.discount = disc
                order.promo_code = code.code
                order.recompute_totals()
                code.uses += 1
                code.save(update_fields=["uses"])
                PromoCodeRedemption.objects.create(
                    promo_code=code, user=request.user, order=order, discount_amount=disc)
                code.influencer.recompute_score()

        resto.orders_count = resto.orders.count()
        resto.save(update_fields=["orders_count"])
        created.append(order)

        from apps.core.services import notify
        notify(resto.owner, f"Nouvelle commande {order.number}",
               f"{order.item_count} article(s) — {order.total} FCFA",
               url="/resto/commandes/")

    _save_cart(request, {})
    if len(created) == 1:
        return redirect("orders:detail", number=created[0].number)
    messages.success(request, f"{len(created)} commandes creees.")
    return redirect("orders:list")


# ---------------- Mes commandes ----------------
@login_required
def order_list(request):
    orders = Order.objects.filter(customer=request.user).select_related("restaurant")
    return render(request, "client/orders.html",
                  {"orders": orders, "cart_count": _cart_count(request)})


ORDER_STEPS = [
    ("confirmed", "Confirmée"),
    ("preparing", "Préparation"),
    ("on_the_way", "En route"),
    ("delivered", "Livrée"),
]
_STEP_RANK = {"pending": 0, "confirmed": 1, "preparing": 2, "ready": 2,
              "picked_up": 3, "on_the_way": 3, "delivered": 4}


@login_required
def order_detail(request, number):
    order = get_object_or_404(Order.objects.select_related("restaurant", "driver"),
                              number=number, customer=request.user)
    rank = _STEP_RANK.get(order.status, 0)
    done = [s for s, _ in ORDER_STEPS if _STEP_RANK.get(s, 99) <= rank]
    return render(request, "client/order_detail.html",
                  {"order": order, "steps": ORDER_STEPS, "done_steps": done,
                   "cart_count": _cart_count(request)})


def order_share(request, token):
    """Lien public de suivi/partage d'une commande."""
    order = get_object_or_404(Order.objects.select_related("restaurant"), share_token=token)
    return render(request, "share/order.html", {"order": order})


@login_required
def review_order(request, number):
    order = get_object_or_404(Order, number=number, customer=request.user)
    if not order.can_review:
        messages.info(request, "Cette commande ne peut pas etre notee.")
        return redirect("orders:detail", number=number)
    if request.method == "POST":
        Review.objects.create(
            order=order, customer=request.user, restaurant=order.restaurant,
            driver=order.driver,
            rating=int(request.POST.get("rating") or 5),
            driver_rating=int(request.POST.get("driver_rating") or 0) or None,
            comment=request.POST.get("comment", ""),
        )
        messages.success(request, "Merci pour votre avis !")
        return redirect("orders:detail", number=number)
    return render(request, "client/review.html", {"order": order})


def models_F_inc():
    from django.db.models import F
    return F("orders_count") + 1
