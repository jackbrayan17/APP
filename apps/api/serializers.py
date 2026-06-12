from rest_framework import serializers

from apps.accounts.models import User
from apps.restaurants.models import Restaurant, Category, MenuSection, Dish
from apps.orders.models import Order, OrderItem, Review
from apps.promotions.models import Promotion, PromoCode


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "emoji", "is_nav"]


class DishSerializer(serializers.ModelSerializer):
    current_price = serializers.IntegerField(read_only=True)
    has_promo = serializers.BooleanField(read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Dish
        fields = ["id", "name", "description", "price", "current_price", "has_promo",
                  "prep_time", "image", "is_available", "is_popular", "section"]

    def get_image(self, obj):
        return obj.image.url if obj.image else ""


class MenuSectionSerializer(serializers.ModelSerializer):
    dishes = DishSerializer(many=True, read_only=True)

    class Meta:
        model = MenuSection
        fields = ["id", "name", "order", "dishes"]


class RestaurantSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    delivery_time_label = serializers.CharField(read_only=True)

    class Meta:
        model = Restaurant
        fields = ["id", "name", "slug", "share_token", "tagline", "bio",
                  "logo", "cover_image", "neighborhood", "city", "lat", "lng",
                  "rating", "rating_count", "delivery_fee", "delivery_time_label",
                  "brand_color", "is_pro", "is_premium", "is_featured"]

    def get_logo(self, obj):
        return obj.logo.url if obj.logo else ""

    def get_cover_image(self, obj):
        return obj.cover_image.url if obj.cover_image else ""


class RestaurantDetailSerializer(RestaurantSerializer):
    sections = MenuSectionSerializer(many=True, read_only=True)

    class Meta(RestaurantSerializer.Meta):
        fields = RestaurantSerializer.Meta.fields + ["sections"]


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "name", "unit_price", "quantity", "line_total"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    status_label = serializers.CharField(read_only=True)

    class Meta:
        model = Order
        fields = ["id", "number", "share_token", "restaurant_name", "status",
                  "status_label", "items_total", "delivery_fee", "discount", "total",
                  "delivery_address", "delivery_lat", "delivery_lng",
                  "driver_lat", "driver_lng", "items", "created_at"]


class ReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.display_name", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "rating", "driver_rating", "comment", "customer_name", "created_at"]


class PromotionSerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)
    is_live = serializers.BooleanField(read_only=True)

    class Meta:
        model = Promotion
        fields = ["id", "title", "description", "discount_type", "discount_value",
                  "label", "banner_color", "starts_at", "ends_at", "is_live"]


# ----------------------------------------------------------------------------
# Comptes / profil
# ----------------------------------------------------------------------------
class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="display_name", read_only=True)
    initials = serializers.CharField(read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "name",
                  "initials", "role", "phone", "city", "address", "lat", "lng",
                  "avatar", "is_verified"]
        read_only_fields = ["id", "username", "role", "is_verified"]

    def get_avatar(self, obj):
        return obj.avatar.url if obj.avatar else ""


class RegisterSerializer(serializers.Serializer):
    """Inscription client depuis l'app mobile."""
    name = serializers.CharField(max_length=140)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(min_length=6, write_only=True)
    city = serializers.CharField(max_length=80, required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet email.")
        return value

    def create(self, validated):
        name = validated["name"].strip()
        parts = name.split(" ", 1)
        user = User.objects.create_user(
            username=validated["email"],
            email=validated["email"],
            password=validated["password"],
            first_name=parts[0],
            last_name=parts[1] if len(parts) > 1 else "",
            phone=validated.get("phone", ""),
            city=validated.get("city") or "Douala",
            role=User.Role.CLIENT,
        )
        return user


# ----------------------------------------------------------------------------
# Checkout / création de commande
# ----------------------------------------------------------------------------
class CartItemSerializer(serializers.Serializer):
    dish_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)


class CheckoutSerializer(serializers.Serializer):
    items = CartItemSerializer(many=True)
    delivery_address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    delivery_lat = serializers.FloatField(required=False, allow_null=True)
    delivery_lng = serializers.FloatField(required=False, allow_null=True)
    payment_method = serializers.ChoiceField(
        choices=[c[0] for c in Order.Payment.choices], default="cash")
    promo_code = serializers.CharField(max_length=24, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Le panier est vide.")
        return value


class ReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, default=5)
    driver_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True)


class DriverPositionSerializer(serializers.Serializer):
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    is_available = serializers.BooleanField(required=False)


class DeviceTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=300)
    platform = serializers.ChoiceField(choices=["android", "ios", "web"], default="android")
    device_id = serializers.CharField(max_length=120, required=False, allow_blank=True)
    app_version = serializers.CharField(max_length=20, required=False, allow_blank=True)
