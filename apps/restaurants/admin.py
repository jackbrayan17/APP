from django.contrib import admin
from .models import Category, Restaurant, RestaurantPhoto, MenuSection, Dish


class DishInline(admin.TabularInline):
    model = Dish
    extra = 1
    fields = ("name", "section", "price", "prep_time", "is_available", "is_popular")


class MenuSectionInline(admin.TabularInline):
    model = MenuSection
    extra = 1


class PhotoInline(admin.TabularInline):
    model = RestaurantPhoto
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("emoji", "name", "order", "is_nav")
    list_editable = ("order", "is_nav")


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("name", "neighborhood", "tagline", "rating", "rating_count",
                    "is_pro", "is_premium", "is_featured", "is_active")
    list_filter = ("is_pro", "is_premium", "is_featured", "is_active", "neighborhood")
    search_fields = ("name", "owner__username")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MenuSectionInline, DishInline, PhotoInline]
    filter_horizontal = ("categories",)


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "section", "price", "prep_time",
                    "is_available", "is_popular", "orders_count")
    list_filter = ("is_available", "is_popular", "restaurant")
    search_fields = ("name", "restaurant__name")


@admin.register(MenuSection)
class MenuSectionAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "order")
