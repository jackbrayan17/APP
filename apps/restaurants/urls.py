from django.urls import path
from . import views

app_name = "restaurants"

urlpatterns = [
    # Dashboard restaurant
    path("resto/", views.dashboard, name="dashboard"),
    path("resto/demarrage/", views.onboarding, name="onboarding"),
    path("resto/menu/", views.menu_manage, name="menu"),
    path("resto/menu/plat/", views.dish_save, name="dish_save"),
    path("resto/menu/plat/<int:dish_id>/supprimer/", views.dish_delete, name="dish_delete"),
    path("resto/menu/section/", views.section_save, name="section_save"),
    path("resto/personnaliser/", views.customize, name="customize"),
    path("resto/commandes/", views.orders_manage, name="orders"),
    path("resto/commandes/<int:order_id>/statut/", views.order_set_status, name="order_status"),
    path("resto/livreurs/", views.drivers_manage, name="drivers"),
    path("resto/promos/", views.promos_manage, name="promos"),
    # Public
    path("restaurant/<slug:slug>/", views.restaurant_detail, name="detail"),
    path("r/<str:token>/", views.restaurant_share, name="share"),
]
