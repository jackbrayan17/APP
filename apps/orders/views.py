from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from apps.accounts.models import Address
from apps.core.inputs import clean_float
from apps.restaurants.models import Dish
from .models import Order, Review
from .services import (PAYMENT_CHOICES, CheckoutError, build_cart_groups, create_orders,
                       reorder_lines, resolve_cart_lines, line_key)
from .workflow import TransitionError, confirm_mobile_money, customer_cancel, customer_validate


# ---------------- Panier ----------------
# Session : {ligne: {"qty": n}}. La ligne est l'id du plat (« 12 ») ou, avec des
# complements, « 12:34-56 » (plat 12 + options 34 et 56). Les anciens paniers restent valides.
def _get_cart(request):
    return request.session.get("cart", {})


def _save_cart(request, cart):
    request.session["cart"] = cart
    request.session.modified = True


def _cart_count(request):
    return sum(i.get("qty", 0) for i in _get_cart(request).values())


def _clean_option_ids(raw_values):
    """Identifiants de complements envoyes par le client : entiers uniques, 20 max."""
    ids = {int(v) for v in raw_values if str(v).isdigit()}
    return sorted(ids)[:20]


def _cart_entries(request):
    entries = []
    for key, entry in _get_cart(request).items():
        head, _, tail = str(key).partition(":")
        if not head.isdigit():
            continue
        option_ids = [int(x) for x in tail.split("-") if x.isdigit()]
        qty = entry.get("qty", 0) if isinstance(entry, dict) else 0
        entries.append((int(head), int(qty or 0), option_ids, key))
    return entries


def _cart_lines(request):
    """(lignes, problemes) avec les prix actuels (jamais ceux figes en session)."""
    return resolve_cart_lines(_cart_entries(request))


@require_POST
def cart_add(request, dish_id):
    dish = get_object_or_404(Dish.objects.select_related("restaurant"), id=dish_id, is_available=True)
    option_ids = _clean_option_ids(request.POST.getlist("options"))
    try:
        qty = max(1, min(50, int(request.POST.get("qty") or 1)))
    except ValueError:
        qty = 1
    key = line_key(dish_id, option_ids)
    _, problems = resolve_cart_lines([(dish_id, qty, option_ids, key)])
    if problems:
        return JsonResponse({"ok": False, "error": problems[0],
                             "count": _cart_count(request)}, status=400)
    cart = _get_cart(request)
    cart[key] = {"qty": cart.get(key, {}).get("qty", 0) + qty}
    _save_cart(request, cart)
    return JsonResponse({"ok": True, "count": _cart_count(request),
                         "name": dish.name, "open": dish.restaurant.is_open_now,
                         "status": dish.restaurant.opening_status_label})


@require_POST
def cart_update(request, key):
    cart = _get_cart(request)
    try:
        qty = max(0, min(50, int(request.POST.get("qty") or 0)))
    except ValueError:
        qty = 0
    if key in cart:
        if qty == 0:
            del cart[key]
        else:
            cart[key]["qty"] = qty
        _save_cart(request, cart)
    return JsonResponse({"ok": True, "count": _cart_count(request)})


def cart_view(request):
    lines, problems = _cart_lines(request)
    for problem in problems:
        messages.warning(request, problem)
    groups = build_cart_groups(lines)
    addresses = request.user.addresses.all() if request.user.is_authenticated else []
    return render(request, "client/cart.html", {
        "groups": groups,
        "items_total": sum(g["subtotal"] for g in groups),
        "fees_total": sum(g["delivery_fee"] for g in groups),
        "grand_total": sum(g["total"] for g in groups),
        "has_blockers": any(g["blockers"] for g in groups),
        "addresses": addresses,
        "payment_choices": PAYMENT_CHOICES,
        "cart_count": _cart_count(request),
    })


@login_required
@require_POST
def checkout(request):
    post = request.POST
    address, lat, lng = post.get("address", ""), post.get("lat"), post.get("lng")
    saved = post.get("address_id", "")
    if saved.isdigit():
        addr = Address.objects.filter(id=int(saved), user=request.user).first()
        if addr:
            address = addr.address + (f" — {addr.instructions}" if addr.instructions else "")
            lat, lng = addr.lat, addr.lng
    elif address and post.get("save_address") == "on":
        Address.objects.create(user=request.user, label=(post.get("address_label") or "Domicile")[:40],
                               address=address[:255],
                               lat=clean_float(lat, lo=-90, hi=90),
                               lng=clean_float(lng, lo=-180, hi=180),
                               is_default=not request.user.addresses.exists())
    lines, problems = _cart_lines(request)
    if problems:
        messages.error(request, problems[0])
        return redirect("orders:cart")
    try:
        orders = create_orders(
            request.user, lines, address=address, lat=lat, lng=lng,
            payment_method=post.get("payment_method", "cash"),
            payment_phone=post.get("payment_phone", ""),
            notes=post.get("notes", ""), promo_code=post.get("promo_code", ""))
    except CheckoutError as exc:
        messages.error(request, str(exc))
        return redirect("orders:cart")

    _save_cart(request, {})
    if not request.user.address:
        request.user.address = address[:255]
        request.user.save(update_fields=["address"])
    first = orders[0]
    if first.is_awaiting_payment:
        request.session["pay_batch"] = [o.number for o in orders]
        return redirect("orders:payment", number=first.number)
    if len(orders) > 1:
        messages.success(request, f"{len(orders)} commandes envoyées aux restaurants.")
        return redirect("orders:list")
    return redirect("orders:detail", number=first.number)


@login_required
def payment(request, number):
    """Validation Mobile Money (simulee pour la demo : aucun debit reel)."""
    order = get_object_or_404(Order.objects.select_related("restaurant"),
                              number=number, customer=request.user)
    if not order.is_awaiting_payment:
        return redirect("orders:detail", number=number)
    batch = request.session.get("pay_batch") or []
    numbers = batch if number in batch else [number]
    pending = list(Order.objects.filter(customer=request.user, number__in=numbers,
                                        status=Order.Status.PENDING,
                                        payment_status=Order.PaymentStatus.PENDING)
                   .select_related("restaurant"))
    if request.method == "POST":
        if request.POST.get("action") == "cancel":
            for o in pending:
                customer_cancel(o, "Paiement Mobile Money abandonné.")
            messages.info(request, "Paiement abandonné, commande annulée.")
            return redirect("orders:list")
        for o in pending:
            confirm_mobile_money(o)
        messages.success(request, "Paiement confirmé ✅ Le restaurant a reçu votre commande.")
        if len(pending) > 1:
            return redirect("orders:list")
        return redirect("orders:detail", number=number)
    return render(request, "client/payment.html", {
        "order": order, "orders": pending,
        "amount": sum(o.total for o in pending),
        "ussd": "*126#" if order.payment_method == "momo" else "#150*50#",
    })


# ---------------- Mes commandes ----------------
@login_required
def order_list(request):
    orders = (Order.objects.filter(customer=request.user)
              .select_related("restaurant").prefetch_related("items"))
    active = [o for o in orders if o.is_active]
    past = [o for o in orders if not o.is_active]
    return render(request, "client/orders.html",
                  {"active_orders": active, "past_orders": past, "cart_count": _cart_count(request)})


ORDER_STEPS = [
    (0, "Envoyée", "created_at"),
    (1, "Acceptée", "confirmed_at"),
    (2, "En cuisine", "ready_at"),
    (3, "En route", "picked_up_at"),
    (4, "Livrée", "delivered_at"),
]


def _steps(order):
    current = order.progress_step
    return [{"index": i, "label": label, "done": i <= current and order.status != "cancelled",
             "current": i == current, "at": getattr(order, attr)} for i, label, attr in ORDER_STEPS]


@login_required
def order_detail(request, number):
    order = get_object_or_404(
        Order.objects.select_related("restaurant", "driver", "driver__driver_profile"),
        number=number, customer=request.user)
    return render(request, "client/order_detail.html",
                  {"order": order, "steps": _steps(order), "cart_count": _cart_count(request)})


@login_required
def order_status_json(request, number):
    """Etat leger pour le rafraichissement automatique de la page commande."""
    order = get_object_or_404(Order.objects.select_related("driver"),
                              number=number, customer=request.user)
    return JsonResponse({
        "status": order.status, "label": order.status_label,
        "text": order.customer_status_text, "step": order.progress_step,
        "driver": order.driver.display_name if order.driver else None,
        "updated": order.updated_at.isoformat(),
    })


@login_required
@require_POST
def order_cancel(request, number):
    order = get_object_or_404(Order, number=number, customer=request.user)
    try:
        customer_cancel(order)
        messages.success(request, "Commande abandonnée.")
    except TransitionError as exc:
        messages.error(request, str(exc))
    return redirect("orders:detail", number=number)


@login_required
@require_POST
def reorder(request, number):
    """Commander a nouveau en un clic : remet les plats disponibles dans le panier."""
    order = get_object_or_404(Order, number=number, customer=request.user)
    lines = reorder_lines(order)
    if not lines:
        messages.error(request, "Ces plats ne sont plus disponibles.")
        return redirect("orders:detail", number=number)
    cart = _get_cart(request)
    for line in lines:
        cart[line.key] = {"qty": cart.get(line.key, {}).get("qty", 0) + line.qty}
    _save_cart(request, cart)
    missing = order.items.count() - len(lines)
    msg = "Plats ajoutés au panier."
    if missing:
        msg += f" {missing} plat(s) ne sont plus disponibles."
    messages.success(request, msg)
    return redirect("orders:cart")


def order_share(request, token):
    """Lien public de suivi/partage d'une commande."""
    order = get_object_or_404(Order.objects.select_related("restaurant"), share_token=token)
    return render(request, "share/order.html", {"order": order})


@login_required
def validate_delivery(request, number):
    """Page de validation : le client saisit (ou scanne) le code et note la livraison."""
    order = get_object_or_404(Order.objects.select_related("restaurant", "driver"),
                              number=number, customer=request.user)
    if request.method == "POST":
        try:
            customer_validate(order, request.user, request.POST.get("code", ""),
                              rating=request.POST.get("rating"),
                              driver_rating=request.POST.get("driver_rating"),
                              comment=request.POST.get("comment", ""))
            messages.success(request, "Livraison validée. Merci pour votre avis !")
            return redirect("orders:detail", number=number)
        except TransitionError as exc:
            messages.error(request, str(exc))
            order.refresh_from_db()
    prefilled = request.GET.get("code", "") if request.method == "GET" else ""
    return render(request, "client/validate.html", {
        "order": order, "prefilled_code": prefilled, "cart_count": _cart_count(request),
    })


@login_required
def review_order(request, number):
    order = get_object_or_404(Order.objects.select_related("restaurant", "driver"),
                              number=number, customer=request.user)
    if not order.can_review:
        messages.info(request, "Cette commande ne peut pas être notée.")
        return redirect("orders:detail", number=number)
    if request.method == "POST":
        def stars(name, default=None):
            try:
                return max(1, min(5, int(request.POST.get(name))))
            except (TypeError, ValueError):
                return default
        Review.objects.create(
            order=order, customer=request.user, restaurant=order.restaurant,
            driver=order.driver, rating=stars("rating", 5),
            driver_rating=stars("driver_rating") if order.driver else None,
            comment=request.POST.get("comment", "")[:1000],
        )
        messages.success(request, "Merci pour votre avis !")
        return redirect("orders:detail", number=number)
    return render(request, "client/review.html", {"order": order})
