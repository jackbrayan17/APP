from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from . import views

app_name = "api"

router = DefaultRouter()
router.register("restaurants", views.RestaurantViewSet, basename="restaurant")
router.register("categories", views.CategoryViewSet, basename="category")
router.register("orders", views.OrderViewSet, basename="order")

urlpatterns = [
    path("", include(router.urls)),

    # Auth & compte
    path("auth/login/", views.api_login, name="login"),
    path("auth/register/", views.api_register, name="register"),
    path("auth/logout/", views.api_logout, name="logout"),
    path("auth/token/", obtain_auth_token, name="token"),
    path("me/", views.api_me, name="me"),

    # Commandes client
    path("checkout/", views.api_checkout, name="checkout"),
    path("orders/<str:number>/review/", views.api_review_order, name="review_order"),
    path("promo/validate/", views.api_validate_promo, name="validate_promo"),

    # Favoris
    path("favorites/", views.api_favorites, name="favorites"),
    path("favorites/toggle/", views.api_favorite_toggle, name="favorite_toggle"),

    # Livreur
    path("delivery/nearby/", views.nearby_orders, name="nearby_orders"),
    path("delivery/position/", views.api_driver_position, name="driver_position"),
    path("delivery/orders/<str:number>/accept/", views.api_driver_accept, name="driver_accept"),
    path("delivery/orders/<str:number>/status/", views.api_driver_status, name="driver_status"),

    # Partage public (deep links)
    path("share/restaurant/<str:token>/", views.api_share_restaurant, name="share_restaurant"),
    path("share/order/<str:token>/", views.api_share_order, name="share_order"),

    # Notifications push natives (FCM)
    path("devices/register/", views.api_register_device, name="register_device"),
    path("devices/unregister/", views.api_unregister_device, name="unregister_device"),
]
