from django.contrib import admin
from .models import DriverProfile


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "restaurant", "vehicle", "is_available",
                    "rating", "deliveries_count")
    list_filter = ("is_available", "vehicle", "restaurant")
    search_fields = ("user__username",)
