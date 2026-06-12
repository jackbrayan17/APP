import json

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Sum, Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.restaurants.models import Restaurant, Category, Dish
from apps.orders.models import Order
from apps.accounts.models import User
from .models import ActivityLog, Notification, PushSubscription


def _cart_count(request):
    cart = request.session.get("cart", {})
    return sum(i.get("qty", 0) for i in cart.values())


def home(request):
    cat_slug = request.GET.get("cat")
    categories = Category.objects.all()
    restaurants = Restaurant.objects.filter(is_active=True).prefetch_related("categories")
    if cat_slug and cat_slug != "tous":
        restaurants = restaurants.filter(categories__slug=cat_slug).distinct()

    context = {
        "categories": categories,
        "featured": Restaurant.objects.filter(is_active=True, is_featured=True)[:8],
        "popular": Restaurant.objects.filter(is_active=True).order_by("-orders_count", "-rating")[:8],
        "restaurants": restaurants.order_by("-is_featured", "-rating"),
        "active_cat": cat_slug or "tous",
        "cart_count": _cart_count(request),
    }
    return render(request, "client/home.html", context)


def explore(request):
    q = request.GET.get("q", "").strip()
    hood = request.GET.get("hood", "")
    restaurants = Restaurant.objects.filter(is_active=True)
    if q:
        restaurants = restaurants.filter(
            Q(name__icontains=q) | Q(dishes__name__icontains=q) | Q(bio__icontains=q)).distinct()
    if hood and hood != "Tous":
        restaurants = restaurants.filter(neighborhood=hood)

    hoods = (Restaurant.objects.filter(is_active=True)
             .exclude(neighborhood="").values_list("neighborhood", flat=True).distinct())
    context = {
        "restaurants": restaurants.order_by("-rating"),
        "q": q, "hood": hood or "Tous",
        "hoods": list(hoods),
        "cart_count": _cart_count(request),
    }
    return render(request, "client/explore.html", context)


def search_api(request):
    q = request.GET.get("q", "").strip()
    results = []
    if q:
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
        "theme_color": "#FF6B1A",
        "lang": "fr",
        "categories": ["food", "shopping", "lifestyle"],
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png",
             "purpose": "any maskable"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "any maskable"},
        ],
        "shortcuts": [
            {"name": "Mes commandes", "url": "/commandes/"},
            {"name": "Explorer", "url": "/explorer/"},
        ],
    }
    return JsonResponse(data)


def service_worker(request):
    sw = render_to_string("pwa/sw.js")
    resp = HttpResponse(sw, content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache"
    return resp


def offline(request):
    return render(request, "pwa/offline.html")


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
    last_30 = now - timezone.timedelta(days=30)

    top_dishes = (Dish.objects.order_by("-orders_count")[:10])
    top_rated = (Restaurant.objects.filter(rating_count__gt=0)
                 .order_by("-rating", "-rating_count")[:10])
    orders_by_status = (Order.objects.values("status")
                        .annotate(n=Count("id")).order_by("-n"))

    # Traffic des 14 derniers jours (logs)
    traffic = []
    for i in range(13, -1, -1):
        day = (now - timezone.timedelta(days=i)).date()
        count = ActivityLog.objects.filter(created_at__date=day).count()
        traffic.append({"day": day.strftime("%d/%m"), "count": count})

    context = {
        "stats": {
            "users": User.objects.count(),
            "clients": User.objects.filter(role=User.Role.CLIENT).count(),
            "restaurants": Restaurant.objects.count(),
            "drivers": User.objects.filter(role=User.Role.DRIVER).count(),
            "orders": Order.objects.count(),
            "orders_30": Order.objects.filter(created_at__gte=last_30).count(),
            "revenue": Order.objects.filter(status=Order.Status.DELIVERED)
                       .aggregate(s=Sum("total"))["s"] or 0,
            "active_orders": Order.objects.filter(
                status__in=[Order.Status.PREPARING, Order.Status.ON_THE_WAY]).count(),
        },
        "top_dishes": top_dishes,
        "top_rated": top_rated,
        "orders_by_status": orders_by_status,
        "recent_orders": Order.objects.select_related("restaurant", "customer")[:15],
        "recent_logs": ActivityLog.objects.all()[:25],
        "traffic": traffic,
        "traffic_json": json.dumps(traffic),
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
