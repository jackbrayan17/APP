from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "phone", "city", "is_verified", "is_staff")
    list_filter = ("role", "is_verified", "is_staff", "city")
    search_fields = ("username", "email", "first_name", "last_name", "phone")
    fieldsets = UserAdmin.fieldsets + (
        ("ONE EAT", {"fields": ("role", "phone", "avatar", "city", "address",
                                "lat", "lng", "is_verified")}),
    )
