from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.delivery.models import DriverProfile
from apps.orders.models import Order
from apps.promotions.models import Promotion
from .models import Restaurant, Category, MenuSection, Dish, RestaurantPhoto


def _cart_count(request):
    return sum(i.get("qty", 0) for i in request.session.get("cart", {}).values())


# ---------------- Cote client ----------------
def restaurant_detail(request, slug):
    resto = get_object_or_404(Restaurant.objects.prefetch_related("sections", "dishes"),
                              slug=slug, is_active=True)
    sections = resto.sections.prefetch_related("dishes").all()
    unsectioned = resto.dishes.filter(section__isnull=True, is_available=True)
    context = {
        "resto": resto,
        "sections": sections,
        "unsectioned": unsectioned,
        "reviews": resto.reviews.select_related("customer")[:10],
        "cart_count": _cart_count(request),
    }
    return render(request, "client/restaurant_detail.html", context)


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
    context = {
        "resto": resto,
        "stats": {
            "orders_today": orders.filter(created_at__date=timezone.now().date()).count(),
            "active": orders.filter(status__in=[
                Order.Status.PENDING, Order.Status.PREPARING, Order.Status.READY]).count(),
            "dishes": resto.dishes.count(),
            "drivers": resto.drivers.count(),
            "rating": resto.rating,
            "revenue": sum(o.total for o in orders.filter(status=Order.Status.DELIVERED)),
        },
        "recent_orders": orders.select_related("customer")[:10],
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
    context = {
        "resto": resto,
        "sections": resto.sections.prefetch_related("dishes").all(),
        "categories": Category.objects.all(),
        "dishes": resto.dishes.all(),
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
    dish.price = int(request.POST.get("price") or 0)
    dish.prep_time = int(request.POST.get("prep_time") or 20)
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
def orders_manage(request):
    resto = _owner_resto(request)
    if not resto:
        return redirect("restaurants:onboarding")
    status = request.GET.get("status", "")
    orders = Order.objects.filter(restaurant=resto).select_related("customer", "driver")
    if status:
        orders = orders.filter(status=status)
    return render(request, "restaurant_dashboard/orders.html",
                  {"resto": resto, "orders": orders, "status": status,
                   "statuses": Order.Status.choices})


@login_required
@require_POST
def order_set_status(request, order_id):
    resto = _owner_resto(request)
    order = get_object_or_404(Order, id=order_id, restaurant=resto)
    new_status = request.POST.get("status")
    if new_status in dict(Order.Status.choices):
        order.status = new_status
        if new_status == Order.Status.CONFIRMED and not order.confirmed_at:
            order.confirmed_at = timezone.now()
        order.save(update_fields=["status", "confirmed_at"])
        from apps.core.services import notify
        notify(order.customer, f"Commande {order.number}",
               f"Statut : {order.get_status_display()}", url=f"/commande/{order.number}/")
    # assignation livreur
    driver_id = request.POST.get("driver")
    if driver_id:
        order.driver = User.objects.filter(id=driver_id).first()
        order.save(update_fields=["driver"])
    return redirect("restaurants:orders")


@login_required
def drivers_manage(request):
    resto = _owner_resto(request)
    if not resto:
        return redirect("restaurants:onboarding")
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if user:
            user.role = User.Role.DRIVER
            user.save(update_fields=["role"])
            DriverProfile.objects.update_or_create(
                user=user, defaults={"restaurant": resto,
                                      "phone": request.POST.get("phone", "")})
            messages.success(request, f"{user.display_name} ajoute comme livreur.")
        else:
            messages.error(request, "Aucun utilisateur avec cet email. Demandez-lui de s'inscrire.")
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
            banner_color=request.POST.get("banner_color", "#E53935"),
        )
        dish_ids = request.POST.getlist("dishes")
        promo.dishes.set(resto.dishes.filter(id__in=dish_ids))
        messages.success(request, "Promotion lancee !")
        return redirect("restaurants:promos")
    return render(request, "restaurant_dashboard/promos.html",
                  {"resto": resto, "promos": resto.promotions.all(),
                   "dishes": resto.dishes.all()})
