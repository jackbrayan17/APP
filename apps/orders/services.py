"""Creation des commandes (panier web et API mobile partagent la meme logique)."""
from collections import defaultdict

from django.db import transaction
from django.db.models import F

from apps.promotions.models import PromoCode, PromoCodeRedemption
from apps.restaurants.models import Dish, Restaurant
from .models import Order, OrderItem
from .workflow import announce_new_order

# Moyens de paiement proposes dans le MVP (carte bancaire : version ulterieure).
PAYMENT_CHOICES = [
    ("cash", "Espèces à la livraison", "Payez le livreur à la réception"),
    ("momo", "MTN Mobile Money", "Validation sur votre téléphone"),
    ("om", "Orange Money", "Validation sur votre téléphone"),
]
MOBILE_MONEY = {"momo", "om"}


class CheckoutError(Exception):
    pass


def restaurant_blockers(resto, subtotal):
    """Raisons empechant de commander chez ce restaurant (liste vide = OK)."""
    issues = []
    if not resto.is_active:
        issues.append(f"{resto.name} n'est plus disponible sur ONE EAT.")
    elif not resto.is_open_now:
        issues.append(f"{resto.name} est fermé ({resto.opening_status_label}).")
    if resto.min_order and subtotal < resto.min_order:
        issues.append(f"Minimum de commande chez {resto.name} : {resto.min_order} FCFA.")
    return issues


def build_cart_groups(lines):
    """lines = [(dish, qty)] -> groupes par restaurant avec totaux et blocages."""
    groups = defaultdict(lambda: {"items": [], "subtotal": 0})
    for dish, qty in lines:
        g = groups[dish.restaurant_id]
        g["restaurant"] = dish.restaurant
        price = dish.current_price
        g["items"].append({"dish": dish, "qty": qty, "price": price, "line": price * qty})
        g["subtotal"] += price * qty
    out = []
    for g in groups.values():
        r = g["restaurant"]
        g["delivery_fee"] = r.delivery_fee
        g["total"] = g["subtotal"] + r.delivery_fee
        g["blockers"] = restaurant_blockers(r, g["subtotal"])
        out.append(g)
    return out


@transaction.atomic
def create_orders(user, lines, *, address, lat=None, lng=None, payment_method="cash",
                  payment_phone="", notes="", promo_code=""):
    """Cree une commande par restaurant. Leve CheckoutError si le panier est invalide."""
    lines = [(d, q) for d, q in lines if q > 0]
    if not lines:
        raise CheckoutError("Votre panier est vide.")
    if payment_method not in {c[0] for c in PAYMENT_CHOICES}:
        raise CheckoutError("Moyen de paiement non disponible.")
    if payment_method in MOBILE_MONEY and len("".join(ch for ch in payment_phone if ch.isdigit())) < 9:
        raise CheckoutError("Indiquez le numéro Mobile Money à débiter.")
    if not (address or "").strip():
        raise CheckoutError("Indiquez une adresse de livraison.")

    unavailable = [d.name for d, _ in lines if not d.is_available]
    if unavailable:
        raise CheckoutError(f"Plus disponible : {', '.join(unavailable)}.")
    groups = build_cart_groups(lines)
    for g in groups:
        if g["blockers"]:
            raise CheckoutError(g["blockers"][0])

    code_str = (promo_code or "").strip().upper()
    created = []
    for g in groups:
        resto = g["restaurant"]
        order = Order.objects.create(
            customer=user, restaurant=resto,
            delivery_address=address.strip()[:255], notes=(notes or "").strip(),
            delivery_lat=float(lat) if lat not in (None, "") else None,
            delivery_lng=float(lng) if lng not in (None, "") else None,
            payment_method=payment_method,
            payment_phone=payment_phone.strip()[:20] if payment_method in MOBILE_MONEY else "",
            payment_status=(Order.PaymentStatus.PENDING if payment_method in MOBILE_MONEY
                            else Order.PaymentStatus.ON_DELIVERY),
            delivery_fee=resto.delivery_fee,
        )
        for it in g["items"]:
            OrderItem.objects.create(order=order, dish=it["dish"], name=it["dish"].name,
                                     unit_price=it["price"], quantity=it["qty"])
            Dish.objects.filter(pk=it["dish"].pk).update(orders_count=F("orders_count") + it["qty"])
        order.recompute_totals()

        if code_str:
            code = PromoCode.objects.filter(code=code_str, restaurant=resto).first()
            if code and code.is_valid:
                disc = code.discount_for(order.items_total)
                order.discount, order.promo_code = disc, code.code
                order.recompute_totals()
                PromoCode.objects.filter(pk=code.pk).update(uses=F("uses") + 1)
                PromoCodeRedemption.objects.create(
                    promo_code=code, user=user, order=order, discount_amount=disc)
                code.influencer.recompute_score()

        Restaurant.objects.filter(pk=resto.pk).update(orders_count=F("orders_count") + 1)
        if not order.is_awaiting_payment:
            announce_new_order(order)
        created.append(order)
    return created


def reorder_lines(order):
    """Plats encore disponibles d'une ancienne commande -> lignes panier."""
    lines = []
    for item in order.items.select_related("dish", "dish__restaurant"):
        if item.dish and item.dish.is_available:
            lines.append((item.dish, item.quantity))
    return lines
