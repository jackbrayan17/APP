from django.contrib.auth import authenticate
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from apps.core.geo import haversine_km
from apps.restaurants.models import Restaurant, Category, Dish
from apps.orders.models import Order
from apps.delivery.models import DriverProfile
from .serializers import (
    RestaurantSerializer, RestaurantDetailSerializer, CategorySerializer,
    DishSerializer, OrderSerializer, ReviewSerializer,
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
                     "name": user.display_name})


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
