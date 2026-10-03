"""Creation des commandes (panier web et API mobile partagent la meme logique)."""
from collections import defaultdict
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.inputs import clean_phone
from apps.promotions.models import PromoCode, PromoCodeRedemption
from apps.restaurants.models import Dish, DishOption, Restaurant
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


@dataclass
class CartLine:
    """Une ligne du panier : un plat, sa quantite et les complements choisis."""
    dish: Dish
    qty: int
    options: list = field(default_factory=list)
    key: str = ""


def resolve_cart_lines(entries):
    """entries = [(dish_id, qty, option_ids, key)] -> (lignes, problemes).

    Les problemes (plat supprime, supplement indisponible) sont renvoyes au lieu
    d'etre ignores : le client doit savoir ce qui ne sera pas commande.
    """
    dishes = {d.id: d for d in Dish.objects.filter(
        id__in={e[0] for e in entries}).select_related("restaurant")}
    options = {o.id: o for o in DishOption.objects.filter(
        id__in={oid for e in entries for oid in e[2]}).select_related("dish")}
    lines, problems = [], []
    for dish_id, qty, option_ids, key in entries:
        dish = dishes.get(dish_id)
        if dish is None:
            problems.append("Un plat de votre panier n'existe plus et a été retiré.")
            continue
        if qty <= 0:
            continue
        chosen = []
        for oid in option_ids:
            opt = options.get(oid)
            if opt is None or opt.dish_id != dish.id:
                problems.append(f"Supplément introuvable pour {dish.name}.")
            elif not opt.is_available:
                problems.append(f"« {opt.name} » n'est plus disponible pour {dish.name}.")
            else:
                chosen.append(opt)
        lines.append(CartLine(dish=dish, qty=qty, options=chosen, key=key))
    return lines, problems


def line_key(dish_id, option_ids):
    """Cle de ligne du panier : « 12 » ou « 12:34-56 » (plat + complements)."""
    return f"{dish_id}:{'-'.join(map(str, option_ids))}" if option_ids else str(dish_id)


def order_item_name(dish, options):
    """Nom affiche sur le ticket restaurant : « Ndolé + Coca-Cola 33cl, Riz ». Max 140 car."""
    if not options:
        return dish.name[:140]
    return f"{dish.name} + {', '.join(o.name for o in options)}"[:140]


def restaurant_blockers(resto, subtotal):
    """Raisons empechant de commander chez ce restaurant (liste vide = OK)."""
    issues = []
    if not resto.is_active:
        issues.append(f"{resto.name} n'est plus disponible sur ONE EAT.")
    elif not resto.is_open_now:
        issues.append(f"{resto.name} est fermé ({resto.opening_status_label}).")
    if resto.max_orders_per_day and orders_today(resto) >= resto.max_orders_per_day:
        issues.append(f"{resto.name} a atteint sa limite de {resto.max_orders_per_day} "
                      "commandes pour aujourd'hui. Réessayez demain.")
    return issues


def orders_today(resto):
    """Commandes du jour acceptees (hors annulees) pour un restaurant."""
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return (Order.objects.filter(restaurant=resto, created_at__gte=start)
            .exclude(status=Order.Status.CANCELLED).count())


def build_cart_groups(lines):
    """lines = [CartLine] -> groupes par restaurant avec totaux et blocages."""
    groups = defaultdict(lambda: {"items": [], "subtotal": 0})
    for line in lines:
        dish = line.dish
        g = groups[dish.restaurant_id]
        g["restaurant"] = dish.restaurant
        # Prix unitaire = plat (avec promo) + complements choisis.
        price = dish.current_price + sum(o.price for o in line.options)
        g["items"].append({"key": line.key, "dish": dish, "qty": line.qty, "price": price,
                           "line": price * line.qty, "options": line.options})
        g["subtotal"] += price * line.qty
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
    lines = [line for line in lines if line.qty > 0]
    if not lines:
        raise CheckoutError("Votre panier est vide.")
    if payment_method not in {c[0] for c in PAYMENT_CHOICES}:
        raise CheckoutError("Moyen de paiement non disponible.")
    if payment_method in MOBILE_MONEY:
        phone = clean_phone(payment_phone)
        if not phone or len(phone.lstrip("+")) < 9:
            raise CheckoutError("Indiquez le numéro Mobile Money à débiter (9 chiffres minimum).")
    if not (address or "").strip():
        raise CheckoutError("Indiquez une adresse de livraison.")

    unavailable = [line.dish.name for line in lines if not line.dish.is_available]
    if unavailable:
        raise CheckoutError(f"Plus disponible : {', '.join(unavailable)}.")
    groups = build_cart_groups(lines)
    for g in groups:
        if g["blockers"]:
            raise CheckoutError(g["blockers"][0])

    code_str = (promo_code or "").strip().upper()
    created = []
    code_applied = False
    for g in groups:
        resto = g["restaurant"]
        order = Order.objects.create(
            customer=user, restaurant=resto,
            delivery_address=address.strip()[:255], notes=(notes or "").strip(),
            delivery_lat=_coord(lat), delivery_lng=_coord(lng),
            payment_method=payment_method,
            payment_phone=payment_phone.strip()[:20] if payment_method in MOBILE_MONEY else "",
            payment_status=(Order.PaymentStatus.PENDING if payment_method in MOBILE_MONEY
                            else Order.PaymentStatus.ON_DELIVERY),
            delivery_fee=resto.delivery_fee,
        )
        for it in g["items"]:
            OrderItem.objects.create(order=order, dish=it["dish"],
                                     name=order_item_name(it["dish"], it["options"]),
                                     unit_price=it["price"], quantity=it["qty"])
            Dish.objects.filter(pk=it["dish"].pk).update(orders_count=F("orders_count") + it["qty"])
        order.recompute_totals()

        if code_str:
            code = PromoCode.objects.filter(code=code_str, restaurant=resto,
                                            status=PromoCode.Status.APPROVED).first()
            if code and code.is_valid:
                code_applied = True
                disc = min(code.discount_for(order.items_total), order.items_total)
                order.discount, order.promo_code = disc, code.code
                order.recompute_totals()
                PromoCode.objects.filter(pk=code.pk).update(uses=F("uses") + 1)
                PromoCodeRedemption.objects.create(
                    promo_code=code, user=user, order=order, discount_amount=disc)
                if code.influencer_id:
                    code.influencer.recompute_score()

        Restaurant.objects.filter(pk=resto.pk).update(orders_count=F("orders_count") + 1)
        if not order.is_awaiting_payment:
            announce_new_order(order)
        created.append(order)

    if code_str and not code_applied:
        # Sans cette verification, le client croit a une remise qui n'est jamais appliquee.
        raise CheckoutError("Code promo invalide ou expiré pour ces restaurants.")
    return created


def _coord(value):
    """Coordonnee GPS saisie ou envoyee par un client : None si absente ou invalide."""
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def reorder_lines(order):
    """Plats encore disponibles d'une ancienne commande -> lignes panier."""
    lines = []
    for item in order.items.select_related("dish", "dish__restaurant"):
        if item.dish and item.dish.is_available:
            # Les complements d'origine ne sont pas re-proposes : le client les rechoisit.
            lines.append(CartLine(dish=item.dish, qty=item.quantity, key=str(item.dish.id)))
    return lines
