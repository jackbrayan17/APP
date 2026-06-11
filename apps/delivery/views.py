import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.geo import haversine_km, within_radius
from apps.orders.models import Order
from .models import DriverProfile


def _profile(request):
    prof, _ = DriverProfile.objects.get_or_create(user=request.user)
    return prof


@login_required
def dashboard(request):
    if not request.user.is_driver and not request.user.is_staff:
        messages.error(request, "Acces reserve aux livreurs.")
        return redirect("core:home")
    prof = _profile(request)

    # Commandes pretes a livrer dans le perimetre (ou de son restaurant)
    candidates = Order.objects.filter(
        status__in=[Order.Status.READY, Order.Status.PREPARING]
    ).select_related("restaurant", "customer").filter(driver__isnull=True)

    available = []
    for o in candidates:
        lat = o.restaurant.lat
        lng = o.restaurant.lng
        if prof.current_lat and prof.current_lng and lat and lng:
            d = haversine_km(prof.current_lat, prof.current_lng, lat, lng)
            if d is not None and d <= prof.service_radius_km:
                o.distance_km = round(d, 1)
                available.append(o)
        else:
            o.distance_km = None
            available.append(o)
        # restreindre aux livreurs du restaurant si rattache
    if prof.restaurant_id:
        available = [o for o in available if o.restaurant_id == prof.restaurant_id]

    my_active = Order.objects.filter(
        driver=request.user,
        status__in=[Order.Status.PICKED_UP, Order.Status.ON_THE_WAY]
    ).select_related("restaurant", "customer")

    # Donnees carte (JSON)
    map_orders = [{
        "id": o.id, "number": o.number,
        "restaurant": o.restaurant.name,
        "rlat": o.restaurant.lat, "rlng": o.restaurant.lng,
        "dlat": o.delivery_lat, "dlng": o.delivery_lng,
        "address": o.delivery_address, "total": o.total,
        "distance": getattr(o, "distance_km", None),
    } for o in available if o.restaurant.lat]

    context = {
        "profile": prof,
        "available": available,
        "my_active": my_active,
        "delivered_count": Order.objects.filter(
            driver=request.user, status=Order.Status.DELIVERED).count(),
        "map_orders_json": json.dumps(map_orders),
    }
    return render(request, "delivery/dashboard.html", context)


@login_required
@require_POST
def toggle_available(request):
    prof = _profile(request)
    prof.is_available = not prof.is_available
    prof.last_seen = timezone.now()
    prof.save(update_fields=["is_available", "last_seen"])
    return JsonResponse({"ok": True, "available": prof.is_available})


@login_required
@require_POST
def update_location(request):
    prof = _profile(request)
    data = json.loads(request.body or "{}")
    prof.current_lat = data.get("lat")
    prof.current_lng = data.get("lng")
    prof.last_seen = timezone.now()
    prof.save(update_fields=["current_lat", "current_lng", "last_seen"])
    # Met a jour la position sur les commandes en cours (suivi client)
    Order.objects.filter(driver=request.user, status=Order.Status.ON_THE_WAY).update(
        driver_lat=prof.current_lat, driver_lng=prof.current_lng)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def accept_order(request, order_id):
    prof = _profile(request)
    order = get_object_or_404(Order, id=order_id, driver__isnull=True)
    order.driver = request.user
    order.status = Order.Status.PICKED_UP
    order.save(update_fields=["driver", "status"])
    from apps.core.services import notify
    notify(order.customer, f"Livreur en route — {order.number}",
           f"{request.user.display_name} va livrer votre commande.",
           url=f"/commande/{order.number}/")
    messages.success(request, f"Commande {order.number} acceptee.")
    return redirect("delivery:dashboard")


@login_required
@require_POST
def update_status(request, order_id):
    order = get_object_or_404(Order, id=order_id, driver=request.user)
    new_status = request.POST.get("status")
    if new_status in dict(Order.Status.choices):
        order.status = new_status
        if new_status == Order.Status.DELIVERED:
            order.delivered_at = timezone.now()
            prof = _profile(request)
            prof.deliveries_count += 1
            prof.save(update_fields=["deliveries_count"])
        order.save()
        from apps.core.services import notify
        notify(order.customer, f"Commande {order.number}",
               f"Statut : {order.get_status_display()}", url=f"/commande/{order.number}/")
    return redirect("delivery:dashboard")


@login_required
def order_map(request, number):
    """Carte de suivi temps reel d'une commande (client + livreur)."""
    order = get_object_or_404(Order, number=number)
    if order.customer_id != request.user.id and order.driver_id != request.user.id \
            and not request.user.is_staff:
        return redirect("core:home")
    data = {
        "restaurant": {"name": order.restaurant.name,
                       "lat": order.restaurant.lat, "lng": order.restaurant.lng},
        "delivery": {"lat": order.delivery_lat, "lng": order.delivery_lng,
                     "address": order.delivery_address},
        "driver": {"lat": order.driver_lat, "lng": order.driver_lng},
        "status": order.status,
    }
    return render(request, "delivery/order_map.html",
                  {"order": order, "map_data_json": json.dumps(data)})
