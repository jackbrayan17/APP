import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.routing import road_route, tracking_payload
from apps.orders.models import Order
from apps.orders.workflow import (TransitionError, driver_claim, driver_deliver, driver_pickup,
                                  mission_offers)
from .models import DriverProfile

OFFER_SECONDS = 30  # delai de reponse a une mission (cahier des charges 5.2)


def _profile(request):
    prof, _ = DriverProfile.objects.get_or_create(user=request.user)
    return prof


def _declined(request):
    return set(request.session.get("declined_missions", []))


def _offers(request, prof):
    if not prof.is_available or prof.active_mission:
        return []
    offers = mission_offers(prof, exclude_ids=_declined(request))
    for o in offers[:3]:
        if prof.current_lat is not None and o.restaurant.lat is not None:
            route = road_route(prof.current_lat, prof.current_lng, o.restaurant.lat, o.restaurant.lng)
            o.route_distance_km, o.route_duration_min = route["distance_km"], route["duration_min"]
    return offers


def _period_starts():
    now = timezone.localtime()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {"today": today, "week": today - timedelta(days=today.weekday()),
            "month": today.replace(day=1)}


@login_required
def dashboard(request):
    if not request.user.is_driver and not request.user.is_staff:
        messages.error(request, "Accès réservé aux livreurs.")
        return redirect("core:home")
    prof = _profile(request)
    mission = prof.active_mission
    offers = _offers(request, prof)
    starts = _period_starts()
    history = (Order.objects.filter(driver=request.user, status__in=[Order.Status.DELIVERED,
                                                                      Order.Status.CANCELLED])
               .select_related("restaurant").order_by("-delivered_at", "-created_at")[:20])

    map_orders = [{"number": o.number, "restaurant": o.restaurant.name,
                   "rlat": o.restaurant.lat, "rlng": o.restaurant.lng, "fee": o.delivery_fee}
                  for o in offers if o.restaurant.lat]
    center_lat = prof.current_lat if prof.current_lat is not None else settings.DOUALA_CENTER["lat"]
    center_lng = prof.current_lng if prof.current_lng is not None else settings.DOUALA_CENTER["lng"]
    return render(request, "delivery/dashboard.html", {
        "profile": prof, "mission": mission, "offers": offers,
        "offer_seconds": OFFER_SECONDS, "history": history,
        "earnings": {k: prof.earnings_since(v) for k, v in starts.items()},
        "earnings_total": prof.earnings_since(),
        "map_orders_json": json.dumps(map_orders),
        "map_center_json": json.dumps([float(center_lat), float(center_lng)]),
        "service_radius_m": int(prof.service_radius_km * 1000),
    })


@login_required
def offers_json(request):
    """Rafraichissement leger : nouvelles missions disponibles."""
    prof = _profile(request)
    offers = _offers(request, prof)
    return JsonResponse({"status": prof.status_key, "count": len(offers),
                         "ids": [o.id for o in offers],
                         "mission": prof.active_mission.status if prof.active_mission else None})


@login_required
@require_POST
def toggle_available(request):
    prof = _profile(request)
    if prof.is_available and prof.active_mission:
        return JsonResponse({"ok": False, "error": "Terminez votre course avant de passer hors ligne."},
                            status=400)
    prof.is_available = not prof.is_available
    prof.last_seen = timezone.now()
    prof.save(update_fields=["is_available", "last_seen"])
    return JsonResponse({"ok": True, "available": prof.is_available})


@login_required
@require_POST
def update_location(request):
    prof = _profile(request)
    try:
        data = json.loads(request.body or "{}")
        lat, lng = float(data["lat"]), float(data["lng"])
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"ok": False}, status=400)
    prof.current_lat, prof.current_lng = lat, lng
    prof.last_seen = timezone.now()
    prof.save(update_fields=["current_lat", "current_lng", "last_seen"])
    # Position visible par le client pendant toute la course.
    Order.objects.filter(driver=request.user).exclude(
        status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED]
    ).update(driver_lat=lat, driver_lng=lng)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def accept_order(request, order_id):
    try:
        order = driver_claim(order_id, request.user)
        messages.success(request, f"Mission {order.number} acceptée. Direction {order.restaurant.name} !")
    except TransitionError as exc:
        messages.error(request, str(exc))
    return redirect("delivery:dashboard")


@login_required
@require_POST
def decline_order(request, order_id):
    declined = _declined(request)
    declined.add(order_id)
    request.session["declined_missions"] = list(declined)[-50:]
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    messages.info(request, "Mission refusée.")
    return redirect("delivery:dashboard")


@login_required
@require_POST
def update_status(request, order_id):
    order = get_object_or_404(Order, id=order_id, driver=request.user)
    action = request.POST.get("action") or request.POST.get("status")
    try:
        if action in ("pickup", Order.Status.PICKED_UP, Order.Status.ON_THE_WAY):
            driver_pickup(order, request.user)
            messages.success(request, "Récupération confirmée. En route vers le client !")
        elif action in ("deliver", Order.Status.DELIVERED):
            driver_deliver(order, request.user)
            messages.success(request, f"Livraison confirmée · +{order.delivery_fee} FCFA 🎉")
        else:
            messages.error(request, "Action inconnue.")
    except TransitionError as exc:
        messages.error(request, str(exc))
    return redirect("delivery:dashboard")


@login_required
def order_map(request, number):
    """Carte de suivi temps reel d'une commande (client + livreur)."""
    order = get_object_or_404(Order, number=number)
    if order.customer_id != request.user.id and order.driver_id != request.user.id \
            and not request.user.is_staff:
        return redirect("core:home")
    return render(request, "delivery/order_map.html",
                  {"order": order, "map_data_json": json.dumps(tracking_payload(order)),
                   "is_driver_tracking": order.driver_id == request.user.id})
