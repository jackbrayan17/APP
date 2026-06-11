from rest_framework import serializers

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
