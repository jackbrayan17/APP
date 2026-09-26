import json

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Avg, Count, Sum, Q
from django.db.models.functions import TruncDate
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.restaurants.models import Restaurant, Category, Dish, Favorite
from apps.orders.models import Order, Review
from apps.delivery.models import DriverProfile
from apps.promotions.models import PromoCodeRedemption
from apps.accounts.models import User
from .models import ActivityLog, Notification, PushSubscription


def _cart_count(request):
    cart = request.session.get("cart", {})
    return sum(i.get("qty", 0) for i in cart.values())


def home(request):
    cat_slug = request.GET.get("cat")
    q = request.GET.get("q", "").strip()
    categories = Category.objects.all()
    restaurants = Restaurant.objects.filter(is_active=True).prefetch_related("categories")
    filter_active = bool(cat_slug)
    active_category = categories.filter(slug=cat_slug).first() if filter_active else None
    if filter_active and cat_slug != "tous":
        restaurants = restaurants.filter(categories__slug=cat_slug).distinct()

    search_restaurants = Restaurant.objects.none()
    search_dishes = Dish.objects.none()
    if q:
        search_restaurants = (restaurants.filter(
            Q(name__icontains=q) |
            Q(tagline__icontains=q) |
            Q(bio__icontains=q) |
            Q(dishes__name__icontains=q)
        ).distinct().order_by("-rating"))
        search_dishes = (Dish.objects.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(restaurant__name__icontains=q),
            is_available=True,
            restaurant__is_active=True,
        ).select_related("restaurant"))
        if filter_active and cat_slug != "tous":
            search_dishes = search_dishes.filter(
                Q(category__slug=cat_slug) |
                Q(restaurant__categories__slug=cat_slug)
            ).distinct()
        search_dishes = search_dishes.order_by("-is_popular", "-orders_count", "name")[:20]
    elif filter_active:
        search_restaurants = restaurants.order_by("-rating")
        search_dishes = Dish.objects.filter(
            is_available=True,
            restaurant__is_active=True,
        ).select_related("restaurant")
        if cat_slug != "tous":
            search_dishes = search_dishes.filter(
                Q(category__slug=cat_slug) |
                Q(restaurant__categories__slug=cat_slug)
            ).distinct()
        search_dishes = search_dishes.order_by(
            "-is_popular", "-orders_count", "name"
        )[:20]

    context = {
        "categories": categories,
        "featured": Restaurant.objects.filter(is_active=True, is_featured=True)[:8],
        "popular": Restaurant.objects.filter(is_active=True).order_by("-orders_count", "-rating")[:8],
        "restaurants": restaurants.order_by("-is_featured", "-rating"),
        "search_restaurants": search_restaurants,
        "search_dishes": search_dishes,
        "q": q,
        "filter_active": filter_active,
        "active_category": active_category,
        "active_cat": cat_slug or "tous",
        "cart_count": _cart_count(request),
        "active_order": (Order.objects.filter(customer=request.user)
                         .exclude(status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED])
                         .select_related("restaurant").first()
                         if request.user.is_authenticated else None),
        "diet_count": Dish.objects.filter(is_diet=True, is_available=True,
                                          restaurant__is_active=True).count(),
    }
    return render(request, "client/home.html", context)


def explore(request):
    q = request.GET.get("q", "").strip()
    hood = request.GET.get("hood", "")
    restaurants = Restaurant.objects.filter(is_active=True)
    dishes = Dish.objects.filter(is_available=True, restaurant__is_active=True).select_related("restaurant")
    if q:
        restaurants = restaurants.filter(
            Q(name__icontains=q) | Q(dishes__name__icontains=q) | Q(bio__icontains=q)).distinct()
        dishes = dishes.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(restaurant__name__icontains=q)
        )
    if hood and hood != "Tous":
        restaurants = restaurants.filter(neighborhood=hood)
        dishes = dishes.filter(restaurant__neighborhood=hood)

    hoods = (Restaurant.objects.filter(is_active=True)
             .exclude(neighborhood="").values_list("neighborhood", flat=True).distinct())
    context = {
        "restaurants": restaurants.order_by("-rating"),
        "dishes": dishes.order_by("-is_popular", "-orders_count", "name")[:20],
        "q": q, "hood": hood or "Tous",
        "hoods": list(hoods),
        "cart_count": _cart_count(request),
    }
    return render(request, "client/explore.html", context)


def search_api(request):
    q = request.GET.get("q", "").strip()
    results = []
    if q:
        for d in Dish.objects.filter(
                Q(name__icontains=q) | Q(description__icontains=q) |
                Q(restaurant__name__icontains=q),
                is_available=True, restaurant__is_active=True
        ).select_related("restaurant")[:8]:
            results.append({"type": "dish", "name": d.name, "id": d.id,
                            "restaurant": d.restaurant.name,
                            "restaurant_slug": d.restaurant.slug,
                            "price": d.current_price,
                            "image": d.image.url if d.image else ""})
        for r in Restaurant.objects.filter(
                Q(name__icontains=q) | Q(dishes__name__icontains=q),
                is_active=True).distinct()[:10]:
            results.append({"type": "restaurant", "name": r.name, "slug": r.slug,
                            "rating": float(r.rating), "neighborhood": r.neighborhood,
                            "logo": r.logo.url if r.logo else ""})
    return JsonResponse({"results": results})


# ---------- Notifications ----------
@login_required
def notifications(request):
    notifs = request.user.notifications.all()[:50]
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, "client/notifications.html", {"notifications": notifs})


@require_POST
@login_required
def push_subscribe(request):
    data = json.loads(request.body or "{}")
    sub = data.get("subscription", {})
    keys = sub.get("keys", {})
    endpoint = sub.get("endpoint")
    if not endpoint:
        return JsonResponse({"ok": False, "error": "endpoint manquant"}, status=400)
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"user": request.user, "p256dh": keys.get("p256dh", ""),
                  "auth": keys.get("auth", ""),
                  "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300]},
    )
    return JsonResponse({"ok": True})


# ---------- PWA ----------
def manifest(request):
    data = {
        "name": "ONE EAT — Livraison à Douala",
        "short_name": "ONE EAT",
        "description": "Commandez vos plats préférés à Douala, livrés rapidement.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#ffffff",
        "theme_color": "#FFFFFF",
        "lang": "fr",
        "categories": ["food", "shopping", "lifestyle"],
        "id": "/",
        "icons": [
            {"src": "/static/icons/icon-192.png?v=3", "sizes": "192x192", "type": "image/png",
             "purpose": "any"},
            {"src": "/static/icons/icon-512.png?v=3", "sizes": "512x512", "type": "image/png",
             "purpose": "any"},
            {"src": "/static/icons/icon-maskable-192.png?v=3", "sizes": "192x192",
             "type": "image/png", "purpose": "maskable"},
            {"src": "/static/icons/icon-maskable-512.png?v=3", "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Mes commandes", "url": "/commandes/"},
            {"name": "Explorer", "url": "/explorer/"},
        ],
    }
    # Type MIME correct pour une installabilité maximale (Chrome/Edge/Android).
    return JsonResponse(data, content_type="application/manifest+json")


def service_worker(request):
    sw = render_to_string("pwa/sw.js")
    resp = HttpResponse(sw, content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache"
    return resp


def offline(request):
    return render(request, "pwa/offline.html")


def help_center(request):
    """Centre d'aide : FAQ + contacts support."""
    faqs = [
        ("Comment passer une commande ?",
         "Choisissez un restaurant, ajoutez des plats au panier, puis validez "
         "votre adresse de livraison et le mode de paiement."),
        ("Quels modes de paiement acceptez-vous ?",
         "Espèces à la livraison, MTN Mobile Money, Orange Money et carte bancaire."),
        ("Comment suivre ma commande ?",
         "Depuis « Mes commandes », ouvrez une commande en cours pour suivre le "
         "livreur en temps réel sur la carte."),
        ("Comment ajouter un restaurant en favori ?",
         "Appuyez sur le cœur ♥ sur la page d'un restaurant. Retrouvez vos favoris "
         "depuis votre profil."),
        ("Quelle est la zone de livraison ?",
         "Nous livrons à Douala, dans un rayon de 10 km autour de chaque restaurant."),
    ]
    return render(request, "client/help.html", {
        "faqs": faqs,
        "support_email": "support@oneeat.cm",
        "support_whatsapp": "237600000000",
        "cart_count": _cart_count(request),
    })


# ---------- Pages legales ----------
def legal_page(request, page):
    templates = {
        "cgu": "legal/cgu.html",
        "confidentialite": "legal/confidentialite.html",
        "cgv": "legal/cgv.html",
        "mentions": "legal/mentions.html",
    }
    template = templates.get(page)
    if not template:
        return redirect("core:home")
    return render(request, template, {"updated": "12 juin 2026"})


# ---------- Tableau de bord ADMIN ----------
def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == User.Role.ADMIN)


@user_passes_test(_is_admin, login_url="/connexion/")
def admin_dashboard(request):
    now = timezone.now()
    period = request.GET.get("period", "30")
    if period not in {"7", "30", "90", "all"}:
        period = "30"
    period_days = None if period == "all" else int(period)
    date_start = now - timezone.timedelta(days=period_days) if period_days else None

    restaurant_id = request.GET.get("restaurant", "")
    neighborhood = request.GET.get("neighborhood", "")

    orders = Order.objects.select_related("restaurant", "customer", "driver")
    if date_start:
        orders = orders.filter(created_at__gte=date_start)
    if restaurant_id.isdigit():
        orders = orders.filter(restaurant_id=int(restaurant_id))
    else:
        restaurant_id = ""
    if neighborhood:
        orders = orders.filter(restaurant__neighborhood=neighborhood)

    delivered_orders = orders.filter(status=Order.Status.DELIVERED)
    order_count = orders.count()
    delivered_count = delivered_orders.count()
    delivered_summary = delivered_orders.aggregate(revenue=Sum("total"), avg_basket=Avg("total"))
    delivered_revenue = delivered_summary["revenue"] or 0
    avg_basket = round(delivered_summary["avg_basket"] or 0)
    active_statuses = [
        Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.PREPARING,
        Order.Status.READY, Order.Status.PICKED_UP, Order.Status.ON_THE_WAY,
    ]
    active_orders = orders.filter(status__in=active_statuses).count()
    delivery_rate = round((delivered_count / order_count * 100), 1) if order_count else 0

    top_dishes = (Dish.objects.select_related("restaurant")
                  .annotate(
                      ordered_qty=Sum(
                          "order_items__quantity",
                          filter=Q(order_items__order__in=orders),
                      ),
                      order_lines=Count(
                          "order_items",
                          filter=Q(order_items__order__in=orders),
                      ),
                  )
                  .filter(ordered_qty__gt=0)
                  .order_by("-ordered_qty", "name")[:8])
    top_restaurants_by_orders = (Restaurant.objects
                                 .annotate(
                                     order_count=Count(
                                         "orders", filter=Q(orders__in=orders), distinct=True),
                                     delivered_revenue=Sum(
                                         "orders__total", filter=Q(orders__in=delivered_orders)),
                                 )
                                 .filter(Q(order_count__gt=0) | Q(delivered_revenue__gt=0))
                                 .order_by("-delivered_revenue", "-order_count")[:8])
    top_drivers_by_orders = (DriverProfile.objects.select_related("user", "restaurant")
                             .annotate(
                                 delivery_count=Count(
                                     "user__deliveries",
                                     filter=Q(user__deliveries__in=orders), distinct=True),
                                 delivered_count=Count(
                                     "user__deliveries",
                                     filter=Q(user__deliveries__in=delivered_orders), distinct=True),
                             )
                             .order_by("-delivered_count", "-delivery_count", "-rating")[:8])
    top_rated = (Restaurant.objects.filter(rating_count__gt=0)
                 .order_by("-rating", "-rating_count")[:8])

    status_rows = list(orders.values("status").annotate(n=Count("id")).order_by("-n"))
    status_labels = dict(Order.Status.choices)
    orders_by_status = [
        {"status": row["status"], "label": status_labels.get(row["status"], row["status"]), "n": row["n"]}
        for row in status_rows
    ]
    payment_labels = dict(Order.Payment.choices)
    payment_rows = list(orders.values("payment_method").annotate(n=Count("id"), value=Sum("total")).order_by("-n"))
    payments = [
        {
            "key": row["payment_method"],
            "label": payment_labels.get(row["payment_method"], row["payment_method"]),
            "n": row["n"],
            "value": row["value"] or 0,
            "share": round(row["n"] / order_count * 100) if order_count else 0,
        }
        for row in payment_rows
    ]

    first_order = orders.order_by("created_at").values_list("created_at", flat=True).first()
    series_start = date_start or (first_order if first_order else now - timezone.timedelta(days=29))
    if (now - series_start).days > 90:
        series_start = now - timezone.timedelta(days=90)
    daily_rows = {
        row["day"]: row for row in
        orders.filter(created_at__gte=series_start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(orders=Count("id"), revenue=Sum("total", filter=Q(status=Order.Status.DELIVERED)))
        .order_by("day")
    }
    series = []
    current_day = series_start.date()
    while current_day <= now.date():
        row = daily_rows.get(current_day, {})
        series.append({
            "day": current_day.strftime("%d/%m"),
            "orders": row.get("orders", 0),
            "revenue": row.get("revenue") or 0,
        })
        current_day += timezone.timedelta(days=1)

    logs = ActivityLog.objects.all()
    if date_start:
        logs = logs.filter(created_at__gte=date_start)
    log_levels = {row["level"]: row["n"] for row in logs.values("level").annotate(n=Count("id"))}
    promo_uses = PromoCodeRedemption.objects.filter(order__in=orders).count()
    cash_orders = next((p["n"] for p in payments if p["key"] == Order.Payment.CASH), 0)
    cash_share = round(cash_orders / order_count * 100) if order_count else 0
    restaurant_revenues = [r.delivered_revenue or 0 for r in top_restaurants_by_orders]
    concentration = round(sum(restaurant_revenues[:2]) / delivered_revenue * 100) if delivered_revenue else 0

    insights = [
        {"level": "danger" if active_orders else "success", "title": f"{active_orders} commandes encore actives", "body": "À suivre dans le pipeline opérationnel."},
        {"level": "warning", "title": f"Les 2 premiers restaurants concentrent {concentration} % du CA", "body": "Mesure le risque de dépendance commerciale."},
        {"level": "warning" if promo_uses == 0 else "success", "title": f"{promo_uses} utilisation(s) de code promo", "body": "Vérifie l'impact réel des campagnes influenceurs."},
        {"level": "danger" if cash_share >= 80 else "info", "title": f"Paiements en espèces : {cash_share} %", "body": "Suit l'adoption des paiements numériques."},
    ]

    restaurants_for_filter = Restaurant.objects.filter(is_active=True).order_by("name")
    neighborhoods = list(Restaurant.objects.exclude(neighborhood="")
                         .values_list("neighborhood", flat=True).distinct().order_by("neighborhood"))

    context = {
        "stats": {
            "users": User.objects.count(),
            "clients": User.objects.filter(role=User.Role.CLIENT).count(),
            "restaurants": Restaurant.objects.count(),
            "drivers": User.objects.filter(role=User.Role.DRIVER).count(),
            "orders": order_count,
            "revenue": delivered_revenue,
            "avg_basket": avg_basket,
            "delivered": delivered_count,
            "delivery_rate": delivery_rate,
            "active_orders": active_orders,
            "reviews": Review.objects.filter(order__in=orders).count(),
            "favorites": Favorite.objects.count(),
            "logs": logs.count(),
            "errors": log_levels.get("error", 0),
        },
        "top_dishes": top_dishes,
        "top_restaurants_by_orders": top_restaurants_by_orders,
        "top_drivers_by_orders": top_drivers_by_orders,
        "top_rated": top_rated,
        "orders_by_status": orders_by_status,
        "payments": payments,
        "recent_orders": orders[:10],
        "recent_logs": logs[:12],
        "series_json": json.dumps(series),
        "status_json": json.dumps(orders_by_status),
        "payment_json": json.dumps(payments),
        "restaurant_chart_json": json.dumps([
            {"name": r.name, "revenue": r.delivered_revenue or 0, "orders": r.order_count}
            for r in top_restaurants_by_orders
        ]),
        "dish_chart_json": json.dumps([
            {"name": d.name, "restaurant": d.restaurant.name, "quantity": d.ordered_qty or 0}
            for d in top_dishes
        ]),
        "insights": insights,
        "log_levels": log_levels,
        "period": period,
        "restaurant_id": restaurant_id,
        "neighborhood": neighborhood,
        "restaurants_for_filter": restaurants_for_filter,
        "neighborhoods": neighborhoods,
        "all_users": User.objects.order_by("-created_at")[:50],
        "all_restaurants": Restaurant.objects.order_by("-created_at"),
    }
    return render(request, "admin_dashboard/dashboard.html", context)


# ----------------------------------------------------------------------------
# SEO : robots.txt + sitemap.xml (référencement Google / moteurs IA)
# ----------------------------------------------------------------------------
def robots_txt(request):
    host = request.get_host()
    scheme = request.scheme
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /django-admin/",
        "Disallow: /tableau-admin/",
        "Disallow: /resto/",
        "Disallow: /livreur/",
        "Disallow: /panier/",
        "Disallow: /commande/",
        "",
        f"Sitemap: {scheme}://{host}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request):
    """Sitemap dynamique : accueil + fiches restaurants (liens de partage)."""
    base = f"{request.scheme}://{request.get_host()}"
    urls = [
        (f"{base}/", "1.0", "daily"),
        (f"{base}/explorer/", "0.9", "daily"),
    ]
    for r in Restaurant.objects.filter(is_active=True):
        urls.append((f"{base}/r/{r.share_token}/", "0.8", "weekly"))
        urls.append((f"{base}/restaurant/{r.slug}/", "0.7", "weekly"))

    items = "".join(
        f"<url><loc>{loc}</loc><changefreq>{freq}</changefreq>"
        f"<priority>{prio}</priority></url>"
        for loc, prio, freq in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{items}</urlset>"
    )
    return HttpResponse(xml, content_type="application/xml")


# ----------------------------------------------------------------------------
# Vérification des deep links (App Links Android / Universal Links iOS)
# ----------------------------------------------------------------------------
def android_assetlinks(request):
    """/.well-known/assetlinks.json — vérifie l'app Android pour ouvrir les
    liens https://oneeat.cm/... directement dans l'app.
    Remplacez l'empreinte SHA-256 par celle de votre clé de signature de prod
    (keytool -list -v -keystore ...)."""
    sha256 = settings.ANDROID_CERT_SHA256 if hasattr(settings, "ANDROID_CERT_SHA256") else "REMPLACER_PAR_SHA256_SIGNATURE"
    data = [{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": "com.oneeat.app",
            "sha256_cert_fingerprints": [sha256],
        },
    }]
    return JsonResponse(data, safe=False)


def apple_app_site_association(request):
    """/.well-known/apple-app-site-association — Universal Links iOS.
    Remplacez TEAMID par votre Apple Team ID."""
    team_app_id = settings.IOS_APP_ID if hasattr(settings, "IOS_APP_ID") else "TEAMID.com.oneeat.app"
    data = {
        "applinks": {
            "apps": [],
            "details": [{
                "appID": team_app_id,
                "paths": ["/r/*", "/c/*", "/o/*", "/restaurant/*", "/suivi/*"],
            }],
        },
    }
    return JsonResponse(data)


# ---------- Dietetique ----------
def dietetique(request):
    """Espace dietetique : plats equilibres filtres par objectif nutritionnel."""
    from apps.restaurants.models import DIET_GOALS
    goal = request.GET.get("objectif", "")
    sort = request.GET.get("tri", "kcal")
    max_kcal = request.GET.get("max", "")
    dishes = list(Dish.objects.filter(is_available=True, restaurant__is_active=True,
                                      calories__isnull=False)
                  .select_related("restaurant"))
    diet_only = request.GET.get("tous") != "1"
    if diet_only:
        dishes = [d for d in dishes if d.is_diet]
    if goal:
        dishes = [d for d in dishes if goal in d.diet_goals]
    if max_kcal.isdigit():
        dishes = [d for d in dishes if d.calories <= int(max_kcal)]
    keys = {
        "kcal": lambda d: d.calories,
        "proteines": lambda d: -(d.protein_grams or 0),
        "fibres": lambda d: -(d.fiber_grams or 0),
        "prix": lambda d: d.current_price,
    }
    dishes.sort(key=keys.get(sort, keys["kcal"]))
    counts = {slug: 0 for slug, _, _ in DIET_GOALS}
    for d in Dish.objects.filter(is_available=True, is_diet=True, calories__isnull=False):
        for g in d.diet_goals:
            counts[g] = counts.get(g, 0) + 1
    goals = [{"slug": s, "label": l, "hint": h, "count": counts.get(s, 0)} for s, l, h in DIET_GOALS]
    healthy_restos = Restaurant.objects.filter(is_active=True, categories__slug="healthy").distinct()
    return render(request, "client/dietetique.html", {
        "dishes": dishes, "goals": goals, "goal": goal, "sort": sort, "max_kcal": max_kcal,
        "diet_only": diet_only, "healthy_restos": healthy_restos,
        "cart_count": _cart_count(request),
    })


def photo_credits(request):
    """Credits des photos de plats (licences Creative Commons)."""
    path = settings.MEDIA_ROOT / "dishes" / "demo" / "CREDITS.json"
    try:
        credits = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        credits = {}
    return render(request, "legal/credits.html", {"credits": sorted(credits.items())})
