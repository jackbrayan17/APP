from collections import defaultdict

from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import F, Q, Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from apps.core.geo import haversine_km
from apps.core.routing import road_route, tracking_payload
from apps.restaurants.models import Restaurant, Category, Dish
from apps.orders.models import Order, OrderItem, Review
from apps.promotions.models import PromoCode, PromoCodeRedemption
from apps.delivery.models import DriverProfile
from apps.orders.services import CheckoutError, create_orders
from apps.orders.workflow import (TransitionError, driver_advance, driver_claim, mission_offers)
from .serializers import (
    RestaurantSerializer, RestaurantDetailSerializer, CategorySerializer,
    DishSerializer, OrderSerializer, ReviewSerializer, UserSerializer,
    RegisterSerializer, CheckoutSerializer, ReviewCreateSerializer,
    DriverPositionSerializer, DeviceTokenSerializer,
)


def _tracking_response(order, request=None):
    payload = tracking_payload(order)
    payload["order"] = OrderSerializer(order, context={"request": request}).data
    return payload


def _can_track(user, order):
    return (
        user.is_staff
        or order.customer_id == user.id
        or order.driver_id == user.id
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
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(bio__icontains=q) |
                Q(dishes__name__icontains=q) |
                Q(dishes__description__icontains=q)
            ).distinct()
        return qs

    @action(detail=True, methods=["get"])
    def reviews(self, request, slug=None):
        resto = self.get_object()
        return Response(ReviewSerializer(resto.reviews.all()[:30], many=True).data)


class DishViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DishSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = (Dish.objects.filter(is_available=True, restaurant__is_active=True)
              .select_related("restaurant", "section", "category")
              .order_by("-is_popular", "-orders_count", "name"))
        q = self.request.query_params.get("q")
        cat = self.request.query_params.get("cat")
        restaurant = self.request.query_params.get("restaurant")
        if q:
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(description__icontains=q) |
                Q(restaurant__name__icontains=q)
            )
        if cat and cat != "tous":
            qs = qs.filter(Q(category__slug=cat) | Q(restaurant__categories__slug=cat)).distinct()
        if restaurant:
            qs = qs.filter(restaurant__slug=restaurant)
        return qs


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
    out = []
    for o in mission_offers(prof):
        data = OrderSerializer(o).data
        data["distance_km"] = o.distance_km
        if o.distance_km is not None:
            route = road_route(prof.current_lat, prof.current_lng,
                               o.restaurant.lat, o.restaurant.lng)
            data["route_distance_km"] = route["distance_km"]
            data["route_duration_min"] = route["duration_min"]
            data["route_provider"] = route["provider"]
        out.append(data)
    return Response(out)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_driver_orders(request):
    """Commandes prises par le livreur + totaux de son tableau de bord."""
    prof = DriverProfile.objects.filter(user=request.user).first()
    if not prof:
        return Response({"detail": "Profil livreur introuvable"}, status=403)

    orders = (Order.objects.filter(driver=request.user)
              .select_related("restaurant", "customer")
              .prefetch_related("items")
              .order_by("-created_at"))
    stats = orders.aggregate(
        total_orders=Count("id"),
        total_amount=Sum("delivery_fee"),
    )
    delivered = orders.filter(status=Order.Status.DELIVERED).aggregate(
        delivered_orders=Count("id"),
        delivered_amount=Sum("delivery_fee"),
    )
    active_orders = orders.filter(status__in=[
        Order.Status.PICKED_UP, Order.Status.ON_THE_WAY
    ]).count()
    return Response({
        "total_orders": stats["total_orders"] or 0,
        "active_orders": active_orders,
        "delivered_orders": delivered["delivered_orders"] or 0,
        "total_amount": stats["total_amount"] or 0,
        "delivered_amount": delivered["delivered_amount"] or 0,
        "orders": OrderSerializer(orders[:50], many=True).data,
    })


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

    qty_by_dish = {}
    for it in data["items"]:
        qty_by_dish[it["dish_id"]] = qty_by_dish.get(it["dish_id"], 0) + it["quantity"]
    dishes = Dish.objects.filter(id__in=qty_by_dish.keys()).select_related("restaurant")
    lines = [(d, qty_by_dish[d.id]) for d in dishes]
    user = request.user
    try:
        created = create_orders(
            user, lines,
            address=data.get("delivery_address") or user.address or "",
            lat=data.get("delivery_lat") if data.get("delivery_lat") is not None else user.lat,
            lng=data.get("delivery_lng") if data.get("delivery_lng") is not None else user.lng,
            payment_method=data.get("payment_method", "cash"),
            payment_phone=data.get("payment_phone") or user.phone or "",
            notes=data.get("notes", ""), promo_code=data.get("promo_code", ""))
    except CheckoutError as exc:
        return Response({"detail": str(exc)}, status=400)

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
    # Répercute la position sur les commandes actives du livreur en temps réel.
    updated = Order.objects.filter(driver=request.user).exclude(
        status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED]).update(
        driver_lat=prof.current_lat, driver_lng=prof.current_lng)
    return Response({
        "ok": True,
        "lat": prof.current_lat,
        "lng": prof.current_lng,
        "active_orders_updated": updated,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_driver_accept(request, number):
    prof = DriverProfile.objects.filter(user=request.user).first()
    if not prof:
        return Response({"detail": "Profil livreur introuvable."}, status=403)
    order = get_object_or_404(Order, number=number)
    try:
        order = driver_claim(order.id, request.user)
    except TransitionError as exc:
        return Response({"detail": str(exc)}, status=409)
    return Response(OrderSerializer(order).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_order_tracking(request, number):
    """Tracking temps réel authentifié avec route routière et position livreur."""
    order = get_object_or_404(
        Order.objects.select_related("restaurant", "driver", "driver__driver_profile")
        .prefetch_related("items"),
        number=number,
    )
    if not _can_track(request.user, order):
        return Response({"detail": "Suivi non autorisé."}, status=403)
    return Response(_tracking_response(order, request))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_driver_status(request, number):
    """Le livreur fait avancer le statut (picked_up -> on_the_way -> delivered)."""
    order = get_object_or_404(Order, number=number, driver=request.user)
    try:
        order = driver_advance(order, request.user, request.data.get("status"))
    except TransitionError as exc:
        return Response({"detail": str(exc)}, status=400)
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


@api_view(["GET"])
@permission_classes([AllowAny])
def api_share_order_tracking(request, token):
    order = get_object_or_404(
        Order.objects.select_related("restaurant", "driver", "driver__driver_profile")
        .prefetch_related("items"),
        share_token=token,
    )
    return Response(_tracking_response(order, request))


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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_favorites(request):
    """Liste des restaurants favoris de l'utilisateur."""
    from apps.restaurants.models import Favorite
    restos = [f.restaurant for f in Favorite.objects.filter(user=request.user)
              .select_related("restaurant")]
    return Response(RestaurantSerializer(restos, many=True,
                                         context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_favorite_toggle(request):
    """Ajoute / retire un restaurant des favoris. Body: {slug}."""
    from apps.restaurants.models import Favorite
    slug = request.data.get("slug")
    resto = get_object_or_404(Restaurant, slug=slug)
    fav = Favorite.objects.filter(user=request.user, restaurant=resto).first()
    if fav:
        fav.delete()
        return Response({"is_favorite": False})
    Favorite.objects.create(user=request.user, restaurant=resto)
    return Response({"is_favorite": True}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_unregister_device(request):
    from apps.core.models import DevicePushToken
    tok = request.data.get("token", "")
    DevicePushToken.objects.filter(token=tok, user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
