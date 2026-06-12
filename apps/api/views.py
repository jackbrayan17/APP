from collections import defaultdict

from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from apps.core.geo import haversine_km
from apps.restaurants.models import Restaurant, Category, Dish
from apps.orders.models import Order, OrderItem, Review
from apps.promotions.models import PromoCode, PromoCodeRedemption
from apps.delivery.models import DriverProfile
from .serializers import (
    RestaurantSerializer, RestaurantDetailSerializer, CategorySerializer,
    DishSerializer, OrderSerializer, ReviewSerializer, UserSerializer,
    RegisterSerializer, CheckoutSerializer, ReviewCreateSerializer,
    DriverPositionSerializer, DeviceTokenSerializer,
)


@api_view(["POST"])
@permission_classes([AllowAny])
def api_login(request):
    """Auth token pour clients mobiles / PWA."""
    identifier = request.data.get("email", "")
    password = request.data.get("password", "")
    from apps.accounts.models import User
    user = authenticate(username=identifier, password=password)
    if user is None:
        u = User.objects.filter(email__iexact=identifier).first()
        if u:
            user = authenticate(username=u.username, password=password)
    if user is None:
        return Response({"detail": "Identifiants invalides"}, status=401)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "role": user.role,
                     "name": user.display_name,
                     "user": UserSerializer(user, context={"request": request}).data})


@api_view(["POST"])
@permission_classes([AllowAny])
def api_register(request):
    """Inscription client depuis l'app mobile -> renvoie un token."""
    ser = RegisterSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    user = ser.save()
    token, _ = Token.objects.get_or_create(user=user)
    return Response(
        {"token": token.key, "role": user.role, "name": user.display_name,
         "user": UserSerializer(user, context={"request": request}).data},
        status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def api_me(request):
    """Profil de l'utilisateur connecté (lecture / mise à jour)."""
    if request.method == "PATCH":
        ser = UserSerializer(request.user, data=request.data, partial=True,
                             context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)
    return Response(UserSerializer(request.user, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_logout(request):
    """Révoque le token courant (déconnexion sécurisée côté serveur)."""
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


class RestaurantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Restaurant.objects.filter(is_active=True)
    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return RestaurantDetailSerializer
        return RestaurantSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        cat = self.request.query_params.get("cat")
        hood = self.request.query_params.get("hood")
        q = self.request.query_params.get("q")
        if cat and cat != "tous":
            qs = qs.filter(categories__slug=cat).distinct()
        if hood:
            qs = qs.filter(neighborhood=hood)
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    @action(detail=True, methods=["get"])
    def reviews(self, request, slug=None):
        resto = self.get_object()
        return Response(ReviewSerializer(resto.reviews.all()[:30], many=True).data)


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "number"

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).select_related("restaurant")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def nearby_orders(request):
    """Commandes pretes dans le perimetre du livreur (10km)."""
    prof = DriverProfile.objects.filter(user=request.user).first()
    if not prof:
        return Response({"detail": "Profil livreur introuvable"}, status=403)
    orders = Order.objects.filter(status=Order.Status.READY, driver__isnull=True)
    out = []
    for o in orders.select_related("restaurant"):
        d = None
        if prof.current_lat and o.restaurant.lat:
            d = haversine_km(prof.current_lat, prof.current_lng,
                             o.restaurant.lat, o.restaurant.lng)
            if d is None or d > prof.service_radius_km:
                continue
        data = OrderSerializer(o).data
        data["distance_km"] = round(d, 1) if d else None
        out.append(data)
    return Response(out)


# ----------------------------------------------------------------------------
# Checkout : crée une commande par restaurant à partir d'un panier JSON
# ----------------------------------------------------------------------------
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def api_checkout(request):
    ser = CheckoutSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data

    # Charger les plats disponibles
    qty_by_dish = {it["dish_id"]: it["quantity"] for it in data["items"]}
    dishes = {d.id: d for d in Dish.objects.filter(
        id__in=qty_by_dish.keys(), is_available=True).select_related("restaurant")}
    if not dishes:
        return Response({"detail": "Aucun plat disponible dans le panier."}, status=400)

    by_resto = defaultdict(list)
    for did, dish in dishes.items():
        by_resto[dish.restaurant_id].append((dish, qty_by_dish[did]))

    promo_code_str = (data.get("promo_code") or "").strip().upper()
    user = request.user
    created = []

    for rid, entries in by_resto.items():
        resto = entries[0][0].restaurant
        order = Order.objects.create(
            customer=user, restaurant=resto,
            delivery_address=data.get("delivery_address") or user.address or "",
            payment_method=data.get("payment_method", "cash"),
            delivery_fee=resto.delivery_fee,
            delivery_lat=data.get("delivery_lat") if data.get("delivery_lat") is not None else user.lat,
            delivery_lng=data.get("delivery_lng") if data.get("delivery_lng") is not None else user.lng,
            notes=data.get("notes", ""),
        )
        for dish, qty in entries:
            OrderItem.objects.create(
                order=order, dish=dish, name=dish.name,
                unit_price=dish.current_price, quantity=qty)
            Dish.objects.filter(id=dish.id).update(orders_count=F("orders_count") + qty)
        order.recompute_totals()

        if promo_code_str:
            code = PromoCode.objects.filter(code=promo_code_str, restaurant=resto).first()
            if code and code.is_valid:
                disc = code.discount_for(order.items_total)
                order.discount = disc
                order.promo_code = code.code
                order.recompute_totals()
                code.uses = F("uses") + 1
                code.save(update_fields=["uses"])
                PromoCodeRedemption.objects.create(
                    promo_code=code, user=user, order=order, discount_amount=disc)
                code.refresh_from_db()
                code.influencer.recompute_score()

        resto.orders_count = resto.orders.count()
        resto.save(update_fields=["orders_count"])
        created.append(order)

        from apps.core.services import notify
        notify(resto.owner, f"Nouvelle commande {order.number}",
               f"{order.item_count} article(s) — {order.total} FCFA",
               url="/resto/commandes/")

    return Response(
        {"orders": OrderSerializer(created, many=True).data,
         "count": len(created)},
        status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def api_validate_promo(request):
    """Valide un code promo pour un restaurant (slug) sans l'utiliser."""
    code_str = (request.query_params.get("code") or "").strip().upper()
    slug = request.query_params.get("restaurant")
    if not code_str or not slug:
        return Response({"valid": False, "detail": "Paramètres manquants."}, status=400)
    resto = Restaurant.objects.filter(slug=slug).first()
    code = PromoCode.objects.filter(code=code_str, restaurant=resto).first()
    if not code or not code.is_valid:
        return Response({"valid": False, "detail": "Code invalide ou expiré."})
    return Response({"valid": True, "code": code.code, "percent": code.percent})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_review_order(request, number):
    """Crée un avis après livraison."""
    order = get_object_or_404(Order, number=number, customer=request.user)
    if not order.can_review:
        return Response({"detail": "Cette commande ne peut pas être notée."}, status=400)
    ser = ReviewCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    Review.objects.create(
        order=order, customer=request.user, restaurant=order.restaurant,
        driver=order.driver,
        rating=ser.validated_data.get("rating", 5),
        driver_rating=ser.validated_data.get("driver_rating"),
        comment=ser.validated_data.get("comment", ""),
    )
    return Response({"ok": True}, status=status.HTTP_201_CREATED)


# ----------------------------------------------------------------------------
# Livreur : position temps réel + cycle de course
# ----------------------------------------------------------------------------
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_driver_position(request):
    prof = DriverProfile.objects.filter(user=request.user).first()
    if not prof:
        return Response({"detail": "Profil livreur introuvable."}, status=403)
    ser = DriverPositionSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    prof.current_lat = ser.validated_data["lat"]
    prof.current_lng = ser.validated_data["lng"]
    if "is_available" in ser.validated_data:
        prof.is_available = ser.validated_data["is_available"]
    prof.last_seen = timezone.now()
    prof.save(update_fields=["current_lat", "current_lng", "is_available", "last_seen"])
    # Répercute la position sur les commandes en cours du livreur
    Order.objects.filter(driver=request.user, status=Order.Status.ON_THE_WAY).update(
        driver_lat=prof.current_lat, driver_lng=prof.current_lng)
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_driver_accept(request, number):
    prof = DriverProfile.objects.filter(user=request.user).first()
    if not prof:
        return Response({"detail": "Profil livreur introuvable."}, status=403)
    order = get_object_or_404(Order, number=number)
    if order.driver_id:
        return Response({"detail": "Course déjà prise."}, status=409)
    order.driver = request.user
    order.status = Order.Status.PICKED_UP
    order.save(update_fields=["driver", "status"])
    from apps.core.services import notify
    notify(order.customer, f"Commande {order.number} prise en charge",
           f"{request.user.display_name} récupère votre commande.",
           url=f"/suivi/{order.number}/")
    return Response(OrderSerializer(order).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_driver_status(request, number):
    """Le livreur fait avancer le statut (picked_up -> on_the_way -> delivered)."""
    order = get_object_or_404(Order, number=number, driver=request.user)
    new_status = request.data.get("status")
    allowed = {Order.Status.ON_THE_WAY, Order.Status.DELIVERED}
    if new_status not in allowed:
        return Response({"detail": "Statut non autorisé."}, status=400)
    order.status = new_status
    if new_status == Order.Status.DELIVERED:
        order.delivered_at = timezone.now()
        prof = DriverProfile.objects.filter(user=request.user).first()
        if prof:
            DriverProfile.objects.filter(pk=prof.pk).update(
                deliveries_count=F("deliveries_count") + 1)
    order.save()
    from apps.core.services import notify
    notify(order.customer, f"Commande {order.number} — {order.status_label}",
           "Votre commande arrive !" if new_status == Order.Status.ON_THE_WAY
           else "Votre commande a été livrée. Bon appétit !",
           url=f"/suivi/{order.number}/")
    return Response(OrderSerializer(order).data)


# ----------------------------------------------------------------------------
# Liens de partage publics (aperçu deep-link dans l'app + SEO)
# ----------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([AllowAny])
def api_share_restaurant(request, token):
    resto = get_object_or_404(Restaurant, share_token=token, is_active=True)
    return Response(RestaurantDetailSerializer(resto, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def api_share_order(request, token):
    order = get_object_or_404(Order, share_token=token)
    return Response(OrderSerializer(order).data)


# ----------------------------------------------------------------------------
# Notifications push natives (FCM)
# ----------------------------------------------------------------------------
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_register_device(request):
    from apps.core.models import DevicePushToken
    ser = DeviceTokenSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    tok = ser.validated_data["token"]
    DevicePushToken.objects.update_or_create(
        token=tok,
        defaults={
            "user": request.user,
            "platform": ser.validated_data.get("platform", "android"),
            "device_id": ser.validated_data.get("device_id", ""),
            "app_version": ser.validated_data.get("app_version", ""),
            "is_active": True,
        },
    )
    return Response({"ok": True}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_unregister_device(request):
    from apps.core.models import DevicePushToken
    tok = request.data.get("token", "")
    DevicePushToken.objects.filter(token=tok, user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
