from django.contrib import admin
from .models import Order, OrderItem, Review


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "customer", "restaurant", "driver", "status",
                    "total", "created_at")
    list_filter = ("status", "payment_method", "restaurant")
    search_fields = ("number", "customer__username", "restaurant__name")
    inlines = [OrderItemInline]
    readonly_fields = ("number", "share_token")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "customer", "rating", "driver_rating", "created_at")
    list_filter = ("rating", "restaurant")
    search_fields = ("restaurant__name", "comment")
