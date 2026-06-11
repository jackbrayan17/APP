from django.contrib import admin
from .models import Promotion, InfluencerProfile, PromoCode, PromoCodeRedemption


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ("title", "restaurant", "discount_type", "discount_value",
                    "starts_at", "ends_at", "is_active")
    list_filter = ("discount_type", "is_active", "restaurant")
    filter_horizontal = ("dishes",)


@admin.register(InfluencerProfile)
class InfluencerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "handle", "followers", "reach_score",
                    "total_redemptions", "total_revenue")
    search_fields = ("handle", "user__username")


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "influencer", "restaurant", "percent", "uses",
                    "max_uses", "is_active")
    list_filter = ("is_active", "restaurant")
    search_fields = ("code",)


@admin.register(PromoCodeRedemption)
class PromoCodeRedemptionAdmin(admin.ModelAdmin):
    list_display = ("promo_code", "user", "discount_amount", "created_at")
