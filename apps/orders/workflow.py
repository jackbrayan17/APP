"""Cycle de vie d'une commande ONE EAT — source unique de verite.

Client -> Restaurant -> Livreur, dans cet ordre :

    PENDING --accept--> CONFIRMED --start--> PREPARING --ready--> READY
       |                    |                    |                  |
       +--refuse/cancel-----+--------cancel------+------cancel------+
                                                                    |
    (livreur) claim : s'affecte la course des CONFIRMED (se rend au restaurant)
    (livreur) pickup : READY -> ON_THE_WAY (uniquement quand la cuisine a fini)
    (livreur) deliver : ON_THE_WAY -> DELIVERED (encaissement si especes)

Le web, l'API mobile et l'admin passent tous par ces fonctions : aucun acteur
ne peut sauter une etape ni modifier une commande qui ne le concerne pas.
"""
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.geo import haversine_km
from .models import Order

S = Order.Status
PS = Order.PaymentStatus

ACTIVE_DRIVER_STATUSES = [S.CONFIRMED, S.PREPARING, S.READY, S.PICKED_UP, S.ON_THE_WAY]
OFFER_STATUSES = [S.CONFIRMED, S.PREPARING, S.READY]
CLOSED_STATUSES = [S.DELIVERED, S.CANCELLED]


class TransitionError(Exception):
    """Action impossible dans l'etat actuel de la commande (message affichable)."""


def _notify(user, title, body, url):
    from apps.core.services import notify
    if user:
        notify(user, title, body, url=url)


def _customer_url(order):
    return f"/commande/{order.number}/"


# --------------------------------------------------------------------------- #
# Creation / paiement
# --------------------------------------------------------------------------- #
def announce_new_order(order):
    """Previent le restaurant (alerte sonore cote tableau de bord)."""
    _notify(order.restaurant.owner, f"Nouvelle commande {order.number}",
            f"{order.item_count} article(s) · {order.restaurant_revenue} FCFA",
            "/resto/commandes/")


def confirm_mobile_money(order, phone=""):
    """Paiement Mobile Money valide (simule en demo, callback operateur en prod)."""
    if order.payment_status != PS.PENDING:
        return order
    order.payment_status = PS.PAID
    if phone:
        order.payment_phone = phone
    order.save(update_fields=["payment_status", "payment_phone", "updated_at"])
    announce_new_order(order)
    return order


# --------------------------------------------------------------------------- #
# Restaurant
# --------------------------------------------------------------------------- #
RESTAURANT_ACTIONS = {
    # action: (statuts de depart autorises, statut d'arrivee, libelle bouton)
    "accept": ([S.PENDING], S.CONFIRMED, "Accepter"),
    "start": ([S.CONFIRMED], S.PREPARING, "Lancer la préparation"),
    "ready": ([S.CONFIRMED, S.PREPARING], S.READY, "Marquer prête"),
    "refuse": ([S.PENDING], S.CANCELLED, "Refuser"),
    "cancel": ([S.CONFIRMED, S.PREPARING, S.READY], S.CANCELLED, "Annuler"),
}


def restaurant_next_actions(order):
    """Actions proposees au restaurant (dans l'ordre d'affichage)."""
    if order.is_awaiting_payment:
        return []
    return [a for a in ("accept", "start", "ready", "refuse")
            if order.status in RESTAURANT_ACTIONS[a][0]]


@transaction.atomic
def restaurant_action(order, action, reason=""):
    if action not in RESTAURANT_ACTIONS:
        raise TransitionError("Action inconnue.")
    order = Order.objects.select_for_update().get(pk=order.pk)
    allowed, target, _ = RESTAURANT_ACTIONS[action]
    if order.is_awaiting_payment:
        raise TransitionError("Le paiement Mobile Money n'est pas encore confirmé.")
    if order.status not in allowed:
        raise TransitionError(
            f"Impossible : la commande est « {order.get_status_display()} ».")
    if action == "cancel" and order.picked_up_at:
        raise TransitionError("Le livreur a déjà récupéré la commande.")

    now = timezone.now()
    order.status = target
    fields = ["status", "updated_at"]
    if target == S.CONFIRMED:
        order.confirmed_at = now
        fields.append("confirmed_at")
    elif target == S.READY:
        order.ready_at = now
        fields.append("ready_at")
    elif target == S.CANCELLED:
        _cancel_fields(order, reason or "Annulée par le restaurant.", fields)
    order.save(update_fields=fields)

    url = _customer_url(order)
    if target == S.CONFIRMED:
        _notify(order.customer, "Commande acceptée ✅",
                f"{order.restaurant.name} prépare votre commande {order.number}.", url)
        offer_to_nearby_drivers(order)
    elif target == S.PREPARING:
        _notify(order.customer, "En cuisine 👩🏾‍🍳", f"Vos plats sont en préparation ({order.number}).", url)
    elif target == S.READY:
        _notify(order.customer, "Commande prête",
                "Le livreur la récupère." if order.driver_id else "Nous cherchons un livreur.", url)
        if order.driver_id:
            _notify(order.driver, f"Commande {order.number} prête",
                    f"Récupérez-la chez {order.restaurant.name}.", "/livreur/")
        else:
            offer_to_nearby_drivers(order)
    elif target == S.CANCELLED:
        _notify(order.customer, f"Commande {order.number} annulée", order.cancel_reason, url)
        if order.driver_id:
            _notify(order.driver, f"Course {order.number} annulée", order.cancel_reason, "/livreur/")
    return order


def _cancel_fields(order, reason, fields):
    order.cancelled_at = timezone.now()
    order.cancel_reason = reason[:160]
    fields += ["cancelled_at", "cancel_reason"]
    if order.payment_status == PS.PAID:
        order.payment_status = PS.REFUNDED
        fields.append("payment_status")


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
@transaction.atomic
def customer_cancel(order, reason="Annulée par le client."):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.is_cancellable_by_customer:
        raise TransitionError("Le restaurant a déjà accepté : contactez le support pour annuler.")
    order.status = S.CANCELLED
    fields = ["status", "updated_at"]
    _cancel_fields(order, reason, fields)
    order.save(update_fields=fields)
    if not order.is_awaiting_payment:
        _notify(order.restaurant.owner, f"Commande {order.number} annulée",
                "Le client a annulé avant acceptation.", "/resto/commandes/")
    return order


# --------------------------------------------------------------------------- #
# Livreur
# --------------------------------------------------------------------------- #
def mission_offers(profile, exclude_ids=()):
    """Courses proposees au livreur : acceptees par le resto, sans livreur, dans son rayon."""
    qs = (Order.objects.filter(status__in=OFFER_STATUSES, driver__isnull=True)
          .exclude(payment_status=PS.PENDING)
          .exclude(id__in=list(exclude_ids))
          .select_related("restaurant", "customer").order_by("confirmed_at", "created_at"))
    if profile.restaurant_id:
        qs = qs.filter(restaurant_id=profile.restaurant_id)
    offers = []
    for o in qs[:30]:
        r = o.restaurant
        o.distance_km = None
        if None not in (profile.current_lat, profile.current_lng, r.lat, r.lng):
            d = haversine_km(profile.current_lat, profile.current_lng, r.lat, r.lng)
            if d is not None and d > profile.service_radius_km:
                continue
            o.distance_km = round(d, 1) if d is not None else None
        offers.append(o)
    return offers


def offer_to_nearby_drivers(order, limit=8):
    """Notifie les livreurs disponibles proches du restaurant (nouvelle mission)."""
    if order.driver_id:
        return
    from apps.delivery.models import DriverProfile
    r = order.restaurant
    drivers = DriverProfile.objects.filter(is_available=True).select_related("user")
    sent = 0
    for prof in drivers:
        if prof.restaurant_id and prof.restaurant_id != r.id:
            continue
        if None not in (prof.current_lat, prof.current_lng, r.lat, r.lng):
            d = haversine_km(prof.current_lat, prof.current_lng, r.lat, r.lng)
            if d is not None and d > prof.service_radius_km:
                continue
        if prof.active_mission:
            continue
        _notify(prof.user, "Nouvelle mission 🛵",
                f"{r.name} ({r.neighborhood}) · {order.delivery_fee} FCFA", "/livreur/")
        sent += 1
        if sent >= limit:
            break


@transaction.atomic
def driver_claim(order_id, driver):
    """Le livreur accepte une mission (une seule course a la fois)."""
    from apps.delivery.models import DriverProfile
    prof, _ = DriverProfile.objects.get_or_create(user=driver)
    if not prof.is_available:
        raise TransitionError("Passez-vous « Disponible » pour accepter une mission.")
    if Order.objects.filter(driver=driver, status__in=ACTIVE_DRIVER_STATUSES).exists():
        raise TransitionError("Terminez votre course en cours avant d'en accepter une autre.")
    order = Order.objects.select_for_update().filter(pk=order_id).first()
    if not order or order.driver_id or order.status not in OFFER_STATUSES \
            or order.is_awaiting_payment:
        raise TransitionError("Cette mission n'est plus disponible.")
    if prof.restaurant_id and prof.restaurant_id != order.restaurant_id:
        raise TransitionError("Cette mission est réservée aux livreurs d'un autre restaurant.")
    order.driver = driver
    order.driver_assigned_at = timezone.now()
    order.driver_lat, order.driver_lng = prof.current_lat, prof.current_lng
    order.save(update_fields=["driver", "driver_assigned_at", "driver_lat", "driver_lng", "updated_at"])
    _notify(order.customer, "Livreur trouvé 🛵",
            f"{driver.display_name} récupérera votre commande chez {order.restaurant.name}.",
            _customer_url(order))
    _notify(order.restaurant.owner, f"Livreur affecté — {order.number}",
            f"{driver.display_name} arrive pour récupérer la commande.", "/resto/commandes/")
    return order


@transaction.atomic
def driver_pickup(order, driver):
    """Le livreur confirme la recuperation au restaurant -> en route."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.driver_id != driver.id:
        raise TransitionError("Cette course ne vous est pas affectée.")
    if order.status not in (S.READY, S.PICKED_UP):
        raise TransitionError("La cuisine n'a pas encore marqué la commande comme prête.")
    now = timezone.now()
    order.status = S.ON_THE_WAY
    order.picked_up_at = order.picked_up_at or now
    order.save(update_fields=["status", "picked_up_at", "updated_at"])
    _notify(order.customer, "Votre commande est en route 🛵",
            f"{driver.display_name} arrive. Suivez-le en direct.", _customer_url(order))
    return order


@transaction.atomic
def driver_deliver(order, driver):
    """Livraison confirmee : encaissement especes + stats livreur/restaurant."""
    from apps.delivery.models import DriverProfile
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.driver_id != driver.id:
        raise TransitionError("Cette course ne vous est pas affectée.")
    if order.status != S.ON_THE_WAY:
        raise TransitionError("Confirmez d'abord la récupération au restaurant.")
    order.status = S.DELIVERED
    order.delivered_at = timezone.now()
    fields = ["status", "delivered_at", "updated_at"]
    if order.payment_status == PS.ON_DELIVERY:
        order.payment_status = PS.PAID
        fields.append("payment_status")
    order.save(update_fields=fields)
    DriverProfile.objects.filter(user=driver).update(deliveries_count=F("deliveries_count") + 1)
    _notify(order.customer, "Commande livrée 🎉",
            "Bon appétit ! Notez le restaurant et votre livreur.", _customer_url(order))
    _notify(order.restaurant.owner, f"Commande {order.number} livrée",
            f"Livrée par {driver.display_name}.", "/resto/commandes/")
    return order


def driver_advance(order, driver, target_status):
    """Compatibilite API : applique le statut demande via la bonne transition."""
    if target_status in (S.PICKED_UP, S.ON_THE_WAY):
        return driver_pickup(order, driver)
    if target_status == S.DELIVERED:
        return driver_deliver(order, driver)
    raise TransitionError("Statut non autorisé pour un livreur.")
