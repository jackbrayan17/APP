from django.contrib import messages
from django.contrib.auth.decorators import login_required
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.orders.models import Order, OrderItem
from apps.orders.workflow import (RESTAURANT_ACTIONS, TransitionError, restaurant_action,
                                  restaurant_next_actions)
from apps.promotions.models import Promotion
from .models import WEEKDAYS, Restaurant, Category, MenuSection, Dish, RestaurantPhoto, Favorite


def _cart_count(request):
    return sum(i.get("qty", 0) for i in request.session.get("cart", {}).values())


# ---------------- Favoris ----------------
@login_required
@require_POST
def favorite_toggle(request, slug):
    resto = get_object_or_404(Restaurant, slug=slug)
    fav = Favorite.objects.filter(user=request.user, restaurant=resto).first()
    if fav:
        fav.delete()
        is_fav = False
    else:
        Favorite.objects.create(user=request.user, restaurant=resto)
        is_fav = True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"is_favorite": is_fav})
    return redirect("restaurants:detail", slug=slug)


@login_required
def favorites_list(request):
    restos = [f.restaurant for f in Favorite.objects.filter(user=request.user)
              .select_related("restaurant")]
    return render(request, "client/favorites.html",
                  {"restaurants": restos, "cart_count": _cart_count(request)})


# ---------------- Cote client ----------------
def restaurant_detail(request, slug):
    resto = get_object_or_404(Restaurant.objects.prefetch_related("sections", "dishes"),
                              slug=slug, is_active=True)
    sections = resto.sections.prefetch_related("dishes").all()
    unsectioned = resto.dishes.filter(section__isnull=True, is_available=True)
    is_favorite = (request.user.is_authenticated and
                   Favorite.objects.filter(user=request.user, restaurant=resto).exists())
    context = {
        "resto": resto,
        "sections": sections,
        "unsectioned": unsectioned,
        "reviews": resto.reviews.select_related("customer")[:10],
        "is_favorite": is_favorite,
        "cart_count": _cart_count(request),
    }
    return render(request, "client/restaurant_detail.html", context)


def dish_detail(request, dish_id):
    """Page detail d'un plat, avec description complete et restaurant source."""
    dish = get_object_or_404(
        Dish.objects.select_related("restaurant", "section", "category"),
        id=dish_id, is_available=True, restaurant__is_active=True,
    )
    resto = dish.restaurant
    related = (resto.dishes.filter(is_available=True)
               .exclude(id=dish.id)
               .order_by("-is_popular", "name")[:4])
    is_favorite = (request.user.is_authenticated and
                   Favorite.objects.filter(user=request.user, restaurant=resto).exists())
    return render(request, "client/dish_detail.html", {
        "dish": dish,
        "resto": resto,
        "related": related,
        "is_favorite": is_favorite,
        "cart_count": _cart_count(request),
    })


def restaurant_share(request, token):
    """Lien public de partage d'un restaurant (logo, nom, note, plats)."""
    resto = get_object_or_404(Restaurant, share_token=token)
    context = {
        "resto": resto,
        "top_dishes": resto.dishes.filter(is_available=True).order_by("-is_popular")[:6],
        "cart_count": _cart_count(request),
    }
    return render(request, "share/restaurant.html", context)


# ---------------- Dashboard restaurant ----------------
def _owner_resto(request):
    return Restaurant.objects.filter(owner=request.user).first()


@login_required
def dashboard(request):
    if not request.user.is_restaurant and not request.user.is_staff:
        messages.error(request, "Acces reserve aux restaurants.")
        return redirect("core:home")
    resto = _owner_resto(request)
    if not resto:
        return redirect("restaurants:onboarding")

    orders = Order.objects.filter(restaurant=resto)
    delivered = orders.filter(status=Order.Status.DELIVERED)
    commission = settings.PLATFORM_COMMISSION_PERCENT
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    periods = {"Aujourd'hui": today, "7 jours": today - timedelta(days=6),
               "30 jours": today - timedelta(days=29)}

    def revenue(qs):
        agg = qs.aggregate(items=Sum("items_total"), disc=Sum("discount"), n=Count("id"))
        gross = (agg["items"] or 0) - (agg["disc"] or 0)
        return {"gross": gross, "net": round(gross * (100 - commission) / 100),
                "count": agg["n"] or 0, "basket": round(gross / agg["n"]) if agg["n"] else 0}

    revenue_periods = [{"label": k, **revenue(delivered.filter(delivered_at__gte=v))}
                       for k, v in periods.items()]
    daily = {row["d"]: row["s"] for row in
             delivered.filter(delivered_at__gte=today - timedelta(days=6))
             .annotate(d=TruncDate("delivered_at")).values("d").annotate(s=Sum("items_total"))}
    chart = []
    for i in range(6, -1, -1):
        day = (today - timedelta(days=i)).date()
        chart.append({"label": WEEKDAYS[day.weekday()][:3], "value": daily.get(day) or 0})
    peak = max([c["value"] for c in chart] + [1])
    for c in chart:
        c["pct"] = max(4, round(c["value"] * 100 / peak)) if c["value"] else 0
    top_dishes = (OrderItem.objects.filter(order__restaurant=resto,
                                           order__status=Order.Status.DELIVERED)
                  .values("name").annotate(qty=Sum("quantity")).order_by("-qty")[:5])
    context = {
        "resto": resto,
        "stats": {
            "orders_today": orders.filter(created_at__gte=today).count(),
            "to_handle": orders.filter(status=Order.Status.PENDING)
                               .exclude(payment_status=Order.PaymentStatus.PENDING).count(),
            "in_kitchen": orders.filter(status__in=[Order.Status.CONFIRMED,
                                                    Order.Status.PREPARING]).count(),
            "ready": orders.filter(status=Order.Status.READY).count(),
            "dishes": resto.dishes.count(),
            "unavailable": resto.dishes.filter(is_available=False).count(),
        },
        "revenue_periods": revenue_periods, "commission": commission,
        "chart": chart, "top_dishes": top_dishes,
        "recent_reviews": resto.reviews.select_related("customer")[:3],
    }
    return render(request, "restaurant_dashboard/home.html", context)


@login_required
def onboarding(request):
    """Creation du restaurant pour un compte restaurant sans resto."""
    if _owner_resto(request):
        return redirect("restaurants:dashboard")
    if request.method == "POST":
        resto = Restaurant.objects.create(
            owner=request.user,
            name=request.POST.get("name", "Mon Restaurant"),
            tagline=request.POST.get("tagline", ""),
            bio=request.POST.get("bio", ""),
            neighborhood=request.POST.get("neighborhood", ""),
            address=request.POST.get("address", ""),
            phone=request.POST.get("phone", ""),
        )
        messages.success(request, "Restaurant cree ! Completez votre menu.")
        return redirect("restaurants:dashboard")
    return render(request, "restaurant_dashboard/onboarding.html")


@login_required
def menu_manage(request):
    resto = _owner_resto(request)
    if not resto:
        return redirect("restaurants:onboarding")
    dishes = resto.dishes.all()
    fields = ("name", "description", "price", "prep_time", "calories", "protein_grams",
              "carbs_grams", "fat_grams", "fiber_grams", "dietary_tags", "dietary_note",
              "section_id", "category_id", "is_available", "is_popular", "is_diet")
    context = {
        "resto": resto,
        "sections": resto.sections.prefetch_related("dishes").all(),
        "categories": Category.objects.all(),
        "dishes": dishes,
        "dishes_data": {d.id: {f: getattr(d, f) for f in fields} for d in dishes},
        "unsectioned": dishes.filter(section__isnull=True),
    }
    return render(request, "restaurant_dashboard/menu.html", context)


@login_required
@require_POST
def dish_save(request):
    resto = _owner_resto(request)
    if not resto:
        return redirect("restaurants:onboarding")
    dish_id = request.POST.get("dish_id")
    dish = Dish.objects.filter(id=dish_id, restaurant=resto).first() if dish_id else Dish(restaurant=resto)
    dish.name = request.POST.get("name", dish.name)
    dish.description = request.POST.get("description", "")
    try:
        dish.price = max(0, int(request.POST.get("price") or 0))
    except ValueError:
        messages.error(request, "Prix invalide.")
        return redirect("restaurants:menu")
    dish.prep_time = int(request.POST.get("prep_time") or 20)
    dish.is_diet = request.POST.get("is_diet") == "on"
    raw_kcal = request.POST.get("calories", "")
    dish.calories = int(raw_kcal) if raw_kcal.isdigit() else None
    for field in ("protein_grams", "carbs_grams", "fat_grams", "fiber_grams"):
        raw = request.POST.get(field, "")
        setattr(dish, field, int(raw) if raw.isdigit() else None)
    dish.dietary_tags = request.POST.get("dietary_tags", "")
    dish.dietary_note = request.POST.get("dietary_note", "")
    section_id = request.POST.get("section")
    dish.section = MenuSection.objects.filter(id=section_id, restaurant=resto).first() if section_id else None
    cat_id = request.POST.get("category")
    dish.category = Category.objects.filter(id=cat_id).first() if cat_id else None
    dish.is_popular = request.POST.get("is_popular") == "on"
    dish.is_available = request.POST.get("is_available", "on") == "on"
    if request.FILES.get("image"):
        dish.image = request.FILES["image"]
    if request.FILES.get("video"):
        dish.video = request.FILES["video"]
    dish.save()
    messages.success(request, f"Plat « {dish.name} » enregistre.")
    return redirect("restaurants:menu")


@login_required
@require_POST
def dish_delete(request, dish_id):
    resto = _owner_resto(request)
    Dish.objects.filter(id=dish_id, restaurant=resto).delete()
    messages.success(request, "Plat supprime.")
    return redirect("restaurants:menu")


@login_required
@require_POST
def section_save(request):
    resto = _owner_resto(request)
    MenuSection.objects.create(
        restaurant=resto, name=request.POST.get("name", "Nouvelle section"),
        order=int(request.POST.get("order") or 0))
    return redirect("restaurants:menu")


@login_required
def customize(request):
    resto = _owner_resto(request)
    if not resto:
        return redirect("restaurants:onboarding")
    if request.method == "POST":
        resto.bio = request.POST.get("bio", resto.bio)
        resto.tagline = request.POST.get("tagline", resto.tagline)
        resto.brand_color = request.POST.get("brand_color", resto.brand_color)
        resto.accent_color = request.POST.get("accent_color", resto.accent_color)
        resto.neighborhood = request.POST.get("neighborhood", resto.neighborhood)
        resto.address = request.POST.get("address", resto.address)
        lat, lng = request.POST.get("lat"), request.POST.get("lng")
        if lat and lng:
            resto.lat, resto.lng = float(lat), float(lng)
        resto.delivery_fee = int(request.POST.get("delivery_fee") or resto.delivery_fee)
        resto.delivery_time_min = int(request.POST.get("delivery_time_min") or resto.delivery_time_min)
        resto.delivery_time_max = int(request.POST.get("delivery_time_max") or resto.delivery_time_max)
        resto.min_order = int(request.POST.get("min_order") or 0)
        resto.phone = request.POST.get("phone", resto.phone)
        if request.POST.get("hours_form") == "1":
            hours = {}
            for d in range(7):
                start, end = request.POST.get(f"open_{d}"), request.POST.get(f"close_{d}")
                on = request.POST.get(f"day_{d}") == "on"
                hours[str(d)] = [start, end] if on and start and end else None
            resto.opening_hours = hours
        if request.FILES.get("logo"):
            resto.logo = request.FILES["logo"]
        if request.FILES.get("cover_image"):
            resto.cover_image = request.FILES["cover_image"]
        resto.save()
        # categories
        cat_ids = request.POST.getlist("categories")
        if cat_ids:
            resto.categories.set(Category.objects.filter(id__in=cat_ids))
        for f in request.FILES.getlist("gallery"):
            RestaurantPhoto.objects.create(restaurant=resto, image=f)
        messages.success(request, "Page du restaurant mise a jour.")
        return redirect("restaurants:customize")
    return render(request, "restaurant_dashboard/customize.html",
                  {"resto": resto, "categories": Category.objects.all()})


@login_required
@require_POST
def toggle_open(request):
    """Fermeture exceptionnelle en un tap (et reouverture)."""
    resto = _owner_resto(request)
    if not resto:
        return redirect("restaurants:onboarding")
    resto.is_temporarily_closed = not resto.is_temporarily_closed
    resto.closure_note = request.POST.get("note", "")[:120] if resto.is_temporarily_closed else ""
    resto.save(update_fields=["is_temporarily_closed", "closure_note"])
    messages.success(request, "Restaurant fermé temporairement." if resto.is_temporarily_closed
                     else "Restaurant rouvert : les commandes reprennent.")
    return redirect("restaurants:dashboard")


@login_required
@require_POST
def dish_toggle(request, dish_id):
    """Activation / desactivation rapide d'un plat (rupture de stock)."""
    dish = get_object_or_404(Dish, id=dish_id, restaurant__owner=request.user)
    dish.is_available = not dish.is_available
    dish.save(update_fields=["is_available"])
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"available": dish.is_available})
    return redirect("restaurants:menu")


ORDER_TABS = [
    ("new", "Nouvelles", [Order.Status.PENDING]),
    ("kitchen", "En cuisine", [Order.Status.CONFIRMED, Order.Status.PREPARING]),
    ("ready", "Prêtes", [Order.Status.READY]),
    ("delivery", "En livraison", [Order.Status.PICKED_UP, Order.Status.ON_THE_WAY]),
    ("done", "Terminées", [Order.Status.DELIVERED, Order.Status.CANCELLED]),
]


def _visible_orders(resto):
    """Commandes visibles par le resto : celles en attente de paiement MoMo sont masquees."""
    return (Order.objects.filter(restaurant=resto)
            .exclude(status=Order.Status.PENDING, payment_status=Order.PaymentStatus.PENDING))


@login_required
def orders_manage(request):
    resto = _owner_resto(request)
    if not resto:
        return redirect("restaurants:onboarding")
    tab = request.GET.get("tab", "new")
    base = _visible_orders(resto)
    tabs = [{"key": k, "label": label, "count": base.filter(status__in=st).count()}
            for k, label, st in ORDER_TABS]
    statuses = {k: st for k, _, st in ORDER_TABS}.get(tab, ORDER_TABS[0][2])
    orders = (base.filter(status__in=statuses).select_related("customer", "driver")
              .prefetch_related("items"))
    orders = list(orders.order_by("-created_at")[:60] if tab == "done" else orders.order_by("created_at"))
    for o in orders:
        o.actions = [(a, RESTAURANT_ACTIONS[a][2]) for a in restaurant_next_actions(o)]
    return render(request, "restaurant_dashboard/orders.html",
                  {"resto": resto, "orders": orders, "tab": tab, "tabs": tabs,
                   "latest_id": base.order_by("-id").values_list("id", flat=True).first() or 0})


@login_required
def orders_feed(request):
    """Poll leger : nouvelles commandes a traiter (alerte sonore cote navigateur)."""
    resto = _owner_resto(request)
    if not resto:
        return JsonResponse({"pending": 0, "latest_id": 0})
    qs = _visible_orders(resto)
    return JsonResponse({
        "pending": qs.filter(status=Order.Status.PENDING).count(),
        "latest_id": qs.order_by("-id").values_list("id", flat=True).first() or 0,
    })


@login_required
@require_POST
def order_set_status(request, order_id):
    resto = _owner_resto(request)
    order = get_object_or_404(Order, id=order_id, restaurant=resto)
    action = request.POST.get("action", "")
    try:
        restaurant_action(order, action, reason=request.POST.get("reason", ""))
        labels = {"accept": "Commande acceptée", "start": "Préparation lancée",
                  "ready": "Commande prête : les livreurs sont prévenus",
                  "refuse": "Commande refusée", "cancel": "Commande annulée"}
        messages.success(request, f"{labels.get(action, 'OK')} · {order.number}")
    except TransitionError as exc:
        messages.error(request, str(exc))
    nxt = request.POST.get("next", "")
    return redirect(nxt if nxt.startswith("/resto/") else "restaurants:orders")


@login_required
def drivers_manage(request):
    resto = _owner_resto(request)
    if not resto:
        return redirect("restaurants:onboarding")
    if request.method == "POST":
        messages.error(
            request,
            "Les livreurs sont affectés par l'équipe ONE EAT. "
            "Contactez l'administration pour une modification.",
        )
        return redirect("restaurants:drivers")
    return render(request, "restaurant_dashboard/drivers.html",
                  {"resto": resto, "drivers": resto.drivers.select_related("user")})


@login_required
def promos_manage(request):
    resto = _owner_resto(request)
    if not resto:
        return redirect("restaurants:onboarding")
    if request.method == "POST":
        promo = Promotion.objects.create(
            restaurant=resto,
            title=request.POST.get("title", "Promo"),
            description=request.POST.get("description", ""),
            discount_type=request.POST.get("discount_type", "percent"),
            discount_value=int(request.POST.get("discount_value") or 0),
            ends_at=request.POST.get("ends_at") or timezone.now() + timezone.timedelta(days=7),
        )
        dish_ids = request.POST.getlist("dishes")
        promo.dishes.set(resto.dishes.filter(id__in=dish_ids))
        messages.success(request, "Promotion lancee !")
        return redirect("restaurants:promos")
    return render(request, "restaurant_dashboard/promos.html",
                  {"resto": resto, "promos": resto.promotions.all(),
                   "dishes": resto.dishes.all()})
